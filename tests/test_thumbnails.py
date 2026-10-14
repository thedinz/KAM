import importlib
import io
import os
from types import SimpleNamespace

import pytest
import requests
from PIL import Image
from starlette.responses import FileResponse


def _write_poster(path, size=(1000, 1500), image_format="JPEG"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 30, 30)).save(path, format=image_format)


@pytest.fixture
def fileproxy_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    poster = assets_root / "Movies" / "Film (2024)" / "poster.jpg"
    _write_poster(poster)

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_THUMBNAIL_CACHE", str(tmp_path / "cache"))
    settings = importlib.reload(importlib.import_module("app.services.settings"))
    settings.set_settings_path(str(tmp_path / "settings.json"))
    settings.save_settings({"libraryMappings": []})
    resolve = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve.ASSETS_ROOT = str(assets_root)
    mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    mappings.clear_cache()
    thumbnails = importlib.reload(importlib.import_module("app.services.thumbnails"))
    fileproxy = importlib.reload(importlib.import_module("app.routers.fileproxy"))
    return SimpleNamespace(
        fileproxy=fileproxy,
        thumbnails=thumbnails,
        poster=poster,
        cache=tmp_path / "cache",
    )


def test_snap_width_rounds_up_to_a_cached_size():
    thumbnails = importlib.import_module("app.services.thumbnails")

    assert thumbnails.snap_width(150) == 200
    assert thumbnails.snap_width(400) == 400
    assert thumbnails.snap_width(401) == 800
    assert thumbnails.snap_width(5000) is None
    assert thumbnails.snap_width(0) is None
    assert thumbnails.snap_width(None) is None


def test_fileproxy_serves_a_resized_cached_jpeg(fileproxy_env):
    env = fileproxy_env

    response = env.fileproxy.fileproxy(path=str(env.poster), w=300, t="123")

    assert isinstance(response, FileResponse)
    assert response.media_type == "image/jpeg"
    assert response.headers["cache-control"] == env.fileproxy.VERSIONED_CACHE_CONTROL
    assert str(env.cache) in response.path
    with Image.open(response.path) as thumb:
        assert thumb.size == (400, 600)

    # A second request reuses the cached file.
    again = env.fileproxy.fileproxy(path=str(env.poster), w=400, t="123")
    assert again.path == response.path


def test_thumbnail_is_rebuilt_when_the_artwork_changes(fileproxy_env):
    env = fileproxy_env
    first = env.thumbnails.thumbnail_path(str(env.poster), 200)

    _write_poster(env.poster, size=(800, 1200))
    stat = os.stat(env.poster)
    os.utime(env.poster, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    second = env.thumbnails.thumbnail_path(str(env.poster), 200)

    assert second != first
    assert not os.path.exists(first)
    assert os.path.exists(second)


def test_fileproxy_serves_the_original_without_a_width(fileproxy_env):
    env = fileproxy_env

    response = env.fileproxy.fileproxy(path=str(env.poster))

    assert response.path == str(env.poster)
    assert "cache-control" not in response.headers


def test_fileproxy_falls_back_to_the_original_for_non_images(fileproxy_env):
    env = fileproxy_env
    notes = env.poster.parent / "notes.txt"
    notes.write_text("not an image")

    response = env.fileproxy.fileproxy(path=str(notes), w=200)

    assert response.path == str(notes)


class _FakeResponse:
    def __init__(self, status=200, body=b"image", content_type="image/jpeg"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.is_redirect = False
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def iter_content(self, chunk_size=1):
        yield self._body

    def close(self):
        pass


def _plex_proxy(monkeypatch, responder):
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))
    monkeypatch.setattr(
        plex_settings,
        "get_plex_config",
        lambda **_kwargs: plex_settings.PlexConfig(url="http://plex.local:32400", token="secret"),
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return responder(url)

    monkeypatch.setattr(plex_settings.requests, "get", fake_get)
    proxy = importlib.reload(importlib.import_module("app.routers.plex_proxy"))
    return proxy, calls


def test_plex_proxy_asks_plex_for_a_resized_image(monkeypatch):
    proxy, calls = _plex_proxy(monkeypatch, lambda url: _FakeResponse())

    response = proxy.plex_image(
        path="/library/metadata/1/thumb/1712345678", ratingKey=None, kind="thumb", w=300
    )

    assert len(calls) == 1
    assert calls[0].startswith("http://plex.local:32400/photo/:/transcode?")
    assert "width=400" in calls[0]
    assert "url=%2Flibrary%2Fmetadata%2F1%2Fthumb%2F1712345678" in calls[0]
    assert response.headers["cache-control"].startswith("private, max-age=31536000")


def test_plex_proxy_falls_back_to_the_original_when_resizing_fails(monkeypatch):
    def responder(url):
        return _FakeResponse(status=500) if "/photo/:/transcode" in url else _FakeResponse()

    proxy, calls = _plex_proxy(monkeypatch, responder)

    response = proxy.plex_image(path="/library/metadata/1/thumb", ratingKey=None, kind="thumb", w=300)

    assert calls[-1] == "http://plex.local:32400/library/metadata/1/thumb"
    assert "cache-control" not in response.headers
