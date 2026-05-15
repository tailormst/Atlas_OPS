"""
Authentication & Authorization for ATLAS-OPS.

Simplified JWT auth with Admin and Company roles.
Admin key-based initial login. No public registration.
"""
import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()
logger = get_logger(__name__)


# ── JWT helpers (lightweight, no external dependency) ────────────────────────
import json
import base64
import hmac

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)

def create_jwt(payload: dict, secret: str, expire_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {**payload, "iat": int(time.time()), "exp": int(time.time()) + expire_seconds}
    header_b64 = _b64url_encode(json.dumps(header).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    signature = hmac.new(secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_jwt(token: str, secret: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        expected_sig = hmac.new(secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ── Request / Response Schemas ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str
    admin_key: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    email: str
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str


# ── Default Credentials (seeded from .env) ───────────────────────────────────

ADMIN_CREDENTIALS = {
    "admin@atlas-ops.ai": {
        "password_hash": hashlib.sha256("atlas_admin_2024".encode()).hexdigest(),
        "role": "admin",
    }
}

COMPANY_CREDENTIALS = {
    "demo@company.com": {
        "password_hash": hashlib.sha256("demo_company_2024".encode()).hexdigest(),
        "role": "company",
        "company_name": "Demo Corp",
    }
}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse, summary="Login")
async def login(body: LoginRequest):
    # Check admin credentials
    if body.email in ADMIN_CREDENTIALS:
        cred = ADMIN_CREDENTIALS[body.email]
        pwd_hash = hashlib.sha256(body.password.encode()).hexdigest()
        if pwd_hash == cred["password_hash"]:
            # Optionally verify admin key
            if body.admin_key and body.admin_key != settings.secret_key:
                raise HTTPException(status_code=401, detail="Invalid admin key")

            access_token = create_jwt(
                {"sub": body.email, "role": "admin"},
                settings.secret_key,
                expire_seconds=3600,
            )
            refresh_token = create_jwt(
                {"sub": body.email, "role": "admin", "type": "refresh"},
                settings.secret_key,
                expire_seconds=86400,
            )
            logger.info("admin_login", email=body.email)
            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                role="admin",
                email=body.email,
                expires_in=3600,
            )

    # Check company credentials
    if body.email in COMPANY_CREDENTIALS:
        cred = COMPANY_CREDENTIALS[body.email]
        pwd_hash = hashlib.sha256(body.password.encode()).hexdigest()
        if pwd_hash == cred["password_hash"]:
            access_token = create_jwt(
                {"sub": body.email, "role": "company", "company": cred.get("company_name", "")},
                settings.secret_key,
                expire_seconds=3600,
            )
            refresh_token = create_jwt(
                {"sub": body.email, "role": "company", "type": "refresh"},
                settings.secret_key,
                expire_seconds=86400,
            )
            logger.info("company_login", email=body.email)
            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                role="company",
                email=body.email,
                expires_in=3600,
            )

    raise HTTPException(status_code=401, detail="Invalid email or password")


@router.post("/refresh", response_model=LoginResponse, summary="Refresh token")
async def refresh_token(body: RefreshRequest):
    payload = verify_jwt(body.refresh_token, settings.secret_key)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_jwt(
        {"sub": payload["sub"], "role": payload["role"]},
        settings.secret_key,
        expire_seconds=3600,
    )
    new_refresh = create_jwt(
        {"sub": payload["sub"], "role": payload["role"], "type": "refresh"},
        settings.secret_key,
        expire_seconds=86400,
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        role=payload["role"],
        email=payload["sub"],
        expires_in=3600,
    )


@router.get("/me", summary="Get current user")
async def get_me(authorization: str = Header(default="")):
    token = authorization.replace("Bearer ", "")
    payload = verify_jwt(token, settings.secret_key)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {
        "email": payload.get("sub"),
        "role": payload.get("role"),
        "company": payload.get("company", ""),
    }
