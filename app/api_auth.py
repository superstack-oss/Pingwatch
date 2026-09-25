from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.mailer import notify
from app.models import AccessRequest, User
from app.schemas import AccessRequestIn, ApproverOut, LoginIn, PasswordIn, PreferencesIn, ProfileIn, UserOut
from app.security import (
    email_allowed,
    find_user,
    hash_password,
    password_rules,
    user_from_session,
    valid_email,
    verify_password,
)
from app.settings_store import all_settings, get_setting, public_settings, write_audit

router = APIRouter()


def _user_out(user: User, approver: User | None = None) -> UserOut:
    approved = None
    if approver:
        approved = ApproverOut(name=approver.name, email=approver.email)
    return UserOut(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        must_change_password=bool(user.must_change_password),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        password_updated_at=user.password_updated_at,
        timezone=user.timezone,
        approved_by=approved,
    )


async def _approver_for(db: AsyncSession, user: User) -> User | None:
    if user.approved_by_id:
        found = await db.get(User, user.approved_by_id)
        if found:
            return found
    row = (
        await db.execute(
            select(AccessRequest)
            .where(AccessRequest.email == user.email, AccessRequest.status == "approved")
            .order_by(AccessRequest.reviewed_at.desc())
        )
    ).scalars().first()
    if row and row.reviewed_by:
        return await db.get(User, row.reviewed_by)
    return None


@router.post("/api/auth/login")
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    user = await find_user(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="This account is disabled")
    user.last_login_at = datetime.utcnow()
    request.session["user_id"] = user.id
    await write_audit(db, "login", "Signed in", user, request)
    await db.commit()
    return {"user": _user_out(user), "must_change_password": bool(user.must_change_password)}


@router.post("/api/auth/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    user = await user_from_session(request, db)
    request.session.clear()
    if user:
        await write_audit(db, "logout", "Signed out", user, request)
        await db.commit()
    return {"ok": True}


@router.get("/api/auth/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    user = await user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    raw = await all_settings(db)
    prefs = public_settings(raw)
    if user.timezone:
        prefs["timezone"] = user.timezone
    return {"user": _user_out(user, await _approver_for(db, user)), "settings": prefs}


@router.post("/api/auth/password")
async def change_password(payload: PasswordIn, request: Request, db: AsyncSession = Depends(get_db)):
    user = await user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    rule = password_rules(payload.new_password)
    if rule:
        raise HTTPException(status_code=400, detail=rule)
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="Choose a different password")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = 0
    user.password_updated_at = datetime.utcnow()
    await write_audit(db, "password_change", "Updated password", user, request)
    await db.commit()
    await db.refresh(user)
    return {"ok": True, "user": _user_out(user, await _approver_for(db, user))}


@router.patch("/api/auth/profile")
async def update_profile(payload: ProfileIn, request: Request, db: AsyncSession = Depends(get_db)):
    user = await user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        cleaned = " ".join((data["name"] or "").split())
        if not cleaned:
            raise HTTPException(status_code=400, detail="Name is required")
        user.name = cleaned
    if "phone" in data:
        user.phone = (data["phone"] or "").strip() or None
    if "email" in data:
        email = (data["email"] or "").strip().lower()
        if not valid_email(email):
            raise HTTPException(status_code=400, detail="Enter a valid email address")
        restriction = await get_setting(db, "email_domain_restriction", "")
        if not email_allowed(email, restriction):
            raise HTTPException(status_code=400, detail="That email domain is not allowed")
        existing = (
            await db.execute(select(User).where(User.email == email, User.id != user.id))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="That email is already in use")
        user.email = email
    user.updated_at = datetime.utcnow()
    await write_audit(db, "profile_update", "Updated profile", user, request)
    await db.commit()
    await db.refresh(user)
    return {"user": _user_out(user, await _approver_for(db, user))}


@router.patch("/api/auth/preferences")
async def update_preferences(payload: PreferencesIn, request: Request, db: AsyncSession = Depends(get_db)):
    user = await user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    if payload.timezone:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(payload.timezone)
        except Exception:
            raise HTTPException(status_code=400, detail="Unknown timezone")
        user.timezone = payload.timezone
    await write_audit(db, "preferences_update", "Updated preferences", user, request)
    await db.commit()
    await db.refresh(user)
    raw = await all_settings(db)
    prefs = public_settings(raw)
    if user.timezone:
        prefs["timezone"] = user.timezone
    return {"user": _user_out(user, await _approver_for(db, user)), "settings": prefs}


@router.post("/api/auth/request-access")
async def request_access(payload: AccessRequestIn, request: Request, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()
    if not valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    restriction = await get_setting(db, "email_domain_restriction", "")
    if not email_allowed(email, restriction):
        raise HTTPException(status_code=400, detail="That email domain is not allowed")
    rule = password_rules(payload.password)
    if rule:
        raise HTTPException(status_code=400, detail=rule)
    existing_user = (await db.execute(select(User).where(or_(User.email == email, User.username == email)))).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    pending = (
        await db.execute(
            select(AccessRequest).where(AccessRequest.email == email, AccessRequest.status == "pending")
        )
    ).scalar_one_or_none()
    if pending:
        raise HTTPException(status_code=409, detail="A request with that email is already pending")
    db.add(
        AccessRequest(
            name=payload.name.strip(),
            email=email,
            phone=payload.phone.strip(),
            password_hash=hash_password(payload.password),
            status="pending",
        )
    )
    await write_audit(db, "access_request", "Requested access for %s" % email, None, request)
    await db.commit()
    notify_flag = (await get_setting(db, "notify_on_access_request", "true")).lower() in {"1", "true", "yes"}
    if notify_flag:
        admins = (await db.execute(select(User).where(User.role == "admin", User.status == "active"))).scalars().all()
        for admin in admins:
            await notify(
                db,
                admin.email,
                "Pingwatch access request",
                "%s (%s) requested access." % (payload.name, email),
            )
    return {"ok": True}


@router.get("/api/settings/public")
async def public_app_settings(db: AsyncSession = Depends(get_db)):
    return public_settings(await all_settings(db))
