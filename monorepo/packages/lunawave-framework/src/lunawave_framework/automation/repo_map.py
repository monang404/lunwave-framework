#!/usr/bin/env python3
"""
Module: automation.repo_map

Purpose:
    Hasilkan satu JSON besar berisi peta relasi SELURUH file Python di repo
    (layer, import edges, reverse deps, event pub/sub, ukuran) dalam satu
    generate — bukan on-demand per simbol seperti find_owner/context_pack.
    Ditulis ke docs/DEPENDENCY_GRAPH.json supaya AI agent cukup baca 1 file
    di awal sesi untuk paham peta relasi lengkap, tanpa panggil tool
    berkali-kali satu per satu.

Inputs:
    Index ter-cache dari shared.repo_index (cakupan ownership: termasuk
    automation/ dan tests/).

Outputs:
    docs/DEPENDENCY_GRAPH.json (atau stdout dengan --dry-run).

Side Effects:
    Menulis docs/DEPENDENCY_GRAPH.json.

CLI:
    python automation/repo_map.py [--dry-run] [--json]

Subscribes to:
    None

Publishes:
    None
"""

import argparse
import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

from ._env import resolve_project_root

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.repo_index import load_ownership_index

OUTPUT_PATH = PROJECT_ROOT / "docs" / "DEPENDENCY_GRAPH.json"


def _internal_edges(rel: str, entry: dict, files: dict) -> list[str]:
    """Import entry -> daftar rel path internal (bukan stdlib/3rd-party)
    yang benar-benar ada di repo. Sama seperti pola resolusi di
    find_owner.get_owner_info, dipakai lagi di sini supaya konsisten."""
    edges = []
    for imp in entry.get("imports", []):
        imp_path = imp.replace(".", "/")
        candidates = [imp_path + ".py", imp_path + "/__init__.py"]
        for c in candidates:
            if c in files:
                edges.append(c)
                break
    return edges


def build_graph(root: Path) -> dict:
    index = load_ownership_index(root)
    files = index["files"]

    nodes = {}
    edges = []
    layer_counts: Counter = Counter()

    for rel, entry in sorted(files.items()):
        layer = entry.get("layer", "root")
        layer_counts[layer] += 1
        deps = _internal_edges(rel, entry, files)
        nodes[rel] = {
            "layer": layer,
            "classes": entry.get("classes", []),
            "function_count": len(entry.get("functions", [])),
            "loc": entry.get("loc", 0),
            "deps": deps,
            "reverse_deps": entry.get("reverse_deps", []),
            "publishes": entry.get("publishes", []),
            "subscribes": entry.get("subscribes", []),
            "purpose": entry.get("docstring_purpose", ""),
        }
        for dep in deps:
            edges.append({"from": rel, "to": dep})

    events: dict = {}
    for rel, entry in files.items():
        for ev in entry.get("publishes", []):
            events.setdefault(ev, {"publishers": [], "subscribers": []})["publishers"].append(rel)
        for ev in entry.get("subscribes", []):
            events.setdefault(ev, {"publishers": [], "subscribers": []})["subscribers"].append(rel)

    orphans = sorted(
        rel
        for rel, n in nodes.items()
        if not n["reverse_deps"] and not rel.endswith("__init__.py") and not rel.startswith("tests/")
    )

    return {
        "_meta": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "note": (
                "Auto-generated oleh automation/repo_map.py — jangan edit manual. "
                "Refresh via `python automation/run_all.py` atau "
                "`python automation/repo_map.py`."
            ),
        },
        "summary": {
            "total_files": len(nodes),
            "total_edges": len(edges),
            "total_events": len(events),
            "files_per_layer": dict(sorted(layer_counts.items(), key=lambda kv: -kv[1])),
            "orphan_candidates": len(orphans),
        },
        "nodes": nodes,
        "edges": edges,
        "events": events,
        "orphan_candidates": orphans,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Cetak ke stdout, jangan tulis file"
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Alias --dry-run")
    args = parser.parse_args()

    graph = build_graph(PROJECT_ROOT)
    text = json.dumps(graph, indent=2, ensure_ascii=False)

    if args.dry_run or args.json_output:
        print(text)
        return

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(text + "\n", encoding="utf-8")
    print(
        f"✅ {OUTPUT_PATH.relative_to(PROJECT_ROOT)} diperbarui — "
        f"{graph['summary']['total_files']} file, {graph['summary']['total_edges']} edges, "
        f"{graph['summary']['total_events']} event."
    )


if __name__ == "__main__":
    main()
