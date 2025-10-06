import os
from typing import List

from .services import library_mappings, plex_settings

PORT = int(os.environ.get("PORT", "8080"))

LIBRARY_MAPPINGS = {}
COLLECTIONS_ROOT = os.environ.get("COLLECTIONS_ROOT", "/assets/Collections")
for entry in library_mappings.seed_from_env():
    name = str(entry.get("library") or "").strip()
    path = str(entry.get("assetPath") or "").strip()
    if name and path:
        LIBRARY_MAPPINGS[name] = path

def get_config_errors() -> List[str]:
    errors: List[str] = []
    if not plex_settings.get_plex_url():
        errors.append("Missing PLEX_URL")
    if not plex_settings.get_plex_token():
        errors.append("Missing PLEX_TOKEN")
    return errors
