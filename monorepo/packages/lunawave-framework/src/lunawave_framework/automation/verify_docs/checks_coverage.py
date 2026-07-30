"""
Module: automation.verify_docs.checks_coverage

Purpose:
    Implement FILE_INDEX sync, REPORT validation, module docstring coverage,
    and overall documentation coverage checks for verify_docs.

Responsibilities:
    - Detect .py files absent from FILE_INDEX.md or REPORT.md.
    - Verify module docstrings contain all required fields.

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

from pathlib import Path

from ..shared.check_result import CheckResult

from .doc_parsing_utils import (
    DOCSTRING_REQUIRED_FIELDS,
    GENERATED_BEGIN_RE,
    GENERATED_END_RE,
    PY_REF_RE,
    collect_py_files,
    filter_ignorable_inits,
    get_module_docstring,
    read_text,
)

# ---------------------------------------------------------------------------
# Cek 5 — FILE_INDEX (sinkron dengan .py di disk)
# ---------------------------------------------------------------------------


def check_file_index(docs_dir: Path, project_root: Path) -> CheckResult:
    fi_path = docs_dir / "FILE_INDEX.md"
    if not fi_path.exists():
        return CheckResult("FILE_INDEX", "FAIL", "docs/FILE_INDEX.md tidak ditemukan")

    fi_text = read_text(fi_path)
    actual_py = collect_py_files(project_root)
    checked_py = filter_ignorable_inits(actual_py, project_root)
    issues: list[str] = []

    missing_from_index: list[str] = []
    for py_path in checked_py:
        py_str = str(py_path).replace("\\", "/")
        py_name = py_path.name
        if py_str not in fi_text and py_name not in fi_text:
            missing_from_index.append(py_str)

    for m in missing_from_index:
        issues.append(f"Belum ada di FILE_INDEX: {m}")

    indexed_refs = {m.group(1).replace("\\", "/") for m in PY_REF_RE.finditer(fi_text)}
    actual_names = {p.name for p in actual_py}

    for ref in sorted(indexed_refs):
        ref_path = project_root / ref
        if not ref_path.exists() and Path(ref).name not in actual_names:
            issues.append(f"Entry di FILE_INDEX tidak ada di disk: {ref}")

    total = len(checked_py)
    current = total - len(missing_from_index)

    if issues:
        has_stale = any("tidak ada di disk" in i for i in issues)
        status = "FAIL" if has_stale else "WARN"
        result = CheckResult("FILE_INDEX", status, f"{len(issues)} issue(s)", issues)
    else:
        result = CheckResult("FILE_INDEX", "PASS", f"{total} file Python terdaftar")

    result.current = current
    result.total = total
    return result


# ---------------------------------------------------------------------------
# Cek 6 — REPORT (generated section valid)
# ---------------------------------------------------------------------------


def check_report(docs_dir: Path) -> CheckResult:
    path = docs_dir / "REPORT.md"
    if not path.exists():
        return CheckResult("REPORT", "FAIL", "docs/REPORT.md tidak ditemukan")

    text = read_text(path)
    has_begin = bool(GENERATED_BEGIN_RE.search(text))
    has_end = bool(GENERATED_END_RE.search(text))

    if has_begin and not has_end:
        return CheckResult("REPORT", "WARN", "BEGIN:GENERATED ada, END:GENERATED hilang")
    if has_end and not has_begin:
        return CheckResult("REPORT", "WARN", "END:GENERATED ada, BEGIN:GENERATED hilang")

    if has_begin and has_end:
        m_begin = GENERATED_BEGIN_RE.search(text)
        m_end = GENERATED_END_RE.search(text)
        if m_begin and m_end:
            inner = text[m_begin.end() : m_end.start()].strip()
            if not inner:
                return CheckResult("REPORT", "WARN", "Generated section kosong (tidak ada konten)")

    return CheckResult("REPORT", "PASS", "Generated section valid")


# ---------------------------------------------------------------------------
# Cek 7 — Module Docstring Coverage
# ---------------------------------------------------------------------------


def check_module_docstrings(project_root: Path) -> CheckResult:
    py_files = filter_ignorable_inits(collect_py_files(project_root), project_root)
    missing: list[str] = []

    for py_rel in py_files:
        docstring = get_module_docstring(project_root / py_rel)
        rel_str = str(py_rel).replace("\\", "/")

        if not docstring:
            missing.append(f"{rel_str} (no module docstring)")
            continue

        missing_fields = [f for f in DOCSTRING_REQUIRED_FIELDS if f not in docstring]
        if missing_fields:
            missing.append(f"{rel_str} (missing: {', '.join(missing_fields)})")

    total = len(py_files)
    current = total - len(missing)
    result = CheckResult(
        "Module Docstring",
        "WARN" if missing else "PASS",
        f"{current}/{total} file OK" if missing else f"{total} file OK",
        missing,
    )
    result.current = current
    result.total = total
    return result


# ---------------------------------------------------------------------------
# Cek 8 — Documentation Coverage (file .py belum tercatat di FILE_INDEX/REPORT)
# ---------------------------------------------------------------------------


def check_documentation_coverage(docs_dir: Path, project_root: Path) -> CheckResult:
    """File Python baru wajib disebut minimal di salah satu dari FILE_INDEX.md
    atau REPORT.md (cukup nama file, tidak harus path lengkap)."""
    fi_path = docs_dir / "FILE_INDEX.md"
    report_path = docs_dir / "REPORT.md"

    fi_text = read_text(fi_path) if fi_path.exists() else ""
    report_text = read_text(report_path) if report_path.exists() else ""

    py_files = filter_ignorable_inits(collect_py_files(project_root), project_root)
    missing: list[str] = []

    for py_rel in py_files:
        py_str = str(py_rel).replace("\\", "/")
        py_name = py_rel.name
        in_index = py_str in fi_text or py_name in fi_text
        in_report = py_str in report_text or py_name in report_text
        if not in_index and not in_report:
            missing.append(py_str)

    total = len(py_files)
    current = total - len(missing)
    result = CheckResult(
        "Documentation Coverage",
        "WARN" if missing else "PASS",
        (
            f"{len(missing)} file belum disebut di FILE_INDEX maupun REPORT"
            if missing
            else f"{total} file terdokumentasi"
        ),
        missing,
    )
    result.current = current
    result.total = total
    return result
