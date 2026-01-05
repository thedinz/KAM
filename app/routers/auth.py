from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..services import auth as auth_service

router = APIRouter()


class LoginPayload(BaseModel):
    password: str


@router.get("/auth/status")
def auth_status(request: Request) -> dict:
    if not auth_service.is_enabled():
        return {"enabled": False, "authenticated": True}
    token = request.cookies.get(auth_service.cookie_name())
    auth_service.clear_expired()
    return {
        "enabled": True,
        "authenticated": auth_service.validate_session(token),
    }


@router.post("/auth/login")
def auth_login(payload: LoginPayload, request: Request, response: Response) -> dict:
    if not auth_service.is_enabled():
        raise HTTPException(status_code=404, detail="Authentication not enabled")
    if not auth_service.verify_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth_service.create_session()
    response.set_cookie(
        auth_service.cookie_name(),
        token,
        httponly=True,
        samesite="lax",
        secure=auth_service.cookie_secure(request),
        max_age=auth_service.token_ttl_seconds(),
    )
    return {"ok": True}


@router.post("/auth/logout")
def auth_logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(auth_service.cookie_name())
    auth_service.clear_session(token)
    response.delete_cookie(auth_service.cookie_name())
    return {"ok": True}
