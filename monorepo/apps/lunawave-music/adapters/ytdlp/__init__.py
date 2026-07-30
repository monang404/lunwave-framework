"""
Module: adapters.ytdlp

Purpose:
    Unified client for interacting with yt-dlp for search, extraction, and downloading.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - adapters.ytdlp.downloader
    - adapters.ytdlp.resolver
    - adapters.ytdlp.searcher

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import os
from concurrent.futures import ThreadPoolExecutor

from adapters.ytdlp.downloader import YtDlpDownloader
from adapters.ytdlp.resolver import YtDlpResolver
from adapters.ytdlp.searcher import YtDlpSearcher


def _set_worker_priority():
    """ThreadPoolExecutor initializer -- jalan sekali per worker thread saat
    thread itu pertama kali dibuat (bukan per job). Menurunkan prioritas CPU
    worker yt-dlp (search/extract/resolve/download, semua dibungkus lewat
    executor yang sama) supaya tidak bersaing dengan playback MPV.

    Pakai os.setpriority(PRIO_PROCESS, 0, N) -- ABSOLUT, bukan os.nice() yang
    relatif/kumulatif (PD-6b) -- walau di sini sudah cukup sekali per thread
    lifetime lewat initializer, tetap absolut supaya aman kalau titik
    pemanggilan ini nanti berubah. Fail-safe: AttributeError (platform tidak
    dukung) / PermissionError (tidak diizinkan) ditelan diam-diam, tidak
    pernah raise -- initializer yang raise akan membuat seluruh worker
    thread gagal dibuat.
    """
    if os.name == "nt":
        return
    try:
        os.setpriority(os.PRIO_PROCESS, 0, 10)
    except (AttributeError, PermissionError):
        pass


class YtDlpClient:
    """Facade — API identik dengan engine/ytdlp_client.py lama."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=4, initializer=_set_worker_priority)
        self._searcher = YtDlpSearcher(self._executor)
        self._resolver = YtDlpResolver(self._executor)
        self._downloader = YtDlpDownloader(self._executor)

    async def search(self, *a, **kw):
        return await self._searcher.search(*a, **kw)

    async def extract_info(self, *a, **kw):
        return await self._searcher.extract_info(*a, **kw)

    async def get_stream_url(self, *a, **kw):
        return await self._resolver.get_stream_url(*a, **kw)

    async def download_audio(self, *a, **kw):
        return await self._downloader.download_audio(*a, **kw)

    def cancel_download(self):
        self._downloader.cancel_download()

    def close(self):
        self._executor.shutdown(wait=False)
