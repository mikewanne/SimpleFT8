# HANDOFF — SimpleFT8

**Stand 2026-05-01:** v0.85 (Dead-Code-Cleanup, Cleanup I + Doc J).
v0.84 Tertile-Analyse heute Mittag. v0.83 Fix F Auto-Close-Dialog
heute Vormittag. v0.82 Fix E gestern abends.

**Tests:** 510/510 gruen (514 - 4 AGC-Tests aus Dead-Code-Cleanup).

---

## ⛔⛔⛔ HARDWARE-WARNUNG — HOECHSTE PRIORITAET ⛔⛔⛔

### ANT1 = TX-Antenne. IMMER. Auf jedem Band.
### ANT2 = NUR Empfangs-Zusatzantenne. NIEMALS TX!

**ANT2 (Regenrinne ~15m) ist NICHT fuer Sendeleistung ausgelegt.** TX auf
ANT2 mit 100 W = Hardware-Schaden moeglich (PA, Antennen-Pfad).

| Aktion | Antenne |
|---|---|
| Manuelle CQ-Anrufe / TUNE | **ANT1** |
| OMNI CQ (passiv) | **ANT1** |
| AUTO HUNT (aktiv) | **ANT1** |
| Diversity RX-Pattern | beide RX, **TX nur ueber ANT1** |

**Im Code:** `set_tx_antenna("ANT1")` zentral abgesichert in
`Encoder.transmit()` (vor `ptt_on()`) UND vor jedem `tune_on()`-Aufruf.
**App-Start Hardware-Dialog (v0.77)** zeigt die Regel explizit + Disclaimer
(Modal, OK/Abbruch, Abbruch = `sys.exit(0)`).

---

## 2026-04-30 (v0.80 → v0.81 → v0.82) — Drei-Bugfix-Tag

### Heute erledigt (chronologisch)

**Vormittag — v0.80 TX-DT-Drift QSO-Retry-Fix (BLOCKER):**
- Folge-Reports kamen seit v0.74 mit DT 0.6-0.8s am Empfaenger an (ueber
  FT8-Decode-Schwelle 0.5s) → 7 Real-QSOs gescheitert.
- 7 atomare Commits: A1+A2+A3+B+C+Race-Fix+Release.
- Workflow voll V1 → V2 → R1 → V3 (R1 fand A2 cancelable-sleep KRITISCH +
  Final-Race-Condition).
- Real-QSO mit 2. Station auf Icom: DT 0.0-0.1s ✓.

**Mittag — v0.81 Fix D Doppel-Report (Versuch 1, gescheitert):**
- `on_decoder_finished` aus `on_cycle_end` rausgezogen, sollte am Slot-Ende
  in `_on_cycle_decoded` laufen.
- Workflow voll V1 → V2 → R1 → V3 (R1 fand BLOCKER P6 CQ_WAIT-Regression).
- Implementation + Final-R1: alles OK laut Code-Review.
- Field-Test scheiterte: Doppel-Report bleibt. Mike sandte „-23" zweimal
  nach R+19.

**Nachmittag — v0.82 Fix E Decoder-Signal-Reihenfolge (Versuch 2,
erfolgreich):**
- Root Cause analysiert: `on_message_received` haengt am `message_decoded`-
  Signal das NACH `cycle_decoded` emittet wird → mein Fix-D-Trigger lief
  VOR den State-Wechseln.
- Mike's Feedback „du arbeitest nicht den deepseek workflow" → vollen
  Workflow erneut durchgezogen.
- Loesung: drittes Decoder-Signal `cycle_finished = Signal()` das NACH
  allen `message_decoded`-Emits feuert; `on_decoder_finished` haengt
  daran.
- 3 atomare Commits + 2 neue Tests (505 → 507).
- Field-Test: QSO mit RW6HP komplett bestaetigt (4-Slot-Pacing).

**Spaetnachmittag — Memory-Updates + Fernwartungs-Setup:**
- Memory `project_simpleft8_ferienhaus.md` — Trigger-Phrase „SimpleFT8 am
  Ferienhaus": Wrapper-Script-Start + Fenster auf Display 2 (Pos 1024,0)
  verschieben.
- Wrapper-Script `tools/remote/start_simpleft8_nokill.py` — umgeht
  `kill_old_instances`-osascript-Self-Kill bei Background-Launch.
- Memory `feedback_workflow_works_with_deepseek.md` — Mike-bestaetigte
  Workflow-Wirksamkeit nach Fix E.
- Memory `feedback_workflow_after_failed_fix.md` — Disziplin nach
  gescheitertem Fix.

### Bilanz heute

- **3 Releases**: v0.80, v0.81 (gescheitert im Field-Test), v0.82
- **13 Commits** lokal (10 fuer v0.80-Run + 3 fuer v0.82, dazu Fix D in
  v0.81)
- **507 Tests** gruen (502 vor heute → +5 Fix-D + +2 Fix-E Tests, 2 v0.80-
  Tests fuer Fix-D angepasst)
- **3 Memory-Eintraege** ergaenzt
- **Voller V1→V2→R1→V3-Workflow** dreimal durchlaufen — Mike's Feedback:
  „unser workflow superfinktioenr mit deepseek im verband"

### Field-Test-Erfolge

- v0.80 Real-QSO am Icom: DT 0.0-0.1s, Drift weg ✓
- v0.82 Real-QSO mit RW6HP: 4-Slot-Pacing, kein Doppel-Report ✓
  ```
  14:28:27 TX_REPORT → TX_RR73 (sauber)
  14:28:43 RX R-15 von RW6HP
  14:28:43 TX RW6HP DA1MHH RR73
  14:29:13 RX 73 von RW6HP — QSO bestätigt ✓
  ```

---

## Offen / Naechste Schritte (priorisiert)

### 🔴 Verifikation v0.82 Fix E

- Real-QSO weitere Stationen (mehr als 1 Bestaetigung des Fix).
- Beobachten: kein Doppel-Report-Bug bei R-Report-Empfang in
  WAIT_REPORT-Phase.

### 🟡 Aus v0.76-Field-Test (offen seit 29.04.)

- 20m FT8 Datensammlung — Ziel 5 Tage flaechendeckend (24h x 3 Modi).
- Aktueller Stand: 2-3 Tage je Stunde-Modi-Slot, mit Luecken.

### 🔵 Aus aelteren Releases (offen)

- Migration `main_window._psk_worker` → `core/psk_reporter` (Konsolidierung).
- Even/Odd dedizierter Timer (FT2 kritisch).
- Per-Station DT-Offset TX (erst nach mehr Feldtest-Daten).
- IC-7300 Fork (TARGET_TX_OFFSET dort separat messen).
- AP-Lite Test-Pipeline (synthetische E2E-Tests).

### ✅ Heute am 2026-05-01 erledigt

- v0.83 Fix F — Kalibrierungs-Dialog Auto-Close 3s ohne OK
- v0.84 Feature H — Tertile-Analyse Statistik (Pooled Mean + 33%/67%-Tertile shaded band)
- v0.85 Cleanup I + Doc J — Dead-Code-Cleanup (AGC + input_sample_rate + sync_ntp + _ntp_offset, ~60 Zeilen)
- TODO-Liste-Lesson: `_reset_defaults` (v0.79) und `btn_omni_cq` (v0.78) waren bereits erledigt. Memory
  `feedback_todo_history_pflicht.md` — vor TODO-Liste IMMER `git log --oneline` + `grep` gegen aktuellen Code.

### 🟢 Long-term (theoretisch)

- SimpleFT8-Field: IC-705 + Pi 4 + Tablet-Browser-Client. ~70-110 h.
- Statistik-Push nach GitHub sobald 5 Tage flaechendeckend erreicht.

---

## Warnungen & Fallen (Stand v0.82)

**v0.82 Fix E NEU:**
- **Decoder-Signal-Reihenfolge** ist KRITISCH:
  `cycle_decoded` → pro msg `message_decoded` → `cycle_finished`.
  REIHENFOLGE NICHT AENDERN. `cycle_decoded` MUSS vor `message_decoded`
  bleiben (`_assign_slot_parity` setzt `msg._tx_even` das in
  `mw_qso.py:85/423` gelesen wird). `cycle_finished` MUSS am Ende
  bleiben (sonst Doppel-Report-Bug zurueck).
- **`on_cycle_end` (Slot-START) vs `on_decoder_finished` (Slot-ENDE)**
  Aufspaltung: nicht zusammenfuehren. CQ_WAIT/3-Min-Gesamttimeout/
  WAIT_73-Tick laufen Decoder-unabhaengig in `on_cycle_end`. Retry-Pfad
  laeuft Decoder-abhaengig in `on_decoder_finished` (sieht state nach
  R-Report-Verarbeitung).

**v0.81 Lessons (Fix D scheiterte):**
- Annahme „`_handle_normal_mode` ruft `on_message_received` direkt" war
  FALSCH. `on_message_received` haengt am separaten `message_decoded`-
  Signal das Qt-FIFO NACH `cycle_decoded` emittet.
- Bei Folge-Fixes nach Field-Test-Scheitern: Workflow nicht abkuerzen.
  Memory: `feedback_workflow_after_failed_fix.md`.

**v0.80 (TX-DT-Drift):**
- `TARGET_TX_OFFSET = -0.8s` ist FlexRadio-spezifisch. IC-7300 Fork
  braucht eigenen Wert.
- `_abort_event` (threading.Event) ist KRITISCH fuer cancelable sleep —
  ohne das schlaeft Encoder bis zu 14s nach abort.
- Drift-Guard 0.3s-Schwelle — nicht groesser ohne neue Mess-Methodik.

**Aus v0.75-v0.78 unveraendert:**
- Auto-Hunt `_auto_hunt_timer` UNABHAENGIG vom Totmannschalter
  (Bot-Tarn-Schutz). Nach Stop ist Pflicht-Restart, kein Auto-Resume.
- App-Start Hardware-Dialog: Pflicht-Acknowledgment, bei Abbruch
  `sys.exit(0)`.

**Fernwartungs-Setup (NEU 30.04.):**
- App via `tools/remote/start_simpleft8_nokill.py` starten (umgeht
  `kill_old_instances`-osascript-Self-Kill bei Background-Launch).
- Fenster nach App-Start auf Display 2 (Pos 1024,0) verschieben.
- Memory `project_simpleft8_ferienhaus.md` — Trigger „SimpleFT8 am
  Ferienhaus".

---

## Test-Suite Status

```
./venv/bin/python3 -m pytest tests/ -q
510 passed in ~7s
```

Neu seit v0.79:
- v0.80: 9 Tests fuer DT-Drift-Fix (A1-A3, B, C, Race-Fix)
- v0.81: 3 Tests fuer Fix D (`on_decoder_finished`)
- v0.82: 2 Tests fuer Fix E (Decoder-Signal-Reihenfolge)
- v0.83: 3 Tests fuer Fix F (Auto-Close-Dialog)
- v0.84: 4 Tests fuer Feature H (Tertile-Analyse)
- v0.85: -4 Tests (4 AGC-Tests entfernt mit Dead-Code-Cleanup)

---

## Letzter bekannter guter Zustand

- **Branch:** main
- **HEAD:** `chore(release): v0.85 — Dead-Code-Cleanup (Cleanup I + Doc J)`
- **Tests:** 510/510 gruen
- **App-Version:** v0.85
- **Backup:** `Appsicherungen/2026-04-30_vor_decoder_reihenfolge_fix/`
  (4 MB code-only, vor Fix E v0.82). Heute Vormittag Fix F + Feature
  H — kein neues Backup, da pure Code-Updates ohne riskante
  Algorithmus-Aenderung.

---

Morgen: `cd SimpleFT8` ODER `cd FT8` → `claude1` → laedt automatisch alle
Memories + CLAUDE.md.
