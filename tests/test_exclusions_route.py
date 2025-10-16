import importlib

from fastapi import HTTPException


def _reload_modules(tmp_path, monkeypatch):
    storage_path = tmp_path / "exclusions.json"
    monkeypatch.setenv("KAM_EXCLUSIONS_PATH", str(storage_path))

    service = importlib.reload(importlib.import_module("app.services.exclusions"))
    service.set_storage_path(str(storage_path))
    router = importlib.reload(importlib.import_module("app.routers.exclusions"))
    return router, service


def test_create_list_delete_exclusions(tmp_path, monkeypatch):
    router, service = _reload_modules(tmp_path, monkeypatch)

    assert router.get_exclusions() == []

    payload = router.ExclusionPayload(
        library="Movies",
        ratingKey="500",
        type="movie",
        title="Sample Movie",
        year=2020,
    )

    created = router.create_exclusion(payload)
    assert created.library == "Movies"
    assert created.ratingKey == "500"
    assert created.type == "movie"
    assert created.title == "Sample Movie"
    assert created.year == 2020
    assert created.excludedAt

    listed = router.get_exclusions()
    assert len(listed) == 1
    assert listed[0].library == "Movies"

    response = router.delete_exclusion("Movies", "500")
    assert response.status_code == 204
    assert service.list_exclusions() == []


def test_delete_missing_exclusion_raises(tmp_path, monkeypatch):
    router, _ = _reload_modules(tmp_path, monkeypatch)

    try:
        router.delete_exclusion("Movies", "999")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing exclusion")
