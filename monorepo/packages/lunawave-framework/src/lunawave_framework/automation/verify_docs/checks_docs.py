"""
Module: automation.verify_docs.checks_docs

Purpose:
    Implement documentation structure, PATCHLOG integrity, frontmatter
    validity, and generated-marker pair checks for verify_docs.

Responsibilities:
    - Verify required docs exist and PATCHLOG IDs are unique and ordered.
    - Check frontmatter fields and BEGIN/END:GENERATED marker integrity.

Depends on:
    - shared.check_result
    - automation.verify_docs.doc_parsing_utils
    - automation.patchlog (verify() — deteksi entry gagal parse)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from ..patchlog import verify as patchlog_verify
from ..shared.check_result import CheckResult

from .doc_parsing_utils import (
    GENERATED_BEGIN_RE,
    GENERATED_END_RE,
    PATCH_ID_RE,
    REQUIRED_DOCS,
    SKIP_FRONTMATTER,
    parse_frontmatter,
    read_text,
)

# ---------------------------------------------------------------------------
# Cek 1 — Struktur docs/
# ---------------------------------------------------------------------------


def check_docs_structure(docs_dir: Path) -> CheckResult:
    project_root = docs_dir.parent
    missing = []
    for doc in REQUIRED_DOCS:
        if doc == "AI_CONTEXT.md":
            if not (project_root / doc).exists():
                missing.append(doc)
        else:
            if not (docs_dir / doc).exists():
                missing.append(f"docs/{doc}")
    if missing:
        return CheckResult(
            "Documentation Structure",
            "FAIL",
            f"{len(missing)} file wajib tidak ditemukan",
            missing,
        )
    return CheckResult(
        "Documentation Structure",
        "PASS",
        f"{len(REQUIRED_DOCS)} file wajib hadir",
    )


# ---------------------------------------------------------------------------
# Cek 2 — PATCHLOG (ID unik, urutan, sinkron frontmatter)
# ---------------------------------------------------------------------------


def check_patchlog(docs_dir: Path) -> CheckResult:
    patchlog = docs_dir / "PATCHLOG.md"
    if not patchlog.exists():
        return CheckResult("PATCHLOG", "FAIL", "docs/PATCHLOG.md tidak ditemukan")

    text = read_text(patchlog)
    ids = PATCH_ID_RE.findall(text)

    if not ids:
        return CheckResult(
            "PATCHLOG",
            "WARN",
            "Tidak ada entry dengan format PATCH-YYYY-MM-DD-NNN",
        )

    issues: list[str] = []

    # ID unik
    seen: set[str] = set()
    dupes: list[str] = []
    for pid in ids:
        if pid in seen:
            dupes.append(pid)
        seen.add(pid)
    if dupes:
        issues.append(f"ID duplikat: {', '.join(sorted(set(dupes)))}")

    # Urutan kronologis
    is_ascending = ids == sorted(ids)
    is_descending = ids == sorted(ids, reverse=True)

    if not is_ascending and not is_descending:
        issues.append("ID tidak berurutan (harus ascending atau descending)")

    # Sinkron dengan frontmatter latest_patch_id
    fm = parse_frontmatter(text)
    if fm is None:
        issues.append("Frontmatter tidak ditemukan — latest_patch_id tidak bisa diverifikasi")
    else:
        latest_fm = fm.get("latest_patch_id", "")
        expected_latest = ids[0] if is_descending else ids[-1]
        if not latest_fm:
            issues.append("Frontmatter tidak punya field 'latest_patch_id'")
        elif latest_fm != expected_latest:
            issues.append(
                f"latest_patch_id='{latest_fm}' tidak cocok dengan entry terbaru ('{expected_latest}')"
            )

    # Konsistensi struktural: ID yang ADA di file vs yang berhasil di-parse
    # penuh (format v2: Tanggal/Type/Area/Priority/Title/.../Changed Files/
    # dst., lihat automation/patchlog.py). Kalau beda, artinya ada entry
    # berformat non-baku yang diam-diam kehilangan riwayatnya di mata
    # tool AI-facing (context_pack.py, find_owner.py) -- lihat
    # PATCH-2026-07-17-074. Ini FAIL, bukan WARN, karena efeknya silent
    # data loss di tool hilir. Ditambah sejak migrasi v2: entry dengan
    # nilai enum (Type/Priority/Breaking Change/Regression Risk/Status)
    # yang tidak valid juga masuk sini via patchlog_verify().
    parse_report = patchlog_verify(text)
    if not parse_report["ok"]:
        issues.append(
            "Entry gagal di-parse penuh (format tidak baku, riwayat hilang dari "
            f"context_pack/find_owner): {', '.join(parse_report['unparsed_ids'])}"
        )
        dupes = dupes or parse_report["unparsed_ids"]  # paksa status FAIL di bawah

    if issues:
        status = "FAIL" if dupes else "WARN"
        return CheckResult("PATCHLOG", status, "", issues)
    return CheckResult("PATCHLOG", "PASS", f"{len(ids)} entries, IDs unik & sinkron")


# ---------------------------------------------------------------------------
# Cek 3 — Frontmatter semua docs/*.md
# ---------------------------------------------------------------------------


def check_frontmatter(docs_dir: Path, stale_days: int) -> CheckResult:
    today = date.today()
    issues: list[str] = []
    checked = 0

    for f in sorted(docs_dir.glob("*.md")):
        if f.name in SKIP_FRONTMATTER:
            continue
        checked += 1
        text = read_text(f)
        rel = f"docs/{f.name}"
        fm = parse_frontmatter(text)

        if fm is None:
            issues.append(f"{rel}: tidak punya frontmatter")
            continue

        for req in ("title", "last_verified"):
            if req not in fm:
                issues.append(f"{rel}: field '{req}' tidak ditemukan")

        if "owner" in fm and not fm["owner"]:
            issues.append(f"{rel}: field 'owner' ada tapi kosong")

        lv = fm.get("last_verified", "")
        if lv:
            try:
                lv_date = datetime.strptime(lv, "%Y-%m-%d").date()
                age = (today - lv_date).days
                if age < 0:
                    issues.append(f"{rel}: last_verified={lv} adalah tanggal masa depan")
                elif age > stale_days:
                    issues.append(
                        f"{rel}: last_verified={lv} sudah {age} hari lalu (ambang: {stale_days})"
                    )
            except ValueError:
                issues.append(f"{rel}: format last_verified='{lv}' tidak valid (harus YYYY-MM-DD)")

        gen = fm.get("generated", "")
        if gen and gen.lower() not in ("true", "false", "yes", "no", "manual"):
            issues.append(f"{rel}: nilai 'generated' tidak dikenali ('{gen}')")

    if not checked:
        return CheckResult("Frontmatter", "WARN", "Tidak ada file .md di docs/")
    if issues:
        return CheckResult("Frontmatter", "WARN", f"{len(issues)} issue(s)", issues)
    return CheckResult("Frontmatter", "PASS", f"{checked} file OK")


# ---------------------------------------------------------------------------
# Cek 4 — Generated Markers (BEGIN:GENERATED / END:GENERATED)
# ---------------------------------------------------------------------------


def check_generated_blocks(docs_dir: Path) -> CheckResult:
    issues: list[str] = []

    for f in sorted(docs_dir.glob("*.md")):
        text = read_text(f)
        has_begin = bool(GENERATED_BEGIN_RE.search(text))
        has_end = bool(GENERATED_END_RE.search(text))
        rel = f"docs/{f.name}"

        if has_begin and not has_end:
            issues.append(f"{rel}: BEGIN:GENERATED ada, END:GENERATED hilang")
        elif has_end and not has_begin:
            issues.append(f"{rel}: END:GENERATED ada, BEGIN:GENERATED hilang")
        elif has_begin and has_end:
            begin_pos = GENERATED_BEGIN_RE.search(text).start()  # type: ignore[union-attr]
            end_pos = GENERATED_END_RE.search(text).start()  # type: ignore[union-attr]
            if begin_pos > end_pos:
                issues.append(f"{rel}: END:GENERATED muncul sebelum BEGIN:GENERATED")

    if issues:
        return CheckResult("Generated Sections", "WARN", f"{len(issues)} broken marker(s)", issues)
    return CheckResult("Generated Sections", "PASS", "Semua marker BEGIN/END lengkap")
