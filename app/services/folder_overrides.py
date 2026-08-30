"""Persistence helpers for per-item folder overrides."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Collection, Dict, Mapping, Optional

from .resolve import resolve_existing_dir_or_422

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def _iter_default_base_candidates() -> list[str]:
    """Return a prioritized list of directories for storing overrides."""

    raw_candidates = (
        os.environ.get("KAM_STATE_ROOT"),
        os.environ.get("KAM_CONFIG_ROOT"),
        "/config",
        os.environ.get("KAM_LEGACY_STATE_ROOT"),
        "/data",
    )

    candidates: list[str] = []
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
    """Determine the initial storage path, preferring existing files."""

    env_override = os.environ.get("KAM_FOLDER_OVERRIDES_PATH")
    if env_override and env_override.strip():
        return env_override

    filename = "folder_overrides.json"
    candidates = _iter_default_base_candidates()

    for base in candidates:
        candidate_path = os.path.join(base, filename)
        if os.path.isfile(candidate_path):
            return candidate_path

    return os.path.join(candidates[0], filename)


_STORAGE_PATH = _resolve_initial_storage_path()


def set_storage_path(path: str) -> None:
    """Override the JSON persistence path (primarily for tests)."""
    global _STORAGE_PATH
    _STORAGE_PATH = path
    logger.debug("Folder overrides storage path set to %s", path)


def _get_storage_path() -> Path:
    return Path(_STORAGE_PATH)


def _storage_read_paths() -> list[Path]:
    paths: list[Path] = []

    primary = _get_storage_path()
    paths.append(primary)

    if os.environ.get("KAM_FOLDER_OVERRIDES_PATH"):
        return paths

    filename = "folder_overrides.json"
    for base in _iter_default_base_candidates():
        candidate = Path(base) / filename
        if candidate not in paths:
            paths.append(candidate)

    return paths


def _parse_payload(raw: str, path: Path) -> Dict[str, Dict[str, str]]:
    try:
        data = json.loads(raw) or {}
    except Exception as exc:
        logger.warning("Invalid JSON in folder overrides file %s: %s", path, exc)
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for lib, entries in data.items():
        if isinstance(lib, str) and isinstance(entries, dict):
            out[lib] = {str(k): str(v) for k, v in entries.items() if v is not None}
    return out


def _read_file(path: Path) -> Dict[str, Dict[str, str]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("Unable to read folder overrides file %s: %s", path, exc)
        return {}
    return _parse_payload(raw, path)


def _merge_payloads(payloads: list[Dict[str, Dict[str, str]]]) -> Dict[str, Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    for payload in reversed(payloads):
        for library, entries in payload.items():
            if not entries:
                continue
            target = merged.setdefault(library, {})
            target.update(entries)
    return merged


def _load_locked() -> Dict[str, Dict[str, str]]:
    payloads = [_read_file(path) for path in _storage_read_paths()]
    return _merge_payloads(payloads)


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


def get_library_overrides(library: str) -> Dict[str, str]:
    """Return all stored folder overrides for a library."""

    if not library:
        return {}
    with _LOCK:
        data = _load_locked()
        return dict(data.get(library, {}))


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


def set_canonical_overrides(library: str, assignments: Mapping[str, str]) -> Dict[str, str]:
    """Persist already-validated ratingKey -> canonical folder overrides in one write."""

    if not library:
        raise ValueError("library is required")

    cleaned: Dict[str, str] = {}
    for rating_key, folder_name in assignments.items():
        key = str(rating_key or "").strip()
        name = str(folder_name or "")
        if key and name.strip():
            cleaned[key] = name

    if not cleaned:
        return {}

    with _LOCK:
        data = _load_locked()
        lib_entries = data.setdefault(library, {})
        lib_entries.update(cleaned)
        _write_locked(data)

    logger.debug(
        "Stored %d folder overrides for library=%s",
        len(cleaned),
        library,
    )
    return dict(cleaned)


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


def clear_overrides_for_folders(library: str, folder_names: Collection[str]) -> int:
    """Remove stale overrides that point at folders deleted from a library."""

    if not library or not folder_names:
        return 0
    # These are canonical filesystem names, so compare them exactly. Linux can
    # contain two distinct directories whose names differ only by case.
    targets = {str(name) for name in folder_names if str(name).strip()}
    if not targets:
        return 0

    removed = 0
    with _LOCK:
        data = _load_locked()
        lib_entries = data.get(library)
        if not lib_entries:
            return 0
        for rating_key, folder_name in list(lib_entries.items()):
            if str(folder_name) not in targets:
                continue
            lib_entries.pop(rating_key, None)
            removed += 1
        if removed:
            if not lib_entries:
                data.pop(library, None)
            _write_locked(data)

    if removed:
        logger.debug(
            "Cleared %d stale folder overrides for library=%s",
            removed,
            library,
        )
    return removed
