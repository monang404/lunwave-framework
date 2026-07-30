# Contributing to LunaWave

Thank you for your interest in contributing to LunaWave!

## Monorepo Layout
We use a monorepo approach split into two core areas:
- `packages/lunawave-framework`: Generic primitives for web servers, plugins, and WebSockets. **Do not put any music-specific logic here.**
- `apps/lunawave-music`: The flagship music streaming application consuming the framework.

## Guidelines
- Follow the Hexagonal Architecture in `lunawave-music`. Domain code MUST NOT import web frameworks or database libraries.
- Run `pytest` before submitting a PR.
- Use the `lunawave` CLI to scaffold new modules.

## Setup
```bash
pip install -e monorepo/packages/lunawave-framework
pip install -r monorepo/apps/lunawave-music/requirements.txt
```
