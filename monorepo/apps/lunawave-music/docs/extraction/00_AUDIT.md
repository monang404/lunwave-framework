# LunaWave → Framework Extraction: Phase 0 Audit

**Status:** Planning only. No source files modified.
**Repo audited:** `lunawave-termux` (314 Python files, 57 JS files, 752 import edges per `docs/DEPENDENCY_GRAPH.json`)
**Rule respected:** per `AI_CONTEXT.md` — no big-bang rewrites, no two-stage refactor in one commit, explicit approval required before touching `engine/playback/controller.py` or `server/handlers/websocket.py`.

---

## 1. Important context this plan had to account for

LunaWave is not a green-field app — it's an actively maintained project with its own
conventions that already overlap heavily with what the framework brief asks for:

- **Hexagonal architecture already exists.** `core/ports.py` declares `Protocol` interfaces
  (`AudioPlayerPort`, `MediaExtractorPort`, `TrackRepositoryPort`, `LyricsProvider`, etc.)
  and `adapters/mpv/`, `adapters/ytdlp/` implement them.
- **Layer boundaries are already enforced by tooling**, not just convention: `.importlinter`
  defines forbidden-import contracts (`core-is-isolated`, `adapters-only-import-core`,
  `automation-is-isolated`, etc.), and I verified this holds in practice — `core/` has
  **zero outbound edges** into `adapters`, `engine`, `server`, `persistence`, `services`,
  `plugins`, or `launcher` in the current dependency graph.
- **An automation suite already exists** that resembles much of what the brief's `CLI` /
  `automation/` sections ask for: `doctor.py`, `verify_structure.py`, `verify_docs.py`,
  `architecture_lint.py`, `repo_map.py`, `patchlog.py`, `call_graph.py`, `event_graph.py`,
  `impact.py`, `hotspot.py`, `find_owner.py`. This is a head start, not a gap.
- **A patchlog + RFC process already governs changes** (`docs/PATCHLOG.md`,
  `docs/rfc/`), and `docs/STATUS.md` is described as the sole source of truth for
  "what's done." Any extraction plan needs to plug into this, not replace it.
- This is a live app with real users (Termux/Android + Windows). Breaking playback,
  auth, or the WebSocket protocol is not acceptable collateral damage.

**Implication:** the task is less "build hexagonal architecture from scratch" and more
"finish separating framework-shaped code that already exists from music-domain
vocabulary that has leaked into it," then formalize the split into two repos.

---

## 2. Dependency snapshot (from `docs/DEPENDENCY_GRAPH.json`)

| Layer | Files | Notes |
|---|---|---|
| tests | 149 | not part of extraction surface directly, but must migrate 1:1 with source |
| automation | 34 | isolated by contract already — lowest-risk extraction candidate |
| engine | 29 | 100% music domain (playback, radio, loudness, queue, downloads) |
| server | 26 | mixed — transport kernel + music-specific WS handlers |
| launcher | 20 | mostly generic process/update/GUI shell |
| core | 18 | **mixed** — generic kernel primitives + music vocabulary baked in |
| persistence | 12 | mixed — generic repo pattern + music-specific repos |
| adapters | 10 | concrete implementations of music-specific ports (mpv, yt-dlp) |
| plugins | 6 | music domain (lyrics, sponsorblock) + one generic-shaped one (notifications) |
| bootstrap | 5 | generic startup orchestration, minor music-specific wiring |
| services | 4 | 100% music domain (discover ranking/service, stream prefetch) |
| data | 2 | internal to automation only (enforced by import-linter contract) |

`core/` measured outbound edges into other layers: **0** (contract holds). The leakage
in `core/` is not import-direction, it's **vocabulary**: e.g.

- `core/state.py` — `lyrics_lines`, `lyrics_timestamps`, `lyrics_offset` fields live
  directly on what should be a generic session/runtime-state object.
- `core/events.py` — `LyricsUpdatedEvent`, `MpvReconnectedEvent` are domain events
  defined in the supposedly domain-agnostic core.
- `core/commands.py` — `CMD_LYRICS_OFFSET` and similar music commands are core constants.
- `core/exceptions.py` — `MpvConnectionError`, YouTube-rate-limit errors defined in core.
- `core/ports.py` — the ports themselves (`AudioPlayerPort`, `MediaExtractorPort`,
  `LyricsProvider`) are legitimately domain-specific (music), so **the file's location
  is the problem, not its content** — it belongs in the music module, not framework core.

This is the single biggest structural finding: **`core/` is doing two jobs** — generic
kernel (event bus, command bus, logging, security, observability) and music-domain
contracts (ports, state fields, events, exceptions). These need to split into
`framework/core` (truly generic) and `music/domain` (the ports/events/state specific
to playback).

---

## 3. Classification — framework-generic vs. application-specific

### Clearly framework-generic (move to `lunawave-framework`, low-to-medium risk)

| Current path | Target framework location | Notes |
|---|---|---|
| `core/event_bus.py` | `core/events/` | generic pub/sub; base `DomainEvent` stays, subclasses (`LyricsUpdatedEvent`, etc.) move out |
| `core/command_bus.py` | `core/kernel/` | generic dispatch; music command constants move out |
| `core/log_config.py`, `log_categories.py`, `log_context.py`, `log_reader.py` | `core/logging/` | already generic, no music vocabulary found |
| `core/observability.py`, `core/mem_stats.py`, `core/latency_window.py`, `core/server_clock.py` | `core/kernel/` | generic runtime instrumentation |
| `core/security.py` | `core/security/` | token hashing, generic auth primitive |
| `core/task_utils.py` | `core/kernel/` | generic async helpers |
| `bootstrap/*` (minus music-specific wiring in `startup_tasks.py`/`services.py`) | `bootstrap/` | generic app lifecycle orchestration |
| `server/app.py`, `connection_manager.py`, `broadcast_service.py`, middleware | `core/routing/` + `core/kernel/` | generic aiohttp kernel, WS transport, connection registry |
| `server/handlers/auth.py`, `setup.py`, `context.py`, `websocket.py` (router only) | `core/routing/` | generic transport-level handlers |
| `automation/*` (all 34 files) | `automation/` (framework CLI backend) | already isolated by import-linter contract; this becomes the seed for `lunawave` CLI commands (`doctor`, `docs`, etc.) |
| `launcher/*` (minus any hardcoded LunaWave branding/paths) | `cli/` + `core/bootstrap/` | process lifecycle, updater, GUI shell — generalize app name/paths as config |
| `persistence/db.py`, `session_repo.py`, `admin_account_repo.py`, `schema.sql` (session/admin tables only) | `core/storage/` | generic session + account/auth persistence pattern |

### Clearly application-specific (move to `lunawave-music`)

| Current path | Notes |
|---|---|
| `engine/*` (playback, radio, loudness, queue, downloads, volume, sleep timer) | 100% music domain |
| `adapters/mpv/*`, `adapters/ytdlp/*` | concrete adapters for music-specific ports |
| `services/discover_service.py`, `discover_ranking.py`, `stream_prefetch.py` | music discovery domain |
| `persistence/track_repo.py`, `artist_repo.py`, `genre_repo.py`, `discover_repo.py`, `library_repo.py`, `chat_repo.py`, `stream_cache.py`, `discover_enrich.py` | music domain repos |
| `plugins/lyrics_sync.py`, `lyrics_fetcher.py`, `lyrics_parser.py`, `sponsorblock.py` | music domain plugins |
| `server/handlers/ws_playback.py`, `ws_discovery.py`, `ws_queue.py`, `ws_cache.py`, `ws_chat.py`, `ws_download.py`, `ws_log_stream.py`, `audio_stream_handler.py`, `log_dashboard.py` | music-domain WS handlers riding on the generic router |
| `web/static/*` (nearly all) | music player UI — pages, player rendering, radio UI, lyrics rendering |
| Ports in `core/ports.py`: `AudioPlayerPort`, `MediaExtractorPort`, `TrackRepositoryPort`, `LyricsProvider` | domain-specific contracts, move alongside their adapters |
| Music-specific fields/events/commands currently sitting in `core/state.py`, `events.py`, `commands.py`, `exceptions.py` | extracted into `music/domain/` |

### Needs a decision, not obviously one or the other

- `plugins/notifications.py` — shaped generically (event-triggered notification dispatch);
  worth checking whether its payload/templates are music-specific before deciding.
- `web/static/shared/js/ws/transport.js`, `router.js`, `store.js` — look like a generic
  WS client transport + state-store pattern reusable across future frontends; the
  `message-handlers/*` next to them are domain-specific and should NOT move with them
  without separating the two.
- `launcher/gui_qt/*` — Qt-based desktop launcher shell; likely generic scaffolding
  with LunaWave-specific branding/copy that needs parameterizing, not rewriting.

---

## 4. Risk ranking for extraction order

1. **Lowest risk — `automation/` extraction.** Already import-isolated by contract,
   not on any runtime hot path, has no music-domain leakage found. Good first phase
   to prove the two-repo split mechanically works (packaging, imports, CI) before
   touching anything that affects the running player.
2. **Low-medium — `core/logging`, `observability`, `security`, `task_utils`.** No
   music vocabulary found in these files; extraction is close to a pure move.
3. **Medium — `bootstrap/`, `server/app.py` + transport-only handlers.** Generic
   shape confirmed, but wired into the live startup path — needs a working
   compatibility shim (per `AI_CONTEXT.md`'s "backward-compat alias" rule) during
   transition.
4. **Medium-high — `persistence` split (session/auth vs. music repos).** Schema is
   shared in one `schema.sql`; splitting requires either a schema convention (framework
   owns core tables, app owns domain tables via its own migration) or a plugin-style
   schema registration mechanism — this needs its own ADR before touching it.
5. **High — `core/state.py`, `events.py`, `commands.py`, `exceptions.py`, `ports.py`
   split.** This is the real "core is mixed" fix. High risk because these are imported
   almost everywhere (highest fan-in in the dependency graph) and because
   `engine/playback/controller.py` — explicitly flagged as high-risk/no-touch-without-approval
   in `AI_CONTEXT.md` — depends on them. This phase must NOT be combined with any other
   phase, per the project's own "no two-stage refactor in one commit" rule.
6. **Highest — WebSocket handler split (`server/handlers/websocket.py`).** Explicitly
   flagged as "don't split without explicit approval" in `AI_CONTEXT.md`. Any framework
   extraction touching this needs sign-off before planning even goes further, separate
   from this document.

---

## 5. What I'm deliberately NOT doing yet

- Not creating `lunawave-framework/` or `lunawave-music/` directories or moving any files.
- Not touching `engine/playback/controller.py` or `server/handlers/websocket.py`.
- Not writing ADRs yet — those should be written per-phase, once each phase's design
  is agreed, not speculatively for all eight up front.
- Not scaffolding the CLI (`lunawave new`, `module:create`, etc.) before Phase 1 proves
  the packaging boundary works, since the CLI's job is to codify conventions that don't
  exist yet in two-repo form.

See `01_ROADMAP.md` for the phased plan and what Phase 1 concretely looks like.
