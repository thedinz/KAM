import importlib
from pathlib import Path
from types import SimpleNamespace


def test_health_report_checks_saved_paths(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    movie_assets = assets_root / "Movies"
    collections = assets_root / "Collections"
    movie_assets.mkdir(parents=True)
    collections.mkdir(parents=True)

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("COLLECTIONS_ROOT", str(collections))

    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    settings_service = importlib.reload(importlib.import_module("app.services.settings"))
    settings_service.set_settings_path(str(tmp_path / "config" / "settings.json"))
    settings_service.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(movie_assets),
                    "collectionsPath": str(collections),
                }
            ],
        }
    )
    library_mappings.clear_cache()

    health_service = importlib.reload(importlib.import_module("app.services.health"))
    monkeypatch.setattr(health_service.plex_service, "get_plex", lambda: SimpleNamespace())

    report = health_service.get_health_report()

    assert report["ok"] is True
    assert {check["key"]: check["status"] for check in report["checks"]} == {
        "plex": "ok",
        "assets-root": "ok",
        "collections": "ok",
        "config": "ok",
    }
    assert Path(report["assetMappings"][0]["path"]) == movie_assets
    assert report["assetMappings"][0]["status"] == "ok"
    assert Path(report["collectionPaths"][0]["path"]) == collections
