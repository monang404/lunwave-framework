"""
Module: engine.loudness.gain_calculator

Purpose:
    Hitung gain (dB) yang perlu diterapkan ke sebuah track supaya loudness-nya
    mendekati target, berdasarkan hasil pengukuran integrated loudness (LUFS)
    dan true peak (dBTP).

Responsibilities:
    - compute_gain_db(): hitung gain dari LUFS terukur, di-clamp ke batas aman
      DAN dibatasi agar true peak setelah boost tidak melewati -1 dBTP.
    - build_af_filter(): bentuk string filter MPV/ffmpeg dengan limiter sebagai
      safety net kedua (alimiter=limit=-1dB).

Depends on:
    None (stateless, semua nilai masuk sebagai argumen)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless — aman dipanggil dari mana saja.
"""

TARGET_LUFS = -14.0  # Sama seperti Spotify/YouTube Music
MAX_BOOST_DB = 8.0  # Clamp atas — sebelum true-peak check
MAX_CUT_DB = 12.0  # Clamp bawah — lagu yang sudah kenceng dipotong maksimal segini
HEADROOM_DBTP = -1.0  # True-peak ceiling industri standar (-1 dBTP)


def compute_gain_db(
    measured_lufs: float | None,
    true_peak_dbtp: float | None = None,
    target_lufs: float = TARGET_LUFS,
    max_boost_db: float = MAX_BOOST_DB,
    max_cut_db: float = MAX_CUT_DB,
    headroom_dbtp: float = HEADROOM_DBTP,
) -> float:
    """Hitung gain (dB). None (belum dianalisis) -> 0.0 (passthrough, tidak
    ada normalisasi -- ini keputusan sengaja, bukan default sembarangan).

    Dua lapis proteksi clipping:
    1. Clamp statis ±MAX dB (lapis lama, tetap dipertahankan sebagai batas kasar).
    2. True-peak clamp: pastikan measured_tp + gain <= HEADROOM_DBTP (-1 dBTP).
       Ini menggunakan data yang sudah dihitung ffmpeg secara gratis (H-3).
       Jika true_peak tidak tersedia (track lama belum dianalisis ulang), hanya
       clamp statis yang aktif — backward-compatible, tidak ada regresi.
    """
    if measured_lufs is None:
        return 0.0
    gain = target_lufs - measured_lufs
    # Lapis 1: clamp statis
    gain = max(-max_cut_db, min(max_boost_db, gain))
    # Lapis 2: true-peak headroom (gratis — data sudah ada dari ffmpeg H-3)
    if true_peak_dbtp is not None:
        max_safe_gain = headroom_dbtp - true_peak_dbtp
        gain = min(gain, max_safe_gain)
    return gain


def build_af_filter(gain_db: float) -> str:
    """Bentuk string untuk property `af` MPV. gain_db=0.0 tetap menghasilkan
    filter eksplisit (bukan string kosong) supaya SELALU meng-override filter
    dari track sebelumnya -- MPV adalah proses persisten yang di-reuse antar
    track (loadfile replace), `af` TIDAK otomatis reset sendiri.

    Safety net kedua: alimiter (soft brick-wall limiter) di ujung chain mencegah
    clipping keras bahkan jika kombinasi gain + volume user melewati 0 dBFS.
    - level=disabled: jangan normalisasi ulang level output (hanya limiter saja)
    - limit=-1dB: ceiling sedikit di bawah 0 dBFS sebagai buffer aman
    """
    return f"lavfi=[volume={gain_db:.2f}dB,alimiter=limit=-1dB:level=disabled]"
