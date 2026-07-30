"""
Module: main

Purpose:
    Unit tests for main.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    None

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


def _make_cursor_mock():
    """Buat mock cursor yang mensimulasikan aiohttp-style async context manager."""
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=None)  # tidak ada last track
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)
    return cursor


@pytest.fixture(autouse=True)
def _reset_bootstrap_context():
    """bootstrap.services.context is a module-level singleton shared across
    all bootstrap stages — reset it in place (not by rebinding the module
    attribute) before/after each test, since bootstrap.startup_tasks and
    bootstrap.maintenance did `from bootstrap.services import context` and
    hold their own reference to the same object; rebinding
    `services.context` would not reach them. Mirrors the fresh locals
    main() used to create on every call before T2.4."""
    import bootstrap.services as services

    services.context.__init__()
    yield
    services.context.__init__()


@pytest.mark.asyncio
@patch("main.log_session_end")
@patch("main.log_session_start")
@patch("bootstrap.services.shutil.which", return_value="/usr/bin/mpv")
@patch("bootstrap.services.Repositories")
@patch("bootstrap.services.MpvController")
@patch("bootstrap.services.YtDlpClient")
@patch("engine.playback.controller.PlaybackController")
@patch("bootstrap.services.DownloadManager")
@patch("bootstrap.services.CommandRouter")
@patch("bootstrap.services.TermuxNowPlaying")
@patch("bootstrap.services.SponsorBlockHandler")
@patch("bootstrap.services.LyricsFetcher")
@patch("persistence.stream_cache.CacheResolver")
@patch("engine.queue_manager.QueueMode")
@patch("engine.radio.RadioMode")
@patch("engine.volume_service.VolumeService")
@patch("server.app.create_app")
@patch("server.app.run_server", new_callable=AsyncMock)
@patch("bootstrap.services.aiohttp.ClientSession")
@patch("engine.loudness.service.LoudnessService")
async def test_main_smoke(
    mock_loudness,
    mock_session,
    mock_run_server,
    mock_create_app,
    mock_volume,
    mock_radio,
    mock_queue,
    mock_resolver,
    mock_lyrics,
    mock_sponsor,
    mock_nowplaying_cls,
    mock_router,
    mock_dl_manager,
    mock_controller,
    mock_ytdlp,
    mock_mpv,
    mock_db,
    mock_which,
    mock_log_session_start,
    mock_log_session_end,
):
    from main import main

    # Setup mocks
    repos_instance = mock_db.return_value
    repos_instance.init = AsyncMock()
    repos_instance.close = AsyncMock()
    repos_instance.tracks = MagicMock()
    repos_instance.tracks.evict_stale_tracks = AsyncMock(return_value=0)
    repos_instance.tracks.get_track = AsyncMock(return_value=None)
    repos_instance.sessions = MagicMock()
    repos_instance.sessions.cleanup_sessions = AsyncMock()
    repos_instance.artists = MagicMock()
    repos_instance.library = MagicMock()
    repos_instance.discover = MagicMock()
    repos_instance.conn = MagicMock()
    repos_instance.conn.execute = MagicMock(return_value=_make_cursor_mock())

    mpv_instance = mock_mpv.return_value
    mpv_instance.connect = AsyncMock()
    mpv_instance.close = AsyncMock()
    mpv_instance.is_connected = False
    mpv_instance.is_available = True

    nowplaying_inst = mock_nowplaying_cls.return_value
    nowplaying_inst.start = AsyncMock()
    nowplaying_inst.cleanup = AsyncMock()

    mock_session.return_value.close = AsyncMock()

    # When run_server is called, gracefully exit as if a signal was received.
    # Yield control dulu ke event loop agar background tasks (mpv_initial_connect,
    # resume_last_track, dll) sempat di-schedule sebelum CancelledError dipropagasi.
    async def mock_run_server_impl(*args, **kwargs):
        await asyncio.sleep(0.05)  # beri kesempatan background tasks jalan
        raise asyncio.CancelledError()

    mock_run_server.side_effect = mock_run_server_impl

    await main()

    # Beri tambahan waktu agar background tasks benar-benar selesai dieksekusi
    await asyncio.sleep(0.1)

    # Assertions
    repos_instance.init.assert_awaited_once()
    mpv_instance.connect.assert_awaited_once()
    mock_create_app.assert_called_once()
    mock_run_server.assert_awaited_once()
    nowplaying_inst.start.assert_awaited_once()
    nowplaying_inst.cleanup.assert_awaited_once()

    # ADR-0010: main.run_server() wajib menandai awal & akhir sesi lewat
    # log_session_start()/log_session_end() (core.log_config) -- ini
    # sebelumnya didefinisikan di sesi 2 tapi belum pernah dipanggil dari
    # mana pun sampai fix ini.
    mock_log_session_start.assert_called_once()
    mock_log_session_end.assert_called_once()

    # Allow event loop to process task cancellations
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
@patch("bootstrap.services.shutil.which", return_value="/usr/bin/mpv")
@patch("bootstrap.services.Repositories")
@patch("bootstrap.services.MpvController")
@patch("bootstrap.services.YtDlpClient")
@patch("engine.playback.controller.PlaybackController")
@patch("bootstrap.services.DownloadManager")
@patch("bootstrap.services.CommandRouter")
@patch("bootstrap.services.TermuxNowPlaying")
@patch("bootstrap.services.SponsorBlockHandler")
@patch("bootstrap.services.LyricsFetcher")
@patch("persistence.stream_cache.CacheResolver")
@patch("engine.queue_manager.QueueMode")
@patch("engine.radio.RadioMode")
@patch("engine.volume_service.VolumeService")
@patch("server.app.create_app")
@patch("server.app.run_server", new_callable=AsyncMock)
@patch("bootstrap.services.aiohttp.ClientSession")
@patch("engine.loudness.service.LoudnessService")
async def test_run_server_not_blocked_by_mpv(
    mock_loudness,
    mock_session,
    mock_run_server,
    mock_create_app,
    mock_volume,
    mock_radio,
    mock_queue,
    mock_resolver,
    mock_lyrics,
    mock_sponsor,
    mock_nowplaying_cls,
    mock_router,
    mock_dl_manager,
    mock_controller,
    mock_ytdlp,
    mock_mpv,
    mock_db,
    mock_which,
):
    """Verifikasi bahwa run_server() dipanggil sebelum mpv.connect() selesai.
    Pakai asyncio.Event untuk koordinasi deterministik — run_server mock
    menge-set 'server_started_event' saat dipanggil, lalu 'mpv_connect' menunggu
    event itu sebelum complete. Kalau run_server benar-benar dipanggil duluan
    (non-blocking), flow ini akan selesai normal; kalau tidak, loop hang."""
    from main import main

    server_started = asyncio.Event()
    mpv_connect_finished = []

    repos_instance = mock_db.return_value
    repos_instance.init = AsyncMock()
    repos_instance.close = AsyncMock()
    repos_instance.tracks = MagicMock()
    repos_instance.tracks.evict_stale_tracks = AsyncMock(return_value=0)
    repos_instance.tracks.get_track = AsyncMock(return_value=None)
    repos_instance.sessions = MagicMock()
    repos_instance.sessions.cleanup_sessions = AsyncMock()
    repos_instance.artists = MagicMock()
    repos_instance.library = MagicMock()
    repos_instance.discover = MagicMock()
    repos_instance.conn = MagicMock()
    repos_instance.conn.execute = MagicMock(return_value=_make_cursor_mock())

    async def event_driven_mpv_connect():
        # MPV 'connect' hanya menunggu sinyal bahwa server sudah dipanggil.
        # Kalau server diblok oleh MPV, ini akan deadlock (dan pytest timeout akan menangkap).
        # Timeout singkat agar test tidak hang jika arsitektur berubah.
        try:
            await asyncio.wait_for(server_started.wait(), timeout=2.0)
            mpv_connect_finished.append(True)
        except TimeoutError:
            pass  # server tidak pernah dipanggil dalam 2 detik — test akan fail di assertion

    mpv_instance = mock_mpv.return_value
    mpv_instance.connect = event_driven_mpv_connect
    mpv_instance.close = AsyncMock()
    mpv_instance.is_connected = False
    mpv_instance.is_available = True

    nowplaying_inst = mock_nowplaying_cls.return_value
    nowplaying_inst.start = AsyncMock()
    nowplaying_inst.cleanup = AsyncMock()
    mock_session.return_value.close = AsyncMock()

    async def signaling_run_server(*args, **kwargs):
        # Set event dulu, beri event loop 1 yield agar MPV task sempat
        # observe event-nya, baru raise CancelledError.
        server_started.set()
        await asyncio.sleep(0.05)  # beri waktu mpv_connect menyelesaikan wait
        raise asyncio.CancelledError()

    mock_run_server.side_effect = signaling_run_server

    await main()

    # Beri tambahan waktu agar background tasks benar-benar selesai
    await asyncio.sleep(0.1)

    # Verifikasi: run_server pasti sudah dipanggil (set event), dan MPV connect
    # berhasil menyelesaikan wait-nya — membuktikan keduanya berjalan concurrently.
    assert server_started.is_set(), "run_server tidak pernah dipanggil"
    assert len(mpv_connect_finished) == 1, (
        "mpv.connect tidak menyelesaikan eksekusinya — "
        "kemungkinan server memblok MPV atau task di-cancel terlalu cepat"
    )
