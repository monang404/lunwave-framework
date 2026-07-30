# ADR-0007: Crossfade Implementation Strategy

## Status
Proposed

## Context
T16 requests support for Crossfade (Optional / Eksperimental).
The application supports two audio output modes:
1. `DEVICE` (Server-side via MPV)
2. `BROWSER` (Client-side via `<audio>` tag streaming from server)

Because of this dual-output architecture, crossfade cannot be simply implemented using MPV's `af=afade` alone. If we implement crossfade entirely in MPV, it will only affect users listening directly on the host device. Users streaming via the browser will not hear the crossfade unless the browser's `<audio>` tag also crossfades.

## Options

### 1. Backend-only Dual Instance MPV (Icecast style)
We mix two MPV instances into a single virtual output stream, and stream that mixed output to the browser.
- **Pros:** True crossfade, works exactly the same for all clients.
- **Cons:** Extremely high complexity, requires capturing MPV's stdout audio stream and muxing it on the fly, breaking the current simple HTTP Range request proxy approach.

### 2. Manual Single-Instance Fade (Simulated Crossfade)
Instead of two tracks playing simultaneously, we simply fade out the volume 2 seconds before the end of the track, load the next track, and fade in the volume over 2 seconds.
- **Pros:** Easy to implement. No overlap needed.
- **Cons:** Not a true crossfade (no overlap).
- **Implementation:**
  - For `DEVICE` mode, a background task monitors `state.position` and `state.current_track.duration`. If `remaining <= 2`, it interpolates `mpv.set_volume()` downwards.
  - For `BROWSER` mode, the frontend monitors its `audio.currentTime` and interpolates `audio.volume` downwards, then upwards on the next track.

### 3. Frontend Dual `<audio>` Tags (For BROWSER) + MPV `afade` (For DEVICE)
For true crossfade, the frontend needs two `<audio>` tags to play the end of track A and start of track B simultaneously. MPV handles its own crossfade natively.
- **Pros:** True crossfade.
- **Cons:** Two divergent implementations. High risk of breaking the `queue_manager.py` state machine since "current track" becomes fuzzy when two tracks overlap.

## Recommendation
Since this is an experimental feature, we recommend **Option 2 (Manual Single-Instance Fade)** for simplicity and stability, or **deferring** the feature entirely if it adds too much complexity to the state synchronization.

We will wait for user input before proceeding with implementation.
