"""Helpers for working with library mapping settings and caching."""
from __future__ import annotations

import copy
import os
import threading
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "normalize_path",
    "normalize_collection_sections",
    "sanitize_library_mappings",
    "set_cached_mappings",
    "get_cached_mappings",
    "clear_cache",
    "load_library_mappings",
    "get_library_map",
    "get_library_entry",
    "get_asset_path",
    "get_collections_path",
    "allowed_roots",
    "is_allowed_path",
    "disallowed_paths",
]

_CACHE: Optional[List[Dict[str, Any]]] = None
_LOCK = threading.Lock()


def _normalize_env_path(value: Any) -> str:
    """Return a normalized absolute path for environment-derived values."""

    if value in (None, ""):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = os.path.normpath(text)
    if normalized in (".", ""):
        return ""
    return normalized.replace("\\", "/")


def _compute_expected_assets_root() -> str:
    """Determine the container assets root using current environment hints."""

    for key in ("KAM_ASSETS_ROOT", "ASSETS_ROOT"):
        candidate = _normalize_env_path(os.environ.get(key))
        if candidate:
            return candidate

    collections_root = _normalize_env_path(os.environ.get("COLLECTIONS_ROOT"))
    if collections_root:
        parent = _normalize_env_path(os.path.dirname(collections_root))
        if parent:
            return parent

    return "/assets"


def _compute_legacy_roots(expected_root: str) -> List[str]:
    """Return possible legacy assets roots that should be remapped."""

    legacy_candidates = []
    for key in ("KAM_LEGACY_ASSETS_ROOT", "LEGACY_ASSETS_ROOT"):
        candidate = _normalize_env_path(os.environ.get(key))
        if candidate and candidate not in legacy_candidates:
            legacy_candidates.append(candidate)

    for default in ("/app", "/app/assets"):
        normalized = _normalize_env_path(default)
        if normalized and normalized not in legacy_candidates:
            legacy_candidates.append(normalized)

    # Never treat the expected root as legacy even if hints include it.
    filtered = [root for root in legacy_candidates if root and root != expected_root]
    filtered.sort(key=len, reverse=True)
    return filtered


_EXPECTED_ASSETS_ROOT = _compute_expected_assets_root()
_LEGACY_ASSETS_ROOTS = _compute_legacy_roots(_EXPECTED_ASSETS_ROOT)


def _remap_legacy_root(path: str) -> str:
    """Rebase legacy asset paths onto the expected assets root."""

    if not path:
        return path

    expected = _EXPECTED_ASSETS_ROOT
    if not expected:
        return path

    normalized_expected = expected.rstrip("/") or "/"

    for legacy_root in _LEGACY_ASSETS_ROOTS:
        if not legacy_root:
            continue
        legacy_normalized = legacy_root.rstrip("/") or "/"
        if path == legacy_normalized:
            return normalized_expected
        legacy_prefix = legacy_normalized + "/"
        if path.startswith(legacy_prefix):
            suffix = path[len(legacy_normalized) :]
            combined = normalized_expected + suffix
            remapped = os.path.normpath(combined).replace("\\", "/")
            return remapped

    return path


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
    normalized = normalized.replace("\\", "/")

    if _LEGACY_ASSETS_ROOTS:
        remapped = _remap_legacy_root(normalized)
        if remapped != normalized:
            normalized = remapped
            if normalized in (".", ""):
                return ""

    return normalized


def allowed_roots() -> List[str]:
    """Return the mounted folders that library mappings may point into.

    Mappings arrive through the settings API, so they must stay inside the
    asset mounts instead of reaching anywhere in the container.
    """

    roots = [_compute_expected_assets_root()]
    collections_root = _normalize_env_path(os.environ.get("COLLECTIONS_ROOT"))
    if collections_root:
        roots.append(collections_root)
    return [root for root in dict.fromkeys(roots) if root]


def is_allowed_path(value: Any) -> bool:
    """Return whether *value* is an absolute path inside an allowed root."""

    text = str(value or "").strip()
    if not text or not os.path.isabs(text):
        return False
    target = os.path.normcase(os.path.realpath(text))
    for root in allowed_roots():
        base = os.path.normcase(os.path.realpath(root))
        if target == base or target.startswith(base.rstrip(os.sep) + os.sep):
            return True
    return False


def _allowed(path: str) -> Optional[str]:
    return path if path and is_allowed_path(path) else None


def _mapping_paths(mappings: Iterable[Dict[str, Any]]) -> List[str]:
    paths: List[str] = []
    for entry in mappings or []:
        for key in ("assetPath", "collectionsPath"):
            path = normalize_path(entry.get(key))
            if path:
                paths.append(path)
        for section in entry.get("collectionSections") or []:
            path = normalize_path(section.get("collectionsPath"))
            if path:
                paths.append(path)
    return paths


def disallowed_paths(
    mappings: Iterable[Dict[str, Any]],
    previous: Iterable[Dict[str, Any]] = (),
) -> List[str]:
    """Return new mapping paths that fall outside the allowed roots.

    Paths already saved in *previous* are left alone so older settings can
    still be saved; they are ignored when KAM resolves folders.
    """

    existing = set(_mapping_paths(previous))
    return [
        path
        for path in dict.fromkeys(_mapping_paths(mappings))
        if path not in existing and not is_allowed_path(path)
    ]


def normalize_collection_sections(value: Any) -> List[Dict[str, str]]:
    """Normalize collection override mappings into a sorted list."""

    if not value:
        return []

    items: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        for key, entry in value.items():
            if isinstance(entry, dict):
                candidate = dict(entry)
            else:
                candidate = {"collectionsPath": entry}
            candidate.setdefault("name", key)
            items.append(candidate)
    elif isinstance(value, list):
        items = [dict(entry) for entry in value if isinstance(entry, dict)]
    else:
        return []

    ordered: Dict[str, Dict[str, str]] = {}
    for item in items:
        raw_name = item.get("name") or item.get("section") or item.get("default") or item.get("key")
        if raw_name in (None, ""):
            continue
        name = str(raw_name).strip()
        if not name:
            continue
        path = normalize_path(
            item.get("collectionsPath")
            or item.get("path")
            or item.get("assetPath")
            or item.get("asset_directory")
        )
        if not path:
            continue
        ordered[name] = {"name": name, "collectionsPath": path}

    return [ordered[key] for key in sorted(ordered.keys(), key=lambda s: s.lower())]


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
        sections = normalize_collection_sections(
            item.get("collectionSections") or item.get("collectionOverrides")
        )

        if not library or not asset_path:
            continue

        ordered[library] = {
            "library": library,
            "assetPath": asset_path,
            "collectionsPath": collections_path or None,
        }
        if sections:
            ordered[library]["collectionSections"] = sections

    return [copy.deepcopy(value) for value in ordered.values()]


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


def _load_from_settings() -> List[Dict[str, Any]]:
    """Return sanitized mappings from persisted settings."""
    try:
        from . import settings as settings_service  # Local import to avoid cycle

        payload = settings_service.load_settings()
        raw = payload.get("libraryMappings") if isinstance(payload, dict) else None
    except Exception:
        raw = None

    mappings = sanitize_library_mappings(raw)
    return mappings


def load_library_mappings() -> List[Dict[str, Any]]:
    """Return sanitized library mappings from settings (cached)."""
    cached = get_cached_mappings()
    if cached is not None:
        return cached

    mappings = _load_from_settings()
    set_cached_mappings(mappings)
    return copy.deepcopy(mappings)


def get_library_map() -> Dict[str, Dict[str, Any]]:
    """Return a library -> mapping lookup."""
    mappings = load_library_mappings()
    lookup: Dict[str, Dict[str, Any]] = {}
    for item in mappings:
        library = str(item.get("library") or "")
        if not library:
            continue
        lookup[library] = dict(item)
    return lookup


def get_library_entry(library: str | None) -> Optional[Dict[str, Any]]:
    """Return the mapping entry for *library* (if any)."""
    if library is None:
        return None
    key = str(library).strip()
    if not key:
        return None
    mapping = get_library_map().get(key)
    return dict(mapping) if mapping else None


def get_asset_path(library: str) -> Optional[str]:
    """Return the configured asset path for *library* (if any)."""
    entry = get_library_entry(library)
    if not entry:
        return None
    path = normalize_path(entry.get("assetPath"))
    return _allowed(path)


def _default_collections_root() -> Optional[str]:
    env_root = _normalize_env_path(os.environ.get("COLLECTIONS_ROOT"))
    if env_root:
        return env_root

    assets_root = _EXPECTED_ASSETS_ROOT or "/assets"
    return _normalize_env_path(os.path.join(assets_root, "Collections"))


def _section_override_path(entry: Dict[str, Any], library: str) -> Optional[str]:
    """Return a collectionsPath override within *entry* matching *library*."""

    if not entry or not library:
        return None

    raw_sections = entry.get("collectionSections")
    if not raw_sections:
        return None

    library_key = library.casefold()
    for section in raw_sections:
        name = str(section.get("name") or "").strip()
        if not name:
            continue
        if name.casefold() != library_key:
            continue
        path = _allowed(normalize_path(section.get("collectionsPath")))
        if path:
            return path

    return None


def get_collections_path(library: Optional[str] = None) -> Optional[str]:
    """Return the collections path for *library* or the global default."""
    if library:
        entry = get_library_entry(library)
        if entry:
            path = _allowed(normalize_path(entry.get("collectionsPath")))
            if path:
                return path
            override = _section_override_path(entry, library)
            if override:
                return override

    explicit = get_library_entry("Collections")
    if explicit:
        if library:
            override = _section_override_path(explicit, library)
            if override:
                return override
        explicit_coll = _allowed(
            normalize_path(explicit.get("collectionsPath") or explicit.get("assetPath"))
        )
        if explicit_coll:
            return explicit_coll

    fallback = _default_collections_root()
    if fallback:
        return fallback

    for entry in load_library_mappings():
        if library:
            override = _section_override_path(entry, library)
            if override:
                return override
        candidate = _allowed(normalize_path(entry.get("collectionsPath")))
        if candidate:
            return candidate
    return None
