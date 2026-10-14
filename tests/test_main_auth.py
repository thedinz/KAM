import importlib

from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    assets_root = tmp_path / "assets"
    poster_dir = assets_root / "Movies" / "Film (2024)"
    poster_dir.mkdir(parents=True)
    (poster_dir / "poster.jpg").write_bytes(b"poster")

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    for name in ("KAM_AUTH_MODE", "KAM_AUTH_USERNAME", "KAM_AUTH_PASSWORD"):
        monkeypatch.delenv(name, raising=False)

    settings = importlib.reload(importlib.import_module("app.services.settings"))
    settings.save_settings(
        {"authMode": "builtin", "authUsername": "admin", "authPassword": "local-secret"}
    )
    importlib.reload(importlib.import_module("app.services.auth"))
    importlib.reload(importlib.import_module("app.routers.auth"))
    main = importlib.reload(importlib.import_module("app.main"))
    return TestClient(main.app)


def test_assets_require_a_login_when_built_in_auth_is_on(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    path = "/assets/Movies/Film%20(2024)/poster.jpg"

    assert client.get(path).status_code == 401

    login = client.post("/auth/login", json={"username": "admin", "password": "local-secret"})
    assert login.status_code == 200

    response = client.get(path)
    assert response.status_code == 200
    assert response.content == b"poster"
