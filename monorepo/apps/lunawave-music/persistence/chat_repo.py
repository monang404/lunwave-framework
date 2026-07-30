"""
Module: persistence.chat_repo

Purpose:
    Repository untuk fitur chat (client <-> admin). Menyimpan dan mengambil
    pesan chat, disegmentasi per `client_uid` -- BUKAN per `client_ip`.

Responsibilities:
    - Simpan pesan chat baru (add_message).
    - Ambil riwayat pesan, opsional difilter per client_uid
      (get_recent_messages).

Depends on:
    - aiosqlite

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from typing import Any

import aiosqlite
import structlog

logger = structlog.get_logger(component="persistence.chat")


class ChatRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def add_message(
        self,
        sender_name: str,
        message: str,
        is_admin: bool = False,
        client_uid: str | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """Menambahkan pesan chat baru ke database dan mengembalikan record tersebut.

        client_uid adalah kunci identitas/segmentasi sesungguhnya (UUID
        per-browser, dikirim dari client). client_ip HANYA disimpan untuk
        keperluan audit/log -- TIDAK dipakai lagi untuk memutuskan siapa
        boleh melihat pesan siapa, karena request.remote tidak reliable di
        balik reverse proxy (lihat docs/PATCHLOG.md, patch client_uid chat).
        """
        async with self.conn.execute(
            "INSERT INTO chat_messages (sender_name, message, is_admin, client_uid, client_ip) "
            "VALUES (?, ?, ?, ?, ?)",
            (sender_name, message, 1 if is_admin else 0, client_uid, client_ip),
        ) as cursor:
            await self.conn.commit()
            msg_id = cursor.lastrowid

        async with self.conn.execute(
            "SELECT id, sender_name, message, is_admin, client_uid, client_ip, created_at "
            "FROM chat_messages WHERE id = ?",
            (msg_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}

    async def get_recent_messages(
        self, limit: int = 100, client_uid: str | None = None
    ) -> list[dict[str, Any]]:
        """Mengambil pesan chat terbaru, diurutkan dari yang terlama ke terbaru
        (untuk di-render). Difilter per client_uid (thread 1:1 client<->admin);
        client_uid=None (khusus admin) mengembalikan semua thread tercampur."""
        params: tuple[Any, ...]
        if client_uid:
            query = (
                "SELECT id, sender_name, message, is_admin, client_uid, client_ip, created_at "
                "FROM chat_messages WHERE client_uid = ? ORDER BY id DESC LIMIT ?"
            )
            params = (client_uid, limit)
        else:
            query = (
                "SELECT id, sender_name, message, is_admin, client_uid, client_ip, created_at "
                "FROM chat_messages ORDER BY id DESC LIMIT ?"
            )
            params = (limit,)

        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            # Balik urutan agar yang tertua di atas, terbaru di bawah.
            # list(...) dulu -- aiosqlite.Row asinkron/hasil fetchall()
            # bertipe Iterable biasa (bukan Reversible), reversed() langsung
            # ke situ tidak match overload manapun di mypy.
            return [dict(row) for row in reversed(list(rows))]
