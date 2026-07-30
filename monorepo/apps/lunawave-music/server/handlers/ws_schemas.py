"""
Module: server.handlers.ws_schemas

Purpose:
    Provide strict validation and schema definitions for WebSocket command payloads.

Responsibilities:
    - Validate incoming JSON data for specific commands (e.g., volume, speed).
    - Raise WsValidationError with user-friendly Indonesian messages if validation fails.

Depends on:
    - None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Safe (stateless functions/dataclasses).
"""

from dataclasses import dataclass
from typing import Self


class WsValidationError(Exception):
    """Pesan siap-tampil untuk client, terpisah dari internal exception."""

    pass


@dataclass
class VolumeSetPayload:
    volume: int

    @classmethod
    def parse(cls, data: dict) -> Self:
        try:
            vol = int(data.get("volume", 80))
        except (TypeError, ValueError):
            raise WsValidationError("Nilai volume harus berupa angka.") from None

        if not (0 <= vol <= 100):
            raise WsValidationError("Volume harus berada di antara 0 dan 100.")

        return cls(volume=vol)


@dataclass
class SetSpeedPayload:
    speed: float

    @classmethod
    def parse(cls, data: dict) -> Self:
        try:
            spd = float(data.get("speed", 1.0))
        except (TypeError, ValueError):
            raise WsValidationError("Nilai kecepatan harus berupa angka.") from None

        if not (0.25 <= spd <= 3.0):
            raise WsValidationError("Kecepatan pemutaran tidak valid (batas: 0.25x - 3.0x).")

        return cls(speed=spd)


@dataclass
class LyricsOffsetPayload:
    offset: float

    @classmethod
    def parse(cls, data: dict) -> Self:
        try:
            off = float(data.get("offset", 0.0))
        except (TypeError, ValueError):
            raise WsValidationError("Nilai offset lirik harus berupa angka.") from None

        return cls(offset=off)


@dataclass
class SetSleepTimerPayload:
    minutes: int

    @classmethod
    def parse(cls, data: dict) -> Self:
        try:
            mins = int(data.get("minutes", 0))
        except (TypeError, ValueError):
            raise WsValidationError("Nilai waktu timer harus berupa angka bulat.") from None

        if not (0 <= mins <= 1440):
            raise WsValidationError("Waktu sleep timer tidak valid (maksimal 1440 menit).")

        return cls(minutes=mins)
