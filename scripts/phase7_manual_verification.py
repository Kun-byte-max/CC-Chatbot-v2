"""
phase7_manual_verification.py — Comprehensive manual verification driver for Phase 7.
Connects to live /chat endpoint with real user authentication headers and records exact query execution logs.
"""

import os
import sys
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

load_dotenv(dotenv_path=root / ".env", override=True)

TOKEN = os.getenv("PLATFORM_TEST_TOKEN", "") or os.getenv("EMPLOYEE_JWT", "") or os.getenv("PLATFORM_ADMIN_TOKEN", "")
USER_ID = os.getenv("PLATFORM_TEST_USER_ID", "200014")
USER_SLUG = os.getenv("PLATFORM_TEST_USER_SLUG", "rakesh-maurya-cce130000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")

def run_chat_query(query: str) -> dict:
    url = f"{BACKEND_URL}/chat"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}" if not TOKEN.startswith("Bearer ") else TOKEN,
        "X-Auth-Token": TOKEN,
        "X-User-Id": str(USER_ID),
    }
    payload = {
        "messages": [{"role": "user", "content": query}],
        "session_id": "manual_verification_session"
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(url, json=payload, headers=headers)
            if res.status_code == 200:
                return res.json()
            return {"status": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        return {"status": False, "error": str(e)}

def main():
    print("=" * 80)
    print("PHASE 7: MANUAL CHATBOT VERIFICATION LOG")
    print("=" * 80)

    from backend.services.user_data_intent_parser import parse_user_data_intents
    from backend.services.user_data_service import resolve_required_endpoints

    test_queries = [
        # Profile Queries
        "What are my skills?",
        "What is my education?",
        "What certificates do I have?",
        "What languages do I know?",
        "Show me my portfolio.",

        # Employment Queries
        "Tell me about my employment history.",
        "Where have I worked?",
        "What was my designation at SP HUMANS PRIVATE LIMITEDff?",
        "What skills did I use at SP HUMANS PRIVATE LIMITEDff?",
        "What was my salary at SP HUMANS PRIVATE LIMITEDff?",

        # User-Detail Queries
        "What is missing from my profile?",
        "What sections of my profile are incomplete?",
        "What reminders do I have?",
        "Do I have any employment notices?",

        # Widget Queries
        "Show me jobs that are closing soon.",
        "Show me organizations near me.",

        # Multi-Intent Queries
        "Tell me my skills and education.",
        "Tell me my skills and employment history.",
        "Tell me my profile skills and the skills I used at my previous company.",

        # Regression Queries
        "Find remote Python jobs.",
        "Show me jobs according to my skills.",
        "Hi",
        "Thanks"
    ]

    results = []

    for idx, q in enumerate(test_queries, 1):
        # Determine intent parser resolution locally for audit log
        intents = parse_user_data_intents(q)
        endpoints = resolve_required_endpoints(intents)
        call_count = len(endpoints)

        # Call live /chat server
        chat_resp = run_chat_query(q)
        reply = chat_resp.get("reply", "") if isinstance(chat_resp, dict) else str(chat_resp)

        result_item = {
            "query": q,
            "intents": [str(i) for i in intents],
            "endpoints": endpoints,
            "call_count": call_count,
            "reply": reply[:300] + ("..." if len(reply) > 300 else ""),
            "success": chat_resp.get("success", False) if isinstance(chat_resp, dict) else False
        }
        results.append(result_item)

        safe_reply = result_item['reply'].encode('utf-8', errors='ignore').decode('utf-8')
        print(f"\n[{idx}/{len(test_queries)}] Query: \"{q}\"")
        print(f"  Intents Detected : {result_item['intents']}")
        print(f"  Endpoints        : {result_item['endpoints']} ({call_count} calls)")
        print(f"  Chatbot Response : {safe_reply}")

    # Save verification report
    report_path = root / "data" / "phase7_manual_verification_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"VERIFICATION COMPLETE. LOG persistent at: {report_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
