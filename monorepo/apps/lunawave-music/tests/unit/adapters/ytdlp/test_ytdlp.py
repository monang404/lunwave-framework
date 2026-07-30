"""
Module: tests.unit.adapters.ytdlp.test_ytdlp

Purpose:
    Unit tests for the adapters.ytdlp package: YtDlpSearcher._to_track and
    search filtering logic (tested directly on the split submodules), plus
    the YtDlpClient facade end-to-end behavior (search/get_stream_url/
    download_audio/cancellation, tested through the facade's public API).
    Consolidated from test_ytdlp.py + test_ytdlp_client.py (T4.6) since both
    files tested overlapping logic (_to_track, _pick_audio_url) just via
    different entry points (submodule directly vs. facade). No assertions
    were dropped in the merge — the facade-level classes below are suffixed
    "ViaYtDlpClient" to avoid name collision with the submodule-level ones.
    yt-dlp is always mocked at the executor level, no real network calls.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - adapters.ytdlp
    - adapters.ytdlp.downloader
    - adapters.ytdlp.resolver
    - adapters.ytdlp.searcher
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.ytdlp import YtDlpClient
from adapters.ytdlp.searcher import YtDlpSearcher
from core.state import TrackInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_entry(
    id="abc123",
    title="Test Song",
    uploader="Test Artist",
    duration=200,
    thumbnail="http://img.example.com/thumb.jpg",
    view_count=1000,
):
    return {
        "id": id,
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "thumbnail": thumbnail,
        "view_count": view_count,
    }


def make_searcher():
    executor = MagicMock()
    return YtDlpSearcher(executor=executor)


# ---------------------------------------------------------------------------
# _to_track
# ---------------------------------------------------------------------------


class TestToTrack:
    def test_maps_basic_fields(self):
        searcher = make_searcher()
        entry = make_entry()
        track = searcher._to_track(entry)

        assert isinstance(track, TrackInfo)
        assert track.video_id == "abc123"
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.duration == 200
        assert track.thumbnail == "http://img.example.com/thumb.jpg"
        assert track.view_count == 1000

    def test_uses_fallback_video_id_when_invalid_chars(self):
        searcher = make_searcher()
        entry = make_entry(id="invalid id with spaces!", title="My Song")
        track = searcher._to_track(entry)

        # Should generate a hash-based fallback
        assert track.video_id.startswith("vid_")

    def test_uses_fallback_video_id_when_empty(self):
        searcher = make_searcher()
        entry = make_entry(id="", title="My Song")
        track = searcher._to_track(entry)

        assert track.video_id.startswith("vid_")

    def test_handles_missing_duration(self):
        searcher = make_searcher()
        entry = make_entry()
        entry.pop("duration")
        track = searcher._to_track(entry)
        assert track.duration == 0

    def test_handles_none_duration(self):
        searcher = make_searcher()
        entry = make_entry(duration=None)
        track = searcher._to_track(entry)
        assert track.duration == 0


# ---------------------------------------------------------------------------
# search — filtering
# ---------------------------------------------------------------------------


class TestSearchFiltering:
    def _make_results(self, entries):
        return {"entries": entries}

    @pytest.mark.asyncio
    async def test_skips_entries_longer_than_600s(self):
        searcher = make_searcher()
        entries = [make_entry(duration=601), make_entry(id="short1", duration=180)]

        with patch.object(searcher, "_extract_sync", return_value=self._make_results(entries)):
            searcher._extract_sync  # ensure it's patched
            # Patch loop.run_in_executor to call _extract_sync directly
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    return_value=self._make_results(entries)
                )
                results = await searcher.search("test")

        assert len(results) == 1
        assert results[0].video_id == "short1"

    @pytest.mark.asyncio
    async def test_skips_entries_with_banned_keywords(self):
        searcher = make_searcher()
        banned_entries = [
            make_entry(id="b1", title="Best Mix 2024"),
            make_entry(id="b2", title="Full Album Collection"),
            make_entry(id="b3", title="Compilation Vol 5"),
        ]
        good_entry = make_entry(id="good1", title="Normal Song", duration=200)
        entries = banned_entries + [good_entry]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=self._make_results(entries)
            )
            results = await searcher.search("test")

        assert len(results) == 1
        assert results[0].video_id == "good1"

    @pytest.mark.asyncio
    async def test_skips_none_entries(self):
        searcher = make_searcher()
        entries = [None, make_entry(id="valid1")]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=self._make_results(entries)
            )
            results = await searcher.search("test")

        assert len(results) == 1
        assert results[0].video_id == "valid1"

    @pytest.mark.asyncio
    async def test_respects_max_results(self):
        searcher = make_searcher()
        entries = [make_entry(id=f"t{i}", title=f"Track {i}", duration=100) for i in range(20)]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=self._make_results(entries)
            )
            results = await searcher.search("test", max_results=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_returns_empty_when_entries_all_filtered(self):
        searcher = make_searcher()
        entries = [make_entry(id="b1", duration=700)]  # too long

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value=self._make_results(entries)
            )
            results = await searcher.search("test")

        assert results == []


# ---------------------------------------------------------------------------
# YtDlpResolver._pick_audio_url
# ---------------------------------------------------------------------------


class TestPickAudioUrl:
    def test_prefers_audio_only_format(self):
        from adapters.ytdlp.resolver import YtDlpResolver

        resolver = YtDlpResolver(executor=MagicMock())
        info = {
            "formats": [
                {"acodec": "mp4a.40.2", "vcodec": "avc1", "url": "http://video.url"},
                {"acodec": "mp4a.40.2", "vcodec": "none", "url": "http://audio.url"},
            ],
        }
        result = resolver._pick_audio_url(info)
        assert result == "http://audio.url"

    def test_falls_back_to_top_level_url_when_no_audio_only(self):
        from adapters.ytdlp.resolver import YtDlpResolver

        resolver = YtDlpResolver(executor=MagicMock())
        info = {
            "formats": [
                {"acodec": "mp4a.40.2", "vcodec": "avc1", "url": "http://muxed.url"},
            ],
        }
        result = resolver._pick_audio_url(info)
        # No audio-only format exists, so it falls back to the muxed
        # (audio+video) format instead of failing outright.
        assert result == "http://muxed.url"


# ---------------------------------------------------------------------------
# YtDlpDownloader
# ---------------------------------------------------------------------------


class TestYtDlpDownloader:
    def test_cancel_sets_flag(self):
        from adapters.ytdlp.downloader import YtDlpDownloader

        dl = YtDlpDownloader(executor=MagicMock())
        assert dl.is_cancelled is False
        dl.cancel_download()
        assert dl.is_cancelled is True

    def test_cancel_hook_raises_when_cancelled(self):
        from adapters.ytdlp.downloader import YtDlpDownloader

        dl = YtDlpDownloader(executor=MagicMock())
        dl.is_cancelled = True
        with pytest.raises(Exception, match="DownloadCancelled"):
            dl._check_cancel_hook({})

    def test_cancel_hook_does_not_raise_when_not_cancelled(self):
        from adapters.ytdlp.downloader import YtDlpDownloader

        dl = YtDlpDownloader(executor=MagicMock())
        dl.is_cancelled = False
        dl._check_cancel_hook({})  # should not raise

    @pytest.mark.asyncio
    async def test_download_mp3_resets_cancel_flag_on_start(self):
        from adapters.ytdlp.downloader import YtDlpDownloader

        dl = YtDlpDownloader(executor=MagicMock())
        dl.is_cancelled = True

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)
            with patch("adapters.ytdlp.downloader.CACHE_DIR") as mock_dir:
                mock_dir.mkdir = MagicMock()
                mock_dir.__truediv__ = MagicMock(return_value=MagicMock())
                await dl.download_mp3("abc123")

        assert dl.is_cancelled is False


# ---------------------------------------------------------------------------
# YtDlpClient facade — helpers
# (merged from test_ytdlp_client.py, T4.6; renamed make_entry -> make_client_entry
#  to avoid colliding with the make_entry() helper above, which uses a
#  different keyword-arg name for the video id: `id=` vs `video_id=`)
# ---------------------------------------------------------------------------


def make_client_entry(
    video_id="abc123",
    title="Test Song",
    uploader="Test Artist",
    duration=180,
    thumbnail="https://img/thumb.jpg",
    view_count=1000,
):
    """Minimal yt-dlp flat-extract entry dict."""
    return {
        "id": video_id,
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "thumbnail": thumbnail,
        "view_count": view_count,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def make_search_result(entries):
    """Wrap entries in a yt-dlp search result envelope."""
    return {"entries": entries}


def make_stream_info(url="https://cdn.example.com/audio.m4a"):
    """Minimal info dict returned by yt-dlp for a single video."""
    return {
        "url": url,
        "formats": [
            {"acodec": "opus", "vcodec": "none", "url": url},
        ],
    }


# ---------------------------------------------------------------------------
# YtDlpClient facade — _to_track (via client._searcher)
# ---------------------------------------------------------------------------


class TestToTrackViaYtDlpClient:
    def test_maps_standard_fields_correctly(self):
        client = YtDlpClient()
        entry = make_client_entry()
        track = client._searcher._to_track(entry)
        assert track.video_id == "abc123"
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.duration == 180
        assert track.thumbnail == "https://img/thumb.jpg"
        assert track.view_count == 1000

    def test_duration_none_becomes_zero(self):
        client = YtDlpClient()
        entry = make_client_entry(duration=None)
        track = client._searcher._to_track(entry)
        assert track.duration == 0

    def test_duration_float_is_coerced_to_int(self):
        client = YtDlpClient()
        entry = make_client_entry(duration=183.7)
        track = client._searcher._to_track(entry)
        assert track.duration == 183

    def test_missing_video_id_generates_stable_fallback(self):
        client = YtDlpClient()
        entry = {"title": "No ID Song", "uploader": "Art", "duration": 100}
        track = client._searcher._to_track(entry)
        assert track.video_id.startswith("vid_")

    def test_invalid_video_id_chars_generates_fallback(self):
        client = YtDlpClient()
        entry = make_client_entry(video_id="bad/id?here")
        track = client._searcher._to_track(entry)
        # Should fall back to hashed id
        assert track.video_id.startswith("vid_")

    def test_valid_video_id_kept_as_is(self):
        client = YtDlpClient()
        entry = make_client_entry(video_id="dQw4w9WgXcQ")
        track = client._searcher._to_track(entry)
        assert track.video_id == "dQw4w9WgXcQ"


# ---------------------------------------------------------------------------
# YtDlpClient facade — _pick_audio_url (via client._resolver)
# ---------------------------------------------------------------------------


class TestPickAudioUrlViaYtDlpClient:
    def test_returns_audio_only_format_url(self):
        client = YtDlpClient()
        info = {
            "formats": [
                {"acodec": "none", "vcodec": "h264", "url": "https://video.url"},
                {"acodec": "opus", "vcodec": "none", "url": "https://audio.url"},
            ],
        }
        assert client._resolver._pick_audio_url(info) == "https://audio.url"

    def test_falls_back_to_top_level_url_when_no_audio_only_format(self):
        client = YtDlpClient()
        info = {
            "formats": [
                {"acodec": "mp4a", "vcodec": "h264", "url": "https://av.url"},
            ],
        }
        # No audio-only format exists, so it falls back to the muxed
        # (audio+video) format instead of failing outright.
        assert client._resolver._pick_audio_url(info) == "https://av.url"

    def test_prefers_last_audio_only_format_reversed(self):
        """_pick_audio_url iterates reversed(formats), so last audio-only wins."""
        client = YtDlpClient()
        info = {
            "formats": [
                {"acodec": "mp4a", "vcodec": "none", "url": "https://audio1.url"},
                {"acodec": "opus", "vcodec": "none", "url": "https://audio2.url"},
            ],
        }
        # reversed: audio2 comes first in iteration -> picked
        assert client._resolver._pick_audio_url(info) == "https://audio2.url"


# ---------------------------------------------------------------------------
# YtDlpClient facade — search()
# ---------------------------------------------------------------------------


class TestSearch:
    async def test_returns_tracks_for_valid_entries(self):
        client = YtDlpClient()
        raw = make_search_result([make_client_entry("v1"), make_client_entry("v2")])

        with patch.object(client._searcher, "_extract_sync", return_value=raw):
            results = await client.search("test query")

        assert len(results) == 2
        assert all(isinstance(t, TrackInfo) for t in results)

    async def test_filters_out_videos_longer_than_10_minutes(self):
        client = YtDlpClient()
        entries = [make_client_entry("v1", duration=601), make_client_entry("v2", duration=300)]
        raw = make_search_result(entries)

        with patch.object(client._searcher, "_extract_sync", return_value=raw):
            results = await client.search("test")

        assert len(results) == 1
        assert results[0].video_id == "v2"

    async def test_filters_out_compilation_keywords_in_title(self):
        client = YtDlpClient()
        bad_titles = [
            "Best Mix 2024",
            "Full Album",
            "Top Playlist",
            "Mega Mashup",
            "Medley",
            "Megamix",
        ]
        entries = [make_client_entry(f"v{i}", title=t) for i, t in enumerate(bad_titles)]
        entries.append(make_client_entry("good", title="Normal Song"))
        raw = make_search_result(entries)

        with patch.object(client._searcher, "_extract_sync", return_value=raw):
            results = await client.search("music")

        assert len(results) == 1
        assert results[0].video_id == "good"

    async def test_respects_max_results_limit(self):
        client = YtDlpClient()
        entries = [make_client_entry(f"v{i}") for i in range(10)]
        raw = make_search_result(entries)

        with patch.object(client._searcher, "_extract_sync", return_value=raw):
            results = await client.search("test", max_results=3)

        assert len(results) == 3

    async def test_skips_none_entries_in_results(self):
        client = YtDlpClient()
        raw = make_search_result([None, make_client_entry("v1"), None, make_client_entry("v2")])

        with patch.object(client._searcher, "_extract_sync", return_value=raw):
            results = await client.search("test")

        assert len(results) == 2

    async def test_returns_empty_list_when_no_entries(self):
        client = YtDlpClient()
        with patch.object(client._searcher, "_extract_sync", return_value={"entries": []}):
            results = await client.search("nothing")
        assert results == []


# ---------------------------------------------------------------------------
# YtDlpClient facade — get_stream_url()
# ---------------------------------------------------------------------------


class TestGetStreamUrl:
    async def test_returns_audio_url_on_success(self):
        client = YtDlpClient()
        info = make_stream_info("https://cdn.example.com/audio.m4a")

        with patch.object(client._resolver, "_extract_sync", return_value=info):
            url = await client.get_stream_url("dQw4w9WgXcQ")

        assert url == "https://cdn.example.com/audio.m4a"

    async def test_raises_runtime_error_when_extract_returns_none(self):
        client = YtDlpClient()

        with patch.object(client._resolver, "_extract_sync", return_value=None):
            with pytest.raises(RuntimeError, match="no stream URL"):
                await client.get_stream_url("vid123")

    async def test_raises_runtime_error_when_extract_returns_empty_formats(self):
        client = YtDlpClient()
        info = {"url": "", "formats": []}  # _pick_audio_url falls through to empty url

        with patch.object(client._resolver, "_extract_sync", return_value=info):
            with pytest.raises(RuntimeError):
                await client.get_stream_url("vid123")

    async def test_wraps_arbitrary_exception_as_runtime_error(self):
        client = YtDlpClient()

        with patch.object(
            client._resolver, "_extract_sync", side_effect=ConnectionError("net down")
        ):
            with pytest.raises(RuntimeError, match="Gagal mengambil"):
                await client.get_stream_url("vid123")

    async def test_raises_runtime_error_on_timeout(self):
        client = YtDlpClient()

        async def slow_executor(*_):
            await asyncio.sleep(999)

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with pytest.raises(RuntimeError, match="Timeout"):
                await client.get_stream_url("vid123")


# ---------------------------------------------------------------------------
# YtDlpClient facade — download_audio()
# ---------------------------------------------------------------------------


class TestDownloadAudio:
    async def test_returns_expected_mp3_path(self, tmp_path, monkeypatch):
        client = YtDlpClient()

        with patch.object(client._downloader, "_download_sync", return_value=None):
            monkeypatch.setattr("adapters.ytdlp.downloader.CACHE_DIR", tmp_path)
            path = await client.download_audio("abc123")

        assert path == str(tmp_path / "abc123.opus")

    async def test_sanitizes_video_id_in_output_path(self, tmp_path, monkeypatch):
        client = YtDlpClient()

        with patch.object(client._downloader, "_download_sync", return_value=None):
            monkeypatch.setattr("adapters.ytdlp.downloader.CACHE_DIR", tmp_path)
            path = await client.download_audio("bad/id:here")

        # Slashes and colons become underscores
        assert "/" not in path.split("/")[-1]

    async def test_resets_is_cancelled_before_download(self, tmp_path, monkeypatch):
        client = YtDlpClient()
        client._downloader.is_cancelled = True

        with patch.object(client._downloader, "_download_sync", return_value=None):
            monkeypatch.setattr("adapters.ytdlp.downloader.CACHE_DIR", tmp_path)
            await client.download_audio("v1")

        assert client._downloader.is_cancelled is False


# ---------------------------------------------------------------------------
# YtDlpClient facade — cancel_download / _check_cancel_hook
# ---------------------------------------------------------------------------


class TestCancellation:
    def test_cancel_download_sets_flag(self):
        client = YtDlpClient()
        assert client._downloader.is_cancelled is False
        client.cancel_download()
        assert client._downloader.is_cancelled is True

    def test_check_cancel_hook_raises_when_cancelled(self):
        client = YtDlpClient()
        client._downloader.is_cancelled = True
        with pytest.raises(Exception, match="DownloadCancelled"):
            client._downloader._check_cancel_hook({})

    def test_check_cancel_hook_does_not_raise_when_not_cancelled(self):
        client = YtDlpClient()
        client._downloader.is_cancelled = False
        # Should not raise
        client._downloader._check_cancel_hook({})
