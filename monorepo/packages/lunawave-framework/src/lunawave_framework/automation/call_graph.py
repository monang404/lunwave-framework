#!/usr/bin/env python3
"""
Module: automation.call_graph

Purpose:
    Cari caller & callee dari 1 nama fungsi, scan AST on-demand (bukan
    disimpan di repo_index — call-graph lengkap semua-fungsi terlalu besar).

Subscribes to:
    None

Publishes:
    None

CLI:
    python automation/call_graph.py <function_name> [--json]
"""

import argparse
import ast
import json
import sys
from pathlib import Path

from ._env import resolve_project_root

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = resolve_project_root()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from .shared.skip_dirs import walk_py_files


def find_callers(root: Path, target: str) -> list[str]:
    callers = []
    for path in walk_py_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
            if name == target:
                callers.append(str(path.relative_to(root)).replace("\\", "/"))
                break
    return sorted(set(callers))


def find_callees(root: Path, target: str) -> list[str]:
    for path in walk_py_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
                callees = {
                    n.func.id
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                }
                return sorted(callees)
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("function_name")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    result = {
        "function": args.function_name,
        "callers": find_callers(PROJECT_ROOT, args.function_name),
        "callees": find_callees(PROJECT_ROOT, args.function_name),
    }
    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{result['function']}")
        print(f"  dipanggil oleh : {', '.join(result['callers']) or '(tidak ditemukan)'}")
        print(f"  memanggil      : {', '.join(result['callees']) or '(tidak ada)'}")


if __name__ == "__main__":
    main()
