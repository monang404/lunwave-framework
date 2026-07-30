#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.mem_stats import get_rss_mb, get_cpu_percent

Private helpers (_get_rss_mb_proc, _get_rss_mb_windows) are NOT re-exported
here -- tests that exercise them directly import
`lunawave_framework.core.kernel.mem_stats` instead (see
packages/lunawave-framework/tests/core/test_mem_stats.py).
"""

from lunawave_framework.core.kernel.mem_stats import get_cpu_percent, get_rss_mb

__all__ = ["get_cpu_percent", "get_rss_mb"]
