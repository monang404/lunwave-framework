#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.server_clock import ServerClock, server_clock

`server_clock` is the same module-level singleton instance defined in
lunawave_framework.core.kernel.server_clock -- importing it here does not
create a second instance, so server/app.py's `.init()` call and any other
reader of `server_clock.uptime_seconds` still observe the one shared clock.

Note: this module does NOT define get_uptime_seconds -- it never did.
main.py's shutdown path imports `from core.server_clock import
get_uptime_seconds` inside a broad try/except that silently swallows the
resulting ImportError; that is a pre-existing bug (unrelated to this
extraction) reproduced identically here, not introduced by it.
"""

from lunawave_framework.core.kernel.server_clock import ServerClock, server_clock

__all__ = ["ServerClock", "server_clock"]
