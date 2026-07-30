"""tests/unit/core/test_security.py — mirrors core/security.py
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

from lunawave_framework.core.security.security import PBKDF2_ITERATIONS, hash_password, verify_password


def test_hash_password_produces_pbkdf2_sha256_format():
    hashed = hash_password("hunter2")
    parts = hashed.split("$")
    assert len(parts) == 3
    assert parts[0] == f"pbkdf2:sha256:{PBKDF2_ITERATIONS}"


def test_hash_password_is_salted_and_nondeterministic():
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_password_rejects_plaintext_fallback():
    """TASK-1.1: no plaintext comparison — anything not prefixed
    'pbkdf2:sha256:' must be rejected outright."""
    assert verify_password("secret", "secret") is False
    assert verify_password("secret", "") is False
    assert verify_password("secret", "md5:deadbeef") is False


def test_verify_password_handles_malformed_hash_gracefully():
    assert verify_password("secret", "pbkdf2:sha256:100000$not-base64$also-not") is False
    assert verify_password("secret", "pbkdf2:sha256:not-an-int$c2FsdA==$a2V5") is False


def test_verify_password_empty_password_against_real_hash():
    hashed = hash_password("")
    assert verify_password("", hashed) is True
    assert verify_password("nonempty", hashed) is False
