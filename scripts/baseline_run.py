"""
baseline_run.py — Benchmark driver for /chat endpoint latency measurements.

Sequence Versions:
  v1 (default, 15-message set):
    Standard 15-turn benchmark sequence (10 employee turns, 5 employer turns).
    Used for all baseline (BASELINE.md) and post-gating (STEP1-RESULTS.md) comparisons.

  v2 (16-message set):
    Extended sequence with an extra mid-flow employer filler message ('ok') inserted between
    employer turns 2 ('with 5 years experience') and 3 ('in Bangalore').
    Used to exercise and validate B3 employer session override (ran_employer_session_override)
    while session current_step is active ('awaiting_location').
"""

import argparse
import os
import sys
import time
import httpx

EMPLOYEE_MESSAGES_V1 = [
    "hi",
    "thanks",
    "what are my skills?",
    "add Python and Django to my skills",
    "I have 4 years of experience in backend development",
    "show me python jobs in Pune",
    "only remote ones",
    "something with better salary",
    "show me data analyst roles",
    "tell me about the second one",
]

EMPLOYER_MESSAGES_V1 = [
    "I need a senior backend engineer",
    "with 5 years experience",
    "in Bangalore",
    "show me more candidates",
    "hi",
]

EMPLOYER_MESSAGES_V2 = [
    "I need a senior backend engineer",
    "with 5 years experience",
    "ok",  # Mid-flow filler inserted while current_step == 'awaiting_location'
    "in Bangalore",
    "show me more candidates",
    "hi",
]

BENCHMARK_ACCOUNTS = {"baseline_emp@collarcheck.com", "baseline_empr@collarcheck.com"}

def get_jwt(client: httpx.Client, base_url: str, email: str, role: str) -> str:
    url = f"{base_url.rstrip('/')}/login"
    res = client.post(url, json={"email": email, "role": role})
    if res.status_code != 200:
        raise RuntimeError(f"Login failed for {email} ({role}): {res.status_code} - {res.text}")
    return res.json()["access_token"]

def main():
    parser = argparse.ArgumentParser(description="Baseline Driver Script for /chat latency benchmark")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL of FastAPI backend")
    parser.add_argument("--employee-email", default="baseline_emp@collarcheck.com", help="Employee account email")
    parser.add_argument("--employer-email", default="baseline_empr@collarcheck.com", help="Employer account email")
    parser.add_argument("--employee-jwt", default=None, help="Employee Bearer JWT token")
    parser.add_argument("--employer-jwt", default=None, help="Employer Bearer JWT token")
    parser.add_argument("--allow-real-account", action="store_true", help="Allow running against a non-benchmark real user profile")
    parser.add_argument("--repeat", type=int, default=2, help="Number of repetitions for message set")
    parser.add_argument("--sequence", choices=["v1", "v2"], default="v1", help="Message sequence version: v1 (15-msg benchmark default) or v2 (16-msg override test)")
    parser.add_argument("--out-ids", default=None, help="Output file for collected request_ids (defaults to baseline_request_ids.txt for v1, baseline_request_ids_v2.txt for v2)")
    parser.add_argument("--dump-responses", default=None, help="Output JSON file for dumping full response payloads per turn")
    parser.add_argument("--force", action="store_true", help="Force overwrite of existing --out-ids file")
    args = parser.parse_args()

    emp_email = args.employee_email.strip().lower()
    empr_email = args.employer_email.strip().lower()

    # Real Account Safety Guard
    if emp_email not in BENCHMARK_ACCOUNTS and not args.allow_real_account:
        print(f"[SAFETY ERROR] Account '{emp_email}' is not a benchmark account and this sequence writes profile data.")
        print("Pass --allow-real-account to explicitly allow running against a real user profile.")
        sys.exit(1)

    emp_messages = EMPLOYEE_MESSAGES_V1
    empr_messages = EMPLOYER_MESSAGES_V2 if args.sequence == "v2" else EMPLOYER_MESSAGES_V1
    out_ids = args.out_ids or (f"baseline_request_ids_{args.sequence}.txt" if args.sequence != "v1" else "baseline_request_ids.txt")

    # Overwrite Guard
    if os.path.exists(out_ids) and not args.force:
        print(f"[OVERWRITE GUARD] File '{out_ids}' already exists. Pass --out-ids <name> or --force to overwrite.")
        sys.exit(1)

    base_url = args.base_url.rstrip('/')
    collected_request_ids = []
    dumped_responses = []

    with httpx.Client(timeout=60.0) as client:
        emp_jwt = args.employee_jwt or os.getenv("EMPLOYEE_JWT")
        if not emp_jwt:
            print(f"[INFO] Logging in employee account {emp_email}...")
            emp_jwt = get_jwt(client, base_url, emp_email, "employee")

        empr_jwt = args.employer_jwt or os.getenv("EMPLOYER_JWT")
        if not empr_jwt:
            print(f"[INFO] Logging in employer account {empr_email}...")
            empr_jwt = get_jwt(client, base_url, empr_email, "employer")

        emp_headers = {"Authorization": f"Bearer {emp_jwt}"}
        empr_headers = {"Authorization": f"Bearer {empr_jwt}"}

        total_expected_turns = args.repeat * (len(emp_messages) + len(empr_messages))
        print(f"[INFO] Starting baseline driver run ({args.sequence}): {args.repeat} repeat(s) = {total_expected_turns} total turns.")

        turn_counter = 0

        for r in range(1, args.repeat + 1):
            print(f"\n--- REPEAT RUN {r} of {args.repeat} ---")
            
            # Employee turn set
            emp_history = []
            session_emp = f"baseline_emp_sess_{r}"
            print(f"Running Employee sequence ({len(emp_messages)} turns)...")
            for idx, msg in enumerate(emp_messages, 1):
                turn_counter += 1
                emp_history.append({"role": "user", "content": msg})
                payload = {
                    "messages": emp_history,
                    "session_id": session_emp
                }
                t0 = time.perf_counter()
                res = client.post(f"{base_url}/chat", json=payload, headers=emp_headers)
                elapsed = time.perf_counter() - t0

                if res.status_code != 200:
                    print(f"  [Turn {turn_counter}] ERROR {res.status_code}: {res.text}")
                    req_id = f"ERROR_{turn_counter}"
                else:
                    data = res.json()
                    req_id = data.get("request_id") or "MISSING"
                    reply = data.get("reply", "")
                    emp_history.append({"role": "assistant", "content": reply})

                collected_request_ids.append(req_id)
                dumped_responses.append({
                    "position": turn_counter,
                    "repeat": r,
                    "role": "employee",
                    "turn_idx": idx,
                    "user_message": msg,
                    "request_id": req_id,
                    "reply": data.get("reply") if res.status_code == 200 else None,
                    "results": data.get("results") if res.status_code == 200 else None,
                    "result_type": data.get("result_type") if res.status_code == 200 else None,
                })
                print(f"  [Turn {turn_counter}/{total_expected_turns}] Emp #{idx}: '{msg[:20]}...' -> req_id={req_id} ({elapsed*1000:.0f}ms)")
                time.sleep(0.5)

            # Employer turn set
            empr_history = []
            session_empr = f"baseline_empr_sess_{r}"
            print(f"Running Employer sequence ({len(empr_messages)} turns)...")
            for idx, msg in enumerate(empr_messages, 1):
                turn_counter += 1
                empr_history.append({"role": "user", "content": msg})
                payload = {
                    "messages": empr_history,
                    "session_id": session_empr
                }
                t0 = time.perf_counter()
                res = client.post(f"{base_url}/chat", json=payload, headers=empr_headers)
                elapsed = time.perf_counter() - t0

                if res.status_code != 200:
                    print(f"  [Turn {turn_counter}] ERROR {res.status_code}: {res.text}")
                    req_id = f"ERROR_{turn_counter}"
                else:
                    data = res.json()
                    req_id = data.get("request_id") or "MISSING"
                    reply = data.get("reply", "")
                    empr_history.append({"role": "assistant", "content": reply})

                collected_request_ids.append(req_id)
                dumped_responses.append({
                    "position": turn_counter,
                    "repeat": r,
                    "role": "employer",
                    "turn_idx": idx,
                    "user_message": msg,
                    "request_id": req_id,
                    "reply": data.get("reply") if res.status_code == 200 else None,
                    "results": data.get("results") if res.status_code == 200 else None,
                    "result_type": data.get("result_type") if res.status_code == 200 else None,
                })
                print(f"  [Turn {turn_counter}/{total_expected_turns}] Employer #{idx}: '{msg[:20]}...' -> req_id={req_id} ({elapsed*1000:.0f}ms)")
                time.sleep(0.5)

    with open(out_ids, "w", encoding="utf-8") as f:
        for rid in collected_request_ids:
            f.write(f"{rid}\n")

    if args.dump_responses:
        import json
        with open(args.dump_responses, "w", encoding="utf-8") as f:
            json.dump(dumped_responses, f, indent=2)
        print(f"Dumped response payloads written to: {args.dump_responses}")

    print(f"\n[SUCCESS] Baseline driver completed {len(collected_request_ids)} turns.")
    print(f"Request IDs written to: {out_ids}")

if __name__ == "__main__":
    main()
