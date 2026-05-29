"""P119 (29.05.2026) — 10W-Einpendeln (Phase B) + Hochrechnungs-Krücke entfernt.

Mike-Wunsch: Das „Leistung wird auf 10 W eingeregelt" nach dem Kontroll-TUNE
(Gain-Messung) sowie die 10W→Ziel-Watt-Hochrechnung sind überflüssig — der
echte rfpower pro (Band, Ziel-Watt) wird im normalen Betrieb via
`_auto_adjust_tx_level` → `rf_preset_store.save` gepflegt.

DeepSeek-v4-pro GO unter Bedingung, dass der Auto-TUNE-Skip bei Bandwechsel von
`has_anchor(watt=10)` auf `has_any_preset` (band-existenz) umgestellt wird —
sonst liefe Auto-TUNE bei jedem Bandwechsel (UX-Regression).

Diese Datei ersetzt test_p54_fix.py (Phase-B-Konvergenz/Krücke obsolet). Die
SWR-Sicherheit (Freeze, Band-Sperre, Re-Entry/Cancel) ist weiter durch
test_p142 + test_p153 abgesichert.

Tests:
- T1: Phase B (_tune_converge_to_target) ist KOMPLETT entfernt
- T2: _wait_with_event_loop (Phase-B-Infrastruktur) entfernt
- T3: _kruecken_skalierung entfernt
- T4: _apply_rf_preset fällt bei load()==None direkt auf get_tx_power
- T5: kein 10W-Stützpunkt-Save mehr in _tune_post_swr_check
- T6: _tune_converged_rf-Referenzen entfernt
- T7: SWR-Freeze (_tune_last_valid_swr) bleibt erhalten (Sicherheit)
- T8: has_any_preset existiert + ist band-agnostisch
- T9: Auto-TUNE-Skip nutzt has_any_preset statt has_anchor(watt=10)
- T10: Anzeige "auf 10 W eingeregelt" aus beiden Dialogen raus
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MW_TX_SRC = (REPO / "ui" / "mw_tx.py").read_text()
MW_RADIO_SRC = (REPO / "ui" / "mw_radio.py").read_text()
MAIN_WINDOW_SRC = (REPO / "ui" / "main_window.py").read_text()
DX_DIALOG_SRC = (REPO / "ui" / "dx_tune_dialog.py").read_text()
AUTO_DIALOG_SRC = (REPO / "ui" / "auto_tune_dialog.py").read_text()
RF_STORE_SRC = (REPO / "core" / "rf_preset_store.py").read_text()


def _code_lines(src: str) -> str:
    """Nur Code-Zeilen (Kommentare raus) — Marker dürfen in Doku bleiben."""
    return "\n".join(
        l for l in src.split("\n")
        if l.strip() and not l.strip().startswith("#")
    )


# ── T1-T3: Phase B + Krücke + Infrastruktur entfernt ────────────────────


def test_t1_phase_b_converge_removed():
    """T1: _tune_converge_to_target (Phase B, 10W-Einpendeln) ist weg."""
    assert "def _tune_converge_to_target" not in MW_TX_SRC, (
        "P119: Phase B (_tune_converge_to_target) muss entfernt sein.")
    # Auch kein Aufruf mehr
    assert "_tune_converge_to_target(" not in _code_lines(MW_TX_SRC), (
        "P119: kein Aufruf von _tune_converge_to_target im Code.")


def test_t2_wait_event_loop_removed():
    """T2: _wait_with_event_loop (nur Phase-B-Infrastruktur) ist weg."""
    assert "def _wait_with_event_loop" not in MW_TX_SRC, (
        "P119: _wait_with_event_loop (Phase-B-Helper) muss entfernt sein.")


def test_t3_kruecke_removed():
    """T3: _kruecken_skalierung (10W→Ziel-Watt-Hochrechnung) ist weg."""
    assert "def _kruecken_skalierung" not in MW_TX_SRC, (
        "P119: _kruecken_skalierung muss entfernt sein.")
    assert "_kruecken_skalierung(" not in _code_lines(MW_TX_SRC), (
        "P119: kein Aufruf von _kruecken_skalierung im Code.")


# ── T4: _apply_rf_preset fällt direkt auf Settings-Default ──────────────


def test_t4_apply_rf_preset_default_fallback():
    """T4: _apply_rf_preset nutzt bei load()==None direkt get_tx_power
    (kein Krücken-Zwischenschritt mehr)."""
    code = _code_lines(MW_TX_SRC)
    assert "self._rfpower_current = self.settings.get_tx_power(band, default=50)" in code, (
        "P119: Default-Fallback get_tx_power muss erhalten sein.")
    # Krücke darf im else-Pfad nicht mehr aufgerufen werden
    idx = MW_TX_SRC.find("def _apply_rf_preset")
    idx_end = MW_TX_SRC.find("\n    def ", idx + 10)
    block = MW_TX_SRC[idx:idx_end]
    # Aufruf (mit Klammer) — der Docstring darf den Namen erwähnen ("entfallen").
    assert "_kruecken_skalierung(" not in block, (
        "P119: _apply_rf_preset darf keine Krücke mehr aufrufen.")


# ── T5: Kein 10W-Stützpunkt-Save mehr ───────────────────────────────────


def test_t5_no_10w_save_in_post_check():
    """T5: _tune_post_swr_check speichert keinen 10W-Stützpunkt mehr."""
    idx = MW_TX_SRC.find("def _tune_post_swr_check")
    idx_end = MW_TX_SRC.find("\n    def ", idx + 10)
    block = MW_TX_SRC[idx:idx_end]
    code = _code_lines(block)
    # Kein hardcodierter 10W-Save mehr
    assert "self.settings.band, 10, rf_to_save" not in code, (
        "P119: 10W-Stützpunkt-Save muss aus dem Post-Check raus.")
    assert "rf_to_save" not in code, (
        "P119: rf_to_save-Logik (Phase-B-Ergebnis) muss weg sein.")


def test_t6_converged_rf_removed():
    """T6: _tune_converged_rf-State ist komplett entfernt."""
    assert "_tune_converged_rf" not in _code_lines(MW_TX_SRC), (
        "P119: _tune_converged_rf darf im mw_tx-Code nicht mehr vorkommen.")
    assert "_tune_converged_rf" not in _code_lines(MAIN_WINDOW_SRC), (
        "P119: _tune_converged_rf-Init muss aus main_window raus.")


# ── T7: SWR-Sicherheit (Freeze) bleibt ──────────────────────────────────


def test_t7_swr_freeze_preserved():
    """T7 (Hardware-Sicherheit): Der SWR-Freeze (_tune_last_valid_swr aus
    _compute_match_swr) bleibt — P119 entfernt NUR Phase B, nicht die
    Band-Sperren-Bewertung."""
    code = _code_lines(MW_TX_SRC)
    assert "self._tune_last_valid_swr = swr_after_match" in code, (
        "P119: SWR-Freeze (Phase-A-Match) MUSS erhalten bleiben.")
    assert "swr_after_match = self._compute_match_swr()" in code, (
        "P119: Median-SWR-Quelle (_compute_match_swr) MUSS bleiben.")


# ── T8-T9: has_any_preset Auto-TUNE-Skip ────────────────────────────────


def test_t8_has_any_preset_exists():
    """T8: rf_preset_store.has_any_preset(radio, band) existiert + ist
    band-agnostisch (kein watt-Parameter)."""
    assert "def has_any_preset(self, radio: str, band: str) -> bool:" in RF_STORE_SRC, (
        "P119: has_any_preset(radio, band) muss existieren.")


def test_t9_band_change_uses_has_any_preset():
    """T9 (DeepSeek-Blocker-Fix): Auto-TUNE-Skip bei Bandwechsel nutzt
    has_any_preset statt has_anchor(watt=10). Sonst liefe Auto-TUNE bei
    jedem Bandwechsel (UX-Regression), da der 10W-Anker entfällt."""
    code = _code_lines(MW_RADIO_SRC)
    assert "self.rf_preset_store.has_any_preset(" in code, (
        "P119: Bandwechsel muss has_any_preset nutzen.")
    assert "has_anchor(" not in code, (
        "P119: has_anchor(watt=10)-Aufruf muss aus dem Bandwechsel-Pfad raus.")


# ── T10: Anzeige "auf 10 W eingeregelt" raus ────────────────────────────


def test_t10_no_10w_regelung_label():
    """T10: Die Anzeige 'Leistung wird auf 10 W eingeregelt' ist aus beiden
    TUNE-Dialogen entfernt (Phase-B-UX-Ballast)."""
    assert "auf 10 W eingeregelt" not in DX_DIALOG_SRC, (
        "P119: 10W-Einregel-Anzeige muss aus dx_tune_dialog raus.")
    assert "auf 10 W eingeregelt" not in AUTO_DIALOG_SRC, (
        "P119: 10W-Einregel-Anzeige muss aus auto_tune_dialog raus.")
