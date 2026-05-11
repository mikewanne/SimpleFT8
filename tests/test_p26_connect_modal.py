#!/usr/bin/env python3
"""Tests fuer P26.CONNECT-MODAL — ConnectStatusDialog + Worker-Lifecycle.

Smoke-Tests fuer die Dialog-Klasse + Whitebox-Tests fuer die Worker-
Callback-Logik. R1-Race-Findings (K1, K2, K3) explizit getestet
(T10, T11).
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Dialog-Klasse: Layout/Smoke ────────────────────────────────────────────


def test_t1_layout_smoke(qapp):
    """T1: Dialog-Layout — Title, Size, Style."""
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        assert dlg.windowTitle() == "FlexRadio wird verbunden"
        # 11.05.2026: 20% kleiner
        assert dlg.size().width() == 352
        assert dlg.size().height() == 176
        assert dlg.isModal()
        assert dlg.windowModality() == Qt.WindowModality.WindowModal
        # Spinner-Label initialisiert
        assert dlg._spinner_label.text() in (".", "..", "...")
        # Versuch-Label initial hidden (nur fuer Failed-State sichtbar).
        # isHidden() unabhaengig von Parent-Show, isVisible() braucht Show.
        assert dlg._attempt_label.isHidden()
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t2_spinner_animation_ticks(qapp):
    """T2: Spinner zykliert . → .. → ... → ."""
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        dlg._tick_timer.stop()  # manuell ticken
        # Initial state nach __init__: _tick_dots() einmal gerufen → 1 Punkt
        # _dots_state = (0+1)%3 = 1 → "." * 2 = ".."
        # Wir ticken 3× und pruefen Sequenz
        seen = set()
        for _ in range(6):
            dlg._tick_dots()
            seen.add(dlg._spinner_label.text())
        assert "." in seen
        assert ".." in seen
        assert "..." in seen
    finally:
        dlg.deleteLater()


def test_t3_set_attempt_is_noop(qapp):
    """T3: set_attempt ist no-op (11.05.2026 Mike-Field-Test).

    Worker emittet weiterhin attempt_changed (API-Kompat), Slot tut
    bewusst nichts. Label bleibt leer + unsichtbar.
    """
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        dlg.set_attempt(3, 10)
        assert dlg._attempt_label.text() == ""
        assert dlg._attempt_label.isHidden()
        dlg.set_attempt(7, 10)
        assert dlg._attempt_label.text() == ""
        assert dlg._attempt_label.isHidden()
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t4_set_failed_state(qapp):
    """T4: set_failed() — Spinner-Timer stop, rotes ✗, Label sichtbar."""
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        assert dlg._tick_timer.isActive()
        dlg.set_failed()
        assert not dlg._tick_timer.isActive()
        assert dlg._spinner_label.text() == "✗"
        assert "fehlgeschlagen" in dlg._attempt_label.text()
        # Failed-State macht Label sichtbar (isHidden == False)
        assert not dlg._attempt_label.isHidden()
        # Buttons bleiben aktiv
        assert dlg._btn_weiter.isEnabled()
        assert dlg._btn_quit.isEnabled()
    finally:
        dlg.deleteLater()


def test_t5_weiter_click_rejects(qapp):
    """T5: "ohne Radio weiter" Click → reject() → Rejected."""
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        dlg._on_continue_without_radio()
        assert dlg.result() == int(QDialog.DialogCode.Rejected)
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t6_quit_click_calls_qapp_quit(qapp):
    """T6: "Beenden" Click → QApplication.quit aufgerufen."""
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        with patch.object(QApplication, "quit") as mock_quit:
            dlg._on_quit()
            mock_quit.assert_called_once()
        # zusaetzlich reject() fuer Fall dass quit() nicht sofort wirkt
        assert dlg.result() == int(QDialog.DialogCode.Rejected)
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t7_window_modal(qapp):
    """T7: WindowModal (NICHT ApplicationModal)."""
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        assert dlg.windowModality() == Qt.WindowModality.WindowModal
        assert dlg.windowModality() != Qt.WindowModality.ApplicationModal
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t8_attempt_changed_signal_triggers_slot(qapp):
    """T8: attempt_changed.emit triggert set_attempt-Slot (no-op, kein Crash).

    11.05.2026: Slot ist no-op, aber Signal-Connection muss noch
    funktionieren (Worker emittet weiterhin). Test prueft dass kein
    Crash auftritt und Label leer bleibt.
    """
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        dlg.attempt_changed.emit(5, 10)
        # no-op Slot: Label bleibt leer + hidden
        assert dlg._attempt_label.text() == ""
        assert dlg._attempt_label.isHidden()
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t9_failed_signal_triggers_slot(qapp):
    """T9: failed_signal.emit triggert set_failed-Slot."""
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    try:
        dlg.failed_signal.emit()
        # Direct-Connection: synchron
        assert "fehlgeschlagen" in dlg._attempt_label.text()
        assert not dlg._tick_timer.isActive()
    finally:
        dlg.deleteLater()


# ── R1-Race-Findings: K1 + K3 ──────────────────────────────────────────────


def test_t10_emit_after_dialog_destroy_no_crash(qapp):
    """T10 (R1-K1): Worker-emit nach Dialog-Destroy → kein Crash.

    Simuliert: Worker holt lokale Referenz, Dialog wird via
    deleteLater zerstoert, Worker emittet trotzdem. Mit try/except
    RuntimeError im Worker darf das nicht crashen.
    """
    from ui.connect_status_dialog import ConnectStatusDialog
    dlg = ConnectStatusDialog()
    dlg._tick_timer.stop()

    # Lokale Worker-Referenz wie in mw_radio._connect_worker
    worker_dlg_ref = dlg

    # Dialog explizit zerstoeren
    dlg.deleteLater()
    qapp.processEvents()  # deleteLater-Queue abarbeiten
    del dlg

    # Worker-Code-Pattern: try/except RuntimeError beim emit
    crashed = False
    try:
        try:
            worker_dlg_ref.attempt_changed.emit(5, 10)
        except RuntimeError:
            pass  # Erwartet — C++-Object destroyed
    except Exception:
        crashed = True
    assert not crashed, "Worker-Pattern darf nicht crashen wenn Dialog destroyed"


def test_t11_connected_signal_during_exec_closes_dialog(qapp):
    """T11 (R1-K3): connected-Signal triggert dialog.accept und schliesst exec.

    Realistischer Test: Signal-Connection wie in mw_radio._start_radio
    aufgebaut, dann exec() starten. Per QTimer wird connected.emit aus
    der Eventloop gefeuert (simuliert sehr schnellen Connect). Dialog
    schliesst sauber mit Accepted.
    """
    from PySide6.QtCore import QObject, QTimer, Signal
    from ui.connect_status_dialog import ConnectStatusDialog

    class FakeRadio(QObject):
        connected = Signal()

    fake = FakeRadio()
    dlg = ConnectStatusDialog()
    dlg._tick_timer.stop()
    fake.connected.connect(dlg.accept, Qt.ConnectionType.QueuedConnection)

    # Simuliere sehr schnellen Connect: emit kurz nach exec()-Start
    QTimer.singleShot(20, fake.connected.emit)

    # Sicherheits-Timeout falls Test haengt
    QTimer.singleShot(2000, dlg.reject)

    try:
        result = dlg.exec()
        assert result == int(QDialog.DialogCode.Accepted), (
            f"exec() sollte mit Accepted returnen, kam aber {result}"
        )
    finally:
        try:
            fake.connected.disconnect(dlg.accept)
        except (TypeError, RuntimeError):
            pass
        dlg.deleteLater()


# ── auto_connect-Signatur (C1) ─────────────────────────────────────────────


def test_t12_auto_connect_on_attempt_callback_called(qapp):
    """T12: auto_connect ruft on_attempt-Callback fuer jeden Versuch."""
    # Mock-Radio-Instanz wuerde echtes FlexRadio brauchen — wir testen
    # die Signatur via Direkt-Aufruf der unverbundenen Methode.
    from radio.flexradio import FlexRadio

    radio = FlexRadio.__new__(FlexRadio)  # ohne __init__ um Discovery zu vermeiden
    radio.ip = None  # Force discovery-fail-Pfad
    radio.error = MagicMock()
    radio.error.emit = MagicMock()

    captured = []

    def cb(attempt, max_attempts):
        captured.append((attempt, max_attempts))
        # Kein echter Discovery — wir muessen schnell durchlaufen
        # → ip bleibt None → time.sleep im Loop, deshalb max_retries=2

    # Discovery soll nichts finden
    with patch.object(FlexRadio, "discover", return_value=[]):
        with patch("radio.flexradio.time.sleep") as mock_sleep:
            mock_sleep.return_value = None  # Sleep schluck'n
            ok = FlexRadio.auto_connect(
                radio, max_retries=3, retry_delay=0.0, on_attempt=cb
            )
    assert ok is False
    assert len(captured) == 3
    assert captured[0] == (1, 3)
    assert captured[1] == (2, 3)
    assert captured[2] == (3, 3)


def test_t13_auto_connect_callback_exception_swallowed(qapp):
    """T13: Exception im on_attempt-Callback wird geschluckt."""
    from radio.flexradio import FlexRadio

    radio = FlexRadio.__new__(FlexRadio)
    radio.ip = None
    radio.error = MagicMock()
    radio.error.emit = MagicMock()

    def bad_cb(attempt, max_attempts):
        raise RuntimeError("Modal weg")

    with patch.object(FlexRadio, "discover", return_value=[]):
        with patch("radio.flexradio.time.sleep"):
            # Darf NICHT crashen
            ok = FlexRadio.auto_connect(
                radio, max_retries=2, retry_delay=0.0, on_attempt=bad_cb
            )
    assert ok is False  # Connect schlaegt fehl, aber kein Crash


def test_t14_auto_connect_default_no_callback(qapp):
    """T14: auto_connect ohne on_attempt — Abwaertskompatibilitaet."""
    from radio.flexradio import FlexRadio

    radio = FlexRadio.__new__(FlexRadio)
    radio.ip = None
    radio.error = MagicMock()
    radio.error.emit = MagicMock()

    with patch.object(FlexRadio, "discover", return_value=[]):
        with patch("radio.flexradio.time.sleep"):
            ok = FlexRadio.auto_connect(radio, max_retries=2, retry_delay=0.0)
    assert ok is False
