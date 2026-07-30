# Data Flow

← [architecture/overview.md](overview.md) | [Blueprint.md](../Blueprint.md)

---

## Gambaran Umum

LunaWave menggunakan dua jalur komunikasi utama:

- **WebSocket** — aksi real-time (play, pause, queue) dan state broadcast ke frontend
- **HTTP** — auth, file statis, status endpoint

State selalu mengalir dari server ke client, bukan sebaliknya. Client tidak boleh menyimpan state kanonik — hanya boleh melakukan optimistic update sementara menunggu konfirmasi dari server.

---

## Flow 1 — User Play Track

```mermaid
sequenceDiagram
    participant Browser
    participant WSHandler as server/handlers/websocket.py
    participant Router as engine/command_router.py
    participant CommandBus as core/command_bus.py
    participant Playback as engine/playback/controller.py
    participant Loader as engine/playback/track_loader.py
    participant Cache as cache/resolver.py
    participant YTDLP as adapters/ytdlp/resolver.py
    participant MPV as adapters/mpv/
    participant EventBus as core/event_bus.py
    participant Broadcast as server/broadcast_service.py

    Browser->>WSHandler: WS {"cmd": "play", "video_id": "abc123"}
    WSHandler->>Router: route(CMD_PLAY, payload)
    Router->>CommandBus: dispatch(CMD_PLAY, payload)
    CommandBus->>Playback: handle_play(payload)
    Playback->>Loader: load_track(video_id)
    Loader->>Cache: get_stream_url(video_id)
    alt Cache miss
        Cache->>YTDLP: resolve(video_id)
        YTDLP-->>Cache: stream_url
        Cache-->>Loader: stream_url (cached)
    else Cache hit
        Cache-->>Loader: stream_url
    end
    Loader->>MPV: load(stream_url)
    MPV-->>Loader: ok
    Loader-->>Playback: track loaded
    Playback->>EventBus: publish(EVENT_PLAYBACK_STARTED, state)
    EventBus->>Broadcast: on_event(...)
    Broadcast-->>Browser: WS broadcast {type:"state", playback:{...}}
```

---

## Flow 2 — Radio Mode

```mermaid
sequenceDiagram
    participant Browser
    participant CommandBus as core/command_bus.py
    participant Radio as engine/radio/engine.py
    participant ArtistSel as engine/radio/artist_selector.py
    participant Filter as engine/radio/track_filter.py
    participant Prefetch as engine/radio/prefetcher.py
    participant YTDLP as adapters/ytdlp/searcher.py
    participant QueueMgr as engine/queue_manager.py
    participant EventBus as core/event_bus.py

    Browser->>CommandBus: CMD_RADIO_START {artist: "Radiohead"}
    CommandBus->>Radio: start(artist)
    Radio->>ArtistSel: select_next(history)
    ArtistSel-->>Radio: artist_name
    Radio->>YTDLP: search(artist_name + " music")
    YTDLP-->>Radio: List[TrackInfo]
    Radio->>Filter: filter(tracks, history, queue)
    Filter-->>Radio: eligible_tracks
    Radio->>QueueMgr: enqueue(track)
    Radio->>Prefetch: schedule_next()
    Prefetch-->>Radio: ok (async)
    Radio->>EventBus: publish(EVENT_RADIO_TRACK_QUEUED, state)
```

> `track_filter.py` adalah titik rawan bug radio mode. Lihat → [backend/services.md](../backend/services.md)

---

## Flow 3 — Download MP3

```mermaid
sequenceDiagram
    participant Browser
    participant CommandBus as core/command_bus.py
    participant DL as engine/download_manager.py
    participant YTDLP as adapters/ytdlp/downloader.py
    participant FS as cache/mp3/
    participant EventBus as core/event_bus.py

    Browser->>CommandBus: CMD_DOWNLOAD_START {video_id: "abc"}
    CommandBus->>DL: enqueue(video_id)
    DL->>YTDLP: download_mp3(url, dest=cache/mp3/)
    loop Progress Hook
        YTDLP->>EventBus: publish(EVENT_DOWNLOAD_PROGRESS, {pct: N})
        EventBus-->>Browser: WS broadcast {download: {pct: N}}
    end
    YTDLP->>FS: write file
    YTDLP-->>DL: done
    DL->>EventBus: publish(EVENT_DOWNLOAD_COMPLETE, {...})
    EventBus-->>Browser: WS broadcast {download: {status: "done"}}
```

---

## Flow 4 — WebSocket Reconnect

```mermaid
sequenceDiagram
    participant Browser
    participant WS as server/handlers/websocket.py
    participant CM as server/connection_manager.py
    participant State as core/state.py
    participant Broadcast as server/broadcast_service.py

    Browser->>WS: WS connect (after disconnect)
    WS->>CM: register(ws)
    WS->>State: get_full_state()
    State-->>WS: AppState
    WS-->>Browser: WS send {type: "full_state", ...}
    note over Browser: render/full-state.js memproses
    Broadcast-->>Browser: subsequent broadcast events
```

---

## Aliran Data Persistensi

```
TrackInfo (dari yt-dlp)
        │
        ▼
persistence/track_repo.py
        │
        ├─── SQLite lunawave.db
        │
        └─── artists_enriched.json   ← data statis artis, bukan runtime
```

Cache URL stream (sementara):
```
adapters/ytdlp/resolver.py
        │
        ▼
cache/resolver.py   (in-memory + optional SQLite TTL cache)
```

---

## State yang Dikirim ke Frontend

Setiap broadcast WebSocket membawa snapshot state partial atau full:

```json
{
  "type": "state",
  "playback": {
    "status": "playing",
    "position": 42.5,
    "duration": 243.0,
    "track": { "video_id": "abc", "title": "...", "artist": "..." }
  },
  "queue": [...],
  "volume": 75,
  "mode": "radio",
  "downloads": [{ "video_id": "xyz", "pct": 63 }]
}
```

Detail serialisasi → [backend/api.md](../backend/api.md)

---

## Dokumen Terkait

- [architecture/layer_diagram.md](layer_diagram.md) — Diagram layer & dependency
- [architecture/domain.md](domain.md) — Event & Command system
- [backend/api.md](../backend/api.md) — Format pesan WS & HTTP
- [frontend/state_management.md](../frontend/state_management.md) — Bagaimana frontend memproses state
- [ADR-0005](../adr/0005-websocket-single-channel.md) — Kenapa satu channel WS?
