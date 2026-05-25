"""P121 — radio_factory.create_radio Tests für alle drei Radio-Typen."""
from __future__ import annotations

import pytest


class _FakeSettings:
    """Minimaler Settings-Mock — Factory braucht nur .get()."""
    def __init__(self, data: dict):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


def test_create_flex_legacy_key():
    """radio_type='flex' → FlexRadio (alte Settings-Bezeichnung)."""
    from radio.radio_factory import create_radio
    from radio.flexradio import FlexRadio

    settings = _FakeSettings({"radio_type": "flex"})
    radio = create_radio(settings)
    assert isinstance(radio, FlexRadio)


def test_create_flex_explicit_key():
    """radio_type='flexradio' → FlexRadio (radio_type-Name == 'flexradio')."""
    from radio.radio_factory import create_radio
    from radio.flexradio import FlexRadio

    settings = _FakeSettings({"radio_type": "flexradio"})
    radio = create_radio(settings)
    assert isinstance(radio, FlexRadio)


def test_create_ic7300_returns_stub():
    """radio_type='ic7300' → IC7300Interface (kein NotImplementedError mehr)."""
    from radio.radio_factory import create_radio
    from radio.ic7300 import IC7300Interface

    settings = _FakeSettings({"radio_type": "ic7300"})
    radio = create_radio(settings)
    assert isinstance(radio, IC7300Interface)
    assert radio.radio_type == "ic7300"


def test_create_ic7100_returns_stub():
    """radio_type='ic7100' → IC7100Interface."""
    from radio.radio_factory import create_radio
    from radio.ic7100 import IC7100Interface

    settings = _FakeSettings({"radio_type": "ic7100"})
    radio = create_radio(settings)
    assert isinstance(radio, IC7100Interface)
    assert radio.radio_type == "ic7100"


def test_create_unknown_raises_value_error():
    """Unbekannter radio_type → ValueError mit Liste gültiger Typen."""
    from radio.radio_factory import create_radio

    settings = _FakeSettings({"radio_type": "kenwood-ts-2000"})
    with pytest.raises(ValueError) as exc_info:
        create_radio(settings)
    msg = str(exc_info.value)
    assert "kenwood-ts-2000" in msg
    assert "ic7300" in msg  # Hinweis auf gültige Typen
