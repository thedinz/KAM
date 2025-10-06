"""Utilities for working with Kometa configuration paths."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from .library_mappings import normalize_path

__all__ = [
    "normalize_config_path",
    "candidate_config_roots",
    "browse_config_locations",
]

logger = logging.getLogger(__name__)


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

