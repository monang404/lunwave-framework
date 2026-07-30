"""
Module: lunawave_framework.core.routing.setup

Purpose:
    Handle Initial Setup: creation of the single admin_account row that
    becomes the sole source of login credentials.
"""

import asyncio
import json
import sqlite3

import structlog
from aiohttp import web

from lunawave_framework.core.logging.log_categories import LC_AUTH
from lunawave_framework.core.security.security import hash_password
from lunawave_framework.core.routing.context import get_admin_account

logger = structlog.get_logger(component="ws.setup")

MIN_PASSWORD_LENGTH = 8
RATE_LIMIT_WINDOW_SEC = 300
RATE_LIMIT_MAX_ATTEMPTS = 5

_ALREADY_SET_UP_MESSAGE = "Akun admin sudah pernah dibuat. Silakan login."


def _validate_setup_input(username: str, password: str) -> str | None:
    if not username or not username.strip():
        return "Username wajib diisi."
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password minimal {MIN_PASSWORD_LENGTH} karakter."
    return None


def _prune_stale_setup_ips(manager, now: float) -> None:
    stale = [
        ip
        for ip, ts_list in manager.setup_attempts.items()
        if not any(now - t < RATE_LIMIT_WINDOW_SEC for t in ts_list)
    ]
    for ip in stale:
        del manager.setup_attempts[ip]


async def handle_setup_admin(ws, data, manager, client_ip, admin_account, now):
    async with manager.rl_lock:
        _prune_stale_setup_ips(manager, now)

        attempts = manager.setup_attempts.get(client_ip, [])
        attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SEC]
        if attempts:
            manager.setup_attempts[client_ip] = attempts
        else:
            manager.setup_attempts.pop(client_ip, None)

        if len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
            await ws.send_str(
                json.dumps(
                    {
                        "type": "setup_status",
                        "data": {
                            "success": False,
                            "message": "Terlalu banyak percobaan. Coba lagi dalam 5 menit.",
                        },
                    }
                )
            )
            return

        def _record_failure():
            attempts.append(now)
            manager.setup_attempts[client_ip] = attempts

        username = data.get("username", "")
        password = data.get("password", "")

        error = _validate_setup_input(username, password)
        if error:
            _record_failure()
            await ws.send_str(
                json.dumps({"type": "setup_status", "data": {"success": False, "message": error}})
            )
            return

        try:
            already_exists = await admin_account.admin_account_exists()
        except Exception:
            logger.error(
                "setup_admin_exists_check_failed",
                category=LC_AUTH,
                client_ip=client_ip,
                exc_info=True,
            )
            _record_failure()
            await ws.send_str(
                json.dumps(
                    {
                        "type": "setup_status",
                        "data": {
                            "success": False,
                            "message": "Gagal menyimpan akun admin. Coba lagi, atau cek log server.",
                        },
                    }
                )
            )
            return
        if already_exists:
            _record_failure()
            await ws.send_str(
                json.dumps(
                    {
                        "type": "setup_status",
                        "data": {"success": False, "message": _ALREADY_SET_UP_MESSAGE},
                    }
                )
            )
            return

    loop = asyncio.get_running_loop()
    password_hash = await loop.run_in_executor(None, hash_password, password)

    try:
        await admin_account.create_admin_account(username.strip(), password_hash)
    except sqlite3.IntegrityError:
        async with manager.rl_lock:
            attempts = manager.setup_attempts.get(client_ip, [])
            attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SEC]
            attempts.append(now)
            manager.setup_attempts[client_ip] = attempts
        await ws.send_str(
            json.dumps(
                {
                    "type": "setup_status",
                    "data": {"success": False, "message": _ALREADY_SET_UP_MESSAGE},
                }
            )
        )
        return
    except Exception:
        logger.error("setup_admin_failed", category=LC_AUTH, client_ip=client_ip, exc_info=True)
        await ws.send_str(
            json.dumps(
                {
                    "type": "setup_status",
                    "data": {
                        "success": False,
                        "message": "Gagal menyimpan akun admin. Coba lagi, atau cek log server.",
                    },
                }
            )
        )
        return

    async with manager.rl_lock:
        manager.setup_attempts.pop(client_ip, None)

    await ws.send_str(json.dumps({"type": "setup_status", "data": {"success": True}}))


async def setup_required(request: web.Request) -> web.Response:
    admin_account = get_admin_account(request)
    if admin_account is None:
        raise RuntimeError("admin_account must be set on app before handling requests")
    try:
        exists = await admin_account.admin_account_exists()
    except Exception:
        logger.error("setup_required_check_failed", category=LC_AUTH, exc_info=True)
        return web.json_response(
            {"error": "Gagal memeriksa status setup. Cek log server."}, status=503
        )
    return web.json_response({"setup_required": not exists})
