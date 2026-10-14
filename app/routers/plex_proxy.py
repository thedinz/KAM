from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlencode, urlsplit

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..services import plex_settings
from ..services import thumbnails as thumbnail_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Plex image paths such as /library/metadata/1/thumb/1712345678 end in a
# version that changes with the artwork, so those responses can be cached.
_VERSIONED_IMAGE_RE = re.compile(r"/library/.+/(?:thumb|art|banner|composite|clearLogo)/\d+$")
_VERSIONED_CACHE_CONTROL = "private, max-age=31536000, immutable"


def _transcode_url(base_url: str, image_url: str, width: int) -> str:
    """Return a Plex URL that resizes *image_url* to *width* pixels wide."""
    base_path = urlsplit(base_url).path.rstrip("/")
    parts = urlsplit(plex_settings.without_token(image_url))
    inner = parts.path
    if base_path and inner.startswith(base_path + "/"):
        inner = inner[len(base_path):]
    if parts.query:
        inner = f"{inner}?{parts.query}"
    query = urlencode({"width": width, "height": width * 4, "upscale": 0, "url": inner})
    return f"{base_url}/photo/:/transcode?{query}"


def _fetch(url: str) -> requests.Response:
    response = plex_settings.plex_get(url, stream=True, timeout=30)
    response.raise_for_status()
    return response


@router.get("/api/plex/image")
def plex_image(
    path: Optional[str] = Query(None, description="Plex image path or URL"),
    ratingKey: Optional[str] = Query(None),
    kind: str = Query("thumb"),
    w: Optional[int] = Query(None, description="Return a resized image about this many pixels wide"),
):
    cfg = plex_settings.get_plex_config()
    if not cfg.url or not cfg.token:
        raise HTTPException(status_code=500, detail="PLEX_URL or PLEX_TOKEN not set")

    if not path:
        if not ratingKey:
            raise HTTPException(status_code=422, detail="path or ratingKey is required")
        kind_normalized = "art" if kind.lower() in ("art", "background") else "thumb"
        path = f"/library/metadata/{ratingKey}/{kind_normalized}"

    if path.startswith("http://") or path.startswith("https://"):
        if not plex_settings.is_plex_url(path):
            raise HTTPException(status_code=403, detail="URL not allowed")
        url = path
    else:
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{cfg.url}{path}"

    width = thumbnail_service.snap_width(w if isinstance(w, int) else None)
    response = None
    if width:
        try:
            response = _fetch(_transcode_url(cfg.url, url, width))
        except requests.RequestException as exc:
            # Fall back to the full-size image if Plex can't resize this one.
            logger.debug("Plex resize failed for %s: %s", urlsplit(url).path, type(exc).__name__)

    try:
        if response is None:
            response = _fetch(url)
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        logger.warning(
            "Plex image proxy failed for %s: %s%s",
            urlsplit(url).path,
            type(exc).__name__,
            f" [{status}]" if status else "",
        )
        raise HTTPException(status_code=502, detail="Plex image proxy failed") from exc

    content_type = response.headers.get("Content-Type") or "application/octet-stream"
    headers = (
        {"Cache-Control": _VERSIONED_CACHE_CONTROL}
        if _VERSIONED_IMAGE_RE.search(urlsplit(url).path)
        else None
    )
    return StreamingResponse(
        response.iter_content(chunk_size=1024 * 128),
        media_type=content_type,
        headers=headers,
    )
