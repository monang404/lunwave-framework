"""
Module: engine.sleep_timer

Purpose:
    Handles setting, tracking, and executing a sleep timer to stop playback
    after a specified duration.

Responsibilities:
    - Set an asyncio task to wait for the specified duration.
    - Cancel any existing timer when a new one is set.
    - Trigger CMD_STOP via CommandBus when the timer expires.

Depends on:
    - core.command_bus
    - core.events

Subscribes to:
    None

Publishes:
    - LogMessageEvent

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import structlog

from core.command_bus import CMD_STOP
from core.events import LogMessageEvent

logger = structlog.get_logger(component="playback.sleep_timer")


class SleepTimer:
    def __init__(self, bus, command_bus=None):
        self.bus = bus
        self._command_bus = command_bus
        self._timer_task = None

    async def set_timer(self, minutes):
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            minutes = 0
        minutes = max(0, min(1440, minutes))

        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None

        if minutes <= 0:
            await self.bus.publish(LogMessageEvent(message="Sleep timer dimatikan."))
            return

        self._timer_task = asyncio.create_task(self._wait_and_stop(minutes))
        await self.bus.publish(LogMessageEvent(message=f"Sleep timer diatur: {minutes} menit."))

    async def _wait_and_stop(self, minutes: int):
        try:
            await asyncio.sleep(minutes * 60)
            await self.bus.publish(
                LogMessageEvent(message="Sleep timer habis. Menghentikan pemutaran.")
            )
            await self._command_bus.execute(CMD_STOP)
        except asyncio.CancelledError:
            pass
