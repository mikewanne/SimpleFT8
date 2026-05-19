"""P82 — „ohne Radio weiter" muss Connect IMMER überspringen

Mike-Field-Test 19.05.2026 (120 km vom Radio, Radio AN): Klick auf
„ohne Radio weiter" während Connect-Worker lief → App startete
TROTZDEM mit Radio (Race-Condition zwischen User-Klick und
`radio.connected.emit()`).

Fix (v0.97.55):
- ConnectStatusDialog: `_user_cancelled`-Flag + `was_cancelled` Property,
  in `_on_continue_without_radio` gesetzt VOR `reject()`.
- mw_radio.py `_start_radio` nach exec(): wenn `was_cancelled` →
  `_demo_mode_forced=True` + `abort_reconnect` + ggf. `radio.disconnect`.
- mw_radio.py Slot-Guards in `_on_radio_connected` und
  `_on_radio_disconnected`: bei `_demo_mode_forced` sofort raus
  (kein Hardware-Call, kein Reconnect-Loop).

Tests T1-T7:
- T1: `_user_cancelled` initial False, `was_cancelled` Property liest korrekt.
- T2: `_on_continue_without_radio` setzt Flag VOR reject().
- T3: `_on_quit` lässt Flag False (Quit-Pfad eindeutig).
- T4: `was_cancelled` True nach Cancel (Race-Test mit verzögertem Connect).
- T5: `_demo_mode_forced=True` → `_on_radio_connected` ruft `radio.disconnect()`,
       KEIN `set_frequency`/`apply_ft8_preset`/`decoder.start`.
- T6: `_demo_mode_forced=True` → `_on_radio_disconnected` startet KEIN
       `_reconnect_worker`.
- T7: Backwards-Compat: `_demo_mode_forced=False` → Slot läuft Standard-Pfad.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── T1 — _user_cancelled initial False ────────────────────────────────


def test_t1_user_cancelled_initial_false(qapp):
    """Frischer Dialog: Flag False, was_cancelled Property False."""
    from ui.connect_status_dialog import ConnectStatusDialog

    dlg = ConnectStatusDialog(app_version="0.97.55")
    try:
        assert dlg._user_cancelled is False
        assert dlg.was_cancelled is False
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


# ── T2 — _on_continue_without_radio setzt Flag VOR reject() ───────────


def test_t2_continue_without_radio_setzt_flag(qapp):
    """Click-Pfad: Flag True nach Click, reject() lief."""
    from ui.connect_status_dialog import ConnectStatusDialog

    dlg = ConnectStatusDialog(app_version="0.97.55")
    try:
        assert dlg._user_cancelled is False

        dlg._on_continue_without_radio()

        assert dlg._user_cancelled is True
        assert dlg.was_cancelled is True
        assert dlg.result() == QDialog.DialogCode.Rejected
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


# ── T3 — _on_quit lässt Flag False (Quit-Pfad eindeutig) ──────────────


def test_t3_quit_laesst_flag_false(qapp):
    """„Beenden"-Pfad: Flag bleibt False (kein Demo-Cancel-Race).

    QApplication.quit() ist eindeutig → keine Demo-Modus-Race möglich.
    """
    from ui.connect_status_dialog import ConnectStatusDialog

    dlg = ConnectStatusDialog(app_version="0.97.55")
    try:
        # QApplication.quit() im _on_quit — patchen damit qapp nicht stirbt
        with patch("ui.connect_status_dialog.QApplication.quit"):
            dlg._on_quit()

        assert dlg._user_cancelled is False
        assert dlg.was_cancelled is False
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


# ── T4 — Race-Test: Cancel + Late-Accept → was_cancelled bleibt True ──


def test_t4_race_cancel_dann_late_accept_was_cancelled_bleibt_true(qapp):
    """User-Cancel-Flag ist stabil, auch wenn nach reject() ein
    Worker-getriggerter accept() noch via Queue ankommt.

    Realistisch: Mike klickt während Worker mitten in connect() ist.
    `reject()` läuft → was_cancelled=True. Worker fertig → accept()
    läuft als Queued-Event → setzt result auf Accepted, ABER Flag
    bleibt True (es ist ein User-Intent-Marker, kein result()-Spiegel).
    """
    from ui.connect_status_dialog import ConnectStatusDialog

    dlg = ConnectStatusDialog(app_version="0.97.55")
    try:
        dlg._on_continue_without_radio()
        assert dlg.was_cancelled is True

        # Simuliere späten accept-Call (z.B. von QueuedConnection)
        dlg.accept()
        # Flag bleibt — _start_radio liest es nach exec() und erkennt
        # User-Intent unabhängig von result().
        assert dlg.was_cancelled is True
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


# ── T5 — _on_radio_connected mit _demo_mode_forced=True → disconnect ──


def test_t5_demo_mode_forced_radio_connected_macht_disconnect():
    """User-Cancel-Override: `_on_radio_connected` ruft `radio.disconnect()`
    + return, KEINE Hardware-Setup-Calls (`set_frequency`,
    `apply_ft8_preset`, `decoder.start`, `create_tx_stream`).
    """
    from ui import mw_radio

    obj = MagicMock()
    obj._demo_mode_forced = True
    obj.radio = MagicMock()
    obj.control_panel = MagicMock()
    obj.settings = MagicMock()
    obj.decoder = MagicMock()
    obj.encoder = MagicMock()

    mw_radio.RadioMixin._on_radio_connected(obj)

    obj.radio.disconnect.assert_called_once()
    # Diese Hardware-Setup-Calls dürfen NIE laufen
    obj.radio.set_frequency.assert_not_called()
    obj.radio.apply_ft8_preset.assert_not_called()
    obj.decoder.start.assert_not_called()
    obj.radio.create_tx_stream.assert_not_called()
    obj.radio.set_rfgain.assert_not_called()
    obj.radio.set_power.assert_not_called()


# ── T6 — _on_radio_disconnected mit _demo_mode_forced=True → kein Reconnect


def test_t6_demo_mode_forced_radio_disconnected_kein_reconnect():
    """User-Cancel-Override: `_on_radio_disconnected` startet KEIN
    `_reconnect_worker`-Thread (Mike wollte Demo, kein Auto-Reconnect).
    """
    from ui import mw_radio

    obj = MagicMock()
    obj._demo_mode_forced = True
    obj.control_panel = MagicMock()
    obj.decoder = MagicMock()

    with patch.object(mw_radio.threading, "Thread") as thread_mock:
        mw_radio.RadioMixin._on_radio_disconnected(obj)

    obj.control_panel.set_connection_status.assert_called_with("disconnected")
    # Decoder.stop() darf NICHT laufen (Decoder war ja nie gestartet)
    obj.decoder.stop.assert_not_called()
    # _reconnect_worker-Thread darf NICHT starten
    thread_mock.assert_not_called()


# ── T7 — Backwards-Compat: _demo_mode_forced=False → Standard-Pfad ────


def test_t7_demo_mode_forced_false_disconnect_normal_path():
    """`_demo_mode_forced=False` → `_on_radio_disconnected` läuft
    Standard-Pfad (`decoder.stop` + `_reconnect_worker` Thread).

    Schützt vor versehentlichem Guard-Bug der ALLE Disconnects abfängt.
    """
    from ui import mw_radio

    obj = MagicMock()
    obj._demo_mode_forced = False
    obj._reconnect_attempts = 0
    obj._reconnect_countdown = 0
    obj.control_panel = MagicMock()
    obj.decoder = MagicMock()

    with patch.object(mw_radio.threading, "Thread") as thread_mock, \
         patch("PySide6.QtCore.QTimer"):
        mw_radio.RadioMixin._on_radio_disconnected(obj)

    # Standard-Pfad: decoder.stop MUSS laufen
    obj.decoder.stop.assert_called_once()
    # _reconnect_worker-Thread MUSS starten
    thread_mock.assert_called_once()
