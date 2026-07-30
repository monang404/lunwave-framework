"""
Module: lunawave_framework.core.storage.session_repo

Purpose:
    Manages authentication session tokens, verifying and cleaning up expired sessions.

Responsibilities:
    - Store and verify session tokens by their SHA-256 hash (never the raw token).
    - Clean up expired sessions.

Depends on:
    lunawave_framework.core.security (hash_token)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import time

from lunawave_framework.core.security.security import hash_token


class SessionRepository:
    def __init__(self, conn):
        self._conn = conn

    async def create_session(self, token: str, expires_at: int):
        """Store the SHA-256 hash of token, never the raw token."""
        await self._conn.execute(
            "INSERT INTO sessions (token, expires_at) VALUES (?, ?)",
            (hash_token(token), expires_at),
        )
        await self._conn.commit()

    async def extend_session(self, token: str, expires_at: int):
        await self._conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE token = ?",
            (expires_at, hash_token(token)),
        )
        await self._conn.commit()

    async def verify_session(self, token: str) -> bool:
        now = int(time.time())
        token_hash = hash_token(token)
        async with self._conn.execute(
            "SELECT expires_at FROM sessions WHERE token = ?", (token_hash,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row["expires_at"] > now:
                return True
            if row:
                await self.delete_session(token)
            return False

    async def delete_session(self, token: str):
        await self._conn.execute("DELETE FROM sessions WHERE token = ?", (hash_token(token),))
        await self._conn.commit()

    async def delete_all_sessions(self):
        """Menghapus semua sesi tanpa filter user. Aman karena aplikasi menggunakan arsitektur single-admin."""
        await self._conn.execute("DELETE FROM sessions")
        await self._conn.commit()

    async def cleanup_sessions(self):
        now = int(time.time())
        await self._conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        await self._conn.commit()
