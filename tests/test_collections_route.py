import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _DummyCollection:
    def __init__(self, title: str, rating_key: int):
        self.title = title
        self.ratingKey = rating_key


class _DummySection:
    def __init__(self, collections):
        self._collections = collections

    def collections(self):
        return self._collections


class _DummyLibrary:
    def __init__(self, sections):
        self._sections = sections

    def sections(self):
        return self._sections


class _DummyPlex:
    def __init__(self, sections):
        self.library = _DummyLibrary(sections)


@pytest.fixture
def collections_call(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    collections_root = assets_root / "Collections"
    ready_folder = collections_root / "my cool collection"
    ready_folder.mkdir(parents=True)

    from app import config
    from app.routers import collections as collections_router

    monkeypatch.setattr(config, "PLEX_URL", "http://plex.test")
    monkeypatch.setattr(config, "PLEX_TOKEN", "token")
    monkeypatch.setattr(config, "CONFIG_ERRORS", [])

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("COLLECTIONS_ROOT", str(collections_root))

    collections_router.ASSETS_ROOT = str(assets_root)
    collections_router.COLLECTIONS_ROOT = str(collections_root)

    sections = [_DummySection([
        _DummyCollection("My Cool Collection", 1),
        _DummyCollection("Missing Assets", 2),
    ])]

    monkeypatch.setattr(collections_router, "get_plex", lambda: _DummyPlex(sections))

    def _call(**kwargs):
        params = {"query": None, "page": 1, "page_size": 60}
        params.update(kwargs)
        return collections_router.collections(**params)

    return _call


def test_collections_route_marks_asset_readiness(collections_call):
    data = collections_call()
    items = {it["title"]: it for it in data["items"]}

    ready = items["My Cool Collection"]
    # Folder detected despite casing difference and missing poster
    assert ready["folderName"] == "my cool collection"
    assert ready["assetReady"] is True

    missing = items["Missing Assets"]
    assert missing["assetReady"] is False
    assert missing["folderName"] == "Missing Assets"


def test_index_html_consumes_asset_ready_flag():
    html = (ROOT / "app" / "web" / "index.html").read_text(encoding="utf-8")
    assert "filter(it => it?.assetReady !== false)" in html
    assert "let folderName = it?.folderName || \"\"" in html
    assert "id=\"folderFinder\"" in html
    assert "data-folder-results" in html
    assert "status.dataset.folderTrigger" in html
