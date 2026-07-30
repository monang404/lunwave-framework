"""
Module: adapters.ytdlp.resolver

Purpose:
    Resolves direct stream URLs for tracks using yt-dlp.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - adapters.ytdlp.ydl_options

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import re

import structlog

from adapters.ytdlp.ydl_options import YDL_OPTS_INFO, YDL_OPTS_INFO_FALLBACK
from config import YTDLP_RESOLVE_TIMEOUT_SEC
from core.exceptions import BotCheckError, RateLimitedError, VideoUnavailableError
from core.log_categories import LC_RESOLVE

logger = structlog.get_logger(component="ytdlp.resolver")

# PATCH-2026-07-20-136: klasifikasi pesan error yt-dlp. yt-dlp tidak punya
# exception class terpisah per jenis kegagalan -- semuanya
# yt_dlp.utils.DownloadError dengan pesan bebas -- jadi satu-satunya cara
# membedakan "video hilang permanen" vs "butuh login" vs "rate limited" vs
# "gangguan biasa" adalah pattern-match pesannya. Pola di bawah berdasarkan
# pesan resmi yt-dlp per 2026-07 (extractor/youtube.py upstream).
_BOT_CHECK_RE = re.compile(r"sign in to confirm|not a bot|confirm you.re not a bot", re.IGNORECASE)
_RATE_LIMIT_RE = re.compile(r"\b429\b|too many requests|http error 429", re.IGNORECASE)
_UNAVAILABLE_RE = re.compile(
    r"video unavailable|private video|has been removed|no longer available|"
    r"account associated with this video has been terminated|"
    r"this video is not available|video has been deleted",
    re.IGNORECASE,
)


def classify_ytdlp_error(video_id: str, exc: Exception) -> Exception | None:
    """Cocokkan pesan exception dari yt-dlp ke salah satu typed exception.
    Return None kalau tidak cocok pola manapun -- caller tetap pakai
    RuntimeError generik seperti sebelumnya (perilaku lama tidak berubah
    untuk error yang belum dikenali)."""
    msg = str(exc)
    if _BOT_CHECK_RE.search(msg):
        return BotCheckError(f"YouTube meminta verifikasi login untuk {video_id}: {msg}")
    if _RATE_LIMIT_RE.search(msg):
        return RateLimitedError(f"Rate-limited oleh YouTube saat resolve {video_id}: {msg}")
    if _UNAVAILABLE_RE.search(msg):
        return VideoUnavailableError(f"Video {video_id} tidak tersedia secara permanen: {msg}")
    return None


class YtDlpResolver:
    """get_stream_url(video_id) → str"""

    def __init__(self, executor):
        self._executor = executor

    async def get_stream_url(self, video_id: str) -> str:
        try:
            return await self._resolve_once(video_id, YDL_OPTS_INFO)
        except TimeoutError:
            logger.error(
                "stream_resolve_timeout",
                category=LC_RESOLVE,
                video_id=video_id,
                timeout_sec=YTDLP_RESOLVE_TIMEOUT_SEC,
            )
            raise RuntimeError(
                f"Timeout ({YTDLP_RESOLVE_TIMEOUT_SEC}s) saat mengambil stream URL untuk {video_id}"
            ) from None
        except RuntimeError:
            raise
        except Exception as e:
            classified = classify_ytdlp_error(video_id, e)
            if isinstance(classified, BotCheckError):
                # Percobaan kedua dengan player client berbeda sebelum
                # benar-benar menyerah -- ini sering cukup untuk lolos
                # bot-check tanpa perlu cookies/login akun.
                logger.warning(
                    "stream_resolve_bot_check_retry",
                    category=LC_RESOLVE,
                    video_id=video_id,
                    fallback_client="android",
                )
                try:
                    return await self._resolve_once(video_id, YDL_OPTS_INFO_FALLBACK)
                except TimeoutError:
                    raise RuntimeError(
                        f"Timeout saat retry fallback client untuk {video_id}"
                    ) from None
                except Exception as e2:
                    classified2 = classify_ytdlp_error(video_id, e2) or classified
                    logger.error(
                        "stream_resolve_fallback_failed",
                        category=LC_RESOLVE,
                        video_id=video_id,
                        error_type=type(classified2).__name__,
                        error=str(classified2),
                    )
                    raise classified2 from e2
            if classified:
                logger.error(
                    "stream_resolve_failed",
                    category=LC_RESOLVE,
                    video_id=video_id,
                    error_type=type(classified).__name__,
                    error=str(classified),
                )
                raise classified from e
            logger.error(
                "stream_resolve_failed",
                category=LC_RESOLVE,
                video_id=video_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise RuntimeError(f"Gagal mengambil stream URL untuk {video_id}: {e}") from e

    async def _resolve_once(self, video_id: str, opts: dict) -> str:
        opts = {**opts, "extract_flat": False}
        url = f"https://www.youtube.com/watch?v={video_id}"
        loop = asyncio.get_running_loop()
        info = await asyncio.wait_for(
            loop.run_in_executor(self._executor, self._extract_sync, url, opts),
            timeout=YTDLP_RESOLVE_TIMEOUT_SEC,
        )
        if info:
            stream_url = self._pick_audio_url(info)
            if stream_url:
                return stream_url
        raise RuntimeError(f"yt-dlp returned no stream URL for {video_id}")

    def _extract_sync(self, url, opts):
        import yt_dlp

        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _pick_audio_url(self, info: dict) -> str:
        # Trust yt-dlp's own selector result — the top-level "url" key is the
        # URL of the format that the selector + format_sort in YDL_OPTS_INFO
        # already chose. Re-iterating "formats" manually here is a second,
        # competing logic that can silently produce a different (worse) result.
        url = info.get("url")
        if url:
            return url
        # Fallback: if for any reason top-level url is absent, pick best
        # audio-only format explicitly sorted by abr descending. Iterate in
        # reverse so that, when abr is missing/tied, the last-listed (usually
        # highest-itag / most-recent) format wins instead of the first one.
        formats = info.get("formats", [])
        audio_only = [
            f for f in reversed(formats) if f.get("acodec") != "none" and f.get("vcodec") == "none"
        ]
        if audio_only:
            best = max(audio_only, key=lambda f: f.get("abr") or 0)
            return best["url"]
        # Last resort: no dedicated audio-only stream at all, only muxed
        # (audio+video) formats. Still usable — mpv is launched with
        # --no-video, so the video stream is simply discarded — better than
        # failing the whole playback outright.
        muxed = [f for f in reversed(formats) if f.get("acodec") != "none"]
        if muxed:
            best = max(muxed, key=lambda f: f.get("abr") or 0)
            return best["url"]
        raise RuntimeError("yt-dlp returned no usable audio format")
