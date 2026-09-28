import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_clearing_settings_resets_cached_values(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"

    with monkeypatch.context() as patch:
        patch.setenv("KAM_SETTINGS_PATH", str(settings_path))

        settings_service = importlib.reload(
            importlib.import_module("app.services.settings")
        )
        plex_settings = importlib.reload(
            importlib.import_module("app.services.plex_settings")
        )

        settings_service.save_settings(
            {"plexUrl": "http://plex.example:32400", "plexToken": "initial-token"}
        )

        cfg = plex_settings.get_plex_config(force_refresh=True)
        assert cfg.url == "http://plex.example:32400"
        assert cfg.token == "initial-token"

        settings_service.save_settings({"plexUrl": "", "plexToken": ""})

        cfg = plex_settings.get_plex_config(force_refresh=True)
        assert cfg.url == ""
        assert cfg.token == ""

    importlib.reload(importlib.import_module("app.services.settings"))
    importlib.reload(importlib.import_module("app.services.plex_settings"))


def _plex_settings_for(monkeypatch, url):
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))
    monkeypatch.setattr(
        plex_settings,
        "get_plex_config",
        lambda **_kwargs: plex_settings.PlexConfig(url=url, token="secret"),
    )
    return plex_settings


def test_is_plex_url_requires_the_configured_origin(monkeypatch):
    plex_settings = _plex_settings_for(monkeypatch, "http://plex.local:32400")

    assert plex_settings.is_plex_url("http://plex.local:32400/library/metadata/1/thumb")
    assert plex_settings.is_plex_url("HTTP://PLEX.local:32400/photo")
    assert not plex_settings.is_plex_url("http://plex.local:32400.attacker.example/x")
    assert not plex_settings.is_plex_url("http://plex.local:32400@attacker.example/x")
    assert not plex_settings.is_plex_url("https://plex.local:32400/library")
    assert not plex_settings.is_plex_url("http://plex.local/library")
    assert not plex_settings.is_plex_url("")


def test_is_plex_url_respects_a_path_prefix(monkeypatch):
    plex_settings = _plex_settings_for(monkeypatch, "https://proxy.local/plex")

    assert plex_settings.is_plex_url("https://proxy.local/plex/library/metadata/1/thumb")
    assert not plex_settings.is_plex_url("https://proxy.local/plexfake/library")
    assert not plex_settings.is_plex_url("https://proxy.local/other")


def test_verify_ssl_reads_the_environment(monkeypatch):
    plex_settings = importlib.reload(importlib.import_module("app.services.plex_settings"))

    monkeypatch.delenv("PLEX_VERIFY_SSL", raising=False)
    assert plex_settings.verify_ssl() is True
    for value in ("false", "FALSE", "0", "no", "off"):
        monkeypatch.setenv("PLEX_VERIFY_SSL", value)
        assert plex_settings.verify_ssl() is False
    monkeypatch.setenv("PLEX_VERIFY_SSL", "true")
    assert plex_settings.verify_ssl() is True


def test_plex_image_proxy_rejects_lookalike_hosts(monkeypatch):
    import pytest
    from fastapi import HTTPException

    _plex_settings_for(monkeypatch, "http://plex.local:32400")
    proxy = importlib.reload(importlib.import_module("app.routers.plex_proxy"))

    def fail_request(*_args, **_kwargs):
        raise AssertionError("the Plex token must not be sent to another host")

    monkeypatch.setattr(proxy.requests, "get", fail_request)

    with pytest.raises(HTTPException) as exc_info:
        proxy.plex_image(path="http://plex.local:32400.attacker.example/x", ratingKey=None, kind="thumb")

    assert exc_info.value.status_code == 403


def test_imports_refuse_urls_outside_plex(monkeypatch, tmp_path):
    import pytest
    from fastapi import HTTPException

    imports = importlib.reload(importlib.import_module("app.routers.imports"))
    monkeypatch.setattr(imports.plex_settings, "is_plex_url", lambda url: False)

    def fail_request(*_args, **_kwargs):
        raise AssertionError("imports must not fetch non-Plex URLs")

    monkeypatch.setattr(imports.requests, "get", fail_request)
    target = tmp_path / "poster.jpg"
    target.write_bytes(b"existing")

    with pytest.raises(HTTPException) as exc_info:
        imports._download_to(str(target), "http://internal.example/admin")

    assert exc_info.value.status_code == 422
    assert target.read_bytes() == b"existing"
