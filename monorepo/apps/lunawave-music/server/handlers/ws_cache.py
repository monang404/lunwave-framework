"""
Module: server.handlers.ws_cache

Purpose:
    WebSocket handler for managing the downloaded MP3 file cache
    (`DOWNLOAD_DIR`, a.k.a. `cache/mp3/`): reporting its size and clearing it.

    Note (T2.6): this module is unrelated to the stream-URL cache moved to
    `persistence/stream_cache.py`. It was kept under its original name
    (`ws_cache.py`, not renamed to `ws_stream_cache.py`) because it never
    touched `cache/resolver.py` in the first place — see
    `docs/backend/caching.md` for the two-cache distinction and rationale.

Responsibilities:
    - Get cache size
    - Clear cache

Depends on:
    - config

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread.
"""

import json
import os

import structlog

from config import DOWNLOAD_DIR
from core.log_categories import LC_CACHE

logger = structlog.get_logger(component="ws.cache")


import asyncio


def _get_cache_size_sync() -> int:
    size = 0
    if DOWNLOAD_DIR.exists():
        for root, dirs, files in os.walk(str(DOWNLOAD_DIR)):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size += os.path.getsize(fp)
                except OSError:
                    pass
    return size


def _clear_cache_sync() -> None:
    if DOWNLOAD_DIR.exists():
        for root, dirs, files in os.walk(str(DOWNLOAD_DIR)):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for f in files:
                fp = os.path.join(root, f)
                try:
                    os.remove(fp)
                except OSError:
                    pass


async def handle_cache_command(action: str, data: dict, ws, db, manager, state):
    if action == "get_cache_size":
        loop = asyncio.get_running_loop()
        size = await loop.run_in_executor(None, _get_cache_size_sync)
        await ws.send_str(json.dumps({"type": "cache_size", "data": {"size_bytes": size}}))
    elif action == "clear_cache":
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _clear_cache_sync)
        if db:
            try:
                await db.execute("UPDATE tracks SET local_path = NULL WHERE local_path IS NOT NULL")
                await db.commit()
            except Exception as e:
                logger.error(
                    "cache_clear_db_update_failed",
                    category=LC_CACHE,
                    error_type=type(e).__name__,
                    error=str(e),
                )
        await manager.broadcast({"type": "log", "data": "Cache berhasil dibersihkan"})
        await ws.send_str(json.dumps({"type": "cache_cleared", "data": {}}))
