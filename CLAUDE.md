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
**Aktueller Stand:** **v0.97.5 Session 12.05.2026 — P39 osascript-Window-Title-Filter auf Python-Prozesse begrenzt, Tests 1136.** Bug-Wurzel von Mike's „App laeuft bereits"-Falschmeldung war NICHT PID-Recycling (P38), sondern dass osascript jeden visible Prozess mit „SimpleFT8" im Window-Titel als laufend interpretiert hat — inkl. Chrome-Tab auf GitHub-Repo. Fix: `if procName is "Python" or procName starts with "python"` Filter. Live-verifiziert 12.05. Workflow V1→V2→R1(0 KRITISCH)→V3. Plan-File `prompts/p39_window_title_python_filter_r1.md`. Push pending mit P38 zusammen.

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

## 📋 Verbindlicher Feature-Workflow

Fuer alle nicht-trivialen Features (>5 Zeilen Code, neue Module, Architektur-
Aenderungen): **siehe `docs/WORKFLOW.md`** — Schritt 0 Code-Verifikation →
V1 → V2 (Self-Review) → DeepSeek-R1-Review → V3 → Mike-Freigabe → Plan-Mode → Code.

Triviale Aenderungen (Tippfehler, Kommentar-Updates, < 5 Zeilen) brauchen den
Workflow nicht.

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

## Mehrstufiger Prompt-Workflow (PFLICHT bei nicht-trivialen Features/Bugs)

Vor jeder nicht-trivialen Umsetzung (>5 Zeilen, neues Modul, Architekturfrage,
mehrere Probleme zugleich) durchlaufen wir gemeinsam diesen Ablauf — KEIN
direkter Sprung in `/plan`:

1. **Probleme erkennen + Prompt V1 entwerfen** (Claude)
   — Symptome präzise beschreiben, Datei:Zeile-Referenzen, Akzeptanzkriterien.
2. **Rolle frischer KI: Self-Review → V2** (Claude)
   — Was fehlt? Was ist mehrdeutig? Was übersieht V1? Lücken füllen, V2 schreiben.
3. **V2 an DeepSeek** (`tools/deepseek_review.py`, model `deepseek-reasoner`)
   — DeepSeek bekommt explizit den Auftrag den Prompt zu kritisieren und
   konkret zu verbessern (nicht das Problem zu lösen).
4. **DeepSeek-Findings einarbeiten → V3** (Claude)
   — Kritisch prüfen (siehe DeepSeek-Caveat oben), V3 schreiben.
5. **Mike vorlegen** — Mike liest V3, gibt Freigabe oder Korrekturen.
6. **Planungsmodus + Umsetzung** — erst dann `/plan`, dann atomare Commits.

**Trigger-Sätze von Mike** für diesen Workflow:
- „selbe vervahrensweise wieder" / „wie bei Locator-DB"
- „erst V1 dann zu deepseek" / „prompt entwerfen"

**Wann der volle V1→V2→V3-Workflow lohnt (Trigger-Schwelle):**
Mindestens EINES der folgenden Kriterien erfüllt → vollen Workflow fahren:
- Task hat ≥2 unabhaengige Akzeptanzkriterien
- Mathematisch/geometrisch (Projektion, Rotation, Filter, Algorithmen)
- Beruehrt ≥2 Dateien oder fuehrt neues Modul ein
- Threading/Persistence/IO neu beteiligt
- Architektur-Entscheidung (siehe „Architektur-Entscheidungen" oben)

**Wann V1 direkt reicht (Workflow uebersprungen):**
- Tippfehler, Umbenennungen, <5 Zeilen
- Lokaler Patch in EINER Methode ohne Architekturwirkung
- Reines Doku-Update, Test-Anpassung an bestehende API
- Bugfix mit klarer Datei:Zeile-Diagnose und einzigem Akzeptanzkriterium

→ Bei Grenzfall lieber Workflow fahren als Sackgasse riskieren.
   Beispiel-Mehrwert siehe v0.66 Map-UI (Sektor-Rotation): DeepSeek fand
   1°→5°-Stabilitaetsproblem, Helper-Extraktion, Test-Reduktion.

**Bei Plan-Mode selbst:** nur die Plan-Datei editieren. Read/Grep/Glob zum
Verifizieren von Code-Behauptungen ist ok. Plan-Datei mit konkreten
Datei:Zeile-Referenzen versehen — Subagents können das schnell verifizieren.

**Begründung:** Mehrstufige Validierung verhindert Over-Engineering.
Beispiel v0.67-Locator-DB: V2 hatte 26-Buchstaben-Splitting, LRU-Cache,
Write-Ahead-Log — DeepSeek hat die Komplexität auf 1/4 reduziert.

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
