"""
Module: automation.shared.skip_dirs

Purpose:
    Define SKIP_DIRS and walk_py_files() used by all scanner scripts to
    exclude non-source directories from file system traversal.

Responsibilities:
    - Expose a unified frozenset of directories to skip during os.walk.
    - Provide a generator that yields .py paths while respecting SKIP_DIRS.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from __future__ import annotations

import os
from pathlib import Path

# Gabungan paling lengkap dari semua SKIP_DIRS / NOISE_DIRS di seluruh automation/
SKIP_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        "dist",
        "build",
        "automation",
        "tests",
    }
)

SKIP_DIRS_FOR_OWNERSHIP: frozenset[str] = frozenset(SKIP_DIRS - {"tests", "automation"})


def walk_py_files(root: Path):
    """Generator yang yield Path absolut untuk setiap file .py di bawah root.

    Direktori yang ada di SKIP_DIRS dilewati secara rekursif sehingga
    __pycache__, .git, dsb. tidak pernah di-scan.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn
