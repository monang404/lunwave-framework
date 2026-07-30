"""
Module: plugins.sponsorblock

Purpose:
    Fetch SponsorBlock skip segments for the current video and auto-seek
    past them during playback.

Responsibilities:
    - Query the SponsorBlock API for configured categories per video.
    - Monitor TrackProgressEvent and seek past matched segment start times.

Depends on:
    - core.event_bus
    - core.events
    - core.ports
    - core.state

Subscribes to:
    TrackProgressEvent

Publishes:
    LogMessageEvent

Thread Safety:
    Worker thread (async; stateless per-track segment list).
"""

import json

import aiohttp
import structlog

from config import SPONSORBLOCK_CATS
from core.event_bus import EventBus
from core.events import LogMessageEvent, TrackProgressEvent
from core.log_categories import LC_EXTERNAL
from core.ports import AudioPlayerPort
from core.state import AppState

logger = structlog.get_logger(component="sponsorblock")
SPONSORBLOCK_API = "https://sponsor.ajay.app/api/skipSegments"


from lunawave_framework.core.plugins import BasePlugin

class SponsorBlockHandler(BasePlugin):
    """
    HIGH-02 fix: Uses json.dumps for category serialization.
    MED-01 fix: Accepts a shared aiohttp session.
    """

    def __init__(
        self,
        mpv: AudioPlayerPort,
        state: AppState,
        session: aiohttp.ClientSession | None = None,
        event_bus: EventBus = None,  # type: ignore
    ):
        self.mpv = mpv
        self.state = state
        self.segments: list[tuple[float, float]] = []
        # PATCH-2026-07-16-001: segment yang sudah pernah di-skip, direset
        # tiap track baru (lihat fetch_segments). Dipakai agar deteksi seek
        # tidak lagi bergantung pada window sempit (start..start+0.6) yang
        # bisa terlewat kalau progress event "melompat" (mis. posisi loncat
        # dari start-0.1 ke start+0.9 dalam satu event, terutama kalau
        # progress event throttle-nya lebih lambat dari 0.6s).
        self._skipped_segments: set[tuple[float, float]] = set()
        self._session = session
        # TASK-3.5: Injected per-room bus (fallback ke global jika belum direfactor)
        if event_bus is None:
            from core.event_bus import bus as _global_bus

            event_bus = _global_bus
        self._bus = event_bus

    async def start(self) -> None:
        self._bus.subscribe(TrackProgressEvent, self._on_progress)

    async def cleanup(self) -> None:
        self._bus.unsubscribe(TrackProgressEvent, self._on_progress)

    async def fetch_segments(self, video_id: str):
        """Fetches skip segments and stores them in memory for the current track."""
        self.segments = []
        self._skipped_segments = set()
        # HIGH-02 fix: Use json.dumps instead of str().replace()
        params = {
            "videoID": video_id,
            "categories": json.dumps(SPONSORBLOCK_CATS),
        }

        try:
            session = self._session or aiohttp.ClientSession()
            close_after = self._session is None
            try:
                async with session.get(
                    SPONSORBLOCK_API, params=params, timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.segments = [(seg["segment"][0], seg["segment"][1]) for seg in data]
                        logger.info(
                            "sponsorblock_segments_fetched",
                            category=LC_EXTERNAL,
                            video_id=video_id,
                            segment_count=len(self.segments),
                        )
                    elif resp.status == 404:
                        pass  # No segments for this video, that's normal
            finally:
                if close_after:
                    await session.close()
        except Exception as e:
            logger.debug(
                "sponsorblock_fetch_failed",
                category=LC_EXTERNAL,
                video_id=video_id,
                error_type=type(e).__name__,
                error=str(e),
            )

    async def _on_progress(self, event: TrackProgressEvent):
        """Called every ~1.0s (throttled) by MpvController. Seeks past sponsored segments."""
        current_pos = event.position
        if not getattr(self.state, "sponsorblock_active", True):
            return
        if not self.segments or not isinstance(current_pos, (int, float)):
            return

        for seg in self.segments:
            start, end = seg
            if seg in self._skipped_segments:
                continue
            if start <= current_pos < end:
                self._skipped_segments.add(seg)
                await self.mpv.seek(end)
                await self._bus.publish(
                    LogMessageEvent(message=f"Melewati sponsor ({int(start)}s - {int(end)}s)")
                )
                break
