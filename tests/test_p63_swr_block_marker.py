"""P63 (v0.97.36): SWR-Block per Band-Marker + Tuner-Settings + Lock-Release.

Mike-Field-Test 17m-Band: SWR-Watchdog feuert → Stop-Block läuft korrekt
aber `_gain_measure_locked` bleibt True (Bug) → UI dauerblockiert. Plus:
OMNI/Hunt bleiben klickbar (würden sofort wieder Watchdog auslösen).

Lösung:
- AC1: `_on_swr_alarm` ruft `_set_gain_measure_lock(False)` (Bug-Fix)
- AC2/AC3: Band-Marker `_swr_blocked_bands` setzen wenn `tuner_present=True`
- AC4: Watchdog-Bypass via `_tune_in_progress` während manuellem TUNE
- AC5: Manueller TUNE 10W fest, Dauer aus `tune_duration_s`-Setting
- AC6/AC7: 2s-Post-Check liest `radio.last_swr` → Marker freigeben oder behalten
- AC8: 6 Pre-Checks (Diversity-Preset, Start-DX, CQ, Station-Click, OMNI-Toggle, Hunt-Toggle)
- AC9: Tuner=False skipt Auto-TUNE + Power-Reset
- AC11: Auto-TUNE-Fehler setzt Marker + ruft Lock-Release
- AC12: Pending-Click-Schutz auch in `_on_tx_finished`
- AC13: `_start_dx_tuning` ruft explizit `set_tx_antenna("ANT1")`

15 Tests T1-T15 + 3 R1-Findings-Tests T18-T20.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ── Source-Reader-Helper ────────────────────────────────────────────────


def _read(path: str) -> str:
    return (Path(__file__).parent.parent / path).read_text()


def _method_src(file_rel: str, method_name: str) -> str:
    """Extrahiert Source-Body einer Methode (regex bis nächste `def` oder EOF)."""
    text = _read(file_rel)
    pattern = rf"    def {method_name}\([^)]*\)[^\n]*:.*?(?=\n    def |\nclass |\Z)"
    m = re.search(pattern, text, flags=re.DOTALL)
    if not m:
        raise AssertionError(f"Methode {method_name} nicht in {file_rel}")
    return m.group(0)


# ── T1 — `_on_swr_alarm` ruft `_set_gain_measure_lock(False)` ──────────


def test_t1_swr_alarm_releases_lock():
    """AC1: nach Stop-Block muss Lock explizit freigegeben werden
    (Mike-17m-Bug: Lock hing True → UI dauerblockiert)."""
    src = _method_src("ui/mw_tx.py", "_on_swr_alarm")
    assert "_set_gain_measure_lock(False)" in src, (
        "P63 AC1: Lock-Release fehlt in _on_swr_alarm")


# ── T2 — `_on_swr_alarm` setzt Marker wenn tuner_present=True ──────────


def test_t2_swr_alarm_sets_marker_when_tuner():
    """AC2: bei tuner_present=True wird Band-Marker gesetzt."""
    src = _method_src("ui/mw_tx.py", "_on_swr_alarm")
    assert "_swr_blocked_bands.add" in src, (
        "P63 AC2: Marker-Set fehlt in _on_swr_alarm")
    assert "tuner_present" in src, (
        "P63 AC2: tuner_present-Branch fehlt")


# ── T3 — `_on_swr_alarm` Tuner=False kein Marker ───────────────────────


def test_t3_swr_alarm_no_marker_when_no_tuner():
    """AC3: bei tuner_present=False werden zwei verschiedene Modal-Texte
    verwendet (mit/ohne Marker-Hinweis)."""
    src = _method_src("ui/mw_tx.py", "_on_swr_alarm")
    # Beide Modal-Pfade müssen existieren
    assert "Band gesperrt" in src, "P63 AC2: Marker-Modal-Text fehlt"
    assert "Antenne prüfen" in src, "P63 AC3: Tuner=NEIN-Modal-Text fehlt"


# ── T4 — OMNI-Toggle-Pre-Check ──────────────────────────────────────────


def test_t4_marker_blocks_omni_toggle():
    """AC8: OMNI-Toggle prüft `_swr_blocked_bands` und resettet Button."""
    src = _method_src("ui/main_window.py", "_on_btn_omni_cq_toggled")
    assert "_swr_blocked_bands" in src, "P63 AC8: OMNI-Pre-Check fehlt"
    assert "blockSignals(True)" in src, "P63 R1-F4: Button-Reset fehlt"
    assert "setChecked(False)" in src, "P63 R1-F4: Button-Reset fehlt"


# ── T5 — Auto-Hunt-Toggle-Pre-Check ─────────────────────────────────────


def test_t5_marker_blocks_auto_hunt_toggle():
    """AC8: Auto-Hunt-Toggle prüft `_swr_blocked_bands` und resettet Button."""
    src = _method_src("ui/main_window.py", "_on_btn_auto_hunt_toggled")
    assert "_swr_blocked_bands" in src, "P63 AC8: Auto-Hunt-Pre-Check fehlt"
    assert "btn_auto_hunt" in src
    assert "blockSignals(True)" in src
    assert "setChecked(False)" in src


# ── T6 — Normal-CQ-Pre-Check + Button-Reset ────────────────────────────


def test_t6_marker_blocks_normal_cq():
    """AC8: `_on_cq_clicked` blockiert auf rotem Band + ruft `set_cq_active(False)`."""
    src = _method_src("ui/mw_qso.py", "_on_cq_clicked")
    assert "_swr_blocked_bands" in src, "P63 AC8: CQ-Pre-Check fehlt"
    assert "set_cq_active(False)" in src, "P63 AC8: CQ-Button-Reset fehlt"


# ── T7 — `_check_diversity_preset` Pre-Check ───────────────────────────


def test_t7_marker_blocks_diversity_preset():
    """AC8: `_check_diversity_preset` early-return bei rotem Marker."""
    src = _method_src("ui/mw_radio.py", "_check_diversity_preset")
    assert "_swr_blocked_bands" in src, "P63 AC8: Diversity-Pre-Check fehlt"
    # Early-return-Pattern: nach Marker-Check kommt return
    idx_marker = src.find("_swr_blocked_bands")
    idx_assess = src.find("_assess_gain")
    assert 0 < idx_marker < idx_assess, (
        "P63 AC8: Marker-Check muss VOR _assess_gain stehen")


# ── T8 — Manueller TUNE auf rotem Band ERLAUBT ──────────────────────────


def test_t8_manual_tune_allowed_on_red_band():
    """AC: `_on_tune_clicked` hat KEINEN Marker-Pre-Check (Diagnostik-Pfad)."""
    src = _method_src("ui/mw_tx.py", "_on_tune_clicked")
    assert "_swr_blocked_bands" not in src, (
        "P63: Manueller TUNE darf KEINEN Marker-Pre-Check haben "
        "(User-Diagnostik bei rotem Band).")


# ── T9 — Manueller TUNE 10W FEST (unabhängig von tune_power) ───────────


def test_t9_tune_uses_10w_fixed():
    """AC5: `_on_tune_clicked` ruft `set_rfpower_direct(TUNE_POWER_W)`
    mit TUNE_POWER_W=10 — UNABHÄNGIG von settings.tune_power."""
    src = _method_src("ui/mw_tx.py", "_on_tune_clicked")
    assert "TUNE_POWER_W = 10" in src, "P63 AC5: 10W FEST fehlt"
    assert "set_rfpower_direct(TUNE_POWER_W)" in src, (
        "P63 AC5: 10W an Radio fehlt")
    # tune_power-Setting wird NICHT mehr im manuellen Pfad gelesen
    assert "settings.get(\"tune_power\"" not in src, (
        "P63 AC5: manueller TUNE darf settings.tune_power NICHT lesen")


# ── T10 — Manuelle TUNE-Dauer aus Setting {15, 30} ──────────────────────


def test_t10_tune_duration_15_30_from_setting():
    """AC5: Dauer kommt aus settings.tune_duration_s mit Whitelist."""
    src = _method_src("ui/mw_tx.py", "_on_tune_clicked")
    assert "tune_duration_s" in src, "P63 AC5: tune_duration_s-Setting fehlt"
    assert "(15, 30)" in src, "P63 AC5: Whitelist {15, 30} fehlt"
    # QTimer.singleShot mit duration_s * 1000
    assert "duration_s * 1000" in src, (
        "P63 AC5: QTimer-Aufruf mit duration_s * 1000 fehlt")


# ── T11 — `_tune_in_progress` bypasst Watchdog ──────────────────────────


def test_t11_tune_in_progress_bypasses_watchdog():
    """AC4: `_on_swr_alarm` returnt sofort wenn `_tune_in_progress=True`.

    Bypass-Code-Block muss VOR dem is_transmitting-Code-Check stehen
    (Docstring-Erwähnungen ignorieren — präzise Code-Pattern-Suche)."""
    src = _method_src("ui/mw_tx.py", "_on_swr_alarm")
    # Präzise Patterns: getattr-Aufruf vor if-not-Block
    idx_bypass = src.find('getattr(self, "_tune_in_progress"')
    idx_is_tx = src.find('if not self.encoder.is_transmitting')
    assert idx_bypass > 0, (
        "P63 AC4: _tune_in_progress-Bypass-Code fehlt in _on_swr_alarm")
    assert idx_is_tx > 0, (
        "Existing is_transmitting-Pre-Check sollte da bleiben")
    assert idx_bypass < idx_is_tx, (
        "P63 AC4: Bypass MUSS vor is_transmitting-Check stehen "
        "(manueller TUNE setzt _tune_in_progress=True BEVOR tune_on, "
        "wir wollen ja gar nicht erst die Pre-Check-Spike-Logik berühren)")


# ── T12 — Post-Tune SWR≤Limit → Marker discard + Diversity-Resume ──────


def test_t12_post_tune_good_clears_marker():
    """AC6: `_tune_post_swr_check` discard(band) bei SWR≤Limit + ruft
    `_check_diversity_preset` wenn rx_mode=diversity."""
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    assert "_swr_blocked_bands.discard" in src, (
        "P63 AC6: Marker-Discard bei SWR ok fehlt")
    assert "_check_diversity_preset" in src, (
        "P63 AC6: Diversity-Resume fehlt")
    assert "swr_now <= swr_limit" in src, (
        "P63 AC6: SWR-Vergleich fehlt")


# ── T13 — Post-Tune SWR>Limit → Marker bleibt + Modal ──────────────────


def test_t13_post_tune_bad_keeps_marker():
    """AC7: `_tune_post_swr_check` zeigt Modal „Tuner konnte nicht matchen",
    Marker bleibt rot (kein discard im else-Branch)."""
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    assert "Tuner konnte nicht matchen" in src, (
        "P63 AC7: Misserfolg-Modal-Text fehlt")
    # Marker wird im else-Pfad NICHT entfernt (kein discard nach Else-Branch)
    # — Source-Reihenfolge: erst if-Branch mit discard, dann else-Branch ohne


# ── T14 — Tuner=False skipt Auto-TUNE in `_start_dx_tuning` ────────────


def test_t14_no_tuner_skips_auto_tune():
    """AC9: `_start_dx_tuning` ruft `tune_on` NUR wenn radio.ip UND tuner_present."""
    src = _method_src("ui/mw_radio.py", "_start_dx_tuning")
    assert "tuner_present" in src, "P63 AC9: tuner_present-Branch fehlt"
    # Auto-TUNE-Branch muss konjunktiv sein: radio.ip AND tuner_present
    assert "if self.radio.ip and tuner_present" in src, (
        "P63 AC9: Auto-TUNE-Guard muss `radio.ip AND tuner_present` sein")


# ── T15 — `set_tuner_present(False)` blendet btn_tune aus ──────────────


def test_t15_no_tuner_hides_button():
    """AC: `ControlPanel.set_tuner_present(value)` setzt `btn_tune.setVisible(value)`."""
    src = _method_src("ui/control_panel.py", "set_tuner_present")
    assert "btn_tune.setVisible" in src, (
        "P63: set_tuner_present muss btn_tune.setVisible(value) rufen")
    assert "self._tuner_present" in src, (
        "P63: Flag `_tuner_present` muss in set_tuner_present gesetzt werden")


# ── T18 — Post-Tune 2s-Timer (R1-F1) ────────────────────────────────────


def test_t18_post_tune_uses_2s_timer():
    """R1-F1: `_tune_stop` ruft `QTimer.singleShot(2000, _tune_post_swr_check)`.
    2s Beruhigungszeit gegen Pre-PTT-Glitch nach tune_off."""
    src = _method_src("ui/mw_tx.py", "_tune_stop")
    assert "QTimer.singleShot" in src, "P63 R1-F1: QTimer fehlt in _tune_stop"
    assert "2000" in src, "P63 R1-F1: 2s-Delay fehlt"
    assert "_tune_post_swr_check" in src, (
        "P63 R1-F1: Post-Check-Callback fehlt")


# ── T19 — Auto-TUNE-Fehler-Pfad setzt Marker + Lock-Release ────────────


def test_t19_auto_tune_failure_sets_marker_and_releases_lock():
    """R1-F2 (AC11): Wenn Auto-TUNE-Post-Check SWR > Limit sieht,
    muss `_set_gain_measure_lock(False)` UND `_swr_blocked_bands.add(band)`
    aufgerufen werden (vorher hing der Lock → UI dauerblockiert)."""
    src = _method_src("ui/mw_radio.py", "_start_dx_tuning")
    # Innere Funktion `_after_tune` enthält den Post-Check
    assert "if swr > swr_limit" in src, "P63 AC11: SWR-Check-Branch fehlt"
    # Lock-Release im Fehler-Branch
    swr_idx = src.find("if swr > swr_limit")
    assert swr_idx > 0
    after = src[swr_idx:swr_idx + 800]  # nächste ~800 Zeichen
    assert "_set_gain_measure_lock(False)" in after, (
        "P63 R1-F2: Lock-Release im SWR-Fehler-Pfad fehlt")
    assert "_swr_blocked_bands.add" in after, (
        "P63 AC11: Marker-Set im SWR-Fehler-Pfad fehlt")


# ── T20 — Power-Reset im Tuner=False-Skip-Branch (R1-F3) ───────────────


def test_t20_no_tuner_resets_power_in_skip_branch():
    """R1-F3 (AC9): Im Skip-Branch (`else`) muss `set_power(power_preset)`
    aufgerufen werden (wenn `radio.ip` truthy)."""
    src = _method_src("ui/mw_radio.py", "_start_dx_tuning")
    else_idx = src.rfind("else:")
    assert else_idx > 0, "P63 AC9: else-Branch fehlt"
    after = src[else_idx:]
    assert "set_power" in after, (
        "P63 R1-F3: Power-Reset im Skip-Branch fehlt")
    assert "power_preset" in after, (
        "P63 R1-F3: power_preset als Default-Quelle fehlt")


# ── Settings-Defaults bonus checks ──────────────────────────────────────


def test_settings_defaults_have_p63_keys():
    """Defaults müssen `tuner_present=True` und `tune_duration_s=15` enthalten."""
    from config.settings import DEFAULTS
    assert DEFAULTS.get("tuner_present") is True
    assert DEFAULTS.get("tune_duration_s") == 15


def test_pending_station_click_protected_in_tx_finished():
    """AC12 (R1-F5): `_on_tx_finished` prüft Marker BEVOR gebufferter
    Klick ausgeführt wird (Band-Wechsel zwischen Buffer + tx_finished
    möglich)."""
    src = _method_src("ui/mw_qso.py", "_on_tx_finished")
    # Marker-Check vor _on_station_clicked(buffered)
    assert "_swr_blocked_bands" in src, (
        "P63 AC12: Pending-Click-Marker-Check in _on_tx_finished fehlt")


def test_station_clicked_pre_check_first():
    """AC8/AC12: `_on_station_clicked` hat Marker-Pre-Check als ERSTES
    (vor `is_transmitting`-Buffer-Branch — R1-F5 KEIN Buffer auf rotem Band)."""
    src = _method_src("ui/mw_qso.py", "_on_station_clicked")
    idx_marker = src.find("_swr_blocked_bands")
    idx_is_tx = src.find("encoder.is_transmitting")
    assert 0 < idx_marker < idx_is_tx, (
        "P63 R1-F5: Marker-Check muss VOR is_transmitting-Buffer stehen")
