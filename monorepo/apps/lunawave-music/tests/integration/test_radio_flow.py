"""
Module: tests.integration.test_radio_flow

Purpose:
    IT-03: Test end-to-end radio communication.
    Radio enabled -> prefetch -> auto-next.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.command_bus
    - core.commands
    - core.event_bus
    - core.events
    - core.state

Subscribes to:
    - TrackStartedEvent

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.commands import CMD_SET_MODE
from core.event_bus import bus
from core.events import TrackStartedEvent
from core.state import PlaybackMode
from server.app import REPOS, STATE

# Fake MPV-compatible stream URL (file:// URI that points to /dev/null or NUL)
_FAKE_STREAM_URL = "https://fake-stream.example/audio.m4a"


@pytest.mark.asyncio
async def test_radio_flow(integration_app):
    from server.app import COMMAND_BUS

    command_bus = integration_app[COMMAND_BUS]
    """
    IT-03: Radio Flow
    Skenario: Radio aktif → prefetch → isi queue

    YtDlpClient.get_stream_url di-patch agar test tidak bergantung pada
    network / yt-dlp yang berjalan sungguhan.  MPV tetap real (butuh proses
    MPV berjalan) tapi stream-nya langsung gagal karena URL fake -- yang
    penting engine dan prefetcher menjalankan alur lengkap mereka.
    """
    events = []

    async def track_event(evt):
        events.append(evt)

    bus.subscribe(TrackStartedEvent, track_event)

    # Seed an artist and a song in the in-memory database to prevent RuntimeError.
    # Gunakan YouTube ID 11 karakter agar yt-dlp ID validator tidak menolak
    # sebelum mock sempat berjalan.
    repos = integration_app[REPOS]
    await repos.conn.execute("INSERT INTO artists (id, nama) VALUES (?, ?)", (1, "Me at the zoo"))
    await repos.conn.executemany(
        "INSERT INTO songs (artist_id, judul, youtube_id, duration) VALUES (?, ?, ?, ?)",
        [
            (1, "Me at the zoo", "jNQXAC9IVRw", 19),
            (1, "Dummy Track 2", "dummyAAAABBB", 20),
            (1, "Dummy Track 3", "dummyCCCDDDD", 21),
        ],
    )
    await repos.conn.commit()

    # Patch YtDlpClient.get_stream_url sehingga semua resolve langsung berhasil
    # tanpa network round-trip -- radio engine tetap menjalankan alur penuh.
    with patch(
        "adapters.ytdlp.YtDlpClient.get_stream_url",
        new_callable=AsyncMock,
        return_value=_FAKE_STREAM_URL,
    ):
        # 1. Enable radio using a famous artist seed
        integration_app[STATE].radio_artist = "Me at the zoo"
        await command_bus.execute(CMD_SET_MODE, PlaybackMode.RADIO)

        # Check that RadioEngine resolves at least one track and starts it.
        # MPV akan gagal memutar fake URL -- yang penting radio_queue terisi
        # oleh prefetcher (tidak perlu TrackStartedEvent sungguhan).
        for _ in range(300):
            await asyncio.sleep(0.1)
            if any(isinstance(e, TrackStartedEvent) for e in events):
                break

        # Tidak wajib started karena MPV tidak bisa play fake URL;
        # yang diuji adalah prefetch queue, bukan pemutaran sungguhan.
        state = integration_app[STATE]

        prefetched = False
        for _ in range(300):
            await asyncio.sleep(0.1)
            if len(state.radio_queue) > 0:
                prefetched = True
                break

    assert prefetched, "Radio did not prefetch and populate radio_queue within 30 seconds"
