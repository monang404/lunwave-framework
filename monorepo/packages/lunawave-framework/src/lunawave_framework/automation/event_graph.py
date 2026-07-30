#!/usr/bin/env python3
"""
Module: automation.event_graph

Purpose:
    Menganalisis dan memvalidasi event pub/sub. Memastikan tidak ada publisher
    tanpa subscriber (dead event) dan tidak ada subscriber tanpa publisher (ghost event).

Subscribes to:
    None

Publishes:
    None

CLI:
    python automation/event_graph.py [--json]
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

from .shared.check_result import CheckResult, _overall_status, _score
from .shared.repo_index import load_index


def build_event_map(files_index: dict) -> dict:
    events = {}  # type: ignore
    for rel, info in files_index.items():
        for ev in info.get("publishes", []):
            events.setdefault(ev, {"publishers": [], "subscribers": []})
            events[ev]["publishers"].append(rel)
        for ev in info.get("subscribes", []):
            events.setdefault(ev, {"publishers": [], "subscribers": []})
            events[ev]["subscribers"].append(rel)
    return events


def check_events(events: dict) -> CheckResult:
    issues = []
    for ev, data in events.items():
        pub = data["publishers"]
        sub = data["subscribers"]
        if not sub:
            issues.append(
                f"Dead event: '{ev}' diterbitkan oleh {pub} tapi tidak ada yang subscribe"
            )
        if not pub:
            issues.append(
                f"Ghost event: '{ev}' di-subscribe oleh {sub} tapi tidak ada yang menerbitkan"
            )

    status = "WARN" if issues else "PASS"
    msg = f"{len(issues)} issue(s)" if issues else "Semua event valid"
    return CheckResult("Event Pub/Sub", status, msg, issues)


def get_json_data(root: Path) -> dict:
    idx = load_index(root)
    events = build_event_map(idx["files"])
    check = check_events(events)

    score = _score([check], {"Event Pub/Sub": 100})
    status = _overall_status([check])

    import dataclasses

    return {
        "checker": "event_graph",
        "repository_status": status,
        "score": score,
        "pass": 1 if check.status == "PASS" else 0,
        "warn": 1 if check.status == "WARN" else 0,
        "fail": 1 if check.status == "FAIL" else 0,
        "checks": [dataclasses.asdict(check)],
        "events": events,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(get_json_data(PROJECT_ROOT), indent=2))
        return

    idx = load_index(PROJECT_ROOT)
    events = build_event_map(idx["files"])
    check = check_events(events)

    print(f"📊 Event Graph ({len(events)} events):")
    for ev, data in sorted(events.items()):
        pub = len(data["publishers"])
        sub = len(data["subscribers"])
        flag = " ⚠️" if pub == 0 or sub == 0 else ""
        print(f"  - {ev}: {pub} pub, {sub} sub{flag}")

    print("\n🔍 Event Health:")
    if check.status == "PASS":
        print("  ✅ Semua event punya minimal 1 publisher dan 1 subscriber.")
    else:
        print("  ⚠️ Ditemukan masalah pada pub/sub:")
        for item in check.items:
            print(f"     - {item}")

    if check.status == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
