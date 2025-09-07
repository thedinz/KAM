from plexapi.server import PlexServer
from fastapi import HTTPException
from .. import config

_plex = None

def get_plex():
    global _plex
    if _plex is None:
        if config.CONFIG_ERRORS:
            raise HTTPException(status_code=500, detail="; ".join(config.CONFIG_ERRORS))
        try:
            _plex = PlexServer(config.PLEX_URL, config.PLEX_TOKEN)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Plex connect failed: {e}")
    return _plex
