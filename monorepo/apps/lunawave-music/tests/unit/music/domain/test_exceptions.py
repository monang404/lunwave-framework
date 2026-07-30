"""tests/unit/core/test_exceptions.py — mirrors core/exceptions.py
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import pytest

from music.domain.exceptions import (
    DownloadError,
    MpvConnectionError,
    TrackResolutionError,
    YtPlayerError,
)


def test_ytplayer_error_is_base_exception():
    assert issubclass(YtPlayerError, Exception)


@pytest.mark.parametrize("exc_cls", [MpvConnectionError, TrackResolutionError, DownloadError])
def test_all_custom_exceptions_inherit_from_ytplayer_error(exc_cls):
    assert issubclass(exc_cls, YtPlayerError)


def test_exceptions_can_be_raised_and_caught_by_base_class():
    with pytest.raises(YtPlayerError):
        raise MpvConnectionError("socket down")
    with pytest.raises(YtPlayerError):
        raise TrackResolutionError("cannot resolve")
    with pytest.raises(YtPlayerError):
        raise DownloadError("download failed")


def test_exceptions_are_independently_catchable():
    with pytest.raises(DownloadError):
        try:
            raise DownloadError("boom")
        except MpvConnectionError:
            pytest.fail("DownloadError should not be caught as MpvConnectionError")


def test_exception_message_is_preserved():
    err = TrackResolutionError("could not resolve video xyz")
    assert str(err) == "could not resolve video xyz"
