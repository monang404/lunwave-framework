"""
Module: config

Purpose:
    Load and expose all environment-based runtime configuration constants
    for LunaWave, including paths, ports, and the admin password.

Responsibilities:
    - Resolve BASE_DIR, cache paths, and the mpv socket path from env vars.
    - Expose ADMIN_PASSWORD_OVERRIDE, a non-default env-var override consumed
      only by bootstrap.services for one-time admin_account seeding (K4).
      admin_account (SQLite) is the actual source of truth for login.
    - Validate the socket path stays within BASE_DIR on Unix.

Depends on:
    - core.security

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread only (module-level initialization at import time).

Notes:
    Changing env vars after this module is imported has no effect.
"""

import os
from pathlib import Path

# BASE_DIR defaults to the project root
# can be overridden by LUNAWAVE_BASE or YT_PLAYER_BASE env var
BASE_DIR = Path(
    os.environ.get("LUNAWAVE_BASE", os.environ.get("YT_PLAYER_BASE", Path(__file__).parent))
)

CACHE_DIR = BASE_DIR / "cache" / "mp3"
# User-facing "Download" feature (CMD_DOWNLOAD / download_manager.py) moves
# the finished file OUT of CACHE_DIR into here -- this is a separate,
# permanent folder from the transient streaming cache above, and is what the
# Settings UI's "Ukuran Cache" / clear-cache action should actually measure,
# since CACHE_DIR is emptied again right after each download completes.
DOWNLOAD_DIR = BASE_DIR / "downloads"
MAX_CACHE_SIZE_BYTES = int(os.environ.get("LUNAWAVE_CACHE_SIZE", 1073741824))  # 1 GB
DB_PATH = BASE_DIR / "data" / "lunawave.db"

# Handle Windows compatibility for Unix Sockets
if os.name == "nt":
    # Windows doesn't support Unix sockets natively in the same way,
    # mpv on Windows supports named pipes instead.
    # Defaulting to a named pipe for Windows testing.
    MPV_SOCKET = os.environ.get(
        "LUNAWAVE_SOCKET", os.environ.get("YT_PLAYER_SOCKET", r"\\.\pipe\mpv-lunawave")
    )
else:
    socket_dir = BASE_DIR / "cache" / "sockets"
    socket_dir.mkdir(parents=True, exist_ok=True)
    _raw_socket = os.environ.get(
        "LUNAWAVE_SOCKET", os.environ.get("YT_PLAYER_SOCKET", str(socket_dir / "mpv-lunawave.sock"))
    )
    _socket_path = Path(_raw_socket).resolve()
    _allowed_prefix = BASE_DIR.resolve()
    if not str(_socket_path).startswith(str(_allowed_prefix)):
        import warnings

        warnings.warn(
            f"LUNAWAVE_SOCKET '{_raw_socket}' di luar BASE_DIR — menggunakan default", stacklevel=2
        )
        _socket_path = socket_dir / "mpv-lunawave.sock"
    MPV_SOCKET = str(_socket_path)

DEFAULT_VOLUME = int(os.environ.get("YT_PLAYER_VOLUME", 80))
GAPLESS_PREBUFFER_SEC = 15
AUTOPLAY_THRESHOLD = 2
SPONSORBLOCK_CATS = ["sponsor", "intro", "outro", "selfpromo"]
LYRICS_API_BASE = "https://lrclib.net/api"
STREAM_URL_TTL_SEC = 21600
# PATCH-YTDLP-RESOLVE-TIMEOUT-01: yt-dlp.get_stream_url() sebelumnya tidak punya batas waktu
# sama sekali -> kalau network Termux lambat/flaky, proses bisa hang TANPA
# BATAS tanpa pernah throw exception, sehingga play_track() nyangkut
# selamanya di status LOADING tanpa ada sinyal error/idle ke UI (kelihatan
# seperti "stuck" tanpa pesan jelas). Timeout ini memaksa gagal cepat
# supaya error/retry-path yang sudah ada di play_track() bisa jalan.
YTDLP_RESOLVE_TIMEOUT_SEC = 25

# PATCH-2026-07-20-136: audio_stream_handler.serve_stream() sebelumnya
# langsung `response.prepare()` lalu proxy `iter_chunked` upstream ke client
# TANPA buffer sama sekali -- kalau upstream (YouTube CDN) lambat/tersendat
# di awal, client langsung ikut kena stutter karena tidak ada cushion data.
# Buffer sekitar 64KB (~4 detik audio di bitrate umum 128kbps) sebelum mulai
# nge-serve ke client; trade-off-nya time-to-first-byte sedikit lebih
# lambat, tapi playback awal jauh lebih halus di jaringan yang jelek/naik-
# turun. Untuk Range request pendek (seek dekat akhir file), buffer ini
# otomatis cuma berisi sisa data yang ada (loop pembacaan berhenti wajar).
STREAM_PREBUFFER_BYTES = 65536

# Adaptive prefetch
PREFETCH_DEFAULT_THRESHOLD_SEC = 30.0
PREFETCH_SAFETY_FACTOR = 1.5
PREFETCH_MIN_THRESHOLD_SEC = 10.0
PREFETCH_MAX_THRESHOLD_SEC = 60.0

# PATCH-2026-07-20-136: prefetch_stream_url() sebelumnya gagal 1x -> cuma
# di-log warning, tidak pernah dicoba ulang. Di jaringan lambat/tersendat
# sesaat, ini bikin prefetch sia-sia padahal percobaan kedua kemungkinan
# besar berhasil -- akibatnya transisi ke track berikutnya tetap kena jeda
# resolve on-demand seperti kalau prefetch tidak pernah ada. Retry ini
# HANYA untuk error transient (bukan VideoUnavailableError/RateLimitedError
# yang memang tidak akan pernah berhasil kalau diulang cepat).
PREFETCH_RETRY_ATTEMPTS = 2
PREFETCH_RETRY_BACKOFF_SEC = 1.0

LOUDNESS_ANALYZE_TIMEOUT_SEC = 25.0

# Web Server
WEB_HOST = os.environ.get("LUNAWAVE_HOST", os.environ.get("YTGUI_HOST", "0.0.0.0"))
WEB_PORT = int(os.environ.get("LUNAWAVE_PORT", os.environ.get("YTGUI_PORT", 8765)))

# Web Security
#
# T-B13.1: satu-satunya source of truth untuk kredensial login sekarang
# adalah tabel admin_account di SQLite (lihat server/handlers/auth.py,
# persistence/admin_account_repo.py), diisi lewat alur Initial Setup
# (server/handlers/setup.py). config.py TIDAK LAGI auto-generate password,
# TIDAK LAGI menulis cache/admin_password.txt, dan TIDAK LAGI mencetak
# banner password saat startup (T-B14.1) -- mekanisme lama itu menulis
# kredensial plaintext ke file cache tanpa proses konfirmasi/setup eksplisit
# apa pun.
ADMIN_USERNAME = os.environ.get("LUNAWAVE_ADMIN_USER", os.environ.get("YTGUI_ADMIN_USER", "admin"))

# ADMIN_PASSWORD_OVERRIDE (K4, T-B14.2): jalur non-default, dipertahankan
# khusus untuk provisioning non-interaktif (CI, automated deploy) yang
# tidak bisa lewat wizard Initial Setup di browser. HANYA dibaca satu kali
# oleh bootstrap.services._seed_admin_account_from_env() untuk mengisi
# admin_account SAAT TABEL MASIH KOSONG; tidak pernah dipakai langsung
# untuk verifikasi login (auth.py tidak mengimpor simbol ini), dan tidak
# pernah menimpa akun admin yang sudah ada (K3 -- tidak ada migrasi
# otomatis, tidak ada overwrite diam-diam).
_raw_env_pass = os.environ.get("LUNAWAVE_ADMIN_PASS", os.environ.get("YTGUI_ADMIN_PASS"))

if _raw_env_pass is not None:
    if _raw_env_pass.startswith("pbkdf2:sha256:"):
        # Sudah di-hash sebelumnya (misalnya dari secret manager / backup)
        ADMIN_PASSWORD_OVERRIDE: str | None = _raw_env_pass
    else:
        # TASK-1.2: Hash password ENV var agar tidak disimpan sebagai plaintext.
        from core.security import hash_password

        ADMIN_PASSWORD_OVERRIDE = hash_password(_raw_env_pass)
else:
    ADMIN_PASSWORD_OVERRIDE = None

DEBUG_EXPOSE_ERRORS = os.environ.get("LUNAWAVE_DEBUG_ERRORS", "0") == "1"
ALLOWED_STREAM_ORIGIN = os.environ.get("LUNAWAVE_ALLOWED_ORIGIN", "")
