import importlib
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _setup_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "TV Shows"
    folder = "Example Show (2024)"
    target_dir = assets_root / library / folder
    target_dir.mkdir(parents=True)

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [],
        }
    )

    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    library_mappings.clear_cache()

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    imports_module = importlib.reload(importlib.import_module("app.routers.imports"))

    return imports_module, target_dir, library, folder


def test_import_title_card_uses_kometa_episode_filename(tmp_path, monkeypatch):
    imports_module, target_dir, library, folder = _setup_env(tmp_path, monkeypatch)
    captured = {}

    def fake_download_result(path, src):
        captured["path"] = path
        captured["src"] = src
        return {"ok": True, "path": path, "src": src, "error": None, "replaced": False}

    monkeypatch.setattr(imports_module, "_download_result", fake_download_result)

    response = imports_module.import_title_card_post(
        library=library,
        folderName=folder,
        season="2",
        episode="3",
        ratingKey="301",
        url="http://plex.test/library/metadata/301/thumb?X-Plex-Token=token",
    )

    expected_path = target_dir / "S02E03.jpg"
    assert response["ok"] is True
    assert captured["path"] == str(expected_path)
    assert response["path"] == str(expected_path)


def test_imports_are_not_reachable_with_get():
    imports_router = importlib.import_module("app.routers.imports")

    get_import_paths = [
        route.path
        for route in imports_router.router.routes
        if route.path.startswith("/api/import/") and "GET" in getattr(route, "methods", set())
    ]

    assert get_import_paths == []


class _FakeImage:
    def __init__(self, body=b"image"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.body


def test_import_accepts_kam_proxy_urls_and_keeps_the_token_server_side(tmp_path, monkeypatch):
    imports_module, target_dir, library, folder = _setup_env(tmp_path, monkeypatch)
    requested = []

    def fake_plex_get(url, **kwargs):
        requested.append(url)
        return _FakeImage()

    monkeypatch.setattr(imports_module.plex_settings, "plex_get", fake_plex_get)

    response = imports_module.import_poster_post(
        library=library,
        folderName=folder,
        ratingKey="301",
        url="/api/plex/image?path=%2Flibrary%2Fmetadata%2F301%2Fthumb%2F1712345678&w=400",
    )

    # The full-size image is imported, not the resized one the page showed.
    assert requested == ["http://plex.test/library/metadata/301/thumb/1712345678"]
    assert (target_dir / "poster.jpg").read_bytes() == b"image"
    assert "token" not in response["src"]


def test_import_rejects_urls_outside_plex(tmp_path, monkeypatch):
    imports_module, _, library, folder = _setup_env(tmp_path, monkeypatch)

    with pytest.raises(HTTPException) as exc:
        imports_module.import_poster_post(
            library=library,
            folderName=folder,
            ratingKey="301",
            url="http://elsewhere.test/library/metadata/301/thumb",
        )

    assert exc.value.status_code == 422


def test_plex_source_url_maps_proxy_and_plex_urls(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)
    plex_assets = importlib.reload(importlib.import_module("app.services.plex_assets"))

    assert plex_assets.plex_source_url("/api/plex/image?ratingKey=7&kind=art") == (
        "http://plex.test/library/metadata/7/art"
    )
    assert plex_assets.plex_source_url(
        "http://plex.test/library/metadata/7/thumb?X-Plex-Token=token"
    ) == ("http://plex.test/library/metadata/7/thumb")
    assert plex_assets.build_plex_asset_url(None, "7", "thumb") == (
        "/api/plex/image?path=%2Flibrary%2Fmetadata%2F7%2Fthumb"
    )
    assert plex_assets.plex_source_url("/fileproxy?path=x") is None
    assert plex_assets.plex_source_url("https://evil.test/api/plex/image?path=/x") is None
