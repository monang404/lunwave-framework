"""
Module: lunawave_framework.core.bootstrap.power

Purpose:
    Acquire a PARTIAL wake-lock via `termux-wake-lock` on startup so the
    Android/HyperOS scheduler is less likely to freeze the server process
    when the screen turns off. This is a secondary, best-effort layer —
    the primary mitigation is the manual OS-level setup documented in
    docs/CONSTRAINTS.md (Autostart, battery saver exemption, recent-apps
    lock), since custom OEM power policies (HyperOS/MIUI) can ignore the
    standard Android wake-lock/notification APIs entirely.

Inputs:
    None.

Outputs:
    None — fire-and-forget subprocess call.

Side Effects:
    Spawns `termux-wake-lock` as a subprocess when available. No-op
    everywhere else (Windows, or environments without the binary).

CLI:
    None (imported by bootstrap.startup_tasks).

Responsibilities:
    - Best-effort acquire a PARTIAL wake-lock without ever raising or
      blocking startup.

Depends on:
    None (stdlib + asyncio only).

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import os
import shutil

import structlog

from lunawave_framework.core.logging.log_categories import LC_SYSTEM

logger = structlog.get_logger(component="framework.bootstrap.power")


async def acquire_wake_lock():
    """Best-effort acquire a PARTIAL termux-wake-lock.

    No-op on Windows/macOS/plain Linux dev machines (binary simply won't be
    found there). Never raises — any failure is logged and swallowed so it
    can never block or crash startup. Not released explicitly: the OS
    reclaims it when the process exits, which matches the intent (the
    server shouldn't die while it's still considered active).
    """
    if os.name == "nt":
        return

    binary = shutil.which("termux-wake-lock")
    if not binary:
        logger.info("wake_lock_binary_not_found", category=LC_SYSTEM)
        return

    try:
        proc = await asyncio.create_subprocess_exec(
            binary, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        logger.info("wake_lock_acquired", category=LC_SYSTEM)
    except Exception as e:
        logger.warning(
            "wake_lock_acquire_failed",
            category=LC_SYSTEM,
            error_type=type(e).__name__,
            error=str(e),
        )
