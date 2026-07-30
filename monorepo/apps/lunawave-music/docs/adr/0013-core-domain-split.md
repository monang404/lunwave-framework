# ADR 0013: Core Domain Split (state / events / commands / exceptions / ports)

## Status
**Accepted** (2026-07-29) — user confirmed proceeding with the proposed
defaults for Open Questions A–D (inheritance for RuntimeState/MusicPlayerState,
defer SessionRepositoryPort/DatabasePort split to Phase 4, `music/domain/` at
the app repo's top level, explicit review required before merge matching the
`controller.py` rule). Execution follows below.

## Context

`core/` currently mixes two things in the same 7 files:

- A generic pub/sub and command-dispatch **mechanism** (`event_bus.py`,
  `command_bus.py`) that has no music vocabulary in it at all.
- Music-domain **vocabulary** riding on top of that mechanism (concrete event
  types, command constants, exception types, ports, and state fields).

I read all 7 files in full to ground this ADR in what's actually there,
not just the Phase 0 audit's summary. Three things are worth flagging up
front because they change the shape of the split slightly from what the
audit implied:

1. **`command_bus.py` re-exports domain constants by wildcard.**
   `from core.commands import *` at the top of `command_bus.py` means 15
   call sites across `server/handlers/`, `engine/`, `plugins/notifications.py`,
   and tests currently do `from core.command_bus import CMD_PLAY_TRACK, command_bus`
   — pulling both the generic dispatcher instance *and* domain constants from
   the same import. Once `command_bus.py` (mechanism) and `commands.py`
   (vocabulary) live in different packages, that combined import breaks
   unless the app-side shim recombines them (see Decision 3).

2. **`ports.py` has one port that isn't obviously domain-specific:**
   `SessionRepositoryPort` (session token CRUD — `create_session`,
   `verify_session`, `delete_session`, `cleanup_sessions`) has no music
   vocabulary in its signature at all, unlike `TrackRepositoryPort` or
   `LyricsProvider` sitting right next to it. It's barely referenced by name
   elsewhere (Protocols are structural), but `DatabasePort` is a composite
   `TrackRepositoryPort + SessionRepositoryPort + ArtistRepositoryPort` — so
   it can't cleanly move to *either* side without splitting itself (see
   Decision 2).

3. **`exceptions.py`'s base class is literally named `YtPlayerError`** — the
   app's old pre-rebrand name, not `LunaWaveError` or anything generic. The
   whole hierarchy (`MpvConnectionError`, `TrackResolutionError`,
   `DownloadError`, etc.) is 100% domain, used only in `adapters/mpv/`,
   `adapters/ytdlp/`, `engine/playback/`, `persistence/`, and `config.py`. No
   generic exception base currently exists in `core/` or the framework
   package at all.

## Decision (proposed)

### What moves to `lunawave-framework` (mechanism only, zero domain vocabulary)

| File | Target | Notes |
|---|---|---|
| `event_bus.py` | `lunawave_framework/core/kernel/event_bus.py` | Already only imports the generic `DomainEvent` base, not concrete subclasses — moves close to verbatim once `DomainEvent` itself has a framework home |
| `command_bus.py` | `lunawave_framework/core/kernel/command_bus.py` | The `from core.commands import *` line is **removed** here — framework must not import domain constants (see Decision 3 for how callers keep working) |
| `DomainEvent` (base class only, currently in `events.py`) | `lunawave_framework/core/kernel/events.py` (new, small file) | Just the base dataclass; every concrete subclass stays in the app |
| A new generic runtime-state base (currently fields embedded in `AppState`) | `lunawave_framework/core/kernel/state.py` (new) | See Decision 1 — this is the one part of the split that isn't a clean lift, it requires actually designing a class |

### What moves to a new `music/domain/` package in the app repo (concrete vocabulary)

| File | Target | Notes |
|---|---|---|
| `commands.py` (all `CMD_*` constants) | `music/domain/commands.py` | 100% domain, verbatim move |
| `events.py` (all concrete `*Event` subclasses) | `music/domain/events.py` | Imports `DomainEvent` from the framework once that lands |
| `exceptions.py` (entire hierarchy, including the `YtPlayerError` base) | `music/domain/exceptions.py` | 100% domain including the base class name — no generic exception base exists to inherit from, and none is proposed (see Open Question B) |
| `ports.py`: `AudioPlayerPort`, `MediaExtractorPort`, `StreamResolverPort`, `TrackRepositoryPort`, `ArtistRepositoryPort`, `LibraryRepositoryPort`, `DiscoverRepositoryPort`, `LyricsProvider`, `SponsorBlockProvider` | `music/domain/ports.py` | Matches Phase 0 audit's classification |
| Music-specific `AppState` fields (`queue`, `radio_queue`, `history`, `lyrics_*`, `current_track`, `playback_mode`, `audio_output`, `sponsorblock_active`, `crossfade_enabled`, `loudness_normalization_enabled`, `current_track_gain_db`, `download_progress`) | `music/domain/state.py` | See Decision 1 |

### Decision 1 — how `AppState` actually splits (this is the real design work)

`AppState` is one flat dataclass today. Proposal: a generic
`lunawave_framework.core.kernel.state.RuntimeState` dataclass holding only
domain-neutral fields (`status: PlayerStatus`, `position`, `duration`,
`error_msg`, `is_online`, `active_tab`), and `music.domain.state.MusicPlayerState`
that **subclasses** `RuntimeState` and adds every music-specific field.
`PlayerStatus` itself (`IDLE/LOADING/PLAYING/PAUSED/ERROR`) is generic enough
to stay in the framework base. The one call site that constructs `AppState()`
(likely `bootstrap/` or `main.py`) would need to import `MusicPlayerState` and
construct that instead — I have not located and counted every such call site
yet; that's part of the actual execution, not this ADR.

### Decision 2 — `SessionRepositoryPort` / `DatabasePort`

Proposal: leave `SessionRepositoryPort` in `music/domain/ports.py` for now,
*not* the framework, even though its shape is generic — because Phase 4
(persistence split) is where the actual `db.py`/`session_repo.py` generic
storage layer gets designed, and moving just the Protocol now, ahead of its
implementation, risks a mismatched abstraction once Phase 4 lands. `DatabasePort`
stays composite and moves to `music/domain/ports.py` as-is. This is a
"defer, don't half-do it" choice — flagging it explicitly so you can override
if you'd rather split it now.

### Decision 3 — preserving the `from core.command_bus import CMD_X` pattern

The app-side shim `core/command_bus.py` will do what Phases 1–2's shims do,
just combining two sources instead of one:

```python
from lunawave_framework.core.kernel.command_bus import CommandBus, command_bus
from music.domain.commands import *  # noqa: F401,F403
```

So all 15 existing call sites keep working completely unchanged, same as
every prior phase — this needs verifying carefully during execution, not
assuming it works from reading the code alone.

## Consequences

**Positive:** this is the actual thesis of the whole extraction — `core`
stops being two things at once. `lunawave-framework` becomes usable by a
genuinely different (non-music) app for the first time, since nothing in
its `core/kernel/` would reference music domain concepts.

**Negative / risk:** highest fan-in files in the codebase (`state.py`,
`events.py` especially, per the Phase 0 dependency graph). `RuntimeState` →
`MusicPlayerState` subclassing means every reader of `AppState` fields still
works if they access a `MusicPlayerState` instance (subclass has all base
fields), but anything that does `isinstance(x, AppState)` or imports `AppState`
by that exact name needs a compat alias — I'd add `AppState = MusicPlayerState`
in the `music/domain/state.py` shim location, matching the class rename
pattern, but this needs confirming against actual call sites during
execution, not assumed here.

## Open questions needing your sign-off before I touch any code

- **A.** Does the `RuntimeState`/`MusicPlayerState` subclassing shape in
  Decision 1 match what you want, or would you rather it be composition
  (`MusicPlayerState.runtime: RuntimeState`) instead of inheritance? Inheritance
  is less invasive to existing `state.field_name` access patterns; composition
  is a cleaner boundary but touches every call site.
- **B.** Decision 2 (defer `SessionRepositoryPort`/`DatabasePort` splitting to
  Phase 4) — agree, or do you want it split now?
- **C.** Should `music/domain/` live at the app repo's top level (sibling to
  `core/`, `engine/`, `server/`, etc.), or nested somewhere else? The roadmap
  says "a new `music/domain/` package in `lunawave-music`" but doesn't pin
  the exact path.
- **D.** Confirming the process point the roadmap itself left open in
  `01_ROADMAP.md`: should this phase additionally require your explicit
  review before merge (not just before I start), matching the
  `controller.py`-adjacent rule in `AI_CONTEXT.md`? I'm assuming yes given
  the roadmap's own emphasis, but it was never explicitly confirmed.

I have not moved, renamed, or edited any of the 7 source files yet, and have
not touched `engine/playback/controller.py`. Once you confirm A–D (or tell me
to just use my best judgment on them), I'll execute the split and produce the
Phase 3 deliverable in the same 9-point format as Phases 1–2.

## Addendum (post-execution, 2026-07-29)

Two things not fully enumerated in Decision 1's field tables above, decided
during actual execution using best judgment (flagged here rather than
silently applied):

- **`volume` and `playback_speed`** ended up in `RuntimeState` (framework),
  not `MusicPlayerState` (domain) -- both are generic media-playback
  concepts (any AV app has a volume level and a playback speed), not
  specific to music.
- **`loop_mode`** ended up in `MusicPlayerState` (domain), not
  `RuntimeState` -- its meaning ("off"/"track"/"queue") is tied to the
  queue/radio concepts, which are domain-specific.

Also: `active_tab`'s default value comment in the original `AppState`
listed the app's actual tab names (`"home"|"search"|"radio"|"queue"`). Since
`RuntimeState` (framework) has no concept of what tabs exist, that comment
was replaced with a generic note rather than moved verbatim -- the field
itself (`active_tab: str = "home"`) is unchanged.

Execution results, test status, and risk findings are in the Phase 3
deliverable report (same 9-point format as Phases 1-2).
