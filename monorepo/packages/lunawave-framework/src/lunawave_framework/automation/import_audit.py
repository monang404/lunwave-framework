import argparse
import ast
import json
from collections import defaultdict
from pathlib import Path

from ._env import resolve_project_root

INTERNAL_PREFIXES = (
    "server",
    "engine",
    "core",
    "persistence",
    "services",
    "bootstrap",
    "plugins",
    "adapters",
    "config",
    "main",
)


def is_internal(module_name):
    if not module_name:
        return False
    parts = module_name.split(".")
    return parts[0] in INTERNAL_PREFIXES


class ImportVisitor(ast.NodeVisitor):
    def __init__(self, file_path, module_name):
        self.file_path = file_path
        self.module_name = module_name
        self.deferred_imports = []
        self.top_level_imports = set()
        self.in_function = False
        self.in_type_checking = False

        with open(file_path, encoding="utf-8") as f:
            self.lines = f.readlines()

    def visit_FunctionDef(self, node):
        old_in_func = self.in_function
        self.in_function = True
        self.generic_visit(node)
        self.in_function = old_in_func

    def visit_AsyncFunctionDef(self, node):
        old_in_func = self.in_function
        self.in_function = True
        self.generic_visit(node)
        self.in_function = old_in_func

    def visit_If(self, node):
        # Check if this is `if TYPE_CHECKING:`
        is_type_checking = False
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            is_type_checking = True
        elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
            is_type_checking = True

        old_in_type = self.in_type_checking
        if is_type_checking:
            self.in_type_checking = True

        self.generic_visit(node)
        self.in_type_checking = old_in_type

    def _check_patchability(self, lineno):
        start = max(0, lineno - 3)
        end = min(len(self.lines), lineno + 2)
        for i in range(start, end):
            line = self.lines[i].lower()
            if "patch" in line or "mock" in line or "test" in line:
                return True
        return False

    def _add_import(self, target, lineno):
        if not is_internal(target):
            return

        if self.in_type_checking:
            return

        if self.in_function:
            patchability = self._check_patchability(lineno)
            self.deferred_imports.append(
                {"line": lineno, "target": target, "patchability": patchability}
            )
        else:
            self.top_level_imports.add(target)

    def visit_Import(self, node):
        for alias in node.names:
            self._add_import(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            # resolve relative imports roughly
            target = node.module
            if node.level > 0:
                parts = self.module_name.split(".")
                if node.level <= len(parts):
                    base = ".".join(parts[: -node.level])
                    if base:
                        target = f"{base}.{target}"
            self._add_import(target, node.lineno)
        self.generic_visit(node)


def path_to_module(path_obj, project_root):
    rel = path_obj.relative_to(project_root)
    if rel.name == "__init__.py":
        parts = rel.parent.parts
    elif rel.suffix == ".py":
        parts = rel.parent.parts + (rel.stem,)
    else:
        return None
    return ".".join(parts)


def scan_project(root_dir):
    root = Path(root_dir)
    top_level_graph = defaultdict(set)
    deferred_list = []

    for py_file in root.rglob("*.py"):
        if "tests" in py_file.parts or ".cache" in py_file.parts:
            continue

        mod_name = path_to_module(py_file, root)
        if not mod_name or not is_internal(mod_name):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                code = f.read()
            tree = ast.parse(code)
            visitor = ImportVisitor(py_file, mod_name)
            visitor.visit(tree)

            for t in visitor.top_level_imports:
                top_level_graph[mod_name].add(t)

            for d in visitor.deferred_imports:
                deferred_list.append(
                    {
                        "file": py_file,
                        "module": mod_name,
                        "target": d["target"],
                        "line": d["line"],
                        "patchability": d["patchability"],
                    }
                )
        except Exception:
            pass

    return top_level_graph, deferred_list


def is_circular(source_mod, target_mod, top_level_graph):
    visited = set()
    queue = [target_mod]

    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)

        # We need to check if 'curr' is EXACTLY source_mod or if it starts with source_mod + '.'
        # Wait, if curr is source_mod, it's circular.
        # Sometimes people import `server.handlers` and source_mod is `server.handlers.websocket`.
        # For simplicity, if source_mod starts with curr or curr starts with source_mod.
        if (
            curr == source_mod
            or source_mod.startswith(curr + ".")
            or curr.startswith(source_mod + ".")
        ):
            return True

        for next_mod in top_level_graph.get(curr, []):
            if next_mod not in visited:
                queue.append(next_mod)

    return False


def run_audit(root_dir):
    top_level_graph, deferred_list = scan_project(root_dir)
    results = []

    for d in deferred_list:
        labels = []
        if is_circular(d["module"], d["target"], top_level_graph):
            labels.append("CIRCULAR")
        else:
            labels.append("SAFE_TO_PROMOTE")

        if d["patchability"]:
            labels.append("PATCHABILITY")

        results.append(
            {
                "file": str(d["file"].relative_to(root_dir)),
                "line": d["line"],
                "target": d["target"],
                "labels": labels,
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args()

    root_dir = resolve_project_root(args.project_root)
    results = run_audit(root_dir)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"{'FILE':<40} {'LINE':<5} {'TARGET':<35} {'LABELS'}")
        print("-" * 100)
        for r in results:
            labels = ", ".join(r["labels"])
            print(f"{r['file']:<40} {r['line']:<5} {r['target']:<35} {labels}")


if __name__ == "__main__":
    main()
