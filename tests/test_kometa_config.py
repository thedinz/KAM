import importlib
from pathlib import Path


def test_normalize_config_path_handles_relative_base(tmp_path):
    module = importlib.import_module("app.services.kometa_config")
    importlib.reload(module)

    # When the Kometa config path is provided as a relative string, we still
    # want to surface the original normalized fragment if nothing on disk
    # matches. This ensures the UI can present "config/..." suggestions for
    # users running Kometa in containers where the actual paths resolve
    # elsewhere.
    result = module.normalize_config_path(
        "config/assets/Collections",
        base_dir=tmp_path / "config",
    )
    assert result == str(tmp_path / "config" / "assets" / "Collections")

    # Passing a relative Path should preserve the original string when no
    # candidate exists locally.
    result_relative = module.normalize_config_path(
        "config/assets/Collections",
        base_dir=Path("config"),
    )
    assert result_relative == "config/assets/Collections"


def test_load_library_summaries_extracts_asset_paths(tmp_path):
    module = importlib.import_module("app.services.kometa_config")
    importlib.reload(module)

    config_dir = tmp_path / "config"
    assets_dir = config_dir / "assets" / "Movies"
    defaults_dir = config_dir / "extras" / "Defaults"
    assets_dir.mkdir(parents=True)
    defaults_dir.mkdir(parents=True)

    config_path = config_dir / "config.yml"
    config_path.write_text(
        """
libraries:
  Movies:
    asset_directory: assets/Movies
    collection_defaults:
      asset_directory: extras/Defaults
    collection_files:
      - file: /config/Movies/N28 Lists.yml
        asset_directory: config/assets/Holidays
      - default: franchise
        asset_directory: config/assets/Collections
    collections:
      Franchise:
        asset_directory: config/assets/Collections
  Documentaries:
    collection_files:
      - default: basic
""",
        encoding="utf-8",
    )

    summaries = module.load_library_summaries(str(config_path))

    assert set(summaries.keys()) == {"Movies", "Documentaries"}

    movies = summaries["Movies"]
    assert movies["assetPath"] == str(assets_dir)
    assert set(movies["collectionsPaths"]) == {
        str(defaults_dir),
        str(config_dir / "assets" / "Collections"),
        str(config_dir / "assets" / "Holidays"),
    }

    assert movies["collectionOverrides"] == [
        {
            "name": "Franchise",
            "assetPath": str(config_dir / "assets" / "Collections"),
        }
    ]

    assert summaries["Documentaries"] == {}


def test_load_library_summaries_handles_missing_file(tmp_path):
    module = importlib.import_module("app.services.kometa_config")
    importlib.reload(module)

    missing_path = tmp_path / "no-config.yml"
    assert module.load_library_summaries(str(missing_path)) == {}
