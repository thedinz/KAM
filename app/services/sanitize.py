# app/services/sanitize.py
import unicodedata
import re

# Optional generic safety helpers if you need them later
_ILLEGAL_CTRL = re.compile(r"[\u0000-\u001F]")

def kometa_sanitize_folder(name: str) -> str:
    """
    Match Kometa's observed folder naming for assets:
    - Normalize unicode (NFKC)
    - Strip colon ':' characters
    - Trim whitespace
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", str(name))
    s = s.replace(":", "")            # Kometa strips colons
    s = _ILLEGAL_CTRL.sub("", s)      # strip control chars, just in case
    return s.strip()
