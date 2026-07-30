#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.log_reader import parse_line, tail, stats

Before importing the framework module, this shim sets LUNAWAVE_LOG_PATH
from the app's own config.BASE_DIR, same as core/log_config.py, so both
modules agree on exactly which file (`BASE_DIR / "lunawave.log"`) to read.
"""

import os

from config import BASE_DIR

os.environ.setdefault("LUNAWAVE_LOG_PATH", str(BASE_DIR / "lunawave.log"))

from lunawave_framework.core.logging.log_reader import parse_line, stats, tail

__all__ = ["parse_line", "tail", "stats"]
