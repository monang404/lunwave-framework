"""
Module: tests.unit.engine.radio.test_engine

Purpose:
    Unit tests for the radio mode engine lifecycle.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.event_bus
    - core.state
    - engine.radio.engine

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from unittest.mock import patch

import pytest

from core.event_bus import EventBus
from core.state import AppState, PlayerStatus, TrackInfo
from engine.radio.engine import RadioMode


class MockExtractor:
    pass


class MockDB:
    def __init__(self):
        self.conn = True

    async def get_all_artists(self):
        return ["A", "B"]

    async def get_random_songs(self, limit, exclude_ids, artist):
        return [TrackInfo(video_id=f"v_{artist}", title="T", artist=artist, duration=100)]


class MockController:
    def __init__(self):
        self.bus = EventBus()
        self.played = []

    async def play_track(self, track):
        self.played.append(track)


@pytest.mark.asyncio
async def test_radio_activate_deactivate():
    state = AppState()
    db = MockDB()
    radio = RadioMode(ytdlp=MockExtractor(), state=state, artists=db, library=db)
    controller = MockController()

    await radio.on_activated(controller)
    assert "A" in radio.artist_selector._seed_artists

    await radio.on_deactivated()
    await asyncio.sleep(0)
    assert len(radio._bg_tasks) == 0


@pytest.mark.asyncio
async def test_radio_next_with_queue():
    state = AppState()
    db = MockDB()
    radio = RadioMode(ytdlp=MockExtractor(), state=state, artists=db, library=db)
    controller = MockController()

    t1 = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    state.radio_queue.append(t1)

    await radio.next(controller)
    assert len(state.radio_queue) == 0
    assert len(controller.played) == 1
    assert controller.played[0] == t1


@pytest.mark.asyncio
async def test_radio_next_empty_queue():
    state = AppState()
    db = MockDB()
    radio = RadioMode(ytdlp=MockExtractor(), state=state, artists=db, library=db)
    controller = MockController()

    await radio.next(controller)
    await asyncio.sleep(0)
    assert state.status == PlayerStatus.LOADING
    # _start will be triggered as a bg task


@pytest.mark.asyncio
@patch("engine.radio.engine.ArtistSelector.gather_batch")
async def test_radio_start_empty_standby_fetches_quick(mock_gather_batch):
    state = AppState()
    db = MockDB()
    radio = RadioMode(ytdlp=MockExtractor(), state=state, artists=db, library=db)
    controller = MockController()

    track = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    mock_gather_batch.return_value = [track]

    await radio._start(controller)

    mock_gather_batch.assert_called_once()
    assert controller.played == [track]


@pytest.mark.asyncio
@patch("engine.radio.engine.ArtistSelector.gather_batch")
async def test_fetch_and_play_initial_randomize(mock_gather_batch):
    state = AppState()
    db = MockDB()
    radio = RadioMode(ytdlp=MockExtractor(), state=state, artists=db, library=db)
    controller = MockController()

    track = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    mock_gather_batch.return_value = [track]

    await radio._fetch_and_play_initial(controller, seed_artist="Coldplay")

    mock_gather_batch.assert_called_once()
    assert controller.played == [track]
