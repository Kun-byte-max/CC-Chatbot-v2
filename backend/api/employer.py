from typing import Optional
import logging

try:
    from backend.utils.utils import is_employer_hiring_query
    from backend.services.search_client import search_users
    from backend.services.search_parser import parse_search_query, resolve_state_id
    from backend.config.config import MAX_RESULTS
except ModuleNotFoundError:
    from utils.utils import is_employer_hiring_query
    from services.search_client import search_users
    from services.search_parser import parse_search_query, resolve_state_id
    from config.config import MAX_RESULTS  # type: ignore

log = logging.getLogger(__name__)

def check_employer_access(last_user_msg: str, session_id: str, is_career_query_func) -> bool:
    # Employers are blocked from the job-search flow (any career query that is not a hiring trigger)
    if is_career_query_func(last_user_msg) and not is_employer_hiring_query(last_user_msg):
        return False
    return True

try:
    from backend.utils.timing import stage_timer, stage_timer_async, set_gate_flags, set_decision_flags
    from backend.utils.gates import should_run_search_parse_safe
except ModuleNotFoundError:
    from utils.timing import stage_timer, stage_timer_async, set_gate_flags, set_decision_flags  # type: ignore
    from utils.gates import should_run_search_parse_safe  # type: ignore

async def handle_employer_context(last_user_msg: str, session_id: str, messages: list = None, user_location: str = None, compose_mode: str = "dual") -> Optional[dict]:
    ran, reason = should_run_search_parse_safe("employer", last_user_msg, session_id=session_id)
    log.info("gate_decision parser=search_parse ran=%s reason=%s msg_len=%d role=employer", ran, reason, len(last_user_msg or ""))
    set_gate_flags(search_parse_ran=ran)

    if not ran:
        set_decision_flags(search_query_found=False, search_executed=False)
        return None

    async with stage_timer_async("search_parse"):
        parsed = await parse_search_query(last_user_msg, "employer", messages)

    is_intent = bool(parsed.get("is_search_intent"))
    set_decision_flags(search_query_found=is_intent)

    if not is_intent:
        set_decision_flags(search_executed=False)
        return None

    set_decision_flags(search_executed=True)
        
    keyword = parsed.get("keyword") or ""
    skills = parsed.get("skills") or []
    if skills:
        skills_str = " ".join(skills)
        keyword = f"{keyword} {skills_str}".strip()
        
    with stage_timer("resolve"):
        state_name = parsed.get("location") or user_location
        state_id = resolve_state_id(state_name)
        
        filters = {}
        if keyword:
            filters["keyword"] = keyword
        if state_id:
            filters["state"] = [state_id]
        if parsed.get("experience"):
            filters["yearExperience"] = [parsed["experience"]]
        
    async with stage_timer_async("search_http"):
        res = await search_users(**filters)
    if not res.get("success"):
        return {"db_context": "## SEARCH STATUS\nSearch is temporarily unavailable. Please try again later.", "results": None, "result_type": None, "allowed_ids": set()}
        
    hits = res.get("data", [])
    total = res.get("total", 0)
    
    if not hits:
        return {"db_context": "Found 0 matches for candidates.", "results": None, "result_type": None, "allowed_ids": set()}
        
    with stage_timer("rank"):
        if parsed.get("sort") == "experience":
            hits.sort(key=lambda x: x.get("total_experience_years", 0.0), reverse=True)
        
    top_hits = hits[:MAX_RESULTS]
    
    try:
        from backend.schemas.schemas import CandidateCard
    except ModuleNotFoundError:
        from schemas.schemas import CandidateCard  # type: ignore

    candidate_cards = []
    allowed_ids = set()
    compact_lines = []

    for i, h in enumerate(top_hits, 1):
        try:
            cand_id = int(h.get("id") or h.get("user_id") or h.get("ccid") or i)
        except Exception:
            cand_id = i
        allowed_ids.add(cand_id)

        name = h.get("full_name") or "Candidate"
        pos = h.get("current_position_name") or "N/A"
        city = h.get("city_name") or "N/A"
        state = h.get("state_name") or "N/A"
        exp = h.get("total_experience_years") or 0.0
        if exp == 0.0:
            exp_str = "Fresher (0 years)"
        elif exp > 0 and exp < 1.0:
            months = int(round(exp * 12))
            exp_str = f"{months} month{'s' if months != 1 else ''}"
        else:
            exp_str = f"{round(exp, 1)} year{'s' if round(exp, 1) != 1.0 else ''}"
            
        sk_list = h.get("skill_names") or []
        slug = h.get("slug") or str(cand_id)
        cand_url = f"https://www.collarcheck.com/candidate-details/{slug}"
        match_reason = f"{exp_str} in {city}, {state}".strip(", ")

        cand_card = CandidateCard(
            cc_id=str(cand_id),
            name=name,
            headline=pos,
            location=f"{city}, {state}",
            experience=exp_str,
            skills=sk_list,
            url=cand_url,
            match_reason=match_reason,
        )
        candidate_cards.append(cand_card)
        compact_lines.append(f"{i}. {name} - {pos} - {match_reason}")

    if compose_mode in ("structured", "dual"):
        parts = []
        parts.append(f"Results found: {total} candidates")
        parts.extend(compact_lines)
        parts.append(
            "\n[MANDATORY AI INSTRUCTION]\n"
            "The user's results are displayed as cards below your message. "
            "Write one or two sentences of framing. Do not list the results, do not repeat titles, salaries, or links."
        )
        db_context_str = "\n".join(parts)
    else:
        parts = []
        parts.append("## COLLARCHECK CANDIDATE SEARCH RESULTS")
        parts.append(f"found {total} matches, showing top {len(top_hits)}")
        parts.append("")
        for i, h in enumerate(top_hits, 1):
            name = h.get("full_name") or "Candidate"
            cc_id = h.get("ccid") or "N/A"
            pos = h.get("current_position_name") or "N/A"
            city = h.get("city_name") or "N/A"
            state = h.get("state_name") or "N/A"
            exp = h.get("total_experience_years") or 0.0
            if exp == 0.0:
                exp_str = "Fresher (0 years)"
            elif exp > 0 and exp < 1.0:
                months = int(round(exp * 12))
                exp_str = f"{months} month{'s' if months != 1 else ''}"
            else:
                exp_str = f"{round(exp, 1)} year{'s' if round(exp, 1) != 1.0 else ''}"
            h_skills = ", ".join(h.get("skill_names", []))
            rating = h.get("star_rating_avg") or 0.0
            parts.append(
                f"CANDIDATE {i}:\n"
                f"  Name: {name}\n"
                f"  CC ID: {cc_id}\n"
                f"  Role/Position: {pos}\n"
                f"  Location: {city}, {state}\n"
                f"  Experience: {exp_str}\n"
                f"  Skills: {h_skills}\n"
                f"  Star Rating: ⭐ {rating} / 5.0\n"
                f"  Link: [View Candidate Profile](https://www.collarcheck.com/candidate-details/{h.get('slug')})\n"
            )
        parts.append(
            "\n[MANDATORY AI INSTRUCTION]\n"
            f"The candidate search returned {total} candidate(s). You MUST:\n"
            f"1. Start with: 'I found {total} candidate(s) matching your criteria.'\n"
            "2. List complete details for ALL top candidates provided above (Name, CC ID, Role/Position, Location, Experience, Star Rating, Skills, and ALWAYS include the clickable markdown link: [View Candidate Profile](URL) for EACH candidate).\n"
            "3. Present EVERY candidate in full without cutting off or omitting candidate profile links.\n"
            "4. Present the candidates in a clear numbered or bulleted list format. DO NOT use a table format.\n"
            "5. NEVER show or guess private information (emails, phone numbers, salaries).\n"
            "6. Offer to refine the search by location, experience, or skills.\n"
        )
        db_context_str = "\n".join(parts)

    return {
        "db_context": db_context_str,
        "results": candidate_cards if compose_mode in ("dual", "structured") else None,
        "result_type": "candidates" if compose_mode in ("dual", "structured") else None,
        "allowed_ids": allowed_ids,
        "raw_hits": top_hits,
    }
