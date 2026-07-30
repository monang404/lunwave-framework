#!/usr/bin/env python3
"""
Module: automation.architecture_lint

Purpose:
    Validate inter-layer import boundaries against the architecture rules
    defined in docs/architecture/dependency_rules.md.

Inputs:
    Python source files in project root (or --file for a single file).

Outputs:
    Console violation report or JSON (--json) with pass/warn/fail status.

Side Effects:
    None (read-only static analysis).

CLI:
    python automation/architecture_lint.py [--file PATH] [--strict] [--json]


Subscribes to:
    None

Publishes:
    None
"""

import argparse
import ast
import json
import os
import sys

# Fix Unicode output di Windows (cp1252 tidak support emoji/karakter UTF-8)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.arch_rules import ALLOWED, Violation, is_known
from .shared.check_result import CheckResult as SharedCheckResult
from .shared.skip_dirs import SKIP_DIRS


def path_to_layer(rel_path: str) -> str | None:
    parts = rel_path.replace("\\", "/").split("/")
    if not parts:
        return None
    top = parts[0]
    return top if top in ALLOWED else None


def module_to_layer(module: str) -> str | None:
    top = module.split(".")[0]
    return top if top in ALLOWED else None


# ---------------------------------------------------------------------------
# Per-file check
# ---------------------------------------------------------------------------


def check_file(path: Path, project_root: Path) -> list[Violation]:
    rel = str(path.relative_to(project_root)).replace("\\", "/")
    importer_layer = path_to_layer(rel)

    if importer_layer is None:
        return []

    allowed_for_layer = ALLOWED.get(importer_layer)
    if allowed_for_layer is None:
        return []

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_layer = module_to_layer(alias.name)
                if imported_layer and imported_layer != importer_layer:
                    if imported_layer not in allowed_for_layer:
                        violations.append(
                            Violation(
                                file=rel,
                                line=node.lineno,
                                importer_layer=importer_layer,
                                imported_module=alias.name,
                                imported_layer=imported_layer,
                            )
                        )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_layer = module_to_layer(node.module)
                if imported_layer and imported_layer != importer_layer:
                    if imported_layer not in allowed_for_layer:
                        violations.append(
                            Violation(
                                file=rel,
                                line=node.lineno,
                                importer_layer=importer_layer,
                                imported_module=node.module,
                                imported_layer=imported_layer,
                            )
                        )

    return violations


# ---------------------------------------------------------------------------
# Scan seluruh project
# ---------------------------------------------------------------------------


def scan_project(project_root: Path, target_file: str | None = None) -> list[Violation]:
    all_violations = []

    if target_file:
        path = (project_root / target_file).resolve()
        if not path.exists():
            print(f"❌ File tidak ditemukan: {path}", file=sys.stderr)
            sys.exit(1)
        return check_file(path, project_root)

    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                path = Path(dirpath) / fn
                all_violations.extend(check_file(path, project_root))

    return all_violations


# ---------------------------------------------------------------------------
# collect_results — bungkus hasil akhir jadi shared.CheckResult
# ---------------------------------------------------------------------------


def collect_results(
    project_root: Path,
    target_file: str | None = None,
) -> dict:
    """Jalankan scan dan kembalikan data mentah sebagai dict.

    Tidak melakukan print apapun. Semua informasi ada di return value.
    """
    violations = scan_project(project_root, target_file)
    new_violations = [v for v in violations if not is_known(v)]
    known_violations = [v for v in violations if is_known(v)]

    files_scanned = 0
    imports_checked = 0
    if target_file:
        path = (project_root / target_file).resolve()
        if path.exists():
            files_scanned = 1
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports_checked += 1
            except SyntaxError:
                pass
    else:
        for dirpath, dirnames, filenames in os.walk(project_root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".py"):
                    files_scanned += 1
                    fp = Path(dirpath) / fn
                    try:
                        source = fp.read_text(encoding="utf-8", errors="replace")
                        tree = ast.parse(source)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.Import, ast.ImportFrom)):
                                imports_checked += 1
                    except SyntaxError:
                        pass

    has_new = len(new_violations) > 0
    if not violations:
        repository_status = "PASS"
    elif has_new:
        repository_status = "FAIL"
    else:
        repository_status = "WARN"

    check_status = "FAIL" if has_new else ("WARN" if known_violations else "PASS")
    if check_status == "PASS":
        score = 100
        message = "Tidak ada violation import boundary"
    elif check_status == "WARN":
        score = 80
        message = f"{len(known_violations)} known violation belum di-fix (lihat REPORT.md)"
    else:
        score = max(0, 100 - 20 * len(new_violations))
        message = f"{len(new_violations)} violation baru ditemukan"

    # Bungkus hasil cek sebagai shared.CheckResult
    cr = SharedCheckResult(
        name="Import Boundaries",
        status=check_status,
        message=message,
        items=[
            f"{v['file']}:{v['line']} — {v['importer_layer']}/ → {v['imported_layer']}/"
            for v in [v.to_dict() for v in new_violations]
        ],
    )

    checks = [
        {
            "name": cr.name,
            "status": cr.status,
            "message": cr.message,
            "count": cr.count,
            "items": cr.items,
            "current": cr.current,
            "total": cr.total,
            "percentage": cr.percentage,
            "weight": 100,
        }
    ]

    return {
        "checker": "architecture_lint",
        "repository_status": repository_status,
        "score": score,
        "pass": 1 if check_status == "PASS" else 0,
        "warn": 1 if check_status == "WARN" else 0,
        "fail": 1 if check_status == "FAIL" else 0,
        "checks": checks,
        "files_scanned": files_scanned,
        "imports_checked": imports_checked,
        "new_violations": len(new_violations),
        "known_violations": len(known_violations),
        "violations": [v.to_dict() for v in new_violations],
        "known_violation_list": [v.to_dict() for v in known_violations],
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_text(
    data: dict,
    violations: list[Violation],
    known_violations: list[Violation],
    show_known: bool,
) -> None:
    """Cetak output teks — identik dengan perilaku sebelumnya."""
    if not violations and not known_violations:
        print("✅ architecture_lint: tidak ada violation.")
        return

    new_violations = [v for v in violations if not is_known(v)]

    if new_violations:
        print(f"\n❌ architecture_lint: {len(new_violations)} VIOLATION BARU ditemukan!\n")
        for v in new_violations:
            print(str(v))
        print()

    if known_violations and show_known:
        print(
            f"\n⚠️  {len(known_violations)} known violation (sudah terdokumentasi di REPORT.md, belum di-fix):\n"
        )
        for v in known_violations:
            print(str(v))
        print()
    elif known_violations and not show_known:
        print(
            f"ℹ️  {len(known_violations)} known violation diabaikan "
            f"(tambah --show-known untuk lihat). Lihat REPORT.md §F-06."
        )


def render_json(data: dict) -> None:
    """Cetak output JSON — format konsisten dengan verify_docs.py."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Validasi batas arsitektur LunaWave.")
    parser.add_argument("--file", help="Cek hanya 1 file (path relatif dari project root)")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print violations tapi exit 0 (untuk mode informational, bukan blocking)",
    )
    parser.add_argument(
        "--show-known",
        action="store_true",
        help="Tampilkan juga known/documented violations (default: suppress)",
    )
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON (cocok untuk CI atau integrasi tool lain seperti doctor.py)",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    data = collect_results(root, args.file)

    if args.json_output:
        render_json(data)
    else:
        violations = scan_project(root, args.file)
        new_v = [v for v in violations if not is_known(v)]
        known_v = [v for v in violations if is_known(v)]
        render_text(data, violations, known_v, args.show_known)

        if new_v and not args.warn_only:
            print(
                "💡 Tips: Jika violation ini disengaja (temporary), tambahkan ke KNOWN_VIOLATIONS\n"
                "   di automation/architecture_lint.py dan dokumentasikan di REPORT.md.\n"
                "   Untuk skip pre-commit sementara: git commit --no-verify"
            )

    has_new = data["new_violations"] > 0
    if args.warn_only:
        sys.exit(0)
    elif has_new:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
