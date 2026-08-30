import importlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import app.services.library_mappings as _library_mappings_module


def _reload_library_mappings():
    importlib.reload(_library_mappings_module)
    return _library_mappings_module

def test_get_collections_path_uses_section_override(tmp_path):
    settings_path = tmp_path / "settings.json"
    assets_root = tmp_path / "assets"
    collections_root = assets_root / "Collections"
    movies_section_root = collections_root / "Movies"
    movies_asset_root = assets_root / "Movies"

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(settings_path))
    settings_module.save_settings(
        {
            "libraryMappings": [
                {
                    "library": "Collections",
                    "assetPath": str(collections_root),
                    "collectionSections": [
                        {
                            "name": "Movies",
                            "collectionsPath": str(movies_section_root),
                        }
                    ],
                },
                {
                    "library": "Movies",
                    "assetPath": str(movies_asset_root),
                    "collectionsPath": None,
                },
            ]
        }
    )

    library_mappings = _reload_library_mappings()
    library_mappings.clear_cache()

    expected = library_mappings.normalize_path(str(movies_section_root))
    assert library_mappings.get_collections_path("Movies") == expected


def test_library_lookup_trims_whitespace(tmp_path):
    settings_path = tmp_path / "settings.json"
    movies_root = tmp_path / "assets" / "Movies"
    collections_root = tmp_path / "collections" / "Movies"

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(settings_path))
    settings_module.save_settings(
        {
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(movies_root),
                    "collectionsPath": str(collections_root),
                }
            ]
        }
    )

    library_mappings = _reload_library_mappings()


def test_normalize_path_rebases_app_root(monkeypatch):
    monkeypatch.setenv("KAM_ASSETS_ROOT", "/mnt/assets")
    library_mappings = _reload_library_mappings()

    assert library_mappings.normalize_path("/app/Movies") == "/mnt/assets/Movies"
    assert library_mappings.normalize_path("/app") == "/mnt/assets"
    assert library_mappings.normalize_path("/app/assets/Shows") == "/mnt/assets/Shows"

    monkeypatch.delenv("KAM_ASSETS_ROOT", raising=False)
    _reload_library_mappings()


def test_normalize_path_preserves_expected_root(monkeypatch):
    monkeypatch.setenv("KAM_ASSETS_ROOT", "/app")
    library_mappings = _reload_library_mappings()

    assert library_mappings.normalize_path("/app/Movies") == "/app/Movies"
    assert library_mappings.normalize_path("/app") == "/app"

    monkeypatch.delenv("KAM_ASSETS_ROOT", raising=False)
    _reload_library_mappings()


def test_default_collections_path_uses_assets_root(monkeypatch):
    monkeypatch.setenv("KAM_ASSETS_ROOT", "/mnt/assets")
    monkeypatch.delenv("COLLECTIONS_ROOT", raising=False)
    library_mappings = _reload_library_mappings()
    library_mappings.clear_cache()

    assert library_mappings.get_collections_path() == "/mnt/assets/Collections"

    monkeypatch.delenv("KAM_ASSETS_ROOT", raising=False)
    _reload_library_mappings()


def test_default_collections_path_without_env(monkeypatch):
    monkeypatch.delenv("KAM_ASSETS_ROOT", raising=False)
    monkeypatch.delenv("ASSETS_ROOT", raising=False)
    monkeypatch.delenv("COLLECTIONS_ROOT", raising=False)
    library_mappings = _reload_library_mappings()
    library_mappings.clear_cache()

    assert library_mappings.get_collections_path() == "/assets/Collections"
