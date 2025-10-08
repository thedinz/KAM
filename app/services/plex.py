import logging

from plexapi.server import PlexServer
from fastapi import HTTPException

from .. import config
from . import plex_settings

_plex = None
_last_creds = (None, None)

logger = logging.getLogger(__name__)


def get_plex():
    global _plex, _last_creds
    errors = config.get_config_errors()
    if errors:
        logger.error("Plex credentials missing: %s", "; ".join(errors))
        raise HTTPException(
            status_code=400,
            detail="Please go to the settings and enter Plex credentials.",
        )

    cfg = plex_settings.get_plex_config()
    creds = (cfg.url, cfg.token)
    if _plex is None or creds != _last_creds:
        try:
            _plex = PlexServer(cfg.url, cfg.token)
            _last_creds = creds
        except Exception as e:
            logger.exception("Failed to connect to Plex")
            message = str(e)
            detail = "Plex connect failed: {0}".format(message)
            lowered = message.lower()
            if "unauthorized" in lowered or "401" in lowered:
                detail = "Plex credentials incorrect."
            raise HTTPException(status_code=400, detail=detail)
    return _plex


def clear_cache() -> None:
    """Reset the cached Plex client."""

    global _plex, _last_creds
    _plex = None
    _last_creds = (None, None)
