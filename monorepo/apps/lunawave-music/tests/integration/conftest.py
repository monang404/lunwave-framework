"""
Module: tests.integration.conftest

Purpose:
    Shared fixtures for integration tests. Wires up real components
    (EventBus, MpvController, Repositories, YtDlpClient, PlaybackController)
    but points them to temporary directories and memory databases to
    prevent side effects on the dev environment.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - adapters.mpv
    - adapters.ytdlp
    - persistence.stream_cache
    - core.event_bus
    - core.state
    - engine.command_router
    - engine.download_manager
    - engine.playback.controller
    - engine.queue_manager
    - engine.radio
    - engine.volume_service
    - persistence
    - plugins.lyrics_fetcher
    - plugins.sponsorblock
    - server.app

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import os
import shutil
from pathlib import Path

import aiohttp
import pytest

from adapters.mpv import MpvController
from adapters.ytdlp import YtDlpClient
from core.event_bus import bus
from core.state import AppState
from engine.command_router import CommandRouter
from engine.download_manager import DownloadManager
from engine.playback.controller import PlaybackController
from engine.queue_manager import QueueMode
from engine.radio import RadioMode
from engine.volume_service import VolumeService
from persistence import Repositories
from persistence.stream_cache import CacheResolver, ResolverDbCompat
from plugins.lyrics_fetcher import LyricsFetcher
from plugins.sponsorblock import SponsorBlockHandler
from server.app import create_app


@pytest.fixture
async def integration_app(tmp_path, monkeypatch):
    """
    Spawns a fully wired LunaWave application instance with real components
    but isolated storage (temp dir, memory DB).
    """
    # Isolate environment
    monkeypatch.setenv("LUNAWAVE_BASE", str(tmp_path))
    import config

    # Ensure CACHE_DIR and other paths from config use tmp_path
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "lunawave.db")
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

    # We must reset EventBus state if we want to run multiple tests cleanly,
    # but EventBus is a singleton. For integration tests, we can just clear listeners.
    bus._subscribers.clear()
    from core.command_bus import CommandBus

    command_bus = CommandBus()

    state = AppState()

    # 0. Fast-skip checks FIRST, before opening any real resource (DB
    # connection, MPV subprocess, HTTP session). Doing this before db.init()
    # matters: this is a generator-based fixture, so pytest.skip() raised
    # before `yield` means the teardown after `yield` never runs -- if the
    # DB were opened first, its connection worker thread would leak as a
    # zombie non-daemon thread on every skipped run.
    if not shutil.which("mpv"):
        pytest.skip("mpv not available in test environment, skipping integration test.")
    if not shutil.which("yt-dlp"):
        pytest.skip("yt-dlp not available in test environment, skipping integration test.")

    # 1. Initialize real DB in memory
    db = Repositories(db_path=Path(":memory:"))
    await db.init()

    # 2. Initialize real MPV (will spawn subprocess)
    # We use a custom socket path in the temp dir so it doesn't conflict
    mpv_socket = tmp_path / "cache" / "sockets" / "mpv.sock"
    mpv_socket.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "MPV_SOCKET", str(mpv_socket))
    mpv = MpvController()
    try:
        await mpv.connect()
    except Exception:
        await db.close()
        pytest.skip("MPV not available in test environment, skipping integration test.")

    # 3. YtDlpClient
    ytdlp = YtDlpClient()

    http_session = aiohttp.ClientSession()
    resolver = CacheResolver(ResolverDbCompat(db.tracks, db.artists, db.discover), ytdlp)

    sponsorblock = SponsorBlockHandler(mpv, state=state, session=http_session, event_bus=bus)
    lyrics_fetcher = LyricsFetcher(state, session=http_session, event_bus=bus)

    queue_mode = QueueMode()
    radio_mode = RadioMode(ytdlp, state, artists=db.artists, library=db.library)

    volume_service = VolumeService(bus, mpv, state)
    playback_controller = PlaybackController(
        bus, state, mpv, resolver, sponsorblock, lyrics_fetcher, queue_mode, radio_mode
    )

    DownloadManager(bus, state, ytdlp, command_bus)
    CommandRouter(playback_controller, volume_service, command_bus=command_bus)

    app = create_app(playback_controller, ytdlp, db, command_bus)

    yield app

    # Teardown
    await http_session.close()
    await db.close()
    await mpv.close()

    import subprocess

    # Ensure MPV process is killed if disconnect didn't
    if os.name != "nt":
        subprocess.run(["pkill", "-f", "mpv"], capture_output=True)
        subprocess.run(["pkill", "-f", "yt-dlp"], capture_output=True)
    else:
        subprocess.run(["taskkill", "/f", "/im", "mpv.exe"], capture_output=True)
        subprocess.run(["taskkill", "/f", "/im", "yt-dlp.exe"], capture_output=True)


@pytest.fixture
def loop(event_loop):
    """Backwards compatibility for pytest-aiohttp which expects 'loop'."""
    return event_loop


@pytest.fixture
async def app_client(aiohttp_client, integration_app):
    return await aiohttp_client(integration_app)
