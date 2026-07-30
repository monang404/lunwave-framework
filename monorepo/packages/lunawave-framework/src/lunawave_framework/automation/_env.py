"""
Module: lunawave_framework.automation._env

Purpose:
    Resolve which project a checker/tool should run against.

    Before this module existed, every automation script computed its own
    PROJECT_ROOT as `Path(__file__).resolve().parent.parent` — i.e. "one
    directory above wherever this script physically lives." That assumption
    was only ever true because automation/ lived inside the app repo it
    analyzed.

    Now that automation/ is an installed package (lunawave_framework), that
    assumption breaks: the script's parent directory is the framework's
    install location, not the consuming app's repo root.

Resolution order (first match wins):
    1. Explicit ``--project-root`` / ``--root`` CLI flag, where a script
       accepts one (scripts keep their own argparse wiring; this module does
       not parse argv).
    2. ``LUNAWAVE_PROJECT_ROOT`` environment variable.
    3. Current working directory — this preserves the pre-extraction
       behavior for the common case (`cd app-repo && python -m
       lunawave_framework.automation.doctor`), since cwd equals the old
       PROJECT_ROOT in that invocation style.

Depends on:
    None (stdlib only, by design — this must stay dependency-free).

Subscribes to:
    None

Publishes:
    None
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_project_root(explicit: str | os.PathLike | None = None) -> Path:
    """Return the project root a tool should analyze.

    Args:
        explicit: value from a script's own --project-root/--root flag, if
            the caller already parsed one. Takes priority when provided.
    """
    if explicit:
        return Path(explicit).resolve()

    env_value = os.environ.get("LUNAWAVE_PROJECT_ROOT")
    if env_value:
        return Path(env_value).resolve()

    return Path.cwd().resolve()
