---
title: Technical Constraints & Limitations
last_verified: 2026-07-21
owner: Architecture Team
generated: false
---

# Technical Constraints

This document outlines the hard technical constraints and environmental limitations that dictate LunaWave's architecture.

## 1. Environment: Termux (Android)
- **Filesystem**: No standard Linux FHS (`/usr/bin`, `/etc`). Everything is under `/data/data/com.termux/files/usr`.
- **Background Execution**: Requires wakelock to prevent Android from killing the process when the screen is off. A `termux-wake-lock` (PARTIAL) is acquired automatically at server startup (`bootstrap/power.py`), but this is only a **secondary** layer — custom OEM power policies (HyperOS/MIUI and similar) can ignore the standard Android wake-lock/notification APIs entirely, regardless of what the code does. The **primary**, mandatory mitigation is a one-time manual device setup by the user:
  - **Autostart** permission enabled for the Termux app.
  - **Battery saver** set to "No restrictions" for Termux.
  - Termux app **locked** in the recent-apps list (so the OS doesn't sweep it on memory pressure).

  This manual setup cannot be automated from application code — it lives at the OS settings level and must be done once per device.
- **Port Binding**: Cannot bind to privileged ports (< 1024).

## 2. Dependencies
- **mpv**: Used for audio playback. Requires `--no-video` and specific IPC configurations for Termux.
- **yt-dlp**: Used for resolving streams. Needs frequent updates to bypass YouTube changes. Rate limiting is a risk.
- **SponsorBlock**: Relies on a community API. Can fail or return malformed data.

## 3. Network & Connectivity
- Mobile networks are inherently unstable. The application must handle disconnects gracefully (hence the Hexagonal Architecture and robust event bus).
- **WebSocket**: Must handle reconnections without losing state (handled via the `AppStore` in the frontend).

## 4. Hardware Limitations
- Devices running Termux may have limited RAM and CPU. The backend Python application must remain lightweight.
- Caching logic must aggressively manage disk space (e.g., limits on `dl_cache/`).

## 5. Security & Isolation
- LunaWave runs locally on the user's device but exposes a web UI.
- The web UI acts as a remote control. Only users with the admin password can issue commands to mpv.
