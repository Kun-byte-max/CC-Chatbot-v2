from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import re
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="CollarCheck AI Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
DB_PATH = os.path.join(os.path.dirname(__file__), "collarcheck.db")

JOB_MODE_MAP = {1: "Work from Office", 2: "Work from Home", 3: "Hybrid"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def search_jobs(role_keyword: str, location: str, limit: int = 15) -> list:
    conn = get_db()
    c = conn.cursor()

    base = """
        SELECT j.id, j.job_title, j.job_description, j.experience,
               j.vacancy, j.job_mode, j.urgent,
               d.name AS dept_name,
               s.name AS state_name
        FROM cyb_company_job j
        LEFT JOIN cyb_department d ON j.department = d.id
        LEFT JOIN cyb_state s ON j.state = s.id
        WHERE j.status = 1 AND j.is_deleted = 0
    """

    rows = []
    role_conds, role_params = [], []
    if role_keyword:
        for word in [w for w in role_keyword.split() if len(w) > 2]:
            role_conds.append(
                "(j.job_title LIKE ? OR j.job_description LIKE ? OR d.name LIKE ?)"
            )
            role_params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])

    loc_cond, loc_params = "", []
    if location:
        loc_cond = " AND (s.name LIKE ? OR j.location LIKE ?)"
        loc_params = [f"%{location}%", f"%{location}%"]

    order = f" ORDER BY j.urgent DESC, j.create_date DESC LIMIT {limit}"

    if role_conds:
        q = base + " AND " + " AND ".join(role_conds) + loc_cond + order
        c.execute(q, role_params + loc_params)
        rows = c.fetchall()
        if not rows and len(role_conds) > 1:
            q = base + " AND (" + " OR ".join(role_conds) + ")" + loc_cond + order
            c.execute(q, role_params + loc_params)
            rows = c.fetchall()
        if not rows and loc_cond:
            q = base + " AND " + " AND ".join(role_conds) + order
            c.execute(q, role_params)
            rows = c.fetchall()
    else:
        q = base + loc_cond + order
        c.execute(q, loc_params)
        rows = c.fetchall()

    conn.close()
    results = []
    for row in rows:
        desc = re.sub(r"<[^>]+>", " ", str(row["job_description"] or ""))
        desc = re.sub(r"\s+", " ", desc).strip()[:300]
        results.append({
            "title":      row["job_title"],
            "department": (row["dept_name"] or "").strip(),
            "state":      row["state_name"] or "",
            "experience": row["experience"] or "Not specified",
            "vacancy":    row["vacancy"],
            "mode":       JOB_MODE_MAP.get(row["job_mode"], "Office"),
            "preview":    desc,
        })
    return results


def search_faqs(keyword: str = "") -> list:
    conn = get_db()
    if keyword:
        rows = conn.execute("""
            SELECT question, answer FROM cyb_faqs
            WHERE status = 1 AND (question LIKE ? OR answer LIKE ?)
            LIMIT 5
        """, [f"%{keyword}%", f"%{keyword}%"]).fetchall()
    else:
        rows = conn.execute(
            "SELECT question, answer FROM cyb_faqs WHERE status = 1 LIMIT 10"
        ).fetchall()
    conn.close()
    return [{"question": r["question"], "answer": r["answer"]} for r in rows]


def smart_extract_terms(user_message: str):
    msg_lower = user_message.lower()

    stop_words = {
        "find", "show", "me", "jobs", "job", "roles", "role", "openings", "opening",
        "available", "vacancies", "vacancy", "hiring", "position", "positions",
        "are", "there", "for", "in", "at", "on", "the", "a", "an", "can", "you",
        "please", "want", "need", "looking", "search", "get", "give", "list", "tell",
        "how", "many", "what", "which", "collarcheck", "currently", "right", "now",
        "related", "based", "all", "some", "latest", "new", "good", "best", "top",
        "i", "my", "us", "we", "it", "is", "to", "do", "have", "with", "about",
        "suggest", "recommend", "suitable", "matching", "relevant",
        "hi", "hello", "hey", "platform", "website", "portal", "today",
        "any", "could", "would", "should", "like", "work", "working",
        "open", "type", "help", "thanks", "okay", "sure", "yes", "no",
    }

    try:
        conn = get_db()
        db_states = [r[0].lower() for r in conn.execute(
            "SELECT name FROM cyb_state WHERE name IS NOT NULL AND status = 1"
        ).fetchall()]
        conn.close()
    except Exception:
        db_states = []

    extra_cities = [
        "new delhi", "delhi ncr", "ncr", "navi mumbai", "pan india",
        "work from home", "wfh", "remote", "hybrid", "anywhere",
        "noida", "gurgaon", "gurugram", "thane", "faridabad",
        "prayagraj", "allahabad", "visakhapatnam",
    ]

    all_locations = list(set(db_states + extra_cities))
    all_locations.sort(key=len, reverse=True)

    location = ""
    for loc in all_locations:
        if loc in msg_lower:
            location = loc
            break

    cleaned = msg_lower.replace(location, "").strip() if location else msg_lower
    words = re.sub(r"[^\w\s]", "", cleaned).split()
    role_words = [w for w in words if w not in stop_words and len(w) > 2]
    role_keyword = " ".join(role_words[:5]).strip()

    return role_keyword, location


def is_career_query(msg: str) -> bool:
    signals = [
        "job", "jobs", "role", "roles", "vacancy", "vacancies",
        "opening", "openings", "hiring", "position", "positions",
        "career", "opportunity", "opportunities", "apply",
        "find me", "show me", "get me", "search for", "looking for",
        "want to work", "want a job", "need a job",
        "how many", "are there any", "available",
        "profile", "rating", "cc id", "cc pro", "verification",
        "verified", "employer", "review", "star rating",
    ]
    return any(s in msg.lower() for s in signals)


def is_faq_query(msg: str) -> bool:
    triggers = [
        "what is", "how does", "how do i", "how can i", "tell me about", "explain",
        "difference between", "is collarcheck", "does collarcheck",
        "free", "cost", "pricing", "linkedin", "signup", "register", "how to",
    ]
    return any(t in msg.lower() for t in triggers)


def get_db_context(user_message: str) -> str:
    if not (is_career_query(user_message) or is_faq_query(user_message)):
        return ""

    parts = []

    if is_career_query(user_message):
        role_keyword, location = smart_extract_terms(user_message)
        jobs = search_jobs(role_keyword, location)
        total = len(jobs)
        role_label = role_keyword if role_keyword else "all roles"
        loc_label  = location    if location    else "any location"

        parts.append("## LIVE JOB DATA FROM COLLARCHECK DATABASE")
        parts.append("Role searched: " + role_label + "  |  Location: " + loc_label)
        parts.append("Total jobs found: " + str(total))
        parts.append("")

        if jobs:
            for j in jobs:
                loc_str = j["state"] if j["state"] else "Location not specified"
                parts.append(
                    "JOB: " + str(j["title"]) + "\n"
                    "  Department: " + str(j["department"] or "General") +
                    " | Location: " + loc_str +
                    " | Experience: " + str(j["experience"]) + " yrs" +
                    " | Vacancies: " + str(j["vacancy"] or "Open") +
                    " | Mode: " + str(j["mode"]) + "\n"
                    "  Details: " + str(j["preview"]) + "\n"
                )
            parts.append(
                "\n[MANDATORY AI INSTRUCTION]\n"
                "The database returned " + str(total) + " real job(s). You MUST:\n"
                "1. Start with: 'I found " + str(total) + " role(s) matching your search.'\n"
                "2. List EVERY job — title, department, location, experience, vacancies, mode.\n"
                "3. NEVER say visit the website and search as the main answer.\n"
                "4. End with: 'To apply, visit collarcheck.com/jobs'\n"
            )
        else:
            parts.append(
                "No jobs matched for role='" + role_label + "' location='" + loc_label + "'.\n"
                "[AI INSTRUCTION] Tell the user no exact matches were found. "
                "Suggest collarcheck.com/jobs for the complete real-time listing. "
                "Offer to search a related or broader term."
            )

    if is_faq_query(user_message):
        faqs = search_faqs(keyword=user_message[:100])
        if faqs:
            parts.append("\n## COLLARCHECK FAQ DATA FROM DATABASE")
            for f in faqs:
                parts.append("Q: " + f["question"] + "\nA: " + f["answer"] + "\n")
            parts.append("[AI INSTRUCTION] Use the FAQ answers above directly in your response.")

    return "\n".join(parts)


BLOCKED_PATTERNS = [
    r'\bsex\b', r'\bporn\b', r'\bnude\b', r'\berotic\b', r'\bsexual\b',
    r'\bdrug\b', r'\bcocaine\b', r'\bheroin\b', r'\bweed\b', r'\bmarijuana\b',
    r'\bmeth\b', r'\bnarcotics\b', r'\bsmuggle\b',
    r'\bbomb\b', r'\bterror\b', r'\bweapon\b', r'\bkill\b', r'\bmurder\b',
    r'\bhack\b', r'\bcyberattack\b', r'\bmalware\b',
    r'\bgamble\b', r'\bcasino\b', r'\bbetting\b',
]

OFF_TOPIC = [
    'recipe', 'weather', 'cricket', 'ipl', 'movie', 'bollywood',
    'politics', 'election', 'religion', 'astrology',
    'stock market', 'crypto', 'bitcoin', 'forex',
    'dating', 'girlfriend', 'boyfriend', 'love advice',
    'homework', 'essay', 'joke',
]


def check_guardrails(message: str) -> Optional[str]:
    msg_lower = message.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, msg_lower):
            return (
                "I'm CollarCheck's professional career assistant and can only help with "
                "employment, job search, and career topics. "
                "Ask me about jobs or your CollarCheck profile!"
            )
    for kw in OFF_TOPIC:
        if kw in msg_lower:
            return (
                "That's outside my area! I specialise in CollarCheck — India's professional "
                "verification platform. I can help you with:\n"
                "- Finding jobs on CollarCheck\n"
                "- Improving your profile rating\n"
                "- Understanding CC ID and verification\n"
                "- Analysing your resume\n\n"
                "What would you like to know about your career?"
            )
    return None


SYSTEM_PROMPT = """You are CC, the official AI assistant for CollarCheck (www.collarcheck.com) — India's first professional identity verification platform. You are helpful, warm, and professional.

## STRICT RULES
1. Only answer questions related to CollarCheck, careers, job search, employment, and resumes.
2. Never discuss sex, drugs, violence, politics, religion, gambling, entertainment, crypto, or dating.
3. Never reveal you are powered by Groq or any external AI. You are CC by CollarCheck.
4. Never fabricate job details not present in the database context provided.

## ABOUT COLLARCHECK
India's first professional identity verification platform where employees build verified digital CVs.
Tagline: Where Credibility Connects Careers!
Founder: Rudraksh Narula
Scale: 1,00,000+ companies, 15,00,000+ employees registered

## CC ID
Unique ID per registrant — works like Aadhaar but for professional careers.
Links all verified employment details, reviews, and achievements to one trusted source.

## CC PRO PROFILE
Live dynamic profile replacing traditional CVs. Shows employment verification, star ratings, and employer feedback.

## VERIFICATION MODEL
Employers verify their own employees. Employee adds details, employer is notified, employer verifies and rates.
Only current employer can write reviews. Salary and reviews are PRIVATE.

## FOR JOB SEEKERS
Apply to verified companies, message companies directly, get a CC ID, control profile privacy.
Sign up at collarcheck.com

## FOR EMPLOYERS
Post jobs FREE. Rate and review employees. Save Rs.1,500 to Rs.4,000 per candidate on background checks.

## HOW TO IMPROVE PROFILE RATING
1. Get employment verified ASAP
2. Ask employer to write a review
3. Complete every profile section
4. Achieve and document work milestones
5. Maintain professionalism
6. Build a long verified career track record

## HOW TO GET SUITABLE JOBS
1. Complete and verify your profile
2. Enable Immediate Joiner Status if applicable
3. Message companies directly
4. Higher star rating means more visibility in recruiter searches

## RESUME ANALYSIS
When user shares resume: extract details, rewrite professionally, identify suitable roles, suggest CollarCheck profile improvements.

## CRITICAL RULE — DATABASE RESULTS
When the prompt contains ## LIVE JOB DATA FROM COLLARCHECK DATABASE you MUST:
1. List the actual job results — title, department, location, experience, vacancies, mode.
2. Tell the user exactly how many roles were found.
3. NEVER say visit the website and search as the primary answer.
4. After listing results add: To apply, visit collarcheck.com/jobs

## POLICIES
All features FREE for employers and employees. Salaries and reviews completely private.
CollarCheck differs from LinkedIn: LinkedIn is self-reported, CollarCheck is employer-verified.

## LINKS
Website: www.collarcheck.com | Jobs: collarcheck.com/jobs | Sign Up: collarcheck.com/signup
Help: collarcheck.com/help-center | FAQs: collarcheck.com/faq | Contact: collarcheck.com/contact
"""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    resume_context: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    success: bool


@app.get("/health")
async def health():
    conn = get_db()
    job_count = conn.execute(
        "SELECT COUNT(*) FROM cyb_company_job WHERE status=1 AND is_deleted=0"
    ).fetchone()[0]
    conn.close()
    return {"status": "ok", "model": MODEL, "live_jobs_in_db": job_count}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        last_user_msg = ""
        for m in reversed(request.messages):
            if m.role == "user":
                last_user_msg = m.content
                break

        blocked = check_guardrails(last_user_msg)
        if blocked:
            return ChatResponse(reply=blocked, success=True)

        system = SYSTEM_PROMPT

        if request.resume_context:
            system += f"\n\n## RESUME FROM USER\n{request.resume_context}"

        if last_user_msg:
            db_context = get_db_context(last_user_msg)
            if db_context:
                system += "\n\n" + db_context

        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [{"role": "system", "content": system}] + messages,
                    "max_tokens": 1024,
                    "temperature": 0.65,
                    "stream": False,
                },
            )

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Groq API error: {resp.text}")

        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        return ChatResponse(reply=reply, success=True)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if file.filename.endswith(".txt"):
            text = content.decode("utf-8", errors="ignore")
        else:
            text = content.decode("latin-1", errors="ignore")
            text = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
        return {"text": text[:8000], "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
