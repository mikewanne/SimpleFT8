"""P104 (21.05.2026, v0.97.81) — Settings-Vereinfachung + RF-Band-Buttons.

Mike-Spec 21.05.: power_watts + tx_level aus Settings raus (überflüssig
für Hobby-Funker), RF-Presets-Tabelle ersetzt durch Band-Farb-Buttons.

Tests:
- T1: power_watts nicht mehr in DEFAULTS
- T2: load() pop't alte power_watts + tx_level (Migration idempotent)
- T3: Settings.power_watts-Property entfernt
- T4: ADIF nutzt _current_power_watts statt settings.power_watts
- T5: mw_radio tx_level fest 75% (kein Settings-Lookup mehr)
- T6: main_window.py kein tx_audio_level-Setter mehr
- T7: settings_dialog hat _rf_band_buttons-Dict
- T8: _refresh_rf_status setzt grün/rot Properties
- T9: _on_rf_band_clicked öffnet Dialog bei grünen Buttons
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(encoding="utf-8")


def test_t1_defaults_no_power_watts():
    from config.settings import DEFAULTS
    assert "power_watts" not in DEFAULTS, "P104: power_watts aus DEFAULTS raus"


def test_t2_load_migrates_old_keys():
    """load() entfernt alte power_watts + tx_level + tx_levels_per_band."""
    from config.settings import Settings
    s = Settings()  # macht load() automatisch
    s._data["power_watts"] = 42
    s._data["tx_level"] = 80
    s._data["tx_levels_per_band"] = {"20m": 50, "40m": 60}
    s.load()
    assert "power_watts" not in s._data, "P104: load pop't power_watts"
    assert "tx_level" not in s._data, "P104: load pop't tx_level"
    assert "tx_levels_per_band" not in s._data, (
        "P104 Final-R1: load pop't auch tx_levels_per_band")


def test_t2b_mw_radio_band_change_no_tx_levels_per_band_lookup():
    """Final-R1-Catch: _on_band_changed darf tx_levels_per_band nicht
    aus Settings lesen (Kommentar-Verweise sind erlaubt)."""
    src = _read("ui/mw_radio.py")
    assert 'settings.get("tx_levels_per_band"' not in src, (
        "P104 Final-R1: _on_band_changed nutzt tx_levels_per_band nicht mehr")


def test_t3_settings_no_power_watts_property():
    """Settings.power_watts-Property komplett entfernt (nicht nur _data-Pop)."""
    from config.settings import Settings
    s = Settings()
    assert not hasattr(type(s), "power_watts") or \
        not isinstance(getattr(type(s), "power_watts", None), property), (
            "P104: power_watts-Property aus Settings-Klasse raus")


def test_t4_adif_uses_current_power_watts():
    src = _read("ui/mw_qso.py")
    assert "self.settings.power_watts" not in src, (
        "P104: kein settings.power_watts mehr im ADIF-Log")
    assert "_current_power_watts" in src, (
        "P104: ADIF nutzt ControlPanel._current_power_watts")


def test_t5_mw_radio_tx_level_fest_75():
    src = _read("ui/mw_radio.py")
    assert 'settings.get("tx_level"' not in src, (
        "P104: kein settings.get('tx_level')-Lookup mehr")
    assert "tx_level = 75" in src, (
        "P104: tx_level fest auf 75% (war Cap, Setting weg)")


def test_t6_main_window_no_tx_audio_level_setter():
    src = _read("ui/main_window.py")
    assert "self.radio.tx_audio_level = self.settings" not in src, (
        "P104: kein Live-Propagation von tx_level mehr")


def test_t7_settings_dialog_has_band_buttons():
    src = _read("ui/settings_dialog.py")
    assert "_rf_band_buttons" in src
    assert "self.rf_table" not in src or "QTableWidget" not in src, (
        "P104: alte rf_table-Tabelle entfernt")


def test_t8_refresh_rf_status_sets_state_properties():
    src = _read("ui/settings_dialog.py")
    m = re.search(r"def _refresh_rf_status\(self\):.*?(?=\n    # |\n    def )",
                  src, re.DOTALL)
    assert m, "_refresh_rf_status nicht gefunden"
    body = m.group(0)
    assert '"rfState", "green"' in body, "P104: grün-State setzen"
    assert '"rfState", "red"' in body, "P104: rot-State setzen"


def test_t9_band_click_handler_exists():
    src = _read("ui/settings_dialog.py")
    assert "def _on_rf_band_clicked" in src, "P104: Band-Klick-Handler"
    m = re.search(r"def _on_rf_band_clicked\(self, band: str\):.*?(?=\n    def )",
                  src, re.DOTALL)
    assert m
    body = m.group(0)
    assert "QMessageBox" in body, "P104: Confirm-Dialog beim Reset"
    assert "store.clear_band" in body, "P104: löscht via RFPresetStore"
