import io
import logging
import os
import pathlib
import re
import shutil
from typing import Optional
from PIL import Image
from fastapi import UploadFile, HTTPException

SAFE = re.compile(r"[^A-Za-z0-9\-\s\.\(\)_]")
MULTI = re.compile(r"\s+")

logger = logging.getLogger(__name__)

def ensure_dir(p: str):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)
    logger.debug("Ensured directory exists: %s", p)

def sanitize_name(name: str) -> str:
    s = (name or "")
    # Always preserve real titles. Only neutralize path separators and nulls.
    s = s.replace("\\", "⧵").replace("/", "⁄").replace("\x00", "")
    s = s.strip()
    sanitized = MULTI.sub(" ", s)
    logger.debug("Sanitized asset name: %r -> %r", name, sanitized)
    return sanitized

def folder_name_for(title: str, year: Optional[int]) -> str:
    original = title or "Untitled"
    sanitized = sanitize_name(original)
    if year:
        folder = f"{sanitized} ({int(year)})"
        logger.debug(
            "Resolved asset folder for title=%r year=%r -> %s", original, year, folder
        )
        return folder
    logger.debug("Resolved asset folder for title=%r -> %s", original, sanitized)
    return sanitized

def save_as_poster_jpg(upload: UploadFile, dest_folder: str) -> str:
    ensure_dir(dest_folder)
    # Remove any existing poster.* file
    for ext in ("jpg", "jpeg", "png", "webp"):
        f = os.path.join(dest_folder, f"poster.{ext}")
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception as e:
                logger.warning("Failed to remove existing poster variant %s: %s", f, e)
    dest = os.path.join(dest_folder, "poster.jpg")
    # if an incorrect directory exists at dest, remove it
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    raw = upload.file.read()
    try:
        im = Image.open(io.BytesIO(raw))
    except Exception as e:
        logger.warning("Unable to open uploaded poster for %s: %s", dest, e)
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
        except Exception as e:
            logger.warning("Failed to remove asset variant %s: %s", p, e)

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
        logger.warning(
            "Unable to open uploaded image for %s/%s: %s", dest_folder, base_no_ext, e
        )
        raise HTTPException(400, f"Invalid image: {e}")
    if im.mode != "RGB":
        im = im.convert("RGB")
    dest = os.path.join(dest_folder, base_no_ext + ".jpg")
    im.save(dest, format="JPEG", quality=90, optimize=True)
    return dest


def save_bytes_as_poster_jpg(data: bytes, dest_folder: str) -> str:
    """Save raw image bytes as poster.jpg in dest_folder, converting to JPEG."""
    ensure_dir(dest_folder)
    try:
        img = Image.open(io.BytesIO(data))
        if img.mode not in ("RGB", "L", "P"):
            img = img.convert("RGB")
        out_path = os.path.join(dest_folder, "poster.jpg")
        img.save(out_path, format="JPEG", quality=92, optimize=True)
        logger.debug("Saved converted poster image to %s", out_path)
        return out_path
    except Exception as e:
        logger.warning(
            "Falling back to raw bytes for poster in %s due to conversion error: %s",
            dest_folder,
            e,
        )
        out_path = os.path.join(dest_folder, "poster.jpg")
        with open(out_path, "wb") as f:
            f.write(data)
        logger.debug("Saved raw poster bytes to %s", out_path)
        return out_path
