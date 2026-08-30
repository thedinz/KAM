"""Runtime setup checks used by the Settings page."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

from fastapi import HTTPException

from . import library_mappings, plex as plex_service, plex_settings, settings as settings_service


def _result(
    key: str,
    label: str,
    status: str,
    detail: str,
    *,
    path: str = "",
    library: str = "",
) -> Dict[str, str]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "path": path,
        "library": library,
    }


def _probe_directory(path: Path) -> tuple[bool, str]:
    try:
        fd, probe_path = tempfile.mkstemp(prefix=".kam-health-", dir=str(path))
        os.close(fd)
        os.unlink(probe_path)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _directory_check(
    key: str,
    label: str,
    path_value: Any,
    *,
    require_write: bool,
    library: str = "",
) -> Dict[str, str]:
    path = library_mappings.normalize_path(path_value)
    if not path:
        return _result(key, label, "warning", "Not configured.", path="", library=library)

    target = Path(path)
    if not target.exists():
        return _result(key, label, "error", "Path is not visible to KAM.", path=path, library=library)
    if not target.is_dir():
        return _result(key, label, "error", "Path is not a directory.", path=path, library=library)
    if not require_write:
        return _result(key, label, "ok", "Path is visible.", path=path, library=library)

    writable, detail = _probe_directory(target)
    if not writable:
        message = "Path is visible but KAM cannot write to it."
        if detail:
            message = f"{message} {detail}"
        return _result(key, label, "error", message, path=path, library=library)
    return _result(key, label, "ok", "Path is visible and writable.", path=path, library=library)


def _plex_check() -> Dict[str, str]:
    cfg = plex_settings.get_plex_config(force_refresh=True)
    if not cfg.url or not cfg.token:
        return _result(
            "plex",
            "Plex connection",
            "error",
            "Enter a Plex URL and token, save Settings, then run the check again.",
        )

    try:
        plex_service.get_plex()
    except HTTPException as exc:
        return _result("plex", "Plex connection", "error", str(exc.detail))
    except Exception as exc:
        return _result("plex", "Plex connection", "error", f"Plex connect failed: {exc}")

    return _result("plex", "Plex connection", "ok", f"Connected to {cfg.url}.")


def _config_check() -> Dict[str, str]:
    path = settings_service.get_storage_path()
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return _result(
            "config",
            "Config persistence",
            "error",
            f"KAM cannot create the settings directory. {exc}",
            path=str(path),
        )

    if path.exists() and not path.is_file():
        return _result(
            "config",
            "Config persistence",
            "error",
            "Settings path exists but is not a file.",
            path=str(path),
        )

    writable, detail = _probe_directory(parent)
    if not writable:
        message = "KAM cannot write to the settings directory."
        if detail:
            message = f"{message} {detail}"
        return _result("config", "Config persistence", "error", message, path=str(path))

    state = "Settings path is ready."
    if path.exists():
        state = "Settings file is visible and its directory is writable."
    return _result("config", "Config persistence", "ok", state, path=str(path))


def _collection_paths(mappings: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    checks: List[Dict[str, str]] = []
    seen: set[str] = set()

    def add_path(label: str, path: Any, library: str = "") -> None:
        normalized = library_mappings.normalize_path(path)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        checks.append(
            _directory_check(
                "collection-path",
                label,
                normalized,
                require_write=True,
                library=library,
            )
        )

    add_path(
        "Collections root",
        os.environ.get("COLLECTIONS_ROOT") or library_mappings.get_collections_path(),
    )
    for mapping in mappings:
        library = str(mapping.get("library") or "").strip()
        add_path(f"{library or 'Library'} collections", mapping.get("collectionsPath"), library)
        for section in mapping.get("collectionSections") or []:
            name = str(section.get("name") or "").strip()
            section_label = f"{name or library or 'Section'} collections"
            add_path(section_label, section.get("collectionsPath"), library)

    return checks


def get_health_report() -> Dict[str, Any]:
    mappings = library_mappings.load_library_mappings()
    asset_root = os.environ.get("KAM_ASSETS_ROOT") or os.environ.get("ASSETS_ROOT") or "/assets"
    asset_mappings = [
        _directory_check(
            "asset-mapping",
            f"{mapping.get('library') or 'Library'} assets",
            mapping.get("assetPath"),
            require_write=True,
            library=str(mapping.get("library") or ""),
        )
        for mapping in mappings
    ]
    collection_paths = _collection_paths(mappings)

    collection_status = "ok"
    collection_detail = f"{len(collection_paths)} configured collection path"
    if len(collection_paths) != 1:
        collection_detail += "s"
    collection_detail += " checked."
    if not collection_paths:
        collection_status = "warning"
        collection_detail = "No collection path is configured yet."
    elif any(check["status"] == "error" for check in collection_paths):
        collection_status = "error"
        collection_detail = "One or more collection paths are not writable."

    checks = [
        _plex_check(),
        _directory_check("assets-root", "Assets root", asset_root, require_write=True),
        _result("collections", "Collections paths", collection_status, collection_detail),
        _config_check(),
    ]

    all_results = [*checks, *asset_mappings, *collection_paths]
    return {
        "ok": not any(result["status"] == "error" for result in all_results),
        "checks": checks,
        "assetMappings": asset_mappings,
        "collectionPaths": collection_paths,
    }
