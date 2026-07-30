"""tests/unit/core/test_log_context.py — mirrors core/log_context.py

Purpose:
    Verify the three bind_*/unbind_* helper pairs are symmetric (bind
    then unbind leaves contextvars clean), that they stack rather than
    overwrite each other (§5.2), and that two independently-created
    asyncio tasks do NOT leak each other's bound values unless the
    value is explicitly propagated (anti-pattern §12.9).

Subscribes to:
    None

Publishes:
    None
"""

import asyncio

import structlog

import lunawave_framework.core.logging.log_context as log_context


def _current_contextvars() -> dict:
    return structlog.contextvars.get_contextvars()


def setup_function():
    # Ensure a clean contextvars slate before each test -- these tests
    # run in the main thread/task, so clear_contextvars() is safe here.
    structlog.contextvars.clear_contextvars()


def teardown_function():
    structlog.contextvars.clear_contextvars()


def test_bind_unbind_session_is_symmetric():
    log_context.bind_session("sess-abc123")
    assert _current_contextvars().get("session_id") == "sess-abc123"
    log_context.unbind_session()
    assert "session_id" not in _current_contextvars()


def test_bind_unbind_request_is_symmetric():
    log_context.bind_request("req-xyz789")
    assert _current_contextvars().get("request_id") == "req-xyz789"
    log_context.unbind_request()
    assert "request_id" not in _current_contextvars()


def test_bind_unbind_correlation_is_symmetric():
    log_context.bind_correlation("corr-000111")
    assert _current_contextvars().get("correlation_id") == "corr-000111"
    log_context.unbind_correlation()
    assert "correlation_id" not in _current_contextvars()


def test_session_and_request_stack_without_overwriting():
    log_context.bind_session("sess-1")
    log_context.bind_request("req-1")
    ctx = _current_contextvars()
    assert ctx.get("session_id") == "sess-1"
    assert ctx.get("request_id") == "req-1"
    log_context.unbind_request()
    log_context.unbind_session()


def test_two_independent_asyncio_tasks_do_not_leak_context():
    """Two tasks that each bind their own session_id must not see each
    other's value -- contextvars are per-task by default in asyncio."""

    results = {}

    async def _task(name: str, session_id: str, delay: float):
        log_context.bind_session(session_id)
        await asyncio.sleep(delay)
        results[name] = _current_contextvars().get("session_id")
        log_context.unbind_session()

    async def _run():
        await asyncio.gather(
            _task("a", "sess-A", 0.01),
            _task("b", "sess-B", 0.02),
        )

    asyncio.run(_run())

    assert results["a"] == "sess-A"
    assert results["b"] == "sess-B"


def test_correlation_id_propagated_explicitly_to_child_task_is_shared():
    """When a parent task explicitly passes its correlation_id down to a
    child task (the correct pattern -- anti-pattern §12.9 forbids minting
    a new one), the child must see the SAME value, not a fresh one."""

    child_seen = {}

    async def _child(correlation_id: str):
        # Child task explicitly receives and re-binds the SAME id --
        # this is the required pattern for radio cycle -> prefetcher,
        # or download -> progress hook.
        log_context.bind_correlation(correlation_id)
        child_seen["correlation_id"] = _current_contextvars().get("correlation_id")
        log_context.unbind_correlation()

    async def _parent():
        log_context.bind_correlation("corr-parent-1")
        parent_correlation_id = _current_contextvars().get("correlation_id")
        await _child(parent_correlation_id)
        log_context.unbind_correlation()

    asyncio.run(_parent())

    assert child_seen["correlation_id"] == "corr-parent-1"


# ---------------------------------------------------------------------------
# P4-T1b (temuan #9): setiap except/pass di log_context.py diklasifikasikan
# "best-effort cleanup" dan diberi logging debug-level. Test di bawah ini
# memicu tiap except-block via monkeypatch untuk memastikan (a) fungsi tetap
# fail-safe (tidak pernah melempar walau structlog.contextvars gagal), dan
# (b) logger.debug dipanggil sekali dengan event yang sesuai -- perubahan
# murni observability, bukan perubahan control-flow.
# ---------------------------------------------------------------------------


class _RecordingLogger:
    """Stub logger minimal untuk merekam pemanggilan .debug() tanpa
    bergantung pada konfigurasi structlog global."""

    def __init__(self):
        self.debug_calls: list[tuple[str, dict]] = []

    def debug(self, event, **kwargs):
        self.debug_calls.append((event, kwargs))


def _boom(*_args, **_kwargs):
    raise RuntimeError("contextvars boom")


def test_bind_session_failure_is_fail_safe_and_logged(monkeypatch):
    fake_logger = _RecordingLogger()
    monkeypatch.setattr(log_context, "logger", fake_logger)
    monkeypatch.setattr(structlog.contextvars, "bind_contextvars", _boom)

    log_context.bind_session("sess-x")  # must not raise

    assert [event for event, _ in fake_logger.debug_calls] == ["session_bind_failed"]


def test_unbind_session_failure_is_fail_safe_and_logged(monkeypatch):
    fake_logger = _RecordingLogger()
    monkeypatch.setattr(log_context, "logger", fake_logger)
    monkeypatch.setattr(structlog.contextvars, "unbind_contextvars", _boom)

    log_context.unbind_session()  # must not raise

    assert [event for event, _ in fake_logger.debug_calls] == ["session_unbind_failed"]


def test_bind_request_failure_is_fail_safe_and_logged(monkeypatch):
    fake_logger = _RecordingLogger()
    monkeypatch.setattr(log_context, "logger", fake_logger)
    monkeypatch.setattr(structlog.contextvars, "bind_contextvars", _boom)

    log_context.bind_request("req-x")  # must not raise

    assert [event for event, _ in fake_logger.debug_calls] == ["request_bind_failed"]


def test_unbind_request_failure_is_fail_safe_and_logged(monkeypatch):
    fake_logger = _RecordingLogger()
    monkeypatch.setattr(log_context, "logger", fake_logger)
    monkeypatch.setattr(structlog.contextvars, "unbind_contextvars", _boom)

    log_context.unbind_request()  # must not raise

    assert [event for event, _ in fake_logger.debug_calls] == ["request_unbind_failed"]


def test_bind_correlation_failure_is_fail_safe_and_logged(monkeypatch):
    fake_logger = _RecordingLogger()
    monkeypatch.setattr(log_context, "logger", fake_logger)
    monkeypatch.setattr(structlog.contextvars, "bind_contextvars", _boom)

    log_context.bind_correlation("corr-x")  # must not raise

    assert [event for event, _ in fake_logger.debug_calls] == ["correlation_bind_failed"]


def test_unbind_correlation_failure_is_fail_safe_and_logged(monkeypatch):
    fake_logger = _RecordingLogger()
    monkeypatch.setattr(log_context, "logger", fake_logger)
    monkeypatch.setattr(structlog.contextvars, "unbind_contextvars", _boom)

    log_context.unbind_correlation()  # must not raise

    assert [event for event, _ in fake_logger.debug_calls] == ["correlation_unbind_failed"]
