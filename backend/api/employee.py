from typing import Optional, Any, List, Dict
import logging
import re

from starlette.concurrency import run_in_threadpool

try:
    from backend.utils.utils import is_employer_hiring_query
    from backend.services.ranking_service import get_employer_session
    from backend.services.search_client import search_jobs
    from backend.services.search_parser import parse_search_query, resolve_state_id
    from backend.services.platform_api import get_closing_soon_jobs, get_nearby_organizations
    from backend.config.config import MAX_RESULTS
    from backend.services import user_data_service
    from backend.recommendation.recommendation_service import recommendation_service
    from backend.recommendation.mappers import to_candidate_profile_from_api
    from backend.utils.session_state import get_pagination_state, set_pagination_state, clear_pagination_state, set_recommendation_session
except ModuleNotFoundError:
    from utils.utils import is_employer_hiring_query
    from services.ranking_service import get_employer_session
    from services.search_client import search_jobs
    from services.search_parser import parse_search_query, resolve_state_id
    from services.platform_api import get_closing_soon_jobs, get_nearby_organizations
    from config.config import MAX_RESULTS
    from services import user_data_service  # type: ignore
    from recommendation.recommendation_service import recommendation_service  # type: ignore
    from recommendation.mappers import to_candidate_profile_from_api  # type: ignore
    from utils.session_state import get_pagination_state, set_pagination_state, clear_pagination_state, set_recommendation_session  # type: ignore



log = logging.getLogger(__name__)

JOB_MODE_FALLBACK = "Work from Office"


def check_employee_access(last_user_msg: str, session_id: str) -> bool:
    session = get_employer_session(session_id, role="employee")
    # Employees are blocked from the employer flow (candidate search)
    if is_employer_hiring_query(last_user_msg) or session["current_step"] != "idle":
        return False
    return True


try:
    from backend.utils.timing import stage_timer, stage_timer_async, set_gate_flags, set_decision_flags
    from backend.utils.gates import should_run_search_parse_safe
except ModuleNotFoundError:
    from utils.timing import stage_timer, stage_timer_async, set_gate_flags, set_decision_flags  # type: ignore
    from utils.gates import should_run_search_parse_safe  # type: ignore


def _empty_result(db_context: str) -> dict:
    return {
        "db_context": db_context,
        "results": None,
        "result_type": None,
        "allowed_ids": set(),
        "raw_hits": [],
    }


def _term_pattern(term: str) -> Optional[re.Pattern]:
    """Word-boundary matcher so 'r' and 'go' don't match every description."""
    term = (term or "").strip()
    if len(term) < 2:
        return None
    return re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", re.IGNORECASE)


def _format_salary(raw: Any) -> Optional[str]:
    """Indian-grouped currency string or LPA representation."""
    if raw in (None, "", 0):
        return None
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        text = str(raw).strip()
        return text or None
    if amount <= 0:
        return None
    if amount < 100:
        val = int(amount) if amount.is_integer() else amount
        return f"₹{val} LPA"
    amount_int = int(amount)
    s = str(amount_int)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = f"{head},{tail}"
    return f"₹{s}"


def resolve_experience_ids(parsed_exp: Any, message: str = "") -> Optional[List[int]]:
    """Resolves extracted experience years or keywords (fresher, 0-1 yrs) to database experience IDs."""
    msg_lower = (message or "").lower()
    if "fresher" in msg_lower or "freshers" in msg_lower or "fresh" in msg_lower or "0 year" in msg_lower or "0 yrs" in msg_lower:
        return [1, 2]

    exp_val = parsed_exp
    if exp_val is None:
        m = re.search(r"(\d+)\s*(?:-\s*\d+)?\s*(?:year|yr|yrs|years)", msg_lower)
        if m:
            exp_val = int(m.group(1))

    if exp_val is None:
        return None

    try:
        exp_num = int(exp_val)
    except (ValueError, TypeError):
        return None

    if exp_num <= 0:
        return [1, 2]
    elif exp_num == 1:
        return [2, 3]
    elif exp_num == 2:
        return [3]
    elif exp_num in (3, 4):
        return [4, 5]
    elif exp_num in (5, 6, 7):
        return [6, 7]
    elif exp_num in (8, 9, 10):
        return [7, 8]
    elif exp_num >= 11:
        return [9, 10]
    return None


import html

def _clean_description(desc: Any) -> Optional[str]:
    text = re.sub(r"<[^>]+>", " ", str(desc or ""))
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def _clean_preview(desc: Any, limit: int = 180) -> Optional[str]:
    text = _clean_description(desc)
    if not text:
        return None
    return (text[:limit].rstrip() + "…") if len(text) > limit else text


async def handle_employee_context(
    last_user_msg: str,
    messages: list = None,
    user_location: Optional[str] = None,
    user_skills: list = None,
    user_roles: list = None,
    compose_mode: str = "structured",
    candidate_id: Optional[Any] = None,
    token: Optional[str] = None,
    user_slug: Optional[str] = None,
    user_profile_api_data: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = "default_session",
) -> Optional[dict]:
    msg_lower = (last_user_msg or "").lower()
    valid_hits = []


    # Widget 1: Position Closing Soon (Urgent Jobs)
    urgent_keywords = ["closing soon", "urgent job", "urgent jobs", "position closing", "deadline approaching", "expiring job"]
    if any(kw in msg_lower for kw in urgent_keywords):
        set_gate_flags(search_parse_ran=True)
        set_decision_flags(search_query_found=True, search_executed=True)

        raw_jobs = await run_in_threadpool(get_closing_soon_jobs, keyword=None, limit=MAX_RESULTS)
        try:
            from backend.schemas.schemas import JobCard
        except ModuleNotFoundError:
            from schemas.schemas import JobCard  # type: ignore

        job_cards = []
        allowed_ids = set()
        for item in raw_jobs:
            try:
                j_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            allowed_ids.add(j_id)
            title = item.get("job_title") or "Job Title"
            company = item.get("company_name") or "CollarCheck Partner"
            dept = item.get("department_name") or "General"
            location = item.get("location") or item.get("city_name") or item.get("state_name") or "Location not specified"
            exp = f"{item.get('experience')} yrs" if item.get("experience") is not None else "Not specified"
            mode = item.get("job_mode_name") or "Office"
            salary = _format_salary(item.get("salary"))
            raw_desc = item.get("job_description")
            preview = _clean_preview(raw_desc)
            full_desc = _clean_description(raw_desc)
            url = f"https://www.collarcheck.com/jobs-details/{j_id}"
            match_reason = "⏰ Position Closing Soon"

            job_cards.append(JobCard(
                job_id=j_id,
                title=title,
                company=company,
                department=dept,
                location=location,
                job_mode=mode,
                experience=exp,
                salary=salary,
                preview=preview,
                description=full_desc,
                url=url,
                match_reason=match_reason,
            ))

        db_context_str = (
            f"## POSITION CLOSING SOON (URGENT JOBS)\n"
            f"Retrieved {len(job_cards)} time-sensitive jobs closing soon.\n"
            f"The top {len(job_cards)} are ALREADY displayed to the user as interactive cards directly below your message.\n\n"
            "[INSTRUCTION]\n"
            "Write ONE short framing sentence informing the user about these positions closing soon. Do NOT list the jobs."
        )
        return {
            "db_context": db_context_str,
            "results": job_cards,
            "result_type": "urgent_jobs",
            "allowed_ids": allowed_ids,
            "raw_hits": raw_jobs,
        }

    # Widget 2: Organizations Near You
    nearby_keywords = ["organizations near", "organization near", "companies near", "company near", "nearby company", "nearby companies", "near me", "local employer", "local employers"]
    if any(kw in msg_lower for kw in nearby_keywords):
        set_gate_flags(search_parse_ran=True)
        set_decision_flags(search_query_found=True, search_executed=True)

        raw_orgs = await run_in_threadpool(get_nearby_organizations, location=user_location, limit=MAX_RESULTS)
        org_cards = []
        for item in raw_orgs:
            name = item.get("name") or "Organization"
            city = item.get("city_name") or ""
            state = item.get("state_name") or ""
            loc = ", ".join([p for p in (city, state) if p]) or "Location not specified"
            dist = item.get("distance")
            dist_str = f"📍 {dist} km away" if dist is not None else "📍 Nearby Organization"
            slug = item.get("slug") or ""
            url = f"https://www.collarcheck.com/company/{slug}" if slug else "https://www.collarcheck.com/organizations"

            org_cards.append({
                "org_id": str(item.get("id")),
                "name": name,
                "location": loc,
                "city": city,
                "state": state,
                "country": item.get("country_name") or "",
                "industry": item.get("industry_name") or "General",
                "company_size": item.get("company_size_name") or "",
                "turnover": item.get("turnover_name") or "",
                "distance": dist,
                "distance_label": dist_str,
                "profile": item.get("profile"),
                "url": url,
                "match_reason": dist_str,
            })

        db_context_str = (
            f"## ORGANIZATIONS NEAR YOU\n"
            f"Retrieved {len(org_cards)} organizations near the user's location.\n"
            f"The top {len(org_cards)} are ALREADY displayed to the user as interactive organization cards directly below your message.\n\n"
            "[INSTRUCTION]\n"
            "Write ONE short framing sentence informing the user about organizations near their location. Do NOT list the organizations."
        )
        return {
            "db_context": db_context_str,
            "results": org_cards,
            "result_type": "nearby_organizations",
            "allowed_ids": set(),
            "raw_hits": raw_orgs,
        }

    # Widget 3 / Follow-up Explanation Handler: e.g. "why was the 2nd job recommended?", "why this job?"
    msg_clean = (last_user_msg or "").lower().strip()
    explanation_keywords = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
    if re.search(r'\bwhy\b', msg_clean) and ("job" in msg_clean or "recommend" in msg_clean or "this" in msg_clean or "that" in msg_clean or "rank" in msg_clean or "#" in msg_clean or any(word in msg_clean for word in explanation_keywords)):
        set_gate_flags(search_parse_ran=True)
        set_decision_flags(search_query_found=True, search_executed=True)

        res_exp = recommendation_service.get_recommendation_by_rank_or_id(
            session_id=session_id,
            user_message=last_user_msg
        )
        if res_exp.get("success"):
            summary_txt = res_exp.get("recommendation_explanation", "")
            g_rank = res_exp.get("global_rank", 1)
            j_id = res_exp.get("job_id")
            
            db_context_str = (
                f"## JOB RECOMMENDATION EXPLANATION\n"
                f"Explanation for global rank #{g_rank} (Job ID {j_id}): {summary_txt}\n\n"
                "[INSTRUCTION]\n"
                f"Explain clearly to the user why job #{g_rank} was recommended: {summary_txt}"
            )
            return {
                "db_context": db_context_str,
                "results": None,
                "result_type": "recommendation_explanation",
                "allowed_ids": set(),
                "raw_hits": [],
                "explanation": summary_txt,
                "global_rank": g_rank,
                "job_id": j_id
            }
        else:
            err_msg = res_exp.get("error", "I couldn't find a matching recommendation snapshot in your current session.")
            db_context_str = f"## RECOMMENDATION EXPLANATION ERROR\n{err_msg}\n\n[INSTRUCTION]\nRespond with: {err_msg}"
            return {
                "db_context": db_context_str,
                "results": None,
                "result_type": "recommendation_explanation_error",
                "allowed_ids": set(),
                "raw_hits": [],
            }


    # Check for conversational pagination commands (e.g. "next page", "prev page", "page 2")
    msg_clean = (last_user_msg or "").lower().strip()
    is_pagination_cmd = False
    requested_page = 1

    saved_p_state = get_pagination_state(session_id)
    page_num_match = re.search(r'\b(?:go\s+to\s+|show\s+)?page\s+(\d+)\b', msg_clean)
    if page_num_match:
        is_pagination_cmd = True
        requested_page = int(page_num_match.group(1))
    elif re.search(r'\b(?:next\s+page|next\s+jobs|show\s+next|next)\b', msg_clean) and not re.search(r'\b(job|role|developer|analyst|engineer|search|find|php|react|python|java|data)\b', msg_clean):
        is_pagination_cmd = True
        if saved_p_state:
            requested_page = saved_p_state.get("current_page", 1) + 1
        else:
            requested_page = 2
    elif re.search(r'\b(?:previous\s+page|prev\s+page|back\s+page|previous)\b', msg_clean) and not re.search(r'\b(job|role|developer|analyst|engineer|search|find|php|react|python|java|data)\b', msg_clean):
        is_pagination_cmd = True
        if saved_p_state:
            requested_page = max(1, saved_p_state.get("current_page", 1) - 1)
        else:
            requested_page = 1

    if not is_pagination_cmd:
        ran, reason = should_run_search_parse_safe("employee", last_user_msg)
        log.info(
            "gate_decision parser=search_parse ran=%s reason=%s msg_len=%d role=employee",
            ran, reason, len(last_user_msg or ""),
        )
        set_gate_flags(search_parse_ran=ran)

        if not ran:
            set_decision_flags(search_query_found=False, search_executed=False)
            return None

        async with stage_timer_async("search_parse"):
            parsed = await parse_search_query(last_user_msg, "employee", messages, user_location=user_location)

        is_intent = bool(parsed.get("is_search_intent"))
        set_decision_flags(search_query_found=is_intent)

        if not is_intent:
            set_decision_flags(search_executed=False)
            return None
    else:
        set_decision_flags(search_query_found=True, search_executed=True)
        parsed = {"is_search_intent": True, "is_recommendation_intent": True}

    set_decision_flags(search_executed=True)


    keyword = parsed.get("keyword") or ""
    skills = parsed.get("skills") or []
    if skills:
        keyword = f"{keyword} {' '.join(skills)}".strip()

    has_explicit_filters = bool(parsed.get("location") or parsed.get("job_mode") or parsed.get("experience") or parsed.get("urgent") or parsed.get("salary"))

    valid_hits = []
    used_profile_fallback = False
    res = {"success": False, "data": [], "total": 0}
    filters = {}

    if not keyword and not has_explicit_filters:


        profile_skills_for_fallback = []
        profile_roles_for_fallback = []

        try:
            prof_data = user_profile_api_data
            if not prof_data:
                prof_data = await run_in_threadpool(
                    user_data_service.fetch_endpoint_data,
                    "user-profile",
                    token=token,
                    user_slug=user_slug,
                    user_id=str(candidate_id or "")
                )
            if isinstance(prof_data, dict) and prof_data.get("status"):
                api_cand_prof = to_candidate_profile_from_api(prof_data)
                profile_skills_for_fallback = api_cand_prof.skills
                if api_cand_prof.current_title:
                    profile_roles_for_fallback = [api_cand_prof.current_title]
        except Exception as p_ex:
            log.warning("Failed to fetch API profile skills for search keyword fallback: %s", p_ex)

        if not profile_skills_for_fallback:
            profile_skills_for_fallback = list(user_skills or [])
        if not profile_roles_for_fallback:
            profile_roles_for_fallback = list(user_roles or [])

        search_terms = []
        if profile_skills_for_fallback:
            search_terms.extend([str(s).strip() for s in profile_skills_for_fallback if s])
        if profile_roles_for_fallback:
            search_terms.extend([str(r).strip() for r in profile_roles_for_fallback if r])

        if search_terms:
            used_profile_fallback = True
            import asyncio

            clean_terms = []
            seen_t = set()
            for t in search_terms:
                t_lower = t.lower()
                if t_lower not in seen_t:
                    seen_t.add(t_lower)
                    clean_terms.append(t)

            with stage_timer("resolve"):
                state_name = parsed.get("location")
                state_id = await run_in_threadpool(resolve_state_id, state_name) if state_name else None
                job_mode_id = None
                mode_str = (parsed.get("job_mode") or "").lower().strip()
                if "home" in mode_str or "wfh" in mode_str or "remote" in mode_str:
                    job_mode_id = 2
                elif "office" in mode_str or "site" in mode_str:
                    job_mode_id = 1
                elif "hybrid" in mode_str:
                    job_mode_id = 3

                base_filters = {}
                if state_id:
                    base_filters["state"] = [state_id]
                if job_mode_id:
                    base_filters["job_mode"] = [job_mode_id]
                if parsed.get("urgent"):
                    base_filters["urgent"] = 1
                exp_ids = resolve_experience_ids(parsed.get("experience"), last_user_msg)
                if exp_ids:
                    base_filters["experience"] = exp_ids

            async with stage_timer_async("search_http"):
                tasks = [search_jobs(keyword=t, **base_filters) for t in clean_terms[:5]]
                results_list = await asyncio.gather(*tasks, return_exceptions=True)

            merged_hits = []
            seen_ids = set()
            for r in results_list:
                if isinstance(r, dict) and r.get("success"):
                    for item in r.get("data", []):
                        j_id = item.get("id")
                        if j_id is not None and j_id not in seen_ids:
                            seen_ids.add(j_id)
                            merged_hits.append(item)

            hits = merged_hits
            res = {"success": True, "data": hits, "total": len(hits)}
    else:
        with stage_timer("resolve"):
            state_name = parsed.get("location")
            state_id = await run_in_threadpool(resolve_state_id, state_name) if state_name else None

            job_mode_id = None
            mode_str = (parsed.get("job_mode") or "").lower().strip()
            if "home" in mode_str or "wfh" in mode_str or "remote" in mode_str:
                job_mode_id = 2
            elif "office" in mode_str or "site" in mode_str:
                job_mode_id = 1
            elif "hybrid" in mode_str:
                job_mode_id = 3

            filters = {}
            if keyword:
                filters["keyword"] = keyword
            if state_id:
                filters["state"] = [state_id]
            if job_mode_id:
                filters["job_mode"] = [job_mode_id]
            if parsed.get("urgent"):
                filters["urgent"] = 1

            exp_ids = resolve_experience_ids(parsed.get("experience"), last_user_msg)
            if exp_ids:
                filters["experience"] = exp_ids

        async with stage_timer_async("search_http"):
            res = await search_jobs(**filters)
        hits = res.get("data", [])

    if not res.get("success"):
        log.warning("search_jobs failed filters=%s", filters)
        return _empty_result(
            "## SEARCH STATUS\n"
            "The job search service is temporarily unavailable.\n\n"
            "[INSTRUCTION]\n"
            "Tell the user in one sentence that job search is briefly unavailable and "
            "ask them to try again in a moment. Do NOT invent job listings. "
            "Do NOT claim any results were found."
        )

    hits = res.get("data", [])
    total = res.get("total", 0)

    if not hits:
        searched_for = keyword or "your search"
        return _empty_result(
            f"## JOB SEARCH RESULT\n"
            f"The search for '{searched_for}' returned 0 jobs.\n\n"
            "[INSTRUCTION]\n"
            "Tell the user in one sentence that no matches were found, then offer to "
            "broaden the search by location, job title, or work mode. "
            "Do NOT invent job titles, companies, or counts. "
            "Do NOT state a number of results."
        )

    user_skills_set = {str(s).lower().strip() for s in (user_skills or []) if s}
    user_roles_set = {str(r).lower().strip() for r in (user_roles or []) if r}

    skill_patterns = {s: p for s in user_skills_set if (p := _term_pattern(s))}
    role_patterns = {r: p for r in user_roles_set if (p := _term_pattern(r))}

    with stage_timer("rank"):
        sort_type = parsed.get("sort")
        if sort_type == "create_ts":
            hits.sort(key=lambda x: x.get("create_ts") or 0, reverse=True)
        elif sort_type == "salary":
            hits.sort(key=lambda x: float(x.get("salary") or 0.0), reverse=True)
        elif skill_patterns or role_patterns:
            def calc_relevance(job: dict) -> float:
                score = 0.0
                j_title = str(job.get("job_title") or "")
                j_dept = str(job.get("department_name") or "")
                j_desc = str(job.get("job_description") or "")
                j_text = f"{j_title} {j_dept} {j_desc}"

                for pattern in role_patterns.values():
                    if pattern.search(j_title):
                        score += 20.0
                    elif pattern.search(j_text):
                        score += 5.0

                for pattern in skill_patterns.values():
                    if pattern.search(j_title):
                        score += 15.0
                    elif pattern.search(j_dept):
                        score += 8.0
                    elif pattern.search(j_desc):
                        score += 3.0

                return score

            hits.sort(key=calc_relevance, reverse=True)

    # Drop rows without a usable primary key, and de-duplicate
    valid_hits.clear()
    seen_ids = set()

    for h in hits:
        try:
            j_id = int(h.get("id"))
        except (TypeError, ValueError):
            log.warning("skipping search hit with unusable id=%r", h.get("id"))
            continue
        if j_id in seen_ids:
            continue
        seen_ids.add(j_id)
        h["_job_id"] = j_id
        valid_hits.append(h)

    if not valid_hits:
        return _empty_result(
            "## JOB SEARCH RESULT\n"
            "The search returned rows but none had a valid job id.\n\n"
            "[INSTRUCTION]\n"
            "Tell the user something went wrong retrieving the listings and ask them "
            "to try again. Do NOT invent job listings."
        )

    # ------------------------------------------------------------------
    # RECOMMENDATION ENGINE RANKING USING USER-PROFILE API DATA
    # ------------------------------------------------------------------
    rec_results_by_job_id = {}
    with stage_timer("recommendation_engine"):
        try:
            profile_api_data = user_profile_api_data
            if not profile_api_data:
                profile_api_data = await run_in_threadpool(
                    user_data_service.fetch_endpoint_data,
                    "user-profile",
                    token=token,
                    user_slug=user_slug,
                    user_id=str(candidate_id or "")
                )

            candidate_prof = to_candidate_profile_from_api(
                profile_api_data if isinstance(profile_api_data, dict) else {},
                user_id=int(candidate_id) if candidate_id and str(candidate_id).isdigit() else None,
                fallback_skills=user_skills
            )


            rec_phrase_match = bool(re.search(r'\b(?:jobs\s+for\s+me|suggest\s+jobs|recommend\s+jobs|jobs\s+for\s+my\s+profile|jobs\s+matching|jobs\s+according)\b', msg_clean))
            is_rec_intent = bool(parsed.get("is_recommendation_intent")) or used_profile_fallback or is_pagination_cmd or rec_phrase_match

            pagination_meta = None
            if is_rec_intent and candidate_prof and candidate_prof.skills:
                saved_p = get_pagination_state(session_id) if (is_pagination_cmd and session_id) else None
                if saved_p and "all_recs" in saved_p:
                    import math
                    all_recs = saved_p["all_recs"]
                    total_results = len(all_recs)
                    total_pages = max(1, math.ceil(total_results / MAX_RESULTS))
                    is_oob = requested_page > total_pages
                    target_p = max(1, min(requested_page, total_pages))
                    page_recs = all_recs[(target_p - 1) * MAX_RESULTS : target_p * MAX_RESULTS]
                    pagination_meta = {
                        "current_page": target_p,
                        "per_page": MAX_RESULTS,
                        "total_results": total_results,
                        "total_pages": total_pages,
                        "start_index": (target_p - 1) * MAX_RESULTS + 1 if total_results > 0 else 0,
                        "end_index": min(target_p * MAX_RESULTS, total_results),
                        "has_next": target_p < total_pages,
                        "has_prev": target_p > 1,
                        "invalid_page_num": requested_page if is_oob else None,
                        "all_recs": all_recs
                    }
                else:

                    rec_jobs_input = valid_hits if (valid_hits and has_explicit_filters and not is_rec_intent) else None
                    page_recs, pagination_meta, all_recs = recommendation_service.get_paginated_recommendations_for_profile(
                        candidate_prof,
                        jobs=rec_jobs_input,
                        page=1,
                        per_page=MAX_RESULTS,
                        session_id=session_id,
                        job_mode=job_mode_id
                    )


                    pagination_meta["all_recs"] = all_recs


                if session_id and pagination_meta:
                    set_pagination_state(session_id, pagination_meta)

                recs = page_recs
                if recs:
                    rec_hits = []
                    for r in recs:
                        if not r.job_id:
                            continue
                        rec_results_by_job_id[r.job_id] = r
                        raw_job = getattr(r, "raw_data", {}) or {}
                        hit_dict = dict(raw_job) if isinstance(raw_job, dict) else {}
                        hit_dict["_job_id"] = r.job_id
                        hit_dict["id"] = r.job_id
                        if not hit_dict.get("job_title"):
                            hit_dict["job_title"] = getattr(r.title_result, "job_title", "Job Title") or "Job Title"
                        rec_hits.append(hit_dict)
                    valid_hits.clear()
                    valid_hits.extend(rec_hits)

                else:
                    valid_hits.clear()



                sort_type = parsed.get("sort")
                if not sort_type:
                    valid_hits.sort(
                        key=lambda h: rec_results_by_job_id.get(h["_job_id"]).overall_score if h["_job_id"] in rec_results_by_job_id else -1.0,
                        reverse=True
                    )

                # If candidate has profile skills, filter out completely unrelated jobs
                if candidate_prof and candidate_prof.skills and not is_rec_intent:

                    def _is_relevant_job(h):

                        rec_res = rec_results_by_job_id.get(h["_job_id"])
                        if not rec_res:
                            return False
                        if rec_res.skill_result.score > 0:
                            return True
                        if rec_res.title_result.match_level in ("exact", "contains", "keyword_match"):
                            return True
                        if rec_res.overall_score >= 50.0:
                            return True

                        job_title_str = (h.get("job_title") or "").lower()
                        job_title_norm = re.sub(r'[^a-z0-9]', '', job_title_str)

                        # Match candidate skills against job title
                        for sk in candidate_prof.skills:
                            sk_str = str(sk).lower()
                            sk_norm = re.sub(r'[^a-z0-9]', '', sk_str)
                            if sk_norm and len(sk_norm) > 2:
                                if sk_norm in job_title_norm or job_title_norm in sk_norm:
                                    return True
                                # Match domain keywords e.g. "frontend" in "Frontend Developer", "data" in "Data Analyst"
                                sk_words = set(sk_str.split()) - {"developer", "engineer", "manager", "executive", "associate", "intern", "js"}
                                jt_words = set(job_title_str.split()) - {"developer", "engineer", "manager", "executive", "associate", "intern", "js"}
                                if sk_words and jt_words and (sk_words & jt_words):
                                    return True
                        return False

                    relevant_hits = [h for h in valid_hits if _is_relevant_job(h)]
                    if relevant_hits:
                        valid_hits.clear()
                        valid_hits.extend(relevant_hits)
                    else:
                        valid_hits.clear()

        except Exception as rec_err:
            log.exception("RecommendationEngine ranking failed in job search: %s", rec_err)


    top_hits = valid_hits[:MAX_RESULTS]

    try:
        from backend.schemas.schemas import JobCard
    except ModuleNotFoundError:
        from schemas.schemas import JobCard  # type: ignore

    job_cards = []
    allowed_ids = set()
    compact_lines = []

    for i, h in enumerate(top_hits, 1):
        j_id = h["_job_id"]
        allowed_ids.add(j_id)

        title = h.get("job_title") or "Job"
        company = h.get("company_name") or "Company"
        department = h.get("department_name") or "General"
        city = h.get("city_name")
        state = h.get("state_name")
        location = ", ".join([p for p in (city, state) if p]) or "Location not specified"
        exp = h.get("experience_name") or h.get("experience") or "Not specified"
        from backend.config.config import JOB_MODE_MAP

        raw_mode_val = h.get("job_mode") or h.get("job_mode_name") or h.get("mode")
        if isinstance(raw_mode_val, int) or (isinstance(raw_mode_val, str) and str(raw_mode_val).isdigit()):
            mode = JOB_MODE_MAP.get(int(raw_mode_val), JOB_MODE_FALLBACK)
        elif isinstance(raw_mode_val, str) and raw_mode_val.strip():
            mode = raw_mode_val.strip()
        else:
            mode = JOB_MODE_FALLBACK
        vacancy = h.get("vacancy")



        rec_res = rec_results_by_job_id.get(j_id)
        if rec_res and rec_res.explanation_result and rec_res.explanation_result.summary:
            match_reason = f"Match Score: {round(rec_res.overall_score)}% • {rec_res.explanation_result.summary}"
        elif skill_patterns:
            haystack = f"{h.get('job_title') or ''} {h.get('department_name') or ''} {h.get('job_description') or ''}"
            matched = [s for s, p in skill_patterns.items() if p.search(haystack)]
            if matched:
                sorted_matched = sorted(matched)
                if len(sorted_matched) > 6:
                    shown = ", ".join(sorted_matched[:6]).title() + f" +{len(sorted_matched)-6} more"
                else:
                    shown = ", ".join(sorted_matched).title()
                match_reason = f"Matches your skills: {shown}"
            else:
                match_reason = "Matched your search terms"
        elif used_profile_fallback:
            match_reason = "Based on your profile"
        else:
            match_reason = "Matched your search terms"

        raw_desc = h.get("job_description")

        rec_res = rec_results_by_job_id.get(j_id)
        g_rank = getattr(rec_res, "global_rank", None) if rec_res else None
        m_score = getattr(rec_res, "overall_score", None) if rec_res else None
        m_skills = getattr(rec_res.skill_result, "matched_skills", None) if (rec_res and hasattr(rec_res, "skill_result")) else None
        rec_exp = getattr(rec_res.explanation_result, "summary", None) if (rec_res and hasattr(rec_res, "explanation_result")) else None

        rec_reasons_dto = []
        if rec_res and hasattr(rec_res, "recommendation_reasons") and rec_res.recommendation_reasons:
            for reason in rec_res.recommendation_reasons:
                rec_reasons_dto.append({
                    "type": getattr(reason, "type", "overall"),
                    "label": getattr(reason, "label", "Overall Fit"),
                    "message": getattr(reason, "message", "")
                })

        job_card = JobCard(
            job_id=j_id,
            title=title,
            company=company,
            department=department,
            location=location,
            job_mode=mode,
            experience=exp,
            vacancy=vacancy,
            salary=_format_salary(h.get("salary")),
            preview=_clean_preview(raw_desc),
            description=_clean_description(raw_desc),
            url=f"https://www.collarcheck.com/jobs-details/{j_id}",
            match_reason=match_reason,
            global_rank=g_rank,
            match_score=m_score,
            matched_skills=m_skills,
            recommendation_explanation=rec_exp,
            recommendation_reasons=rec_reasons_dto if rec_reasons_dto else None
        )

        job_cards.append(job_card)
        compact_lines.append(f"{i}. {title} — {company}")

    if session_id and top_hits:
        from backend.utils.session_state import get_recommendation_session
        existing_rec_session = get_recommendation_session(session_id)
        if not existing_rec_session or not existing_rec_session.get("ranked_jobs"):
            displayed_recs = []
            for idx, h in enumerate(top_hits, start=1):
                j_id = h["_job_id"]
                r = rec_results_by_job_id.get(j_id)
                if not r and candidate_prof:
                    try:
                        from backend.recommendation.mappers import to_job_profile
                        jp = to_job_profile(h)
                        r_list = recommendation_service.engine.recommend_jobs(candidate_prof, [jp])
                        if r_list:
                            r = r_list[0]
                    except Exception as ex:
                        log.warning("Fallback job scoring for session snapshot failed: %s", ex)
                if r:
                    r.global_rank = idx
                    displayed_recs.append(r)
            if displayed_recs:
                q_key = f"cand_{candidate_prof.id if (candidate_prof and hasattr(candidate_prof, 'id')) else 'default'}"
                set_recommendation_session(
                    session_id=session_id,
                    query_key=q_key,
                    ranked_jobs=displayed_recs,
                    current_page=1,
                    page_size=MAX_RESULTS,
                    total_jobs=len(displayed_recs)
                )



    location_label = f" in {state_name}" if state_name else ""

    display_total = len(valid_hits)

    if compose_mode != "legacy":
        # structured/dual mode: cards carry the data, the model only frames it.
        parts = [
            "## JOB SEARCH RESULT SUMMARY",
            f"The search{location_label} returned {display_total} matching job(s). "
            f"The top {len(job_cards)} are ALREADY displayed to the user as interactive "
            f"cards directly below your message.",
            "",
            "Titles retrieved (for your awareness only — do NOT repeat them):",
        ]
        parts.extend(compact_lines)
        if pagination_meta and pagination_meta.get("total_pages", 1) > 0:
            s_idx = pagination_meta.get("start_index", 1)
            e_idx = pagination_meta.get("end_index", len(job_cards))
            t_res = pagination_meta.get("total_results", len(job_cards))
            c_page = pagination_meta.get("current_page", 1)
            t_pages = pagination_meta.get("total_pages", 1)
            is_oob = pagination_meta.get("is_out_of_bounds", False)
            oob_num = pagination_meta.get("invalid_page_num")
            if is_oob and oob_num:
                example_sentence = f"Page {oob_num} isn't available. You can view pages 1–{t_pages}."
            elif t_res == 0:
                example_sentence = "I couldn't find any roles matching your skills."
            elif t_pages == 1:
                example_sentence = f"I found {t_res} roles matching your skills — here are the top matches."
            else:
                example_sentence = f"Showing jobs {s_idx}–{e_idx} of {t_res} matching your skills (Page {c_page} of {t_pages})."
        elif display_total == 0:
            example_sentence = "I couldn't find any roles matching your skills."
        elif display_total == 1:
            example_sentence = "I found 1 role matching your skills — here it is."
        else:
            example_sentence = f"I found {display_total} roles matching your skills — here are the top matches."

        parts.append(
            "\n[INSTRUCTION]\n"
            "Write ONE short sentence of framing, then stop. You MUST NOT:\n"
            "- list, number, bullet, or name any job\n"
            "- mention companies, locations, salaries, experience, or links\n"
            "- state any count other than the numbers given above\n"
            "- add a closing line about visiting collarcheck.com\n"
            f"Good example: '{example_sentence}'\n"
            "You may optionally add one short follow-up question offering to filter by "
            "location, experience, or work mode."
        )
        if used_profile_fallback:
            parts.append(
                "Note: the user did not name a role, so results were matched from their "
                "saved profile. Mention this briefly in your sentence."
            )
        db_context_str = "\n".join(parts)
    else:
        # dual / text path: no cards in UI or fallback: model renders full job listings in text
        parts = ["## LIVE JOB DATA FROM COLLARCHECK DATABASE",
                 f"found {total} matches, showing top {len(top_hits)}", ""]
        for i, c in enumerate(job_cards, 1):
            parts.append(
                f"{i}. **{c.title}**\n"
                f"   - **Company:** {c.company}\n"
                f"   - **Department:** {c.department}\n"
                f"   - **Location:** {c.location}\n"
                f"   - **Experience:** {c.experience}\n"
                f"   - **Vacancies:** {c.vacancy or 'Open'}\n"
                f"   - **Mode:** {c.job_mode}\n"
                f"   - **Apply:** [{c.url}]({c.url})\n"
            )
        parts.append(
            "\n[INSTRUCTION]\n"
            f"Start with: 'I found {total} role(s) matching your search:'\n"
            "Reproduce each job above exactly as given — do not add, invent, or omit "
            "any field, and do not change any value. Keep spacing tight.\n"
            "End with: 'To apply, visit [collarcheck.com/jobs](https://www.collarcheck.com/jobs)'"
        )
        db_context_str = "\n".join(parts)

    return {
        "db_context": db_context_str,
        "results": job_cards,
        "result_type": "jobs",
        "allowed_ids": allowed_ids,
        "raw_hits": top_hits,
        "pagination": pagination_meta,
    }