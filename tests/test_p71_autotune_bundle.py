"""P71 (v0.97.47) — Auto-Tune Bundle nach Mike-Field-Test 18.05.2026.

5 Bugs:
- Bug 1: Backup-Timer-Race (Grace 5 → 12 s).
- Bug 2: App-Start triggert Auto-Tune (Guard-Flag + RFPreset-Anker-Check).
- Bug 3: Settings tune_duration_s 15/30 → 5/10/15.
- Bug 4: AutoTuneDialog-UX (Title band.lower() + mode, Status mit FWDPWR).
- Bug 5: DONE OK/FAIL-Logging fuer alle 4 Pfade.

12 Tests:
- T1: Backup-Timer-Wert = (duration_s + 12) * 1000 ms.
- T2: Title-Label band.lower() + mode.
- T3: Status-Label-Format mit Mode + FWDPWR-Token.
- T4: Settings-Migration tune_duration_s=30 → 15 nach load.
- T5: ComboBox findData-Fallback bei unbekanntem Wert.
- T6: ComboBox-Items {5, 10, 15}.
- T7: _initial_band_set initialisiert + nach Init geclearted.
- T8: App-Start triggert KEIN Auto-Tune (Flag-Pfad).
- T9: User-Bandwechsel triggert Auto-Tune wenn alle Bedingungen erfuellt.
- T10: Auto-Tune skippt wenn RFPresetStore.has_anchor() True.
- T11: Cancel-Pfad setzt _tune_convergence_cancelled=True + Log.
- T12: Logging-Format [P54a] DONE OK/FAIL fuer 4 Pfade.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── T1 — Backup-Timer-Wert (Bug 1) ────────────────────────────────────


def test_t1_backup_timer_grace_12s():
    """Source-Level: Backup-Timer berechnet sich aus duration_s + _BACKUP_GRACE_S.

    _BACKUP_GRACE_S muss 12 sein (Phase B 6.5 + Post-Check 2 + Safety 3.5).
    """
    src = Path("ui/auto_tune_dialog.py").read_text()
    assert "_BACKUP_GRACE_S = 12" in src, \
        "Konstante _BACKUP_GRACE_S = 12 fehlt"
    assert "(duration_s + _BACKUP_GRACE_S) * 1000" in src, \
        "Backup-Timer benutzt nicht die Konstante"
    # Alter +5-Wert ist raus
    assert "(duration_s + 5) * 1000" not in src, \
        "Alter Backup-Wert +5 ist noch da"


# ── T2 — Title-Label band.lower() + mode (Bug 4) ──────────────────────


def test_t2_title_label_lowercase_with_mode():
    """Title-Label nutzt band.lower() + mode, nicht band.upper()."""
    src = Path("ui/auto_tune_dialog.py").read_text()
    # F-String-Body — Zeilenumbruch-toleranter Check
    assert "{band.lower()} {mode}" in src, \
        "Title-Format band.lower() + mode fehlt"
    assert "🔧 Auto-TUNE läuft" in src, \
        "Title-Praefix fehlt"
    # Alter Title-Code (NICHT Kommentare/Docstrings) ist raus.
    # Suche speziell nach dem alten f-string-Pattern in einer Code-Zeile.
    assert "{band.upper()}" not in src, \
        "Alter f-string {band.upper()} ist noch da (Code)"


# ── T3 — Status-Label-Format mit Mode + FWDPWR (Bug 4 + V2-F5) ────────


def test_t3_status_label_mode_and_fwdpwr():
    """_on_tick liest _fwdpwr_samples[-1] + Mode + FWDPWR im Status."""
    src = Path("ui/auto_tune_dialog.py").read_text()
    assert "self._mode" in src, "self._mode fehlt"
    assert "_fwdpwr_samples[-1]" in src, "FWDPWR-Sample-Lesen fehlt"
    assert "FWDPWR" in src, "Status-Token FWDPWR fehlt"


# ── T4 — Settings-Migration tune_duration_s 30 → 15 (Bug 3 + F3-D) ────


def test_t4_settings_migration_30_to_15(tmp_path, monkeypatch):
    """Settings.load() poppt/migriert alten Wert 30 → 15."""
    cfg_dir = tmp_path / "simpleft8"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({"tune_duration_s": 30, "callsign": "TEST"}))

    monkeypatch.setattr("config.settings.CONFIG_FILE", cfg_file)

    # Frische Settings-Instanz
    from importlib import reload
    import config.settings as settings_mod
    reload(settings_mod)
    monkeypatch.setattr(settings_mod, "CONFIG_FILE", cfg_file)
    settings = settings_mod.Settings()

    assert settings.get("tune_duration_s") == 15, \
        f"Migration 30 → 15 fehlgeschlagen: got {settings.get('tune_duration_s')}"


def test_t4b_settings_migration_unknown_value(tmp_path, monkeypatch):
    """Settings.load() migriert beliebigen unbekannten Wert → 15."""
    cfg_dir = tmp_path / "simpleft8"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({"tune_duration_s": 7}))

    from importlib import reload
    import config.settings as settings_mod
    reload(settings_mod)
    monkeypatch.setattr(settings_mod, "CONFIG_FILE", cfg_file)
    settings = settings_mod.Settings()

    assert settings.get("tune_duration_s") == 15


# ── T5 — ComboBox findData-Fallback (V2-F4) ──────────────────────────


def test_t5_combobox_finddata_fallback():
    """Settings-Dialog _load_settings nutzt findData mit Fallback auf 15."""
    src = Path("ui/settings_dialog.py").read_text()
    # Pruefe Fallback-Pattern (Idx<0 → findData(15))
    assert "tune_duration_combo.findData" in src, \
        "ComboBox.findData() Aufruf fehlt"
    assert "findData(15)" in src, \
        "Fallback findData(15) fehlt"


# ── T6 — ComboBox-Items (Bug 3) ───────────────────────────────────────


def test_t6_combobox_items_5_10_15():
    """ComboBox hat Items 5, 10, 15 s — nicht mehr 15, 30."""
    src = Path("ui/settings_dialog.py").read_text()
    assert 'addItem("5 s", 5)' in src
    assert 'addItem("10 s", 10)' in src
    assert 'addItem("15 s", 15)' in src
    # Alter 30 s ist raus
    assert 'addItem("30 s", 30)' not in src, \
        "Alter 30-s-Item ist noch da"


# ── T7 — _initial_band_set Init + Clear (Bug 2 / F2-A) ────────────────


def test_t7_initial_band_set_lifecycle():
    """Source-Level: _initial_band_set wird in __init__ True und am Ende False."""
    src = Path("ui/main_window.py").read_text()
    assert "self._initial_band_set = True" in src, \
        "Initial-Set des Guard-Flags auf True fehlt"
    assert "self._initial_band_set = False" in src, \
        "Clear des Guard-Flags auf False fehlt"
    # Sicherstellen dass True VOR False kommt
    true_pos = src.find("self._initial_band_set = True")
    false_pos = src.find("self._initial_band_set = False")
    assert true_pos < false_pos, \
        "Guard-Flag wird VOR False gesetzt, nicht danach"


# ── T8 — App-Start triggert KEIN Auto-Tune (Bug 2) ────────────────────


def test_t8_initial_band_set_blocks_auto_tune():
    """Source-Level: _on_band_changed pruefen ob _initial_band_set Auto-Tune blockt."""
    src = Path("ui/mw_radio.py").read_text()
    # Auto-Tune-Block hat getattr-Check
    assert 'getattr(self, "_initial_band_set", False)' in src, \
        "Guard-Check fuer _initial_band_set fehlt"
    # Skip-Branch wenn Flag True
    assert "not getattr(self, \"_initial_band_set\", False)" in src, \
        "Skip-Logik nicht initial_band_set falsch"


# ── T9 — User-Bandwechsel triggert Auto-Tune (Regression-Schutz) ─────


def test_t9_user_band_change_triggers_auto_tune_logic():
    """Source-Level: alle bisherigen Bedingungen bleiben aktiv neben neuen Guards."""
    src = Path("ui/mw_radio.py").read_text()
    # Bestehende Bedingungen
    assert 'self.settings.get("auto_tune_on_band_change", True)' in src
    assert "self.radio.ip" in src
    assert "self._swr_blocked_bands" in src
    assert 'self.settings.get("tuner_present", True)' in src
    # Neue Bedingungen
    assert "_has_anchor" in src
    assert "_initial_band_set" in src
    # Helper _start_auto_tune_for_band_change wird im if-Branch gerufen
    assert "_start_auto_tune_for_band_change(band)" in src


# ── T10 — Auto-Tune skippt wenn has_anchor (Belt-and-suspenders) ─────


def test_t10_has_anchor_skips_auto_tune(tmp_path):
    """RFPresetStore.has_anchor() liefert True wenn Eintrag existiert."""
    from core.rf_preset_store import RFPresetStore

    store = RFPresetStore(path=tmp_path / "rf_presets.json")
    # Vorher: kein Anker
    assert store.has_anchor("flexradio", "20m", watt=10) is False
    # Nach Save: Anker da
    store.save("flexradio", "20m", watt=10, rf=12)
    assert store.has_anchor("flexradio", "20m", watt=10) is True
    # Anderer Band: kein Anker
    assert store.has_anchor("flexradio", "40m", watt=10) is False
    # Anderes Watt: kein Anker
    assert store.has_anchor("flexradio", "20m", watt=20) is False


# ── T11 — Cancel-Pfad: _tune_convergence_cancelled + Log ─────────────


def test_t11_cancel_sets_flag():
    """_on_cancel_clicked setzt _tune_convergence_cancelled = True.

    DONE FAIL cancelled-Log wird Source-Level in test_t12d geprueft —
    capsys/capfd faengt PySide6-Prints in offscreen-Modus nicht
    zuverlaessig. KISS-Trennung.
    """
    from ui.auto_tune_dialog import AutoTuneDialog
    from PySide6.QtWidgets import QApplication, QWidget
    import sys

    if QApplication.instance() is None:
        _app = QApplication(sys.argv)

    parent = QWidget()
    parent.radio = MagicMock()
    parent.radio.last_swr = 1.5
    parent._fwdpwr_samples = []
    parent._tune_convergence_cancelled = False
    parent._tune_in_progress = True
    parent._tune_stop = MagicMock()

    dlg = AutoTuneDialog(parent, band="20m", duration_s=15, mode="FT8")
    dlg._on_cancel_clicked()

    # Cancel-Flag muss True sein (greift in _tune_converge_to_target)
    assert parent._tune_convergence_cancelled is True
    # _tune_stop wird mit None gerufen (User-Cancel-Pfad)
    parent._tune_stop.assert_called_once_with(None)
    parent.deleteLater()


def test_t11b_cancel_log_format_source():
    """Source-Level: _on_cancel_clicked enthaelt DONE FAIL cancelled-Log."""
    src = Path("ui/auto_tune_dialog.py").read_text()
    # Block ab _on_cancel_clicked bis naechste def
    idx_start = src.find("def _on_cancel_clicked")
    idx_end = src.find("def _on_backup_timeout")
    assert idx_start > 0 and idx_end > idx_start
    block = src[idx_start:idx_end]
    assert "[P54a] DONE FAIL reason=cancelled" in block, \
        "Cancel-Pfad enthaelt nicht DONE FAIL cancelled-Log"
    assert "band={self._band}" in block, "band-Token fehlt"
    assert "mode={self._mode}" in block, "mode-Token fehlt"


# ── T12 — Logging-Format DONE OK/FAIL (Bug 5 + F5) ───────────────────


def test_t12_done_ok_log_format():
    """Source-Level: _tune_post_swr_check enthaelt DONE OK-Log mit allen Keys."""
    src = Path("ui/mw_tx.py").read_text()
    # OK-Log key=value-Format
    assert "[P54a] DONE OK band=" in src
    assert "mode=" in src
    assert "ant=ANT1" in src
    assert "swr=" in src
    assert "fwdpwr=" in src
    assert "rf=" in src
    assert "duration=" in src


def test_t12b_done_fail_swr_bad_log():
    """SWR-bad Log mit reason=swr_bad."""
    src = Path("ui/mw_tx.py").read_text()
    assert "[P54a] DONE FAIL reason=swr_bad" in src
    assert "limit=" in src


def test_t12c_done_fail_disconnect_log():
    """Radio-disconnect Log mit reason=disconnect."""
    src = Path("ui/mw_tx.py").read_text()
    assert "[P54a] DONE FAIL reason=disconnect" in src


def test_t12d_done_fail_timeout_log():
    """Backup-Timeout Log mit reason=timeout."""
    src = Path("ui/auto_tune_dialog.py").read_text()
    assert "[P54a] DONE FAIL reason=timeout" in src
    assert "after=" in src


# ── T13 — Manuelle TUNE-Whitelist konsistent (Final-R1-Catch) ─────────


def test_t13_manual_tune_whitelist_5_10_15():
    """`_on_tune_clicked` whitelist (5, 10, 15) — vorher (15, 30).

    Final-R1 fand: ohne Fix wuerde User-Wahl 5/10 im manuellen TUNE-Pfad
    silently auf 15 gemappt, obwohl Settings/ComboBox 5/10 anbieten.
    """
    src = Path("ui/mw_tx.py").read_text()
    # Block ab _on_tune_clicked bis _tune_stop
    idx_start = src.find("def _on_tune_clicked")
    idx_end = src.find("def _tune_stop")
    assert idx_start > 0 and idx_end > idx_start
    block = src[idx_start:idx_end]
    assert "duration_s not in (5, 10, 15)" in block, \
        "Manuelle TUNE-Whitelist nicht auf (5, 10, 15) umgestellt"
    # Code-Zeile mit "duration_s not in (15, 30)" darf nicht mehr existieren
    # (Doc-Kommentar zur Historie darf bleiben).
    assert "duration_s not in (15, 30)" not in block, \
        "Alte Whitelist-Code (15, 30) noch im manuellen TUNE-Pfad"
