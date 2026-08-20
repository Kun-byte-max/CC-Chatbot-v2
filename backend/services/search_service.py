try:
    from backend.repositories.job_repository import JobRepository
    from backend.utils.utils import is_career_query, is_faq_query, smart_extract_terms
except ModuleNotFoundError:
    from repositories.job_repository import JobRepository
    from utils.utils import is_career_query, is_faq_query, smart_extract_terms

class SearchService:
    @staticmethod
    def get_db_context(user_message: str) -> str:
        if not (is_career_query(user_message) or is_faq_query(user_message)):
            return ""

        parts = []

        if is_career_query(user_message):
            role_keyword, location = smart_extract_terms(user_message)
            jobs = JobRepository.search_jobs(role_keyword, location)
            total = len(jobs)
            role_label = role_keyword if role_keyword else "all roles"
            loc_label  = location    if location    else "any location"

            parts.append("## LIVE JOB DATA FROM COLLARCHECK DATABASE")
            parts.append("Role searched: " + role_label + "  |  Location: " + loc_label)
            parts.append("Total jobs found: " + str(total))
            parts.append("")

            if jobs:
                for j in jobs:
                    loc_str = j["state"] if j["state"] else "Location not specified"
                    job_url = f"https://www.collarcheck.com/jobs-details/{j['id']}"
                    parts.append(
                        "JOB: " + str(j["title"]) + "\n"
                        "  Department: " + str(j["department"] or "General") +
                        " | Location: " + loc_str +
                        " | Experience: " + str(j["experience"]) + " yrs" +
                        " | Vacancies: " + str(j["vacancy"] or "Open") +
                        " | Mode: " + str(j["mode"]) + "\n"
                        "  Details: " + str(j["preview"]) + "\n"
                    )
                parts.append(
                    "\n[MANDATORY AI INSTRUCTION]\n"
                    "The database returned " + str(total) + " real job(s). You MUST:\n"
                    "1. Start with: 'I found " + str(total) + " role(s) matching your search.'\n"
                    "2. List EVERY job — title, department, location, experience, vacancies, mode, and always provide its specific Link formatted as a markdown link: [Apply / View Details](URL).\n"
                    "3. NEVER say visit the website and search as the main answer.\n"
                    "4. End with: 'To apply, visit collarcheck.com/jobs'\n"
                )
            else:
                parts.append(
                    "No jobs matched for role='" + role_label + "' location='" + loc_label + "'.\n"
                    "[AI INSTRUCTION] Tell the user no exact matches were found. "
                    "Suggest collarcheck.com/jobs for the complete real-time listing. "
                    "Offer to search a related or broader term."
                )

        if is_faq_query(user_message):
            faqs = JobRepository.search_faqs(keyword=user_message[:100])
            if faqs:
                parts.append("\n## COLLARCHECK FAQ DATA FROM DATABASE")
                for f in faqs:
                    parts.append("Q: " + f["question"] + "\nA: " + f["answer"] + "\n")
                parts.append("[AI INSTRUCTION] Use the FAQ answers above directly in your response.")

        return "\n".join(parts)
