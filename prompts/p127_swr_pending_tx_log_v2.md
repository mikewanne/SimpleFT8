# R1 — P127 Sende-Log bei SWR-Abbruch verwerfen

## Was ich will

Du bist Reviewer. KEIN Code generieren. Findings nach Severity
(🔴/🟠/🟡/🟢). KISS bewerten. Code ist Referenz.

## Kontext

**Mike-Field-Bug 25.05.2026 10:52 (Screenshot 15M SWR 31.3):**
```
⚠ Band 15M gesperrt — SWR 31.3
08:51:15 [0] → Sende Z62NS DA1MHH -15   ← NACH der Sperre-Meldung
```

Sende-Eintrag erscheint mit Slot-Start-Timestamp UNTER der SWR-Sperre-
Meldung — wirkt wie „App hat noch gesendet nach Sperre". Mike: „wurde
wirklich gesendet oder nur Meldung?"

**Root Cause (P93-Defer-Mechanik):**
P93 (v0.97.65) deferiert Sende-Log-Eintrag von `tx_started` auf
`tx_finished`. Bei SWR-Stop mitten im Slot:
1. tx_started feuert → `_pending_tx_log` gesetzt
2. SWR-Spike → `encoder.abort()` → ptt_off()
3. Worker wacht aus abort_event auf → emittet `tx_finished`
4. `_on_tx_finished` (mw_qso.py:454) liest pending → ruft add_tx
   → Eintrag landet trotz Abbruch im Log

**Hardware ist sicher** (PTT abgeschaltet, Bruchteil vor 2. Spike
rausgegangen, danach Stop). Nur Log-Anzeige ist missverständlich.

**Mike-Spec Variante C (aus TODO P127):** im SWR-Watchdog direkt
`_pending_tx_log = None` setzen. KISS, am Ursprung des Problems,
analog zum bestehenden P60-F3-Pattern (`_pending_station_click = None`).

## V1/V2-Architektur

**Eine atomare Änderung in `ui/mw_tx.py:_on_swr_alarm`** nach Z. 740:

```python
# Z. 737-740 bestehend (P60-F3):
if hasattr(self, "_pending_station_click"):
    self._pending_station_click = None
# P127 (25.05.2026): pending deferred TX-Log verwerfen
if hasattr(self, "_pending_tx_log"):
    self._pending_tx_log = None
```

## Pattern-Familie etabliert

P127 ist die 5. Iteration der QSO-Lifecycle-Defer-Familie:

| Ticket | Was | Bei Anlass-Wegfall |
|---|---|---|
| P81 (v0.97.53) | Auto-Hunt-Stop-Meldung | Flush am QSO-Ende |
| P122 (v0.98.05) | Auto-Hunt-Stop-Aktion | Flush am QSO-Ende |
| P124 (v0.98.06) | Hash-Marker im Display | Kontextuell auflösen |
| P128 (v0.98.07) | Empf.-Log-Eintrag nach ✓ | Lazy-Aging nach 60s |
| **P127 (NEU)** | Sende-Log-Eintrag bei SWR-Stop | **Verwerfen am Ursprung** |

## ACs

- AC1: `_pending_tx_log` cleared in `_on_swr_alarm` nach P60-F3-Block
- AC2: `_on_tx_finished` mit pending=None → kein add_tx
- AC3: Hardware-Sicherheit unverändert (abort + ptt_off bleiben)
- AC4: HALT-Pfad (`_on_cancel`) unverändert — Mike-Spec war NUR SWR
- AC5: Bandwechsel ohne SWR — kein Eingriff
- AC6: 1-Spike / Pre-TX-Pfade (early return) — kein Eingriff
- AC7: Defensive `hasattr` für Test-Fakes

## Was du prüfen sollst

1. **Symmetrie P60-F3:** ist die Position direkt nach
   `_pending_station_click = None` semantisch korrekt? Gleiche Klasse
   von „pending-Cleanup nach SWR-Stop". KISS-OK?

2. **Race-Condition mit tx_finished:** GUI-Thread läuft Qt-Slots
   sequenziell. `_on_swr_alarm` setzt pending=None. tx_finished
   feuert später im selben Thread → liest pending=None → kein add_tx.
   Sauber oder Race-Fenster?

3. **Edge-Case Manueller HALT mid-slot:** Mike-Spec war explizit
   „SWR-Abbruch". Bei HALT (`_on_cancel`) bleibt Verhalten gleich —
   Eintrag erscheint mit Slot-Timestamp. Akzeptabel oder sollte HALT
   auch verwerfen? Mein Vorschlag: NICHT verwerfen, Mike will bei HALT
   evtl. sehen was er gerade abgebrochen hat.

4. **Edge-Case Bandwechsel mid-slot:** Encoder wird ggf. via
   `_on_band_changed` abort'd. Würde dort der gleiche Bug auftreten?
   Mein Vorschlag: separates Ticket falls Mike's Field-Test das zeigt.
   KISS für P127: nur SWR-Pfad.

5. **Tests-Vollständigkeit:** 5 Tests in V1-Plan. Was fehlt?

6. **Pattern-Familie:** 5. Iteration. Gibt es weitere Lifecycle-Pfade
   mit dem gleichen Bug-Vektor die wir gleich mit beheben sollten?
   Mein Bauchgefühl: NEIN — `_pending_station_click` ist schon durch
   P60-F3 abgedeckt, `_pending_tx_log` ist neu durch P127. Weitere
   pending-States existieren nicht (`grep -rn "_pending_" ui/`).

7. **KISS-Bewertung Gesamt:** 1 if-block, 2 Zeilen Code, 5 Tests.
   Sauberste Lösung möglich?

## Verdict erwartet

FINDINGS + GO/NO-GO für direkten Code.
