"""Lightweight authentication helpers for KAM."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from typing import Optional

from fastapi import Request

from . import settings as settings_service

_PASSWORD_ENV = "KAM_AUTH_PASSWORD"
_USERNAME_ENV = "KAM_AUTH_USERNAME"
_AUTH_MODE_ENV = "KAM_AUTH_MODE"
_COOKIE_NAME_ENV = "KAM_AUTH_COOKIE"
_TOKEN_TTL_ENV = "KAM_AUTH_TOKEN_TTL_SECONDS"
_COOKIE_SECURE_ENV = "KAM_AUTH_COOKIE_SECURE"

_AUTH_MODE_BUILTIN = "builtin"
_AUTH_MODE_REVERSE_PROXY = "reverse_proxy"
_DEFAULT_COOKIE_NAME = "kam_auth"
_DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7
_MAX_USERNAME_LENGTH = 128
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 10
_LOGIN_MAX_TRACKED = 1000

_LOCK = threading.Lock()
# token -> (expiry, credentials fingerprint at login)
_SESSIONS: dict[str, tuple[float, str]] = {}
# client address -> failed login timestamps inside the window
_FAILED_LOGINS: dict[str, list[float]] = {}


def _normalize_mode(value: object) -> str:
    if value is None:
        return _AUTH_MODE_BUILTIN
    text = str(value).strip().lower().replace("-", "_")
    if text in {"reverse_proxy", "proxy"}:
        return _AUTH_MODE_REVERSE_PROXY
    return _AUTH_MODE_BUILTIN


def auth_mode() -> str:
    env_mode = os.getenv(_AUTH_MODE_ENV)
    if env_mode and env_mode.strip():
        return _normalize_mode(env_mode)
    try:
        data = settings_service.load_settings()
    except Exception:
        return _AUTH_MODE_BUILTIN
    return _normalize_mode(data.get("authMode"))


def is_reverse_proxy_mode() -> bool:
    return auth_mode() == _AUTH_MODE_REVERSE_PROXY


def _resolve_password() -> str:
    env_password = os.getenv(_PASSWORD_ENV)
    if env_password and env_password.strip():
        return env_password.strip()
    try:
        data = settings_service.load_settings()
    except Exception:
        return ""
    value = data.get("authPassword", "")
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _resolve_username() -> str:
    env_username = os.getenv(_USERNAME_ENV)
    if env_username and env_username.strip():
        return env_username.strip()
    try:
        data = settings_service.load_settings()
    except Exception:
        return ""
    value = data.get("authUsername", "")
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def is_enabled() -> bool:
    if is_reverse_proxy_mode():
        return False
    password = _resolve_password()
    return bool(password)


def username_required() -> bool:
    """Return whether a password-only deployment still needs a username."""
    return is_enabled() and not bool(_resolve_username())


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
        normalized = raw.strip().lower()
        if normalized and normalized != "auto":
            return normalized in {"1", "true", "yes", "on"}
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


def verify_password(candidate: Optional[str]) -> bool:
    if not candidate or not is_enabled():
        return False
    expected = _resolve_password()
    if not expected:
        return False
    return secrets.compare_digest(candidate, expected)


def verify_credentials(candidate_username: Optional[str], candidate_password: Optional[str]) -> bool:
    """Verify credentials and migrate password-only installs on their first UI login.

    A missing username remains accepted while no username is configured so older API
    clients that only send a password keep working. The new UI always supplies a
    username, which is claimed after the existing password has been verified.
    """
    if not verify_password(candidate_password):
        return False

    expected_username = _resolve_username()
    if expected_username:
        if candidate_username is None:
            return False
        return secrets.compare_digest(candidate_username.strip(), expected_username)

    if candidate_username is None:
        return True

    username = candidate_username.strip()
    if not username or len(username) > _MAX_USERNAME_LENGTH:
        return False

    claimed_username = settings_service.claim_auth_username(username)
    return secrets.compare_digest(username, claimed_username)


def _credentials_fingerprint() -> str:
    """Return a digest that changes whenever the login mode or credentials do.

    Sessions remember the fingerprint they were created under, so changing
    the username, password or auth mode signs out every existing session.
    """
    material = json.dumps([auth_mode(), _resolve_username(), _resolve_password()])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    expiry = time.time() + token_ttl_seconds()
    fingerprint = _credentials_fingerprint()
    with _LOCK:
        _SESSIONS[token] = (expiry, fingerprint)
    return token


def validate_session(token: Optional[str]) -> bool:
    if not token:
        return False
    now = time.time()
    fingerprint = _credentials_fingerprint()
    with _LOCK:
        session = _SESSIONS.get(token)
        if not session or session[0] < now or session[1] != fingerprint:
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
        expired = [token for token, (expiry, _) in _SESSIONS.items() if expiry < now]
        for token in expired:
            _SESSIONS.pop(token, None)


def _recent_failures(client: str, now: float) -> list[float]:
    cutoff = now - _LOGIN_WINDOW_SECONDS
    recent = [stamp for stamp in _FAILED_LOGINS.get(client, []) if stamp > cutoff]
    if recent:
        _FAILED_LOGINS[client] = recent
    else:
        _FAILED_LOGINS.pop(client, None)
    return recent


def login_retry_after(client: str) -> int:
    """Return seconds until *client* may try again, or 0 if it may now."""
    now = time.time()
    with _LOCK:
        recent = _recent_failures(client, now)
        if len(recent) < _LOGIN_MAX_FAILURES:
            return 0
        return max(1, int(recent[0] + _LOGIN_WINDOW_SECONDS - now) + 1)


def record_login_failure(client: str) -> None:
    now = time.time()
    with _LOCK:
        if client not in _FAILED_LOGINS and len(_FAILED_LOGINS) >= _LOGIN_MAX_TRACKED:
            for stale in list(_FAILED_LOGINS):
                _recent_failures(stale, now)
            if len(_FAILED_LOGINS) >= _LOGIN_MAX_TRACKED:
                oldest = min(_FAILED_LOGINS, key=lambda key: _FAILED_LOGINS[key][-1])
                _FAILED_LOGINS.pop(oldest, None)
        _FAILED_LOGINS.setdefault(client, []).append(now)


def clear_login_failures(client: str) -> None:
    with _LOCK:
        _FAILED_LOGINS.pop(client, None)
