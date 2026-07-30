#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.log_categories import LC_LIFECYCLE, ALL_CATEGORIES

It re-exports every public name from
`lunawave_framework.core.logging.log_categories` unchanged.
"""

from lunawave_framework.core.logging.log_categories import (
    ALL_CATEGORIES,
    LC_AUTH,
    LC_CACHE,
    LC_COMMAND,
    LC_DOWNLOAD,
    LC_EVENT,
    LC_EXTERNAL,
    LC_LIFECYCLE,
    LC_PERSISTENCE,
    LC_PLAYBACK,
    LC_QUEUE,
    LC_RADIO,
    LC_RESOLVE,
    LC_SECURITY,
    LC_SESSION,
    LC_SYSTEM,
)

__all__ = [
    "LC_LIFECYCLE",
    "LC_SESSION",
    "LC_AUTH",
    "LC_COMMAND",
    "LC_EVENT",
    "LC_PLAYBACK",
    "LC_QUEUE",
    "LC_RADIO",
    "LC_DOWNLOAD",
    "LC_RESOLVE",
    "LC_CACHE",
    "LC_PERSISTENCE",
    "LC_EXTERNAL",
    "LC_SECURITY",
    "LC_SYSTEM",
    "ALL_CATEGORIES",
]
