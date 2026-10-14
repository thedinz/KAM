import importlib

from starlette.responses import FileResponse


def test_fileproxy_allows_assets_root(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    poster_dir = assets_root / "Movies" / "My Film (2024)"
    poster_dir.mkdir(parents=True)
    poster_path = poster_dir / "poster.jpg"
    poster_path.write_bytes(b"poster")

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

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    library_mappings.clear_cache()

    fileproxy_router = importlib.reload(importlib.import_module("app.routers.fileproxy"))

    response = fileproxy_router.fileproxy(path=str(poster_path))

    assert isinstance(response, FileResponse)


def test_fileproxy_rejects_a_saved_mapping_outside_the_asset_root(tmp_path, monkeypatch):
    import pytest
    from fastapi import HTTPException

    assets_root = tmp_path / "assets"
    assets_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("secret")

    settings_module = importlib.reload(importlib.import_module("app.services.settings"))
    settings_module.set_settings_path(str(tmp_path / "settings.json"))
    settings_module.save_settings(
        {"libraryMappings": [{"library": "Movies", "assetPath": str(outside)}]}
    )
    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)
    library_mappings = importlib.reload(importlib.import_module("app.services.library_mappings"))
    library_mappings.clear_cache()
    fileproxy_router = importlib.reload(importlib.import_module("app.routers.fileproxy"))

    with pytest.raises(HTTPException) as exc:
        fileproxy_router.fileproxy(path=str(secret))
    assert exc.value.status_code == 403
