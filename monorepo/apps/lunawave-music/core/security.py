#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.security import hash_password, verify_password, needs_rehash, hash_token
"""

from lunawave_framework.core.security.security import (
    PBKDF2_ITERATIONS,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)

__all__ = [
    "PBKDF2_ITERATIONS",
    "hash_password",
    "verify_password",
    "needs_rehash",
    "hash_token",
]
