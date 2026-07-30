# Layer Diagram

← [architecture/overview.md](overview.md) | [Blueprint.md](../Blueprint.md)

---

## Layer Architecture

```mermaid
graph TB
    subgraph FE["🖥️ Frontend Layer"]
        UI["Browser UI\n(Vanilla JS, PWA)"]
        SW["Service Worker\n(sw.js)"]
    end

    subgraph SRV["🌐 Server Layer"]
        MW["Middleware / Auth\n(middleware.py)"]
        WS["WebSocket Handlers\n(ws_playback, ws_queue, ws_discovery, ws_download)"]
        HTTP["HTTP Handlers\n(http.py, auth.py)"]
        CM["Connection Manager\n(connection_manager.py)"]
        BS["Broadcast Service\n(broadcast_service.py)"]
    end

    subgraph ENG["⚙️ Engine Layer"]
        CR["Command Router\n(command_router.py)"]
        PB["Playback Controller\n(playback/)"]
        QM["Queue Manager\n(queue_manager.py)"]
        RM["Radio Engine\n(radio/)"]
        DL["Download Manager\n(download_manager.py)"]
        VS["Volume Service\n(volume_service.py)"]
    end

    subgraph CORE["🧠 Core (Pure Domain)"]
        ST["State\n(state.py)"]
        EB["Event Bus\n(event_bus.py)"]
        CB["Command Bus\n(command_bus.py)"]
        PR["Ports / Protocols\n(ports.py)"]
        SEC["Security\n(security.py)"]
    end

    subgraph EXT["🔌 Adapters (External)"]
        MPV["MPV Adapter\n(adapters/mpv/)"]
        YTDLP["yt-dlp Adapter\n(adapters/ytdlp/)"]
    end

    subgraph PER["💾 Persistence"]
        DB["SQLite DB\n(persistence/db.py)"]
        REPO["Repositories\n(track, session, artist, genre, library)"]
        CACHE["Cache Resolver\n(cache/resolver.py)"]
    end

    UI -->|"WS / HTTP"| MW
    SW -.->|"Precache / Offline"| UI
    MW --> WS & HTTP
    WS --> CR
    HTTP --> CR
    CM --> BS
    BS -->|"Broadcast state"| UI

    CR --> PB & QM & RM & DL & VS
    PB & QM & RM & DL & VS --> CORE

    CORE --> PR
    PR --> MPV & YTDLP
    ENG --> PER
    EB -->|"Events → broadcast"| BS
```

---

## Dependency Graph

```mermaid
graph LR
    core["core/\n(no imports)"]
    adapters["adapters/\n← core/"]
    persistence["persistence/\n← core/"]
    plugins["plugins/\n← core/"]
    engine["engine/\n← core, adapters, persistence"]
    server["server/\n← core, engine, services, persistence"]
    services["services/\n← core, persistence"]
    launcher["launcher/\n← server (start only)"]

    core --> adapters
    core --> persistence
    core --> plugins
    core --> engine
    adapters --> engine
    persistence --> engine
    core --> services
    persistence --> services
    engine --> server
    services --> server
    persistence --> server
    server --> launcher
```

Aturan lengkap → [architecture/dependency_rules.md](dependency_rules.md)

---

## Request Flow — User Play Track

```mermaid
sequenceDiagram
    participant Browser
    participant WSHandler as WebSocket Handler
    participant CommandBus
    participant PlaybackCtrl as Playback Controller
    participant MPVAdapter as MPV Adapter
    participant EventBus
    participant Broadcast as Broadcast Service

    Browser->>WSHandler: {"cmd": "play", "video_id": "abc"}
    WSHandler->>CommandBus: dispatch(CMD_PLAY, payload)
    CommandBus->>PlaybackCtrl: handle_play(payload)
    PlaybackCtrl->>MPVAdapter: load_url(stream_url)
    MPVAdapter-->>PlaybackCtrl: ok
    PlaybackCtrl->>EventBus: publish(EVENT_PLAYBACK_STARTED, state)
    EventBus->>Broadcast: on_event(EVENT_PLAYBACK_STARTED)
    Broadcast->>Browser: broadcast({type: "state", ...})
```

---

## Testing Pyramid

```mermaid
graph TB
    E2E["🔺 E2E / Manual QA\n(Playwright, Tkinter GUI)\nSedikit, lambat, mahal"]
    INT["Integration Tests\n4 skenario flow utama\n(pytest-asyncio)"]
    UNIT["Unit Tests\n~65 file, mirror 1:1\nCepat, murah, high value"]

    E2E --> INT --> UNIT
```

Detail → [testing/testing_strategy.md](../testing/testing_strategy.md)

---

## Build & Release Flow

```mermaid
flowchart LR
    push["git push"] --> lint["Lint\n(ruff, mypy)"]
    lint --> audit["Audit\n(bandit, pip-audit, import-linter)"]
    audit --> test["Unit Tests\n(pytest --cov)"]
    test --> inttest["Integration Tests\n(pytest integration/)"]

    tag["git tag v*.*.*"] --> ci["Full CI"]
    ci --> changelog["Generate CHANGELOG"]
    changelog --> release["GitHub Release\n(source tarball)"]
    release --> docker["Docker Build\n(GHCR)"]
```

Detail → [devops/release.md](../devops/release.md)

---

## Folder Hierarchy (Ringkas)

```mermaid
graph TD
    root["lunawave/"]
    root --> core["core/ — pure domain"]
    root --> adapters["adapters/ — external systems"]
    root --> engine["engine/ — domain logic"]
    root --> persistence["persistence/ — SQLite repos"]
    root --> server["server/ — API layer"]
    root --> plugins["plugins/ — optional features"]
    root --> launcher["launcher/ — GUI & process"]
    root --> cache["cache/ — file cache"]
    root --> scripts["automation/ — tooling"]
    root --> data["data/ — static data"]
    root --> tests["tests/ — all tests"]
    root --> web["web/static/ — frontend"]
    root --> docs["docs/ — documentation"]
```

Tree lengkap → [architecture/folder_structure.md](folder_structure.md)
