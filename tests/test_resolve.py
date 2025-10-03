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

    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module,
        "LIBRARY_MAPPINGS",
        {library: str(mapped_library_path)},
        raising=False,
    )

    resolve_module = _reload_with_assets_root(str(assets_root))

    resolved = resolve_module.resolve_existing_dir_or_422(library, target)
    assert resolved == os.path.join(str(mapped_library_path), target)


def test_resolve_accepts_high_similarity_variant(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    target = "Jurassic World Fallen Kingdom (2018)"
    existing = "Jurassic World Fallen Kingdom (Extended Edition) (2018)"

    library_path = assets_root / library
    library_path.mkdir(parents=True)
    (library_path / existing).mkdir()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

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

    resolve_module = _reload_with_assets_root(str(assets_root))

    with pytest.raises(FileNotFoundError):
        resolve_module.resolve_existing_dir_or_422(library, target)
