"""Diagnose-Logging für den ungeklärten Watt-/RF-Bug (v0.99.9, 05.06.2026).

Reine Diagnose (`debug_log("TXPWR", …)`) — verhaltensneutral. Diese Tests
sichern den von DeepSeek-R1 markierten NameError-Guard (`action`-Default greift,
wenn kein if/elif-Zweig `action` setzt) und dass der Marker-Umbau die Regelung
selbst NICHT verändert hat (rfpower-Hoch + Konvergenz-Speichern laufen weiter).
"""
from types import SimpleNamespace

from ui.mw_tx import TXMixin


class _FakeRadio:
    def __init__(self, audio=0.75, peak=0.85, swr=1.3):
        self.tx_audio_level = audio
        self.tx_raw_peak = peak
        self.last_swr = swr
        self.radio_type = "flexradio"
        self.ip = "1.2.3.4"
        self.set_power_calls = []

    def set_power(self, p):
        self.set_power_calls.append(p)

    def set_tx_level(self, v):
        pass


class _FakeControlPanel:
    def __init__(self):
        self.tx_level_bar = SimpleNamespace(setValue=lambda v: None)
        self.tx_level_label = SimpleNamespace(setText=lambda t: None)
        self.rfpower = None

    def update_tx_peak(self, v):
        pass

    def update_rfpower(self, v):
        self.rfpower = v


class _FakeSettings:
    def __init__(self):
        self.band = "20m"
        self.mode = "FT8"
        self._d = {}

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v

    def save_tx_power(self, band, val):
        pass


def _make_self(fwdpwr, target=70, rfpower=73, was_converged=True,
               audio=0.75, peak=0.85):
    radio = _FakeRadio(audio=audio, peak=peak)
    return SimpleNamespace(
        _fwdpwr_samples=[fwdpwr, fwdpwr, fwdpwr],
        _power_target=target,
        _rfpower_current=rfpower,
        _rfpower_converged=was_converged,
        _was_converged=was_converged,
        radio=radio,
        control_panel=_FakeControlPanel(),
        settings=_FakeSettings(),
        rf_preset_store=SimpleNamespace(save=lambda *a: None),
    )


def test_action_default_no_nameerror():
    """In-Band + bereits konvergiert: KEIN if/elif-Zweig setzt `action` →
    nur der Default 'hold' greift. Bricht der Default weg, wirft die
    TXPWR-Logzeile (f-String wird IMMER ausgewertet) NameError.
    Mutationsbeweis für den DeepSeek-R1-Catch."""
    me = _make_self(fwdpwr=70, target=70, was_converged=True)
    TXMixin._auto_adjust_tx_level(me)  # darf nicht werfen
    # In-Band → nichts zu regeln → kein set_power
    assert me.radio.set_power_calls == []


def test_below_target_at_clip_limit_raises_rfpower():
    """fwdpwr unter Ziel + Audio am Clip-Limit + rfpower < 100 → rfpower wird
    erhöht (set_power gesendet). Sichert, dass der Marker-Umbau die Regelung
    nicht verändert hat."""
    me = _make_self(fwdpwr=60, target=70, rfpower=73, audio=0.75, peak=0.85)
    TXMixin._auto_adjust_tx_level(me)
    assert me.radio.set_power_calls, "rfpower hätte erhöht werden müssen"
    assert me.radio.set_power_calls[-1] > 73


def test_converge_save_path_runs():
    """In-Band + noch nicht gespeichert → Konvergenz erkannt, Preset gespeichert,
    `action`=converge_save (kein NameError, save aufgerufen)."""
    saved = []
    me = _make_self(fwdpwr=70, target=70, was_converged=False)
    me.rf_preset_store = SimpleNamespace(save=lambda *a: saved.append(a))
    TXMixin._auto_adjust_tx_level(me)
    assert me._rfpower_converged is True
    assert me._was_converged is True
    assert saved, "Konvergenz hätte 1× gespeichert werden müssen"
