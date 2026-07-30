#!/usr/bin/env python3
"""
Module: automation.find_silent_excepts

Purpose:
    Scan seluruh sumber .py di repo untuk pola `except ...:` yang diikuti
    langsung oleh `pass` tanpa komentar penjelas di baris yang sama atau
    baris sebelumnya -- exception yang ditelan diam-diam.

Inputs:
    Pohon file .py di bawah PROJECT_ROOT (via automation.shared.skip_dirs).

Outputs:
    Terminal: ringkasan jumlah per-direktori + daftar lengkap temuan.
    JSON (--json): daftar temuan berisi file, baris, exception type,
    dan flag has_comment.

Side Effects:
    None (read-only scan, tidak mengubah file apa pun).

CLI:
    python automation/find_silent_excepts.py [--json]

Subscribes to:
    None

Publishes:
    None
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.skip_dirs import walk_py_files


@dataclass
class Finding:
    file: str
    line: int
    exception_type: str
    has_comment: bool


def _exception_type_label(handler: ast.ExceptHandler) -> str:
    """Render nama tipe exception yang ditangkap oleh satu ExceptHandler.

    `except:` telanjang (tanpa tipe) dilabeli "bare except".
    """
    if handler.type is None:
        return "bare except"
    try:
        return ast.unparse(handler.type)
    except Exception:
        return "unknown"


def _has_nearby_comment(lines: list[str], pass_lineno: int) -> bool:
    """Cek apakah ada komentar `#` di baris `pass` itu sendiri atau di
    baris tepat sebelumnya (baris index 0-based = pass_lineno - 2).

    "Baris sebelumnya" di sini adalah baris sebelum `pass`, bukan sebelum
    `except:` -- ini mencakup kasus umum komentar penjelas yang diselipkan
    di antara `except:` dan `pass`, mis.:
        except asyncio.CancelledError:
            # CancelledError adalah exception normal saat task di-cancel
            pass
    """
    idx_pass = pass_lineno - 1
    if 0 <= idx_pass < len(lines) and "#" in lines[idx_pass]:
        return True
    idx_before_pass = pass_lineno - 2
    if 0 <= idx_before_pass < len(lines) and lines[idx_before_pass].strip().startswith("#"):
        return True
    return False


def scan_file(path: Path, root: Path) -> list[Finding]:
    """Scan satu file .py untuk pola except/pass tanpa komentar.

    Mengembalikan list kosong kalau file gagal di-parse (mis. syntax
    error) -- file semacam itu dilewati saja, bukan bikin skrip crash.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    lines = source.splitlines()
    rel_path = str(path.relative_to(root)).replace("\\", "/")
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        if len(body) != 1 or not isinstance(body[0], ast.Pass):
            continue

        pass_stmt = body[0]
        has_comment = _has_nearby_comment(lines, pass_stmt.lineno)
        findings.append(
            Finding(
                file=rel_path,
                line=node.lineno,
                exception_type=_exception_type_label(node),
                has_comment=has_comment,
            )
        )

    return findings


def scan_repo(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in walk_py_files(root):
        findings.extend(scan_file(path, root))
    return sorted(findings, key=lambda f: (f.file, f.line))


def summarize_by_dir(findings: list[Finding]) -> dict[str, int]:
    """Hitung jumlah temuan (tanpa komentar) per direktori top-level."""
    counter: Counter[str] = Counter()
    for f in findings:
        top_dir = f.file.split("/", 1)[0] if "/" in f.file else "."
        counter[top_dir] += 1
    return dict(sorted(counter.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    findings = scan_repo(PROJECT_ROOT)
    silent = [f for f in findings if not f.has_comment]
    summary = summarize_by_dir(silent)

    if args.json_output:
        result = {
            "total": len(findings),
            "silent_total": len(silent),
            "summary_by_dir": summary,
            "findings": [asdict(f) for f in findings],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(f"Total except/pass ditemukan : {len(findings)}")
    print(f"Tanpa komentar (silent)     : {len(silent)}")
    print()
    print("Ringkasan per-direktori (silent only):")
    for d, count in summary.items():
        print(f"  {d}/: {count}")
    print()
    print("Daftar lengkap:")
    for f in findings:
        flag = "" if f.has_comment else "  <-- SILENT"
        print(f"  {f.file}:{f.line}  ({f.exception_type}){flag}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
