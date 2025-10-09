
import os, mimetypes
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from ..services import library_mappings as library_mappings_service
from ..services import resolve as resolve_service

router = APIRouter()

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
    rp = os.path.realpath(path)
    for root in _allowed_roots():
        if rp.startswith(root + os.sep) or rp == root:
            return True
    return False

@router.get("/fileproxy")
def fileproxy(path: str = Query(..., description="Absolute path inside mapped asset roots")):
    if not path:
        raise HTTPException(400, "Missing path")
    if not _is_allowed(path):
        raise HTTPException(403, "Path not allowed")
    if not os.path.isfile(path):
        raise HTTPException(404, "File not found")
    mt, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=mt or "application/octet-stream")
