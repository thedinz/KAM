"""Lightweight authentication helpers for KAM."""
from __future__ import annotations

import os
import secrets
import threading
import time
from typing import Optional

from fastapi import Request

_PASSWORD_ENV = "KAM_AUTH_PASSWORD"
_COOKIE_NAME_ENV = "KAM_AUTH_COOKIE"
_TOKEN_TTL_ENV = "KAM_AUTH_TOKEN_TTL_SECONDS"
_COOKIE_SECURE_ENV = "KAM_AUTH_COOKIE_SECURE"

_DEFAULT_COOKIE_NAME = "kam_auth"
_DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7

_LOCK = threading.Lock()
_SESSIONS: dict[str, float] = {}


def is_enabled() -> bool:
    password = os.getenv(_PASSWORD_ENV)
    return bool(password and password.strip())


def cookie_name() -> str:
    value = os.getenv(_COOKIE_NAME_ENV)
    return value.strip() if value and value.strip() else _DEFAULT_COOKIE_NAME


def token_ttl_seconds() -> int:
    raw = os.getenv(_TOKEN_TTL_ENV)
    if not raw:
        return _DEFAULT_TTL_SECONDS
    try:
        return max(60, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SECONDS


def cookie_secure(request: Request) -> bool:
    raw = os.getenv(_COOKIE_SECURE_ENV)
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


def verify_password(candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    expected = os.getenv(_PASSWORD_ENV, "")
    if not expected:
        return False
    return secrets.compare_digest(candidate, expected)


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    expiry = time.time() + token_ttl_seconds()
    with _LOCK:
        _SESSIONS[token] = expiry
    return token


def validate_session(token: Optional[str]) -> bool:
    if not token:
        return False
    now = time.time()
    with _LOCK:
        expiry = _SESSIONS.get(token)
        if not expiry or expiry < now:
            _SESSIONS.pop(token, None)
            return False
        return True


def clear_session(token: Optional[str]) -> None:
    if not token:
        return
    with _LOCK:
        _SESSIONS.pop(token, None)


def clear_expired() -> None:
    now = time.time()
    with _LOCK:
        expired = [token for token, expiry in _SESSIONS.items() if expiry < now]
        for token in expired:
            _SESSIONS.pop(token, None)
