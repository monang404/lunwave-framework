"""
Module: server.handlers

Purpose:
    Backward-compatibility re-export of accessor functions from context.py.
    New accessors should be added to context.py, not here.
"""

from server.handlers.context import *  # noqa: F401, F403
