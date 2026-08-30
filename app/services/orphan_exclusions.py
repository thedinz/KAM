"""Persistence for asset folders a user has excluded from orphan audits."""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_STORAGE_PATH = os.environ.get(
    "KAM_ORPHAN_EXCLUSIONS_PATH",
    os.path.join(os.environ.get("KAM_STATE_ROOT") or "/config", "orphan_exclusions.json"),
)


def set_storage_path(path: str) -> None:
    global _STORAGE_PATH
    _STORAGE_PATH = str(path)


def _path() -> Path:
    return Path(_STORAGE_PATH)


def _read_locked() -> List[Dict[str, Any]]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning("Unable to read orphan exclusions: %s", exc)
        return []
    if not isinstance(raw, list):
        return []
    entries: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        library = str(item.get("library") or "").strip()
        folder_name = str(item.get("folderName") or "").strip()
        if not library or not folder_name:
            continue
        entries.append({
            "library": library,
            "folderName": folder_name,
            "excludedAt": str(item.get("excludedAt") or ""),
        })
    return entries


def _write_locked(entries: List[Dict[str, Any]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def list_exclusions(library: str | None = None) -> List[Dict[str, Any]]:
    with _LOCK:
        entries = _read_locked()
    if library:
        key = str(library).strip().casefold()
        entries = [entry for entry in entries if entry["library"].casefold() == key]
    return entries


def is_excluded(library: str, folder_name: str) -> bool:
    library_key = str(library or "").strip().casefold()
    folder_key = str(folder_name or "").strip().casefold()
    if not library_key or not folder_key:
        return False
    return any(
        entry["library"].casefold() == library_key
        and entry["folderName"].casefold() == folder_key
        for entry in list_exclusions()
    )


def add_exclusion(library: str, folder_name: str) -> Dict[str, Any]:
    library_name = str(library or "").strip()
    canonical_folder = str(folder_name or "").strip()
    if not library_name or not canonical_folder:
        raise ValueError("library and folder_name are required")
    with _LOCK:
        entries = _read_locked()
        for entry in entries:
            if (
                entry["library"].casefold() == library_name.casefold()
                and entry["folderName"].casefold() == canonical_folder.casefold()
            ):
                return dict(entry)
        stored = {
            "library": library_name,
            "folderName": canonical_folder,
            "excludedAt": datetime.now(timezone.utc).isoformat(),
        }
        entries.append(stored)
        _write_locked(entries)
    return dict(stored)


def remove_exclusion(library: str, folder_name: str) -> bool:
    library_key = str(library or "").strip().casefold()
    folder_key = str(folder_name or "").strip().casefold()
    if not library_key or not folder_key:
        return False
    with _LOCK:
        entries = _read_locked()
        kept = [
            entry for entry in entries
            if not (
                entry["library"].casefold() == library_key
                and entry["folderName"].casefold() == folder_key
            )
        ]
        if len(kept) == len(entries):
            return False
        _write_locked(kept)
    return True
