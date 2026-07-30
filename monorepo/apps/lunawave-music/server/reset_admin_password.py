"""
Module: server.reset_admin_password

Purpose:
    CLI untuk reset password admin.
    Dijalankan via: python -m server.reset_admin_password

Subscribes to:
    None

Publishes:
    None
"""

import asyncio
import getpass
import sqlite3
import sys

from config import DB_PATH
from lunawave_framework.core.security.security import hash_password
from lunawave_framework.core.routing.setup import MIN_PASSWORD_LENGTH
from persistence.admin_account_repo import AdminAccountRepository
from persistence.session_repo import SessionRepository


async def do_reset(new_password: str, conn: sqlite3.Connection):
    if not new_password or len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password minimal {MIN_PASSWORD_LENGTH} karakter.")

    admin_repo = AdminAccountRepository(conn)
    session_repo = SessionRepository(conn)

    if not await admin_repo.admin_account_exists():
        raise ValueError("Akun admin belum dibuat (belum Initial Setup).")

    hashed = hash_password(new_password)
    await admin_repo.update_password(hashed)
    await session_repo.delete_all_sessions()
    print("Berhasil! Password admin direset dan semua sesi lama telah dicabut.")


async def main():
    if not sys.stdin.isatty():
        print("Skrip ini membutuhkan terminal interaktif untuk menginput password.")
        print("Penggunaan: python -m server.reset_admin_password")
        sys.exit(1)

    print("--- Reset Password Admin ---")
    try:
        import aiosqlite
    except ImportError:
        print("aiosqlite tidak ditemukan")
        sys.exit(1)

    try:
        new_pass = getpass.getpass("Password baru: ")
        confirm_pass = getpass.getpass("Ketik ulang password baru: ")

        if new_pass != confirm_pass:
            print("Error: Password tidak cocok.")
            sys.exit(1)

        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            await do_reset(new_pass, conn)
    except Exception as e:
        print(f"Gagal mereset password: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
