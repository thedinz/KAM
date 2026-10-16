"""Login password hashing with the standard library's scrypt."""
from __future__ import annotations

import base64
import hashlib
import secrets

_PREFIX = "scrypt"
_N = 2**14
_R = 8
_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=128 * r * (n + p + 2) + 1024 * 1024,
        dklen=_KEY_BYTES,
    )


def hash_password(password: str) -> str:
    """Return a salted hash of *password* in the form scrypt$n$r$p$salt$key."""
    salt = secrets.token_bytes(_SALT_BYTES)
    key = _derive(password, salt, _N, _R, _P)
    return "$".join([_PREFIX, str(_N), str(_R), str(_P), _b64(salt), _b64(key)])


def is_hash(value: str) -> bool:
    return value.startswith(_PREFIX + "$") and value.count("$") == 5


def verify_password(candidate: str, stored: str) -> bool:
    """Return whether *candidate* matches the hash *stored*."""
    try:
        prefix, n, r, p, salt, key = stored.split("$")
        if prefix != _PREFIX:
            return False
        expected = base64.b64decode(key)
        actual = _derive(candidate, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(actual, expected)
