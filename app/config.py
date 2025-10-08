import os
from typing import List

from .services import plex_settings

PORT = int(os.environ.get("PORT", "8080"))

def get_config_errors() -> List[str]:
    errors: List[str] = []
    if not plex_settings.get_plex_url():
        errors.append("Missing PLEX_URL")
    if not plex_settings.get_plex_token():
        errors.append("Missing PLEX_TOKEN")
    return errors
