"""
Module: adapters.ytdlp.ydl_options

Purpose:
    Shared utilities and constants for yt-dlp integration.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

YDL_OPTS_INFO = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "format": "bestaudio/best",
    "format_sort": ["abr", "asr"],
    "socket_timeout": 10,
    "extractor_retries": 1,
}

# PATCH-2026-07-20-136: dipakai YtDlpResolver sebagai percobaan KEDUA saat
# client default kena bot-check ("Sign in to confirm you're not a bot").
# Player client "android" sering bisa lolos bot-check yang menghalangi
# client web default, tanpa perlu cookies/login akun. Bukan solusi permanen
# (YouTube bisa menutup celah ini kapan saja), tapi mitigasi murah yang
# tidak butuh input user.
YDL_OPTS_INFO_FALLBACK = {
    **YDL_OPTS_INFO,
    "extractor_args": {"youtube": {"player_client": ["android"]}},
}
