"""
Module: server.handlers.ws_download

Purpose:
    WebSocket handler for managing track download requests and status.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.command_bus
    - server.serializers

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import os
import re

import structlog

from core.command_bus import CMD_CANCEL_DOWNLOAD, CMD_DOWNLOAD
from core.log_categories import LC_DOWNLOAD
from server.serializers import dict_to_track, track_to_dict
from services.discover_service import DiscoverService

logger = structlog.get_logger(component="ws.download")


async def handle_download_command(
    action: str, data: dict, tracks, discover, manager, state, command_bus, ws=None
):
    if action == "download":
        track = dict_to_track(data) if data else None
        if track and track.video_id and tracks:
            db_track = await tracks.get_track(track.video_id)
            if db_track and db_track.local_path and os.path.exists(db_track.local_path):
                if ws:
                    import json

                    await ws.send_str(
                        json.dumps(
                            {
                                "type": "download_conflict",
                                "data": {
                                    "video_id": track.video_id,
                                    "local_path": db_track.local_path,
                                },
                            }
                        )
                    )
                return
        await command_bus.execute(CMD_DOWNLOAD, track)

    elif action == "download_confirm_overwrite":
        track = dict_to_track(data) if data else None
        await command_bus.execute(CMD_DOWNLOAD, track)

    elif action == "cancel_download":
        await command_bus.execute(CMD_CANCEL_DOWNLOAD)

    elif action == "delete_download":
        track = dict_to_track(data) if data else None
        if track and track.video_id:
            db_track = await tracks.get_track(track.video_id)
            if db_track and db_track.local_path:
                # Hapus file utama yang terdaftar di DB (bisa berupa downloads/ atau cache/mp3/ lama)
                if os.path.exists(db_track.local_path):
                    try:
                        os.remove(db_track.local_path)
                    except Exception as e:
                        logger.error(
                            "download_local_file_delete_failed",
                            category=LC_DOWNLOAD,
                            local_path=db_track.local_path,
                            error_type=type(e).__name__,
                            error=str(e),
                        )

                # Fallback legacy: coba hapus dari downloads/ dengan berbagai ekstensi
                # (dulu .mp3, sekarang bisa .opus/.m4a/dll setelah C-1 fix)
                safe_artist = re.sub(r'[\\/*?:"<>|]', "", db_track.artist)
                safe_title = re.sub(r'[\\/*?:"<>|]', "", db_track.title)
                from config import DOWNLOAD_DIR

                for ext in (".mp3", ".opus", ".m4a", ".webm", ".ogg"):
                    user_path = DOWNLOAD_DIR / f"{safe_artist} - {safe_title}{ext}"
                    if user_path.exists() and str(user_path) != db_track.local_path:
                        try:
                            os.remove(str(user_path))
                        except Exception as e:
                            logger.debug(
                                "download_legacy_file_delete_failed",
                                category=LC_DOWNLOAD,
                                legacy_path=str(user_path),
                                error_type=type(e).__name__,
                                error=str(e),
                            )

                # Update DB
                db_track.local_path = None
                await tracks.set_local_path(db_track.video_id, None)

                # Update current state if playing this track
                if state.current_track and state.current_track.video_id == db_track.video_id:
                    state.current_track.local_path = None
                    from server.serializers import state_to_dict

                    await manager.broadcast({"type": "state", "data": state_to_dict(state)})

                # Update discover
                ds = DiscoverService(discover)
                recent, favorites, cached, featured_artists, featured_genres = await asyncio.gather(
                    ds.get_recent(15),
                    ds.get_favorites(15),
                    ds.get_cached(15),
                    ds.get_featured_artists(100),
                    ds.get_featured_genres(100),
                )
                await manager.broadcast(
                    {
                        "type": "discover_data",
                        "data": {
                            "recent": [track_to_dict(t) for t in recent],
                            "favorites": [track_to_dict(t) for t in favorites],
                            "cached_tracks": [track_to_dict(t) for t in cached],
                            "featured_artists": featured_artists,
                            "featured_genres": featured_genres,
                        },
                    }
                )
                await manager.broadcast(
                    {"type": "log", "data": f"Unduhan dihapus: {db_track.title}"}
                )
