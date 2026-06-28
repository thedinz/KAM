import importlib
import importlib
import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture
def items_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Movies"
    library_path = assets_root / library
    folder = library_path / "My Film (2023)"
    folder.mkdir(parents=True)
    (folder / "poster.jpg").write_bytes(b"poster")
    tagged_folder = (
        library_path
        / "Tagged Movie (2024) {tmdb-12345} [Custom Format][Bluray-1080p][x265]-GROUP"
    )
    tagged_folder.mkdir(parents=True)

    overrides_path = tmp_path / "overrides.json"
    exclusions_path = tmp_path / "exclusions.json"

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(overrides_path))
    monkeypatch.setenv("KAM_EXCLUSIONS_PATH", str(exclusions_path))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
            "libraryMappings": [
                {
                    "library": library,
                    "assetPath": str(library_path),
                    "collectionsPath": None,
                }
            ],
        }
    )
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))
    plex_settings.clear_cache()

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    folder_overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    folder_overrides.set_storage_path(str(overrides_path))

    exclusions_module = importlib.reload(importlib.import_module("app.services.exclusions"))
    exclusions_module.set_storage_path(str(exclusions_path))

    items_router = importlib.reload(importlib.import_module("app.routers.items"))

    monkeypatch.setattr(items_router, "_section_key_by_name", lambda _: "1")

    def fake_plex_list(path, params=None):
        if params and params.get("type") == 1:
            return [
                {
                    "title": "My Film",
                    "year": 2023,
                    "ratingKey": "11",
                    "type": "movie",
                    "thumb": "/thumb",
                },
                {
                    "title": "Needs Assets",
                    "year": 2020,
                    "ratingKey": "22",
                    "type": "movie",
                    "thumb": "/thumb2?width=500&height=750",
                },
                {
                    "title": "Tagged Movie",
                    "year": 2024,
                    "ratingKey": "33",
                    "type": "movie",
                    "thumb": "/thumb3",
                },
            ]
        return []

    monkeypatch.setattr(items_router, "_plex_list", fake_plex_list)

    def _call(**kwargs):
        params = {
            "library": library,
            "page": 1,
            "page_size": 60,
            "query": None,
            "sort": "title",
            "not_ready_only": False,
            "include_counts": True,
            "counts_only": False,
        }
        params.update(kwargs)
        return items_router.list_items(**params)

    return SimpleNamespace(
        call=_call,
        items_router=items_router,
        folder_overrides=folder_overrides,
        folder=folder,
        tagged_folder=tagged_folder,
        exclusions=exclusions_module,
    )


def test_items_route_prefers_override(items_env):
    items_env.folder_overrides.set_override("Movies", "11", items_env.folder.name)

    data = items_env.call()
    items = {it["ratingKey"]: it for it in data["items"]}

    overridden = items["11"]
    assert overridden["folderName"] == items_env.folder.name
    assert overridden["assetReady"] is True
    assert overridden["posterUrl"].startswith("/fileproxy")
    assert overridden["posterUrlLocal"].startswith("/fileproxy")
    assert overridden["posterUrlPlex"].startswith("http://plex.test")


def test_items_route_reports_not_ready_count_and_filters(items_env):
    data = items_env.call()

    assert data["not_ready_count"] == 1

    by_key = {it["ratingKey"]: it for it in data["items"]}
    assert by_key["33"]["assetReady"] is True
    assert by_key["33"]["folderName"] == items_env.tagged_folder.name
    assert by_key["22"]["assetReady"] is False
    assert by_key["22"]["posterUrl"].startswith("/api/plex/image")
    assert by_key["22"]["posterUrlPlex"].startswith("http://plex.test")
    assert "?" in by_key["22"]["posterUrlPlex"]
    assert "X-Plex-Token=token" in by_key["22"]["posterUrlPlex"].split("?")[-1]

    filtered = items_env.call(not_ready_only=True)

    assert filtered["not_ready_count"] == 1
    assert filtered["total_count"] == 1
    assert len(filtered["items"]) == 1
    assert filtered["items"][0]["ratingKey"] == "22"


def test_items_route_uses_alternate_title_candidates(items_env, monkeypatch):
    localized_folder = items_env.folder.parent / "Leon The Professional (1994)"
    localized_folder.mkdir()

    def fake_plex_list(path, params=None):
        if params and params.get("type") == 1:
            return [
                {
                    "title": "Léon - Der Profi",
                    "originalTitle": "Léon The Professional",
                    "year": 1994,
                    "ratingKey": "44",
                    "type": "movie",
                    "thumb": "/thumb4",
                    "Media": [
                        {
                            "Part": [
                                {
                                    "file": (
                                        "/movies/Léon - The Professional (1994)/"
                                        "Léon The Professional (1994) {tmdb-101} "
                                        "{edition-Remastered} [Bluray-1080p].mkv"
                                    )
                                }
                            ]
                        }
                    ],
                }
            ]
        return []

    monkeypatch.setattr(items_env.items_router, "_plex_list", fake_plex_list)

    data = items_env.call()
    item = data["items"][0]

    assert data["not_ready_count"] == 0
    assert item["assetReady"] is True
    assert item["folderName"] == "Leon The Professional (1994)"


def test_items_route_fast_page_does_not_scan_full_library(items_env, monkeypatch):
    calls = []

    monkeypatch.setattr(
        items_env.items_router,
        "_section_info_by_name",
        lambda library: ("1", "movie"),
    )

    def fake_plex_list_page(path, params=None):
        params = dict(params or {})
        calls.append((path, params))
        start = int(params.get("X-Plex-Container-Start") or 0)
        size = int(params.get("X-Plex-Container-Size") or 0)
        items = [
            {
                "title": f"Movie {idx}",
                "year": 2020,
                "ratingKey": str(idx),
                "type": "movie",
                "thumb": f"/thumb/{idx}",
            }
            for idx in range(start, start + size)
        ]
        return items, 1000

    monkeypatch.setattr(items_env.items_router, "_plex_list_page", fake_plex_list_page)

    data = items_env.items_router.list_items(
        library="Movies",
        page=2,
        page_size=2,
        query=None,
        sort="title",
        not_ready_only=False,
        include_counts=False,
        counts_only=False,
    )

    assert len(calls) == 1
    assert calls[0][0] == "/library/sections/1/all"
    assert calls[0][1]["type"] == 1
    assert calls[0][1]["X-Plex-Container-Start"] == 2
    assert calls[0][1]["X-Plex-Container-Size"] == 2
    assert data["total_count"] == 1000
    assert data["total_pages"] == 500
    assert data["not_ready_count"] is None
    assert [item["ratingKey"] for item in data["items"]] == ["2", "3"]


def test_items_route_counts_only_omits_items(items_env):
    data = items_env.call(counts_only=True)

    assert data["items"] == []
    assert data["total_count"] == 3
    assert data["not_ready_count"] == 1


def test_items_route_omits_excluded_items(items_env):
    items_env.exclusions.add_exclusion("Movies", "22", "movie", title="Needs Assets")

    data = items_env.call()

    keys = {it["ratingKey"] for it in data["items"]}
    assert "22" not in keys


def test_mapping_source_returns_lightweight_items(items_env):
    items_env.folder_overrides.set_override("Movies", "11", items_env.folder.name)

    data = items_env.items_router.list_items_for_mapping_scan(library="Movies")
    by_key = {it["ratingKey"]: it for it in data["items"]}

    assert data["total_count"] == 3
    assert by_key["11"]["folderName"] == items_env.folder.name
    assert by_key["11"]["assetReady"] is True
    assert by_key["33"]["folderName"] == ""
    assert by_key["33"]["assetReady"] is False
    assert by_key["22"]["folderName"] == ""
    assert by_key["22"]["assetReady"] is False
    assert "posterUrl" not in by_key["11"]


def test_item_rows_sort_newest_uses_added_at_then_year(items_env):
    rows = [
        {"title": "Middle Added", "year": 2021, "addedAt": 200},
        {"title": "Newest Added", "year": 2020, "addedAt": 300},
        {"title": "Newest Year Fallback", "year": 2025, "addedAt": None},
        {"title": "Oldest Year Fallback", "year": 2019, "addedAt": None},
    ]

    importlib.import_module("app.routers.items")._sort_item_rows(rows, "newest")

    assert [row["title"] for row in rows] == [
        "Newest Added",
        "Middle Added",
        "Newest Year Fallback",
        "Oldest Year Fallback",
    ]


def test_item_rows_sort_defaults_to_title(items_env):
    rows = [
        {"title": "Zebra", "year": 2025, "addedAt": 300},
        {"title": "alpha", "year": 2020, "addedAt": 100},
    ]

    importlib.import_module("app.routers.items")._sort_item_rows(rows, "unexpected")

    assert [row["title"] for row in rows] == ["alpha", "Zebra"]
