from typing import Any, Dict, List, Optional

BOOL_WHITELIST = {"still_working", "approved", "status", "is_verified", "same_address"}

TOP_LEVEL_FK_KEYS = {
    "id", "location", "country", "city", "state",
    "current_position", "current_company",
    "still_working_position", "still_working_company",
    "industry", "slug", "user_slug", "company_slug"
}

def coerce_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("1", "true", "yes"):
            return True
        if v in ("0", "false", "no", ""):
            return False
    return bool(val)

def normalize(raw: dict) -> dict:
    """
    Normalizes raw user profile payload into a clean, flat dictionary structure.
    Strips top-level FK fields and slugs, flattens employment history, extracts education and languages.
    """
    data = raw.get("data", raw) if isinstance(raw, dict) else raw

    normalized: Dict[str, Any] = {}

    # Copy top-level scalar fields, performing selective bool coercion and FK filtering
    for k, v in data.items():
        if k in TOP_LEVEL_FK_KEYS or k.endswith("_id") or k == "employement_history":
            continue

        if k in BOOL_WHITELIST:
            normalized[k] = coerce_bool(v)
        else:
            normalized[k] = v

    # Extract & flatten employment history
    jobs: List[Dict[str, Any]] = []
    emp_history_new = data.get("employement_history_new", []) or []
    for emp_parent in emp_history_new:
        if not isinstance(emp_parent, dict):
            continue
        parent_company = emp_parent.get("company", "")
        parent_is_verified = coerce_bool(emp_parent.get("is_verified", False))

        lists = emp_parent.get("lists", []) or []
        if not lists:
            # Fallback if top-level company has no nested lists
            joining_date = emp_parent.get("joining_date")
            worked_till_date = emp_parent.get("worked_till_date")
            is_present = not worked_till_date
            jobs.append({
                "company": parent_company,
                "designation": "",
                "employment_type": "",
                "from": joining_date,
                "to": worked_till_date if not is_present else None,
                "is_present": is_present,
                "is_verified": parent_is_verified,
                "skills": [],
            })
        else:
            for job_item in lists:
                if not isinstance(job_item, dict):
                    continue
                designation = job_item.get("designation", "")
                employment_type = job_item.get("employment_type", "")
                joining_date = job_item.get("joining_date")
                worked_till_date = job_item.get("worked_till_date")
                still_working = job_item.get("still_working")
                is_present = (worked_till_date is None or worked_till_date == "") or coerce_bool(still_working)

                job_is_verified = parent_is_verified or coerce_bool(job_item.get("approved"))

                skill_objs = job_item.get("skill", []) or []
                job_skills = [s.get("name") for s in skill_objs if isinstance(s, dict) and s.get("name")]

                jobs.append({
                    "company": parent_company,
                    "designation": designation,
                    "employment_type": employment_type,
                    "from": joining_date,
                    "to": worked_till_date if not is_present else None,
                    "is_present": is_present,
                    "is_verified": job_is_verified,
                    "skills": job_skills,
                })

    normalized["jobs"] = jobs

    # Extract skills
    all_skills = data.get("all_Skill", []) or []
    normalized["skills"] = [s.get("skill") for s in all_skills if isinstance(s, dict) and s.get("skill")]

    # Extract education preserving readable location names
    all_education = data.get("all_education", []) or []
    education_list: List[Dict[str, Any]] = []
    for edu in all_education:
        if isinstance(edu, dict):
            education_list.append({
                "university": edu.get("university"),
                "course": edu.get("course"),
                "course_type": edu.get("course_type"),
                "state": edu.get("state"),
                "city": edu.get("city"),
                "country": edu.get("country"),
                "starting_date": edu.get("starting_date"),
                "ending_date": edu.get("ending_date"),
                "ishighest": coerce_bool(edu.get("ishighest", False)),
            })
    normalized["education"] = education_list

    # Extract languages
    all_languages = data.get("all_languages", []) or []
    lang_list: List[Dict[str, Any]] = []
    for lang in all_languages:
        if isinstance(lang, dict):
            lang_list.append({
                "name": lang.get("name"),
                "verbal": lang.get("verbal"),
                "written": lang.get("written"),
            })
    normalized["languages"] = lang_list

    return normalized
