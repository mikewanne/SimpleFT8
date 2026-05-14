"""P53 (14.05.2026, v0.97.28 → v0.97.29) — SWR-Live-Watchdog.

Mike-Field-Test 14.05.2026: nasse Antenne nach Regen → SWR > 30 bei
TX mit 70 W. swr_limit (3.0) aus Settings hat NICHT gegriffen weil:

  1. SWR-Check lief nur vor Gain-Messung (mw_radio.py:1336+1352),
     nicht im normalen TX-Pfad.
  2. swr_alarm-Signal feuert zwar aus VITA-Loop (flexradio.py:1388),
     aber Handler (mw_tx.py:99-105) zeigt nur Statusbar — stoppt nichts.
  3. Settings.swr_limit wurde nirgends an FlexRadio propagiert.

P53-Fix:
  - mw_tx._on_swr_alarm: Komplett-Rewrite mit Pre-Check, Spike-Counter
    (500 ms), Komplett-Stop, Modal, QSO-Panel-Eintrag.
  - flexradio.set_swr_limit(): Setter mit Clamp [1.5, 10.0].
  - mw_radio._start_radio: Propagiert Setting an Radio nach Connect.
  - settings_dialog._save_and_close: Propagiert bei Save wenn radio.ip.
  - main_window.__init__: Spike-State explizit initialisiert.

R1-V4-pro Findings angenommen: ABC-Stub (F1), Spike-State-Init (F2),
AC1-Widerspruch-Streichung (F3), AC10-Code-Anhang (F4). 0 Halluzinationen.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ─────────────────────────────────────────────────────────────────────
# Helper: _on_swr_alarm Handler-Mount + Mock-Setup
# ─────────────────────────────────────────────────────────────────────

def _make_mw_tx(*, is_transmitting: bool = True,
                cq_mode: bool = False,
                qso_state_name: str = "IDLE",
                omni_active: bool = False,
                hunt_active: bool = False,
                radio_ip: str = "192.168.1.68",
                swr_limit: float = 3.0,
                spike_count: int = 0,
                first_alarm_t: float = 0.0):
    """Test-Setup: minimaler Mock fuer TXMixin._on_swr_alarm."""
    from ui.mw_tx import TXMixin
    from core.qso_state import QSOState

    obj = MagicMock()
    obj._on_swr_alarm = TXMixin._on_swr_alarm.__get__(obj)

    # Spike-Counter-State (AC13 — würde sonst AttributeError werfen)
    obj._swr_spike_count = spike_count
    obj._swr_first_alarm_t = first_alarm_t

    obj.encoder = MagicMock()
    obj.encoder.is_transmitting = is_transmitting
    obj.encoder.abort = MagicMock()

    obj.radio = MagicMock()
    obj.radio.ip = radio_ip
    obj.radio.ptt_off = MagicMock()
    obj.radio.set_tx_antenna = MagicMock()

    obj.qso_sm = MagicMock()
    obj.qso_sm.cq_mode = cq_mode
    obj.qso_sm.state = getattr(QSOState, qso_state_name)
    obj.qso_sm.stop_cq = MagicMock()
    obj.qso_sm.cancel = MagicMock()

    obj.control_panel = MagicMock()
    obj.control_panel.set_cq_active = MagicMock()

    obj._omni_cq = MagicMock()
    obj._omni_cq.is_active = MagicMock(return_value=omni_active)
    obj._omni_cq.stop = MagicMock()

    obj._auto_hunt = MagicMock()
    obj._auto_hunt.active = hunt_active
    obj._auto_hunt.stop_auto_hunt = MagicMock()

    obj.qso_panel = MagicMock()
    obj.qso_panel.add_info = MagicMock()

    obj.settings = MagicMock()
    obj.settings.get = MagicMock(return_value=swr_limit)

    return obj


# ─────────────────────────────────────────────────────────────────────
# T1: AC1+AC4 — 2 Alarms in Folge triggern Stop-Block
# ─────────────────────────────────────────────────────────────────────

def test_t1_alarm_2_in_a_row_triggers_stop(app, monkeypatch):
    """2 Alarms innerhalb 500 ms + is_transmitting=True → kompletter Stop."""
    obj = _make_mw_tx(is_transmitting=True, cq_mode=True)

    # QMessageBox.warning monkey-patchen damit Test nicht blockiert
    warning_spy = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warning_spy)

    # time.monotonic stubben für deterministische Zeit
    times = iter([10.0, 10.05])  # 50 ms Abstand
    monkeypatch.setattr("time.monotonic", lambda: next(times))

    # Aufruf 1: 1. Alarm → spike_count=1, kein Stop
    obj._on_swr_alarm(5.5)
    assert obj._swr_spike_count == 1
    assert obj.encoder.abort.call_count == 0

    # Aufruf 2: 2. Alarm innerhalb 50 ms → Stop läuft
    obj._on_swr_alarm(5.5)
    assert obj.encoder.abort.called
    assert obj.radio.ptt_off.called
    assert obj.qso_sm.stop_cq.called
    assert obj.qso_sm.cancel.called
    assert obj.control_panel.set_cq_active.called
    assert obj.qso_panel.add_info.called
    assert warning_spy.called
    # AC4(1): Reset
    assert obj._swr_spike_count == 0


# ─────────────────────────────────────────────────────────────────────
# T2: AC2 — Isolierter Alarm (kein 2.) → kein Stop
# ─────────────────────────────────────────────────────────────────────

def test_t2_isolated_alarm_no_stop(app, monkeypatch):
    """1 Alarm ohne 2. innerhalb 500 ms → kein Stop."""
    obj = _make_mw_tx(is_transmitting=True)

    warning_spy = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warning_spy)

    # Erst 1 Alarm
    monkeypatch.setattr("time.monotonic", lambda: 10.0)
    obj._on_swr_alarm(5.5)
    assert obj._swr_spike_count == 1

    # 600 ms später kommt 2. Alarm — aber > 500 ms → wird als NEUER 1. Alarm gewertet
    monkeypatch.setattr("time.monotonic", lambda: 10.6)
    obj._on_swr_alarm(5.5)
    assert obj._swr_spike_count == 1  # immer noch 1, nicht 2!
    assert obj.encoder.abort.call_count == 0
    assert warning_spy.call_count == 0


# ─────────────────────────────────────────────────────────────────────
# T3: AC3 — Alarm bei is_transmitting=False (ptt_on-Pre-Check) → kein Stop
# ─────────────────────────────────────────────────────────────────────

def test_t3_alarm_when_not_transmitting_returns(app, monkeypatch):
    """Pre-TX-Alarm aus ptt_on() → kein Stop, spike_count zurück auf 0."""
    obj = _make_mw_tx(is_transmitting=False, spike_count=1)

    warning_spy = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warning_spy)

    obj._on_swr_alarm(5.5)
    obj._on_swr_alarm(5.5)

    assert obj.encoder.abort.call_count == 0
    assert obj.radio.ptt_off.call_count == 0
    assert obj.qso_sm.stop_cq.call_count == 0
    assert warning_spy.call_count == 0
    assert obj._swr_spike_count == 0  # nach jedem Pre-TX-Alarm reset


# ─────────────────────────────────────────────────────────────────────
# T4: AC4 — Stop-Block-Reihenfolge: abort vor ptt_off vor stop_cq vor add_info vor modal
# ─────────────────────────────────────────────────────────────────────

def test_t4_stop_block_order(app, monkeypatch):
    """Stop-Block ruft Calls in exakter Reihenfolge."""
    obj = _make_mw_tx(is_transmitting=True, cq_mode=True,
                      omni_active=True, hunt_active=True)

    # Ein gemeinsamer Recording-Mock für Order-Verify
    recorder = MagicMock()
    obj.encoder.abort = recorder.encoder_abort
    obj.radio.ptt_off = recorder.radio_ptt_off
    obj.qso_sm.stop_cq = recorder.qso_sm_stop_cq
    obj.qso_sm.cancel = recorder.qso_sm_cancel
    obj.control_panel.set_cq_active = recorder.cp_set_cq_active
    obj._omni_cq.stop = recorder.omni_stop
    obj._auto_hunt.stop_auto_hunt = recorder.hunt_stop
    obj.qso_panel.add_info = recorder.panel_add_info

    warning_spy = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warning_spy)

    monkeypatch.setattr("time.monotonic", lambda: 10.0)
    obj._on_swr_alarm(4.0)
    monkeypatch.setattr("time.monotonic", lambda: 10.05)
    obj._on_swr_alarm(4.0)

    # Reihenfolge prüfen (Methoden-Namen in recorder.mock_calls)
    call_names = [c[0] for c in recorder.mock_calls]
    # encoder.abort kommt VOR ptt_off
    assert call_names.index("encoder_abort") < call_names.index("radio_ptt_off")
    # ptt_off VOR qso_sm.stop_cq
    assert call_names.index("radio_ptt_off") < call_names.index("qso_sm_stop_cq")
    # qso_sm.cancel VOR cp.set_cq_active
    assert call_names.index("qso_sm_cancel") < call_names.index("cp_set_cq_active")
    # cp.set_cq_active VOR omni.stop (omni nach allen QSO-Stops)
    assert call_names.index("cp_set_cq_active") < call_names.index("omni_stop")
    # omni.stop VOR hunt.stop
    assert call_names.index("omni_stop") < call_names.index("hunt_stop")
    # hunt.stop VOR panel.add_info
    assert call_names.index("hunt_stop") < call_names.index("panel_add_info")
    # add_info VOR Modal (Modal blockiert Event-Loop)
    assert warning_spy.called


# ─────────────────────────────────────────────────────────────────────
# T5: AC5 — set_tx_antenna NIE im Stop-Pfad (ANT1 bleibt ANT1)
# ─────────────────────────────────────────────────────────────────────

def test_t5_no_set_tx_antenna_in_stop(app, monkeypatch):
    """Hardware-Pflicht: Stop-Block fasst Antennen-Wahl NIE an."""
    obj = _make_mw_tx(is_transmitting=True)

    monkeypatch.setattr(QMessageBox, "warning", MagicMock())
    monkeypatch.setattr("time.monotonic", lambda: 10.0)
    obj._on_swr_alarm(4.0)
    monkeypatch.setattr("time.monotonic", lambda: 10.05)
    obj._on_swr_alarm(4.0)

    assert obj.radio.set_tx_antenna.call_count == 0


# ─────────────────────────────────────────────────────────────────────
# T6: AC6 — Modal Text & Title prüfen
# ─────────────────────────────────────────────────────────────────────

def test_t6_modal_dialog_text(app, monkeypatch):
    """Modal-Titel 'SWR-Schutz ausgelöst' + Text enthält SWR + Limit."""
    obj = _make_mw_tx(is_transmitting=True, swr_limit=2.5)

    warning_spy = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warning_spy)

    monkeypatch.setattr("time.monotonic", lambda: 10.0)
    obj._on_swr_alarm(4.5)
    monkeypatch.setattr("time.monotonic", lambda: 10.05)
    obj._on_swr_alarm(4.5)

    assert warning_spy.called
    args = warning_spy.call_args[0]
    # args: (parent, title, text)
    assert args[1] == "SWR-Schutz ausgelöst"
    assert "4.5" in args[2]  # SWR
    assert "2.5" in args[2]  # Limit
    assert "Antenne" in args[2] or "Einstellungen" in args[2]


# ─────────────────────────────────────────────────────────────────────
# T7: AC7 — qso_panel.add_info VOR Modal aufgerufen
# ─────────────────────────────────────────────────────────────────────

def test_t7_panel_info_before_modal(app, monkeypatch):
    """add_info läuft VOR Modal (synchroner Panel-Update, dann Modal blockt)."""
    recorder = MagicMock()
    obj = _make_mw_tx(is_transmitting=True)
    obj.qso_panel.add_info = recorder.panel_add_info

    def fake_warning(*args, **kwargs):
        recorder.modal_warning(*args, **kwargs)
    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    monkeypatch.setattr("time.monotonic", lambda: 10.0)
    obj._on_swr_alarm(4.0)
    monkeypatch.setattr("time.monotonic", lambda: 10.05)
    obj._on_swr_alarm(4.0)

    names = [c[0] for c in recorder.mock_calls]
    assert names.index("panel_add_info") < names.index("modal_warning")
    # Text-Prüfung
    info_text = recorder.panel_add_info.call_args[0][0]
    assert "TX abgebrochen" in info_text
    assert "4.0" in info_text


# ─────────────────────────────────────────────────────────────────────
# T8: AC8 — Kein Auto-Resume nach Stop
# ─────────────────────────────────────────────────────────────────────

def test_t8_no_auto_resume_after_stop(app, monkeypatch):
    """Nach Stop: spike_count=0, kein hidden Auto-Resume-State."""
    obj = _make_mw_tx(is_transmitting=True, cq_mode=True)

    monkeypatch.setattr(QMessageBox, "warning", MagicMock())
    monkeypatch.setattr("time.monotonic", lambda: 10.0)
    obj._on_swr_alarm(4.0)
    monkeypatch.setattr("time.monotonic", lambda: 10.05)
    obj._on_swr_alarm(4.0)

    # Nach Stop: spike-state zurückgesetzt
    assert obj._swr_spike_count == 0
    # cq_mode bleibt im Mock auf True (qso_sm.stop_cq ist Spy, ändert nichts) —
    # aber stop_cq wurde aufgerufen, das ist die echte Aktion
    assert obj.qso_sm.stop_cq.called


# ─────────────────────────────────────────────────────────────────────
# T9: AC9 — Settings.swr_limit nach Radio-Connect propagiert
# ─────────────────────────────────────────────────────────────────────

def test_t9_swr_limit_set_at_connect(app):
    """mw_radio._start_radio ruft radio.set_swr_limit() mit Settings-Wert.

    Lese Source-Code damit das Pattern als invariant getestet ist
    (Architektur-Test analog P47-Source-Level-Schutz).
    """
    src = Path(__file__).resolve().parent.parent / "ui" / "mw_radio.py"
    text = src.read_text()
    # Muss in _start_radio / Connect-Pfad sein, in Nähe von swr_alarm.connect
    assert "self.radio.set_swr_limit" in text, \
        "P53: set_swr_limit muss nach Radio-Connect aufgerufen werden"
    # Es muss aus Settings kommen, nicht hardcoded
    assert 'self.settings.get("swr_limit"' in text, \
        "P53: SWR-Limit muss aus settings.swr_limit geladen werden"


# ─────────────────────────────────────────────────────────────────────
# T10: AC10 — Settings-Dialog-Save propagiert SWR-Limit
# ─────────────────────────────────────────────────────────────────────

def test_t10_swr_limit_set_on_settings_save(app):
    """settings_dialog._save_and_close ruft parent.radio.set_swr_limit().

    Source-Level-Test damit P47-Pattern (tote Settings nicht zurück).
    """
    src = Path(__file__).resolve().parent.parent / "ui" / "settings_dialog.py"
    text = src.read_text()
    # In _save_and_close muss parent.radio.set_swr_limit gerufen werden
    assert "parent.radio.set_swr_limit" in text, \
        "P53: settings_dialog muss SWR-Limit an Radio propagieren"
    # Mit ip-Check (kein Crash bei disconnect)
    assert "parent.radio.ip" in text or 'getattr(parent.radio, "ip"' in text, \
        "P53: Save-Hook muss radio.ip prüfen"


# ─────────────────────────────────────────────────────────────────────
# T11: AC11 — set_swr_limit clampt auf [1.5, 10.0]
# ─────────────────────────────────────────────────────────────────────

def test_t11_set_swr_limit_clamps(app):
    """FlexRadio.set_swr_limit clampt extreme Werte gegen kaputte Settings."""
    from radio.flexradio import FlexRadio

    r = FlexRadio()

    r.set_swr_limit(0.5)
    assert r._swr_limit == 1.5  # untere Klemme

    r.set_swr_limit(99.0)
    assert r._swr_limit == 10.0  # obere Klemme

    r.set_swr_limit(2.5)
    assert r._swr_limit == 2.5  # normal


# ─────────────────────────────────────────────────────────────────────
# T12: AC12 — RadioInterface hat set_swr_limit als Default-Stub
# ─────────────────────────────────────────────────────────────────────

def test_t12_base_radio_has_set_swr_limit(app):
    """RadioInterface hat set_swr_limit (Default-Pass, IC-7300-Fork-fest).

    RadioInterface ist ABC mit teilweise konkreten Stub-Methoden (z.B.
    tx_audio_level.setter: pass) — wir prüfen Method-Existenz auf Klasse
    und dass der Code-Body 'pass' ist (Default-Stub-Pattern).
    """
    import inspect
    from radio.base_radio import RadioInterface

    assert hasattr(RadioInterface, "set_swr_limit")
    src = inspect.getsource(RadioInterface.set_swr_limit)
    # Default-Stub: enthält 'pass' und keine echte Logik
    assert "pass" in src


# ─────────────────────────────────────────────────────────────────────
# T13: AC13 — MainWindow initialisiert Spike-State explizit
# ─────────────────────────────────────────────────────────────────────

def test_t13_main_window_inits_spike_state(app):
    """MainWindow.__init__ muss _swr_spike_count + _swr_first_alarm_t setzen.

    Source-Level-Test gegen AttributeError beim 1. Alarm.
    """
    src = Path(__file__).resolve().parent.parent / "ui" / "main_window.py"
    text = src.read_text()
    assert "self._swr_spike_count = 0" in text, \
        "P53: MainWindow muss _swr_spike_count = 0 initialisieren"
    assert "self._swr_first_alarm_t = 0.0" in text, \
        "P53: MainWindow muss _swr_first_alarm_t = 0.0 initialisieren"
