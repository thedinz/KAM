import importlib
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reload_with_assets_root(path):
    module = importlib.import_module("app.services.resolve")
    module = importlib.reload(module)
    module.ASSETS_ROOT = path
    return module


def test_resolve_prefers_config_mapping(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Avatar"

    mapped_library_path = tmp_path / "custom_movies"
    mapped_library_path.mkdir(parents=True)
    (mapped_library_path / target).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings(
        [
            {
                "library": library,
                "assetPath": str(mapped_library_path),
                "collectionsPath": None,
            }
        ]
    )

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert Path(resolved) == mapped_library_path / target


def test_resolve_accepts_high_similarity_variant(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Jurassic World Fallen Kingdom (2018)"
    existing = "Jurassic World Fallen Kingdom (Extended Edition) (2018)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_ignores_radarr_metadata_tags(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Jurassic World: Fallen Kingdom (2018)"
    existing = (
        "Jurassic World Fallen Kingdom (2018) {tmdb-351286} "
        "{edition-Extended Edition} [IMAX Enhanced][Bluray-1080p]"
        "[3D][HDR10][DTS 5.1][x265]-RARBG"
    )

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_folds_diacritics_for_title_matching(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Léon The Professional (1994)"
    existing = "Leon The Professional (1994)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_ignores_bare_folder_ids_after_year(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "The Matrix (1999)"
    existing = "The Matrix (1999) tt0133093 603"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_ignores_leading_folder_id_and_certification_tokens(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "The Matrix (1999)"
    existing = "603 R The Matrix (1999)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_ignores_sonarr_series_folder_ids(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "TV Shows"
    target = "Breaking Bad (2008)"
    existing = "Breaking Bad [tvmaze-169] (2008) [imdb-tt0903747]"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_keeps_real_leading_bracketed_title(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "[REC] (2007)"
    existing = "[REC] (2007) [Bluray-1080p]"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_matches_stopword_and_year_variants(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "The Super Mario Bros. Movie"
    existing = "Super Mario Bros. (2023)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_rejects_low_similarity_titles(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Jurassic World Dominion (2022)"
    existing = "Jurassic World Fallen Kingdom (Extended Edition) (2018)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)


def test_resolve_does_not_match_short_titles_to_longer_phrases(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Collections"
    target = "It"
    existing = "In association With Marvel"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)


def test_resolve_preserves_numeric_titles(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "1408 (2007)"
    existing = "1408 (2007)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_does_not_cross_match_numeric_titles(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Ballerina (2015)"
    existing = "1408"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)


def test_resolve_matches_sequel_to_same_year_folder(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    original = "Movie (2009)"
    sequel = "Movie 2 (2015)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / original).mkdir()
    (library_path / sequel).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, sequel)
    assert os.path.basename(resolved) == sequel


def test_resolve_does_not_match_sequel_to_original_year(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Movie 2 (2015)"
    existing = "Movie (2009)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)


def test_resolve_does_not_match_roman_part_sequel_to_original_title(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "A Quiet Place Part II"
    existing = "A Quiet Place"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)


def test_resolve_does_not_treat_plain_title_prefix_as_edition_variant(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Jurassic World"
    existing = "Jurassic World Dominion"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)


def test_resolve_does_not_match_original_to_sequel_year(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Movie (2009)"
    existing = "Movie 2 (2015)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)


def test_resolve_matches_year_scoped_movie_to_unique_yearless_folder(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Movie 2 (2015)"
    existing = "Movie 2"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert os.path.basename(resolved) == existing


def test_resolve_rejects_yearless_folder_when_explicit_year_conflicts(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Dune (2021)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / "Dune").mkdir()
    (library_path / "Dune (1984) {tmdb-841} [Bluray-1080p]").mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_library_mappings([])

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)
