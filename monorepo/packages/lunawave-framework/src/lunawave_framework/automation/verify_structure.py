#!/usr/bin/env python3
"""
Module: automation.verify_structure

Purpose:
    Validate project structure health: oversized Python files and
    unimplemented stub items tracked in STATUS.md.

Inputs:
    Python source files, docs/CONSTRAINTS.md, launcher/updater.py.

Outputs:
    Console summary or JSON (--json); exit code 1 on any FAIL.

Side Effects:
    None (read-only analysis).

CLI:
    python automation/verify_structure.py [--json]


Subscribes to:
    None

Publishes:
    None
"""

import argparse
import json
import os
import sys
from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.check_result import CheckResult, _overall_status, _score
from .shared.constants import LARGE_FILE_THRESHOLD
from .shared.skip_dirs import SKIP_DIRS

CHECK_WEIGHTS: dict[str, int] = {
    "Big Files": 50,
    "Pending Items": 50,
}


# ---------------------------------------------------------------------------
# Cek 1 — file Python besar
# ---------------------------------------------------------------------------


def check_big_files(project_root: Path) -> CheckResult:
    big = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                path = Path(dirpath) / fn
                try:
                    n = sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
                    if n > LARGE_FILE_THRESHOLD:
                        rel = str(path.relative_to(project_root)).replace("\\", "/")
                        big.append((rel, n))
                except Exception:
                    pass

    big.sort(key=lambda x: -x[1])

    if not big:
        return CheckResult("Big Files", "PASS", f"Semua file di bawah {LARGE_FILE_THRESHOLD} baris")

    critical = [(r, n) for r, n in big if n > LARGE_FILE_THRESHOLD]
    items = [f"{r} ({n} baris)" for r, n in big]

    if critical:
        return CheckResult(
            "Big Files",
            "FAIL",
            f"{len(critical)} file kritis (>{LARGE_FILE_THRESHOLD} baris) perlu dipecah",
            items,
        )
    return CheckResult(
        "Big Files",
        "WARN",
        f"{len(big)} file (>{LARGE_FILE_THRESHOLD} baris) — perhatikan",
        items,
    )


# ---------------------------------------------------------------------------
# Cek 2 — dokumen/berkas pending
# ---------------------------------------------------------------------------


def check_pending_items(project_root: Path) -> CheckResult:
    issues = []
    info = []

    constraints = project_root / "docs" / "CONSTRAINTS.md"
    if not constraints.exists():
        issues.append("docs/CONSTRAINTS.md belum dibuat (disebut di STATUS.md §Sprint 3.3)")

    rfc_dir = project_root / "docs" / "kompas" / "rfc"
    if rfc_dir.exists():
        rfc_files = list(rfc_dir.glob("*.md"))
        if not rfc_files:
            issues.append("docs/rfc/ kosong — isi atau hapus (disebut di STATUS.md)")
    else:
        info.append("docs/rfc/ tidak ditemukan")

    updater = project_root / "launcher" / "updater.py"
    if updater.exists():
        content = updater.read_text(encoding="utf-8", errors="replace")
        if "pass" in content and len(content) < 500:
            issues.append("launcher/updater.py masih stub — belum diimplementasi")

    if issues:
        return CheckResult(
            "Pending Items",
            "WARN",
            f"{len(issues)} item pending",
            issues,
        )
    return CheckResult("Pending Items", "PASS", "Semua item terpenuhi", info)


def _run_all_checks(project_root: Path) -> list[CheckResult]:
    return [
        check_big_files(project_root),
        check_pending_items(project_root),
    ]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_summary(results: list[CheckResult]) -> None:
    bar = "=" * 50
    print(bar)
    print("Project Structure Health")
    print(bar)
    print()
    print("Repository")
    print(_overall_status(results))
    print()
    print("Score")
    print(f"{_score(results, CHECK_WEIGHTS)} / 100")

    for r in results:
        print()
        print(f"{r.name} — {r.status}")
        if r.message:
            print(f"  • {r.message}")
        for item in r.items:
            print(f"    - {item}")

    print()
    print(bar)


def render_json(results: list[CheckResult]) -> None:
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    pass_count = sum(1 for r in results if r.status == "PASS")
    data = {
        "checker": "verify_structure",
        "repository_status": _overall_status(results),
        "score": _score(results, CHECK_WEIGHTS),
        "pass": pass_count,
        "warn": warn_count,
        "fail": fail_count,
        "checks": [
            {
                "name": r.name,
                "status": r.status,
                "message": r.message,
                "count": r.count,
                "items": r.items,
                "current": r.current,
                "total": r.total,
                "percentage": r.percentage,
                "weight": CHECK_WEIGHTS.get(r.name),
            }
            for r in results
        ],
    }
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project Structure Health Checker untuk LunaWave.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Root project (default: parent dari folder automation/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON (cocok untuk CI atau integrasi tool lain seperti doctor.py)",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    results = _run_all_checks(project_root)

    if args.json_output:
        render_json(results)
    else:
        render_summary(results)

    has_fail = any(r.status == "FAIL" for r in results)
    sys.exit(1 if has_fail else 0)


if __name__ == "__main__":
    main()
