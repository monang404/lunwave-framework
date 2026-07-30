"""
Module: tests.integration.test_download_flow

Purpose:
    IT-04: Test end-to-end download communication.
    Download -> progress event -> complete event -> file exists.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.command_bus
    - core.commands
    - core.event_bus
    - core.events
    - core.state

Subscribes to:
    - DownloadCompleteEvent
    - LogMessageEvent

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from pathlib import Path

import pytest

from core.commands import CMD_DOWNLOAD
from core.event_bus import bus
from core.events import DownloadCompleteEvent, LogMessageEvent
from core.state import TrackInfo


@pytest.mark.asyncio
async def test_download_flow(integration_app):
    from server.app import COMMAND_BUS

    command_bus = integration_app[COMMAND_BUS]
    """
    IT-04: Download Flow
    Skenario: Download → yt-dlp → selesai
    """
    events = []

    async def capture_event(evt):
        events.append(evt)

    bus.subscribe(DownloadCompleteEvent, capture_event)
    bus.subscribe(LogMessageEvent, capture_event)

    # We need a track object to download. We can just create one manually.
    # Use a very short video to not hang the test forever.
    # "Me at the zoo" is 19 seconds.
    track = TrackInfo(video_id="jNQXAC9IVRw", title="Me at the zoo", artist="jawed", duration=19)

    # Dispatch download command
    await command_bus.execute(CMD_DOWNLOAD, track)

    # Wait for completion event
    # yt-dlp download takes a few seconds
    completed = False
    for _ in range(400):  # max 20 seconds
        await asyncio.sleep(0.1)
        if any(isinstance(e, DownloadCompleteEvent) for e in events):
            completed = True
            break

    assert completed, "Download did not complete within 40 seconds"

    # Get the file path from the event
    completion_event = next(e for e in events if isinstance(e, DownloadCompleteEvent))

    # File should exist on disk
    path = Path(completion_event.track.local_path)
    assert path.exists(), f"Downloaded file does not exist at {path}"
    assert path.stat().st_size > 0, "Downloaded file is empty"
