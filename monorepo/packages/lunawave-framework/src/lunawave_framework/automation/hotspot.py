#!/usr/bin/env python3
"""
Module: automation.hotspot

Purpose:
    Ranking file paling berisiko: skor = churn (jumlah kemunculan di
    PATCHLOG.md) x sentralitas (reverse-dep 1-hop dari repo_index).

Subscribes to:
    None

Publishes:
    None

CLI:
    python automation/hotspot.py [--top N] [--json]
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .patchlog import PATCHLOG, parse_entries
from .shared.repo_index import load_index


def compute_hotspots(root: Path) -> list[dict]:
    index = load_index(root)["files"]
    entries = parse_entries(PATCHLOG.read_text(encoding="utf-8"))

    churn = Counter()  # type: ignore
    for e in entries:
        for f in e["files"]:
            churn[f] += 1

    hotspots = []
    for rel, info in index.items():
        c = churn.get(rel, 0)
        # Sentralitas = reverse deps 1-hop (ditambah 1 supaya perkalian tidak nol)
        s = len(info.get("reverse_deps", [])) + 1
        score = c * s
        if score > 0:
            hotspots.append({"file": rel, "churn": c, "centrality": s - 1, "score": score})

    return sorted(hotspots, key=lambda x: x["score"], reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    hotspots = compute_hotspots(PROJECT_ROOT)
    result = hotspots[: args.top]

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nTop {args.top} Hotspots (Score = Churn * (Centrality + 1)):")
        for i, h in enumerate(result, 1):
            print(
                f"{i:2d}. {h['file']} (Score: {h['score']}, Churn: {h['churn']}, Centrality: {h['centrality']})"
            )


if __name__ == "__main__":
    main()
