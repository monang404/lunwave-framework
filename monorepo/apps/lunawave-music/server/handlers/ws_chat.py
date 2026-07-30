"""
Module: server.handlers.ws_chat

Purpose:
    Handler perintah WebSocket untuk fitur chat (client <-> admin).

Responsibilities:
    - `get_chat_history`: kirim riwayat pesan ke pemanggil.
    - `send_chat`: simpan pesan baru lalu broadcast ke koneksi yang relevan.
    - Segmentasi thread chat berdasarkan `client_uid` (UUID per-browser
      dikirim client, lihat web/static/js/client.js::getClientUid()) --
      BUKAN `client_ip`. `client_ip`/`request.remote` tidak reliable
      sebagai kunci identitas begitu server diakses lewat reverse proxy
      (Nginx/Cloudflare Tunnel/ngrok -- semua direkomendasikan di README):
      semua client eksternal akan terlihat sebagai satu IP yang sama,
      sehingga chat antar user berbeda bisa saling bocor. Lihat
      docs/PATCHLOG.md untuk detail patch ini.

Depends on:
    - persistence.Repositories
    - server.connection_manager.ConnectionManager (client_uids map)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import json
from typing import Any

import structlog

from persistence import Repositories

logger = structlog.get_logger(component="ws.chat")

# Batas panjang input chat -- vektor DoS kecil (spam ke SQLite + broadcast
# ke semua koneksi aktif) kalau dibiarkan tanpa batas. Angka longgar,
# cukup untuk percakapan wajar tapi menutup kasus ekstrem.
MAX_MESSAGE_LEN = 2000
MAX_SENDER_NAME_LEN = 60


async def handle_chat_command(
    action: str,
    data: dict[str, Any],
    ws,
    repos: Repositories,
    manager,
    is_admin: bool,
    client_ip: str,
):
    if not repos.chat:
        return

    # client_uid adalah identitas asli (lihat docstring modul). Admin tidak
    # kirim client_uid sendiri -- admin diidentifikasi lewat is_admin, dan
    # memilih thread client mana yang mau dilihat/dibalas lewat target_uid.
    client_uid = (data.get("client_uid") or "").strip()[:80] or None
    if client_uid:
        try:
            manager.bind_client_uid(ws, client_uid)
        except PermissionError:
            await ws.send_str(
                json.dumps(
                    {"type": "error", "message": "Sesi chat tidak valid."}, ensure_ascii=False
                )
            )
            return

    if action == "get_chat_history":
        target_uid: str | None
        if is_admin:
            raw_target = data.get("target_uid")
            target_uid = str(raw_target) if raw_target else None
        else:
            target_uid = manager.client_uids.get(ws)
        if not is_admin and not target_uid:
            # Client tanpa client_uid (browser lama/JS gagal load) -- tidak
            # ada thread yang bisa ditentukan dengan aman, jangan tebak
            # pakai IP lagi.
            return
        messages = await repos.chat.get_recent_messages(client_uid=target_uid)
        await ws.send_str(
            json.dumps({"type": "chat_history", "data": messages}, ensure_ascii=False)
        )

    elif action == "send_chat":
        sender = (data.get("sender_name") or "Anonymous").strip()[:MAX_SENDER_NAME_LEN]
        message = (data.get("message") or "").strip()[:MAX_MESSAGE_LEN]
        target_uid_send: str | None
        if is_admin:
            raw_target = data.get("target_uid")
            target_uid_send = str(raw_target) if raw_target else None
        else:
            target_uid_send = manager.client_uids.get(ws)

        if not sender:
            sender = "Anonymous"
        if not message or not target_uid_send:
            return

        saved_msg = await repos.chat.add_message(
            sender, message, is_admin, client_uid=target_uid_send, client_ip=client_ip
        )

        if saved_msg:
            payload = json.dumps({"type": "chat_message", "data": saved_msg}, ensure_ascii=False)

            for conn in manager.active_connections:
                conn_is_admin = conn in manager.authenticated_connections
                conn_uid = manager.client_uids.get(conn)

                # Kirim ke Admin ATAU ke Klien yang bersangkutan (dicocokkan
                # lewat client_uid, bukan IP).
                if conn_is_admin or conn_uid == target_uid_send:
                    try:
                        await conn.send_str(payload)
                    except Exception:
                        pass
