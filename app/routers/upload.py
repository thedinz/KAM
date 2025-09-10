from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import os, io
from PIL import Image

from ..services.assets import ensure_dir
from .. import config

router = APIRouter()

# ---------- helpers ----------

def _delete_variants(dest_folder: str, base_no_ext: str) -> None:
    """Remove any existing files named <base_no_ext>.(jpg|jpeg|png|webp) in the folder."""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(dest_folder, base_no_ext + ext)
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            # don't block the request if cleanup fails
            pass

def _save_as_named_jpg_from_upload(file: UploadFile, dest_folder: str, base_no_ext: str) -> str:
    """
    Save uploaded image to <dest_folder>/<base_no_ext>.jpg.
    - Deletes existing variants first (handled by caller)
    - Normalizes via Pillow to JPEG
    """
    ensure_dir(dest_folder)

    data = file.file.read()
    out_path = os.path.join(dest_folder, base_no_ext + ".jpg")
    try:
        img = Image.open(io.BytesIO(data))
        # Convert so JPEG save is safe
        if img.mode not in ("RGB", "L", "P"):
            img = img.convert("RGB")
        img.save(out_path, format="JPEG", quality=92, optimize=True)
        return out_path
    except Exception:
        # Fallback: raw write (still .jpg extension)
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path

def _validate_folder_name(folderName: str) -> None:
    # Fix: backslash must be written as "\\"
    if "/" in folderName or "\\" in folderName:
        raise HTTPException(400, "Invalid folder name")

def _library_base_or_404(library: str) -> str:
    base = config.LIBRARY_MAPPINGS.get(library)
    if not base:
        raise HTTPException(404, f"Library '{library}' not configured")
    return base

# ---------- Movies: /api/upload ----------

@router.post("/upload")
def upload_movie(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: int = Form(...),
    kind: str = Form("poster"),
    file: UploadFile = File(...),
):
    """
    Movies upload:
      kind=poster      -> poster.jpg
      kind=background  -> background.jpg
    """
    _validate_folder_name(folderName)
    base = _library_base_or_404(library)
    dest_folder = os.path.join(base, folderName)
    ensure_dir(dest_folder)

    base_no_ext = "background" if (kind or "").lower() == "background" else "poster"
    # Critical: delete old variants before saving, to guarantee overwrite
    _delete_variants(dest_folder, base_no_ext)
    path = _save_as_named_jpg_from_upload(file, dest_folder, base_no_ext)
    return {"ok": True, "path": path}

# ---------- TV: /api/upload_show ----------

@router.post("/upload_show")
def upload_show(
    library: str = Form(...),
    folderName: str = Form(...),
    ratingKey: int = Form(...),
    kind: str = Form("poster"),
    file: UploadFile = File(...),
    seasonIndex: Optional[int] = Form(None),
):
    """
    TV upload:
      - Series-level poster/background -> poster.jpg / background.jpg
      - Season poster (if seasonIndex provided) -> SeasonXX.jpg (no subfolders)
    """
    _validate_folder_name(folderName)
    base = _library_base_or_404(library)
    dest_folder = os.path.join(base, folderName)
    ensure_dir(dest_folder)

    if seasonIndex is not None:
        # Save as SeasonXX.jpg inside the show's folder
        base_no_ext = f"Season{int(seasonIndex):02d}"
    else:
        base_no_ext = "background" if (kind or "").lower() == "background" else "poster"

    # Critical: delete old variants (this fixes your "import blocks upload overwrite" case)
    _delete_variants(dest_folder, base_no_ext)
    path = _save_as_named_jpg_from_upload(file, dest_folder, base_no_ext)
    return {"ok": True, "path": path}
