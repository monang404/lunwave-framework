"""
Module: bootstrap.maintenance

Purpose:
    Stage 3 of application startup: schedule the periodic DB maintenance
    loop and the MPV connection watchdog as background tasks. Extracted
    from main.py's `main()` (T2.4) without changing call order. Also
    schedules the ADR-0010 periodic `[STATUS]` summary log.

Inputs:
    Populated `bootstrap.services.context` (must run after
    `init_core_services()`).

Outputs:
    Appends `db_maintenance`, `mpv_watchdog`, and `status_log` tasks to
    `context.tasks`.

Side Effects:
    Deletes stale tracks / expired sessions from the DB on a timer, flips
    player state to ERROR if MPV stays disconnected, writes one `[STATUS]`
    log line and refreshes PROCESS_RSS_MB every 15 minutes.

CLI:
    None (imported by main.py).

Responsibilities:
    - Run periodic upkeep as background asyncio tasks.

Depends on:
    - bootstrap.services
    - core.task_utils
    - core.state
    - core.server_clock
    - core.mem_stats
    - core.observability

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import structlog

from bootstrap.services import context
from core.log_categories import LC_AUTH, LC_EXTERNAL, LC_LIFECYCLE, LC_PERSISTENCE
from core.state import PlayerStatus
from core.task_utils import safe_create_task

logger = structlog.get_logger(component="system.maintenance")


# DB Maintenance: eviction track stale + cleanup session expired.
async def db_maintenance():
    ctx = context
    # Jalankan sekali di awal, baru masuk loop periodik
    try:
        deleted = await ctx.repos.tracks.evict_stale_tracks()
        if deleted:
            logger.info(
                "db_maintenance_stale_tracks_evicted",
                category=LC_PERSISTENCE,
                deleted_count=deleted,
                phase="initial",
            )
    except Exception as e:
        logger.warning(
            "db_maintenance_evict_stale_tracks_failed",
            category=LC_PERSISTENCE,
            phase="initial",
            error_type=type(e).__name__,
            error=str(e),
        )
    try:
        await ctx.repos.sessions.cleanup_sessions()
    except Exception as e:
        logger.warning(
            "db_maintenance_cleanup_sessions_failed",
            category=LC_AUTH,
            phase="initial",
            error_type=type(e).__name__,
            error=str(e),
        )

    while True:
        await asyncio.sleep(6 * 3600)  # tiap 6 jam
        try:
            deleted = await ctx.repos.tracks.evict_stale_tracks()
            if deleted:
                logger.info(
                    "db_maintenance_stale_tracks_evicted",
                    category=LC_PERSISTENCE,
                    deleted_count=deleted,
                    phase="periodic",
                )
        except Exception as e:
            logger.warning(
                "db_maintenance_evict_stale_tracks_failed",
                category=LC_PERSISTENCE,
                phase="periodic",
                error_type=type(e).__name__,
                error=str(e),
            )
        try:
            await ctx.repos.sessions.cleanup_sessions()
        except Exception as e:
            logger.warning(
                "db_maintenance_cleanup_sessions_failed",
                category=LC_AUTH,
                phase="periodic",
                error_type=type(e).__name__,
                error=str(e),
            )


def schedule_db_maintenance():
    """Schedule the DB maintenance loop as a background task."""
    context.lifecycle.schedule_task(db_maintenance(), name="db_maintenance")


# MPV watchdog: no longer polls/reconnects itself. MpvObserver now owns
# reconnect (immediate, bounded retries) so there is a single reconnect
# path instead of two racing ones. This watchdog only handles the case
# where mpv never comes back at all (observer gave up after its own
# retries): it surfaces that as a visible error state instead of silently
# leaving playback stuck, without spawning yet another mpv process or
# reloading/seeking the track itself.
async def mpv_watchdog():
    ctx = context
    while True:
        await asyncio.sleep(10)
        if (
            getattr(ctx.mpv, "is_available", True)
            and not getattr(ctx.mpv, "is_connected", False)
            and ctx.state.status not in (PlayerStatus.ERROR, PlayerStatus.IDLE)
        ):
            logger.error("mpv_watchdog_still_disconnected", category=LC_EXTERNAL)
            ctx.state.status = PlayerStatus.ERROR
            ctx.state.error_msg = "Koneksi ke MPV terputus dan gagal reconnect."


def start_mpv_watchdog():
    """Schedule the MPV connection watchdog as a background task."""
    context.lifecycle.schedule_task(mpv_watchdog(), name="mpv_watchdog")


# ADR-0010: ringkasan periodik ke log (uptime, jumlah koneksi aktif, total
# request, RAM proses) -- pola sama dengan db_maintenance/mpv_watchdog di
# atas (while True + asyncio.sleep + safe_create_task), sehingga otomatis
# ikut ter-cancel bersih oleh loop shutdown main.py yang sudah ada
# (for t in ctx.tasks: t.cancel(); await asyncio.gather(...)).
STATUS_LOG_INTERVAL_SECONDS = 15 * 60  # 15 menit


def _sum_counter_total(counter) -> int | None:
    """Jumlahkan semua sample '_total' dari sebuah Counter berlabel
    Prometheus (mis. HTTP_REQUESTS_TOTAL) lintas semua kombinasi label.
    Fail-safe: None kalau gagal, tidak pernah raise."""
    try:
        total = 0.0
        for metric in counter.collect():
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    total += sample.value
        return int(total)
    except Exception:
        return None


async def status_log_task():
    """Loop tak-terbatas: tiap STATUS_LOG_INTERVAL_SECONDS, tulis satu
    baris ringkasan '[STATUS] uptime=... aktif=... req=... ram=...' ke log
    dan refresh gauge PROCESS_RSS_MB. Setiap sumber data dibungkus
    try/except sendiri -- kegagalan satu sumber (mis. gagal baca RAM di
    platform tak didukung) tidak boleh menggagalkan baris log lainnya
    ataupun membuat loop berhenti/crash.
    """
    from core.mem_stats import get_rss_mb
    from core.observability import ACTIVE_WEBSOCKETS, HTTP_REQUESTS_TOTAL, PROCESS_RSS_MB
    from core.server_clock import server_clock

    while True:
        await asyncio.sleep(STATUS_LOG_INTERVAL_SECONDS)

        try:
            uptime_seconds = server_clock.uptime_seconds
        except Exception:
            uptime_seconds = None

        try:
            active = ACTIVE_WEBSOCKETS._value.get()
        except Exception:
            active = None

        total_requests = _sum_counter_total(HTTP_REQUESTS_TOTAL)

        try:
            ram_mb = get_rss_mb()
        except Exception:
            ram_mb = None
        if ram_mb is not None:
            try:
                PROCESS_RSS_MB.set(ram_mb)
            except Exception:
                pass

        try:
            logger.info(
                "status_snapshot",
                category=LC_LIFECYCLE,
                uptime_minutes=(int(uptime_seconds // 60) if uptime_seconds is not None else None),
                active_websockets=active,
                total_requests=total_requests,
                ram_mb=(round(ram_mb) if ram_mb is not None else None),
            )
        except Exception:
            # Instrumentasi tidak boleh pernah membuat loop status ini mati.
            pass


def schedule_status_log():
    """Schedule the periodic [STATUS] summary log as a background task."""
    context.lifecycle.schedule_task(status_log_task(), name="status_log")
