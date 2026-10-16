import importlib

from fastapi.testclient import TestClient

_LOGIN = {"authMode": "builtin", "authUsername": "admin", "authPassword": "local-secret"}


def _client(tmp_path, monkeypatch, saved=_LOGIN, env=None):
    assets_root = tmp_path / "assets"
    poster_dir = assets_root / "Movies" / "Film (2024)"
    poster_dir.mkdir(parents=True)
    (poster_dir / "poster.jpg").write_bytes(b"poster")

    monkeypatch.setenv("KAM_ASSETS_ROOT", str(assets_root))
    monkeypatch.setenv("KAM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    for name in ("KAM_AUTH_MODE", "KAM_AUTH_USERNAME", "KAM_AUTH_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)

    settings = importlib.reload(importlib.import_module("app.services.settings"))
    if saved:
        settings.save_settings(saved)
    auth = importlib.reload(importlib.import_module("app.services.auth"))
    importlib.reload(importlib.import_module("app.routers.auth"))
    importlib.reload(importlib.import_module("app.routers.settings"))
    main = importlib.reload(importlib.import_module("app.main"))
    return TestClient(main.app), auth


def test_assets_require_a_login_when_built_in_auth_is_on(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    path = "/assets/Movies/Film%20(2024)/poster.jpg"

    assert client.get(path).status_code == 401

    login = client.post("/auth/login", json={"username": "admin", "password": "local-secret"})
    assert login.status_code == 200

    response = client.get(path)
    assert response.status_code == 200
    assert response.content == b"poster"


def test_fresh_install_is_locked_until_setup(tmp_path, monkeypatch):
    client, auth = _client(tmp_path, monkeypatch, saved=None)
    with client:  # runs the startup hook, which logs the setup code
        code = auth._SETUP_CODE
        assert code

        assert client.get("/api/settings").status_code == 401
        assert client.put("/api/settings", json={"theme": "dark"}).status_code == 401
        assert client.get("/assets/Movies/Film%20(2024)/poster.jpg").status_code == 401
        page = client.get("/libraries", headers={"accept": "text/html"}, follow_redirects=False)
        assert page.headers["location"] == "/login"
        assert client.get("/auth/status").json()["setupRequired"] is True

        setup = client.post(
            "/auth/setup",
            json={"code": code, "username": "admin", "password": "long-secret"},
        )
        assert setup.status_code == 200

        # The setup response signs the owner in.
        settings = client.get("/api/settings")
        assert settings.status_code == 200
        assert settings.json()["authUsername"] == "admin"


def test_none_mode_runs_without_a_login(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, saved=None, env={"KAM_AUTH_MODE": "none"})

    assert client.get("/api/settings").status_code == 200
    assert client.get("/auth/status").json()["authenticated"] is True
