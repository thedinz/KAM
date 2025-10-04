"""Helpers for persisting simple UI settings."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS: Dict[str, Any] = {"theme": "dark"}

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
        merged = _merge_with_defaults(data)
        _write_locked(merged)
        return merged


def _merge_with_defaults(data: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = dict(_DEFAULT_SETTINGS)
    if data:
        for key, value in data.items():
            merged[key] = value
    return merged


def _load_locked() -> Dict[str, Any]:
    path = _get_storage_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return dict(_DEFAULT_SETTINGS)
    except Exception as exc:
        logger.warning("Unable to read settings file %s: %s", path, exc)
        return dict(_DEFAULT_SETTINGS)

    try:
        data = json.loads(raw) or {}
    except Exception as exc:
        logger.warning("Invalid JSON in settings file %s: %s", path, exc)
        data = {}

    return _merge_with_defaults(data if isinstance(data, dict) else {})


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
