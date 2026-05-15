# P60 R1-Review — User-Stop-Pfade brechen TX-Slot nicht ab

Du bist Senior-Reviewer für ein FT8-Funkprogramm (Python + PySide6 +
FlexRadio TCP/VITA-49). **Hardware-Pflicht: ANT1 = TX immer, NIEMALS
TX auf ANT2.**

## Kontext

Mike-Field-Test 15.05.2026 morgens: Bei OMNI-CQ Toggle-Off während
aktivem TX-Slot läuft der 15s-Slot komplett durch (Button wird sofort
rot, aber TX bleibt 15s aktiv). Mike: „Toggle = an/aus, nicht
Slot-Schalter."

Code-Audit zeigt: **gleicher Bug in 3 Stop-Pfaden:**
1. OMNI-CQ Toggle (`ui/main_window.py:791-792`)
2. Auto-Hunt Toggle (`ui/main_window.py:862-863`)
3. Normal-CQ Toggle (`ui/mw_qso.py:311-317`)

Bestehende richtige Pfade (Referenz):
- HALT-Button (`mw_qso.py:_on_cancel:329-333`)
- SWR-Watchdog (`mw_tx.py:_on_swr_alarm`)
- Bandwechsel (`mw_radio.py:_on_band_changed`)
- Mode-Wechsel (`mw_radio.py:_on_rx_mode_changed`, Bundle I)

## Geplanter Fix (V3)

Helper-Methode `_abort_active_tx()` in `mw_tx.py`:
```python
def _abort_active_tx(self) -> None:
    """No-op wenn nicht-TX, ptt_off-Skip bei radio.ip=None."""
    if self.encoder.is_transmitting:
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()
```

Verwendet in:
- OMNI-Toggle-Stop (vor `_omni_cq.stop()`)
- Auto-Hunt-Toggle-Stop (vor `stop_auto_hunt()`)
- Normal-CQ-Toggle-Stop (vor `qso_sm.stop_cq()`)
- HALT-Button (refactor von Inline-Block zu Helper-Call)

**NICHT verwendet in:**
- SWR-Watchdog (eigener Spike-Schutz-Block mit add_info + Modal)
- Bandwechsel/Mode-Wechsel (eigene komplexere Sequenz mit
  State-Cleanups, stop_cq + cancel + set_cq_active)

## Acceptance Criteria

- **AC1-AC3:** Toggle-Off während TX → < 100 ms Stop
- **AC4:** Helper idempotent
- **AC5:** Kein Crash bei `radio.ip=None`
- **AC6:** Antennen-neutral (kein `set_tx_antenna`)
- **AC7:** HALT-Button nutzt Helper
- **AC8:** SWR-Watchdog unverändert

## Test-Plan

T1-T8 inkl. Source-Level-Bug-Schutz + Hardware-Pflicht-Test
(`set_tx_antenna` NICHT im Helper-Body).

## Atomare Commits

C1 Helper-NEU, C2 OMNI+Hunt, C3 Normal-CQ, C4 HALT-Refactor, C5 Tests,
C6 APP_VERSION+Doku.

## Fragen an dich

1. **Helper-Location:** mw_tx.py oder besser eigenes Modul? Im Code
   ist `_on_swr_alarm` auch in mw_tx.py — TX-related Logik dort. OK?
2. **Reihenfolge im Stop-Pfad:** abort → ptt_off → State-Stop. Sicher
   keine Race-Conditions in Qt-Slots? (Slots laufen serialisiert im
   Main-Thread, sollte ok sein)
3. **HALT-Refactor (SR2):** Pro/Con HALT-Pfad in den Helper migrieren
   vs. inline lassen? V2-Self-Review-Entscheidung: refactorn (Konsistenz).
4. **Hardware-Risiko:** Siehst du ANT1-Verletzung? (Sollte nein, Helper
   greift nicht in Antennen-Wahl)
5. **Test-Coverage:** Reichen T1-T8?
6. **Sonstige Findings:** Race-Conditions, Lifecycle, Drift-Risiken?

Bitte Reviewen wie üblich (Bug ROT, Risiko ORANGE, Verb. GELB, Hinweis
GRAU) + PUSH FREIGEGEBEN / KORREKTUR NÖTIG am Ende.
