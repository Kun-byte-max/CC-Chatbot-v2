import asyncio
import json
import logging
import httpx
from typing import Dict, Any, Optional

try:
    from backend.services.llm_service import LLMService
    from backend.repositories.db import get_db
except ModuleNotFoundError:
    from services.llm_service import LLMService  # type: ignore
    from repositories.db import get_db  # type: ignore

log = logging.getLogger(__name__)

async def parse_search_query(message: str, role: str, messages: list = None, user_location: Optional[str] = None) -> Dict[str, Any]:
    """
    Parses unstructured user message into structured search criteria using the LLM.
    """
    user_loc_info = f"\nUser's Stored/Current Resolved Location: {user_location}" if user_location else ""
    prompt = f"""
    You are an AI assistant designed to extract search criteria from user messages for a career portal search.
    The user is a/an {role}.{user_loc_info}
    
    Extract the following details from the user's message:
    - keyword: The designation, job title, or role name (e.g., "data analyst", "sales manager", "python developer"). CRITICAL: If a specific role or job title is mentioned anywhere in the user's message (e.g., "suggest me data analyst jobs", "show me civil engineer roles"), you MUST extract that exact title (e.g., "data analyst") into keyword. ONLY return null for keyword if NO specific role or job title is mentioned (e.g. "suggest me jobs", "show jobs for my profile").
    - location: The state or city name mentioned (e.g., "pune", "maharashtra", "delhi"). If the user asks for jobs/candidates "near me", "nearby", "around me", "in my area", or "close to me", set location to the city or state from User's Stored/Current Resolved Location (e.g. if resolved location is "Pune, Maharashtra, India", set location to "Pune" or "Maharashtra").
    - skills: A list of specific skill keywords explicitly requested in the message (e.g., ["python", "javascript"]). Do not invent skills.
    - experience: Years of experience required (e.g., 0 for "fresher" or "freshers" or "no experience", 2 for "2 years", 5 for "5 years").
    - salary: Minimum salary numeric value or salary bracket if mentioned (e.g., 15000).
    - job_mode: One of "office", "home", or "hybrid".
    - urgent: True if they explicitly mention needing someone urgently, immediately, or fast, otherwise False.
    - sort: If they ask to sort/order by something, identify if they want:
      - "experience" (e.g., "sort by experience", "highest experience first")
      - "create_ts" (e.g., "most recent", "newest", "latest")
      - "salary" (e.g., "highest paying", "best salary")
      - Otherwise null.
    is_search_intent: True if the message represents an actual query to search for jobs or candidates (including "suggest jobs related to my skills/profile"). False if it is just small talk, greetings, FAQs (like "what is collarcheck"), or general talk.
    is_recommendation_intent: True if the user asks for job recommendations based on their profile, skills, experience, suitability, or general fit (e.g. "jobs for me", "suggest jobs for me", "find jobs for me", "recommend jobs for me", "show jobs according to my skills", "find matching jobs", "which jobs suit my profile").

    
    Response MUST be a single raw JSON object matching this schema:
    {{
      "keyword": "string or null",
      "location": "string or null",
      "skills": ["string"] or null,
      "experience": int or null,
      "salary": int or null,
      "job_mode": "string or null",
      "urgent": boolean or null,
      "sort": "string or null",
      "is_search_intent": boolean,
      "is_recommendation_intent": boolean
    }}
    """
    
    history_str = ""
    if messages:
        recent = messages[-5:]
        formatted_msgs = []
        for m in recent:
            if isinstance(m, dict):
                formatted_msgs.append(f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}")
            else:
                formatted_msgs.append(f"{m.role.capitalize()}: {m.content}")
        history_str = "\n    Conversation History:\n    " + "\n    ".join(formatted_msgs) + "\n"

    prompt += f"""{history_str}
    User message: "{message}"
    
    If the user's message is a follow-up, use the conversation history to fill in the missing details (like the job role or location they were previously searching for).
    JSON:
    """
    try:
        completion = await LLMService.get_chat_completion(prompt, [], timeout=12.0)
        cleaned_completion = completion.strip()
        if "```json" in cleaned_completion:
            cleaned_completion = cleaned_completion.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_completion:
            cleaned_completion = cleaned_completion.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(cleaned_completion)
        return parsed
    except (httpx.TimeoutException, asyncio.TimeoutError):
        log.warning("extraction_timeout parser=search_parse")
        return {
            "keyword": message,
            "location": None,
            "skills": None,
            "experience": None,
            "salary": None,
            "job_mode": None,
            "urgent": False,
            "sort": None,
            "is_search_intent": True
        }
    except Exception as e:
        log.exception("Error parsing search query with LLM")
        return {
            "keyword": None,
            "location": None,
            "skills": None,
            "experience": None,
            "salary": None,
            "job_mode": None,
            "urgent": False,
            "sort": None,
            "is_search_intent": False
        }

def resolve_state_id(state_name: str) -> Optional[int]:
    """
    Query the SQLite database to resolve state name to its state ID.
    """
    if not state_name:
        return None
    state_name_lower = state_name.lower().strip()
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Try exact match first
        cursor.execute(
            "SELECT id FROM cyb_state WHERE LOWER(name) = %s AND status = 1 AND country = 101",
            (state_name_lower,)
        )
        row = cursor.fetchone()
        if row:
            return int(row[0])
            
        # Try substring match
        cursor.execute(
            "SELECT id FROM cyb_state WHERE LOWER(name) LIKE %s AND status = 1 AND country = 101",
            (f"%{state_name_lower}%",)
        )
        row = cursor.fetchone()
        if row:
            return int(row[0])
    except Exception:
        log.exception("Failed to query state ID from SQLite")
    finally:
        conn.close()
    return None
