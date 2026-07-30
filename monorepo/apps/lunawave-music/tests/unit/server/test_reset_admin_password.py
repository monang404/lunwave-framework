import pytest

from core.security import verify_password
from server.reset_admin_password import do_reset


@pytest.mark.asyncio
async def test_do_reset():
    import aiosqlite

    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            """CREATE TABLE admin_account (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            """CREATE TABLE sessions (
                token TEXT PRIMARY KEY,
                expires_at INTEGER NOT NULL
            )"""
        )

        # Test error if no account
        with pytest.raises(ValueError, match="Akun admin belum dibuat"):
            await do_reset("newpassword123", conn)

        await conn.execute(
            "INSERT INTO admin_account (username, password_hash, created_at) VALUES ('admin', 'old', 0)"
        )
        await conn.execute("INSERT INTO sessions (token, expires_at) VALUES ('token1', 9999999999)")
        await conn.commit()

        # Test error short password
        with pytest.raises(ValueError, match="Password minimal"):
            await do_reset("short", conn)

        await do_reset("newpassword123", conn)

        # Verify
        async with conn.execute("SELECT password_hash FROM admin_account") as cur:
            row = await cur.fetchone()
            assert verify_password("newpassword123", row["password_hash"])

        async with conn.execute("SELECT COUNT(*) as c FROM sessions") as cur:
            row = await cur.fetchone()
            assert row["c"] == 0
