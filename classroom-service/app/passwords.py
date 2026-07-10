import hashlib
import hmac
import os
import secrets

_ITERATIONS = 260_000
_ALGO = "sha256"

# Excludes visually-confusable characters (0/O, 1/I/l) - this is read aloud
# or typed by hand by students. 8 chars from this 31-char alphabet is ~39
# bits of entropy, versus the old system's 6-digit-only default (~20 bits).
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_join_password(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def hash_password(password: str) -> str:
    """One format, always a hash - the old system's join_password column
    ambiguously held either plaintext or a hash. Here there is only one."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(_ALGO, password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_{_ALGO}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo_label, iterations_str, salt_hex, digest_hex = stored.split("$")
        algo = algo_label.removeprefix("pbkdf2_")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac(algo, password.encode(), salt, iterations)
    return hmac.compare_digest(candidate, expected)
