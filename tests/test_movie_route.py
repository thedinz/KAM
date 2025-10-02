import sys
from pathlib import Path

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
def movie_call(tmp_path, monkeypatch):
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
    from app.services import resolve as resolve_module
    from app.routers import movie as movie_router

    monkeypatch.setattr(config, "LIBRARY_MAPPINGS", {library: str(library_path)})
    monkeypatch.setattr(config, "PLEX_URL", "http://plex.test")
    monkeypatch.setattr(config, "PLEX_TOKEN", "token")
    monkeypatch.setattr(config, "CONFIG_ERRORS", [])

    monkeypatch.setattr(resolve_module, "ASSETS_ROOT", str(assets_root))

    items = {
        1: _DummyItem("Jurassic World: Fallen Kingdom", 2018),
        2: _DummyItem("Some Other Movie", 2021),
    }
    sections = [_DummySection(library)]

    monkeypatch.setattr(movie_router, "get_plex", lambda: _DummyPlex(sections, items))

    def _call(rating_key: int):
        return movie_router.movie_api(library=library, ratingKey=rating_key)

    return _call


def test_movie_route_uses_resolved_folder(movie_call):
    data = movie_call(1)
    assert data["folderExists"] is True
    assert data["folderName"] == "Jurassic World Fallen Kingdom (Extended Edition) (2018)"


def test_movie_route_rejects_unrelated_folder(movie_call):
    data = movie_call(2)
    assert data["folderExists"] is False
    assert data["folderName"] == "Some Other Movie (2021)"
