import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture
def orphaned_assets_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library_root = assets_root / "Movies"
    present = library_root / "Present Movie (2020)"
    present_yearless = library_root / "Present Movie"
    present_directors_cut = library_root / "Present Movie Directors Cut (2020)"
    returns = library_root / "Returns Later (2005)"
    orphaned = library_root / "Step Brothers (2008)"
    custom = library_root / "A Hand Picked Folder"
    for folder in (
        present,
        present_yearless,
        present_directors_cut,
        returns,
        orphaned,
        custom,
    ):
        folder.mkdir(parents=True)
    (orphaned / "poster.png").write_bytes(b"poster")
    (orphaned / "background.jpg").write_bytes(b"background")

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(tmp_path / "overrides.json"))
    monkeypatch.setenv("KAM_EXCLUSIONS_PATH", str(tmp_path / "exclusions.json"))
    monkeypatch.setenv(
        "KAM_ORPHAN_EXCLUSIONS_PATH",
        str(tmp_path / "orphan_exclusions.json"),
    )

    settings = importlib.reload(importlib.import_module("app.services.settings"))
    settings.set_settings_path(str(tmp_path / "settings.json"))
    settings.save_settings({
        "plexUrl": "http://plex.test",
        "plexToken": "token",
        "libraryMappings": [{"library": "Movies", "assetPath": str(library_root)}],
    })

    mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    mappings.clear_cache()
    resolve = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve.ASSETS_ROOT = str(assets_root)
    overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    overrides.set_storage_path(str(tmp_path / "overrides.json"))
    orphan_exclusions = importlib.reload(
        importlib.import_module("app.services.orphan_exclusions")
    )
    orphan_exclusions.set_storage_path(str(tmp_path / "orphan_exclusions.json"))
    items = importlib.reload(importlib.import_module("app.routers.items"))
    route = importlib.reload(importlib.import_module("app.routers.orphaned_assets"))

    rows = [
        {
            "title": "Present Movie",
            "year": 2020,
            "ratingKey": "1",
            "type": "movie",
            "titleCandidates": [],
        },
        {
            "title": "Custom Match",
            "year": 2024,
            "ratingKey": "2",
            "type": "movie",
            "titleCandidates": [],
        },
    ]
    overrides.set_canonical_overrides("Movies", {"2": custom.name})
    monkeypatch.setattr(route.items_router, "_library_rows", lambda _library: list(rows))

    return SimpleNamespace(
        route=route,
        rows=rows,
        root=library_root,
        present=present,
        present_yearless=present_yearless,
        present_directors_cut=present_directors_cut,
        returns=returns,
        orphaned=orphaned,
        custom=custom,
        overrides=overrides,
        orphan_exclusions=orphan_exclusions,
    )


@pytest.fixture
def collection_cleanup_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library_root = assets_root / "Movies"
    collections_root = assets_root / "Collections" / "Movies"
    regular_same_name = library_root / "Retired Collection"
    active = collections_root / "Hero Collection"
    alternate = collections_root / "Hero"
    orphaned = collections_root / "Retired Collection"
    yearless = collections_root / "Franchise Collection"
    for folder in (regular_same_name, active, alternate, orphaned, yearless):
        folder.mkdir(parents=True)
    (alternate / "poster.jpg").write_bytes(b"poster")

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(tmp_path / "overrides.json"))
    monkeypatch.setenv(
        "KAM_ORPHAN_EXCLUSIONS_PATH",
        str(tmp_path / "orphan_exclusions.json"),
    )

    settings = importlib.reload(importlib.import_module("app.services.settings"))
    settings.set_settings_path(str(tmp_path / "settings.json"))
    settings.save_settings({
        "plexUrl": "http://plex.test",
        "plexToken": "token",
        "libraryMappings": [{
            "library": "Movies",
            "assetPath": str(library_root),
            "collectionsPath": str(collections_root),
        }],
    })

    mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    mappings.clear_cache()
    resolve = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve.ASSETS_ROOT = str(assets_root)
    overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    overrides.set_storage_path(str(tmp_path / "overrides.json"))
    orphan_exclusions = importlib.reload(
        importlib.import_module("app.services.orphan_exclusions")
    )
    orphan_exclusions.set_storage_path(str(tmp_path / "orphan_exclusions.json"))
    route = importlib.reload(importlib.import_module("app.routers.orphaned_assets"))

    collection_rows = [
        {
            "title": "Hero Collection",
            "year": None,
            "ratingKey": "collection-1",
            "type": "collection",
            "titleCandidates": [],
        },
        {
            "title": "Franchise Collection (2024)",
            "year": None,
            "ratingKey": "collection-2",
            "type": "collection",
            "titleCandidates": [],
        },
    ]
    monkeypatch.setattr(
        route.collections_router,
        "_collection_audit_rows",
        lambda _library: list(collection_rows),
    )
    monkeypatch.setattr(route.items_router, "_library_rows", lambda _library: [])

    return SimpleNamespace(
        route=route,
        root=collections_root,
        library_root=library_root,
        regular_same_name=regular_same_name,
        active=active,
        alternate=alternate,
        orphaned=orphaned,
        yearless=yearless,
        overrides=overrides,
        orphan_exclusions=orphan_exclusions,
    )


def test_lists_only_folders_without_a_current_plex_match(orphaned_assets_env):
    data = orphaned_assets_env.route.list_orphaned_assets(library="Movies")

    assert data["totalCount"] == 2
    by_name = {item["folderName"]: item for item in data["items"]}
    assert set(by_name) == {"Returns Later (2005)", "Step Brothers (2008)"}
    assert by_name["Step Brothers (2008)"]["title"] == "Step Brothers"
    assert by_name["Step Brothers (2008)"]["year"] == 2008
    assert by_name["Step Brothers (2008)"]["assetCount"] == 2
    assert by_name["Step Brothers (2008)"]["posterUrl"].startswith("/fileproxy?path=")


def test_folder_drops_from_orphaned_results_when_movie_returns(orphaned_assets_env):
    orphaned_assets_env.rows.append({
        "title": "Returns Later",
        "year": 2005,
        "ratingKey": "3",
        "type": "movie",
        "titleCandidates": [],
    })

    data = orphaned_assets_env.route.list_orphaned_assets(library="Movies")

    assert [item["folderName"] for item in data["items"]] == ["Step Brothers (2008)"]


def test_delete_rechecks_plex_and_skips_a_folder_that_now_matches(orphaned_assets_env):
    orphaned_assets_env.rows.append({
        "title": "Step Brothers",
        "year": 2008,
        "ratingKey": "4",
        "type": "movie",
        "titleCandidates": [],
    })
    payload = orphaned_assets_env.route.DeleteOrphanedAssetsPayload(
        library="Movies",
        folderNames=["Step Brothers (2008)"],
    )

    data = orphaned_assets_env.route.delete_orphaned_assets(payload)

    assert data["deletedCount"] == 0
    assert data["skipped"][0]["folderName"] == "Step Brothers (2008)"
    assert orphaned_assets_env.orphaned.is_dir()


def test_deletes_selected_orphaned_folder_and_clears_stale_override(orphaned_assets_env):
    orphaned_assets_env.overrides.set_canonical_overrides(
        "Movies", {"old-rating-key": orphaned_assets_env.orphaned.name}
    )
    payload = orphaned_assets_env.route.DeleteOrphanedAssetsPayload(
        library="Movies",
        folderNames=[orphaned_assets_env.orphaned.name],
    )

    data = orphaned_assets_env.route.delete_orphaned_assets(payload)

    assert data["deleted"] == ["Step Brothers (2008)"]
    assert not orphaned_assets_env.orphaned.exists()
    assert "old-rating-key" not in orphaned_assets_env.overrides.get_library_overrides("Movies")


def test_delete_rejects_traversal_as_not_orphaned(orphaned_assets_env):
    payload = orphaned_assets_env.route.DeleteOrphanedAssetsPayload(
        library="Movies",
        folderNames=["../Movies"],
    )

    data = orphaned_assets_env.route.delete_orphaned_assets(payload)

    assert data["deletedCount"] == 0
    assert data["skipped"]
    assert orphaned_assets_env.root.is_dir()


def test_all_plausible_folder_variations_are_protected_from_orphans(orphaned_assets_env):
    data = orphaned_assets_env.route.list_orphaned_assets(library="Movies")

    names = {item["folderName"] for item in data["items"]}
    assert "Present Movie (2020)" not in names
    assert "Present Movie" not in names
    assert "Present Movie Directors Cut (2020)" not in names


def test_ambiguous_yearless_remake_is_protected_but_not_called_duplicate(
    orphaned_assets_env,
):
    ambiguous = orphaned_assets_env.root / "Shared Title"
    ambiguous.mkdir()
    orphaned_assets_env.rows.extend([
        {
            "title": "Shared Title",
            "year": 1980,
            "ratingKey": "80",
            "type": "movie",
            "titleCandidates": [],
        },
        {
            "title": "Shared Title",
            "year": 2020,
            "ratingKey": "81",
            "type": "movie",
            "titleCandidates": [],
        },
    ])

    orphaned = orphaned_assets_env.route.list_orphaned_assets(library="Movies")
    duplicates = orphaned_assets_env.route.list_duplicate_folders(library="Movies")

    assert "Shared Title" not in {item["folderName"] for item in orphaned["items"]}
    assert all(group["title"] != "Shared Title" for group in duplicates["groups"])


def test_orphan_false_positive_can_be_excluded_and_restored(orphaned_assets_env):
    payload = orphaned_assets_env.route.OrphanExclusionPayload(
        library="Movies",
        folderName="Step Brothers (2008)",
    )

    orphaned_assets_env.route.exclude_orphaned_asset(payload)
    hidden = orphaned_assets_env.route.list_orphaned_assets(library="Movies")
    visible = orphaned_assets_env.route.list_orphaned_assets(
        library="Movies",
        include_excluded=True,
    )

    assert "Step Brothers (2008)" not in {item["folderName"] for item in hidden["items"]}
    by_name = {item["folderName"]: item for item in visible["items"]}
    assert by_name["Step Brothers (2008)"]["excluded"] is True

    orphaned_assets_env.route.include_orphaned_asset(payload)
    restored = orphaned_assets_env.route.list_orphaned_assets(library="Movies")
    assert "Step Brothers (2008)" in {item["folderName"] for item in restored["items"]}


def test_duplicate_groups_include_title_variations_and_active_folder(orphaned_assets_env):
    data = orphaned_assets_env.route.list_duplicate_folders(library="Movies")

    group = next(item for item in data["groups"] if item["ratingKey"] == "1")
    assert group["activeFolderName"] == "Present Movie (2020)"
    assert {item["folderName"] for item in group["folders"]} == {
        "Present Movie",
        "Present Movie (2020)",
        "Present Movie Directors Cut (2020)",
    }


def test_duplicate_resolution_keeps_selection_and_deletes_other_folders(
    orphaned_assets_env,
):
    payload = orphaned_assets_env.route.ResolveDuplicateFoldersPayload(
        library="Movies",
        ratingKey="1",
        keepFolderName="Present Movie Directors Cut (2020)",
    )

    data = orphaned_assets_env.route.resolve_duplicate_folders(payload)

    assert data["keptFolderName"] == "Present Movie Directors Cut (2020)"
    assert data["previousActiveFolderName"] == "Present Movie (2020)"
    assert data["folderAssignmentChanged"] is True
    assert set(data["deleted"]) == {"Present Movie", "Present Movie (2020)"}
    assert orphaned_assets_env.present_directors_cut.is_dir()
    assert not orphaned_assets_env.present.is_dir()
    assert not orphaned_assets_env.present_yearless.is_dir()
    assert orphaned_assets_env.overrides.get_override("Movies", "1") == (
        "Present Movie Directors Cut (2020)"
    )


def test_duplicate_batch_resolution_switches_kam_before_deleting_other_folders(
    orphaned_assets_env,
):
    payload = orphaned_assets_env.route.ResolveDuplicateFoldersBatchPayload(
        library="Movies",
        selections=[
            orphaned_assets_env.route.ResolveDuplicateFolderSelection(
                ratingKey="1",
                keepFolderName="Present Movie Directors Cut (2020)",
            )
        ],
    )

    data = orphaned_assets_env.route.resolve_all_duplicate_folders(payload)

    assert data["processedCount"] == 1
    assert data["deletedCount"] == 2
    assert data["folderAssignmentsChanged"] == 1
    assert data["failures"] == []
    assert data["results"][0]["folderAssignmentChanged"] is True
    assert orphaned_assets_env.overrides.get_override("Movies", "1") == (
        "Present Movie Directors Cut (2020)"
    )
    assert orphaned_assets_env.present_directors_cut.is_dir()
    assert not orphaned_assets_env.present.is_dir()
    assert not orphaned_assets_env.present_yearless.is_dir()


def test_collection_scope_finds_orphans_and_duplicate_collection_folders(
    collection_cleanup_env,
):
    orphaned = collection_cleanup_env.route.list_orphaned_assets(
        library="Movies",
        scope="collections",
    )
    duplicates = collection_cleanup_env.route.list_duplicate_folders(
        library="Movies",
        scope="collections",
    )

    assert orphaned["scope"] == "collections"
    assert orphaned["root"] == str(collection_cleanup_env.root.resolve())
    assert {item["folderName"] for item in orphaned["items"]} == {
        "Retired Collection"
    }
    group = duplicates["groups"][0]
    assert group["title"] == "Hero Collection"
    assert group["activeFolderName"] == "Hero Collection"
    assert {item["folderName"] for item in group["folders"]} == {
        "Hero",
        "Hero Collection",
    }


def test_collection_orphan_exclusions_do_not_hide_same_named_library_folder(
    collection_cleanup_env,
):
    payload = collection_cleanup_env.route.OrphanExclusionPayload(
        library="Movies",
        scope="collections",
        folderName="Retired Collection",
    )

    stored = collection_cleanup_env.route.exclude_orphaned_asset(payload)
    hidden = collection_cleanup_env.route.list_orphaned_assets(
        library="Movies",
        scope="collections",
    )
    regular = collection_cleanup_env.route.list_orphaned_assets(
        library="Movies",
        scope="assets",
    )

    assert stored["scope"] == "collections"
    assert hidden["items"] == []
    assert {item["folderName"] for item in regular["items"]} == {
        "Retired Collection"
    }
    collection_cleanup_env.route.include_orphaned_asset(payload)
    restored = collection_cleanup_env.route.list_orphaned_assets(
        library="Movies",
        scope="collections",
    )
    assert {item["folderName"] for item in restored["items"]} == {
        "Retired Collection"
    }


def test_collection_duplicate_resolution_switches_only_the_collection_folder(
    collection_cleanup_env,
):
    payload = collection_cleanup_env.route.ResolveDuplicateFoldersPayload(
        library="Movies",
        scope="collections",
        ratingKey="collection-1",
        keepFolderName="Hero",
    )

    data = collection_cleanup_env.route.resolve_duplicate_folders(payload)

    assert data["scope"] == "collections"
    assert data["folderAssignmentChanged"] is True
    assert data["deleted"] == ["Hero Collection"]
    assert collection_cleanup_env.alternate.is_dir()
    assert not collection_cleanup_env.active.exists()
    assert collection_cleanup_env.regular_same_name.is_dir()
    assert collection_cleanup_env.overrides.get_override(
        "Movies", "collection-1"
    ) == "Hero"


def test_duplicate_resolution_keeps_exact_name_when_folders_differ_only_by_case(
    collection_cleanup_env,
    monkeypatch,
):
    group = {
        "ratingKey": "collection-case",
        "title": "Men In Black",
        "year": None,
        "type": "collection",
        "activeFolderName": "men in black",
        "folders": [
            {"folderName": "Men In Black", "isActive": False},
            {"folderName": "men in black", "isActive": True},
        ],
    }
    deleted = []
    monkeypatch.setattr(
        collection_cleanup_env.route,
        "_duplicate_groups",
        lambda _library, _scope: (collection_cleanup_env.root, [group]),
    )
    monkeypatch.setattr(
        collection_cleanup_env.route,
        "_delete_direct_folder",
        lambda _root, folder_name: deleted.append(folder_name),
    )

    payload = collection_cleanup_env.route.ResolveDuplicateFoldersPayload(
        library="Movies",
        scope="assets",
        ratingKey="collection-case",
        keepFolderName="Men In Black",
    )
    data = collection_cleanup_env.route.resolve_duplicate_folders(payload)

    assert data["keptFolderName"] == "Men In Black"
    assert data["folderAssignmentChanged"] is True
    assert data["deleted"] == ["men in black"]
    assert deleted == ["men in black"]
    assert collection_cleanup_env.overrides.get_override(
        "Movies", "collection-case"
    ) == "Men In Black"


def test_duplicate_selection_preserves_significant_folder_whitespace(
    collection_cleanup_env,
):
    exact_name = "Men In Black\N{NO-BREAK SPACE}"

    single = collection_cleanup_env.route.ResolveDuplicateFoldersPayload(
        library="Movies",
        scope="collections",
        ratingKey="collection-space",
        keepFolderName=exact_name,
    )
    selection = collection_cleanup_env.route.ResolveDuplicateFolderSelection(
        ratingKey="collection-space",
        keepFolderName=exact_name,
    )
    collection_cleanup_env.overrides.set_canonical_overrides(
        "Movies", {"collection-space": exact_name}
    )

    assert single.keepFolderName == exact_name
    assert selection.keepFolderName == exact_name
    assert collection_cleanup_env.overrides.get_override(
        "Movies", "collection-space"
    ) == exact_name


def test_collection_orphan_delete_preserves_same_named_library_folder_and_override(
    collection_cleanup_env,
):
    collection_cleanup_env.overrides.set_canonical_overrides(
        "Movies",
        {"regular-item": "Retired Collection"},
    )
    payload = collection_cleanup_env.route.DeleteOrphanedAssetsPayload(
        library="Movies",
        scope="collections",
        folderNames=["Retired Collection"],
    )

    data = collection_cleanup_env.route.delete_orphaned_assets(payload)

    assert data["scope"] == "collections"
    assert data["deleted"] == ["Retired Collection"]
    assert not collection_cleanup_env.orphaned.exists()
    assert collection_cleanup_env.regular_same_name.is_dir()
    assert collection_cleanup_env.overrides.get_override(
        "Movies", "regular-item"
    ) == "Retired Collection"


def test_collection_audit_never_falls_back_to_the_regular_asset_root(
    collection_cleanup_env,
    tmp_path,
    monkeypatch,
):
    missing_collections = tmp_path / "missing-collections"
    monkeypatch.setattr(
        collection_cleanup_env.route.library_mappings_service,
        "get_collections_path",
        lambda _library: str(missing_collections),
    )
    monkeypatch.setattr(
        collection_cleanup_env.route.collections_router,
        "_collections_root_for_library",
        lambda _library: collection_cleanup_env.library_root,
    )

    with pytest.raises(collection_cleanup_env.route.HTTPException) as exc_info:
        collection_cleanup_env.route.list_orphaned_assets(
            library="Movies",
            scope="collections",
        )

    assert exc_info.value.status_code == 404
    assert collection_cleanup_env.regular_same_name.is_dir()
