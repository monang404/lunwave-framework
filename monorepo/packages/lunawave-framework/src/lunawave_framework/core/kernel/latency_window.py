"""
Module: lunawave_framework.core.kernel.latency_window

Purpose:
    Rolling window durasi (detik) untuk menghitung percentile ke-n dari
    N sample terakhir. Dipakai untuk threshold adaptif yang bereaksi ke
    kondisi jaringan aktual, bukan angka statis.

Responsibilities:
    - Simpan maksimal `maxlen` durasi terakhir.
    - Hitung percentile dengan fallback default kalau sample belum cukup.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Tidak thread-safe untuk akses konkuren dari banyak coroutine yang
    menulis bersamaan — dipakai di satu writer (CacheResolver.resolve())
    per instance, sesuai pola single-writer yang sudah ada di project ini.
"""

from collections import deque


class LatencyWindow:
    def __init__(self, maxlen: int = 20):
        self._samples: deque[float] = deque(maxlen=maxlen)

    def record(self, duration_sec: float) -> None:
        if duration_sec >= 0:
            self._samples.append(duration_sec)

    def percentile(self, p: int, default: float) -> float:
        """Kembalikan `default` kalau sample < 5 (belum cukup data untuk
        percentile yang berarti)."""
        if len(self._samples) < 5:
            return default
        ordered = sorted(self._samples)
        idx = min(int(len(ordered) * p / 100), len(ordered) - 1)
        return ordered[idx]

    def sample_count(self) -> int:
        return len(self._samples)
