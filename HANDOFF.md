# HANDOFF — SimpleFT8

**Stand 2026-05-04:** v0.89 — Kalibrier-Pipeline Block 1 erledigt.
Pipeline 6:50 → ~4:31 Min (-2:19 Min, -34 %). 5 atomare Commits
(ebddd3e..aec3706). Voller Workflow V1→V2→R1→V3 — R1 fand
1 KRITISCH (mw_radio.py:798 ueberschreibt MEASURE_CYCLES).

**Tests:** 659/659 grün.

**🔴 KRITISCH-Bug entdeckt nach Block 1 (R1-Audit 2026-05-04):**
``core/diversity.py:86`` Mess-Phase nutzt OPERATE-70:30-Pattern
(4×A1 + 2×A2 statt 3:3). ANT2 strukturell unter-gemessen — erklaert
teilweise Mike's 40m-Beobachtung 4% ANT2-Win-Rate.
→ Plan: ``prompts/v090_mess_pattern_fix_plan.md``
→ Memory: ``project_v090_mess_pattern_bug.md``

**Naechster Schritt — Reihenfolge nach Compact:**
1. **v0.90 Mess-Pattern-Fix** (KRITISCH) — Trigger „v0.90 starten" oder
   „Mess-Pattern-Fix starten". Default Option C: 3:3 fair mit Even+Odd
   beider Antennen, ~30-45 min.
2. **Block 1 Feldtest** — Mike testet kalibrierungs-Dauer/Qualitaet
   (parallel zu v0.90 moeglich).
3. **Block 2 starten** (Adaptiv-Stops) — eigener V1→V3-Zyklus, Ziel
   typisch ~3:20 Min Pipeline. Trigger: „Block 2 starten".
4. Antennen-Drossel-Beobachtung 2026-05-04: Mantelwellensperre
   wieder ausgebaut, ANT2-Kabel jetzt mit lockeren 8-foermigen
   Schlaufen verlegt. Zukunfts-Test ob ANT2-Win-Rate erholt.

**Rollback bei Problemen:** `git checkout v0.88.1` (Snapshot vor Block 1).

---

## 2026-05-04 (v0.88) — Bandpilot Stunden-Refactor

**Voller Workflow ft8_workflow durchgezogen:** V1 (Mike-Konsens) → V2
(Self-Review, 25 neue AKs) → R1 (5 KRITISCH + 3 OPTIONAL) → V3 (36 AKs)
→ Mike-Freigabe → 13 atomare Commits → Final-R1 (1 KRITISCH +
2 EMPFEHLUNGEN, alle gefixt).

**Neue Architektur (v0.87 → v0.88):**
- Drei direkte Werte pro UTC-Stunde **ohne Aggregation**
  (R1: Std + DX sind nicht IID → Aggregat erzeugt Bias)
- Settings ``bandpilot_mode`` ∈ ``{off, auto, manual}`` ersetzt
  ``bandpilot_enabled`` + ``bandpilot_diversity_pref``
- Auto-Modus: Toleranz ``max(5%, 1 Sta)`` **gegen aktuellen Modus**
  (R1-Finding A) — kein Pingpong wenn nahe Top-1
- Manuell-Modus: Dialog **nur** wenn Top-1 != aktueller Modus
  (R1-smart, kein Klick-Overhead)
- TX-Schutz mit Band-Konsistenz-Check (R1-Final): wenn User waehrend
  TX das Band wechselt, wird pending-Empfehlung verworfen
- Atomic save() in Settings + atomic write in MD-Generator
- Migration alter Settings + Cache-Cleanup automatisch beim 1. Start

**Implementierte Files:**
- `core/mode_recommender.py` (komplett ersetzt — alte Bandpilot-API
  geloescht, neue HourlyBandpilot)
- `core/bandpilot_md.py` (neu — MD-Generator)
- `ui/bandpilot_dialogs.py` (neu — Toast + Manuell-Dialog)
- `ui/mw_radio.py`, `ui/main_window.py`, `ui/settings_dialog.py`
- `config/settings.py` (Migration + atomic save)
- `scripts/generate_plots.py` (MD-Hook am Ende)
- `docs/explained/bandpilot_de.md` + `bandpilot.md` (komplett neu)
- `README.md` (DE+EN, Migrations-Hinweis)
- `auswertung/Bandpilot-20m-FT8.md` + `Bandpilot-40m-FT8.md`

**Tests +43:** 616 → 659 grün.

---

## 2026-05-02 (v0.87.1) — Doku-Konsolidierung

**Voller Workflow ft8_workflow durchgezogen** (V1→V2(17 Self-Review-
Lücken)→R1(13 Findings)→V3→11 atomare Commits→Final-R1).

- `docs/explained/` ist jetzt die **Single Source of Truth** für
  alle 20 User-Features (= 40 Files DE+EN).
- 4 alte UPPER_SNAKE_CASE-Files migriert (POWER, FREQUENCY, DX_TUNING,
  bandpilot), 4 redundante geloescht (DIVERSITY, DT_CORRECTION) mit
  Inhalts-Merge ihrer einzigartigen Sektionen.
- 5 neue User-Doku-Files (DE+EN): antenna-preference, waitlist,
  direction-map, locator-mining, auto-hunt.
- `ui/help_dialog.py:_FEATURES` von 11 auf 20 alphabetisch sortiert.
- `?`-Button bekommt Tooltip.
- README.md komplett aktualisiert (Bandpilot in Key Innov + All
  Features + In Field Test + 20-Feature-Doc-Tabelle, v0.86→v0.87,
  Tests-Badge 563→616).
- OMNI-TX-Aktivierungs-Methode aus Doku entfernt (PRIVAT, gehoert
  nicht auf GitHub).
- 11 atomare Commits. Final-R1 fand 1 valides Finding (Modul-Verweis
  raus aus User-Doku) + 4 Halluzinationen.

---

## 2026-05-01 (v0.87) — Bandpilot

---

## 2026-05-01 (v0.87) — Bandpilot

**Implementiert (autonom, voller Workflow V1→V2→R1→V3→Plan→Code):**

- `core/mode_recommender.py` (neu) — Pure-Logik: aggregiert Stats aus
  `statistics/<Modus>/<Band>/FT8/`, empfiehlt RX-Modus.
  - `MIN_DAYS=2`, `MIN_CYCLES=50` Schwellen pro Modus.
  - Kandidat-A-Aggregation: `Normal_Mean` vs `(Diversity_Normal_Mean + Diversity_DX_Mean) / 2`.
  - `BandpilotSummaryCache` mit 24h-TTL pro Band, atomarem Write.
- `tests/test_mode_recommender.py` (neu) — 28 Tests.
- `ui/mw_radio.py` — `_activate_diversity_with_scoring(scoring)` aus
  `_on_rx_mode_changed` extrahiert (Refactor), neuer `_set_rx_mode_direct(target)`
  Helper, `_maybe_apply_bandpilot(band)` Hook in `_on_band_changed`.
  Override-Set `_bandpilot_overridden_bands` mit „greift einmal beim
  Rückwechsel"-Semantik.
- `ui/main_window.py` — Bandpilot-Init in `_init_optional_features`.
- `ui/settings_dialog.py` — Bandpilot-Section in Tab „FT8 & Diversity":
  Checkbox + Pref-Combo (Auto/Standard/DX) + ?-Button mit
  sprachabh. QMessageBox-Hilfe.
- `config/settings.py` — `bandpilot_enabled=False`,
  `bandpilot_diversity_pref="auto"`.
- `docs/bandpilot_help_de.md` + `docs/bandpilot_help_en.md` (neu).

**Live-Smoke-Test mit Mike's Daten:** 40m → diversity_normal
(42.4 vs 19.2), 20m → normal (20m-Diversity-Datenlage noch dünn).

**Anmerkung Lesson:** Premature Annahme „Diversity_DX zählt nur SNR<-10"
in der Aggregation war falsch — Mike hat den Code-Check eingefordert,
ich habe verifiziert dass alle drei Stats-Pfade die gleiche Metrik
loggen (Anzahl dekodierter Stationen). Damit ist Mike's
Kandidat A (50/50-Aggregat) korrekt — Mindest-Messzeit halbiert.

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

### 🐛 Heute neu beobachtet (01.05.2026 abends)

- **Propagation-False-Positive-Dialog beim App-Start:** Mike sah einmal
  „Kein Netzwerk — keine Propagationsdaten verfügbar" obwohl Netzwerk da
  war. Root-Cause: `_init_propagation_polling` triggert ersten UI-Update
  nach 3s (`main_window.py:316`), aber Background-HamQSL-Fetch kann
  laenger dauern → `_raw_data = None` beim ersten UI-Tick → Dialog.
  Fix-Idee (voller Workflow): zusaetzliches `_prop_ever_loaded`-Flag,
  Dialog nur bei Verlust nach erfolgreichem Erst-Fetch, nicht im
  initialen Race-Window.

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
- **SESSION_WORKFLOW.md v1.2 aktiviert** (Doku-only) — neuer Lifecycle-Workflow analog zu WORKFLOW.md v1.1.
  CLAUDE.md/feierabend.md/MEMORY.md auf neue Struktur umgestellt. R1-Review fand 3 Findings inkl. KRITISCH
  2a↔2b-Widerspruch (Trivial-Klausel ergänzt).
- TODO-Liste-Lesson: `_reset_defaults` (v0.79) und `btn_omni_cq` (v0.78) waren bereits erledigt. Memory
  `feedback_todo_history_pflicht.md` — vor TODO-Liste IMMER `git log --oneline` + `grep` gegen aktuellen Code.
- v0.86 Fix G — Falscher Kalibrierungstext im Normal-Modus. `DXTuneDialog` zeigte "Diversity Standard"
  statt "Gain-Messung". `rx_mode`-Parameter hinzugefügt, `_get_mode_label()` unterscheidet Normal/Diversity.
  Statusbar-Text modus-abhängig. 2 neue Smoke-Tests. 512/512 grün.
- **WORKFLOW-PFLICHT verschärft:** Keine Ausnahmen mehr. IMMER V1→V2→R1→V3→Plan→Code.
  CLAUDE.md Anfang+Ende doppelt eingetragen. Skill `.claude/skills/ft8_workflow.md` erstellt.

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
563 passed in ~8s
```

Neu seit v0.79:
- v0.80: 9 Tests fuer DT-Drift-Fix (A1-A3, B, C, Race-Fix)
- v0.81: 3 Tests fuer Fix D (`on_decoder_finished`)
- v0.82: 2 Tests fuer Fix E (Decoder-Signal-Reihenfolge)
- v0.83: 3 Tests fuer Fix F (Auto-Close-Dialog)
- v0.84: 4 Tests fuer Feature H (Tertile-Analyse)
- v0.85: -4 Tests (4 AGC-Tests entfernt mit Dead-Code-Cleanup)
- v0.86: +2 Smoke-Tests Fix G + AC-1..AC-4 (+56, -5 Duplikate = +51 netto)
  - test_protocol.py: 22 Tests (protocol.py, vorher 0)
  - test_diversity_merger.py: 10 Tests (diversity_merger.py, vorher 0)
  - test_ap_lite.py: 24 Tests (ap_lite.py, vorher 5 in test_modules.py)
  - test_modules.py: -5 (AP-Lite-Duplikate entfernt)

---

## Letzter bekannter guter Zustand

- **Branch:** main
- **HEAD:** `refactor(tests): AP-Lite-Duplikate aus test_modules.py entfernen (AC-4)`
- **Tests:** 563/563 gruen
- **App-Version:** v0.86
- **Backup:** `Appsicherungen/2026-04-30_vor_decoder_reihenfolge_fix/`
  (4 MB code-only, vor Fix E v0.82). Heute Vormittag Fix F + Feature
  H — kein neues Backup, da pure Code-Updates ohne riskante
  Algorithmus-Aenderung.

---

Morgen: `cd SimpleFT8` ODER `cd FT8` → `claude1` → laedt automatisch alle
Memories + CLAUDE.md.
