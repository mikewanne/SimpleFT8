"""P121 — IC7100Interface Stub-Klassen-Tests (analog IC7300)."""
from __future__ import annotations

import pytest


def test_instantiation_no_hardware_access():
    from radio.ic7100 import IC7100Interface
    radio = IC7100Interface()
    assert radio is not None
    assert radio.ip == ""


def test_radio_type():
    from radio.ic7100 import IC7100Interface
    assert IC7100Interface.radio_type == "ic7100"


def test_radio_name():
    from radio.ic7100 import IC7100Interface
    radio = IC7100Interface()
    assert radio.radio_name == "IC-7100"


def test_supports_diversity_false():
    from radio.ic7100 import IC7100Interface
    radio = IC7100Interface()
    assert radio.supports_diversity is False


def test_antennas_single():
    from radio.ic7100 import IC7100Interface
    radio = IC7100Interface()
    assert radio.get_antennas() == ["ANT1"]


def test_connect_raises_not_implemented():
    from radio.ic7100 import IC7100Interface
    radio = IC7100Interface()
    with pytest.raises(NotImplementedError) as exc_info:
        radio.connect()
    msg = str(exc_info.value)
    assert "IC-7100" in msg
    assert "P121" in msg


def test_hardware_constants_set():
    from radio.ic7100 import IC7100Interface
    assert IC7100Interface.tx_buffer_s == 0.5
    assert IC7100Interface.rx_hardware_offset_default_s == 0.10
    assert IC7100Interface.tune_power_w == 10
