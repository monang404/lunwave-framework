"""
Module: tests.integration

Purpose:
    Integration test package. Tests here use real components
    (real SQLite, real aiohttp server, real event bus) but mock
    external process dependencies (MPV, yt-dlp) so they run
    without hardware dependencies.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""
