"""
indexer.py — Fetch from MySQL and push to Meilisearch (jobs / users / companies).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import unicodedata
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import aiomysql
import requests
from dotenv import load_dotenv

load_dotenv()

MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7701")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey123")
HEADERS = {"Authorization": f"Bearer {MEILI_KEY}"}

DB_DSN = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "db": os.getenv("DB_NAME", "collarcheck"),
    "minsize": 1,
    "maxsize": 4,
    "autocommit": True,
}

_non_alnum = re.compile(r"[^a-z0-9]+")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_JOBS = """
SELECT
  cj.id,
  cj.job_title,
  cj.job_description,
  cj.tag,
  cj.slug,
  cj.roles_responsibility,
  cj.department,
  cj.experience,
  cj.role_type,
  cj.location,
  cj.country,
  cj.state,
  cj.city,
  cntry.name AS country_name,
  st.name AS state_name,
  ct.name AS city_name,
  dept.name AS department_name,
  desig.name AS designation_name,
  rt.name AS role_type_name,
  jm.name AS job_mode_name,
  je.name AS experience_name,
  sal.name AS salary_name,
  cj.job_mode,
  cj.designation,
  cj.urgent,
  cj.vacancy,
  cj.posted_date,
  cj.closing_date,
  cj.salary,
  cj.create_date,
  cj.modify_date,
  UNIX_TIMESTAMP(cj.create_date) AS create_ts,
  cj.company AS company_id,
  cu.full_name AS company_name,
  cj.industry AS industry_id,
  ind.name AS industry_name,

  -- skills
  COALESCE(
    GROUP_CONCAT(DISTINCT s.id ORDER BY s.id SEPARATOR ','),
    ''
  ) AS skill_ids_csv,
  COALESCE(
    GROUP_CONCAT(DISTINCT s.name ORDER BY s.name SEPARATOR '||'),
    ''
  ) AS skill_names_csv,

  -- company benefits
  COALESCE(
    GROUP_CONCAT(DISTINCT CAST(cb.benefit_id AS UNSIGNED) ORDER BY CAST(cb.benefit_id AS UNSIGNED) SEPARATOR ','),
    ''
  ) AS benefit_ids_csv,

  -- applicant count
  COALESCE(COUNT(DISTINCT app.id), 0) AS applicant_count

FROM cyb_company_job cj
LEFT JOIN cyb_user cu            ON cu.id = cj.company
LEFT JOIN cyb_industries ind     ON ind.id = cj.industry
LEFT JOIN cyb_country cntry      ON cntry.id = cj.country
LEFT JOIN cyb_state st           ON st.id = cj.state
LEFT JOIN cyb_cities ct          ON ct.id = cj.city
LEFT JOIN cyb_department dept    ON dept.id = cj.department
LEFT JOIN cyb_designation desig  ON desig.id = cj.designation
LEFT JOIN cyb_role_types rt      ON rt.id = cj.role_type
LEFT JOIN cyb_job_mode jm        ON jm.id = cj.job_mode
LEFT JOIN cyb_job_experiences je ON je.id = CAST(cj.experience AS UNSIGNED)
LEFT JOIN cyb_salary sal         ON sal.id = cj.salary

LEFT JOIN cyb_skill s ON (
    cj.skill IS NOT NULL 
    AND JSON_VALID(cj.skill) 
    AND (
        JSON_CONTAINS(cj.skill, CONCAT('"', s.id, '"')) 
        OR JSON_CONTAINS(cj.skill, CAST(s.id AS CHAR))
    )
)

LEFT JOIN cyb_company_benefits cb
       ON cb.company_id = cj.company AND cb.is_deleted = 0

LEFT JOIN cyb_application app
       ON app.job = cj.id AND app.is_deleted = 0

WHERE cj.status = 1 AND cj.is_deleted = 0
{since_clause}
GROUP BY
  cj.id, cj.job_title, cj.job_description, cj.tag, cj.slug,
  cj.roles_responsibility, cj.department, cj.experience, cj.role_type,
  cj.location, cj.country, cj.state, cj.city, cj.job_mode,
  cj.designation, cj.urgent, cj.vacancy, cj.posted_date, cj.closing_date,
  cj.salary, cj.create_date, cj.modify_date, cj.company,
  cu.full_name, cj.industry, ind.name,
  cntry.name, st.name, ct.name,
  dept.name, desig.name, rt.name, jm.name, je.name, sal.name
ORDER BY cj.id;
"""

# Users SQL — fixed:
# 1. company_industry_id from current company (cmp2.industry) — matches PHP which filters on cmp.industry
# 2. star_rating_avg — matches PHP getstarRatingEmployies exactly (includes ur.is_deleted=0 check)
# 3. total_experience_years — matches PHP getExperienceEmployee exactly
# 4. education_course_ids and education_course_type_ids — for course/course_type filters
# 5. verified_identity — matches PHP user_verified() exactly (all 3 conditions: doc match + phone + email)
SQL_USERS = """
SELECT
  u.id,
  u.full_name,
  u.individual_id,
  u.email,
  u.phone,
  u.slug,
  u.industry AS user_industry_id,
  ind.name AS industry_name,
  u.percentage,
  u.create_date,
  u.modify_date,

  -- location
  u.city,
  u.state,
  u.country,
  cntry.name AS country_name,
  st.name AS state_name,
  ct.name AS city_name,
  wt.name AS work_status_name,
  u.work_status,
  cc.full_name AS current_company_name,
  u.current_company,
  desig.name AS current_position_name,
  u.current_possition,
  u.on_immediate,
  u.on_notice,

  -- current company industry (matches PHP: cmp.industry)
  cc.industry AS company_industry_id,

  -- skills
  COALESCE(
    GROUP_CONCAT(DISTINCT CAST(us.skill AS UNSIGNED) ORDER BY CAST(us.skill AS UNSIGNED) SEPARATOR ','),
    ''
  ) AS skill_ids_csv,
  COALESCE(
    GROUP_CONCAT(DISTINCT s.name ORDER BY s.name SEPARATOR '||'),
    ''
  ) AS skill_names_csv,

  -- current experience row
  ue.department AS exp_department,
  dept.name AS exp_department_name,
  ue.employment_type AS exp_employment_type,
  et.name AS exp_employment_type_name,
  ue.salary AS exp_salary,
  ue.approved AS exp_approved,
  CASE WHEN ue.approved = 1 THEN 1 ELSE 0 END AS verified_employement,
  CASE WHEN ue.salary IS NOT NULL THEN 1 ELSE 0 END AS verified_salary,

  -- verified identity — matches PHP user_verified() exactly:
  -- all 3 conditions must be true: document match + phone + email
  CASE WHEN (
    -- condition 1: verify_document with verify=1 AND doc_name matches full_name (case-insensitive)
    EXISTS (
      SELECT 1 FROM cyb_verify_document vd
      WHERE vd.user_id = u.id
        AND vd.verify = 1
        AND LOWER(vd.doc_name COLLATE utf8mb4_unicode_ci) = LOWER(u.full_name COLLATE utf8mb4_unicode_ci)
    )
    AND
    -- condition 2: phone verified (primary or secondary)
    (
      (u.phone_verified IS NOT NULL AND u.phone_verified != 0 AND u.phone IS NOT NULL AND u.phone != '')
      OR
      (u.second_phone_verify IS NOT NULL AND u.second_phone_verify != 0 AND u.second_phone IS NOT NULL AND u.second_phone != '')
    )
    AND
    -- condition 3: email verified (primary or alternate)
    (
      (u.email_verified IS NOT NULL AND u.email_verified != 0 AND u.email IS NOT NULL AND u.email != '')
      OR
      (u.email_alternate_verify IS NOT NULL AND u.email_alternate_verify != 0 AND u.email_alternate IS NOT NULL AND u.email_alternate != '')
    )
  ) THEN 1 ELSE 0 END AS verified_identity,

  -- total experience years (approved=1) — matches PHP getExperienceEmployee exactly
  (
    SELECT COALESCE(
      SUM(
        CASE
          WHEN ex.joining_date IS NULL OR ex.joining_date = '' OR ex.joining_date = '0000-00-00' THEN 0
          ELSE TIMESTAMPDIFF(
            MONTH,
            ex.joining_date,
            CASE WHEN ex.worked_till_date IS NULL OR ex.worked_till_date = '' OR ex.worked_till_date = '0000-00-00' THEN CURDATE() ELSE ex.worked_till_date END
          )
        END
      ) / 12,
      0
    )
    FROM cyb_user_experience ex
    WHERE ex.user = u.id AND ex.approved = 1
  ) AS total_experience_years,

  -- star rating avg — matches PHP getstarRatingEmployies exactly
  -- PHP: WHERE ue.user != '' AND uer.approved=1 AND ue.is_deleted=0 AND ur.is_deleted=0
  (
    SELECT AVG(rh.rating)
    FROM cyb_user_experience_rating_history rh
    LEFT JOIN cyb_user_experience_rating r ON rh.rating_id = r.id
    LEFT JOIN cyb_user_experience ex2 ON r.experience = ex2.id
    WHERE ex2.user = u.id
      AND ex2.user IS NOT NULL
      AND ex2.user != 0
      AND r.approved = 1
      AND ex2.is_deleted = 0
      AND u.is_deleted = 0
  ) AS star_rating_avg,

  -- education: course ids and course_type ids (for course/course_type filters)
  COALESCE(
    GROUP_CONCAT(DISTINCT CAST(ued.course AS UNSIGNED) ORDER BY CAST(ued.course AS UNSIGNED) SEPARATOR ','),
    ''
  ) AS education_course_ids_csv,
  COALESCE(
    GROUP_CONCAT(DISTINCT CAST(ued.course_type AS UNSIGNED) ORDER BY CAST(ued.course_type AS UNSIGNED) SEPARATOR ','),
    ''
  ) AS education_course_type_ids_csv

FROM cyb_user u
LEFT JOIN cyb_industries ind ON ind.id = u.industry
LEFT JOIN cyb_country cntry  ON cntry.id = u.country
LEFT JOIN cyb_state st       ON st.id = u.state
LEFT JOIN cyb_cities ct      ON ct.id = u.city
LEFT JOIN cyb_work_type wt   ON wt.id = u.work_status
LEFT JOIN cyb_user cc        ON cc.id = u.current_company
LEFT JOIN cyb_designation desig ON desig.id = u.current_possition

LEFT JOIN cyb_user_skill us
       ON us.user = u.id AND us.status = 1 AND us.is_deleted = 0
LEFT JOIN cyb_skill s ON s.id = us.skill

LEFT JOIN cyb_user_experience ue
       ON ue.user = u.id
      AND ue.company = u.current_company
      AND ue.designation = u.current_possition
      AND ue.status = 1
      AND ue.is_deleted = 0
LEFT JOIN cyb_department dept     ON dept.id = ue.department
LEFT JOIN cyb_employement_type et ON et.id = ue.employment_type

-- education join for course/course_type filters
LEFT JOIN cyb_user_education ued
       ON ued.user = u.id AND ued.is_deleted = 0 AND ued.status = 1

WHERE u.user_type = 1 AND u.status = 1 AND u.is_deleted = 0
{since_clause}
GROUP BY
  u.id, u.full_name, u.individual_id, u.email, u.phone, u.slug,
  u.industry, ind.name, u.percentage, u.create_date, u.modify_date,
  u.city, u.state, u.country, cntry.name, st.name, ct.name,
  wt.name, cc.full_name, desig.name, cc.industry,
  u.work_status, u.current_company,
  u.current_possition, u.on_immediate, u.on_notice,
  ue.department, dept.name, ue.employment_type, et.name, ue.salary, ue.approved
ORDER BY u.id;
"""

SQL_COMPANIES = """
SELECT
  u.id,
  u.full_name,
  u.individual_id,
  u.slug,
  u.email,
  u.phone,
  u.industry AS industry_id,
  ind.name AS industry_name,
  u.country,
  u.state,
  u.city,
  cntry.name AS country_name,
  st.name AS state_name,
  ct.name AS city_name,
  u.create_date,
  u.modify_date,

  -- benefits
  COALESCE(
    GROUP_CONCAT(DISTINCT CAST(cb.benefit_id AS UNSIGNED) ORDER BY CAST(cb.benefit_id AS UNSIGNED) SEPARATOR ','),
    ''
  ) AS benefit_ids_csv,

  -- job modes
  COALESCE(
    GROUP_CONCAT(DISTINCT CAST(cj.job_mode AS UNSIGNED) ORDER BY CAST(cj.job_mode AS UNSIGNED) SEPARATOR ','),
    ''
  ) AS job_mode_ids_csv,

  -- job titles (for keyword search — mirrors PHP orLike cj.job_title)
  COALESCE(
    GROUP_CONCAT(DISTINCT cj.job_title ORDER BY cj.job_title SEPARATOR '||'),
    ''
  ) AS job_titles_csv,

  -- last job create timestamp (for actively hiring filter)
  COALESCE(MAX(UNIX_TIMESTAMP(cj.create_date)), 0) AS last_job_create_ts,

  -- verified company — matches PHP user_verified() exactly
  -- all 3 conditions must be true: document + phone + email
  CASE WHEN (
    -- condition 1: verify_document with verify=1 AND doc_name = full_name (case-insensitive)
    EXISTS (
      SELECT 1 FROM cyb_verify_document vd
      WHERE vd.user_id = u.id
        AND vd.verify = 1
        AND LOWER(vd.doc_name COLLATE utf8mb4_unicode_ci) = LOWER(u.full_name COLLATE utf8mb4_unicode_ci)
    )
    AND
    -- condition 2: phone verified (primary or secondary)
    (
      (u.phone_verified IS NOT NULL AND u.phone_verified != 0 AND u.phone IS NOT NULL AND u.phone != '')
      OR
      (u.second_phone_verify IS NOT NULL AND u.second_phone_verify != 0 AND u.second_phone IS NOT NULL AND u.second_phone != '')
    )
    AND
    -- condition 3: email verified (primary or alternate)
    (
      (u.email_verified IS NOT NULL AND u.email_verified != 0 AND u.email IS NOT NULL AND u.email != '')
      OR
      (u.email_alternate_verify IS NOT NULL AND u.email_alternate_verify != 0 AND u.email_alternate IS NOT NULL AND u.email_alternate != '')
    )
  ) THEN 1 ELSE 0 END AS is_verified_company

FROM cyb_user u
LEFT JOIN cyb_industries ind ON ind.id = u.industry
LEFT JOIN cyb_country cntry  ON cntry.id = u.country
LEFT JOIN cyb_state st       ON st.id = u.state
LEFT JOIN cyb_cities ct      ON ct.id = u.city
LEFT JOIN cyb_company_benefits cb
       ON cb.company_id = u.id AND cb.is_deleted = 0

LEFT JOIN cyb_company_job cj
       ON cj.company = u.id AND cj.is_deleted = 0 AND cj.status = 1

WHERE u.user_type = 2 AND u.status = 1 AND u.is_deleted = 0
{since_clause}
GROUP BY
  u.id, u.full_name, u.individual_id, u.slug, u.email, u.phone,
  u.industry, ind.name, u.country, u.state, u.city,
  cntry.name, st.name, ct.name,
  u.create_date, u.modify_date
ORDER BY u.id;
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    return str(v)


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _make_compact(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return _non_alnum.sub("", s.lower()) or None


def _normalise_skill(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return n.strip().lower()


def _dedup_skills(names: List[str]) -> List[str]:
    seen: Dict[str, str] = {}
    for n in (names or []):
        if not n:
            continue
        key = _normalise_skill(n)
        if key not in seen:
            seen[key] = n.strip()
    return list(seen.values())


def _parse_int_csv(value: Optional[str]) -> List[int]:
    if not value:
        return []
    out: List[int] = []
    for token in str(value).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError:
            continue
    return out


def _parse_skill_names(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split("||") if part.strip()]


# ---------------------------------------------------------------------------
# Document mappers
# ---------------------------------------------------------------------------

def to_job_doc(r: Dict[str, Any]) -> Dict[str, Any]:
    title = r["job_title"]
    return {
        "id": int(r["id"]),
        "job_title": title,
        "job_title_compact": _make_compact(title),
        "tag": r["tag"],
        "slug": r["slug"],
        "department": _safe_int(r.get("department")),
        "department_name": _safe_str(r.get("department_name")),
        "experience": _safe_int(r.get("experience")),
        "experience_name": _safe_str(r.get("experience_name")),
        "role_type": _safe_int(r.get("role_type")),
        "role_type_name": _safe_str(r.get("role_type_name")),
        "job_mode": _safe_int(r.get("job_mode")),
        "job_mode_name": _safe_str(r.get("job_mode_name")),
        "location": r["location"],
        "country": _safe_int(r["country"]),
        "state": _safe_int(r["state"]),
        "city": _safe_int(r["city"]),
        "country_name": _safe_str(r.get("country_name")),
        "state_name": _safe_str(r.get("state_name")),
        "city_name": _safe_str(r.get("city_name")),
        "designation": _safe_int(r["designation"]),
        "designation_name": _safe_str(r.get("designation_name")),
        "urgent": bool(r["urgent"]) if r["urgent"] is not None else False,
        "vacancy": _safe_int(r["vacancy"]),
        "salary": _safe_float(r["salary"]),
        "salary_name": _safe_str(r.get("salary_name")),
        "posted_date": _safe_str(r["posted_date"]),
        "closing_date": _safe_str(r["closing_date"]),
        "create_date": _safe_str(r["create_date"]),
        "modify_date": _safe_str(r["modify_date"]),
        "create_ts": _safe_int(r.get("create_ts")),
        "company_id": _safe_int(r["company_id"]),
        "company_name": r["company_name"],
        "industry_id": _safe_int(r["industry_id"]),
        "industry_name": r["industry_name"],
        "skill_ids": _parse_int_csv(r.get("skill_ids_csv")),
        "skill_names": _dedup_skills(_parse_skill_names(r.get("skill_names_csv"))),
        "benefit_ids": _parse_int_csv(r.get("benefit_ids_csv")),
        "applicant_count": _safe_int(r.get("applicant_count")) or 0,
        "job_description": r["job_description"],
        "roles_responsibility": r["roles_responsibility"],
    }

def _compute_user_rank(r: Dict[str, Any]) -> float:
    has_reviews     = (_safe_float(r.get("star_rating_avg")) or 0.0) > 0
    verified_id     = bool(_safe_int(r.get("verified_identity")))
    verified_emp    = bool(_safe_int(r.get("verified_employement")))
    any_verified    = verified_id or verified_emp
    percentage      = min(_safe_float(r.get("percentage")) or 0.0, 100.0)
    star_rating     = min(_safe_float(r.get("star_rating_avg")) or 0.0, 5.0)

    star_sub    = (star_rating / 5.0) * 500
    profile_sub = (percentage / 100.0) * 99

    if has_reviews and verified_id and verified_emp:
        base = 3000
    elif has_reviews and any_verified:
        base = 2700
    elif any_verified:
        base = 2000
    elif percentage >= 70:
        base = 1000
    else:
        base = 0

    return round(base + star_sub + profile_sub, 4)


def to_user_doc(r: Dict[str, Any]) -> Dict[str, Any]:
    name = r["full_name"]
    return {
        "id": int(r["id"]),
        "full_name": name,
        "full_name_compact": _make_compact(name),
        "ccid": r["individual_id"],
        "individual_id": r["individual_id"],
        "email": r["email"],
        "phone": r["phone"],
        "slug": r["slug"],

        # user's own industry
        "user_industry_id": _safe_int(r["user_industry_id"]),
        # current company's industry (matches PHP filter on cmp.industry)
        "industry_id": _safe_int(r.get("company_industry_id")),
        "industry_name": r["industry_name"],
        "percentage": _safe_float(r["percentage"]),

        "country": _safe_int(r.get("country")),
        "state": _safe_int(r.get("state")),
        "city": _safe_int(r.get("city")),
        "country_name": _safe_str(r.get("country_name")),
        "state_name": _safe_str(r.get("state_name")),
        "city_name": _safe_str(r.get("city_name")),

        "work_status": _safe_int(r.get("work_status")),
        "work_status_name": _safe_str(r.get("work_status_name")),
        "current_company": _safe_int(r.get("current_company")),
        "current_company_name": _safe_str(r.get("current_company_name")),
        "current_possition": _safe_int(r.get("current_possition")),
        "current_position_name": _safe_str(r.get("current_position_name")),
        "on_immediate": _safe_int(r.get("on_immediate")),
        "on_notice": _safe_int(r.get("on_notice")),

        "exp_department": _safe_int(r.get("exp_department")),
        "exp_department_name": _safe_str(r.get("exp_department_name")),
        "exp_employment_type": _safe_int(r.get("exp_employment_type")),
        "exp_employment_type_name": _safe_str(r.get("exp_employment_type_name")),
        "exp_salary": _safe_int(r.get("exp_salary")),
        "verified_employement": bool(_safe_int(r.get("verified_employement")) or 0),
        "verified_salary": bool(_safe_int(r.get("verified_salary")) or 0),
        "verified_identity": bool(_safe_int(r.get("verified_identity")) or 0),

        "star_rating_avg": _safe_float(r.get("star_rating_avg")) or 0.0,
        "total_experience_years": _safe_float(r.get("total_experience_years")) or 0.0,

        "create_date": _safe_str(r["create_date"]),
        "modify_date": _safe_str(r["modify_date"]),

        "skill_ids": _parse_int_csv(r.get("skill_ids_csv")),
        "skill_names": _dedup_skills(_parse_skill_names(r.get("skill_names_csv"))),

        # education fields for course/course_type filters
        "education_course_ids": _parse_int_csv(r.get("education_course_ids_csv")),
        "education_course_type_ids": _parse_int_csv(r.get("education_course_type_ids_csv")),
	"rank_score": _compute_user_rank(r),
    }

def _compute_company_rank(r: Dict[str, Any]) -> float:
    import time

    is_verified  = bool(_safe_int(r.get("is_verified_company")))
    last_job_ts  = _safe_int(r.get("last_job_create_ts")) or 0
    has_jobs     = last_job_ts > 0
    benefit_ids  = (r.get("benefit_ids_csv") or "").strip()
    has_benefits = bool(benefit_ids)

    recency_sub = 0.0
    if has_jobs:
        age_days    = (time.time() - last_job_ts) / 86400
        recency_sub = max(0.0, 1.0 - age_days / 180.0) * 500

    benefit_sub = 99.0 if has_benefits else 0.0

    if is_verified and has_jobs:
        base = 2000
    elif is_verified or has_jobs:
        base = 1000
    else:
        base = 0

    return round(base + recency_sub + benefit_sub, 4)

def to_company_doc(r: Dict[str, Any]) -> Dict[str, Any]:
    name = r["full_name"]
    return {
        "id": int(r["id"]),
        "full_name": name,
        "full_name_compact": _make_compact(name),
        "ccid": r["individual_id"],
        "individual_id": r["individual_id"],
        "slug": r["slug"],
        "email": r["email"],
        "phone": r["phone"],

        "industry_id": _safe_int(r["industry_id"]),
        "industry_name": r["industry_name"],

        "country": _safe_int(r.get("country")),
        "state": _safe_int(r.get("state")),
        "city": _safe_int(r.get("city")),
        "country_name": _safe_str(r.get("country_name")),
        "state_name": _safe_str(r.get("state_name")),
        "city_name": _safe_str(r.get("city_name")),

        "benefit_ids": _parse_int_csv(r.get("benefit_ids_csv")),
        "job_mode_ids": _parse_int_csv(r.get("job_mode_ids_csv")),
	"job_titles": [t.strip() for t in (r.get("job_titles_csv") or "").split("||") if t.strip()],
        "last_job_create_ts": _safe_int(r.get("last_job_create_ts")) or 0,
        "is_verified_company": bool(_safe_int(r.get("is_verified_company")) or 0),

        "create_date": _safe_str(r["create_date"]),
        "modify_date": _safe_str(r["modify_date"]),
	"rank_score": _compute_company_rank(r),
    }


# ---------------------------------------------------------------------------
# Meilisearch helpers
# ---------------------------------------------------------------------------

def meili_post(index: str, docs: List[Dict[str, Any]]) -> int:
    if not docs:
        return -1
    r = requests.post(
        f"{MEILI_URL}/indexes/{index}/documents",
        headers=HEADERS,
        json=docs,
        timeout=120,
    )
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Indexing '{index}' failed: {r.status_code} {r.text}")
    return r.json().get("taskUid", -1)


def meili_delete_all(index: str) -> int:
    r = requests.delete(
        f"{MEILI_URL}/indexes/{index}/documents",
        headers=HEADERS,
        timeout=60,
    )
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Delete all docs '{index}' failed: {r.status_code} {r.text}")
    task_uid = r.json().get("taskUid", -1)
    print(f"  [ok]  Delete-all enqueued for '{index}' (task: {task_uid})")
    return task_uid


def meili_wait_for_task(task_uid: int, poll: float = 1.0, timeout: float = 300.0) -> None:
    import time
    elapsed = 0.0
    while elapsed < timeout:
        r = requests.get(f"{MEILI_URL}/tasks/{task_uid}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            status = r.json().get("status", "")
            if status == "succeeded":
                return
            if status in ("failed", "canceled"):
                raise RuntimeError(f"Meilisearch task {task_uid} {status}: {r.json().get('error')}")
        time.sleep(poll)
        elapsed += poll
    raise TimeoutError(f"Meilisearch task {task_uid} did not complete in {timeout}s")


# ---------------------------------------------------------------------------
# Streaming fetch + index
# ---------------------------------------------------------------------------

def _build_sql(sql_template: str, since_expr: str, since: Optional[str]) -> Tuple[str, Sequence[Any]]:
    if since:
        # Convert provided since (ISO datetime string) to UNIX timestamp (int)
        # This avoids issues with non-standard datetime formats stored in the DB
        try:
            # Expecting format like "YYYY-MM-DD HH:MM:SS"
            dt = datetime.strptime(since, "%Y-%m-%d %H:%M:%S")
            ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            # If numeric string was passed (already a timestamp), use it
            try:
                ts = int(float(since))
            except Exception:
                # Fallback to original string comparison if parsing fails
                return sql_template.format(since_clause=f" AND {since_expr} >= %s"), (since,)

        # Compare using UNIX_TIMESTAMP on DB side to avoid format mismatches
        return sql_template.format(since_clause=f" AND UNIX_TIMESTAMP({since_expr}) >= %s"), (ts,)
    return sql_template.format(since_clause=""), ()


async def stream_and_index(
    pool: aiomysql.Pool,
    sql: str,
    params: Sequence[Any],
    index: str,
    mapper: Callable[[Dict[str, Any]], Dict[str, Any]],
    batch_size: int,
    clear_index: bool,
) -> int:
    if clear_index:
        delete_task = meili_delete_all(index)
        print(f"  [wait] Waiting for delete task {delete_task} to complete...")
        meili_wait_for_task(delete_task)
        print(f"  [ok]   Index '{index}' cleared.")

    count = 0
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.SSDictCursor) as cursor:
            log.debug("[indexer] Executing SQL: %s params=%s", sql, params)
            await cursor.execute(sql, params)
            while True:
                rows = await cursor.fetchmany(batch_size)
                if not rows:
                    break
                docs = [mapper(row) for row in rows]
                count += len(docs)
                task_uid = meili_post(index, docs)
                print(f"  [push] {index}: {count} docs pushed (task: {task_uid})")
    return count


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

INDEXES = {
    "jobs": {
        "sql": SQL_JOBS,
        "mapper": to_job_doc,
        "since_expr": "COALESCE(cj.modify_date, cj.create_date)",
    },
    "users": {
        "sql": SQL_USERS,
        "mapper": to_user_doc,
        "since_expr": "COALESCE(u.modify_date, u.create_date)",
    },
    "companies": {
        "sql": SQL_COMPANIES,
        "mapper": to_company_doc,
        "since_expr": "COALESCE(u.modify_date, u.create_date)",
    },
}


async def run_index(
    indexes_to_run: Optional[List[str]] = None,
    batch_size: int = 1000,
    since: Optional[str] = None,
) -> Dict[str, int]:
    targets = indexes_to_run or list(INDEXES.keys())
    pool = await aiomysql.create_pool(**DB_DSN)
    totals: Dict[str, int] = {}
    try:
        for name in targets:
            cfg = INDEXES[name]
            sql, params = _build_sql(cfg["sql"], cfg["since_expr"], since)
            clear_index = since is None
            print(f"\n── Rebuilding '{name}' ──────────────────────────────────")
            total = await stream_and_index(pool, sql, params, name, cfg["mapper"], batch_size, clear_index)
            print(f"  [done] '{name}': {total} documents indexed.")
            totals[name] = total
    finally:
        pool.close()
        await pool.wait_closed()
    print("\nAll done.")
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Meilisearch indexes from MySQL.")
    parser.add_argument("--rebuild-all", action="store_true", required=True)
    parser.add_argument("--index", choices=list(INDEXES.keys()))
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--since", type=str, default=None)
    args = parser.parse_args()

    targets = [args.index] if args.index else list(INDEXES.keys())
    asyncio.run(run_index(targets, args.batch_size, args.since))


if __name__ == "__main__":
    main()
