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


_PROXY_PATH = "/api/plex/image"


def build_plex_asset_url(
    path: Optional[str],
    rating_key: Optional[str],
    kind: str,
) -> Optional[str]:
    """Return the proxy URL of a Plex asset, or None while Plex isn't configured.

    The browser never gets a URL that carries the Plex token; it loads Plex
    artwork through KAM, and imports turn the URL back into a Plex one.
    """
    cfg = plex_settings.get_plex_config()
    if not cfg.url or not cfg.token:
        return None
    return build_plex_proxy_url(path, rating_key, kind)


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
    return f"{_PROXY_PATH}?path={quote(stripped, safe='')}"


def plex_source_url(url: Optional[str]) -> Optional[str]:
    """Return the token-free Plex URL behind a proxy URL or Plex URL, else None.

    Plex requests add the token themselves, so the result never contains it.
    """
    cfg = plex_settings.get_plex_config()
    if not url or not cfg.url:
        return None
    parts = urlsplit(url)
    if not parts.scheme and not parts.netloc and parts.path == _PROXY_PATH:
        query = dict(parse_qsl(parts.query))
        kind = "art" if query.get("kind", "").lower() in ("art", "background") else "thumb"
        path = _normalize_path(query.get("path"), query.get("ratingKey"), kind)
        if not path:
            return None
        return plex_settings.without_token(f"{cfg.url}{path}")
    if plex_settings.is_plex_url(url):
        return plex_settings.without_token(url)
    return None
