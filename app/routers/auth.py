from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..services import auth as auth_service

router = APIRouter()


class LoginPayload(BaseModel):
    username: str | None = Field(default=None, max_length=1024)
    password: str = Field(max_length=1024)


class SetupPayload(BaseModel):
    code: str = Field(max_length=64)
    username: str = Field(max_length=1024)
    password: str = Field(max_length=1024)


def _client(request: Request) -> str:
    peer = getattr(request, "client", None)
    return peer.host if peer else "unknown"


def _check_throttle(client: str) -> None:
    retry_after = auth_service.login_retry_after(client)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def _start_session(request: Request, response: Response) -> None:
    token = auth_service.create_session()
    response.set_cookie(
        auth_service.cookie_name(),
        token,
        httponly=True,
        samesite="lax",
        secure=auth_service.cookie_secure(request),
        max_age=auth_service.token_ttl_seconds(),
    )


@router.get("/auth/status")
def auth_status(request: Request) -> dict:
    mode = auth_service.auth_mode()
    if not auth_service.login_required():
        return {
            "mode": mode,
            "enabled": False,
            "authenticated": True,
            "usernameRequired": False,
            "setupRequired": False,
        }
    if auth_service.setup_required():
        return {
            "mode": mode,
            "enabled": True,
            "authenticated": False,
            "usernameRequired": False,
            "setupRequired": True,
        }
    token = request.cookies.get(auth_service.cookie_name())
    auth_service.clear_expired()
    return {
        "mode": mode,
        "enabled": True,
        "authenticated": auth_service.validate_session(token),
        "usernameRequired": auth_service.username_required(),
        "setupRequired": False,
    }


@router.post("/auth/setup")
def auth_setup(payload: SetupPayload, request: Request, response: Response) -> dict:
    if not auth_service.setup_required():
        raise HTTPException(status_code=409, detail="KAM's login is already set up")
    client = _client(request)
    _check_throttle(client)
    if not auth_service.verify_setup_code(payload.code):
        auth_service.record_login_failure(client)
        raise HTTPException(status_code=401, detail="Invalid setup code")
    username = payload.username.strip()
    password = payload.password.strip()
    error = auth_service.setup_credentials_error(username, password)
    if error:
        raise HTTPException(status_code=422, detail=error)
    if not auth_service.complete_setup(username, password):
        raise HTTPException(status_code=409, detail="KAM's login is already set up")
    auth_service.clear_login_failures(client)
    _start_session(request, response)
    return {"ok": True}


@router.post("/auth/login")
def auth_login(payload: LoginPayload, request: Request, response: Response) -> dict:
    if auth_service.setup_required():
        raise HTTPException(status_code=409, detail="Finish setting up KAM's login first")
    if not auth_service.is_enabled():
        raise HTTPException(status_code=404, detail="Built-in authentication not enabled")
    client = _client(request)
    _check_throttle(client)
    if not auth_service.verify_credentials(payload.username, payload.password):
        auth_service.record_login_failure(client)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    auth_service.clear_login_failures(client)
    _start_session(request, response)
    return {"ok": True, "usernameRequired": auth_service.username_required()}


@router.post("/auth/logout")
def auth_logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(auth_service.cookie_name())
    auth_service.clear_session(token)
    response.delete_cookie(auth_service.cookie_name())
    return {"ok": True}
