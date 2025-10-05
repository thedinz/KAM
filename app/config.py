import os
from typing import List

from .services import plex_settings

PORT = int(os.environ.get("PORT", "8080"))

LIBRARY_MAPPINGS = {}
COLLECTIONS_ROOT = os.environ.get("COLLECTIONS_ROOT", "/assets/Collections")
raw = os.environ.get("LIBRARIES", "")
for e in filter(None, (x.strip() for x in raw.split(","))):
    if ":" in e:
        name, path = e.split(":", 1)
        LIBRARY_MAPPINGS[name.strip()] = path.strip()

def get_config_errors() -> List[str]:
    errors: List[str] = []
    if not plex_settings.get_plex_url():
        errors.append("Missing PLEX_URL")
    if not plex_settings.get_plex_token():
        errors.append("Missing PLEX_TOKEN")
    if not LIBRARY_MAPPINGS:
        errors.append("Missing LIBRARIES (e.g. Movies:/assets/Movies,Collections:/assets/Collections)")
    return errors
