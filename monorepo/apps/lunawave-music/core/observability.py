#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.observability import COMMAND_COUNT, get_counter_value, ...

Metric singletons are process-wide (Prometheus client registers them at
import time), so importing them here vs. importing them directly from the
framework module refers to the exact same objects -- no state duplication.
"""

from lunawave_framework.core.kernel.observability import (
    ACTIVE_USER_SESSION_SECONDS,
    ACTIVE_WEBSOCKETS,
    COMMAND_COUNT,
    COMMAND_LATENCY,
    EVENT_COUNT,
    HTTP_BYTES_TOTAL,
    HTTP_REQUESTS_TOTAL,
    PROCESS_RSS_MB,
    RESOLVE_LATENCY,
    WS_MESSAGES_TOTAL,
    get_counter_value,
    get_metrics_content,
)

__all__ = [
    "COMMAND_COUNT",
    "COMMAND_LATENCY",
    "EVENT_COUNT",
    "ACTIVE_WEBSOCKETS",
    "RESOLVE_LATENCY",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_BYTES_TOTAL",
    "WS_MESSAGES_TOTAL",
    "PROCESS_RSS_MB",
    "ACTIVE_USER_SESSION_SECONDS",
    "get_metrics_content",
    "get_counter_value",
]
