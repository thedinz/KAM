import importlib


def test_add_list_and_remove_exclusions(tmp_path, monkeypatch):
    storage_path = tmp_path / "exclusions.json"
    monkeypatch.setenv("KAM_EXCLUSIONS_PATH", str(storage_path))

    service = importlib.reload(importlib.import_module("app.services.exclusions"))
    service.set_storage_path(str(storage_path))

    assert service.list_exclusions() == []

    added = service.add_exclusion(
        "Movies",
        "101",
        "movie",
        title="Example",
        year=2024,
    )

    assert added["library"] == "Movies"
    assert added["ratingKey"] == "101"
    assert added["type"] == "movie"
    assert added["title"] == "Example"
    assert added["year"] == 2024
    assert "excludedAt" in added

    again = service.add_exclusion("Movies", "101", "movie", title="Updated")
    assert again["title"] == "Updated"
    assert "year" not in again

    listed = service.list_exclusions()
    assert listed == [again]

    assert service.is_excluded("Movies", "101") is True

    removed = service.remove_exclusion("Movies", "101")
    assert removed is True
    assert service.list_exclusions() == []
    assert service.is_excluded("Movies", "101") is False


def test_invalid_exclusion_type_raises(tmp_path, monkeypatch):
    storage_path = tmp_path / "exclusions.json"
    monkeypatch.setenv("KAM_EXCLUSIONS_PATH", str(storage_path))

    service = importlib.reload(importlib.import_module("app.services.exclusions"))
    service.set_storage_path(str(storage_path))

    try:
        service.add_exclusion("Movies", "303", "invalid")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for invalid exclusion type")
