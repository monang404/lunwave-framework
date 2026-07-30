#!/usr/bin/env python3
"""
Module: automation.impact

Purpose:
    Blast radius sebelum refactor/hapus: reverse-dep transitif (import graph)
    DIGABUNG reverse-dep via event bus (subscriber dari event yang dipublish
    file target) — sisi event wajib, bukan opsional (lihat rationale di atas).

Subscribes to:
    None

Publishes:
    None

CLI:
    python automation/impact.py <file_or_symbol> [--json]
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

from .event_graph import build_event_map
from .find_owner import collect_py_files, resolve_target
from .shared.repo_index import load_index
from .test_locator import find_test_for


def transitive_reverse_deps(index: dict, target: str) -> set[str]:
    seen, queue = set(), [target]
    while queue:
        current = queue.pop()
        for dep in index["files"].get(current, {}).get("reverse_deps", []):
            if dep not in seen:
                seen.add(dep)
                queue.append(dep)
    seen.discard(target)
    return seen


def event_impacted(index: dict, graph: dict, target: str) -> set[str]:
    published = index["files"].get(target, {}).get("publishes", [])
    impacted = set()
    for ev in published:
        impacted.update(graph.get(ev, {}).get("subscribers", []))
    impacted.discard(target)
    return impacted


def compute_impact(root: Path, query: str) -> dict:
    all_files = collect_py_files(root)
    resolved = resolve_target(query, all_files, root)
    if not resolved:
        return {"error": f"Target '{query}' tidak ditemukan."}

    target = str(resolved.relative_to(root)).replace("\\", "/")
    index = load_index(root)
    graph = build_event_map(index["files"])

    via_import = transitive_reverse_deps(index, target)
    via_event = event_impacted(index, graph, target)

    tests = set()
    for f in via_import | via_event | {target}:
        t = find_test_for(root, f)
        if t:
            tests.add(str(t.relative_to(root)).replace("\\", "/"))

    return {
        "target": target,
        "query": query,
        "impacted_via_import": sorted(via_import),
        "impacted_via_event": sorted(via_event),
        "related_tests": sorted(tests),
        "risk_score": len(via_import) + 2 * len(via_event),  # event dibobot 2x
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file_or_symbol")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    result = compute_impact(PROJECT_ROOT, args.file_or_symbol)
    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        if "error" in result:
            print(result["error"])
            sys.exit(1)
        print(f"\nImpact Analysis untuk: {result['target']} (query: {result['query']})")
        print(f"Risk Score: {result['risk_score']}")
        print(f"\nImpact via Import ({len(result['impacted_via_import'])} modul):")
        for m in result["impacted_via_import"]:
            print(f"  - {m}")
        print(f"\nImpact via Event ({len(result['impacted_via_event'])} modul):")
        for m in result["impacted_via_event"]:
            print(f"  - {m}")
        print(f"\nRelated Tests ({len(result['related_tests'])} test):")
        for t in result["related_tests"]:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
