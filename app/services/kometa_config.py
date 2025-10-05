"""Utilities for parsing Kometa configuration files."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypedDict

import yaml

from .library_mappings import normalize_path

__all__ = [
    "KometaLibraryInfo",
    "normalize_config_path",
    "extract_library_info",
    "load_library_summaries",
]

logger = logging.getLogger(__name__)


class KometaLibraryInfo(TypedDict, total=False):
    """Summary of asset configuration for a single Kometa library."""

    assetPath: Optional[str]
    collectionsPaths: List[str]


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
            candidate = normalize_path(str(base.joinpath(normalized)))
            if candidate and os.path.exists(candidate):
                return candidate

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

