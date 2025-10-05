import importlib
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


@pytest.fixture
def overrides_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    movies_dir = assets_root / "Movies"
    movies_dir.mkdir(parents=True)
    movie_folder = movies_dir / "Jurassic World Fallen Kingdom (Extended Edition) (2018)"
    movie_folder.mkdir()
    (movie_folder / "poster.jpg").write_bytes(b"poster")
    (movie_folder / "background.jpg").write_bytes(b"background")

    collections_dir = assets_root / "Collections"
    collections_dir.mkdir()
    (collections_dir / "Override Collection").mkdir()

    loose_dir = assets_root / "LooseAssets"
    loose_dir.mkdir()
    (loose_dir / "Clips").mkdir()

    overrides_path = tmp_path / "overrides.json"

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(overrides_path))

    from app import config

    monkeypatch.setattr(config, "LIBRARY_MAPPINGS", {"Movies": str(movies_dir)})
    monkeypatch.setattr(config, "COLLECTIONS_ROOT", str(collections_dir))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    folder_overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    folder_overrides.set_storage_path(str(overrides_path))

    assets_router = importlib.reload(importlib.import_module("app.routers.assets"))

    return SimpleNamespace(
        folder_overrides=folder_overrides,
        assets_router=assets_router,
        overrides_path=overrides_path,
        movie_folder=movie_folder,
        movies_dir=movies_dir,
        collections_dir=collections_dir,
        loose_dir=loose_dir,
    )


def test_folder_override_roundtrip(overrides_env):
    fo = overrides_env.folder_overrides

    saved = fo.set_override("Movies", "1", overrides_env.movie_folder.name)
    assert saved == overrides_env.movie_folder.name
    assert fo.get_override("Movies", "1") == overrides_env.movie_folder.name

    data = json.loads(overrides_env.overrides_path.read_text(encoding="utf-8"))
    assert data == {"Movies": {"1": overrides_env.movie_folder.name}}

    assert fo.clear_override("Movies", "1") is True
    assert fo.get_override("Movies", "1") is None


def test_assign_folder_endpoint_persists_override(overrides_env):
    fo = overrides_env.folder_overrides
    router = overrides_env.assets_router

    payload = router.AssignFolderPayload(
        library="Movies",
        ratingKey="9",
        folderName=overrides_env.movie_folder.name,
    )
    result = router.assign_folder(payload)

    assert result["folderName"] == overrides_env.movie_folder.name
    assert result["assetReady"] is True
    assert result["posterExists"] is True
    assert result["backgroundExists"] is True
    assert fo.get_override("Movies", "9") == overrides_env.movie_folder.name


def test_list_asset_folders(overrides_env):
    router = overrides_env.assets_router
    movie_folder = overrides_env.movie_folder
    nested = movie_folder / "Extras"
    nested.mkdir()
    (movie_folder / "note.txt").write_text("hello", encoding="utf-8")

    listing = router.list_asset_folders(library="Movies")
    assert listing["library"] == "Movies"
    names = {item["name"] for item in listing["items"]}
    assert movie_folder.name in names

    filtered = router.list_asset_folders(library="Movies", search="extras")
    assert any(item["name"] == "Extras" for item in filtered["items"])

    sub_listing = router.list_asset_folders(library="Movies", parent=movie_folder.name)
    sub_names = {item["name"] for item in sub_listing["items"]}
    assert "Extras" in sub_names
    assert "note.txt" in sub_names

    with pytest.raises(HTTPException):
        router.list_asset_folders(library="Movies", parent="../..")


def test_unmapped_library_navigation(overrides_env):
    router = overrides_env.assets_router

    listing = router.list_asset_folders(library="Documentaries")
    assert listing["parent"] == ""
    names = {item["name"] for item in listing["items"]}
    assert overrides_env.loose_dir.name in names
    assert overrides_env.movies_dir.name in names

    nested = router.list_asset_folders(
        library="Documentaries", parent=overrides_env.loose_dir.name
    )
    nested_names = {item["name"] for item in nested["items"]}
    assert "Clips" in nested_names

    with pytest.raises(HTTPException):
        router.list_asset_folders(library="Documentaries", parent="../Collections")
