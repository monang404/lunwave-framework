"""
Module: lunawave_framework.core.logging.log_config

Purpose:
    Configure structlog and stdlib logging with an async queue handler,
    rotating file output, and per-handler rendering (plain file, optional
    auto-colored console).

Responsibilities:
    - Wire QueueHandler + QueueListener to decouple log I/O from hot paths.
    - Set up RotatingFileHandler (1 MB, 2 backups) and a console handler,
      each with its own renderer (file always plain ASCII, console colored
      only when the terminal supports it -- ADR-0010 decision OD-1).
    - Merge structlog.contextvars (req_id) into every log line so a single
      request/WS session can be grep-ed end to end.
    - Provide log_session_start()/log_session_end() banner lines.

Depends on:
    - lunawave_framework.core._env (resolves the log file path -- see that
      module's docstring for why this replaced a direct app-config import
      in Phase 2 of the framework extraction)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread only for setup_logging() (called once during startup).
    log_session_start()/log_session_end() are best-effort and fail-safe.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

import structlog

from lunawave_framework.core._env import resolve_log_path

# Handler references kept at module level so log_session_start/end can
# write banner lines directly, bypassing the processor chain.
_file_handler: RotatingFileHandler | None = None
_console_handler: logging.StreamHandler | None = None


def file_renderer(logger, name, event_dict):
    """Renderer plain ASCII, tanpa ANSI escape apa pun -- dipakai untuk
    lunawave.log. Ini adalah renderer asli sebelum ADR-0010 (namanya
    berubah dari simple_renderer, perilaku tidak berubah)."""
    ts = event_dict.pop("timestamp", "")
    level = event_dict.pop("level", "").upper()
    event = event_dict.pop("event", "")

    extras = []
    for k, v in event_dict.items():
        if k not in ("logger", "exc_info"):
            extras.append(f"{k}={v}")

    extra_str = f" ({', '.join(extras)})" if extras else ""
    return f"[{ts}] {level}: {event}{extra_str}"


# Backward-compat alias -- nama lama dipakai sebelum split file/console.
simple_renderer = file_renderer


_LEVEL_COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[41m",  # red background
}
_RESET = "\033[0m"


def _console_color_enabled() -> bool:
    """Auto-detect murni: sys.stdout.isatty() + TERM bukan dumb/kosong.
    TIDAK ADA env var atau flag manual (ADR-0010 keputusan OD-1). Default
    aman (tanpa warna) kalau ragu atau deteksi gagal."""
    try:
        if not sys.stdout.isatty():
            return False
        term = os.environ.get("TERM", "")
        if term in ("", "dumb"):
            return False
        return True
    except Exception:
        return False


def console_renderer(logger, name, event_dict):
    """Sama seperti file_renderer, tapi menambah warna ANSI kalau console
    interaktif mendukungnya. Hasil fungsi ini hanya dipakai untuk console
    handler -- TIDAK PERNAH ditulis ke lunawave.log."""
    level = event_dict.get("level", "").upper()
    line = file_renderer(logger, name, event_dict)
    if _console_color_enabled():
        color = _LEVEL_COLORS.get(level, "")
        if color:
            return f"{color}{line}{_RESET}"
    return line


def setup_logging():
    global _file_handler, _console_handler
    import queue
    from logging.handlers import QueueHandler, QueueListener

    class _StructlogQueueHandler(QueueHandler):
        """QueueHandler biasa memanggil record.getMessage() di prepare()
        dan menimpa record.msg jadi string -- ini merusak event_dict yang
        dibutuhkan ProcessorFormatter di sisi QueueListener (interaksi
        dikenal antara structlog ProcessorFormatter dan QueueHandler).
        Karena queue di sini cuma memindah kerja ke thread lain dalam
        proses yang sama (bukan lintas proses), aman melewati stringify
        itu -- record tetap objek yang sama, bukan disalin lintas proses."""

        def prepare(self, record):
            return record

    log_path = resolve_log_path("app.log")
    _file_handler = RotatingFileHandler(
        log_path, maxBytes=1 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    _console_handler = logging.StreamHandler(sys.stdout)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
    ]

    _file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                file_renderer,
            ],
            foreign_pre_chain=shared_processors,
        )
    )
    _console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                console_renderer,
            ],
            foreign_pre_chain=shared_processors,
        )
    )

    log_queue = queue.Queue(-1)
    queue_handler = _StructlogQueueHandler(log_queue)
    listener = QueueListener(log_queue, _file_handler, _console_handler)
    listener.start()

    logging.basicConfig(format="%(message)s", level=logging.INFO, handlers=[queue_handler])

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _emit_banner_line(line: str) -> None:
    """Tulis satu baris banner sesi langsung ke handler, bypass processor
    chain (banner bukan log event biasa). Selalu plain text, fail-safe --
    tidak boleh melempar exception ke pemanggil kalau logging belum
    di-setup atau stream gagal ditulis."""
    for handler in (_file_handler, _console_handler):
        if handler is None:
            continue
        stream = getattr(handler, "stream", None)
        if stream is None:
            continue
        try:
            stream.write(line + "\n")
            stream.flush()
        except Exception:
            pass


def log_session_start(pid: int, host: str = "", port: int | str = "") -> None:
    """Tulis baris "==== SESSION START ... ====" ke file dan console."""
    ts = datetime.now().isoformat(timespec="seconds")
    _emit_banner_line(f"==== SESSION START pid={pid} host={host} port={port} {ts} ====")


def log_session_end(pid: int) -> None:
    """Tulis baris "==== SESSION END ... ====" ke file dan console."""
    ts = datetime.now().isoformat(timespec="seconds")
    _emit_banner_line(f"==== SESSION END pid={pid} {ts} ====")
