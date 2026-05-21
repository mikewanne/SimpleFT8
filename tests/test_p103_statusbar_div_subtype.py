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
    src = _read("ui/settings_dialog.py")
    assert "_rf_hint_label" in src, "P103: _rf_hint_label-Attribut existiert"
    # Hint-Text bei leerer Tabelle
    assert "Noch keine RF-Presets" in src, "P103: Hint-Text für leere Tabelle"
    # _refresh_rf_table muss Hint setzen
    m = re.search(r"def _refresh_rf_table\(self\):.*?(?=\n    def )",
                  src, re.DOTALL)
    assert m
    body = m.group(0)
    assert "_rf_hint_label" in body, (
        "P103: _refresh_rf_table muss _rf_hint_label setzen")
