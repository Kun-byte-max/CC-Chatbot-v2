import os
import sys
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Union
import httpx
from dotenv import load_dotenv

# Add root project folder to sys.path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

load_dotenv()

BASE_URL = os.getenv("PLATFORM_API_BASE", "https://admin.collarcheck.com/wapi").rstrip("/")
TOKEN = os.getenv("PLATFORM_TEST_TOKEN", "") or os.getenv("EMPLOYEE_JWT", "") or os.getenv("PLATFORM_ADMIN_TOKEN", "")
USER_ID = os.getenv("PLATFORM_TEST_USER_ID", "200014")
USER_SLUG = os.getenv("PLATFORM_TEST_USER_SLUG", "rakesh-maurya-cce130000")

SENSITIVE_KEY_PATTERNS = [
    r"token", r"jwt", r"password", r"passwd", r"secret", r"cookie",
    r"session", r"auth", r"api_key", r"apikey", r"bearer", r"hash"
]

JWT_REGEX = re.compile(r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*")

def redact_sensitive(obj: Any) -> Any:
    """
    Recursively redacts sensitive values, keys, tokens, JWTs, cookies, and credentials from JSON structures.
    """
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            k_str = str(k).lower()
            if any(re.search(pat, k_str) for pat in SENSITIVE_KEY_PATTERNS):
                new_dict[k] = "[REDACTED_SENSITIVE_KEY_VALUE]"
            else:
                new_dict[k] = redact_sensitive(v)
        return new_dict
    elif isinstance(obj, list):
        return [redact_sensitive(item) for item in obj]
    elif isinstance(obj, str):
        if JWT_REGEX.search(obj) or obj.startswith("Bearer "):
            return "[REDACTED_TOKEN_STRING]"
        return obj
    return obj

def summarize_structure(data: Any, depth: int = 0) -> str:
    """
    Generates a clear structural schema outline (keys, types, array contents).
    """
    indent = "  " * depth
    if isinstance(data, dict):
        lines = ["{"]
        for k, v in data.items():
            v_summary = summarize_structure(v, depth + 1)
            lines.append(f"{indent}  \"{k}\": {v_summary}")
        lines.append(f"{indent}}}")
        return "\n".join(lines)
    elif isinstance(data, list):
        if not data:
            return "[]"
        sample_item = summarize_structure(data[0], depth + 1)
        return f"[\n{indent}  // List containing {len(data)} items matching:\n{indent}  {sample_item}\n{indent}]"
    else:
        val_type = type(data).__name__
        if isinstance(data, str) and data.startswith("[REDACTED"):
            return f"\"{data}\" ({val_type})"
        return f"({val_type})"

def fetch_endpoint(endpoint_path: str, headers: dict) -> dict:
    url = f"{BASE_URL}/{endpoint_path.lstrip('/')}"
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            res = client.get(url, headers=headers)
            print(f"FETCH {url} -> Status {res.status_code}")
            if res.status_code == 200:
                try:
                    return res.json()
                except Exception as e:
                    return {"status": False, "error": f"JSON decode error: {e}", "raw": res.text[:200]}
            return {"status": False, "status_code": res.status_code, "text": res.text[:200]}
    except Exception as e:
        return {"status": False, "error": str(e)}

def main():
    print("=" * 80)
    print("PHASE 0: LIVE API INSPECTION & REDACTION CHECKPOINT")
    print("=" * 80)

    auth_header = TOKEN if TOKEN.startswith("Bearer ") else f"Bearer {TOKEN}" if TOKEN else ""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": auth_header,
        "X-Auth-Token": TOKEN,
        "X-User-Id": str(USER_ID),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    endpoints = {
        "allEmployementNew": "employee/allEmployementNew",
        "user-profile/{slug}": f"auth/user-profile/{USER_SLUG}",
        "user-detail": "employee/user-detail",
        "random-widget": "random-widget"
    }

    results = {}
    structures = {}

    output_dir = root / "data" / "phase0_inspection"
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, path in endpoints.items():
        print(f"\n---> Inspecting endpoint: {name} ({path})")
        raw_data = fetch_endpoint(path, headers)
        sanitized_data = redact_sensitive(raw_data)
        
        file_name = name.replace("/", "_").replace("{", "").replace("}", "") + ".json"
        save_path = output_dir / file_name
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(sanitized_data, f, indent=2)

        results[name] = sanitized_data
        structures[name] = summarize_structure(sanitized_data)
        print(f"Saved sanitized output to: {save_path}")

    report_path = output_dir / "schema_inspection_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Phase 0 Live API Schema Inspection & Redaction Report\n\n")
        f.write("All authentication tokens, JWTs, headers, and credentials have been strictly redacted.\n\n")
        for name in endpoints:
            f.write(f"## Endpoint: `{name}`\n\n")
            f.write("```json\n")
            f.write(structures[name])
            f.write("\n```\n\n")

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE. REPORT GENERATED AT:")
    print(f"  {report_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
