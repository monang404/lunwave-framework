"""
Module: tests.unit.engine.playback.test_circuit_breaker

Purpose:
    Unit test MURNI untuk engine.playback.circuit_breaker -- tanpa mock
    mpv/event bus/asyncio, karena PlaybackCircuitBreaker tidak punya
    dependency ke luar stdlib `enum`.

Responsibilities:
    - Verifikasi state awal CLOSED.
    - Verifikasi record_failure() di bawah threshold tetap CLOSED.
    - Verifikasi record_failure() ke-N (N=threshold) membuka breaker dan
      mengembalikan True hanya pada transisi itu.
    - Verifikasi record_failure() setelah OPEN tetap OPEN, return False.
    - Verifikasi record_success() mereset breaker ke CLOSED.
    - Verifikasi threshold custom.

Depends on:
    - engine.playback.circuit_breaker

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (sync, tidak ada asyncio sama sekali di test ini).
"""

from engine.playback.circuit_breaker import BreakerState, PlaybackCircuitBreaker


class TestPlaybackCircuitBreaker:
    def test_initial_state_is_closed_and_can_advance(self):
        breaker = PlaybackCircuitBreaker()
        assert breaker.state is BreakerState.CLOSED
        assert breaker.can_advance() is True

    def test_failures_below_threshold_stay_closed(self):
        breaker = PlaybackCircuitBreaker(threshold=3)
        assert breaker.record_failure() is False
        assert breaker.state is BreakerState.CLOSED
        assert breaker.record_failure() is False
        assert breaker.state is BreakerState.CLOSED
        assert breaker.can_advance() is True

    def test_nth_failure_opens_breaker_and_returns_true(self):
        breaker = PlaybackCircuitBreaker(threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        just_opened = breaker.record_failure()
        assert just_opened is True
        assert breaker.state is BreakerState.OPEN
        assert breaker.can_advance() is False

    def test_failure_after_open_stays_open_and_returns_false(self):
        breaker = PlaybackCircuitBreaker(threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        again = breaker.record_failure()
        assert again is False
        assert breaker.state is BreakerState.OPEN
        assert breaker.can_advance() is False

    def test_success_resets_open_breaker_to_closed(self):
        breaker = PlaybackCircuitBreaker(threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state is BreakerState.OPEN

        breaker.record_success()
        assert breaker.state is BreakerState.CLOSED
        assert breaker.can_advance() is True
        # Counter juga harus reset -- kegagalan berikutnya butuh threshold
        # penuh lagi sebelum OPEN.
        assert breaker.record_failure() is False
        assert breaker.state is BreakerState.CLOSED

    def test_custom_threshold_opens_after_one_failure(self):
        breaker = PlaybackCircuitBreaker(threshold=1)
        just_opened = breaker.record_failure()
        assert just_opened is True
        assert breaker.state is BreakerState.OPEN
        assert breaker.can_advance() is False
