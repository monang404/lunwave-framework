"""
Module: plugins.lyrics

Purpose:
    Fetch synchronized lyrics from lrclib.net and syncedlyrics, then
    update the active lyric index on each playback progress event.

Responsibilities:
    - Try lrclib /get, lrclib /search, and syncedlyrics as fallback sources.
    - Parse LRC timestamps and expose clean text lines via AppState.

Depends on:
    - core.event_bus
    - core.events
    - core.state
    - plugins.lyrics_parser
    - plugins.lyrics_sync

Subscribes to:
    TrackProgressEvent

Publishes:
    LyricsUpdatedEvent

Thread Safety:
    Worker thread (async; _current_generation guards stale fetch results).
"""

import asyncio
import re

_NOISE_RE = re.compile(
    r"\b(?:official|music video|lyrics?|audio|video|mv|hq)s?\b",
    re.IGNORECASE,
)

import aiohttp
import structlog

from config import LYRICS_API_BASE
from core.event_bus import EventBus
from core.events import LyricsUpdatedEvent
from core.log_categories import LC_EXTERNAL

logger = structlog.get_logger(component="lyrics.fetcher")

from core.state import TrackInfo


from lunawave_framework.core.plugins import BasePlugin

class LyricsFetcher(BasePlugin):
    """
    MED-01 fix: Accepts a shared aiohttp session.
    LOW-07 fix: Strips timestamp prefixes from displayed lyrics.
    """

    def __init__(self, state, session: aiohttp.ClientSession = None, event_bus: EventBus = None):  # type: ignore
        self.state = state
        self.lyrics_data: list[tuple[float, str]] = []
        self._session = session
        self._owns_session = False  # True jika kita yang buat, kita yang harus tutup
        self._current_generation = 0
        self._last_lyrics_broadcast_ts: float = 0.0  # throttle LyricsUpdatedEvent
        # TASK-3.4: Injected per-room bus (fallback ke global jika belum direfactor)
        if event_bus is None:
            from core.event_bus import bus as _global_bus

            event_bus = _global_bus
        self._bus = event_bus
        from plugins.lyrics_sync import LyricsSync

        self._sync = LyricsSync(self.state, self._bus)

    def _get_session(self) -> aiohttp.ClientSession:
        """Kembalikan session yang ada, atau buat satu fallback session yang persisten."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def start(self) -> None:
        pass

    async def cleanup(self) -> None:
        self._sync.cleanup()
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            self._owns_session = False

    async def fetch(self, track: TrackInfo):
        """Fetches synchronized lyrics from lrclib.net and parses them."""
        title = track.title
        artist = track.artist
        duration = track.duration
        self.lyrics_data = []
        self.state.lyrics_lines = []
        self.state.lyrics_index = 0
        self.state.lyrics_offset = 0.0
        self.state.lyrics_loading = True

        self._current_generation += 1
        gen = self._current_generation

        await self._bus.publish(LyricsUpdatedEvent())

        try:
            session = self._get_session()
            if True:  # dummy block untuk menjaga indentasi try/except di bawah
                # 1. Coba pencarian spesifik (exact match) dengan durasi
                url_get = f"{LYRICS_API_BASE}/get"
                params_get = {"track_name": title, "artist_name": artist, "duration": duration}
                lrc = None

                async with session.get(
                    url_get,
                    params=params_get,  # type: ignore
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        lrc = data.get("syncedLyrics") or data.get("plainLyrics", "")

                # Bersihkan judul secara umum (karena info dari YouTube sering kotor)
                clean_title = re.sub(r"[\(\[].*?[\)\]]", "", title)
                clean_title = _NOISE_RE.sub("", clean_title)
                clean_title = re.sub(r"\s+", " ", clean_title).strip("- ")

                # Buat search query yang lebih bersih
                if "-" in title:
                    search_query = clean_title
                else:
                    search_query = (
                        f"{clean_title} {artist}"
                        if artist and artist.lower() not in ["unknown", "topic"]
                        else clean_title
                    )

                # 2. Jika gagal karena durasi tidak persis sama (sering terjadi di YouTube), gunakan fallback search
                if not lrc:
                    url_search = f"{LYRICS_API_BASE}/search"
                    params_search = {"q": search_query}

                    async with session.get(
                        url_search, params=params_search, timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            results = await resp.json()
                            if isinstance(results, list):
                                for res in results:
                                    lrc = res.get("syncedLyrics") or res.get("plainLyrics", "")
                                    if lrc:
                                        break

            # 3. Ultimate Fallback: gunakan pustaka syncedlyrics untuk mencari di Musixmatch, NetEase, dll.
            if not lrc:
                logger.info(
                    "lyrics_lrclib_fallback",
                    category=LC_EXTERNAL,
                )
                logger.info(
                    "lyrics_syncedlyrics_query",
                    category=LC_EXTERNAL,
                    search_query=search_query,
                )
                import syncedlyrics  # lazy import — modul besar, hanya dipakai di fallback terakhir ini

                loop = asyncio.get_running_loop()
                try:
                    lrc = await asyncio.wait_for(
                        loop.run_in_executor(None, syncedlyrics.search, search_query), timeout=5.0
                    )
                except TimeoutError:
                    logger.warning(
                        "lyrics_syncedlyrics_timeout", category=LC_EXTERNAL, timeout_seconds=5.0
                    )
                    lrc = None

            if self._current_generation == gen:
                if lrc:
                    from plugins.lyrics_parser import LyricsParser

                    self.lyrics_data = LyricsParser.parse_lrc(lrc)
                    # LOW-07 fix: Store CLEAN lines (no timestamps) for display
                    self.state.lyrics_lines = [text for _, text in self.lyrics_data]
                    self.state.lyrics_timestamps = [t for t, _ in self.lyrics_data]
                    await self._bus.publish(LyricsUpdatedEvent())
                    logger.info(
                        "lyrics_fetched",
                        category=LC_EXTERNAL,
                        line_count=len(self.lyrics_data),
                    )
                else:
                    logger.info("lyrics_not_found", category=LC_EXTERNAL)

        except Exception as e:
            if self._current_generation == gen:
                logger.debug(
                    "lyrics_fetch_failed",
                    category=LC_EXTERNAL,
                    error_type=type(e).__name__,
                    error=str(e),
                )
        finally:
            if self._current_generation == gen:
                self.state.lyrics_loading = False
                await self._bus.publish(LyricsUpdatedEvent())
