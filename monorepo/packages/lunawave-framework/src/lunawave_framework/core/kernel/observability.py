"""
Module: lunawave_framework.core.kernel.observability

Purpose:
    Expose Prometheus metric singletons and an OpenTelemetry tracer for
    application-wide instrumentation.

Responsibilities:
    - Define Counter/Histogram/Gauge for commands, events, and WebSockets.
    - Initialize a TracerProvider and return the application tracer.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Thread-safe (prometheus_client handles concurrent metric updates).
"""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# --- Prometheus Metrics ---

# 1. Total Command Executions (Counter)
COMMAND_COUNT = Counter(
    "ytplayer_commands_total", "Total number of commands executed", ["command_name", "status"]
)

# 2. Command Latency (Histogram)
COMMAND_LATENCY = Histogram(
    "ytplayer_command_duration_seconds",
    "Duration of command execution in seconds",
    ["command_name"],
)

# 3. Domain Events Published (Counter)
EVENT_COUNT = Counter("lunawave_events_total", "Total events published", ["event_type"])

# 4. Active WebSockets (Gauge)
ACTIVE_WEBSOCKETS = Gauge(
    "ytplayer_active_websockets",
    "Number of currently active WebSocket connections",
)

# 5. Resolve Latency (Histogram)
RESOLVE_LATENCY = Histogram(
    "lunawave_stream_resolve_duration_seconds",
    "Duration of yt-dlp stream URL resolution (Rule 3 cache miss only)",
)

# --- Observability Baseline (ADR-0010) ---

# 6. Total HTTP Requests (Counter)
HTTP_REQUESTS_TOTAL = Counter(
    "lunawave_http_requests_total",
    "Total number of HTTP requests handled",
    ["method", "path", "status"],
)

# 7. Total HTTP Bytes Transferred (Counter)
HTTP_BYTES_TOTAL = Counter(
    "lunawave_http_bytes_total",
    "Total bytes transferred over HTTP",
    ["direction"],
)

# 8. Total WebSocket Messages (Counter)
WS_MESSAGES_TOTAL = Counter(
    "lunawave_ws_messages_total",
    "Total number of WebSocket messages",
    ["direction"],
)

# 9. Process RSS Memory in MB (Gauge)
PROCESS_RSS_MB = Gauge(
    "lunawave_process_rss_mb",
    "Resident set size (RAM) of the current process in MB, cross-platform "
    "(None/unavailable reads are simply skipped, gauge keeps last value)",
)

# 10. Active User Session Duration (Histogram)
ACTIVE_USER_SESSION_SECONDS = Histogram(
    "lunawave_active_user_session_seconds",
    "Duration of an active WebSocket user session, from connect to disconnect",
)


def get_metrics_content():
    """Returns the Prometheus metrics in text format."""
    return generate_latest(), CONTENT_TYPE_LATEST


def get_counter_value(metric, **label_kwargs) -> float:
    """
    Reads the cumulative value of a Counter or Histogram (sum) matching the given labels.
    If no labels are provided, it sums across all series for that metric.
    Fail-safe: returns 0.0 if there are no samples or on error.
    """
    try:
        metrics = list(metric.collect())
        if not metrics:
            return 0.0

        total = 0.0
        for m in metrics:
            for sample in m.samples:
                # Target the cumulative value samples
                if not (
                    sample.name.endswith("_total")
                    or sample.name.endswith("_sum")
                    or sample.name == m.name
                ):
                    continue

                # Match labels
                match = True
                for k, v in label_kwargs.items():
                    if sample.labels.get(k) != str(v):
                        match = False
                        break

                if match:
                    total += sample.value
        return total
    except Exception:
        return 0.0
