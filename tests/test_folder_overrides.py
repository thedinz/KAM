import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _reload_overrides_module():
    return importlib.reload(importlib.import_module("app.services.folder_overrides"))


def test_default_storage_path_prefers_existing_file(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    existing = config_dir / "folder_overrides.json"
    existing.write_text("{}", encoding="utf-8")

    monkeypatch.delenv("KAM_FOLDER_OVERRIDES_PATH", raising=False)
    monkeypatch.setenv("KAM_STATE_ROOT", str(state_dir))
    monkeypatch.setenv("KAM_CONFIG_ROOT", str(config_dir))

    module = _reload_overrides_module()
    assert module._get_storage_path() == existing


def test_default_storage_path_defaults_to_first_candidate(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    monkeypatch.delenv("KAM_FOLDER_OVERRIDES_PATH", raising=False)
    monkeypatch.setenv("KAM_STATE_ROOT", str(state_dir))
    monkeypatch.delenv("KAM_CONFIG_ROOT", raising=False)

    module = _reload_overrides_module()
    assert module._get_storage_path() == state_dir / "folder_overrides.json"


def test_default_storage_path_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("KAM_FOLDER_OVERRIDES_PATH", raising=False)
    monkeypatch.delenv("KAM_STATE_ROOT", raising=False)
    monkeypatch.delenv("KAM_CONFIG_ROOT", raising=False)

    module = _reload_overrides_module()
    assert str(module._get_storage_path()) == "/config/folder_overrides.json"


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

    documentaries_dir = assets_root / "Documentaries"
    documentaries_folder = documentaries_dir / "Nature Wonders"

    overrides_path = tmp_path / "overrides.json"

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(overrides_path))

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(movies_dir),
                    "collectionsPath": str(collections_dir),
                }
            ]
        }
    )

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
        documentaries_dir=documentaries_dir,
        documentaries_folder=documentaries_folder,
        settings_module=settings_module,
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


def test_assign_folder_creates_library_mapping_when_missing(overrides_env):
    router = overrides_env.assets_router
    settings_module = overrides_env.settings_module

    overrides_env.documentaries_folder.mkdir(parents=True)

    settings_module.save_settings(
        {
            "libraryMappings": [
                {
                    "library": "Movies",
                    "assetPath": str(overrides_env.movies_dir),
                    "collectionsPath": str(overrides_env.collections_dir),
                }
            ]
        }
    )

    payload = router.AssignFolderPayload(
        library="Documentaries",
        ratingKey="55",
        folderName=overrides_env.documentaries_folder.name,
    )
    router.assign_folder(payload)

    stored = settings_module.load_settings()
    mappings = stored.get("libraryMappings", [])
    doc_entries = [entry for entry in mappings if entry.get("library") == "Documentaries"]
    assert doc_entries
    assert doc_entries[0]["assetPath"] == str(overrides_env.documentaries_dir)


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
