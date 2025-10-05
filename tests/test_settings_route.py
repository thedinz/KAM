import importlib
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def settings_modules(tmp_path, monkeypatch):
    settings_path = tmp_path / "state" / "settings.json"
    monkeypatch.setenv("KAM_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("PLEX_URL", "http://plex.example:32400")
    monkeypatch.setenv("PLEX_TOKEN", "initial-token")
    monkeypatch.setenv(
        "LIBRARIES",
        "Movies:/assets/Movies,TV Shows:/assets/TV Shows",
    )
    monkeypatch.setenv("COLLECTIONS_ROOT", " /assets/Collections ")

    library_module = importlib.reload(
        importlib.import_module("app.services.library_mappings")
    )
    settings_service = importlib.reload(importlib.import_module("app.services.settings"))
    settings_router = importlib.reload(importlib.import_module("app.routers.settings"))

    return settings_router, settings_service, settings_path, library_module


def test_get_settings_returns_defaults(settings_modules):
    router, _, _, _ = settings_modules

    resp = router.get_settings()
    assert resp.model_dump() == {
        "theme": "dark",
        "plexUrl": "http://plex.example:32400",
        "plexToken": "initial-token",
        "libraryMappings": [
            {
                "library": "Movies",
                "assetPath": "/assets/Movies",
                "collectionsPath": "/assets/Collections",
            },
            {
                "library": "TV Shows",
                "assetPath": "/assets/TV Shows",
                "collectionsPath": "/assets/Collections",
            },
        ],
    }


def test_put_settings_updates_file(settings_modules):
    router, service, path, _ = settings_modules

    payload = router.SettingsPayload(
        theme="light",
        plexUrl="http://plex.changed",
        plexToken="  updated-token  ",
        libraryMappings=[
            {
                "library": "Movies",
                "assetPath": "/assets/New Movies/",
                "collectionsPath": "",
            },
            {
                "library": "TV Shows",
                "assetPath": " /assets/TV Shows ",
                "collectionsPath": "/assets/Collections/Shows",
            },
        ],
    )
    resp = router.update_settings(payload)
    assert resp.model_dump() == {
        "theme": "light",
        "plexUrl": "http://plex.changed",
        "plexToken": "updated-token",
        "libraryMappings": [
            {
                "library": "Movies",
                "assetPath": "/assets/New Movies",
                "collectionsPath": None,
            },
            {
                "library": "TV Shows",
                "assetPath": "/assets/TV Shows",
                "collectionsPath": "/assets/Collections/Shows",
            },
        ],
    }

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == {
        "theme": "light",
        "plexUrl": "http://plex.changed",
        "plexToken": "updated-token",
        "libraryMappings": [
            {
                "library": "Movies",
                "assetPath": "/assets/New Movies",
                "collectionsPath": None,
            },
            {
                "library": "TV Shows",
                "assetPath": "/assets/TV Shows",
                "collectionsPath": "/assets/Collections/Shows",
            },
        ],
    }

    # Ensure the service merges persisted values with defaults
    assert service.load_settings() == {
        "theme": "light",
        "plexUrl": "http://plex.changed",
        "plexToken": "updated-token",
        "libraryMappings": [
            {
                "library": "Movies",
                "assetPath": "/assets/New Movies",
                "collectionsPath": None,
            },
            {
                "library": "TV Shows",
                "assetPath": "/assets/TV Shows",
                "collectionsPath": "/assets/Collections/Shows",
            },
        ],
    }


def test_put_settings_rejects_invalid_theme(settings_modules):
    router, _, _, _ = settings_modules

    with pytest.raises(ValidationError):
        router.SettingsPayload(theme="blue")


def test_put_settings_rejects_invalid_plex_url(settings_modules):
    router, _, _, _ = settings_modules

    with pytest.raises(ValidationError):
        router.SettingsPayload(theme="dark", plexUrl="not-a-url")


def test_put_settings_rejects_invalid_library_mapping(settings_modules):
    router, _, _, _ = settings_modules

    with pytest.raises(ValidationError):
        router.SettingsPayload(
            theme="dark",
            libraryMappings=[{"library": "", "assetPath": ""}],
        )


def test_save_settings_sanitizes_library_mappings(settings_modules):
    _, service, path, _ = settings_modules

    stored = service.save_settings(
        {
            "libraryMappings": [
                {
                    "library": " Movies ",
                    "assetPath": "/assets/Movies/",
                    "collectionsPath": "  ",
                },
                {
                    "library": "Movies",
                    "assetPath": "/assets/Movies Updated",
                    "collectionsPath": "/collections/movies",
                },
                {"library": "", "assetPath": "/invalid"},
            ]
        }
    )

    assert stored["libraryMappings"] == [
        {
            "library": "Movies",
            "assetPath": "/assets/Movies Updated",
            "collectionsPath": "/collections/movies",
        }
    ]

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["libraryMappings"] == [
        {
            "library": "Movies",
            "assetPath": "/assets/Movies Updated",
            "collectionsPath": "/collections/movies",
        }
    ]


def test_save_settings_clears_library_mapping_cache(settings_modules):
    _, service, _, library_module = settings_modules

    library_module.set_cached_mappings(
        [{"library": "Movies", "assetPath": "/assets/Movies", "collectionsPath": None}]
    )
    assert library_module.get_cached_mappings() is not None

    service.save_settings({})

    assert library_module.get_cached_mappings() is None
