import asyncio
import importlib
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _setup_route(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    folder = assets_root / "TV Shows" / "Example Show (2024)"
    folder.mkdir(parents=True)
    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": "TV Shows",
                    "assetPath": str(assets_root / "TV Shows"),
                }
            ],
        }
    )

    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    library_mappings.clear_cache()
    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)
    route = importlib.reload(importlib.import_module("app.routers.plex_artwork"))
    return route, folder


def test_manual_route_applies_saved_season_background(tmp_path, monkeypatch):
    route, folder = _setup_route(tmp_path, monkeypatch)
    artwork = folder / "Season02_background.jpg"
    artwork.write_bytes(b"background")
    calls = []

    monkeypatch.setattr(
        route.plex_artwork_service,
        "apply_artwork_file",
        lambda rating_key, path, kind: calls.append((rating_key, path, kind))
        or {"ok": True, "ratingKey": rating_key, "path": path, "kind": kind},
    )

    payload = route.ApplyPlexArtworkPayload(
        library="TV Shows",
        folderName="Example Show (2024)",
        ratingKey="84",
        kind="background",
        season=2,
    )
    result = asyncio.run(route.apply_saved_artwork(payload))

    assert result["ok"] is True
    assert len(calls) == 1
    rating_key, applied_path, kind = calls[0]
    assert rating_key == "84"
    assert Path(applied_path) == artwork
    assert kind == "background"


def test_manual_route_rejects_missing_saved_asset(tmp_path, monkeypatch):
    route, _ = _setup_route(tmp_path, monkeypatch)
    payload = route.ApplyPlexArtworkPayload(
        library="TV Shows",
        folderName="Example Show (2024)",
        ratingKey="84",
        kind="poster",
        season=2,
    )

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(route.apply_saved_artwork(payload))

    assert excinfo.value.status_code == 404
    assert "Season02" in str(excinfo.value.detail)


def test_service_uses_plex_poster_and_background_methods(tmp_path, monkeypatch):
    service = importlib.reload(importlib.import_module("app.services.plex_artwork"))
    poster = tmp_path / "poster.jpg"
    background = tmp_path / "background.jpg"
    poster.write_bytes(b"poster")
    background.write_bytes(b"background")

    class FakeItem:
        def __init__(self):
            self.poster_paths = []
            self.background_paths = []

        def uploadPoster(self, filepath):
            self.poster_paths.append(filepath)

        def uploadArt(self, filepath):
            self.background_paths.append(filepath)

    item = FakeItem()

    class FakePlex:
        def fetchItem(self, rating_key):
            assert rating_key == 42
            return item

    monkeypatch.setattr(service, "get_plex", lambda: FakePlex())

    service.apply_artwork_file("42", str(poster), "poster")
    service.apply_artwork_file("42", str(background), "background")

    assert item.poster_paths == [str(poster)]
    assert item.background_paths == [str(background)]


def test_automatic_apply_reports_failure_without_raising(monkeypatch):
    service = importlib.reload(importlib.import_module("app.services.plex_artwork"))
    monkeypatch.setattr(service, "auto_apply_enabled", lambda: True)

    def reject_artwork(*_args):
        raise service.PlexArtworkError("Plex is unavailable.")

    monkeypatch.setattr(service, "apply_artwork_file", reject_artwork)

    result = service.auto_apply_result("42", "/assets/poster.jpg", "poster")

    assert result == {
        "attempted": True,
        "ok": False,
        "error": "Plex is unavailable.",
    }
