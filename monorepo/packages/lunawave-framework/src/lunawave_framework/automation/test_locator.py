#!/usr/bin/env python3
"""
Module: automation.test_locator

Purpose:
    Petakan source <-> test dua arah via konvensi path-mirroring
    tests/unit/<subpath>/test_<nama>.py <-> <subpath>/<nama>.py.

Subscribes to:
    None

Publishes:
    None

CLI:
    python automation/test_locator.py --for <file>
    python automation/test_locator.py --orphan
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

from .shared.skip_dirs import walk_py_files

TEST_ROOT = Path("tests/unit")
SKIP_PREFIXES = ("tests/", "automation/", "scratch/", "data/")


def find_test_for(root: Path, rel_source: str) -> Path | None:
    parts = Path(rel_source).parts
    if not parts:
        return None
    candidate = root / TEST_ROOT.joinpath(*parts[:-1], f"test_{parts[-1]}")
    return candidate if candidate.exists() else None


def find_orphans(root: Path) -> list[str]:
    orphans = []
    for path in walk_py_files(root):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if rel.startswith(SKIP_PREFIXES) or "__init__" in rel:
            continue
        if find_test_for(root, rel) is None:
            orphans.append(rel)
    return sorted(orphans)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--for", dest="target")
    group.add_argument("--orphan", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    if args.orphan:
        result = find_orphans(PROJECT_ROOT)
    else:
        test = find_test_for(PROJECT_ROOT, args.target)
        result = {
            "source": args.target,
            "test": str(test.relative_to(PROJECT_ROOT)).replace("\\", "/") if test else None,
        }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        if isinstance(result, list):
            print(f"Orphan files ({len(result)}):")
            for f in result:
                print(f"  - {f}")
        else:
            print(f"Source: {result['source']}")
            print(f"Test  : {result['test'] or 'Tidak ditemukan'}")


if __name__ == "__main__":
    main()
