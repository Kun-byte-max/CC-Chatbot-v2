#!/usr/bin/env python3
"""
reset_benchmark_account.py — Snapshot-based state restoration for benchmark accounts.

Diffs live database state against scripts/benchmark_fixture_snapshot.json,
restores modified user fields, and deletes sequence-inserted skill/experience rows.

Safety Guards:
  - Refuses to touch any account not in BENCHMARK_ACCOUNTS.
  - Requires user confirmation unless --yes / -y is passed.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from backend.repositories.db import get_db
except ModuleNotFoundError:
    from repositories.db import get_db  # type: ignore

BENCHMARK_ACCOUNTS = {"baseline_emp@collarcheck.com", "baseline_empr@collarcheck.com"}
SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), "benchmark_fixture_snapshot.json")

def main():
    parser = argparse.ArgumentParser(description="Snapshot-based reset script for benchmark accounts")
    parser.add_argument("--email", default="baseline_emp@collarcheck.com", help="Email of benchmark account to reset")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if email not in BENCHMARK_ACCOUNTS:
        print(f"[ERROR] Refusing to reset non-benchmark account: '{email}'.")
        print(f"Allowed benchmark accounts: {', '.join(sorted(BENCHMARK_ACCOUNTS))}")
        sys.exit(1)

    if not os.path.exists(SNAPSHOT_FILE):
        print(f"[ERROR] Snapshot file missing: '{SNAPSHOT_FILE}'. Run setup_benchmark_accounts.py first.")
        sys.exit(1)

    with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM cyb_user WHERE email = %s", (email,))
    user_row = c.fetchone()
    if not user_row:
        print(f"[ERROR] User '{email}' not found in database.")
        sys.exit(1)

    user_id = user_row["id"]

    # 1. Diff User Profile Fields
    expected_profile = snapshot.get("user_profile", {})
    user_field_updates = {}
    for key, expected_val in expected_profile.items():
        current_val = user_row.get(key)
        if str(current_val or "") != str(expected_val or ""):
            user_field_updates[key] = (current_val, expected_val)

    # 2. Diff Skills (delete non-seeded skills)
    seeded_skills = set(snapshot.get("seeded_skills", []))
    c.execute("SELECT id, skill FROM cyb_user_skill WHERE user = %s AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
    live_skills = c.fetchall()
    skill_ids_to_delete = [s["id"] for s in live_skills if s["id"] not in seeded_skills]

    # 3. Diff Experience (delete non-seeded experience)
    seeded_experience = set(snapshot.get("seeded_experience", []))
    c.execute("SELECT id, company FROM cyb_user_experience WHERE user = %s AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
    live_exp = c.fetchall()
    exp_ids_to_delete = [ex["id"] for ex in live_exp if ex["id"] not in seeded_experience]

    # 4. Diff Education (delete non-seeded education)
    seeded_education = set(snapshot.get("seeded_education", []))
    c.execute("SELECT id, university FROM cyb_user_education WHERE user = %s AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
    live_edu = c.fetchall()
    edu_ids_to_delete = [e["id"] for e in live_edu if e["id"] not in seeded_education]

    has_changes = user_field_updates or skill_ids_to_delete or exp_ids_to_delete or edu_ids_to_delete

    print("==================================================")
    print(f"BENCHMARK ACCOUNT RESET AUDIT: {email} (ID: {user_id})")
    print("==================================================")

    if not has_changes:
        print("[INFO] Benchmark account is already in pristine seeded state. Zero changes needed.")
        return

    if user_field_updates:
        print("\nUser Profile Fields to Restore:")
        for key, (cur, exp) in user_field_updates.items():
            print(f"  - {key}: '{cur}' -> '{exp}'")

    if skill_ids_to_delete:
        print(f"\nSequence-Created Skill Row IDs to Delete: {skill_ids_to_delete}")

    if exp_ids_to_delete:
        print(f"Sequence-Created Experience Row IDs to Delete: {exp_ids_to_delete}")

    if edu_ids_to_delete:
        print(f"Sequence-Created Education Row IDs to Delete: {edu_ids_to_delete}")

    if not args.yes:
        resp = input("\nProceed with restoring snapshot state and deleting non-seeded rows? [y/N]: ")
        if resp.lower().strip() not in ["y", "yes"]:
            print("[CANCELLED] Reset operation aborted by user.")
            sys.exit(0)

    # Perform Restoration & Deletions
    if user_field_updates:
        update_fields = ", ".join([f"{k}=%s" for k in user_field_updates.keys()])
        update_values = [v[1] for v in user_field_updates.values()] + [user_id]
        c.execute(f"UPDATE cyb_user SET {update_fields} WHERE id=%s", update_values)

    if skill_ids_to_delete:
        c.execute(f"DELETE FROM cyb_user_skill WHERE id IN ({','.join(['%s']*len(skill_ids_to_delete))})", skill_ids_to_delete)

    if exp_ids_to_delete:
        c.execute(f"DELETE FROM cyb_user_experience WHERE id IN ({','.join(['%s']*len(exp_ids_to_delete))})", exp_ids_to_delete)

    if edu_ids_to_delete:
        c.execute(f"DELETE FROM cyb_user_education WHERE id IN ({','.join(['%s']*len(edu_ids_to_delete))})", edu_ids_to_delete)

    conn.commit()
    print(f"\n[SUCCESS] Reset complete. Account '{email}' restored to pristine seeded state.")

if __name__ == "__main__":
    main()
