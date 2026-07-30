"""
Module: music.domain.exceptions

Purpose:
    Define the custom exception hierarchy for LunaWave error conditions.

Responsibilities:
    - Provide typed exceptions for mpv connection, track resolution, and
      download failures that callers can catch independently.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""


class YtPlayerError(Exception):
    """Base exception for LunaWave."""

    pass


class MpvConnectionError(YtPlayerError):
    """Raised when unable to connect to the mpv IPC socket."""

    pass


class TrackResolutionError(YtPlayerError):
    """Raised when unable to resolve a track's stream URL or local path."""

    pass


class DownloadError(YtPlayerError):
    """Raised when yt-dlp fails to download a track."""

    pass


class VideoUnavailableError(TrackResolutionError):
    """Video dihapus/private/diblokir secara permanen -- retry tidak akan
    pernah berhasil untuk video_id ini, harus di-skip tanpa membakar jatah
    retry dan sebaiknya ditandai di DB agar tidak dicoba lagi di masa depan."""

    pass


class BotCheckError(TrackResolutionError):
    """YouTube meminta verifikasi login ("Sign in to confirm you're not a
    bot") untuk video_id ini. Retry dengan client/opsi yang sama tidak akan
    membantu -- butuh strategi berbeda (ganti player client, atau cookies)."""

    pass


class RateLimitedError(TrackResolutionError):
    """YouTube membatasi rate request (HTTP 429 / "Too Many Requests").
    Retry per-track langsung memperparah rate limit -- butuh cooldown
    global, bukan backoff per-track seperti error biasa."""

    pass
