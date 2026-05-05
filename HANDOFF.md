# HANDOFF — SimpleFT8

**Stand 2026-05-05:** **v0.95.4 — P1.10 End-of-QSO Icom-73-Loop-Fix
(Courtesy-73).** Atomare Commits `9783583` (Code+Tests+Workflow-Files,
13 Files, +3439/-14) + Doku-Commit. Wurzel: IC-7300 (DA1TST) Auto-Sequence
wartet auf abschliessendes Hoeflichkeits-73 von uns. SimpleFT8 sendete
bisher kein Courtesy-73 → IC-7300 retried 5× `73` in Folgeslots. Andere
FT8-Apps (WSJT-X, JTDX, MSHV) senden Courtesy-73 als Funkalltag-Standard.
Fix (Option A1 + R1-Slot-Paritaet-Defensive): neuer State
`TX_73_COURTESY` + Feld `qso.courtesy_73_sent` (max 1× pro QSO), Branch
in WAIT_73-Logik (qso_state.py:582-597) + on_message_sent + 3-Min-Timeout-
Ausschluss + mw_qso `_on_tx_slot_for_partner` state-abhaengig (Panel-Info
nur bei CQ-Reply). Voller V1→V2(8 V1-Luecken)→R1(4 KP + 3 Findings)→V3
Diagnose + V1→V2(6 V1-Luecken, D8 Timeout-Liste)→R1(3 wichtige + 3
optionale Findings)→V3 Plan-Workflow. Tests 764 → 777 gruen (+13 neu,
2 angepasst).

## 🟢 OFFEN nach v0.95.4 (Liste fuer naechste Session)

### 🔴 P1.10 Field-Test ausstehend
Mike soll mit DA1TST IC-7300 auf 30m FT8 (oder anderem Band) testen:
- **Erwartung:** Nach unserem RR73 + DA1TST 73 + unserem Courtesy-73
  → IC-7300 sendet KEIN weiteres 73 (oder maximal 1, falls Auto-Seq
  verzoegert).
- **Beobachtung:** Im simpleft8.log sollte erscheinen:
  `[QSO-DBG] [TX] Courtesy-73 für DA1TST: 'DA1TST DA1MHH 73'`
  `STATE WAIT_73 → TX_73_COURTESY` (statt direkt CQ_CALLING).
  Nach Send: `STATE TX_73_COURTESY → CQ_CALLING` + `qso_confirmed`.
- **Mindestens 2 QSO-Reproduktionen** noetig vor Bug-Closure.
- **Field-Test-Beobachtungspunkt R1 KP4:** Decoder/Encoder-Race
  0.2s-Window — falls Overshoot >0.3s häufig, Encoder-Wake auf
  `next_boundary - 1.0s` verschieben (separater Workflow).

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
