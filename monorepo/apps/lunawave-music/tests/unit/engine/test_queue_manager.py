"""tests/unit/engine/test_queue_manager.py — mirrors engine/queue_manager.py

engine/ is still a monolithic layer in the actual repo (unlike the
aspirational engine/playback/* split in the target docs), so instead of
wiring a full PlaybackController we use a minimal stand-in that only
exposes what QueueMode.next() actually touches: `.state`, `.bus`, and an
async `.play_track()`. This keeps the test scoped to queue_manager.py only.

Purpose:
    Auto-generated purpose.

Subscribes to:
    - QueueUpdatedEvent

Publishes:
    None
"""

from collections import deque

from core.event_bus import EventBus
from core.events import QueueUpdatedEvent
from core.state import AppState, PlayerStatus, TrackInfo
from engine.queue_manager import QueueMode


class _FakeController:
    """Minimal stand-in for PlaybackController — only what QueueMode.next()
    depends on: state, bus, and play_track()."""

    def __init__(self, state: AppState, bus: EventBus):
        self.state = state
        self.bus = bus
        self.played: list[TrackInfo] = []

    async def play_track(self, track: TrackInfo) -> None:
        self.played.append(track)


def make_track(video_id="v1"):
    return TrackInfo(video_id=video_id, title="T", artist="A", duration=100)


async def test_next_pops_first_track_and_delegates_to_play_track():
    state = AppState(queue=deque([make_track("v1"), make_track("v2")]))
    controller = _FakeController(state, EventBus())
    mode = QueueMode()

    await mode.next(controller)

    assert len(controller.played) == 1
    assert controller.played[0].video_id == "v1"
    # remaining queue should have the second track still in it
    assert list(state.queue) == [make_track("v2")]


async def test_next_on_empty_queue_sets_idle_and_clears_current_track():
    state = AppState(status=PlayerStatus.PLAYING, current_track=make_track("was-playing"))
    controller = _FakeController(state, EventBus())
    mode = QueueMode()

    await mode.next(controller)

    assert state.status is PlayerStatus.IDLE
    assert state.current_track is None
    assert controller.played == []


async def test_next_on_empty_queue_publishes_queue_updated_event():
    state = AppState()
    bus = EventBus()
    received = []
    bus.subscribe(QueueUpdatedEvent, lambda e: received.append(e))
    controller = _FakeController(state, bus)
    mode = QueueMode()

    await mode.next(controller)

    assert len(received) == 1
    assert isinstance(received[0], QueueUpdatedEvent)


async def test_next_with_tracks_in_queue_does_not_publish_queue_updated_event():
    """QueueMode.next() only publishes QueueUpdatedEvent on the
    empty-queue/IDLE path; popping a track delegates state changes to
    play_track() instead."""
    state = AppState(queue=deque([make_track("v1")]))
    bus = EventBus()
    received = []
    bus.subscribe(QueueUpdatedEvent, lambda e: received.append(e))
    controller = _FakeController(state, bus)
    mode = QueueMode()

    await mode.next(controller)

    assert received == []


async def test_next_pops_from_the_left_fifo_order():
    state = AppState(queue=deque([make_track("first"), make_track("second"), make_track("third")]))
    controller = _FakeController(state, EventBus())
    mode = QueueMode()

    await mode.next(controller)

    assert controller.played[0].video_id == "first"
    assert [t.video_id for t in state.queue] == ["second", "third"]


async def test_next_loop_track():
    state = AppState(current_track=make_track("v1"), loop_mode="track")
    controller = _FakeController(state, EventBus())
    mode = QueueMode()

    await mode.next(controller)

    assert len(controller.played) == 1
    assert controller.played[0].video_id == "v1"


async def test_next_loop_queue():
    state = AppState(queue=deque([make_track("v1"), make_track("v2")]), loop_mode="queue")
    controller = _FakeController(state, EventBus())
    mode = QueueMode()

    await mode.next(controller)

    assert len(controller.played) == 1
    assert controller.played[0].video_id == "v1"
    assert [t.video_id for t in state.queue] == ["v2", "v1"]
