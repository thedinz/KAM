# app/routers/upload.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import os

from ..services.resolve import resolve_existing_dir_or_422

router = APIRouter()

def _write_file(dest_path: str, up: UploadFile) -> None:
    data = up.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")
    # ensure parent exists (we only ever write into an existing dir)
    parent = os.path.dirname(dest_path)
    if not os.path.isdir(parent):
        raise HTTPException(status_code=422, detail="Asset folder does not exist")
    with open(dest_path, "wb") as f:
        f.write(data)

@router.post("/api/upload")
def upload_movie_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    file: UploadFile = File(...),
    kind: Optional[str] = Form("poster"),  # "poster" or "background"
):
    """
    Movie upload: write ONLY into an existing Kometa folder.
    If the folder doesn't exist, return 422. Never create a new folder.
    """
    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    filename = "background.jpg" if (kind or "").lower() == "background" else "poster.jpg"
    dest_path = os.path.join(dest_dir, filename)
    _write_file(dest_path, file)
    return {"ok": True, "path": dest_path}

@router.post("/api/upload_show")
def upload_show_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    kind: str = Form(...),                  # "poster" | "background"
    file: UploadFile = File(...),
):
    """
    Series upload: write ONLY into an existing Kometa folder.
    """
    if kind not in ("poster", "background"):
        raise HTTPException(status_code=422, detail=f"Invalid kind: {kind}")

    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    dest_name = "poster.jpg" if kind == "poster" else "background.jpg"
    dest_path = os.path.join(dest_dir, dest_name)
    _write_file(dest_path, file)
    return {"ok": True, "path": dest_path}

@router.post("/api/upload_season")
def upload_season_asset(
    library: str = Form(...),
    folderName: str = Form(...),
    season: str = Form(...),                # numeric string (e.g., "1", "02")
    file: UploadFile = File(...),
):
    """
    Season upload: write ONLY into an existing Kometa folder.
    """
    try:
        idx = int(str(season).strip())
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid season: {season!r}")

    try:
        dest_dir = resolve_existing_dir_or_422(library, folderName)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    dest_name = f"Season{idx:02d}.jpg"
    dest_path = os.path.join(dest_dir, dest_name)
    _write_file(dest_path, file)
    return {"ok": True, "path": dest_path}
