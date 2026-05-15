# P60 — V3.1: Finale Spec (R1-V4-pro-F1 ROT eingearbeitet)

## R1-Findings

| ID | Klasse | Status |
|---|---|---|
| F1 | ROT — `_pending_station_click` nicht gecleart in Stop-Pfaden | **angenommen** |
| F2 | ORANGE — Race tx_finished sync vs. async | **entkräftet** (Worker-Thread → QueuedConnection, kein Race) |
| F3 | GELB — SWR-Watchdog auch _pending_station_click clearen | **angenommen** (Konsistenz) |

## F1-Hintergrund (V4-pro-Catch)

`_pending_station_click` in `mw_qso.py:162` wird gesetzt wenn User
auf Station klickt während TX läuft (Click-Puffer). `_on_tx_finished`
(Z.410-412) führt den gepufferten Klick nach TX-Ende aus.

**Bug-Szenario:** User klickt Station während OMNI-TX → Puffer voll →
User klickt OMNI-Off Toggle → V1-Plan ruft nur `_abort_active_tx +
_omni_cq.stop`, **NICHT** `_pending_station_click = None`. Wenn
`tx_finished` feuert (Worker-Thread, QueuedConnection), läuft
`_on_tx_finished` → gepufferter Klick startet neues QSO!

HALT (`_on_cancel:327`) macht es richtig: `_pending_station_click = None`.

## F2 entkräftet

`encoder.abort()` setzt `_is_transmitting=False` + `_abort_event.set()`.
Es feuert KEIN `tx_finished` direkt. Das macht der TX-Worker im Thread
nach Aufwachen aus Sleep. Worker → Main-Thread = `QueuedConnection` →
Slot-Handler läuft NACH dem aktuellen Slot. **Kein synchroner Race.**

## Code-Änderungen (aktualisiert)

## Code-Änderungen

### C1 — `ui/mw_tx.py` Helper `_abort_active_tx()` NEU (R1-F1 erweitert)

```python
def _abort_active_tx(self) -> None:
    """P60: TX sofort abbrechen wenn aktiv + gepufferten Click verwerfen.

    Used by: User-Stop-Toggle (OMNI/Auto-Hunt/Normal-CQ) + HALT.
    NICHT used by: SWR-Watchdog (eigener Spike-Schutz-Flow — F3 GELB
    separat) — Bandwechsel/Mode-Wechsel (eigene Cleanup-Sequenzen).

    Antennen-neutral (kein set_tx_antenna — ANT1 bleibt).
    No-op wenn encoder.is_transmitting=False (idempotent).
    ptt_off nur wenn radio.ip truthy (kein Crash bei disconnect).

    R1-V4-pro-F1: setzt _pending_station_click = None damit kein
    gepufferter Klick aus dem Puffer ein QSO nach Stop startet
    (HALT macht das schon in _on_cancel, neue Pfade brauchten es auch).
    """
    if self.encoder.is_transmitting:
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()
    # F1 ROT: gepufferten Station-Klick verwerfen (verhindert post-stop QSO)
    if hasattr(self, "_pending_station_click"):
        self._pending_station_click = None
```

### C2 — `ui/main_window.py:791-792` OMNI-Stop

**VORHER:**
```python
elif not checked and self._omni_cq.is_active():
    self._omni_cq.stop("manual_halt")
```

**NACHHER:**
```python
elif not checked and self._omni_cq.is_active():
    self._abort_active_tx()
    self._omni_cq.stop("manual_halt")
```

### C2 — `ui/main_window.py:862-863` Auto-Hunt-Stop

**VORHER:**
```python
elif not checked and self._auto_hunt.active:
    self._auto_hunt.stop_auto_hunt("manual_halt")
```

**NACHHER:**
```python
elif not checked and self._auto_hunt.active:
    self._abort_active_tx()
    self._auto_hunt.stop_auto_hunt("manual_halt")
```

### C3 — `ui/mw_qso.py:311-317` Normal-CQ-Stop

**VORHER:**
```python
else:
    count = self.qso_sm.cq_qso_count
    self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
    self.qso_panel.status_label.setText(f"{count} QSO(s)")
    self.qso_panel.status_label.setStyleSheet(...)
    self.qso_sm.stop_cq()
    self.control_panel.update_qso_counter(0)
```

**NACHHER:**
```python
else:
    count = self.qso_sm.cq_qso_count
    self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
    self.qso_panel.status_label.setText(f"{count} QSO(s)")
    self.qso_panel.status_label.setStyleSheet(...)
    self._abort_active_tx()
    self.qso_sm.stop_cq()
    self.control_panel.update_qso_counter(0)
```

### C4 — `ui/mw_qso.py:_on_cancel` HALT-Pfad

**VORHER (Z.329-333):**
```python
# TX sofort stoppen
if self.encoder.is_transmitting:
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
```

**NACHHER:**
```python
# TX sofort stoppen (P60: zentraler Helper)
self._abort_active_tx()
```

### C5 — `tests/test_p60_stop_paths.py` NEU mit 10 Tests

- T1: `_abort_active_tx` ruft `encoder.abort()` + `radio.ptt_off()` wenn beide Bedingungen erfüllt
- T2: No-op wenn `encoder.is_transmitting=False` (TX-Pfad)
- T3: Kein `ptt_off` wenn `radio.ip=None`
- T4: OMNI-Toggle-Off → Source-Check `_abort_active_tx` vor `_omni_cq.stop` in main_window.py
- T5: Auto-Hunt-Toggle-Off → Source-Check `_abort_active_tx` vor `_auto_hunt.stop_auto_hunt`
- T6: Normal-CQ-Toggle-Off → Source-Check `_abort_active_tx` in mw_qso.py
- T7: SWR-Watchdog-Block unverändert (eigener Inline-Code, NICHT Helper)
- T8: Hardware-Pflicht — `_abort_active_tx` enthält kein `set_tx_antenna`
- **T9 (R1-F1):** `_abort_active_tx` setzt `_pending_station_click = None`
- **T10 (R1-F1):** Helper-Call ohne `_pending_station_click`-Attribut crasht nicht (defensive hasattr)

### C6 — `main.py` APP_VERSION 0.97.31 → 0.97.32 + Doku

## Acceptance Criteria

- **AC1:** OMNI Toggle-Off während TX → TX < 100 ms
- **AC2:** Auto-Hunt Toggle-Off während TX → TX < 100 ms
- **AC3:** Normal-CQ Toggle-Off während TX → TX < 100 ms
- **AC4:** Helper idempotent (no-op bei nicht-TX)
- **AC5:** Helper `ptt_off`-Skip bei `radio.ip=None`
- **AC6:** Helper antennen-neutral (kein `set_tx_antenna`)
- **AC7:** HALT-Button nutzt Helper (Konsistenz)
- **AC8:** SWR-Watchdog unverändert (eigener Spike-Schutz-Block)

## Mike Field-Test

| F# | Was prüfen |
|---|---|
| F1 | OMNI starten, während TX-Slot läuft (3-5s nach Start) erneut klicken → TX bricht SOFORT ab (Audio-Ende hörbar/RF-Meter geht runter) |
| F2 | Auto-Hunt analog |
| F3 | Normal-CQ analog |
| F4 | HALT funktioniert weiter — drückt während TX → alle Modi gestoppt |
| F5 | SWR-Watchdog künstlich auslösen → Modal kommt, Stop greift |
| F6 | Bandwechsel während TX → TX bricht ab (Regression Bundle I) |
