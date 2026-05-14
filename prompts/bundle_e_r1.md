# Bundle E — R1-Antwort

## Q1-Q7 verbindlich
- **Q1 Ignorieren+add_info** ✓
- **Q2 select_next filtert** ✓
- **Q3 Restart-State unverändert** ✓
- **Q4 Tooltip genügt** ✓
- **Q5 OMNI nicht betroffen** ✓
- **Q6 Helper in `core/qso_state.py`** ✓ (zentraler Ort, alle Pfade
  greifen drauf zu)
- **Q7 Mid-TX läuft durch** ✓

## Bewertung 6/10
Konzept solide, aber Thread-Safety-Lücke + fehlende Pfad-Konsolidierung.

## Findings
### KRITISCH
- **F1** Thread-Safety: `encoder.tx_even` GUI vs Worker-Thread →
  `threading.Lock` schützen.
- **F2** 4 TX-Pfade: Helper muss VON ALLEN gerufen werden — OMNI ist
  Diversity-only, aber Hunt+CQ+Reply+Auto-Hunt ALLE.

### SOLLTE
- **S1** RX-Filter-Rollback komplett (Signal rename + Methode löschen).
- **S2** Auto-Hunt-Loop-Schutz: wenn keine kompatible Station → Pause
  1 Zyklus.
- **S3** Helper `_resolve_tx_slot` in `core/qso_state.py`.
- **S4** UI-Feedback bei Mismatch sichtbar (rote Markierung statt nur
  add_info).

### KÖNNTE
- **K1** OMNI-Lock-Prüfung als Defensive (Edge-Case).
- **K2** Mid-TX-Wechsel-Test.

### HINWEIS
- **H1** Tests anpassen.
- **H2** Persist bei jedem Klick OK (atomic write).

## V3-Marschrute
1. Thread-safe `encoder.tx_even` via Lock
2. `_resolve_tx_slot(their_even, lock_status)` Helper in qso_state.py
3. RX-Filter-Rollback (Signal + Methode)
4. Auto-Hunt-Pause-Logik
5. UI-Feedback verbessern
6. Tests aktualisieren + neue für Lock + Thread-Safety
