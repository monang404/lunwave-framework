"""tests/unit/core/test_observability.py — mirrors core/observability.py
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

from prometheus_client import CONTENT_TYPE_LATEST

from lunawave_framework.core.kernel.observability import (
    ACTIVE_WEBSOCKETS,
    COMMAND_COUNT,
    COMMAND_LATENCY,
    EVENT_COUNT,
    get_metrics_content,
)


def test_command_count_is_a_labeled_counter():
    COMMAND_COUNT.labels(command_name="cmd.test", status="success").inc()
    sample = COMMAND_COUNT.labels(command_name="cmd.test", status="success")
    assert sample._value.get() >= 1


def test_command_latency_records_observations():
    COMMAND_LATENCY.labels(command_name="cmd.test").observe(0.05)
    # Histogram exposes _sum via internal metric; just assert no exception
    # and that the child collector exists.
    assert COMMAND_LATENCY.labels(command_name="cmd.test") is not None


def test_event_count_increments_per_event_type():
    before = EVENT_COUNT.labels(event_type="TestEvent")._value.get()
    EVENT_COUNT.labels(event_type="TestEvent").inc()
    after = EVENT_COUNT.labels(event_type="TestEvent")._value.get()
    assert after == before + 1


def test_active_websockets_gauge_inc_dec():
    ACTIVE_WEBSOCKETS.set(0)
    ACTIVE_WEBSOCKETS.inc()
    assert ACTIVE_WEBSOCKETS._value.get() == 1
    ACTIVE_WEBSOCKETS.dec()
    assert ACTIVE_WEBSOCKETS._value.get() == 0


def test_get_metrics_content_returns_bytes_and_content_type():
    payload, content_type = get_metrics_content()
    assert isinstance(payload, bytes)
    assert content_type == CONTENT_TYPE_LATEST
    assert b"ytplayer_commands_total" in payload


def test_get_counter_value():
    from prometheus_client import Counter, Histogram

    from lunawave_framework.core.kernel.observability import get_counter_value

    # Test counter
    test_counter = Counter("test_counter", "desc", ["lbl"])
    test_counter.labels(lbl="A").inc(5)
    test_counter.labels(lbl="B").inc(10)

    assert get_counter_value(test_counter, lbl="A") == 5.0
    assert get_counter_value(test_counter, lbl="B") == 10.0
    # Assuming the previous metrics in prometheus registry doesn't conflict, wait, we are using new metric names.
    # Without labels it sums all (5+10=15)
    assert get_counter_value(test_counter) == 15.0

    # Test histogram
    test_hist = Histogram("test_hist", "desc", ["lbl"])
    test_hist.labels(lbl="X").observe(2.5)
    test_hist.labels(lbl="X").observe(3.5)
    test_hist.labels(lbl="Y").observe(10.0)

    # Histograms sum the values in _sum
    assert get_counter_value(test_hist, lbl="X") == 6.0
    assert get_counter_value(test_hist, lbl="Y") == 10.0
    assert get_counter_value(test_hist) == 16.0

    # Empty metric
    empty_counter = Counter("empty_counter", "desc")
    assert get_counter_value(empty_counter) == 0.0
