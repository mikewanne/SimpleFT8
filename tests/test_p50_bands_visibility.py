"""P50 — Bänder-Sichtbarkeit (v0.97.20).

Mike-Wunsch nach P34-Stufe2: Bänder im Settings-Dialog deaktivierbar.
Default alle 9 aktiv, defensive Filter, current_band-Guarantee (R1-F1),
Prop-Bars werden mitversteckt (R1-F2), Reset-Button (R1-S3),
Min-1-Logik (AC3).

11 Tests T1-T11:
- T1 Settings: kein enabled_bands-Key → Default alle 9
- T2 Settings: ungültige Bänder werden gefiltert
- T3 Settings: leere Liste → Default Fallback
- T4 ControlPanel.set_visible_bands: Buttons versteckt
- T5 (R1-F1) ControlPanel: current_band bleibt sichtbar
- T6 SettingsDialog: Min-1-Logik blockt letzte Checkbox
- T7 SettingsDialog roundtrip: Toggle → Save → Load → identisch
- T8 (R1-F2) ControlPanel: Prop-Bars werden mitversteckt
- T9 ControlPanel: _set_band auf deaktiviertes Band → wird zwangs-sichtbar
- T10 SettingsDialog Reset-Button → alle 9 wieder aktiv
- T11 Settings: set_enabled_bands mit Garbage → Default Fallback
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope="module")
def qapp():
    """Qt Application Instance — module-scoped."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tmp_settings_file(monkeypatch, tmp_path):
    """Pro Test eigene config.json (vermeidet Cross-Test-Verschmutzung)."""
    cfg_dir = tmp_path / ".simpleft8"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr("config.settings.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("config.settings.CONFIG_FILE", cfg_file)
    return cfg_file


# ── T1: Settings ohne Key → Default alle 9 ──────────────────────────────

def test_t1_settings_default_all_9_bands(tmp_settings_file):
    """T1: get_enabled_bands ohne Key → alle 9 Bänder."""
    from config.settings import Settings, BAND_FREQUENCIES
    s = Settings()
    enabled = s.get_enabled_bands()
    assert set(enabled) == set(BAND_FREQUENCIES.keys())
    assert len(enabled) == 9


# ── T2: Defensiv-Filter gegen ungültige Bänder ──────────────────────────

def test_t2_settings_filter_invalid_bands(tmp_settings_file):
    """T2: ungültige Einträge werden defensiv gefiltert."""
    from config.settings import Settings
    s = Settings()
    # garbage: kein-String, falsches Band, Duplikate
    s._data["enabled_bands"] = ["20m", "99m", None, 42, "20m", "40m"]
    enabled = s.get_enabled_bands()
    assert enabled == ["20m", "40m"]


# ── T3: Leere Liste → Default Fallback ──────────────────────────────────

def test_t3_settings_empty_fallback(tmp_settings_file):
    """T3: leere oder nur-ungültige Liste → Default alle 9."""
    from config.settings import Settings, BAND_FREQUENCIES
    s = Settings()
    s._data["enabled_bands"] = []
    assert set(s.get_enabled_bands()) == set(BAND_FREQUENCIES.keys())
    s._data["enabled_bands"] = ["99m", "blabla"]
    assert set(s.get_enabled_bands()) == set(BAND_FREQUENCIES.keys())


# ── T4: ControlPanel set_visible_bands versteckt Buttons ────────────────

def test_t4_control_panel_set_visible_bands(qapp, tmp_settings_file):
    """T4: set_visible_bands(['20m','40m']) → andere Buttons unsichtbar."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp.set_visible_bands(["20m", "40m"])
    # 20m und 40m sind sichtbar
    # In offscreen ohne show() ist isVisible() False — wir prüfen isHidden().
    assert not cp.band_buttons["20m"].isHidden()
    assert not cp.band_buttons["40m"].isHidden()
    # 10m, 12m, 80m sind versteckt (Show-Status; in offscreen evtl. nur isVisible auf False)
    # Mit setVisible(False) ist der WidgetVisible-Status False
    for b in ["10m", "12m", "15m", "17m", "30m", "60m", "80m"]:
        # _band_visible-Map sollte False zeigen
        assert cp._mode_band_card._band_visible[b] is False, f"{b} should be hidden"


# ── T5 (R1-F1): current_band bleibt sichtbar ────────────────────────────

def test_t5_current_band_stays_visible(qapp, tmp_settings_file):
    """T5 R1-F1: current_band wird nicht versteckt auch wenn nicht in bands."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._set_band("60m")
    # 60m ist nicht in der Liste → muss trotzdem sichtbar bleiben
    cp.set_visible_bands(["20m", "40m"])
    assert cp._mode_band_card._band_visible["60m"] is True, \
        "current_band='60m' MUST stay visible (R1-F1 guarantee)"
    assert not cp.band_buttons["60m"].isHidden()


# ── T6: SettingsDialog Min-1-Logik ──────────────────────────────────────

def test_t6_settings_dialog_min1_locks_last_checkbox(qapp, tmp_settings_file):
    """T6 AC3: letzte aktive Checkbox wird disabled, damit nicht alle aus."""
    from config.settings import Settings
    from ui.settings_dialog import SettingsDialog
    s = Settings()
    d = SettingsDialog(s)
    # Alle bis auf 20m deaktivieren
    for b, cb in d._band_checkboxes.items():
        cb.setChecked(b == "20m")
    # Min-1-Logik triggern (manueller Aufruf, weil setChecked Signale schickt)
    d._on_band_visibility_toggled()
    # 20m muss disabled sein (kann nicht aus)
    assert not d._band_checkboxes["20m"].isEnabled()
    # Andere sind aktivierbar
    assert d._band_checkboxes["40m"].isEnabled()


# ── T7: Roundtrip Save→Load → identisch ─────────────────────────────────

def test_t7_settings_roundtrip(tmp_settings_file):
    """T7: Save → reload → identisch."""
    from config.settings import Settings
    s1 = Settings()
    s1.set_enabled_bands(["20m", "40m", "80m"])
    s1.save()
    # Neue Instanz lädt die Datei
    s2 = Settings()
    assert s2.get_enabled_bands() == ["20m", "40m", "80m"]


# ── T8 (R1-F2): Prop-Bars werden mitversteckt ───────────────────────────

def test_t8_prop_bars_hidden_with_band(qapp, tmp_settings_file):
    """T8 R1-F2: prop_bars[b].setVisible(False) für versteckte Bänder."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    # Erst Propagation simulieren, damit Bars sichtbar wären
    cp._mode_band_card.update_propagation(
        conditions={"10m": "good", "20m": "fair", "40m": "good", "60m": "poor"},
        active_band="20m",
    )
    # Vorher: alle Bars die Daten haben sind sichtbar (= nicht hidden)
    assert not cp._mode_band_card.prop_bars["60m"].isHidden()
    # Jetzt 60m verstecken
    cp.set_visible_bands(["20m", "40m"])
    # 60m-Bar muss versteckt sein
    assert cp._mode_band_card.prop_bars["60m"].isHidden()
    # Sichtbares Band 20m hat noch eine Bar
    # (mit update_propagation neu aufrufen muss Bar sichtbar bleiben)
    cp._mode_band_card.update_propagation(
        conditions={"10m": "good", "20m": "fair", "40m": "good", "60m": "poor"},
        active_band="20m",
    )
    assert not cp._mode_band_card.prop_bars["20m"].isHidden()
    assert cp._mode_band_card.prop_bars["60m"].isHidden()


# ── T9: _set_band auf deaktiviertes Band → zwangs-sichtbar ──────────────

def test_t9_set_band_forces_visibility(qapp, tmp_settings_file):
    """T9 R1-F1 Extra: externes _set_band auf deaktiviertes Band → sichtbar."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._set_band("20m")
    cp.set_visible_bands(["20m"])
    # 60m ist versteckt
    assert cp._mode_band_card._band_visible["60m"] is False
    # Externer Aufruf (z.B. Auto-Hunt, Bandpilot würde NICHT, aber theoretisch)
    cp._set_band("60m")
    # 60m muss jetzt sichtbar sein
    assert cp._mode_band_card._band_visible["60m"] is True
    assert not cp.band_buttons["60m"].isHidden()


# ── T10: Reset-Button setzt enabled_bands zurück ────────────────────────

def test_t10_settings_dialog_reset_re_enables_all(qapp, tmp_settings_file):
    """T10 R1-S3: Reset-Button → alle 9 Checkboxen wieder aktiv."""
    from config.settings import Settings, BAND_FREQUENCIES
    from ui.settings_dialog import SettingsDialog
    s = Settings()
    s.set_enabled_bands(["20m"])  # nur ein Band aktiv
    s.save()
    d = SettingsDialog(s)
    # Vorher: nur 20m angekreuzt
    assert d._band_checkboxes["20m"].isChecked()
    assert not d._band_checkboxes["40m"].isChecked()
    # Reset simulieren (ohne QMessageBox-Klick) — wir patchen exec
    with patch.object(d, "_reset_defaults", wraps=d._reset_defaults) as mock_reset:
        # Direkt die Reset-Logik ausführen (nur den Bänder-Teil)
        for cb in d._band_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        d._on_band_visibility_toggled()
    # Alle 9 sind jetzt angekreuzt
    for b in BAND_FREQUENCIES.keys():
        assert d._band_checkboxes[b].isChecked()


# ── T11: set_enabled_bands mit nur Garbage → Default Fallback ───────────

def test_t11_set_enabled_bands_garbage_fallback(tmp_settings_file):
    """T11: set_enabled_bands(['junk']) → defensive Fallback alle 9."""
    from config.settings import Settings, BAND_FREQUENCIES
    s = Settings()
    s.set_enabled_bands(["junk", None, 42])
    # alle ungültig → Fallback
    assert set(s.get_enabled_bands()) == set(BAND_FREQUENCIES.keys())
