"""
Module: engine.download_manager

Purpose:
    Handle the CMD_DOWNLOAD command by downloading the current or specified
    track via yt-dlp and moving it to the downloads/ folder.

Responsibilities:
    - Guard against concurrent downloads with an asyncio.Lock.
    - Report progress via DownloadProgressEvent and completion via
      DownloadCompleteEvent.

Depends on:
    - core.command_bus
    - core.event_bus
    - core.events
    - core.ports
    - core.state
    - core.task_utils

Subscribes to:
    CMD_DOWNLOAD

Publishes:
    LogMessageEvent, DownloadCompleteEvent, DownloadProgressEvent

Thread Safety:
    Worker thread (async with lock; progress hook runs in thread executor).
"""

import asyncio
import secrets
import time

import structlog

from core.command_bus import CMD_CANCEL_DOWNLOAD, CMD_DOWNLOAD
from core.events import DownloadCompleteEvent, LogMessageEvent
from core.log_categories import LC_DOWNLOAD
from core.log_context import bind_correlation
from core.state import TrackInfo
from core.task_utils import safe_create_task

logger = structlog.get_logger(component="download.manager")


class DownloadManager:
    def __init__(self, event_bus, state, ytdlp, command_bus=None):
        self.bus = event_bus
        self.state = state
        self.ytdlp = ytdlp
        self._command_bus = command_bus
        self._download_lock = asyncio.Lock()
        # RACE-FIX: `_download_lock.locked()` saja tidak cukup untuk menolak
        # trigger download kedua, karena lock itu baru benar-benar ter-acquire
        # saat task `_do_download` MULAI JALAN (bukan saat dijadwalkan lewat
        # safe_create_task). Antara dua trigger download() yang datang beruntun
        # cepat (mis. klik tombol dobel, atau klik + shortcut keyboard di message
        # WS yang berbeda tapi diproses berdekatan), _on_download() bisa
        # dipanggil dua kali sebelum task pertama sempat berjalan sama sekali --
        # keduanya lolos cek .locked() dan sama-sama menjadwalkan _do_download(),
        # sehingga file yang sama ter-download dua kali secara berurutan.
        # Flag ini di-set SINKRON (tanpa ada `await` di antaranya) tepat sebelum
        # task dijadwalkan, sehingga trigger kedua langsung tertolak walau task
        # pertama belum sempat jalan sama sekali.
        self._download_scheduled = False

        self._command_bus.register(CMD_DOWNLOAD, self._on_download)
        self._command_bus.register(CMD_CANCEL_DOWNLOAD, self._on_cancel_download)

    async def _on_download(self, track: TrackInfo | None = None):
        target = track or self.state.current_track
        if not target:
            await self.bus.publish(
                LogMessageEvent(message="Tidak ada lagu yang dipilih untuk di-download")
            )
            return

        if target.local_path:
            await self.bus.publish(LogMessageEvent(message="Lagu sudah tersimpan lokal"))
            return

        if self._download_lock.locked() or self._download_scheduled:
            await self.bus.publish(
                LogMessageEvent(message="Download sedang berjalan, tunggu selesai.")
            )
            return

        self._download_scheduled = True
        # L5.4: correlation_id baru di titik mulai download, dibind di sini.
        # _do_download() dijadwalkan sebagai task terpisah via
        # safe_create_task()/asyncio.create_task -- yang secara otomatis
        # mewarisi (copy) context yang sudah dibind ini (sama seperti pola
        # session_id/request_id L5.1/L5.2), jadi TIDAK perlu parameter
        # tambahan di _do_download() (non-breaking terhadap signature yang
        # sudah dipakai test mocking).
        correlation_id = secrets.token_hex(4)
        bind_correlation(correlation_id)
        safe_create_task(self._do_download(target), name=f"download_{target.video_id}")

    async def _on_cancel_download(self, _data=None):
        """PATCH-2026-07-27: `ytdlp.cancel_download()` sudah ada di adapter
        (dipakai untuk cleanup internal), tapi sebelum ini tidak ada jalur
        command dari UI untuk memicunya -- ws_download.py cuma expose
        "download" dan "delete_download". Ini menyambungkan yang sudah ada,
        bukan menambah mekanisme cancel baru: set `is_cancelled = True` di
        adapter, dicek oleh `_check_cancel_hook` pada progress-hook
        berikutnya (dipanggil yt-dlp dari thread executor), yang raise
        Exception("DownloadCancelled") -- balik ke _do_download() lewat
        `except Exception` di bawah, di mana kita bedakan pesannya dari
        error generik."""
        if not self._download_lock.locked():
            await self.bus.publish(
                LogMessageEvent(message="Tidak ada download yang sedang berjalan untuk dibatalkan")
            )
            return
        self.ytdlp.cancel_download()
        await self.bus.publish(LogMessageEvent(message="Membatalkan download..."))

    async def _do_download(self, track: TrackInfo):
        # L5.4: baca correlation_id yang sudah diwariskan via context dari
        # _on_download() -- TIDAK generate baru di sini (anti-pattern
        # §12.9). Dipakai di bawah untuk diteruskan eksplisit ke progress
        # hook, karena hook itu dipanggil yt-dlp dari thread executor
        # terpisah dan contextvars tidak menyeberang thread secara
        # otomatis.
        correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")
        async with self._download_lock:
            start_time = time.perf_counter()
            logger.info(
                "download_started",
                category=LC_DOWNLOAD,
                video_id=track.video_id,
            )
            try:
                self.state.download_progress = 0.0
                await self.bus.publish(LogMessageEvent(message=f"Memulai download: {track.title}"))

                loop = asyncio.get_running_loop()

                def sync_progress_hook(d):
                    if d.get("status") == "downloading":
                        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
                        downloaded_bytes = d.get("downloaded_bytes", 0)
                        if total_bytes and total_bytes > 0:
                            percent = downloaded_bytes / total_bytes
                            # L5.4: progress hook ini dipanggil yt-dlp dari
                            # thread executor terpisah (bukan asyncio task)
                            # -- contextvars TIDAK menyeberang thread secara
                            # otomatis, jadi correlation_id WAJIB diteruskan
                            # eksplisit sebagai argumen, bukan mengandalkan
                            # context (anti-pattern §12.9: juga bukan
                            # generate correlation_id baru di titik ini).
                            loop.call_soon_threadsafe(
                                self._update_progress, percent, correlation_id
                            )

                local_path = await self.ytdlp.download_audio(
                    track.video_id, on_progress=sync_progress_hook
                )

                import re
                import shutil
                from pathlib import Path

                from config import DOWNLOAD_DIR

                downloads_dir = DOWNLOAD_DIR
                downloads_dir.mkdir(parents=True, exist_ok=True)
                safe_artist = re.sub(r'[\\/*?:"<>|]', "", track.artist)
                safe_title = re.sub(r'[\\/*?:"<>|]', "", track.title)
                # Preserve real extension (may be .opus, .m4a, .webm, etc.)
                real_ext = Path(local_path).suffix  # e.g. ".opus" or ".m4a"
                user_path = downloads_dir / f"{safe_artist} - {safe_title}{real_ext}"

                if user_path.exists():
                    try:
                        user_path.unlink()
                    except Exception as e:
                        logger.warning(
                            "download_existing_path_remove_failed",
                            category=LC_DOWNLOAD,
                            user_path=str(user_path),
                            error_type=type(e).__name__,
                            error=str(e),
                        )

                shutil.move(local_path, user_path)

                track.local_path = str(user_path)
                self.state.download_progress = None

                duration_ms = round((time.perf_counter() - start_time) * 1000)
                try:
                    file_bytes = user_path.stat().st_size
                except OSError:
                    file_bytes = None
                logger.info(
                    "download_completed",
                    category=LC_DOWNLOAD,
                    video_id=track.video_id,
                    bytes=file_bytes,
                    duration_ms=duration_ms,
                )

                await self.bus.publish(
                    LogMessageEvent(
                        message=f"Download sukses: {track.title} (Tersimpan di folder 'downloads')"
                    )
                )
                await self.bus.publish(DownloadCompleteEvent(track=track))

            except Exception as e:
                self.state.download_progress = None
                is_cancelled = str(e) == "DownloadCancelled"
                logger.info(
                    "download_cancelled",
                    category=LC_DOWNLOAD,
                    video_id=track.video_id,
                ) if is_cancelled else logger.error(
                    "download_failed",
                    category=LC_DOWNLOAD,
                    video_id=track.video_id,
                    error_type=type(e).__name__,
                    error=str(e),
                    exc_info=True,
                )
                await self.bus.publish(
                    LogMessageEvent(
                        message=f"Download dibatalkan: {track.title}"
                        if is_cancelled
                        else f"Download gagal: {str(e)}"
                    )
                )
            finally:
                self._download_scheduled = False

    def _update_progress(self, percent: float, correlation_id: str | None = None):
        # L5.4: dijalankan via loop.call_soon_threadsafe() dari progress
        # hook -- rebind correlation_id yang diteruskan eksplisit dari
        # _do_download() sebelum menjadwalkan task publish di bawah, supaya
        # log dari task publish itu ikut membawa correlation_id yang sama.
        if correlation_id:
            bind_correlation(correlation_id)
        self.state.download_progress = percent
        from core.events import DownloadProgressEvent

        safe_create_task(
            self.bus.publish(DownloadProgressEvent(progress=percent)), name="pub_dl_prog"
        )
