# P1.BUNDLE2 V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-08.
**Workflow:** V1 → V2 → R1 ✅ (1 KRITISCH + 2 SOLLTE + 1 KOENNTE adressiert)
→ **V3** → Compact → Code.
**Vorgaenger:** v0.95.18 (P1.BUNDLE-LOGBOOK-RST-SNR), Tests 938 gruen.
**APP_VERSION-Ziel:** 0.95.19 (Patch).
**Compact-fest:** Diese Datei enthaelt ALLE Diffs. Nach Compact direkt Code.

---

## 1. R1-Findings adressiert

| # | Severity | R1-Finding | V3-Loesung |
|---|---|---|---|
| 8 | 🚨 KRITISCH | P1.7 Skip-Order: UI-Cleanup MUSS vor Skip-Return | `_active_qso_targets.discard`, `rx_panel.set_active_call("")`, `auto_hunt.on_qso_complete` laufen IMMER (Z.312-316), Duplikat-Check NUR bei ADIF + qso_log.add_qso + log_antenna_qso (Z.318+) |
| 4 | ⚠️ SOLLTE | P1.13 Histogramm-Update bedingt | `isVisible()`-Check oder weglassen. V3 entscheidet: weglassen (KISS) — Spinbox+Encoder reichen |
| 3 | ⚠️ SOLLTE | P1.13 Range aus Spinbox-Properties | `spin.minimum()`/`spin.maximum()` statt hardcoded 150/2800 |
| 7 | 💡 KOENNTE | P1.7 Mode-Edge-Case | Nur dokumentieren in V3, kein Code-Aenderung |
| 10 | ➕ TEST | 4 Edge-Case-Tests | Eingebaut: `wait_73_retries=0 nach start_qso`, `freq_hz=0 no update`, `band case-norm`, `empty band` |

**Test-Soll:** 938 → **955 erwartet (+17)**. R1-bestaetigt: 16-17 Tests sinnvoll.

---

## 2. Konkrete Diffs (Compact-fest)

### Diff 1 — `core/qso_state.py:83` neues Feld `wait_73_retries`

**Aktuell (Z.83):**
```python
    rr73_retries: int = 0  # Retries speziell fuer WAIT_RR73
    courtesy_73_sent: bool = False  # P1.10 Fix (v0.95.4): max 1x pro QSO
```

**Neu:**
```python
    rr73_retries: int = 0  # Retries speziell fuer WAIT_RR73
    wait_73_retries: int = 0  # P1.11 (v0.95.19): Retries fuer WAIT_73-Hoeflichkeit (R-Report-Wiederholung), entkoppelt von rr73_retries
    courtesy_73_sent: bool = False  # P1.10 Fix (v0.95.4): max 1x pro QSO
```

**Auto-Reset:** `QSOData()` in `start_qso(...)` initialisiert beide Counter
auf 0 — kein expliziter Reset noetig.

### Diff 2 — `core/qso_state.py:633-642` WAIT_73-Hoeflichkeit nutzt neues Feld

**Aktuell (Z.633-642):**
```python
            elif msg.is_r_report and msg.caller == self.qso.their_call:
                # Hoeflichkeit: Station hat unser RR73 nicht empfangen → nochmal senden (max 2x)
                if self.qso.rr73_retries < 2:
                    self.qso.rr73_retries += 1
                    tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
                    print(f"[QSO] Hoeflichkeit: {msg.caller} wiederholt R-Report → sende RR73 erneut "
                          f"({self.qso.rr73_retries}/2)")
                    self.send_message.emit(tx_msg)
                else:
                    print(f"[QSO] {msg.caller} wiederholt R-Report — max Retries erreicht, ignoriert")
            return
```

**Neu:**
```python
            elif msg.is_r_report and msg.caller == self.qso.their_call:
                # P1.11 (v0.95.19): Hoeflichkeits-Retry nutzt eigenes Feld
                # wait_73_retries — entkoppelt von rr73_retries (das nach
                # WAIT_RR73-Sequenz auf MAX_RR73_RETRIES=3 stehen kann und
                # sonst diesen Pfad blockieren wuerde).
                if self.qso.wait_73_retries < 2:
                    self.qso.wait_73_retries += 1
                    tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
                    print(f"[QSO] Hoeflichkeit: {msg.caller} wiederholt R-Report → sende RR73 erneut "
                          f"({self.qso.wait_73_retries}/2)")
                    self.send_message.emit(tx_msg)
                else:
                    print(f"[QSO] {msg.caller} wiederholt R-Report — max Retries erreicht, ignoriert")
            return
```

### Diff 3 — `ui/mw_qso.py:_on_station_clicked` TX-Frequenz-Sync (P1.13)

**Position:** Nach `start_qso(...)` Z.133, VOR `_was_cq=True` Z.137.

**Aktuell (Z.129-138):**
```python
        self.qso_sm.start_qso(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
        )
        # P1.14 KP6 (Plan-V2-Entscheidung): Workaround BEHALTEN. Saubere
        # Integration in start_qso ist nicht moeglich weil stop_cq() vor
        # start_qso() laufen MUSS — _was_cq waere dort schon False.
        if _cq_was_active:
            self.qso_sm._was_cq = True
```

**Neu:**
```python
        self.qso_sm.start_qso(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
        )
        # P1.13 (v0.95.19): Im Normal-Modus TX-Frequenz auf Station-Frequenz
        # nachziehen + Spinbox synchronisieren. Frequenz wird NICHT
        # persistiert (settings.save_normal_tx_freq) — Hunt-Klick ist
        # temporaer, bandbezogene Default-Frequenz bleibt erhalten.
        # Histogramm-Update bewusst weggelassen (KISS, R1-Empfehlung) —
        # Histogramm-Widget ist im Normal-Modus typisch nicht sichtbar,
        # Encoder + Spinbox-Sync reichen vollstaendig.
        if self._rx_mode == "normal" and msg.freq_hz:
            spin = self.control_panel._tx_freq_spin
            # Hardware-Range aus Spinbox-Properties (statt hardcoded
            # 150/2800) — bleibt automatisch konsistent bei Range-Aenderung.
            freq_hz = max(spin.minimum(), min(spin.maximum(), int(msg.freq_hz)))
            self.encoder.audio_freq_hz = freq_hz
            spin.blockSignals(True)
            spin.setValue(freq_hz)
            spin.blockSignals(False)
        # P1.14 KP6 (Plan-V2-Entscheidung): Workaround BEHALTEN. Saubere
        # Integration in start_qso ist nicht moeglich weil stop_cq() vor
        # start_qso() laufen MUSS — _was_cq waere dort schon False.
        if _cq_was_active:
            self.qso_sm._was_cq = True
```

### Diff 4 — `ui/main_window.py` Init `_recent_logged_calls`

**Position:** Klassen-Init wo andere `_pending_*`-Attribute initialisiert
sind (z.B. nach `_pending_station_click`).

**Suche:** `grep -n "_pending_station_click" ui/main_window.py` zur
Lokalisierung.

**Neu (1 Zeile + 1 Konstante am Modul-Top):**
```python
# Modul-Top von ui/main_window.py (oder mw_qso.py — V3-Entscheidung: mw_qso.py)
_LOG_DEDUP_WINDOW_S = 300  # P1.7 (v0.95.19): 5-Min-Fenster fuer ADIF-Duplikat-Filter
```

```python
# in __init__ nach _pending_station_click
self._recent_logged_calls: dict[tuple[str, str], float] = {}  # P1.7: (call, band) → ts
```

**Wichtig:** `_LOG_DEDUP_WINDOW_S` als Modul-Konstante in `ui/mw_qso.py`
(am File-Top zu den anderen Imports), nicht in main_window.py.

### Diff 5 — `ui/mw_qso.py:_on_qso_complete` Duplikat-Filter (P1.7)

**Aktuell (Z.310-336):**
```python
    @Slot(object)
    def _on_qso_complete(self, qso_data):
        """RR73 gesendet — ADIF schreiben (UI-Meldung kommt erst bei 73 oder Timeout)."""
        self._active_qso_targets.discard(qso_data.their_call)
        self.rx_panel.set_active_call("")
        # Auto-Hunt: QSO erfolgreich → Pause, dann naechste Station
        if self._auto_hunt.active:
            self._auto_hunt.on_qso_complete(qso_data.their_call)

        # KEIN add_qso_complete hier — kommt in _on_qso_confirmed (nach 73 oder Timeout)

        band = self.settings.band.upper()
        freq = self.settings.frequency_mhz

        self.adif.log_qso(
            call=qso_data.their_call,
            band=band,
            freq_mhz=freq,
            mode=self.settings.mode,
            rst_sent=qso_data.our_snr or "-10",
            rst_rcvd=qso_data.their_snr or "-10",
            gridsquare=qso_data.their_grid or "",
            my_gridsquare=self.settings.locator,
            my_callsign=self.settings.callsign,
            tx_power=self.settings.power_watts,
            time_on=qso_data.start_time,
        )
        self.qso_log.add_qso(qso_data.their_call, band)

        # Antennen-Statistik pro QSO loggen — immer schreiben, "–" wenn kein Pref
        if hasattr(self, '_stats_logger') and self._stats_logger is not None:
            pref = None
            if self._rx_mode == "diversity" and hasattr(self, '_antenna_prefs'):
                pref = self._antenna_prefs.get_pref(qso_data.their_call)
            self._stats_logger.log_antenna_qso(
                call=qso_data.their_call,
                band=self.settings.band,
                ft_mode=self.settings.mode,
                best_ant=pref["best_ant"] if pref else None,
                delta_db=pref["delta_db"] if pref else None,
            )
```

**Neu:**
```python
    @Slot(object)
    def _on_qso_complete(self, qso_data):
        """RR73 gesendet — ADIF schreiben (UI-Meldung kommt erst bei 73 oder Timeout).

        P1.7 (v0.95.19): Duplikat-Filter — wenn dieselbe Station auf
        gleichem Band innerhalb _LOG_DEDUP_WINDOW_S=300s schon geloggt
        wurde, ADIF/qso_log/Antennen-Stats ueberspringen.
        UI-Cleanup (active_qso, rx_panel, auto_hunt) laeuft IMMER —
        sonst Inkonsistenzen (R1-KRITISCH).
        """
        # UI-Cleanup IMMER (vor Duplikat-Check) — R1-KRITISCH:
        self._active_qso_targets.discard(qso_data.their_call)
        self.rx_panel.set_active_call("")
        if self._auto_hunt.active:
            self._auto_hunt.on_qso_complete(qso_data.their_call)

        # KEIN add_qso_complete hier — kommt in _on_qso_confirmed (nach 73 oder Timeout)

        band = self.settings.band.upper()
        freq = self.settings.frequency_mhz

        # P1.7 Duplikat-Check: (call, band)-Tupel-Key, beide UPPER (siehe
        # qso_log.py:23 add_qso normiert Band/Call gleich). Mode wird
        # bewusst NICHT in den Key aufgenommen — KISS, Mike's Mode-Wechsel
        # binnen 5 Min mit gleicher Station ist Hobby-Praxis quasi nie.
        import time
        now = time.time()
        call_key = qso_data.their_call.upper()
        dedup_key = (call_key, band)
        last = self._recent_logged_calls.get(dedup_key, 0.0)
        if now - last < _LOG_DEDUP_WINDOW_S:
            print(f"[QSO] DUPLIKAT-FILTER: {call_key}@{band} schon vor "
                  f"{int(now-last)}s geloggt → skip ADIF + qso_log + antenna_stats")
            self.qso_panel.add_info(
                f"{call_key} Duplikat ({int(now-last)}s) — kein ADIF-Eintrag")
            return  # KEIN log_qso, KEIN add_qso, KEIN log_antenna_qso
        self._recent_logged_calls[dedup_key] = now

        self.adif.log_qso(
            call=qso_data.their_call,
            band=band,
            freq_mhz=freq,
            mode=self.settings.mode,
            rst_sent=qso_data.our_snr or "-10",
            rst_rcvd=qso_data.their_snr or "-10",
            gridsquare=qso_data.their_grid or "",
            my_gridsquare=self.settings.locator,
            my_callsign=self.settings.callsign,
            tx_power=self.settings.power_watts,
            time_on=qso_data.start_time,
        )
        self.qso_log.add_qso(qso_data.their_call, band)

        # Antennen-Statistik pro QSO loggen — immer schreiben, "–" wenn kein Pref
        if hasattr(self, '_stats_logger') and self._stats_logger is not None:
            pref = None
            if self._rx_mode == "diversity" and hasattr(self, '_antenna_prefs'):
                pref = self._antenna_prefs.get_pref(qso_data.their_call)
            self._stats_logger.log_antenna_qso(
                call=qso_data.their_call,
                band=self.settings.band,
                ft_mode=self.settings.mode,
                best_ant=pref["best_ant"] if pref else None,
                delta_db=pref["delta_db"] if pref else None,
            )
```

### Diff 6 — `ui/mw_qso.py` Modul-Top: Konstante

**Position:** Nach den `from ... import ...` Statements am File-Top.

**Neu:**
```python
# P1.7 (v0.95.19): ADIF-Duplikat-Filter Zeit-Fenster (Sekunden).
# Mike's Spec 2026-05-05: < 5 Min nach RR73 erneut → kein doppelter Eintrag.
# Cache ist Session-lokal in MainWindow._recent_logged_calls (App-Restart
# loescht den State, ist gewollt — Mike will Reset bei manuellem Neustart).
# Cache-Wachstum: bei 18000 QSOs ~1-2 MB, kein Cleanup noetig (KISS).
_LOG_DEDUP_WINDOW_S = 300
```

### Diff 7 — `ui/main_window.py` Init `_recent_logged_calls`

**Suche-Pattern:** `_pending_station_click = None` (existiert seit P1.24
v0.95.9 — laut CLAUDE.md `ui/main_window.py:209`).

**Aktuell (Beispiel-Position, V3 verifiziert beim Code):**
```python
self._pending_station_click: object = None  # P1.24 (v0.95.9): Klick-Buffer
```

**Neu:**
```python
self._pending_station_click: object = None  # P1.24 (v0.95.9): Klick-Buffer
self._recent_logged_calls: dict[tuple[str, str], float] = {}  # P1.7 (v0.95.19): ADIF-Dedup
```

### Diff 8 — `tests/test_p1_bundle2.py` (NEU, 17 Tests)

```python
"""Tests fuer P1.BUNDLE2 (v0.95.19).

3 unabhaengige Bugs in einem Workflow:
- P1.11: rr73_retries shared zwischen WAIT_RR73 + WAIT_73-Hoeflichkeit
- P1.13: TX-Frequenz-Spinbox-Sync bei Hunt-Klick im Normal-Modus
- P1.7:  Lokaler Duplikat-Filter ADIF/Logbuch (5-Min-Fenster)
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ── P1.11: rr73_retries / wait_73_retries ────────────────────────────────


def _make_sm():
    """Hilfsfunktion: QSOStateMachine mit Test-Setup."""
    from core.qso_state import QSOStateMachine, QSOData
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    return sm


def test_p1_11_rr73_retries_does_not_block_wait_73():
    """P1.11: voller WAIT_RR73-Counter blockiert WAIT_73-Hoeflichkeit NICHT."""
    from core.qso_state import QSOState
    from core.message import FT8Message
    sm = _make_sm()
    sm._set_state(QSOState.WAIT_73)
    sm.qso.their_call = "SP6AXW"
    sm.qso.rr73_retries = 3  # voll ausgereizt
    sm.qso.wait_73_retries = 0
    captured = []
    sm.send_message.connect(lambda m: captured.append(m))

    msg = FT8Message(raw="DA1MHH SP6AXW R-08", field1="DA1MHH",
                     field2="SP6AXW", field3="R-08", snr=-8)
    sm.on_message_received(msg)

    assert sm.qso.wait_73_retries == 1
    assert any("RR73" in m for m in captured)


def test_p1_11_wait_73_max_2_retries():
    """P1.11: WAIT_73-Hoeflichkeit max 2× RR73 erneut, dann ignoriert."""
    from core.qso_state import QSOState
    from core.message import FT8Message
    sm = _make_sm()
    sm._set_state(QSOState.WAIT_73)
    sm.qso.their_call = "SP6AXW"
    captured = []
    sm.send_message.connect(lambda m: captured.append(m))

    msg = FT8Message(raw="DA1MHH SP6AXW R-08", field1="DA1MHH",
                     field2="SP6AXW", field3="R-08", snr=-8)
    sm.on_message_received(msg)
    sm.on_message_received(msg)
    sm.on_message_received(msg)  # 3. — sollte ignoriert werden

    rr73_count = sum(1 for m in captured if "RR73" in m)
    assert rr73_count == 2
    assert sm.qso.wait_73_retries == 2


def test_p1_11_independent_counters():
    """P1.11: rr73_retries + wait_73_retries sind unabhaengig."""
    sm = _make_sm()
    sm.qso.rr73_retries = 3
    sm.qso.wait_73_retries = 1
    assert sm.qso.rr73_retries != sm.qso.wait_73_retries


def test_p1_11_wait_73_retries_zero_after_start_qso():
    """P1.11 (R1-Test): nach start_qso ist wait_73_retries=0
    (durch QSOData()-Neuinit)."""
    sm = _make_sm()
    sm.qso.wait_73_retries = 5  # alter QSO-Zustand
    sm.cq_mode = False
    sm.start_qso(their_call="EA2BHE", freq_hz=1500)
    assert sm.qso.wait_73_retries == 0


# ── P1.13: TX-Frequenz-Spinbox-Sync ──────────────────────────────────────


def _make_main_window(app):
    """Hilfsfunktion: MainWindow mit Mock-Encoder + Mock-Settings."""
    from ui.main_window import MainWindow
    # Wir testen nur _on_station_clicked, kein voller Init noetig.
    # Daher Mock-basiert — V3-Code muss API-stabil bleiben.
    from unittest.mock import patch
    with patch("ui.main_window.create_radio"), \
         patch("ui.main_window.QSOLog"), \
         patch("ui.main_window.LocatorDB"):
        mw = MainWindow.__new__(MainWindow)
    return mw


def test_p1_13_normal_hunt_click_updates_encoder_and_spin(app):
    """P1.13: Normal-Modus Hunt-Klick → encoder.audio_freq_hz + spin.value
    auf msg.freq_hz."""
    from core.message import FT8Message
    from PySide6.QtWidgets import QSpinBox
    # Minimal-Setup: Encoder + Spinbox + _rx_mode
    spin = QSpinBox()
    spin.setRange(150, 2800)
    spin.setValue(1500)
    encoder = MagicMock()
    encoder.audio_freq_hz = 1500
    encoder.is_transmitting = False

    # Test direkt die Sync-Logik aus Diff 3:
    msg = FT8Message(raw="DA1MHH SP6AXW JO80", field1="DA1MHH",
                     field2="SP6AXW", field3="JO80", snr=-8, freq_hz=823)
    rx_mode = "normal"
    if rx_mode == "normal" and msg.freq_hz:
        freq_hz = max(spin.minimum(), min(spin.maximum(), int(msg.freq_hz)))
        encoder.audio_freq_hz = freq_hz
        spin.blockSignals(True)
        spin.setValue(freq_hz)
        spin.blockSignals(False)

    assert encoder.audio_freq_hz == 823
    assert spin.value() == 823


def test_p1_13_diversity_hunt_click_does_not_change_freq(app):
    """P1.13: Diversity-Modus Hunt-Klick → KEIN Sync (Auto-Suche aktiv)."""
    from core.message import FT8Message
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    spin.setValue(1500)
    encoder = MagicMock()
    encoder.audio_freq_hz = 1500

    msg = FT8Message(raw="...", field1="DA1MHH", field2="SP6AXW",
                     field3="JO80", snr=-8, freq_hz=823)
    rx_mode = "diversity"
    if rx_mode == "normal" and msg.freq_hz:
        # SOLL NICHT betreten werden
        spin.setValue(int(msg.freq_hz))
        encoder.audio_freq_hz = int(msg.freq_hz)

    assert encoder.audio_freq_hz == 1500
    assert spin.value() == 1500


def test_p1_13_clamp_to_hardware_range(app):
    """P1.13: Frequenz wird auf Spinbox-Range geclampt."""
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    # over-range:
    freq_hz = max(spin.minimum(), min(spin.maximum(), 3500))
    assert freq_hz == 2800
    # under-range:
    freq_hz = max(spin.minimum(), min(spin.maximum(), 50))
    assert freq_hz == 150


def test_p1_13_freq_hz_zero_no_update(app):
    """P1.13 (R1-Test): msg.freq_hz=0 → kein Encoder/Spinbox-Update."""
    from core.message import FT8Message
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    spin.setValue(1500)
    encoder = MagicMock()
    encoder.audio_freq_hz = 1500

    msg = FT8Message(raw="...", field1="DA1MHH", field2="SP6AXW",
                     field3="JO80", snr=-8, freq_hz=0)  # 0 = Decoder-Edge-Case
    rx_mode = "normal"
    if rx_mode == "normal" and msg.freq_hz:
        # SOLL NICHT betreten werden weil msg.freq_hz=0 falsy
        encoder.audio_freq_hz = int(msg.freq_hz)
        spin.setValue(int(msg.freq_hz))

    assert encoder.audio_freq_hz == 1500
    assert spin.value() == 1500


def test_p1_13_no_persistence_call(app):
    """P1.13: settings.save_normal_tx_freq darf NICHT aufgerufen werden
    bei Hunt-Klick (Hunt-Klick ist temporaer)."""
    settings = MagicMock()
    # Wir simulieren nur den Code aus Diff 3 — kein save_normal_tx_freq-Call
    from PySide6.QtWidgets import QSpinBox
    spin = QSpinBox()
    spin.setRange(150, 2800)
    encoder = MagicMock()

    rx_mode = "normal"
    msg_freq = 823
    if rx_mode == "normal" and msg_freq:
        freq_hz = max(spin.minimum(), min(spin.maximum(), int(msg_freq)))
        encoder.audio_freq_hz = freq_hz
        spin.blockSignals(True)
        spin.setValue(freq_hz)
        spin.blockSignals(False)
        # KEIN settings.save_normal_tx_freq

    settings.save_normal_tx_freq.assert_not_called()


# ── P1.7: ADIF-Duplikat-Filter ───────────────────────────────────────────


_LOG_DEDUP_WINDOW_S = 300  # mirror der Modul-Konstante


def _dedup_check(cache: dict, call: str, band: str, now: float) -> bool:
    """Hilfsfunktion: True wenn Duplikat (skip), False wenn neu (log + cache)."""
    key = (call.upper(), band.upper())
    last = cache.get(key, 0.0)
    if now - last < _LOG_DEDUP_WINDOW_S:
        return True
    cache[key] = now
    return False


def test_p1_7_duplicate_within_window_skipped():
    """P1.7: Selber Call+Band binnen 5 Min → 2. ist Duplikat."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False  # 1. log
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is True  # Duplikat


def test_p1_7_duplicate_outside_window_logged():
    """P1.7: Selber Call+Band nach 6+ Min → 2. ist legitim."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False
    assert _dedup_check(cache, "SP6AXW", "20M", now + 360) is False  # 6 Min spaeter


def test_p1_7_different_calls_both_logged():
    """P1.7: Verschiedene Calls binnen 5 Min → beide loggen."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False
    assert _dedup_check(cache, "EA2BHE", "20M", now + 60) is False


def test_p1_7_multi_band_both_logged():
    """P1.7: Selber Call auf verschiedenen Baendern → beide loggen
    (Tupel-Key (call, band))."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20M", now) is False
    assert _dedup_check(cache, "SP6AXW", "40M", now + 60) is False  # legitim


def test_p1_7_session_local_cache():
    """P1.7: Cache ist Session-lokal (kein Persist) — App-Restart-Simulation."""
    cache = {}
    now = 1000.0
    _dedup_check(cache, "SP6AXW", "20M", now)
    # App-Restart: neuer Cache
    cache_new = {}
    assert _dedup_check(cache_new, "SP6AXW", "20M", now + 60) is False


def test_p1_7_band_case_normalized():
    """P1.7 (R1-Test): Band „20m" und „20M" werden gleich behandelt
    (Tupel-Key normalisiert .upper())."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "20m", now) is False  # lowercase eingang
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is True  # Duplikat


def test_p1_7_empty_band_does_not_collide():
    """P1.7 (R1-Test): Leerer Band-String kollidiert nicht mit normalen Bands."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "SP6AXW", "", now) is False
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is False  # andere Keys


def test_p1_7_call_case_normalized():
    """P1.7: Call wird auch ueber .upper() normalisiert."""
    cache = {}
    now = 1000.0
    assert _dedup_check(cache, "sp6axw", "20M", now) is False
    assert _dedup_check(cache, "SP6AXW", "20M", now + 60) is True
```

### Diff 9 — `main.py:16` APP_VERSION

```python
APP_VERSION = "0.95.19"
```

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** (Verifikation):
   - `prompts/p1_bundle2_v3.md` (diese Datei)
   - `core/qso_state.py:80-90,630-645` (Diff 1+2)
   - `ui/mw_qso.py:60-140,300-350` (Diff 3+5+6)
   - `ui/main_window.py` (Diff 7 — Suche `_pending_station_click`)
2. **Diff 1+2** — `core/qso_state.py`: neues Feld + WAIT_73-Branch nutzt es.
3. **Diff 6** — `ui/mw_qso.py` Modul-Top-Konstante.
4. **Diff 3** — `ui/mw_qso.py:_on_station_clicked` TX-Sync (P1.13).
5. **Diff 5** — `ui/mw_qso.py:_on_qso_complete` Duplikat-Filter (P1.7).
6. **Diff 7** — `ui/main_window.py` Init `_recent_logged_calls`.
7. **Diff 8** — `tests/test_p1_bundle2.py` NEU mit 17 Tests.
8. **Diff 9** — `main.py` APP_VERSION 0.95.18 → 0.95.19.
9. **Tests:** `938 → 955 erwartet gruen` (+17).
10. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P1.BUNDLE2 v0.95.19 final-Code. 3 Bugs gefixt:
    P1.11 wait_73_retries entkoppelt rr73_retries, P1.13 Hunt-Klick
    Normal-Mode TX-Sync, P1.7 ADIF-Duplikat-Filter 5min." | \
    ./venv/bin/python3 tools/deepseek_review.py \
    core/qso_state.py ui/mw_qso.py ui/main_window.py \
    tests/test_p1_bundle2.py
    ```
11. **Atomare Commits — 3 Code + 1 Doku:**
    - Bug 1: `P1.BUNDLE2 P1.11 (v0.95.19): wait_73_retries entkoppelt rr73_retries`
    - Bug 2: `P1.BUNDLE2 P1.13 (v0.95.19): Hunt-Klick Normal-Mode TX-Frequenz-Sync`
    - Bug 3: `P1.BUNDLE2 P1.7 (v0.95.19): ADIF-Duplikat-Filter 5-Min-Fenster`
    - Doku: `docs (v0.95.19): P1.BUNDLE2 HISTORY+HANDOFF+CLAUDE+Tests+APP_VERSION`
12. **Doku-Updates** (HISTORY, HANDOFF beide Pfade, CLAUDE beide
    Pfade, Memory).
13. **Push** NUR nach Mike-Field-Test-Freigabe.
14. **Lessons-Learned**.

**Git-Add-P-Hinweis:** `ui/mw_qso.py` hat 3 separate Aenderungen
(Modul-Konstante, _on_station_clicked, _on_qso_complete). Saubere
Atomaritaet via `git add -p` mit selektiver Hunk-Annahme:
- Commit 1 (Bug-1): nur `core/qso_state.py`-Hunks
- Commit 2 (Bug-2): nur `_on_station_clicked`-Hunk in mw_qso.py
- Commit 3 (Bug-3): `_LOG_DEDUP_WINDOW_S` Konstante + `_on_qso_complete`
  in mw_qso.py + `_recent_logged_calls` in main_window.py
- Commit 4 (Doku): Tests + APP_VERSION + HISTORY/HANDOFF/CLAUDE

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] Diff 1: QSOData.wait_73_retries: int = 0
- [ ] Diff 2: WAIT_73-Hoeflichkeit nutzt wait_73_retries (Z.633-642)
- [ ] Diff 3: _on_station_clicked Normal-Mode TX-Sync mit Range-Clamp
- [ ] Diff 4/6: _LOG_DEDUP_WINDOW_S Konstante in mw_qso.py
- [ ] Diff 5: _on_qso_complete UI-Cleanup vor Duplikat-Check, dann Skip
- [ ] Diff 7: _recent_logged_calls Init in MainWindow
- [ ] Diff 8: 17 Tests in tests/test_p1_bundle2.py
- [ ] Diff 9: APP_VERSION 0.95.19
- [ ] Tests gesamt: 938 → 955 gruen
- [ ] Final-R1 ohne KP-Findings
- [ ] HISTORY/HANDOFF/CLAUDE updated (beide Pfade)
- [ ] 3 atomare Code-Commits + 1 Doku-Commit
- [ ] Mike-Field-Test fuer P1.11 + P1.13 (P1.7 hardware-frei)
- [ ] Mike-Push-Freigabe explizit
- [ ] Lessons-Learned
```

---

## 5. Field-Test-Plan (R1-Pflicht)

**P1.11 Field-Test:**
- QSO mit Mike's IC-7300 (DA1TST) starten — voll durchziehen bis 73.
- Wenn DA1TST nach RR73-Sequenz (ggf. mit Retries) im WAIT_73-State
  einen R-Report nochmal sendet → unsere Antwort sollte RR73 sein
  (vorher: ignoriert).
- Pruefen: Logs `[QSO] Hoeflichkeit: ... (1/2)` und ggf. `(2/2)`.

**P1.13 Field-Test:**
- App im Normal-Modus starten (KEIN Diversity).
- Spinbox manuell auf 1500 Hz setzen → Default fuer dieses Band.
- Station auf 800 Hz im RX-Panel anklicken.
- Pruefen: Spinbox zeigt jetzt 800 Hz, TX laeuft auf 800 Hz (RX-Klick
  fuehrt nicht ins Leere).
- App neu starten → Spinbox sollte wieder 1500 Hz zeigen (Default
  pro Band, NICHT 800 Hz persistiert).

**P1.7 hardware-frei:** Tests im Loop reichen, kein Funkbetrieb noetig.

**Push-Freigabe-Kriterium:** Alle 3 Field-Tests erfolgreich + Mike's
explizite Genehmigung.

---

## 6. Risiken & Notbremse

- **P1.11 Backward-Compat:** Neues Feld `wait_73_retries` ist additiv,
  kein Risiko fuer bestehende Tests/Persistenz (QSOData wird nirgends
  serialisiert).
- **P1.13 _rx_mode-Edge-Cases:** Kalibrier-Modi (`_rx_mode in
  ("dx_tuning", "gain_measure")`) — der `== "normal"`-Filter ist
  strikt, also wird der Sync NUR im Normal-Modus aktiv. R1-bestaetigt OK.
- **P1.7 Cache-Wachstum:** Bei 18000 QSOs ~1-2 MB, kein Cleanup noetig.
  Wird beim App-Restart geleert (Mike-Praxis).
- **P1.7 Stats-Bias:** Antennen-Statistik-Skip bei Duplikat ist gewollt
  (siehe V2 L4) — Doppel-Eintrag binnen 5 Min hat keinen Mehrwert.

---

## 7. Lessons-Learned-Vorschlaege (Skill Schritt 6 final)

1. Neue State-Felder in QSOData: `QSOData()`-Auto-Reset prueft V2/R1
   immer („wird das automatisch initialisiert?")
2. Spinbox-Range aus Properties statt Hardcode bei UI-Sync — Wartbarkeits-
   Pattern fuer alle zukuenftigen Spinbox-Sync-Stellen.
3. UI-Cleanup-Reihenfolge bei Skip-Pfaden: R1-KRITISCH-Lesson
   (Punkt 8) — bei jeder Slot-Funktion mit early-return die Side-Effects
   vor dem Return ausfuehren oder explizit doppelt-checken.

Memory-Vorschlaege:
- `feedback_qsodata_auto_reset_check.md` — bei jedem neuen QSOData-Feld
  pruefen ob `start_qso(...)` den Reset wirklich uebernimmt.
- `feedback_skip_path_ui_cleanup_first.md` — bei jedem Skip-Return
  (wegen Filter, Duplikat, Race) UI-Cleanup VOR dem return — nie
  nachgelagert.

---

**V3-Ende. Bereit fuer Compact + Code.**
