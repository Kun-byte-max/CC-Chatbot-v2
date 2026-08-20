import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

def main():
    import main
    client = TestClient(main.app)

    token = client.post("/login", json={"email": "sahil@collarcheck.com", "role": "employee"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    target_msgs = [
        "add Python and Django to my skills",
        "I have 4 years of experience in backend development"
    ]

    print("=== PART E TARGETED DOUBLE EXECUTION TEST ===")
    for msg in target_msgs:
        print(f"\n--- Testing message: '{msg}' ---")
        for pass_num in [1, 2]:
            payload = {
                "messages": [{"role": "user", "content": msg}],
                "session_id": f"part_e_sess_pass_{pass_num}"
            }
            res = client.post("/chat", json=payload, headers=headers)
            print(f"Pass {pass_num}: HTTP {res.status_code} | Response snippet: {res.json().get('reply')[:60]}...")

if __name__ == "__main__":
    main()
