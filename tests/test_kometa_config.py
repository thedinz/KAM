from pathlib import Path
import importlib


def test_normalize_config_path_handles_relative_base(tmp_path):
    module = importlib.import_module("app.services.kometa_config")
    importlib.reload(module)

    # When the Kometa config path is provided as a relative string, we still
    # want to surface the original normalized fragment if nothing on disk
    # matches. This ensures the UI can present "config/..." suggestions for
    # users running Kometa in containers where the actual paths resolve
    # elsewhere.
    result = module.normalize_config_path(
        "config/assets/Collections",
        base_dir=tmp_path / "config",
    )
    assert result == str(tmp_path / "config" / "assets" / "Collections")

    # Passing a relative Path should preserve the original string when no
    # candidate exists locally.
    result_relative = module.normalize_config_path(
        "config/assets/Collections",
        base_dir=Path("config"),
    )
    assert result_relative == "config/assets/Collections"
