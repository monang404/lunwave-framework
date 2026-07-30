"""
Module: automation.verify_docs.checks_files

Purpose:
    Implement large-file and empty-package checks for verify_docs.

Responsibilities:
    - Flag Python files exceeding the LOC threshold as WARN or FAIL.
    - Detect packages containing only a trivial __init__.py with no modules.

Depends on:
    - shared.check_result
    - automation.verify_docs.doc_parsing_utils

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..shared.check_result import CheckResult
from ..shared.constants import LARGE_FILE_THRESHOLD

from .doc_parsing_utils import (
    INIT_FILENAME,
    collect_py_files,
    count_lines,
)

# ---------------------------------------------------------------------------
# Cek 9 — Large Files (>300 LOC)
# ---------------------------------------------------------------------------


def check_large_files(project_root: Path) -> CheckResult:
    py_files = collect_py_files(project_root)
    large: list[tuple[str, int]] = []

    for py_rel in py_files:
        n = count_lines(project_root / py_rel)
        if n > LARGE_FILE_THRESHOLD:
            large.append((str(py_rel).replace("\\", "/"), n))

    if large:
        large.sort(key=lambda x: -x[1])
        items = [f"{path} ({loc} LOC)" for path, loc in large]
        return CheckResult(
            "Large Files",
            "WARN",
            f"{len(large)} file >{LARGE_FILE_THRESHOLD} LOC",
            items,
        )
    return CheckResult("Large Files", "PASS", f"Semua file ≤{LARGE_FILE_THRESHOLD} LOC")


# ---------------------------------------------------------------------------
# Cek 10 — Empty Packages (hanya __init__.py kosong, tidak ada modul lain)
# ---------------------------------------------------------------------------


def check_empty_packages(project_root: Path) -> CheckResult:
    py_files = collect_py_files(project_root)
    py_set = set(py_files)

    by_dir: dict[Path, list[Path]] = defaultdict(list)
    for p in py_files:
        by_dir[p.parent].append(p)

    empty_pkgs: list[str] = []

    for dir_path, files_in_dir in sorted(by_dir.items()):
        init_rel = dir_path / INIT_FILENAME
        if init_rel not in py_set:
            continue  # bukan package

        non_init = [f for f in files_in_dir if f.name != INIT_FILENAME]
        if non_init:
            continue

        dir_parts = dir_path.parts
        has_sub_py = any(
            p
            for p in py_files
            if len(p.parts) > len(dir_parts) + 1
            and p.parts[: len(dir_parts)] == dir_parts
            and p.name != INIT_FILENAME
        )
        if has_sub_py:
            continue

        init_abs = project_root / init_rel
        try:
            content = init_abs.read_text(encoding="utf-8", errors="replace").strip()
            meaningful = [
                ln for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")
            ]
            if meaningful:
                continue
        except Exception:
            continue

        label = str(dir_path).replace("\\", "/") if dir_path != Path(".") else "."
        empty_pkgs.append(label)

    if empty_pkgs:
        return CheckResult(
            "Empty Packages",
            "WARN",
            f"{len(empty_pkgs)} package kosong ditemukan",
            empty_pkgs,
        )
    return CheckResult("Empty Packages", "PASS", "Tidak ada empty package")
