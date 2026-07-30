"""
Module: lunawave_framework.core.routing.connection_manager

Purpose:
    Manages active WebSocket connections and broadcasts events to connected clients.

Responsibilities:
    - Track connected_at per WS and record active-session duration on disconnect.
    - Provide a registry for on_disconnect callbacks.
"""

import asyncio
import json
import secrets
import time
from typing import Callable, List, Dict, Set

import structlog

from lunawave_framework.core.logging.log_categories import LC_SESSION
from lunawave_framework.core.logging.log_context import bind_session, unbind_session
from lunawave_framework.core.kernel.observability import ACTIVE_USER_SESSION_SECONDS, ACTIVE_WEBSOCKETS

logger = structlog.get_logger(component="ws.connection")


class ConnectionManager:
    def __init__(self):
        self.active_connections = []
        self.authenticated_connections: Set = set()
        self.session_tokens: Dict = {}
        self.login_attempts: Dict = {}
        self.command_history: Dict = {}
        self.chat_history: dict = {}
        self.setup_attempts: Dict = {}
        self.rl_lock = asyncio.Lock()
        self.connected_at: dict = {}
        self.client_ips: dict = {}
        self.client_uids: dict = {}
        self.on_disconnect_callbacks: List[Callable] = []

    def register_on_disconnect(self, callback: Callable):
        self.on_disconnect_callbacks.append(callback)

    async def connect(self, ws, request=None):
        self.active_connections.append(ws)
        self.connected_at[ws] = time.monotonic()
        req = request or getattr(ws, "_req", None)
        user_agent = req.headers.get("User-Agent", "") if req else ""
        referer = req.headers.get("Referer", "") if req else ""
        if not referer and req:
            page = req.query.get("page", "")
            if page:
                referer = page
        self.client_ips[ws] = {
            "ip": getattr(req, "remote", "Unknown") if req else "Unknown",
            "user_agent": user_agent,
            "referer": referer,
        }
        ACTIVE_WEBSOCKETS.inc()
        session_id = secrets.token_hex(4)
        bind_session(session_id)
        logger.info(
            "ws_connected",
            category=LC_SESSION,
            client_count=len(self.active_connections),
        )

    def disconnect(self, ws):
        for callback in self.on_disconnect_callbacks:
            try:
                callback(ws)
            except Exception as e:
                logger.error(
                    "on_disconnect_callback_failed", 
                    category=LC_SESSION, 
                    error_type=type(e).__name__, 
                    error=str(e)
                )

        if ws in self.active_connections:
            self.active_connections.remove(ws)
            ACTIVE_WEBSOCKETS.dec()
        if ws in self.authenticated_connections:
            self.authenticated_connections.remove(ws)
        self.client_ips.pop(ws, None)
        self.client_uids.pop(ws, None)

        duration = None
        connected_at = self.connected_at.pop(ws, None)
        if connected_at is not None:
            try:
                duration = time.monotonic() - connected_at
                ACTIVE_USER_SESSION_SECONDS.observe(duration)
            except Exception:
                duration = None

        logger.info(
            "ws_disconnected",
            category=LC_SESSION,
            client_count=len(self.active_connections),
            duration_s=duration,
        )
        unbind_session()

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        data = json.dumps(message, ensure_ascii=False)
        snapshot = list(self.active_connections)
        results = await asyncio.gather(
            *[ws.send_str(data) for ws in snapshot],
            return_exceptions=True,
        )
        dead = [
            ws
            for ws, result in zip(snapshot, results, strict=False)
            if isinstance(result, Exception)
        ]
        for ws in dead:
            self.disconnect(ws)

    def bind_client_uid(self, ws, client_uid: str) -> None:
        existing_uid = self.client_uids.get(ws)
        if existing_uid is not None and existing_uid != client_uid:
            raise PermissionError("client_uid koneksi ini sudah terikat")
        self.client_uids[ws] = client_uid
