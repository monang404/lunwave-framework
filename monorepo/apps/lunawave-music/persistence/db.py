#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 4 of the framework extraction (see docs/extraction/ and
docs/adr/0014-persistence-split.md) moved this module's implementation
(100% generic connection-lifecycle mechanism, no music vocabulary at
all) to lunawave_framework.core.storage.db. This file exists purely so
existing imports keep working unchanged:

    from persistence.db import DatabaseConnection

Per ADR 0014, the app still owns its full schema.sql (passed in as
`schema_path` at call time) -- the framework class itself never reads
or ships a schema.
"""

from lunawave_framework.core.storage.db import DatabaseConnection

__all__ = ["DatabaseConnection"]
