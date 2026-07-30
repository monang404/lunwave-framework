"""
Module: tests.unit.plugins.test_lyrics_sync

Purpose:
    Unit tests for lyrics synchronization with playback.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.event_bus
    - core.events
    - core.state
    - plugins.lyrics_sync

Subscribes to:
    - LyricsUpdatedEvent

Publishes:
    - TrackProgressEvent

Thread Safety:
    Main thread (async event loop).
"""

import pytest

from core.event_bus import EventBus
from core.events import LyricsUpdatedEvent, TrackProgressEvent
from core.state import AppState
from plugins.lyrics_sync import LyricsSync


@pytest.mark.asyncio
async def test_lyrics_sync():
    state = AppState()
    state.lyrics_lines = ["L1", "L2", "L3"]
    state.lyrics_timestamps = [0.0, 10.0, 20.0]

    bus = EventBus()
    sync = LyricsSync(state, bus)

    events = []
    bus.subscribe(LyricsUpdatedEvent, lambda e: events.append(e))

    # Progress at 5.0s -> index should be 0
    await bus.publish(TrackProgressEvent(position=5.0))
    assert state.lyrics_index == 0

    # Progress at 15.0s -> index should be 1
    await bus.publish(TrackProgressEvent(position=15.0))
    assert state.lyrics_index == 1

    # Since it changed, a LyricsUpdatedEvent should have been emitted
    assert len(events) >= 1

    sync.cleanup()
