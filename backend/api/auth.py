import jwt
import contextvars
from typing import Optional
from fastapi import Depends, HTTPException, Request, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

try:
    from backend.config.config import JWT_SECRET, JWT_ALGORITHM
    from backend.schemas.schemas import LoginRequest
    from backend.repositories.db import get_db
except ModuleNotFoundError:
    from config.config import JWT_SECRET, JWT_ALGORITHM
    from schemas.schemas import LoginRequest
    from repositories.db import get_db

router = APIRouter()

request_role = contextvars.ContextVar("request_role", default=None)
request_email = contextvars.ContextVar("request_email", default=None)

security = HTTPBearer(auto_error=False)

def find_user_by_token(token: str) -> Optional[dict]:
    email = None
    role = None
    uid = None

    # 1. Try local JWT secret decode
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("email")
        role = payload.get("role")
        uid = payload.get("uid") or payload.get("id")
    except Exception:
        # 2. Try unverified decode for platform JWT tokens
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            email = payload.get("email")
            uid = payload.get("uid") or payload.get("id")
        except Exception:
            pass

    conn = get_db()
    c = conn.cursor()
    try:
        if email:
            c.execute(
                "SELECT * FROM cyb_user WHERE LOWER(email) = %s AND status = 1 AND (is_deleted IS NULL OR is_deleted = 0) LIMIT 1",
                (email.lower().strip(),)
            )
            row = c.fetchone()
            if row:
                return dict(row)

        if uid:
            c.execute(
                "SELECT * FROM cyb_user WHERE (id = %s OR individual_id = %s) AND status = 1 AND (is_deleted IS NULL OR is_deleted = 0) LIMIT 1",
                (str(uid), str(uid))
            )
            row = c.fetchone()
            if row:
                return dict(row)

        c.execute(
            "SELECT * FROM cyb_user WHERE token = %s AND status = 1 AND (is_deleted IS NULL OR is_deleted = 0) LIMIT 1",
            (token.strip(),)
        )
        row = c.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    user = find_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def verify_token(req: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated. Bearer token missing.")
    token = credentials.credentials
    email = None
    role = "employee"
    payload = {}

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("email")
        role = payload.get("role", "employee")
    except jwt.PyJWTError:
        user = find_user_by_token(token)
        if user:
            email = user.get("email")
            role = "employee" if user.get("user_type") == 1 else "employer"
            payload = {"email": email, "role": role, "uid": user.get("id")}
        else:
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                email = payload.get("email")
                role = payload.get("role", "employee")
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid or expired token.")

    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    req.state.email = email
    req.state.role = role
    request_role.set(role)
    request_email.set(email)
    return payload

@router.post("/login")
async def login(request: LoginRequest):
    role = request.role.lower()
    if role not in ["employee", "employer"]:
        raise HTTPException(status_code=400, detail="Role must be 'employee' or 'employer'")
    
    payload = {
        "email": request.email.lower().strip(),
        "role": role
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # Fetch user data from DB
    user_type = 1 if role == "employee" else 2
    user_data = None
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """
            SELECT u.id, u.individual_id, u.fname, u.lname, u.email, u.phone, u.user_type, u.token,
                   u.city, u.state, u.country,
                   c.name AS city_name,
                   s.name AS state_name
            FROM cyb_user u
            LEFT JOIN cyb_cities c ON u.city = c.id
            LEFT JOIN cyb_state s ON u.state = s.id
            WHERE LOWER(u.email) = %s AND u.user_type = %s AND u.status = 1 AND (u.is_deleted IS NULL OR u.is_deleted = 0)
            LIMIT 1
            """,
            (request.email.lower().strip(), user_type)
        )
        row = c.fetchone()
        if row:
            if row.get("token") and len(str(row["token"]).strip()) > 20 and str(row["token"]).lower() != "none":
                token = str(row["token"]).strip()
            user_data = {
                "id": row["id"],
                "individual_id": row["individual_id"],
                "fname": row["fname"],
                "lname": row["lname"],
                "email": row["email"],
                "phone": row["phone"],
                "user_type": row["user_type"],
                "token": token,
                "city": row["city"],
                "city_name": row["city_name"],
                "state": row["state"],
                "state_name": row["state_name"],
                "country": row["country"]
            }
        conn.close()
    except Exception as e:
        print(f"Database error while querying user details on login: {e}")

    if not user_data:
        # Auto-generate user profile for testing if email not found in local database
        name_part = request.email.split("@")[0].title()
        user_data = {
            "id": 200014,
            "individual_id": "CCE914539",
            "fname": name_part,
            "lname": "Candidate",
            "email": request.email.lower().strip(),
            "phone": "+919315031513",
            "user_type": user_type,
            "city": 1,
            "city_name": "Delhi",
            "state": 1,
            "state_name": "Delhi",
            "country": 101
        }

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_data
    }
