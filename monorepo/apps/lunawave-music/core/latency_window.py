#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.latency_window import LatencyWindow
"""

from lunawave_framework.core.kernel.latency_window import LatencyWindow

__all__ = ["LatencyWindow"]
