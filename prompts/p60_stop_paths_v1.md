# P60 — V1: User-Stop-Pfade brechen TX-Slot nicht sofort ab

## 1. Trigger

Mike-Field-Test 15.05.2026 morgens, im Anschluss an P55-F6:

> „Okay ich rufe omni cq - wird gestartet - während des sendens drücke
> ich wieder omnicq. button wird rot - senden läuft aber komplett durch
> heißt der 15 sekunden zyklus wird abgearbeitet - danach ist aus.
> Sollte nicht sofort bei erneuten drücken abgebrochen werden. Ich würde
> ja nicht im CQ-Ruf drücken wenn ich nicht wollte das es nicht mehr
> sendet. Es ist ein Toggle-Schalter also an aus. Nicht Slot-Schalter."

Plus Folge-Audit (Mike: „bitte auch bei normal cq ruf überprüfen"):
**dieser Bug existiert in ALLEN DREI User-Toggle-Stop-Pfaden**.

## 2. Wurzel-Analyse (3 Pfade, alle gleicher Bug)

### Pfad 1: OMNI-CQ Stop
`ui/main_window.py:791-792` (`_on_btn_omni_cq_toggled`)
```python
elif not checked and self._omni_cq.is_active():
    self._omni_cq.stop("manual_halt")   # ← nur Flags, kein TX-Stop
```

### Pfad 2: Auto-Hunt Stop
`ui/main_window.py:862-863` (`_on_btn_auto_hunt_toggled`)
```python
elif not checked and self._auto_hunt.active:
    self._auto_hunt.stop_auto_hunt("manual_halt")   # ← nur Flags
```

### Pfad 3: Normal-CQ Stop
`ui/mw_qso.py:311-317` (`_on_cq_clicked` Else-Branch)
```python
else:
    count = self.qso_sm.cq_qso_count
    self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
    self.qso_panel.status_label.setText(f"{count} QSO(s)")
    self.qso_panel.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
    self.qso_sm.stop_cq()    # ← nur State-Wechsel, kein TX-Stop
    self.control_panel.update_qso_counter(0)
```

### Referenz: HALT-Button macht es richtig
`ui/mw_qso.py:329-333` (`_on_cancel`)
```python
if self.encoder.is_transmitting:
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
```

Plus weitere Pfade die es bereits richtig machen:
- **SWR-Watchdog** `_on_swr_alarm` in `mw_tx.py` — abort + ptt_off + Stops
- **Bandwechsel** in `mw_radio.py` — abort + ptt_off + stops
- **Mode-Wechsel** in `mw_radio.py:_on_rx_mode_changed` (P55-Bundle-I) — abort + ptt_off

## 3. Lösungs-Optionen

### Option A — Inline-Erweiterung der 3 Stop-Pfade

In jedem der 3 Pfade vor dem `*.stop()`-Call den TX-Abbruch einfügen:
```python
if self.encoder.is_transmitting:
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
```

**Vorteil:** Minimal-invasiv, lokal.
**Nachteil:** 3× dasselbe Pattern. Drift-Risiko (zukünftige Stop-Pfade
vergessen es wieder).

### Option B — Helper-Methode `_abort_active_tx()`

In einem Mixin (`mw_tx.py`?) zentrale Helper-Methode:

```python
def _abort_active_tx(self) -> None:
    """P60: TX sofort abbrechen wenn aktiv. Antennen-neutral (ANT1 bleibt).

    Used by: User-Stop-Pfade (OMNI/Auto-Hunt/Normal-CQ Toggle), HALT,
    SWR-Watchdog. NICHT used by: Bandwechsel/Mode-Wechsel (haben eigene
    Logik die noch Stops anschließen müssen).
    """
    if self.encoder.is_transmitting:
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()
```

Dann in den 3 Stop-Pfaden:
```python
self._abort_active_tx()
self._omni_cq.stop("manual_halt")   # bzw. _auto_hunt, qso_sm
```

**Vorteil:** Single source of truth. Zukünftige Stop-Pfade nutzen
denselben Helper. Drift verhindert.
**Nachteil:** 1 zusätzliche Methode.

### Option C — Stop-Methoden selbst erweitern

`OmniCQ.stop()`, `AutoHunt.stop_auto_hunt()`, `QSOStateMachine.stop_cq()`
bekommen Reference auf Encoder/Radio und brechen TX selbst ab.

**Vorteil:** Stop-Logik gekapselt.
**Nachteil:** Encoder/Radio gehören NICHT in core/-Module — bisher saubere
UI/Core-Trennung. Würde Architektur verletzen.

## 4. Empfehlung

**Option B (Helper-Methode)** — zukunftssicher gegen Drift, keine
Architektur-Verletzung, KISS-konform.

**Anmerkung:** P53 SWR-Watchdog hat seinen eigenen Stop-Block mit
abort+ptt_off+_omni_cq.stop+_auto_hunt.stop+add_info+Modal — der bleibt
unverändert (komplexerer Pfad, eigenes Pattern).

## 5. Acceptance Criteria

- **AC1:** Klick auf OMNI CQ während aktiver TX-Slot → TX bricht
  innerhalb < 100 ms ab (kein 15-Sekunden-Slot-Ende abgewartet)
- **AC2:** Klick auf AUTO HUNT während aktiver TX-Slot → analog AC1
- **AC3:** Klick auf CQ (Normal) während aktiver TX-Slot → analog AC1
- **AC4:** Helper `_abort_active_tx()` ist no-op wenn `encoder.is_transmitting=False`
- **AC5:** Helper ruft `radio.ptt_off()` nur wenn `self.radio.ip` truthy
- **AC6:** Helper greift NICHT in Antennen-Wahl ein (kein `set_tx_antenna`)
- **AC7:** HALT-Button (`_on_cancel`) bleibt unverändert (er macht
  noch mehr: cancel-active_qso_targets, set_active_call(""), Auto-Hunt-
  Freigabe etc.) — er ruft den Helper aber NICHT, weil sein bestehender
  Code-Block schon richtig ist (Konsistenz-Verbesserung optional)
- **AC8:** SWR-Watchdog `_on_swr_alarm` bleibt unverändert

## 6. Test-Plan

- **T1:** `_abort_active_tx` ruft `encoder.abort()` + `radio.ptt_off()` wenn `encoder.is_transmitting=True` + `radio.ip="1.2.3.4"`
- **T2:** `_abort_active_tx` ist no-op wenn `encoder.is_transmitting=False`
- **T3:** `_abort_active_tx` ruft KEIN `ptt_off` wenn `radio.ip=None`
- **T4:** OMNI-Toggle-Off während TX → `_abort_active_tx` gerufen + `_omni_cq.stop("manual_halt")` gerufen
- **T5:** Auto-Hunt-Toggle-Off während TX → analog T4 mit `_auto_hunt.stop_auto_hunt`
- **T6:** Normal-CQ-Toggle-Off während TX → `_abort_active_tx` gerufen + `qso_sm.stop_cq` gerufen
- **T7:** SWR-Watchdog-Stop unverändert — `_on_swr_alarm` nutzt eigenen Block, NICHT den Helper (Regression)
- **T8:** Hardware-Pflicht-Test: kein `set_tx_antenna` im `_abort_active_tx`-Source (ANT1-Pflicht)

## 7. Files

- `ui/mw_tx.py` — neue Methode `_abort_active_tx()` (Helper-Mixin)
- `ui/main_window.py:791-792` OMNI-Stop um Helper-Aufruf erweitert
- `ui/main_window.py:862-863` Auto-Hunt-Stop analog
- `ui/mw_qso.py:311-317` Normal-CQ-Stop analog
- `tests/test_p60_stop_paths.py` NEU mit T1-T8

## 8. Mike Field-Test (nach Code)

| F# | Was prüfen |
|---|---|
| F1 | OMNI CQ starten, während TX-Slot läuft (5s nach Start) erneut klicken → TX bricht SOFORT ab (kein Slot-Ende abgewartet) |
| F2 | Auto-Hunt starten, während Hunt-TX läuft Stop → SOFORT ab |
| F3 | Normal CQ starten, während CQ-TX läuft Stop → SOFORT ab |
| F4 | HALT funktioniert weiter wie immer (alle Modi gestoppt) |
| F5 | SWR-Watchdog: künstlich auslösen, alle Stops greifen + Modal (Regression P53) |
| F6 | Bandwechsel/Mode-Wechsel während TX: TX bricht ab (Regression Bundle I) |

## 9. Workflow-Schritte

1. **V1** (dieses Dokument)
2. **V2 Self-Review** — Findings: Helper-Location (mw_tx vs. mw_qso vs.
   eigenes Modul?), Test-Vollständigkeit, Bugs in V1?
3. **R1 V4-pro** — Architektur-Review, Klärungs-Q, Hardware-Pflicht-Check
4. **V3** — finale Spec
5. **Code** — 5-6 atomare Commits
6. **Final-R1** — Push-Freigabe
