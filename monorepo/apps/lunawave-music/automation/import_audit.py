#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 1 of the framework extraction (see docs/extraction/) moved this
script's implementation into the `lunawave-framework` package. This file
exists purely so existing invocations keep working unchanged:

    python automation/import_audit.py

It delegates to `lunawave_framework.automation.import_audit` and sets
LUNAWAVE_PROJECT_ROOT so the tool analyzes this app repo, not wherever the
framework package happens to be installed.
"""

import os
import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("LUNAWAVE_PROJECT_ROOT", str(_APP_ROOT))

from lunawave_framework.automation.import_audit import main

if __name__ == "__main__":
    sys.exit(main())
