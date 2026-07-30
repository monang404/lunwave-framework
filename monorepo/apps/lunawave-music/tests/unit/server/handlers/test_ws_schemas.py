import pytest

from server.handlers.ws_schemas import (
    LyricsOffsetPayload,
    SetSleepTimerPayload,
    SetSpeedPayload,
    VolumeSetPayload,
    WsValidationError,
)


class TestVolumeSetPayload:
    def test_valid(self):
        payload = VolumeSetPayload.parse({"volume": 50})
        assert payload.volume == 50

    def test_invalid_type(self):
        with pytest.raises(WsValidationError, match="Nilai volume harus berupa angka.") as exc:
            VolumeSetPayload.parse({"volume": "abc"})
        assert exc.value.__cause__ is None

    def test_out_of_range(self):
        with pytest.raises(WsValidationError, match="Volume harus berada di antara 0 dan 100."):
            VolumeSetPayload.parse({"volume": 105})

        with pytest.raises(WsValidationError, match="Volume harus berada di antara 0 dan 100."):
            VolumeSetPayload.parse({"volume": -5})

    def test_missing_key_uses_default(self):
        payload = VolumeSetPayload.parse({})
        assert payload.volume == 80


class TestSetSpeedPayload:
    def test_valid(self):
        payload = SetSpeedPayload.parse({"speed": 1.5})
        assert payload.speed == 1.5

    def test_invalid_type(self):
        with pytest.raises(WsValidationError, match="Nilai kecepatan harus berupa angka.") as exc:
            SetSpeedPayload.parse({"speed": "abc"})
        assert exc.value.__cause__ is None

    def test_out_of_range(self):
        with pytest.raises(WsValidationError, match="Kecepatan pemutaran tidak valid"):
            SetSpeedPayload.parse({"speed": 0.1})

        with pytest.raises(WsValidationError, match="Kecepatan pemutaran tidak valid"):
            SetSpeedPayload.parse({"speed": 4.0})

    def test_missing_key_uses_default(self):
        payload = SetSpeedPayload.parse({})
        assert payload.speed == 1.0


class TestLyricsOffsetPayload:
    def test_valid(self):
        payload = LyricsOffsetPayload.parse({"offset": -1.5})
        assert payload.offset == -1.5

    def test_invalid_type(self):
        with pytest.raises(WsValidationError, match="Nilai offset lirik harus berupa angka.") as exc:
            LyricsOffsetPayload.parse({"offset": "abc"})
        assert exc.value.__cause__ is None

    def test_missing_key_uses_default(self):
        payload = LyricsOffsetPayload.parse({})
        assert payload.offset == 0.0


class TestSetSleepTimerPayload:
    def test_valid(self):
        payload = SetSleepTimerPayload.parse({"minutes": 30})
        assert payload.minutes == 30

    def test_invalid_type(self):
        with pytest.raises(
            WsValidationError, match="Nilai waktu timer harus berupa angka bulat."
        ) as exc:
            SetSleepTimerPayload.parse({"minutes": "abc"})
        assert exc.value.__cause__ is None

    def test_out_of_range(self):
        with pytest.raises(WsValidationError, match="Waktu sleep timer tidak valid"):
            SetSleepTimerPayload.parse({"minutes": -5})

        with pytest.raises(WsValidationError, match="Waktu sleep timer tidak valid"):
            SetSleepTimerPayload.parse({"minutes": 1500})

    def test_missing_key_uses_default(self):
        payload = SetSleepTimerPayload.parse({})
        assert payload.minutes == 0
