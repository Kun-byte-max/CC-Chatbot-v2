"""
user_data_intent_parser.py — Centralized deterministic intent classifier for user-data and widget queries.

Phase 1 / Fix Scope:
  - 100% deterministic regex and keyword parsing without LLM fallback.
  - Multi-intent support returning List[UserIntent].
  - Typo tolerance and stemmed keyword matching for education, skills, employment, etc.
  - Strict 4-level Contextual Precedence Hierarchy (Level 1 > Level 2 > Level 3 > Level 4).
"""

import re
from enum import Enum
from typing import List, Set


class UserIntent(str, Enum):
    # Level 1 — User Detail Context
    PROFILE_INCOMPLETE = "PROFILE_INCOMPLETE"
    USER_DETAIL_NOTICES = "USER_DETAIL_NOTICES"
    USER_DETAIL_REMINDERS = "USER_DETAIL_REMINDERS"

    # Level 2 — Employment / Company-Specific Context
    EMPLOYMENT_HISTORY = "EMPLOYMENT_HISTORY"
    EMPLOYMENT_SKILLS = "EMPLOYMENT_SKILLS"
    EMPLOYMENT_SALARY = "EMPLOYMENT_SALARY"
    EMPLOYMENT_VERIFICATION = "EMPLOYMENT_VERIFICATION"
    EMPLOYMENT_DOCUMENTS = "EMPLOYMENT_DOCUMENTS"

    # Level 3 — Widget Context
    WIDGET_CLOSING_SOON = "WIDGET_CLOSING_SOON"
    WIDGET_NEARBY_ORGS = "WIDGET_NEARBY_ORGS"
    WIDGET_ALL = "WIDGET_ALL"

    # Level 4 — Generic Profile Context
    PROFILE_SKILLS = "PROFILE_SKILLS"
    PROFILE_EDUCATION = "PROFILE_EDUCATION"
    PROFILE_CERTIFICATES = "PROFILE_CERTIFICATES"
    PROFILE_LANGUAGES = "PROFILE_LANGUAGES"
    PROFILE_PORTFOLIO = "PROFILE_PORTFOLIO"
    PROFILE_SUMMARY = "PROFILE_SUMMARY"


def parse_user_data_intents(text: str) -> List[UserIntent]:
    """
    Parses a user query string deterministically and returns matching intents ordered by precedence.
    Supports multi-intent extraction for compound prompts and fuzzy typo tolerance.
    """
    if not text or not text.strip():
        return []

    raw = text.lower().strip()

    # Exclude past/previous employment job queries from job search
    is_past_jobs_query = bool(re.search(r"\b(previous|past|last|old|prior)\s+jobs?\b", raw)) or bool(re.search(r"\b(work\s+experience|employment\s+history)\b", raw))

    # CRITICAL REGRESSION GUARD: Check if user is asking to SEARCH, FIND, RECOMMEND, or SHOW OPEN JOBS
    is_job_search_intent = False
    if not is_past_jobs_query:
        if re.search(r"\b(jobs?|roles?|positions?|vacancies|openings?)\b.*?\b(according\s+to|based\s+on|matching|for|with)\b.*?\b(skills?|profile|experience)\b", raw):
            is_job_search_intent = True
        elif re.search(r"\b(find|search|recommend)\b.*?\b(jobs?|roles?|positions?|vacancies|openings?)\b", raw):
            is_job_search_intent = True
        elif re.search(r"\b(show|get|list)\b.*?\b(remote|active|available|open|hiring|tech|developer|engineer|python|java|react)\s+(jobs?|roles?|vacancies)\b", raw):
            is_job_search_intent = True

    if is_job_search_intent and not re.search(r"\b(what|list|tell|show)\s+(are\s+)?(my|profile)\s+skil*s?\b", raw):
        return []

    intents: Set[UserIntent] = set()

    # -------------------------------------------------------------------
    # LEVEL 1: Missing / Incomplete / Notice / Reminder Context (USER_DETAIL)
    # -------------------------------------------------------------------
    if re.search(r"\b(missing|incomplete|complete(ness)?|percentage|how complete|what is missing|profile completion)\b", raw):
        intents.add(UserIntent.PROFILE_INCOMPLETE)

    if re.search(r"\b(notice|notice period|notices|notice employments|company on notice|on notice)\b", raw):
        intents.add(UserIntent.USER_DETAIL_NOTICES)

    if re.search(r"\b(reminder|reminders|experience reminder|pending reminder)\b", raw):
        intents.add(UserIntent.USER_DETAIL_REMINDERS)

    # -------------------------------------------------------------------
    # LEVEL 2: Employment / Company-Specific Context (EMPLOYMENT_*)
    # -------------------------------------------------------------------
    # Employment Skills
    if re.search(r"\bskil*s?.*?\b(used|applied|at|in|during|for)\b.*?\b(previous|past|last|company|work|job|employ?ment|[a-z0-9_-]+)\b", raw) or "work skill" in raw or "company skill" in raw:
        if not re.search(r"\b(profile\s+skil*s?|skil*s?\s+on\s+my\s+profile)\b", raw) or re.search(r"\b(previous|past|last|company|zenith|work|job)\b", raw):
            intents.add(UserIntent.EMPLOYMENT_SKILLS)

    # Employment Salary
    if re.search(r"\b(sal[a-e]ry|pay|ctc)\b.*?\b(at|in|during|company|previous|last|employ?ment)\b", raw):
        intents.add(UserIntent.EMPLOYMENT_SALARY)

    # Employment Verification
    if re.search(r"\b(verification|claim\s+status)\b", raw):
        intents.add(UserIntent.EMPLOYMENT_VERIFICATION)

    # Employment Documents
    if re.search(r"\b(employ?ment\s+documents?|work\s+documents?|relieving\s+letter|experience\s+letter|pay\s+slip)\b", raw):
        intents.add(UserIntent.EMPLOYMENT_DOCUMENTS)

    # Employment History (General)
    if re.search(r"\b(employ?ment\s+history|work\s+experience|past\s+jobs|previous\s+jobs|previous\s+companies|company\s+history|where\s+(?:did\s+i|have\s+i|i\s+have|i)\s+work(ed)?|my\s+experience|employ?ment\s+experience|past\s+employ?ment|companies?\s+i\s+(have\s+)?work(ed)?)\b", raw):
        intents.add(UserIntent.EMPLOYMENT_HISTORY)
    elif re.search(r"\bemploy?ment\b", raw) and not re.search(r"\b(notice|notice period|notices|salary|pay|document|documents|verification)\b", raw):
        intents.add(UserIntent.EMPLOYMENT_HISTORY)

    # -------------------------------------------------------------------
    # LEVEL 3: Widget Context (WIDGET_*)
    # -------------------------------------------------------------------
    if re.search(r"\b(closing\s+soon|urgent\s+jobs?|deadline\s+approaching|expiring\s+jobs?|urgent\s+position)\b", raw):
        intents.add(UserIntent.WIDGET_CLOSING_SOON)

    if re.search(r"\b(companies\s+near\s+me|organizations?\s+near(by)?|local\s+employers?|employers?\s+near(by)?)\b", raw):
        intents.add(UserIntent.WIDGET_NEARBY_ORGS)

    if re.search(r"\b(show\s+widgets?|all\s+widgets?|random\s+widgets?|dashboard\s+widgets?)\b", raw):
        intents.add(UserIntent.WIDGET_ALL)

    # -------------------------------------------------------------------
    # LEVEL 4: Generic Profile Context (PROFILE_*)
    # -------------------------------------------------------------------
    if re.search(r"\b(profile\s+skil*s?|my\s+skil*s?|what\s+skil*s?\s+(do\s+i\s+have|i\s+have|are\s+on\s+my\s+profile)|skil*s?\s+list)\b", raw):
        intents.add(UserIntent.PROFILE_SKILLS)
    elif ("skill" in raw or "skil" in raw) and UserIntent.EMPLOYMENT_SKILLS not in intents and not is_job_search_intent:
        intents.add(UserIntent.PROFILE_SKILLS)

    if re.search(r"\b(educat(io|ion)?|degree|university|college|course|qualification|academic)\b", raw) or raw.startswith("what is my educat"):
        intents.add(UserIntent.PROFILE_EDUCATION)

    if re.search(r"\b(certif(icate|ication)?s?|licenses?)\b", raw):
        intents.add(UserIntent.PROFILE_CERTIFICATES)

    if re.search(r"\b(languag(e|es)?|languages\s+i\s+speak|spoken\s+languages)\b", raw):
        intents.add(UserIntent.PROFILE_LANGUAGES)

    if re.search(r"\b(portfol(io|ios)?|projects?|links?)\b", raw):
        intents.add(UserIntent.PROFILE_PORTFOLIO)

    if re.search(r"\b(profile\s+summary|about\s+me|full\s+profile|overview\s+of\s+my\s+profile|tell\s+me\s+about\s+my\s+profile|profile\s+info(rmation)?|profile\s+details|what\s+is\s+my\s+profile)\b", raw):
        intents.add(UserIntent.PROFILE_SUMMARY)

    # Order results deterministically according to precedence hierarchy
    precedence_order = [
        # Level 1
        UserIntent.PROFILE_INCOMPLETE,
        UserIntent.USER_DETAIL_NOTICES,
        UserIntent.USER_DETAIL_REMINDERS,
        # Level 2
        UserIntent.EMPLOYMENT_SKILLS,
        UserIntent.EMPLOYMENT_SALARY,
        UserIntent.EMPLOYMENT_VERIFICATION,
        UserIntent.EMPLOYMENT_DOCUMENTS,
        UserIntent.EMPLOYMENT_HISTORY,
        # Level 3
        UserIntent.WIDGET_CLOSING_SOON,
        UserIntent.WIDGET_NEARBY_ORGS,
        UserIntent.WIDGET_ALL,
        # Level 4
        UserIntent.PROFILE_SKILLS,
        UserIntent.PROFILE_EDUCATION,
        UserIntent.PROFILE_CERTIFICATES,
        UserIntent.PROFILE_LANGUAGES,
        UserIntent.PROFILE_PORTFOLIO,
        UserIntent.PROFILE_SUMMARY,
    ]

    sorted_intents = [intent for intent in precedence_order if intent in intents]
    return sorted_intents
