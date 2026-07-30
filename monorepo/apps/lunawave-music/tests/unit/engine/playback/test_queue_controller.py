"""
Module: tests.unit.engine.playback.test_queue_controller

Purpose:
    Unit tests for QueueController: command CMD_QUEUE_* dan advance-to-next,
    diekstrak dari test_controller.py mengikuti pemisahan PlaybackController
    (T2.3.1) menjadi QueueController + SettingsController.

Responsibilities:
    - Verifikasi delegasi PlaybackController._on_queue_* ke QueueController.
    - Verifikasi advance_to_next memilih queue_mode/radio_mode sesuai
      playback_mode, dan mencatat completion/skip untuk artist-bandit.

Depends on:
    - core.state
    - tests.unit.engine.conftest

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from collections import deque

from core.state import PlaybackMode, PlayerStatus
from tests.unit.engine.conftest import make_track


class TestQueueSelect:
    async def test_select_plays_chosen_track_and_pops_preceding(self, controller, state, extractor):
        extractor.stream_urls["v2"] = "https://stream/v2"
        state.queue = deque([make_track("v1"), make_track("v2"), make_track("v3")])
        await controller._on_queue_select(1)
        assert state.current_track.video_id == "v2"
        assert list(state.queue) == [make_track("v3")]

    async def test_select_out_of_range_is_noop(self, controller, state):
        state.queue = deque([make_track("v1")])
        await controller._on_queue_select(5)
        assert state.current_track is None

    async def test_select_from_radio_mode_deactivates_radio(
        self, controller, state, extractor, radio_mode
    ):
        extractor.stream_urls["v2"] = "https://stream/v2"
        state.playback_mode = PlaybackMode.RADIO
        state.queue = deque([make_track("v1"), make_track("v2"), make_track("v3")])
        await controller._on_queue_select(1)
        assert state.playback_mode == PlaybackMode.QUEUE
        assert radio_mode.deactivated_calls == 1
        assert state.current_track.video_id == "v2"


class TestQueueMutations:
    async def test_add_appends_track(self, controller, state):
        state.queue = deque()
        await controller._on_queue_add(make_track("v1"))
        assert list(state.queue) == [make_track("v1")]

    async def test_remove_deletes_by_index(self, controller, state):
        state.queue = deque([make_track("v1"), make_track("v2")])
        await controller._on_queue_remove(0)
        assert list(state.queue) == [make_track("v2")]

    async def test_replace_clears_and_sets_new_queue(self, controller, state):
        state.queue = deque([make_track("old")])
        await controller._on_queue_replace([make_track("v1"), make_track("v2")])
        assert [t.video_id for t in state.queue] == ["v1", "v2"]

    async def test_reorder_moves_item(self, controller, state):
        state.queue = deque([make_track("v1"), make_track("v2"), make_track("v3")])
        await controller._on_queue_reorder({"from_index": 0, "to_index": 2})
        assert [t.video_id for t in state.queue] == ["v2", "v3", "v1"]


class TestAdvanceToNext:
    async def test_queue_mode_delegates_to_queue_mode_next(self, controller, state, queue_mode):
        state.playback_mode = PlaybackMode.QUEUE
        await controller._advance_to_next()
        assert len(queue_mode.next_calls) == 1

    async def test_radio_mode_delegates_to_radio_mode_next(self, controller, state, radio_mode):
        state.playback_mode = PlaybackMode.RADIO
        await controller._advance_to_next()
        assert len(radio_mode.next_calls) == 1

    async def test_no_current_track_still_advances(self, controller, state, queue_mode):
        state.playback_mode = PlaybackMode.QUEUE
        state.current_track = None
        await controller._advance_to_next()
        assert len(queue_mode.next_calls) == 1

    async def test_status_unaffected_by_advance_itself(self, controller, state, queue_mode):
        state.playback_mode = PlaybackMode.QUEUE
        state.status = PlayerStatus.PLAYING
        await controller._advance_to_next()
        # advance_to_next hanya delegasi ke queue_mode.next; perubahan status
        # jadi tanggung jawab queue_mode/radio_mode itu sendiri.
        assert state.status == PlayerStatus.PLAYING
