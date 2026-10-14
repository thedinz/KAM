from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..services import auth as auth_service

router = APIRouter()


class LoginPayload(BaseModel):
    username: str | None = Field(default=None, max_length=1024)
    password: str = Field(max_length=1024)


@router.get("/auth/status")
def auth_status(request: Request) -> dict:
    mode = auth_service.auth_mode()
    if auth_service.is_reverse_proxy_mode():
        return {
            "mode": mode,
            "enabled": False,
            "authenticated": True,
            "usernameRequired": False,
        }
    if not auth_service.is_enabled():
        return {
            "mode": mode,
            "enabled": False,
            "authenticated": True,
            "usernameRequired": False,
        }
    token = request.cookies.get(auth_service.cookie_name())
    auth_service.clear_expired()
    return {
        "mode": mode,
        "enabled": True,
        "authenticated": auth_service.validate_session(token),
        "usernameRequired": auth_service.username_required(),
    }


@router.post("/auth/login")
def auth_login(payload: LoginPayload, request: Request, response: Response) -> dict:
    if not auth_service.is_enabled():
        raise HTTPException(status_code=404, detail="Built-in authentication not enabled")
    peer = getattr(request, "client", None)
    client = peer.host if peer else "unknown"
    retry_after = auth_service.login_retry_after(client)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    if not auth_service.verify_credentials(payload.username, payload.password):
        auth_service.record_login_failure(client)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    auth_service.clear_login_failures(client)
    token = auth_service.create_session()
    response.set_cookie(
        auth_service.cookie_name(),
        token,
        httponly=True,
        samesite="lax",
        secure=auth_service.cookie_secure(request),
        max_age=auth_service.token_ttl_seconds(),
    )
    return {"ok": True, "usernameRequired": auth_service.username_required()}


@router.post("/auth/logout")
def auth_logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(auth_service.cookie_name())
    auth_service.clear_session(token)
    response.delete_cookie(auth_service.cookie_name())
    return {"ok": True}
