from __future__ import annotations

import binascii
import hashlib
import re
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User

PBKDF2_ROUNDS = 120000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return "pbkdf2$%s$%s" % (salt, binascii.hexlify(digest).decode("ascii"))


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return secrets.compare_digest(binascii.hexlify(check).decode("ascii"), digest)


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def email_allowed(email: str, restriction: str) -> bool:
    domains = [item.strip().lower().lstrip("@") for item in (restriction or "").split(",") if item.strip()]
    if not domains:
        return True
    host = email.split("@")[-1].lower()
    return host in domains


def password_rules(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if password.isdigit() or password.isalpha():
        return "Password must include letters and numbers"
    return None


async def user_from_session(request: Request, db: AsyncSession) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = await db.get(User, int(user_id))
    if not user or user.status != "active":
        return None
    return user


async def optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[User]:
    return await user_from_session(request, db)


async def require_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user = await user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    path = request.url.path
    allowed = path in {
        "/api/auth/me",
        "/api/auth/logout",
        "/api/auth/password",
        "/api/auth/profile",
        "/api/auth/preferences",
        "/password",
    }
    if user.must_change_password and not allowed and not path.startswith("/static"):
        raise HTTPException(status_code=403, detail="password_change_required")
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def find_user(db: AsyncSession, identifier: str) -> Optional[User]:
    ident = identifier.strip().lower()
    result = await db.execute(
        select(User).where(or_(User.username == ident, User.email == ident))
    )
    return result.scalar_one_or_none()
