# P61 — Auto-Hunt picked Station SOFORT WIEDER nach abgeschlossenem QSO

**Session:** 15.05.2026 vormittags · APP_VERSION-Ziel 0.97.33 · Tests 1279 → ~1290

## 1. Symptom (Mike-Field-Test 15.05.2026 morgens)

Screenshot zeigt: nach erfolgreichem QSO mit `HA8RC` (Logging um 04:59:30
mit „✓ QSO mit HA8RC komplett") wählt Auto-Hunt **30 Sekunden später**
(05:00:00) dieselbe Station HA8RC für einen erneuten QSO-Versuch. Das
2. QSO läuft komplett durch (89s), wird aber durch die existierende
ADIF-Duplikat-Erkennung erst BEIM SCHREIBEN abgelehnt:

```
05:00:45  HA8RC Duplikat (89s) — kein ADIF-Eintrag
```

**Praktischer Schaden:**
- 89s verschwendete Funkzeit auf einem Slot der eine NEUE Station hätte
  arbeiten können
- Gegenstation HA8RC sieht doppelten Anruf in 90s → Funkverkehr-Etikette-
  Verletzung
- Auto-Hunt-Zähler verschwendet Versuche

## 2. Existierende Schutz-Mechaniken (sollten greifen, tun's nicht)

### 2.1 `qso_log.is_worked_on_band(call, band)` in `core/auto_hunt.py:286`

Bei score-Berechnung:
```python
if self._qso_log:
    if not self._qso_log.is_worked(c.call):
        score += _W_NEW_STATION
    elif not self._qso_log.is_worked_on_band(c.call, self._band):
        score += _W_NEW_BAND
    else:
        return 0.0      # ← Schon auf Band gearbeitet → score=0 → skip
```

Anschließend in `select_next`:
```python
if best.score <= 0:
    return None
```

Sollte HA8RC nach `qso_log.add_qso("HA8RC", "20M")` (mw_qso.py:508)
korrekt filtern.

### 2.2 ADIF-Duplikat-Filter `_LOG_DEDUP_WINDOW_S=300` in `ui/mw_qso.py:23`

Greift erst beim ADIF-Schreiben. Verhindert doppelten Log-Eintrag, aber
NICHT das vorherige 89s-QSO.

## 3. Wurzel-Hypothesen

Die existierende `is_worked_on_band`-Mechanik HAT versagt. Mögliche
Ursachen (in absteigender Wahrscheinlichkeit):

**Hypothese A — `qso_log.add_qso` lief NICHT:**
- `adif.log_qso` (mw_qso.py:492) wirft Exception (z.B. File-IO)
- `qso_log.add_qso` Z.508 wird übersprungen (kein try/except)
- HA8RC bleibt aus `_worked_band` set
- Bei nächstem `select_next` ist `is_worked_on_band` False → score>0

**Hypothese B — Reihenfolge-Race:**
- `_run_auto_hunt(messages)` läuft in `_on_cycle_decoded` (mw_cycle.py:128)
- `qso_log.add_qso` läuft in `_on_qso_complete` (über `qso_complete`-Signal aus `on_message_sent`)
- Beide werden vom GUI-Thread sequenziell verarbeitet, aber Reihenfolge der Qt-Slots ist Sender-FIFO. Wenn Decoder-cycle_decoded VOR encoder-tx_finished feuert, läuft Auto-Hunt-Pick mit altem qso_log.

**Hypothese C — Stale qso_log-Reference:**
- `main_window.qso_log` und `auto_hunt._qso_log` sind dieselbe Instanz
  (verifiziert via `main_window.py:332`).
- ❌ ausgeschlossen.

**Hypothese D — Band-String-Mismatch:**
- `qso_log.add_qso` upper-cased `band` (Z.48): `"20M"`
- `is_worked_on_band` upper-cased erneut: `"20M"`
- Match ist symmetrisch. ❌ ausgeschlossen.

Keine Hypothese ist ohne Live-Debug-Log mit Sicherheit zu bestätigen.

## 4. Lösungsansatz — Belt-and-Suspenders mit Cooldown-Schicht

Statt die Wurzel-Hypothese zu jagen (kostet Stunden ohne garantierten Fix),
ziehen wir eine **zweite Schutz-Schicht** ein, die unabhängig von
`qso_log` greift und auch dann sicher ist wenn Hypothese A oder B
zutreffen.

### 4.1 Neue Cooldown-Schicht in `core/auto_hunt.py`

```python
# Neu in __init__
self._recent_qso: dict[str, float] = {}   # base_call → timestamp
# Konstante (oben in Modul)
_RECENT_QSO_COOLDOWN_S = 300              # 5 Min — analog _LOG_DEDUP_WINDOW_S

# In on_qso_complete: Call mit Timestamp persistieren
def on_qso_complete(self, call: str):
    self._current_target = None
    self._cooldown.pop(call, None)        # alte Fail-Cooldown raus
    base = call.strip().upper().split("/")[0]
    self._recent_qso[base] = time.time()  # ← NEU
    print(f"[Auto-Hunt] QSO mit {call} fertig — 5min Recent-Cooldown")

# In select_next: NEUE Filter-Schicht VOR _cooldown-Check
for msg in (messages or []):
    if not getattr(msg, 'is_cq', False):
        continue
    call = msg.caller
    if not call:
        continue
    base = call.strip().upper().split("/")[0]
    # NEU: Recent-QSO-Cooldown (P61)
    last_qso = self._recent_qso.get(base, 0)
    if now - last_qso < _RECENT_QSO_COOLDOWN_S:
        continue
    # ... bestehende _cooldown + SNR-Filter
```

### 4.2 Pflege

- **Reset bei Bandwechsel:** `_recent_qso.clear()` in `set_band` —
  Hobby-Praxis: gleiches Call auf anderem Band SOLL gepickt werden
- **Reset bei Mode-Wechsel:** ebenfalls clear (analog Bandwechsel)
- **Reset bei `stop_auto_hunt`:** NEIN — User soll Auto-Hunt Toggle nicht
  als Cooldown-Bypass nutzen
- **App-Restart:** dict leer — Mike-Spec aus P1.7 (`_recent_logged_calls`
  ist auch session-lokal)

### 4.3 Hardware-Pflicht ANT1

Auto-Hunt ist TX-Feature. **Kein Einfluss** auf Antennen-Wahl — der
neue Cooldown-Filter verhindert TX-Calls, schaltet nicht zwischen
ANT1/ANT2 um. ANT1-Pflicht bleibt unverändert (P53-T5-Hardware-Pflicht-
Test deckt das ab).

## 5. Aus Scope

- **Wurzelanalyse der `is_worked_on_band`-Fehlfunktion** — separate
  Folge-Untersuchung wenn Mike weiter Symptome sieht. Bessere
  Daten-Lage durch Diag-Log möglich, aber nicht jetzt.
- **`try/except` um adif.log_qso** — Defensive-Hardening, könnte
  Hypothese A entschärfen. Aber: wenn ADIF-Write fehlschlägt MUSS Mike
  das erfahren (Disk voll!), nicht silent absorbieren.
- **`_recent_logged_calls` als Filter-Quelle** — Alternative wäre dieses
  Dict an `auto_hunt` zu reichen. ABER: dann hängt Auto-Hunt am
  MainWindow-State. KISS-Verstoß.

## 6. Code-Änderungen (Vorab-Schätzung)

| Commit | Datei | Was |
|---|---|---|
| C1 | `core/auto_hunt.py` | `_recent_qso` dict + Konstante + Filter in `select_next` + Persist in `on_qso_complete` + Clear in `set_band`/`set_mode` |
| C2 | `tests/test_p61_autohunt_recent_qso.py` NEU | T1-T6 Unit-Tests AutoHunt mit FakeMW-Pattern |
| C3 | `main.py` APP_VERSION 0.97.32 → 0.97.33 + Backup |
| C4 | Doku: HISTORY/HANDOFF/CLAUDE/TODO/Memory/MEMORY.md/Plan-Files |

## 7. Tests (Plan, V3 konkretisiert)

- **T1** `select_next` mit kürzlich erfolgreichem QSO → None (cooldown)
- **T2** `select_next` mit QSO älter als 5 Min → Pick erlaubt
- **T3** Cooldown ist Band-spezifisch — `set_band` clear → erneut pickbar
- **T4** Cooldown ist Mode-spezifisch — `set_mode` clear → erneut pickbar
- **T5** Base-Call-Normalisierung — `HA8RC/P` matched `HA8RC`
- **T6** Bug-Schutz-Assertion: Source-Level grep `_recent_qso` exists
  in `core/auto_hunt.py`

## 8. Field-Test-Punkte für Mike (V3 §X)

| F# | Was prüfen |
|---|---|
| F1 | QSO mit Station X auf Band Y → unmittelbar danach noch nicht (5 Min lang) erneut gepickt |
| F2 | Nach 5 Min QSO mit X auf Band Y kann erneut gepickt werden |
| F3 | Band-Wechsel Y→Z → X auf Z kann sofort gepickt werden |
| F4 | Mode-Wechsel FT8→FT4 → X auf FT4 gleichen Bands kann sofort gepickt werden |
| F5 | Regression: Auto-Hunt-Stop (P60-F2) bricht TX weiterhin sofort ab |
| F6 | Regression: HALT-Button (P60-F4) bricht alle TX weiterhin sofort ab |

## 9. Klärungsfragen (intern für Self-Review)

- Q1: Sollte Cooldown nicht nur auf BAND sondern (BAND, MODE) trennen?
  → Spec: ja, weil Hobby-Praxis 80m FT8 vs 80m FT4 = unterschiedliche
  QSOs. Aktuelle V1: nur Band-Reset bei `set_band`/`set_mode`. Wenn V2
  Self-Review da ein Loch findet, refactor zu `(call, band, mode)`-Key.
- Q2: 5 Min Cooldown — zu kurz? zu lang?
  → Analog `_LOG_DEDUP_WINDOW_S=300` aus P1.7. Mike hat dort 5 Min
  abgesegnet, gleiches Kontext-Fenster passt.
- Q3: Reset bei App-Restart OK?
  → Ja, analog P1.7. Mike will Reset bei manuellem Neustart.
