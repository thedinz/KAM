"""Apply saved KAM artwork directly to Plex."""
from __future__ import annotations

import logging
import os
from typing import Any

from . import settings as settings_service
from .plex import get_plex

logger = logging.getLogger(__name__)


class PlexArtworkError(RuntimeError):
    """Raised when a saved asset cannot be applied to Plex."""


def auto_apply_enabled() -> bool:
    """Return whether uploads should also be sent directly to Plex."""

    try:
        return bool(settings_service.load_settings().get("autoApplyToPlex", False))
    except Exception:
        logger.warning("Unable to read the automatic Plex artwork setting", exc_info=True)
        return False


def apply_artwork_file(rating_key: str, path: str, kind: str) -> dict[str, Any]:
    """Upload one saved poster or background to the matching Plex item."""

    normalized_rating_key = str(rating_key or "").strip()
    if not normalized_rating_key:
        raise PlexArtworkError("A Plex rating key is required.")

    normalized_path = os.path.abspath(str(path or ""))
    if not os.path.isfile(normalized_path):
        raise PlexArtworkError("The saved artwork file was not found.")

    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind not in {"poster", "background"}:
        raise PlexArtworkError(f"Unsupported artwork kind: {kind!r}")

    try:
        item = get_plex().fetchItem(int(normalized_rating_key))
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        raise PlexArtworkError(f"Unable to find the Plex item: {detail}") from exc

    method_name = "uploadArt" if normalized_kind == "background" else "uploadPoster"
    method = getattr(item, method_name, None)
    if not callable(method):
        label = "background artwork" if normalized_kind == "background" else "poster artwork"
        raise PlexArtworkError(f"This Plex item does not support {label}.")

    try:
        method(filepath=normalized_path)
    except Exception as exc:
        raise PlexArtworkError(f"Plex rejected the artwork update: {exc}") from exc

    logger.info(
        "Applied %s artwork to Plex ratingKey=%s from %s",
        normalized_kind,
        normalized_rating_key,
        normalized_path,
    )
    return {
        "ok": True,
        "ratingKey": normalized_rating_key,
        "kind": normalized_kind,
        "path": normalized_path,
    }


def auto_apply_result(rating_key: str | None, path: str, kind: str) -> dict[str, Any] | None:
    """Apply an uploaded asset when enabled without invalidating the saved upload."""

    if not auto_apply_enabled():
        return None

    normalized_rating_key = str(rating_key or "").strip()
    if not normalized_rating_key:
        return {
            "attempted": False,
            "ok": False,
            "error": "Artwork was saved, but no Plex rating key was provided.",
        }

    try:
        result = apply_artwork_file(normalized_rating_key, path, kind)
    except PlexArtworkError as exc:
        logger.warning(
            "Automatic Plex artwork application failed for ratingKey=%s path=%s: %s",
            normalized_rating_key,
            path,
            exc,
        )
        return {"attempted": True, "ok": False, "error": str(exc)}

    return {"attempted": True, **result}
