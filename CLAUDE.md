Lies nach dieser Datei sofort auch HANDOFF.md **und HISTORY.md** und bestätige alle drei mit je einer Zeile.

---

# ⛔⛔⛔ DEEPSEEK-ZWEITMEINUNG PFLICHT BEI SCHWIERIGEN PROBLEMEN ⛔⛔⛔

**Mike-Anweisung 11.05.2026 nach P34-Bug-Diagnose:**

Bei jedem **schwierigen Problem** (Bug-Diagnose, Architektur-Frage,
„warum greift mein Fix nicht?", Race-Condition, mehrere fehlgeschlagene
Eigen-Fixes) → **IMMER DeepSeek einbinden als Zweit-Perspektive.**

**Verwerfen kann man die Antwort hinterher** — aber Nicht-Einbinden ist
die einzige Sache die nicht rueckgaengig zu machen ist.

**Merksatz: „2 KIs sehen mehr als eine."**

**Aufruf:** `cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py`
(Model `deepseek-reasoner` ist Default.)

**Konkretes Beispiel 11.05.2026:** Mike-Symptom „Toggle Dynamic AN aber
Statik-Mess laeuft trotzdem" — mein erster Fix hatte Smoke-Test gruen,
aber Mike sah das Problem weiter. DeepSeek-Diagnose hat meine
Aufmerksamkeit auf die UI-Update-Override-Schicht gelenkt (mw_cycle.py
Z.732 ueberschreibt jeden Slot das Panel-Label). **Ohne diese
Zweitmeinung haette ich noch lange im falschen Modul gesucht.**

**Trivial-Klausel:** Tippfehler, Umbenennung, <5 Zeilen, pure Refactor
ohne Verhaltensaenderung → DeepSeek nicht noetig.

Memory: `feedback_deepseek_always_second_opinion.md` (Pruef-Trigger-
Liste, Prompt-Pflicht, Antwort-Umgang).

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
**Aktueller Stand:** **v0.97.45 Session 17.05.2026 — P54-FIX: echte 10W-Closed-Loop-Convergenz beim TUNE, Tests 1415.** Mike-Analyse: P54 (v0.97.44) hatte fälschlich „Slider 10 = 10W" hart für jedes Band gespeichert — Kalibrierungs-Philosophie der `RFPresetStore`-Tabelle kompromittiert. P54-FIX implementiert das eigentliche Konzept: zweiphasiger TUNE mit Closed-Loop in Phase B. **Phase A (`duration_s - 5`s):** Slider=10 fest, Tuner-Match. **Phase B (max 5s):** SWR-Check → wenn OK, `_tune_converge_to_target` iteriert proportional bis FWDPWR≈10W (max 5 Iter, Toleranz 1W). Speichert echten Slider-Wert in `rf_preset_store.save(band, 10, <konvergiert>)`. Plausibilität `rf ∈ [3..50]` — Werte ausserhalb verworfen. `_kruecken_skalierung` als Initial-Startwert: `anchor_rf × (target_w / anchor_watt) × 0.9` (Sicherheits-Faktor gegen nichtlineare PA, Mike-Spec). Krücke nur wenn genau 1 Stützpunkt — Closed-Loop ersetzt sie ab 1. konvergiertem QSO. Voller V1→V2→R1→V3→Code→Final-R1+Round 2 autonom. **R1-V4-pro fand 4 ROT-Bugs:** F1 `set_power` nach `_apply_rf_preset` (State-Sync), F2 Cancel-Race in Convergenz, F3 State-Var Init fehlte, F4 hart-Save war eigentlicher P54-Bug. **Final-R1 V4-pro fand 1 weiteren ROT-Bug:** Re-Entry-Race in `_tune_stop` durch Qt-Sub-Event-Loop (Cancel-Click parallel zum Stop-Pfad → doppelte `tune_off`). Fix: `_tune_stop_active`-Sperre, bei Re-Entry nur `_tune_convergence_cancelled=True`. **Final-R1 Round 2: „PUSH FREIGEGEBEN".** **V4-pro 20-Cycle-Bilanz: 0 Halluzinationen, 3 echte ROT-Bugs gefangen.** APP_VERSION 0.97.44→0.97.45. Tests 1395→1415 (+20 netto: 19 neue P54-FIX-Tests + 14 alte P54-Tests an neue rf-Plausibilitäts-Logik angepasst). Backup `Appsicherungen/2026-05-16_v0.97.44_vor_p54fix/`. **Push pending** bis Mike Field-Test F1-F8 (alle radio-pflichtig).

**Vorgänger:** **v0.97.44 Session 16.05.2026 — P54 Auto-Tune bei Bandwechsel + RFPreset-Stützpunkt (Bundle), Tests 1395.** Mike-Idee: TUNE bei Bandwechsel speichert sofort 10-W-Stützpunkt im RFPresetStore → kein Hochtasten mehr beim ersten QSO. Voller V1→V2→R1→V3→Code→Final-R1 (+Round 2) autonom mit DeepSeek-V4-pro. **P54a:** Settings-Toggle `auto_tune_on_band_change` (Default True), neues `ui/auto_tune_dialog.py` (WindowModal, Spinner, Backup-Timeout, `auto_tune_done`-Signal). Hook in `_on_band_changed` nach `_apply_rf_preset()`. Helper `_start_auto_tune_for_band_change` mit `set_tx_antenna("ANT1")` VOR `tune_on()`. **P54b:** `_on_meter_update` FWDPWR-Sampling erweitert auf `_tune_active`. `_tune_post_swr_check` speichert bei SWR-Good + plausibler FWDPWR (`2.0 < avg < 80.0`) als `rf_preset_store.save(radio, band, 10, 10)` — nominal watt=10 (R1-F1 Klassiker-Catch — V1 hatte fälschlich `watt=round(avg)`). Re-Entry-Schutz in `_on_band_changed` bei `_tune_active=True`. **R1-V4-pro 6 Findings:** F1+F2 ROT (Schlüssel-Korrektur + Signal-Routing statt QMessageBox), F3+F4 ORANGE (Diversity-Resume-Schutz + Timeout-Cleanup), F5+F6 GELB (5 extra Tests). **Final-R1 V4-pro fand 1 ROT-Bug:** State-Sync zwischen `_rfpower_current` und Hardware nach `_apply_rf_preset()` — `radio.set_power(_rfpower_current)` explizit hinzugefügt sonst Power-Spike-Risiko. **Final-R1 Round 2 „PUSH FREIGEGEBEN".** **V4-pro 19-Cycle-Bilanz: 0 Halluzinationen, 2 echte ROT-Bugs gefangen (R1-F1 + Final-R1-State-Sync).** APP_VERSION 0.97.43→0.97.44. Tests 1367→1395 (+28: T1-T24b inkl. Boundary-Grenzen + Source-Level ANT1 + State-Sync). Backup `Appsicherungen/2026-05-16_v0.97.43_vor_p54/`. **Push pending** bis Mike Field-Test F1-F8 (alle Radio-pflichtig).

**Vorgänger:** **v0.97.43 Session 16.05.2026 — P67 Auto-Hunt 5-Min-Maus-Inaktivität (Variante C), Tests 1367.** Mike-Wunsch nach GitHub-Präsentations-Review: zusätzliche Schicht „5 Min ohne Mausbewegung → Auto-Hunt stoppt" parallel zum bestehenden 10-Min-Hard-Cap. Voller V1→V2→R1→V3→Code→Final-R1 autonom mit DeepSeek-V4-pro. **Lösung:** Klassen-Konstante `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300` in `ui/main_window.py`. Neuer State `_auto_hunt_last_mouse_t` in `_init_presence_watchdog`. `_poll_mouse_activity` setzt Anker bei Bewegung (zusätzlich zu bestehendem `_reset_presence`). `_on_btn_auto_hunt_toggled(True)` setzt Anker VOR `start_auto_hunt(600)` (gegen Sofort-Stop bei Default 0.0). `_on_auto_hunt_polling_tick` prüft `monotonic() - _auto_hunt_last_mouse_t > 300` NACH `active`-Guard, VOR Text-Update → `add_info + print + stop_auto_hunt("mouse_inactive_5min")`. Kein `_abort_active_tx` (laufendes QSO darf zu Ende, analog `totmann_expired`). `core/auto_hunt.py:stop_auto_hunt` Docstring + Cleanup-Branch: `mouse_inactive_5min` fällt in DEFAULT-Branch (`_cooldown.clear()` + `_last_tx_even=None`, analog `manual_halt`). **V2-Self-Review** fand 2 Halluzinationen aus V1 (Methodennamen `_init_presence_timer` → `_init_presence_watchdog`, `_on_auto_hunt_toggled` → `_on_btn_auto_hunt_toggled`). **R1-V4-pro** 4 Findings (0 Bug, 2 ORANGE Bestätigung V2, 2 GELB davon 1 angenommen `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S` Naming, 1 abgelehnt Helper-Methode KISS). R1-S7 +3 Tests (T11 Mehrfach-Reset, T12 Race timer+mouse, T13 Reihenfolge-Test). UI-Text Verbesserung „AUTO HUNT-Taste drücken zum Fortsetzen". **Final-R1 V4-pro** 0 KP, 1 GELB akademisch, „Push-Status: FREIGEGEBEN." **V4-pro 18-Cycle-Bilanz: 0 Halluzinationen.** Tests 1352→1367 (+15 P67: T1-T13 inkl. T3b + T8b Regression). APP_VERSION 0.97.42→0.97.43. Backup `Appsicherungen/2026-05-16_v0.97.42_vor_p67/`. **Push pending** bis Mike Field-Test F1-F5 (F1+F3+F5 ohne Radio, F4 mit Radio).

**Vorgänger:** **v0.97.42 Session 16.05.2026 — P66 Logbuch-Tab-Auto-Show + README-Updates (ANT1/ANT2-Korrektur + Stats-Zahlen), Tests 1352.** Mike-Wunsch 16.05.: Wenn man auf Logbuch-Tab wechselt UND eine Zeile ist selektiert, soll Detail-Overlay rechts automatisch erscheinen (statt manuellem Re-Click). Voller V1→V2→R1→V3→Code→Final-R1 autonom mit DeepSeek-V4-pro. Lösung: `_on_qso_tab_changed` um elif-Branch `index==1` erweitert (`logbook._selected_record()` → bei Treffer `_on_logbook_qso_clicked(rec)`). try/except gegen defekte UserRole-Daten (R1-V3 Defensive). R1-V4-pro 5 Findings (0 Bug, 3 Risiko, 2 Verb, 1 Hinweis). Final-R1 „Push-bereit. Keine Regressionen, keine offenen To-dos." 0 KP. **V4-pro 17-Cycle-Bilanz: 0 Halluzinationen.** Plus README-Korrektur (Mike-Hinweis 16.05.): „② TX nutzt aktiv die bessere Antenne" war gefährlich falsch (suggerierte TX-Schaltung zu ANT2). Korrigiert auf „RX nutzt aktiv die bessere Antenne pro Station, TX läuft IMMER über ANT1". Plus Stats-Zahlen aktualisiert: 40m 8-9 Tage/27.200 Zyklen/+126%, 20m 7-9 Tage/19.936/-6%, 30m vorläufig +69%/+59%. Statistiken+PDFs regeneriert (`scripts/generate_plots.py`). APP_VERSION 0.97.41→0.97.42. Tests 1347→1352 (+5: T1-T5 inkl. Exception-Catch). Backup `Appsicherungen/2026-05-16_v0.97.41_vor_p66/`. **Push pending** bis Mike Field-Test F1-F4 bestätigt (kein Radio nötig).

**Vorgänger:** **v0.97.41 Session 16.05.2026 — P52: Statistik-Toggle raus + 90-Tage-Rolling-Window auto-cleanup, Tests 1347.** Mike-Anweisung autonom durchgezogen mit DeepSeek-V4-pro. Settings-Toggle „Statistik-Erfassung aktivieren" hatte keinen Sinn weil Bandpilot ohne Stats blind ist und Auswertungen sie brauchen. Plus: Stats wuchsen unbegrenzt (~1 MB/Tag). Fix: Toggle komplett raus, Stats immer an, `core/stats_cleanup.py` NEU mit `cleanup_stats_older_than_days(stats_dir, days=90)` (rekursiver rglob, zwei Pattern `YYYY-MM-DD_HH.md` + `YYYY-MM-DD.md`, Cutoff aus Dateinamen-Datum NICHT mtime → Backup-robust, fail-silent). `main.py` ruft Cleanup VOR Qt-Init mit Fail-Silent-Wrapper. `Settings.load()` poppt `stats_enabled` idempotent analog P47-Pattern. R1-V4-pro 6 Findings (0 Bug, 3 Risiko bearbeitet, 2 Verb, 1 Hinweis). Final-R1 „Push-bereit, sauber, KISS" mit 1 Anmerkung Pfad-Sync — verifiziert OK. **V4-pro 16-Cycle-Bilanz: 0 Halluzinationen.** APP_VERSION 0.97.40→0.97.41. Tests 1339→1347 (+8 P52: T1-T8 inkl. Migration + Idempotenz). Backup `Appsicherungen/2026-05-16_v0.97.40_vor_p52/`. **Push pending** bis Mike Field-Test F1-F4 bestätigt (kein Radio nötig).

**Vorgänger:** **v0.97.40 Session 16.05.2026 — Bundle-L-Revert: „ohne Radio weiter" wieder Demo-Modus, Tests 1339.** Mike-Klärung 16.05.: Bundle L Punkt B (v0.97.38) hatte `_on_continue_without_radio` auf `QApplication.quit()` umgestellt — beide Buttons im ConnectStatusDialog machten danach exakt dasselbe (UX-Logik-Bug). Mike-Quote: „häää ne eigendlich nicht was macht es für einen Sinn ohne radio weiter - dann ohne radio - dann beenden ???". Plus Crash-Bericht aus Hotfix v0.97.39: bei jedem „ohne Radio weiter"-Klick SIGBUS (Race quit() + _tick_timer). Revert: `_on_continue_without_radio` ruft nur noch `_tick_timer.stop() + self.reject()` (Demo-Modus weiter wie vor v0.97.38). `_on_quit` unverändert mit Hotfix-Reihenfolge (`stop → reject → quit`). Bundle L Punkt A (Display-3-Auto-Move) bleibt — funktioniert. Workflow: V1+V2 + Fragen-Antwort-Iteration mit Mike (Variante A defensiv, Timer-Stop bleibt drin), R1 übersprungen nach Mike-Freigabe (Trivial-Klausel: 4 Code-Zeilen Pure Revert). APP_VERSION 0.97.39→0.97.40. Tests 1339→1339 (T4 invertiert + T7 reduziert auf `_on_quit`, gleicher Test-Count). Backup `Appsicherungen/2026-05-16_v0.97.39_vor_bundle_l_revert/`. **Push pending** bis Mike Field-Test F1+F2 bestätigt (kein Radio nötig).

**Vorgänger:** **v0.97.37 Session 15.05.2026 abends — Intent-Klausel im App-Start-Disclaimer (DA1MHH + MIT-Lizenz + Funklizenz-Verstöße), Tests 1332.** Mike-Vorbereitung für eventuelle GitHub-Veröffentlichung — Belt-and-suspenders zur MIT-Lizenz: Disclaimer-Text im Hardware-Warnungs-Bestätigungsdialog (`main.py:_show_hardware_warning`) durch Mike-Wortlaut ersetzt. Höhe 540×340 → 540×400 (R1-V4-pro-F2: HiDPI-Puffer gegen Font-Substitution). Voller V1→V2→R1→V3→Code-Workflow trotz Trivial-Patch (CLAUDE.md-Pflicht). R1 3 Findings, alle übernommen. **V4-pro 13-Cycle-Bilanz: 0 Halluzinationen.** APP_VERSION 0.97.36→0.97.37. Tests 1327→1332 (+5: 4 neue Intent-Klausel + 1 Bonus + 1 Bundle-J-Test umgestellt von „persönlichen Gebrauch" auf „DA1MHH"/„MIT-Lizenz"). **Push pending** bis Mike visuelle Bestätigung dass Disclaimer-Text nicht abgeschnitten (App-Start ohne Radio reicht).

**Vorgänger:** **v0.97.36 Session 15.05.2026 spätnachmittags — P63 SWR-Block per Band-Marker + Tuner-Settings + Lock-Release, Tests 1327.** Mike-Field-Test 17m-Band: SWR-Watchdog (P53) feuert → 3 Bugs gleichzeitig: (1) Lock hängt → TUNE-Button gesperrt (Mike braucht TUNE zur Diagnostik), (2) OMNI/Hunt klickbar (würden sofort wieder SWR-Alarm), (3) Inkonsistenz. Mike-Spec: Band-Marker pro Band in-memory, blockiert Auto-Pfade, manueller TUNE bleibt klickbar zur Freischaltung. Settings `tuner_present` (Default True) + `tune_duration_s` (15/30s). Manueller TUNE 10W FEST (LDG AT-200 Pro Standard, UNABHÄNGIG von `tune_power`). Voller V1→V2→R1→V3→Code→Final-R1-Workflow mit DeepSeek-V4-pro. V2 fand 12 Findings F1-F12 (z.B. `control_panel.last_swr()`-Halluzination → korrekt `radio.last_swr`). R1 fand 6 weitere F-R1-1 bis F-R1-6, davon 3 kritisch: F-R1-1 Post-Tune-SWR-Race-Condition (2s-Timer statt sofort), F-R1-2 Auto-TUNE-Fehler-Pfad ruft kein Lock-Release (UI hängt), F-R1-5 Pending-Click-Schutz auf rotem Band fehlt. Plus R1-HW: explizites `set_tx_antenna("ANT1")` vor Auto-TUNE. AC1-AC13 alle implementiert. 11 atomare Commits C1-C11. **21 neue Tests** (18 V3-AC + 3 Bonus Source-Level): T1 Lock-Release, T2 Marker-Set, T3 No-Marker-Tuner=False, T4-T6 Toggle-Pre-Checks mit Button-State-Reset, T7 Diversity-Pre-Check VOR _assess_gain, T8 Manueller TUNE auf rotem Band erlaubt, T9 10W FEST Bug-Schutz, T10 Dauer-Whitelist, T11 Watchdog-Bypass, T12 Post-Tune-Good, T13 Post-Tune-Bad, T14 Auto-TUNE-Skip, T15 TUNE-Button-Hide, T18 2s-Timer, T19 Auto-TUNE-Fehler-Pfad, T20 Power-Reset Skip-Branch. Tests 1306→1327 (+21). Backup `Appsicherungen/2026-05-15_v0.97.35_vor_p63/`. **Field-Test F1-F10 pending bei Mike. Push pending bis Field-Test ✓.**

**Vorgänger:** **v0.97.35 Session 15.05.2026 nachmittags — P62 Bandwechsel→Gain-Messung UX-Pause (1s) gefixt, Tests 1306.** Mike-Feedback P60-F6 vormittags: Bandwechsel auf neues Band ohne Preset → Gain-Mess-TUNE startet direkt nach TX-Stop → visuell „80W → 10W" statt „TX aus → neue Messung". DeepSeek-V4-pro hat P62 als beste Aufgabe für autonomen 30-Min-Slot ausgewählt (niedriges Risiko, Mike-Spec klar). Fix: 1s `QTimer.singleShot` vor `_start_dx_tuning` in `_check_diversity_preset` stale/missing-Branch. `_set_gain_measure_lock(True)` SOFORT (sperrt UI), Statusbar-Hinweis „TX gestoppt — Gain-Messung startet in 1s ...". Race-Schutz via existierender `_gain_measure_locked`-Guard in `_on_*_changed` — kein Token-Pattern nötig (R1-bestätigt). KALIBRIEREN-Button ohne Pause (User-Action). Lock-Release lückenlos via `_on_dx_tune_accepted`/`_on_dx_tune_rejected`. R1-V4-pro 0 Findings „Push freigegeben (V3-Phase OK)". Final-R1 V4-pro 0 KP „Push freigegeben". **V4-pro 11-Cycle-Bilanz: 0 Halluzinationen.** 5 atomare Commits. 6 neue P62-Tests T1-T6 + 2 alte P1-Cache-Tests angepasst (QTimer.singleShot gemockt). Tests 1300→1306 (+6 netto). Backup `Appsicherungen/2026-05-15_v0.97.34_vor_p62/`. **Field-Test F1-F5 pending. Push pending bis Field-Test ✓.**

**Vorgänger:** **v0.97.34 Session 15.05.2026 mittags — Bundle K + P61 + P60 + P58 ERLEDIGT + alle Field-Tests ✓, Tests 1300.** Bundle K Field-Test ✓ (F1+F2+F4+F6 explizit). **P61 Field-Test ✓** Mike-O-Ton „autohunt ruft andere station, vorherige qso wurde korrekt abgearbeitet" — Kern-Bug-Fix bestätigt. **ALLE 4 fertigen Bundles (P58/P60/P61/Bundle K) push-bereit.** Plus ältere pending Bundles (P51/P53/P55/Bundle F-J) im Alltagsbetrieb bestätigt. Push freigabe-bereit auf Mike-Anfrage. Zwei UI-Tweaks aus Mike's Field-Test-Beobachtungen 15.05. morgens: (P57) SWR-Limit nur in 0.5-Schritten 1.5..5.0 wählbar, neue QComboBox statt QDoubleSpinBox verhindert freie Tastatur-Eingabe wie 1.7. Snap auf nächst-höheren Wert (sicherer: schärferes Limit), `print()` bei Snap zeigt Mike die Änderung im Terminal. (P59) `_mode_btn_style` Active-Block von rot/gelb auf grün analog `_omni_btn_style` — wirkt auf btn_cq + btn_auto_hunt → alle 3 Aktiv-Buttons (CQ/OMNI/Auto-Hunt) einheitlich grün. R1-V4-pro 0 Findings „Push freigegeben (V3-Phase OK)". Final-R1 V4-pro 0 KP „Push freigegeben". **V4-pro 10-Cycle-Bilanz: 0 Halluzinationen, 100% verifizierbar.** 5 atomare Commits. 11 neue Bundle-K-Tests T1-T8 (+T3a/b/c/d). Tests 1289→1300 (+11). Backup `Appsicherungen/2026-05-15_v0.97.33_vor_bundle_k/`. Field-Test F1-F6 pending. **Vorgänger:** v0.97.33 P61 Auto-Hunt Recent-QSO-Cooldown — Code fertig, Field-Test F1-F7 ebenfalls pending. **Push pending bis beide Field-Tests ✓.**

**Vorgänger:** **v0.97.33 Session 15.05.2026 mittags — P61 Auto-Hunt Recent-QSO-Cooldown gefixt, Tests 1289.** Mike-Field-Test 15.05. morgens (Screenshot): Auto-Hunt picked HA8RC **30 Sekunden** nach abgeschlossenem QSO erneut → 89s verschwendetes 2. QSO → Funkverkehr-Etikette-Verletzung. Existierende `qso_log.is_worked_on_band`-Filterung versagte aus unbekannten Gründen (Race Decoder/Encoder oder ADIF-Exception). **Fix:** Belt-and-Suspenders Cooldown-Schicht direkt in `AutoHunt` mit Key `(base_call, band, mode)`. Konstante `_RECENT_QSO_COOLDOWN_S=300` (5 Min analog `_LOG_DEDUP_WINDOW_S` aus P1.7). Neue Methoden `set_mode()`, `mark_pick()`. Filter VOR `_cooldown`-Check mit Lazy-Cleanup. `mark_pick` SOFORT in `mw_cycle._run_auto_hunt` nach erfolgreichem `select_next` (primärer Race-Schutz) + redundant in `on_qso_complete` (manuelle QSOs). Key-Design: selbes Call auf anderem Band/Mode sofort pickbar (Hobby-Praxis). Mode-Verkabelung in `mw_radio._on_mode_changed` + `main_window.__init__`. R1-V4-pro 7 Findings (1 ROT F1 Mode-Awareness, 2 ORANGE F2+F4, 1 GELB F3 abgelehnt, 1 OK F5, 1 Coverage F6, 1 GELB F7 abgelehnt) — alle bearbeitet/begründet. **V4-pro 9-Cycle-Bilanz: 47 Findings total, 0 Halluzinationen, 100% verifizierbar.** Final-R1 V4-pro „Push freigegeben." 0 KP. 10 neue P61-Tests T1-T10. Tests 1279→1289 (+10). Backup `Appsicherungen/2026-05-15_v0.97.32_vor_p61/`. Push pending bis Field-Test F1-F7. Mike-Field-Test P55-F6: OMNI während TX-Slot per Toggle gestoppt → 15s-Slot lief komplett durch. Code-Audit: gleicher Bug in **3 User-Stop-Pfaden** (OMNI/Auto-Hunt/Normal-CQ Toggle). Alle 3 riefen nur State-Stop (Flags) ohne `encoder.abort + ptt_off`. **R1-V4-pro-F1 ROT (Klassiker-Catch):** Zusätzlich `_pending_station_click` (Click-Puffer wenn User während TX Station klickt) muss in den Stop-Pfaden geleert werden — sonst startet er nach tx_finished ein ungewünschtes QSO. HALT-Button (`_on_cancel:327`) hatte das schon richtig, neue Pfade nicht. **Fix:** zentraler Helper `_abort_active_tx()` in mw_tx.py (encoder.abort + ptt_off + clearing). Genutzt von 3 User-Stop-Pfaden + HALT-Refactor. SWR-Watchdog behält eigenen Block + bekommt F3-1-Zeiler (Konsistenz). **Tests 1268 → 1279 (+11 P60).** Final-R1 V4-pro „PUSH FREIGEGEBEN" + F3-Empfehlung eingebaut. **V4-pro 8-Cycle-Bilanz: 40 Findings, 0 Halluzinationen, 100% verifizierbar.** F1 war Klassiker-Catch — V4-pro hat einen Bug entdeckt den V2-Self-Review übersah. Backup `Appsicherungen/2026-05-15_v0.97.31_vor_p60/`. Push pending bis P60 Field-Test F1-F6.

**Vorgänger:** **v0.97.31 Session 15.05.2026 vormittags — P58 SWR-Limit Save-Hook Live-Propagation gefixt, Tests 1268.** Mike-Field-Test P53 morgens: SWR-Limit in Settings auf 1.5 gespeichert während App lief → Watchdog griff NICHT (Setter wurde nicht aufgerufen). Erst nach App-Neustart funktionierte alles. Wurzel: P53 hatte Live-Propagation INLINE in `settings_dialog._save_and_close:680-683` gebaut — alle anderen Live-Settings (`tx_audio_level`, `set_power`) werden aber NACH `dialog.exec()` im MainWindow propagiert. Fix: Inline-Pfad raus, set_swr_limit in `main_window._on_settings_clicked` analog zu den anderen Settern. R1-V4-pro-F1: alle 3 Setter unter gemeinsamen `if self.radio.ip:`-Guard gruppiert (Wartbarkeit). 5 atomare Commits (C1 settings_dialog raus, C2 main_window neu, C3 Tests, C4 APP_VERSION+Backup, C5 Doku). Tests 1262→1268 (+6: 6 neue P58 T1-T6 + 1 angepasstes P53-T10). Final-R1 V4-pro „PUSH FREIGEGEBEN, 0 Findings". **V4-pro 7-Cycle-Bilanz: 35 Findings total, 0 Halluzinationen, 100% verifizierbar.** Plus dieselbe Session: DeepSeek-Lessons-Files entfernt (Mike-Entscheidung — V3-Schwächen-Liste nicht mehr relevant, V4-pro hat 0% Hallu). Plus 5 neue TODO-Bugs aus Field-Test eingetragen (P57 SWR-Schritte, P58 ERLEDIGT jetzt, P59 CQ-Button grün, P60 Stop-Pfade Slot-Abbruch, P61 Auto-Hunt-Dup). Backup `Appsicherungen/2026-05-15_v0.97.30_vor_p58/`. Push pending bis P58 Field-Test F1-F3.

**Vorgänger:** **v0.97.30 Session 15.05.2026 morgens — P55 Easter-Egg + Diversity-CQ-Code-Leichen entfernt, Tests 1262.** Mike-Spec nach Screenshot-Analyse: Diversity = nur OMNI CQ (kein versteckter Normal-CQ), Easter-Egg-Funktion komplett raus, Normal-Modus = plain FT8 ohne Extras. Voller V1→V2→R1→V3-Workflow autonom mit DeepSeek-V4-pro. **R1-V4-pro: 5 Findings (1 Bug rot F1 — `core/auto_hunt.py` in V2-Datei-Liste vergessen, 3 Doc-String-Verweise auf easter_egg_off; 1 Risiko F2 fragile Zeilennummern; 1 Verbesserung F3 AC1 unklar; 2 Hinweise F4 Smoke-Test + F5 starre Tests), 4 angenommen + 1 Doku-Akzeptanz, Halluzinations-Rate 0/5.** **Code-Removal in 8 atomaren Commits:** C1 `main_window.py` (_on_easter_egg_toggle-Methode + _easter_egg_active + Signal-Connect + _update_button_visibility simplifiziert auf 2-Wege ohne Override), C2 `control_panel.py` (easter_egg_toggle_clicked-Signal + _omni_active-Flag + _version_label.setCursor/mousePressEvent + _on_cq_clicked/set_cq_active OMNI-Branches raus — btn_cq ist jetzt reiner Normal-CQ-Button), C3 `mw_radio.py` (5× _easter_egg_active-Verweise raus, hasattr-Gates obsolet), C4 `core/auto_hunt.py` (R1-F1 — 3 Doc-String-Verweise auf easter_egg_off-Reason, Listen aktualisiert mit rx_mode_change + superseded), C5 3 bestehende Tests bereinigt, C6 13 → 6 neue Source-Level-Tests T1-T6 in `tests/test_p55_easter_egg_removed.py` (T1 rekursiver grep mit `_strip_comments`-Helper, T6 R1-F1-Coverage), C7 APP_VERSION-Bump, C7b Final-R1-Nachfass — 8 irreführende Doku-Kommentare in 4 Files aktualisiert ("nur via Easter-Egg sichtbar" → "sichtbar in Diversity"). **Final-R1 V4-pro „PUSH uneingeschränkt freigeben." 0 KP.** **V4-pro 5-Cycle-Bilanz:** Bundle I + J + P51 + P53 + P55 = 30 Findings total, 0 Halluzinationen, **100% verifizierbar**. Tests 1258 → 1262 (+4 netto: -2 parametrize, +6 P55-Regression). Backup `Appsicherungen/2026-05-15_v0.97.29_vor_p55/`. Push pending bis Field-Test F1-F8.

**Vorgänger:** **v0.97.29 Session 14.05.2026 abends — P53 SWR-Live-Watchdog (Hardware-Sicherheit), Tests 1258.** Mike-Field-Test 14.05.: nasse Antenne nach Regen → SWR>30 bei 70W, `swr_limit` (3.0) aus Settings hat NICHT gegriffen weil (1) SWR-Check lief nur vor Gain-Messung, (2) `swr_alarm`-Signal feuerte aus VITA-49 aber Handler stoppte nichts, (3) Settings-Wert nirgends an FlexRadio propagiert (hardcoded 3.0). Voller V1→V2→R1→V3-Workflow autonom mit DeepSeek-V4-pro. **R1-V4-pro: 4 Findings (2 Bug rot F1+F2, 2 Risiko F3+F4), alle 4 angenommen, Halluzinations-Rate 0/4.** Architektur-Korrektur zur TODO-V0-Spec: statt neuem QTimer-200ms-Polling reagiert Watchdog auf bestehendes `swr_alarm`-Signal (VITA-49-Meter-Loop) — KISS. **Code:** `radio/base_radio.py` Default-Pass-Stub `set_swr_limit`. `radio/flexradio.py` Setter mit Clamp `[1.5, 10.0]`. `ui/main_window.py` `_swr_spike_count=0` + `_swr_first_alarm_t=0.0` explizit initialisiert (F2-Fix). `ui/mw_radio.py` nach `swr_alarm.connect()` ruft `radio.set_swr_limit(settings.swr_limit)`. `ui/mw_tx.py:_on_swr_alarm` **Komplett-Rewrite**: Pre-Check (`encoder.is_transmitting`) gegen Pre-TX-Alarm aus `ptt_on()` Z.957, Spike-Schutz 2 Alarms innerhalb 500ms via `time.monotonic`, Reset spike_count=0 SOFORT vor Stop-Calls (gegen 3. Alarm in Qt-Queue), Stop-Block antennen-neutral (`encoder.abort` → `ptt_off` → `qso_sm.stop_cq`/`cancel` → `cp.set_cq_active(False)` → `_omni_cq.stop("swr_block")` → `_auto_hunt.stop_auto_hunt("swr_block")` → `qso_panel.add_info("⚠ TX abgebrochen — SWR X.X")` → `QMessageBox.warning`), `add_info` VOR Modal weil Modal Event-Loop blockt, kein Auto-Resume. `ui/settings_dialog.py:_save_and_close` Save-Hook `parent.radio.set_swr_limit()` wenn `parent.radio.ip`. **Aus Scope:** TUNE-Pfad (P54), eigener QTimer (verworfen), Cooldown (Modal blockt). **Final-R1 V4-pro „PUSH empfohlen — FINAL-R1 freigeben." 0 KP**, ANT1-Pflicht + KISS + Thread-Safety explizit bestätigt. **7 atomare Commits** (C1 radio setter, C2 main_window init, C3 mw_radio connect-hook, C4 mw_tx handler, C5 settings save-hook, C6 APP_VERSION, C7 13 Tests NEU T1-T13). **V4-pro Lessons P53 (4. Anwendung):** F1 klassisch (ABC-Status-Check), F2 sehr stark (AttributeError-Bug bei Mixin ohne zentralen Init). Halluzinations-Bilanz nach 4 Cycles: **25 Findings total, 0 Halluzinationen, 100% verifizierbar**. Tests 1245→1258 (+13). T5 ist Hardware-Pflicht-Test (`set_tx_antenna` NIE im Stop-Pfad). Backup `Appsicherungen/2026-05-14_v0.97.28_vor_p53/`. Push pending bis Field-Test F1-F7.

**Vorgänger:** **v0.97.28 Session 14.05.2026 abends — P51 Gain-Messung vereinheitlichen (1 Messung, 2 Auswertungen), Tests 1245.** Mike-Beobachtung 14.05.: 20m FT8 hat Std 10/10 vs DX 20/10 weil aus unterschiedlichen Mess-Sessions. Voll-autonom V1→V2→R1→V3-Workflow mit DeepSeek-V4-pro. **R1-V4-pro: 9 Findings (1 Bug rot, 4 Risiko, 2 Verbesserung, 2 Hinweis), 6 angenommen 3 abgelehnt mit Begründung** (F3 Variablen-Zweck-Missverständnis, F5 Normal-Pfad separat, F9 KISS). **Bug F1 (Code-Realität-Check):** Mike's V2 sagte „18 Zyklen", Code hat tatsächlich `ROUNDS=2 × 2 Antennen × 2 Gain-Stufen = 8`. P51 spart trotzdem 50% (vorher 2× 8 = 16, jetzt 1× 8). **Risiko F4 (kritisch):** Fallback `r.get("standard", r)` würde DX-Store mit Std-identischen Werten korruptieren → V3 ändert auf `has_dual = isinstance(r.get("standard"), dict) AND isinstance(r.get("dx"), dict)`, Single-Store-Fallback wie pre-P51 bei altem Format. **Code:** `ui/dx_tune_dialog.py` Helper `_best_for(ant, use_snr) → dict` + `_build_scoring_result(use_snr) → dict`, `_finish` baut `_results` mit Sub-Keys `"standard"`+`"dx"` + Top-Level-Spiegel des aktiven Modus (Backwards-Compat für `set_rfgain`). `_update_results_display` markiert `←(Std)`/`←(DX)`/`←(Std+DX)` pro `(ant, gain)`. Neues `mode_label` „Misst gleichzeitig für Standard- und DX-Modus". `ui/mw_radio.py:_on_dx_tune_accepted` Dual-Save mit Fallback. `settings.save_dx_preset`-Aufrufe komplett raus (R1-F6: tote API, grep bestätigt). **Final-R1 V4-pro „Push freigegeben." 0 KP**, 3 INFO (Kommentar-Drift „12 Einträge" auf 8 gefixt, 2 by-design). **8 atomare Commits** (C1 dx_tune_dialog Helper, C2 dx_tune_dialog finish/display, C3 mw_radio Dual-Save+save_dx_preset raus, C4 mw_qso-evtl, C5 main.py APP_VERSION+Bundle-J-Test-Bump, C6 Tests NEU, C7 Doku, C8 Plan-Files). **V4-pro Lessons P51:** F1 klassisch (Code-Realität-Check), F4 sehr stark (Daten-Korruptions-Pfad gefunden), Halluzinations-Rate 0/9. Tests 1235→1245 (+10). Backup `Appsicherungen/2026-05-14_v0.97.27_vor_p51/`. Push pending bis Field-Test F1-F7.

**Vorgänger:** **v0.97.27 Session 14.05.2026 spätnachmittags — Bundle J (Connect-Modal-Branding + SimpleHelpDialog + RX-Label + Intent-Klausel), Tests 1235.** Mike-Klärungsgespräch nach Bundle I: 4 UI/Doku-Tweaks als gemeinsames Bundle eingespielt, voller V1→V2→R1→V3-Workflow autonom mit DeepSeek-V4-pro. **R1: 7 Findings (0 Bug, 2 Risiko, 4 Verbesserung, 1 Hinweis), 5 angenommen 2 abgelehnt mit Begründung (F2 Overengineering-Vorwurf gegen Mike's explizite Konsistenz-Spec abgelehnt, F7 setFixedSize-Plattformrisiko KISS-akzeptiert).** Final-R1 V4-pro „Push freigegeben." 0 KP (2 Verbesserung-Hinweise akademisch). **Code:** `main.py` APP_VERSION 0.97.26→0.97.27 + Disclaimer-Text + setFixedSize 540×340. `ui/connect_status_dialog.py` Konstruktor-Param `app_version` + Footer-Label `SimpleFT8 v{APP_VERSION} · MIT License` unten rechts (5-7 Sek sichtbar) + setFixedSize 352×196. `ui/simple_help_dialog.py` NEU — `SimpleHelpDialog(QDialog)` + `show_simple_help`-Helper, 700×600 resizable, QTextBrowser+Scrollbar, WindowModal, vollständiges Stylesheet (Hintergrund/Text/Border/QPushButton/QScrollBar). `ui/settings_dialog.py` Module-Top-Import + `_make_info_btn` Z.60 + `_show_bandpilot_help` Z.381 umgestellt. `ui/mw_qso.py` `_antenna_pref_label` ANT2-Zweige mit RX-Prefix (`(RX: ANT2 ↑X.X dB)` bzw. `(RX: ANT2)` bei delta<0.05 — R1-F5). `ui/mw_radio.py` Lazy-Import `from main import APP_VERSION`. **8 atomare Commits geplant** (C1 main APP_VERSION+Disclaimer, C2 connect_status, C3 mw_radio app_version, C4 simple_help_dialog NEU, C5 settings_dialog, C6 mw_qso RX-Label, C7 Tests + 1 alter Test-Fix, C8 Doku/Plan-Files). **V4-pro Lessons Bundle J:** Halluzinations-Rate 0/7, Finding 5 (delta_db=0) klassische Defensive die Claude übersehen hätte. Mike-Spec-Begründung wird respektiert (kein Insistieren bei F2). Backup `Appsicherungen/2026-05-14_v0.97.26_vor_bundle_j/`. Push pending bis Field-Test F1-F7.

**Vorgänger:** **v0.97.26 Session 14.05.2026 nachmittags — Bundle I (Settings-Spacing + QSO-Reihenfolge + OMNI-Race-Stop), Tests 1220.** Mike-Field-Test 14.05. nachmittags brachte 3 Befunde: (1) Settings „Sichtbare Bänder" gedrungen trotz Bundle D, (2) `✓ QSO komplett` vor Courtesy-73 sichtbar (zu früh — Mike: „wenn wir IMMER das 2. 73 senden, dann zeig die Bestätigung danach"), (4) OMNI-CQ-Race: OMNI aus aber 1 weiterer normaler CQ wird gesendet beim Mode-Wechsel. **Voller V1→V2→R1→V3-Workflow** mit DeepSeek-V4-pro Erstnutzung (Migration heute Abend abgeschlossen). V4-pro fand 5 Findings, davon Finding 1 (Bug rot) Kernursache: `qso_sm.stop_cq()` allein reicht nicht — `encoder.abort()` + `ptt_off()` nötig damit kein armed Slot durchrutscht. Final-R1 (V4-pro) „Push freigegeben" 0 Findings. **Code:** `ui/settings_dialog.py` Spacing 10→16 + Margins (12,8,12,10)→(16,16,16,16) + Stylesheet `QCheckBox::indicator 18×18` lokal auf `bands_group`. `core/qso_state.py` `qso_confirmed_visual.emit` wandert von `on_message_received` WAIT_73-Branch (Z.692) nach `on_message_sent` TX_73_COURTESY-Branch (Z.538). `ui/mw_radio.py` Stop-Block in `_on_rx_mode_changed` analog Bandwechsel-Pattern: `stop_cq + cancel + set_cq_active(False) + encoder.abort + ptt_off`. **8 atomare Commits geplant** (C1 Backup, C2 Settings, C3 Tests Settings, C4 qso_state, C5 Tests P33 + Bundle D Spacing-Anpassung, C6 mw_radio, C7 Tests Bundle I, C8 Doku). **V4-pro Lessons First-Look:** stark bei Halluzinations-Aufdeckung (Finding 2 zeigte CLAUDE.md-Notiz zur Encoder-Pending-Queue als veraltet — P7.OMNI-SIMPLIFY hat sie entfernt), schwach bei Klärungsfragen (Finding 5 hat delegiert). Backup `Appsicherungen/2026-05-14_v0.97.25_vor_bundle_i/`. Push pending bis Field-Test F1-F7.

**Vorgänger:** **v0.97.25 Session 14.05.2026 Abend — Bundle F+G+H gepusht (Tests 1205), DeepSeek V4 Migration system-wide.** Mike-Anweisung „Kosten irrelevant, bestes Modell überall": alle Configs auf `deepseek-v4-pro` mit 1M Context + 131K Max-Output umgestellt (44 Stellen — Account1+Main PAL, `tools/deepseek_review.py`, 22 Johnboy-INIs + Python-Core, App-Configs JimBob Cockpit/Gmail Tools/JimBob RAG/N8N Assistent/VibePrompt). Ollama-Experiment (qwen3:30b-a3b lokal) komplett beendet — Sprachausgabe läuft eh über TTS-Server Port 8881, nicht über Ollama. Verifikation: `curl api.deepseek.com/v1/models` bestätigt deepseek-v4-pro + deepseek-v4-flash live. 75% Pro-Rabatt bis 31.05.2026. Wirkung sofort für Direct-API (`tools/deepseek_review.py`), für PAL-MCP erst neue Session (Config-Cache). Bundles F+G+H Field-Tests pending. Nächste Session: `docs/deepseek_lessons.md` V4-Sektion aufbauen nach 2-3 V4-R1-Reviews (empirisch).

**Vorgänger:** **v0.97.25 Session 14.05.2026 mittags — Bundle H: Bandpilot-Aware Diversity-Klick, Tests 1205.** Voller Workflow autonom V1→V2→R1→V3→Code→Final-R1 (Mike offline beim Field-Test Bundle F+G). Mike-Beobachtung: bp=Auto + DIVERSITY-Klick zeigt trotzdem Wahl-Dialog. Spec: bp=Auto+genug → Toast, bp=Auto+wenig → Dialog mit Mangel-Text, bp=off → Dialog wie heute. **Code:** `recommend_for_hour(..., allowed_modes=)` Subset-Vergleich, `code_mode_to_scoring()` Mapping, `_show_diversity_choice_dialog(intro_text)` extrahiert aus inline-Dialog, `_on_rx_mode_changed("diversity")` Refactor mit bp_mode-Dispatch. `BandpilotManualDialog` Hint bei current=None ausgeblendet. R1 7/10 mit 1 KRITISCH (Auto+DXTuneDialog) **teilweise übernommen** mit Begründung: DXTuneDialog ist Mess-Dialog (funktional), kein Wahl-Dialog → Mike-Spec nicht verletzt. 11 Tests inkl. T1-Suite mit synthetischem summary_24h (Anti-Mock-Pattern). Final-R1 „Push freigegeben" 0 KP. Backup `Appsicherungen/2026-05-14_v0.97.24_vor_bundle_h/`. Statistiken+PDFs aktualisiert. Push pending bis Field-Test F1-F8.

**Vorgänger:** **v0.97.24 Session 14.05.2026 vormittags — Bundle G: Diversity Std↔DX Direkt-Toggle (Mike-Wunsch während Bundle F Field-Test), Tests 1194.** Voller Workflow autonom V1→V2→R1→V3→Code→Final-R1. Bei Bandpilot=Aus + wiederholtem Klick auf DIVERSITY-Button: direkter Toggle zwischen Standard und DX (kein Dialog, weil Mike sonst NORMAL klicken würde). Mike's Logik: „Klick auf DIVERSITY im Div-Modus = den anderen Sub-Modus, weil sonst würde ich Normal klicken." **Architektur:** neues Signal `diversity_subtoggle_requested` in ControlPanel, neuer Slot `_on_diversity_subtoggle_requested` in mw_radio mit 3-fach-Guard (bp_mode=off + nicht gain_locked + radio.ip). **R1-K1+K2 KRITISCH:** OMNI+Auto-Hunt-Stop vor Sub-Mode-Wechsel (Encoder-Konflikt-Schutz wenn Toggle DXTuneDialog auslöst). Bandpilot=Auto/Manual: kein Toggle (Bandpilot dominant). 11 Tests (T8 mit ECHTEM DiversityController, T9+T10 R1-K1+K2-Coverage). Final-R1 „Push freigegeben" 0 KP. Backup `Appsicherungen/2026-05-14_v0.97.23_vor_bundle_g/`. Push pending bis Field-Test F1-F9.

**Vorgänger:** **v0.97.23 Session 14.05.2026 vormittags — Bundle F: 3 Bugs nach Mike-Field-Test gefixt, Tests 1183.** Voller Workflow autonom V1→V2→R1→V3→Code→Final-R1 (Mike ist offline). Field-Test v0.97.22 meldete: (1) **OMNI CQ sendet nicht** (KRITISCH), (2) doppelter Slot-Balken (großer in QSO-Kachel + kleiner Statusbar), (3) Magenta „nix funker-like" → Orange. **Wurzel Bug 1:** P34-Stufe2 (v0.97.19) entfernte `phase` aus `DiversityController`, aber `core/omni_cq.py:232` griff weiter darauf zu → AttributeError im Qt-Slot silently → OMNI sendet nie. 4 Test-Files mockten `diversity.phase = "operate"` → Tests grün, Live tot. **Fix 4 Commits:** C1 omni_cq Phase-Check raus, C2 Tests Mock-Cleanup + test_bundle_f.py NEU (5 Bug-Schutz-Tests, T2 mit ECHTEM DiversityController), C3 cycle_bar weg + `addSpacing(4)` Layout-Schutz, C4 `#FF66CC`→`#FFAA00` alle 5 Stellen. **R1-SOLLTE-1 abgelehnt** (R1-Halluzination `_gain_measure_locked` auf DiversityController, sitzt nur in mw_radio.py). Final-R1 „Push freigegeben" 0 KP. Backup `Appsicherungen/2026-05-14_v0.97.22_vor_bundle_f/`. Push pending bis Field-Test F1-F6.

**Vorgänger:** **v0.97.22 Session 14.05.2026 morgens — Bundle E TX-Slot-Lock Refactor (nach Mike-Korrektur Bundle-D), Tests 1179.** Voller Workflow autonom V1→V2→R1→V3→Code→Final-R1. Mike: „ich hatte mich falsch ausgedrückt — Even/Odd ist TX-Slot-Lock (SmartSDR-Style), nicht RX-Filter." Refactor: Settings-Key `tx_slot_lock` ∈ {"none","even","odd"} mit defensivem Filter + `get_tx_slot_lock`/`set_tx_slot_lock`-API. Helper `resolve_tx_slot(their_even, lock_status, rx_mode)` als Modul-Funktion in `core/qso_state.py` — zentralisiert TX-Slot-Wahl für alle 4 Pfade (CQ-Pfad mit Lock returnt Lock-Slot, Hunt-Pfad mit kompatiblem Slot returnt Gegentakt, Hunt-Mismatch returnt None für Caller-Block, Diversity-Modus ignoriert Lock). 3 TX-Pfade gepatcht: `_on_station_clicked` (Pre-Validierung VOR QSO-State-Mutation, bei Mismatch `add_info` Hinweis + return), `_on_cq_clicked`, `_on_tx_slot_for_partner`. Bundle-D-Filter-Code in `rx_panel.py` komplett zurückgebaut. Signal `slot_filter_changed` → `tx_slot_lock_changed`. Bei Mode-Wechsel zu Normal: `set_tx_slot_lock_buttons(get_tx_slot_lock())` lädt UI aus Settings. R1-F1 Thread-Safety als KISS-Entscheidung (GIL atomar) gelassen, R1-S2 Auto-Hunt-Pause nicht explizit (10-Min-Hard-Cap reicht). 13 neue Bundle-E-Tests T1-T8 + Bundle-D-Tests T6/T7/T8/T10 angepasst auf neuen Signal-Namen. Final-R1: „0 Findings, Push freigegeben". Backup `Appsicherungen/2026-05-14_v0.97.21_vor_bundle_e_refactor/`. Push pending bis Field-Test F1-F9.

**Vorgänger:** **v0.97.21 Session 14.05.2026 morgens — Bundle D UI-Tweaks (5 Stück) nach P50-Field-Test ✓, Tests 1166.** Voller Workflow autonom (V1→V2→R1→V3→Code→Final-R1). **A** Settings „Sichtbare Bänder" Spacing 6→10 luftiger. **B** DT-Anzeige `+0.0`/`-0.0` → `0.0` (Helper `_format_dt` in `ui/rx_panel.py`). **C** Even/Odd-Labels oben → Filter-Buttons (Normal-only) mit exklusiver Toggle-Logik, neues Signal `slot_filter_changed`, RX-Panel `apply_slot_filter` blendet Zeilen des nicht-aktiven Slots aus (komplett, nicht ausgegraut). **D** Diversity-Modus: Buttons ausgeblendet (zu komplex), QSO/Logbuch füllen Platz, Filter immer reset bei Modus-Wechsel (R1-Q4). **E** NEU `_slot_progress_bar` in Statusbar (unten rechts): QProgressBar 80×14 px, Cyan `#00CCFF` für Even / Magenta `#FF66CC` für Odd (R1-Q5 Farben), liest `cycle_duration` dynamisch (FT8=15/FT4=7.5/FT2=3.8). R1-F1 KRITISCH Signal-Verdrahtung umgesetzt, S1-S4 alle eingearbeitet. Final-R1: „0 KP, Push freigegeben". Backup `Appsicherungen/2026-05-14_v0.97.20_vor_bundle_d/`. **Memory-Leak P30 bestätigt resolved:** war TTS-Server-Akkumulation, nicht SimpleFT8 — App ist sauber. Push pending bis Mike's Field-Test F1-F8.

**Vorgänger:** **v0.97.20 Session 13.05.2026 spätnachmittags — P50 Bänder-Sichtbarkeit Settings-Toggle, Tests 1155.** Field-Test ✓ Mike: „funktioniert super". Voller Workflow autonom (V1→V2→R1→V3→Code→Final-R1) nach P34-Stufe2-Field-Test-Pending. Mike-Wunsch: nicht benötigte Bänder im Settings-Dialog abwählbar machen. **Neue API:** `Settings.get_enabled_bands()` + `set_enabled_bands(list)` mit defensiver Filterung (kein String/nicht in BAND_FREQUENCIES/Duplikate → ignoriert, leere Liste → Default alle 9). **UI:** QGroupBox „Sichtbare Bänder" in Tab „FT8 & Diversity", 3×3-QCheckBox-Raster (10/12/15, 17/20/30, 40/60/80), Min-1-Logik (letzte aktive Checkbox `setEnabled(False)`+Tooltip), Reset-Button setzt zurück. **ControlPanel:** `set_visible_bands(list)` mit `_band_visible`-Map; **R1-F1 KRITISCH current_band-Guarantee** (aktuelles Band bleibt sichtbar auch bei externen `_set_band`-Calls); **R1-F2 KRITISCH Prop-Bars mitversteckt** (`update_propagation` respektiert `_band_visible` damit kein Geister-Pulse). **MainWindow:** `apply_visible_bands()` beim App-Start nach `_set_band` und nach `dialog.exec()` (Pull-Pattern konsistent). **Bandpilot NICHT angefasst** — R1-Q1 war Halluzination (recommend_for_hour empfiehlt MODI nicht Bänder). 11 neue P50-Tests T1-T11 (T5 F1, T8 F2, T10 S3). Final-R1: „Push freigegeben, 0 KP". Backup `Appsicherungen/2026-05-13_v0.97.19_vor_p50_bands_visibility/`. Push pending bis Mike's Field-Test F1-F8 (V3 §5).

**Vorgänger:** **v0.97.19 Session 13.05.2026 nachmittags — P34-Stufe2 Statik-Ratio-Pipeline komplett raus, Tests 1144.** Voller Workflow autonom (V1→V2→R1→V3→Code→Final-R1). Statik-Mess-Phase, `_phase`/`should_remeasure`/`MEASURE_CYCLES`/`record_measurement`/`_evaluate`, 1h-Re-Mess-Frist, MessStatusDialog (gelöscht), Settings-Toggle "dynamisch anpassen", PresetStore-Ratio-API (is_valid_ratio/save_ratio/commit_with_ratio), `Settings.save_diversity_preset` und `_apply_dynamic_toggle` alle entfernt. **DynamicDiversityController** ist jetzt einziger Pfad für Ratio-Bestimmung — `_enable_diversity()` ruft `activate()` (nur wenn Radio verbunden — R1-F1 KRITISCH Deferred-Branch). `_enable_diversity` 3 Pfade → 1 Pfad. `_check_diversity_preset` 5 Branches → 2. ~250 LOC raus. 8 Test-Files gelöscht, 1 neu (`test_p34_stufe2.py` 15 Tests). Bonus: 80m-Abbruch-Bug obsolet (keine Mess-Phase mehr → keine "0/6-Hänger"-Symptome). Final-R1: "0 Bugs, 0 kritische Risiken, Push freigegeben". Tech-Debt: `update_diversity_ratio` hat noch `**_ignored_legacy` (v0.98+ bereinigen). Backup `Appsicherungen/2026-05-13_v0.97.18_vor_p34_stufe2/`. Push pending bis Field-Test F1-F10.

**Vorgänger 2:** **v0.97.18 Session 13.05.2026 mittags — Toast-Bundle (Medaillen + 6s + Manual-Konsistenz), Tests 1239.** Mike-Feedback nach P46-Field-Test: Ranking 1./2./3. nicht klar als Ranking erkennbar bei 5s-Toast. **Loesung `ui/bandpilot_dialogs.py`:** Neuer Helper `_rank_marker(idx)` → 🥇🥈🥉. `_USE_EMOJI`-Konstante mit Env-Var-Fallback `SIMPLEFT8_TEXT_MARKERS=1` → Text-Marker "Top:" "2.:" "3.:" (R1-SOLLTE-Defensive fuer Systeme ohne Color-Emoji). `_TOAST_DISPLAY_MS = 6000` (war 5000). BandpilotAutoToast + BandpilotManualDialog Ranking-Labels nutzen Helper, `●`-current-Marker bleibt. **R1: 9/10 1 SOLLTE → V3 uebernommen → Final-R1 0 Findings „Push freigegeben".** 6 neue Tests (T1-T6 inkl. T6 importlib.reload-Pattern fuer Env-Var-Fallback). Tests 1233→1239 grün. Backup `Appsicherungen/2026-05-13_v0.97.17_vor_toast_bundle/`. Push pending bis Mike's visuelle Bestaetigung.

**Vorgänger 2:** **v0.97.17 Session 13.05.2026 mittags — P46 Bandpilot Normal-Reintegration, Tests 1233.** Mike's Strategie-Wechsel 12.05. umgesetzt: P35-Bug-E (Bandpilot empfiehlt NIE Normal) zurueckgenommen. Bandpilot vergleicht 3-Wege (Normal/Std/DX), darf Normal als Target empfehlen, current=normal startet Bandpilot. **Code `ui/mw_radio.py`:** Z.774-779+811-816 (Skip+Block) geloescht. `_set_rx_mode_direct("normal")` Doppelaufruf-Refactor (R1-F2): `_disable_diversity()` einmal aufgerufen statt 2× `_apply_normal_mode`. `_apply_bandpilot_auto` pending-Tupel 4→5 elementig mit `current` (R1-F3): `_on_bandpilot_tx_finished` verwirft pending wenn User Modus zwischendurch manuell aenderte. **Tests:** 2 alte P35-Bug-E-Tests geloescht, 4 Workaround-Kommentare bereinigt, 2 TX-finished-Tests auf 5-Tupel angepasst. **Neu:** 8 P46-Tests in `tests/test_p46_bandpilot_normal.py` (T1-T8). **Workflow V1→V2→R1→V3:** R1 8/10 mit 1 KRITISCH + 2 SOLLTE + 1 KOENNTE alle uebernommen. **Final-R1:** 9/10 „Push freigegeben", 0 KP, 1 KOENNTE (Doku) sofort gefixt: `docs/explained/bandpilot_de.md`+`bandpilot.md` Hinweis ergaenzt. Tests 1227→1233 grün. Backup `Appsicherungen/2026-05-13_v0.97.16_vor_p46_bandpilot_normal/`. **P35-Bug-F (App-Start IMMER 20m FT8 Normal) unveraendert** — orthogonal. Push pending bis Field-Test-OK.

**Vorgänger:** **v0.97.16 Session 13.05.2026 morgens — P14 DT-Werte-Symmetrie (MAD-Outlier-Filter + Totband-Reduktion), Tests 1227.** Mike-Beobachtung 07:30 UTC: RX-Panel zeigt 11/20 negative DT-Werte mit Ausreißern bei -1.2/-0.7/-0.4 → Median wandert nach unten → Korrektur 0.27s zentriert nicht auf 0. **Wurzel:** `statistics.median(valid)` robust gegen einzelne Outliers, aber bei 5+ negativen Ausreißern in 20er-Stichprobe wandert Median selbst. Plus DEADBAND 0.05 friert bei -0.05 ein (R1-F1 KRITISCH). **Lösung:** Neue Helper-Funktion `_filter_outliers_mad(values, k=2.5)` in `core/ntp_time.py` (Hampel-Filter: Median + MAD, entferne |x-med|>k×MAD). Edge-Cases: n<7 Identity (FT4/FT2-Schutz), MAD=0 Identity, <3 übrig Notnagel. DEADBAND 0.05 → 0.02. DAMPING bleibt 0.7 (R1-F4 KISS). Opt-in Debug-Log via `SIMPLEFT8_DT_DEBUG=1` pro Slot: `[DT-DBG] FT8_20m n=20 raw=-0.100 filt=+0.000 outliers=7 corr=+0.270`. Fast-Path-stdev bewusst ungetrimmt (konservatives Stop-Kriterium R1-F8). Voller Workflow V1→V2 (10 Findings)→R1 5/10 mit 2 KRITISCH→V3 alle übernommen→Code→Final-R1 9/10 „Push freigegeben" 0 KP. 10 neue Tests (T7 Sanity-Anker mit einfachem Median als Wurzel-Schutz R1-F2). 1227 grün. Backup `Appsicherungen/2026-05-13_v0.97.15_vor_p14_dt_symmetry/`. Asynchroner Field-Test: Mike schickt Screenshots, Push pending bis mehrfache Bestätigung.

**Vorgänger:** **v0.97.15 Session 13.05.2026 — Bundle C (P10 PSK-Backoff-Reset + P13 RX-Panel-Slot-Times), Tests 1217.** P10: BACKOFF_MAX_S 3600→600 (10 Min Cap), `_Backoff` thread-safe via threading.Lock (R1-V2-KP-2 fand Race in `fail()` read-modify-write), public `reset_backoff()` + `set_mode()` an PSKReporterClient (Final-R1-KP-1 fand Mode-Sync-Bug). Helper `_reset_psk_polling_on_change` in mw_radio: bei Band/Modus-Wechsel sofortiges Statusbar-Re-Fetch via `_psk_timer.start(0)` + Karten-Pfad-Reset (falls offen). P13: UTC-Spalte zeigt jetzt FT8-Slot-Boundary (10:51:30) statt Wall-Time (10:51:42); Fix in `add_message` UND `_populate_row` (2. Bug-Stelle erst beim Code-Schreiben aufgefallen — Memory-Lesson). `_set_sort` time-Branch defensive Float-Key gegen mixed-Type-TypeError. 13 neue Tests (7 P10 + 6 P13) + 1 bestehender angepasst. Final-R1: „Push nach KP-1-Fix freigegeben". Backup `Appsicherungen/2026-05-13_v0.97.14_vor_bundle_c/`.

**Vorgänger:** **v0.97.14 Session 13.05.2026 — Bundle B' (P32 RX-Panel-Spalten-Persist + P33 QSO-Komplett-Reihenfolge), Tests 1204.** Zwei voneinander unabhängige UI-Bugs als gemeinsames Bundle. **P32:** Spalten-Auswahl im RX-Panel via Rechtsklick bleibt jetzt über App-Restart hinweg — neuer Settings-Key `rx_panel_hidden_cols`, defensiv gefiltert (Range + Typ + `COL_MSG`-Schutz), persistiert via Signal-Pattern analog `country_filter`. **P33:** `✓ QSO komplett`-Zeile erschien NACH nächstem CQ statt davor weil `qso_confirmed.emit` erst nach Courtesy-73-Send feuerte. Fix per 2-Signal-Split: neues `qso_confirmed_visual` SOFORT bei 73-Empfang (nur UI-Update), bestehendes `qso_confirmed` bleibt nach Courtesy-Send für alle anderen Ops (OMNI-Resume, Auto-Hunt-Reset, Logbuch). V2-Self-Review fand OMNI-Race in V1-Variante-A (qso_confirmed.emit hätte _maybe_resume_omni vor Courtesy-Send gerufen). 12 neue Tests. Final-R1: „Push freigegeben", 0 KP, 1 SOLLTE (try/except um settings.save) sofort gefixt. Backup `Appsicherungen/2026-05-13_v0.97.13_vor_bundle_b/`.

**Vorgänger:** **v0.97.13 Session 13.05.2026 — P48 DT-System aufräumen + tunen (4 Teile), Tests 1192.** Empirische Auswertung von 10.212 DT-Median-Einträgen zeigte FlexRadio-Hardware-Latenz reproduzierbar bei +0.26 s ± 0.04 s über alle Bänder. **P48-A:** Hardware-Werte (`tx_buffer_s=1.3`, `rx_hardware_offset_default_s=0.26`) aus Code in Settings `radio_timing`-Block ausgelagert. Encoder bekommt `tx_buffer_s`-Parameter, `TARGET_TX_OFFSET` entfernt. **P48-B:** Cross-Modus-Fallback FT4/FT2 → FT8 vom gleichen Band. **P48-C:** Hardware-Default 0.26 als Kaltstart (statt 0.0). **P48-D:** Schnell-Konvergenz im 1. Slot bei ≥10 Stationen + Stddev<0.1 → 1 statt 2 Slots. **Kritischer Bug-Fix:** `_is_initial = _saved.get(_mode_key()) is None` (R1-V2 Finding 1) — sonst hätte Hardware-Default 0.26 alle Initial-Logik tot gelegt. 17 neue Tests + 3 bestehende angepasst. Voller Workflow V1→V2→R1→V3 (1 Bug + 2 Risiken + 1 Overengineering + 1 Verbesserung angenommen). Final-R1: „Push freigegeben", 9.5/10, 0 KP. Backup `Appsicherungen/2026-05-13_v0.97.12_vor_p48_dt_optimization/`.

**Vorgänger:** **v0.97.12 Session 13.05.2026 — Bundle A (P43 + P20 + P18), Tests 1175.** Drei kleine QoL-Fixes als gemeinsames Bundle. **P43 setproctitle** zeigt „SimpleFT8 v0.97.12" in Activity Monitor (Remote: „SimpleFT8 (Ferienhaus)") — endlich von Qwen3-TTS unterscheidbar. **P20 Log-Rotation** mit datierten Tagesdateien + Symlink + 7-Tage-Cleanup + dauerhaftes `archive/`-Unterordner für Mike's bestehende Historie. **P18 DT-Print-Dedup** ersetzt 3× identischen Spam beim App-Start durch 1×. Neues Modul `core/log_setup.py` (5 Funktionen) wird von `main.py` UND `tools/remote/start_simpleft8_nokill.py` genutzt — kein Drift. Neue optionale Dependency `setproctitle>=1.3`. 8 neue Tests inkl. Symlink-OSError-Fallback. Voller Workflow V1→V2→R1→V3 (3 Risiken alle adressiert, 1 Verbesserung + 1 Hinweis angenommen, 2 Hinweise mit Begründung beibehalten). Final-R1: „Push freigegeben", 0 KP. Backup `Appsicherungen/2026-05-13_v0.97.11_vor_bundle_qol/`.

**Vorgänger:** **v0.97.11 Session 13.05.2026 — P47 Tote Frequenz-Settings + Statusbar-Filter-Anzeige entfernt, Tests 1167.** Bug: `audio_freq_hz` + `max_decode_freq` waren UI-Settings ohne Wirkung (Encoder vom CQ-Algo überschrieben, `decoder.max_freq` nie zur Laufzeit aktualisiert). Plus Statusbar `Filter: 100-4000 Hz` für FT2 irreführend (Decoder faktisch 3000 Hz). Fix: Defaults als Konstanten hartkodiert (`Encoder(1500)` + `Decoder(max_freq=3000)`), UI-Felder + Hints + Load/Save/Reset raus, Statusbar-Segment raus, `Settings.load()` popped alte Keys idempotent. 5 neue Tests inkl. Bug-Schutz-Assertion auf Source-Level. Voller V1→V2→R1→V3-Workflow (R1: 2 Risiken — 1 widerlegt, 1 abgelehnt; 3 Unklarheiten + 2 Verbesserungen alle eingebaut). Final-R1: „Push freigegeben", 0 KP. Backup `Appsicherungen/2026-05-13_v0.97.10_vor_p47_dead_freq_settings/`.

**Vorgänger:** **v0.97.10 Session 13.05.2026 — P44 Statusbar DT-Korrektur als eigenes Label, Tests 1162.** Bug: globaler `setStyleSheet` bei DT-Korrektur färbte ganze Statusbar grün. Fix: eigenes Permanent-Widget `_dt_indicator` rechts neben `_stats_indicator` (Mike-Vision „dynamische Indikatoren rechts"). Plus `dt_text` aus zentralem msg-String entfernt (sonst Doppelanzeige). 2 neue Tests inkl. Bug-Schutz-Assertion. Voller V1→V2→R1→V3-Workflow (R1: „kann atomar eingespielt werden"). Backup `Appsicherungen/2026-05-13_v0.97.9_vor_p44_dt_indicator/`.

**Vorgänger:** **v0.97.9 Session 12.05.2026 — P45 Stats-Guard für OMNI-CQ, Tests 1160.** Bug: `_log_stats` in `ui/mw_cycle.py` blockierte korrekt CQ/QSO/Tuning/Warmup, aber NICHT OMNI-CQ (separate State-Machine, setzt nie `qso_sm.cq_mode`). Fix: `_omni_cq.is_active()` als eigener Guard-Block unabhängig von `_qsm` (R1-K1). Plus konsistenter Indikator-Grau bei CQ/QSO/OMNI-Block. 4 neue Tests. Workflow V1→V2→R1→V3 voll durchgezogen. Backup `Appsicherungen/2026-05-12_v0.97.8_vor_p45_omni_stats_guard/`.

**Vorgänger:** **v0.97.8 Session 12.05.2026 — P30 Diagnose-Code in Decoder eingebaut, Tests 1156.** R1-bestätigter Hauptverdacht: `_audio_buffer_24k` Skip-Bug in `core/decoder.py` Z.174-178 (Liste wird nicht geleert wenn Decode überspringt). KEIN Fix sondern Mess-Code für nächste Phase. Default AUS, opt-in via `export SIMPLEFT8_DECODER_DIAG=1`. NEU `_emit_p30_sample()` loggt alle 60s Buffer-Größe + feed-Throughput + Skip-Counter + Threads + RSS + busy_held (Hang-Detection). 8 neue Tests `tests/test_p30_diagnostic_code.py`. Voller Workflow V1→V2→R1→V3 + Backup `Appsicherungen/2026-05-12_v0.97.7_vor_p30_diagnostic_code/`. Memory-Watcher-Daemon läuft (PID 72060). Nächster Schritt: Mike aktiviert Diagnose, App 1-3 Tage Diversity, dann P30.FIX als eigener Workflow.

**Vorgänger:** **v0.97.7 Session 12.05.2026 — P41 audio_streaming-Flag fuer OMNI-CQ Antennen-Switch, Tests 1148.** Mike-Field-Test mit OMNI-CQ + Adaptive 30:70 zeigte 20-Slot-lange Antennen-Switch-Blockade weil `is_transmitting` zu grob war (Worker-Setup+Sleep zaehlte mit). Neuer feiner Flag `is_audio_streaming` (True nur von ptt_on bis ptt_off) ersetzt den Check in mw_cycle.py:678. R1-KRITISCH eingearbeitet (abort() faesst Flag nicht an — Race mit FlexRadio-Buffer-Latenz). Workflow V1→V2→R1→V3 voll durchgezogen. 8 neue Tests `tests/test_p41_audio_streaming_flag.py`. Plan-File `prompts/p41_audio_streaming_flag_r1.md`. Backup `Appsicherungen/2026-05-12_v0.97.6_vor_p41_omni_antenna_fix/`. Push pending.

**Vorgänger:** **v0.97.6 Session 12.05.2026 — P40 P37-Komplettierung (3 weitere `current_ant`-Aufrufer), Tests 1140.** Mike-Field-Test zeigte Adaptive-Label ohne RX-Suffix. P37 hatte nur 1 von 4 Aufrufern von `update_diversity_ratio(is_dynamic=True)` gefixt — klassischer Partial-Fix. Restliche 3 (main_window.py:1357 `_on_dynamic_ratio_changed`, mw_radio.py:990, mw_cycle.py:290) jetzt nachgezogen. 4 neue Integration-Tests (`tests/test_p40_dynamic_ratio_slot.py`) für den Signal-Slot. Workflow V1→V2(Memory-Lesson zitiert)→R1(0 KRITISCH+1 SOLLTE→Test)→V3. Plan-File `prompts/p40_p37_completion_r1.md`. Push pending.

**Vorgänger:** **v0.97.5 Session 12.05.2026 — P39 osascript-Window-Title-Filter auf Python-Prozesse begrenzt, Tests 1136.** Bug-Wurzel von Mike's „App laeuft bereits"-Falschmeldung war NICHT PID-Recycling (P38), sondern dass osascript jeden visible Prozess mit „SimpleFT8" im Window-Titel als laufend interpretiert hat — inkl. Chrome-Tab auf GitHub-Repo. Fix: `if procName is "Python" or procName starts with "python"` Filter. Live-verifiziert 12.05. Workflow V1→V2→R1(0 KRITISCH)→V3. Plan-File `prompts/p39_window_title_python_filter_r1.md`. Push pending mit P38 zusammen.

**Vorgänger:** **v0.97.4 Session 12.05.2026 — P38 PID-Recycling-Schutz im Starter-Script, Tests 1136.** Mike-Screenshot 12.05. zeigte Starter blockt legitimen Neustart weil macOS SimpleFT8-PID an Chrome recycled hat. Fix in `starter.command:36-50` — `ps -p $LOCK_PID -o command=` + `grep "SimpleFT8.*main\.py"` hinter `kill -0`. Bei Recycling Lock loeschen + sauber starten. NICHT identisch mit altem „2 unsichtbare Instanzen"-Bug (separater Cleanup-Issue, Folgeprojekt). Workflow V1→V2→R1(0 KRITISCH)→V3. Plan-File `prompts/p38_pid_recycling_starter_r1.md`. Push pending.

**Vorgänger:** **v0.97.3 Session 12.05.2026 — P37 RX-Antennen-Anzeige im Adaptive-Label, Tests 1136.** Mike-Wunsch nach Live-Test: Phase-Label „● DYNAMISCH (live)" zeigt zusätzlich aktive RX-Antenne („— RX Ant1"/„— RX Ant2"), slot-für-slot Update. `update_diversity_ratio()` neuer optionaler Parameter `current_ant`. mw_cycle.py Aufruf erweitert. 5 Tests R1-Coverage (`tests/test_p37_rx_antenna_label.py`). Voller Workflow V1→V2→R1(0 KRITISCH)→V3. Plan-File `prompts/p37_rx_antenna_label_r1.md`. Push pending.

**Vorgänger:** **v0.97.2 Session 11.05.2026 — P35 Bug D+E+F live-gefixt während Field-Test, Tests 1131.** Bug D: `_on_band_changed` ruft `on_band_change()` nur bei rx_mode=diversity + radio.ip (sonst Fallback Phase=operate). Bug E: Bandpilot überschreibt NIE Normal-Modus (skipt bei current=normal ODER target=normal, Mike-Vision). Bug F: App-Start IMMER 20m FT8 Normal (hardcoded in `main_window.__init__`, kein band+mode-Restore mehr). Commits `6347c0a`+`18db03f`+`91728f7`. Field-Test 11.05. abends: App-Start ✅, Normal→Diversity DX ✅, Dynamic-Buffer füllen sich ✅. Push pending.

**Vorgänger:** **v0.97.1 Session 11.05.2026 — P35.DIVERSITY-STARTUP-FIX (3 Bugs aus P34-Field-Test gefixt).** Bug A: `_enable_diversity` bei radio.ip=None defer + Resume via `_check_diversity_preset` nach Radio-Connect. Bug B: `_apply_dynamic_toggle` resettet Queue + current_ant unter Lock. Bug B5: Settings-Toggle überlebt Session — Auto-Reactivate bei Diversity-Mode-Wechseln. Plus AK5-Cache-Reuse-Respekt (Cache 70:30 wird beim Toggle AN NICHT mehr auf 50:50 zurückgesetzt). 5 atomare Commits, Tests 1116 → 1129 (+13). Plan-Files prompts/p35_diversity_startup_fix_v[1,2,3]+r1+final_r1.md (Compact-fest).

**Vorgänger:** **v0.97.0 Session 11.05.2026 — P34.DIVERSITY-DYNAMIC Code fertig, Field-Test pending.** Mike-Vision: Antennen-Verhältnis im laufenden Betrieb live anpassen statt nur 1× pro Stunde mit 90-Sek-UI-Sperre. ENTWEDER-ODER zur statischen Pipeline (Toggle in Settings „Antennen-Verhältnis dynamisch anpassen (Testphase)"). 9 atomare Commits, ~480 LOC neu (`core/dynamic_diversity.py` NEU 190 LOC + 2 Helper-Funktionen `compute_slot_score`/`evaluate_ratio` in `core/diversity.py` + Hooks in mw_cycle, mw_radio, main_window, control_panel, settings_dialog, settings). Tests **1070 → 1111 grün** (+14 Helper + 15 Unit + 12 Integration). Plan-Files prompts/p34_diversity_dynamic_v[1,2,3]+r1.md. Field-Test 12 Punkte F1-F12 (V3 §5) pending. Push pending bis Mike Field-Test-OK. **Offen weiter: P30 MEMORY-LEAK 124 GB nach Tagen** (RAM nicht Disk, Live-Check bestätigt) — eigener Workflow nötig.

**Vorgänger:** **v0.96.10 P26.CONNECT-MODAL Field-Test ✅ + Tweak (11.05.2026)** — Modaler Dialog beim App-Start, Mike Field-Test „funktioniert super". Tweak v0.96.10: Versuch-Counter raus (set_attempt no-op), Fenster 352×176 (20% kleiner). Spinner + „ohne Radio weiter"-Link + „Beenden"-Button.

**Vorgänger:** **v0.96.9 P26.CONNECT-MODAL — Code fertig + Final-R1 OK („Push freigegeben"), Field-Test pending (10.05.2026 ~18:30 UTC)** — Modaler Dialog beim App-Start während FlexRadio-Connect. Spinner + „Versuch X von 10" + „ohne Radio weiter"-Link (klein/dezent) + „Beenden"-Button. Auto-Close bei `connected`-Signal. **R1-K2-Goldwert:** `_start_radio()` deferred via `QTimer.singleShot(0, ...)` damit `window.show()` zuerst läuft (sonst exec() blockt restlichen Init). **R1-K1-Race-Fix:** Worker holt lokale Dialog-Referenz + `try/except RuntimeError` um emit (PySide6 wirft RuntimeError bei emit auf destroyed C++-Object). 6 atomare Commits geplant. **Tests 1056 → 1070 grün** (+14 P26 inkl. T10 R1-K1-Race + T11 R1-K3-Race). Plan-Files prompts/p26_connect_modal_v[1,2,3]+r1+final_r1.md. Push pending bis Mike Field-Test 6 Punkte (V3 §8) abnimmt.

**Vorheriger Stand:** **v0.96.7 P23.OMNI-COUNTER-EIGEN — Code fertig + Final-R1 pending, Field-Test pending (10.05.2026)** — Mike-Vorschlag nach P22: OMNI-Paritaets-Wechsel haengt am Diversity-Such-Counter, brüchig. Loesung: eigener Down-Counter pro Modus (FT8=10, FT4=20, FT2=40 = ~5 Min Wallclock) im OMNI-Modul. Counter sichtbar als `↻N` Suffix in TX-Zeile + Statusbar `Ω CQ=10 (E)`. Auto-Flip bei 0 + Reset auf TARGET (1 Emit pro Slot, kein Zwischen-0-Flicker). QSO-Resume + Mess-Ende → Reset auf TARGET. Bandwechsel/Modus-Wechsel → OMNI stop (heute). `core/omni_cq.py` `_cq_count` (UP) → `_cq_remaining` (DOWN) + `_cq_target`. `_OMNI_FLIP_AFTER_SEARCHES`/`on_search_trigger` weg. `reset_counter_after_measure` neu. `mw_cycle.py` Hook-Umbau (search-trigger raus, mess-reset rein). `qso_panel.add_tx` neuer Param `omni_remaining`. **8 atomare Commits geplant.** **Test-Bilanz: 1035 → 1049 grün** (+14 effektiv: 17 neue P23 - 3 gelöschte search_trigger). Plan-Files prompts/p23_omni_counter_v[1,2,3].md + _r1.md.

**Vorheriger Stand:** **v0.96.6 P22+P8 ATOMARES PERSIST + MESS-MODAL — Code fertig, Final-R1 + Field-Test pending (10.05.2026)** — Mike-Diagnose 14:35: Half-State im `presets_dx.json`/`presets_standard.json` führt nach Restart zu endlosen Phase-3-Versuchen wenn Wurzel-Bedingung noch da. Phase 2 schreibt sofort, Phase 3 nur bei Erfolg → Disk-Halbstand bei Hang/Crash/Cancel. **Loesung 2-Bausteine:** (1) Atomares Persist in `core/preset_store.py` — `stage_gain` (Memory) + `commit_with_ratio` (atomar Disk) + `discard_staged` (Cancel). `is_valid_gain` lehnt Half-State ab. Atomic write tempfile+os.replace. R1-K1: staged-erst-nach-success. R1-K3: Exception-Catch+rollback statt re-raise. (2) `ui/mess_status_dialog.py` NEU — WindowModal sperrt UI während Phase 3 (kein Bandwechsel/Modus/Hunt/CQ), zeigt Antenne+Schritt+Restzeit, Cancel räumt staged+Diversity auf. **Stall-Detector NICHT gebaut** (Mike-Klärung Q1: Wurzel unbestätigt → P23 separat). **8 atomare Commits geplant:** C1 preset_store, C2 PresetStore-Tests, C3 mess_status_dialog NEU, C4 mw_radio Pipeline+Helpers, C5 mw_cycle commit+Modal-Close, C6 main_window closeEvent, C7 P22-Tests NEU, C8 APP_VERSION+Doku. **Test-Bilanz: 1019 → 1034 grün** (+15 Pipeline+Modal). **Final-R1 + Field-Test (V3 §8 5 Punkte) ausstehend.** **Plan-Files:** prompts/p22_preset_atomic_v[1,2,3].md + _r1.md.
**Tests:** `./venv/bin/python3 -m pytest tests/ -q` → **1034 passed** v0.96.6 (Qt-Smoke-Tests via `QT_QPA_PLATFORM=offscreen`)
**Vor Commits:** Tests grün + bei nicht-trivialen Änderungen DeepSeek-Review (`pal codereview` model `deepseek-chat`) — bereits durch globale §0 + Projektregeln gefordert.

⚠️ **DeepSeek-Workflow Stand 2026-04-28:**

**Direkt-API ist jetzt Default-Werkzeug** (nicht mehr `pal chat`-MCP):
- Helper: `tools/deepseek_review.py` — kein Token-Limit (128K Context)
- Aufruf: `cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py`
- Key in `~/.deepseek_key` (chmod 600, ausserhalb Repo)

**Default-Modell: `deepseek-reasoner` (R1)** — Mike-Entscheidung 28.04.:
„Quality > Speed, ~$3/Monat-Differenz egal gegen Bug der Stunden frisst."

| Modell | Wann | Antwort-Zeit | Kosten |
|---|---|---|---|
| **R1 (Default)** | Code-Review, Architektur, Race-Conditions, Trade-offs, KISS-Bewertung | 6-30s | ~$0.005 |
| V4 via `--chat` | Trivial-Fragen ("Ist X im Code?"), Tippfehler, Pure Verifikation | 2-5s | ~$0.001 |

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

**SimpleFT8 ist ein Hobby-Funker-Tool. KEIN Contest-Tool.** Diese Leitlinien
gelten fuer Claude UND DeepSeek bei Feature-Vorschlaegen, Architektur-Beratung,
Implementierungen:

- **Zielgruppe:** Hobby-Funker. Nicht Pileup-Jaeger, nicht Contest-Operatoren,
  keine 1000-QSO-pro-Tag-Stationen.
- **Use-Case:** App starten → ein bisschen FT8/FT4/FT2 funken → fertig.
  Keine Stunden-langen Sessions mit komplexer Konfiguration.
- **UX-Prinzip:** Einfache Bedienung > Vollstaendigkeit. Lieber 3 gut funktio-
  nierende Features als 30 die Mike erst lernen muss.
- **Visueller Stil:** Modern (dunkles Theme, Neon-Akzente, weiche Verlaeufe).
  Nicht 90er-Jahre-Funktionalitaets-UI wie WSJT-X / JTDX.
- **NICHT geplant:** Contest-Modi, Multi-Operator, RTTY/CW/SSB, Skimmer-
  Integration, Pileup-Tools, komplexe Filter-Macros, Cluster-Spotting fuer
  DX-Hunting. Wenn ein DeepSeek-Vorschlag in diese Richtung geht: ablehnen.
- **Was modern bedeutet:** 3D-Globus statt platter PSK-Reporter-Karte,
  Live-Diversity-Visualisierung, Antennen-Farb-Coding, glow-Effekte —
  Dinge die in 2026 selbstverstaendlich sind aber im Funker-Tool-Alltag fehlen.

**Wenn DeepSeek oder ich ein Feature vorschlagen, immer pruefen:** „Hilft das
einem Hobby-Funker beim Hobby-Funken? Oder waere das nur fuer Power-User /
Contester sinnvoll?" — bei letzterem: NICHT umsetzen, in eine optionale
Erweiterung ausgliedern oder ganz verwerfen.

---

## ⛔ Programmier-Leitsaetze (PFLICHT bei jedem Entwurf!)

Diese Saetze gelten fuer Claude UND DeepSeek bei jedem Plan, jedem Prompt,
jeder Code-Aenderung. Wenn ich (Claude) gegen sie verstosse: Mike soll mich
darauf hinweisen, ich nehme die Korrektur an.

1. **Overengineering vermeiden — kritisch beurteilen.** Vor jedem neuen
   Konzept (neue Klasse, neue Konfig-Datei, neue Abstraktionsebene) fragen:
   *„Brauchen wir das wirklich, oder sind wir verliebt in unsere Idee?"*
   Wenn es ohne geht — ohne. Drei aehnliche Zeilen sind besser als eine
   verfruehte Abstraktion. KISS schlaegt Eleganz.

2. **Sauber wie ein Chirurg.** Schlamperei oder Eile beim Entwurf raechen
   sich spaeter doppelt — schlechtes Design generiert mehr Bugs, mehr
   Re-Reviews, mehr Frust. Lieber 30 Min laenger im Plan-Mode als 3 Stunden
   nachbessern. Schritt fuer Schritt, sauber, kein Drauflos-Schneiden.

3. **Code als Referenz, nicht Annahmen.** Bevor V2-Prompts an DeepSeek gehen
   oder Plans entstehen: tatsaechlichen Code lesen, Dateipfade + Zeilen
   verifizieren. Annahmen fuehren zu Halluzinationen die niemand mehr sauber
   reviewen kann.

4. **Mike auf Overengineering hinweisen.** Wenn Mike ein Feature beschreibt
   das mit weniger Aufwand sauberer geht: ansprechen, alternative skizzieren,
   ihn entscheiden lassen. Nicht stillschweigend kompliziert umsetzen.

5. **V1 → V2 (Self-Review) → DeepSeek → V3 → Plan-Mode → Code.** Diese
   Reihenfolge bei nicht-trivialen Aenderungen. Kein Skip von Self-Review.
   Kein Skip von Code-Verifikation. „Sauber am Anfang spart 10x Zeit am Ende"
   (Mike, 2026-04-28).

---

**Diagramme:** `./venv/bin/python3 scripts/generate_plots.py`
→ Generiert IMMER beide Sprachen: DE → `auswertung/` + EN → `auswertung/en/`
→ DE: `SimpleFT8_Bericht.pdf` (7 S.) | EN: `SimpleFT8_Report.pdf` (7 p.)
→ Regel: Statistiken und PDFs IMMER auf Deutsch UND Englisch erstellen!

**⚠ Tages-/Pooled-Mean-Auswertungen:** ZUERST `auswertung.md` lesen!
Format-Stolpersteine (3 vs 5 Tabellenspalten, Rescue extern in `stations/`,
DX-Modus zählt nur SNR<-10) sind dort dokumentiert inkl. Code-Vorlage.
Mike's „Tagestrend"-Anfragen → stundenweise Tabelle, nicht nur Pooled-Mean.
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

## Architektur & Module

```
core/
  decoder.py          RMS AGC (-12 dBFS Ziel, ±3 dB Hysterese), 5-Pass Subtraktion
                      DT_BUFFER_OFFSET: FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet!)
  encoder.py          FT8/FT4/FT2 encode → VITA-49 TX
                      TARGET_TX_OFFSET=-0.8s (kompensiert FlexRadio TX-Buffer 1.3s)
  qso_state.py        State Machine: Hunt, CQ, Waitlist, RR73 Courtesy (max 2×)
                      _was_cq: in start_qso() UND _process_cq_reply() gesetzt (Bug-Fix!)
  diversity.py        Controller: Standard(Stationsanzahl) / DX(SNR<-10dB)
  diversity_merger.py Merged A1/A2 Dekodierungen
  ntp_time.py         DT-Korrektur v3: pro Modus+Band (Key "FT8_20m"), set_band(),
                      2-Zyklen-Messen, 70% Dämpfung, engere Grenzen pro Modus,
                      gedämpfte Erstkorrektur bei ≤2 Stationen
  station_accumulator.py Gemeinsame Logik Normal+Diversity
                      Aging: 75s normal / 150s active_qso / 300s CQ-Rufer
  station_stats.py    Async Queue+Daemon-Thread Logging → statistics/<Modus>/<Band>/<Proto>/
                      + Entry-Typ antenna_qso → statistics/antenna_qso/YYYY-MM-DD.md
  antenna_pref.py     AntennaPreferenceStore: {best_ant, delta_db} pro Callsign,
                      1dB Hysterese, kein Timeout (jeder Zyklus überschreibt)
  propagation.py      HamQSL + _apply_seasonal_correction(band, condition, utc_hour, month)
                      60m fehlt in XML → Interpolation 40m/80m (day+night getrennt, implementiert)
  ap_lite.py          ⛔ UNGETESTET — Feldtest ausstehend (SCORE_THRESHOLD=0.75)
  omni_cq.py          OMNI-CQ signal-getriggert (v0.96.1+).
                      on_cycle_start(@Slot int, bool) im GUI-Thread, von
                      mw_cycle._on_cycle_start gerufen. 5-Slot Even/Odd
                      Pattern (TX-TX-RX-RX-RX), Block-Auto-Rollover bei
                      slot_index 4→0, Toggle-Start IMMER Block 1, Frequenz-
                      Sticky 1× am ersten TX. Diversity-only, btn_omni_cq
                      Easter-Egg (Klick auf Version). KEIN Worker-Thread,
                      keine Sleep-Logik, keine Boundary-Berechnung mehr.
                      → Spec: memory project_omni_cq_spec.md (verbindlich)
  auto_hunt.py        Auto-Hunt Logik (v0.78: wird Diversity-only Feature
                      analog OMNI — Mode-gekoppelt, btn_auto_hunt nur in
                      Diversity sichtbar; Mode-Wechsel zu Normal stoppt
                      Auto-Hunt automatisch via auto_hunt_stopped("mode_change")).
  timing.py           UTC-Takt, modus-abh. Zyklen
  protocol.py         FTX_PROTOCOL_FT8/FT4/FT2
  ft8lib_decoder.py   C-Library Wrapper
  geo.py              Maidenhead, Haversine, Großkreis-Bearing (atan2),
                      Azimuthal-Equidistant-Projektion (Karten-Render),
                      safe_locator_to_latlon (None-safe Wrapper)
  direction_pattern.py Sektor-Aggregation (16x 22.5°), Mobile-Filter,
                      StationPoint/SectorBucket Datenklassen,
                      NaN/Inf-Schutz fuer korrupte externe Inputs
  psk_reporter.py     PSKReporterClient: XML-Polling mit Cache + Backoff
                      (1.5x bis 60min), Call-Normalisierung (.rsplit('/',1)),
                      atomarer Cache-Write (.tmp + os.replace)
  locator_db.py       LocatorDB: persistenter Locator-Cache (~/.simpleft8/
                      locator_cache.json). Source-Priority (cq_6 > psk_6 >
                      qso_log_6 > _4-Varianten). RLock-Threading, atomic-Write,
                      Mobile-Suffixe (/MM/AM/QRP) prec_km x 1.5. get() returnt
                      Kopie. Bulk-Import aus ADIF-Dateien. Save bei App-Close.

radio/
  base_radio.py       RadioInterface ABC
  radio_factory.py    create_radio(settings)
  flexradio.py        SmartSDR TCP + VITA-49 + Auto RX-Filter

ui/
  main_window.py      3-Panel + Statusbar; _tune_active/_tune_freq_mhz State-Vars
  mw_cycle.py         Cycle Processing; _diversity_in_operate Flag (Transition Guard!)
                      _log_stats Guard: btn_cq.isChecked() + cq_mode + state (3-fach robust)
  mw_radio.py         Band/Modus/Diversity, _diversity_in_operate Reset bei _enable_diversity()
                      set_band()/set_mode() bei Wechsel + Radio-Connect (DT-Korrektur!)
  mw_tx.py            TX-Regelung: rfpower konvergiert → save_tx_power();
                      _on_tune_clicked() setzt _tune_active/_tune_freq_mhz + _update_statusbar()
  mw_qso.py           QSO Callbacks, CQ, Logbuch;
                      _on_station_clicked: _cq_was_active VOR stop_cq() sichern → _was_cq fix
                      _antenna_pref_label() → "(ANT1)" in Normal, "(ANT2, +6.3 dB)" in Diversity
  control_panel.py    UI Controls (57 KB — größte UI-Datei); Frequenz in kHz
  rx_panel.py         RX-Tabelle; Answer-Me-Highlighting; Spalten per Rechtsklick
  dx_tune_dialog.py   18-Zyklus interleaved Messung; cache.save() HIER nach Messung!
  direction_map_widget.py  Azimuthal-Karte mit RX/TX-Toggle (v0.66).
                      MapCanvas (paintEvent + QPixmap-Background-Cache, Resize-
                      Debounce 200ms) + DirectionMapDialog (non-modal QDialog,
                      Toggle, Filter-Bar, Status). LocatorCache fuer FT8 (CQ
                      ist die einzige Quelle fuer Locators). Aufruf via
                      Settings-Dialog → "Karte oeffnen ..."-Button.

scripts/
  generate_plots.py   3-Modus Vergleich, pooled mean, Error Bars
                      PDF-Bericht 7 Seiten (nur 40m FT8), cursor-basiertes Inch-Layout
                      Helpers: _ctext/_chline/_csection (y in Zoll von oben, kein hardcoded fig-y)

config/settings.py    Frequenzen, Band-Configs, mode-aware get/save_dx_preset()
                      TUNE_FREQS (Band_Mode → Nebenfrequenz -2kHz) + get_tune_freq_mhz()
log/adif.py           ADIF 3.1.7
dt.md                 DT-Timing Analyse: Theorie, Änderungen, Validierungsergebnisse
```

---

## DT-Timing (Stand 23.04.2026 — validiert)

```
RX: DT_BUFFER_OFFSET FT8=2.0 (= 1.5 Buffer + 0.5 WSJT-X Protokoll)
    Korrektur konvergiert auf ~0.24s (nur FlexRadio VITA-49 RX-Hardware)
    Stationen zeigen DT ≈ 0.0–0.2 nach Konvergenz

TX: TARGET_TX_OFFSET = -0.8s = 0.5 (Protokoll) - 1.3 (FlexRadio TX-Buffer)
    FlexRadio puffert TX-Samples konstant 1.3s vor RF-Ausgabe
    Validiert: 8 Zyklen 0.0s DT am Icom, 20m + 40m getestet

Speicherung: ~/.simpleft8/dt_corrections.json → Key "FT8_20m" (pro Modus+Band)
    set_band() / set_mode(mode, band) lädt gespeicherten Wert sofort
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

### DT-Korrektur
- **Pfad:** `~/.simpleft8/dt_corrections.json`
- **Format:** `{"FT8_20m": 0.24, "FT8_40m": 0.24, ...}` (pro Modus+Band)
- Migration von altem Format (`"FT8"` → `"FT8_20m"`) automatisch in `_load_for_current_key()`

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
- **Suchbereich DYNAMISCH:** `min(occupied_bins)..max(occupied_bins)` + `SEARCH_MARGIN_BINS=0`.
  TX landet immer ZWISCHEN niedrigster und höchster Station (= dort wo zugehört wird).
  Kein fester Sweet-Spot mehr (war v0.58-Sackgasse, in v0.59 verworfen).
- **Graduelle Lücken-Toleranz:** stufenweise `(max_count_per_bin, min_gap_bins)`:
  `(0,3)` → `(0,2)` → `(0,1)` → `(1,3)` → `(1,2)`. Bei vollem Band findet der Algo IMMER
  noch eine Position (notfalls in schwach-belegtem Bereich), nie mehr None außer leerem Histogramm.
- **Score:** `gap_width − 100·n_self − 50·n_close − 25·n_near − 0.01·median_distance`
  - `n_self` (Stationen IM TX-Bin) = höchste Strafe (100 Hz/Station) — für Notfall-Stufen
  - `n_close` (±1 Bin) = 50 Hz/Station, `n_near` (±2 Bin) = 25 Hz/Station
  - Median-Distance nur Tiebreaker (0.01)
- **Sticky Gap:** bleibt bei aktueller Frequenz wenn im dynamischen Suchbereich, keine Kollisions-
  Schwelle erreicht (`n_direct >= 2` ODER `n_in_band >= 3`) und neue Lücke nicht > +50 Hz breiter.
  `_measure_gap_around()` refresht `_current_gap_width_hz` nach Sticky-Hit.
- **Such-Trigger SLOT-SYNCHRON (v0.59 Punkt 3):** `_search_slots_remaining` Counter, modus-abhängig
  initialisiert via `_SEARCH_INTERVAL_SLOTS = {FT8:4, FT4:8, FT2:16}` = ~60 s alle Modi.
  `tick_slot()` dekrementiert pro Slot, bei 0 → Such-Trigger + auto-reset.
  Anzeige `seconds_until_search` = `remaining_slots × cycle_s`. Wert friert bei App-Pause ein (gut).
- **Pro-Slot-Aufruf:** `mw_cycle._refresh_diversity_freq_view()` läuft JEDEN Slot in
  `_on_cycle_decoded`, UNABHÄNGIG vom messages-Inhalt. Hinter `if messages:` Guard darf NIE
  was hin was UI/Such-Logik betrifft (P1-Bug aus v0.54-v0.58, fixed in v0.59).
- **`reset()` muss `_current_gap_width_hz = 0` und `_search_slots_remaining` setzen** —
  sonst Bandwechsel-Bug.

---

## Cycle-Zeiten

| Modus | Zyklusdauer | RX-Filter |
|-------|------------|-----------|
| FT8   | 15.0s      | 100-3100 Hz |
| FT4   | 7.5s       | 100-3100 Hz |
| FT2   | 3.8s       | 100-4000 Hz |

---

## ⛔ Statistik-Veröffentlichung — Regel

- **Minimum (Push erlaubt):** Normal + Diversity_Standard + Diversity_Dx je ≥ 2 Messtage,
  Stunden über den ganzen Tag verteilt (mind. 06–22 UTC).
- **Soll fuer solide Aussage (Mike+Claude+R1 2026-04-29):** **5 Tage flaechendeckend**
  pro Stunde-Modi-Slot, Tage ueber 2-4 Wochen verteilt (Solar-Variation glaetten).
  Lueckenfreie Slot-Abdeckung schlaegt mehr-Tage-mit-Luecken.
- **7 Tage Goldstandard:** explizit verworfen — nur ~15% Standard-Error-Reduktion
  gegenueber 5, ~5 Wochen Aufwand vs ~3 Wochen. Diminishing Returns klar erreicht.
  Overengineering im Hobby-Kontext.
- **Auswertungs-Methodik:** Pooled Mean über ALLE Messzyklen aller Messtage und Tageszeiten —
  kein Stunden-Filter. Monatlich wachsende Datenbasis.
- Ergebnis 40m FT8 (Pooled Mean, global, Stand 25.04.2026): Diversity Standard +88%, Diversity DX +123%.

---

## generate_plots.py — Berechnungsmethodik (Tagesdurchschnitt)

**Wie der Ø Sta./15s-Zyklus berechnet wird:**

```
statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md
  → jede Datei = 1 UTC-Stunde, 1 Modus, 1 Band
  → jede Zeile = 1 FT8-Zyklus (15s) mit Spalte "stationen" (Anzahl dekodierter Stationen)

Ø Sta./15s = Summe aller Stationswerte ÷ Anzahl aller Zyklen
             (über ALLE Dateien = alle Tage × alle Stunden × alle Zyklen)

Beispiel Normal: 6.744 Zyklen × ~18.5 Sta./Zyklus
  → Das entspricht dem Tagesdurchschnitt wenn man morgens, mittags, abends misst
  → KEIN Tageszeit-Filter, KEINE Gewichtung nach Stunde oder Tag
  → Je mehr Messpunkte (Zyklen), desto stabiler der Wert
```

**Was der Wert NICHT ist:**
- ❌ Nicht Stationen pro Stunde (wäre 18.5 × 240 = 4.440/h)
- ❌ Nicht der Spitzenwert einer bestimmten Tageszeit
- ✅ Der Durchschnitt über einen ganzen typischen Betriebstag

**Weitere PDF-Layout-Details:**
- **Inch-Koordinaten:** `_yf(y_in) = 1.0 - y_in / _PH` konvertiert Zoll→figure-coord
- **Cursor-Helpers:** `_ctext(fig, y, text, fs)` → gibt neues y zurück; `_chline` → Linie; `_csection` → Titel+Linie+Body
- **Seitenhöhe:** A4 landscape: `_PH=8.27`, `_PW=11.69`, `_CTOP=1.00`, `_CBOT=7.71`
- **Body 11pt / Titel 13pt** — nie hardcoded figure-y, nie `_r_hline` (veraltet, gelöscht)
- **Rescue-Kappen:** grün, nur Diversity-Modi, `load_rescue_by_hour(stats_dir, mode, band, proto)`
- Statistics-Daten: `statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md`

---

## Datenlage (Stand 26.04.2026)

**WICHTIG:** Statistik-Filter v0.63 — nur 20m + 40m FT8 werden noch protokolliert.
Andere Baender werden empfangen aber nicht gespeichert (Skalierungs-Entscheidung).

| Modus            | Band | Tage | Zyklen | Bemerkung |
|------------------|------|------|--------|-----------|
| Normal           | 40m  | 4    | 6.744  | 24h Abdeckung |
| Diversity_Normal | 40m  | 4    | 6.827  | 24h Abdeckung |
| Diversity_Dx     | 40m  | 4    | 9.125  | 24h Abdeckung |
| Normal           | 20m  | 5    | 688    | 13 Stunden, waechst |
| Diversity_Normal | 20m  | 2    | 364    | 5 Stunden, schwach |
| Diversity_Dx     | 20m  | 4    | 2.469  | 18 Stunden |

**40m FT8 Ergebnis (Pooled Mean global, 22.696 Zyklen):**
- Diversity Standard: **+88% / +122%** (ohne/mit Rescue), Rescue allein +35%
- Diversity DX:       **+124% / +158%** (ohne/mit Rescue), Rescue allein +34%

**20m FT8 Ergebnis (Pooled Mean Stunden-Vergleich, Stand 26.04.):**
- Diversity_Normal: +15-30% im Tageshoch (12-16 UTC) — KEIN Antennen-Mismatch
  wie auf 40m, sondern echte Pol-/Pattern-Diversity (ANT1 ist resonant!)
- Diversity_Dx: +59% beim Tag→Nacht-Uebergang (18 UTC) — DX-Modus glaenzt am Skip-Zonen-Rand
- ANT2-Win-Rate Doppelempfaenge: 79% (Std), 86% (Dx) trotz resonantem Kelemen-Dipol auf ANT1
- Datenbasis waechst noch — siehe `Auswertung-20m-FT8.pdf` mit eigenem Narrativ

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
- Datei: `SimpleFT8/HISTORY.md`
- Regel: **Nur anhängen, niemals löschen oder überschreiben.**
- Bei jeder Session: Änderungen am Ende eintragen (Feierabend-Routine Schritt 3).
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

## Bekannte Fallen & Bugs

- **cache.save() nie im Cycle-Loop** — refresht Timestamp → 2h Gültigkeit wird sinnlos
- **_diversity_in_operate vergessen** — once-only Code läuft sonst jeden Zyklus
- **Gain-Messung** — sperrt GUI always-on-top; TX vorher stoppen
- **Stats Warmup** — `_stats_warmup_cycles` an mehreren Stellen in mw_radio.py
- **Statusbar Race** — nach Radio-Connect kurz unsichtbar; Workaround: QTimer.singleShot(200, ...)
- **_r_hline existiert nicht mehr** — ersetzt durch `_chline` in generate_plots.py (nie wieder einbauen)
- **`_tune_active` + `_tune_freq_mhz`** — in `main_window.__init__` initialisiert; `_update_statusbar()` liest beide für `TUNE: xx kHz` Anzeige
- **CQ set_cq_active()** — muss immer wenn `cq_mode=True` aufgerufen werden, nicht nur in CQ_CALLING/CQ_WAIT (sonst bleibt Button nach QSO visuell inaktiv)
- **DT_BUFFER_OFFSET** — FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet!) — bei Modus-Änderungen immer prüfen
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 Fork braucht eigenen Wert
- **dt_corrections.json Key-Format** — "FT8_20m" (Modus_Band), Migration von "FT8" automatisch
- **_was_cq Bug (gefixt)** — `_on_station_clicked` rief `stop_cq()` VOR `start_qso()` → `_was_cq=False` → CQ resumte nicht nach manuellem QSO; Fix: `_cq_was_active` vor stop_cq() sichern, nach start_qso() als `_was_cq=True` setzen
- **Stats Guard (3-fach)** — `btn_cq.isChecked()` + `cq_mode` + `state not in IDLE/TIMEOUT` → robuster gegen desynchronisierte States
- **Histogramm-/Freq-View Update muss IMMER pro Slot laufen** (v0.59 Punkt 3 / P1-Bug-Fix). Niemals einen `if messages:` Guard um `_refresh_diversity_freq_view()` legen — sonst Counter-Drift, hängende Anzeige, TX-Position veraltet
- **CQ-Such-Periode = 60 s konstant** alle Modi (DeepSeek + WSJT-X-Praxis: < 30 s killt QSO-Aufbau weil antwortende Station auf alter TX-Frequenz fixiert ist)
- **`SWEET_SPOT_MIN_HZ`/`MAX_HZ` Klassenkonstanten gibt's NICHT mehr** (v0.58-Sackgasse, v0.59 entfernt). Falls in altem Code Verweis auftaucht: Suchbereich ist dynamisch, nicht fest
- **v0.75 Auto-Hunt:** `_auto_hunt_timer` ist UNABHAENGIG vom Totmannschalter — Maus/Tastatur reset ihn NICHT (Bot-Tarn-Schutz). Nach jedem Stop ist Pflicht-Restart (User-Klick), kein Auto-Resume in `_reset_presence`. Race-Doppel-Check in `select_next` ist ethische Belt-and-suspenders zur 10-Min-Hard-Cap — NICHT als "redundant" entfernen. `_MAX_ATTEMPTS=3` in `core/auto_hunt.py:45` ist Modul-Konstante OHNE Verwendung in der Klasse (3-Versuche-Logik liegt in `qso_state.py`). `btn_omni_cq` hat aktuell keinen eigenen `clicked`-Handler — OMNI-CQ laeuft weiter ueber bisherige Logik (Phase 2-TODO)
- **v0.81/v0.82 Decoder-Signal-Reihenfolge (Fix D + Fix E):** Decoder emittet 3 Signale pro Slot in dieser Reihenfolge: `cycle_decoded` (Aggregation in `mw_cycle._on_cycle_decoded`) → pro msg `message_decoded` (state-Wechsel via `on_message_received`) → `cycle_finished` (Slot-Ende-Hook via `_on_cycle_finished` → `qso_sm.on_decoder_finished`). REIHENFOLGE NICHT AENDERN — `on_decoder_finished` MUSS nach allen State-Wechseln laufen (Doppel-Report-Bug v0.80/v0.81). `_assign_slot_parity` in `_on_cycle_decoded` setzt `msg._tx_even` BEVOR `on_message_received` es liest (mw_qso.py:85, :423) — `cycle_decoded` muss vor `message_decoded` bleiben.
- **`on_cycle_end` vs `on_decoder_finished`:** `on_cycle_end` laeuft am Slot-START (Timer-Pfad, Decoder-unabhaengig) und behandelt: 3-Min-Gesamttimeout, WAIT_73-Tick, CQ_WAIT-Trigger, Counter-Inkrement, Max-Timeout-Check. `on_decoder_finished` laeuft am Slot-ENDE (Decoder-Pfad ueber `cycle_finished`-Signal) und triggert NUR den Retry-Pfad (WAIT_REPORT/WAIT_RR73 mit `timeout_cycles == 1`). Aufspaltung ist kritisch — wer sie zusammenfuehren will: CQ_WAIT bricht bei Decoder-Hang.

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
