"""
Module: bootstrap.startup_tasks

Purpose:
    Unit tests for bootstrap.startup_tasks.

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
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.state import PlayerStatus


def _make_cursor_mock(row=None):
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=row)
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)
    return cursor


@pytest.fixture(autouse=True)
def _reset_context():
    """Reset the module-level context singleton in place before/after each
    test (see tests/unit/test_main.py for why rebinding wouldn't work)."""
    import bootstrap.services as services

    services.context.__init__()
    yield
    services.context.__init__()


@pytest.mark.asyncio
async def test_run_startup_checks_schedules_three_background_tasks():
    from bootstrap.services import context
    from bootstrap.startup_tasks import run_startup_checks

    context.state = MagicMock()
    context.http_session = MagicMock()
    context.mpv = MagicMock()
    context.mpv.connect = AsyncMock()
    context.mpv_ready_event = asyncio.Event()
    context.repos = MagicMock()
    context.repos.conn.execute = MagicMock(return_value=_make_cursor_mock(row=None))
    context.playback_controller = MagicMock()

    await run_startup_checks()

    assert len(context.lifecycle.tasks) == 5
    names = {t.get_name() for t in context.lifecycle.tasks}
    assert names == {
        "connectivity_checker",
        "mpv_initial_connect",
        "resume_last_track",
        "wake_lock_acquire",
        "cache_eviction",
    }

    for t in context.lifecycle.tasks:
        t.cancel()
    await asyncio.gather(*context.lifecycle.tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_resume_last_track_resumes_when_position_saved():
    from bootstrap.services import context
    from bootstrap.startup_tasks import _resume_last_track

    context.state = MagicMock()
    context.state.status = PlayerStatus.IDLE
    context.mpv_ready_event = asyncio.Event()
    context.mpv_ready_event.set()

    track = MagicMock()
    track.title = "Some Song"
    context.repos = MagicMock()
    context.repos.conn.execute = MagicMock(
        return_value=_make_cursor_mock(row={"video_id": "abc123", "last_position": 42.0})
    )
    context.repos.tracks.get_track = AsyncMock(return_value=track)
    context.playback_controller = MagicMock()
    context.playback_controller.play_track = AsyncMock()

    await _resume_last_track()

    context.playback_controller.play_track.assert_awaited_once_with(
        track, start_position=42.0, start_paused=True
    )


@pytest.mark.asyncio
async def test_resume_last_track_skips_when_mpv_errored():
    from bootstrap.services import context
    from bootstrap.startup_tasks import _resume_last_track

    context.state = MagicMock()
    context.state.status = PlayerStatus.ERROR
    context.mpv_ready_event = asyncio.Event()
    context.mpv_ready_event.set()
    context.playback_controller = MagicMock()
    context.playback_controller.play_track = AsyncMock()

    await _resume_last_track()

    context.playback_controller.play_track.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_connectivity_marks_offline_on_error():
    from bootstrap.services import context
    from bootstrap.startup_tasks import check_connectivity

    context.state = MagicMock()
    context.http_session = MagicMock()
    context.http_session.get = MagicMock(side_effect=TimeoutError())

    task = asyncio.create_task(check_connectivity())
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert context.state.is_online is False
