"""Detect and remove asset folders that no longer match anything in Plex."""
from __future__ import annotations

import os
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from . import items as items_router
from ..services import folder_overrides, orphan_exclusions
from ..services import library_mappings as library_mappings_service
from ..services import resolve as resolve_service

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


class OrphanExclusionPayload(BaseModel):
    library: str
    folderName: str

    @field_validator("library", "folderName", mode="before")
    @classmethod
    def _required_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Value is required")
        return text


class ResolveDuplicateFoldersPayload(BaseModel):
    library: str
    ratingKey: str
    keepFolderName: str

    @field_validator("library", "ratingKey", "keepFolderName", mode="before")
    @classmethod
    def _required_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Value is required")
        return text


class ResolveDuplicateFolderSelection(BaseModel):
    ratingKey: str
    keepFolderName: str

    @field_validator("ratingKey", "keepFolderName", mode="before")
    @classmethod
    def _required_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Value is required")
        return text


class ResolveDuplicateFoldersBatchPayload(BaseModel):
    library: str
    selections: List[ResolveDuplicateFolderSelection] = Field(
        default_factory=list,
        min_length=1,
        max_length=10000,
    )

    @field_validator("library", mode="before")
    @classmethod
    def _library_required(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Library is required")
        return text

    @field_validator("selections")
    @classmethod
    def _unique_rating_keys(
        cls,
        value: List[ResolveDuplicateFolderSelection],
    ) -> List[ResolveDuplicateFolderSelection]:
        seen: set[str] = set()
        for selection in value:
            key = selection.ratingKey.casefold()
            if key in seen:
                raise ValueError("Each asset can only be selected once")
            seen.add(key)
        return value


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


def _active_folder_paths(library: str, rows: List[Dict[str, Any]]) -> Dict[str, str]:
    resolver = items_router._RequestDirectoryResolver(library)
    overrides = folder_overrides.get_library_overrides(library)
    active: Dict[str, str] = {}

    for row in rows:
        rating_key = str(row.get("ratingKey") or "").strip()
        if not rating_key:
            continue
        override = overrides.get(rating_key)
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
            active[rating_key] = _path_key(folder_path)
    return active


def _row_match_targets(row: Dict[str, Any]) -> List[str]:
    title_values = [row.get("title"), *(row.get("titleCandidates") or [])]
    targets: List[str] = []
    seen: set[str] = set()
    year = row.get("year")
    item_type = str(row.get("type") or "").casefold()
    for raw_title in title_values:
        title = str(raw_title or "").strip()
        if not title:
            continue
        has_year = resolve_service._has_release_year(title)
        candidates: List[str] = []
        if year and not has_year:
            candidates.append(f"{title} ({year})")
        if not (year and item_type == "movie" and not has_year):
            candidates.append(title)
        for candidate in candidates:
            key = candidate.casefold()
            if key in seen:
                continue
            seen.add(key)
            targets.append(candidate)
    return targets


def _build_match_index(rows: List[Dict[str, Any]]):
    records: List[Dict[str, Any]] = []
    normalized_index: Dict[str, set[int]] = defaultdict(set)
    token_index: Dict[str, set[int]] = defaultdict(set)
    prefix_index: Dict[str, set[int]] = defaultdict(set)

    for row in rows:
        targets = _row_match_targets(row)
        if not targets:
            continue
        record_index = len(records)
        record = {"row": row, "targets": targets}
        records.append(record)
        for target in targets:
            normalized, _year, tokens = resolve_service._comparison_parts(target)
            if normalized:
                normalized_index[normalized].add(record_index)
                prefix_index[normalized[:2]].add(record_index)
            for token in tokens:
                if len(token) > 1 and not resolve_service._is_metadata_token(token):
                    token_index[token].add(record_index)
    return records, normalized_index, token_index, prefix_index


def _plausible_matches_for_folder(
    folder_name: str,
    records: List[Dict[str, Any]],
    normalized_index: Dict[str, set[int]],
    token_index: Dict[str, set[int]],
    prefix_index: Dict[str, set[int]],
) -> set[str]:
    normalized, _year, tokens = resolve_service._comparison_parts(folder_name)
    candidate_indexes: set[int] = set(normalized_index.get(normalized, set()))
    if normalized:
        candidate_indexes.update(prefix_index.get(normalized[:2], set()))
    for token in tokens:
        if len(token) > 1 and not resolve_service._is_metadata_token(token):
            candidate_indexes.update(token_index.get(token, set()))

    matches: set[str] = set()
    for index in candidate_indexes:
        record = records[index]
        if not any(
            resolve_service._best_match([folder_name], target) == folder_name
            for target in record["targets"]
        ):
            continue
        rating_key = str(record["row"].get("ratingKey") or "").strip()
        if rating_key:
            matches.add(rating_key)
    return matches


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


def _folder_payload(folder: Path) -> Dict[str, Any]:
    asset_count, size_bytes, poster, modified_at = _folder_stats(folder)
    title, year = _display_metadata(folder.name)
    poster_url = f"/fileproxy?path={quote(str(poster), safe='')}" if poster else None
    return {
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
    }


def _asset_audit(library: str) -> Dict[str, Any]:
    root = _library_root(library)
    rows = items_router._library_rows(library)
    folders = _direct_asset_folders(root)
    active_by_rating = _active_folder_paths(library, rows)
    records, normalized_index, token_index, prefix_index = _build_match_index(rows)
    matches_by_path: Dict[str, set[str]] = {}

    active_by_path: Dict[str, set[str]] = defaultdict(set)
    for rating_key, path_key in active_by_rating.items():
        active_by_path[path_key].add(rating_key)

    for folder in folders:
        path_key = _path_key(folder)
        matches = _plausible_matches_for_folder(
            folder.name,
            records,
            normalized_index,
            token_index,
            prefix_index,
        )
        matches.update(active_by_path.get(path_key, set()))
        matches_by_path[path_key] = matches

    return {
        "root": root,
        "rows": rows,
        "folders": folders,
        "activeByRating": active_by_rating,
        "matchesByPath": matches_by_path,
    }


def _orphaned_assets(
    library: str,
    *,
    include_excluded: bool = False,
) -> tuple[Path, List[Dict[str, Any]]]:
    audit = _asset_audit(library)
    orphaned: List[Dict[str, Any]] = []
    excluded_names = {
        entry["folderName"].casefold()
        for entry in orphan_exclusions.list_exclusions(library)
    }

    for folder in audit["folders"]:
        if audit["matchesByPath"].get(_path_key(folder)):
            continue
        excluded = folder.name.casefold() in excluded_names
        if excluded and not include_excluded:
            continue
        item = _folder_payload(folder)
        item["excluded"] = excluded
        orphaned.append(item)
    return audit["root"], orphaned


def _duplicate_groups(library: str) -> tuple[Path, List[Dict[str, Any]]]:
    audit = _asset_audit(library)
    rows_by_key = {
        str(row.get("ratingKey") or "").strip(): row
        for row in audit["rows"]
        if str(row.get("ratingKey") or "").strip()
    }
    grouped: Dict[str, List[Path]] = defaultdict(list)

    for folder in audit["folders"]:
        path_key = _path_key(folder)
        active_ratings = [
            rating_key
            for rating_key, active_path in audit["activeByRating"].items()
            if active_path == path_key
        ]
        matches = audit["matchesByPath"].get(path_key, set())
        if active_ratings:
            grouped[active_ratings[0]].append(folder)
        elif len(matches) == 1:
            grouped[next(iter(matches))].append(folder)

    groups: List[Dict[str, Any]] = []
    for rating_key, folders in grouped.items():
        if len(folders) < 2:
            continue
        row = rows_by_key.get(rating_key)
        if not row:
            continue
        active_path = audit["activeByRating"].get(rating_key)
        folder_items: List[Dict[str, Any]] = []
        for folder in sorted(folders, key=lambda path: path.name.casefold()):
            item = _folder_payload(folder)
            item["isActive"] = _path_key(folder) == active_path
            folder_items.append(item)
        groups.append({
            "ratingKey": rating_key,
            "title": row.get("title") or "(Untitled)",
            "year": row.get("year"),
            "type": row.get("type"),
            "activeFolderName": next(
                (item["folderName"] for item in folder_items if item["isActive"]),
                None,
            ),
            "folders": folder_items,
        })
    groups.sort(key=lambda group: (str(group["title"]).casefold(), group.get("year") or 0))
    return audit["root"], groups


def _delete_direct_folder(root: Path, folder_name: str) -> None:
    target = root / folder_name
    resolved = target.resolve(strict=True)
    if resolved.parent != root or target.is_symlink() or not resolved.is_dir():
        raise ValueError("Invalid asset folder")
    shutil.rmtree(resolved)


@router.get("/api/orphaned-assets")
def list_orphaned_assets(
    library: str = Query(...),
    include_excluded: bool = Query(False, alias="includeExcluded"),
) -> Dict[str, Any]:
    """List orphaned asset folders not currently claimed by an item in Plex."""

    normalized_library = str(library or "").strip()
    if not normalized_library:
        raise HTTPException(status_code=422, detail="Missing library")
    include_flag = (
        include_excluded
        if isinstance(include_excluded, bool)
        else bool(getattr(include_excluded, "default", False))
    )
    root, items = _orphaned_assets(
        normalized_library,
        include_excluded=include_flag,
    )
    return {
        "library": normalized_library,
        "root": str(root),
        "totalCount": len(items),
        "items": items,
    }


@router.post("/api/orphaned-assets/exclude")
def exclude_orphaned_asset(payload: OrphanExclusionPayload) -> Dict[str, Any]:
    """Hide a known false positive while keeping the folder and its assets."""

    _root, items = _orphaned_assets(payload.library, include_excluded=True)
    by_name = {item["folderName"].casefold(): item["folderName"] for item in items}
    canonical_name = by_name.get(payload.folderName.casefold())
    if not canonical_name:
        raise HTTPException(
            status_code=409,
            detail="Folder is missing or now matches an item in Plex.",
        )
    stored = orphan_exclusions.add_exclusion(payload.library, canonical_name)
    return stored


@router.post("/api/orphaned-assets/include")
def include_orphaned_asset(payload: OrphanExclusionPayload) -> Dict[str, Any]:
    """Restore a previously excluded folder to the orphan audit."""

    removed = orphan_exclusions.remove_exclusion(payload.library, payload.folderName)
    if not removed:
        raise HTTPException(status_code=404, detail="Orphan exclusion not found")
    return {"library": payload.library, "folderName": payload.folderName, "excluded": False}


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
        try:
            _delete_direct_folder(root, canonical_name)
            deleted.append(canonical_name)
        except FileNotFoundError:
            skipped.append({"folderName": canonical_name, "reason": "Folder no longer exists."})
        except (PermissionError, OSError, ValueError) as exc:
            errors.append({"folderName": canonical_name, "error": str(exc) or "Delete failed"})

    if deleted:
        folder_overrides.clear_overrides_for_folders(payload.library, deleted)
        for folder_name in deleted:
            orphan_exclusions.remove_exclusion(payload.library, folder_name)

    return {
        "library": payload.library,
        "deletedCount": len(deleted),
        "deleted": deleted,
        "skipped": skipped,
        "errors": errors,
    }


@router.get("/api/duplicate-folders")
def list_duplicate_folders(library: str = Query(...)) -> Dict[str, Any]:
    """List Plex assets with more than one plausible asset folder."""

    normalized_library = str(library or "").strip()
    if not normalized_library:
        raise HTTPException(status_code=422, detail="Missing library")
    root, groups = _duplicate_groups(normalized_library)
    return {
        "library": normalized_library,
        "root": str(root),
        "totalCount": len(groups),
        "groups": groups,
    }


@router.post("/api/duplicate-folders/resolve")
def resolve_duplicate_folders(payload: ResolveDuplicateFoldersPayload) -> Dict[str, Any]:
    """Keep one selected folder and delete the other freshly verified duplicates."""

    root, groups = _duplicate_groups(payload.library)
    group = next(
        (item for item in groups if str(item.get("ratingKey")) == payload.ratingKey),
        None,
    )
    if not group:
        raise HTTPException(
            status_code=409,
            detail="This asset no longer has verified duplicate folders.",
        )
    try:
        return _resolve_duplicate_group(
            root=root,
            library=payload.library,
            group=group,
            rating_key=payload.ratingKey,
            keep_folder_name=payload.keepFolderName,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _resolve_duplicate_group(
    *,
    root: Path,
    library: str,
    group: Dict[str, Any],
    rating_key: str,
    keep_folder_name: str,
) -> Dict[str, Any]:
    """Switch KAM to the retained folder, then remove its verified alternatives."""

    folders_by_name = {
        item["folderName"].casefold(): item["folderName"]
        for item in group["folders"]
    }
    keep_name = folders_by_name.get(keep_folder_name.casefold())
    if not keep_name:
        raise ValueError("Selected folder is no longer a duplicate.")

    previous_active_name = group.get("activeFolderName")
    assignment_changed = (
        not previous_active_name
        or str(previous_active_name).casefold() != keep_name.casefold()
    )

    # Persist this first so KAM never points at one of the folders being removed.
    folder_overrides.set_canonical_overrides(library, {rating_key: keep_name})
    deleted: List[str] = []
    errors: List[Dict[str, str]] = []
    for folder_name in folders_by_name.values():
        if folder_name == keep_name:
            continue
        try:
            _delete_direct_folder(root, folder_name)
            deleted.append(folder_name)
        except FileNotFoundError:
            continue
        except (PermissionError, OSError, ValueError) as exc:
            errors.append({"folderName": folder_name, "error": str(exc) or "Delete failed"})

    if deleted:
        folder_overrides.clear_overrides_for_folders(library, deleted)
        for folder_name in deleted:
            orphan_exclusions.remove_exclusion(library, folder_name)

    return {
        "library": library,
        "ratingKey": rating_key,
        "keptFolderName": keep_name,
        "previousActiveFolderName": previous_active_name,
        "folderAssignmentChanged": assignment_changed,
        "deleted": deleted,
        "deletedCount": len(deleted),
        "errors": errors,
    }


@router.post("/api/duplicate-folders/resolve-all")
def resolve_all_duplicate_folders(
    payload: ResolveDuplicateFoldersBatchPayload,
) -> Dict[str, Any]:
    """Resolve a user-staged set of duplicate groups after one fresh audit."""

    root, groups = _duplicate_groups(payload.library)
    groups_by_rating = {
        str(group.get("ratingKey") or ""): group
        for group in groups
    }
    results: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []

    for selection in payload.selections:
        group = groups_by_rating.get(selection.ratingKey)
        if not group:
            failures.append({
                "ratingKey": selection.ratingKey,
                "keepFolderName": selection.keepFolderName,
                "error": "This asset no longer has verified duplicate folders.",
            })
            continue
        try:
            result = _resolve_duplicate_group(
                root=root,
                library=payload.library,
                group=group,
                rating_key=selection.ratingKey,
                keep_folder_name=selection.keepFolderName,
            )
        except (OSError, ValueError) as exc:
            failures.append({
                "ratingKey": selection.ratingKey,
                "keepFolderName": selection.keepFolderName,
                "error": str(exc) or "Resolution failed.",
            })
            continue
        results.append(result)

    deleted_count = sum(result["deletedCount"] for result in results)
    changed_count = sum(
        1 for result in results if result["folderAssignmentChanged"]
    )
    return {
        "library": payload.library,
        "processedCount": len(results),
        "deletedCount": deleted_count,
        "folderAssignmentsChanged": changed_count,
        "results": results,
        "failures": failures,
    }
