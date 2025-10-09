import importlib
import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture
def items_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    library_path = assets_root / library
    folder = library_path / "My Film (2023)"
    folder.mkdir(parents=True)
    (folder / "poster.jpg").write_bytes(b"poster")

    overrides_path = tmp_path / "overrides.json"

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(overrides_path))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": library,
                    "assetPath": str(library_path),
                    "collectionsPath": None,
                }
            ],
        }
    )
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))
    plex_settings.clear_cache()

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    folder_overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    folder_overrides.set_storage_path(str(overrides_path))

    items_router = importlib.reload(importlib.import_module("app.routers.items"))

    monkeypatch.setattr(items_router, "_section_key_by_name", lambda _: "1")

    def fake_plex_list(path, params=None):
        if params and params.get("type") == 1:
            return [
                {
                    "title": "My Film",
                    "year": 2023,
                    "ratingKey": "11",
                    "type": "movie",
                    "thumb": "/thumb",
                },
                {
                    "title": "Needs Assets",
                    "year": 2020,
                    "ratingKey": "22",
                    "type": "movie",
                    "thumb": "/thumb2?width=500&height=750",
                },
            ]
        return []

    monkeypatch.setattr(items_router, "_plex_list", fake_plex_list)

    def _call(**kwargs):
        params = {
            "library": library,
            "page": 1,
            "page_size": 60,
            "query": None,
            "not_ready_only": False,
        }
        params.update(kwargs)
        return items_router.list_items(**params)

    return SimpleNamespace(
        call=_call,
        folder_overrides=folder_overrides,
        folder=folder,
    )


def test_items_route_prefers_override(items_env):
    items_env.folder_overrides.set_override("Movies", "11", items_env.folder.name)

    data = items_env.call()
    items = {it["ratingKey"]: it for it in data["items"]}

    overridden = items["11"]
    assert overridden["folderName"] == items_env.folder.name
    assert overridden["assetReady"] is True
    assert overridden["posterUrl"].startswith("/fileproxy")
    assert overridden["posterUrlLocal"].startswith("/fileproxy")
    assert overridden["posterUrlPlex"].startswith("http://plex.test")


def test_items_route_reports_not_ready_count_and_filters(items_env):
    data = items_env.call()

    assert data["not_ready_count"] == 1

    by_key = {it["ratingKey"]: it for it in data["items"]}
    assert by_key["22"]["assetReady"] is False
    assert by_key["22"]["posterUrl"].startswith("http://plex.test")
    assert by_key["22"]["posterUrlPlex"].startswith("http://plex.test")
    assert "?" in by_key["22"]["posterUrlPlex"]
    assert "X-Plex-Token=token" in by_key["22"]["posterUrlPlex"].split("?")[-1]

    filtered = items_env.call(not_ready_only=True)

    assert filtered["not_ready_count"] == 1
    assert filtered["total_count"] == 1
    assert len(filtered["items"]) == 1
    assert filtered["items"][0]["ratingKey"] == "22"
