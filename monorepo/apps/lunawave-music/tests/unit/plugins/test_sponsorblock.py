from unittest.mock import AsyncMock, MagicMock

import pytest

from core.events import TrackProgressEvent
from core.state import AppState
from plugins.sponsorblock import SponsorBlockHandler


@pytest.mark.asyncio
async def test_sponsorblock_fetch_segments():
    mock_mpv = MagicMock()
    mock_state = AppState()
    mock_bus = MagicMock()
    mock_session = MagicMock()

    # Mocking the context manager for aiohttp session.get
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value=[{"segment": [10.0, 20.0]}, {"segment": [30.0, 40.0]}]
    )

    # The __aenter__ method is what gets called when using `async with`
    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_request_context)

    handler = SponsorBlockHandler(mock_mpv, mock_state, session=mock_session, event_bus=mock_bus)
    await handler.fetch_segments("test_video_id")

    assert len(handler.segments) == 2
    assert handler.segments[0] == (10.0, 20.0)
    assert handler.segments[1] == (30.0, 40.0)


@pytest.mark.asyncio
async def test_sponsorblock_on_progress_seeks_past_segment():
    mock_mpv = AsyncMock()
    mock_state = AppState()
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()

    handler = SponsorBlockHandler(mock_mpv, mock_state, session=MagicMock(), event_bus=mock_bus)
    handler.segments = [(15.0, 30.0)]

    # Progress is just before the segment, no seek
    await handler._on_progress(TrackProgressEvent(position=14.0))
    mock_mpv.seek.assert_not_called()

    # Progress is inside the segment, seek!
    await handler._on_progress(TrackProgressEvent(position=15.2))
    mock_mpv.seek.assert_called_once_with(30.0)
    mock_bus.publish.assert_called_once()


@pytest.mark.asyncio
async def test_sponsorblock_seeks_even_when_progress_jumps_past_old_narrow_window():
    """PATCH-2026-07-16-001 regression: sebelumnya deteksi pakai window
    sempit (start..start+0.6), jadi kalau satu progress event melompat dari
    posisi sebelum window ke posisi setelah window (mis. akibat throttle
    progress event lebih lambat dari 0.6s), segment itu tidak pernah
    ke-skip. Sekarang cukup start <= pos < end, tidak ada window sempit."""
    mock_mpv = AsyncMock()
    mock_state = AppState()
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()

    handler = SponsorBlockHandler(mock_mpv, mock_state, session=MagicMock(), event_bus=mock_bus)
    handler.segments = [(15.0, 30.0)]

    # Progress "melompat" dari sebelum start ke jauh di dalam segment,
    # melewati window lama (start + 0.6 = 15.6) dalam satu event.
    await handler._on_progress(TrackProgressEvent(position=20.0))
    mock_mpv.seek.assert_called_once_with(30.0)


@pytest.mark.asyncio
async def test_sponsorblock_does_not_reseek_same_segment_twice():
    """PATCH-2026-07-16-001 regression: segment yang sudah di-skip tidak
    boleh trigger seek lagi walau posisi masih di dalam rentang start-end
    (mis. mpv butuh beberapa progress event untuk benar-benar pindah
    posisi setelah perintah seek dikirim)."""
    mock_mpv = AsyncMock()
    mock_state = AppState()
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()

    handler = SponsorBlockHandler(mock_mpv, mock_state, session=MagicMock(), event_bus=mock_bus)
    handler.segments = [(15.0, 30.0)]

    await handler._on_progress(TrackProgressEvent(position=15.2))
    await handler._on_progress(TrackProgressEvent(position=15.4))
    await handler._on_progress(TrackProgressEvent(position=15.6))

    mock_mpv.seek.assert_called_once_with(30.0)


@pytest.mark.asyncio
async def test_sponsorblock_resets_skipped_segments_on_new_fetch():
    """PATCH-2026-07-16-001 regression: fetch_segments (dipanggil tiap track
    baru) harus reset _skipped_segments, atau segment dengan rentang waktu
    kebetulan sama di track berikutnya tidak akan pernah ke-skip."""
    mock_mpv = MagicMock()
    mock_state = AppState()
    mock_bus = MagicMock()
    mock_session = MagicMock()

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=[{"segment": [15.0, 30.0]}])
    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_request_context)

    handler = SponsorBlockHandler(mock_mpv, mock_state, session=mock_session, event_bus=mock_bus)
    handler._skipped_segments = {(15.0, 30.0)}

    await handler.fetch_segments("next_video_id")

    assert handler._skipped_segments == set()
