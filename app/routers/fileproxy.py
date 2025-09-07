
import os, mimetypes
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from .. import config

router = APIRouter()

def _allowed_roots():
    roots = set()
    roots.update(getattr(config, "LIBRARY_MAPPINGS", {}).values())
    coll = getattr(config, "COLLECTIONS_ROOT", None)
    if coll:
        roots.add(coll)
    return [os.path.realpath(p) for p in roots if p]

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
