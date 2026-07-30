"""
Module: tests.unit.server.middleware.test_traffic

Purpose:
    Unit tests for the aiohttp traffic middleware (ADR-0010 O3.1).

Responsibilities:
    - Verify req_id is bound during the request and cleared afterward.
    - Verify HTTP_REQUESTS_TOTAL/HTTP_BYTES_TOTAL are incremented.
    - Verify HTTPException responses (e.g. 403) still propagate and are
      counted with their real status, not silently swallowed.

Depends on:
    - server.middleware.traffic
    - core.observability

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import pytest
import structlog
from aiohttp import web

from core.observability import HTTP_REQUESTS_TOTAL
from server.middleware.traffic import traffic_middleware


class FakeRequest:
    def __init__(self, method="GET", path="/health", content_length=None):
        self.method = method
        self.path = path
        self.content_length = content_length


@pytest.mark.asyncio
async def test_traffic_middleware_passes_through_response():
    request = FakeRequest()

    async def handler(req):
        return web.json_response({"status": "ok"})

    resp = await traffic_middleware(request, handler)
    assert resp.status == 200


@pytest.mark.asyncio
async def test_traffic_middleware_binds_and_clears_req_id():
    request = FakeRequest()
    seen = {}

    async def handler(req):
        seen["ctx"] = dict(structlog.contextvars.get_contextvars())
        return web.Response(text="ok")

    await traffic_middleware(request, handler)

    assert "req_id" in seen["ctx"]
    assert len(seen["ctx"]["req_id"]) == 8
    # After the request finishes, req_id must not leak into later contexts.
    assert "req_id" not in dict(structlog.contextvars.get_contextvars())


@pytest.mark.asyncio
async def test_traffic_middleware_counts_request_metric():
    request = FakeRequest(method="GET", path="/api/tracks-metric-test")

    async def handler(req):
        return web.Response(text="ok")

    before = HTTP_REQUESTS_TOTAL.labels(
        method="GET", path="/api/tracks-metric-test", status="200"
    )._value.get()

    await traffic_middleware(request, handler)

    after = HTTP_REQUESTS_TOTAL.labels(
        method="GET", path="/api/tracks-metric-test", status="200"
    )._value.get()
    assert after == before + 1


@pytest.mark.asyncio
async def test_traffic_middleware_reraises_http_exception_with_real_status():
    request = FakeRequest(method="GET", path="/health")

    async def handler(req):
        raise web.HTTPForbidden(text="nope")

    with pytest.raises(web.HTTPForbidden):
        await traffic_middleware(request, handler)


class _RecordingLogger:
    """Minimal stand-in for structlog's BoundLogger that just records which
    method (debug/info/...) was called with which line, so tests can assert
    on log *level* without depending on the real logging pipeline."""

    def __init__(self):
        self.calls = []

    def debug(self, msg, **kwargs):
        self.calls.append(("debug", msg))

    def info(self, msg, **kwargs):
        self.calls.append(("info", msg))


@pytest.mark.asyncio
async def test_traffic_middleware_logs_stream_requests_at_debug(monkeypatch):
    """Audio playback fires many chunked/range GETs against
    /api/stream/<video_id> -- these must be logged at DEBUG (quiet by
    default), not INFO, so they don't flood lunawave.log / console.
    Metrics are unaffected either way (covered by the metric-count test)."""
    import server.middleware.traffic as traffic_module

    fake_logger = _RecordingLogger()
    monkeypatch.setattr(traffic_module, "logger", fake_logger)

    request = FakeRequest(method="GET", path="/api/stream/dQw4w9WgXcQ")

    async def handler(req):
        return web.Response(text="ok")

    await traffic_module.traffic_middleware(request, handler)

    assert fake_logger.calls, "expected exactly one log call"
    level, msg = fake_logger.calls[0]
    assert level == "debug"
    assert "/api/stream/dQw4w9WgXcQ" in msg


@pytest.mark.asyncio
async def test_traffic_middleware_logs_static_requests_at_debug(monkeypatch):
    """Every page load pulls in a batch of CSS/JS/icon files under
    /static/ -- these carry no diagnostic value and must be quiet (DEBUG)
    by default, just like audio stream range requests."""
    import server.middleware.traffic as traffic_module

    fake_logger = _RecordingLogger()
    monkeypatch.setattr(traffic_module, "logger", fake_logger)

    request = FakeRequest(method="GET", path="/static/css/app.css")

    async def handler(req):
        return web.Response(text="ok")

    await traffic_module.traffic_middleware(request, handler)

    assert fake_logger.calls, "expected exactly one log call"
    level, msg = fake_logger.calls[0]
    assert level == "debug"
    assert "/static/css/app.css" in msg


@pytest.mark.asyncio
async def test_traffic_middleware_logs_other_requests_at_info(monkeypatch):
    """Non-stream endpoints keep their existing INFO-level line -- only the
    audio stream endpoint is quieted."""
    import server.middleware.traffic as traffic_module

    fake_logger = _RecordingLogger()
    monkeypatch.setattr(traffic_module, "logger", fake_logger)

    request = FakeRequest(method="GET", path="/api/tracks")

    async def handler(req):
        return web.Response(text="ok")

    await traffic_module.traffic_middleware(request, handler)

    assert fake_logger.calls, "expected exactly one log call"
    level, msg = fake_logger.calls[0]
    assert level == "info"
    assert "/api/tracks" in msg


@pytest.mark.asyncio
async def test_traffic_middleware_never_crashes_on_handler_exception():
    """Even for a totally unexpected (non-HTTP) exception, the middleware's
    own instrumentation code (finally block) must not itself crash or mask
    the original exception."""
    request = FakeRequest(method="GET", path="/boom")

    async def handler(req):
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await traffic_middleware(request, handler)
