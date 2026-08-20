#!/usr/bin/env python3
"""
setup_benchmark_accounts.py — Create and seed dedicated benchmark fixture accounts.

Accounts created:
  - baseline_emp@collarcheck.com (Employee, user_type=1)
  - baseline_empr@collarcheck.com (Employer, user_type=2)

Also exports scripts/benchmark_fixture_snapshot.json representing the pristine seeded state.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from backend.repositories.db import get_db
except ModuleNotFoundError:
    from repositories.db import get_db  # type: ignore

SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), "benchmark_fixture_snapshot.json")

def setup_employee(c) -> int:
    email = "baseline_emp@collarcheck.com"
    c.execute("SELECT id FROM cyb_user WHERE email = %s", (email,))
    row = c.fetchone()
    
    user_data = {
        "user_type": 1,
        "fname": "Baseline",
        "lname": "Employee",
        "full_name": "Baseline Employee",
        "email": email,
        "gender": 1,
        "dob": "2000-01-01",
        "city": 131679,
        "state": 4021,
        "country": 101,
        "profile_description": "Benchmark test fixture account — automated performance evaluation.",
        "email_verified": 1,
        "display_type": 1,
        "status": 1,
        "percentage": 100,
        "is_deleted": 0,
    }

    if row:
        user_id = row["id"]
        c.execute(
            "UPDATE cyb_user SET fname=%s, lname=%s, full_name=%s, gender=%s, dob=%s, city=%s, state=%s, country=%s, profile_description=%s, status=1, is_deleted=0 WHERE id=%s",
            (
                user_data["fname"], user_data["lname"], user_data["full_name"], user_data["gender"],
                user_data["dob"], user_data["city"], user_data["state"], user_data["country"],
                user_data["profile_description"], user_id
            )
        )
    else:
        c.execute(
            """INSERT INTO cyb_user (user_type, fname, lname, full_name, email, gender, dob, city, state, country, profile_description, email_verified, display_type, status, percentage, is_deleted, create_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (
                user_data["user_type"], user_data["fname"], user_data["lname"], user_data["full_name"],
                user_data["email"], user_data["gender"], user_data["dob"], user_data["city"],
                user_data["state"], user_data["country"], user_data["profile_description"],
                user_data["email_verified"], user_data["display_type"], user_data["status"],
                user_data["percentage"], user_data["is_deleted"]
            )
        )
        c.execute("SELECT id FROM cyb_user WHERE email = %s", (email,))
        user_id = c.fetchone()["id"]

    # Seed 1 skill row (Python skill = 12576)
    c.execute("SELECT id FROM cyb_user_skill WHERE user = %s AND skill = 12576 AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
    s_row = c.fetchone()
    if s_row:
        seeded_skill_id = s_row["id"]
    else:
        c.execute(
            "INSERT INTO cyb_user_skill (user, skill, rating, status, is_deleted, create_date) VALUES (%s, 12576, 5, 1, 0, NOW())",
            (user_id,)
        )
        c.execute("SELECT id FROM cyb_user_skill WHERE user = %s AND skill = 12576 AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
        seeded_skill_id = c.fetchone()["id"]

    # Seed 1 education row
    c.execute("SELECT id FROM cyb_user_education WHERE user = %s AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
    e_row = c.fetchone()
    if e_row:
        seeded_edu_id = e_row["id"]
    else:
        c.execute(
            """INSERT INTO cyb_user_education (user, university, course, course_type, starting_date, ending_date, ongoing, status, is_deleted, create_date)
               VALUES (%s, 121, 1205, 1, '2009-06-01', '2018-06-01', 0, 1, 0, NOW())""",
            (user_id,)
        )
        c.execute("SELECT id FROM cyb_user_education WHERE user = %s AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
        seeded_edu_id = c.fetchone()["id"]

    # Seed 1 experience row
    c.execute("SELECT id FROM cyb_user_experience WHERE user = %s AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
    exp_row = c.fetchone()
    if exp_row:
        seeded_exp_id = exp_row["id"]
    else:
        c.execute(
            """INSERT INTO cyb_user_experience (user, company, designation, employment_type, salary, salary_inhand, salary_mode, joining_date, department, still_working, status, is_deleted, create_date)
               VALUES (%s, 13, 5, 1, '2423423', 'CTC', 'Per Annum', '2025-07-11', 177, 1, 1, 0, NOW())""",
            (user_id,)
        )
        c.execute("SELECT id FROM cyb_user_experience WHERE user = %s AND (is_deleted IS NULL OR is_deleted = 0)", (user_id,))
        seeded_exp_id = c.fetchone()["id"]

    return user_id, seeded_skill_id, seeded_edu_id, seeded_exp_id

def setup_employer(c) -> int:
    email = "baseline_empr@collarcheck.com"
    c.execute("SELECT id FROM cyb_user WHERE email = %s", (email,))
    row = c.fetchone()

    user_data = {
        "user_type": 2,
        "fname": "Collar Check Pvt. Ltd.",
        "full_name": "Collar Check Pvt. Ltd.",
        "email": email,
        "city": 131679,
        "state": 4021,
        "country": 101,
        "profile_description": "Benchmark employer test fixture account.",
        "email_verified": 1,
        "display_type": 0,
        "claim_status": 1,
        "status": 1,
        "percentage": 100,
        "is_deleted": 0,
    }

    if row:
        user_id = row["id"]
        c.execute(
            "UPDATE cyb_user SET fname=%s, full_name=%s, city=%s, state=%s, country=%s, profile_description=%s, status=1, is_deleted=0 WHERE id=%s",
            (user_data["fname"], user_data["full_name"], user_data["city"], user_data["state"], user_data["country"], user_data["profile_description"], user_id)
        )
    else:
        c.execute(
            """INSERT INTO cyb_user (user_type, fname, full_name, email, city, state, country, profile_description, email_verified, display_type, claim_status, status, percentage, is_deleted, create_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (
                user_data["user_type"], user_data["fname"], user_data["full_name"], user_data["email"],
                user_data["city"], user_data["state"], user_data["country"], user_data["profile_description"],
                user_data["email_verified"], user_data["display_type"], user_data["claim_status"],
                user_data["status"], user_data["percentage"], user_data["is_deleted"]
            )
        )
        c.execute("SELECT id FROM cyb_user WHERE email = %s", (email,))
        user_id = c.fetchone()["id"]

    return user_id

def main():
    conn = get_db()
    c = conn.cursor()

    emp_id, seeded_skill_id, seeded_edu_id, seeded_exp_id = setup_employee(c)
    empr_id = setup_employer(c)

    conn.commit()

    snapshot = {
        "employee_email": "baseline_emp@collarcheck.com",
        "employee_user_id": emp_id,
        "employer_email": "baseline_empr@collarcheck.com",
        "employer_user_id": empr_id,
        "user_profile": {
            "fname": "Baseline",
            "lname": "Employee",
            "gender": 1,
            "dob": "2000-01-01",
            "city": 131679,
            "state": 4021,
            "country": 101,
            "profile_description": "Benchmark test fixture account — automated performance evaluation."
        },
        "seeded_skills": [seeded_skill_id],
        "seeded_education": [seeded_edu_id],
        "seeded_experience": [seeded_exp_id]
    }

    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    print("==================================================")
    print("BENCHMARK ACCOUNTS SETUP SUMMARY")
    print("==================================================")
    print(f"Employee Account : baseline_emp@collarcheck.com (User ID: {emp_id})")
    print(f"Employer Account : baseline_empr@collarcheck.com (User ID: {empr_id})")
    print(f"Seeded Skill ID  : {seeded_skill_id}")
    print(f"Seeded Edu ID    : {seeded_edu_id}")
    print(f"Seeded Exp ID    : {seeded_exp_id}")
    print(f"Snapshot file    : {SNAPSHOT_FILE}")
    print("[SUCCESS] Benchmark accounts setup and snapshot created cleanly.")

if __name__ == "__main__":
    main()
