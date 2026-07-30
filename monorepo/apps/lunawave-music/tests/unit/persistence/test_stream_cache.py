"""tests/unit/persistence/test_stream_cache.py — mirrors persistence/stream_cache.py

Priority: Sedang (needs fakes, no real I/O). Uses FakeTrackRepository
(implements TrackRepositoryPort) and FakeMediaExtractor (implements
MediaExtractorPort) so the resolver's priority logic (local file > cached
stream URL > fresh yt-dlp fetch) is tested in full isolation.

Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import time

import pytest

import config
from core.state import TrackInfo
from persistence.stream_cache import CacheResolver
from tests.fakes.fake_media_extractor import FakeMediaExtractor
from tests.fakes.fake_track_repository import FakeTrackRepository


def make_track(video_id="v1"):
    return TrackInfo(video_id=video_id, title="T", artist="A", duration=100)


@pytest.fixture
def repo():
    return FakeTrackRepository()


@pytest.fixture
def extractor():
    return FakeMediaExtractor()


@pytest.fixture
def resolver(repo, extractor):
    return CacheResolver(db=repo, ytdlp=extractor)


async def test_resolve_returns_local_path_when_file_exists_on_disk(resolver, repo, tmp_path):
    local_file = tmp_path / "song.mp3"
    local_file.write_bytes(b"fake audio")
    repo.seed(
        TrackInfo(video_id="v1", title="T", artist="A", duration=100, local_path=str(local_file))
    )

    track = make_track("v1")
    result = await resolver.resolve(track)

    assert result == str(local_file)
    assert track.local_path == str(local_file)


async def test_resolve_falls_through_when_local_path_recorded_but_file_missing(
    resolver, repo, extractor
):
    repo.seed(
        TrackInfo(
            video_id="v1", title="T", artist="A", duration=100, local_path="/no/such/file.mp3"
        )
    )
    extractor.stream_urls["v1"] = "https://fresh-url"

    track = make_track("v1")
    result = await resolver.resolve(track)

    # Falls all the way through to rule 3 since no stream_url was cached either.
    assert result == "https://fresh-url"
    assert track.local_path is None


async def test_resolve_returns_cached_stream_url_when_fresh(resolver, repo):
    now = int(time.time())
    repo.seed(
        TrackInfo(
            video_id="v1",
            title="T",
            artist="A",
            duration=100,
            stream_url="https://cached-url",
            stream_url_ts=now,
        )
    )

    track = make_track("v1")
    result = await resolver.resolve(track)

    assert result == "https://cached-url"
    assert track.stream_url == "https://cached-url"


async def test_resolve_treats_stale_stream_url_as_a_cache_miss(resolver, repo, extractor):
    stale_ts = int(time.time()) - config.STREAM_URL_TTL_SEC - 1
    repo.seed(
        TrackInfo(
            video_id="v1",
            title="T",
            artist="A",
            duration=100,
            stream_url="https://stale-url",
            stream_url_ts=stale_ts,
        )
    )
    extractor.stream_urls["v1"] = "https://brand-new-url"

    track = make_track("v1")
    result = await resolver.resolve(track)

    assert result == "https://brand-new-url"


async def test_resolve_boundary_exactly_at_ttl_is_treated_as_stale(resolver, repo, extractor):
    """`time.time() - ts < TTL` is a strict inequality, so a URL fetched
    exactly TTL seconds ago must already count as stale."""
    boundary_ts = int(time.time()) - config.STREAM_URL_TTL_SEC
    repo.seed(
        TrackInfo(
            video_id="v1",
            title="T",
            artist="A",
            duration=100,
            stream_url="https://boundary-url",
            stream_url_ts=boundary_ts,
        )
    )
    extractor.stream_urls["v1"] = "https://refetched-url"

    track = make_track("v1")
    result = await resolver.resolve(track)

    assert result == "https://refetched-url"


async def test_resolve_with_no_db_row_at_all_falls_back_to_ytdlp(resolver, extractor):
    extractor.stream_urls["v1"] = "https://first-time-url"

    track = make_track("v1")
    result = await resolver.resolve(track)

    assert result == "https://first-time-url"
    assert track.stream_url == "https://first-time-url"


async def test_resolve_local_file_takes_priority_over_fresh_stream_url(resolver, repo, tmp_path):
    local_file = tmp_path / "song.mp3"
    local_file.write_bytes(b"fake audio")
    now = int(time.time())
    repo.seed(
        TrackInfo(
            video_id="v1",
            title="T",
            artist="A",
            duration=100,
            local_path=str(local_file),
            stream_url="https://should-not-be-used",
            stream_url_ts=now,
        )
    )

    track = make_track("v1")
    result = await resolver.resolve(track)

    assert result == str(local_file)


async def test_resolve_on_ytdlp_fallback_persists_track_and_stream_url(resolver, repo, extractor):
    extractor.stream_urls["v1"] = "https://persist-me"

    track = make_track("v1")
    await resolver.resolve(track)

    assert ("upsert_track", "v1", "https://persist-me", None) in repo.call_log
    stored = await repo.get_track("v1")
    assert stored.stream_url == "https://persist-me"


async def test_resolve_calls_ytdlp_get_stream_url_with_correct_video_id(resolver, extractor):
    extractor.stream_urls["v1"] = "https://irrelevant"

    track = make_track("v1")
    await resolver.resolve(track)

    assert ("get_stream_url", "v1") in extractor.call_log


async def test_resolve_raises_video_unavailable_without_calling_ytdlp_when_marked(
    resolver, repo, extractor
):
    """PATCH-2026-07-20-136 Rule 0: kalau video_id sudah pernah ditandai
    unavailable, CacheResolver harus gagal cepat TANPA memanggil yt-dlp lagi
    -- sebelumnya tidak ada mekanisme ini sama sekali, jadi video yang sudah
    terbukti mati akan dicoba resolve lagi setiap kali dimainkan/diprefetch."""
    from core.exceptions import VideoUnavailableError

    track = make_track("v1")
    await repo.mark_unavailable(track, "Private video")
    extractor.stream_urls["v1"] = "https://should-never-be-fetched"

    with pytest.raises(VideoUnavailableError):
        await resolver.resolve(track)

    assert ("get_stream_url", "v1") not in extractor.call_log


async def test_resolve_proceeds_normally_when_not_marked_unavailable(resolver, repo, extractor):
    """Sanity check: track yang TIDAK pernah ditandai unavailable tetap
    resolve seperti biasa (Rule 0 tidak mengganggu jalur normal)."""
    extractor.stream_urls["v2"] = "https://normal-flow"
    track = make_track("v2")

    result = await resolver.resolve(track)

    assert result == "https://normal-flow"
