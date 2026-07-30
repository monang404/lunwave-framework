"""
Module: engine.playback.circuit_breaker

Purpose:
    Circuit breaker eksplisit lintas-track untuk PlaybackController --
    menggantikan counter integer implisit yang sebelumnya hidup langsung
    di controller dengan state machine bernama, tanpa mengubah behavior
    lama sedikit pun.

Responsibilities:
    - Menghitung kegagalan play_track BERTURUT-TURUT (track apapun, bukan
      retry pada track yang sama).
    - Membuka (OPEN) setelah `threshold` kegagalan beruntun, menutup
      kembali (CLOSED) begitu ada satu track yang berhasil play atau saat
      _on_stop.

Depends on:
    - (tidak ada dependency internal repo -- murni stdlib `enum`)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Tidak thread-safe secara internal (tidak ada lock) -- dipanggil dari
    context yang sudah dilindungi lock milik PlaybackController, sama
    seperti counter lama yang digantikannya.
"""

from enum import Enum, auto


class BreakerState(Enum):
    CLOSED = auto()  # normal, boleh advance ke track berikutnya
    OPEN = auto()  # berhenti total, tidak boleh advance otomatis


class PlaybackCircuitBreaker:
    """Circuit breaker lintas-track: menghitung kegagalan play_track
    BERTURUT-TURUT (track apapun), bukan retry per-track yang sama.
    Dibuka (OPEN) setelah `threshold` kegagalan beruntun."""

    def __init__(self, threshold: int = 3):
        self._threshold = threshold
        self._consecutive_failures = 0
        self.state = BreakerState.CLOSED

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self.state = BreakerState.CLOSED

    def record_failure(self) -> bool:
        """Return True jika breaker baru saja OPEN akibat kegagalan ini."""
        if self.state is BreakerState.OPEN:
            return False
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self.state = BreakerState.OPEN
            return True
        return False

    def can_advance(self) -> bool:
        return self.state is BreakerState.CLOSED
