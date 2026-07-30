# Architecture Overview

← [Blueprint.md](../Blueprint.md)

---

## Visi Arsitektur

LunaWave menggunakan arsitektur **hexagonal (ports & adapters)** — domain logic murni di tengah, sistem eksternal di pinggir. Keputusan ini diambil agar:

- Domain logic dapat di-test tanpa MPV, yt-dlp, atau database nyata
- Adapter ke sistem eksternal bisa diganti tanpa menyentuh domain
- Dependency arahnya selalu satu arah: luar → dalam, tidak pernah sebaliknya

Lihat → [architecture/dependency_rules.md](dependency_rules.md) untuk aturan lengkap dan penegakannya via `.importlinter`.

---

## Prinsip Arsitektur

**1 file = 1 tanggung jawab**
File yang tanggung jawabnya tidak bisa dijelaskan dalam satu kalimat pendek adalah kandidat untuk dipecah.

**Ports & Protocols**
`core/ports.py` mendefinisikan `Protocol` Python untuk semua adapter eksternal. Engine hanya berbicara lewat port — tidak pernah langsung ke adapter.

**Event-driven, bukan request-response**
State perubahan disebarkan via `core/event_bus.py`. Frontend menerima update via WebSocket broadcast, bukan polling.

**Command Bus sebagai single entry point**
Semua aksi user masuk lewat `core/command_bus.py`. Tidak ada shortcut langsung ke engine.

**Honest Engineering**
File yang belum bisa di-test diberi label eksplisit di `pyproject.toml [tool.coverage] omit` — bukan diam-diam diabaikan.

---

## Layer System

```
┌─────────────────────────────────┐
│        Frontend (Browser)       │  Vanilla JS, PWA
├─────────────────────────────────┤
│         Server Layer            │  FastAPI/ASGI, WebSocket, HTTP, Auth
├─────────────────────────────────┤
│         Engine / Domain         │  Playback, Queue, Radio, Download
├─────────────────────────────────┤
│      Core (Pure Domain)         │  State, EventBus, CommandBus, Ports
├──────────────┬──────────────────┤
│   Adapters   │   Persistence    │  MPV, yt-dlp │ SQLite, Repositories
└──────────────┴──────────────────┘
```

Diagram lengkap dengan Mermaid → [architecture/layer_diagram.md](layer_diagram.md)

---

## Komponen Utama

| Komponen | Lokasi | Peran |
|---|---|---|
| State | `core/state.py` | Single source of truth state aplikasi |
| Event Bus | `core/event_bus.py` | Pub/sub internal |
| Command Bus | `core/command_bus.py` | Entry point semua aksi user |
| Ports | `core/ports.py` | Protocol/interface untuk adapters |
| Playback Controller | `engine/playback/controller.py` | Orchestrator playback |
| Radio Engine | `engine/radio/engine.py` | Orchestrator radio mode |
| MPV Adapter | `adapters/mpv/` | Bridge ke MPV via IPC socket |
| yt-dlp Adapter | `adapters/ytdlp/` | Search, resolve URL, download |
| Persistence | `persistence/` | SQLite + domain repositories |
| WebSocket Handler | `server/handlers/websocket.py` | Lifecycle + routing WS |

---

## Keputusan Arsitektur Penting

Setiap keputusan besar didokumentasikan sebagai ADR:

- [ADR-0001](../adr/0001-mpv-ipc-over-subprocess.md) — Kenapa MPV dikontrol lewat IPC socket?
- [ADR-0002](../adr/0002-sqlite-over-json-cache.md) — Kenapa SQLite dibanding file JSON cache?
- [ADR-0003](../adr/0003-hexagonal-ports-protocol.md) — Kenapa arsitektur hexagonal?
- [ADR-0004](../adr/0004-command-bus-single-writer.md) — Kenapa `command_bus.py` pakai single-writer?
- [ADR-0005](../adr/0005-websocket-single-channel.md) — Kenapa satu channel WS broadcast semua state?
- [ADR-0006](../adr/0006-vanilla-js-over-framework.md) — Kenapa vanilla JS, bukan React/Vue/Svelte?

---

## Dokumen Terkait

- [architecture/backend.md](backend.md) — Peta modul Python lengkap
- [architecture/frontend.md](frontend.md) — Peta modul JS & CSS
- [architecture/domain.md](domain.md) — Domain model detail
- [architecture/data_flow.md](data_flow.md) — Bagaimana data mengalir
- [architecture/technology_stack.md](technology_stack.md) — Stack & alasan pilihan
