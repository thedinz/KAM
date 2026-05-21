import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routers import items


def test_movie_with_year_does_not_try_bare_title_fallback(monkeypatch):
    calls = []

    def fake_resolve(library, folder_name):
        calls.append((library, folder_name))
        raise FileNotFoundError(folder_name)

    monkeypatch.setattr(items, "resolve_existing_dir_or_422", fake_resolve)

    folder_name, folder_path = items._try_existing_asset_folder(
        "Movies", "Movie 2", 2015, "movie"
    )

    assert (folder_name, folder_path) == (None, None)
    assert calls == [("Movies", "Movie 2 (2015)")]


def test_show_with_year_can_still_try_title_folder(monkeypatch):
    calls = []

    def fake_resolve(library, folder_name):
        calls.append((library, folder_name))
        if folder_name == "Breaking Bad":
            return "/assets/TV Shows/Breaking Bad"
        raise FileNotFoundError(folder_name)

    monkeypatch.setattr(items, "resolve_existing_dir_or_422", fake_resolve)

    folder_name, folder_path = items._try_existing_asset_folder(
        "TV Shows", "Breaking Bad", 2008, "show"
    )

    assert folder_name == "Breaking Bad"
    assert folder_path == "/assets/TV Shows/Breaking Bad"
    assert calls == [
        ("TV Shows", "Breaking Bad (2008)"),
        ("TV Shows", "Breaking Bad"),
    ]
