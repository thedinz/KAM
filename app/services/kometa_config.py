"""Utilities for parsing Kometa configuration files."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, TypedDict

import yaml

from .library_mappings import normalize_path

__all__ = [
    "KometaLibraryInfo",
    "KometaCollectionOverride",
    "normalize_config_path",
    "extract_library_info",
    "load_library_summaries",
    "candidate_config_roots",
    "browse_config_locations",
]

logger = logging.getLogger(__name__)


class KometaCollectionOverride(TypedDict, total=False):
    """Named collection override discovered in the Kometa config."""

    name: str
    assetPath: str


class KometaLibraryInfo(TypedDict, total=False):
    """Summary of asset configuration for a single Kometa library."""

    assetPath: Optional[str]
    collectionsPaths: List[str]
    collectionOverrides: List[KometaCollectionOverride]


def normalize_config_path(value: Any, base_dir: Optional[Path] = None) -> str:
    """Return a sanitized path extracted from the Kometa config."""

    if value in (None, ""):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    expanded = os.path.expanduser(os.path.expandvars(text))
    normalized = normalize_path(expanded)
    if not normalized:
        return ""

    if base_dir:
        try:
            base = Path(base_dir)
        except TypeError:  # pragma: no cover - defensive
            base = None

        if base and not os.path.isabs(normalized):
            candidates: List[str] = []

            def _add_candidate(root: Path, fragment: str) -> None:
                try:
                    combined = root.joinpath(fragment)
                except Exception:  # pragma: no cover - defensive
                    return
                try:
                    combined = combined.resolve(strict=False)
                except Exception:  # pragma: no cover - defensive
                    pass
                candidate = normalize_path(str(combined))
                if candidate and candidate not in candidates:
                    candidates.append(candidate)

            name = base.name
            if name and normalized.startswith(f"{name}/"):
                trimmed = normalized[len(name) + 1 :]
                if trimmed:
                    _add_candidate(base, trimmed)

            _add_candidate(base, normalized)

            parent = base.parent
            if parent != base:
                _add_candidate(parent, normalized)

            for candidate in candidates:
                if os.path.exists(candidate):
                    return candidate

            if candidates:
                if isinstance(base, Path) and not base.is_absolute():
                    return normalized
                return candidates[0]

    return normalized


def _collect_asset_directories(value: Any, base_dir: Optional[Path]) -> Set[str]:
    """Return all asset_directory values found in *value*."""

    collected: Set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if "asset_directory" in node:
                path = normalize_config_path(node.get("asset_directory"), base_dir)
                if path:
                    collected.add(path)
            for child in node.values():
                _walk(child)
        elif isinstance(node, list):
            for child in node:
                _walk(child)

    _walk(value)
    return collected


def _normalize_override_name(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if not text:
        return ""

    cleaned = text.replace("_", " ").replace("-", " ").strip()
    if cleaned and cleaned.lower() == cleaned:
        cleaned = " ".join(part for part in cleaned.split())
        cleaned = cleaned.title()
    return cleaned or text


def _extract_override_entry(
    entry: Any, base_dir: Optional[Path], fallback_name: Optional[str] = None
) -> Optional[Tuple[str, str]]:
    if not isinstance(entry, dict):
        return None

    path = normalize_config_path(
        entry.get("asset_directory") or entry.get("asset_path"), base_dir
    )
    if not path:
        return None

    name_value = (
        entry.get("name")
        or entry.get("default")
        or entry.get("collection")
        or entry.get("template")
        or fallback_name
    )
    name = _normalize_override_name(name_value)
    if not name:
        return None

    return name, path


def _collect_overrides_from_collection_files(
    value: Any, base_dir: Optional[Path]
) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if isinstance(value, list):
        for entry in value:
            result = _extract_override_entry(entry, base_dir)
            if result:
                name, path = result
                overrides.setdefault(name, path)
    elif isinstance(value, dict):
        for key, entry in value.items():
            result = _extract_override_entry(entry, base_dir, str(key))
            if result:
                name, path = result
                overrides.setdefault(name, path)
    return overrides


def _collect_overrides_from_mapping(
    value: Any, base_dir: Optional[Path]
) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if isinstance(value, dict):
        for key, entry in value.items():
            result = _extract_override_entry(entry, base_dir, str(key))
            if result:
                name, path = result
                overrides.setdefault(name, path)
    return overrides


def extract_library_info(library_config: Any, base_dir: Optional[Path]) -> KometaLibraryInfo:
    """Return library asset information from a Kometa *library_config*."""

    info: KometaLibraryInfo = {}
    if not isinstance(library_config, dict):
        return info

    asset_path = normalize_config_path(library_config.get("asset_directory"), base_dir)
    if not asset_path:
        # Some configs may use "asset_path"; be generous.
        asset_path = normalize_config_path(library_config.get("asset_path"), base_dir)
    if asset_path:
        info["assetPath"] = asset_path

    collections_paths: Set[str] = set()

    for key in (
        "collection_files",
        "collection_defaults",
        "collections",
        "dynamic_collections",
    ):
        if key in library_config:
            paths = _collect_asset_directories(library_config.get(key), base_dir)
            collections_paths.update(paths)

    if collections_paths:
        info["collectionsPaths"] = sorted(collections_paths)

    overrides: Dict[str, str] = {}
    overrides.update(
        _collect_overrides_from_collection_files(
            library_config.get("collection_files"), base_dir
        )
    )
    overrides.update(
        _collect_overrides_from_mapping(
            library_config.get("collections"), base_dir
        )
    )
    overrides.update(
        _collect_overrides_from_mapping(
            library_config.get("dynamic_collections"), base_dir
        )
    )

    if overrides:
        info["collectionOverrides"] = [
            {"name": name, "assetPath": path}
            for name, path in sorted(overrides.items(), key=lambda item: item[0].lower())
        ]

    return info


def load_library_summaries(path: str | os.PathLike[str] | None) -> Dict[str, KometaLibraryInfo]:
    """Parse the Kometa config at *path* and return library summaries."""

    if not path:
        return {}

    normalized_path = normalize_config_path(path)
    if not normalized_path:
        return {}

    config_path = Path(normalized_path)
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.debug("Kometa config file not found: %s", config_path)
        return {}
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to read Kometa config %s: %s", config_path, exc)
        return {}

    try:
        data = yaml.safe_load(raw) or {}
    except Exception as exc:
        logger.warning("Invalid YAML in Kometa config %s: %s", config_path, exc)
        return {}

    if not isinstance(data, dict):
        return {}

    libraries_section = data.get("libraries")
    if not isinstance(libraries_section, dict):
        return {}

    base_dir = config_path.parent
    results: Dict[str, KometaLibraryInfo] = {}
    for name, config in libraries_section.items():
        if not isinstance(name, str) or not name.strip():
            continue
        info = extract_library_info(config, base_dir)
        if info:
            results[name.strip()] = info
        else:
            # Ensure libraries are represented even if no directories were found.
            results[name.strip()] = {}

    return results


def _nearest_existing_dir(path: Path) -> Optional[Path]:
    """Return the closest existing directory for *path* (including parents)."""

    try:
        candidate = path.resolve(strict=False)
    except Exception:  # pragma: no cover - defensive
        candidate = path

    visited: Set[Path] = set()
    current = candidate
    while True:
        if current in visited:
            break
        visited.add(current)
        if current.exists():
            if current.is_dir():
                try:
                    return current.resolve()
                except Exception:  # pragma: no cover - best-effort resolution
                    return current
            if current.is_file():
                current = current.parent
                continue
        parent = current.parent
        if parent == current:
            break
        current = parent

    if current.exists() and current.is_dir():
        try:
            return current.resolve()
        except Exception:  # pragma: no cover - best-effort resolution
            return current
    return None


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    seen: Set[str] = set()
    result: List[Path] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except Exception:  # pragma: no cover - defensive
            resolved = path
        key = resolved.as_posix()
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return result


def candidate_config_roots(
    current: str | os.PathLike[str] | None = None,
) -> List[Path]:
    """Return possible base directories to browse for Kometa configs."""

    raw_candidates: List[str] = []
    if current:
        normalized_current = normalize_config_path(current)
        if normalized_current:
            raw_candidates.append(normalized_current)

    try:
        from . import settings as settings_service  # Local import to avoid circular

        stored_path = settings_service.load_settings().get("kometaConfigPath")
        if stored_path:
            normalized_stored = normalize_config_path(stored_path)
            if normalized_stored:
                raw_candidates.append(normalized_stored)
    except Exception:  # pragma: no cover - defensive
        logger.debug("Unable to load stored Kometa config path", exc_info=True)

    env_path = os.environ.get("KOMETA_CONFIG_PATH")
    if env_path:
        normalized_env = normalize_config_path(env_path)
        if normalized_env:
            raw_candidates.append(normalized_env)

    # Provide sensible defaults inside containers where Kometa configs are often mounted.
    raw_candidates.extend(["/config", "/configs", "/etc", "/data"])

    directories: List[Path] = []
    for raw in raw_candidates:
        try:
            candidate = Path(raw)
        except TypeError:  # pragma: no cover - defensive
            continue
        existing = _nearest_existing_dir(candidate)
        if existing:
            directories.append(existing)

    if not directories:
        fallback = _nearest_existing_dir(Path.cwd())
        if fallback:
            directories.append(fallback)

    return _dedupe_paths(directories)


def _ensure_within_root(root: Path, target: Path) -> Path:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError("Invalid path outside Kometa config root")
    return target_resolved


def browse_config_locations(
    *,
    parent: str | None = None,
    search: str | None = None,
    current: str | os.PathLike[str] | None = None,
) -> Dict[str, Any]:
    """Return directory contents suitable for browsing Kometa config files."""

    normalized_current = normalize_config_path(current)
    roots = candidate_config_roots(normalized_current)
    if not roots:
        raise FileNotFoundError("No Kometa config directories are available")

    root = roots[0]
    root_resolved = root.resolve()

    parent_value = normalize_path(parent) if parent else ""
    if parent_value in (".", ""):
        parent_value = ""

    if parent_value:
        parent_path = Path(parent_value)
        if any(part == ".." for part in parent_path.parts):
            raise ValueError("Invalid parent path")
        candidate_dir = (root_resolved / parent_path).resolve()
        candidate_dir = _ensure_within_root(root_resolved, candidate_dir)
        if not candidate_dir.exists() or not candidate_dir.is_dir():
            raise FileNotFoundError("Directory not found")
        current_dir = candidate_dir
    else:
        current_dir = root_resolved

    selection_rel = ""

    if not parent_value and normalized_current:
        current_path = Path(normalized_current)
        try:
            current_resolved = current_path.resolve(strict=False)
        except Exception:  # pragma: no cover - defensive
            current_resolved = current_path
        try:
            rel_to_root = current_resolved.relative_to(root_resolved)
        except ValueError:
            rel_to_root = None

        if rel_to_root is not None:
            candidate_dir = current_resolved
            if candidate_dir.exists() and candidate_dir.is_dir():
                current_dir = candidate_dir
                parent_value = rel_to_root.as_posix()
                if parent_value == ".":
                    parent_value = ""
            else:
                selection_rel = rel_to_root.as_posix()
                if selection_rel == ".":
                    selection_rel = ""
                candidate_parent = current_resolved.parent
                while True:
                    try:
                        rel_parent = candidate_parent.relative_to(root_resolved)
                    except ValueError:
                        break
                    if candidate_parent.exists() and candidate_parent.is_dir():
                        current_dir = candidate_parent
                        parent_value = rel_parent.as_posix()
                        if parent_value == ".":
                            parent_value = ""
                        break
                    if candidate_parent == root_resolved:
                        current_dir = root_resolved
                        parent_value = ""
                        break
                    candidate_parent = candidate_parent.parent

    try:
        current_dir = _ensure_within_root(root_resolved, current_dir)
    except ValueError as exc:
        raise ValueError(str(exc))

    if not current_dir.exists() or not current_dir.is_dir():
        raise FileNotFoundError("Directory not found")

    term = (search or "").strip().lower()
    items: List[Dict[str, Any]] = []

    try:
        if term:
            matches: List[Path] = []
            for child in current_dir.rglob("*"):
                try:
                    name_lower = child.name.lower()
                    is_valid = child.is_dir() or child.is_file()
                except PermissionError:
                    continue
                if term not in name_lower or not is_valid:
                    continue
                try:
                    resolved_child = child.resolve()
                    resolved_child.relative_to(root_resolved)
                except (OSError, ValueError):
                    continue
                matches.append(resolved_child)
            matches.sort(
                key=lambda p: (not p.is_dir(), str(p.relative_to(root_resolved)).lower())
            )
            for child in matches:
                rel_path = child.relative_to(root_resolved)
                rel_text = rel_path.as_posix()
                if rel_text == ".":
                    rel_text = ""
                items.append(
                    {
                        "name": child.name,
                        "path": rel_text,
                        "isDir": child.is_dir(),
                        "isFile": child.is_file(),
                    }
                )
        else:
            entries = sorted(
                current_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
            for child in entries:
                try:
                    resolved_child = child.resolve()
                    resolved_child.relative_to(root_resolved)
                except (OSError, ValueError):
                    continue
                rel_path = resolved_child.relative_to(root_resolved)
                rel_text = rel_path.as_posix()
                if rel_text == ".":
                    rel_text = ""
                items.append(
                    {
                        "name": child.name,
                        "path": rel_text,
                        "isDir": resolved_child.is_dir(),
                        "isFile": resolved_child.is_file(),
                    }
                )
    except PermissionError:
        raise PermissionError("Permission denied")

    parent_value = parent_value or ""

    return {
        "root": root_resolved.as_posix(),
        "parent": parent_value,
        "items": items,
        "selection": selection_rel or None,
    }

