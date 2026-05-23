import importlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _DummyCollection:
    def __init__(
        self,
        title: str,
        rating_key: int,
        *,
        library: Optional[str] = None,
        year: Optional[int] = None,
    ):
        self.title = title
        self.ratingKey = rating_key
        if library is not None:
            self.librarySectionTitle = library
        if year is not None:
            self.year = year


class _DummySection:
    def __init__(self, title, collections):
        self.title = title
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
        self._items = {}
        for section in sections:
            for coll in section.collections():
                try:
                    key = int(coll.ratingKey)
                except Exception:
                    key = coll.ratingKey
                self._items[key] = coll

    def fetchItem(self, rating_key):
        key = int(rating_key)
        return self._items[key]


@pytest.fixture
def collections_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    collections_root = assets_root / "Collections"
    movies_section_root = collections_root / "Movies"
    movies_root = assets_root / "Movies"
    movies_root.mkdir(parents=True)
    ready_folder = movies_section_root / "my cool collection"
    ready_folder.mkdir(parents=True)
    override_folder = movies_section_root / "override folder"
    override_folder.mkdir()
    sanitized_only_folder = movies_section_root / "Mission Impossible Collection"
    sanitized_only_folder.mkdir()
    yearless_folder = movies_section_root / "Franchise Collection"
    yearless_folder.mkdir()

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": "Collections",
                    "assetPath": str(collections_root),
                    "collectionSections": [
                        {
                            "name": "Movies",
                            "collectionsPath": str(movies_section_root),
                        }
                    ],
                },
                {
                    "library": "Movies",
                    "assetPath": str(movies_root),
                    "collectionsPath": None,
                }
            ],
        }
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

    exclusions_module = importlib.reload(importlib.import_module("app.services.exclusions"))
    exclusions_path = tmp_path / "exclusions.json"
    exclusions_module.set_storage_path(str(exclusions_path))

    collections_router = importlib.reload(importlib.import_module("app.routers.collections"))

    sections = [_DummySection(
        "Movies",
        [
            _DummyCollection("My Cool Collection", 1),
            _DummyCollection("Missing Assets", 2),
            _DummyCollection("Mission: Impossible Collection", 3),
            _DummyCollection("Franchise Collection (2024)", 4),
        ],
    )]

    monkeypatch.setattr(collections_router, "get_plex", lambda: _DummyPlex(sections))

    def _call(**kwargs):
        params = {"query": None, "page": 1, "page_size": 60, "not_ready_only": False}
        params.update(kwargs)
        return collections_router.collections(**params)

    return SimpleNamespace(
        call=_call,
        folder_overrides=folder_overrides,
        override_folder=override_folder,
        collections_root=movies_section_root,
        exclusions=exclusions_module,
        collection=collections_router.collection,
    )


@pytest.fixture
def collections_env_with_nested_root(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    collections_root = assets_root / "Collections"
    nested_root = collections_root / "Movies"
    movies_root = assets_root / "Movies"
    movies_root.mkdir(parents=True)
    ready_folder = nested_root / "my cool collection"
    ready_folder.mkdir(parents=True)
    override_folder = nested_root / "override folder"
    override_folder.mkdir()
    sanitized_only_folder = nested_root / "Mission Impossible Collection"
    sanitized_only_folder.mkdir()
    yearless_folder = nested_root / "Franchise Collection"
    yearless_folder.mkdir()

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": "Collections",
                    "assetPath": str(collections_root),
                },
                {
                    "library": "Movies",
                    "assetPath": str(movies_root),
                },
            ],
        }
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

    exclusions_module = importlib.reload(importlib.import_module("app.services.exclusions"))
    exclusions_path = tmp_path / "exclusions.json"
    exclusions_module.set_storage_path(str(exclusions_path))

    collections_router = importlib.reload(importlib.import_module("app.routers.collections"))

    sections = [_DummySection(
        "Movies",
        [
            _DummyCollection("My Cool Collection", 1),
            _DummyCollection("Missing Assets", 2),
            _DummyCollection("Mission: Impossible Collection", 3),
            _DummyCollection("Franchise Collection (2024)", 4),
        ],
    )]

    monkeypatch.setattr(collections_router, "get_plex", lambda: _DummyPlex(sections))

    def _call(**kwargs):
        params = {"query": None, "page": 1, "page_size": 60, "not_ready_only": False}
        params.update(kwargs)
        return collections_router.collections(**params)

    return SimpleNamespace(
        call=_call,
        folder_overrides=folder_overrides,
        override_folder=override_folder,
        collections_root=nested_root,
        exclusions=exclusions_module,
    )


@pytest.fixture
def collections_env_without_mapping(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    collections_root = assets_root / "Collections"
    movies_root = assets_root / "Movies"
    movies_root.mkdir(parents=True)
    ready_folder = collections_root / "my cool collection"
    ready_folder.mkdir(parents=True)
    sanitized_only_folder = collections_root / "Mission Impossible Collection"
    sanitized_only_folder.mkdir()
    yearless_folder = collections_root / "Franchise Collection"
    yearless_folder.mkdir()

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(movies_root),
                    "collectionsPath": None,
                }
            ],
        }
    )
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))
    plex_settings.clear_cache()

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("COLLECTIONS_ROOT", str(collections_root))
    overrides_path = tmp_path / "overrides.json"
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(overrides_path))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    folder_overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    folder_overrides.set_storage_path(str(overrides_path))

    exclusions_module = importlib.reload(importlib.import_module("app.services.exclusions"))
    exclusions_path = tmp_path / "exclusions.json"
    exclusions_module.set_storage_path(str(exclusions_path))

    collections_router = importlib.reload(importlib.import_module("app.routers.collections"))

    sections = [_DummySection(
        "Movies",
        [
            _DummyCollection("My Cool Collection", 1),
            _DummyCollection("Missing Assets", 2),
            _DummyCollection("Mission: Impossible Collection", 3),
            _DummyCollection("Franchise Collection (2024)", 4),
        ],
    )]

    monkeypatch.setattr(collections_router, "get_plex", lambda: _DummyPlex(sections))

    def _call(**kwargs):
        params = {"query": None, "page": 1, "page_size": 60, "not_ready_only": False}
        params.update(kwargs)
        return collections_router.collections(**params)

    return SimpleNamespace(call=_call, exclusions=exclusions_module)


def test_collections_route_marks_asset_readiness(collections_env):
    data = collections_env.call()
    items = {it["title"]: it for it in data["items"]}

    ready = items["My Cool Collection"]
    # Folder detected despite casing difference and missing poster
    assert ready["folderName"].casefold() == "my cool collection"
    assert ready["assetReady"] is True
    assert ready["library"] == "Movies"

    missing = items["Missing Assets"]
    assert missing["assetReady"] is False
    assert missing["folderName"] == "Missing Assets"
    assert missing["library"] == "Movies"
    assert missing["posterUrlPlex"].startswith("http://plex.test")

    sanitized = items["Mission: Impossible Collection"]
    assert sanitized["assetReady"] is True

    yearless = items["Franchise Collection (2024)"]
    assert yearless["assetReady"] is True
    assert yearless["folderName"] == "Franchise Collection"
    assert sanitized["folderName"] == "Mission Impossible Collection"
    assert sanitized["library"] == "Movies"


def test_collections_route_omits_excluded_items(collections_env):
    collections_env.exclusions.add_exclusion("Movies", "1", "collection")

    data = collections_env.call()
    titles = [item["title"] for item in data["items"]]

    assert "My Cool Collection" not in titles
    assert data["total_count"] == 3
    # Not-ready counts should still reflect the remaining entries.
    assert data["not_ready_count"] == 1


def test_collections_route_omits_collections_alias_entries(collections_env):
    collections_env.exclusions.add_exclusion("Collections", "1", "collection")

    data = collections_env.call()
    titles = [item["title"] for item in data["items"]]

    assert "My Cool Collection" not in titles


def test_collection_detail_uses_source_library_for_exclusions(collections_env):
    collections_env.exclusions.add_exclusion("Collections", "1", "collection")

    detail = collections_env.collection(
        library="Collections", ratingKey=1, sourceLibrary="Movies"
    )

    assert detail["excluded"] is True
    assert detail["sourceLibrary"] == "Movies"


def test_collections_route_handles_nested_collections_root(collections_env_with_nested_root):
    data = collections_env_with_nested_root.call()
    items = {it["title"]: it for it in data["items"]}

    ready = items["My Cool Collection"]
    assert ready["assetReady"] is True
    assert ready["folderName"].casefold() == "my cool collection"

    sanitized = items["Mission: Impossible Collection"]
    assert sanitized["assetReady"] is True
    assert sanitized["folderName"] == "Mission Impossible Collection"

    missing = items["Missing Assets"]
    assert missing["assetReady"] is False

    yearless = items["Franchise Collection (2024)"]
    assert yearless["assetReady"] is True
    assert yearless["folderName"] == "Franchise Collection"


def test_collections_route_falls_back_to_env_path(collections_env_without_mapping):
    data = collections_env_without_mapping.call()
    items = {it["title"]: it for it in data["items"]}

    ready = items["My Cool Collection"]
    assert ready["assetReady"] is True
    assert ready["folderName"].casefold() == "my cool collection"

    sanitized = items["Mission: Impossible Collection"]
    assert sanitized["assetReady"] is True
    assert sanitized["folderName"] == "Mission Impossible Collection"

    missing = items["Missing Assets"]
    assert missing["assetReady"] is False

    yearless = items["Franchise Collection (2024)"]
    assert yearless["assetReady"] is True
    assert yearless["folderName"] == "Franchise Collection"


INDEX_HTML = ROOT / "app" / "web" / "index.html"


@pytest.mark.skipif(not INDEX_HTML.exists(), reason="SPA bundle has not been built")
def test_index_html_consumes_asset_ready_flag():
    html = INDEX_HTML.read_text(encoding="utf-8")
    asset_refs = re.findall(r'/(spa-assets/[^"\']+)', html)
    assert asset_refs
    for asset_ref in asset_refs:
        assert (ROOT / "app" / "web" / asset_ref).is_file()


def test_collections_route_uses_overrides(collections_env):
    folder = collections_env.override_folder
    (folder / "poster.jpg").write_bytes(b"poster")

    collections_env.folder_overrides.set_override("Movies", "2", folder.name)

    data = collections_env.call()
    items = {it["title"]: it for it in data["items"]}
    overridden = items["Missing Assets"]

    assert overridden["folderName"] == folder.name
    assert overridden["assetReady"] is True
    assert overridden["posterUrlLocal"] is not None
    assert overridden["posterUrlLocal"].startswith("/fileproxy?")


def test_collections_route_reports_not_ready_count_and_filters(collections_env):
    data = collections_env.call()

    assert data["not_ready_count"] == 1

    filtered = collections_env.call(not_ready_only=True)

    assert filtered["not_ready_count"] == 1
    assert filtered["total_count"] == 1
    assert len(filtered["items"]) == 1
    assert filtered["items"][0]["title"] == "Missing Assets"
