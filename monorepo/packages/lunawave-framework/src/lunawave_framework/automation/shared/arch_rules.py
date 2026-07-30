"""
Module: automation.shared.arch_rules

Purpose:
    Auto-generated module docstring.

Subscribes to:
    None

Publishes:
    None
"""

from dataclasses import dataclass

ALLOWED: dict[str, set[str] | None] = {
    "core": set(),
    "adapters": {"core"},
    "persistence": {"core"},
    "plugins": {"core"},
    "engine": {"core", "adapters", "persistence"},
    "services": {"core", "persistence"},
    "server": {"core", "engine", "services", "persistence"},
    "launcher": {"core", "server"},
    "data": None,
    "automation": None,
    "cache": {"core", "persistence"},
}

KNOWN_VIOLATIONS = {
    ("config.py", "core"),
    ("engine/playback/track_loader.py", "cache"),
    ("engine/playback/controller.py", "cache"),
    ("services/discover_service.py", "cache"),
}


@dataclass
class Violation:
    file: str
    line: int
    importer_layer: str
    imported_module: str
    imported_layer: str

    def __str__(self) -> str:
        return (
            f"  {self.file}:{self.line}\n"
            f"    ↳ `{self.importer_layer}/` tidak boleh import dari `{self.imported_layer}/`\n"
            f"      import: {self.imported_module}"
        )

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "importer_layer": self.importer_layer,
            "imported_module": self.imported_module,
            "imported_layer": self.imported_layer,
        }


def is_known(v: Violation) -> bool:
    return (v.file, v.imported_layer) in KNOWN_VIOLATIONS
