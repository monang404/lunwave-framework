"""
Module: adapters.ytdlp.searcher

Purpose:
    Performs metadata extraction and search operations via yt-dlp.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - adapters.ytdlp.ydl_options
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import hashlib
import re

_VALID_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

from adapters.ytdlp.ydl_options import YDL_OPTS_INFO
from core.state import TrackInfo


class YtDlpSearcher:
    """search(query) → list[TrackInfo]"""

    def __init__(self, executor):
        self._executor = executor

    async def search(self, query: str, max_results: int = 10) -> list[TrackInfo]:
        opts = {**YDL_OPTS_INFO, "extract_flat": True}
        url = f"ytsearch10:{query}"
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(self._executor, self._extract_sync, url, opts)

        tracks = []
        for e in results.get("entries", []):
            if not e:
                continue

            duration_raw = e.get("duration")
            try:
                duration = int(duration_raw) if duration_raw else 0
            except (ValueError, TypeError):
                duration = 0

            title_raw = e.get("title")
            title = str(title_raw).lower() if title_raw else ""

            if duration > 600:
                continue
            if any(
                kw in title
                for kw in [
                    "compilation",
                    "full album",
                    "mix",
                    "playlist",
                    "mashup",
                    "medley",
                    "megamix",
                ]
            ):
                continue

            tracks.append(self._to_track(e))
            if len(tracks) >= max_results:
                break

        return tracks

    async def extract_info(self, url: str) -> TrackInfo | None:
        opts = {**YDL_OPTS_INFO, "extract_flat": True}
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(self._executor, self._extract_sync, url, opts)
            if not result:
                return None
            return self._to_track(result)
        except Exception:
            return None

    def _extract_sync(self, url, opts):
        import yt_dlp

        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _to_track(self, entry: dict) -> TrackInfo:
        duration_raw = entry.get("duration", 0)
        duration = int(duration_raw) if duration_raw else 0

        video_id = entry.get("id", "") or entry.get("url", "")
        if video_id and not _VALID_ID_RE.match(video_id):
            video_id = f"vid_{hashlib.sha1(entry.get('title', '').encode(), usedforsecurity=False).hexdigest()[:10]}"
        elif not video_id:
            video_id = f"vid_{hashlib.sha1(entry.get('title', '').encode(), usedforsecurity=False).hexdigest()[:10]}"

        return TrackInfo(
            video_id=video_id,
            title=entry.get("title", "Unknown"),
            artist=entry.get("uploader", "Unknown"),
            duration=duration,
            thumbnail=entry.get("thumbnail"),
            view_count=entry.get("view_count"),
        )
