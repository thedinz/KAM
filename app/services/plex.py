from plexapi.server import PlexServer
from fastapi import HTTPException

from .. import config
from . import plex_settings

_plex = None
_last_creds = (None, None)


def get_plex():
    global _plex, _last_creds
    errors = config.get_config_errors()
    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    cfg = plex_settings.get_plex_config()
    creds = (cfg.url, cfg.token)
    if _plex is None or creds != _last_creds:
        try:
            _plex = PlexServer(cfg.url, cfg.token)
            _last_creds = creds
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Plex connect failed: {e}")
    return _plex
