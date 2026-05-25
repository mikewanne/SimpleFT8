"""P121 — IC7300Interface Stub-Klassen-Tests.

Stub muss instanziierbar sein OHNE Hardware-Anfassung (kein Serial-Open,
kein USB-Audio). Properties sind gesetzt damit UI-Layer ohne Connect
arbeiten kann. Hardware-Methoden raisen NotImplementedError mit
P121-Verweis.
"""
from __future__ import annotations

import pytest


def test_instantiation_no_hardware_access():
    """IC7300Interface() läuft ohne Exception, ohne Serial-/USB-Anfassung."""
    from radio.ic7300 import IC7300Interface
    radio = IC7300Interface()
    assert radio is not None
    # ip ist leerer String (für ip-presence-Checks im Code)
    assert radio.ip == ""


def test_radio_type():
    """radio_type == 'ic7300' für rf_preset_store-Key."""
    from radio.ic7300 import IC7300Interface
    assert IC7300Interface.radio_type == "ic7300"


def test_radio_name():
    """radio_name == 'IC-7300' für UI-Anzeige (Dialog, Statusbar)."""
    from radio.ic7300 import IC7300Interface
    radio = IC7300Interface()
    assert radio.radio_name == "IC-7300"


def test_supports_diversity_false():
    """IC-7300 hat 1 Antennenbuchse → niemals Diversity."""
    from radio.ic7300 import IC7300Interface
    radio = IC7300Interface()
    assert radio.supports_diversity is False


def test_antennas_single():
    """get_antennas() liefert genau ['ANT1']."""
    from radio.ic7300 import IC7300Interface
    radio = IC7300Interface()
    assert radio.get_antennas() == ["ANT1"]


def test_connect_raises_not_implemented():
    """connect() raised NotImplementedError mit P121-Verweis + Radio-Name."""
    from radio.ic7300 import IC7300Interface
    radio = IC7300Interface()
    with pytest.raises(NotImplementedError) as exc_info:
        radio.connect()
    msg = str(exc_info.value)
    assert "IC-7300" in msg
    assert "P121" in msg


def test_hardware_constants_set():
    """tx_buffer_s + tune_power_w sind als Schätzungen gesetzt."""
    from radio.ic7300 import IC7300Interface
    # Schätzungen — beim echten Fork validieren!
    assert IC7300Interface.tx_buffer_s == 0.5
    assert IC7300Interface.rx_hardware_offset_default_s == 0.10
    assert IC7300Interface.tune_power_w == 10
