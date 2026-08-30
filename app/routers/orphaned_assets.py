"""Detect and remove asset folders that no longer match anything in Plex."""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from . import items as items_router
from ..services import folder_overrides
from ..services import library_mappings as library_mappings_service

router = APIRouter()

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_YEAR_PATTERN = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)(?:\s|$)")


class DeleteOrphanedAssetsPayload(BaseModel):
    library: str
    folderNames: List[str] = Field(default_factory=list, min_length=1, max_length=10000)

    @field_validator("library", mode="before")
    @classmethod
    def _library_required(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Library is required")
        return text

    @field_validator("folderNames", mode="before")
    @classmethod
    def _normalize_folder_names(cls, value: Any) -> List[str]:
        values = value if isinstance(value, list) else []
        result: List[str] = []
        seen: set[str] = set()
        for raw in values:
            name = str(raw or "").strip()
            key = name.casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            result.append(name)
        return result


def _library_root(library: str) -> Path:
    mapped = library_mappings_service.get_asset_path(library)
    if not mapped:
        raise HTTPException(status_code=404, detail=f"No assets mapping for library '{library}'")
    try:
        root = Path(mapped).resolve(strict=True)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assets library not found: {mapped}")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except OSError:
        raise HTTPException(status_code=400, detail="Unable to resolve assets path")
    if not root.is_dir():
        raise HTTPException(status_code=404, detail=f"Assets library not found: {root}")
    return root


def _path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def _direct_asset_folders(root: Path) -> List[Path]:
    try:
        return sorted(
            (child for child in root.iterdir() if child.is_dir() and not child.is_symlink()),
            key=lambda child: child.name.casefold(),
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


def _matched_folder_keys(library: str, rows: List[Dict[str, Any]]) -> set[str]:
    resolver = items_router._RequestDirectoryResolver(library)
    overrides = folder_overrides.get_library_overrides(library)
    matched: set[str] = set()

    for row in rows:
        override = overrides.get(row.get("ratingKey", ""))
        _name, folder_path = items_router._resolve_override_folder(library, override, resolver)
        if not folder_path:
            _name, folder_path = items_router._try_existing_asset_folder(
                library,
                row.get("title"),
                row.get("year"),
                row.get("type"),
                resolver,
                row.get("titleCandidates"),
            )
        if folder_path:
            matched.add(_path_key(folder_path))
    return matched


def _folder_stats(folder: Path) -> tuple[int, int, Optional[Path], Optional[float]]:
    asset_count = 0
    size_bytes = 0
    poster: Optional[Path] = None
    modified_at: Optional[float] = None
    try:
        for current, _directories, files in os.walk(folder, followlinks=False):
            for filename in files:
                path = Path(current) / filename
                try:
                    stat = path.stat()
                except (FileNotFoundError, PermissionError, OSError):
                    continue
                asset_count += 1
                size_bytes += stat.st_size
                modified_at = max(modified_at or stat.st_mtime, stat.st_mtime)
                if (
                    poster is None
                    and path.parent == folder
                    and path.stem.casefold() == "poster"
                    and path.suffix.casefold() in _IMAGE_EXTENSIONS
                ):
                    poster = path
    except PermissionError:
        pass
    return asset_count, size_bytes, poster, modified_at


def _display_metadata(folder_name: str) -> tuple[str, Optional[int]]:
    match = _YEAR_PATTERN.match(folder_name)
    if not match:
        return folder_name, None
    return match.group("title").strip(), int(match.group("year"))


def _orphaned_assets(library: str) -> tuple[Path, List[Dict[str, Any]]]:
    root = _library_root(library)
    rows = items_router._library_rows(library)
    matched = _matched_folder_keys(library, rows)
    orphaned: List[Dict[str, Any]] = []

    for folder in _direct_asset_folders(root):
        if _path_key(folder) in matched:
            continue
        asset_count, size_bytes, poster, modified_at = _folder_stats(folder)
        title, year = _display_metadata(folder.name)
        poster_url = f"/fileproxy?path={quote(str(poster), safe='')}" if poster else None
        orphaned.append({
            "folderName": folder.name,
            "title": title,
            "year": year,
            "assetCount": asset_count,
            "sizeBytes": size_bytes,
            "modifiedAt": (
                datetime.fromtimestamp(modified_at, tz=timezone.utc).isoformat()
                if modified_at is not None
                else None
            ),
            "posterUrl": poster_url,
        })
    return root, orphaned


@router.get("/api/orphaned-assets")
def list_orphaned_assets(library: str = Query(...)) -> Dict[str, Any]:
    """List orphaned asset folders not currently claimed by an item in Plex."""

    normalized_library = str(library or "").strip()
    if not normalized_library:
        raise HTTPException(status_code=422, detail="Missing library")
    root, items = _orphaned_assets(normalized_library)
    return {
        "library": normalized_library,
        "root": str(root),
        "totalCount": len(items),
        "items": items,
    }


@router.post("/api/orphaned-assets/delete")
def delete_orphaned_assets(payload: DeleteOrphanedAssetsPayload) -> Dict[str, Any]:
    """Delete selected folders only if they are still orphaned after a fresh Plex scan."""

    root, orphaned = _orphaned_assets(payload.library)
    orphaned_by_name = {item["folderName"].casefold(): item["folderName"] for item in orphaned}
    deleted: List[str] = []
    skipped: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []

    for requested_name in payload.folderNames:
        canonical_name = orphaned_by_name.get(requested_name.casefold())
        if not canonical_name:
            skipped.append({
                "folderName": requested_name,
                "reason": "Folder is missing or now matches an item in Plex.",
            })
            continue
        target = root / canonical_name
        try:
            resolved = target.resolve(strict=True)
            if resolved.parent != root or resolved.is_symlink() or not resolved.is_dir():
                raise ValueError("Invalid asset folder")
            shutil.rmtree(resolved)
            deleted.append(canonical_name)
        except FileNotFoundError:
            skipped.append({"folderName": canonical_name, "reason": "Folder no longer exists."})
        except (PermissionError, OSError, ValueError) as exc:
            errors.append({"folderName": canonical_name, "error": str(exc) or "Delete failed"})

    if deleted:
        folder_overrides.clear_overrides_for_folders(payload.library, deleted)

    return {
        "library": payload.library,
        "deletedCount": len(deleted),
        "deleted": deleted,
        "skipped": skipped,
        "errors": errors,
    }
