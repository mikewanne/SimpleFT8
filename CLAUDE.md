Lies nach dieser Datei sofort auch HANDOFF.md **und HISTORY.md** und bestätige alle drei mit je einer Zeile.

---

# ⛔⛔⛔ DEEPSEEK-ZWEITMEINUNG PFLICHT BEI SCHWIERIGEN PROBLEMEN ⛔⛔⛔

Bei jedem **schwierigen Problem** (Bug-Diagnose, Architektur-Frage, „warum
greift mein Fix nicht?", Race-Condition, mehrere fehlgeschlagene Eigen-Fixes)
→ **IMMER DeepSeek als Zweit-Perspektive einbinden.** Verwerfen kann man die
Antwort hinterher — Nicht-Einbinden ist das Einzige, was nicht rückgängig zu
machen ist. **Merksatz: „2 KIs sehen mehr als eine."**

**Aufruf:** `cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py`
(Model `deepseek-v4-pro` ist Default — DeepSeeks bestes Modell. Verifiziert
29.05.2026: API bietet nur noch v4-pro + v4-flash, alte Namen `deepseek-reasoner`/
`deepseek-chat` existieren nicht mehr. Tool nutzt v4-pro, MCP-Aliase mappen alle
auf v4-pro. Siehe Memory `reference_deepseek_model_verified`.)

**Warum (Mike 11.05.2026):** Mein erster Fix hatte Smoke-Test grün, Mike sah
das Problem trotzdem weiter. DeepSeek lenkte die Aufmerksamkeit sofort auf die
richtige Schicht — ohne diese Zweitmeinung hätte ich lange im falschen Modul
gesucht.

**Trivial-Klausel:** Tippfehler, Umbenennung, <5 Zeilen, pure Refactor ohne
Verhaltensänderung → DeepSeek nicht nötig.
Memory: `feedback_deepseek_always_second_opinion.md`.

---

# ⛔⛔⛔ WORKFLOW-PFLICHT — KEINE AUSNAHME — ABSOLUT VERBINDLICH ⛔⛔⛔

**JEDE Code-Änderung — egal wie trivial sie erscheint — MUSS den vollen Workflow durchlaufen:**

## V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code

**Es gibt NULL Ausnahmen.** Nicht für "nur 5 Zeilen". Nicht für "reine Labels". Nicht für
"offensichtliche Fixes". Nicht für Bugfixes mit klarer Diagnose. Das Projekt ist zu komplex.

→ **Beweis 01.05.2026:** Label-Fix in 2 Dateien ohne Workflow = Mike-Unterbrechung + Regelverletzung
→ **Skill:** `.claude/skills/ft8_workflow.md` — VOR jedem Code aufrufen
→ **Slash-Command:** `/workflow [bug-name]` — startet Skill direkt
→ **Selbst-Check vor JEDEM Tastendruck:** "Habe ich den vollen Workflow durchgeführt? NEIN → STOP."
→ **Verstoss = Vertrauensverlust.** Mike unterbricht, korrigiert, und hat immer Recht.

**Mike-Trigger-Phrasen die den Skill SOFORT laden:**
- „vollen workflow", „kompletten workflow", „voller worflow"
- „workflow mit deepseek", „mit deepseek durch", „deepseek einbinden"
- „ausführlicher plan", „sauber planen", „v1 v2 v3"
- „selbe verfahrensweise", „wie immer", „wie bei P1.X"
- „erst V1 dann zu deepseek", „prompt entwerfen"

**Trivial-Klausel (Workflow NICHT laden):** Tippfehler/Style/Doku/<5 Zeilen.
Vollständige Trigger- und Trivial-Liste: `.claude/skills/ft8_workflow.md`.

---

# ⛔⛔⛔ HARDWARE-WARNUNG — HOECHSTE PRIORITAET ⛔⛔⛔

## ANT1 = TX-Antenne. IMMER. Auf jedem Band.
## ANT2 = NUR Empfangs-Zusatzantenne. NIEMALS TX!

**ANT2 (Regenrinne ~15m) ist NICHT fuer Sendeleistung ausgelegt.** TX auf
ANT2 mit 100 W = **Hardware-Schaden moeglich** (Antennen-Pfad, hochohmige
Last → PA-Schutzschaltung greift, im worst case PA-Schaden am FlexRadio).

### Konsequenz fuer ALLE TX-Modi

| Aktion | Antenne |
|---|---|
| Manuelle CQ-Anrufe | **ANT1** |
| OMNI CQ (passiv) | **ANT1** |
| AUTO HUNT (aktiv) | **ANT1** |
| TUNE-Button | **ANT1** (Tuner-Match) |
| Diversity RX-Pattern (70:30 / 50:50 / 30:70) | beide RX, **TX nur ueber ANT1** |

**Im Code:** Vor jedem TX-Trigger (Encoder, TUNE) muss `radio.set_tx_antenna("ANT1")`
verifiziert sein. Diversity-Pattern darf **nie** ANT2 als TX-Slot vergeben.

**Wenn neue TX-Funktionalitaet gebaut wird** (Auto-Hunt, Hybrid-Modi, was
auch immer): **erste Frage — laeuft TX garantiert ueber ANT1?**
Beantworte das BEVOR du Code schreibst, niemals erst im Test.

---

⛔ **SESSION-LIFECYCLE-WORKFLOW: `docs/SESSION_WORKFLOW.md` v1.2 ist
verbindlich.**

- **Session-Start**: Phase 1 ausfuehren — CLAUDE.md → MEMORY.md →
  HISTORY.md → HANDOFF.md lesen, dann Begruessung mit Stand.
- **Waehrend Arbeit**: Phase 2 — nicht-triviale Aenderungen ueber
  WORKFLOW.md v1.1 (V1→V2→R1→V3), nach jedem Punkt HISTORY+HANDOFF+
  CLAUDE+Memory in dieser Reihenfolge updaten. Trivial-Klausel:
  Tippfehler/Kommentare/<5 Zeilen brauchen kein 4-Datei-Update.
- **Feierabend**: Phase 3 — Verifikations-Check + Bestaetigungs-Block.
- **Notfall-Save**: Phase 2f bei „muss kurz weg".

⛔ **HISTORY.md ZWINGEND beim Session-Start lesen!** — Sie ist die einzige
verlaessliche Quelle dafuer welche Features in welchen Versionen tatsaechlich
implementiert wurden. Wer das ueberspringt, plant Features doppelt (Beispiel
27.04.: V1→V2→V3-Prompt-Zyklus fuer „Live-PSK-Bandindikator" in DeepSeek-
Review entworfen — nutzlose Stunde, weil v0.69 das Feature schon vollstaendig
abdeckt). Bei jedem „lass uns ein Feature X bauen" zuerst grep in
HISTORY.md ob X nicht schon drin ist.

⛔ **PFLICHT NACH JEDEM ERLEDIGTEN FIX/FEATURE (Mike 01.05.2026):**
Reihenfolge VOR der naechsten Aufgabe:
1. **HISTORY.md** anhaengen — `## YYYY-MM-DD vX.YY — Kurztitel` + Eintrag.
2. **HANDOFF.md** updaten (TODO-Punkt raus, neuer Stand rein, Test-Count).
3. **CLAUDE.md** Header updaten (`Aktueller Stand` + Test-Count).
4. **Memory** wenn Lesson gelernt.

> **Hinweis (Mike 10.05.2026):** `FT8/HANDOFF.md` und `FT8/CLAUDE.md`
> sind Symlinks auf die echten Dateien in `SimpleFT8/`. Nur die echten
> Dateien editieren — die Symlinks aktualisieren sich automatisch.
> KEIN Doppel-Update mehr noetig.

Bei Halluzination einer TODO-Liste (Mike 01.05.: ich hatte
`_reset_defaults` als offen vorgeschlagen, war aber in v0.79 schon erledigt)
→ STOP, Code-Verifikation mit `git log --oneline | head -30` + grep gegen
aktuellen Code, BEVOR Workflow gestartet wird.

Memory: `feedback_todo_history_pflicht.md`.

# SimpleFT8 — Claude Kontext

**Trigger „SimpleFT8 am Ferienhaus":** Memory `project_simpleft8_ferienhaus.md`
laden — App via `tools/remote/start_simpleft8_nokill.py` starten (umgeht
`kill_old_instances`-osascript-Self-Kill bei Background-Launch), dann Fenster
auf Display 2 (Position 1024,0) verschieben. Mike macht von dort
Fernwartung — App MUSS auf dem mittleren Bildschirm landen.

**Start:** `cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8" && ./venv/bin/python3 main.py`
**Aktueller Stand:** v0.98.63 (03.06.2026) — **FT4-OMNI sendete 30s statt 15s — Slot-Takt vom Modus-Versatz entkoppelt** (voller Workflow, 2× DeepSeek). Regression aus v0.98.62. Mike-Field (OMNI-CQ FT4): TX nur alle 30s (Log je +30s), **intermittierend** (mal 15s mal 30s, je nachdem ob vorher FT8). Diagnose: Cycle-Timer (`timing.py:43`) leitet den Slot-Takt aus `ntp_time.get_time()` ab — und `get_time()` zog seit v0.98.62 den `_MODE_DELTA["FT4"]=−0.30` mit → `cycle_start` feuerte auf FT4 zu spät (an der Slot-Grenze statt davor) → OMNI-TX (`omni_cq.on_cycle_start`→`encoder.transmit`) landete im aktuellen Slot dessen Sende-Frist (Grenze−0.8) schon vorbei war → Encoder-Drift-Guard (`encoder.py:337`) +2 Slots, Folge-Slot „encoder busy" → 30s. **Schwellenabhängig:** kippt sobald `_correction<0.30` (FT4-effektiv ≤0 → Timer feuert an/nach Grenze); da nur FT8 misst und der Wert um ~0.27–0.45 schwankt, flackerte FT4-OMNI je nach FT8-Messwert. Fix (`core/ntp_time.py`, 1 Funktion): `get_time()` nutzt jetzt NUR die FT8-Basis `_correction` (OHNE `_MODE_DELTA`) → Slot-Takt immer deutlich positiv → deterministisch 15s. `get_correction()` (mit Delta) bleibt für RX-Decode-Shift (decoder:361) + Anzeige → FT4-Empfang/Anzeige zentriert (keine RX-Regression). Physikalisch korrekt (TX am echten Protokoll-Slot; −0.3-TX-Versatz würde uns bei der Gegenstation mit DT −0.3 zeigen). **Kein TX-Antennen-Eingriff, ANT1/ANT2 unberührt** (Encoder nutzt ohnehin reine `time.time()`). DeepSeek R1 (Diagnose+Fix wasserdicht, kein versteckter Pfad) + Final-R1 **PUSH FREIGEBEN** (Schwelle korrekt, Umsetzung exakt, keine Nebenwirkungen, Kaltstart-Edge bestätigt). Tests 2348→**2349** (`test_get_time_uses_effective_correction`→`test_get_time_uses_base_not_delta` umgedreht + neuer `test_slot_takt_invariant_but_rx_diverges`). **✅ Field-Test BESTANDEN (Mike am Radio 03.06.):** FT4-Sende-Takt korrekt (~8s Slot-Intervall, durch QSO bestätigt — kein 30s mehr), FT4-Empfang/DT-Zeiten sehr gut. — **Vorgänger v0.98.62 DT-Korrektur modus-abhängig (FT4-Versatz), ✅ field-validiert** (voller Workflow). FT8-DT um 0, FT4 alle ~−0.3 → der gelernte Wert ist modus-abhängig (FT8 ~+0.29, FT4 ~0; je schneller desto enger). `_MODE_DELTA={FT8:0,FT4:-0.30,FT2:0}` auf `get_correction()`; nur FT8 lernt Basis, FT4/FT2 erben+Delta. DeepSeek Final-R1 fand P171-Migrations-Bug (allnum-Fallback lud FT4=0.045 als falsche Basis ohne FT8-Keys) → gefixt (return bei fehlenden FT8-Keys). **✅ Feld-Test BESTANDEN:** FT4-DT −0.3→~0 (leicht +0.1), Empfang STABIL (11 Stationen, KEIN P168-Decode-Einbruch — Risiko entwarnt), FT4-QSOs liefen (LZ2II, SV7BAY). Offene Mikrojustierung (NICHT akut): optional `_MODE_DELTA["FT4"]` −0.30→−0.20, NUR datenbasiert. R1+Final-R1 **PUSH FREIGEBEN**. Tests →2348. NICHT gepusht. — **Vorgänger v0.98.61 Audio-Mithör-Monitor (🔊-Toggle, Diagnose)** (voller Workflow). Mike-Wunsch: per Ohr prüfen ob Betrieb ist — Gezwitscher hörbar + leere Empfangsliste = App-Problem (nicht leeres Band). Neu `core/audio_monitor.py`: RX-Audio (24k int16 mono) optional auf Lautsprecher; **Decoder unangetastet** (Wrapper `mw_radio._on_rx_audio`, Decoder zuerst); vorallokierter numpy-Ringpuffer (GC-frei, nicht-blockierend im VITA-49-Empfangsthread), sounddevice-Callback, Ausgabe **fest 48k** (×2 sample-and-hold, kein Pitch-Shift — 24k auf macOS nicht überall nativ), Underrun→Stille (read-Index nie über write). `active`=GIL-atomares bool, Lock um Ringpuffer. 🔊-Toggle in `rx_panel` neben NEUE, persistent (`settings["audio_monitor"]`, Auto-Start wenn zuletzt an), Start-Fehler→Button zurück+Info-Zeile, closeEvent→stop. **Reiner RX, kein TX, ANT1/ANT2 unberührt.** DeepSeek R1 (2🔴 48k+Fehler-Rückroll, 3🟠/🟡 Ringpuffer/Underrun/Lifecycle — eingearbeitet) + Final-R1 **PUSH FREIGEBEN** (7 Prüfpunkte, 0 Bugs, keine Races). Tests 2324→**2339** (+15 `test_audio_monitor.py`, Fake-sounddevice). FEATURES §22. NICHT gepusht. — **Vorgänger v0.98.60 P171: DT-Korrektur auf EINEN globalen Wert (nur FT8 misst)** (voller Workflow). Mike: wenige Stationen auf FT4/FT2 verschlechtern die DT; die gelernte Korrektur (~0.26s) ist die konstante FlexRadio-RX-Latenz (VITA-49) → modus-/band-unabhängig (modus-/slot-abhängige Fensterlage liegt separat in `decoder._DT_OFFSETS`). Field-Beweis: fast alle FT4/FT2-Werte matchen FT8, nur FT4_20m=0.0451 war ein 1-Stationen-Artefakt (`_MIN={FT8:3,FT4:1,FT2:1}`). `core/ntp_time.py`: EIN globaler `_correction` (`{"dt_correction_s":0.26}`), gelernt NUR aus FT8 (`update_from_decoded` → `if _mode!="FT8": return False`), FT4/FT2 lesen/No-op; `set_mode`/`set_band` BEHALTEN den Wert (kein Per-Key-Laden); `MIN_STATIONS=3`, Clamp 1.0; Migration alt→global = Median der FT8-Werte in `_load_saved()` (in-memory, kein Import-Write → FT4_20m=0.045-Müll fällt raus); Seed = Hardware-Default 0.26. Entfernt: `_mode_key`/`_load_for_current_key` (Cross-Modus-Fallback P48-B)/per-Modus-`_MIN`/`_MAX_CORR`/`_log_load_dedup`. Decode-Unabhängigkeit geklärt (Korrektur ist KEINE Decode-Voraussetzung). DeepSeek R1 (3🔴 aufgelöst) + Final-R1 **PUSH FREIGEBEN**. Tooling: `deepseek_review.py max_tokens 16K→32K` (v4-pro-Reasoning sprengte das Limit → leere Antwort). Kein TX-Eingriff, ANT1/ANT2 unberührt. Tests 2332→**2324** (entfernte Sonderpfade). **⚠️ Mike: App NEU STARTEN** (Migration baut dt_corrections.json um). NICHT gepusht. — **Vorgänger v0.98.59 P170: Upload-Move mergt bei Namens-Kollision** (voller Workflow). Mike-Field: 205 hochgeladene QSOs blieben in der „neu"-Liste, weil das Verschieben nach `hochgeladen/` bei gleichnamiger Tagesdatei übersprang (11/12 neu-Dateien hatten einen Zwilling in hochgeladen/ — Phase-1-Migrationsfolge; strukturell wiederkehrend, da tägliche Logdateien gleich heißen). Fix `log/adif.py:merge_adif_files(src,dest)`: bei Kollision Records dedupliziert (`(CALL,QSO_DATE,TIME_ON)` = Export-Key) an die vorhandene hochgeladen/-Datei **anhängen**, dann neu-Datei löschen. **Datensicherheit:** dest byte-erhaltend (nur Anhang), `open(...,newline="")` (keine Newline-Übersetzung), striktes utf-8 + `<EOH>`-Check → bei kaputter Datei ValueError, Aufrufer lässt beide stehen; atomar (Temp + os.replace); idempotent. `_handle_qrz_file_results` mergt statt zu skippen. **Die 205 räumen sich von selbst:** App neu starten → 1× QRZ-Upload → Dups → je Datei gemergt, neu/ leert sich. DeepSeek R1 (Datensicherheit) + Final-R1 NICHT FREIGEBEN (Newline-Byte-Erhalt) → behoben → Final-R1b **PUSH FREIGEBEN**. Reine Dateioperation, kein TX-Eingriff. Tests 2324→**2332** (+8 `test_p170_upload_merge.py`, Kollisions-Skip-Test auf Merge umgestellt). NICHT gepusht. — **Vorgänger v0.98.58 P169 Phase 2: mode-genauer Worked-Filter (Call,Band,Mode) + Auto-Hunt-Transparenz** (voller Workflow). „Schon gearbeitet" unterscheidet jetzt die Betriebsart: eine auf 20m FT8 gearbeitete Station ist auf **20m FT4** und **15m FT8** wieder „neu" — NEUE-Filter (RX-Liste) UND Auto-Hunt band+mode-genau. Neuer Index `QSOLog._worked_band_mode: set[(call,band,mode)]` (additiv, alte Indizes bleiben), befüllt in `load_adif` (**effektiver Mode = SUBMODE wenn vorhanden, sonst MODE**, `.upper()`; FT4=MFSK+SUBMODE→„FT4", QRZ MODE=FT4→„FT4", FT8→„FT8"; **leerer Mode NIE indiziert**) + `add_qso(call,band,mode="")`; neue `is_worked_on_band_mode(call,band,mode)` (leerer/None mode-Param→False); `clear()` leert mit. `ui/mw_qso.py:657` Live-`add_qso` gibt `settings.mode` mit (Token-konsistent zum ADIF-Loader). `ui/rx_panel.py` NEUE-Filter band+mode-genau via **Provider-Callback** `set_band_mode_provider(lambda:(settings.band,settings.mode))` (lazy gelesen → eine Quelle, kein Staleness; bewusst gegen kombinierten Setter, vermeidet P102/P114-Sync-Bug-Klasse); kein Provider → call-only-Fallback. `core/auto_hunt.py` Worked-Filter `is_worked_on_band`→`is_worked_on_band_mode`; neues Signal `all_worked=Signal(str,str,int)` **entprellt** (`_all_worked_reported`, Reset NUR start/set_band/set_mode — NICHT pro Pick) → `main_window._on_auto_hunt_all_worked` → `qso_panel.add_info("Auto-Hunt: alle N Stationen auf {Band} {Mode} schon gearbeitet")`; Emit nur wenn vor Worked-Filter Kandidaten da waren. `ui/mw_radio.py:609` `auto_hunt.set_band` jetzt **IMMER** (auch bei inaktivem Auto-Hunt — sonst `_band` stale beim nächsten Start), `on_band_change()` nur wenn aktiv. **Land-Seltenheit bleibt mode-blind** (`_country_count`/`_country_band`/`_compute_priority` unberührt — keine P165-Regression). DeepSeek R1 (6 Findings, alle 🟡/⚪, 0 Blocker — F2 set_band-immer + F4 Debounce-nur-start/band/mode angenommen, F1 Provider→Setter + F3 _apply_filters-Trigger abgelehnt: Callback robuster, RX-Tabelle wird bei Wechsel ohnehin geleert) + Final-R1 **PUSH FREIGEBEN** (0 Bugs/Risiken, Token-Konsistenz+Debounce+keine Races bestätigt). Reine State-/Anzeige-Logik, **kein TX-Eingriff, ANT1/ANT2 unberührt.** Tests 2312→**2324** (+12 `test_p169_phase2.py`; 4 Test-Fakes/Mocks um `is_worked_on_band_mode` ergänzt). **Damit ist P169 komplett (Phase 1 + 2).** NICHT gepusht, Field-Test pending. — **Vorgänger v0.98.57 P169 Phase 1: adif/erfasst/ = einzige Worked-Quelle + ADIF-Import + Migration** (voller Workflow). Mike-Field: Auto-Hunt rief auf vollen Bändern „kein Ruf raus" (Debug-Log `all_worked_on_band` = P165-Filter greift, KEIN Bug); Analyse deckte ADIF-Unordnung auf (Worked-Index las nur 3/8 Ordner, nicht-rekursiv; frische QSOs zählten erst nach QRZ-Upload; 95 Stationen nur in nicht-geladenen Ordnern; doppeltes `adif/adif/`). Fix: EINE rekursiv gelesene Quelle **`adif/erfasst/{neu,hochgeladen,importiert}/`**. Migration `tools/migrate_adif_erfasst.py` (copy→SHA256-verify→delete + Backup-ZIP nach Appsicherungen/, idempotent, Nicht-ADIF bleibt): 75 .adi → 9647 (Call,Band) byte-genau erhalten, Altordner weg, Klassifikation Variante A (Historie→importiert/ = kein Re-Upload, frische→neu/, hochgeladene→hochgeladen/). 8 Code-Touchpoints: `load_directory`/`parse_all_adif_files`/`bulk_import_directory` mit `recursive=`; qso_log+LocatorDB+Logbuch lesen nur erfasst/ rekursiv; `AdifWriter`→`erfasst/neu/`; Upload-Kandidaten = nur `erfasst/neu/`, Move neu/→hochgeladen/; `export_all_records` aus erfasst/ (nur `SimpleFT8_LOG_*`); Diplome via `_all_records`; neuer `QSOLog.clear()` für Import-Reload-ohne-Doppelzählung. **Import-Button** (validieren ≥1 CALL → Kopie nach `erfasst/importiert/` → Index+Anzeige+LocatorDB reload via `adif_imported`); manuelles Kopieren nach erfasst/ wird beim Start ebenfalls erfasst. DeepSeek Migration-R1 (7 Findings → gehärtet) + Final-R1 **PUSH FREIGEBEN** (Upload-Filter wasserdicht, kein Re-Upload der 18k-Historie). Tests 2303→**2312** (+9 `test_p169_erfasst.py`). adif/ gitignored. **⚠️ Mike: App NEU STARTEN** (Migration baute adif/ um). (Phase 2 inzwischen erledigt — v0.98.58 oben.) — **Vorgänger v0.98.56 P168** (FT4 30s→15s Decode-Pfad-Fix, field-validiert QSO SV5AZK 15s-Takt): Mike-Field (2 QSOs, ms-Log): FT4-QSOs doppelt so langsam (unsere TX 30s statt 15s auseinander). FT4 = Zeitspar-Modus → 30s vergrault Stationen. Root Cause: Decoder weckte FT4 0,5s vor Slot-Ende (absolut 14,5s) → Decode ~0,24s NACH Boundary fertig → zu spät für Audio-Start des Folge-Slots (Boundary−0,8, FlexRadio-1,3s-TX-Buffer) → Encoder-Drift-Guard (`encoder.py:337`) sprang +2 Slots (15s) → 30s. Decoder weckt STRUKTURELL nach der Sende-Frist; Decode-Fenster hing an der Weckzeit (`audio_12k[-slot_samples:]`). **⚠️ 1. Versuch (nur `_WAKE_OFFSETS["FT4"]` 0,5→1,5) brach den EMPFANG (0 Decodes 15/20/30m, Field-Crash Mike) → zurückgerollt:** früheres Wecken verschob das gekoppelte Fenster → Signal aus dem ft8_lib-FT4-Sync-Fenster (+2,24 statt +1,24s). **Lehre: WAKE ≠ Fenster-Position ≠ DT.** Echter Fix `core/decoder.py`: 3 Größen ENTKOPPELT — `_WAKE_OFFSETS["FT4"]`=**1,5** (früh wecken) · neuer **`_WINDOW_OFFSETS`** {FT8:2.5,FT4:0.5,FT2:0.3} = Decode-Fenster **slot-ausgerichtet** [Slot−0,5;+7,0] via Helper **`_keep_window`** (end-verankert), Post-Signal-Rest **`_TAIL_PAD_SAMPLES`** (FT4=1,0s) **NACH `_preprocess_audio`** mit Nullen gefüllt (DeepSeek-Gold-Finding: sonst verfälschen Nullen RMS-Norm+Whitening) · **`_DT_OFFSETS` aus `_WINDOW_OFFSETS` abgeleitet** (NICHT _WAKE!) → FT4-DT konstant **1,0** unabhängig von WAKE. FT8/FT2 **bit-identisch** (tail=WAKE−WINDOW=0). DeepSeek Plan-R1 (Gold-Finding übernommen) + Final-R1 **PUSH FREIGEBEN** 0 Blocker; **Halluzination abgefangen** (DeepSeek wollte Parität /15 statt /7.5 — gegen `encoder.py:381` geprüft + verworfen, FT4 alterniert auf 7,5s). Hardware: reine Decoder-Timing-Logik, **kein TX-Eingriff, ANT1/ANT2 unberührt.** Tests 2290→**2303** (+13, `test_p168_ft4_timing.py` inkl. FT4-Positionierungs-Äquivalenz + FT8-Decode-Rundlauf). **Field-Test BESTANDEN (02.06. 10:25 UTC, QSO SV5AZK, TX exakt 15s-Takt, 6 Stationen Empfang). Push-Freigabe Mike ausstehend.** — Vorgänger v0.98.55 **P167 eingeschobenes QSO hing nach 1 Anruf** (Einschub synchron im qso_state-Handler → `_resume_cq_if_needed` überschrieb TX_CALL mit IDLE; Fix `QTimer.singleShot`-Defer), v0.98.54 **Logbuch-Tabelle: Datums-/km-Spalte chronologisch/numerisch sortieren** (`_SortableItem.__lt__` mit `_SORT_ROLE`; Claude-Catch DeepSeek-`super().__lt__` = PySide6 RecursionError → `self.text()<other.text()`; Tests +8), v0.98.53 **Diplome-Erweiterung: WAE + WPX + DXCC-Band-Tiefe + Ein-/Ausblenden** (Diplome-Feature war DXCC/WAC/WAS/WAZ; WAE=`CONT==EU`-Näherung Ziel 70, WPX=`wpx_prefix()` Ziel 300, DXCC-Challenge+5-Band-DXCC; 👁-Toggle pro Karte via `core/awards_prefs.py`; DLD/IOTA bewusst raus; Claude-Catch DeepSeek-WPX-`digit_parts[0]` falsch → kürzerer Teil; FEATURES §19; Tests +23), v0.98.52 **RX-Listen-Doppelklick = harter Auto-Hunt-Stop** (`_on_station_clicked(msg, hard_stop=True)` + Stop-Block oben; P164-QSO-Fenster bleibt sanft), v0.98.51 **Auto-Hunt DX-Scoring** (persönliche Land-Seltenheit aus 18k-Historie > Distanz > Signal; `_compute_priority`-Tupel, `SNR_FLOOR=-26`), v0.98.50 Bug 1 Anchor-Bleed, v0.98.49 Diplome. Ältere Versionen vollständig in **HISTORY.md** (grep nach Version).

→ Vollständige Versionshistorie + Vorgänger-Details: **HISTORY.md** (grep nach Version).


> **Aeltere Versionen sind in `HISTORY.md` archiviert** (nur anhaengen,
> nie loeschen). CLAUDE.md fuehrt nur den aktuellen Stand — Vorgaenger-
> Detailblocks gehoeren in HISTORY. Bei "wie war v0.97.X?" → grep HISTORY.

**Tests-Pflicht:** `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q` muss vor jedem Commit grün sein. Bei nicht-trivialen Änderungen DeepSeek-Review (`tools/deepseek_review.py`) — durch globale §0 + Projektregeln gefordert.


⚠️ **DeepSeek-Workflow Stand 2026-04-28:**

**Direkt-API ist jetzt Default-Werkzeug** (nicht mehr `pal chat`-MCP):
- Helper: `tools/deepseek_review.py` — kein Token-Limit (128K Context)
- Aufruf: `cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py`
- Key in `~/.deepseek_key` (chmod 600, ausserhalb Repo)

**Default-Modell: `deepseek-v4-pro`** (DeepSeeks STÄRKSTES Modell) — Mike-Regel
(28.04. + bekräftigt 29.05.2026): „IMMER das beste Modell, Kosten egal — nie
mal das schnellere." **Verifiziert 29.05.2026** (Memory
`reference_deepseek_model_verified`): DeepSeek-API bietet nur noch v4-pro +
v4-flash; das alte `deepseek-reasoner`/`deepseek-chat` (R1/V3-Namen) gibt es
nicht mehr. v4-pro IST das Reasoning-Modell. Tool-Default + alle MCP-Aliase →
v4-pro.

| Modell | Wann | Antwort-Zeit | Kosten |
|---|---|---|---|
| **`deepseek-v4-pro` (Default, IMMER)** | Alles: Code-Review, Architektur, Race-Conditions, Trade-offs, KISS, auch „triviale" Verifikation | 6-30s | ~$0.005 |
| `deepseek-v4-flash` via `--flash` | NUR explizit für Bulk wo Pro overthinkt — niemals automatisch | 2-5s | ~$0.001 |

**DeepSeek-Antworten IMMER kritisch pruefen** — auch R1 halluziniert
gelegentlich. Bei Widerspruch: Code ist Referenz. V0.74 Bilanz mit V4: 5
echte Findings + 1 Halluzination („Phase haengt ewig" — falsch). R1 sollte
hier praeziser sein (verifiziert Code-Pfade intern), aber Verifikation
bleibt Pflicht.

**`pal chat`-MCP** noch fuer einfache Multi-Turn-Sessions nutzbar
(Continuation-IDs), aber Files-Limit 7077 Tokens — fuer ernste Reviews
immer Direkt-API.

**📊 V4-pro Empirische Bilanz (Stand 15.05.2026, 5 Cycles: Bundle I + J +
P51 + P53 + P55):** 30 Findings, 0 Halluzinationen, 100% verifizierbar.
Lessons-Files entfernt (Mike-Entscheidung 15.05.: V4-pro hat keine
bekannten Schwächen mehr, V3-Schwächen-Liste nicht mehr relevant).
Falls V4-pro je halluziniert → ad-hoc Notiz im jeweiligen Cycle-Memory,
keine zentrale Lessons-Datei.

## ⛔ Projekt-Philosophie (PFLICHT bei Architektur-Entscheidungen!)

**SimpleFT8 ist ein Hobby-Funker-Tool. KEIN Contest-Tool.** Gilt fuer Claude
UND DeepSeek bei jedem Feature-Vorschlag:

- **Zielgruppe:** Hobby-Funker — App starten, ein bisschen FT8/FT4/FT2 funken,
  fertig. Keine Pileup-Jaeger, keine Contest-Operatoren, keine 1000-QSO-Tage,
  keine Stunden-langen Sessions mit komplexer Konfiguration.
- **UX-Prinzip:** Einfache Bedienung > Vollstaendigkeit. Lieber 3 gut funktio-
  nierende Features als 30 die Mike erst lernen muss.
- **Visueller Stil:** Modern — dunkles Theme, Neon-Akzente, weiche Verlaeufe,
  3D-Globus, Live-Diversity-Visualisierung, Antennen-Farb-Coding, glow-Effekte.
  Nicht 90er-Jahre-Funktionalitaets-UI wie WSJT-X / JTDX.
- **NICHT geplant:** Contest-Modi, Multi-Operator, RTTY/CW/SSB, Skimmer-
  Integration, Pileup-Tools, komplexe Filter-Macros, Cluster-Spotting fuer
  DX-Hunting. DeepSeek-Vorschlaege in diese Richtung: ablehnen.

**Prueffrage bei jedem Feature:** „Hilft das einem Hobby-Funker beim Hobby-
Funken?" — wenn nur fuer Power-User / Contester sinnvoll: NICHT umsetzen,
ausgliedern oder verwerfen.

---

## ⛔ Programmier-Leitsaetze (PFLICHT bei jedem Entwurf!)

Gelten fuer Claude UND DeepSeek bei jedem Plan, Prompt, Code. Bei Verstoss:
Mike weist hin, Claude nimmt die Korrektur an.

1. **Overengineering vermeiden.** Vor jeder neuen Klasse/Konfig/Abstraktion
   fragen: „Brauchen wir das wirklich?" Drei aehnliche Zeilen schlagen eine
   verfruehte Abstraktion. KISS schlaegt Eleganz.

2. **Sauber wie ein Chirurg.** Lieber 30 Min laenger im Plan-Mode als 3 Stunden
   nachbessern — schlechtes Design generiert mehr Bugs und Re-Reviews.

3. **Code als Referenz, nicht Annahmen.** Vor V2-Prompts/Plans echten Code
   lesen, Dateipfade + Zeilen verifizieren. Annahmen fuehren zu Halluzinationen.

4. **Mike auf Overengineering hinweisen.** Geht ein Feature einfacher:
   ansprechen, Alternative skizzieren, ihn entscheiden lassen.

5. **V1 → V2 (Self-Review) → DeepSeek → V3 → Plan-Mode → Code** bei nicht-
   trivialen Aenderungen. Kein Skip von Self-Review oder Code-Verifikation.
   „Sauber am Anfang spart 10x Zeit am Ende" (Mike, 2026-04-28).

---

**⚠ Statistik, Auswertung & Diagramme:** ZUERST `auswertung.md` lesen — dort
stehen Methodik, Tabellen-Formate, Code-Vorlagen, der `generate_plots.py`-
Aufruf und das PDF-Layout. Gilt bei jeder „auswerten / Tagestrend / Pooled-
Mean"-Anfrage; Mike-Default ist die stundenweise Tabelle (nicht nur Pooled-Mean).
**Git:** branch `main`, Repo aktiv, Statistics-Daten committed

---

## Kommunikation bei Problemen (PFLICHT)

Wenn ein Bug oder Problem auftaucht, IMMER zuerst eine verständliche Erklärung
auf Deutsch ohne KI-Codes, ohne interne Bezeichnungen (P17, P19, ratio_timestamp
etc.), ohne Fachjargon:

1. **Was passiert** — in normalen Sätzen, so als würde ich es einem Funker
   erklären der kein Programmierer ist.
2. **Was konkret kaputt ist** — ein Satz, klar benannt.
3. **Was ich als nächstes mache** — ein Satz.

Erst DANACH (und nur wenn Mike fragt) technische Details, Dateinamen, interne
Bezeichnungen. Mike will verstehen was los ist, bevor er entscheidet ob er
weitermacht oder eine Pause braucht.

**Schlechtes Beispiel:** „P19 ist Folge von P17 — ratio_timestamp wird in Phase 3
gesetzt, Phase 3 hängt bei DX wegen P17 (Antennen-Switch greift nicht → MESSEN
0/6 → Ratio nie gespeichert)."

**Gutes Beispiel:** „Die App hängt beim Antennen-Vergleich weil sie ANT1 und ANT2
nicht umschaltet. Deswegen wird kein Messergebnis gespeichert, und beim
Neustart fängt sie wieder von vorne an. Ich fixe jetzt den Antennen-Switch."

---

## Empfehlung geben (PFLICHT, Mike-Wunsch 25.05.2026)

Bei JEDER Antwort wo Mike eine Entscheidung treffen muss (Optionen
vorlegen, Trade-offs erklären, „was sollen wir tun?"):

**IMMER eine persönliche Empfehlung dazuschreiben** — mit 1-2 Sätzen
Begründung. Mike möchte nicht nur die Optionen sehen sondern auch
wissen was Claude für richtig hält und WARUM.

**Format:**
```
## Optionen
- A: ...
- B: ...
- C: ...

## Meine Empfehlung
**B** — weil [Grund 1] und [Grund 2]. Bei deinem Setup mit X spricht
das besonders dafür.
```

**Warum diese Regel?** Mike-Worte 25.05.: „du bist so gut du hast
einfach meistens recht is so, muss man ja mal sagen". Mike will keine
neutrale Optionen-Liste, er will Claude's Urteil mit Erklärung.
Verantwortung übernehmen, nicht nur Fakten servieren. Mike bleibt
final-Entscheider — aber Claude soll Position beziehen.

**Wann NICHT empfehlen:** reine Wissens-Fragen („wie funktioniert X?"),
Erklärungen ohne Entscheidungs-Bedarf, eindeutige Faktenchecks.

---

## Rollen

- **Mike (Ideengeber, Tester, Inspirator):** definiert Ziele, testet im Feld, entdeckt
  Ideen und Probleme aus der Praxis, entscheidet bei strategischen Architektur-Fragen
  und über alles was nach außen sichtbar wird (Push, Doku auf GitHub, Releases).
- **Claude (Chef-Programmierer):** verantwortlich für Code-Qualität, Struktur,
  Wartbarkeit, Fehlerfreiheit, Tests. Trifft Code-Architektur-Entscheidungen
  innerhalb des vereinbarten Ziels eigenständig und proaktiv. Bei wirklich
  grundlegenden Weichenstellungen einmal kurz vorlegen, dann umsetzen.

## Commits

Lokale Commits trifft Claude eigenständig wenn ein Schritt logisch in sich geschlossen
ist. Aufteilung **atomar** — pro Refactoring/Feature/Bugfix ein Commit, nicht alles in
einen Mega-Commit zusammenwerfen. Beispiel: Refactoring + neue Tests + Doku =
3 Commits, nicht 1.

`git push` und alles was nach außen sichtbar wird (PRs, Releases, Tags) **nur nach
expliziter Anfrage von Mike**.

## Architektur-Entscheidungen

Folgende Änderungen werden Mike VOR Umsetzung kurz vorgelegt (Plan + Begründung,
dann seine Bestätigung):

- **Modul-Auflösung:** eine Klasse/Datei in mehrere Module splitten
  (z.B. `flexradio.py` in connection/audio/slice aufteilen)
- **Architektur-Pattern-Wechsel:** z.B. von Mixins zu Composition,
  von Singleton zu DI-Container
- **Threading-Modell-Änderungen:** neue Threads, Lock-Strukturen, Async-Migration
- **Eingriffe in produktive Algorithmen ohne Test-Schutz**
  (siehe AP-Lite v2.2: kein End-to-End-Test → kein blinder Fix)
- **Neue externe Abhängigkeiten** (Pip-Pakete, C-Libraries)
- **Breaking Changes** an öffentlichen Schnittstellen
  (Settings-Dateiformat, Statistics-MD-Format, ADIF-Export, JSON-Cache-Schemas)

Alles andere — Helper-Extraktion innerhalb derselben Datei, Bug-Fixes über
mehrere Dateien, neue Tests, Doku-Updates, lokales Refactoring, Optimierungen
ohne Verhaltensänderung — entscheidet Claude eigenständig und meldet im
Anschluss was gemacht wurde.

---

## Architektur & Module (Top-Level)

```
core/      Decoder/Encoder (ft8_lib), QSO-State-Machine, Diversity-Controller,
           DT-Korrektur, Station-Stats, Antenna-Preference, Propagation,
           OMNI-CQ, Auto-Hunt, Locator-DB
radio/     RadioInterface ABC + flexradio.py (SmartSDR TCP + VITA-49)
ft8_lib/   C-Bibliothek (MIT, kgoba) — seit 29.05.2026 VENDORED (kein
           Submodul mehr!). Enthaelt lokale Patches: P150 kMin_score=4 (FT8)
           + FT2-Protokoll. NICHT `git submodule update`. Build: cc -O3
           -dynamiclib → libft8simple.dylib. Backup der alten Submodul-
           Historie: Appsicherungen/2026-05-29_vor_ft8lib_vendoring/
ui/        main_window.py + mw_*.py Mixins (cycle, qso, radio, tx) +
           control_panel.py, rx_panel.py, qso_panel.py, dx_tune_dialog.py,
           direction_map_widget.py
scripts/   generate_plots.py (stats → auswertung/ PNG+PDF DE+EN)
config/    settings.py (Frequenzen, Band-Configs, mode-aware get/save_dx_preset)
log/       adif.py (ADIF 3.1.7 + QRZ-API)
tests/     1727+ automatisierte Regressions-Tests
```

**Wichtige Konstanten in core/ (für Bugfixes):**
- `decoder.py:_WAKE_OFFSETS` (Modul-Konstante) — FT8=2.5, **FT4=1.5** (P168, war 0.5 → 30s-Periode-Bug), FT2=0.3 = wieviele s VOR Slot-Ende der Decode-Loop weckt. **`_WINDOW_OFFSETS`** (P168) = wo das Decode-Fenster VOR Slot-Start beginnt — FT8=2.5, **FT4=0.5** (entkoppelt von WAKE!), FT2=0.3. `_DT_OFFSETS` wird aus **`_WINDOW_OFFSETS`** abgeleitet (`= WINDOW + 0.5` WSJT-X) → FT8=3.0, **FT4=1.0**, FT2=0.8. `_TAIL_PAD_SAMPLES = (WAKE−WINDOW)*12000` (FT4=12000=1.0s, FT8/FT2=0). FT4-Fenster slot-ausgerichtet via `_keep_window` (sonst rutscht Signal aus ft8_lib-Sync → 0 Decodes, P168 1. Versuch).
- `encoder.py:TARGET_TX_OFFSET = -0.8s` (FlexRadio-spezifisch, kompensiert 1.3s TX-Buffer)
- `qso_state.py:MAX_STATION_CALLS = 7` (Hard-Cap WAIT_REPORT) + `MAX_RR73_RETRIES = 5`
- `diversity.py:THRESHOLD = 0.08` (8% → 70:30, sonst 50:50) + `MIN_MEASURE_STATIONS = 5`
- `auto_hunt.py` 10-Min Hard-Cap + Maus-Inaktivitäts-Timeout (5 Min)

**Bekannte UI-Bigfile:** `ui/control_panel.py` (~57 KB — größte UI-Datei).

---

## DT-Timing (Stand 23.04.2026 — validiert)

```
RX: _DT_OFFSETS = _WINDOW_OFFSETS + 0.5 (WSJT-X-Protokoll), abgeleitet/code-erzwungen.
    FT8=3.0 (Window 2.5), FT4=1.0 (Window 0.5), FT2=0.8 (Window 0.3).
    Korrektur konvergiert auf ~0.24s (nur FlexRadio VITA-49 RX-Hardware)
    Stationen zeigen DT ≈ 0.0–0.2 nach Konvergenz
    (P168 02.06.: FT4-Wake 0.5→1.5 für 15s-Periode, ABER DT an _WINDOW_OFFSETS
     gebunden [0.5] nicht an Wake → DT bleibt 1.0; Fenster slot-ausgerichtet,
     sonst 0 Decodes. WAKE/WINDOW/DT sind getrennte Größen!)

TX: TARGET_TX_OFFSET = -0.8s = 0.5 (Protokoll) - 1.3 (FlexRadio TX-Buffer)
    FlexRadio puffert TX-Samples konstant 1.3s vor RF-Ausgabe
    Validiert: 8 Zyklen 0.0s DT am Icom, 20m + 40m getestet

Speicherung: ~/.simpleft8/dt_corrections.json → EIN globaler Wert
    {"dt_correction_s": 0.26} (P171, 03.06.2026). Gelernt NUR aus FT8 (Hardware-
    Latenz ist modus-/band-unabhängig); FT4/FT2 lesen, schreiben nie. set_mode/
    set_band BEHALTEN den Globalwert (kein Per-Key-Laden mehr). _DT_OFFSETS oben
    (modus-/slot-abhängige Fensterlage) bleibt davon getrennt.
```

---

## Gain-Algorithmus & Hard-Limit

- **Ziel:** -12 dBFS RMS (±3 dB Hysterese)
- **Normalisierung:** -18 dBFS RMS nach AGC
- **TX-Power:** Closed-Loop FWDPWR Feedback, `_rfpower_current` (0-100)
- **rfpower pro Band:** `settings.save_tx_power(band, val)` / `get_tx_power(band, default=50)`, Clamp 10–80%
- **Konvergenz-Flag:** `_rfpower_converged` — True wenn stabil, reset bei Änderung/Bandwechsel

---

## DX-Preset System & Cache

- **Mode-aware Keys:** `"20m_FT8"` hat Vorrang vor `"20m"`
- `get_dx_preset(band, mode=None)` / `save_dx_preset(..., scoring="standard"/"dx")`
- **DiversityCache:** 2h Gültigkeit, Key `diversity_cache_{band}_{scoring}`
- **cache.save() NUR in `_on_dx_tune_accepted()`** — NICHT im Cycle-Loop!
- Bei Normal+Standard: Dialog "Vorhandene Daten verwenden oder neu einmessen?" (wie bei DX)

---

## Verzeichnis-Struktur (Dateiablage)

### Kalibrierungsdateien
- **Pfad:** `~/.simpleft8/kalibrierung/`
- `presets_standard.json` → Gain + Ratio für Diversity Standard (pro Band+FTMode)
- `presets_dx.json`       → Gain + Ratio für Diversity DX (pro Band+FTMode)
- **Format Key:** `"40m_FT8"`, Werte: `rxant, ant1_gain, ant2_gain, ant1_avg, ant2_avg, ratio, dominant, timestamp, measured`
- **Klasse:** `core/preset_store.py` → `PresetStore("presets_standard.json")` / `PresetStore("presets_dx.json")`
- **Auto-Migration:** PresetStore verschiebt automatisch alte Dateien aus `~/.simpleft8/` nach `~/.simpleft8/kalibrierung/`

### DT-Korrektur (P171, 03.06.2026 — EIN globaler Wert)
- **Pfad:** `~/.simpleft8/dt_corrections.json`
- **Format:** `{"dt_correction_s": 0.26}` — EIN globaler Wert für alle Modi/Bänder.
- **Gelernt NUR aus FT8** (Hardware-RX-Latenz ist modus-/band-unabhängig; FT4/FT2
  haben zu wenige Stationen → verschlechterten den Wert, z.B. FT4_20m=0.045).
  FT4/FT2 nutzen den Wert, schreiben nie. `set_mode`/`set_band` behalten ihn.
- **Migration** vom alten per-(Modus,Band)-Format automatisch in `_load_saved()`
  (globaler Wert = Median der FT8-Werte, in-memory; Datei wird bei erster
  FT8-Messung ins neue Format überführt). Seed-Kaltstart = Hardware-Default 0.26.

### App-Sicherungen
- **Pfad:** `SimpleFT8/Appsicherungen/`
- Letzte stabile Sicherung: `2026-04-22_stable/`
- DT-Optimierung Backup: `2026-04-23_vor_dt_optimierung_core/` + `_ui/`

---

## Diversity-System

- **`_diversity_in_operate`** — Transition Guard in mw_cycle.py
  - Verhindert dass once-only Code (warmup, CQ-unlock, freq-update) jeden Zyklus läuft
  - Wird in `_enable_diversity()` auf False gesetzt (Reset)
  - Wird True beim ersten operate-Eintritt nach measure
- **THRESHOLD = 0.08** (8%) → 70:30 Ratio; darunter 50:50
- **MIN_MEASURE_STATIONS = 5**
- Median über 4 Zyklen
- Stats-Warmup: 60s nach Band/Modus-/App-Start

### CQ-Frequenz-Algorithmus (v0.59, dynamisch + slot-synchron)
- **Dynamischer Suchbereich** (`min..max(occupied_bins)`) + graduelle
  Lücken-Toleranz `(0,3)→(0,2)→(0,1)→(1,3)→(1,2)`. Score-Formel:
  `gap_width − 100·n_self − 50·n_close − 25·n_near − 0.01·median_distance`.
- **Sticky Gap** bei n_direct<2 + n_in_band<3 + neue Lücke nicht >+50 Hz.
- **Slot-synchroner Such-Trigger** alle ~60s (`_SEARCH_INTERVAL_SLOTS =
  {FT8:4, FT4:8, FT2:16}`).
- **Pro-Slot-Aufruf** `_refresh_diversity_freq_view()` läuft JEDEN Slot
  UNABHÄNGIG von messages-Inhalt — kein `if messages:` Guard hier (P1-Bug
  v0.54-v0.58, fixed in v0.59).
- **`reset()` muss `_current_gap_width_hz=0` und `_search_slots_remaining`
  setzen** — sonst Bandwechsel-Bug.

Detail-Geschichte (v0.58-Sackgasse, Score-Tuning): siehe HISTORY.md.

---

## Cycle-Zeiten

| Modus | Zyklusdauer | RX-Filter |
|-------|------------|-----------|
| FT8   | 15.0s      | 100-3100 Hz |
| FT4   | 7.5s       | 100-3100 Hz |
| FT2   | 3.8s       | 100-4000 Hz |

---

## Statistik-Veröffentlichungs-Regel

- **Push erlaubt:** je Modus ≥ 2 Messtage, Stunden 06–22 UTC verteilt
- **Soll für solide Aussage:** 5 Tage flächendeckend (Solar-Variation glätten)
- **Methodik:** Pooled Mean über alle Zyklen, kein Stunden-Filter
- Aktuelle Zahlen: siehe README + `auswertung/`-PDFs

---

## ⛔ OMNI-TX (PRIVAT — NICHT AUF GITHUB WIE MAN ES AKTIVIERT)

- Aktivierung: Klick auf Versionsnummer → CQ-Button wird "OMNI CQ"
- Status: **DEAKTIVIERT** — Feldtest ausstehend
- GitHub: Feature darf erwähnt werden, NICHT wie aktiviert

---

## Thread-Safety

| Modul | Lock | Was geschützt |
|-------|------|---------------|
| `core/diversity.py` | `threading.Lock()` (`_hist_lock`) | Histogramm-Daten |
| `core/station_stats.py` | `queue.Queue` + Daemon-Thread | File-Writes |
| `core/ntp_time.py` | `threading.Lock()` (`_lock`) | Korrekturwert + Phase |
| `core/antenna_pref.py` | `threading.RLock()` (`_lock`) | _prefs dict (Karten-Render-Pfad) |
| `core/psk_reporter.py` | `threading.Lock()` (`_lock`) | _thread/_stop_event Lifecycle |
| `core/locator_db.py` | `threading.RLock()` (`_lock`) | _calls dict (Decoder + PSK-Worker konkurrent) |

**Karten-Live-Daten-Pfad (v0.66):** Decoder-Thread → `_emit_map_snapshot_if_open`
→ `direction_map_signal.emit(snapshot, band)` → `Qt.QueuedConnection` →
`_on_direction_map_snapshot` (GUI-Thread) → `canvas.update_stations`. Niemals
direkt aus dem Decoder-Thread Widget-Methoden aufrufen — immer ueber das Signal.

---

## Änderungshistorie

**HISTORY.md** — lückenlose Aufzeichnung aller Änderungen, Bugfixes und Features.
- Datei: `SimpleFT8/HISTORY.md` — führt nur die **letzten 30 Versionen**; ältere
  in `history/HISTORY_archiv_NN.md`, ausgelagert per `tools/rotate_history.py`
  (Byte-Verifikation + Backup, bei „wie war v0.9X?" → grep im `history/`-Ordner).
- Regel: **Gelöscht wird nie etwas.** Neue Einträge **OBEN** anhängen (Datei ist
  nach Version absteigend sortiert). Wächst sie über ~40 Einträge →
  `./venv/bin/python3 tools/rotate_history.py --apply` laufen lassen.
- Bei jeder Session: Änderungen oben eintragen (Feierabend-Routine Schritt 3).
- **Versionsnummer IMMER mitführen!** Format: `## YYYY-MM-DD vX.YY — Kurztitel`
  - `APP_VERSION` steht in `main.py` (erste Konstante nach den Imports)
  - Bei neuen Features: Patch-Version +0.01 erhöhen, bei Bugfix-only: unverändert lassen
  - So ist für jedes Appsicherungen-Backup sofort klar, welcher HISTORY-Eintrag dazugehört

---

## ⛔ TODOs gehoeren in TODO.md im Projektverzeichnis (Mike-Anweisung 07.05.2026)

**Regel:** Alle offenen Aufgaben, Bugs, Feature-Wuensche, Folgearbeiten
gehoeren EXKLUSIV in `SimpleFT8/TODO.md` — NICHT in CLAUDE.md, NICHT in
HANDOFF.md (HANDOFF nur „Stand der laufenden Session" + „naechste 1-2
Schritte"). CLAUDE.md ist fuer Architektur, Konventionen, Workflow-Regeln,
Hardware-Warnungen — nicht fuer den Backlog.

- **Naechste Aufgaben + offene Bugs** → `SimpleFT8/TODO.md`
- **Aktueller Stand der Session + naechster Schritt** → `HANDOFF.md`
- **Lueckenlose Aenderungshistorie** → `HISTORY.md`

Bei Doku-Updates: nicht in CLAUDE.md duplizieren was in TODO.md steht.

---

## 📖 ⛔ PFLICHT: FEATURES.md ZUERST LESEN vor Code-Archäologie

**FEATURES.md ist KEIN optionales Nachschlagewerk — es ist das
funktionale Lexikon der App.** Bei jeder „wie funktioniert X?"-
Frage, bei jedem Bug der nicht offensichtlich ist, bei jedem
Feature-Plan: **ZUERST FEATURES.md grep'en**, dann Code lesen.

**Beweis dass es funktioniert (Mike 26.05.2026):**
- §9 „Bandsperre + TUNE-Pipeline" entstand aus Mike-Frage „ist das
  ein Anzeige- oder Mess-Fehler?" — Antwort kam in 2 Min statt 30
  Min Code-Archäologie. Mike: „bei einem Bug schaust du erst da
  rein und siehst ahhh das und das hängt so zusammen".

### 🎯 Lookup-Tabelle (Thema → §)

**Bei Fragen zu diesen Themen ZUERST FEATURES.md §X lesen:**

| Thema / Bug-Schlüsselwort | § | Inhalt |
|---|---|---|
| Diversity DX-Filter, „warum sehe ich starke Stationen", SNR-Threshold | §1 | DX-Filter Mechanik (was wird gefiltert, was nicht) |
| Defer-Familie, P81/P122/P124/P127/P128/P129, Hintergrund-Aktion mitten im QSO | §2 | Pattern-Familie 8 Iterationen + Helper `_qso_active_for_msg_defer` |
| Hash-Marker `<...>` / `<CALL>`, i3-Frame, Special-Event-Calls, Endlosschleife | §3 | P124-Resolution, 2 Marker-Formen, 3 KISS-Guards |
| Debug-Konsole, Ctrl+D, Filter, stdout-Umleitung | §4 | Live-Konsole im Fenster |
| `statistics/`-Verzeichnis, Stats-Format, FIFO-Cleanup, Bandpilot-Cache | §5 | Datei-Format + Pause-Bedingungen |
| DT-Korrektur, `TARGET_TX_OFFSET`, FlexRadio-Buffer 1.3s, FT8-Slot-Timing | §6 | RX-Konvergenz ~0.24s + TX-Offset Multi-Radio |
| Auto-Hunt Call-Validation, „JA" als Call, `looks_like_callsign`, CQ-mit-Richtung | §7 | P136 2-Schichten-Fix (Parser + Validation) |
| **Debug-LOG-Datei** (~/.simpleft8/debug_*.log), Auto-Hunt-Trace, Bug-Reproduktion | §8a | P21/P139 File-Logging-Framework |
| QSO-Ende-Blocker, 60s-Cooldown, „warum verschwindet 73 nach ✓", `_recently_completed_qsos` | §8 | P128/P129/P138-Historie + 2-Zeitfenster-Verhalten |
| **Bandsperre, SWR-Watchdog, TUNE-Pipeline, Phase A/B, `_swr_blocked_bands`** | **§9** | **3-Phasen-Pipeline + Marker-Lifecycle + Stolperfallen** |
| **QSO-Log Zwei-Speicher (`_entries` + `log_view`), Resurrection, Auto-Trim, `clear_log_completely`** | **§10** | **P95+P143 Architektur, wann leeren / wann nicht (Mike-Spec-Tabelle)** |
| **Mode-aware Symmetrie-Pattern** (P102/P114/P135/P141 — Anzeige hängt im falschen rx_mode) | **§11** | **Pattern-Klasse 4 Iterationen + Risiko-Tabelle für andere Funktionen** |
| **Hardware-Sicherheit Pattern** (P53 Watchdog / P76-A / P142 / P153 Median / P154 / **P159 Clamp-1.0-Filter**), Clamp-1.0-Bug, `_swr_blocked_bands`, `_compute_match_swr` | **§12** | **Pattern-Klasse 6 Schichten, Clamp-1.0-Sensor-Eigenheit (exakt 1.0 = kein Träger, aus Aggregation filtern), Marker-Lifecycle, Stolperfallen** |
| Sim-Modus, FakeRadio, SimInjector, `SIMPLEFT8_FAKE_RADIO`, App ohne Hardware testen | §13 | P64 FakeRadio + SimInjector + Safety-Guards |
| Netto-Leistung, graue Zahl in (), FWD·(1−Γ²), „abgestrahlt vs netto" | §14 | P156 Netto-Watt-Anzeige zwischen W und SWR |
| **RX-Liste, Empfangsfenster, Aging, „alte Stationen kleben", `_slot_start_ts`/`_last_heard`, `remove_stale`, `_rebuild_rx_table`, leere Slots** | **§15** | **P157 Stations-Akkumulator + Aging — dict-Projektion, 2 Aging-Trigger, UTC=zuletzt-gehört** |
| **TUNE-Dauer, `tune_duration_s`, Rechtsklick-Override, Auto-TUNE bei Bandwechsel, `auto_tune_on_band_change`, „Band gesperrt — SWR" welcher Pfad, RFPreset-Anker** | **§16** | **4 TUNE-Pfade + Dauer-Quellen, Rechtsklick=Ad-hoc (gewollt), 2 verschiedene gesperrt-Meldungen (TUNE-Median vs Live-Watchdog)** |
| QSO-Fenster-Klick auf Anrufer während Auto-Hunt, Einschub, `_insert_pending_call`, RX-Liste=aktiv/QSO-Fenster=passiv | §17 | P158 wartende Station einschieben + Auto-Resume |
| **Statistik-Diagramme, Modi-Vergleich, „DX zählt nur <-10?", Pooled Mean, fairer date+hour-Vergleich, `generate_plots.py`, alle Modi loggen ALLE Stationen** | **§18** | **Diagramm-Methodik: alle 3 Modi erfassen alle Stationen (DX-<-10 nur Antennen-Ratio), date+hour-gematchter Mehrtages-Vergleich, Erzeugung DE+EN** |
| **Diplome/Awards, DXCC/WAE/WPX/WAC/WAS/WAZ, `compute_awards`, `wpx_prefix` Slash-Logik, DXCC-Challenge/5-Band, Diplom ein-/ausblenden, `awards_prefs`, „warum WAE Näherung", DLD/IOTA gehen nicht** | **§19** | **6 Diplome aus QRZ-Export, WAE=CONT==EU-Näherung (ehrlich), WPX-Präfix-Parser 3 Slash-Formen, DXCC-Band-Tiefe, 👁-Sichtbarkeit über eigene JSON (kein Settings-Durchreichen)** |

### Abgrenzung der 5 Doku-Dateien

| Datei | Zweck | Wann lesen |
|---|---|---|
| CLAUDE.md (DIESE) | Regeln + Architektur + Workflow-Pflichten | Session-Start (immer) |
| **FEATURES.md** | **funktionales Lexikon — wie/warum Code-Pfade verknüpft sind** | **Vor JEDER Bug-Analyse** |
| HISTORY.md | Changelog — WANN was geändert wurde | bei Versions-Recherche / vor Feature-Plan |
| HANDOFF.md | aktueller Session-Stand + nächste 1-2 Schritte | Session-Start (immer) |
| TODO.md | Backlog (offene Bugs/Features mit voller Spec) | Bei „was als nächstes" |

### Pflicht: FEATURES.md NACH nicht-trivialem Bug-Fix updaten

Wenn ich einen Bug fixe der eine **Funktionsverknüpfung neu erklärt**
(z.B. P140 die Trigger-Differenzierung `qso_complete` vs
`qso_confirmed_visual`) → **gehört in FEATURES.md §8 als Update**.
Nicht nur in HISTORY.md. Sonst hat zukünftige Claude-Instanz nur
„WANN" und muss „WIE" wieder ausgraben.

**Trivial-Klausel:** 1-2-Zeilen-Fixes ohne funktionale Architektur-
Erklärung → nur HISTORY.md. FEATURES.md ist für nicht-triviale
Funktionsweisen-Doku.

### Memory-Anker zu Sessions/Pattern-Familien

`~/.claude-account1/projects/.../memory/MEMORY.md` ist Index der
**Cycle-Memories** (jeweils ein Bug-Fix-Workflow dokumentiert mit
V1/V2/R1/V3-Findings). Bei `[[name]]`-Querverweisen aus einem
Memory zu einem anderen kann ich die ganze Pattern-Familie
nachvollziehen. FEATURES.md verlinkt thematisch — Memory chronologisch
+ findings-bezogen.

**Selbst-Check vor jeder Bug-Analyse:**
1. Habe ich FEATURES.md nach dem Thema gegrep't?
2. Habe ich die relevante § gelesen?
3. Falls keine § passt — ist das ein Doku-Lück → später ergänzen?

---

## Bekannte Fallen & Bugs

- **cache.save() nie im Cycle-Loop** — refresht Timestamp → 2h Gültigkeit wird sinnlos
- **_diversity_in_operate vergessen** — once-only Code läuft sonst jeden Zyklus
- **Gain-Messung** — sperrt GUI always-on-top; TX vorher stoppen
- **Stats Warmup** — `_stats_warmup_cycles` an mehreren Stellen in mw_radio.py
- **Statusbar Race** — nach Radio-Connect kurz unsichtbar; Workaround: QTimer.singleShot(200, ...)
- **_r_hline existiert nicht mehr** — ersetzt durch `_chline` in generate_plots.py (nie wieder einbauen)
- **`_tune_active` + `_tune_freq_mhz`** — in `main_window.__init__` initialisiert; `_update_statusbar()` liest beide für `TUNE: xx kHz` Anzeige
- **CQ set_cq_active()** — muss immer wenn `cq_mode=True` aufgerufen werden, nicht nur in CQ_CALLING/CQ_WAIT (sonst bleibt Button nach QSO visuell inaktiv)
- **`_DT_OFFSETS`** (decoder.py, Modul-Konstante, ABGELEITET aus **`_WINDOW_OFFSETS`** + 0.5 — seit P168 NICHT mehr aus `_WAKE_OFFSETS`!) — FT8=3.0, FT4=1.0, FT2=0.8. Die DT hängt an der FENSTER-Position (`_WINDOW_OFFSETS`), NICHT an der Weckzeit. WAKE/WINDOW/DT sind seit P168 (02.06.) drei GETRENNTE Größen: FT4 weckt früh (WAKE 1,5) für 15s-Periode, aber Fenster + DT bleiben kanonisch (WINDOW 0,5 / DT 1,0). 1. P168-Versuch koppelte DT an WAKE (→ 2,0) → Empfang tot. NIE WINDOW>WAKE setzen (tail_pad würde negativ)
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 Fork braucht eigenen Wert
- **dt_corrections.json** — seit P171 (03.06.2026) EIN globaler Wert `{"dt_correction_s": 0.26}` (nicht mehr per-(Modus,Band)). Gelernt nur aus FT8, FT4/FT2 schreiben nie. Migration alt→global (Median der FT8-Werte) in `_load_saved()`. `set_mode`/`set_band` behalten den Globalwert (laden ihn NICHT neu — das wäre das alte Verhalten)
- **_was_cq Bug (gefixt)** — `_on_station_clicked` rief `stop_cq()` VOR `start_qso()` → `_was_cq=False` → CQ resumte nicht nach manuellem QSO; Fix: `_cq_was_active` vor stop_cq() sichern, nach start_qso() als `_was_cq=True` setzen
- **Stats Guard (3-fach)** — `btn_cq.isChecked()` + `cq_mode` + `state not in IDLE/TIMEOUT` → robuster gegen desynchronisierte States
- **Histogramm-/Freq-View Update muss IMMER pro Slot laufen** (v0.59 Punkt 3 / P1-Bug-Fix). Niemals einen `if messages:` Guard um `_refresh_diversity_freq_view()` legen — sonst Counter-Drift, hängende Anzeige, TX-Position veraltet
- **CQ-Such-Periode = 60 s konstant** alle Modi (DeepSeek + WSJT-X-Praxis: < 30 s killt QSO-Aufbau weil antwortende Station auf alter TX-Frequenz fixiert ist)
- **`SWEET_SPOT_MIN_HZ`/`MAX_HZ` Klassenkonstanten gibt's NICHT mehr** (v0.58-Sackgasse, v0.59 entfernt). Falls in altem Code Verweis auftaucht: Suchbereich ist dynamisch, nicht fest
- **v0.75 Auto-Hunt:** `_auto_hunt_timer` ist UNABHAENGIG vom Totmannschalter — Maus/Tastatur reset ihn NICHT (Bot-Tarn-Schutz). Nach jedem Stop ist Pflicht-Restart (User-Klick), kein Auto-Resume in `_reset_presence`. Race-Doppel-Check in `select_next` ist ethische Belt-and-suspenders zur 10-Min-Hard-Cap — NICHT als "redundant" entfernen. `_MAX_ATTEMPTS=3` in `core/auto_hunt.py:45` ist Modul-Konstante OHNE Verwendung in der Klasse (3-Versuche-Logik liegt in `qso_state.py`). `btn_omni_cq` hat aktuell keinen eigenen `clicked`-Handler — OMNI-CQ laeuft weiter ueber bisherige Logik (Phase 2-TODO)
- **v0.81/v0.82 Decoder-Signal-Reihenfolge (Fix D + Fix E):** Decoder emittet 3 Signale pro Slot in dieser Reihenfolge: `cycle_decoded` (Aggregation in `mw_cycle._on_cycle_decoded`) → pro msg `message_decoded` (state-Wechsel via `on_message_received`) → `cycle_finished` (Slot-Ende-Hook via `_on_cycle_finished` → `qso_sm.on_decoder_finished`). REIHENFOLGE NICHT AENDERN — `on_decoder_finished` MUSS nach allen State-Wechseln laufen (Doppel-Report-Bug v0.80/v0.81). `_assign_slot_parity` in `_on_cycle_decoded` setzt `msg._tx_even` BEVOR `on_message_received` es liest (mw_qso.py:85, :423) — `cycle_decoded` muss vor `message_decoded` bleiben.
- **`on_cycle_end` vs `on_decoder_finished`:** `on_cycle_end` laeuft am Slot-START (Timer-Pfad, Decoder-unabhaengig) und behandelt: 3-Min-Gesamttimeout, WAIT_73-Tick, CQ_WAIT-Trigger, Counter-Inkrement, Max-Timeout-Check. `on_decoder_finished` laeuft am Slot-ENDE (Decoder-Pfad ueber `cycle_finished`-Signal) und triggert NUR den Retry-Pfad (WAIT_REPORT/WAIT_RR73 mit `timeout_cycles == 1`). Aufspaltung ist kritisch — wer sie zusammenfuehren will: CQ_WAIT bricht bei Decoder-Hang.
- **FT2-Button versteckt** (`btn_ft2.setVisible(False)` in `control_panel.py`, 2026-05-23) — Standards-Fragmentierung Decodium vs WSJT-X-Improved-FT2. **FT2-Code (decoder/encoder/cycle/protocol) ist intakt** — FT2 = Decodium-Standard (per `core/protocol.py:9`). Reaktivierung: setVisible-Zeile löschen + `freq_frame` zurück auf `grid.addWidget(freq_frame, 0, 4, 1, 3)`.
- **Band/Modus werden nicht persistiert** (2026-05-23, Mike-Entscheidung) — App startet IMMER mit 20m+FT8 (`DEFAULTS` in `config/settings.py:49`). `load()` forciert die Werte beim Start, `save()` schliesst sie vom JSON-Dump aus. Runtime-Updates per `settings.set('band'/'mode', ...)` funktionieren weiter (`mw_radio.py:405/505`) — nur über App-Neustarts hinweg gibt es kein Merken mehr.
- **QSO-Finish-Button (`btn_advance`) versteckt** (`control_panel.py:1199`, 2026-05-23) — Mike: nie gebraucht (FT8-Timeouts MAX_STATION_CALLS=5 + 3-Min-Gesamt fangen stuck-Gegenstationen ab). Code/Signal/Handler intakt; `setEnabled`/`setText`-Calls laufen weiter auf hidden Button ohne Wirkung. HALT bleibt — andere Rolle (Sicherheits-Notbremse). Reaktivierung: `setVisible(False)`-Zeile löschen. QHBoxLayout kollabiert hidden Widget automatisch, kein Layout-Shift nötig.
- **Code-Verträge / Aufruf-Pflichten & Symmetrie-Regeln** (Details + Begründung in FEATURES.md §9–§17 bzw. HISTORY.md grep nach P-Nummer — aus CLAUDE.md ausgelagert 31.05.2026 zum Entschlacken): DXTuneDialog State-Machine (P74-A, `_tune_phase_finished`/`auto_tune_done`-Duck-Typing, AutoTuneDialog NICHT löschen) · rx_mode-Setter-Symmetrie `_refresh_antenna_status_label` (P102) · Stale-Gain-Warning in BEIDEN Bandwechsel-Pfaden, Schwelle >14 Tage (P113) · MODUS+BAND-Status-Sync `_refresh_modeband_status_label` in `_set_mode`+`_set_band` (P114) · RX-Liste/Stations-Dicts nur in 3 Pfaden leeren, KEIN setRowCount(0) bei rx-mode-Switch/Kalibrierung (P115) · Stats-Cleanup FIFO statt Datum (P116) · Band-Aktivitäts-Script standalone + Berliner Zeit (P117/P118) · Auto-Hunt-Stop-Defer `flush_pending_stop` VOR `_flush_auto_hunt_stop_msg` (P122) · **Multi-Radio Hardware-Konstanten** `tx_buffer_s`/`rx_hardware_offset_default_s`/`tune_power_w` je Radio-Klasse, TUNE-Power IMMER über `radio.tune_power_w` (P121, Multiband-relevant — Vertrag NICHT verwerfen).

---

# ⛔⛔⛔ WORKFLOW-PFLICHT — NOCHMAL — LETZTE ERINNERUNG (RECENCY BIAS) ⛔⛔⛔

Du liest das am Ende des Dokuments. Recency Bias sorgt dafuer dass du dich daran erinnerst.

**JEDE Code-Änderung — JEDE — IMMER den vollen Workflow:**
## V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code

**KEINE Ausnahmen. NIEMALS. Das Projekt ist zu komplex fuer Quick-Fixes.**

→ **Skill aufrufen:** `.claude/skills/ft8_workflow.md`
→ **Selbst-Check:** "Workflow durchgeführt?" NEIN → SOFORT STOPPEN.
→ **01.05.2026:** Claude hat Label-Fix ohne Workflow gemacht → Mike-Unterbrechung.
   Genau das DARF NICHT WIEDER PASSIEREN.
