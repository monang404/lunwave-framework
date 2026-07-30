"""
Module: server.handlers.ws_discovery

Purpose:
    WebSocket handler for processing discovery and search commands.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - server.serializers
    - services.discover_service

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import json
from typing import Any

from server.serializers import track_to_dict
from services.discover_service import DiscoverService


async def handle_discovery_command(action: str, data: dict, ytdlp, discover_repo, ws):
    if action == "search":
        query = data.get("query", "").strip()
        if query:
            results = await ytdlp.search(query, max_results=10)
            await ws.send_str(
                json.dumps(
                    {
                        "type": "search_results",
                        "data": [track_to_dict(t) for t in results],
                    },
                    ensure_ascii=False,
                )
            )

    elif action == "discover_search":
        # Quick Search Discover (T-A3). NOT the same as action == "search"
        # above (that one is a live YouTube search via ytdlp). This one
        # searches already-cached local tracks via
        # DiscoverRepository.search_tracks() — no ranking/scoring, so no
        # DiscoverService wrapper needed here (unlike "discover" below).
        query = data.get("query", "").strip()
        kategori = data.get("kategori")
        # "all" adalah sentinel client-side untuk "tanpa filter kategori"
        # (chip "Semua" default aktif di discover-search-events.js), BUKAN
        # nilai kategori yang valid -- artists.kategori cuma pernah berisi
        # "individu"/"band" (lihat schema.sql + data-kategori di index.html).
        # Perlakukan sama seperti decade di bawah, kalau tidak, filter
        # "Semua" (posisi default) bikin search_tracks() selalu 0 hasil.
        kategori = kategori if kategori not in (None, "", "all") else None
        decade = data.get("decade")
        decade = int(str(decade)) if decade not in (None, "", "all") else None
        results = await discover_repo.search_tracks(query, kategori=kategori, decade=decade)
        # search_tracks() returns plain DB row dicts (not TrackInfo objects),
        # so track_to_dict() doesn't apply here directly — build the same
        # shape it produces for the "search" action above instead.
        payload = [
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "artist": r["artist"],
                "duration": r["duration"],
                "thumbnail": r["thumbnail"],
                "is_cached": bool(r["local_path"]),
                "view_count": r["view_count"],
                "is_favorite": bool(r["is_favorite"]),
            }
            for r in results
        ]
        await ws.send_str(
            json.dumps(
                {
                    "type": "discover_search_results",
                    "data": payload,
                },
                ensure_ascii=False,
            )
        )

    elif action == "discover":
        ds = DiscoverService(discover_repo)
        (
            recent,
            favorites,
            cached,
            featured_artists,
            featured_genres,
            for_you,
            unheard,
            genre_affinity,
            taste_spectrum,
        ) = await asyncio.gather(
            ds.get_recent(15),
            ds.get_favorites(15),
            ds.get_cached(15),
            ds.get_featured_artists(30),
            ds.get_featured_genres(30),
            ds.get_for_you(15),
            ds.get_unheard(15),
            ds.get_genre_affinity(15),
            ds.get_taste_spectrum(),
        )
        recent = list(recent)  # type: ignore
        favorites = list(favorites)  # type: ignore
        cached = list(cached)  # type: ignore
        genre_affinity_data: dict[str, Any] = genre_affinity  # type: ignore
        await ws.send_str(
            json.dumps(
                {
                    "type": "discover_data",
                    "data": {
                        "recent": [track_to_dict(t) for t in recent],
                        "favorites": [track_to_dict(t) for t in favorites],
                        "cached_tracks": [track_to_dict(t) for t in cached],
                        "featured_artists": featured_artists,
                        "featured_genres": featured_genres,
                        "for_you": for_you,
                        "unheard": unheard,
                        "genre_affinity_genre": genre_affinity_data["genre"],
                        "genre_affinity_artists": genre_affinity_data["artists"],
                        "taste_spectrum": taste_spectrum,
                    },
                },
                ensure_ascii=False,
            )
        )

    elif action == "get_artist_detail":
        # get_artist_detail terdaftar di DISCOVERY_CMDS
        # (server/handlers/websocket.py) -- branch ini reachable.
        ds = DiscoverService(discover_repo)
        artist = data.get("artist", "").strip()
        detail = await ds.get_artist_detail(artist) if artist else None
        await ws.send_str(
            json.dumps(
                {
                    "type": "artist_detail",
                    "data": detail,
                },
                ensure_ascii=False,
            )
        )
