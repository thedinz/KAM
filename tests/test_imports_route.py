import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _setup_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "TV Shows"
    folder = "Example Show (2024)"
    target_dir = assets_root / library / folder
    target_dir.mkdir(parents=True)

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [],
        }
    )

    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    library_mappings.clear_cache()

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    imports_module = importlib.reload(importlib.import_module("app.routers.imports"))

    return imports_module, target_dir, library, folder


def test_import_title_card_uses_kometa_episode_filename(tmp_path, monkeypatch):
    imports_module, target_dir, library, folder = _setup_env(tmp_path, monkeypatch)
    captured = {}

    def fake_download_result(path, src):
        captured["path"] = path
        captured["src"] = src
        return {"ok": True, "path": path, "src": src, "error": None, "replaced": False}

    monkeypatch.setattr(imports_module, "_download_result", fake_download_result)

    response = imports_module.import_title_card_post(
        library=library,
        folderName=folder,
        season="2",
        episode="3",
        ratingKey="301",
        url="http://plex.test/library/metadata/301/thumb?X-Plex-Token=token",
    )

    expected_path = target_dir / "S02E03.jpg"
    assert response["ok"] is True
    assert captured["path"] == str(expected_path)
    assert response["path"] == str(expected_path)
