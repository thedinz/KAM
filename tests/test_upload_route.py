import asyncio
import importlib
import io
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _setup_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "Kids Movies"
    folder = "Example Movie (2020)"
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

    upload_module = importlib.reload(importlib.import_module("app.routers.upload"))

    return upload_module, target_dir, library, folder


async def _invoke_upload(upload_module, library, folder, content: bytes):
    upload_file = UploadFile(
        filename="poster.jpg",
        file=io.BytesIO(content),
    )
    return await upload_module.upload_movie_asset(
        library=library,
        folderName=folder,
        file=upload_file,
        kind="poster",
    )


async def _invoke_season_upload(upload_module, library, folder, content: bytes, kind: str):
    upload_file = UploadFile(
        filename="season.jpg",
        file=io.BytesIO(content),
    )
    return await upload_module.upload_season_asset(
        library=library,
        folderName=folder,
        season="2",
        kind=kind,
        file=upload_file,
    )


def test_upload_movie_writes_file(tmp_path, monkeypatch):
    upload_module, target_dir, library, folder = _setup_env(tmp_path, monkeypatch)

    response = asyncio.run(_invoke_upload(upload_module, library, folder, b"poster-bytes"))

    assert response == {"ok": True, "path": str(target_dir / "poster.jpg")}
    poster_path = target_dir / "poster.jpg"
    assert poster_path.exists()
    assert poster_path.read_bytes() == b"poster-bytes"


def test_upload_movie_rejects_empty_file(tmp_path, monkeypatch):
    upload_module, target_dir, library, folder = _setup_env(tmp_path, monkeypatch)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(_invoke_upload(upload_module, library, folder, b""))

    assert excinfo.value.status_code == 422
    assert "Empty file" in str(excinfo.value.detail)
    assert not (target_dir / "poster.jpg").exists()


def test_upload_season_background_uses_kometa_filename(tmp_path, monkeypatch):
    upload_module, target_dir, library, folder = _setup_env(tmp_path, monkeypatch)

    response = asyncio.run(
        _invoke_season_upload(upload_module, library, folder, b"season-background", "background")
    )

    background_path = target_dir / "Season02_background.jpg"
    assert response == {"ok": True, "path": str(background_path)}
    assert background_path.read_bytes() == b"season-background"
