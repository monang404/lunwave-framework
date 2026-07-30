"""
Module: bootstrap.services

Purpose:
    Stage 1 of application startup: open the DB, connect core adapters
    (MPV, yt-dlp), and wire every domain service used by the rest of the
    app (resolver, playback controller, radio, volume, sleep timer, etc).
    Extracted from main.py's `main()` (T2.4, section "1-6" of the original
    God Function) without changing call order.

Inputs:
    None (reads config via the modules it wires).

Outputs:
    A populated `BootstrapContext` (module-level singleton `context`)
    consumed by bootstrap.startup_tasks, bootstrap.maintenance, and
    main.py's server/shutdown stage.

Side Effects:
    Opens SQLite DB, spawns/attaches mpv IPC client, opens shared HTTP
    session, starts Termux now-playing integration.

CLI:
    None (imported by main.py).

Responsibilities:
    - Build and hold every long-lived service object needed at runtime.
    - Seed admin_account from an explicit env var override (K4, T-B14.2)
      when the table is still empty -- non-default provisioning path only,
      never overwrites an existing account.

Depends on:
    - persistence
    - adapters.mpv
    - adapters.ytdlp
    - plugins.notifications
    - plugins.lyrics_fetcher
    - plugins.sponsorblock
    - persistence.stream_cache
    - engine.loudness.service
    - engine.playback.controller
    - engine.queue_manager
    - engine.radio
    - engine.volume_service
    - engine.sleep_timer
    - engine.command_router
    - engine.download_manager
    - core.event_bus
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import shutil

import aiohttp
import structlog

from adapters.mpv import MpvController
from adapters.ytdlp import YtDlpClient
from core.command_bus import CommandBus
from core.event_bus import bus
from core.log_categories import LC_AUTH, LC_EXTERNAL
from core.state import AppState, PlayerStatus
from engine.command_router import CommandRouter
from engine.download_manager import DownloadManager
from persistence import Repositories
from plugins.lyrics_fetcher import LyricsFetcher
from plugins.notifications import TermuxNowPlaying
from plugins.sponsorblock import SponsorBlockHandler

logger = structlog.get_logger(component="system.services")


class BootstrapContext:
    """Holds every service built during startup so later bootstrap stages
    (startup_tasks, maintenance) and main.py's shutdown block can reach
    them without re-wiring. Populated once by `init_core_services()`."""

    def __init__(self):
        from lunawave_framework.core.bootstrap.lifecycle import LifecycleManager

        self.state: AppState | None = None
        self.mpv_ready_event: asyncio.Event | None = None
        self.repos = None
        self.mpv = None
        self.ytdlp = None
        self.http_session: aiohttp.ClientSession | None = None
        self.resolver = None
        self.sponsorblock = None
        self.lyrics_fetcher = None
        self.loudness_service = None
        self.queue_mode = None
        self.radio_mode = None
        self.volume_service = None
        self.playback_controller = None
        self.sleep_timer = None
        self.download_manager = None
        self.command_bus = None
        self.command_router = None
        self.nowplaying = None
        self.lifecycle = LifecycleManager()


# Module-level singleton — main.py's four bootstrap calls all operate on
# this shared context, mirroring the local variables the original God
# Function used to close over.
context = BootstrapContext()


async def _init_mpv():
    """Background task: connect MPV, signal `mpv_ready_event` either way
    (success or failure) so `_resume_last_track` never hangs waiting."""
    ctx = context

    if shutil.which("mpv") is None:
        logger.critical(
            "mpv_initial_connect_failed",
            category=LC_EXTERNAL,
            reason="executable_not_found",
        )
        ctx.state.error_msg = (
            "MPV tidak ditemukan. Jalankan: pkg install mpv (Termux) "
            "atau install MPV dan tambahkan ke PATH (Windows/Linux)."
        )
        ctx.state.status = PlayerStatus.ERROR
        ctx.mpv_ready_event.set()
        return

    try:
        await ctx.mpv.connect()
        ctx.mpv_ready_event.set()
    except Exception as e:
        logger.critical(
            "mpv_initial_connect_failed",
            category=LC_EXTERNAL,
            error_type=type(e).__name__,
            error=str(e),
        )
        ctx.state.error_msg = (
            "MPV tidak ditemukan. Jalankan: pkg install mpv (Termux) "
            "atau install MPV dan tambahkan ke PATH (Windows/Linux)."
        )
        ctx.state.status = PlayerStatus.ERROR
        ctx.mpv_ready_event.set()  # set juga saat error agar resume tidak hang


async def _seed_admin_account_from_env(repos):
    """T-B14.2 (K4): satu-satunya konsumen dari config.ADMIN_PASSWORD_OVERRIDE.

    admin_account (SQLite) adalah source of truth untuk login (T-B13.1).
    Jalur normal untuk mengisinya adalah wizard Initial Setup di browser
    (server/handlers/setup.py). Helper ini hanya jalur *override* eksplisit
    untuk provisioning non-interaktif (CI, automated deploy) yang tidak
    bisa lewat browser.

    Perilaku, sesuai K3 (tidak ada migrasi otomatis / overwrite diam-diam)
    dan K4 (override dipertahankan, non-default, terpisah dari auto-generate
    yang sudah dihapus di T-B14.1):
      - Kalau admin_account SUDAH ADA -> tidak melakukan apa-apa, walau
        ADMIN_PASSWORD_OVERRIDE di-set. Tidak pernah overwrite akun existing.
      - Kalau admin_account KOSONG dan ADMIN_PASSWORD_OVERRIDE TIDAK di-set
        -> tidak melakukan apa-apa. Instalasi baru tetap diarahkan ke
        Initial Setup seperti biasa (perilaku default, tanpa env var).
      - Kalau admin_account KOSONG dan ADMIN_PASSWORD_OVERRIDE di-set ->
        seed satu baris admin_account dari config.ADMIN_USERNAME +
        ADMIN_PASSWORD_OVERRIDE (sudah ter-hash oleh config.py).
    """
    from config import ADMIN_PASSWORD_OVERRIDE, ADMIN_USERNAME

    if ADMIN_PASSWORD_OVERRIDE is None:
        return
    if await repos.admin_account.admin_account_exists():
        logger.info(
            "admin_account_seed_skipped_already_exists",
            category=LC_AUTH,
            reason="ADMIN_PASSWORD_OVERRIDE env var di-set tapi admin_account "
            "sudah ada -- tidak di-overwrite (K3).",
        )
        return
    await repos.admin_account.create_admin_account(ADMIN_USERNAME, ADMIN_PASSWORD_OVERRIDE)
    logger.info(
        "admin_account_seeded_from_env",
        category=LC_AUTH,
        username=ADMIN_USERNAME,
        reason="admin_account kosong + ADMIN_PASSWORD_OVERRIDE di-set (K4, "
        "jalur provisioning non-interaktif, bukan alur default).",
    )


async def init_core_services() -> BootstrapContext:
    """Bootstrap stage 1: DB, MPV, yt-dlp, shared HTTP session, and every
    domain service (resolver, playback controller, radio, volume, sleep
    timer, download manager, command router, now-playing integration).
    Mirrors steps 1-6 of the original main() God Function verbatim."""
    ctx = context
    ctx.state = AppState()

    # Event untuk koordinasi: _resume_last_track menunggu MPV selesai connect
    # tanpa memblok run_server — browser bisa akses UI sementara kedua task jalan.
    ctx.mpv_ready_event = asyncio.Event()

    # 1. Inisialisasi DB (server membutuhkan DB, jadi ini tetap blocking)
    print("  [1/5] Membuka database...")
    ctx.repos = Repositories()
    ctx.mpv = MpvController()
    await ctx.repos.init()
    # T-B14.2 (K4): seed admin_account dari env var override, hanya kalau
    # tabel masih kosong. No-op kalau ADMIN_PASSWORD_OVERRIDE tidak di-set
    # atau admin_account sudah ada -- lihat docstring _seed_admin_account_from_env.
    await _seed_admin_account_from_env(ctx.repos)

    # 2. Initialize Core Engine (YtDlpClient ringan — hanya buat ThreadPoolExecutor)
    print("  [2/5] Menginisialisasi YT-DLP Engine...")
    ctx.ytdlp = YtDlpClient()

    print("  [3/5] Menyiapkan layanan playback...")
    print("  (Audio player dihubungkan di background — server akan listen duluan)")

    # 3. Shared HTTP session
    ctx.http_session = aiohttp.ClientSession()

    # 4. Global Services Initialization
    from engine.loudness.service import LoudnessService
    from engine.playback.controller import PlaybackController
    from engine.queue_manager import QueueMode
    from engine.radio import RadioMode
    from engine.sleep_timer import SleepTimer
    from engine.volume_service import VolumeService
    from persistence.stream_cache import CacheResolver, ResolverDbCompat

    ctx.command_bus = CommandBus()

    ctx.resolver = CacheResolver(
        ResolverDbCompat(ctx.repos.tracks, ctx.repos.artists, ctx.repos.discover), ctx.ytdlp
    )

    ctx.sponsorblock = SponsorBlockHandler(
        ctx.mpv, state=ctx.state, session=ctx.http_session, event_bus=bus
    )
    ctx.lyrics_fetcher = LyricsFetcher(ctx.state, session=ctx.http_session, event_bus=bus)
    ctx.loudness_service = LoudnessService(ctx.repos.tracks)

    ctx.queue_mode = QueueMode()
    ctx.radio_mode = RadioMode(
        ctx.ytdlp, ctx.state, artists=ctx.repos.artists, library=ctx.repos.library
    )

    ctx.volume_service = VolumeService(bus, ctx.mpv, ctx.state)
    ctx.playback_controller = PlaybackController(
        bus,
        ctx.state,
        ctx.mpv,
        ctx.resolver,
        ctx.sponsorblock,
        ctx.lyrics_fetcher,
        ctx.queue_mode,
        ctx.radio_mode,
        ctx.loudness_service,
    )

    ctx.sleep_timer = SleepTimer(bus, ctx.command_bus)

    ctx.download_manager = DownloadManager(bus, ctx.state, ctx.ytdlp, ctx.command_bus)
    ctx.command_router = CommandRouter(
        ctx.playback_controller, ctx.volume_service, ctx.sleep_timer, ctx.command_bus
    )

    # Termux now-playing notification (no-op outside Termux)
    ctx.nowplaying = TermuxNowPlaying(bus, ctx.state, ctx.command_bus)
    await ctx.nowplaying.start()

    return ctx
