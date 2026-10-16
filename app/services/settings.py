"""Helpers for persisting simple UI settings."""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from . import library_mappings, passwords

logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "plexUrl": "",
    "plexToken": "",
    "autoApplyToPlex": False,
    "authMode": "builtin",
    "authUsername": "",
    # A salted hash; the login password itself is never stored.
    "authPasswordHash": "",
    "libraryMappings": [],
}


def _iter_default_base_candidates() -> List[str]:
    """Return a prioritized list of storage roots to consider."""

    raw_candidates = (
        os.environ.get("KAM_STATE_ROOT"),
        os.environ.get("KAM_CONFIG_ROOT"),
        "/config",
        "/data",
    )
    candidates: List[str] = []
    for value in raw_candidates:
        if not value:
            continue
        normalized = str(value).strip()
        if normalized:
            candidates.append(normalized)
    if not candidates:
        candidates.append("/config")
    return candidates


def _resolve_initial_storage_path() -> str:
    """Determine the initial settings storage path with backwards compatibility."""

    env_override = os.environ.get("KAM_SETTINGS_PATH")
    if env_override and env_override.strip():
        return env_override

    candidates = _iter_default_base_candidates()
    filename = "settings.json"

    for base in candidates:
        candidate_path = os.path.join(base, filename)
        if os.path.isfile(candidate_path):
            return candidate_path

    return os.path.join(candidates[0], filename)


_STORAGE_PATH = _resolve_initial_storage_path()

_LOCK = threading.Lock()
# plain-text password from an older settings file -> its hash
_LEGACY_HASHES: Dict[str, str] = {}


def _normalize_auth_mode(value: Any) -> str:
    if value in (None, ""):
        return "builtin"
    text = str(value).strip().lower().replace("-", "_")
    if text in {"reverse_proxy", "proxy"}:
        return "reverse_proxy"
    return "builtin"


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def set_settings_path(path: str) -> None:
    """Override the JSON persistence path (primarily for tests)."""
    global _STORAGE_PATH
    _STORAGE_PATH = path
    logger.debug("Settings storage path set to %s", path)


def _get_storage_path() -> Path:
    return Path(_STORAGE_PATH)


def get_storage_path() -> Path:
    """Return the current settings JSON path."""
    return _get_storage_path()


def load_settings() -> Dict[str, Any]:
    """Return the stored settings merged with defaults."""
    with _LOCK:
        return _load_locked()


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Persist settings and return the stored payload merged with defaults.

    The login password and Plex token are write-only for the UI: a blank
    ``authPassword`` keeps the saved one, a blank ``plexToken`` keeps the saved
    one while ``plexUrl`` is unchanged, and a new password is stored only as a
    hash.
    """
    incoming = dict(data) if isinstance(data, dict) else {}
    password = str(incoming.pop("authPassword", None) or "").strip()
    incoming.pop("authPasswordHash", None)
    with _LOCK:
        current = _load_locked()
        sanitized = _sanitize_payload(incoming)
        sanitized["authPasswordHash"] = (
            passwords.hash_password(password) if password else current["authPasswordHash"]
        )
        # Keep the saved token only for the same Plex server, so changing the
        # URL can't send it somewhere new.
        same_server = str(sanitized.get("plexUrl") or "").strip() == str(
            current["plexUrl"] or ""
        ).strip()
        if not str(sanitized.get("plexToken") or "").strip() and same_server:
            sanitized["plexToken"] = current["plexToken"]
        merged = _merge_with_defaults(sanitized)
        _write_locked(merged)
        _clear_plex_cache()
        _clear_library_mapping_cache()
        return merged


def save_library_mappings(mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Persist only the library mappings while preserving other settings."""
    with _LOCK:
        sanitized = library_mappings.sanitize_library_mappings(mappings)
        current = _load_locked()
        current["libraryMappings"] = _clone_mappings(sanitized)
        _write_locked(current)
        _clear_plex_cache()
        _clear_library_mapping_cache()
        return copy.deepcopy(current)


def claim_auth_username(username: str) -> str:
    """Atomically save the first built-in-auth username and return the winner."""
    normalized = str(username).strip()
    if not normalized:
        return ""
    with _LOCK:
        current = _load_locked()
        existing = str(current.get("authUsername") or "").strip()
        if existing:
            return existing
        current["authUsername"] = normalized
        _write_locked(current)
        return normalized


def claim_auth_credentials(username: str, password: str) -> bool:
    """Atomically save the first built-in login; False if a password already exists."""
    with _LOCK:
        current = _load_locked()
        if current["authPasswordHash"]:
            return False
        current["authMode"] = "builtin"
        current["authUsername"] = str(username).strip()
        current["authPasswordHash"] = passwords.hash_password(str(password).strip())
        _write_locked(current)
        return True


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
    for key in (
        "theme",
        "plexUrl",
        "plexToken",
        "autoApplyToPlex",
        "authUsername",
        "authPasswordHash",
    ):
        if key in data:
            sanitized[key] = (
                _normalize_bool(data[key]) if key == "autoApplyToPlex" else data[key]
            )

    if "authMode" in data:
        sanitized["authMode"] = _normalize_auth_mode(data.get("authMode"))

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

    data = data if isinstance(data, dict) else {}
    migrated = _hash_legacy_password(data)
    merged = _merge_with_defaults(_sanitize_payload(data))
    if migrated:
        try:
            _write_locked(merged)
            logger.info("Stored the login password as a hash")
        except Exception as exc:
            logger.warning("Unable to save the hashed login password to %s: %s", path, exc)
    return merged


def _hash_legacy_password(data: Dict[str, Any]) -> bool:
    """Replace a plain-text password saved by KAM 8.0 or older with its hash.

    Returns whether the file still holds the old key and needs rewriting.
    """
    if "authPassword" not in data:
        return False
    legacy = str(data.pop("authPassword") or "").strip()
    if legacy and not str(data.get("authPasswordHash") or "").strip():
        # Reuse the hash if the file couldn't be rewritten, so each load
        # doesn't make a new one and sign everyone out.
        if legacy not in _LEGACY_HASHES:
            _LEGACY_HASHES[legacy] = passwords.hash_password(legacy)
        data["authPasswordHash"] = _LEGACY_HASHES[legacy]
    return True


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
        from . import plex as plex_service  # Local import to avoid circular dependency
        from . import plex_settings  # Local import to avoid circular dependency

        plex_settings.clear_cache()
        plex_service.clear_cache()
    except Exception:
        logger.debug("Unable to clear Plex settings cache", exc_info=True)


def _clear_library_mapping_cache() -> None:
    try:
        library_mappings.clear_cache()
    except Exception:
        logger.debug("Unable to clear library mapping cache", exc_info=True)


def _clone_mappings(mappings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(item) for item in mappings]
