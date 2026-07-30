#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 4 of the framework extraction (see docs/extraction/ and
docs/adr/0014-persistence-split.md) moved this module's implementation
(100% generic single-row account CRUD, no music vocabulary at all) to
lunawave_framework.core.storage.admin_account_repo. This file exists
purely so existing imports keep working unchanged:

    from persistence.admin_account_repo import AdminAccountRepository
"""

from lunawave_framework.core.storage.admin_account_repo import AdminAccountRepository

__all__ = ["AdminAccountRepository"]
