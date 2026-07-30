# lunawave_framework.core.logging -- structlog setup, log categories,
# correlation-id context helpers, and log tail/stats utilities. Moved
# verbatim from the app's core/ in Phase 2 (no music vocabulary found in
# Phase 0 audit), except for BASE_DIR-based path resolution which now goes
# through lunawave_framework.core._env instead of importing the app's
# top-level config module directly.
