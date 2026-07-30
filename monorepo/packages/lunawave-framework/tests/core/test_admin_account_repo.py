"""
Module: tests.core.test_admin_account_repo

Purpose:
    Unit tests for the admin_account repository: create/read lifecycle
    and the UNIQUE(username) constraint that guards against a second
    admin account being created. Moved from the app repo's
    tests/unit/persistence/test_admin_account_repo.py in Phase 4 (see
    ADR 0014). Uses a self-contained in-memory `admin_account` table
    instead of the app's full `Repositories`/`db` fixture, so this test
    never depends on the app repo.

Depends on:
    - lunawave_framework.core.storage.admin_account_repo

Thread Safety:
    Main thread (async event loop).
"""

import sqlite3

import aiosqlite
import pytest

from lunawave_framework.core.storage.admin_account_repo import AdminAccountRepository


@pytest.fixture
async def repo():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            """CREATE TABLE admin_account (
                username TEXT UNIQUE,
                password_hash TEXT,
                created_at INTEGER
            )"""
        )
        yield AdminAccountRepository(conn)


async def test_get_admin_account_returns_none_when_empty(repo):
    assert await repo.get_admin_account() is None


async def test_admin_account_exists_false_when_empty(repo):
    assert await repo.admin_account_exists() is False


async def test_create_then_get_admin_account(repo):
    await repo.create_admin_account("admin", "pbkdf2:sha256:100000$salt$key")
    row = await repo.get_admin_account()
    assert row is not None
    assert row["username"] == "admin"
    assert row["password_hash"] == "pbkdf2:sha256:100000$salt$key"
    assert row["created_at"] is not None


async def test_admin_account_exists_true_after_create(repo):
    await repo.create_admin_account("admin", "pbkdf2:sha256:100000$salt$key")
    assert await repo.admin_account_exists() is True


async def test_create_admin_account_duplicate_username_raises_unique_error(repo):
    await repo.create_admin_account("admin", "hash-1")
    with pytest.raises(sqlite3.IntegrityError):
        await repo.create_admin_account("admin", "hash-2")
    # Baris pertama tidak boleh ter-overwrite oleh percobaan kedua yang gagal.
    row = await repo.get_admin_account()
    assert row["password_hash"] == "hash-1"


async def test_update_password_changes_hash(repo):
    await repo.create_admin_account("admin", "old-hash")
    await repo.update_password("new-hash")
    row = await repo.get_admin_account()
    assert row["password_hash"] == "new-hash"
