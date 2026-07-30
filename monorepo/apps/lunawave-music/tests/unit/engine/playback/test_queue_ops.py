"""
Module: tests.unit.engine.playback.test_queue_ops

Purpose:
    Unit tests for queue manipulation operations.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.event_bus
    - core.events
    - core.state
    - engine.playback.queue_ops

Subscribes to:
    - QueueUpdatedEvent

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import pytest

from core.event_bus import EventBus
from core.events import QueueUpdatedEvent
from core.state import AppState, TrackInfo
from engine.playback.queue_ops import QueueOps


@pytest.fixture
def setup_queue_ops():
    state = AppState()
    bus = EventBus()
    lock = asyncio.Lock()
    ops = QueueOps(state, bus, lock)
    return ops, state, bus


@pytest.mark.asyncio
async def test_add_track(setup_queue_ops):
    ops, state, bus = setup_queue_ops
    track = TrackInfo(video_id="1", title="T", artist="A", duration=100)

    events = []
    bus.subscribe(QueueUpdatedEvent, lambda e: events.append(e))

    await ops.add_track(track)
    assert len(state.queue) == 1
    assert len(events) == 1


@pytest.mark.asyncio
async def test_queue_select(setup_queue_ops):
    ops, state, bus = setup_queue_ops
    t1 = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    t2 = TrackInfo(video_id="2", title="T2", artist="A", duration=100)
    state.queue.extend([t1, t2])

    selected = await ops.queue_select(1)
    assert selected == t2
    assert len(state.queue) == 0  # Popped both


@pytest.mark.asyncio
async def test_remove_track(setup_queue_ops):
    ops, state, bus = setup_queue_ops
    t1 = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    t2 = TrackInfo(video_id="2", title="T2", artist="A", duration=100)
    state.queue.extend([t1, t2])

    await ops.remove_track(0)
    assert len(state.queue) == 1
    assert state.queue[0] == t2


@pytest.mark.asyncio
async def test_replace_queue(setup_queue_ops):
    ops, state, bus = setup_queue_ops
    t1 = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    t2 = TrackInfo(video_id="2", title="T2", artist="A", duration=100)

    await ops.replace_queue([t1, t2])
    assert len(state.queue) == 2
    assert state.queue[0] == t1


@pytest.mark.asyncio
async def test_reorder(setup_queue_ops):
    ops, state, bus = setup_queue_ops
    t1 = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    t2 = TrackInfo(video_id="2", title="T2", artist="A", duration=100)
    state.queue.extend([t1, t2])

    await ops.reorder(0, 1)
    assert state.queue[0] == t2
    assert state.queue[1] == t1
