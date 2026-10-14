"""Resized copies of local artwork, cached on disk.

Grids show dozens of posters at a time. Serving the full-size files (often
several megabytes each) makes pages crawl on slow connections, so the UI asks
for a width and gets a small JPEG instead.
"""
from __future__ import annotations

import hashlib
import io
import os
import threading
from pathlib import Path
from typing import Optional

from PIL import Image

from . import settings as settings_service

# Widths the UI can ask for. Requests round up to one of these so each image
# has at most a few cached sizes; anything larger gets the original file.
THUMBNAIL_WIDTHS = (200, 400, 800)
_MAX_SOURCE_PIXELS = 100_000_000
_JPEG_QUALITY = 82


def snap_width(value: Optional[int]) -> Optional[int]:
    """Return the cached width to use for a requested width, or None."""
    if not value or value <= 0:
        return None
    for width in THUMBNAIL_WIDTHS:
        if value <= width:
            return width
    return None


def cache_dir() -> Path:
    override = os.environ.get("KAM_THUMBNAIL_CACHE")
    if override:
        return Path(override)
    return settings_service.get_storage_path().parent / "cache" / "thumbnails"


def thumbnail_path(source: str, width: int) -> str:
    """Return the path of a cached *width*-wide JPEG of *source*, creating it if needed."""
    stat = os.stat(source)
    key = hashlib.sha256(os.path.realpath(source).encode("utf-8")).hexdigest()
    folder = cache_dir() / key[:2] / key
    version = f"{stat.st_mtime_ns}-{stat.st_size}"
    target = folder / f"{version}-{width}.jpg"
    if target.is_file():
        return str(target)

    data = _render(source, width)
    folder.mkdir(parents=True, exist_ok=True)
    # Thumbnails of an older version of this file are no longer reachable.
    for old in folder.glob("*.jpg"):
        if not old.name.startswith(f"{version}-"):
            try:
                old.unlink()
            except OSError:
                pass
    tmp = folder / f".{version}-{width}.{os.getpid()}-{threading.get_ident()}.tmp"
    try:
        tmp.write_bytes(data)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return str(target)


def _render(source: str, width: int) -> bytes:
    with Image.open(source) as image:
        if image.width * image.height > _MAX_SOURCE_PIXELS:
            raise ValueError("Image dimensions are too large")
        # thumbnail() keeps the aspect ratio, never enlarges, and lets JPEG
        # decode at a reduced scale, which is most of the speed-up.
        image.thumbnail((width, width * 4), Image.Resampling.LANCZOS)
        converted = image if image.mode == "RGB" else image.convert("RGB")
        output = io.BytesIO()
        converted.save(output, format="JPEG", quality=_JPEG_QUALITY, optimize=True, progressive=True)
        return output.getvalue()
