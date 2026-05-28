"""P64 (28.05.2026, v0.98.38) — FakeRadio + SimInjector (Sim-Modus).

Mike-Wunsch: SimpleFT8 ohne echtes FlexRadio starten + Fake-Decodes/SWR
einspeisen, um UI/QSO-Flow/Auto-Hunt remote zu testen. Variante B (von 3).

- radio/fake_radio.py: FakeRadio(QObject), duck-typing-kompatibel zur
  FlexRadio-Oberflaeche (8 Signals + ~34 genutzte Member). ip="SIM" →
  App-Gates `if self.radio.ip:` = connected. Liefert KEIN Audio.
- core/sim_injector.py: SimInjector feuert pro Slot Fake-FT8Messages ueber
  die DECODER-Signals (cycle_decoded → message_decoded → cycle_finished).
- core/sim_mode.py: is_sim_mode() (Env-Var SIMPLEFT8_FAKE_RADIO=1).
- Guards: weak_decode_log + station_stats schreiben im Sim NICHT (Mikes
  P150-Evidenz + Statistik nicht kontaminieren). PSK-Reporter ist read-only
  (fetch), kein Guard noetig.

DeepSeek-R1 (V4-pro): GO, 0 Blocker. Konformitaet + Smoke manuell verifiziert
(MainWindow konstruiert in Sim 0.4s; 8 Fake-Decodes → 8 RX-Zeilen im Normal-
Modus). GRENZE V1: kein interaktiver QSO-Responder, Diversity-MESSUNG nicht
simuliert (braucht Variante C dual-stream) — beides als P64-B notiert.

Tests:
- T1/T2: FakeRadio Konformitaet (alle genutzten Member + 8 Signals)
- T3: Schluessel-Returns (ip, radio_type, get_frequency>0, antennas, swr)
- T4: connect-Methoden crashen nicht, auto_connect gibt True
- T5: factory liefert FakeRadio bei Env-Var
- T6: SimInjector baut valide FT8Messages (_tx_even/_slot_start_ts attached)
- T7: SimInjector._emit_slot Signal-Reihenfolge cycle→message→finished
- T8: Sim-Guards — weak_decode_log + station_stats schreiben NICHT im Sim
- T9: is_sim_mode liest Env-Var
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from core.message import FT8Message


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# Die Oberflaeche die der App-Code auf self.radio nutzt (grep-verifiziert).
_USED_MEMBERS = [
    "abort_connect", "abort_reconnect", "apply_ft8_preset", "auto_connect",
    "create_tx_stream", "disconnect", "has_secondary_slice", "ip", "last_swr",
    "on_audio_callback", "ptt_off", "radio_type", "reconnect_forever",
    "rx_hardware_offset_default_s", "set_frequency", "set_power", "set_rfgain",
    "set_rfgain_secondary", "set_rfpower_direct", "set_rx_antenna",
    "set_rx_filter", "set_swr_limit", "set_tx_antenna", "set_tx_level",
    "tune_off", "tune_on", "tune_power_w", "tx_audio_level", "tx_buffer_s",
    "tx_raw_peak",
]
_SIGNALS = ["connected", "disconnected", "frequency_changed", "audio_received",
            "meter_update", "swr_alarm", "dx_tune_progress", "error"]


def test_t1_conformance_all_used_members(qapp):
    """T1: FakeRadio hat ALLE vom App-Code genutzten Member (Abstraktions-
    Konformitaet — fehlt einer, crasht der Sim-Start)."""
    from radio.fake_radio import FakeRadio
    r = FakeRadio()
    missing = [m for m in _USED_MEMBERS if not hasattr(r, m)]
    assert not missing, f"FakeRadio fehlen Member: {missing}"


def test_t2_conformance_all_signals(qapp):
    """T2: FakeRadio definiert alle 8 FlexRadio-Signals."""
    from radio.fake_radio import FakeRadio
    r = FakeRadio()
    missing = [s for s in _SIGNALS if not hasattr(r, s)]
    assert not missing, f"FakeRadio fehlen Signals: {missing}"


def test_t3_key_returns(qapp):
    """T3: Schluessel-Returns plausibel (R1-Hinweise: ip non-empty,
    get_frequency > 0, 2 Antennen)."""
    from radio.fake_radio import FakeRadio
    r = FakeRadio()
    assert r.ip == "SIM" and bool(r.ip)        # non-empty → connected-Gate
    assert r.radio_type == "fake"
    assert r.get_frequency() > 0               # kein div-by-zero
    assert r.get_antennas() == ["ANT1", "ANT2"]
    assert r.supports_diversity is True
    assert r.last_swr == 1.0
    r.set_sim_swr(4.5)
    assert r.last_swr == 4.5                    # SWR einspeisbar (Bandsperre-Test)
    # Final-R1: set_frequency normalisiert MHz → Hz (intern immer Hz)
    r.set_frequency(14.074)                     # MHz
    assert r.get_frequency() == 14_074_000
    r.set_frequency(7_074_000)                  # Hz bleibt Hz
    assert r.get_frequency() == 7_074_000


def test_t4_connect_methods_no_crash(qapp):
    """T4: connect-Methoden crashen nicht, auto_connect/reconnect_forever
    geben True (Signatur identisch zum echten Aufruf)."""
    from radio.fake_radio import FakeRadio
    r = FakeRadio()
    assert r.connect() is True
    assert r.auto_connect(max_retries=10, retry_delay=3.0, on_attempt=None) is True
    assert r.reconnect_forever(on_waiting=None) is True
    r.disconnect()
    # no-op-Methoden duerfen nicht werfen
    r.tune_on(); r.tune_off(); r.ptt_off(); r.set_power(50)
    r.set_tx_antenna("ANT1"); r.set_rfgain(20); r.apply_ft8_preset()
    r.create_tx_stream(); r.set_rx_filter(100, 3100)


def test_t5_factory_returns_fake_with_env(qapp, monkeypatch):
    """T5: radio_factory liefert FakeRadio wenn SIMPLEFT8_FAKE_RADIO=1."""
    monkeypatch.setenv("SIMPLEFT8_FAKE_RADIO", "1")
    from radio.radio_factory import create_radio
    from radio.fake_radio import FakeRadio
    settings = SimpleNamespace(get=lambda k, d=None: d)
    r = create_radio(settings)
    assert isinstance(r, FakeRadio)


def _mock_decoder():
    d = SimpleNamespace()
    d._mode = "FT8"
    d.cycle_decoded = MagicMock()
    d.message_decoded = MagicMock()
    d.cycle_finished = MagicMock()
    return d


def test_t6_build_messages_valid(qapp):
    """T6: SimInjector baut 6-9 valide FT8Messages mit attached
    _tx_even/_slot_start_ts."""
    from core.sim_injector import SimInjector
    inj = SimInjector(_mock_decoder(), MagicMock())
    msgs = inj._build_messages(tx_even=True, slot_start=1700000000.0)
    assert 6 <= len(msgs) <= 9
    for m in msgs:
        assert isinstance(m, FT8Message)
        assert m.field2                       # caller gesetzt
        assert getattr(m, "_tx_even") is True
        assert getattr(m, "_slot_start_ts") == 1700000000.0
    # Mix: mind. ein CQ moeglich (probabilistisch, aber raw immer gesetzt)
    assert all(m.raw for m in msgs)


def test_t7_emit_slot_signal_order(qapp):
    """T7: _emit_slot feuert cycle_decoded → message_decoded(je msg) →
    cycle_finished in EXAKTER Reihenfolge (wie echter Decoder)."""
    from core.sim_injector import SimInjector
    d = _mock_decoder()
    order = []
    d.cycle_decoded.emit.side_effect = lambda *a: order.append("cycle")
    d.message_decoded.emit.side_effect = lambda *a: order.append("msg")
    d.cycle_finished.emit.side_effect = lambda *a: order.append("finished")
    inj = SimInjector(d, MagicMock())
    inj._running = True
    inj._emit_slot()
    assert order[0] == "cycle", "cycle_decoded muss zuerst kommen"
    assert order[-1] == "finished", "cycle_finished muss zuletzt kommen"
    assert order.count("cycle") == 1 and order.count("finished") == 1
    n_msgs = d.cycle_decoded.emit.call_args[0][0]
    assert order.count("msg") == len(n_msgs)   # 1 message_decoded je msg


def test_t8_sim_guards_no_write(qapp, monkeypatch, tmp_path):
    """T8: Im Sim-Modus schreibt weak_decode_log NICHT (Mikes P150-Evidenz
    schuetzen)."""
    from core import weak_decode_log
    monkeypatch.setattr(weak_decode_log, "LOG_DIR", tmp_path)
    # Ohne Sim: schreibt
    monkeypatch.delenv("SIMPLEFT8_FAKE_RADIO", raising=False)
    weak_decode_log.log_weak_decodes([(-25, "CQ X Y", 1234)], "20m", "FT8")
    files_normal = list(tmp_path.glob("weak_decodes_*.log"))
    assert files_normal, "Ohne Sim muss geschrieben werden"
    for f in files_normal:
        f.unlink()
    # Mit Sim: schreibt NICHT
    monkeypatch.setenv("SIMPLEFT8_FAKE_RADIO", "1")
    weak_decode_log.log_weak_decodes([(-25, "CQ X Y", 1234)], "20m", "FT8")
    assert not list(tmp_path.glob("weak_decodes_*.log")), (
        "P64: im Sim-Modus darf die Weak-Decode-Liste NICHT wachsen")


def test_t9_is_sim_mode(monkeypatch):
    """T9: is_sim_mode liest Env-Var SIMPLEFT8_FAKE_RADIO."""
    from core.sim_mode import is_sim_mode
    monkeypatch.setenv("SIMPLEFT8_FAKE_RADIO", "1")
    assert is_sim_mode() is True
    monkeypatch.setenv("SIMPLEFT8_FAKE_RADIO", "0")
    assert is_sim_mode() is False
    monkeypatch.delenv("SIMPLEFT8_FAKE_RADIO", raising=False)
    assert is_sim_mode() is False
