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
    monkeypatch.setenv("PLEX_URL", "http://plex.test")
    monkeypatch.setenv("PLEX_TOKEN", "token")

    from app import config

    monkeypatch.setattr(config, "LIBRARY_MAPPINGS", {library: str(library_path)})
    monkeypatch.setattr(config, "COLLECTIONS_ROOT", "")

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
                }
            ]
        return []

    monkeypatch.setattr(items_router, "_plex_list", fake_plex_list)

    def _call(**kwargs):
        params = {"library": library, "page": 1, "page_size": 60, "query": None}
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
    assert data["items"][0]["folderName"] == items_env.folder.name
    assert data["items"][0]["assetReady"] is True
    assert data["items"][0]["posterUrl"].startswith("/fileproxy")
