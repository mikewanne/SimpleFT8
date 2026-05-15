# P60 Final-R1 — Push-Freigabe

Du bist Senior-Reviewer. P60 (User-Stop-Pfade Slot-Abbruch + Click-
Puffer-Clearing) ist implementiert. R1-V4-pro-F1 ROT eingearbeitet.

## Was geändert wurde

### `ui/mw_tx.py` Helper `_abort_active_tx()` NEU

```python
def _abort_active_tx(self) -> None:
    """P60 (v0.97.32): TX sofort abbrechen + gepufferten Click verwerfen."""
    if self.encoder.is_transmitting:
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()
    if hasattr(self, "_pending_station_click"):
        self._pending_station_click = None
```

### `ui/main_window.py` 2 Toggle-Stop-Pfade erweitert

OMNI-Stop (~Z.793) + Auto-Hunt-Stop (~Z.864):
```python
elif not checked and self._omni_cq.is_active():
    self._abort_active_tx()           # NEU
    self._omni_cq.stop("manual_halt")
```

### `ui/mw_qso.py` Normal-CQ-Stop + HALT-Refactor

`_on_cq_clicked` Else-Branch + `_on_cancel` HALT — beide nutzen
jetzt `_abort_active_tx()` statt Inline-Block.

### `tests/test_p60_stop_paths.py` NEU 11 Tests

T1-T3 Behavior (abort/ptt_off/no-op), T4-T6 Source-Level (Helper-Call
vor State-Stop), T7 SWR-Watchdog unverändert (Regression), T8 Hardware-
Pflicht (kein set_tx_antenna), T9-T10 (R1-F1) Click-Puffer-Cleanup +
defensive hasattr-Check, plus halt_uses_helper-Konsistenz-Test.

### `tests/test_omni_cq_integration.py` Mock erweitert

`_FakeMW` bekommt `_abort_active_tx`-Stub damit Integration-Tests
gegen den neuen Pfad laufen.

### `main.py` APP_VERSION 0.97.31 → 0.97.32

## Test-Status

**1279 grün** (1268 → 1279, +11 netto: +11 P60).

## AC-Check

- AC1-AC3: ✓ Source-Level (T4, T5, T6 prüfen Helper-Aufruf vor State-Stop)
- AC4: ✓ T2 (no-op wenn nicht-TX)
- AC5: ✓ T3 (kein ptt_off wenn radio.ip=None)
- AC6: ✓ T8 (kein set_tx_antenna — ANT1-Pflicht)
- AC7: ✓ test_halt_uses_helper
- AC8: ✓ T7 (SWR-Watchdog unverändert)
- AC9 (R1-F1): ✓ T9 (_pending_station_click cleared)
- AC10 (R1-F1): ✓ T10 (kein Crash wenn Attr fehlt)

## Hardware-Check

- Kein `set_tx_antenna` im Helper-Pfad — ANT1 bleibt
- SWR-Watchdog unverändert (eigener Stop-Block)
- Bandwechsel/Mode-Wechsel unverändert (eigene Cleanups)

## R1-Findings (vorheriger Round)

- F1 ROT (`_pending_station_click` Clear): **angenommen** + Tests T9/T10
- F2 ORANGE (tx_finished sync vs. async): **entkräftet** durch Code-Check
  (Worker-Thread → QueuedConnection)
- F3 GELB (SWR-Watchdog auch _pending_station_click): **noch nicht**
  umgesetzt — separater Folge-Commit, weil komplexerer Block

## Frage an dich

1. Push-Freigabe?
2. F3 (SWR-Watchdog Pending-Click) als Bestandteil von P60 oder separates
   Commit später?
3. Sonstige Findings?
