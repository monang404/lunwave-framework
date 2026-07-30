"""
Module: adapters.mpv.ipc

Purpose:
    Handles JSON IPC communication and command execution with MPV.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import json

import structlog

from core.log_categories import LC_EXTERNAL

logger = structlog.get_logger(component="mpv.ipc")


class MpvIPC:
    """Send/receive JSON IPC ke MPV. Tidak tahu tentang event domain."""

    def __init__(self, connection):
        self._conn = connection
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._req_lock = asyncio.Lock()

    async def send_command(self, cmd: list) -> int:
        if not self._conn.is_connected or not self._conn.writer:
            return 0
        async with self._req_lock:
            self._request_id += 1
            req_id = self._request_id
            payload = json.dumps({"command": cmd, "request_id": req_id}) + "\n"
            try:
                self._conn.writer.write(payload.encode())
                await self._conn.writer.drain()
            except OSError as e:
                logger.warning(
                    "mpv_command_send_failed",
                    category=LC_EXTERNAL,
                    error_type=type(e).__name__,
                    error=str(e),
                )
        return req_id

    async def get_property(self, prop: str):
        if not self._conn.is_connected:
            return None
        loop = asyncio.get_running_loop()
        async with self._req_lock:
            self._request_id += 1
            req_id = self._request_id
            fut = loop.create_future()
            self._pending[req_id] = fut
        payload = json.dumps({"command": ["get_property", prop], "request_id": req_id}) + "\n"
        try:
            self._conn.writer.write(payload.encode())
            await self._conn.writer.drain()
            return await asyncio.wait_for(fut, timeout=2.0)
        except (TimeoutError, OSError):
            self._pending.pop(req_id, None)
            return None

    async def set_property(self, prop: str, value):
        return await self.send_command(["set_property", prop, value])

    def pop_pending(self, req_id: int) -> asyncio.Future | None:
        return self._pending.pop(req_id, None)

    def cancel_all_pending(self):
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
