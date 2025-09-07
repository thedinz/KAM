import os, io, re, pathlib
from typing import Optional
from PIL import Image
from fastapi import UploadFile, HTTPException

SAFE = re.compile(r"[^A-Za-z0-9\-\s\.\(\)_]")
MULTI = re.compile(r"\s+")

def ensure_dir(p: str):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def sanitize_name(name: str) -> str:
    s = SAFE.sub("", name or "").strip()
    return MULTI.sub(" ", s)

def folder_name_for(title: str, year: Optional[int]) -> str:
    title = title or "Untitled"
    title = sanitize_name(title)
    if year:
        return f"{title} ({int(year)})"
    return title

def save_as_poster_jpg(upload: UploadFile, dest_folder: str) -> str:
    ensure_dir(dest_folder)
    # Remove any existing poster.* file
    for ext in ("jpg", "jpeg", "png", "webp"):
        f = os.path.join(dest_folder, f"poster.{ext}")
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    dest = os.path.join(dest_folder, "poster.jpg")
    # if an incorrect directory exists at dest, remove it
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    raw = upload.file.read()
    try:
        im = Image.open(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {e}")
    if im.mode != "RGB":
        im = im.convert("RGB")
    im.save(dest, format="JPEG", quality=90, optimize=True)
    return dest

def _delete_existing_variants(dest_folder: str, base_no_ext: str):
    """Delete poster/background/SeasonXX variants regardless of extension."""
    base = os.path.join(dest_folder, base_no_ext)
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        try:
            p = base + ext
            if os.path.isfile(p):
                os.remove(p)
        except Exception:
            pass

def save_as_named_jpg(upload: UploadFile, dest_folder: str, base_no_ext: str) -> str:
    """Save an uploaded image to dest_folder/<base_no_ext>.jpg, converting to JPEG,
    deleting any pre-existing variants (jpg/png/webp). Ensures dest_folder exists.
    """
    ensure_dir(dest_folder)
    _delete_existing_variants(dest_folder, base_no_ext)
    raw = upload.file.read()
    try:
        im = Image.open(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {e}")
    if im.mode != "RGB":
        im = im.convert("RGB")
    dest = os.path.join(dest_folder, base_no_ext + ".jpg")
    im.save(dest, format="JPEG", quality=90, optimize=True)
    return dest
