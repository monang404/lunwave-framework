#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.log_config import setup_logging, log_session_start, log_session_end

Before importing the framework module, this shim sets LUNAWAVE_LOG_PATH
from the app's own config.BASE_DIR so the log file still lands at exactly
`BASE_DIR / "lunawave.log"`, same as before this extraction. See
lunawave_framework.core._env for the resolution order this feeds into.

Private module-level state (_file_handler, _console_handler) and helpers
(_console_color_enabled, _emit_banner_line) intentionally are NOT
re-exported here -- they live in, and are only meaningful as, the
framework module's own globals. Tests that need to poke at them import
`lunawave_framework.core.logging.log_config` directly (see
packages/lunawave-framework/tests/core/test_log_config.py).
"""

import os

from config import BASE_DIR

os.environ.setdefault("LUNAWAVE_LOG_PATH", str(BASE_DIR / "lunawave.log"))

from lunawave_framework.core.logging.log_config import (
    console_renderer,
    file_renderer,
    log_session_end,
    log_session_start,
    setup_logging,
    simple_renderer,
)

__all__ = [
    "file_renderer",
    "simple_renderer",
    "console_renderer",
    "setup_logging",
    "log_session_start",
    "log_session_end",
]
