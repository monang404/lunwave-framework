"""
Module: plugins.lyrics_sync

Purpose:
    Synchronizes lyrics display with current track playback progress.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.events

Subscribes to:
    - TrackProgressEvent

Publishes:
    - LyricsUpdatedEvent

Thread Safety:
    Main thread (async event loop).
"""

import bisect
import time

from core.events import LyricsUpdatedEvent, TrackProgressEvent


class LyricsSync:
    def __init__(self, state, event_bus):
        self.state = state
        self._bus = event_bus
        self._last_lyrics_broadcast_ts = 0.0
        self._bus.subscribe(TrackProgressEvent, self.on_progress)

    def cleanup(self):
        self._bus.unsubscribe(TrackProgressEvent, self.on_progress)

    async def on_progress(self, event: TrackProgressEvent):
        position = event.position
        if not self.state.lyrics_lines or not isinstance(position, (int, float)):
            return

        timestamps = getattr(self.state, "lyrics_timestamps", [])
        if not timestamps:
            return

        adjusted_position = position + getattr(self.state, "lyrics_offset", 0.0)
        active_idx = bisect.bisect_right(timestamps, adjusted_position) - 1
        active_idx = max(0, active_idx)

        if getattr(self.state, "lyrics_index", 0) != active_idx:
            self.state.lyrics_index = active_idx
            _now = time.monotonic()
            if _now - self._last_lyrics_broadcast_ts >= 0.5:
                self._last_lyrics_broadcast_ts = _now
                await self._bus.publish(LyricsUpdatedEvent())
