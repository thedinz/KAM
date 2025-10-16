import importlib
import os
from pathlib import Path

import pytest


MODULE_NAME = "app.services.settings"


@pytest.fixture
def reload_settings(monkeypatch):
    """Reload the settings module after mutating environment variables."""

    def _reload():
        module = importlib.import_module(MODULE_NAME)
        return importlib.reload(module)

    try:
        yield _reload
    finally:
        module = importlib.import_module(MODULE_NAME)
        importlib.reload(module)


def _clear_env(monkeypatch):
    for key in ("KAM_SETTINGS_PATH", "KAM_STATE_ROOT", "KAM_CONFIG_ROOT"):
        monkeypatch.delenv(key, raising=False)


def test_default_path_prefers_config_directory(monkeypatch, reload_settings):
    _clear_env(monkeypatch)

    monkeypatch.setattr(os.path, "isfile", lambda _: False)

    settings_module = reload_settings()

    assert settings_module._get_storage_path() == Path("/config/settings.json")


def test_existing_legacy_data_file_is_reused(monkeypatch, reload_settings):
    _clear_env(monkeypatch)

    monkeypatch.setattr(
        os.path,
        "isfile",
        lambda candidate: Path(candidate) == Path("/data/settings.json"),
    )

    settings_module = reload_settings()

    assert settings_module._get_storage_path() == Path("/data/settings.json")

