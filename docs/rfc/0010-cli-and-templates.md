# RFC 0010: Framework Scaffolding (CLI & Templates)

## Context
With the successful extraction of `lunawave_framework` from `lunawave-music` (Phases 1-7), the framework is now an independent package providing generic primitives:
- Storage lifecycle and Admin Account Repository
- WebSocket message routing and broadcasting
- Plugin loading, events, and metrics
- Frontend reactive store and transport

To facilitate adoption by other projects (like the mock CRM or Inventory apps), we need an easy way to generate boilerplate code. 

## Proposal
Introduce a `lunawave` command-line tool installed automatically with the framework. The CLI will provide:
1. `lunawave new <project_name>`: Scaffolds a complete `aiohttp` backend wired with framework components.
2. `lunawave module:create <name>`, `plugin:create`, `adapter:create`: Scaffolds domain-specific components inside an existing project.

## Implementation Details
- Templates are stored in `lunawave_framework/templates/`.
- `argparse` is used to expose the commands.
- Python's `shutil` and simple string replacement (`{{PROJECT_NAME}}`) handle the scaffolding.

## Consequences
- **Positive:** Lowers the barrier to entry for creating new applications. Enforces Hexagonal Architecture structure implicitly.
- **Negative:** Framework maintainers now have to keep the templates up-to-date whenever internal API signatures change.
