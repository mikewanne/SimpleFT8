# P60 — V2: Self-Review der V1-Spec

## Self-Review Findings

### SR1 — Helper-Location: wo gehört `_abort_active_tx` hin?

V1 sagt `mw_tx.py`. Aber:
- `mw_tx.py` enthält TX-Regelung (rfpower, audio_level, tune)
- `_abort_active_tx` ist eher Stop-Logik
- `mw_qso.py` enthält bereits `_on_cancel` mit dem Pattern (HALT)

**Code-Check:** Welche Mixin-Klasse hat `encoder` und `radio`?
- MainWindow erbt von mehreren Mixins (`MWRadio`, `MWTx`, `MWQso`, `MWCycle`)
- Alle haben Zugriff auf `self.encoder` + `self.radio` (MainWindow-Attribute)
- Helper kann in JEDEM Mixin sein

**Entscheidung:** `mw_tx.py` ist ok — TX-related Stop-Helper. Plus
SWR-Watchdog (`_on_swr_alarm`) ist bereits in `mw_tx.py` und nutzt
ähnliches Pattern. **Bleibt mw_tx.py**.

### SR2 — Sollte HALT-Button den Helper auch nutzen?

V1 sagt AC7: HALT bleibt unverändert. Aber zur Konsistenz könnte
HALT auch den Helper nutzen:

```python
# Vorher (mw_qso.py:_on_cancel:329-333)
if self.encoder.is_transmitting:
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
```
↓
```python
# Nachher
self._abort_active_tx()
```

**Vorteil:** Single source of truth WIRKLICH single.
**Nachteil:** 1 zusätzlicher Pfad zum Testen, 1 zusätzlicher Commit.

**Entscheidung:** Ja, HALT auch refactorn. KISS-Sieg ist größer als
der zusätzliche Commit.

**Update AC7:** HALT-Button ruft `_abort_active_tx()` statt Inline-Block.

### SR3 — Sollte SWR-Watchdog den Helper nutzen?

`_on_swr_alarm` in mw_tx.py:131-134:
```python
self.encoder.abort()
if self.radio.ip:
    self.radio.ptt_off()
```

Sieht identisch aus. Aber: SWR-Watchdog hat KOMPLEXEREN Block davor/danach
(spike_count, add_info VOR Modal, etc.). Wenn wir nur die 4 Zeilen
durch Helper ersetzen, gewinnen wir 0 Zeilen Code aber verlieren
Inline-Lesbarkeit.

**Entscheidung:** SWR-Watchdog bleibt mit Inline-Block (kommentiert
warum: er hat eigenen komplexen Stop-Flow).

### SR4 — Bandwechsel/Mode-Wechsel — gleicher Pattern?

`mw_radio.py:_on_band_changed` und `_on_rx_mode_changed` haben auch
Stop-Blöcke. Schauen wir.

Code-Check:
- Bandwechsel: hat `encoder.abort + ptt_off + stop_cq + cancel + cp.set_cq_active(False)`
- Mode-Wechsel (Bundle I): `stop_cq + cancel + set_cq_active + encoder.abort + ptt_off`

Beide haben mehr als nur abort+ptt_off. Plus sie laufen automatisch
bei Band/Mode-Wechsel — kein User-Toggle.

**Entscheidung:** Bandwechsel/Mode-Wechsel bleiben unverändert. Helper
ist explizit nur für User-Toggle-Stop-Pfade.

### SR5 — Test T7 Formulierung

T7 sagt „SWR-Watchdog nutzt NICHT den Helper". Aber Test muss positiv
formuliert sein: „SWR-Watchdog-Stop-Block bleibt unverändert
(funktioniert weiter)".

**Fix in V3:** T7 als Regression-Test mit Mock — `_on_swr_alarm`
ruft eigenen abort+ptt_off-Block, nicht den Helper.

### SR6 — Edge-Case Order-of-Operations

V1 Option B Sketch:
```python
self._abort_active_tx()
self._omni_cq.stop("manual_halt")
```

Reihenfolge: erst TX abbrechen, dann State. Aber was wenn `_omni_cq.stop()`
nochmal versucht TX zu starten? (sollte nicht, aber prüfen)

**Code-Check:** `core/omni_cq.py:stop()` setzt nur Flags (`_active=False`),
keine TX-Aktion. ✓ sicher.

`core/auto_hunt.py:stop_auto_hunt()` — schauen.

`core/qso_state.py:stop_cq()` — setzt `_cq_mode = False`. Schauen.

**Annahme:** Stop-Methoden in core/ sind reine State-Mutation. Race
ausschließen indem wir verifizieren.

### SR7 — Mehrere Stop-Pfade gleichzeitig

Was wenn User OMNI CQ und Auto-Hunt aktiv hat (geht eigentlich nicht
wegen mutually-exclusive), und einer wird gestoppt? Sollte trivial sein.

Aber: was wenn Mike OMNI-Off klickt während ein PENDING-State noch
in der Queue ist (z.B. Qt-Slot noch nicht abgearbeitet)? — Qt
serialisiert Slots im Main-Thread, also kein Race.

### SR8 — Was rufen wir in welcher Reihenfolge?

Aktuell:
- HALT: abort → ptt_off → stop_cq → cancel → set_cq_active(False) → Auto-Hunt-Freigabe
- SWR-Watchdog: abort → ptt_off → stop_cq/cancel/set_cq_active → omni.stop → hunt.stop → add_info → Modal

Für die 3 neuen Helper-User-Pfade:
- OMNI: abort → ptt_off → _omni_cq.stop
- Hunt: abort → ptt_off → _auto_hunt.stop_auto_hunt
- Normal-CQ: abort → ptt_off → qso_sm.stop_cq

**Reihenfolge:** Abort vor State-Stop. Das macht Sinn:
1. TX-Hardware sofort stoppen (Belastung weg)
2. dann State (User-Reaktion ist UI: Button-Visual)

**Entscheidung:** Diese Reihenfolge bestätigt in V3.

## Aktualisierter Plan (V3-Vorlage)

- **C1:** `mw_tx.py` Helper `_abort_active_tx()` NEU
- **C2:** `main_window.py` OMNI + Auto-Hunt Stop-Pfade nutzen Helper
- **C3:** `mw_qso.py:_on_cq_clicked` Normal-CQ-Stop nutzt Helper
- **C4:** `mw_qso.py:_on_cancel` HALT-Pfad nutzt Helper (SR2-Refactor)
- **C5:** `tests/test_p60_stop_paths.py` NEU T1-T8
- **C6:** APP_VERSION 0.97.31 → 0.97.32 + Doku

## V3-Anpassungen

- AC7 angepasst: HALT ruft `_abort_active_tx()` (statt „unverändert")
- T7 positiv formuliert
- 6 statt 5-6 Commits (HALT-Refactor + Helper)

## Workflow weiter

V3 mit SR2/T7-Anpassung schreiben, dann R1 V4-pro.
