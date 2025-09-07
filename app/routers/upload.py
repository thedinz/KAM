from fastapi import APIRouter, Form, File, UploadFile, HTTPException
import os
from ..services.assets import save_as_poster_jpg, sanitize_name
from .. import config

router = APIRouter()

@router.post("/upload", summary="Upload")
def upload(library: str = Form(...), ratingKey: int = Form(...),
           folderName: str = Form(...), file: UploadFile = File(...)):
    if not file:
        raise HTTPException(400, "No file uploaded")
    if "/" in folderName or "\\" in folderName:
        raise HTTPException(400, "Invalid folder name")

    if library.lower() == "collections":
        coll_root = getattr(config, "COLLECTIONS_ROOT", None)
        if not coll_root:
            for k, v in config.LIBRARY_MAPPINGS.items():
                if k.lower() == "collections":
                    coll_root = v
                    break
        if not coll_root:
            raise HTTPException(400, "Collections root not configured")

        safe = sanitize_name(folderName)
        dest_folder = os.path.join(coll_root, safe)
        os.makedirs(dest_folder, exist_ok=True)

        # Correct call: (UploadFile, dest_folder) -> path
        path = save_as_poster_jpg(file, dest_folder)
        return {"ok": True, "path": path}

    else:
        if library not in config.LIBRARY_MAPPINGS:
            raise HTTPException(404, f"Library '{library}' not configured")
        dest_folder = os.path.join(config.LIBRARY_MAPPINGS[library], folderName)

    path = save_as_poster_jpg(file, dest_folder)
    return {"ok": True, "path": path}
