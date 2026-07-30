"""
Module: lunawave_framework.core.kernel.command_bus

Purpose:
    Implement a single-writer CommandBus that enforces exactly one handler
    per command name and records Prometheus metrics for every execution.

Responsibilities:
    - Register/unregister command handlers (1-to-1, raises on duplicate).
    - Dispatch commands with OpenTelemetry span and latency/count metrics.

Depends on:
    - lunawave_framework.core.kernel.observability
    - lunawave_framework.core.logging.log_categories
    - lunawave_framework.core.logging.log_context

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async execute).

Phase 3 extraction note:
    The pre-Phase-3 core/command_bus.py had `from core.commands import *`
    here, re-exporting the app's CMD_* constants for caller convenience.
    That import is intentionally REMOVED in the framework version -- a
    generic dispatcher must not depend on any app's concrete command
    vocabulary (see ADR 0013 in the app repo). The app-side shim
    (core/command_bus.py in lunawave-music) recombines CommandBus from here
    with CMD_* from music.domain.commands, so existing call sites doing
    `from core.command_bus import CMD_PLAY_TRACK, CommandBus` keep working
    unchanged.
"""

import asyncio
import secrets
import time
from collections.abc import Callable
from typing import Any

import structlog

from lunawave_framework.core.kernel.observability import COMMAND_COUNT, COMMAND_LATENCY
from lunawave_framework.core.logging.log_categories import LC_COMMAND
from lunawave_framework.core.logging.log_context import bind_request, unbind_request

logger = structlog.get_logger(component="core.command_bus")


class CommandBus:
    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register(self, command: str, handler: Callable):
        if command in self._handlers:
            raise RuntimeError(
                f"Command '{command}' is already registered to {self._handlers[command]}"
            )
        self._handlers[command] = handler

    def unregister(self, command: str):
        if command in self._handlers:
            del self._handlers[command]

    async def execute(self, command: str, data: Any = None) -> Any:
        if command not in self._handlers:
            raise RuntimeError(f"No handler registered for command '{command}'")

        handler = self._handlers[command]
        start_time = time.perf_counter()
        status = "success"

        # L5.2: request_id baru per eksekusi command, ditumpuk di atas
        # session_id yang sudah aktif (jika ada) via contextvars -- tidak
        # saling menimpa (§5.2). Dilepas lagi di finally supaya tidak bocor
        # ke eksekusi command berikutnya dalam task WS yang sama.
        request_id = secrets.token_hex(4)
        bind_request(request_id)

        # L7.1: entry/exit alur command. DEBUG (volume tinggi, §8.2/§8.3) --
        # bukan kejadian yang tiap kali perlu dilihat operator.
        logger.debug(
            "command_received",
            category=LC_COMMAND,
            command_name=command,
        )

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(data)
            else:
                result = handler(data)
            logger.debug(
                "command_succeeded",
                category=LC_COMMAND,
                command_name=command,
            )
            return result
        except Exception as e:
            status = "error"
            logger.error(
                "command_execution_failed",
                category=LC_COMMAND,
                command_name=command,
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            raise
        finally:
            duration = time.perf_counter() - start_time
            COMMAND_LATENCY.labels(command_name=command).observe(duration)
            COMMAND_COUNT.labels(command_name=command, status=status).inc()
            unbind_request()
