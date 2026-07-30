"""
Module: bootstrap.startup_tasks

Purpose:
    Stage 2 of application startup: kick off the background tasks that
    must not block the web server from listening — connectivity polling,
    the initial MPV connect, and resuming the last-played track. Extracted
    from main.py's `main()` (T2.4) without changing call order.

Inputs:
    Populated `bootstrap.services.context` (must run after
    `init_core_services()`).

Outputs:
    Appends `connectivity_checker`, `mpv_initial_connect`, and
    `resume_last_track` tasks to `context.tasks`.

Side Effects:
    Network calls (connectivity check, possible yt-dlp resolve on resume),
    starts async background tasks.

CLI:
    None (imported by main.py).

Responsibilities:
    - Run non-blocking startup checks as background asyncio tasks.

Depends on:
    - bootstrap.services
    - core.task_utils
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import os

import aiohttp
import structlog

from bootstrap.power import acquire_wake_lock
from bootstrap.services import _init_mpv, context
from config import MAX_CACHE_SIZE_BYTES
from core.log_categories import LC_CACHE, LC_PLAYBACK, LC_SYSTEM
from core.state import PlayerStatus
from core.task_utils import safe_create_task

logger = structlog.get_logger(component="system.startup_tasks")


# Connectivity Check
async def check_connectivity():
    ctx = context
    while True:
        try:
            async with ctx.http_session.get(
                "https://connectivitycheck.gstatic.com/generate_204",
                timeout=aiohttp.ClientTimeout(total=3),
            ) as r:
                ctx.state.is_online = r.status == 204
        except (TimeoutError, aiohttp.ClientError):
            ctx.state.is_online = False
        except Exception as e:
            logger.warning(
                "connectivity_check_failed",
                category=LC_SYSTEM,
                error_type=type(e).__name__,
                error=str(e),
            )
            ctx.state.is_online = False

        await asyncio.sleep(300)  # 60→300 det: cek konektivitas cukup sekali per 5 menit


# Resume last playback — dijalankan sebagai background task agar tidak memblok
# run_server(). Menunggu MPV siap via _mpv_ready_event (tanpa timeout) sebelum
# memanggil play_track(), sehingga browser sudah bisa connect ke UI sementara
# resume (dan kemungkinan network call yt-dlp) masih diproses di belakang layar.
async def _resume_last_track():
    ctx = context
    # Tunggu MPV siap sebelum resume — tanpa timeout agar resume tidak di-skip
    # di hardware lambat (Termux/Android). Karena ini background task, menunggu
    # di sini tidak memblok server sama sekali.
    await ctx.mpv_ready_event.wait()
    if ctx.state.status == PlayerStatus.ERROR:
        # MPV gagal start, tidak ada gunanya mencoba resume
        return
    try:
        async with ctx.repos.conn.execute(
            "SELECT video_id, last_position FROM tracks WHERE last_played IS NOT NULL ORDER BY last_played DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row and row["video_id"]:
                last_pos = float(row["last_position"] or 0.0)
                track = await ctx.repos.tracks.get_track(row["video_id"])
                if track and last_pos > 0:
                    await ctx.playback_controller.play_track(
                        track, start_position=last_pos, start_paused=True
                    )
                    logger.info(
                        "playback_resumed_last_track",
                        category=LC_PLAYBACK,
                        video_id=track.video_id,
                        position_sec=last_pos,
                    )
    except Exception as e:
        logger.error(
            "playback_resume_last_position_failed",
            category=LC_PLAYBACK,
            error_type=type(e).__name__,
            error=str(e),
        )


def _evict_cache_sync(files_to_remove: list[str]) -> None:
    for fp in files_to_remove:
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except OSError:
            pass


async def _cache_eviction_loop():
    ctx = context
    try:
        while True:
            try:
                from server.handlers.ws_cache import _get_cache_size_sync

                loop = asyncio.get_running_loop()
                current_size = await loop.run_in_executor(None, _get_cache_size_sync)

                if current_size > MAX_CACHE_SIZE_BYTES:
                    target_size = int(MAX_CACHE_SIZE_BYTES * 0.8)
                    bytes_to_free = current_size - target_size

                    async with ctx.repos.conn.execute(
                        "SELECT video_id, local_path FROM tracks WHERE local_path IS NOT NULL ORDER BY COALESCE(last_played, 0) ASC"
                    ) as cursor:
                        rows = await cursor.fetchall()

                    freed = 0
                    files_to_remove = []
                    video_ids_cleared = []

                    for row in rows:
                        if freed >= bytes_to_free:
                            break
                        local_path = row["local_path"]
                        if not local_path:
                            continue

                        try:
                            st = os.stat(local_path)
                            freed += st.st_size
                            files_to_remove.append(local_path)
                            video_ids_cleared.append(row["video_id"])
                        except OSError:
                            video_ids_cleared.append(row["video_id"])

                    if files_to_remove:
                        await loop.run_in_executor(None, _evict_cache_sync, files_to_remove)

                    if video_ids_cleared:
                        for i in range(0, len(video_ids_cleared), 100):
                            chunk = video_ids_cleared[i : i + 100]
                            placeholders = ",".join(["?"] * len(chunk))
                            await ctx.repos.conn.execute(
                                f"UPDATE tracks SET local_path = NULL WHERE video_id IN ({placeholders})",
                                chunk,
                            )
                        await ctx.repos.conn.commit()
                        logger.info(
                            "cache_files_evicted",
                            category=LC_CACHE,
                            evicted_count=len(video_ids_cleared),
                        )

            except Exception as e:
                logger.error(
                    "cache_eviction_cycle_failed",
                    category=LC_CACHE,
                    error_type=type(e).__name__,
                    error=str(e),
                )

            await asyncio.sleep(900)  # Cek setiap 15 menit
    except asyncio.CancelledError:
        # Shutdown normal (task.cancel() dari caller) -- bukan kejadian
        # tak wajar, tidak perlu event ERROR.
        raise
    except Exception as e:
        # L7.5: jalur ini hanya tercapai bila ada exception yang lolos dari
        # try/except per-siklus di atas (bug di luar penanganan error yang
        # sudah ada, mis. kegagalan akses `context` itu sendiri) -- artinya
        # loop benar-benar berhenti tanpa sinyal shutdown eksplisit.
        logger.error(
            "cache_eviction_loop_stopped_unexpectedly",
            category=LC_CACHE,
            error_type=type(e).__name__,
            error=str(e),
            exc_info=True,
        )
        raise


async def run_startup_checks():
    """Schedule connectivity check, MPV initial connect, and resume-last-
    track as background tasks (non-blocking), in that order."""
    ctx = context

    ctx.lifecycle.schedule_task(check_connectivity(), name="connectivity_checker")

    ctx.lifecycle.schedule_task(acquire_wake_lock(), name="wake_lock_acquire")

    # MPV connect dijalankan sebagai background task — server tidak perlu menunggu.
    # _mpv_ready_event akan di-set oleh _init_mpv() saat koneksi selesai (sukses/gagal).
    ctx.lifecycle.schedule_task(_init_mpv(), name="mpv_initial_connect")

    ctx.lifecycle.schedule_task(_resume_last_track(), name="resume_last_track")

    # Background task untuk membersihkan cache MP3 (LRU)
    ctx.lifecycle.schedule_task(_cache_eviction_loop(), name="cache_eviction")
