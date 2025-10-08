import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_clearing_settings_resets_cached_values(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"

    with monkeypatch.context() as patch:
        patch.setenv("KAM_SETTINGS_PATH", str(settings_path))

        settings_service = importlib.reload(
            importlib.import_module("app.services.settings")
        )
        plex_settings = importlib.reload(
            importlib.import_module("app.services.plex_settings")
        )

        settings_service.save_settings(
            {"plexUrl": "http://plex.example:32400", "plexToken": "initial-token"}
        )

        cfg = plex_settings.get_plex_config(force_refresh=True)
        assert cfg.url == "http://plex.example:32400"
        assert cfg.token == "initial-token"

        settings_service.save_settings({"plexUrl": "", "plexToken": ""})

        cfg = plex_settings.get_plex_config(force_refresh=True)
        assert cfg.url == ""
        assert cfg.token == ""

    importlib.reload(importlib.import_module("app.services.settings"))
    importlib.reload(importlib.import_module("app.services.plex_settings"))
