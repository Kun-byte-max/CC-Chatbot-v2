# Chat API Response Contract (`POST /chat`)

This document defines the response schema and payload contract for `POST /chat` under the structured response rollout (`COMPOSE_MODE`).

---

## 1. Overview & Feature Flag (`COMPOSE_MODE`)

The backend response format supports three operational modes controlled by the `COMPOSE_MODE` environment variable:

| Mode | `reply` Text | `results` Array | Purpose / Client Impact |
| :--- | :--- | :--- | :--- |
| `legacy` | Full job/candidate descriptions in prose | `None` / empty | Rollback path. Identical to pre-change behavior. |
| `dual` *(Default)* | Full job/candidate descriptions in prose | **Populated with structured objects** | Frontend integration & testing against real payloads. |
| `structured` | 1–2 framing sentences only | **Populated with structured objects** | Latency optimized. Frontend renders structured result cards. |

---

## 2. Response Schema Definitions (`backend/schemas/schemas.py`)

### `ChatResponse`
- **`reply`** (`str`, required): The assistant's text message. In `structured` mode, this is a concise framing message.
- **`success`** (`bool`, required): `True` if request completed successfully.
- **`request_id`** (`str`, optional): Unique correlation ID for tracing.
- **`results`** (`List[Union[JobCard, CandidateCard]]`, optional): Structured search result items. `None` if no structured results exist for this turn.
- **`result_type`** (`str`, optional): Discriminator field (`"jobs"` or `"candidates"`). `None` if no structured results exist.

---

### `JobCard` Schema (`result_type == "jobs"`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `job_id` | `int` | Unique job listing ID. |
| `title` | `str` | Job title (e.g. `"Senior Backend Engineer"`). |
| `company` | `Optional[str]` | Company name (e.g. `"Acme Fintech"`). |
| `location` | `Optional[str]` | Job location (e.g. `"Pune, India"`). |
| `job_mode` | `Optional[str]` | Work arrangement (`"Remote"`, `"Hybrid"`, `"On-site"`). |
| `experience` | `Optional[str]` | Required experience (e.g. `"4+ years"`). |
| `salary` | `Optional[str]` | Salary range / figure (e.g. `"₹18,00,000 - ₹24,00,000"`). |
| `url` | `Optional[str]` | Absolute or relative URL to job details page. |
| `match_reason` | `Optional[str]` | Server-computed match explanation (e.g. `"8 of 9 skills matched"`). |

---

### `CandidateCard` Schema (`result_type == "candidates"`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `candidate_id` | `int` | Unique candidate user ID. |
| `name` | `str` | Candidate full name. |
| `headline` | `Optional[str]` | Professional headline (e.g. `"Senior Python & Django Developer"`). |
| `location` | `Optional[str]` | Candidate location (e.g. `"Bangalore, India"`). |
| `experience` | `Optional[str]` | Total years of experience (e.g. `"5 years"`). |
| `skills` | `List[str]` | Matched or relevant skill set tags. |
| `url` | `Optional[str]` | URL to candidate profile page. |
| `match_reason` | `Optional[str]` | Server-computed match explanation. |

> [!CAUTION]
> **Privacy & Security Constraint**: `CandidateCard` NEVER carries contact details (`email` or `phone`). Frontend must render contact buttons that route through authorized backend endpoints.

---

## 3. Real Payload Examples

### Example A: Job Search Result Payload (`result_type == "jobs"`)

```json
{
  "reply": "I found 2 remote Python developer positions matching your profile in Pune.",
  "success": true,
  "request_id": "req_8f9a12bc",
  "result_type": "jobs",
  "results": [
    {
      "job_id": 1042,
      "title": "Senior Backend Engineer",
      "company": "Acme Fintech",
      "location": "Pune, India",
      "job_mode": "Remote",
      "experience": "4+ years",
      "salary": "₹20,00,000 - ₹25,00,000",
      "url": "/jobs-details/1042",
      "match_reason": "8 of 9 skills matched"
    },
    {
      "job_id": 1089,
      "title": "Python Developer",
      "company": "Globex Systems",
      "location": "Pune, India",
      "job_mode": "Remote",
      "experience": "3+ years",
      "salary": "₹15,00,000 - ₹18,00,000",
      "url": "/jobs-details/1089",
      "match_reason": "6 of 9 skills matched"
    }
  ]
}
```

---

### Example B: Candidate Search Result Payload (`result_type == "candidates"`)

```json
{
  "reply": "Here are candidate profiles matching senior backend engineer roles in Bangalore.",
  "success": true,
  "request_id": "req_9921ab01",
  "result_type": "candidates",
  "results": [
    {
      "candidate_id": 2041,
      "name": "Rohan Mehta",
      "headline": "Senior Backend Developer | FastAPI & Distributed Systems",
      "location": "Bangalore, India",
      "experience": "5 years",
      "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
      "url": "/candidates/2041",
      "match_reason": "5 years exp in Bangalore"
    }
  ]
}
```

---

## 4. Frontend Rendering Expectations

1. **Card Rendering**: If `results` is non-empty, render item cards below `reply` text according to `result_type` (`"jobs"` vs `"candidates"`).
2. **Fallback**: If `results` is `null` or missing (e.g. during smalltalk or profile updates), render `reply` as standard chat prose message.
3. **Link Handling**: Use `url` field from the structured card for primary card actions. Do not rely on LLM text parsing for links.
