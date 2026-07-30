"""tests/unit/core/test_server_clock.py — mirrors core/server_clock.py
Purpose:
    Pastikan uptime_seconds naik monoton dan init() bisa mereset start time.

Subscribes to:
    None

Publishes:
    None
"""

import time

from lunawave_framework.core.kernel.server_clock import ServerClock


def test_uptime_seconds_increases_monotonically():
    clock = ServerClock()
    first = clock.uptime_seconds
    time.sleep(0.01)
    second = clock.uptime_seconds
    assert second > first


def test_uptime_seconds_starts_near_zero_on_construction():
    clock = ServerClock()
    assert clock.uptime_seconds >= 0
    assert clock.uptime_seconds < 1.0


def test_init_resets_start_time():
    clock = ServerClock()
    time.sleep(0.02)
    before_reset = clock.uptime_seconds
    clock.init()
    after_reset = clock.uptime_seconds
    assert after_reset < before_reset


def test_start_time_is_wall_clock_epoch_seconds():
    before = time.time()
    clock = ServerClock()
    after = time.time()
    assert before <= clock.start_time <= after
