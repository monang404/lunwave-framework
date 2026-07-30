"""
Module: core.log_categories

Purpose:
    Closed set of `category` constants for structured logging, per the
    §4 table in docs/rfc/logging_standard/LOGGING_STANDARD.md (15 rows;
    the audit/implementation-plan docs say "14 kategori standar" but the
    actual table has 15 -- this module follows the table, the normative
    spec, not the prose count). Category groups log lines by *domain of
    the event*, never by the Python module/file that emitted them (see
    §4 anti-pattern #7).

Responsibilities:
    - Provide one string constant per standard category, so a typo in a
      category name is caught by ImportError/AttributeError at import time
      instead of silently becoming a new, uncontrolled free-form string.
    - Nothing else. This module has zero behavior -- it is a vocabulary,
      not a helper (see core.log_context for the correlation-id helpers).

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    N/A -- module-level string constants, immutable.
"""

# Closed list -- do NOT add categories beyond these 14 without updating
# LOGGING_STANDARD.md §4 first (design principle #9: simple, memorizable,
# not an ever-growing enterprise taxonomy).
LC_LIFECYCLE = "lifecycle"
LC_SESSION = "session"
LC_AUTH = "auth"
LC_COMMAND = "command"
LC_EVENT = "event"
LC_PLAYBACK = "playback"
LC_QUEUE = "queue"
LC_RADIO = "radio"
LC_DOWNLOAD = "download"
LC_RESOLVE = "resolve"
LC_CACHE = "cache"
LC_PERSISTENCE = "persistence"
LC_EXTERNAL = "external"
LC_SECURITY = "security"
LC_SYSTEM = "system"

ALL_CATEGORIES = (
    LC_LIFECYCLE,
    LC_SESSION,
    LC_AUTH,
    LC_COMMAND,
    LC_EVENT,
    LC_PLAYBACK,
    LC_QUEUE,
    LC_RADIO,
    LC_DOWNLOAD,
    LC_RESOLVE,
    LC_CACHE,
    LC_PERSISTENCE,
    LC_EXTERNAL,
    LC_SECURITY,
    LC_SYSTEM,
)
