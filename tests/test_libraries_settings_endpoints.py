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
        },
    )

    resp = client.get("/api/settings/libraries")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {
            "name": "Movies",
            "type": "movie",
            "key": "1",
            "assetPath": "/assets/Movies",
            "collectionsPath": "/collections/movies",
        },
        {
            "name": "TV Shows",
            "type": "show",
            "key": "2",
            "assetPath": None,
            "collectionsPath": None,
        },
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
    (assets_root / "Movies").mkdir()
    loose = assets_root / "LooseAssets"
    loose.mkdir()
    (loose / "Clips").mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    from app import config

    monkeypatch.setattr(config, "LIBRARY_MAPPINGS", {"Movies": str(assets_root / "Movies")})
    monkeypatch.setattr(config, "COLLECTIONS_ROOT", str(assets_root / "Collections"))

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
