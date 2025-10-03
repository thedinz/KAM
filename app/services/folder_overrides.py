"""Persistence helpers for per-item folder overrides."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional

from .resolve import resolve_existing_dir_or_422

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

_DEF_BASE = (
    os.environ.get("KAM_STATE_ROOT")
    or os.environ.get("KAM_CONFIG_ROOT")
    or "/data"
)
_STORAGE_PATH = os.environ.get("KAM_FOLDER_OVERRIDES_PATH") or os.path.join(
    _DEF_BASE, "folder_overrides.json"
)


def set_storage_path(path: str) -> None:
    """Override the JSON persistence path (primarily for tests)."""
    global _STORAGE_PATH
    _STORAGE_PATH = path
    logger.debug("Folder overrides storage path set to %s", path)


def _get_storage_path() -> Path:
    return Path(_STORAGE_PATH)


def _load_locked() -> Dict[str, Dict[str, str]]:
    path = _get_storage_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("Unable to read folder overrides file %s: %s", path, exc)
        return {}
    try:
        data = json.loads(raw) or {}
    except Exception as exc:
        logger.warning("Invalid JSON in folder overrides file %s: %s", path, exc)
        return {}
    # ensure nested dicts
    out: Dict[str, Dict[str, str]] = {}
    for lib, entries in data.items():
        if isinstance(lib, str) and isinstance(entries, dict):
            out[lib] = {str(k): str(v) for k, v in entries.items() if v is not None}
    return out


def _write_locked(data: Dict[str, Dict[str, str]]) -> None:
    path = _get_storage_path()
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.warning("Unable to create folder overrides parent %s: %s", parent, exc)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def get_override(library: str, rating_key: str) -> Optional[str]:
    if not library or not rating_key:
        return None
    key = str(rating_key)
    with _LOCK:
        data = _load_locked()
        return data.get(library, {}).get(key)


def set_override(library: str, rating_key: str, folder_name: str) -> str:
    if not library:
        raise ValueError("library is required")
    if not rating_key:
        raise ValueError("rating_key is required")
    if not folder_name:
        raise ValueError("folder_name is required")

    resolved = resolve_existing_dir_or_422(library, folder_name)
    canonical = os.path.basename(os.path.normpath(resolved))

    key = str(rating_key)
    with _LOCK:
        data = _load_locked()
        lib_entries = data.setdefault(library, {})
        lib_entries[key] = canonical
        _write_locked(data)
    logger.debug(
        "Stored folder override: library=%s ratingKey=%s -> %s",
        library,
        key,
        canonical,
    )
    return canonical


def clear_override(library: str, rating_key: str) -> bool:
    if not library or not rating_key:
        return False
    key = str(rating_key)
    removed = False
    with _LOCK:
        data = _load_locked()
        lib_entries = data.get(library)
        if lib_entries and key in lib_entries:
            removed = True
            lib_entries.pop(key, None)
            if not lib_entries:
                data.pop(library, None)
            _write_locked(data)
    if removed:
        logger.debug(
            "Cleared folder override: library=%s ratingKey=%s",
            library,
            key,
        )
    return removed
