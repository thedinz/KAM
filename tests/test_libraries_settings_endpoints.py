import importlib
from dataclasses import dataclass
from typing import List

import pytest

pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class _DummySection:
    title: str
    type: str
    key: str


class _DummyLibrary:
    def __init__(self, sections: List[_DummySection]):
        self._sections = sections

    def sections(self) -> List[_DummySection]:
        return list(self._sections)


class _DummyPlex:
    def __init__(self, sections: List[_DummySection]):
        self.library = _DummyLibrary(sections)


def _create_libraries_client(
    monkeypatch: pytest.MonkeyPatch,
    load_settings_payload: dict,
    sections: List[_DummySection] | None = None,
    plex_factory=None,
) -> TestClient:
    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    monkeypatch.setattr(settings_module, "load_settings", lambda: load_settings_payload)

    plex_settings_module = importlib.reload(importlib.import_module("app.services.plex_settings"))
    plex_settings_module.clear_cache()

    default_sections = sections or [
        _DummySection("Movies", "movie", "1"),
        _DummySection("TV Shows", "show", "2"),
    ]

    plex_module = importlib.reload(importlib.import_module("app.services.plex"))
    if plex_factory is None:
        plex_factory = lambda: _DummyPlex(default_sections)
    monkeypatch.setattr(plex_module, "get_plex", plex_factory)

    router_module = importlib.reload(importlib.import_module("app.routers.libraries"))

    app = FastAPI()
    app.include_router(router_module.router)

    return TestClient(app)


def test_settings_libraries_endpoint_lists_sections(monkeypatch):
    client = _create_libraries_client(
        monkeypatch,
        {
            "theme": "dark",
            "plexUrl": "http://plex.example:32400",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": "/assets/Movies",
                    "collectionsPath": "/collections/movies",
                }
            ],
        },
        sections=[
            _DummySection("TV Shows", "show", "2"),
            _DummySection("Documentaries", "show", "3"),
            _DummySection("Movies", "movie", "1"),
            _DummySection("Music", "artist", "4"),
        ],
    )

    resp = client.get("/api/settings/libraries")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {
            "name": "Documentaries",
            "type": "show",
            "key": "3",
            "assetPath": None,
            "collectionsPath": None,
            "collectionAssetPaths": [],
        },
        {
            "name": "Movies",
            "type": "movie",
            "key": "1",
            "assetPath": "/assets/Movies",
            "collectionsPath": "/collections/movies",
            "collectionAssetPaths": [],
        },
        {
            "name": "TV Shows",
            "type": "show",
            "key": "2",
            "assetPath": None,
            "collectionsPath": None,
            "collectionAssetPaths": [],
        },
    ]

    

def test_settings_libraries_endpoint_omits_music_sections(monkeypatch):
    client = _create_libraries_client(
        monkeypatch,
        {
            "theme": "dark",
            "plexUrl": "http://plex.example:32400",
            "plexToken": "token",
            "libraryMappings": [],
        },
        sections=[
            _DummySection("Music", "artist", "4"),
            _DummySection("Concerts", "audio", "5"),
            _DummySection("Movies", "movie", "1"),
        ],
    )

    resp = client.get("/api/settings/libraries")
    assert resp.status_code == 200
    data = resp.json()

    assert data == [
        {
            "name": "Movies",
            "type": "movie",
            "key": "1",
            "assetPath": None,
            "collectionsPath": None,
            "collectionAssetPaths": [],
        }
    ]


def test_update_library_mappings_endpoint(monkeypatch):
    settings_module = importlib.reload(importlib.import_module("app.services.settings"))

    captured = {}

    def _save_library_mappings(payload):
        captured["payload"] = payload
        return {
            "theme": "dark",
            "plexUrl": "http://plex.example",
            "plexToken": "token",
            "libraryMappings": payload,
        }

    monkeypatch.setattr(settings_module, "save_library_mappings", _save_library_mappings)

    router_module = importlib.reload(importlib.import_module("app.routers.settings"))

    app = FastAPI()
    app.include_router(router_module.router)

    client = TestClient(app)

    resp = client.put(
        "/api/settings/library-mappings",
        json={
            "libraryMappings": [
                {
                    "library": " Movies ",
                    "assetPath": " /assets/Movies ",
                    "collectionsPath": "",
                },
                {
                    "library": "Movies",
                    "assetPath": "/assets/Movies",
                    "collectionsPath": None,
                },
            ]
        },
    )

    assert resp.status_code == 200
    assert resp.json() == [
        {
            "library": "Movies",
            "assetPath": "/assets/Movies",
            "collectionsPath": None,
        }
    ]

    assert captured["payload"] == [
        {
            "library": "Movies",
            "assetPath": "/assets/Movies",
            "collectionsPath": None,
        }
    ]


def test_settings_libraries_endpoint_handles_empty_mappings(monkeypatch):
    client = _create_libraries_client(
        monkeypatch,
        {
            "theme": "dark",
            "plexUrl": "http://plex.example:32400",
            "plexToken": "token",
            "libraryMappings": [],
        },
        sections=[
            _DummySection("TV Shows", "show", "2"),
            _DummySection("Movies", "movie", "1"),
        ],
    )

    resp = client.get("/api/settings/libraries")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {
            "name": "Movies",
            "type": "movie",
            "key": "1",
            "assetPath": None,
            "collectionsPath": None,
        },
        {
            "name": "TV Shows",
            "type": "show",
            "key": "2",
            "assetPath": None,
            "collectionsPath": None,
        },
    ]


def test_settings_libraries_endpoint_returns_empty_without_credentials(monkeypatch):
    calls = {"count": 0}

    def _should_not_run():
        calls["count"] += 1
        raise AssertionError("get_plex should not be called when credentials are missing")

    client = _create_libraries_client(
        monkeypatch,
        {
            "theme": "dark",
            "plexUrl": "",
            "plexToken": "",
            "libraryMappings": [],
        },
        sections=[],
        plex_factory=_should_not_run,
    )

    resp = client.get("/api/settings/libraries")
    assert resp.status_code == 200
    assert resp.json() == []
    assert calls["count"] == 0


def test_asset_folders_unmapped_library(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    assets_root.mkdir()
    movies_dir = assets_root / "Movies"
    movies_dir.mkdir()
    loose = assets_root / "LooseAssets"
    loose.mkdir()
    (loose / "Clips").mkdir()
    collections_dir = assets_root / "Collections"
    collections_dir.mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(movies_dir),
                    "collectionsPath": str(collections_dir),
                }
            ]
        }
    )

    assets_router = importlib.reload(importlib.import_module("app.routers.assets"))

    app = FastAPI()
    app.include_router(assets_router.router)

    client = TestClient(app)

    resp = client.get("/api/asset-folders", params={"library": "Documentaries"})
    assert resp.status_code == 200
    data = resp.json()
    names = {item["name"] for item in data["items"]}
    assert "LooseAssets" in names
    assert "Movies" in names

    nested = client.get(
        "/api/asset-folders",
        params={"library": "Documentaries", "parent": "LooseAssets"},
    )
    assert nested.status_code == 200
    nested_data = nested.json()
    nested_names = {item["name"] for item in nested_data["items"]}
    assert "Clips" in nested_names

    invalid = client.get(
        "/api/asset-folders", params={"library": "Documentaries", "parent": "../"}
    )
    assert invalid.status_code == 400


def test_asset_folders_settings_mode_allows_assets_root(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    movies_dir = assets_root / "Movies"
    featured_dir = movies_dir / "Featured"
    posters_dir = featured_dir / "Posters"
    loose_dir = assets_root / "LooseAssets"

    posters_dir.mkdir(parents=True)
    loose_dir.mkdir(parents=True)

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(featured_dir),
                    "collectionsPath": None,
                }
            ]
        }
    )

    library_mappings_module = importlib.reload(
        importlib.import_module("app.services.library_mappings")
    )
    library_mappings_module.clear_cache()

    assets_router = importlib.reload(importlib.import_module("app.routers.assets"))

    app = FastAPI()
    app.include_router(assets_router.router)

    client = TestClient(app)

    # Runtime (non-settings) access remains scoped to the configured mapping
    restricted = client.get("/api/asset-folders", params={"library": "Movies"})
    assert restricted.status_code == 200
    restricted_data = restricted.json()
    restricted_names = {item["name"] for item in restricted_data["items"]}
    assert restricted_names == {"Posters"}

    # Settings browsing exposes the assets root even when a mapping exists
    settings_root = client.get(
        "/api/asset-folders",
        params={"library": "Movies", "settings": "true"},
    )
    assert settings_root.status_code == 200
    root_payload = settings_root.json()
    root_names = {item["name"] for item in root_payload["items"]}
    assert {"Movies", "LooseAssets"}.issubset(root_names)

    # Absolute parent paths resolve relative to the assets root in settings mode
    absolute = client.get(
        "/api/asset-folders",
        params={
            "library": "Movies",
            "settings": "true",
            "parent": str(featured_dir),
        },
    )
    assert absolute.status_code == 200
    absolute_payload = absolute.json()
    assert absolute_payload["parent"] == "Movies/Featured"
    absolute_names = {item["name"] for item in absolute_payload["items"]}
    assert "Posters" in absolute_names

    # Relative navigation within settings mode continues to work
    relative = client.get(
        "/api/asset-folders",
        params={
            "library": "Movies",
            "settings": "true",
            "parent": "Movies",
        },
    )
    assert relative.status_code == 200
    relative_payload = relative.json()
    assert relative_payload["parent"] == "Movies"
    relative_names = {item["name"] for item in relative_payload["items"]}
    assert "Featured" in relative_names

    outside = client.get(
        "/api/asset-folders",
        params={
            "library": "Movies",
            "settings": "true",
            "parent": str(tmp_path),
        },
    )
    assert outside.status_code == 400


def test_asset_folders_allow_beyond_mapping(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    movies_dir = assets_root / "Movies"
    featured_dir = movies_dir / "Featured"
    posters_dir = featured_dir / "Posters"
    loose_dir = assets_root / "LooseAssets"

    posters_dir.mkdir(parents=True)
    loose_dir.mkdir(parents=True)

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(featured_dir),
                    "collectionsPath": None,
                }
            ]
        }
    )

    library_mappings_module = importlib.reload(
        importlib.import_module("app.services.library_mappings")
    )
    library_mappings_module.clear_cache()

    assets_router = importlib.reload(importlib.import_module("app.routers.assets"))

    app = FastAPI()
    app.include_router(assets_router.router)

    client = TestClient(app)

    scoped = client.get(
        "/api/asset-folders",
        params={"library": "Movies", "allowBeyondMapping": "true"},
    )
    assert scoped.status_code == 200
    scoped_payload = scoped.json()
    assert scoped_payload["parent"] == "Movies/Featured"
    scoped_names = {item["name"] for item in scoped_payload["items"]}
    assert scoped_names == {"Posters"}

    ascended = client.get(
        "/api/asset-folders",
        params={
            "library": "Movies",
            "allowBeyondMapping": "true",
            "parent": "Movies",
        },
    )
    assert ascended.status_code == 200
    ascended_payload = ascended.json()
    assert ascended_payload["parent"] == "Movies"
    ascended_names = {item["name"] for item in ascended_payload["items"]}
    assert "Featured" in ascended_names

    root_view = client.get(
        "/api/asset-folders",
        params={
            "library": "Movies",
            "allowBeyondMapping": "true",
            "parent": "",
        },
    )
    assert root_view.status_code == 200
    root_payload = root_view.json()
    assert root_payload["parent"] == ""
    root_names = {item["name"] for item in root_payload["items"]}
    assert {"Movies", "LooseAssets"}.issubset(root_names)


