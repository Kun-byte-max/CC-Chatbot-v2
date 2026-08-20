from typing import Any, Dict

def to_context(profile: dict) -> str:
    """
    Formats normalized user profile into a plain-text context block for system prompt injection.
    Strictly suppresses salary fields if showSalary is false.
    """
    # TODO: job-level numerical salary amount field name is unconfirmed
    # in the API schema — verify with backend before live mode.

    lines = ["=== USER PROFILE CONTEXT ==="]

    # Candidate Name & Location
    fname = profile.get("fname", "") or ""
    lname = profile.get("lname", "") or ""
    full_name = f"{fname} {lname}".strip() or "Candidate"
    lines.append(f"Name: {full_name}")

    work_status_name = profile.get("work_status_name")
    if work_status_name:
        lines.append(f"Work Status: {work_status_name}")

    state_name = profile.get("state_name")
    country_name = profile.get("country_name")
    loc_parts = [p for p in [state_name, country_name] if p]
    if loc_parts:
        lines.append(f"Location: {', '.join(loc_parts)}")

    # Top-level Identity Verification label
    is_verified = profile.get("is_verified")
    id_verif_str = "Verified" if is_verified else "Unverified"
    lines.append(f"Identity Verification Status: [{id_verif_str}]")

    # Current Employer (if specified)
    current_company = profile.get("still_working_company_name")
    current_position = profile.get("still_working_position_name")
    if current_company or current_position:
        comp_str = current_company or "Unknown Company"
        pos_str = current_position or "Role"
        lines.append(f"Current Role: {pos_str} at {comp_str}")

    # Profile Description
    desc = profile.get("profile_description")
    if desc:
        lines.append(f"Summary: {desc}")

    # Salary & Compensation block
    # HARD PRIVACY RULE: if showSalary is false/falsy, ZERO salary fields may appear in output string
    show_salary = profile.get("showSalary")
    if show_salary:
        exp_sal = profile.get("expected_salary")
        exp_inhand = profile.get("expected_inhand")
        exp_mode = profile.get("expected_mode")
        sal_parts = []
        if exp_sal:
            sal_parts.append(str(exp_sal))
        if exp_inhand:
            sal_parts.append(str(exp_inhand))
        if exp_mode:
            sal_parts.append(f"({exp_mode})")
        if sal_parts:
            lines.append(f"Compensation / Expected Salary: {' '.join(sal_parts)}")

    # Employment History / Jobs
    jobs = profile.get("jobs", [])
    if jobs:
        lines.append("\nWork History:")
        for j in jobs:
            comp = j.get("company") or "Unknown Company"
            desig = j.get("designation") or "Role"
            emp_type = j.get("employment_type")
            verif = "[VERIFIED]" if j.get("is_verified") else "[UNVERIFIED]"
            
            dates = ""
            start = j.get("from")
            end = "Present" if j.get("is_present") else j.get("to")
            if start:
                dates = f" ({start} to {end or 'N/A'})"

            emp_type_str = f" [{emp_type}]" if emp_type else ""
            lines.append(f"- {verif} {desig} at {comp}{emp_type_str}{dates}")

            skills = j.get("skills", [])
            if skills:
                lines.append(f"  Skills: {', '.join(skills)}")
    else:
        lines.append("\nWork History: None listed")

    # Education
    education = profile.get("education", [])
    if education:
        lines.append("\nEducation:")
        for edu in education:
            uni = edu.get("university") or ""
            course = edu.get("course") or ""
            c_type = f" ({edu.get('course_type')})" if edu.get("course_type") else ""
            loc = []
            if edu.get("city"):
                loc.append(edu.get("city"))
            if edu.get("state"):
                loc.append(edu.get("state"))
            if edu.get("country"):
                loc.append(edu.get("country"))
            loc_str = f" - {', '.join(loc)}" if loc else ""
            lines.append(f"- {course}{c_type} from {uni}{loc_str}")

    # Skills
    skills = profile.get("skills", [])
    if skills:
        lines.append(f"\nSkills: {', '.join(skills)}")

    # Languages
    languages = profile.get("languages", [])
    if languages:
        lang_strs = []
        for lang in languages:
            name = lang.get("name")
            if name:
                v = lang.get("verbal")
                w = lang.get("written")
                detail = []
                if v:
                    detail.append(f"Verbal: {v}/5")
                if w:
                    detail.append(f"Written: {w}/5")
                det_str = f" ({', '.join(detail)})" if detail else ""
                lang_strs.append(f"{name}{det_str}")
        if lang_strs:
            lines.append(f"Languages: {'; '.join(lang_strs)}")

    return "\n".join(lines)
