import importlib
from dataclasses import dataclass
from pathlib import Path
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
    config_summaries: dict | None = None,
) -> TestClient:
    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    monkeypatch.setattr(settings_module, "load_settings", lambda: load_settings_payload)

    kometa_module = importlib.reload(importlib.import_module("app.services.kometa_config"))
    monkeypatch.setattr(
        kometa_module,
        "load_library_summaries",
        lambda path: config_summaries or {},
    )

    plex_settings_module = importlib.reload(importlib.import_module("app.services.plex_settings"))
    plex_settings_module.clear_cache()

    default_sections = sections or [
        _DummySection("Movies", "movie", "1"),
        _DummySection("TV Shows", "show", "2"),
    ]

    plex_module = importlib.reload(importlib.import_module("app.services.plex"))
    monkeypatch.setattr(plex_module, "get_plex", lambda: _DummyPlex(default_sections))

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
            "kometaConfigPath": "/config/config.yml",
        },
        sections=[
            _DummySection("TV Shows", "show", "2"),
            _DummySection("Documentaries", "show", "3"),
            _DummySection("Movies", "movie", "1"),
            _DummySection("Music", "artist", "4"),
        ],
        config_summaries={
            "Movies": {
                "collectionsPaths": ["config/assets/Collections"],
            },
            "Documentaries": {
                "assetPath": "/assets/Documentaries",
                "collectionsPaths": [
                    "config/assets/Docs",
                    "config/assets/Docs",
                    "config/assets/Docs Extras",
                ],
            },
        },
    )

    resp = client.get("/api/settings/libraries")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {
            "name": "Documentaries",
            "type": "show",
            "key": "3",
            "assetPath": "/assets/Documentaries",
            "collectionsPath": "config/assets/Docs",
            "collectionAssetPaths": [
                "config/assets/Docs",
                "config/assets/Docs Extras",
            ],
        },
        {
            "name": "Movies",
            "type": "movie",
            "key": "1",
            "assetPath": "/assets/Movies",
            "collectionsPath": "/collections/movies",
            "collectionAssetPaths": [
                "/collections/movies",
                "config/assets/Collections",
            ],
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
            "kometaConfigPath": "/config/config.yml",
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


def _create_settings_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    kometa_module = importlib.reload(importlib.import_module("app.services.kometa_config"))
    router_module = importlib.reload(importlib.import_module("app.routers.settings"))

    app = FastAPI()
    app.include_router(router_module.router)
    client = TestClient(app)

    # Ensure patched modules remain referenced for the duration of the test
    monkeypatch.setattr("app.routers.settings.settings_service", settings_module)
    monkeypatch.setattr("app.routers.settings.kometa_config_service", kometa_module)
    return client


def test_browse_kometa_config_lists_files(tmp_path, monkeypatch):
    config_root = tmp_path / "config"
    config_root.mkdir()
    primary_config = config_root / "config.yml"
    primary_config.write_text("libraries: {}", encoding="utf-8")
    extra_file = config_root / "extra.yaml"
    extra_file.write_text("", encoding="utf-8")

    monkeypatch.setenv("KOMETA_CONFIG_PATH", str(primary_config))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings({"kometaConfigPath": str(primary_config)})

    client = _create_settings_client(monkeypatch)

    resp = client.get("/api/settings/kometa-config/browse")
    assert resp.status_code == 200
    data = resp.json()
    assert data["root"] == config_root.resolve().as_posix()
    assert data["parent"] == ""

    names = {item["name"]: item for item in data["items"]}
    assert "config.yml" in names
    assert names["config.yml"]["isFile"] is True
    assert names["config.yml"]["path"] == "config.yml"
    assert names["extra.yaml"]["isFile"] is True


def test_browse_kometa_config_supports_navigation_and_search(tmp_path, monkeypatch):
    config_root = tmp_path / "config"
    config_root.mkdir()
    primary_config = config_root / "config.yml"
    primary_config.write_text("libraries: {}", encoding="utf-8")
    nested_dir = config_root / "profiles"
    nested_dir.mkdir()
    nested_file = nested_dir / "alt.yml"
    nested_file.write_text("", encoding="utf-8")

    monkeypatch.setenv("KOMETA_CONFIG_PATH", str(primary_config))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings({"kometaConfigPath": str(primary_config)})

    client = _create_settings_client(monkeypatch)

    # Navigate into a subdirectory
    nested = client.get(
        "/api/settings/kometa-config/browse",
        params={"parent": "profiles"},
    )
    assert nested.status_code == 200
    nested_payload = nested.json()
    assert nested_payload["parent"] == "profiles"
    nested_names = {item["name"] for item in nested_payload["items"]}
    assert "alt.yml" in nested_names

    # Search within the current directory
    search = client.get(
        "/api/settings/kometa-config/browse",
        params={"search": "alt"},
    )
    assert search.status_code == 200
    search_payload = search.json()
    search_names = {item["name"] for item in search_payload["items"]}
    assert "alt.yml" in search_names

    # Ensure the current path highlights the configured file
    current = client.get(
        "/api/settings/kometa-config/browse",
        params={"current": str(nested_file)},
    )
    assert current.status_code == 200
    current_payload = current.json()
    assert current_payload["selection"] == "profiles/alt.yml"
    assert current_payload["parent"] == "profiles"

    invalid = client.get(
        "/api/settings/kometa-config/browse",
        params={"parent": "../"},
    )
    assert invalid.status_code == 400
