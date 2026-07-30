"""
Module: tests.unit.engine.conftest

Purpose:
    Pytest fixtures and configuration for the engine test suite.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - persistence.stream_cache
    - core.event_bus
    - core.state
    - engine.playback.controller
    - tests.fakes.fake_audio_player
    - tests.fakes.fake_media_extractor
    - tests.fakes.fake_track_repository

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import pytest

from core.event_bus import EventBus
from core.state import AppState, TrackInfo
from tests.fakes.fake_audio_player import FakeAudioPlayer
from tests.fakes.fake_media_extractor import FakeMediaExtractor
from tests.fakes.fake_track_repository import FakeTrackRepository


class FakeSponsorBlock:
    async def fetch_segments(self, video_id: str) -> None:
        pass


class FakeLyrics:
    async def fetch(self, track: TrackInfo) -> None:
        pass


class FakeQueueMode:
    def __init__(self):
        self.next_calls: list = []

    async def next(self, controller) -> None:
        self.next_calls.append(controller)


class FakeRadioMode:
    def __init__(self):
        self.next_calls = []
        self.activated = False
        self.deactivated = False
        self.deactivated_calls = 0
        self.fetch_initial_calls: list = []

    async def next(self, controller) -> None:
        self.next_calls.append(controller)

    async def on_activated(self, controller) -> None:
        self.activated = True

    async def on_deactivated(self) -> None:
        self.deactivated = True
        self.deactivated_calls += 1

    def check_prefetch(self, controller, position, duration) -> None:
        pass

    async def _fetch_and_play_initial(self, controller, seed_artist=None) -> None:
        self.fetch_initial_calls.append(seed_artist)


def make_track(video_id="v1", duration=200):
    return TrackInfo(video_id=video_id, title="Test Song", artist="Artist", duration=duration)


@pytest.fixture
def player():
    p = FakeAudioPlayer()

    async def get_position():
        return 0.0

    async def get_duration():
        return 200.0

    async def toggle_pause():
        pass

    p.get_position = get_position
    p.get_duration = get_duration
    p.toggle_pause = toggle_pause
    return p


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def state():
    return AppState(volume=80)


@pytest.fixture
def repo():
    r = FakeTrackRepository()
    r.seed(make_track("v1"))
    return r


@pytest.fixture
def extractor():
    e = FakeMediaExtractor()
    e.stream_urls["v1"] = "https://stream/v1.m4a"
    e.stream_urls["v2"] = "https://stream/v2.m4a"
    return e


@pytest.fixture
def queue_mode():
    return FakeQueueMode()


@pytest.fixture
def radio_mode():
    return FakeRadioMode()


@pytest.fixture
def controller(bus, state, player, repo, extractor, queue_mode, radio_mode):
    from persistence.stream_cache import CacheResolver

    resolver = CacheResolver(db=repo, ytdlp=extractor)
    from engine.playback.controller import PlaybackController

    return PlaybackController(
        bus=bus,
        state=state,
        mpv=player,
        resolver=resolver,
        sponsorblock=FakeSponsorBlock(),
        lyrics_fetcher=FakeLyrics(),
        queue_mode=queue_mode,
        radio_mode=radio_mode,
    )
