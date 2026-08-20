import logging
from typing import Optional, Tuple

try:
    from backend.services.ranking_service import EMPLOYER_SESSIONS
except ModuleNotFoundError:
    from services.ranking_service import EMPLOYER_SESSIONS  # type: ignore

log = logging.getLogger(__name__)

PROFILE_HINTS = (
    "i am", "i'm", "my name", "my skill", "i know", "i work", "i worked",
    "add ", "remove ", "update my", "i have", "years of experience",
    "i studied", "graduated", "my email", "my phone", "my location",
    "i live", "based in", "certification", "certified", "resume", "cv",
)

SMALLTALK_EXACT = {
    "hi", "hello", "hey", "yo", "hola",
    "thanks", "thank you", "thanks!", "ty",
    "ok", "okay", "k", "cool", "nice", "great",
    "yes", "no", "yeah", "yep", "nope",
    "bye", "goodbye", "good morning", "good evening", "good night",
}

def might_be_profile_update(msg: str) -> bool:
    m = (msg or "").lower().strip()
    if len(m) < 8:
        return False
    return any(h in m for h in PROFILE_HINTS)

def is_definitely_not_search(msg: str) -> bool:
    m = (msg or "").lower().strip().rstrip("!.?")
    return m in SMALLTALK_EXACT

def should_run_profile_parse(role: str, user_message: str) -> Tuple[bool, str]:
    if role != "employee":
        return False, "skip_role"
    m = (user_message or "").strip()
    if len(m) < 8:
        return False, "skip_too_short"
    if not might_be_profile_update(m):
        return False, "skip_no_hint"
    return True, "ran_hint_matched"

def should_run_profile_parse_safe(role: str, user_message: str) -> Tuple[bool, str]:
    try:
        return should_run_profile_parse(role, user_message)
    except Exception:
        log.exception("Gate function failed, running profile_parse fail-open")
        return True, "ran_gate_error"

def should_run_search_parse(role: str, user_message: str, session_id: Optional[str] = None) -> Tuple[bool, str]:
    # B3 Employer Session Override check (side-effect free direct lookup)
    if role == "employer":
        sid = f"employer_{session_id}" if session_id else "employer_default_session"
        session = EMPLOYER_SESSIONS.get(sid)
        if session and session.get("current_step", "idle") != "idle":
            return True, "ran_employer_session_override"

    if is_definitely_not_search(user_message):
        return False, "skip_exact_smalltalk"

    return True, "ran_default"

def should_run_search_parse_safe(role: str, user_message: str, session_id: Optional[str] = None) -> Tuple[bool, str]:
    try:
        return should_run_search_parse(role, user_message, session_id=session_id)
    except Exception:
        log.exception("Gate function failed, running search_parse fail-open")
        return True, "ran_gate_error"
