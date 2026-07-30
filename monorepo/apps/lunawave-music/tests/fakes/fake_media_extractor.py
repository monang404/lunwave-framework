"""Fake implementation of core.ports.MediaExtractorPort for tests.
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

from core.state import TrackInfo


class FakeMediaExtractor:
    def __init__(self):
        self.search_results: list[TrackInfo] = []
        self.stream_urls: dict[str, str] = {}
        self.download_paths: dict[str, str] = {}
        self.cancelled = False
        self.call_log: list[tuple] = []

    async def search(self, query: str, max_results: int = 15) -> list[TrackInfo]:
        self.call_log.append(("search", query, max_results))
        return self.search_results[:max_results]

    async def extract_info(self, url: str) -> TrackInfo | None:
        self.call_log.append(("extract_info", url))
        for track in self.search_results:
            if track.video_id in url:
                return track
        return None

    async def get_stream_url(self, video_id: str) -> str | None:
        self.call_log.append(("get_stream_url", video_id))
        return self.stream_urls.get(video_id)

    async def download_mp3(self, video_id: str, on_progress=None) -> str:
        self.call_log.append(("download_mp3", video_id))
        if on_progress:
            on_progress(1.0)
        return self.download_paths.get(video_id, f"/tmp/{video_id}.mp3")

    def cancel_download(self) -> None:
        self.call_log.append(("cancel_download",))
        self.cancelled = True
