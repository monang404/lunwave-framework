"""
Module: automation.verify_docs.doc_parsing_utils

Purpose:
    Provide shared constants, regex patterns, and I/O/filesystem utilities
    for all verify_docs sub-modules.

Responsibilities:
    - Expose DOCSTRING_REQUIRED_FIELDS, CHECK_WEIGHTS, and SKIP_FRONTMATTER.
    - Implement collect_py_files, parse_frontmatter, get_module_docstring,
      and filter_ignorable_inits.

Depends on:
    - shared.skip_dirs

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

from ..shared.skip_dirs import SKIP_DIRS

# ---------------------------------------------------------------------------
# Regex patterns (dipakai di berbagai cek)
# ---------------------------------------------------------------------------

# PATCHLOG format v2 (lihat automation/patchlog.py): ID sekarang adalah
# heading level-2 `## PATCH-YYYY-MM-DD-NNN`, bukan lagi field `**ID:**`
# terpisah di dalam body entry seperti format v1.
PATCH_ID_RE = re.compile(r"^##[ \t]+(PATCH-\d{4}-\d{2}-\d{2}-\d{3})[ \t]*$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
GENERATED_BEGIN_RE = re.compile(r"<!--\s*BEGIN:GENERATED\s*-->")
GENERATED_END_RE = re.compile(r"<!--\s*END:GENERATED\s*-->")

# Pattern untuk mengambil referensi path .py dari teks markdown
PY_REF_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_/\\.-]*\.py)`")

# ---------------------------------------------------------------------------
# Konstanta konfigurasi
# ---------------------------------------------------------------------------

REQUIRED_DOCS = [
    "INDEX.md",
    "STATUS.md",
    "REPORT.md",
    "PATCHLOG.md",
    "FILE_INDEX.md",
    "architecture/folder_structure.md",
    "AI_CONTEXT.md",
]

# Docstring module wajib mengandung field-field ini
DOCSTRING_REQUIRED_FIELDS = ("Purpose:", "Subscribes to:", "Publishes:")


STALE_DAYS_DEFAULT = 30
PREVIEW_COUNT = 3  # item ditampilkan sebelum "(+N more)"

# Dokumen yang di-skip dari cek frontmatter
SKIP_FRONTMATTER: frozenset[str] = frozenset({"PATCHLOG.md"})

INIT_FILENAME = "__init__.py"

# Bobot tiap cek terhadap skor akhir (total = 100)
CHECK_WEIGHTS: dict[str, int] = {
    "Documentation Structure": 20,
    "PATCHLOG": 15,
    "FILE_INDEX": 15,
    "Documentation Coverage": 15,
    "Module Docstring": 12,
    "REPORT": 8,
    "Frontmatter": 8,
    "Generated Sections": 4,
    "Large Files": 2,
    "Empty Packages": 1,
}

# Hint perintah CLI untuk cek tertentu
CHECK_HINTS: dict[str, str] = {
    "Module Docstring": "python automation/verify_docs.py --show-docstring",
    "Large Files": "python automation/verify_docs.py --show-large-files",
}

# ---------------------------------------------------------------------------
# Helper I/O
# ---------------------------------------------------------------------------


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> dict | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm


# ---------------------------------------------------------------------------
# File scanner
# ---------------------------------------------------------------------------


def collect_py_files(project_root: Path) -> list[Path]:
    """Kumpulkan semua .py file (relatif ke project_root), exclude SKIP_DIRS."""
    result: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        dp = Path(dirpath)
        for fn in filenames:
            if fn.endswith(".py"):
                result.append((dp / fn).relative_to(project_root))
    return sorted(result)


def count_lines(abs_path: Path) -> int:
    try:
        return len(read_text(abs_path).splitlines())
    except Exception:
        return 0


def get_module_docstring(abs_path: Path) -> str | None:
    """Ambil module-level docstring via AST. Return None jika tidak ada / syntax error."""
    try:
        tree = ast.parse(abs_path.read_text(encoding="utf-8", errors="replace"))
        return ast.get_docstring(tree)
    except SyntaxError:
        return None


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def fmt_items(items: list[str], verbose: bool, indent: str = "  ") -> list[str]:
    """Format daftar item (dengan bullet) dan truncation opsional."""
    if not items:
        return []
    if verbose or len(items) <= PREVIEW_COUNT:
        return [f"{indent}• {it}" for it in items]
    shown = items[:PREVIEW_COUNT]
    rest = len(items) - PREVIEW_COUNT
    return [f"{indent}• {it}" for it in shown] + [f"{indent}(+{rest} more)"]


# ---------------------------------------------------------------------------
# __init__.py significance check
# ---------------------------------------------------------------------------


def is_significant_init(abs_path: Path) -> bool:
    """True jika __init__.py berisi implementasi nyata (bukan cuma re-export
    kosong/`__all__`/import), sehingga layak ikut divalidasi seperti modul
    biasa. Mengurangi false positive dari paket yang sengaja punya
    __init__.py tipis."""
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return True  # gagal dibaca/parse -> aman diperlakukan sebagai signifikan

    body = tree.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(getattr(body[0], "value", None), ast.Constant)
    ):
        body = body[1:]  # lewati module docstring

    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "__all__":
                continue
        return True  # ada statement lain (fungsi, class, logic, dst.)
    return False


def filter_ignorable_inits(py_files: list[Path], project_root: Path) -> list[Path]:
    """Buang __init__.py yang tidak signifikan dari daftar file yang dicek.
    Dipakai oleh Module Docstring, Documentation Coverage, dan FILE_INDEX
    supaya __init__.py kosong/re-export tidak jadi false positive."""
    return [
        p
        for p in py_files
        if not (p.name == INIT_FILENAME and not is_significant_init(project_root / p))
    ]
