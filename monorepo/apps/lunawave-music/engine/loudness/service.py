"""
Module: engine.loudness.service

Purpose:
    Orkestrasi analisis loudness: cek apakah track sudah pernah diukur,
    kalau belum -> ukur via LoudnessAnalyzer lalu simpan ke DB.

Responsibilities:
    - analyze_and_store(): idempotent, aman dipanggil berkali-kali untuk
      track yang sama (skip kalau sudah ada loudness_lufs).

Depends on:
    - core.ports
    - engine.loudness.analyzer

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async); kerja berat ffmpeg didelegasikan ke ThreadPoolExecutor.
"""

import asyncio
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import structlog

from core.log_categories import LC_PERSISTENCE, LC_SYSTEM
from core.ports import TrackRepositoryPort
from engine.loudness.analyzer import LoudnessAnalyzer

logger = structlog.get_logger(component="playback.loudness_service")


def _is_charging_or_unknown() -> bool:
    """Fail-open charging check for loudness batch analysis (PERF-6/PD-6).

    Returns True (boleh jalan) kalau `termux-battery-status` tidak ada
    (non-Termux/dev machine), kalau parsing gagal, atau kalau field yang
    diharapkan tidak dikenali -- gating ini hanya untuk hemat baterai di
    Termux, bukan sesuatu yang boleh memblokir analisis di environment lain.
    """
    binary = shutil.which("termux-battery-status")
    if not binary:
        return True

    try:
        result = subprocess.run([binary], capture_output=True, text=True, timeout=5, shell=False)
        data = json.loads(result.stdout)
        # Output resmi termux-battery-status: field "status" bernilai salah
        # satu dari "CHARGING" / "DISCHARGING" / "NOT_CHARGING" / "FULL".
        status = data.get("status")
        if status is None:
            return True  # field tidak dikenali -- fail-open
        return status == "CHARGING"
    except Exception as e:
        logger.debug(
            "termux_battery_status_check_failed",
            category=LC_SYSTEM,
            error_type=type(e).__name__,
            error=str(e),
        )
        return True


class LoudnessService:
    def __init__(self, db: TrackRepositoryPort, executor: ThreadPoolExecutor | None = None):
        self.db = db
        self.analyzer = LoudnessAnalyzer()
        # max_workers=1 sengaja dibatasi -- ffmpeg loudnorm analysis itu
        # CPU-heavy, dan salah satu target platform (Termux/Android) punya
        # CPU terbatas (lihat docs/CONSTRAINTS.md). Satu analisis background
        # dalam satu waktu sudah cukup, tidak perlu paralel.
        self._executor = executor or ThreadPoolExecutor(max_workers=1)

    async def analyze_and_store(self, video_id: str, uri: str) -> None:
        """Idempotent -- aman dipanggil tiap kali track dimuat. Kalau sudah
        pernah dianalisis (both lufs AND true_peak tersedia), langsung return."""
        row = await self.db.get_track(video_id)
        if row and row.loudness_lufs is not None and row.true_peak_dbtp is not None:
            return  # Sudah pernah diukur lengkap, tidak perlu ulang

        loop = asyncio.get_running_loop()
        # _is_charging_or_unknown() memanggil subprocess.run(...) secara
        # blocking (sampai 5s timeout). LunaWave single-process asyncio --
        # kalau ini dipanggil langsung di sini, seluruh event loop (WS, HTTP,
        # broadcast progress) ikut freeze, bukan cuma task loudness ini.
        # Delegasikan ke executor yang sama seperti measure_sync di bawah.
        is_charging_or_unknown = await loop.run_in_executor(self._executor, _is_charging_or_unknown)
        if not is_charging_or_unknown:
            return  # Tidak charging -- ditunda, coba lagi di play berikutnya

        measurement = await loop.run_in_executor(self._executor, self.analyzer.measure_sync, uri)
        if measurement is None:
            return  # Analisis gagal -- diam saja, coba lagi di play berikutnya

        try:
            await self.db.set_loudness(video_id, measurement.lufs, measurement.true_peak)
        except Exception as e:
            logger.warning(
                "loudness_save_failed",
                category=LC_PERSISTENCE,
                video_id=video_id,
                error_type=type(e).__name__,
                error=str(e),
            )
