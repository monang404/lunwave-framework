"""
Module: tests.core.test_session_repo

Purpose:
    Unit tests for session token creation, verification, and cleanup.
    Moved from the app repo's tests/unit/persistence/test_session_repo.py
    and test_session_repo_delete_all.py in Phase 4 (see ADR 0014). Uses a
    self-contained in-memory `sessions` table instead of the app's full
    `Repositories`/`db` fixture, so this test never depends on the app repo.

Depends on:
    - lunawave_framework.core.storage.session_repo

Thread Safety:
    Main thread (async event loop).
"""

import time

import aiosqlite
import pytest

from lunawave_framework.core.storage.session_repo import SessionRepository


@pytest.fixture
async def repo():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            """CREATE TABLE sessions (
                token TEXT PRIMARY KEY,
                expires_at INTEGER NOT NULL
            )"""
        )
        yield SessionRepository(conn)


async def test_create_verify_delete_session_lifecycle(repo):
    now = int(time.time())
    await repo.create_session("token-123", now + 3600)
    assert await repo.verify_session("token-123") is True
    await repo.delete_session("token-123")
    assert await repo.verify_session("token-123") is False


async def test_verify_session_unknown_token_returns_false(repo):
    assert await repo.verify_session("never-created") is False


async def test_verify_session_expired_token_returns_false_and_self_deletes(repo):
    now = int(time.time())
    await repo.create_session("expired-token", now - 10)
    assert await repo.verify_session("expired-token") is False
    async with repo._conn.execute(
        "SELECT 1 FROM sessions WHERE token = ?", ("expired-token",)
    ) as cursor:
        assert await cursor.fetchone() is None


async def test_verify_session_boundary_expires_at_equal_now_is_expired(repo):
    now = int(time.time())
    await repo.create_session("boundary-token", now)
    assert await repo.verify_session("boundary-token") is False


async def test_cleanup_sessions_removes_all_expired_but_keeps_valid(repo):
    now = int(time.time())
    await repo.create_session("old-1", now - 100)
    await repo.create_session("old-2", now - 1)
    await repo.create_session("valid", now + 100)
    await repo.cleanup_sessions()
    assert await repo.verify_session("old-1") is False
    assert await repo.verify_session("old-2") is False
    assert await repo.verify_session("valid") is True


async def test_delete_all_sessions_removes_every_token(repo):
    now = int(time.time())
    await repo.create_session("token1", now + 3600)
    await repo.create_session("token2", now + 3600)
    await repo.delete_all_sessions()
    assert await repo.verify_session("token1") is False
    assert await repo.verify_session("token2") is False


async def test_extend_session_updates_expiry():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            """CREATE TABLE sessions (
                token TEXT PRIMARY KEY,
                expires_at INTEGER NOT NULL
            )"""
        )
        repo = SessionRepository(conn)
        now = int(time.time())
        await repo.create_session("token-x", now - 10)
        assert await repo.verify_session("token-x") is False

        # Re-create then extend, since verify_session self-deletes expired rows.
        await repo.create_session("token-x", now - 10)
        await repo.extend_session("token-x", now + 3600)
        assert await repo.verify_session("token-x") is True
