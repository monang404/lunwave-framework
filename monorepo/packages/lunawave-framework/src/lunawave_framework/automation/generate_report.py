#!/usr/bin/env python3
"""
Module: automation.generate_report

Purpose:
    Generate and inject project statistics into the <!-- BEGIN:GENERATED -->
    block of docs/REPORT.md.

Inputs:
    Python/JS/CSS source files and SQLite databases in project root.

Outputs:
    Updated docs/REPORT.md (or stdout with --dry-run).

Side Effects:
    Overwrites the generated statistics section in REPORT.md.

CLI:
    python automation/generate_report.py [--dry-run]


Subscribes to:
    None

Publishes:
    None
"""

import argparse
import ast
import io
import os
import re
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from datetime import date
from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.constants import LARGE_FILE_THRESHOLD
from .shared.generated_block import replace_marker_block
from .shared.skip_dirs import SKIP_DIRS

MARKER_BEGIN = "<!-- BEGIN:GENERATED -->"
MARKER_END = "<!-- END:GENERATED -->"


# ---------------------------------------------------------------------------
# Metric collectors
# ---------------------------------------------------------------------------


def count_py_files(root: Path) -> int:
    count = 0
    for _dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        count += sum(1 for f in filenames if f.endswith(".py"))
    return count


def count_folders(root: Path) -> int:
    count = 0
    for _dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        count += len(dirnames)
    return count


def count_classes_and_functions(root: Path) -> tuple[int, int]:
    classes = 0
    functions = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = Path(dirpath) / fn
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes += 1
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions += 1
    return classes, functions


def count_lines(root: Path, ext: str) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(ext):
                try:
                    total += sum(
                        1 for _ in (Path(dirpath) / fn).open(encoding="utf-8", errors="replace")
                    )
                except Exception:
                    pass
    return total


def count_js_files(root: Path) -> int:
    count = 0
    for _dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        count += sum(1 for f in filenames if f.endswith(".js") and not f.endswith(".min.js"))
    return count


def count_css_files(root: Path) -> int:
    count = 0
    for _dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        count += sum(1 for f in filenames if f.endswith(".css") and not f.endswith(".min.css"))
    return count


def db_size_str(path: Path) -> str:
    if not path.exists():
        return "tidak ditemukan"
    kb = path.stat().st_size / 1024
    wal = path.with_suffix(".db-wal")
    if wal.exists():
        wal_kb = wal.stat().st_size / 1024
        return f"{kb:.0f} KB (+ WAL {wal_kb:.0f} KB)"
    return f"{kb:.0f} KB"


def biggest_py_files(root: Path, n: int = 5) -> list[tuple[str, int]]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                path = Path(dirpath) / fn
                try:
                    lines = sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
                    rel = str(path.relative_to(root)).replace("\\", "/")
                    files.append((rel, lines))
                except Exception:
                    pass
    files.sort(key=lambda x: -x[1])
    return files[:n]


# ---------------------------------------------------------------------------
# Build generated block
# ---------------------------------------------------------------------------


def build_generated_block(root: Path) -> str:
    py_count = count_py_files(root)
    js_count = count_js_files(root)
    css_count = count_css_files(root)
    folder_count = count_folders(root)
    class_count, fn_count = count_classes_and_functions(root)
    py_lines = count_lines(root, ".py")
    js_lines = count_lines(root / "web", ".js")
    css_lines = count_lines(root / "web", ".css")

    db_main = db_size_str(root / "data" / "lunawave.db")
    db_lib = db_size_str(root / "cache" / "library.db")

    top_files = biggest_py_files(root)

    lines = [
        f"> **Auto-generated:** {date.today().isoformat()} oleh `automation/generate_report.py`  \n"
        f"> **Jangan edit blok ini secara manual.**\n",
        "",
        "| Metrik | Nilai |",
        "|--------|-------|",
        f"| Total folder (ekskl. `__pycache__`, `.git`) | {folder_count} |",
        f"| Total file `.py` (source, ekskl. `__pycache__`) | {py_count} |",
        f"| Total file `.js` (ekskl. `.min.js`) | {js_count} |",
        f"| Total file `.css` (ekskl. `.min.css`) | {css_count} |",
        f"| Total class (Python) | {class_count} |",
        f"| Total function/method (Python) | {fn_count} |",
        f"| Total baris Python | {py_lines:,} |",
        f"| Total baris JS (web/) | {js_lines:,} |",
        f"| Total baris CSS (web/) | {css_lines:,} |",
        f"| Ukuran DB utama (`data/lunawave.db`) | {db_main} |",
        f"| Ukuran DB library (`cache/library.db`) | {db_lib} |",
        "",
        "### File Python Terbesar\n",
        "| File | Baris |",
        "|------|-------|",
    ]

    for rel, n in top_files:
        flag = " ⚠️" if n > LARGE_FILE_THRESHOLD else ""
        lines.append(f"| `{rel}` | {n}{flag} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Inject
# ---------------------------------------------------------------------------


def inject_into_file(target: Path, generated_block: str, dry_run: bool) -> None:
    original = target.read_text(encoding="utf-8")

    if MARKER_BEGIN not in original:
        # Fallback lokal: cari section "## Statistik Project" dan inject
        stats_match = re.search(r"(## Statistik Project\n)", original)
        if stats_match:
            insert_pos = stats_match.end()
            rest = original[insert_pos:]
            table_end = re.search(r"\n\n---", rest)
            if table_end:
                new_content = (
                    original[:insert_pos]
                    + f"\n{MARKER_BEGIN}\n{generated_block}\n{MARKER_END}\n"
                    + original[insert_pos + table_end.start() :]
                )
            else:
                new_content = (
                    original.rstrip() + f"\n\n{MARKER_BEGIN}\n{generated_block}\n{MARKER_END}\n"
                )
        else:
            new_content = (
                original.rstrip() + f"\n\n{MARKER_BEGIN}\n{generated_block}\n{MARKER_END}\n"
            )
    else:
        new_content = replace_marker_block(original, generated_block, MARKER_BEGIN, MARKER_END)

    # Update frontmatter tanggal scan
    new_content = re.sub(
        r"(> \*\*Tanggal Scan:\*\* )\d{4}-\d{2}-\d{2}",
        f"\\g<1>{date.today().isoformat()}",
        new_content,
    )
    # Update last_verified
    new_content = re.sub(
        r"(last_verified:\s*)\d{4}-\d{2}-\d{2}",
        f"\\g<1>{date.today().isoformat()}",
        new_content,
        count=1,
    )

    if dry_run:
        print(new_content)
    else:
        target.write_text(new_content, encoding="utf-8")
        print(f"✅ {target.relative_to(PROJECT_ROOT)} diperbarui ({date.today().isoformat()})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Update statistik di REPORT.md.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    target = root / "docs" / "REPORT.md"

    if not target.exists():
        print(f"❌ REPORT.md tidak ditemukan: {target}", file=sys.stderr)
        sys.exit(1)

    print("📊 Menghitung metrik...", file=sys.stderr)
    block = build_generated_block(root)
    inject_into_file(target, block, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
