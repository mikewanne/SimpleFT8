"""P121 — RadioInterface ABC Defaults für Hardware-Konstanten.

ABC liefert Stub-Defaults damit eine konkrete Radio-Subclass auch ohne
explizite Class-Variables noch sinnvolle Werte hätte. Echtes Pattern
ist aber: jede konkrete Klasse setzt eigene Werte (FlexRadio, IC7300,
IC7100 — siehe test_flexradio_constants.py etc.).
"""
from __future__ import annotations


def test_abc_default_tx_buffer_s():
    """ABC liefert 1.3 als Notfall-Fallback (FlexRadio-historischer Default)."""
    from radio.base_radio import RadioInterface
    assert RadioInterface.tx_buffer_s == 1.3


def test_abc_default_rx_hardware_offset():
    """ABC liefert 0.26 als Notfall-Fallback."""
    from radio.base_radio import RadioInterface
    assert RadioInterface.rx_hardware_offset_default_s == 0.26


def test_abc_default_tune_power():
    """ABC liefert 10W als Notfall-Fallback."""
    from radio.base_radio import RadioInterface
    assert RadioInterface.tune_power_w == 10


def test_subclass_can_override_class_vars():
    """Dummy-Subclass kann eigene Werte setzen (Vererbung über ABC selbst)."""
    from radio.base_radio import RadioInterface

    class DummyRadio(RadioInterface):
        tx_buffer_s = 0.7
        rx_hardware_offset_default_s = 0.05
        tune_power_w = 5

        # ABC-Methoden minimal-stub damit Instanziation klappt (sind hier
        # nicht aufgerufen, nur abstrakte-Methoden-Pflicht erfüllen).
        def connect(self): return False
        def disconnect(self): pass
        @property
        def is_connected(self): return False
        def set_frequency(self, f): return False
        def get_frequency(self): return None
        def set_mode(self, m): return False
        def set_ptt(self, a): return False
        def set_tx_power(self, w): return False
        def get_antennas(self): return ["ANT1"]
        def set_antenna(self, a): return False
        def get_rx_audio_callback(self): return None
        def send_audio(self, p): return False
        def get_meter_data(self): return {}
        def set_rx_antenna(self, a): pass
        def set_tx_antenna(self, a): pass
        def set_rfgain(self, g): pass

    assert DummyRadio.tx_buffer_s == 0.7
    assert DummyRadio.rx_hardware_offset_default_s == 0.05
    assert DummyRadio.tune_power_w == 5
