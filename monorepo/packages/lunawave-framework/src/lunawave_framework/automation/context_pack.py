#!/usr/bin/env python3
"""
Module: automation.context_pack

Purpose:
    Satu panggilan yang menggabungkan semua tool automation/ jadi 1 JSON —
    endpoint utama untuk AI agent supaya tidak perlu 5 panggilan terpisah.

Subscribes to:
    None

Publishes:
    None

CLI:
    python automation/context_pack.py <file_or_feature> [--json]
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

from .find_owner import get_owner_info, resolve_target_rel
from .patchlog import parse_entries
from .shared.repo_index import load_ownership_index
from .test_locator import find_test_for


def _status_lines_for(root: Path, target: str) -> list[str]:
    status = (root / "docs" / "STATUS.md").read_text(encoding="utf-8", errors="replace")
    return [line.strip() for line in status.splitlines() if target in line]


def build_context_pack(root: Path, target: str) -> dict:
    # Satu index ownership dipakai dua kali (resolve + deps lookup) supaya
    # tetap 1 load ter-cache, bukan 2 rescan terpisah.
    index = load_ownership_index(root)

    # PATCH-2026-07-17-075: sebelumnya `index["files"].get(target, {})`
    # hanya cocok kalau `target` persis rel path file. Kalau AI agent kasih
    # nama class/fungsi (mis. "DownloadManager"), deps/reverse_deps/
    # event_flow diam-diam jadi kosong tanpa error — AI bisa salah simpul
    # bahwa modul itu tidak punya dependency. Resolusi dulu ke rel path
    # lewat mekanisme yang sama dipakai find_owner.py (file/class/fungsi).
    resolved_rel = resolve_target_rel(target, index, root) or target
    entry = index["files"].get(resolved_rel, {})

    test = find_test_for(root, resolved_rel)
    # Baca PATCHLOG.md relatif ke `root` yang diterima fungsi ini, BUKAN
    # dari konstanta global patchlog.PATCHLOG (yang selalu menunjuk ke
    # PROJECT_ROOT/docs/PATCHLOG.md milik proses ini). Sebelumnya
    # build_context_pack(root, target) terlihat root-parameterized tapi
    # diam-diam selalu membaca PATCHLOG.md yang sama terlepas dari `root`
    # yang diberikan -- baru ketahuan saat ditest dengan fake repo terpisah.
    patchlog_path = root / "docs" / "PATCHLOG.md"
    patchlog_text = patchlog_path.read_text(encoding="utf-8") if patchlog_path.exists() else ""
    history = [
        e
        for e in parse_entries(patchlog_text)
        if resolved_rel in e["files"] or target in e["files"]
    ]

    return {
        "target": target,
        "resolved_path": resolved_rel if resolved_rel != target else None,
        "ownership": get_owner_info(target, root),
        "deps": entry.get("imports", []),
        "reverse_deps": entry.get("reverse_deps", []),
        "event_flow": {
            "publishes": entry.get("publishes", []),
            "subscribes": entry.get("subscribes", []),
        },
        "related_test": str(test.relative_to(root)).replace("\\", "/") if test else None,
        "patchlog_history": history[:3],
        "status_notes": _status_lines_for(root, resolved_rel),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file_or_feature")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    result = build_context_pack(PROJECT_ROOT, args.file_or_feature)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
