"""
Module: server.handlers.ws_log_stream

Purpose:
    Provide WebSocket handler for live log tailing.

Responsibility:
    - Handle log_tail subscribe/unsubscribe commands.
    - Stream new log lines from lunawave.log to subscribed clients.
    - Batch new lines every 500ms to avoid flooding the client.

Depends on:
    - core.log_reader
    - config.BASE_DIR

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (asyncio tasks).
"""

import asyncio
import os

import structlog

from config import BASE_DIR
from core.log_reader import parse_line

logger = structlog.get_logger(component="server.ws_log_stream")

# Map of websocket to its tail task
_log_tail_tasks: dict[object, asyncio.Task] = {}


async def handle_log_stream_command(action: str, ws):
    if action == "subscribe":
        if ws in _log_tail_tasks:
            return

        task = asyncio.create_task(_tail_log_loop(ws))
        _log_tail_tasks[ws] = task
        logger.debug("log_tail_subscribed")

    elif action == "unsubscribe":
        _cleanup_task(ws)
        logger.debug("log_tail_unsubscribed")


def _cleanup_task(ws):
    if ws in _log_tail_tasks:
        task = _log_tail_tasks.pop(ws)
        if not task.done():
            task.cancel()


def cleanup_log_viewer(ws):
    """Called when connection manager detects disconnect."""
    _cleanup_task(ws)


async def _tail_log_loop(ws):
    log_path = BASE_DIR / "lunawave.log"
    batch_interval = 0.5

    try:
        if not log_path.exists():
            for _ in range(10):
                if log_path.exists():
                    break
                await asyncio.sleep(0.5)
            else:
                return

        with open(log_path, encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)

            while True:
                batch = []
                while True:
                    line = f.readline()
                    if not line:
                        break

                    if line.strip():
                        batch.append(parse_line(line))

                if batch:
                    try:
                        await ws.send_json({"type": "log_batch", "logs": batch})
                    except Exception:
                        break

                await asyncio.sleep(batch_interval)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("log_tail_error", error=str(e))
    finally:
        _cleanup_task(ws)
