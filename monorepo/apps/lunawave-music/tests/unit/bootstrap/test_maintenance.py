"""
Module: bootstrap.maintenance

Purpose:
    Unit tests for bootstrap.maintenance.

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

from core.state import PlayerStatus


@pytest.fixture(autouse=True)
def _reset_context():
    """Reset the module-level context singleton in place before/after each
    test (see tests/unit/test_main.py for why rebinding wouldn't work)."""
    import bootstrap.services as services

    services.context.__init__()
    yield
    services.context.__init__()


@pytest.mark.asyncio
async def test_schedule_db_maintenance_appends_task():
    from bootstrap.maintenance import schedule_db_maintenance
    from bootstrap.services import context

    context.repos = MagicMock()
    context.repos.tracks.evict_stale_tracks = AsyncMock(return_value=0)
    context.repos.sessions.cleanup_sessions = AsyncMock()

    schedule_db_maintenance()

    assert len(context.lifecycle.tasks) == 1
    assert context.lifecycle.tasks[0].get_name() == "db_maintenance"

    for t in context.lifecycle.tasks:
        t.cancel()
    await asyncio.gather(*context.lifecycle.tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_db_maintenance_runs_initial_eviction_and_cleanup():
    from bootstrap.maintenance import db_maintenance
    from bootstrap.services import context

    context.repos = MagicMock()
    context.repos.tracks.evict_stale_tracks = AsyncMock(return_value=3)
    context.repos.sessions.cleanup_sessions = AsyncMock()

    task = asyncio.create_task(db_maintenance())
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    context.repos.tracks.evict_stale_tracks.assert_awaited_once()
    context.repos.sessions.cleanup_sessions.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_mpv_watchdog_appends_task():
    from bootstrap.maintenance import start_mpv_watchdog
    from bootstrap.services import context

    context.mpv = MagicMock()
    context.state = MagicMock()

    start_mpv_watchdog()

    assert len(context.lifecycle.tasks) == 1
    assert context.lifecycle.tasks[0].get_name() == "mpv_watchdog"

    for t in context.lifecycle.tasks:
        t.cancel()
    await asyncio.gather(*context.lifecycle.tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_mpv_watchdog_sets_error_when_disconnected(monkeypatch):
    from bootstrap import maintenance
    from bootstrap.services import context

    context.mpv = MagicMock()
    context.mpv.is_available = True
    context.mpv.is_connected = False
    context.state = MagicMock()
    context.state.status = PlayerStatus.PLAYING

    # `mpv_watchdog` is an infinite `while True: await asyncio.sleep(10); ...`
    # loop. Rather than racing real timers, let the first sleep pass through
    # (so the loop body runs once and mutates state) and raise on the second
    # call to break out of the loop deterministically.
    call_count = {"n": 0}

    async def _sleep_then_stop(_seconds):
        call_count["n"] += 1
        if call_count["n"] > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr(maintenance.asyncio, "sleep", _sleep_then_stop)

    with pytest.raises(asyncio.CancelledError):
        await maintenance.mpv_watchdog()

    assert context.state.status == PlayerStatus.ERROR
    assert context.state.error_msg


@pytest.mark.asyncio
async def test_schedule_status_log_appends_task():
    from bootstrap.maintenance import schedule_status_log
    from bootstrap.services import context

    schedule_status_log()

    assert len(context.lifecycle.tasks) == 1
    assert context.lifecycle.tasks[0].get_name() == "status_log"

    for t in context.lifecycle.tasks:
        t.cancel()
    await asyncio.gather(*context.lifecycle.tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_status_log_task_logs_summary_line_each_interval(monkeypatch):
    """ADR-0010 O4.2: with time accelerated (mocked sleep), the loop must
    run multiple iterations and emit a '[STATUS] ...' line each time,
    without ever raising."""
    from bootstrap import maintenance

    call_count = {"n": 0}

    async def _fast_sleep(_seconds):
        call_count["n"] += 1
        if call_count["n"] > 3:
            raise asyncio.CancelledError()

    monkeypatch.setattr(maintenance.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(maintenance, "STATUS_LOG_INTERVAL_SECONDS", 0)

    logged = []
    fake_logger = MagicMock()
    fake_logger.info.side_effect = lambda msg, **kwargs: logged.append(msg)
    # `logger` is bound once at module import time (component=... per L-D1),
    # not re-fetched per call -- patch the module-level instance directly,
    # the same pattern used in tests/unit/server/middleware/test_traffic.py,
    # instead of patching structlog.get_logger (which no longer has any
    # effect after the logger object already exists).
    monkeypatch.setattr(maintenance, "logger", fake_logger)

    with pytest.raises(asyncio.CancelledError):
        await maintenance.status_log_task()

    assert call_count["n"] == 4
    assert len(logged) == 3
    assert all(line == "status_snapshot" for line in logged)


@pytest.mark.asyncio
async def test_status_log_task_never_crashes_when_all_sources_fail(monkeypatch):
    """Fail-safe: even if RAM read, uptime, and metric collection all raise,
    the loop must keep running (only the cancellation from sleep() should
    stop it), never propagate an unrelated exception."""
    from bootstrap import maintenance

    call_count = {"n": 0}

    async def _fast_sleep(_seconds):
        call_count["n"] += 1
        if call_count["n"] > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr(maintenance.asyncio, "sleep", _fast_sleep)

    with (
        patch("core.mem_stats.get_rss_mb", side_effect=Exception("boom")),
        patch(
            "core.server_clock.ServerClock.uptime_seconds",
            new_callable=lambda: property(lambda self: (_ for _ in ()).throw(Exception("boom"))),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await maintenance.status_log_task()

    assert call_count["n"] == 2
