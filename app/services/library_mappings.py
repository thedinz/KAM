"""Helpers for working with library mapping settings and caching."""
from __future__ import annotations

import copy
import os
import threading
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "normalize_path",
    "sanitize_library_mappings",
    "seed_from_env",
    "set_cached_mappings",
    "get_cached_mappings",
    "clear_cache",
]

_CACHE: Optional[List[Dict[str, Any]]] = None
_LOCK = threading.Lock()


def normalize_path(value: Any) -> str:
    """Return a trimmed, normalized path or an empty string."""
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = os.path.normpath(text)
    if normalized in (".", ""):
        return ""
    return normalized.replace("\\", "/")


def sanitize_library_mappings(raw: Any) -> List[Dict[str, Any]]:
    """Normalize arbitrary input into a deterministic list of mappings."""
    if not raw:
        return []

    items: Iterable[Dict[str, Any]]
    if isinstance(raw, dict):
        items = (
            {
                "library": key,
                "assetPath": value,
                "collectionsPath": None,
            }
            for key, value in raw.items()
        )
    elif isinstance(raw, list):
        items = (item for item in raw if isinstance(item, dict))
    else:
        return []

    ordered: Dict[str, Dict[str, Any]] = {}
    for item in items:
        library = str(item.get("library", "")) if item.get("library") is not None else ""
        library = library.strip()
        asset_path = normalize_path(item.get("assetPath"))
        collections_path = normalize_path(item.get("collectionsPath"))

        if not library or not asset_path:
            continue

        ordered[library] = {
            "library": library,
            "assetPath": asset_path,
            "collectionsPath": collections_path or None,
        }

    return [copy.deepcopy(value) for value in ordered.values()]


def seed_from_env() -> List[Dict[str, Any]]:
    """Return library mappings derived from the LIBRARIES/COLLECTIONS_ROOT envs."""
    env_raw = os.environ.get("LIBRARIES", "")
    collection_root = normalize_path(os.environ.get("COLLECTIONS_ROOT"))

    candidates = []
    for part in env_raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name, path = part.split(":", 1)
        candidates.append(
            {
                "library": name,
                "assetPath": path,
                "collectionsPath": collection_root or None,
            }
        )

    return sanitize_library_mappings(candidates)


def set_cached_mappings(mappings: List[Dict[str, Any]] | None) -> None:
    """Persist a copy of the mappings in memory for fast reuse."""
    global _CACHE
    with _LOCK:
        _CACHE = copy.deepcopy(mappings) if mappings is not None else None


def get_cached_mappings() -> Optional[List[Dict[str, Any]]]:
    """Return the cached mappings (if any)."""
    with _LOCK:
        return copy.deepcopy(_CACHE) if _CACHE is not None else None


def clear_cache() -> None:
    """Clear the cached mappings."""
    set_cached_mappings(None)
