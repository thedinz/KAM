"""Helpers for resolving Plex connection details from persisted settings."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

from . import settings as settings_service


@dataclass(frozen=True)
class PlexConfig:
    """Resolved Plex configuration."""

    url: str
    token: str


_TOKEN_KEYS = ("plexToken", "plex_token")
_URL_KEYS = ("plexUrl", "plex_url")

_TOKEN_PARAM = "X-Plex-Token"
_MAX_REDIRECTS = 5

_LOCK = threading.Lock()
_CACHE: Optional[PlexConfig] = None


def _coalesce_setting(data: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    return url.rstrip("/")


def _resolve_uncached() -> PlexConfig:
    data = settings_service.load_settings()
    url = _coalesce_setting(data, _URL_KEYS)
    token = _coalesce_setting(data, _TOKEN_KEYS)
    return PlexConfig(url=_normalize_url(url), token=token.strip())


def get_plex_config(*, force_refresh: bool = False) -> PlexConfig:
    """Return the current Plex configuration, optionally forcing a refresh."""
    global _CACHE
    if force_refresh:
        with _LOCK:
            cfg = _resolve_uncached()
            _CACHE = cfg
            return cfg

    if _CACHE is None:
        with _LOCK:
            if _CACHE is None:
                _CACHE = _resolve_uncached()
    assert _CACHE is not None
    return _CACHE


def clear_cache() -> None:
    """Clear any cached Plex configuration."""
    global _CACHE
    with _LOCK:
        _CACHE = None


def get_plex_url(*, force_refresh: bool = False) -> str:
    return get_plex_config(force_refresh=force_refresh).url


def get_plex_token(*, force_refresh: bool = False) -> str:
    return get_plex_config(force_refresh=force_refresh).token


def verify_ssl() -> bool:
    """Return whether TLS certificates should be verified for Plex requests."""
    raw = os.environ.get("PLEX_VERIFY_SSL", "true")
    return raw.strip().lower() not in {"false", "0", "no", "off"}


def is_plex_url(url: Optional[str]) -> bool:
    """Return whether *url* points at the configured Plex server.

    A plain prefix check would accept hosts such as ``plex:32400.example.com``
    and leak the Plex token to them, so compare the parsed origin instead.
    """
    base_url = get_plex_url()
    if not url or not base_url:
        return False
    try:
        base = urlsplit(base_url)
        target = urlsplit(str(url))
    except ValueError:
        return False
    if target.scheme.lower() != base.scheme.lower():
        return False
    if target.netloc.lower() != base.netloc.lower():
        return False
    base_path = base.path.rstrip("/")
    return not base_path or target.path == base_path or target.path.startswith(base_path + "/")


def without_token(url: str) -> str:
    """Return *url* without an X-Plex-Token query parameter."""
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() != _TOKEN_PARAM.lower()
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))


def plex_get(url: str, **kwargs: Any) -> requests.Response:
    """GET *url* on the configured Plex server.

    The token travels only in the X-Plex-Token header, never in the URL, so
    it can't end up in exception messages or logs. Redirects are followed
    only while they stay on the configured Plex server.
    """
    params = {
        key: value
        for key, value in (kwargs.pop("params", None) or {}).items()
        if key.lower() != _TOKEN_PARAM.lower()
    }
    headers = dict(kwargs.pop("headers", None) or {})
    token = get_plex_token()
    if token:
        headers[_TOKEN_PARAM] = token
    kwargs.setdefault("verify", verify_ssl())

    url = without_token(url)
    for _ in range(_MAX_REDIRECTS + 1):
        response = requests.get(
            url,
            params=params or None,
            headers=headers,
            allow_redirects=False,
            **kwargs,
        )
        if not response.is_redirect:
            return response
        location = urljoin(url, response.headers.get("Location") or "")
        response.close()
        if not is_plex_url(location):
            raise requests.RequestException("Plex redirected outside the configured server")
        url = without_token(location)
    raise requests.TooManyRedirects("Too many Plex redirects")
