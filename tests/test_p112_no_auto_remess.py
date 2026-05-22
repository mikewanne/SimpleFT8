"""P112 (22.05.2026, v0.97.89) — Auto-Mess raus, KISS Option E.

Mike-Bug 22.05.: nach Statistik-Session in Nacht zeigte App "noch 3h"
obwohl er nicht eingemessen hatte. Diagnose: DXTuneDialog mit Auto-Accept
(dx_tune_dialog.py:490) wurde mehrfach automatisch getriggert (Re-Connect,
Mode-Wechsel) während Mike die App durchlaufen ließ → save_gain ohne Klick.

Spec Option E:
- Stale Gain (>6h)    → Anzeige "Re-Mess nötig" rot, Diversity läuft mit
                        alten Werten weiter. Niemals Auto-Dialog.
- Missing Gain        → Anzeige "Re-Mess nötig" rot, Diversity läuft mit
                        Standard 10/10. Niemals Auto-Dialog.
- Fresh Gain (≤6h)    → Anzeige "noch X h" grün, Diversity läuft mit
                        gespeicherten Werten.
- KALIBRIEREN-Klick   → DXTuneDialog (User-Pfad unverändert).

Opt-in Setting: "Auto-Gain bei Bandwechsel" (Default False, Auto-TUNE-
GroupBox). Wenn True + Bandwechsel + stale/missing → DXTuneDialog wie
früher.

Tests:
- T1: Settings-Default `auto_gain_on_band_change=False`
- T2: `_check_diversity_preset` Signatur mit `auto_remess: bool = False`
- T3: Source — stale-Pfad NICHT mehr DXTuneDialog (default-Pfad)
- T4: Source — missing-Pfad NICHT mehr DXTuneDialog (default-Pfad)
- T5: Source — auto_remess=True triggert weiterhin DXTuneDialog
- T6: `_on_band_changed` reicht Setting als `auto_remess` durch
- T7: `_format_gain_status` — MISSING zeigt "Re-Mess nötig" (statt grau)
- T8: `_format_gain_status` — STALE zeigt "Re-Mess nötig" (statt "fällig")
- T9: `_enable_diversity` MISSING-Pfad: ANT1=ANT2=Standard (10/10), nicht +10
- T10: Settings-Dialog hat `auto_gain_band_cb` Checkbox
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


def test_t1_setting_default_false():
    """DEFAULTS enthält auto_gain_on_band_change: False."""
    src = _read("config/settings.py")
    m = re.search(
        r'"auto_gain_on_band_change":\s*False\s*,',
        src,
    )
    assert m, ("P112: DEFAULTS muss auto_gain_on_band_change: False "
               "enthalten")


def test_t2_check_preset_signature():
    """_check_diversity_preset hat auto_remess: bool = False."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _check_diversity_preset\(self,\s*band:\s*str,\s*"
        r"scoring:\s*str,\s*clear_panels:\s*bool\s*=\s*True\s*,\s*"
        r"auto_remess:\s*bool\s*=\s*False\s*\)",
        src,
    )
    assert m, ("P112: _check_diversity_preset muss "
               "auto_remess: bool = False als 4. Parameter haben")


def test_t3_stale_path_no_auto_dialog():
    """Default-Pfad (auto_remess=False) ruft _enable_diversity, nicht
    _start_dx_tuning."""
    src = _read("ui/mw_radio.py")
    # Methodenkörper extrahieren
    m = re.search(
        r"def _check_diversity_preset\(.*?(?=\n    def )",
        src, re.DOTALL)
    assert m, "_check_diversity_preset nicht gefunden"
    body = m.group(0)
    # Es muss einen "no auto"-Branch geben, der _enable_diversity aufruft
    assert "if not auto_remess:" in body, (
        "P112: Branch `if not auto_remess:` fehlt")
    no_auto = body.split("if not auto_remess:")[1].split("auto_remess=True")[0]
    assert "_enable_diversity" in no_auto, (
        "P112: no-auto-Pfad muss _enable_diversity rufen")
    assert "_start_dx_tuning" not in no_auto, (
        "P112: no-auto-Pfad darf KEIN _start_dx_tuning rufen")


def test_t4_missing_path_no_auto_dialog():
    """Missing wird wie stale behandelt — gleicher Pfad."""
    # Wenn T3 grün ist, ist T4 implizit auch grün, weil der gleiche
    # Pfad (gain_status != "fresh") beide abdeckt.
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _check_diversity_preset\(.*?(?=\n    def )",
        src, re.DOTALL)
    body = m.group(0)
    # Es darf KEIN separater Branch für "missing" mit DXTuneDialog mehr existieren
    # (alles in if not auto_remess: zusammengeführt)
    no_auto_idx = body.find("if not auto_remess:")
    assert no_auto_idx >= 0
    after = body[no_auto_idx:]
    # Im no-auto-Branch wird der branch-name geloggt (für stale und missing)
    assert "_branch" in body[:no_auto_idx], (
        "P112: _branch-Variable für Logging muss vor no-auto-Branch stehen")


def test_t5_auto_remess_true_still_opens_dialog():
    """Bei auto_remess=True läuft alter Pfad: Lock + _start_dx_tuning."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _check_diversity_preset\(.*?(?=\n    def )",
        src, re.DOTALL)
    body = m.group(0)
    # Es muss ein Pfad existieren in dem _start_dx_tuning aufgerufen wird
    assert "_start_dx_tuning" in body, (
        "P112: auto_remess=True-Pfad muss _start_dx_tuning aufrufen")
    assert "_set_gain_measure_lock(True)" in body, (
        "P112: auto_remess=True-Pfad muss Lock setzen")


def test_t6_band_change_reads_setting():
    """_on_band_changed liest auto_gain_on_band_change und reicht durch."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _on_band_changed\(.*?(?=\n    def )",
        src, re.DOTALL)
    assert m, "_on_band_changed nicht gefunden"
    body = m.group(0)
    assert "auto_gain_on_band_change" in body, (
        "P112: _on_band_changed muss settings.get('auto_gain_on_band_change') "
        "lesen")
    assert "auto_remess=" in body, (
        "P112: _on_band_changed muss auto_remess als kwarg übergeben")


def test_t7_missing_shows_re_mess_noetig():
    """_format_gain_status missing-Branch zeigt 'Re-Mess nötig' rot."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _format_gain_status\(.*?(?=\n    def )",
        src, re.DOTALL)
    assert m, "_format_gain_status nicht gefunden"
    body = m.group(0)
    # Missing-Branch erkennt
    assert "is_missing" in body, (
        "P112: _format_gain_status muss is_missing-Variable nutzen")
    # Re-Mess nötig statt nicht kalibriert/grau
    # In Missing-Branch
    missing_block = body.split("if is_missing:")[1].split("ts = entry.get")[0]
    assert "Re-Mess nötig" in missing_block, (
        "P112: missing-Pfad muss 'Re-Mess nötig' zeigen")
    assert "#FF3333" in missing_block, (
        "P112: missing-Pfad muss rote Farbe nutzen")
    # "nicht kalibriert" raus
    assert "nicht kalibriert" not in body, (
        "P112: alter Text 'nicht kalibriert' muss weg sein")


def test_t8_stale_shows_re_mess_noetig():
    """_format_gain_status stale-Branch zeigt 'Re-Mess nötig', nicht
    mehr 'fällig'."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _format_gain_status\(.*?(?=\n    def )",
        src, re.DOTALL)
    body = m.group(0)
    # "Re-Mess fällig" muss weg sein
    assert "Re-Mess fällig" not in body, (
        "P112: alter Text 'Re-Mess fällig' muss durch 'nötig' ersetzt sein")
    # mindestens ein "Re-Mess nötig" muss da sein
    assert "Re-Mess nötig" in body, (
        "P112: 'Re-Mess nötig' muss im _format_gain_status stehen")


def test_t9_missing_diversity_uses_10_10():
    """_enable_diversity MISSING-Pfad: ANT1=ANT2=PREAMP_PRESETS, nicht +10."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _enable_diversity\(.*?(?=\n    def )",
        src, re.DOTALL)
    assert m, "_enable_diversity nicht gefunden"
    body = m.group(0)
    # Alter Code: ant2_gain = PREAMP_PRESETS.get(band, 10) + 10
    assert "PREAMP_PRESETS.get(band, 10) + 10" not in body, (
        "P112: ANT2 darf nicht mehr mit +10 dB Boost initialisiert werden")
    # Neuer Code: std_gain = PREAMP_PRESETS, dann beide gleich
    assert "std_gain" in body, (
        "P112: MISSING-Pfad muss std_gain-Variable nutzen")


def test_t10_settings_dialog_has_checkbox():
    """Settings-Dialog hat auto_gain_band_cb Checkbox in TUNE-GroupBox."""
    src = _read("ui/settings_dialog.py")
    # Widget-Anlage
    assert "self.auto_gain_band_cb = QCheckBox" in src, (
        "P112: Settings-Dialog muss self.auto_gain_band_cb anlegen")
    # Load
    assert (
        "self.auto_gain_band_cb.setChecked" in src
        and 'self.settings.get("auto_gain_on_band_change"' in src
    ), "P112: Load-Pfad fehlt"
    # Save
    assert 'self.settings.set("auto_gain_on_band_change"' in src, (
        "P112: Save-Pfad fehlt")
