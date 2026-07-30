"""packages/lunawave-framework/tests/core/test_log_config.py — mirrors
lunawave_framework/core/logging/log_config.py (moved here from
apps/lunawave-music/tests/unit/core/test_log_config.py in Phase 2 of the
framework extraction; core/log_config.py in the app repo is now just a
backward-compat shim, see docs/extraction/ there).

Priority: Rendah (wiring). We cover the pure `simple_renderer` function
thoroughly, and treat `setup_logging()` as a smoke test with logging state
restored afterwards so it doesn't leak into other tests.

Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import logging
import logging.handlers
from unittest.mock import patch

import pytest

import lunawave_framework.core.logging.log_config as log_config


def test_simple_renderer_formats_basic_fields():
    result = log_config.simple_renderer(
        None, "info", {"timestamp": "12:00:00", "level": "info", "event": "hello"}
    )
    assert result == "[12:00:00] INFO: hello"


def test_simple_renderer_appends_extra_keys():
    result = log_config.simple_renderer(
        None,
        "info",
        {"timestamp": "12:00:00", "level": "warning", "event": "disk low", "free_mb": 12},
    )
    assert result == "[12:00:00] WARNING: disk low (free_mb=12)"


def test_simple_renderer_ignores_logger_and_exc_info_keys():
    result = log_config.simple_renderer(
        None,
        "info",
        {
            "timestamp": "00:00:01",
            "level": "error",
            "event": "boom",
            "logger": "some.logger",
            "exc_info": True,
        },
    )
    assert result == "[00:00:01] ERROR: boom"


def test_simple_renderer_handles_missing_optional_fields():
    result = log_config.simple_renderer(None, "info", {})
    assert result == "[] : "


def test_simple_renderer_is_alias_for_file_renderer():
    # Backward-compat: nama lama `simple_renderer` harus tetap ada dan
    # identik dengan `file_renderer` setelah split ADR-0010.
    assert log_config.simple_renderer is log_config.file_renderer


def test_file_renderer_matches_simple_renderer_behavior():
    result = log_config.file_renderer(
        None, "info", {"timestamp": "12:00:00", "level": "info", "event": "hello"}
    )
    assert result == "[12:00:00] INFO: hello"


def test_console_renderer_no_color_when_not_a_tty():
    with patch("sys.stdout.isatty", return_value=False):
        result = log_config.console_renderer(
            None, "info", {"timestamp": "12:00:00", "level": "error", "event": "boom"}
        )
    assert result == "[12:00:00] ERROR: boom"
    assert "\x1b[" not in result


def test_console_renderer_no_color_when_term_is_dumb():
    with (
        patch("sys.stdout.isatty", return_value=True),
        patch.dict("os.environ", {"TERM": "dumb"}),
    ):
        result = log_config.console_renderer(
            None, "info", {"timestamp": "12:00:00", "level": "error", "event": "boom"}
        )
    assert "\x1b[" not in result


def test_console_renderer_no_color_when_term_empty():
    with (
        patch("sys.stdout.isatty", return_value=True),
        patch.dict("os.environ", {"TERM": ""}),
    ):
        result = log_config.console_renderer(
            None, "info", {"timestamp": "12:00:00", "level": "error", "event": "boom"}
        )
    assert "\x1b[" not in result


def test_console_renderer_adds_color_when_tty_and_term_ok():
    with (
        patch("sys.stdout.isatty", return_value=True),
        patch.dict("os.environ", {"TERM": "xterm-256color"}),
    ):
        result = log_config.console_renderer(
            None, "info", {"timestamp": "12:00:00", "level": "error", "event": "boom"}
        )
    assert result == "\x1b[31m[12:00:00] ERROR: boom\x1b[0m"


def test_console_renderer_never_leaks_ansi_into_file_renderer_output():
    # file_renderer harus selalu polos walau dipanggil di lingkungan
    # dengan TTY + TERM valid.
    with (
        patch("sys.stdout.isatty", return_value=True),
        patch.dict("os.environ", {"TERM": "xterm-256color"}),
    ):
        file_result = log_config.file_renderer(
            None, "info", {"timestamp": "12:00:00", "level": "error", "event": "boom"}
        )
    assert "\x1b[" not in file_result


def test_console_color_enabled_fails_safe_on_exception():
    with patch("sys.stdout.isatty", side_effect=Exception("no tty attr")):
        assert log_config._console_color_enabled() is False


def test_emit_banner_line_is_fail_safe_when_handlers_not_setup():
    # Sebelum setup_logging() dipanggil, handler module-level None --
    # tidak boleh melempar exception.
    log_config._file_handler = None
    log_config._console_handler = None
    log_config._emit_banner_line("==== SESSION START test ====")


def test_emit_banner_line_writes_plain_text_to_handlers(tmp_path):
    import io

    fake_stream = io.StringIO()

    class _FakeHandler:
        stream = fake_stream

    log_config._file_handler = _FakeHandler()
    log_config._console_handler = None
    try:
        log_config._emit_banner_line("==== SESSION START pid=1 ====")
        assert fake_stream.getvalue() == "==== SESSION START pid=1 ====\n"
    finally:
        log_config._file_handler = None


def test_log_session_start_writes_banner_with_pid_host_port():
    import io

    fake_stream = io.StringIO()

    class _FakeHandler:
        stream = fake_stream

    log_config._file_handler = _FakeHandler()
    log_config._console_handler = None
    try:
        log_config.log_session_start(4242, host="0.0.0.0", port=8765)
        output = fake_stream.getvalue()
        assert "SESSION START" in output
        assert "pid=4242" in output
        assert "host=0.0.0.0" in output
        assert "port=8765" in output
    finally:
        log_config._file_handler = None


def test_log_session_end_writes_banner_with_pid():
    import io

    fake_stream = io.StringIO()

    class _FakeHandler:
        stream = fake_stream

    log_config._file_handler = _FakeHandler()
    log_config._console_handler = None
    try:
        log_config.log_session_end(4242)
        output = fake_stream.getvalue()
        assert "SESSION END" in output
        assert "pid=4242" in output
    finally:
        log_config._file_handler = None


@pytest.fixture
def clean_logging_state():
    """setup_logging() mutates the global logging module — snapshot and
    restore root handlers so this test doesn't leak into others."""
    import structlog

    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    # logging.basicConfig() is a no-op if the root logger already has
    # handlers (pytest's own log-capture handler, in this case), so we
    # clear them for the duration of the test to let setup_logging() take
    # effect the way it would on a fresh process.
    root.handlers = []
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)
    structlog.reset_defaults()


def test_setup_logging_smoke_creates_log_file(tmp_path, monkeypatch, clean_logging_state):
    # pytest's own log-capture plugin keeps a handler on the root logger for
    # the whole test call, which makes logging.basicConfig() (called inside
    # setup_logging()) a legitimate no-op per stdlib semantics — so we don't
    # assert on root.handlers here. What we *can* assert without fighting
    # the test runner's own logging setup is the concrete file-system effect:
    # setup_logging() must create <resolved log path> via RotatingFileHandler
    # -- resolve_log_path is monkeypatched below so we can assert on a
    # tmp_path file instead of touching the real app log.
    monkeypatch.setattr(log_config, "resolve_log_path", lambda default_filename="app.log": tmp_path / "lunawave.log")
    log_config.setup_logging()
    assert (tmp_path / "lunawave.log").exists()


def test_setup_logging_end_to_end_req_id_and_no_ansi_leak_in_file(
    monkeypatch, tmp_path, clean_logging_state
):
    """Smoke test end-to-end: req_id via contextvars sampai ke baris log,
    dan file lunawave.log tidak pernah mengandung byte escape ANSI --
    verifikasi wajib dari RFC observability_logging.md."""
    import time

    import structlog
    import structlog.contextvars as cv

    monkeypatch.setattr(log_config, "resolve_log_path", lambda default_filename="app.log": tmp_path / "lunawave.log")
    root = logging.getLogger()
    root.handlers = []
    log_config.setup_logging()

    cv.bind_contextvars(req_id="a91c")
    try:
        structlog.get_logger("test").info("hello world", foo="bar")
    finally:
        cv.unbind_contextvars("req_id")

    time.sleep(0.2)  # beri waktu QueueListener memproses

    content = (tmp_path / "lunawave.log").read_text(encoding="utf-8")
    assert "\x1b[" not in content
    assert "req_id=a91c" in content
    assert "hello world" in content


def test_setup_logging_wires_a_queue_handler_when_root_has_no_handlers(monkeypatch, tmp_path):
    """Same smoke test, but run in a truly clean logging.basicConfig()
    scenario (as it would run at real app startup) by bypassing pytest's
    log-capture handler for the duration of the call."""
    monkeypatch.setattr(log_config, "resolve_log_path", lambda default_filename="app.log": tmp_path / "lunawave.log")
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        root.handlers = []
        log_config.setup_logging()
        assert any(isinstance(h, logging.handlers.QueueHandler) for h in root.handlers)
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
