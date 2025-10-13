import importlib

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

    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
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

    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    library_mappings.clear_cache()

    expected_asset = library_mappings.normalize_path(str(movies_root))
    expected_collections = library_mappings.normalize_path(str(collections_root))

    assert library_mappings.get_asset_path("  Movies  ") == expected_asset
    assert library_mappings.get_collections_path("\tMovies\n") == expected_collections

