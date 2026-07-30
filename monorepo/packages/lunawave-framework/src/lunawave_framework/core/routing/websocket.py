"""
Module: lunawave_framework.core.routing.websocket

Purpose:
    Provide the core WebSocket router that handles CSWSH protection,
    authentication, rate limiting, and dispatches generic actions to registered
    domain-specific handlers.
"""

import json
import time
from urllib.parse import urlparse
from typing import Callable, Dict, Any, Awaitable

import aiohttp
import structlog
from aiohttp import web

from lunawave_framework.core.logging.log_categories import LC_SECURITY, LC_SESSION, LC_COMMAND
from lunawave_framework.core.routing.context import get_manager, get_sessions, get_admin_account
from lunawave_framework.core.routing.auth import handle_auth, require_auth
from lunawave_framework.core.routing.setup import handle_setup_admin

logger = structlog.get_logger(component="ws.router")

def check_ws_origin(request) -> bool:
    origin = request.headers.get("Origin", "")
    if not origin:
        return True
    try:
        origin_host = urlparse(origin).netloc
    except Exception:
        return False
    return origin_host.lower() == request.host.lower()

class WsRouter:
    def __init__(self):
        self.handlers: Dict[str, Callable[[str, dict, web.WebSocketResponse, str, float], Awaitable[None]]] = {}
        self.on_connect_hooks: list = []

    def register_handler(self, action: str, handler: Callable):
        """Register a handler for a specific action string."""
        self.handlers[action] = handler

    def register_on_connect(self, hook: Callable):
        """Register a hook to run when a client connects (e.g. to send initial state)."""
        self.on_connect_hooks.append(hook)

    async def ws_handler(self, request):
        if not check_ws_origin(request):
            logger.warning(
                "ws_handshake_rejected_origin_mismatch",
                category=LC_SECURITY,
                origin=request.headers.get("Origin", ""),
                host=request.host,
            )
            return web.Response(status=403, text="Forbidden: cross-origin WebSocket not allowed")

        manager = get_manager(request)
        sessions = get_sessions(request)
        admin_account = get_admin_account(request)

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await manager.connect(ws, request)

        try:
            for hook in self.on_connect_hooks:
                await hook(ws, request)
        except Exception:
            manager.disconnect(ws)
            return ws

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    await self.handle_ws_message(
                        data, ws, request, manager, sessions, admin_account
                    )
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        except Exception as e:
            logger.error(
                "ws_connection_error", category=LC_SESSION, error_type=type(e).__name__, error=str(e)
            )
        finally:
            manager.disconnect(ws)

        return ws

    async def handle_ws_message(
        self, msg: dict, ws, request, manager, sessions, admin_account
    ):
        msg_type = msg.get("type")
        action = msg.get("action", "")
        data = msg.get("data", {})
        client_ip = request.remote

        if msg_type != "cmd":
            return

        now = time.time()
        if action == "auth":
            await handle_auth(ws, data, manager, client_ip, sessions, admin_account, now)
            return

        if action == "logout":
            token = data.get("token")
            if token and sessions:
                await sessions.delete_session(token)
            manager.authenticated_connections.discard(ws)
            return

        elif action == "logout_all":
            is_admin = require_auth(manager, ws)
            if not is_admin:
                await ws.send_str(
                    json.dumps({"type": "error", "data": "Akses ditolak. Silakan login sebagai Admin."})
                )
                return
            if sessions:
                await sessions.delete_all_sessions()
            manager.authenticated_connections.clear()
            return

        if action == "setup_admin":
            await handle_setup_admin(ws, data, manager, client_ip, admin_account, now)
            return

        # Hand over to registered handlers
        if action in self.handlers:
            try:
                await self.handlers[action](action, data, ws, request, now)
            except Exception as e:
                logger.error(
                    "ws_command_handling_failed",
                    category=LC_COMMAND,
                    command_action=action,
                    error_type=type(e).__name__,
                    error=str(e),
                    exc_info=True,
                )
                try:
                    await ws.send_str(
                        json.dumps({"type": "error", "data": "Terjadi kesalahan saat memproses permintaan."})
                    )
                except Exception:
                    pass
        else:
            # Let the fallback happen or send an error if action is unknown
            pass
