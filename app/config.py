import os

PLEX_URL = os.environ.get("PLEX_URL")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN")
PORT = int(os.environ.get("PORT", "8080"))

LIBRARY_MAPPINGS = {}
COLLECTIONS_ROOT = os.environ.get("COLLECTIONS_ROOT", "/assets/Collections")
raw = os.environ.get("LIBRARIES", "")
for e in filter(None, (x.strip() for x in raw.split(","))):
    if ":" in e:
        name, path = e.split(":", 1)
        LIBRARY_MAPPINGS[name.strip()] = path.strip()

CONFIG_ERRORS = []
if not PLEX_URL: CONFIG_ERRORS.append("Missing PLEX_URL")
if not PLEX_TOKEN: CONFIG_ERRORS.append("Missing PLEX_TOKEN")
if not LIBRARY_MAPPINGS:
    CONFIG_ERRORS.append("Missing LIBRARIES (e.g. Movies:/assets/Movies,Collections:/assets/Collections)")
