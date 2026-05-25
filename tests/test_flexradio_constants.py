"""P121 — FlexRadio Hardware-Konstanten Regression-Anker.

Sichert die heutigen Werte 1.3/0.26/10 ab — wer sie ändert muss
HISTORY.md grep + Regression-Test einer FT8-QSO-Sequenz machen
(DT-Buffer-Drift, TX-Power-Konvergenz).
"""
from __future__ import annotations


def test_flexradio_tx_buffer_legacy_value():
    """FlexRadio.tx_buffer_s == 1.3 (VITA-49 Hardware-Latenz)."""
    from radio.flexradio import FlexRadio
    assert FlexRadio.tx_buffer_s == 1.3


def test_flexradio_rx_hardware_offset_legacy_value():
    """FlexRadio.rx_hardware_offset_default_s == 0.26 (empirisch 10.212 Messungen)."""
    from radio.flexradio import FlexRadio
    assert FlexRadio.rx_hardware_offset_default_s == 0.26


def test_flexradio_tune_power_legacy_value():
    """FlexRadio.tune_power_w == 10 (Hardware-sicher für ATU-Match)."""
    from radio.flexradio import FlexRadio
    assert FlexRadio.tune_power_w == 10


def test_flexradio_radio_type():
    """radio_type == 'flexradio' (Top-Level-Key in rf_presets.json)."""
    from radio.flexradio import FlexRadio
    assert FlexRadio.radio_type == "flexradio"
