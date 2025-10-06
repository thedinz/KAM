import importlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MODULES_TO_RELOAD = [
    "app.services.settings",
    "app.services.library_mappings",
    "app.services.plex_settings",
    "app.config",
]


@pytest.fixture
def reload_config(monkeypatch, tmp_path):
    """Provide a helper that reloads config-related modules with a clean env."""

    monkeypatch.setenv("KAM_SETTINGS_PATH", str(tmp_path / "settings.json"))

    def _reload() -> object:
        module = None
        for name in MODULES_TO_RELOAD:
            module = importlib.import_module(name)
            module = importlib.reload(module)
        assert module is not None
        return sys.modules["app.config"]

    try:
        yield _reload
    finally:
        for name in MODULES_TO_RELOAD:
            module = importlib.import_module(name)
            importlib.reload(module)


def test_config_errors_ignore_missing_library_mappings(reload_config, monkeypatch):
    monkeypatch.delenv("LIBRARIES", raising=False)
    monkeypatch.delenv("COLLECTIONS_ROOT", raising=False)
    monkeypatch.setenv("PLEX_URL", "http://plex.example:32400")
    monkeypatch.setenv("PLEX_TOKEN", "example-token")

    config_module = reload_config()
    errors = config_module.get_config_errors()

    assert "Missing LIBRARIES" not in errors


def test_config_errors_require_plex_credentials(reload_config, monkeypatch):
    monkeypatch.delenv("PLEX_URL", raising=False)
    monkeypatch.delenv("PLEX_TOKEN", raising=False)

    config_module = reload_config()
    errors = config_module.get_config_errors()

    assert "Missing PLEX_URL" in errors
    assert "Missing PLEX_TOKEN" in errors
