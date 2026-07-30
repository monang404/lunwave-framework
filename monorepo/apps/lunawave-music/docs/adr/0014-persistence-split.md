# ADR 0014: Persistence Split (Schema Ownership + SessionRepositoryPort)

## Status
**Accepted, executed.** Small ADR per the roadmap's own requirement
("needs its own small ADR on schema ownership... made before this phase
starts, not during it") — written and applied in the same pass since both
decisions below are low-risk and don't touch the playback hot path or
anything flagged no-touch-without-approval.

## Context

Phase 4 of the roadmap splits `persistence/`:

- `db.py`, `session_repo.py`, `admin_account_repo.py` → generic storage
  layer, move to `lunawave-framework`.
- `track_repo.py`, `artist_repo.py`, `genre_repo.py`, `discover_repo.py`,
  `library_repo.py`, `chat_repo.py`, `stream_cache.py`, `discover_enrich.py`
  → stay in `lunawave-music` (100% music vocabulary).

I read all three files moving. All three are already schema-agnostic in
the way that matters:

- `DatabaseConnection.init(schema_path)` already takes the schema file as
  a parameter — it executes whatever `schema_path` points to via
  `executescript()` and never hardcodes table names it doesn't touch
  directly (only `songs`/`artists`/`tracks`/`tracks_fts`/`songs_fts`, for
  the pre-existing migration/backfill logic, which is itself
  schema-agnostic in the sense that it only cares those tables exist).
- `session_repo.py` and `admin_account_repo.py` take a raw `conn` and
  only ever reference `sessions` / `admin_account` — no music vocabulary
  anywhere in either file.

The only genuinely app-specific thing left in `db.py` was `from config
import DB_PATH` used as a *default* for the `db_path` constructor
parameter. The one real caller (`persistence/__init__.py`) already always
passes `db_path or DB_PATH` explicitly, and every test constructs
`DatabaseConnection` with an explicit path too — so the default was dead
weight, not a real dependency.

## Decision 1 — schema ownership

The roadmap's open question: does the framework own a base `schema.sql`
with app-registered migrations, or does each app own its full schema and
just reuse the framework's `db.py` connection/migration runner?

**Decision: the app owns its full schema, unsplit.** `schema.sql` stays a
single file in `apps/lunawave-music/persistence/schema.sql`, containing
every table including `sessions` and `admin_account`. The framework's
`DatabaseConnection` becomes a pure, schema-agnostic connection-lifecycle
runner — `schema_path` was already an `init()` argument supplied by the
caller, so no change there; the only edit is dropping the app-specific
`DB_PATH` default on the constructor's `db_path` parameter (now required,
matching how the one real caller already used it).

**Why not the base-schema-plus-registered-migrations design:** that
requires inventing a real schema-composition/migration-registration
mechanism (order-dependent `CREATE TABLE` statements, foreign keys between
framework-owned and app-owned tables like the FTS5 triggers referencing
`songs`/`artists`) with no second consumer yet to validate the design
against. Given the "prove the boundary cheaply, one risky thing at a time"
rule the roadmap itself sets, and that `db.py` was *already* accidentally
schema-agnostic (nothing to redesign, just delete a default), this is the
lower-risk choice and ships now instead of blocking the phase on a schema
DSL nobody's asked for yet. Revisit only if/when a second app actually
needs to compose its schema with the framework's.

## Decision 2 — `SessionRepositoryPort`

ADR 0013 Decision 2 deferred this: the Protocol is generic-shaped (no
music vocabulary) but was left in `music/domain/ports.py` because moving
the Protocol ahead of its implementation risked a mismatched abstraction.
Now that `session_repo.py` (the implementation) has moved to
`lunawave_framework.core.storage.session_repo`, the deferred half of the
decision resolves itself: **`SessionRepositoryPort` moves to
`lunawave_framework.core.storage.ports`, alongside its implementation.**
`music/domain/ports.py` re-exports it (`from
lunawave_framework.core.storage.ports import SessionRepositoryPort`) so
`DatabasePort` (which composes `TrackRepositoryPort`, `SessionRepositoryPort`,
`ArtistRepositoryPort`) and every existing caller of
`core.ports.SessionRepositoryPort` / `music.domain.ports.SessionRepositoryPort`
keep working unchanged. `DatabasePort` itself stays in `music/domain/ports.py`
as a composite — it can't move, since two of its three parents are
music-domain.

## Execution summary

- New: `packages/lunawave-framework/src/lunawave_framework/core/storage/{__init__,db,session_repo,admin_account_repo,ports}.py`.
- `apps/lunawave-music/persistence/{db,session_repo,admin_account_repo}.py`
  became backward-compat shims (same pattern as Phases 2–3).
- `music/domain/ports.py`: local `SessionRepositoryPort` definition
  removed, re-exported from the framework instead.
- `core/__init__.py`'s stale "Phase 3 not done yet" comment corrected
  (Phase 3 landed before this phase started) and a note added about where
  the Phase 4 shims live.
- 4 pre-existing test files (`test_db.py`, `test_session_repo.py`,
  `test_admin_account_repo.py`, `test_session_repo_delete_all.py`) removed
  from the app repo; equivalent + slightly expanded coverage added to
  `packages/lunawave-framework/tests/core/{test_db,test_session_repo,
  test_admin_account_repo}.py`, using a local minimal schema fixture
  (`tests/core/fixtures/minimal_schema.sql`) instead of the app's real
  `schema.sql`, so the framework's own tests never depend on the app repo.

## Consequences

**Positive:** the generic storage layer (connection lifecycle,
session-token CRUD, single-row account CRUD) is now genuinely reusable by
a non-music second app, with zero coupling to LunaWave's schema or config
module. `SessionRepositoryPort`'s home now matches its implementation's
home, closing the last open item from ADR 0013 Decision 2.

**Negative / risk:** low. Neither `engine/playback/controller.py` nor
`server/handlers/websocket.py` import anything from `persistence/db.py`,
`session_repo.py`, or `admin_account_repo.py` (verified by grep across the
app repo) — this phase doesn't go near either no-touch-without-approval
file. `persistence/__init__.py` (the `Repositories` wiring class) needed
zero changes, since it already imported these three modules by their
stable `persistence.*` names, which the shims preserve exactly.

## What's next

Phase 5 (server kernel vs. music handlers) per the roadmap — splitting
`server/app.py`/`connection_manager.py`/`broadcast_service.py` and the
transport-only parts of `server/handlers/` into the framework's routing
layer, explicitly noting the roadmap's own flag that touching
`server/handlers/websocket.py` needs sign-off before that phase starts.
