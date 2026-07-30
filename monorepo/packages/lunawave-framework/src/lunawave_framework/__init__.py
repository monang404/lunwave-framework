"""
lunawave_framework — reusable application-framework pieces extracted from
LunaWave Music.

Phase 1 of the extraction plan (see docs/extraction/) contains only the
`automation` subpackage: repo-analysis and health-check tooling that was
already import-isolated from the rest of the app (see `.importlinter`'s
`automation-is-isolated` contract in the source app).

Later phases will add `core`, `bootstrap`, `routing`, and `storage` — see
docs/extraction/01_ROADMAP.md for the full plan. Nothing else is extracted
yet; importing anything but `lunawave_framework.automation` from this
package is not supported at this stage.
"""

__version__ = "0.1.0"
