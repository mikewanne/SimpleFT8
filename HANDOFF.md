# HANDOFF — SimpleFT8

**Stand 2026-05-05:** **v0.95.2 — CQ-Reply-Bug-Fix (P1.5).**
5-Min-Sperre `_WORKED_BLOCK_SECS = 300` + Methode `_is_worked_recently`
+ 3 Block-Stellen + Eintrag-Stelle in `core/qso_state.py` komplett
entfernt (-22 Zeilen, +0 Code). Mike's Funker-Entscheidung-Linie:
bekannte Stationen duerfen wieder anrufen. Voller V1→V2→R1→V3 Diagnose
+ voller V1→V2→R1→V3 Plan, R1 zwei Mal bestaetigt ohne Halluzinationen.
Tests 756 → 759 gruen (+3). Atomarer Commit `43dd062` + Doku-Commit.

## 🟢 OFFEN nach v0.95.2 (Liste fuer naechste Session)

### 🟡 P1.5 Field-Test ausstehend
Mike testet das DA1TST-Szenario: vorheriges QSO mit RR73, dann gleiche
Station < 5 Min spaeter ruft uns nochmal an. Erwartet: App antwortet
mit Report. Falls Symptom doch noch da ist → die Sperre als Verursacher
ausgeklammert, Diagnose-V4 mit neuen Daten.

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
