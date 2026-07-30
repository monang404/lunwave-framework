"""
Module: lunawave_framework.core.logging.log_context

Purpose:
    Thin wrappers over structlog.contextvars for the three correlation
    fields defined in docs/rfc/logging_standard/LOGGING_STANDARD.md §5.2:
    session_id (one WebSocket connection), request_id (one Command Bus
    execution), correlation_id (one flow that crosses separately
    scheduled asyncio tasks, e.g. a radio cycle triggering a prefetch, or
    a download whose progress hook runs in a separate task).

Responsibilities:
    - bind_session(session_id) / bind_request(request_id) /
      bind_correlation(correlation_id): bind one field each into
      structlog's contextvars, following the exact pattern already
      proven correct in server/middleware/traffic.py (req_id).
    - Provide matching unbind_*() helpers for callers that need to scope
      the binding explicitly (e.g. tests, or a caller that wants to clear
      before the enclosing async context ends).
    - Nothing else. These are NOT a replacement for
      structlog.contextvars.bind_contextvars/unbind_contextvars -- they
      are named, single-purpose call sites so every binding site in the
      codebase uses the same field name and the same fail-safe pattern.

Depends on:
    None (structlog is a third-party dependency, already used elsewhere)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Per-asyncio-task contextvars -- safe across concurrent WS
    connections/commands/radio cycles/downloads as long as each task
    binds its own values and callers propagate the SAME id to child
    tasks explicitly (anti-pattern §12.9: never mint a new correlation
    id mid-flow -- pass the existing one down to
    asyncio.create_task(...) callables instead).
"""

import structlog

from .log_categories import LC_LIFECYCLE

_SESSION_KEY = "session_id"
_REQUEST_KEY = "request_id"
_CORRELATION_KEY = "correlation_id"

# PATCH-2026-07-28 (temuan #9, P4-T1b): logger lokal untuk log debug-level
# saat bind/unbind contextvar gagal. AMAN dari circular-import: hanya
# bergantung pada `structlog` (third-party, sudah dipakai di atas) dan
# lunawave_framework.core.logging.log_categories (modul vokabuler murni tanpa import balik ke sini) --
# TIDAK mengimpor lunawave_framework.core.logging.log_config (tempat structlog.configure() dipanggil),
# jadi tidak ada siklus dengan infrastruktur setup logging itu sendiri.
logger = structlog.get_logger(component="core.log_context")


def bind_session(session_id: str) -> None:
    """Bind session_id for the lifetime of a WebSocket connection.
    Call once from ConnectionManager.connect(). Fail-safe: never raises,
    mirroring the pattern in server/middleware/traffic.py."""
    # Klasifikasi: best-effort cleanup. Gagal bind session_id tidak boleh
    # menggagalkan koneksi WS yang baru dibuka -- hanya berarti baris log
    # berikutnya kehilangan satu field korelasi. Debug-level saja (bukan
    # warning) supaya tidak berisik di log produksi normal (INFO+).
    try:
        structlog.contextvars.bind_contextvars(**{_SESSION_KEY: session_id})
    except Exception as e:
        logger.debug("session_bind_failed", category=LC_LIFECYCLE, error=str(e))


def unbind_session() -> None:
    """Unbind session_id. Call from ConnectionManager.disconnect()."""
    # Klasifikasi: best-effort cleanup. Gagal unbind di disconnect() tidak
    # boleh menghalangi urutan cleanup lain -- sisa contextvar (kalau ada)
    # akan hilang sendiri saat task/scope berakhir.
    try:
        structlog.contextvars.unbind_contextvars(_SESSION_KEY)
    except Exception as e:
        logger.debug("session_unbind_failed", category=LC_LIFECYCLE, error=str(e))


def bind_request(request_id: str) -> None:
    """Bind request_id for one Command Bus execution. Call at the entry
    point of CommandBus.execute(). Stacks on top of session_id (and any
    correlation_id) already bound -- contextvars do not overwrite each
    other, per §5.2."""
    # Klasifikasi: best-effort cleanup. Sama seperti bind_session -- gagal
    # bind request_id tidak boleh menggagalkan eksekusi command itu
    # sendiri, hanya kehilangan satu field korelasi di log.
    try:
        structlog.contextvars.bind_contextvars(**{_REQUEST_KEY: request_id})
    except Exception as e:
        logger.debug("request_bind_failed", category=LC_LIFECYCLE, error=str(e))


def unbind_request() -> None:
    """Unbind request_id. Call when a single command execution ends."""
    # Klasifikasi: best-effort cleanup. Gagal unbind di akhir eksekusi
    # command tidak boleh menggagalkan penyelesaian command tersebut.
    try:
        structlog.contextvars.unbind_contextvars(_REQUEST_KEY)
    except Exception as e:
        logger.debug("request_unbind_failed", category=LC_LIFECYCLE, error=str(e))


def bind_correlation(correlation_id: str) -> None:
    """Bind correlation_id for a flow that crosses separately scheduled
    asyncio tasks (a radio cycle and the prefetch task it triggers; a
    download and its progress hook running in a separate executor task).
    Call at the entry point of that flow, and propagate the SAME value
    explicitly to every child task -- never mint a new one mid-flow
    (anti-pattern §12.9)."""
    # Klasifikasi: best-effort cleanup. Gagal bind correlation_id tidak
    # boleh menggagalkan flow (radio cycle, download, dsb) itu sendiri --
    # hanya kehilangan kemampuan menghubungkan log lintas-task untuk flow
    # ini secara spesifik.
    try:
        structlog.contextvars.bind_contextvars(**{_CORRELATION_KEY: correlation_id})
    except Exception as e:
        logger.debug("correlation_bind_failed", category=LC_LIFECYCLE, error=str(e))


def unbind_correlation() -> None:
    """Unbind correlation_id. Call when the flow it identifies ends."""
    # Klasifikasi: best-effort cleanup. Gagal unbind di akhir flow tidak
    # boleh menggagalkan penyelesaian flow tersebut.
    try:
        structlog.contextvars.unbind_contextvars(_CORRELATION_KEY)
    except Exception as e:
        logger.debug("correlation_unbind_failed", category=LC_LIFECYCLE, error=str(e))
