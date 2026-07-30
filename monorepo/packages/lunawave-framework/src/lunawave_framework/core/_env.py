"""
Module: lunawave_framework.core._env

Purpose:
    Resolve filesystem locations (currently: the log file path) that core
    kernel modules need but must not hardcode, since a framework module
    cannot assume it is installed inside the app repo it is serving.

    core.log_config and core.log_reader previously did
    ``from config import BASE_DIR`` to find the app's root directory. That
    only worked because ``automation/`` and ``core/`` both lived inside the
    app repo, next to its top-level ``config.py``. Once core/logging is an
    installed package, ``import config`` is no longer a safe assumption --
    there may be no top-level ``config`` module at all, or it may belong to
    a different app entirely. This mirrors the same fix already applied to
    ``lunawave_framework.automation._env.resolve_project_root`` in Phase 1.

Resolution order for the log path (first match wins):
    1. ``LUNAWAVE_LOG_PATH`` -- explicit full path to the log file.
    2. ``LUNAWAVE_PROJECT_ROOT`` / <default_filename> -- same project-root
       env var established in Phase 1's automation extraction.
    3. Current working directory / <default_filename>.

Depends on:
    None (stdlib only, by design -- this must stay dependency-free, same
    rule as automation._env).

Subscribes to:
    None

Publishes:
    None
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_log_path(default_filename: str = "app.log") -> Path:
    """Return the path core.log_config/core.log_reader should read/write.

    Args:
        default_filename: file name to use when only a directory is known
            (i.e. resolved via LUNAWAVE_PROJECT_ROOT or cwd, not an explicit
            full-path override). A consuming app can also override just the
            filename via LUNAWAVE_LOG_FILENAME without setting a full path.
    """
    explicit = os.environ.get("LUNAWAVE_LOG_PATH")
    if explicit:
        return Path(explicit).resolve()

    filename = os.environ.get("LUNAWAVE_LOG_FILENAME", default_filename)

    root_env = os.environ.get("LUNAWAVE_PROJECT_ROOT")
    if root_env:
        return Path(root_env).resolve() / filename

    return Path.cwd().resolve() / filename
