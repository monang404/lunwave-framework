"""
Module: engine.radio.artist_selector

Purpose:
    Selects and rotates artists intelligently to maintain variety in radio mode.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state
    - engine.radio.radio_config
    - engine.radio.track_filter
    - engine.radio.track_interleaver

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import random

import structlog

from core.log_categories import LC_RADIO
from core.ports import ArtistRepositoryPort, LibraryRepositoryPort
from core.state import AppState
from engine.radio.radio_config import (
    ARTISTS_PER_BATCH,
    BANDIT_QUOTA,
    TRACKS_PER_ARTIST_TARGET,
)
from engine.radio.track_filter import TrackFilter
from engine.radio.track_interleaver import interleave_by_artist

logger = structlog.get_logger(component="radio.artist_selector")


class ArtistSelector:
    """Rotasi artis, seed selection, deduplication pool."""

    def __init__(
        self,
        artists: ArtistRepositoryPort | None,
        library: LibraryRepositoryPort | None,
        state: AppState,
    ):
        self.artists = artists
        self.library = library
        self.state = state
        self._seed_artists: list[str] = []
        self._artist_rotation: list[str] = []

    async def ensure_artists_loaded(self) -> None:
        if self._seed_artists:
            return
        try:
            if self.artists and self.artists.conn:
                self._seed_artists = await self.artists.get_all_artists()
        except Exception as e:
            logger.warning(
                "radio_seed_artists_load_failed",
                category=LC_RADIO,
                error_type=type(e).__name__,
                error=str(e),
            )

        if not self._seed_artists:
            # Bug #3 fix: pesan error sebut path DB yang benar
            raise RuntimeError(
                "Tabel artists kosong. Jalankan: python data/import_artists.py "
                "--db data/lunawave.db --json data/artists.json"
            )

    def reset_rotation(self):
        self._artist_rotation = []

    def build_exclusion_set(self) -> set[str]:
        ids = {t.video_id for t in self.state.radio_queue}
        if self.state.current_track:
            ids.add(self.state.current_track.video_id)
        for t in list(self.state.history)[-20:]:
            ids.add(t.video_id)
        return ids

    async def _sampled_seed_artists(self, k: int) -> list[str]:
        if not self._seed_artists:
            return []
        stats = {}
        if self.artists and getattr(self.artists, "conn", None):
            try:
                stats = await self.artists.get_reward_stats()
            except Exception as e:
                logger.warning(
                    "radio_reward_stats_fetch_failed",
                    category=LC_RADIO,
                    error_type=type(e).__name__,
                    error=str(e),
                )
        from engine.radio.artist_bandit import ArtistStat, sample_artists

        candidates = [
            ArtistStat(
                name=name,
                alpha=float(stats.get(name, (1.0, 1.0))[0]),
                beta=float(stats.get(name, (1.0, 1.0))[1]),
            )
            for name in self._seed_artists
        ]
        return sample_artists(candidates, k=k)

    async def gather_batch(
        self, prioritized_artist: str | None = None, max_artists: int = ARTISTS_PER_BATCH
    ) -> list:
        limit = max_artists * TRACKS_PER_ARTIST_TARGET
        existing = self.build_exclusion_set()

        seed_artists = []
        if prioritized_artist:
            seed_artists.append(prioritized_artist)

        needed = max_artists - len(seed_artists)
        if needed > 0 and self._seed_artists:
            bandit_count = min(needed, BANDIT_QUOTA)

            if bandit_count > 0:
                sampled = await self._sampled_seed_artists(k=bandit_count)
                for s in sampled:
                    if s not in seed_artists:
                        seed_artists.append(s)

            still_needed = max_artists - len(seed_artists)
            if still_needed > 0:
                available_for_explore = list(set(self._seed_artists) - set(seed_artists))
                if available_for_explore:
                    explore_picked = random.sample(
                        available_for_explore, min(still_needed, len(available_for_explore))
                    )
                    seed_artists.extend(explore_picked)

        if self.library and getattr(self.library, "conn", None):  # Use getattr for safety
            try:
                tracks = await self.library.get_random_songs(
                    limit=limit,
                    exclude_ids=existing,
                    artists=seed_artists if seed_artists else None,
                    max_per_artist=TRACKS_PER_ARTIST_TARGET,
                )
                track_filter = TrackFilter(self.state)
                filtered_tracks = track_filter.filter_tracks(tracks)
                return interleave_by_artist(filtered_tracks)
            except Exception as e:
                logger.warning(
                    "radio_random_tracks_fetch_failed",
                    category=LC_RADIO,
                    error_type=type(e).__name__,
                    error=str(e),
                )
        return []
