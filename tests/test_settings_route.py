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

    library_module = importlib.reload(
        importlib.import_module("app.services.library_mappings")
    )
    settings_service = importlib.reload(importlib.import_module("app.services.settings"))
    settings_router = importlib.reload(importlib.import_module("app.routers.settings"))

    return settings_router, settings_service, settings_path, library_module


def test_get_settings_returns_defaults_when_missing_file(settings_modules):
    router, _, _, _ = settings_modules

    resp = router.get_settings()
    assert resp.model_dump() == {
        "theme": "dark",
        "plexUrl": "",
        "plexToken": "",
        "authMode": "builtin",
        "authPassword": "",
        "libraryMappings": [],
    }


def test_get_settings_returns_stored_values(settings_modules):
    router, service, _, _ = settings_modules

    service.save_settings(
        {
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
    )

    resp = router.get_settings()
    assert resp.model_dump() == {
        "theme": "dark",
        "plexUrl": "http://plex.example:32400",
        "plexToken": "initial-token",
        "authMode": "builtin",
        "authPassword": "",
        "libraryMappings": [
            {
                "library": "Movies",
                "assetPath": "/assets/Movies",
                "collectionsPath": "/assets/Collections",
                "collectionSections": [],
            },
            {
                "library": "TV Shows",
                "assetPath": "/assets/TV Shows",
                "collectionsPath": "/assets/Collections",
                "collectionSections": [],
            },
        ],
    }


def test_get_settings_health_returns_runtime_report(settings_modules, monkeypatch):
    router, _, _, _ = settings_modules
    expected = {
        "ok": True,
        "checks": [{"key": "plex", "status": "ok"}],
        "assetMappings": [],
        "collectionPaths": [],
    }
    monkeypatch.setattr(router.health_service, "get_health_report", lambda: expected)

    assert router.get_settings_health() == expected


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
        "authMode": "builtin",
        "authPassword": "",
        "libraryMappings": [
            {
                "library": "Movies",
                "assetPath": "/assets/New Movies",
                "collectionsPath": None,
                "collectionSections": [],
            },
            {
                "library": "TV Shows",
                "assetPath": "/assets/TV Shows",
                "collectionsPath": "/assets/Collections/Shows",
                "collectionSections": [],
            },
        ],
    }

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == {
        "theme": "light",
        "plexUrl": "http://plex.changed",
        "plexToken": "updated-token",
        "authMode": "builtin",
        "authPassword": "",
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
        "authMode": "builtin",
        "authPassword": "",
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


def test_put_settings_accepts_reverse_proxy_auth_mode(settings_modules):
    router, service, path, _ = settings_modules

    payload = router.SettingsPayload(
        theme="dark",
        authMode="reverse-proxy",
        authPassword="  keep-existing-secret  ",
    )

    resp = router.update_settings(payload)

    assert resp.authMode == "reverse_proxy"
    assert resp.authPassword == "keep-existing-secret"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["authMode"] == "reverse_proxy"
    assert service.load_settings()["authMode"] == "reverse_proxy"


def test_put_settings_rejects_invalid_auth_mode(settings_modules):
    router, _, _, _ = settings_modules

    with pytest.raises(ValidationError):
        router.SettingsPayload(theme="dark", authMode="external")


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


def test_save_library_mappings_updates_only_mapping_data(settings_modules):
    _, service, path, library_module = settings_modules

    service.save_settings(
        {
            "theme": "light",
            "plexUrl": "http://plex.custom", 
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": "/assets/Movies",
                    "collectionsPath": None,
                }
            ],
        }
    )

    library_module.set_cached_mappings(
        [{"library": "Movies", "assetPath": "/assets/Movies", "collectionsPath": None}]
    )

    updated = service.save_library_mappings(
        [
            {
                "library": "Movies",
                "assetPath": "/assets/New Movies",
                "collectionsPath": "",
            },
            {
                "library": "TV Shows",
                "assetPath": "/assets/TV Shows",
                "collectionsPath": "/collections/tv",
            },
        ]
    )

    assert updated["theme"] == "light"
    assert updated["plexUrl"] == "http://plex.custom"
    assert updated["libraryMappings"] == [
        {
            "library": "Movies",
            "assetPath": "/assets/New Movies",
            "collectionsPath": None,
        },
        {
            "library": "TV Shows",
            "assetPath": "/assets/TV Shows",
            "collectionsPath": "/collections/tv",
        },
    ]

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["libraryMappings"] == [
        {
            "library": "Movies",
            "assetPath": "/assets/New Movies",
            "collectionsPath": None,
        },
        {
            "library": "TV Shows",
            "assetPath": "/assets/TV Shows",
            "collectionsPath": "/collections/tv",
        },
    ]

    assert library_module.get_cached_mappings() is None
