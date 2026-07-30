"""
Module: tests.unit.engine.radio.test_prefetcher

Purpose:
    Unit tests for radio track prefetching.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state
    - engine.radio.prefetcher

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

from core.state import AppState, TrackInfo
from engine.radio.prefetcher import RadioPrefetcher


class MockArtistSelector:
    async def gather_batch(self, prioritized_artist=None, max_artists=1):
        return [
            TrackInfo(video_id="1", title="T1", artist="A", duration=100),
            TrackInfo(video_id="2", title="T2", artist="B", duration=100),
        ]


class MockPlaybackController:
    pass


@pytest.mark.asyncio
async def test_build_and_pop_standby():
    state = AppState()
    selector = MockArtistSelector()
    prefetcher = RadioPrefetcher(state, selector)
    controller = MockPlaybackController()

    # Standby is initially empty
    assert await prefetcher.pop_standby() is None

    # Build standby
    await prefetcher.build_standby(controller)
    assert len(prefetcher._standby) == 2

    # Pop standby
    popped = await prefetcher.pop_standby()
    assert len(popped) == 2
    assert popped[0].video_id == "1"

    # Standby is empty again
    assert await prefetcher.pop_standby() is None


@pytest.mark.asyncio
async def test_clear_standby():
    state = AppState()
    selector = MockArtistSelector()
    prefetcher = RadioPrefetcher(state, selector)
    controller = MockPlaybackController()

    await prefetcher.build_standby(controller)
    assert len(prefetcher._standby) == 2

    await prefetcher.async_clear_standby()
    assert len(prefetcher._standby) == 0


@pytest.mark.asyncio
async def test_do_prefetch_handles_resolve_error():
    state = AppState()
    state.radio_queue.append(TrackInfo(video_id="1", title="T1", artist="A", duration=100))
    selector = MockArtistSelector()
    prefetcher = RadioPrefetcher(state, selector)

    controller = MagicMock()
    controller.track_loader.resolver.resolve = AsyncMock(side_effect=Exception("Resolve Error"))

    await prefetcher._do_prefetch(controller)
    controller.track_loader.resolver.resolve.assert_called_once()


@pytest.mark.asyncio
async def test_check_prefetch_triggers_prefetch():
    state = AppState()
    state.current_track = TrackInfo(video_id="1", title="T1", artist="A", duration=100)
    selector = MockArtistSelector()
    prefetcher = RadioPrefetcher(state, selector)

    controller = MagicMock()
    controller.track_loader.resolver.latency_window.percentile.return_value = 10.0

    # 10 * 1.5 = 15 sec threshold
    # position 86, duration 100 -> remaining 14 sec (<= 15) -> trigger
    prefetcher.check_prefetch(controller, 86, 100)

    assert len(prefetcher._bg_tasks) == 1

    # check idempotency
    prefetcher.check_prefetch(controller, 87, 100)
    assert len(prefetcher._bg_tasks) == 1


@pytest.mark.asyncio
async def test_do_prefetch_limits_concurrency_to_semaphore_cap():
    """Bug #4 fix: RADIO_SEARCH_SEM (cap 4) harus benar-benar membatasi
    berapa banyak resolve() yang jalan bersamaan, walau kandidatnya lebih
    banyak dari itu."""
    state = AppState()
    for i in range(6):
        state.radio_queue.append(
            TrackInfo(video_id=str(i), title=f"T{i}", artist="A", duration=100)
        )
    selector = MockArtistSelector()
    prefetcher = RadioPrefetcher(state, selector)
    prefetcher.PREFETCH_LOOKAHEAD = 6  # pastikan >4 kandidat sekaligus masuk _do_prefetch

    current = 0
    peak = 0

    async def fake_resolve(track):
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.02)
        current -= 1

    controller = MagicMock()
    controller.track_loader.resolver.resolve = AsyncMock(side_effect=fake_resolve)

    await prefetcher._do_prefetch(controller)

    assert peak <= 4
    assert controller.track_loader.resolver.resolve.call_count == 6


@pytest.mark.asyncio
async def test_do_prefetch_resolves_all_candidates_regardless_of_semaphore():
    """Regresi: semaphore membatasi paralelisme, bukan hasil akhir --
    semua kandidat tetap ter-resolve seperti sebelum fix."""
    state = AppState()
    for i in range(5):
        state.radio_queue.append(
            TrackInfo(video_id=str(i), title=f"T{i}", artist="A", duration=100)
        )
    selector = MockArtistSelector()
    prefetcher = RadioPrefetcher(state, selector)
    prefetcher.PREFETCH_LOOKAHEAD = 5

    controller = MagicMock()
    controller.track_loader.resolver.resolve = AsyncMock()

    await prefetcher._do_prefetch(controller)

    assert controller.track_loader.resolver.resolve.call_count == 5
