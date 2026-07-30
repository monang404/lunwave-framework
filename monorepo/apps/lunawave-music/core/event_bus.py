#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 3 of the framework extraction (see docs/extraction/ and
docs/adr/0013-core-domain-split.md) moved this module's implementation
(100% generic mechanism, no domain vocabulary at all) to
lunawave_framework.core.kernel.event_bus. This file exists purely so
existing imports keep working unchanged:

    from core.event_bus import EventBus, bus

`bus` here is the exact same singleton instance defined in the framework
module, not a copy -- every subscriber/publisher across the app still
shares one EventBus.
"""

from lunawave_framework.core.kernel.event_bus import EventBus, bus

__all__ = ["EventBus", "bus"]
