"""DT-Kalibrier-Knopf (v0.99.0).

Die automatische DT-Lernschleife wurde durch eine MANUELLE Einmal-Kalibrierung
ersetzt (Mike-Entscheidung 03.06.2026): ``record_samples`` puffert nur das
gleitende FT8-Fenster, ``calibrate()`` korrigiert auf Knopfdruck inkrementell.

Warum manuell statt fester Wert / statt Auto-Lernen: Mikes Ferienhaus-iMac hat
eine defekte Pufferbatterie → die System-Uhr driftet je nach Standzeit (mal vor,
mal nach). Ein fester Wert veraltet; das Auto-Lernen war fragil (pendelte/sprang
ins Minus → OMNI-CQ-Takt verdoppelte sich). Der Knopf ist stabil (Wert aendert
sich nur auf Druck) UND nachjustierbar (negativer Wert legitim — kein Riegel).

_DT_FILE-Schutz kommt aus conftest.py (Mikes echte Datei wird nie beruehrt).
"""
from __future__ import annotations

import collections
import json

import pytest


@pytest.fixture
def nt(monkeypatch):
    """Frischer DT-Modul-State."""
    import core.ntp_time as _nt
    monkeypatch.setattr(_nt, "_correction", 0.0)
    monkeypatch.setattr(_nt, "_hardware_default_offset", 0.0)
    monkeypatch.setattr(_nt, "_mode", "FT8")
    monkeypatch.setattr(_nt, "_band", "20m")
    monkeypatch.setattr(_nt, "_is_initial", True)
    monkeypatch.setattr(_nt, "_recent_samples",
                        collections.deque(maxlen=_nt.RECENT_SLOTS))
    monkeypatch.setattr(_nt, "_last_median_dt", 0.0)
    monkeypatch.setattr(_nt, "_last_sample_count", 0)
    yield _nt


# ── record_samples: nur puffern, nicht lernen ────────────────────────────


def test_record_buffers_only_ft8(nt):
    """FT8-Slots fuellen den Kalibrier-Puffer, FT4/FT2 nicht."""
    nt._mode = "FT8"
    nt.record_samples([0.1] * 5)
    assert len(nt._recent_samples) == 1
    nt._mode = "FT4"
    nt.record_samples([0.1] * 5)
    assert len(nt._recent_samples) == 1   # unveraendert
    nt._mode = "FT2"
    nt.record_samples([0.1] * 5)
    assert len(nt._recent_samples) == 1


def test_record_does_not_change_correction(nt):
    """record_samples aendert _correction NIE (kein Auto-Lernen mehr)."""
    nt._correction = 0.26
    nt._mode = "FT8"
    for _ in range(10):
        nt.record_samples([0.9] * 12)
    assert nt._correction == 0.26


def test_record_updates_display_all_modes(nt):
    """Anzeige-Werte (_last_*) werden fuer ALLE Modi gesetzt (informativ)."""
    nt._mode = "FT4"
    nt.record_samples([0.2, 0.2, 0.2, 0.2])
    assert nt._last_sample_count == 4
    assert nt._last_median_dt == pytest.approx(0.2)


def test_record_filters_out_of_range(nt):
    """Werte ausserhalb −2..2 werden verworfen."""
    nt._mode = "FT8"
    nt.record_samples([0.1, 0.1, 0.1, 5.0, -9.0])
    flat = [dt for slot in nt._recent_samples for dt in slot]
    assert flat == [0.1, 0.1, 0.1]


def test_rolling_window_drops_oldest(nt):
    """Nur die letzten RECENT_SLOTS Slots bleiben (deque(maxlen)). Alle Werte
    in −2..2 (sonst filtert record_samples sie weg und es wird nichts gepuffert)."""
    nt._mode = "FT8"
    nt.record_samples([-1.5] * 3)               # Sentinel = aeltester Slot
    for _ in range(nt.RECENT_SLOTS):            # RECENT_SLOTS frische Slots
        nt.record_samples([0.1] * 3)
    assert len(nt._recent_samples) == nt.RECENT_SLOTS
    flat = [dt for slot in nt._recent_samples for dt in slot]
    assert -1.5 not in flat                      # Sentinel rausgefallen


# ── calibrate: Mindestanzahl, inkrementell, voller Schritt ───────────────


def test_calibrate_too_few_returns_false(nt):
    """< MIN_STATIONS → (False, …), Korrektur unveraendert."""
    nt._correction = 0.26
    nt._mode = "FT8"
    nt.record_samples([0.3] * (nt.MIN_STATIONS - 1))
    ok, msg = nt.calibrate()
    assert ok is False
    assert nt._correction == 0.26
    assert "wenige" in msg.lower()


def test_calibrate_incremental(nt):
    """calibrate addiert den Median der Residuen (voller Schritt, keine Daempfung)."""
    nt._correction = 0.30
    nt._mode = "FT8"
    nt.record_samples([0.10] * 8)
    ok, msg = nt.calibrate()
    assert ok is True
    assert nt._correction == pytest.approx(0.40, abs=0.01)


def test_calibrate_one_click_converges(nt):
    """Ueberkorrektur: corr=0.26, Bedarf 0 → Residuen ~−0.26 → 1 Klick auf ~0."""
    nt._correction = 0.26
    nt._mode = "FT8"
    nt.record_samples([-0.26] * 8)
    ok, msg = nt.calibrate()
    assert ok is True
    assert nt._correction == pytest.approx(0.0, abs=0.01)


def test_calibrate_sets_is_initial_false(nt):
    """Nach erfolgreicher Kalibrierung ist _is_initial False."""
    nt._mode = "FT8"
    nt._is_initial = True
    nt.record_samples([0.2] * 8)
    nt.calibrate()
    assert nt._is_initial is False


def test_calibrate_persists(nt):
    """calibrate schreibt das Single-Value-Format sofort."""
    nt._correction = 0.0
    nt._mode = "FT8"
    nt.record_samples([0.25] * 8)
    nt.calibrate()
    data = json.loads(nt._DT_FILE.read_text())
    assert data["dt_correction_s"] == pytest.approx(0.25, abs=0.01)


def test_calibrate_message_shows_value_and_count(nt):
    """Erfolgsmeldung nennt den resultierenden Wert + Stationszahl."""
    nt._correction = 0.0
    nt._mode = "FT8"
    nt.record_samples([0.26] * 9)
    ok, msg = nt.calibrate()
    assert ok is True
    assert "kalibriert" in msg.lower()
    assert "9" in msg


def test_calibrate_clears_buffer_on_success(nt):
    """Field-Bug 03.06.2026: erfolgreiche Kalibrierung leert den Puffer — sonst
    addiert ein zweiter Druck (vor frischen Slots) denselben Median nochmal."""
    nt._correction = 0.0
    nt._mode = "FT8"
    nt.record_samples([0.12] * 8)
    ok1, _ = nt.calibrate()
    assert ok1 is True
    assert len(nt._recent_samples) == 0            # Puffer geleert
    first = nt._correction
    # Sofortiger zweiter Druck → Puffer leer → (False), Korrektur UNVERÄNDERT
    ok2, _ = nt.calibrate()
    assert ok2 is False
    assert nt._correction == first                 # KEINE Doppel-Addition


def test_calibrate_failed_keeps_buffer(nt):
    """Fehlgeschlagene Kalibrierung (zu wenige) verwirft die gesammelten Samples
    NICHT — Mike kann nach kurzem Warten erfolgreich nachkalibrieren."""
    nt._correction = 0.0
    nt._mode = "FT8"
    nt.record_samples([0.2] * 3)                   # < MIN_STATIONS
    ok, _ = nt.calibrate()
    assert ok is False
    assert len(nt._recent_samples) == 1            # Slot bleibt erhalten
    nt.record_samples([0.2] * 3)                   # jetzt 6 ≥ MIN_STATIONS
    ok2, _ = nt.calibrate()
    assert ok2 is True


# ── Negativ erlaubt (kein Riegel), Clamp ±1.0 ────────────────────────────


def test_calibrate_allows_negative(nt):
    """Voreilende Uhr → negativer Wert ist LEGITIM (kein Negativ-Riegel)."""
    nt._correction = 0.0
    nt._mode = "FT8"
    nt.record_samples([-0.4] * 8)
    ok, msg = nt.calibrate()
    assert ok is True
    assert nt._correction == pytest.approx(-0.4, abs=0.01)
    assert nt._correction < 0


def test_calibrate_clamps_symmetric(nt):
    """Sanity-Clamp ±MAX_CORRECTION (positiv UND negativ)."""
    nt._mode = "FT8"
    nt._correction = 0.5
    nt.record_samples([1.9] * 8)        # weit jenseits +1.0
    nt.calibrate()
    assert nt._correction <= nt.MAX_CORRECTION

    nt._correction = -0.5
    nt._recent_samples.clear()
    nt.record_samples([-1.9] * 8)       # weit jenseits −1.0
    nt.calibrate()
    assert nt._correction >= -nt.MAX_CORRECTION


def test_calibrate_mad_removes_outliers(nt):
    """MAD-Filter entfernt einen groben Ausreisser vor dem Median."""
    nt._correction = 0.0
    nt._mode = "FT8"
    # 8 Werte um 0.2 + 1 grober Ausreisser −2.0
    nt.record_samples([0.2, 0.2, 0.21, 0.19, 0.2, 0.2, 0.18, 0.22, -2.0])
    ok, msg = nt.calibrate()
    assert ok is True
    # Ohne Ausreisser-Filter wuerde der Median nach unten gezogen — hier ~0.2
    assert nt._correction == pytest.approx(0.20, abs=0.03)


# ── Modus-/Band-Wechsel leert den Puffer ─────────────────────────────────


def test_set_mode_clears_buffer(nt):
    nt._mode = "FT8"
    nt.record_samples([0.1] * 6)
    nt.set_mode("FT4")
    assert len(nt._recent_samples) == 0


def test_set_band_clears_buffer(nt):
    nt._mode = "FT8"
    nt.record_samples([0.1] * 6)
    nt.set_band("40m")
    assert len(nt._recent_samples) == 0


# ── get_time vs get_correction (Modus-Versatz NUR in Anzeige/RX) ─────────


def test_get_time_uses_base_not_delta(nt):
    """Slot-Takt nutzt die reine FT8-Basis (kein _MODE_DELTA) — sonst
    Sende-Takt-Verdopplung (v0.98.63)."""
    import time
    nt._correction = 0.30
    nt._mode = "FT4"   # Delta −0.30
    t = nt.get_time()
    # get_time = time.time() + 0.30 (NICHT + (0.30−0.30)=0.0)
    assert (t - time.time()) == pytest.approx(0.30, abs=0.05)


def test_get_correction_applies_mode_delta(nt):
    """RX-/Anzeige-Korrektur = Basis + _MODE_DELTA[mode]."""
    nt._correction = 0.30
    nt._mode = "FT8"
    assert nt.get_correction() == pytest.approx(0.30)
    nt._mode = "FT4"
    assert nt.get_correction() == pytest.approx(0.0, abs=0.001)   # 0.30 − 0.30
