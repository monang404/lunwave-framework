"""
Module: automation.shared.repo_index

Purpose:
    Index AST satu kali untuk seluruh repo (classes, functions, imports, layer,
    event publish/subscribe, reverse-deps), dengan cache ber-invalidasi mtime.

Depends on:
    - automation.shared.skip_dirs (walk_py_files)

Subscribes to:
    None

Publishes:
    None
"""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path

from .skip_dirs import SKIP_DIRS_FOR_OWNERSHIP, walk_py_files

CACHE_PATH = Path(".cache/repo_index.json")
_BUS_METHODS = {"publish", "subscribe"}

# Index "ownership" terpisah dari index utama di atas: index utama sengaja
# skip automation/ dan tests/ (dipakai call_graph/hotspot/architecture_lint
# yang fokus ke kode aplikasi). Tapi find_owner.py/context_pack.py perlu
# bisa melihat automation/ dan tests/ juga. Sebelum PATCH-2026-07-17-075,
# find_owner.py karena itu re-walk + re-parse AST SELURUH repo dari nol di
# SETIAP panggilan (termasuk saat context_pack.py sudah punya index utama
# ter-cache di panggilan yang sama) -- cache kedua ini menghilangkan
# duplikasi kerja itu tanpa mengubah cakupan index utama.
OWNERSHIP_CACHE_PATH = Path(".cache/repo_index_ownership.json")


def _walk_py_files_for_ownership(root: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS_FOR_OWNERSHIP]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def _event_name(node: ast.Call) -> str | None:
    """publish: bus.publish(DownloadCompleteEvent(...)) -> arg adalah Call.
    subscribe: bus.subscribe(DownloadCompleteEvent, handler) -> arg adalah Name."""
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Call) and isinstance(first.func, ast.Name):
        return first.func.id
    if isinstance(first, ast.Name):
        return first.id
    return None


def _parse_file(path: Path, root: Path) -> dict:
    rel = str(path.relative_to(root)).replace("\\", "/")
    source = path.read_text(encoding="utf-8", errors="replace")
    entry = {
        "layer": rel.split("/")[0] if "/" in rel else "root",
        "classes": [],
        "functions": [],
        "imports": [],
        "publishes": [],
        "subscribes": [],
        "loc": source.count("\n") + 1,
        "docstring_purpose": "",
    }
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return entry

    doc = ast.get_docstring(tree) or ""
    if "Purpose:" in doc:
        after = doc.split("Purpose:", 1)[1].lstrip("\n")
        entry["docstring_purpose"] = after.split("\n\n")[0].strip().replace("\n", " ")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            entry["classes"].append(node.name)  # type: ignore
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                entry["functions"].append(node.name)  # type: ignore
        elif isinstance(node, ast.Import):
            entry["imports"] += [a.name for a in node.names]  # type: ignore
        elif isinstance(node, ast.ImportFrom) and node.module:
            entry["imports"].append(node.module)  # type: ignore
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _BUS_METHODS:
                ev = _event_name(node)
                if ev:
                    key = "publishes" if node.func.attr == "publish" else "subscribes"
                    entry[key].append(ev)  # type: ignore
    return entry


def _rebuild_reverse_deps(files_index: dict) -> None:
    for entry in files_index.values():
        entry["reverse_deps"] = []
    for rel, entry in files_index.items():
        for imp in entry["imports"]:
            imp_path = imp.replace(".", "/") + ".py"
            if imp_path in files_index:
                files_index[imp_path]["reverse_deps"].append(rel)


def _load_or_build(root: Path, force: bool, cache_path: Path, walker) -> dict:
    current = {str(p.relative_to(root)).replace("\\", "/"): p.stat().st_mtime for p in walker(root)}

    if not force and cache_path.exists():
        cached = json.loads(cache_path.read_text())
        old = cached["_meta"]["source_mtimes"]
        changed = {f for f, m in current.items() if old.get(f) != m}
        deleted = set(old) - set(current)
        if not changed and not deleted:
            return cached  # tidak ada yang berubah — pakai cache apa adanya

        files_index = cached["files"]
        for f in deleted:
            files_index.pop(f, None)
        for f in changed:  # <- hanya file berubah di-reparse
            files_index[f] = _parse_file(root / f, root)
    else:
        files_index = {f: _parse_file(root / f, root) for f in current}

    _rebuild_reverse_deps(files_index)  # murah: invert dict, bukan AST
    data = {"_meta": {"generated_at": time.time(), "source_mtimes": current}, "files": files_index}
    cache_path.parent.mkdir(exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2))
    return data


def build_index(root: Path) -> dict:
    """Full rebuild — abaikan cache lama. Cakupan: kode aplikasi (skip
    automation/ dan tests/), dipakai call_graph/hotspot/architecture_lint."""
    return _load_or_build(root, force=True, cache_path=CACHE_PATH, walker=walk_py_files)


def load_index(root: Path) -> dict:
    """Load dari cache; reparse hanya file yang mtime-nya berubah."""
    return _load_or_build(root, force=False, cache_path=CACHE_PATH, walker=walk_py_files)


def build_ownership_index(root: Path) -> dict:
    """Full rebuild index cakupan "ownership" (termasuk automation/ dan
    tests/) — dipakai find_owner.py/context_pack.py."""
    return _load_or_build(
        root, force=True, cache_path=OWNERSHIP_CACHE_PATH, walker=_walk_py_files_for_ownership
    )


def load_ownership_index(root: Path) -> dict:
    """Load index ownership dari cache; reparse hanya file yang berubah."""
    return _load_or_build(
        root, force=False, cache_path=OWNERSHIP_CACHE_PATH, walker=_walk_py_files_for_ownership
    )
