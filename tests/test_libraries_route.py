import importlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def test_get_libraries_keeps_collections_after_mapped_libraries(monkeypatch):
    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    monkeypatch.setattr(
        settings_module,
        "load_settings",
        lambda: {
            "theme": "dark",
            "plexUrl": "http://plex.example:32400",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": "Collections",
                    "assetPath": "/assets/Collections",
                },
                {
                    "library": "Movies",
                    "assetPath": "/assets/Movies",
                },
                {
                    "library": "TV Shows",
                    "assetPath": "/assets/TV Shows",
                },
            ],
        },
    )

    library_mappings_module = importlib.reload(
        importlib.import_module("app.services.library_mappings")
    )
    library_mappings_module.clear_cache()
    router_module = importlib.reload(importlib.import_module("app.routers.libraries"))

    assert router_module.get_libraries() == ["Movies", "TV Shows", "Collections"]
