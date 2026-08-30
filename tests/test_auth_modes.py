import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def auth_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("KAM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.delenv("KAM_AUTH_MODE", raising=False)
    monkeypatch.delenv("KAM_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("KAM_AUTH_PASSWORD", raising=False)

    settings_service = importlib.reload(importlib.import_module("app.services.settings"))
    auth_service = importlib.reload(importlib.import_module("app.services.auth"))
    auth_router = importlib.reload(importlib.import_module("app.routers.auth"))

    return settings_service, auth_service, auth_router


def test_builtin_auth_mode_uses_saved_password(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    settings_service.save_settings(
        {"authMode": "builtin", "authPassword": "local-secret"}
    )

    request = SimpleNamespace(cookies={})
    status = auth_router.auth_status(request)

    assert auth_service.auth_mode() == "builtin"
    assert auth_service.is_enabled() is True
    assert auth_service.verify_password("local-secret") is True
    assert status == {
        "mode": "builtin",
        "enabled": True,
        "authenticated": False,
        "usernameRequired": True,
    }


def test_reverse_proxy_mode_disables_builtin_login(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    settings_service.save_settings(
        {"authMode": "reverse_proxy", "authPassword": "local-secret"}
    )

    request = SimpleNamespace(cookies={})
    status = auth_router.auth_status(request)

    assert auth_service.auth_mode() == "reverse_proxy"
    assert auth_service.is_reverse_proxy_mode() is True
    assert auth_service.is_enabled() is False
    assert auth_service.verify_password("local-secret") is False
    assert status == {
        "mode": "reverse_proxy",
        "enabled": False,
        "authenticated": True,
        "usernameRequired": False,
    }

    with pytest.raises(HTTPException) as exc:
        auth_router.auth_login(
            auth_router.LoginPayload(password="local-secret"),
            request,
            Response(),
        )
    assert exc.value.status_code == 404


def test_auth_mode_env_overrides_saved_mode(auth_modules, monkeypatch):
    settings_service, auth_service, _ = auth_modules
    settings_service.save_settings(
        {"authMode": "builtin", "authPassword": "local-secret"}
    )

    monkeypatch.setenv("KAM_AUTH_MODE", "reverse-proxy")

    assert auth_service.auth_mode() == "reverse_proxy"
    assert auth_service.is_enabled() is False


def test_auth_username_env_overrides_saved_username(auth_modules, monkeypatch):
    settings_service, auth_service, _ = auth_modules
    settings_service.save_settings(
        {
            "authMode": "builtin",
            "authUsername": "saved-admin",
            "authPassword": "local-secret",
        }
    )
    monkeypatch.setenv("KAM_AUTH_USERNAME", "env-admin")

    assert auth_service.verify_credentials("env-admin", "local-secret") is True
    assert auth_service.verify_credentials("saved-admin", "local-secret") is False


def test_configured_username_and_password_are_both_required(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    settings_service.save_settings(
        {
            "authMode": "builtin",
            "authUsername": "admin",
            "authPassword": "local-secret",
        }
    )

    assert auth_service.username_required() is False
    assert auth_service.verify_credentials("admin", "local-secret") is True
    assert auth_service.verify_credentials("other", "local-secret") is False
    assert auth_service.verify_credentials(None, "local-secret") is False

    request = SimpleNamespace(cookies={})
    assert auth_router.auth_status(request)["usernameRequired"] is False


def test_first_legacy_ui_login_claims_username(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    settings_service.save_settings(
        {"authMode": "builtin", "authPassword": "local-secret"}
    )
    request = SimpleNamespace(
        cookies={},
        headers={},
        url=SimpleNamespace(scheme="http"),
    )

    response = Response()
    result = auth_router.auth_login(
        auth_router.LoginPayload(username=" admin ", password="local-secret"),
        request,
        response,
    )

    assert result == {"ok": True, "usernameRequired": False}
    assert settings_service.load_settings()["authUsername"] == "admin"
    assert auth_service.verify_credentials("admin", "local-secret") is True


def test_legacy_password_only_api_login_remains_compatible(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    settings_service.save_settings(
        {"authMode": "builtin", "authPassword": "local-secret"}
    )
    request = SimpleNamespace(
        cookies={},
        headers={},
        url=SimpleNamespace(scheme="http"),
    )

    result = auth_router.auth_login(
        auth_router.LoginPayload(password="local-secret"),
        request,
        Response(),
    )

    assert result == {"ok": True, "usernameRequired": True}
    assert settings_service.load_settings()["authUsername"] == ""


def test_blank_cookie_secure_env_keeps_auto_detection(auth_modules, monkeypatch):
    _, auth_service, _ = auth_modules
    request = SimpleNamespace(
        headers={"x-forwarded-proto": "https"},
        url=SimpleNamespace(scheme="http"),
    )

    monkeypatch.setenv("KAM_AUTH_COOKIE_SECURE", "")
    assert auth_service.cookie_secure(request) is True

    monkeypatch.setenv("KAM_AUTH_COOKIE_SECURE", "auto")
    assert auth_service.cookie_secure(request) is True

    monkeypatch.setenv("KAM_AUTH_COOKIE_SECURE", "false")
    assert auth_service.cookie_secure(request) is False
