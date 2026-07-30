"""
Module: lunawave_framework.core.storage.admin_account_repo

Purpose:
    Manages the single admin_account row: the sole source of truth for
    login credentials under a single-admin auth design. Populated via
    an app-defined initial-setup flow, never auto-generated.

Responsibilities:
    - Create the admin account (single row, enforced by UNIQUE on username).
    - Read the admin account, or report whether one exists yet.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import time


class AdminAccountRepository:
    def __init__(self, conn):
        self._conn = conn

    async def create_admin_account(self, username: str, password_hash: str):
        """Insert satu baris admin_account. Hashing dilakukan di caller
        (mis. server.handlers.setup di aplikasi) — layer ini tidak tahu
        apa-apa soal algoritma hash. UNIQUE constraint pada kolom username
        akan melempar IntegrityError kalau caller mencoba insert kedua
        kali; caller bertanggung jawab menangani itu (kontrak
        race-condition submit ganda)."""
        now = int(time.time())
        await self._conn.execute(
            "INSERT INTO admin_account (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, now),
        )
        await self._conn.commit()

    async def update_password(self, password_hash: str):
        """Update hash password untuk akun admin yang sudah ada. Caller bertanggung jawab
        melakukan hashing; layer ini tidak tahu menahu algoritma hashing."""
        await self._conn.execute("UPDATE admin_account SET password_hash = ?", (password_hash,))
        await self._conn.commit()

    async def get_admin_account(self):
        """Return row admin_account pertama (dan satu-satunya yang
        diharapkan) sebagai dict-like `aiosqlite.Row`, atau None kalau
        tabel masih kosong (instalasi baru, belum lewat Initial Setup)."""
        async with self._conn.execute(
            "SELECT username, password_hash, created_at FROM admin_account LIMIT 1"
        ) as cursor:
            return await cursor.fetchone()

    async def admin_account_exists(self) -> bool:
        """Konsisten dengan get_admin_account(): True persis ketika
        get_admin_account() akan mengembalikan sebuah row."""
        return await self.get_admin_account() is not None
