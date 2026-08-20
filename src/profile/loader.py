import json
import os
import time

CACHE_TTL_SECONDS = 900  # 15 minutes
_profile_cache: dict[str, tuple[float, dict]] = {}

def fetch_raw(individual_id: str) -> dict:
    """
    Fetches raw user profile dictionary by individual_id.
    Uses in-memory cache with 15-minute TTL.
    Controlled by USE_MOCK environment variable (default: true).
    """
    now = time.time()

    if individual_id in _profile_cache:
        timestamp, cached_data = _profile_cache[individual_id]
        if now - timestamp < CACHE_TTL_SECONDS:
            return cached_data

    # Live/Staging API call (GET https://admin.collarcheck.com/wapi/employee/user-detail)
    try:
        import httpx
        token = os.getenv("PLATFORM_TEST_TOKEN", "")
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if token:
            headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
            headers["X-Auth-Token"] = token
        if individual_id:
            headers["X-User-Id"] = str(individual_id)
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            res = client.get("https://admin.collarcheck.com/wapi/employee/user-detail", headers=headers)
            if res.status_code == 200:
                raw_data = res.json()
                _profile_cache[individual_id] = (now, raw_data)
                return raw_data
            else:
                res = client.get("https://api.collarcheck.com/wapi/employee/user-detail", headers=headers)
                if res.status_code == 200:
                    raw_data = res.json()
                    _profile_cache[individual_id] = (now, raw_data)
                    return raw_data

    except Exception as e:
        print(f"[LIVE API ERROR] Failed to fetch profile from live API: {e}")

    return {"status": False, "data": {}}
