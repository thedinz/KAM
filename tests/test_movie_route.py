import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _DummySection:
    def __init__(self, title: str):
        self.title = title


class _DummyLibrary:
    def __init__(self, sections):
        self._sections = sections

    def sections(self):
        return self._sections


class _DummyPlex:
    def __init__(self, sections, items):
        self.library = _DummyLibrary(sections)
        self._items = items

    def fetchItem(self, rating_key):
        return self._items[int(rating_key)]


class _DummyItem:
    def __init__(self, title, year):
        self.title = title
        self.year = year


@pytest.fixture
def movie_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    library_path = assets_root / library
    library_path.mkdir(parents=True)

    # Variant directory that should be resolved
    existing_variant = "Jurassic World Fallen Kingdom (Extended Edition) (2018)"
    (library_path / existing_variant).mkdir()

    # Another unrelated folder to ensure false positives are avoided
    (library_path / "Completely Different (2020)").mkdir()

    from app import config

    monkeypatch.setattr(config, "LIBRARY_MAPPINGS", {library: str(library_path)})

    settings_module = importlib.import_module("app.services.settings")
    monkeypatch.setattr(
        settings_module,
        "load_settings",
        lambda: {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
        },
    )
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))
    plex_settings.clear_cache()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    overrides_path = tmp_path / "overrides.json"
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(overrides_path))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    folder_overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    folder_overrides.set_storage_path(str(overrides_path))

    movie_router = importlib.reload(importlib.import_module("app.routers.movie"))

    items = {
        1: _DummyItem("Jurassic World: Fallen Kingdom", 2018),
        2: _DummyItem("Some Other Movie", 2021),
    }
    sections = [_DummySection(library)]

    monkeypatch.setattr(movie_router, "get_plex", lambda: _DummyPlex(sections, items))

    def _call(rating_key: int):
        return movie_router.movie_api(library=library, ratingKey=rating_key)

    return SimpleNamespace(
        call=_call,
        folder_overrides=folder_overrides,
        library_path=library_path,
        existing_variant=existing_variant,
    )


def test_movie_route_uses_resolved_folder(movie_env):
    data = movie_env.call(1)
    assert data["folderExists"] is True
    assert data["folderName"] == "Jurassic World Fallen Kingdom (Extended Edition) (2018)"


def test_movie_route_rejects_unrelated_folder(movie_env):
    data = movie_env.call(2)
    assert data["folderExists"] is False
    assert data["folderName"] == "Some Other Movie (2021)"


def test_movie_route_prefers_override(movie_env):
    folder = movie_env.library_path / movie_env.existing_variant
    (folder / "poster.jpg").write_bytes(b"poster")
    (folder / "background.jpg").write_bytes(b"bg")

    movie_env.folder_overrides.set_override("Movies", "1", folder.name)

    data = movie_env.call(1)
    assert data["folderName"] == folder.name
    assert data["folderExists"] is True
    assert data["posterExists"] is True
    assert data["backgroundExists"] is True
    assert data["posterUrlPlex"].startswith("http://plex.test")
    assert data["backgroundUrlPlex"].startswith("http://plex.test")
