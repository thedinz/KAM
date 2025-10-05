import importlib
from types import SimpleNamespace

import pytest


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._payload

    @property
    def text(self):  # pragma: no cover - not used in tests
        return ""


@pytest.fixture
def tv_env(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    library = "TV Shows"
    library_path = assets_root / library
    show_folder = library_path / "My Show (2023)"
    show_folder.mkdir(parents=True)
    (show_folder / "poster.jpg").write_bytes(b"poster")
    (show_folder / "background.jpg").write_bytes(b"background")
    (show_folder / "Season01.jpg").write_bytes(b"s1")

    overrides_path = tmp_path / "overrides.json"

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_FOLDER_OVERRIDES_PATH", str(overrides_path))

    settings_module = importlib.import_module("app.services.settings")
    monkeypatch.setattr(
        settings_module,
        "load_settings",
        lambda: {
            "theme": "dark",
            "plexUrl": "http://plex.test",
            "plexToken": "token",
        },
    )
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))
    plex_settings.clear_cache()

    from app import config

    monkeypatch.setattr(config, "LIBRARY_MAPPINGS", {library: str(library_path)})
    monkeypatch.setattr(config, "COLLECTIONS_ROOT", "")

    resolve_module = importlib.reload(importlib.import_module("app.services.resolve"))
    resolve_module.ASSETS_ROOT = str(assets_root)

    folder_overrides = importlib.reload(importlib.import_module("app.services.folder_overrides"))
    folder_overrides.set_storage_path(str(overrides_path))

    tv_router = importlib.reload(importlib.import_module("app.routers.tv"))

    def fake_plex(path):
        if path.endswith("/children"):
            payload = {
                "MediaContainer": {
                    "Metadata": [
                        {
                            "type": "season",
                            "index": 1,
                            "title": "Season 1",
                            "ratingKey": "201",
                            "thumb": "/season/thumb",
                        }
                    ]
                }
            }
        else:
            payload = {
                "MediaContainer": {
                    "Metadata": [
                        {
                            "type": "show",
                            "title": "My Show",
                            "year": 2023,
                            "thumb": "/show/thumb",
                            "art": "/show/art",
                        }
                    ]
                }
            }
        return _DummyResponse(payload)

    monkeypatch.setattr(tv_router, "_plex_json_or_xml", fake_plex)

    def _call():
        return tv_router.get_show(library=library, ratingKey="101")

    return SimpleNamespace(
        call=_call,
        folder_overrides=folder_overrides,
        show_folder=show_folder,
    )


def test_tv_route_prefers_override(tv_env):
    tv_env.folder_overrides.set_override("TV Shows", "101", tv_env.show_folder.name)

    data = tv_env.call()
    assert data["folderName"] == tv_env.show_folder.name
    assert data["folderExists"] is True
    assert data["posterUrl"].startswith("/fileproxy")
    assert data["backgroundUrl"].startswith("/fileproxy")
    assert data["seasons"][0]["posterUrl"].startswith("/fileproxy")
    assert data["plexPosterUrl"].startswith("http://plex.test")
    assert data["plexBackgroundUrl"].startswith("http://plex.test")
