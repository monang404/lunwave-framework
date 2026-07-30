"""
Module: config

Purpose:
    Load and expose all environment-based runtime configuration constants
    for LunaWave, including paths, ports, and the admin password.

Responsibilities:
    - Resolve BASE_DIR, cache paths, and the mpv socket path from env vars.
    - Auto-generate a secure admin password on first run if none is set.
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

# Web Server
WEB_HOST = os.environ.get("LUNAWAVE_HOST", os.environ.get("YTGUI_HOST", "0.0.0.0"))
WEB_PORT = int(os.environ.get("LUNAWAVE_PORT", os.environ.get("YTGUI_PORT", 8765)))

# Web Security
ADMIN_USERNAME = os.environ.get("LUNAWAVE_ADMIN_USER", os.environ.get("YTGUI_ADMIN_USER", "admin"))

IS_PASSWORD_AUTO_GENERATED = False
_password_file = BASE_DIR / "cache" / "admin_password.txt"

if "LUNAWAVE_ADMIN_PASS" in os.environ:
    _raw_env_pass = os.environ["LUNAWAVE_ADMIN_PASS"]
elif "YTGUI_ADMIN_PASS" in os.environ:
    _raw_env_pass = os.environ["YTGUI_ADMIN_PASS"]
else:
    _raw_env_pass = None

if _raw_env_pass is not None:
    if _raw_env_pass.startswith("pbkdf2:sha256:"):
        # Sudah di-hash sebelumnya (misalnya dari file yang di-backup)
        ADMIN_PASSWORD = _raw_env_pass
    else:
        # TASK-1.2: Hash password ENV var agar tidak disimpan sebagai plaintext.
        # Ini wajib setelah TASK-1.1 menghapus plaintext fallback di verify_password.
        from core.security import hash_password

        ADMIN_PASSWORD = hash_password(_raw_env_pass)
else:
    IS_PASSWORD_AUTO_GENERATED = True
    if _password_file.exists():
        with open(_password_file, encoding="utf-8") as f:
            ADMIN_PASSWORD = f.read().strip()
    else:
        # Generate random password
        import secrets

        from core.security import hash_password

        raw_password = secrets.token_urlsafe(12)
        ADMIN_PASSWORD = hash_password(raw_password)
        _password_file.parent.mkdir(parents=True, exist_ok=True)
        with open(_password_file, "w", encoding="utf-8") as f:
            f.write(ADMIN_PASSWORD)
        try:
            import stat

            _password_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

        print("\\n==========================================")
        print(f"PASSWORD ADMIN GENERATED: {raw_password}")
        print("Harap simpan password ini! Tidak akan ditampilkan lagi.")
        print("==========================================\\n")
