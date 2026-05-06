# HANDOFF — SimpleFT8

**Stand 2026-05-06:** **v0.95.10 — P1.AP-FIX generate_candidates
State-1 Format-Bug.**

**P1.AP-FIX (NEU):** P1.AP E2E-Test-Pipeline (v0.95.9, hardware-frei mit
ft8lib + Gauß-Rauschen) entdeckte den Bug: `core/ap_lite.py:126`
`generate_candidates(state=1)` produzierte 4-Token-Strings
(`OWN THEIR LOC SNR`, z.B. „DA1MHH DK5ON JO31 +05"). FT8 erlaubt nur
3 Tokens pro Frame → ft8lib lehnt jeden Kandidaten mit `rc=5` →
alle Korrelations-Scores=0 → **State-1-Rescue (WAIT_REPORT) scheiterte
IMMER silent seit AP-Lite-Implementierung**.

**Fix (1 Zeile, KISS):** Locator weglassen, Report-only:
```python
candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")
```
Plus Code-Kommentar Z.121-131 fachlich aktualisiert.

**Voller Workflow:** V1 (Diagnose) → V2 (Self-Review, 9 Lessons) → R1
(„Plan freigegeben") → V3 (5 Compact-feste Diffs) → Compact → Code →
Final-R1-Codereview („Push freigegeben, keine Vorbehalte").
Plan-Files: `prompts/p1_ap_fix_v[1-3].md`.

**Tests 830 → 831 gruen** (+1 maschineller Format-Schutz):
- `test_generate_state1_basic` — 3-Token-Asserts mit Regex
- `test_try_rescue_state1_runs_after_fix` (umbenannt) — kein silent-Block
- `test_generate_candidates_state1_format_correct` (umbenannt) — 3-Token
- `test_generate_candidates_state1_ft8lib_compatible` **NEU** — ruft
  `encoder.generate_reference_wave()` für jeden Kandidaten → ft8lib-Reject
  schlägt sofort an

**Code:** `core/ap_lite.py:121-131`. Atomare Commits `17b7237`
(Code+Tests+main.py 4 Files +79/-36) + Doku-Commit.

**APP_VERSION:** 0.95.9 → 0.95.10.

**Field-Test:** Mike ist in Kur — Test post-Rückkehr. Erwartung: Rescue-
Rate steigt. Notbremse: `AP_LITE_ENABLED=False`.

---

**Vorher v0.95.9 (06.05.2026):** **P1.24 TX-Klick-Buffer (Folge-Fix
zu P1.14, Field-Test bestätigt).** TX-Klick wurde ignoriert wenn
`encoder.is_transmitting=True`. Fix: Buffer-Logik mit State-Cleanup
+ `_pending_station_click` + Statusbar + rekursiver Replay in
`_on_tx_finished`. Tests 812 → 816 gruen.

---

**Vorher v0.95.8:** **P1.14 Station-Wechsel-Bug +
P1.23 Status-UI-Feinjustierung.**

**P1.14 (voller Workflow V1→V2→R1→V3 Diagnose + Plan-V1→V2→R1→V3):**
6 Bug-Wurzeln W1-W6:
- W1: `start_qso` resetete keine Pendings bei `state != IDLE` → Geister-
  Pendings mit alter `their_call`
- W2: angeklickte Station blieb in `_caller_queue` → Doppel-QSO-Risiko
- W3: `_active_qso_targets` wuchs monoton bei Wechseln
- W4/KP6: `_was_cq` State-Machine-extern korrigiert (Plan-V2: BEHALTEN —
  saubere Integration unmöglich, stop_cq() läuft vor start_qso())
- W5: TX-Klick silent ignoriert → Statusbar-Toast „TX aktiv – Klick
  ignoriert" (3s)
- W6: `auto_hunt._manual_override` wurde NIE zurückgesetzt — Auto-Hunt
  pausierte dauerhaft nach manuellem QSO/HALT/Timeout. Fix: `on_manual_qso_end()`
  in `_on_cancel`, `_on_qso_confirmed`, `_on_qso_timeout` (Plan-V2-Erweiterung).

Code-Änderungen: `core/qso_state.py:start_qso` (Reset-Set + 3 Pendings),
`ui/mw_qso.py` (5 Stellen: _on_station_clicked, _on_cancel,
_on_qso_confirmed, _on_qso_timeout).

**P1.23 UI-Feinjustierung:** Label „Lokale Empfangsqualität:" (statt
„Lokaler Empfang:"), Status-Schriftgrößen 11→10px, Sterne 15→13px.

Tests 802 → 812 grün (+10 in `tests/test_p1_14_station_switch.py`).
APP_VERSION 0.95.7 → 0.95.8.

---

**Vorher v0.95.7:** P1.18 DT-Drift Wurzel-Fix + P1.21 Sterne-UX-Refactor.
DT-Bug war 1 vergessene Konstante in v0.95.3 (`_WAKE_OFFSETS["FT8"]`
1.5→2.5 erhoeht, `_DT_OFFSETS["FT8"]` blieb 2.0 statt 3.0). Mike-Hartnaeckigkeit
+ git-diff + DeepSeek bestaetigt. Sterne: Label `Empfang:`, Gold #FFD700,
RichText, Score nur SNR (-10/-14/-18/-22 dB).

**Vorher v0.95.6:** P1-Bundle1 (5 UI-Cleanups: P1.6+P1.12+P1.15+P1.16+P1.19).

**Sub-Aufgaben umgesetzt:**
- **P1.6** Versionsnummer Color #333 → #666 (lesbar)
- **P1.12** NEU-Button (`btn_remeasure`) entfernt — KALIBRIEREN macht alles seit v0.94
- **P1.15** Statusbar `→ Call | RX: ANT` raus — Mike's Wunsch
- **P1.16** QSO-Panel zeitbasiertes 5-Min-Rolling-Window (statt 40-Zeilen)
- **P1.19** 5-Sterne-Anzeige `★★★☆☆` ersetzt SNR-Label (lokale Conditions)

**APP_VERSION:** 0.95.5 → 0.95.6.

**Field-Test offen:** Mike testet im Praxis-Betrieb (Sterne sollten je nach
Conditions schwanken; KALIBRIEREN funktioniert weiter).

---

**Vorheriger Stand 2026-05-05:** **v0.95.5 — Single-Instance-Lock**
(`24aba07` + `f348763` + `13c067f`). Garantiert nur EINE Instanz, schuetzt
fremde main.py-Apps (Websdr) vor Kollateral-Kill via lsof CWD-Filter.

**Vorher v0.95.4 — P1.10 Courtesy-73:** Atomare Commits `9783583`. Wurzel:
IC-7300 Auto-Sequence wartet auf abschliessendes Hoeflichkeits-73. Fix:
neuer State `TX_73_COURTESY` + Feld `qso.courtesy_73_sent`. Field-Test
BESTAETIGT (16:59 UTC EA2BHE). Tests 764 → 777 gruen.

## 🟢 OFFEN nach v0.95.4 (Liste fuer naechste Session)

### ✅ P1.10 Field-Test BESTAETIGT (Mike 16:56-:59 UTC, EA2BHE Spanien)
QSO mit EA2BHE (echte Station, Locator IN83):
- 16:59:00 RR73 → 16:59:15 EA2BHE 73 → 16:59:30 unser Courtesy-73
- KEIN weiteres 73 von EA2BHE → Auto-Sequence sauber gestoppt
- ✓ QSO komplett, CQ-Modus laeuft weiter

**Pattern bestaetigt:** Courtesy-73 funktioniert mit Standard-FT8-Apps
(WSJT-X, JTDX, MSHV). Echte Stationen weltweit akzeptieren das
abschliessende 73 sauber.

### ✅ IC-7300 Endlos-73 GEKLAERT (Mike 2026-05-05) — KEIN Bug
**Wurzel:** Mike's SDR-Control hatte **Retry=99** in den Auto-Sequence-
Einstellungen (Test-Override). Mit Retry=99 sendet SDR-Control 99× sein
73 wenn keine "QSO-Ende-Bestaetigung" kommt. Das ist **Mike's eigene
Test-Konfiguration**, kein SimpleFT8-Bug, kein SDR-Control-Bug.

**SDR-Control-Verhalten (laut Help-Text vom Entwickler):**
> „Meine App wartet nach RR73 einen Taktzyklus und antwortet, falls
> sie eine weitere 73-Nachricht korrekt empfaengt, ebenfalls mit einem
> 73 — fuer zuverlaessige QSO-Protokollierung."

Das ist **identisch zu P1.10's Courtesy-73-Logik**. Beide Apps machen
also dasselbe Standard-Verhalten. Bei Mike's Retry=99 → 99× 73-Spam.
Bei Standard-Retry (1-3) → max 3 73-Slots, sauberer Abschluss.

**Loesung:** Mike setzt SDR-Control Retry auf Standard (1) zurueck.
Kein Code-Aenderung in SimpleFT8 noetig.

**12000-QSO-Erfahrung erklaert:** Mike hatte Retry=99 erst kuerzlich
fuer Test gesetzt. Vorher mit Standard-Retry und gegen WSJT-X-Stationen
(senden 1× 73, kein Retry) gab es nie ein Problem.

### ✅ P1.9 Field-Test BESTAETIGT (Mike 11:18-:24 UTC, 2 QSOs DA1TST)
QSO 1 (11:19:45 RX → 11:20:00 Report, Replace mit -20).
QSO 2 (11:22:15 RX → 11:22:30 Report, Replace mit -23).
2/2 Replace-Pfad genommen, kein „erster Ruf ignoriert" mehr. Bug tot.

### 🟡 P1.11 — `rr73_retries`-Counter shared (NEU aus Plan-R1 F1, 05.05.)
Bestehender Bug, NICHT durch P1.10 verschaerft. `qso.rr73_retries` wird
in WAIT_RR73 (`qso_state.py:346`) UND in WAIT_73-Hoeflichkeits-Pfad
(`qso_state.py:589-590`) inkrementiert/getestet. Wenn QSO viele
WAIT_RR73-Retries hatte (z.B. 2 von 3), bleibt fuer WAIT_73-R-Report-
Hoeflichkeit nichts uebrig. Fix: separates Feld `wait_73_retries` oder
Reset bei WAIT_73-Eintritt. ~1 Stunde Aufwand, KISS.

### ✅ P1.5 Field-Test BESTAETIGT (Mike 09:35-:44 UTC, 4 QSOs in Folge)
SP6AXW + DA1TST + HA0GK (aus Warteliste) + S50XX alle erfolgreich.
Bekannte Stationen koennen wieder anrufen, Caller-Queue-Pop funktioniert.
P1.5-Symptom „App ignoriert komplett" ist weg.

### 🟡 P1.8 — Report-SNR-Bug `_last_snr` statt `msg.snr` (NEU 2026-05-05)
Wir senden Reports mit schlechteren dB-Werten als wir empfangen
(z.B. DA1TST: wir -23, er R+19 = 42 dB Diff). Wurzel: `_last_snr`
wird fuer jede msg im Slot ueberschrieben → letzte/schwaechste msg-SNR
wird verwendet. Fix: `msg.snr` direkt in `_process_cq_reply` (qso_state.py:
218, 233). Voller V1→V2→R1→V3, NACH P1.9 + P1.10. Siehe TODO.md P1.8.

### ✅ P1.6 — Versionsnummer-Anzeige (ERLEDIGT v0.95.6 / Bundle1)
Color `#333` (auf `#1a1a2e` unsichtbar) → `#666` (lesbar, Theme-konform).

### 🟢 P1.7 — Lokaler Duplikat-Filter ADIF/Logbuch (NEU 05.05.)
Folgebug-Risiko aus P1.5-Fix: bekannte Station < 5 Min nach RR73
erneut anruft → zweites QSO + zweiter ADIF-Eintrag. QRZ.com filtert
serverseitig (REASON=duplicate), aber lokal nicht. Aufgabe: Duplikat-
Check in `log/adif.py` und `qso_log.add_qso` (gleicher Call+Band+Mode
binnen 60 Min → updaten oder skip + Info-Log). ~1 Tag Aufwand, KISS.

### Field-Test offen aus v0.94 (Liste fuer naechste Session)
- **v0.94 KALIBRIEREN-Button im Diversity-Modus** → Phase 2 + Phase 3
  laufen automatisch durch, Cache + 1h-Timer frisch
- **v0.94 Stats-Pause Phase 2 verifizieren** → waehrend DXTuneDialog
  laufen darf KEIN Stats-Logging mehr (~/.simpleft8/simpleft8.log)
- **v0.94 RX-Panel-Hardware-Antenne** → waehrend Phase 2 zeigt RX-
  Panel die Antenne aus _schedule[_step] (ANT1/ANT2 als A1/A2)
- **v0.93 Cache-Reuse beim Bandwechsel innerhalb 1 h** → 5-s-Toast
- **v0.93 FT2-Score-basierte Statistik** bei duenner Stations-Dichte
- **v0.93 1h-Frist** → nach 60 Min ohne QSO/CQ automatischer Re-Measure
- **v0.91 Block 1+2 Pipeline-Dauer messen** (Best-Case ~2:30, typisch ~3:20)
- **Antennen-Drossel-Beobachtung** (Mantelwellensperre 04.05.
  ausgebaut, 8-foermige Schlaufen)

### Code-Refactor offen
- **P2 Reply-Lag durch Audio-Buffer-Latenz** (TODO.md) — nach v0.95
  Display-Fix kann Mike den ECHTEN Reply-Lag am korrekten Slot ablesen.
  Falls Lag dann noch >1 Slot: separater Workflow (Wake-Offset +
  Audio-Buffer-Tuning, hardware-nah).
- **Single-Instance-Lock im App-Code** — robuster Schutz gegen
  Doppelstart (Lockfile vs TCP-Port). Memory:
  `project_v095_single_instance_lock.md`. Aktuell nur Memory-Regel fuer
  Claude (`feedback_app_start_single_instance.md`).

### Wartung
- **~50 neue Statistics-Files** committen (auswertung/ + statistics/
  Output-Files vom heutigen generate_plots-Run plus Decoder-Logs)
- **Stats-Sammlung 5 Tage flaechendeckend** pro Stunde-Modi-Slot
  (laut Memory `project_statistics_strategy.md`)

---

Mike's Field-Test-Befund 05.05.: RX-Panel zeigte waehrend Phase 2
"A1" fuer Station die im DXTuneDialog-Bucket "ANT2 G20" landete.
