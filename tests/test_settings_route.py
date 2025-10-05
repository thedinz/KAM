import importlib
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def settings_modules(tmp_path, monkeypatch):
    settings_path = tmp_path / "state" / "settings.json"
    monkeypatch.setenv("KAM_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("PLEX_URL", "http://plex.example:32400")
    monkeypatch.setenv("PLEX_TOKEN", "initial-token")

    settings_service = importlib.reload(importlib.import_module("app.services.settings"))
    settings_router = importlib.reload(importlib.import_module("app.routers.settings"))

    return settings_router, settings_service, settings_path


def test_get_settings_returns_defaults(settings_modules):
    router, _, _ = settings_modules

    resp = router.get_settings()
    assert resp.model_dump() == {
        "theme": "dark",
        "plexUrl": "http://plex.example:32400",
        "plexToken": "initial-token",
    }


def test_put_settings_updates_file(settings_modules):
    router, service, path = settings_modules

    payload = router.SettingsPayload(
        theme="light",
        plexUrl="http://plex.changed",  # domain only is fine for HttpUrl
        plexToken="  updated-token  ",
    )
    resp = router.update_settings(payload)
    assert resp.model_dump() == {
        "theme": "light",
        "plexUrl": "http://plex.changed",
        "plexToken": "updated-token",
    }

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == {
        "theme": "light",
        "plexUrl": "http://plex.changed",
        "plexToken": "updated-token",
    }

    # Ensure the service merges persisted values with defaults
    assert service.load_settings() == {
        "theme": "light",
        "plexUrl": "http://plex.changed",
        "plexToken": "updated-token",
    }


def test_put_settings_rejects_invalid_theme(settings_modules):
    router, _, _ = settings_modules

    with pytest.raises(ValidationError):
        router.SettingsPayload(theme="blue")


def test_put_settings_rejects_invalid_plex_url(settings_modules):
    router, _, _ = settings_modules

    with pytest.raises(ValidationError):
        router.SettingsPayload(theme="dark", plexUrl="not-a-url")
