#!/usr/bin/env python3
"""
Module: automation.verify_docs

Purpose:
    Orchestrate all documentation health checks and report results as a
    human-readable summary or a structured JSON payload.

Inputs:
    docs/ filesystem and project .py files.

Outputs:
    Console summary or JSON (--json); exit code 1 on any FAIL.

Side Effects:
    None (read-only analysis).

CLI:
    python automation/verify_docs_cli.py [--verbose] [--show-docstring] [--json]


Subscribes to:
    None

Publishes:
    None
"""

import argparse
import sys
from pathlib import Path

from ._env import resolve_project_root

# Windows terminals often default to a legacy codepage (e.g. cp1252) that
# can't encode characters like U+2714 (✔) or U+2022 (•) used in the summary
# output below. Reconfiguring the streams to UTF-8 (with a safe fallback
# instead of raising) prevents the checker from crashing mid-report on
# those consoles while keeping the nicer glyphs everywhere else.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = resolve_project_root()
DEFAULT_DOCS_DIR = DEFAULT_PROJECT_ROOT / "docs"

# Tambahkan SCRIPT_DIR ke sys.path agar sub-package verify_docs/ dan shared/
# bisa diimport saat script dijalankan langsung maupun via subprocess.
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.constants import LARGE_FILE_THRESHOLD
from .verify_docs.checks_coverage import (
    check_documentation_coverage,
    check_file_index,
    check_module_docstrings,
    check_report,
)
from .verify_docs.checks_docs import (
    check_docs_structure,
    check_frontmatter,
    check_generated_blocks,
    check_patchlog,
)
from .verify_docs.checks_files import check_empty_packages, check_large_files
from .verify_docs.doc_parsing_utils import STALE_DAYS_DEFAULT
from .verify_docs.render import render_json, render_summary

# ---------------------------------------------------------------------------
# Orkestrasi semua cek
# ---------------------------------------------------------------------------


def _run_all_checks(docs_dir: Path, project_root: Path, stale_days: int):
    return [
        check_docs_structure(docs_dir),
        check_patchlog(docs_dir),
        check_frontmatter(docs_dir, stale_days),
        check_generated_blocks(docs_dir),
        check_file_index(docs_dir, project_root),
        check_report(docs_dir),
        check_documentation_coverage(docs_dir, project_root),
        check_module_docstrings(project_root),
        check_large_files(project_root),
        check_empty_packages(project_root),
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Documentation Health Checker untuk LunaWave.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--docs-dir",
        default=str(DEFAULT_DOCS_DIR),
        help="Folder docs (default: dihitung dari lokasi script ini, bukan cwd)",
    )
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Root project (default: parent dari folder automation/)",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=STALE_DAYS_DEFAULT,
        help=f"Ambang hari sebelum last_verified dianggap basi (default: {STALE_DAYS_DEFAULT})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Tampilkan seluruh detail item tanpa truncation",
    )
    parser.add_argument(
        "--show-docstring",
        action="store_true",
        help="Hanya tampilkan daftar file yang belum punya module docstring standar",
    )
    parser.add_argument(
        "--show-large-files",
        action="store_true",
        help=f"Hanya tampilkan file Python >{LARGE_FILE_THRESHOLD} LOC",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON (cocok untuk CI atau integrasi tool lain)",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir).resolve()
    project_root = Path(args.project_root).resolve()

    if not docs_dir.exists():
        print(f"FAIL  Folder docs tidak ditemukan: {docs_dir}", file=sys.stderr)
        sys.exit(1)

    # --- Mode khusus (single-check) ---

    if args.show_docstring:
        result = check_module_docstrings(project_root)
        if result.status == "PASS":
            print("Semua file Python sudah punya module docstring lengkap.")
        else:
            print(f"File tanpa module docstring standar ({result.count}):")
            for item in result.items:
                print(f"  {item}")
        sys.exit(0)

    if args.show_large_files:
        result = check_large_files(project_root)
        if result.status == "PASS":
            print(f"Semua file Python ≤{LARGE_FILE_THRESHOLD} LOC.")
        else:
            print(f"File >{LARGE_FILE_THRESHOLD} LOC ({result.count}):")
            for item in result.items:
                print(f"  {item}")
        sys.exit(0)

    # --- Mode normal: jalankan semua cek ---

    results = _run_all_checks(docs_dir, project_root, args.stale_days)

    if args.json_output:
        render_json(results)
    else:
        render_summary(results, verbose=args.verbose)

    has_fail = any(r.status == "FAIL" for r in results)
    sys.exit(1 if has_fail else 0)


if __name__ == "__main__":
    main()
