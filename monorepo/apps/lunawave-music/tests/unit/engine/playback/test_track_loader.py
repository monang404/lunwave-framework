"""tests/unit/engine/test_track_loader.py — mirrors engine/playback/track_loader.py

Semua dependensi (resolver, sponsorblock, lyrics) di-fake agar test murni
unit tanpa I/O. Periksa bahwa TrackLoader memanggil dependensi dengan benar
dan mengembalikan URI hasil resolve.

Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import asyncio

import pytest

from core.state import TrackInfo
from engine.playback.track_loader import TrackLoader
from tests.fakes.fake_media_extractor import FakeMediaExtractor
from tests.fakes.fake_track_repository import FakeTrackRepository

# ---------------------------------------------------------------------------
# Fakes for SponsorBlockProvider and LyricsProvider
# ---------------------------------------------------------------------------


class FakeSponsorBlock:
    def __init__(self):
        self.call_log: list[tuple] = []

    async def fetch_segments(self, video_id: str) -> None:
        self.call_log.append(("fetch_segments", video_id))


class FakeLyrics:
    def __init__(self):
        self.call_log: list[tuple] = []

    async def fetch(self, track: TrackInfo) -> None:
        self.call_log.append(("fetch", track.video_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_track(video_id="v1"):
    return TrackInfo(video_id=video_id, title="T", artist="A", duration=180)


@pytest.fixture
def repo():
    return FakeTrackRepository()


@pytest.fixture
def extractor():
    e = FakeMediaExtractor()
    e.stream_urls["v1"] = "https://stream/v1.m4a"
    return e


@pytest.fixture
def sponsorblock():
    return FakeSponsorBlock()


@pytest.fixture
def lyrics():
    return FakeLyrics()


@pytest.fixture
def loader(repo, extractor, sponsorblock, lyrics):
    from persistence.stream_cache import CacheResolver

    resolver = CacheResolver(db=repo, ytdlp=extractor)
    return TrackLoader(resolver=resolver, sponsorblock=sponsorblock, lyrics_fetcher=lyrics)


# ---------------------------------------------------------------------------
# load_track
# ---------------------------------------------------------------------------


class TestLoadTrack:
    async def test_returns_resolved_uri(self, loader, extractor, repo):
        extractor.stream_urls["v1"] = "https://cdn.example.com/v1.m4a"
        track = make_track("v1")
        result = await loader.load_track(track)
        assert result.uri == "https://cdn.example.com/v1.m4a"

    async def test_returns_local_path_when_file_exists(self, loader, repo, tmp_path):
        local = tmp_path / "v1.mp3"
        local.write_bytes(b"fake audio")
        repo.seed(
            TrackInfo(video_id="v1", title="T", artist="A", duration=180, local_path=str(local))
        )
        track = make_track("v1")
        result = await loader.load_track(track)
        assert result.uri == str(local)

    async def test_increments_play_count_as_background_task(self, loader, repo, extractor):
        extractor.stream_urls["v1"] = "https://stream/v1"
        repo.seed(TrackInfo(video_id="v1", title="T", artist="A", duration=180))
        track = make_track("v1")
        await loader.load_track(track)
        # Give safe_create_task a tick to run
        await asyncio.sleep(0.05)
        assert ("increment_play_count", "v1") in repo.call_log

    async def test_fires_sponsorblock_fetch_as_background_task(
        self, loader, extractor, sponsorblock
    ):
        extractor.stream_urls["v1"] = "https://stream/v1"
        track = make_track("v1")
        await loader.load_track(track)
        await asyncio.sleep(0.05)
        assert ("fetch_segments", "v1") in sponsorblock.call_log

    async def test_fires_lyrics_fetch_as_background_task(self, loader, extractor, lyrics):
        extractor.stream_urls["v1"] = "https://stream/v1"
        track = make_track("v1")
        await loader.load_track(track)
        await asyncio.sleep(0.05)
        assert ("fetch", "v1") in lyrics.call_log

    async def test_does_not_block_on_background_tasks(self, loader, extractor):
        """load_track must return quickly even if background tasks are slow."""
        extractor.stream_urls["v1"] = "https://stream/v1"

        slow_called = asyncio.Event()

        async def slow_fetch(video_id):
            slow_called.set()
            await asyncio.sleep(10)  # would block if awaited

        loader.sponsorblock.fetch_segments = slow_fetch

        track = make_track("v1")
        # Should complete without waiting for slow_fetch
        result = await asyncio.wait_for(loader.load_track(track), timeout=1.0)
        assert result.uri.startswith("https://")
