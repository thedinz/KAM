
import logging
import os, mimetypes
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from ..services import library_mappings as library_mappings_service
from ..services import resolve as resolve_service
from ..services import thumbnails as thumbnail_service

logger = logging.getLogger(__name__)

router = APIRouter()

# URLs with ?t=<mtime> change whenever the file does, so browsers can keep
# them instead of re-checking every image on every page.
VERSIONED_CACHE_CONTROL = "private, max-age=31536000, immutable"

def _allowed_roots():
    roots = set()
    for entry in library_mappings_service.load_library_mappings():
        asset = entry.get("assetPath")
        if asset:
            roots.add(asset)
        coll = entry.get("collectionsPath")
        if coll:
            roots.add(coll)
    fallback_coll = library_mappings_service.get_collections_path()
    if fallback_coll:
        roots.add(fallback_coll)
    assets_root = resolve_service.ASSETS_ROOT
    if assets_root:
        roots.add(assets_root)
    normalized = []
    for root in roots:
        if not root:
            continue
        normalized.append(os.path.realpath(os.path.abspath(root)))
    return normalized

def _is_allowed(path: str) -> bool:
    if not library_mappings_service.is_allowed_path(path):
        return False
    rp = os.path.realpath(path)
    for root in _allowed_roots():
        if rp.startswith(root + os.sep) or rp == root:
            return True
    return False

@router.get("/fileproxy")
def fileproxy(
    path: str = Query(..., description="Absolute path inside mapped asset roots"),
    w: Optional[int] = Query(None, description="Return a resized JPEG about this many pixels wide"),
    t: Optional[str] = Query(None, description="File version; makes the response cacheable"),
):
    if not path:
        raise HTTPException(400, "Missing path")
    if not _is_allowed(path):
        raise HTTPException(403, "Path not allowed")
    if not os.path.isfile(path):
        raise HTTPException(404, "File not found")
    # Direct calls (tests) pass the Query defaults through unchanged.
    version = t if isinstance(t, str) else None
    requested_width = w if isinstance(w, int) else None
    headers = {"Cache-Control": VERSIONED_CACHE_CONTROL} if version else None

    width = thumbnail_service.snap_width(requested_width)
    if width:
        try:
            thumbnail = thumbnail_service.thumbnail_path(path, width)
            return FileResponse(thumbnail, media_type="image/jpeg", headers=headers)
        except Exception as exc:
            # Not an image Pillow can read, or the cache isn't writable: the
            # original file still works, just slower.
            logger.debug("Serving original for %s: %s", path, exc)

    mt, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=mt or "application/octet-stream", headers=headers)
