"""Helpers for building Plex asset URLs."""
from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from . import plex_settings


def _normalize_path(path: Optional[str], rating_key: Optional[str], kind: str) -> Optional[str]:
    resolved_path = path or (f"/library/metadata/{rating_key}/{kind}" if rating_key else None)
    if not resolved_path:
        return None

    if resolved_path.startswith("http://") or resolved_path.startswith("https://"):
        parsed = urlsplit(resolved_path)
        return urlunsplit(("", "", parsed.path, parsed.query, ""))

    if not resolved_path.startswith("/"):
        resolved_path = f"/{resolved_path}"
    return resolved_path


def _strip_token(path: str) -> str:
    parsed = urlsplit(path)
    if not parsed.query:
        return path
    filtered = [(key, value) for key, value in parse_qsl(parsed.query) if key != "X-Plex-Token"]
    query = urlencode(filtered)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def build_plex_asset_url(
    path: Optional[str],
    rating_key: Optional[str],
    kind: str,
) -> Optional[str]:
    """Return a usable Plex asset URL with token attached when possible."""
    cfg = plex_settings.get_plex_config()
    if not cfg.url or not cfg.token:
        return None

    resolved_path = _normalize_path(path, rating_key, kind)
    if not resolved_path:
        return None

    if resolved_path.startswith("http://") or resolved_path.startswith("https://"):
        base = resolved_path
    else:
        base = f"{cfg.url}{resolved_path}"

    if "X-Plex-Token=" in base:
        return base

    separator = "&" if "?" in base else "?"
    return f"{base}{separator}X-Plex-Token={cfg.token}"


def build_plex_proxy_url(
    path: Optional[str],
    rating_key: Optional[str],
    kind: str,
) -> Optional[str]:
    """Return a local proxy URL for a Plex asset."""
    resolved_path = _normalize_path(path, rating_key, kind)
    if not resolved_path:
        return None
    stripped = _strip_token(resolved_path)
    return f"/api/plex/image?path={quote(stripped, safe='')}"
