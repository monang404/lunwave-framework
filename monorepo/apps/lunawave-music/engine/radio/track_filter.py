"""
Module: engine.radio.track_filter

Purpose:
    Filter candidate tracks for the radio queue to prevent duplicates,
    skip recently played tracks, and limit artist dominance.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread.
"""

import time

import structlog

from core.log_categories import LC_RADIO
from core.state import AppState, TrackInfo
from engine.radio.radio_config import MAX_TRACK_DURATION
from engine.radio.track_interleaver import normalize_title

logger = structlog.get_logger(component="radio.track_filter")


class TrackFilter:
    def __init__(self, state: AppState):
        self.state = state
        self.max_history_check = 50
        self.max_per_artist = 3

    def filter_tracks(self, candidates: list[TrackInfo]) -> list[TrackInfo]:
        """
        Filters a list of candidate tracks based on history, queue, duplicates,
        and artist quotas.
        """
        if not candidates:
            return []

        t0 = time.monotonic()

        # Build exclusion set from active queue and history
        exclude_ids = set()
        # PATCH-2026-07-16-001: exclude berdasarkan title ternormalisasi juga,
        # bukan cuma video_id -- menutup celah dua video_id beda tapi lagu
        # sama (mis. "Song (Official Video)" vs "Song (Lyrics)") lolos dedup.
        # Guard: title kosong-setelah-normalize (mis. "Acoustic Cover" yang
        # semuanya noise word) TIDAK dimasukkan set exclude, supaya semua
        # track dengan title kosong-setelah-normalize tidak saling exclude
        # secara salah satu sama lain.
        exclude_normalized_titles = set()

        def _track_normalized(t) -> str:
            normalized = normalize_title(t.title)
            if normalized:
                exclude_normalized_titles.add(normalized)
            return normalized

        if self.state.current_track:
            exclude_ids.add(self.state.current_track.video_id)
            _track_normalized(self.state.current_track)

        for t in self.state.radio_queue:
            exclude_ids.add(t.video_id)
            _track_normalized(t)

        history_list = list(self.state.history)
        for t in history_list[-self.max_history_check :]:
            exclude_ids.add(t.video_id)
            _track_normalized(t)

        # Build current artist quota from the queue
        artist_counts = {}  # type: ignore
        for t in self.state.radio_queue:
            artist_counts[t.artist] = artist_counts.get(t.artist, 0) + 1

        filtered = []
        seen_in_batch = set()

        for track in candidates:
            # 1. Filter out completely if recently played or in queue
            if track.video_id in exclude_ids:
                continue

            # 1b. Filter out if title (normalized) matches something already
            # in history/queue/current -- catches duplicate uploads of the
            # same song under a different video_id.
            normalized_title = normalize_title(track.title)
            if normalized_title and normalized_title in exclude_normalized_titles:
                continue

            # 1c. Filter out tracks longer than the radio cap (Bug #3 fix --
            # MAX_TRACK_DURATION dideklarasikan tapi sebelumnya tidak pernah
            # dipakai). duration <= 0 dianggap "belum diketahui", TIDAK
            # dibuang oleh filter ini.
            if track.duration and track.duration > MAX_TRACK_DURATION:
                continue

            # 2. Filter out duplicates within the candidate batch itself
            if track.video_id in seen_in_batch:
                continue

            # 3. Filter by artist quota to prevent one artist from dominating
            current_count = artist_counts.get(track.artist, 0)
            if current_count >= self.max_per_artist:
                # We skip this track but we might want to log it if debugging
                continue

            # If it passes all filters, add to results and update trackers
            seen_in_batch.add(track.video_id)
            if normalized_title:
                exclude_normalized_titles.add(normalized_title)
            artist_counts[track.artist] = current_count + 1
            filtered.append(track)

        duration_ms = round((time.monotonic() - t0) * 1000)
        logger.info(
            "radio_filter_completed",
            category=LC_RADIO,
            candidates_in=len(candidates),
            candidates_out=len(filtered),
            duration_ms=duration_ms,
        )

        return filtered
