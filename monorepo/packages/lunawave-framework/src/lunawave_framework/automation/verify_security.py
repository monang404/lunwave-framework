#!/usr/bin/env python3
"""
Module: automation.verify_security

Purpose:
    Verify that sensitive files are listed in .gitignore to prevent
    accidental credential or database commits.

Inputs:
    .gitignore in project root.

Outputs:
    Console summary or JSON (--json); exit code 1 on any FAIL.

Side Effects:
    None (read-only analysis).

CLI:
    python automation/verify_security.py [--json]


Subscribes to:
    None

Publishes:
    None
"""

import argparse
import json
import sys
from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.check_result import CheckResult, _overall_status, _score

ADMIN_PW_PATTERNS = ("cache/admin_password.txt", "admin_password.txt")
DB_PATTERNS = ("*.db", "cache/library.db")

CHECK_WEIGHTS: dict[str, int] = {
    "Credential Ignore": 70,
    "DB Files Ignore": 30,
}


def _read_gitignore(project_root: Path) -> str | None:
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        return None
    return gitignore.read_text(encoding="utf-8", errors="replace")


def _gitignore_lines(content: str) -> list[str]:
    """Parse isi .gitignore jadi daftar baris pattern aktif (bukan komentar,
    bukan baris kosong). PATCH-2026-07-16-001: sebelumnya kode ini pakai
    substring match ke SELURUH isi file, jadi pattern yang cuma muncul di
    dalam komentar (mis. `# TODO: ignore cache/admin_password.txt`) salah
    dianggap PASS. Parsing baris-per-baris menutup celah itu."""
    lines = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _pattern_covered(patterns: tuple[str, ...], gitignore_lines: list[str]) -> bool:
    return any(p in line for line in gitignore_lines for p in patterns)


def check_credential_ignore(project_root: Path) -> CheckResult:
    content = _read_gitignore(project_root)
    if content is None:
        return CheckResult(
            "Credential Ignore",
            "FAIL",
            ".gitignore tidak ditemukan!",
        )
    if _pattern_covered(ADMIN_PW_PATTERNS, _gitignore_lines(content)):
        return CheckResult(
            "Credential Ignore",
            "PASS",
            "cache/admin_password.txt terlindungi di .gitignore",
        )
    return CheckResult(
        "Credential Ignore",
        "FAIL",
        "cache/admin_password.txt TIDAK ada di .gitignore — risiko commit credential!",
    )


def check_db_files_ignore(project_root: Path) -> CheckResult:
    content = _read_gitignore(project_root)
    if content is None:
        return CheckResult(
            "DB Files Ignore",
            "FAIL",
            ".gitignore tidak ditemukan!",
        )
    if _pattern_covered(DB_PATTERNS, _gitignore_lines(content)):
        return CheckResult("DB Files Ignore", "PASS", "File .db di-ignore")
    return CheckResult(
        "DB Files Ignore",
        "WARN",
        "File .db mungkin tidak di-ignore — cek .gitignore",
    )


def _run_all_checks(project_root: Path) -> list[CheckResult]:
    return [
        check_credential_ignore(project_root),
        check_db_files_ignore(project_root),
    ]


def render_summary(results: list[CheckResult]) -> None:
    bar = "=" * 50
    print(bar)
    print("Security Health")
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

    print()
    print(bar)


def render_json(results: list[CheckResult]) -> None:
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    pass_count = sum(1 for r in results if r.status == "PASS")
    data = {
        "checker": "verify_security",
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Security Health Checker untuk LunaWave.",
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
