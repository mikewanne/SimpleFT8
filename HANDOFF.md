# HANDOFF — SimpleFT8

**Stand 2026-05-05:** **v0.95.3 — P1.9 First-Reply-Lost-Bug-Fix.**
Atomare Commits `20c7fe7` (Code+Tests, +282/-29 in 7 Files) + Doku-Commit.
Wurzel: Decoder-Encoder-Timing-Race (FlexRadio TX-Buffer 1.3s) — Encoder
wachte 0.2-3.0s VOR Decoder fertig → CQ-Audio bereits in send_audio
(BLOCKING) wenn _pending_reply gesetzt wurde → Report 1 Slot zu spaet.
Fix-Kombination (atomar): Decoder-Wake 1.5→2.5 + Encoder request_replace
API + State-Machine try_replace_pending_tx Signal + Defense-in-Depth in
_send_cq + mw_qso Slot-Handler + Connect in main_window:543. Voller
V1→V2(12 Findings A-L)→R1(6 Pruefauftraege KORREKT)→V3 Workflow.
Tests 759 → 764 gruen (+5).

## 🟢 OFFEN nach v0.95.3 (Liste fuer naechste Session)

### ✅ P1.9 Field-Test BESTAETIGT (Mike 11:18-:24 UTC, 2 QSOs DA1TST)
QSO 1 (11:19:45 RX → 11:20:00 Report, Replace mit -20):
  `[Encoder] TX-Replace → 'DA1TST DA1MHH -20'`
  `[QSO] P1.9 Replace OK: CQ → 'DA1TST DA1MHH -20'`
QSO 2 (11:22:15 RX → 11:22:30 Report, Replace mit -23): identisch.
2/2 Replace-Pfad genommen, kein „erster Ruf ignoriert" mehr. Bug tot.

### 🔴 P1.10 — End-of-QSO Icom-73-Loop (NEU 2026-05-05, Diagnose offen)
**Symptom:** Field-Test 11:24-:27 UTC + 11:28-:29 UTC zweimal reproduziert.
Nach unserem RR73 + DA1TST 73 (QSO komplett, ADIF geloggt) sendet der
IC-7300 von DA1TST **5× weiter `73`** in den Folgeslots (alle :15-Slots).
Wir senden CQ → Icom „antwortet" mit 73 → ignoriert von uns. Nach 5 73's
gibt der IC-7300 auf.

**Trace 1 (11:24-:27):**
- :24:00 [E] RR73 → :24:15 [O] 73 (DA1TST) → State WAIT_73 → CQ_CALLING
- :24:30 [E] CQ → :24:45 [O] 73 → ignoriert (CQ_CALLING)
- :25:00 [E] CQ → :25:15 [O] 73 → ignoriert
- :25:30 [E] CQ → :25:45 [O] 73 → ignoriert
- :26:00 [E] CQ → :26:15 [O] 73 → ignoriert
- :26:30 [E] CQ → IC-7300 still
- :27:45 [O] DA1TST JO31 (neuer Anruf) → P1.9 Replace OK ✓

**Code-Pfade verifiziert:**
- `core/qso_state.py:582-586` — `WAIT_73` + `73`-Empfang: `qso_confirmed.emit`
  + `_resume_cq_if_needed` direkt → kein 73 zurueck. Hier liegt der Hebel.
- `core/qso_state.py:419-436` — `on_message_sent` `TX_RR73`: `qso_complete.emit`
  + ADIF + state → WAIT_73. Sauber.
- `core/qso_state.py:447-451` — CQ_CALLING + 73 → log „nach Timeout/CQ ignoriert".

**Mike's Hypothese (zu pruefen):** WSJT-X sendet optional Hoeflichkeits-73
zurueck nach 73-Empfang, IC-7300 wartet darauf. Loesung: 1× Hoeflichkeits-
73 nach 73-Empfang in WAIT_73, mit Counter (max 1× pro QSO).

**Naechster Schritt nach Compact:** P1.10 V1 schreiben.

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

### 🟢 P1.6 — Versionsnummer-Anzeige fehlt
Mike sieht `SimpleFT8 v0.95.2` unten rechts nicht mehr. Code unveraendert.
Trivial-Diagnose ausstehend.

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
