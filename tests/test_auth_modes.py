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
