#!/usr/bin/env python3
"""
Module: automation.patchlog

Purpose:
    Baca/tulis docs/PATCHLOG.md terstruktur — format v2 (field-based).
    ID PATCH-YYYY-MM-DD-NNN, NNN = total entries berjalan (bukan reset per
    hari), tetap immutable begitu ditulis.

    Tiap entry adalah heading level-2 `## PATCH-YYYY-MM-DD-NNN` (satu ID =
    satu sumber judul, bisa dijadikan anchor link) diikuti field
    `**Nama:** nilai` atau `**Nama:**\nblok multi-baris`. Urutan field selalu
    sama persis di semua entry (lihat FIELD_ORDER di bawah) supaya predictable
    untuk AI/tool maupun manusia:

        Tanggal, Timestamp, Git Branch, Git Commit   (auto-generated)
        Type, Area, Priority                          (semi-otomatis)
        Title, Reason, Root Cause, Solution            (manual)
        Changed Files                                  (auto, dari --files)
        Changed Symbols                                (manual)
        Tests, Breaking Change, Regression Risk,
        Related Patch, Status, Notes                   (manual)

    Klasifikasi field:
      - Auto-generated : ID, Tanggal, Timestamp, Git Branch, Git Commit,
        Changed Files — tidak pernah diketik manual, selalu benar.
      - Semi-otomatis  : Type (wajib via --type, TIDAK ditebak), Area (boleh
        disarankan dari prefix path --files, tapi wajib dikonfirmasi via
        --area — tidak pernah dipaksa), Priority (--priority, default
        "Medium" bila tidak diisi).
      - Manual         : Title, Reason, Root Cause, Solution, Changed
        Symbols, Tests, Breaking Change, Regression Risk, Related Patch,
        Status, Notes — butuh penilaian manusia, tidak pernah ditebak
        otomatis oleh script.

Subscribes to:
    None

Publishes:
    None

CLI:
    python automation/patchlog.py add \
        --type Fix --area Player --priority High \
        --title "Pause tidak sinkron ulang setelah reconnect WebSocket" \
        --reason "User report" \
        --files web/static/js/store.js,web/static/js/ws.js \
        --symbols "markPendingToggle(),isPendingToggleActive()" \
        --tests "vitest, manual Android" \
        --breaking No --risk Low --status Merged \
        --related PATCH-2026-07-16-065 \
        --root-cause "..." --solution "..." --notes "..."
        # Root Cause/Solution/Notes juga bisa lewat --root-cause-file dst.,
        # atau dibuka di $EDITOR kalau tidak ada flag maupun file sama sekali
        # dan sesi berjalan interaktif (isatty).

    python automation/patchlog.py latest --n 5 [--json]
    python automation/patchlog.py history --file <path> [--json]
    python automation/patchlog.py symbol <nama-simbol> [--json]
    python automation/patchlog.py verify [--json]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

PATCHLOG = PROJECT_ROOT / "docs" / "PATCHLOG.md"

# ---------------------------------------------------------------------------
# Parsing — format v2
# ---------------------------------------------------------------------------

# Heading per entry: satu-satunya sumber ID (menggantikan **ID:** field lama
# dari format v1).
ENTRY_HEADING_RE = re.compile(
    r"^##[ \t]+(?P<id>PATCH-\d{4}-\d{2}-\d{2}-\d{3})[ \t]*$", re.MULTILINE
)

# Regex generik satu pola untuk SEMUA field "**Nama:** nilai" atau
# "**Nama:**\nblok...". Menambah field baru di masa depan tidak perlu regex
# baru per field — cukup tambah namanya ke FIELD_ORDER.
FIELD_RE = re.compile(
    r"\*\*(?P<name>[A-Za-z ]+):\*\*[ \t]*\n?(?P<value>.*?)(?=\n\*\*[A-Za-z ]+:\*\*|\Z)",
    re.DOTALL,
)

LIST_FIELDS = ("Changed Files", "Changed Symbols")

# Field yang nilainya harus salah satu dari enum tetap (dipakai verify()).
# "Unclassified" hanya sah untuk entry hasil migrasi dari format v1 — jujur
# menandakan belum diklasifikasi, bukan pura-pura sudah lengkap.
ENUM_FIELDS = {
    "Type": {
        "Feature",
        "Fix",
        "Refactor",
        "Performance",
        "Cleanup",
        "Security",
        "Test",
        "Docs",
        "Build",
        "CI",
        "Breaking",
        "Unclassified",
    },
    "Priority": {"Critical", "High", "Medium", "Low", "Unclassified"},
    "Breaking Change": {"Yes", "No", "Unclassified"},
    "Regression Risk": {"Critical", "High", "Medium", "Low", "Unclassified"},
    "Status": {"Draft", "Merged", "Released", "Reverted", "Deprecated", "Unclassified"},
}

# Field header (grouped, tanpa baris kosong di antaranya) vs field body
# (blok panjang, dipisah baris kosong sebelum/sesudah) — urutan ini WAJIB
# konsisten di semua entry, baru maupun hasil migrasi.
HEADER_FIELDS = [
    "Tanggal",
    "Timestamp",
    "Git Branch",
    "Git Commit",
    "Type",
    "Area",
    "Priority",
    "Title",
]
INLINE_FIELDS = ["Reason", "Tests", "Breaking Change", "Regression Risk", "Related Patch", "Status"]
BLOCK_FIELDS = ["Root Cause", "Solution", "Notes"]
FIELD_ORDER = (
    HEADER_FIELDS
    + ["Reason", "Root Cause", "Solution"]
    + list(LIST_FIELDS)
    + [
        "Tests",
        "Breaking Change",
        "Regression Risk",
        "Related Patch",
        "Status",
        "Notes",
    ]
)


def _split_into_chunks(text: str) -> list[str]:
    """Pecah body PATCHLOG per-entry.

    PATCH-2026-07-16-001: split via separator "\n\n---\n\n" untuk hindari
    catastrophic backtracking dari regex DOTALL raksasa lama. PATCH-2026-07-17-074:
    separator itu ternyata rapuh -- entry yang ditulis manual (tanpa baris
    kosong presisi di sekitar "---") gagal ke-split dan diam-diam MENGHILANG
    (5 entry hilang tanpa error/warning di docs/PATCHLOG.md nyata). Fix: split
    di setiap baris "---" berdiri sendiri (toleran spasi di sekitarnya).
    Masih O(n) per chunk kecil -- tidak membuka lagi celah backtracking 001.

    Dipertahankan APA ADANYA saat migrasi ke format v2 (sudah teruji) --
    hanya titik pemecah per-entry di dalam chunk yang berubah, dari heading
    bebas (v1: "## [tanggal] judul-bebas...") menjadi heading ber-ID (v2:
    "## PATCH-..."), yang justru lebih ketat & sulit salah tulis manual.
    """
    return re.split(r"\n[ \t]*---[ \t]*\n", text)


def parse_entry_fields(chunk: str) -> dict:
    """Parse semua field `**Nama:** nilai` di satu chunk entry menjadi dict."""
    fields: dict = {}
    for m in FIELD_RE.finditer(chunk):
        name = m.group("name").strip()
        value = m.group("value").strip()
        fields[name] = value
    for list_field in LIST_FIELDS:
        if list_field in fields:
            fields[list_field] = re.findall(r"-\s*`([^`]+)`", fields[list_field])
    return fields


def parse_entries(text: str) -> list[dict]:
    """Parse seluruh PATCHLOG.md jadi list of dict, satu per entry.

    Kontrak stabil dipakai oleh automation/hotspot.py dan
    automation/context_pack.py: setiap dict SELALU punya key "id" (str) dan
    "files" (list[str]), berapa pun field lain berubah di masa depan.
    """
    entries = []
    for chunk in _split_into_chunks(text):
        head_m = ENTRY_HEADING_RE.search(chunk)
        if not head_m:
            continue
        fields = parse_entry_fields(chunk)
        if "Tanggal" not in fields or "Changed Files" not in fields:
            continue
        entries.append(
            {
                "id": head_m.group("id"),
                "tanggal": fields.get("Tanggal", ""),
                "timestamp": fields.get("Timestamp", ""),
                "git_branch": fields.get("Git Branch", ""),
                "git_commit": fields.get("Git Commit", ""),
                "type": fields.get("Type", ""),
                "area": fields.get("Area", ""),
                "priority": fields.get("Priority", ""),
                "title": fields.get("Title", ""),
                "reason": fields.get("Reason", ""),
                "root_cause": fields.get("Root Cause", ""),
                "solution": fields.get("Solution", ""),
                "files": fields.get("Changed Files", []) or [],
                "symbols": fields.get("Changed Symbols", []) or [],
                "tests": fields.get("Tests", ""),
                "breaking_change": fields.get("Breaking Change", ""),
                "regression_risk": fields.get("Regression Risk", ""),
                "related_patch": fields.get("Related Patch", ""),
                "status": fields.get("Status", ""),
                "notes": fields.get("Notes", ""),
            }
        )
    return entries


def verify(text: str) -> dict:
    """Bandingkan ID yang ADA di file vs ID yang berhasil di-parse penuh, dan
    cek setiap field enum (Type/Priority/Breaking Change/Regression
    Risk/Status) punya nilai yang sah.

    Sebelum PATCH-2026-07-17-074, entry yang gagal parsing (format tidak
    baku) hilang dari `parse_entries()` TANPA sinyal apapun -- konsumen
    seperti context_pack.py/find_owner.py diam-diam kehilangan riwayat
    entry itu. Dipakai automation/verify_docs.py untuk menangkap kasus ini
    sebagai FAIL, bukan cuma "ID unik & berurutan".
    """
    all_ids = ENTRY_HEADING_RE.findall(text)
    entries = parse_entries(text)
    parsed_ids = {e["id"] for e in entries}
    missing = [pid for pid in all_ids if pid not in parsed_ids]

    invalid_enum: list = []
    for chunk in _split_into_chunks(text):
        head_m = ENTRY_HEADING_RE.search(chunk)
        if not head_m:
            continue
        fields = parse_entry_fields(chunk)
        for field_name, allowed in ENUM_FIELDS.items():
            value = fields.get(field_name)
            if value and value not in allowed:
                invalid_enum.append(f"{head_m.group('id')}: {field_name}='{value}'")

    return {
        "total_ids_found": len(all_ids),
        "total_parsed": len(parsed_ids),
        "unparsed_ids": missing,
        "invalid_enum_values": invalid_enum,
        "ok": not missing and not invalid_enum,
    }


def _next_id() -> str:
    # PATCH-2026-07-17-074: `len(entries) + 1` salah kalau parse_entries()
    # kehilangan entry (lihat bug di atas) -- menghasilkan ID yang sudah
    # dipakai (tabrakan). Pakai NNN tertinggi dari SEMUA ID heading yang ada
    # di file (bukan cuma yang ke-parse penuh) + 1, supaya tetap benar walau
    # ada entry lama berformat rusak.
    all_ids = ENTRY_HEADING_RE.findall(PATCHLOG.read_text(encoding="utf-8"))
    seqs = [int(pid.rsplit("-", 1)[1]) for pid in all_ids]
    next_seq = (max(seqs) + 1) if seqs else 1
    return f"PATCH-{date.today().isoformat()}-{next_seq:03d}"


def _git(args: list[str]) -> str:
    """Best-effort git metadata. Kalau bukan git repo atau gagal, kembalikan
    "-" -- BUKAN error fatal (spec §4.1: "best-effort")."""
    try:
        out = subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            value = out.stdout.strip()
            return value if value else "-"
    except Exception:
        pass
    return "-"


AREA_PREFIX_MAP = [
    ("web/static/js/", "Frontend"),
    ("web/static/css/", "Frontend"),
    ("web/static/", "Frontend"),
    ("server/", "Backend"),
    ("engine/", "Backend"),
    ("core/", "Backend"),
    ("adapters/", "Backend"),
    ("persistence/", "Backend"),
    ("services/", "Backend"),
    ("plugins/", "Backend"),
    ("bootstrap/", "Backend"),
    ("automation/", "Tooling"),
    ("docs/", "Docs"),
    ("tests/", "Test"),
    ("launcher/", "Packaging"),
]


def suggest_area(files: list[str]):
    """Usulan `Area` dari prefix path -- SARAN saja, tidak pernah dipaksa.
    CLI `add` tetap mewajibkan --area eksplisit; ini hanya dipakai untuk
    pesan bantuan saat --area tidak diisi."""
    votes: Counter[str] = Counter()
    for f in files:
        for prefix, area in AREA_PREFIX_MAP:
            if f.startswith(prefix):
                votes[area] += 1
                break
    if not votes:
        return None
    return votes.most_common(1)[0][0]


def _resolve_long_field(cli_value, file_value, field_label: str) -> str:
    """Field panjang (Root Cause/Solution/Notes) bisa diisi lewat flag
    string langsung, lewat file sementara (--xxx-file), atau (kalau tidak
    ada keduanya dan sesi interaktif) lewat $EDITOR -- pola commit message
    git, sesuai spec §4.1."""
    if cli_value is not None:
        return cli_value.strip()
    if file_value:
        return Path(file_value).read_text(encoding="utf-8").strip()
    if sys.stdin.isatty() and sys.stdout.isatty():
        editor = os.environ.get("EDITOR", "nano")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tf:
            tf.write(f"# Isi {field_label}. Baris berawalan # diabaikan.\n")
            tmp_path = tf.name
        try:
            subprocess.run([editor, tmp_path])
            content = Path(tmp_path).read_text(encoding="utf-8")
            lines = [ln for ln in content.splitlines() if not ln.strip().startswith("#")]
            return "\n".join(lines).strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    return "-"


def render_entry(pid: str, fields: dict) -> str:
    """Render satu entry sesuai FIELD_ORDER -- urutan field SELALU sama di
    semua entry (baru maupun hasil migrasi)."""
    lines = [f"## {pid}", ""]

    for key in HEADER_FIELDS:
        lines.append(f"**{key}:** {fields.get(key, '-') or '-'}")
    lines.append("")

    lines.append(f"**Reason:** {fields.get('Reason', '-') or '-'}")
    lines.append("")

    for key in ("Root Cause", "Solution"):
        value = fields.get(key, "-") or "-"
        lines.append(f"**{key}:**")
        lines.append(value)
        lines.append("")

    for key in LIST_FIELDS:
        items = fields.get(key) or []
        lines.append(f"**{key}:**")
        if items:
            for item in items:
                lines.append(f"- `{item}`")
        else:
            lines.append("- (tidak ada)")
        lines.append("")

    for key in ("Tests", "Breaking Change", "Regression Risk", "Related Patch", "Status"):
        lines.append(f"**{key}:** {fields.get(key, '-') or '-'}")
        lines.append("")

    lines.append("**Notes:**")
    lines.append(fields.get("Notes", "-") or "-")

    return "\n".join(lines) + "\n"


def add_entry(
    *,
    type_: str,
    area: str,
    title: str,
    reason: str,
    files: list,
    priority: str = "Medium",
    symbols=None,
    tests: str = "-",
    breaking: str = "Unclassified",
    risk: str = "Unclassified",
    status: str = "Draft",
    related: str = "-",
    root_cause: str = "-",
    solution: str = "-",
    notes: str = "-",
) -> str:
    text = PATCHLOG.read_text(encoding="utf-8")
    new_id = _next_id()
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M")

    fields = {
        "Tanggal": today,
        "Timestamp": now,
        "Git Branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "Git Commit": _git(["rev-parse", "--short", "HEAD"]),
        "Type": type_,
        "Area": area,
        "Priority": priority or "Medium",
        "Title": title[:100],
        "Reason": reason,
        "Root Cause": root_cause,
        "Solution": solution,
        "Changed Files": files,
        "Changed Symbols": symbols or [],
        "Tests": tests,
        "Breaking Change": breaking,
        "Regression Risk": risk,
        "Related Patch": related,
        "Status": status,
        "Notes": notes,
    }

    block = render_entry(new_id, fields)

    marker = "---\n\n"  # tepat setelah blockquote format-notice
    # PENTING: file diawali frontmatter YAML yang juga dibuka/ditutup dengan "---".
    # text.index(marker) tanpa offset akan selalu cocok dengan "---\n\n" di baris
    # pertama (pembuka frontmatter), bukan garis horizontal setelah blockquote —
    # ini menyebabkan entry baru disisipkan DI DALAM frontmatter dan merusaknya.
    # Lewati dulu blok frontmatter (jika ada) sebelum mencari marker sungguhan.
    search_start = 0
    if text.startswith("---"):
        fm_close = text.find("\n---", 3)
        if fm_close != -1:
            search_start = fm_close + len("\n---")
    idx = text.index(marker, search_start) + len(marker)
    new_text = text[:idx] + block + "\n---\n\n" + text[idx:]

    total = len(ENTRY_HEADING_RE.findall(new_text))
    new_text = re.sub(r"latest_patch_id:.*", f"latest_patch_id: {new_id}", new_text, count=1)
    new_text = re.sub(r"total_entries:.*", f"total_entries: {total}", new_text, count=1)
    PATCHLOG.write_text(new_text, encoding="utf-8")
    return new_id


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Tambah entry baru (format v2)")
    p_add.add_argument(
        "--type", required=True, choices=sorted(ENUM_FIELDS["Type"] - {"Unclassified"})
    )
    p_add.add_argument("--area", required=True, help="Mis. Frontend/Backend/Tooling/Docs/Test")
    p_add.add_argument(
        "--priority", default="Medium", choices=sorted(ENUM_FIELDS["Priority"] - {"Unclassified"})
    )
    p_add.add_argument("--title", required=True, help="Satu kalimat, <=100 karakter")
    p_add.add_argument("--reason", required=True)
    p_add.add_argument("--files", required=True, help="Comma-separated")
    p_add.add_argument(
        "--symbols", default="", help="Comma-separated, mis. 'markPendingToggle(),X'"
    )
    p_add.add_argument("--tests", default="-")
    p_add.add_argument(
        "--breaking", default="Unclassified", choices=sorted(ENUM_FIELDS["Breaking Change"])
    )
    p_add.add_argument(
        "--risk", default="Unclassified", choices=sorted(ENUM_FIELDS["Regression Risk"])
    )
    p_add.add_argument("--status", default="Draft", choices=sorted(ENUM_FIELDS["Status"]))
    p_add.add_argument("--related", default="-")
    p_add.add_argument("--root-cause", dest="root_cause", default=None)
    p_add.add_argument("--root-cause-file", dest="root_cause_file", default=None)
    p_add.add_argument("--solution", default=None)
    p_add.add_argument("--solution-file", dest="solution_file", default=None)
    p_add.add_argument("--notes", default=None)
    p_add.add_argument("--notes-file", dest="notes_file", default=None)

    p_latest = sub.add_parser("latest")
    p_latest.add_argument("--n", type=int, default=5)
    p_latest.add_argument("--json", action="store_true", dest="json_output")

    p_hist = sub.add_parser("history")
    p_hist.add_argument("--file", required=True)
    p_hist.add_argument("--json", action="store_true", dest="json_output")

    p_symbol = sub.add_parser("symbol", help="Cari entry berdasarkan Changed Symbols")
    p_symbol.add_argument("name")
    p_symbol.add_argument("--json", action="store_true", dest="json_output")

    p_verify = sub.add_parser("verify", help="Cek entry yang gagal di-parse / enum tidak valid")
    p_verify.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args()

    if args.cmd == "add":
        files = [f.strip() for f in args.files.split(",") if f.strip()]
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        area = args.area
        if not area:
            suggestion = suggest_area(files)
            hint = f" (saran: {suggestion})" if suggestion else ""
            print(f"[ERROR] --area wajib diisi{hint}", file=sys.stderr)
            sys.exit(1)
        root_cause = _resolve_long_field(args.root_cause, args.root_cause_file, "Root Cause")
        solution = _resolve_long_field(args.solution, args.solution_file, "Solution")
        notes = _resolve_long_field(args.notes, args.notes_file, "Notes")
        new_id = add_entry(
            type_=args.type,
            area=area,
            priority=args.priority,
            title=args.title,
            reason=args.reason,
            files=files,
            symbols=symbols,
            tests=args.tests,
            breaking=args.breaking,
            risk=args.risk,
            status=args.status,
            related=args.related,
            root_cause=root_cause,
            solution=solution,
            notes=notes,
        )
        print(f"Ditambahkan: {new_id}")
        return

    text = PATCHLOG.read_text(encoding="utf-8")

    if args.cmd == "verify":
        report = verify(text)
        if args.json_output:
            print(json.dumps(report, indent=2))
        else:
            print(f"ID ditemukan   : {report['total_ids_found']}")
            print(f"Berhasil parse : {report['total_parsed']}")
            ok = True
            if report["unparsed_ids"]:
                ok = False
                print(f"[ERROR] Gagal parse ({len(report['unparsed_ids'])}):")
                for pid in report["unparsed_ids"]:
                    print(f"   - {pid}")
            if report["invalid_enum_values"]:
                ok = False
                print(f"[ERROR] Nilai enum tidak valid ({len(report['invalid_enum_values'])}):")
                for item in report["invalid_enum_values"]:
                    print(f"   - {item}")
            if ok:
                print("[OK] Semua entry berhasil di-parse & enum valid.")
            else:
                sys.exit(1)
        return

    entries = parse_entries(text)

    if args.cmd == "symbol":
        result = [e for e in entries if args.name in e["symbols"]]
        print(json.dumps(result, indent=2))
        return

    result = (
        entries[: args.n]
        if args.cmd == "latest"
        else [e for e in entries if args.file in e["files"]]
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
