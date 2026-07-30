#!/usr/bin/env python3
"""
Module: automation.find_owner

Purpose:
    Display ownership, dependencies, and impact radius of a given module,
    class, or function name.

Inputs:
    A file path, class name, or function name as a CLI argument.

Outputs:
    Console report with layer, callers, imports, size, and ADR hints or JSON with --json.

Side Effects:
    None (read-only static analysis).

CLI:
    python automation/find_owner.py <file|class|function> [--json]


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
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.constants import LARGE_FILE_THRESHOLD
from .shared.repo_index import load_ownership_index

LAYER_DESCRIPTIONS = {
    "core": "Foundation — shared primitives, tidak boleh import siapapun",
    "engine": "Domain Logic — audio playback, radio, queue, ytdlp",
    "cache": "Persistence (sementara) — SQLite layer, akan pindah ke persistence/",
    "server": "Web Layer — aiohttp handlers, WebSocket, HTTP REST",
    "services": "Application Services — discovery, query layer",
    "plugins": "Plugin System — lyrics, notifications, sponsorblock",
    "launcher": "Launcher — Tkinter GUI, process lifecycle",
    "adapters": "Adapters (target) — external adapter implementations",
    "persistence": "Persistence (target) — repository pattern",
    "data": "Data & Scripts — one-time migration, static data",
    "automation": "Developer Scripts — generators, linters, tools",
}

ADR_HINTS = {
    "mpv": "ADR-0001 (mpv-ipc-over-subprocess)",
    "MpvController": "ADR-0001 (mpv-ipc-over-subprocess)",
    "sqlite": "ADR-0002 (sqlite-over-json-cache)",
    "Database": "ADR-0002 (sqlite-over-json-cache)",
    "db": "ADR-0002 (sqlite-over-json-cache)",
    "ports": "ADR-0003 (hexagonal-ports-protocol)",
    "Port": "ADR-0003 (hexagonal-ports-protocol)",
    "CommandBus": "ADR-0004 (command-bus-single-writer)",
    "command_bus": "ADR-0004 (command-bus-single-writer)",
    "websocket": "ADR-0005 (websocket-single-channel)",
    "WebSocket": "ADR-0005 (websocket-single-channel)",
}


def find_all_classes_and_functions(index: dict) -> dict[str, str]:
    """Peta simbol (class/fungsi) -> rel path, dibangun dari index yang
    sudah di-cache (bukan AST rescan). PATCH-2026-07-17-075: sebelumnya
    fungsi ini (dan collect_py_files/extract_info/build_reverse_index di
    atasnya) me-re-walk + re-parse AST SELURUH repo dari nol di setiap
    panggilan find_owner.py — walau context_pack.py di baris lain pada
    panggilan yang sama sudah punya index ter-cache. Sekarang keduanya
    berbagi satu sumber (shared.repo_index.load_ownership_index)."""
    symbols: dict[str, str] = {}
    for rel, entry in index["files"].items():
        for cls in entry.get("classes", []):
            symbols[cls] = rel
        for fn in entry.get("functions", []):
            symbols.setdefault(fn, rel)
    return symbols


def read_status_for_file(rel_path: str, root: Path) -> str | None:
    status_file = root / "docs" / "STATUS.md"
    if not status_file.exists():
        return None
    content = status_file.read_text(encoding="utf-8", errors="replace")
    basename = Path(rel_path).name.replace(".py", "")
    for line in content.splitlines():
        if f"`{rel_path}`" in line or f"`{basename}`" in line:
            return line.strip()
    return None


def resolve_target(query: str, index: dict, root: Path) -> Path | None:
    """Resolusi query ke path file: coba sebagai path file dulu, lalu
    sebagai nama class/fungsi lewat index simbol ter-cache."""
    candidates = [
        root / query,
        root / (query + ".py"),
    ]
    for c in candidates:
        if c.exists():
            return c

    sym_index = find_all_classes_and_functions(index)
    if query in sym_index:
        return root / sym_index[query]

    return None


def resolve_target_rel(query: str, index: dict, root: Path) -> str | None:
    """Sama seperti resolve_target, tapi kembalikan rel path (str) yang
    langsung cocok dengan key di index["files"] — dipakai context_pack.py
    supaya deps/reverse_deps/event_flow tidak diam-diam kosong saat query
    berupa nama class/fungsi, bukan path file persis. Lihat
    PATCH-2026-07-17-075."""
    target = resolve_target(query, index, root)
    if target is None:
        return None
    return str(target.relative_to(root)).replace("\\", "/")


def get_adr_hints(rel_path: str, classes: list[str]) -> list[str]:
    hints = set()
    tokens = [rel_path] + classes
    for token in tokens:
        for keyword, adr in ADR_HINTS.items():
            if keyword.lower() in token.lower():
                hints.add(adr)
    return sorted(hints)


def get_owner_info(query: str, root: Path) -> dict | None:
    index = load_ownership_index(root)
    target = resolve_target(query, index, root)

    if target is None:
        return None

    rel = str(target.relative_to(root)).replace("\\", "/")
    entry = index["files"].get(rel)
    if entry is None:
        # File ada di disk tapi belum ter-index (kondisi balapan langka
        # antara mtime check dan disk) — fallback rebuild sekali.
        from shared.repo_index import build_ownership_index

        index = build_ownership_index(root)
        entry = index["files"].get(rel, {})

    top = rel.split("/")[0] if "/" in rel else "root"
    layer_desc = LAYER_DESCRIPTIONS.get(top, "—")

    classes = entry.get("classes", [])
    functions = entry.get("functions", [])
    callers = list(entry.get("reverse_deps", []))

    adrs = get_adr_hints(rel, classes)
    status_line = read_status_for_file(rel, root)

    internal_imports = []
    for imp in entry.get("imports", []):
        imp_path = imp.replace(".", "/")
        if any((root / (imp_path + ext)).exists() for ext in [".py", "/__init__.py"]):
            internal_imports.append(imp_path)

    lines = entry.get("loc", 0)
    size_kb = 0.0
    try:
        size_kb = target.stat().st_size / 1024
    except OSError:
        pass

    return {
        "target": query,
        "resolved_path": rel,
        "layer": top,
        "layer_description": layer_desc,
        "classes": classes,
        "functions": functions,
        "internal_imports": internal_imports,
        "callers": callers,
        "adr_hints": adrs,
        "status_line": status_line,
        "lines": lines,
        "size_kb": round(size_kb, 1),
    }


def show_owner(query: str, root: Path, json_output: bool) -> None:
    data = get_owner_info(query, root)
    if json_output:
        if data is None:
            print(json.dumps({"error": f"Tidak ditemukan: '{query}'"}, indent=2))
            sys.exit(1)
        print(json.dumps(data, indent=2))
        return

    if data is None:
        print(f"❌ Tidak ditemukan: '{query}'")
        print("   Coba: nama file (cache/db.py), nama class (Database), atau nama fungsi (publish)")
        sys.exit(1)

    rel = data["resolved_path"]
    top = data["layer"]
    layer_desc = data["layer_description"]

    print(f"\n{'━' * 60}")
    print(f"  📦  {rel}")
    print(f"{'━' * 60}")
    print(f"\n  Layer          : {top}/ — {layer_desc}")

    if data["classes"]:
        print(f"\n  Classes        : {', '.join(data['classes'])}")

    pub_fns = [f for f in data["functions"] if not f.startswith("_")]
    if pub_fns:
        shown = pub_fns[:8]
        suffix = f" (+{len(pub_fns) - 8} lainnya)" if len(pub_fns) > 8 else ""
        print(f"\n  Fungsi publik  : {', '.join(shown)}{suffix}")

    if data["internal_imports"]:
        print("\n  Menggunakan    :")
        for imp in data["internal_imports"][:8]:
            print(f"    → {imp}")
        if len(data["internal_imports"]) > 8:
            print(f"    … {len(data['internal_imports']) - 8} lainnya")

    if data["callers"]:
        print(f"\n  Digunakan oleh : ({len(data['callers'])} modul)")
        for c in sorted(data["callers"])[:8]:
            print(f"    ← {c}")
        if len(data["callers"]) > 8:
            print(f"    … {len(data['callers']) - 8} lainnya")
        print(
            f"\n  ⚡ Impact radius: mengubah modul ini berpotensi break {len(data['callers'])} modul di atas"
        )
    else:
        print("\n  Digunakan oleh : — (tidak ada modul yang mengimport ini secara statis)")

    if data["adr_hints"]:
        print(f"\n  ADR terkait    : {', '.join(data['adr_hints'])}")
        print("  (lihat docs/adr/)")

    if data["status_line"]:
        print("\n  STATUS.md      :")
        print(f"    {data['status_line']}")

    lines = data["lines"]
    size_kb = data["size_kb"]
    flag = (
        f" ⚠️ (>{LARGE_FILE_THRESHOLD} baris, pertimbangkan pecah)"
        if lines > LARGE_FILE_THRESHOLD
        else ""
    )
    print(f"\n  Ukuran file    : {lines} baris / {size_kb} KB{flag}")

    print(f"\n{'━' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Find owner of a file, class, or function.")
    parser.add_argument("query", help="File path, class name, or function name")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    args = parser.parse_args()

    show_owner(args.query, PROJECT_ROOT, args.json_output)


if __name__ == "__main__":
    main()
