import os
import time
import logging
from typing import Dict, Any, Optional, List

log = logging.getLogger(__name__)

# Global in-memory session state dictionary
_SESSION_STATES: Dict[str, Dict[str, Any]] = {}
SESSION_TTL_SECONDS = 1800  # 30 minutes


def get_pagination_state(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves active pagination state for a session if not expired.
    """
    pid = os.getpid()
    log.info("[SESSION_TRACE][PID=%d][get_pagination_state] incoming session_id=%s, store_keys=%s",
             pid, session_id, list(_SESSION_STATES.keys()))
    if not session_id:
        return None

    state = _SESSION_STATES.get(session_id)
    if not state:
        return None

    # Check TTL expiry
    last_active = state.get("_last_active", 0)
    if time.time() - last_active > SESSION_TTL_SECONDS:
        log.info("[SESSION_TRACE][PID=%d] Session state expired for session_id=%s", pid, session_id)
        _SESSION_STATES.pop(session_id, None)
        return None

    return state.get("pagination")


def set_pagination_state(session_id: str, pagination_data: Dict[str, Any]) -> None:
    """
    Saves or updates pagination state for a session.
    """
    pid = os.getpid()
    if not session_id:
        return

    if session_id not in _SESSION_STATES:
        _SESSION_STATES[session_id] = {"_last_active": time.time()}

    _SESSION_STATES[session_id]["_last_active"] = time.time()
    _SESSION_STATES[session_id]["pagination"] = pagination_data
    log.info("[SESSION_TRACE][PID=%d][set_pagination_state] Saved pagination for session_id=%s, store_keys_after=%s",
             pid, session_id, list(_SESSION_STATES.keys()))


def get_recommendation_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves active recommendation session state (ranked snapshots) for session_id if not expired.
    """
    pid = os.getpid()
    store_keys = list(_SESSION_STATES.keys())
    has_key = session_id in _SESSION_STATES if session_id else False
    log.info("[SESSION_TRACE][PID=%d][get_recommendation_session] lookup session_id=%s, has_key=%s, store_keys=%s",
             pid, session_id, has_key, store_keys)

    if not session_id:
        return None

    state = _SESSION_STATES.get(session_id)
    if not state:
        log.info("[SESSION_TRACE][PID=%d][get_recommendation_session] RESULT=None for session_id=%s", pid, session_id)
        return None

    last_active = state.get("_last_active", 0)
    if time.time() - last_active > SESSION_TTL_SECONDS:
        log.info("[SESSION_TRACE][PID=%d] Recommendation session expired for session_id=%s", pid, session_id)
        _SESSION_STATES.pop(session_id, None)
        return None

    res = state.get("recommendation_context")
    log.info("[SESSION_TRACE][PID=%d][get_recommendation_session] RESULT=%s for session_id=%s",
             pid, "FOUND" if res is not None else "NO_REC_CTX", session_id)
    return res


def set_recommendation_session(
    session_id: str,
    query_key: str,
    ranked_jobs: List[Any],
    current_page: int = 1,
    page_size: int = 5,
    total_jobs: int = 0,
    last_referenced_job_id: Optional[Any] = None,
) -> None:
    """
    Stores complete pre-computed RecommendationResult snapshot list under session_id.
    """
    pid = os.getpid()
    log.info("[SESSION_TRACE][PID=%d][set_recommendation_session] Storing for session_id=%s, query_key=%s, count=%d",
             pid, session_id, query_key, len(ranked_jobs))

    if not session_id:
        return

    if session_id not in _SESSION_STATES:
        _SESSION_STATES[session_id] = {}

    _SESSION_STATES[session_id]["_last_active"] = time.time()
    _SESSION_STATES[session_id]["recommendation_context"] = {
        "query_key": query_key,
        "ranked_jobs": ranked_jobs,
        "current_page": current_page,
        "page_size": page_size,
        "total_jobs": total_jobs or len(ranked_jobs),
        "last_referenced_job_id": last_referenced_job_id,
    }
    log.info("[SESSION_TRACE][PID=%d][set_recommendation_session] STORED SUCCESS session_id=%s, store_keys_after=%s",
             pid, session_id, list(_SESSION_STATES.keys()))


def update_last_referenced_job_id(session_id: str, job_id: Any) -> None:
    """
    Updates last_referenced_job_id in active session recommendation context.
    """
    pid = os.getpid()
    ctx = get_recommendation_session(session_id)
    if ctx is not None and job_id is not None:
        ctx["last_referenced_job_id"] = job_id
        _SESSION_STATES[session_id]["_last_active"] = time.time()
        log.info("[SESSION_TRACE][PID=%d] Updated last_referenced_job_id=%s for session_id=%s", pid, job_id, session_id)


def clear_pagination_state(session_id: str) -> None:
    """
    Clears pagination state for a session.
    """
    pid = os.getpid()
    if session_id in _SESSION_STATES:
        _SESSION_STATES.pop(session_id, None)
        log.info("[SESSION_TRACE][PID=%d] Cleared pagination state for session_id=%s", pid, session_id)

