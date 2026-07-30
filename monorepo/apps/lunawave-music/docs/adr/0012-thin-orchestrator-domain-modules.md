# ADR 0007: Thin Orchestrator and Domain Modules

## Status
Accepted

## Context
During the scaling of the frontend and backend codebase, certain files (e.g., `admin-logs.js` and `controller.py`) grew into "god files" or "god classes". These files handled everything from DOM manipulation and network requests to complex business logic, making them difficult to test, maintain, and understand. They also suffered from circular dependencies and high coupling.

## Decision
We adopt a pattern of "Thin Orchestrator + Domain Modules + Shared Transport" for complex subsystems:

1. **Thin Orchestrator:** The main entry point (e.g., `admin-logs.js` or `PlaybackController`) should act merely as an orchestrator. It is responsible for initializing domain modules, passing configurations, and wiring up global event listeners. It should contain minimal to no actual business logic.
2. **Domain Modules:** Logic is split into cohesive, single-responsibility modules (e.g., `dashboard-stats.js`, `log-tail.js` for frontend, or `play_ops.py`, `queue_ops.py` for backend). These modules should not directly import each other ("no cross-domain import") to prevent tight coupling and circular dependencies.
3. **Shared Transport / Event Bus:** Communication between domain modules, or between domain modules and the orchestrator, should happen via a shared transport layer (e.g., `admin-ws-transport.js`) or an Event Bus (`document.dispatchEvent`, `CommandBus`, etc.).

## Consequences
**Positive:**
- **Testability:** Domain modules can be unit tested in isolation without needing to mock the entire world.
- **Maintainability:** Clear boundaries make it easier to locate bugs and add features without unexpected regressions.
- **Dependency Management:** Eliminates circular dependencies by enforcing a unidirectional flow of control (Event -> Orchestrator -> Domain Module).

**Negative:**
- **Indirection:** Tracing the flow of execution can sometimes be slightly more complex due to the use of events instead of direct function calls.
- **Boilerplate:** Requires slightly more setup code for event emission and listening.
