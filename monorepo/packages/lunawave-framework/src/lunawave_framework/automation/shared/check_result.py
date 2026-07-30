"""
Module: automation.shared.check_result

Purpose:
    Define the CheckResult dataclass and generic weighted-scoring helpers
    shared by all LunaWave health checker scripts.

Responsibilities:
    - Provide a typed result model with status, items, and coverage fields.
    - Compute a weighted score and aggregate overall status from a result list.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS" | "WARN" | "FAIL"
    message: str = ""  # satu baris keterangan
    items: list[str] = field(default_factory=list)
    current: int | None = None  # untuk cek bertipe "coverage": jumlah yang OK
    total: int | None = None  # untuk cek bertipe "coverage": jumlah total

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def percentage(self) -> int | None:
        if not self.total:
            return None
        return round(100 * (self.current or 0) / self.total)


def _score(results: list[CheckResult], check_weights: dict[str, int]) -> int:
    """Skor berbobot generik.

    Cek PASS mendapat penuh, FAIL mendapat 0, WARN mendapat kredit parsial:
    - Bila punya current/total → proporsional terhadap persentase yang OK.
    - Bila tidak punya → 50%.

    Args:
        results: daftar hasil cek.
        check_weights: dict nama_cek -> bobot (int).
    """
    total_weight = sum(check_weights.get(r.name, 0) for r in results) or 1
    earned = 0.0

    for r in results:
        weight = check_weights.get(r.name, 0)
        if r.status == "PASS":
            earned += weight
        elif r.status == "FAIL":
            earned += 0.0
        else:  # WARN
            if r.total:
                ratio = (r.current or 0) / r.total
            else:
                ratio = 0.5
            earned += weight * ratio

    return round(100 * earned / total_weight)


def _overall_status(results: list[CheckResult]) -> str:
    """Kembalikan status tertinggi (FAIL > WARN > PASS) dari list hasil cek."""
    if any(r.status == "FAIL" for r in results):
        return "FAIL"
    if any(r.status == "WARN" for r in results):
        return "WARN"
    return "PASS"
