"""Helpers for persisting simple UI settings."""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from . import library_mappings

logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "plexUrl": os.environ.get("PLEX_URL") or "",
    "plexToken": os.environ.get("PLEX_TOKEN") or "",
    "libraryMappings": library_mappings.seed_from_env(),
}

_DEF_BASE = (
    os.environ.get("KAM_STATE_ROOT")
    or os.environ.get("KAM_CONFIG_ROOT")
    or "/data"
)
_STORAGE_PATH = os.environ.get("KAM_SETTINGS_PATH") or os.path.join(
    _DEF_BASE, "settings.json"
)

_LOCK = threading.Lock()


def set_settings_path(path: str) -> None:
    """Override the JSON persistence path (primarily for tests)."""
    global _STORAGE_PATH
    _STORAGE_PATH = path
    logger.debug("Settings storage path set to %s", path)


def _get_storage_path() -> Path:
    return Path(_STORAGE_PATH)


def load_settings() -> Dict[str, Any]:
    """Return the stored settings merged with defaults."""
    with _LOCK:
        return _load_locked()


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Persist settings and return the stored payload merged with defaults."""
    with _LOCK:
        sanitized = _sanitize_payload(data)
        merged = _merge_with_defaults(sanitized)
        _write_locked(merged)
        _clear_plex_cache()
        _clear_library_mapping_cache()
        return merged


def _merge_with_defaults(data: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = copy.deepcopy(_DEFAULT_SETTINGS)
    if data:
        for key, value in data.items():
            if key == "libraryMappings" and isinstance(value, list):
                merged[key] = _clone_mappings(value)
            else:
                merged[key] = value
    return merged


def _sanitize_payload(data: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}

    sanitized: Dict[str, Any] = {}
    for key in ("theme", "plexUrl", "plexToken"):
        if key in data:
            sanitized[key] = data[key]

    if "libraryMappings" in data:
        sanitized["libraryMappings"] = library_mappings.sanitize_library_mappings(
            data.get("libraryMappings")
        )

    return sanitized


def _load_locked() -> Dict[str, Any]:
    path = _get_storage_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return copy.deepcopy(_DEFAULT_SETTINGS)
    except Exception as exc:
        logger.warning("Unable to read settings file %s: %s", path, exc)
        return copy.deepcopy(_DEFAULT_SETTINGS)

    try:
        data = json.loads(raw) or {}
    except Exception as exc:
        logger.warning("Invalid JSON in settings file %s: %s", path, exc)
        data = {}

    sanitized = _sanitize_payload(data if isinstance(data, dict) else {})
    return _merge_with_defaults(sanitized)


def _write_locked(data: Dict[str, Any]) -> None:
    path = _get_storage_path()
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.warning("Unable to create settings parent %s: %s", parent, exc)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )
    tmp_path.replace(path)


def _clear_plex_cache() -> None:
    try:
        from . import plex_settings  # Local import to avoid circular dependency

        plex_settings.clear_cache()
    except Exception:
        logger.debug("Unable to clear Plex settings cache", exc_info=True)


def _clear_library_mapping_cache() -> None:
    try:
        library_mappings.clear_cache()
    except Exception:
        logger.debug("Unable to clear library mapping cache", exc_info=True)


def _clone_mappings(mappings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(item) for item in mappings]
