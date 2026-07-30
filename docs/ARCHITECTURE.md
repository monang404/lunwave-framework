# LunaWave Architecture

## Two-Package Split
The LunaWave project is organized as a monorepo containing:
1. **`lunawave-framework`**: A domain-agnostic generic web and websocket application framework.
2. **`lunawave-music`**: The specific domain application that consumes the framework.

## Hexagonal Architecture (Ports and Adapters)
`lunawave-music` strictly adheres to a Hexagonal Architecture (also known as Ports and Adapters).
- **Core Domain (`domain/`)**: Pure Python objects without side effects. Contains entities, value objects, and business logic.
- **Ports (`ports.py`)**: Abstract Base Classes (ABCs) that define how the domain communicates with the outside world.
- **Adapters (`adapters/`, `persistence/`)**: Concrete implementations of ports (e.g. SQLite Repositories, API clients).
- **Services/Use Cases**: Orchestrate flow between the domain and the adapters.

## Frontend
The frontend follows a similar modular split.
- Core reactivity (`store.js`) and WebSocket transport (`transport.js`, `router.js`) are served directly by `lunawave-framework`.
- Domain-specific logic, UI components, and rendering logic live in `lunawave-music/web/static`.

## CLI Tooling
The `lunawave` CLI allows developers to scaffold new applications, plugins, and modules to rapidly build upon the generic kernel.
