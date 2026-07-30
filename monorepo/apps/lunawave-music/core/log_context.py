#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 2 of the framework extraction (see docs/extraction/) moved this
module's implementation into the `lunawave-framework` package. This file
exists purely so existing imports keep working unchanged:

    from core.log_context import bind_session, unbind_session, ...

It re-exports every public name from
`lunawave_framework.core.logging.log_context` unchanged.
"""

from lunawave_framework.core.logging.log_context import (
    bind_correlation,
    bind_request,
    bind_session,
    unbind_correlation,
    unbind_request,
    unbind_session,
)

__all__ = [
    "bind_session",
    "unbind_session",
    "bind_request",
    "unbind_request",
    "bind_correlation",
    "unbind_correlation",
]
