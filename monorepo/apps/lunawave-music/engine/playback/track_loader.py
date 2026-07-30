"""
Module: engine.playback.track_loader

Purpose:
    Resolve a track URI and trigger background side-effects (sponsorblock,
    lyrics fetch, play-count increment) before playback begins.

Responsibilities:
    - Delegate URI resolution to CacheResolver.
    - Increment play count and launch sponsorblock/lyrics tasks in parallel.

Depends on:
    - core.ports
    - core.state
    - core.task_utils

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import AppState
    from engine.loudness.service import LoudnessService

import structlog

from core.ports import LyricsProvider, SponsorBlockProvider, StreamResolverPort
from core.state import TrackInfo
from core.task_utils import safe_create_task

logger = structlog.get_logger(component="playback.track_loader")


@dataclass
class LoadedTrack:
    uri: str
    gain_db: float = 0.0


class TrackLoader:
    def __init__(
        self,
        resolver: StreamResolverPort,
        sponsorblock: SponsorBlockProvider,
        lyrics_fetcher: LyricsProvider,
        loudness_service: "LoudnessService | None" = None,
        state: "AppState | None" = None,
    ):
        self.resolver = resolver
        self.sponsorblock = sponsorblock
        self.lyrics_fetcher = lyrics_fetcher
        self.loudness_service = loudness_service
        self.state = state

    async def load_track(self, track: TrackInfo) -> LoadedTrack:
        """
        Resolves the track URI and triggers background tasks
        for lyrics and sponsorblock. Also increments play count.
        Returns the playable URI.
        """
        # Resolve URI
        uri = await self.resolver.resolve(track)

        # C-02: Increment play count — fire-and-forget, tidak boleh menunda mpv.play(uri)
        safe_create_task(
            self.resolver.db.increment_play_count(track.video_id),
            name=f"incr_play_count_{track.video_id}",
        )

        # Fetch sponsorblock and lyrics
        safe_create_task(
            self.sponsorblock.fetch_segments(track.video_id),
            name=f"fetch_sponsorblock_{track.video_id}",
        )
        safe_create_task(self.lyrics_fetcher.fetch(track), name=f"fetch_lyrics_{track.video_id}")

        gain_db = 0.0
        if self.loudness_service:
            row = await self.resolver.db.get_track(track.video_id)
            if row and row.loudness_lufs is not None:
                from engine.loudness.gain_calculator import compute_gain_db

                gain_db = compute_gain_db(row.loudness_lufs, row.true_peak_dbtp)
            if getattr(self.state, "loudness_normalization_enabled", False):
                safe_create_task(
                    self.loudness_service.analyze_and_store(track.video_id, uri),
                    name=f"analyze_loudness_{track.video_id}",
                )

        return LoadedTrack(uri=uri, gain_db=gain_db)
