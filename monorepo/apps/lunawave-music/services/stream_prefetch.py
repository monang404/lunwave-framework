"""
Module: services.stream_prefetch

Purpose:
    Pre-fetch and cache the stream URL for the next track in the background
    to reduce playback latency at track transitions.

Responsibilities:
    - Skip pre-fetch when a valid cached URL is already available.
    - Resolve a fresh URL via yt-dlp and persist it to the database.

Depends on:
    - core.ports

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async; spawned as background task).
"""

import asyncio
import time

import structlog

from config import PREFETCH_RETRY_ATTEMPTS, PREFETCH_RETRY_BACKOFF_SEC, STREAM_URL_TTL_SEC
from core.exceptions import RateLimitedError, VideoUnavailableError
from core.log_categories import LC_PERSISTENCE, LC_RESOLVE
from core.ports import MediaExtractorPort, TrackRepositoryPort

logger = structlog.get_logger(component="resolve.stream_prefetch")


class StreamPrefetchService:
    def __init__(self, db: TrackRepositoryPort, ytdlp: MediaExtractorPort):
        self.db = db
        self.ytdlp = ytdlp

    async def prefetch_stream_url(self, video_id: str):
        row = await self.db.get_track(video_id)
        if row and row.stream_url and row.stream_url_ts:
            if time.time() - row.stream_url_ts < STREAM_URL_TTL_SEC:
                return

        # PATCH-2026-07-20-136 Rule 0: video yang sudah dikonfirmasi
        # dihapus/private/diblokir permanen tidak perlu dicoba prefetch sama
        # sekali -- ini cuma optimasi latensi, tidak ada gunanya membuang
        # request yt-dlp untuk video yang pasti gagal.
        if await self.db.get_unavailable_reason(video_id):
            return

        last_error: Exception | None = None
        for attempt in range(PREFETCH_RETRY_ATTEMPTS):
            try:
                url = await self.ytdlp.get_stream_url(video_id)
                await self.db.update_stream_url_only(video_id, url)  # type: ignore
                return
            except VideoUnavailableError as e:
                # Permanen -- retry tidak akan pernah berhasil. Tandai di DB
                # supaya prefetch/play berikutnya untuk video ini langsung
                # skip lewat Rule 0 di atas, alih-alih mencoba lagi.
                from core.state import TrackInfo

                track = row or TrackInfo(
                    video_id=video_id, title=video_id, artist="unknown", duration=0
                )
                try:
                    await self.db.mark_unavailable(track, str(e))
                except Exception as mark_err:
                    logger.error(
                        "prefetch_mark_unavailable_failed",
                        category=LC_PERSISTENCE,
                        video_id=video_id,
                        error_type=type(mark_err).__name__,
                        error=str(mark_err),
                    )
                logger.info(
                    "prefetch_cancelled_video_unavailable",
                    category=LC_RESOLVE,
                    video_id=video_id,
                    reason=str(e),
                )
                return
            except RateLimitedError as e:
                # Retry cepat pada prefetch (background, tidak kritis) malah
                # berisiko memperparah rate-limit yang sedang dialami jalur
                # playback utama. Cukup log & serahkan ke jalur play utama.
                logger.warning(
                    "prefetch_cancelled_rate_limited",
                    category=LC_RESOLVE,
                    video_id=video_id,
                    error=str(e),
                )
                return
            except Exception as e:
                last_error = e
                if attempt < PREFETCH_RETRY_ATTEMPTS - 1:
                    logger.info(
                        "prefetch_retry_attempt_failed",
                        category=LC_RESOLVE,
                        video_id=video_id,
                        attempt=attempt + 1,
                        max_attempts=PREFETCH_RETRY_ATTEMPTS,
                        error=str(e),
                    )
                    await asyncio.sleep(PREFETCH_RETRY_BACKOFF_SEC * (attempt + 1))

        logger.warning(
            "prefetch_failed_after_retries",
            category=LC_RESOLVE,
            video_id=video_id,
            attempt_count=PREFETCH_RETRY_ATTEMPTS,
            error=str(last_error),
        )
