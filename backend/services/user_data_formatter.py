"""
user_data_formatter.py — Natural language response formatter for user-data and widget queries.

Phase 4 / Fix Scope:
  - Formats extracted JSON into clean, user-facing natural language text.
  - Complete support for LANGUAGES, PORTFOLIO, SALARY, CLOSING_SOON, NEARBY_ORGS, WIDGET_ALL.
  - Company-specific filtering for employment queries.
  - "Previous company" semantics resolution.
  - Zero raw JSON or credential leakage.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from backend.services.user_data_intent_parser import UserIntent

log = logging.getLogger(__name__)


def _extract_company_name_from_query(query: str, available_companies: List[str]) -> Optional[str]:
    """
    Matches explicit company names mentioned in the prompt against available company names from employment history.
    Also handles "previous company" / "last company" / "latest company" references.
    """
    if not query or not available_companies:
        return None

    q_lower = query.lower()

    # Direct substring match against available companies
    for comp in available_companies:
        if comp and comp.lower() in q_lower:
            return comp

    # Handles "previous company" / "last company" / "latest company" -> Returns most recent (first) company
    if re.search(r"\b(previous|last|recent|latest)\s+company\b", q_lower):
        return available_companies[0]

    return None


def format_single_intent(
    intent: UserIntent,
    extracted_data: Dict[str, Any],
    api_response: Dict[str, Any],
    query: str = ""
) -> str:
    """
    Formats extracted data for a single intent with explicit error vs empty data handling and company filtering.
    """
    # Check for API / HTTP / Auth Failure
    if isinstance(api_response, dict):
        status_code = api_response.get("status_code")
        if status_code == 401 or api_response.get("error") == "401":
            return "Please log in to view your profile details."
        if api_response.get("status") is False and (api_response.get("error") or status_code):
            return "I couldn't retrieve your information right now due to a service connection issue."

    # 1. PROFILE_INCOMPLETE
    if intent == UserIntent.PROFILE_INCOMPLETE:
        percentage = extracted_data.get("profile_percentage")
        uncomplete = extracted_data.get("uncomplete") or []
        incomplete = extracted_data.get("incomplete") or []

        if percentage is None and not uncomplete and not incomplete:
            return "I couldn't find any profile completeness data recorded on your account."

        lines = []
        if percentage is not None:
            lines.append(f"Your profile is **{percentage}% complete**.")

        if uncomplete:
            lines.append("**Missing Sections:**")
            for item in uncomplete:
                lines.append(f"• {item}")
        elif incomplete:
            lines.append("**Incomplete Details:**")
            for item in incomplete:
                key = item.get("key")
                val = item.get("value")
                lines.append(f"• {key} ({val} impact)")
        else:
            lines.append("Great job! Your profile details appear to be fully complete.")

        return "\n".join(lines)

    # 2. USER_DETAIL_NOTICES
    elif intent == UserIntent.USER_DETAIL_NOTICES:
        notices = extracted_data.get("noticeEmployments") or []
        notice_period = extracted_data.get("notice_period_name")

        if not notices:
            return "You currently have no active employment notice records on file."

        count = len(notices)
        period_str = f" ({notice_period})" if notice_period else ""
        return f"You are currently on notice for **{count} company record(s)**{period_str} (Company IDs: {', '.join(notices)})."

    # 3. USER_DETAIL_REMINDERS
    elif intent == UserIntent.USER_DETAIL_REMINDERS:
        has_reminder = extracted_data.get("reminderExperience")
        reminders = extracted_data.get("reminderExperienceList") or []

        if not has_reminder and not reminders:
            return "You have no pending experience reminders at this time."

        lines = ["**Pending Experience Reminders:**"]
        for r in reminders:
            comp = r.get("company") or "Company"
            desig = r.get("designation") or "Position"
            lines.append(f"• {desig} at Company #{comp}")

        return "\n".join(lines)

    # 4. EMPLOYMENT_HISTORY
    elif intent == UserIntent.EMPLOYMENT_HISTORY:
        history = extracted_data.get("employment_history") or []
        if not history:
            return "I couldn't find any employment history recorded on your account."

        available_companies = [comp.get("company") for comp in history if comp.get("company")]
        target_company = _extract_company_name_from_query(query, available_companies)

        if target_company:
            history = [comp for comp in history if comp.get("company") and comp.get("company").lower() == target_company.lower()]

        if not history:
            return f"I couldn't find any employment history recorded for **{target_company}**."

        lines = ["**Your Work Experience:**"]
        for comp in history:
            name = comp.get("company") or "Company"
            roles = comp.get("roles") or []
            verified_badge = " ✓ (Verified)" if comp.get("is_verified") else ""
            lines.append(f"• **{name}**{verified_badge}")

            for r in roles:
                desig = r.get("designation") or "Role"
                j_date = r.get("joining_date") or ""
                w_date = r.get("worked_till_date") or ("Present" if r.get("still_working") == "1" else "")
                date_str = f" ({j_date} to {w_date})" if j_date else ""
                lines.append(f"   - {desig}{date_str}")

        return "\n".join(lines)

    # 5. EMPLOYMENT_SKILLS
    elif intent == UserIntent.EMPLOYMENT_SKILLS:
        emp_skills = extracted_data.get("employment_skills") or []
        if not emp_skills:
            return "I couldn't find any work skills recorded under your employment history."

        available_companies = list(dict.fromkeys([s.get("company") for s in emp_skills if s.get("company")]))
        target_company = _extract_company_name_from_query(query, available_companies)

        if target_company:
            emp_skills = [s for s in emp_skills if s.get("company") and s.get("company").lower() == target_company.lower()]

        if not emp_skills:
            target_name = target_company or "the specified company"
            return f"I couldn't find any work skills recorded for **{target_name}**."

        skills_by_comp = {}
        for item in emp_skills:
            comp = item.get("company") or "Previous Employment"
            sname = item.get("name")
            if sname:
                skills_by_comp.setdefault(comp, []).append(sname)

        lines = ["**Skills Used in Previous Employment:**"]
        for comp, sk_list in skills_by_comp.items():
            lines.append(f"• **{comp}**: {', '.join(sk_list)}")

        return "\n".join(lines)

    # 6. EMPLOYMENT_SALARY
    elif intent == UserIntent.EMPLOYMENT_SALARY:
        salaries = extracted_data.get("employment_salary") or []
        if not salaries:
            return "I couldn't find any salary details recorded under your employment history."

        available_companies = list(dict.fromkeys([s.get("company") for s in salaries if s.get("company")]))
        target_company = _extract_company_name_from_query(query, available_companies)

        if target_company:
            salaries = [s for s in salaries if s.get("company") and s.get("company").lower() == target_company.lower()]

        if not salaries:
            target_name = target_company or "the specified company"
            return f"I couldn't find any salary records listed for **{target_name}**."

        lines = ["**Employment Salary Details:**"]
        for item in salaries:
            comp = item.get("company") or "Company"
            desig = item.get("designation") or "Role"
            sal = item.get("salary")
            mode = item.get("salary_mode") or "Per Annum"
            inhand = item.get("salary_inhand") or ""
            inhand_str = f" ({inhand})" if inhand else ""
            lines.append(f"• **{desig}** at **{comp}**: ₹{sal} {mode}{inhand_str}")

        return "\n".join(lines)

    # 7. WIDGET_CLOSING_SOON
    elif intent == UserIntent.WIDGET_CLOSING_SOON:
        widgets = extracted_data.get("widgets") or []
        closing_widget = next((w for w in widgets if "closing" in str(w.get("slug")).lower() or "closing" in str(w.get("heading")).lower() or w.get("api_slug") == "auth-all-job"), None)

        items = closing_widget.get("items") if closing_widget else []
        if not items:
            return "There are currently no positions closing soon on CollarCheck."

        lines = ["**Positions Closing Soon:**"]
        for item in items[:5]:
            title = item.get("job_title") or "Position"
            comp = item.get("company") or "Employer"
            loc = item.get("location") or "India"
            url = item.get("url")
            link_str = f" - [View Job]({url})" if url else ""
            lines.append(f"• **{title}** at **{comp}** ({loc}){link_str}")

        return "\n".join(lines)

    # 8. WIDGET_NEARBY_ORGS
    elif intent == UserIntent.WIDGET_NEARBY_ORGS:
        widgets = extracted_data.get("widgets") or []
        nearby_widget = next((w for w in widgets if "nearby" in str(w.get("slug")).lower() or "near" in str(w.get("heading")).lower() or w.get("api_slug") == "nearby-company"), None)

        items = nearby_widget.get("items") if nearby_widget else []
        if not items:
            return "There are currently no nearby organizations listed for your location."

        lines = ["**Organizations Near You:**"]
        for item in items[:5]:
            name = item.get("company") or item.get("name") or "Organization"
            city = item.get("city_name") or item.get("location") or ""
            dist = item.get("distance")
            dist_str = f" ({dist} km away)" if dist else ""
            ind = item.get("industry_name")
            ind_str = f" - {ind}" if ind else ""
            lines.append(f"• **{name}**{dist_str}{ind_str}")

        return "\n".join(lines)

    # 9. WIDGET_ALL
    elif intent == UserIntent.WIDGET_ALL:
        widgets = extracted_data.get("widgets") or []
        if not widgets:
            return "There are currently no platform widgets available on your dashboard."

        lines = ["**Platform Dashboard Widgets:**"]
        for w in widgets:
            heading = w.get("heading") or w.get("slug") or "Widget"
            count = w.get("list_count") or 0
            lines.append(f"• **{heading}**: {count} active items")

        return "\n".join(lines)

    # 10. PROFILE_SKILLS
    elif intent == UserIntent.PROFILE_SKILLS:
        prof_skills = extracted_data.get("profile_skills") or []
        if not prof_skills:
            return "I couldn't find any skills listed on your profile."

        skill_names = [s.get("skill") for s in prof_skills if s.get("skill")]
        if not skill_names:
            return "I couldn't find any skills listed on your profile."

        return f"**Your Profile Skills:** {', '.join(skill_names)}."

    # 11. PROFILE_EDUCATION
    elif intent == UserIntent.PROFILE_EDUCATION:
        edu_list = extracted_data.get("education") or []
        if not edu_list:
            return "I couldn't find any education background recorded on your profile."
        return "Here are your education details:"

    # 12. PROFILE_CERTIFICATES
    elif intent == UserIntent.PROFILE_CERTIFICATES:
        cert_list = extracted_data.get("certificates") or []
        if not cert_list:
            return "I couldn't find any certificates listed on your profile."

        lines = ["**Your Certifications:**"]
        for cert in cert_list:
            course = cert.get("course") or "Certificate"
            uni = cert.get("university") or ""
            uni_str = f" ({uni})" if uni else ""
            lines.append(f"• {course}{uni_str}")

        return "\n".join(lines)

    # 13. PROFILE_LANGUAGES
    elif intent == UserIntent.PROFILE_LANGUAGES:
        lang_list = extracted_data.get("languages") or []
        if not lang_list:
            return "I couldn't find any spoken languages listed on your profile."

        lines = ["**Spoken Languages:**"]
        for lang in lang_list:
            name = lang.get("name") or "Language"
            verbal = lang.get("verbal")
            written = lang.get("written")
            levels = []
            if verbal:
                levels.append(f"Verbal Level {verbal}")
            if written:
                levels.append(f"Written Level {written}")
            level_str = f" ({', '.join(levels)})" if levels else ""
            lines.append(f"• **{name}**{level_str}")

        return "\n".join(lines)

    # 14. PROFILE_PORTFOLIO
    elif intent == UserIntent.PROFILE_PORTFOLIO:
        port_list = extracted_data.get("portfolio") or []
        if not port_list:
            return "I couldn't find any portfolio entries listed on your profile."

        lines = ["**Your Portfolio & Projects:**"]
        for p in port_list:
            title = p.get("title") or "Project"
            desc = p.get("description") or ""
            url = p.get("url")
            link_str = f" - [View Portfolio]({url})" if url else ""
            desc_str = f": {desc}" if desc else ""
            lines.append(f"• **{title}**{link_str}{desc_str}")

        return "\n".join(lines)

    # 15. PROFILE_SUMMARY
    elif intent == UserIntent.PROFILE_SUMMARY:
        ps = extracted_data.get("profile_summary") or {}
        name = ps.get("name") or "User"
        email = ps.get("email")
        phone = ps.get("phone")
        dob = ps.get("dob")
        
        loc_parts = [p for p in [ps.get("city_name"), ps.get("state_name"), ps.get("country_name")] if p]
        location = ", ".join(loc_parts) if loc_parts else ps.get("state_name") or ps.get("country_name") or "Not provided"
        
        work_status = ps.get("work_status_name") or "Not provided"
        
        pos = ps.get("current_position_name")
        comp = ps.get("current_company_name")
        role_str = f"{pos} at {comp}" if pos and comp else (pos or comp or "Not provided")
        
        desc = ps.get("profile_description") or ""
        skills = ps.get("skills") or []

        lines = [
            f"Here is your profile information:\n",
            f"**Name:** {name}",
            f"**Email:** {email or 'Not provided'}",
            f"**Phone:** {phone or 'Not provided'}",
            f"**Date of Birth:** {dob or 'Not provided'}",
            f"**Location:** {location}",
            f"**Work Status:** {work_status}",
            f"**Current Role:** {role_str}",
            f"**Profile Description:** {desc}",
        ]
        
        if skills:
            lines.append("\n**Skills:**")
            for skill in skills:
                lines.append(f"- {skill}")

        return "\n".join(lines)

    return "Your requested information was processed."


def format_multi_intent_response(
    intents: List[UserIntent],
    extracted_data_by_intent: Dict[UserIntent, Dict[str, Any]],
    api_responses_by_endpoint: Dict[str, Any],
    query: str = ""
) -> str:
    if not intents:
        return "How can I assist you with your profile or employment details?"

    formatted_sections = []
    for intent in intents:
        data = extracted_data_by_intent.get(intent) or {}
        from backend.services.user_data_service import INTENT_ENDPOINT_MAP
        ep_key = INTENT_ENDPOINT_MAP.get(intent)
        api_resp = api_responses_by_endpoint.get(ep_key) or {}

        section_text = format_single_intent(intent, data, api_resp, query=query)
        formatted_sections.append(section_text)

    return "\n\n".join(formatted_sections)
