from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from app.database import get_pool
from app.auth_utils import hash_password, verify_password, create_access_token
import asyncpg

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "attendee"  # or "organizer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, pool: asyncpg.Pool = Depends(get_pool)):
    if payload.role not in ("attendee", "organizer"):
        raise HTTPException(400, "role must be 'attendee' or 'organizer'")

    password_hash = hash_password(payload.password)

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO users (email, password_hash, role)
            VALUES ($1, $2, $3)
            RETURNING id, role
            """,
            payload.email, password_hash, payload.role,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "email already registered")

    token = create_access_token(row["id"], row["role"])
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, pool: asyncpg.Pool = Depends(get_pool)):
    row = await pool.fetchrow(
        "SELECT id, password_hash, role FROM users WHERE email = $1",
        payload.email,
    )
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(401, "invalid email or password")

    token = create_access_token(row["id"], row["role"])
    return TokenResponse(access_token=token)