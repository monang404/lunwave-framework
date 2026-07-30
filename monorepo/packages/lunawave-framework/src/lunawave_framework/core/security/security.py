"""
Module: lunawave_framework.core.security.security

Purpose:
    Provide PBKDF2-SHA256 password hashing, constant-time verification,
    and SHA-256 session token hashing.

Responsibilities:
    - Hash a plaintext password with a random 16-byte salt.
    - Verify a plaintext password against a stored pbkdf2 hash string.
    - Hash a session token (SHA-256, no salt needed — token entropy is already
      128-bit from secrets.token_hex(16)) before storing in the DB.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

import base64
import hashlib
import secrets

PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2:sha256:{PBKDF2_ITERATIONS}${base64.b64encode(salt).decode('utf-8')}${base64.b64encode(key).decode('utf-8')}"


def verify_password(password: str, hashed_password: str) -> bool:
    if not hashed_password.startswith("pbkdf2:sha256:"):
        # TASK-1.1: Tolak semua format non-pbkdf2 — hapus plaintext fallback
        # Plaintext comparison adalah security hole: password mentah tersimpan
        # di env var, log, dan /proc/self/environ.
        return False
    try:
        _, _, iterations, salt_b64, key_b64 = (
            hashed_password.split("$")[0].split(":") + hashed_password.split("$")[1:]
        )
        salt = base64.b64decode(salt_b64)
        expected_key = base64.b64decode(key_b64)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return secrets.compare_digest(key, expected_key)
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    if not hashed_password.startswith("pbkdf2:sha256:"):
        return False
    try:
        iterations = hashed_password.split("$")[0].split(":")[2]
        return int(iterations) < PBKDF2_ITERATIONS
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Hash a session token with SHA-256 for storage in the DB.

    Session tokens are generated via secrets.token_hex(16) (128-bit entropy),
    so a single-pass SHA-256 without salt is sufficient — no PBKDF2 needed.
    Returns a 64-character hex digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
