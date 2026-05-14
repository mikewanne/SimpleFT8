"""Smoke-Tests fuer ui/mw_radio.RadioMixin._maybe_apply_bandpilot.

Direkter Test der Methode ueber unbound-method-Aufruf mit Mock-Object —
keine echte MainWindow-Instanziierung noetig (zu teuer fuer Smoke-Tests).
Plus Smoke-Tests fuer BandpilotAutoToast / BandpilotManualDialog.
"""

from unittest.mock import MagicMock

import pytest

from ui.mw_radio import RadioMixin


@pytest.fixture(scope="module")
def qapp():
    """Qt Application Instance — module-scoped (1× pro Test-Modul)."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _make_mock_self(*, mode: str, current: str | None, rec: dict | None,
                    is_transmitting: bool = False):
    """Mock-Objekt fuer self mit allen benoetigten Attributen + Methoden."""
    self_mock = MagicMock()
    # Settings.get('bandpilot_mode', ...) → mode
    self_mock.settings.get = MagicMock(side_effect=lambda key, default=None:
                                       {"bandpilot_mode": mode}.get(key, default))
    self_mock._bandpilot.recommend.return_value = rec
    self_mock._current_rx_mode_string.return_value = current
    self_mock.encoder.is_transmitting = is_transmitting
    self_mock._bandpilot_pending = None
    self_mock._bandpilot_tx_connected = False
    # Stub Methoden
    self_mock._show_bandpilot_insufficient_data = MagicMock()
    self_mock._show_bandpilot_auto_toast = MagicMock()
    self_mock._show_bandpilot_manual_dialog = MagicMock(
        return_value=rec["top1"] if rec else None)
    self_mock._set_rx_mode_direct = MagicMock()
    self_mock._apply_bandpilot_auto = lambda b, h, r: \
        RadioMixin._apply_bandpilot_auto(self_mock, b, h, r)
    self_mock._apply_bandpilot_manual = lambda b, h, r, c: \
        RadioMixin._apply_bandpilot_manual(self_mock, b, h, r, c)
    return self_mock


# ── Test 15: Auto + decision=switch ruft _set_rx_mode_direct ───────────────────

def test_maybe_apply_bandpilot_auto_calls_set_rx_mode_direct():
    """V3-AK 32 #15: Auto-Modus mit switch-Decision triggert Modus-Wechsel."""
    rec = {
        "top1": "diversity_dx",
        "top1_mean": 50.0,
        "ranking": [("diversity_dx", 50.0), ("diversity_normal", 30.0),
                    ("normal", 10.0)],
        "decision": "switch",
        "decision_mode": "diversity_dx",
    }
    s = _make_mock_self(mode="auto", current="diversity_normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is True
    s._set_rx_mode_direct.assert_called_once_with("diversity_dx")
    s._show_bandpilot_auto_toast.assert_called_once()


def test_maybe_apply_bandpilot_auto_no_change_does_nothing():
    """Auto-Modus mit no_change → kein Wechsel, kein Toast."""
    rec = {
        "top1": "normal",
        "top1_mean": 10.0,
        "ranking": [("normal", 10.0), ("diversity_dx", 9.5),
                    ("diversity_normal", 9.0)],
        "decision": "no_change",
        "decision_mode": "normal",
    }
    s = _make_mock_self(mode="auto", current="diversity_normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._set_rx_mode_direct.assert_not_called()
    s._show_bandpilot_auto_toast.assert_not_called()


# ── Test 16: Manuell Dialog NUR wenn Top-1 != current ─────────────────────────

def test_maybe_apply_bandpilot_manual_dialog_only_when_top1_diff():
    """V3-AK 32 #16: Manuell + Top-1 != aktuell → Dialog erscheint."""
    rec = {
        "top1": "diversity_dx",
        "top1_mean": 50.0,
        "ranking": [("diversity_dx", 50.0), ("diversity_normal", 30.0),
                    ("normal", 10.0)],
        "decision": "switch",
        "decision_mode": "diversity_dx",
    }
    s = _make_mock_self(mode="manual", current="diversity_normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    s._show_bandpilot_manual_dialog.assert_called_once()
    assert result is True
    s._set_rx_mode_direct.assert_called_once_with("diversity_dx")


def test_maybe_apply_bandpilot_manual_top1_equals_current_silent():
    """Manuell + Top-1 == aktuell → KEIN Dialog, stillschweigend bestaetigt."""
    rec = {
        "top1": "normal",
        "top1_mean": 50.0,
        "ranking": [("normal", 50.0), ("diversity_dx", 30.0),
                    ("diversity_normal", 10.0)],
        "decision": "no_change",
        "decision_mode": "normal",
    }
    s = _make_mock_self(mode="manual", current="normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._show_bandpilot_manual_dialog.assert_not_called()
    s._set_rx_mode_direct.assert_not_called()


# ── Test 17: Statusbar-Hinweis bei zu wenig Daten ─────────────────────────────

def test_maybe_apply_bandpilot_silent_when_insufficient_data():
    """V3-AK 32 #17: Bei rec=None → Statusbar-Hinweis, kein Wechsel."""
    s = _make_mock_self(mode="auto", current="diversity_normal", rec=None)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._show_bandpilot_insufficient_data.assert_called_once_with("40m", pytest.approx(s._show_bandpilot_insufficient_data.call_args[0][1]))
    s._set_rx_mode_direct.assert_not_called()


# ── Test 18: dx_tuning skippt Bandpilot ────────────────────────────────────────

def test_maybe_apply_bandpilot_skips_during_dx_tuning():
    """V3-AK 32 #18 / V3-AK 19: current_mode=None (dx_tuning) → Skip."""
    rec = {
        "top1": "diversity_dx",
        "top1_mean": 50.0,
        "ranking": [],
        "decision": "switch",
        "decision_mode": "diversity_dx",
    }
    s = _make_mock_self(mode="auto", current=None, rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._bandpilot.recommend.assert_not_called()
    s._set_rx_mode_direct.assert_not_called()


# ── Bandpilot-Mode 'off' ──────────────────────────────────────────────────────

def test_maybe_apply_bandpilot_off_does_nothing():
    """Mode='off' → recommend wird gar nicht aufgerufen, return False."""
    rec = {
        "top1": "diversity_dx",
        "top1_mean": 50.0,
        "ranking": [],
        "decision": "switch",
        "decision_mode": "diversity_dx",
    }
    s = _make_mock_self(mode="off", current="normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._bandpilot.recommend.assert_not_called()


# ── Bandpilot-Aggregations-Exception ──────────────────────────────────────────

def test_maybe_apply_bandpilot_handles_exception_gracefully():
    """Wenn _bandpilot.recommend raised → kein Crash, return False."""
    s = _make_mock_self(mode="auto", current="normal", rec=None)
    s._bandpilot.recommend.side_effect = OSError("disk read fail")
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._set_rx_mode_direct.assert_not_called()


# ── TX-Schutz (Phase 8 / V3-AK 7) ─────────────────────────────────────────────

def test_auto_tx_active_delays_set_rx_mode():
    """Bei is_transmitting=True wird Modus-Wechsel verzoegert."""
    rec = {
        "top1": "diversity_dx", "top1_mean": 50.0,
        "ranking": [("diversity_dx", 50.0), ("diversity_normal", 30.0),
                    ("normal", 10.0)],
        "decision": "switch", "decision_mode": "diversity_dx",
    }
    s = _make_mock_self(mode="auto", current="diversity_normal", rec=rec,
                        is_transmitting=True)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is True
    # Pending gespeichert, aber Modus NOCH NICHT gewechselt
    s._set_rx_mode_direct.assert_not_called()
    assert s._bandpilot_pending is not None
    assert s._bandpilot_pending[3] == "diversity_dx"
    s._show_bandpilot_auto_toast.assert_called_once()


def test_on_bandpilot_tx_finished_applies_pending():
    """tx_finished-Hook fuehrt gespeicherten Wechsel aus + leert pending."""
    s = MagicMock()
    # P46 R1-F3: pending-Tupel hat jetzt 5 Elemente inkl. current
    s._bandpilot_pending = ("40m", 13, {}, "diversity_dx", "diversity_normal")
    s.settings.band = "40m"  # Band identisch → wechseln
    s._current_rx_mode_string.return_value = "diversity_normal"  # Modus identisch
    s._set_rx_mode_direct = MagicMock()
    RadioMixin._on_bandpilot_tx_finished(s)
    s._set_rx_mode_direct.assert_called_once_with("diversity_dx")
    assert s._bandpilot_pending is None


def test_on_bandpilot_tx_finished_noop_when_no_pending():
    """Ohne pending-Wechsel: tx_finished tut nichts."""
    s = MagicMock()
    s._bandpilot_pending = None
    s._set_rx_mode_direct = MagicMock()
    RadioMixin._on_bandpilot_tx_finished(s)
    s._set_rx_mode_direct.assert_not_called()


def test_on_bandpilot_tx_finished_discards_when_band_changed():
    """R1-Final-Finding: Band-Wechsel waehrend TX → pending verwerfen.

    Szenario: User auf 20m → TX laeuft + Bandpilot pending fuer 20m →
    User wechselt auf 40m waehrend TX → TX endet → KEIN Modus-Wechsel
    (sonst wuerde der 20m-empfohlene Modus auf 40m gesetzt).
    """
    s = MagicMock()
    # P46 R1-F3: 5-Tupel inkl. current
    s._bandpilot_pending = ("20m", 13, {}, "diversity_dx", "diversity_normal")
    s.settings.band = "40m"  # User hat Band gewechselt
    s._current_rx_mode_string.return_value = "diversity_normal"
    s._set_rx_mode_direct = MagicMock()
    RadioMixin._on_bandpilot_tx_finished(s)
    s._set_rx_mode_direct.assert_not_called()
    # pending wird trotzdem geleert (kein Backlog)
    assert s._bandpilot_pending is None


# ── BandpilotAutoToast Smoke-Tests (Phase 6) ──────────────────────────────────

@pytest.fixture
def sample_rec():
    return {
        "top1": "diversity_dx",
        "top1_mean": 50.4,
        "ranking": [("diversity_dx", 50.4), ("normal", 35.2),
                    ("diversity_normal", 30.1)],
        "decision": "switch",
        "decision_mode": "diversity_dx",
    }


def test_auto_toast_instantiable_without_crash(qapp, sample_rec):
    """Toast laesst sich erstellen + zeigen ohne Exception (offscreen-mode)."""
    from ui.bandpilot_dialogs import BandpilotAutoToast
    toast = BandpilotAutoToast(None, "40m", 13, sample_rec)
    assert toast.windowFlags()  # Frameless+Tool-Flags gesetzt
    toast.show()
    qapp.processEvents()
    toast.close()


def test_auto_toast_contains_top1_label(qapp, sample_rec):
    from ui.bandpilot_dialogs import BandpilotAutoToast
    toast = BandpilotAutoToast(None, "40m", 13, sample_rec)
    # Sammle alle QLabel-Texte
    from PySide6.QtWidgets import QLabel
    texts = [w.text() for w in toast.findChildren(QLabel)]
    combined = " ".join(texts)
    assert "Diversity DX" in combined
    assert "40m" in combined
    assert "13 UTC" in combined
    toast.close()


# ── BandpilotManualDialog Smoke-Tests (Phase 7) ───────────────────────────────

def test_manual_dialog_instantiable(qapp, sample_rec):
    from ui.bandpilot_dialogs import BandpilotManualDialog
    dlg = BandpilotManualDialog(None, "40m", 13, sample_rec, "normal")
    assert dlg.chosen is None
    dlg.close()


def test_manual_dialog_select_returns_mode(qapp, sample_rec):
    """Direkter Aufruf von _select setzt chosen + accept."""
    from ui.bandpilot_dialogs import BandpilotManualDialog
    dlg = BandpilotManualDialog(None, "40m", 13, sample_rec, "normal")
    dlg._select("diversity_normal")
    assert dlg.chosen == "diversity_normal"
    dlg.close()


def test_manual_dialog_shows_current_marker(qapp, sample_rec):
    """● Marker erscheint vor dem aktuellen Modus."""
    from ui.bandpilot_dialogs import BandpilotManualDialog
    dlg = BandpilotManualDialog(None, "40m", 13, sample_rec, "normal")
    from PySide6.QtWidgets import QLabel
    texts = [w.text() for w in dlg.findChildren(QLabel)]
    # Eine Label-Zeile muss "●" enthalten + "Normal" erwaehnen
    has_current_marker = any("●" in t and "Normal" in t for t in texts)
    assert has_current_marker
    dlg.close()


# ── P35-Bug-E-Tests entfernt durch P46 (13.05.2026) ──────────────────────
# Die alten Tests test_bandpilot_skips_when_current_is_normal und
# test_bandpilot_rejects_normal_target testeten das Block-Verhalten das
# Mike mit P35-Bug-E am 11.05. eingebaut hatte. Mit P46 (12.05.) wurde
# diese Strategie zurueckgenommen — Bandpilot darf jetzt auch Normal
# vorschlagen + bei current=normal aktiv werden. Die positiven Pfade
# sind in tests/test_p46_bandpilot_normal.py (T1+T2) abgedeckt.
