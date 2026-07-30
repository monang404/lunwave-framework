"""
Module: tests.unit.engine.radio.test_artist_selector

Purpose:
    Unit tests for radio artist selection and rotation.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state
    - engine.radio.artist_selector

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import pytest

from core.state import AppState, TrackInfo
from engine.radio.artist_selector import ArtistSelector


class MockDB:
    def __init__(self):
        self.conn = True

    async def get_all_artists(self):
        return ["Artist A", "Artist B"]

    async def get_reward_stats(self):
        return {}  # No stats yet; bandit will use defaults (1, 1)

    async def get_random_songs(self, limit, exclude_ids, artists=None, max_per_artist=3):
        artist = artists[0] if artists else "Artist A"
        return [
            TrackInfo(video_id="1", title="T1", artist=artist, duration=100),
            TrackInfo(video_id="2", title="T2", artist=artist, duration=100),
        ]


@pytest.mark.asyncio
async def test_ensure_artists_loaded():
    state = AppState()
    db = MockDB()
    selector = ArtistSelector(db, db, state)

    await selector.ensure_artists_loaded()
    assert "Artist A" in selector._seed_artists


@pytest.mark.asyncio
async def test_build_exclusion_set():
    state = AppState()
    state.radio_queue.append(TrackInfo(video_id="q1", title="Q", artist="A", duration=100))
    state.current_track = TrackInfo(video_id="c1", title="C", artist="B", duration=100)
    state.history.append(TrackInfo(video_id="h1", title="H", artist="C", duration=100))

    selector = ArtistSelector(None, None, state)
    exclusions = selector.build_exclusion_set()

    assert exclusions == {"q1", "c1", "h1"}


@pytest.mark.asyncio
async def test_gather_batch():
    state = AppState()
    db = MockDB()
    selector = ArtistSelector(db, db, state)
    await selector.ensure_artists_loaded()

    batch = await selector.gather_batch(prioritized_artist="Artist A")
    assert len(batch) == 2
    assert batch[0].artist == "Artist A"
