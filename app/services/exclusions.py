"""Helpers for persisting per-item exclusion preferences."""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

_DEF_BASE = (
    os.environ.get("KAM_STATE_ROOT")
    or os.environ.get("KAM_CONFIG_ROOT")
    or "/data"
)
_STORAGE_PATH = os.environ.get("KAM_EXCLUSIONS_PATH") or os.path.join(
    _DEF_BASE, "exclusions.json"
)

_VALID_TYPES = {"movie", "show", "collection"}


def set_storage_path(path: str) -> None:
    """Override the JSON persistence path (primarily for tests)."""

    global _STORAGE_PATH
    _STORAGE_PATH = path
    logger.debug("Exclusions storage path set to %s", path)


def _get_storage_path() -> Path:
    return Path(_STORAGE_PATH)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"series", "tv", "tv show", "television"}:
        text = "show"
    if text in {"collection", "collections", "collection set"}:
        text = "collection"
    if text not in _VALID_TYPES:
        return None
    return text


def _normalize_title(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_year(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        year = int(str(value).strip())
    except Exception:
        return None
    if year <= 0:
        return None
    return year


def _normalize_rating_key(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_library(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_timestamp(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _now_iso()


def _sanitize_entry(entry: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(entry, dict):
        return None

    library = _normalize_library(entry.get("library"))
    rating_key = _normalize_rating_key(entry.get("ratingKey"))
    item_type = _normalize_type(entry.get("type"))

    if not library or not rating_key or not item_type:
        return None

    sanitized: Dict[str, Any] = {
        "library": library,
        "ratingKey": rating_key,
        "type": item_type,
        "excludedAt": _normalize_timestamp(entry.get("excludedAt")),
    }

    title = _normalize_title(entry.get("title"))
    if title:
        sanitized["title"] = title

    year = _normalize_year(entry.get("year"))
    if year:
        sanitized["year"] = year

    return sanitized


def _load_locked() -> List[Dict[str, Any]]:
    path = _get_storage_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning("Unable to read exclusions file %s: %s", path, exc)
        return []

    try:
        data = json.loads(raw) or []
    except Exception as exc:
        logger.warning("Invalid JSON in exclusions file %s: %s", path, exc)
        return []

    if not isinstance(data, list):
        return []

    sanitized: List[Dict[str, Any]] = []
    for entry in data:
        clean = _sanitize_entry(entry)
        if clean:
            sanitized.append(clean)
    return sanitized


def _write_locked(entries: List[Dict[str, Any]]) -> None:
    path = _get_storage_path()
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.warning("Unable to create exclusions parent %s: %s", parent, exc)

    payload = sorted(
        entries,
        key=lambda item: (
            item.get("library", "").lower(),
            item.get("type", ""),
            item.get("title", "").lower(),
            item.get("ratingKey", ""),
        ),
    )

    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def list_exclusions() -> List[Dict[str, Any]]:
    """Return all stored exclusions."""

    with _LOCK:
        data = _load_locked()
        return [dict(entry) for entry in data]


def is_excluded(library: str, rating_key: str) -> bool:
    library_norm = _normalize_library(library)
    rating_norm = _normalize_rating_key(rating_key)
    if not library_norm or not rating_norm:
        return False

    with _LOCK:
        for entry in _load_locked():
            if entry["library"] == library_norm and entry["ratingKey"] == rating_norm:
                return True
    return False


def add_exclusion(
    library: str,
    rating_key: str,
    item_type: str,
    *,
    title: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """Store an exclusion and return the persisted payload."""

    library_norm = _normalize_library(library)
    rating_norm = _normalize_rating_key(rating_key)
    type_norm = _normalize_type(item_type)

    if not library_norm:
        raise ValueError("library is required")
    if not rating_norm:
        raise ValueError("rating_key is required")
    if not type_norm:
        raise ValueError("type must be movie, show, or collection")

    payload = {
        "library": library_norm,
        "ratingKey": rating_norm,
        "type": type_norm,
        "title": _normalize_title(title),
        "year": _normalize_year(year),
        "excludedAt": _now_iso(),
    }

    # Remove ``None`` values so the JSON stays tidy
    payload = {k: v for k, v in payload.items() if v is not None}

    with _LOCK:
        entries = _load_locked()
        filtered = [
            entry
            for entry in entries
            if not (
                entry["library"] == library_norm
                and entry["ratingKey"] == rating_norm
            )
        ]
        filtered.append(payload)
        _write_locked(filtered)

    logger.debug(
        "Stored exclusion: library=%s ratingKey=%s type=%s", library_norm, rating_norm, type_norm
    )
    return dict(payload)


def remove_exclusion(library: str, rating_key: str) -> bool:
    library_norm = _normalize_library(library)
    rating_norm = _normalize_rating_key(rating_key)
    if not library_norm or not rating_norm:
        return False

    removed = False
    with _LOCK:
        entries = _load_locked()
        filtered: List[Dict[str, Any]] = []
        for entry in entries:
            if entry["library"] == library_norm and entry["ratingKey"] == rating_norm:
                removed = True
                continue
            filtered.append(entry)
        if removed:
            _write_locked(filtered)

    if removed:
        logger.debug(
            "Removed exclusion: library=%s ratingKey=%s", library_norm, rating_norm
        )
    return removed
