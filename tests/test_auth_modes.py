import importlib
import json
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
        "setupRequired": False,
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
        "setupRequired": False,
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


def _login_request(host="198.51.100.7"):
    return SimpleNamespace(
        cookies={},
        headers={},
        url=SimpleNamespace(scheme="http"),
        client=SimpleNamespace(host=host),
    )


def test_changing_the_password_signs_out_existing_sessions(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    settings_service.save_settings(
        {"authMode": "builtin", "authUsername": "admin", "authPassword": "old-secret"}
    )
    token = auth_service.create_session()
    assert auth_service.validate_session(token) is True

    settings_service.save_settings(
        {"authMode": "builtin", "authUsername": "admin", "authPassword": "new-secret"}
    )

    assert auth_service.validate_session(token) is False


def test_repeated_failed_logins_are_throttled(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    settings_service.save_settings(
        {"authMode": "builtin", "authUsername": "admin", "authPassword": "local-secret"}
    )
    payload = auth_router.LoginPayload(username="admin", password="wrong")

    for _ in range(auth_service._LOGIN_MAX_FAILURES):
        with pytest.raises(HTTPException) as exc:
            auth_router.auth_login(payload, _login_request(), Response())
        assert exc.value.status_code == 401

    correct = auth_router.LoginPayload(username="admin", password="local-secret")
    with pytest.raises(HTTPException) as exc:
        auth_router.auth_login(correct, _login_request(), Response())
    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) > 0

    # Other addresses are not affected.
    result = auth_router.auth_login(correct, _login_request("198.51.100.8"), Response())
    assert result["ok"] is True


def test_fresh_install_requires_setup_before_anything_else(auth_modules):
    _, auth_service, auth_router = auth_modules

    assert auth_service.login_required() is True
    assert auth_service.setup_required() is True
    assert auth_service.is_enabled() is False
    assert auth_router.auth_status(_login_request()) == {
        "mode": "builtin",
        "enabled": True,
        "authenticated": False,
        "usernameRequired": False,
        "setupRequired": True,
    }

    with pytest.raises(HTTPException) as exc:
        auth_router.auth_login(
            auth_router.LoginPayload(username="admin", password="anything"),
            _login_request(),
            Response(),
        )
    assert exc.value.status_code == 409


def test_setup_code_creates_the_first_login(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    code = auth_service.setup_code()
    assert code == auth_service.setup_code()

    response = Response()
    result = auth_router.auth_setup(
        # The code is accepted without dashes and in lower case.
        auth_router.SetupPayload(
            code=code.replace("-", "").lower(), username=" admin ", password="long-secret"
        ),
        _login_request(),
        response,
    )

    assert result == {"ok": True}
    assert auth_service.cookie_name() in response.headers["set-cookie"]
    stored = settings_service.load_settings()
    assert (stored["authMode"], stored["authUsername"]) == ("builtin", "admin")
    assert stored["authPasswordHash"].startswith("scrypt$")
    assert "long-secret" not in json.dumps(stored)
    assert auth_service.setup_required() is False
    assert auth_service.verify_credentials("admin", "long-secret") is True

    with pytest.raises(HTTPException) as exc:
        auth_router.auth_setup(
            auth_router.SetupPayload(code=code, username="other", password="other-secret"),
            _login_request(),
            Response(),
        )
    assert exc.value.status_code == 409


def test_setup_rejects_a_wrong_code_and_short_passwords(auth_modules):
    settings_service, auth_service, auth_router = auth_modules
    code = auth_service.setup_code()

    with pytest.raises(HTTPException) as exc:
        auth_router.auth_setup(
            auth_router.SetupPayload(code="AAAA-BBBB-CCCC", username="admin", password="long-secret"),
            _login_request(),
            Response(),
        )
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        auth_router.auth_setup(
            auth_router.SetupPayload(code=code, username="admin", password="short"),
            _login_request(),
            Response(),
        )
    assert exc.value.status_code == 422
    assert settings_service.load_settings()["authPasswordHash"] == ""
    assert auth_service.setup_required() is True


def test_wrong_setup_codes_are_throttled(auth_modules):
    _, auth_service, auth_router = auth_modules
    code = auth_service.setup_code()
    wrong = auth_router.SetupPayload(code="AAAA-BBBB-CCCC", username="admin", password="long-secret")

    for _ in range(auth_service._LOGIN_MAX_FAILURES):
        with pytest.raises(HTTPException) as exc:
            auth_router.auth_setup(wrong, _login_request(), Response())
        assert exc.value.status_code == 401

    right = auth_router.SetupPayload(code=code, username="admin", password="long-secret")
    with pytest.raises(HTTPException) as exc:
        auth_router.auth_setup(right, _login_request(), Response())
    assert exc.value.status_code == 429


def test_none_mode_runs_without_a_login_only_from_the_environment(auth_modules, monkeypatch):
    settings_service, auth_service, auth_router = auth_modules

    # A saved "none" is ignored, so the setting can't be switched off from the UI.
    settings_service.save_settings({"authMode": "none"})
    assert auth_service.login_required() is True

    monkeypatch.setenv("KAM_AUTH_MODE", "none")
    assert auth_service.auth_mode() == "none"
    assert auth_service.login_required() is False
    assert auth_service.setup_required() is False
    assert auth_router.auth_status(_login_request())["authenticated"] is True


def test_password_env_skips_setup(auth_modules, monkeypatch):
    _, auth_service, _ = auth_modules
    monkeypatch.setenv("KAM_AUTH_PASSWORD", "env-secret")

    assert auth_service.setup_required() is False
    assert auth_service.is_enabled() is True


def test_login_works_with_a_password_saved_by_older_versions(auth_modules, tmp_path):
    settings_service, auth_service, _ = auth_modules
    (tmp_path / "settings.json").write_text(
        json.dumps({"authMode": "builtin", "authUsername": "admin", "authPassword": "old-plain"}),
        encoding="utf-8",
    )

    assert auth_service.verify_credentials("admin", "old-plain") is True
    assert auth_service.verify_credentials("admin", "wrong") is False
    token = auth_service.create_session()
    # Later loads reuse the stored hash, so sessions stay valid.
    assert auth_service.validate_session(token) is True
    assert "old-plain" not in (tmp_path / "settings.json").read_text(encoding="utf-8")
