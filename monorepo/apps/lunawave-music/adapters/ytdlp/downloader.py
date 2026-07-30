"""
Module: adapters.ytdlp.downloader

Purpose:
    Handles downloading audio streams using yt-dlp.

Responsibilities:
    - Download audio in its native container (opus/m4a/webm) via remux — no
      decode-encode transcode. This preserves the original codec/bitrate and
      avoids the double-lossy penalty of MP3 re-encoding.
    - Return the actual path with its real extension so callers always use the
      correct file, regardless of the container yt-dlp chose.

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
import glob
import re

from adapters.ytdlp.ydl_options import YDL_OPTS_INFO
from config import CACHE_DIR


class YtDlpDownloader:
    """download_audio(video_id) -> str (actual file path with real extension)"""

    def __init__(self, executor):
        self._executor = executor
        self.is_cancelled = False

    def cancel_download(self):
        self.is_cancelled = True

    def _check_cancel_hook(self, d):
        if self.is_cancelled:
            raise Exception("DownloadCancelled")

    async def download_audio(self, video_id: str, on_progress=None) -> str:
        """Download audio in native container (remux, no transcode).

        Returns the actual path on disk (extension may be .opus, .m4a, .webm,
        etc. — whatever yt-dlp resolves as bestaudio for this video).
        """
        self.is_cancelled = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", video_id)
        out_path = CACHE_DIR / f"{safe_id}.%(ext)s"

        hooks = [self._check_cancel_hook]
        if on_progress:
            hooks.append(on_progress)

        opts = {
            **YDL_OPTS_INFO,
            # Explicitly request bestaudio for downloads too (no m4a bias).
            "format": "bestaudio/best",
            "format_sort": ["abr", "asr"],
            "outtmpl": str(out_path),
            # Remux to a clean container without re-encoding audio data.
            # 'preferredcodec: "best"' instructs FFmpegExtractAudio to keep the
            # original audio codec and simply remux (copy stream) into a
            # standalone audio file — zero quality loss vs. MP3 transcode.
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "best",
                    "preferredquality": "0",
                }
            ],
            "progress_hooks": hooks,
        }
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._download_sync, video_id, opts)

        # Discover the actual file yt-dlp wrote (extension is dynamic).
        pattern = str(CACHE_DIR / f"{safe_id}.*")
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
        # Fallback: should not happen, but keep caller from crashing.
        return str(CACHE_DIR / f"{safe_id}.opus")

    # Backward-compat alias so callers that still use download_mp3 don't break.
    async def download_mp3(self, video_id: str, on_progress=None) -> str:
        """Deprecated: use download_audio() instead. Kept for backward compat."""
        return await self.download_audio(video_id, on_progress)

    def _download_sync(self, video_id, opts):
        import yt_dlp

        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
