"""P103 (21.05.2026, v0.97.80) — Statusbar Diversity-Subtyp + RF-Hint.

Mike-Field-Test 21.05. nach P102-Push: Statusbar zeigte nur „DIVERSITY",
fehlender Standard/DX-Suffix. Plus RF-Presets-Tabelle ist leer wenn noch
nichts gespeichert → User-Education-Hint.

Tests:
- T1: Statusbar-Source enthält Diversity-DX/Standard-Logik
- T2: _on_diversity_subtoggle_requested ruft _update_statusbar
- T3: settings_dialog hat _rf_hint_label Attribut + Hint-Text-Logik
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


def test_t1_statusbar_shows_diversity_subtype():
    """_update_statusbar muss Standard/DX aus _current_scoring_mode lesen."""
    src = _read("ui/main_window.py")
    m = re.search(r"def _update_statusbar\(self\):.*?(?=\n    def )",
                  src, re.DOTALL)
    assert m, "_update_statusbar nicht gefunden"
    body = m.group(0)
    assert "_current_scoring_mode" in body, (
        "P103: muss ControlPanel._current_scoring_mode lesen")
    assert "DIVERSITY DX" in body
    assert "DIVERSITY STANDARD" in body


def test_t2_subtoggle_updates_statusbar():
    """_on_diversity_subtoggle_requested muss _update_statusbar aufrufen
    damit Statusbar sofort den neuen Subtyp anzeigt."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _on_diversity_subtoggle_requested\(self\):.*?(?=\n    def )",
        src, re.DOTALL)
    assert m
    body = m.group(0)
    assert "_update_statusbar" in body, (
        "P103: subtoggle muss _update_statusbar rufen")


def test_t3_settings_dialog_has_rf_hint_label():
    # P104 (v0.97.81) Update: P103 Hint-Label wurde durch Band-Farb-Buttons
    # ersetzt (siehe test_p104_*). Hier nur prüfen dass die neue Struktur da ist.
    src = _read("ui/settings_dialog.py")
    assert "_rf_band_buttons" in src, "P104: _rf_band_buttons (P103-Hint abgelöst)"
    assert "_refresh_rf_status" in src, "P104: _refresh_rf_status-Methode"
