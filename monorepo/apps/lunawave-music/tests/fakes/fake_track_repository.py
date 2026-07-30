"""Fake implementation of core.ports.TrackRepositoryPort for tests.
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

from core.state import TrackInfo


class FakeTrackRepository:
    def __init__(self):
        self._tracks: dict[str, TrackInfo] = {}
        self._unavailable: dict[str, str] = {}
        self.call_log: list[tuple] = []

    def seed(self, track: TrackInfo) -> None:
        """Test helper: directly place a TrackInfo row into the fake DB."""
        self._tracks[track.video_id] = track

    async def upsert_track(
        self, track: TrackInfo, stream_url: str = None, local_path: str = None
    ) -> None:
        self.call_log.append(("upsert_track", track.video_id, stream_url, local_path))
        existing = self._tracks.get(track.video_id)
        stored = TrackInfo(
            video_id=track.video_id,
            title=track.title,
            artist=track.artist,
            duration=track.duration,
            thumbnail=track.thumbnail,
            local_path=local_path
            if local_path is not None
            else (existing.local_path if existing else None),
            stream_url=stream_url
            if stream_url is not None
            else (existing.stream_url if existing else None),
            view_count=track.view_count,
            stream_url_ts=None,
            play_count=existing.play_count if existing else 0,
            last_played=existing.last_played if existing else None,
            is_favorite=existing.is_favorite if existing else 0,
            loudness_lufs=existing.loudness_lufs if existing else None,
        )
        if stream_url is not None:
            import time

            stored.stream_url_ts = int(time.time())
        self._tracks[track.video_id] = stored

    async def update_stream_url_only(self, video_id: str, stream_url: str) -> None:
        self.call_log.append(("update_stream_url_only", video_id, stream_url))
        if video_id in self._tracks:
            self._tracks[video_id].stream_url = stream_url

    async def get_track(self, video_id: str) -> TrackInfo | None:
        self.call_log.append(("get_track", video_id))
        return self._tracks.get(video_id)

    async def increment_play_count(self, video_id: str) -> None:
        self.call_log.append(("increment_play_count", video_id))
        if video_id in self._tracks:
            self._tracks[video_id].play_count = (self._tracks[video_id].play_count or 0) + 1

    async def set_loudness(
        self, video_id: str, lufs: float, true_peak: float | None = None
    ) -> None:
        self.call_log.append(("set_loudness", video_id, lufs, true_peak))
        if video_id in self._tracks:
            self._tracks[video_id].loudness_lufs = lufs
            if true_peak is not None:
                self._tracks[video_id].true_peak_dbtp = true_peak

    async def mark_unavailable(self, track: TrackInfo, reason: str) -> None:
        self.call_log.append(("mark_unavailable", track.video_id, reason))
        self._unavailable[track.video_id] = reason
        if track.video_id not in self._tracks:
            self._tracks[track.video_id] = track

    async def get_unavailable_reason(self, video_id: str) -> str | None:
        self.call_log.append(("get_unavailable_reason", video_id))
        return self._unavailable.get(video_id)

    async def record_completion(self, artist: str) -> None:
        # PATCH-2026-07-20-136: dipanggil queue_controller.advance_to_next()
        # (via c.resolver.db.record_completion) -- fake ini sebelumnya tidak
        # punya method ini sama sekali, jadi setiap test yang benar-benar
        # menembus alur advance_to_next() penuh akan meledak AttributeError
        # duluan sebelum sempat mencapai queue_mode.next(). No-op minimal,
        # cukup dicatat di call_log untuk keperluan assert kalau dibutuhkan.
        self.call_log.append(("record_completion", artist))

    async def record_skip(self, artist: str) -> None:
        self.call_log.append(("record_skip", artist))
