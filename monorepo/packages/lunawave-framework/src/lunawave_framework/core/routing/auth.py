"""
Module: lunawave_framework.core.routing.auth

Purpose:
    Handle WebSocket authentication, session token verification, and
    per-IP login rate limiting.

Responsibilities:
    - Verify existing session tokens against the database.
    - Validate credentials via PBKDF2 (dibaca dari admin_account_repo).
    - Reject IPs that exceed 5 failed login attempts in a 5-minute window.
"""

import asyncio
import json
import secrets

import structlog

from lunawave_framework.core.logging.log_categories import LC_AUTH
from lunawave_framework.core.security.security import hash_password, needs_rehash, verify_password

logger = structlog.get_logger(component="ws.auth")

_DUMMY_PASSWORD_HASH = hash_password(secrets.token_hex(32))

def _prune_stale_ips(manager, now: float) -> None:
    WINDOW_AUTH = 300
    WINDOW_CMD = 60

    stale_auth = [
        ip
        for ip, ts_list in manager.login_attempts.items()
        if not any(now - t < WINDOW_AUTH for t in ts_list)
    ]
    for ip in stale_auth:
        del manager.login_attempts[ip]

    stale_cmd = [
        ip
        for ip, ts_list in manager.command_history.items()
        if not any(now - t < WINDOW_CMD for t in ts_list)
    ]
    for ip in stale_cmd:
        del manager.command_history[ip]


async def handle_auth(ws, data, manager, client_ip, sessions, admin_account, now):
    async with manager.rl_lock:
        _prune_stale_ips(manager, now)

        token = data.get("token")
        if token and sessions:
            if await sessions.verify_session(token):
                await sessions.extend_session(token, int(now) + 10800)
                manager.authenticated_connections.add(ws)
                logger.info("auth_token_verified", category=LC_AUTH, client_ip=client_ip)
                await ws.send_str(
                    json.dumps({"type": "auth_status", "data": {"success": True, "token": token}})
                )
                return

        attempts = manager.login_attempts.get(client_ip, [])
        attempts = [t for t in attempts if now - t < 300]
        if not attempts:
            manager.login_attempts.pop(client_ip, None)
        else:
            manager.login_attempts[client_ip] = attempts
        if len(attempts) >= 5:
            logger.warning(
                "auth_rate_limited",
                category=LC_AUTH,
                client_ip=client_ip,
                attempt_count=len(attempts),
            )
            await ws.send_str(
                json.dumps(
                    {
                        "type": "auth_status",
                        "data": {
                            "success": False,
                            "message": "Terlalu banyak percobaan login. Coba lagi dalam 5 menit.",
                        },
                    }
                )
            )
            return

    username = data.get("username", "")
    password = data.get("password", "")

    account = await admin_account.get_admin_account() if admin_account else None
    stored_hash = account["password_hash"] if account else _DUMMY_PASSWORD_HASH
    stored_username = account["username"] if account else None

    loop = asyncio.get_running_loop()
    password_matches = await loop.run_in_executor(None, verify_password, password, stored_hash)
    password_ok = password_matches and account is not None and username == stored_username

    async with manager.rl_lock:
        if password_ok:
            if account and needs_rehash(stored_hash):
                try:
                    new_hash = await loop.run_in_executor(None, hash_password, password)
                    await admin_account.update_password(new_hash)
                    logger.info("auth_password_rehashed", category=LC_AUTH, client_ip=client_ip)
                except Exception as e:
                    logger.warning("auth_password_rehash_failed", category=LC_AUTH, error=str(e))

            new_token = secrets.token_hex(16)
            if sessions:
                await sessions.create_session(new_token, int(now) + 10800)
                logger.info("auth_session_created", category=LC_AUTH, client_ip=client_ip)
            manager.authenticated_connections.add(ws)
            if client_ip in manager.login_attempts:
                del manager.login_attempts[client_ip]
            logger.info("auth_login_succeeded", category=LC_AUTH, client_ip=client_ip)
            await ws.send_str(
                json.dumps({"type": "auth_status", "data": {"success": True, "token": new_token}})
            )
        else:
            attempts = manager.login_attempts.get(client_ip, [])
            attempts = [t for t in attempts if now - t < 300]
            attempts.append(now)
            manager.login_attempts[client_ip] = attempts
            logger.info(
                "auth_login_rejected",
                category=LC_AUTH,
                client_ip=client_ip,
                reason="invalid_credentials",
            )
            await ws.send_str(
                json.dumps(
                    {
                        "type": "auth_status",
                        "data": {"success": False, "message": "Username atau Password salah!"},
                    }
                )
            )

def require_auth(manager, ws) -> bool:
    return ws in manager.authenticated_connections
