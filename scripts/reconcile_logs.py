#!/usr/bin/env python3
import re
import sys

def main():
    ids_file = "baseline_request_ids.txt"
    log_file = "baseline_run.log"

    if len(sys.argv) > 1:
        ids_file = sys.argv[1]
    if len(sys.argv) > 2:
        log_file = sys.argv[2]

    try:
        with open(ids_file, "r", encoding="utf-8") as f:
            expected_ids = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"[RECONCILE ERROR] Could not read {ids_file}: {e}")
        sys.exit(1)

    try:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log_content = f.read()
        except UnicodeDecodeError:
            with open(log_file, "r", encoding="utf-16") as f:
                log_content = f.read()
    except Exception as e:
        print(f"[RECONCILE ERROR] Could not read {log_file}: {e}")
        sys.exit(1)

    # Extract all request_id=<id> from chat_turn log lines
    logged_ids = re.findall(r'chat_turn\s+request_id=(\S+)', log_content)

    print("==================================================")
    print("LOG RECONCILIATION SUMMARY")
    print("==================================================")
    print(f"Driver Collected Request IDs : {len(expected_ids)}")
    print(f"Server Logged chat_turn IDs : {len(logged_ids)}")

    missing_ids = [rid for rid in expected_ids if rid not in logged_ids]

    if missing_ids:
        print(f"\n[MISMATCH] {len(missing_ids)} request ID(s) missing from server log:")
        for m in missing_ids:
            print(f"  - {m}")
        sys.exit(1)
    else:
        print("\n[SUCCESS] 100% Request ID Match! All collected request IDs found in server chat_turn logs.")

if __name__ == "__main__":
    main()
