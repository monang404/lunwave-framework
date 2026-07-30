# LunaWave → Framework Extraction: Phased Roadmap

Companion to `00_AUDIT.md`. Ordered by the risk ranking established there — lowest
risk first, so the two-repo mechanics get proven before anything on the playback
hot path is touched. Each phase is independently shippable and keeps the app running
throughout, per the "never break the running application" rule.

Each phase below ends with the 9-point deliverable format the brief requires
(what changed / why / files affected / architectural impact / migration notes /
risks / TODOs / test status / docs status) — filled in once the phase is actually
executed, not speculatively now.

---

## Phase 1 — Prove the boundary: extract `automation/`

**Goal:** Stand up `lunawave-framework` as a real installable package containing
only `automation/*`, consumed by `lunawave-termux` as a dependency instead of a
local folder. No behavior change.

- Create `lunawave-framework` repo with `automation/` moved in as-is.
- `lunawave-termux` depends on it (editable install during transition).
- Re-run `doctor.py`, `verify_structure.py`, `architecture_lint.py` from the
  installed package against the app repo to confirm cross-repo operation works.
- No music-domain code touched at all in this phase.

**Why first:** this is the only layer confirmed to have zero coupling in both
directions already (`automation-is-isolated` contract), so it validates packaging,
versioning, and CI wiring between two repos before any risk is introduced.

**Exit criteria:** `doctor.py` run from the installed framework package against
`lunawave-termux` produces identical output to running it in-tree today.

---

## Phase 2 — Extract clean kernel primitives

Move `core/logging/*`, `core/observability.py`, `core/mem_stats.py`,
`core/latency_window.py`, `core/server_clock.py`, `core/security.py`,
`core/task_utils.py` into `lunawave-framework/core/`. These had no music vocabulary
found in Phase 0 audit, so this should be close to a pure relocate + import-path
update, with backward-compat aliases left in the app repo per `AI_CONTEXT.md`
convention until all callers are verified migrated.

**Exit criteria:** full backend test suite (currently 812 passing per `docs/STATUS.md`)
still green; `import-linter` contracts still hold with paths updated.

---

## Phase 3 — Split `core/` domain leakage (event bus / command bus / ports / state)

The highest-value, highest-risk phase identified in the audit. Splits into:

- `core/event_bus.py`, `core/command_bus.py` → generic dispatch mechanism stays in
  framework; concrete event/command types (`LyricsUpdatedEvent`, `CMD_LYRICS_OFFSET`,
  etc.) move to a new `music/domain/` package in `lunawave-music`.
- `core/ports.py` → `AudioPlayerPort`, `MediaExtractorPort`, `TrackRepositoryPort`,
  `LyricsProvider` move to `lunawave-music`; framework keeps zero domain ports,
  only the `Protocol`-based port *convention* documented, not instances of it.
- `core/state.py`, `core/events.py`, `core/exceptions.py` → split generic
  session/runtime-state base from music-specific fields (lyrics, queue, track).

**This phase must not be combined with any other phase in one commit**, per the
project's own rule, given `engine/playback/controller.py` (flagged no-touch-without-approval)
depends directly on these files. Requires explicit sign-off before execution,
and its own ADR (`0009-core-domain-split.md`) written before code changes, not after.

**Exit criteria:** `engine/playback/controller.py` untouched in diff; all tests
touching state/events/commands pass; import-linter contracts pass with `music`
as a new root package importing framework core (never the reverse).

---

## Phase 4 — Adapters and persistence

- `adapters/mpv/*`, `adapters/ytdlp/*` move to `lunawave-music` alongside the ports
  they implement (Phase 3 output).
- `persistence/` splits: `db.py`, `session_repo.py`, `admin_account_repo.py` become
  framework's generic storage layer; `track_repo.py`, `artist_repo.py`, `genre_repo.py`,
  `discover_repo.py`, `library_repo.py`, `chat_repo.py`, `stream_cache.py`,
  `discover_enrich.py` move to `lunawave-music`.
- Needs its own small ADR on schema ownership: does the framework own a base
  `schema.sql` with app-registered migrations, or does each app own its full schema
  and just reuse the framework's `db.py` connection/migration runner? This decision
  should be made before this phase starts, not during it.

---

## Phase 5 — Server kernel vs. music handlers

- `server/app.py`, `connection_manager.py`, `broadcast_service.py`, and the
  transport-only parts of `server/handlers/` (`auth.py`, `setup.py`, `context.py`,
  the router logic in `websocket.py`) become the framework's `core/routing/` layer.
- `ws_playback.py`, `ws_discovery.py`, `ws_queue.py`, `ws_cache.py`, `ws_chat.py`,
  `ws_download.py`, `ws_log_stream.py`, `audio_stream_handler.py`, `log_dashboard.py`
  stay in `lunawave-music` as handlers registered against the generic router.
- Splitting `websocket.py` itself requires the explicit approval `AI_CONTEXT.md`
  already flags as a precondition — this is called out again here so it isn't
  missed when this phase is scheduled.

---

## Phase 6 — Bootstrap, launcher, plugin system formalization

- Generalize `bootstrap/` and `launcher/` (parameterize app name, paths, branding
  currently hardcoded to LunaWave) into framework startup/process-lifecycle code.
- Formalize the plugin contract implied by `plugins/notifications.py` (the one
  plugin flagged in the audit as possibly-generic) into the framework's plugin
  loading convention; `lyrics_*` and `sponsorblock.py` stay as music plugins
  built against that convention.

## Phase 7 — Frontend transport split

- `web/static/shared/js/ws/transport.js`, `router.js`, and `store.js` become a
  reusable frontend transport/state package; `message-handlers/*` stay app-side.
- Everything else in `web/static/` (pages, player rendering, radio/lyrics UI)
  stays in `lunawave-music` — no attempt to generalize UI components in this pass.

## Phase 8 — CLI, templates, examples, ADRs, remaining docs

Only after Phases 1–7 land does it make sense to build `lunawave new`,
`module:create`, `plugin:create`, `adapter:create`, project templates, and the
`examples/` apps (CRM, inventory, etc.) — building these earlier would be
scaffolding conventions that haven't been proven against a real second consumer
of the framework yet. Full ADR set and remaining docs (`ARCHITECTURE.md`,
`CONTRIBUTING.md`, convention docs, migration/upgrade guides) get written phase-by-phase
as each lands, not all up front.

---

## Sequencing rationale (why not start with Phase 3, the "real" work)

Phase 3 is where the framework brief's actual thesis (core must never know business
domains) gets satisfied. But starting there first fails the project's own
"never big-bang, never two risky things at once" rule, since it simultaneously
requires: (a) proving cross-repo packaging works, (b) splitting the highest-fan-in
files in the codebase, and (c) working near a file (`controller.py`) that needs
explicit sign-off. Phases 1–2 de-risk (a) cheaply first.

---

## What I need from you before Phase 1 starts

- Confirm you want this executed as two actual separate repos (as the brief specifies),
  vs. a monorepo with `packages/framework` + `packages/music` — changes packaging/CI
  details in Phase 1 but not the extraction order above.
- Confirm Phase 3 sign-off process: the brief says nothing may be merged without
  passing lint/tests/coverage/security scan — should Phase 3 additionally require
  your explicit review before merge, matching `AI_CONTEXT.md`'s existing rule for
  `controller.py`-adjacent changes?
- Once confirmed, I'll execute Phase 1 only, produce the 9-point deliverable report
  for it, and stop for review before Phase 2.
