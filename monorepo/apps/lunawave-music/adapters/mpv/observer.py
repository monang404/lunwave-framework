"""
Module: adapters.mpv.observer

Purpose:
    Observes and dispatches asynchronous events emitted by the MPV player.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.event_bus
    - core.events
    - core.task_utils

Subscribes to:
    None

Publishes:
    - TrackDurationEvent
    - TrackEndedEvent
    - TrackPauseChangedEvent
    - TrackProgressEvent

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import json

import structlog

from core.event_bus import EventBus
from core.events import (
    MpvReconnectedEvent,
    TrackDurationEvent,
    TrackEndedEvent,
    TrackPauseChangedEvent,
    TrackProgressEvent,
)
from core.log_categories import LC_EXTERNAL
from core.task_utils import safe_create_task

logger = structlog.get_logger(component="mpv.observer")

# Jumlah percobaan reconnect sebelum menyerah dan mengumumkan track sebagai
# error. Backoff dibuat pendek (detik, bukan puluhan detik) karena ini
# satu-satunya jalur reconnect -- lihat catatan di bawah.
RECONNECT_MAX_ATTEMPTS = 3
RECONNECT_BACKOFF_SECONDS = (1, 2, 4)


class MpvObserver:
    """Baca event dari MPV socket, publish ke EventBus sebagai DomainEvent."""

    def __init__(self, connection, ipc, event_bus: EventBus, room_id="default"):
        self._conn = connection
        self._ipc = ipc
        self._bus = event_bus
        self._room_id = room_id
        self._task = None
        self._last_progress_ts: float = 0.0

    async def start(self):
        if not self._task or self._task.done():
            self._task = safe_create_task(self._observe_loop(), name="mpv-observer")

    async def stop(self):
        # PATCH-2026-07-16-001: cancel() saja tidak menunggu task selesai;
        # await eksplisit di sini agar caller (adapters/mpv/__init__.py) tahu
        # observer benar-benar berhenti sebelum lanjut, mencegah task
        # menggantung di background saat shutdown.
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _subscribe_properties(self):
        await asyncio.gather(
            self._ipc.send_command(["observe_property", 1, "time-pos"]),
            self._ipc.send_command(["observe_property", 2, "pause"]),
            self._ipc.send_command(["observe_property", 3, "duration"]),
        )

    async def _observe_loop(self):
        """Event loop listener for mpv events (end-file, time-pos, etc)."""
        try:
            await self._subscribe_properties()

            while self._conn.is_connected:
                try:
                    if not self._conn.reader:
                        break
                    line = await self._conn.reader.readline()
                    if not line:
                        raise ConnectionError("mpv socket closed (EOF)")
                    msg = json.loads(line.decode())
                    await self._handle_event(msg)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                except (ConnectionError, OSError, asyncio.IncompleteReadError):
                    if getattr(self._conn, "shutting_down", False):
                        break
                    # NOTE: This used to be handled by main.py's
                    # mpv_reconnect_checker polling every 5s, to avoid a race
                    # where this loop reconnected the raw socket almost
                    # instantly but never restored playback. In practice that
                    # made *every* drop (even a one-off blip) wait up to 5s
                    # before recovery even started, and by the time the
                    # checker restored playback state.position was several
                    # seconds stale -- audible as "musik mati" (silence) plus
                    # the track jumping backwards. Reconnecting immediately,
                    # right here, closes that staleness window; the checker
                    # in main.py has been removed so there is now exactly one
                    # reconnect path.
                    reconnected = await self._reconnect_with_retries()
                    if not reconnected:
                        await self._bus.publish(TrackEndedEvent(reason="error"))
                        break
                    # Fresh connection (possibly a brand-new mpv process) has
                    # no observers registered yet -- re-subscribe or we'd go
                    # deaf to time-pos/pause/duration/end-file from here on.
                    await self._subscribe_properties()
                    # Let PlaybackController know it needs to reload the
                    # current track/seek/volume/gain onto the new mpv
                    # process -- this loop only owns the socket, not
                    # playback state.
                    await self._bus.publish(MpvReconnectedEvent())
        finally:
            self._conn.is_connected = False
            self._ipc.cancel_all_pending()
            logger.warning(
                "mpv_observer_loop_ended",
                category=LC_EXTERNAL,
                reason="connection_lost",
            )

    async def _reconnect_with_retries(self) -> bool:
        for attempt in range(1, RECONNECT_MAX_ATTEMPTS + 1):
            logger.warning(
                "mpv_reconnect_attempt_started",
                category=LC_EXTERNAL,
                attempt=attempt,
                max_attempts=RECONNECT_MAX_ATTEMPTS,
            )
            try:
                if await self._conn.reconnect():
                    logger.info(
                        "mpv_reconnected",
                        category=LC_EXTERNAL,
                        attempt=attempt,
                    )
                    return True
            except Exception as e:
                logger.error(
                    "mpv_reconnect_attempt_failed",
                    category=LC_EXTERNAL,
                    attempt=attempt,
                    error_type=type(e).__name__,
                    error=str(e),
                )
            if attempt < RECONNECT_MAX_ATTEMPTS:
                await asyncio.sleep(RECONNECT_BACKOFF_SECONDS[attempt - 1])
        logger.critical("mpv_reconnect_exhausted", category=LC_EXTERNAL)
        return False

    async def _handle_event(self, msg: dict):
        if "request_id" in msg:
            fut = self._ipc.pop_pending(msg["request_id"])
            if fut and not fut.done():
                fut.set_result(msg.get("data"))
            return

        event = msg.get("event")
        if event == "property-change":
            name = msg.get("name")
            data = msg.get("data")
            if name == "time-pos" and isinstance(data, (int, float)):
                import time as _time

                _now = _time.monotonic()
                # Throttle: publish maksimal 1× per detik untuk hemat CPU/baterai.
                if _now - self._last_progress_ts >= 1.0:
                    self._last_progress_ts = _now
                    await self._bus.publish(TrackProgressEvent(position=float(data)))
            elif name == "pause":
                await self._bus.publish(TrackPauseChangedEvent(is_paused=bool(data)))
            elif name == "duration" and isinstance(data, (int, float)):
                await self._bus.publish(TrackDurationEvent(duration=float(data)))
        elif event == "end-file":
            reason = msg.get("reason", "")
            if reason in ("eof", "stop", "error"):
                await self._bus.publish(TrackEndedEvent(reason=reason))
