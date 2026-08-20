"""
mappers.py — Converts raw database dicts/entities into CandidateProfile and JobProfile models.
"""

from typing import Dict, Any, Optional, List

from backend.recommendation.models import CandidateProfile, JobProfile


def to_candidate_profile(db_candidate: Dict[str, Any]) -> CandidateProfile:
    """
    Maps candidate DB dictionary into typed CandidateProfile dataclass.
    """
    if not db_candidate:
        raise ValueError("Cannot map empty candidate data.")

    cand_id = db_candidate.get("id")
    if cand_id is None:
        raise ValueError("Candidate data must include 'id'.")

    fname = db_candidate.get("fname") or ""
    lname = db_candidate.get("lname") or ""
    full_name = f"{fname} {lname}".strip() or "Candidate"

    skills = db_candidate.get("skills") or []
    exp_years = float(db_candidate.get("experience_years") or 0.0)
    city = db_candidate.get("city")
    state = db_candidate.get("state")
    country = db_candidate.get("country")
    loc_str = db_candidate.get("location") or ", ".join([p for p in [city, state, country] if p]) or None

    exp_sal = db_candidate.get("expected_salary")
    if exp_sal is not None:
        try:
            exp_sal = float(exp_sal)
        except (ValueError, TypeError):
            exp_sal = None

    return CandidateProfile(
        id=int(cand_id),
        name=full_name,
        skills=skills,
        experience_years=exp_years,
        location=loc_str,
        city=city,
        state=state,
        country=country,
        expected_salary=exp_sal,
        current_title=db_candidate.get("current_title"),
        raw_data=db_candidate.get("raw_data") or db_candidate,
    )


def to_candidate_profile_from_api(
    api_data: Dict[str, Any],
    user_id: Optional[int] = None,
    fallback_skills: Optional[List[Any]] = None
) -> CandidateProfile:
    """
    Maps user-profile API endpoint JSON payload into typed CandidateProfile dataclass.
    Supports comprehensive skill dict formats and fallback_skills list.
    """
    if not isinstance(api_data, dict):
        api_data = {}

    data = api_data.get("data") if isinstance(api_data.get("data"), dict) else api_data

    cand_id = user_id or data.get("id") or data.get("user_id") or 1
    try:
        cand_id = int(cand_id)
    except (ValueError, TypeError):
        cand_id = 1

    fname = data.get("fname") or ""
    lname = data.get("lname") or ""
    full_name = f"{fname} {lname}".strip() or "Candidate"

    # Extract skills from all_Skill list, all_skills, skills, user_skills, user_skill, or skill_names
    skills = []
    all_skills_raw = (
        data.get("all_Skill")
        or data.get("all_skills")
        or data.get("skills")
        or data.get("user_skills")
        or data.get("user_skill")
        or data.get("skill_names")
        or []
    )
    if isinstance(all_skills_raw, list):
        for s in all_skills_raw:
            if isinstance(s, dict):
                val = s.get("skill") or s.get("name") or s.get("skill_name") or s.get("title")
                if val:
                    skills.append(str(val).strip())
            elif isinstance(s, str) and s.strip():
                skills.append(s.strip())

    if not skills and fallback_skills:
        for s in fallback_skills:
            if isinstance(s, str) and s.strip():
                skills.append(s.strip())
            elif isinstance(s, dict):
                val = s.get("skill") or s.get("name") or s.get("skill_name")
                if val:
                    skills.append(str(val).strip())

    city = data.get("city_name") or data.get("city")
    state = data.get("state_name") or data.get("state")
    country = data.get("country_name") or data.get("country")
    loc_str = ", ".join([str(p) for p in [city, state, country] if p]) or None

    exp_years = 0.0
    try:
        exp_years = float(data.get("experience_years") or data.get("total_experience") or 0.0)
    except (ValueError, TypeError):
        exp_years = 0.0

    exp_sal = data.get("expected_salary")
    if exp_sal is not None:
        try:
            exp_sal = float(exp_sal)
        except (ValueError, TypeError):
            exp_sal = None

    current_title = data.get("still_working_position_name") or data.get("current_title") or data.get("designation")

    return CandidateProfile(
        id=cand_id,
        name=full_name,
        skills=skills,
        experience_years=exp_years,
        location=loc_str,
        city=str(city) if city else None,
        state=str(state) if state else None,
        country=str(country) if country else None,
        expected_salary=exp_sal,
        current_title=str(current_title) if current_title else None,
        raw_data=api_data,
    )



def to_job_profile(db_job: Dict[str, Any]) -> JobProfile:
    """
    Maps job DB dictionary into typed JobProfile dataclass.
    """
    if not db_job:
        raise ValueError("Cannot map empty job data.")

    job_id = db_job.get("id") or db_job.get("_job_id") or db_job.get("job_id")
    if job_id is None:
        raise ValueError("Job data must include 'id'.")

    title = db_job.get("title") or db_job.get("job_title") or "Job Title"
    company = db_job.get("company_name") or db_job.get("company")
    skills = db_job.get("required_skills") or db_job.get("skills") or db_job.get("skill_names") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    if not skills:
        try:
            from backend.repositories.job_repository import infer_job_skills
            raw_desc = db_job.get("job_description") or db_job.get("description") or ""
            dept_name = db_job.get("dept_name") or db_job.get("department_name") or ""
            skills = infer_job_skills(str(title), str(dept_name), str(raw_desc))
        except Exception:
            skills = []


    exp_years = 0.0
    try:
        exp_years = float(db_job.get("required_experience_years") or db_job.get("experience") or 0.0)
    except (ValueError, TypeError):
        exp_years = 0.0

    city = db_job.get("city") or db_job.get("city_name")
    state = db_job.get("state") or db_job.get("state_name")
    country = db_job.get("country") or db_job.get("country_name")
    loc_str = db_job.get("location") or ", ".join([str(p) for p in [city, state] if p]) or None

    job_mode = db_job.get("job_mode", 1)
    if job_mode not in (1, 2, 3):
        job_mode = 1

    sal_min = db_job.get("offered_salary_min") or db_job.get("salary")
    sal_max = db_job.get("offered_salary_max") or db_job.get("salary")

    return JobProfile(
        id=int(job_id),
        title=str(title),
        company_name=str(company) if company else None,
        required_skills=list(skills),
        required_experience_years=exp_years,
        location=loc_str,
        city=str(city) if city else None,
        state=str(state) if state else None,
        country=str(country) if country else None,
        job_mode=job_mode,
        offered_salary_min=float(sal_min) if sal_min is not None and str(sal_min).replace('.','',1).isdigit() else None,
        offered_salary_max=float(sal_max) if sal_max is not None and str(sal_max).replace('.','',1).isdigit() else None,
        raw_data=db_job.get("raw_data") or db_job,
    )
