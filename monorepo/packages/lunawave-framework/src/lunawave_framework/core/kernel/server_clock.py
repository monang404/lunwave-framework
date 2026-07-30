"""
Module: lunawave_framework.core.kernel.server_clock

Purpose:
    Menyimpan waktu mulai server dan menghitung uptime, tanpa dependency
    apa pun di luar stdlib.

Responsibilities:
    - Simpan start_time (sekali, via init() atau lazy saat import).
    - Hitung uptime_seconds berdasarkan monotonic clock (tidak terpengaruh
      perubahan jam sistem).

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Thread-safe (baca angka float, tidak ada mutasi setelah init()).
"""

import time


class ServerClock:
    """Objek kecil untuk melacak waktu mulai server dan uptime-nya."""

    def __init__(self) -> None:
        self._start_monotonic: float = time.monotonic()
        self._start_wall: float = time.time()

    def init(self) -> None:
        """Reset titik awal waktu (dipanggil eksplisit dari main.py saat startup)."""
        self._start_monotonic = time.monotonic()
        self._start_wall = time.time()

    @property
    def start_time(self) -> float:
        """Wall-clock timestamp (epoch seconds) saat server mulai."""
        return self._start_wall

    @property
    def uptime_seconds(self) -> float:
        """Detik sejak server mulai, monoton naik (aman dari perubahan jam sistem)."""
        return time.monotonic() - self._start_monotonic


# Instance module-level default — cukup untuk sebagian besar pemakaian
# (di-wiring ke web.AppKey di server/app.py pada sesi 3).
server_clock = ServerClock()
