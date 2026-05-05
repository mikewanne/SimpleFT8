"""Auto-Hunt Erweiterung (v0.75) — Tests fuer Session-Lifecycle, Slot-Affinitaet,
Race-Condition-Sicherung und Stop-Reasons.

Run: ./venv/bin/python3 -m pytest tests/test_auto_hunt_extended.py -v
"""
from __future__ import annotations

import time
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def qapp():
    """QApplication-Singleton — Voraussetzung fuer Qt-Signal-Emit."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class _MockQSOLog:
    """Minimaler QSO-Log-Mock (parallel zu test_modules.py._MockQSOLog)."""
    def __init__(self, worked=None, worked_on_band=None):
        self._worked = set(worked or [])
        self._wob = set(worked_on_band or [])

    def is_worked(self, call):
        return call in self._worked

    def is_worked_on_band(self, call, band):
        return (call, band) in self._wob


# ─────────────────────────────────────────────────────────────────────────────
# Commit 4 — Session-Lifecycle (start/stop)
# ─────────────────────────────────────────────────────────────────────────────

def test_start_sets_active_starts_timer_resets_state(qapp):
    """start_auto_hunt setzt active=True, startet Timer, resetet State."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    # Vorbedingung: alter State vorhanden
    hunt._cooldown = {"DL1OLD": time.time()}
    hunt._last_tx_even = True
    hunt._manual_override = True

    hunt.start_auto_hunt(600)

    assert hunt.active is True
    assert hunt._auto_hunt_timer.isActive(), "Timer muss laufen"
    assert hunt._cooldown == {}, "Cooldowns muessen geleert sein"
    assert hunt._last_tx_even is None, "_last_tx_even muss reset sein"
    assert hunt._manual_override is False
    assert hunt._hunt_session_start > 0


def test_double_start_restarts_timer(qapp):
    """Doppelklick-Schutz: zweiter start_auto_hunt restartet Timer sauber."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.start_auto_hunt(600)
    first_session_start = hunt._hunt_session_start
    assert hunt._auto_hunt_timer.isActive()

    time.sleep(0.01)  # damit time.time() definitiv weitergetickt ist
    hunt.start_auto_hunt(600)

    assert hunt.active is True
    assert hunt._auto_hunt_timer.isActive()
    assert hunt._hunt_session_start > first_session_start, (
        "Doppel-Start muss neue Session-Start-Zeit setzen"
    )


@pytest.mark.parametrize("reason,should_clear", [
    ("timer_expired", True),
    ("manual_halt", True),
    ("easter_egg_off", True),
    ("band_change", True),
    ("ft_mode_change", True),     # v0.78: ehemals "mode_change", umbenannt
    ("rx_mode_change", True),     # v0.78: NEU (Diversity → Normal)
    ("superseded", True),         # v0.78: NEU (Mutually-exclusive)
    ("totmann_expired", False),   # User soll fortsetzen koennen
])
def test_stop_reasons_clear_cooldown_and_last_tx_even_correctly(
    qapp, reason, should_clear
):
    """stop_auto_hunt cleart Cooldown+_last_tx_even ausser bei totmann_expired."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.start_auto_hunt(600)
    hunt._cooldown = {"DL1ABC": time.time()}
    hunt._last_tx_even = True

    hunt.stop_auto_hunt(reason)

    assert hunt.active is False
    assert not hunt._auto_hunt_timer.isActive()
    if should_clear:
        assert hunt._cooldown == {}, f"{reason} muss Cooldown leeren"
        assert hunt._last_tx_even is None, f"{reason} muss _last_tx_even reset"
    else:
        assert "DL1ABC" in hunt._cooldown, (
            f"{reason} darf Cooldown NICHT leeren (User-fortsetzbar)"
        )
        assert hunt._last_tx_even is True


@pytest.mark.parametrize("reason", [
    "timer_expired", "manual_halt", "band_change",
    "ft_mode_change", "rx_mode_change", "superseded",
    "totmann_expired", "easter_egg_off",
])
def test_auto_hunt_stopped_signal_emits_with_reason(qapp, reason):
    """auto_hunt_stopped(reason) wird bei jedem Stop emittiert."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.start_auto_hunt(600)
    received = []
    hunt.auto_hunt_stopped.connect(lambda r: received.append(r))

    hunt.stop_auto_hunt(reason)

    assert received == [reason], f"Signal sollte ['{reason}'] sein, war {received}"


def test_qso_log_unaffected_by_stop(qapp):
    """_qso_log wird durch stop_auto_hunt NIEMALS angetastet (24h-Block bleibt)."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    qso_log = _MockQSOLog(worked={"DL1OLD"}, worked_on_band={("DL1OLD", "20m")})
    hunt.set_qso_log(qso_log)
    hunt.set_band("20m")
    hunt.start_auto_hunt(600)

    for reason in ("timer_expired", "manual_halt", "band_change",
                   "ft_mode_change", "rx_mode_change", "superseded",
                   "totmann_expired", "easter_egg_off"):
        hunt.start_auto_hunt(600)  # Session re-starten zwischen Tests
        hunt.stop_auto_hunt(reason)
        assert hunt._qso_log is qso_log, f"_qso_log bleibt nach {reason}"
        assert qso_log.is_worked("DL1OLD"), f"DL1OLD bleibt worked nach {reason}"
        assert qso_log.is_worked_on_band("DL1OLD", "20m")


# ─────────────────────────────────────────────────────────────────────────────
# Commit 5 — Slot-Affinitaet + Race-Condition-Doppel-Check
# ─────────────────────────────────────────────────────────────────────────────

def _make_cq_msg(call: str, freq_hz: int = 1500, snr: int = -10,
                 tx_even: bool = True):
    """Mini-Mock einer FT8-CQ-Message fuer select_next-Tests."""
    from types import SimpleNamespace
    return SimpleNamespace(
        is_cq=True,
        caller=call,
        grid_or_report="JO31",
        is_grid=True,
        snr=snr,
        freq_hz=freq_hz,
        _tx_even=tx_even,
    )


def test_double_active_check_in_select_next(qapp):
    """Race-Condition-Sicherung: aktiv-Check VOR Return blockt 'letztes QSO'.

    Szenario: select_next laeuft, Kandidat ist gefunden, dann timer_expired
    feuert (active=False). Der zweite active-Check VOR return verhindert
    dass ein finaler Candidate noch herausgegeben wird.
    """
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.start_auto_hunt(600)
    msg = _make_cq_msg("DL1ABC", tx_even=True)

    # Verhalten emulieren: nach Kandidaten-Auswahl wird active=False gesetzt
    # (z.B. durch parallel feuernden Timer). Wir patchen _score so dass es
    # einmal active deaktiviert.
    original_score = hunt._score

    def _spying_score(c):
        result = original_score(c)
        hunt.active = False  # simuliert Race: Timer ist gerade abgelaufen
        return result

    hunt._score = _spying_score

    result = hunt.select_next([msg], qso_idle=True, presence_ok=True)
    assert result is None, "Doppel-Active-Check muss letzten Candidate blocken"


def test_slot_affinity_prefers_same_tx_even(qapp):
    """Bei _last_tx_even=True wird Kandidat mit tx_even=True bevorzugt."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.start_auto_hunt(600)
    hunt._last_tx_even = True  # Affinitaet aus vorherigem Zyklus

    msg_even = _make_cq_msg("DL1EVEN", tx_even=True, snr=-15)
    msg_odd = _make_cq_msg("DL2ODD", tx_even=False, snr=-5)  # bessere SNR
    # Trotz schlechterer SNR muss DL1EVEN gewaehlt werden (Slot-Affinitaet).

    result = hunt.select_next([msg_even, msg_odd], True, True)
    assert result is not None
    assert result.call == "DL1EVEN", (
        "Slot-Affinitaet: Kandidat mit gleichem tx_even muss bevorzugt werden"
    )
    assert hunt._last_tx_even is True  # Affinitaet bleibt


def test_slot_affinity_fallback_when_no_match(qapp):
    """Wenn kein Kandidat mit gleichem tx_even: Fallback auf alle Kandidaten."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.start_auto_hunt(600)
    hunt._last_tx_even = True  # Wir wollen even, aber keiner ist da

    msg_odd1 = _make_cq_msg("DL1ODD1", tx_even=False, snr=-15)
    msg_odd2 = _make_cq_msg("DL2ODD2", tx_even=False, snr=-5)  # bessere SNR

    result = hunt.select_next([msg_odd1, msg_odd2], True, True)
    assert result is not None
    assert result.call == "DL2ODD2", (
        "Fallback: ohne even-Kandidat soll bester odd gewaehlt werden"
    )
    # _last_tx_even wird auf den neuen Slot aktualisiert
    assert hunt._last_tx_even is False


def test_auto_hunt_with_corrected_tx_even(qapp):
    """V3-Slot-Fix: Auto-Hunt arbeitet weiterhin korrekt wenn _tx_even
    jetzt vom Decoder direkt gesetzt wird (latenz-frei) statt vom
    is_even_cycle() zur Decode-Output-Zeit (potentiell Folge-Slot).

    Regression-Sicherung gegen R1-Frage: 'Hat Auto-Hunt mit dem alten,
    Latenz-bedingt FALSCHEN _tx_even gearbeitet und durch Inversion
    kompensiert?' R1+Code-Analyse: Nein, kein Inversion-Schutz im Code.
    Fix korrigiert, bricht nicht.

    Test: Mock-Message mit Decoder-typisch gesetzten Slot-Feldern
    (_tx_even = aus target_slot_start abgeleitet). Auto-Hunt waehlt
    den Kandidat und setzt _last_tx_even korrekt.
    """
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.start_auto_hunt(600)
    hunt._last_tx_even = None  # noch keine Affinitaet

    # Decoder hat _tx_even=True gesetzt (TX-Slot der Nachricht ist EVEN).
    # _slot_start_ts simuliert was Decoder.target_slot_start liefert.
    msg = _make_cq_msg("DL3DEC", tx_even=True, snr=-12)
    msg._slot_start_ts = 1730000100.0  # zusaetzlich Decoder-Zeitstempel

    result = hunt.select_next([msg], qso_idle=True, presence_ok=True)
    assert result is not None
    assert result.call == "DL3DEC"
    assert result.tx_even is True, "tx_even muss aus Decoder-Quelle uebernommen sein"
    # _last_tx_even wird gespeichert fuer naechsten Zyklus
    assert hunt._last_tx_even is True


# ─────────────────────────────────────────────────────────────────────────────
# Commit 9 — UI-Integration
# ─────────────────────────────────────────────────────────────────────────────

def test_control_panel_three_mode_buttons_initially_hidden(qapp):
    """Smoke-Test: ControlPanel hat btn_omni_cq + btn_auto_hunt initial hidden."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from ui.control_panel import ControlPanel
    from config.settings import Settings
    settings = Settings()
    cp = ControlPanel(settings)

    # btn_cq: immer sichtbar
    assert cp.btn_cq is not None
    assert not cp.btn_cq.isHidden(), "btn_cq muss immer sichtbar sein"
    assert cp.btn_cq.text() == "CQ RUFEN"

    # btn_omni_cq + btn_auto_hunt: initial hidden (nur via Easter-Egg)
    assert cp.btn_omni_cq is not None
    assert cp.btn_omni_cq.isHidden(), "btn_omni_cq muss initial hidden sein"
    assert cp.btn_omni_cq.text() == "OMNI CQ"

    assert cp.btn_auto_hunt is not None
    assert cp.btn_auto_hunt.isHidden(), "btn_auto_hunt muss initial hidden sein"
    assert cp.btn_auto_hunt.text() == "AUTO HUNT"

    # QButtonGroup NICHT exclusive (ab v0.79): erlaubt Re-Klick-Deselect
    # auf btn_cq. Mutually-exclusive zwischen OMNI ↔ Auto-Hunt wird in
    # main_window.py via "superseded"-Reason gemacht.
    assert cp.mode_button_group.exclusive() is False
    assert len(cp.mode_button_group.buttons()) == 3

    cp.deleteLater()


def test_auto_hunt_timer_expiry_via_emit_triggers_stop_signal(qapp):
    """Timer-Ablauf simuliert via direktem timeout.emit() → Stop-Signal."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    received = []
    hunt.auto_hunt_stopped.connect(lambda r: received.append(r))

    hunt.start_auto_hunt(600)
    assert hunt.active

    # Timer-Ablauf simulieren (ohne 10 Min zu warten)
    hunt._auto_hunt_timer.timeout.emit()

    assert not hunt.active, "Timer-Expiry muss active=False setzen"
    assert received == ["timer_expired"]
    assert hunt._cooldown == {}, "timer_expired muss Cooldowns leeren"
