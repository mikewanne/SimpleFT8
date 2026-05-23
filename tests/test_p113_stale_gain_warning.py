"""P113 (23.05.2026, v0.97.98) — Stale-Gain-Warning bei Bandwechsel.

Mike-Spec (DeepSeek-Brainstorm 18.05.) P74-B Phase 1: bei Bandwechsel
dezenter Statusbar-Hinweis wenn `gain_timestamp > 14 Tage` alt.

Mike-Symptom-Pfad: User klickt im 6h-Re-Mess-Dialog wiederholt
„Vorhandene Daten verwenden" → Preset wird Wochen alt → dx_info-Label
zeigt nur „Re-Mess nötig" ohne konkretes Alter. P113 Toast macht das
Alter prominent („17 Tage alt") in der untersten Leiste.

Schwelle strikt > 14 Tage (R1-F2): Toast greift ab Tag 15.
Tests decken Pfad direkt gegen `_check_stale_gain_warning` ab
(unabhaengig von `_on_band_changed`).

Test-Plan:
- T1 15 Tage alt   → Toast mit „15 Tage" + ⚠ + Bandname
- T2 14 Tage exakt → KEIN Toast (Spec strikt >14)
- T3 13 Tage alt   → KEIN Toast
- T4 30 Tage alt   → Toast mit „30 Tage"
- T5 missing       → KEIN Toast (age_min returnt None)
- T6 ts==0.0       → KEIN Toast (Migration-Marker, age_min returnt None)
- T7 frisch 1 Tag  → KEIN Toast
- T8 Statusbar-Mock: showMessage called genau 1x, timeout=15000
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest


# ── Helper ──────────────────────────────────────────────────────────


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Isolierter PresetStore in tmp_path — verhindert dass Tests die
    echte ~/.simpleft8/kalibrierung/presets.json anfassen."""
    from core import preset_store as ps_mod
    monkeypatch.setattr(ps_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ps_mod, "CALIB_DIR", tmp_path / "kalibrierung")
    monkeypatch.setattr(ps_mod, "SETTINGS_PATH", tmp_path / "settings.json")
    return ps_mod.PresetStore("presets.json")


def _set_preset_age_days(store, band: str, days: float) -> None:
    """Hilfsfunktion: speichert Preset und setzt gain_timestamp auf Alter X Tage."""
    store.save_gain(band, rxant="ANT1", ant1_gain=10, ant2_gain=20,
                    ant1_avg=-12.0, ant2_avg=-12.0, ant2_calibrated=True)
    store._data[band]["gain_timestamp"] = time.time() - days * 86400


class _FakeRadioMixin:
    """Minimal-Klasse die nur die Felder + Methode bereitstellt die
    `_check_stale_gain_warning` braucht. Vermeidet vollen MainWindow-Bau."""

    def __init__(self, gain_store):
        self._gain_store = gain_store
        self._sb = MagicMock()

    def statusBar(self):
        return self._sb

    # Methode aus mw_radio.py kopieren NICHT — wir testen die echte.
    # Stattdessen: Import + bind als Method via __get__ Trick.


@pytest.fixture
def fake_mixin(isolated_store):
    """Mixin-Instanz mit echter _check_stale_gain_warning-Methode."""
    from ui.mw_radio import RadioMixin
    inst = _FakeRadioMixin(isolated_store)
    # Echte Methode an Instanz binden — kein neuer Methodencode, nur Bind
    inst._check_stale_gain_warning = (
        RadioMixin._check_stale_gain_warning.__get__(inst, _FakeRadioMixin))
    return inst


# ── Tests ───────────────────────────────────────────────────────────


def test_t1_15_days_old_shows_toast(fake_mixin, isolated_store):
    """15 Tage alt → Toast mit Pattern „⚠ ... 15 Tage alt ... KALIBRIEREN"."""
    _set_preset_age_days(isolated_store, "20m", days=15.5)
    fake_mixin._check_stale_gain_warning("20m")
    assert fake_mixin._sb.showMessage.call_count == 1
    args, _ = fake_mixin._sb.showMessage.call_args
    msg = args[0]
    assert "⚠" in msg
    assert "15 Tage" in msg
    assert "20M" in msg  # band.upper()
    assert "KALIBRIEREN" in msg


def test_t2_14_days_exactly_no_toast(fake_mixin, isolated_store):
    """14.5 Tage → days=14 (// 1440) → KEIN Toast (Spec strikt >14)."""
    _set_preset_age_days(isolated_store, "40m", days=14.5)
    fake_mixin._check_stale_gain_warning("40m")
    fake_mixin._sb.showMessage.assert_not_called()


def test_t3_13_days_no_toast(fake_mixin, isolated_store):
    """13 Tage → KEIN Toast."""
    _set_preset_age_days(isolated_store, "30m", days=13.0)
    fake_mixin._check_stale_gain_warning("30m")
    fake_mixin._sb.showMessage.assert_not_called()


def test_t4_30_days_shows_toast(fake_mixin, isolated_store):
    """30 Tage → Toast „30 Tage"."""
    _set_preset_age_days(isolated_store, "15m", days=30.0)
    fake_mixin._check_stale_gain_warning("15m")
    assert fake_mixin._sb.showMessage.call_count == 1
    msg = fake_mixin._sb.showMessage.call_args[0][0]
    assert "30 Tage" in msg
    assert "15M" in msg


def test_t5_missing_preset_no_toast(fake_mixin):
    """Kein Preset fuer Band → age_min=None → kein Toast."""
    fake_mixin._check_stale_gain_warning("17m")  # nie kalibriert
    fake_mixin._sb.showMessage.assert_not_called()


def test_t6_ts_zero_migration_marker_no_toast(fake_mixin, isolated_store):
    """ts==0.0 (Migration-Marker fuer normal_presets ohne parsbares Datum)
    → age_min=None → kein Toast (Migration-Pfad nicht falsch alarmieren)."""
    isolated_store.save_gain("12m", rxant="ANT1", ant1_gain=10,
                              ant2_gain=20, ant2_calibrated=True)
    isolated_store._data["12m"]["gain_timestamp"] = 0.0
    fake_mixin._check_stale_gain_warning("12m")
    fake_mixin._sb.showMessage.assert_not_called()


def test_t7_fresh_preset_no_toast(fake_mixin, isolated_store):
    """Frisch (1 Tag alt) → KEIN Toast."""
    _set_preset_age_days(isolated_store, "10m", days=1.0)
    fake_mixin._check_stale_gain_warning("10m")
    fake_mixin._sb.showMessage.assert_not_called()


def test_t8_toast_uses_15s_timeout(fake_mixin, isolated_store):
    """Toast zeigt mit timeout=15000ms (15s) — auto-clear nach Ablauf."""
    _set_preset_age_days(isolated_store, "20m", days=20.0)
    fake_mixin._check_stale_gain_warning("20m")
    args, _ = fake_mixin._sb.showMessage.call_args
    assert len(args) == 2
    assert args[1] == 15000


def test_t9_statusbar_exception_swallowed(isolated_store):
    """Statusbar nicht verfuegbar (z.B. Smoke-Test) → keine Exception
    propagiert. Fail-silent fuer Test/Background-Pfade."""
    from ui.mw_radio import RadioMixin
    inst = _FakeRadioMixin(isolated_store)
    inst._sb.showMessage.side_effect = RuntimeError("no statusbar")
    inst._check_stale_gain_warning = (
        RadioMixin._check_stale_gain_warning.__get__(inst, _FakeRadioMixin))
    _set_preset_age_days(isolated_store, "20m", days=20.0)
    # Darf nicht crashen:
    inst._check_stale_gain_warning("20m")  # noqa: assert nicht noetig — kein Crash = OK
