from __future__ import annotations

import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services import folder_overrides
from ..services import library_mappings as library_mappings_service
from ..services.resolve import ASSETS_ROOT, resolve_existing_dir_or_422

router = APIRouter()


class AssignFolderPayload(BaseModel):
    library: str
    ratingKey: str
    folderName: str


def _library_root(
    library: str,
    *,
    settings_mode: bool = False,
    allow_beyond_mapping: bool = False,
) -> tuple[Path, str | None]:
    if not library:
        raise HTTPException(status_code=422, detail="Missing library")
    if library == "Collections":
        base = library_mappings_service.get_collections_path()
        if not base:
            raise HTTPException(
                status_code=404, detail="No assets mapping for library 'Collections'"
            )
        root = Path(base)
        default_relative = None
    else:
        mapped = library_mappings_service.get_asset_path(library)
        default_relative = None
        mapped_path = Path(mapped) if mapped else None
        assets_root = Path(ASSETS_ROOT) if ASSETS_ROOT else None

        assets_root_resolved: Path | None = None
        if assets_root:
            try:
                assets_root_resolved = assets_root.resolve()
            except FileNotFoundError:
                raise HTTPException(
                    status_code=404, detail=f"Assets library not found: {assets_root}"
                )
            except PermissionError:
                raise HTTPException(status_code=403, detail="Permission denied")
            except OSError:
                raise HTTPException(
                    status_code=400, detail="Unable to resolve assets path"
                )
            if not assets_root_resolved.is_dir():
                raise HTTPException(
                    status_code=404,
                    detail=f"Assets library not found: {assets_root_resolved}",
                )

        mapped_resolved: Path | None = None
        if mapped_path:
            try:
                mapped_resolved = mapped_path.resolve()
            except FileNotFoundError:
                raise HTTPException(
                    status_code=404, detail=f"Assets library not found: {mapped_path}"
                )
            except PermissionError:
                raise HTTPException(status_code=403, detail="Permission denied")
            except OSError:
                raise HTTPException(
                    status_code=400, detail="Unable to resolve assets path"
                )

        if mapped_resolved and not settings_mode:
            can_expand = (
                allow_beyond_mapping
                and assets_root_resolved is not None
                and mapped_resolved.is_relative_to(assets_root_resolved)
            )
            if can_expand:
                root = assets_root_resolved
                relative = mapped_resolved.relative_to(assets_root_resolved)
                default_relative = str(relative) if str(relative) != "." else ""
            else:
                root = mapped_resolved
        else:
            if not assets_root_resolved:
                if mapped_resolved:
                    root = mapped_resolved
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No assets mapping for library '{library}'",
                    )
            else:
                if settings_mode:
                    root = assets_root_resolved
                elif mapped_resolved:
                    root = mapped_resolved
                else:
                    candidate = assets_root_resolved / library
                    root = candidate if candidate.is_dir() else assets_root_resolved

    try:
        resolved_root = root.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assets library not found: {root}")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except OSError:
        raise HTTPException(status_code=400, detail="Unable to resolve assets path")

    if not resolved_root.is_dir():
        raise HTTPException(status_code=404, detail=f"Assets library not found: {resolved_root}")
    return resolved_root, default_relative


def _ensure_within_root(root: Path, target: Path) -> Path:
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid parent path")
    return target


@router.get("/api/asset-folders")
def list_asset_folders(
    library: str = Query(...),
    parent: str | None = Query(None),
    search: str | None = Query(None),
    settings: bool = Query(False),
    allow_beyond_mapping: bool = Query(False, alias="allowBeyondMapping"),
):
    parent_value = parent if isinstance(parent, str) else None
    parent_provided = parent_value is not None
    search_value = search if isinstance(search, str) else None
    if isinstance(settings, bool):
        settings_flag = settings
    else:
        default_value = getattr(settings, "default", settings)
        settings_flag = bool(default_value)

    if isinstance(allow_beyond_mapping, bool):
        allow_flag = allow_beyond_mapping
    else:
        default_allow = getattr(allow_beyond_mapping, "default", allow_beyond_mapping)
        allow_flag = bool(default_allow)

    root, default_relative = _library_root(
        library,
        settings_mode=settings_flag,
        allow_beyond_mapping=allow_flag,
    )
    current = root
    if parent_provided:
        rel = Path(parent_value or ".")
        if settings and rel.is_absolute():
            current = _ensure_within_root(root, rel.resolve())
        else:
            if rel.is_absolute():
                raise HTTPException(status_code=400, detail="Invalid parent path")
            current = _ensure_within_root(root, (root / rel).resolve())
        if not current.exists() or not current.is_dir():
            raise HTTPException(status_code=404, detail="Parent directory not found")
    elif default_relative:
        current = _ensure_within_root(root, (root / default_relative).resolve())
        if not current.exists() or not current.is_dir():
            current = root

    term = (search_value or "").strip().lower()
    items: List[dict] = []
    try:
        if term:
            matches: List[Path] = []
            for child in current.rglob("*"):
                try:
                    name_lower = child.name.lower()
                    is_valid = child.is_file() or child.is_dir()
                except PermissionError:
                    continue
                if term not in name_lower or not is_valid:
                    continue
                matches.append(child)
            matches.sort(key=lambda p: (not p.is_dir(), str(p.relative_to(root)).lower()))
            for child in matches:
                rel_path = "" if child == root else str(child.relative_to(root))
                items.append({
                    "name": child.name,
                    "isDir": child.is_dir(),
                    "path": rel_path,
                    "absolutePath": str(child),
                })
        else:
            for child in sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                rel_path = "" if child == root else str(child.relative_to(root))
                items.append({
                    "name": child.name,
                    "isDir": child.is_dir(),
                    "path": rel_path,
                    "absolutePath": str(child),
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    parent_rel = "" if current == root else str(current.relative_to(root))

    return {
        "library": library,
        "root": str(root),
        "parent": parent_rel,
        "parentAbsolute": str(current),
        "items": items,
    }


@router.post("/api/items/assign-folder")
def assign_folder(payload: AssignFolderPayload):
    canonical_path = resolve_existing_dir_or_422(payload.library, payload.folderName)
    canonical_folder = os.path.basename(os.path.normpath(canonical_path))
    folder_overrides.set_override(payload.library, payload.ratingKey, canonical_folder)

    folder_dir = Path(canonical_path)
    poster_exists = (folder_dir / "poster.jpg").is_file()
    background_exists = (folder_dir / "background.jpg").is_file()

    return {
        "library": payload.library,
        "ratingKey": payload.ratingKey,
        "folderName": canonical_folder,
        "folderExists": True,
        "assetReady": True,
        "posterExists": poster_exists,
        "backgroundExists": background_exists,
    }
