"""
Module: lunawave_framework.core.storage.ports

Purpose:
    Declare the one storage Protocol that has no domain vocabulary in
    it at all: session-token CRUD. Moved here in Phase 4 alongside its
    implementation (session_repo.py), per ADR 0013 Decision 2's deferral
    and ADR 0014's resolution of it.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless (interface definition only).
"""

from typing import Protocol


class SessionRepositoryPort(Protocol):
    async def create_session(self, token: str, expires_at: int) -> None: ...
    async def extend_session(self, token: str, expires_at: int) -> None: ...
    async def verify_session(self, token: str) -> bool: ...
    async def delete_session(self, token: str) -> None: ...
    async def cleanup_sessions(self) -> None: ...
