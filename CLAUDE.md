Lies nach dieser Datei sofort auch HANDOFF.md **und HISTORY.md** und bestätige alle drei mit je einer Zeile.

---

# ⛔⛔⛔ DEEPSEEK-ZWEITMEINUNG PFLICHT BEI SCHWIERIGEN PROBLEMEN ⛔⛔⛔

Bei jedem **schwierigen Problem** (Bug-Diagnose, Architektur-Frage, „warum
greift mein Fix nicht?", Race-Condition, mehrere fehlgeschlagene Eigen-Fixes)
→ **IMMER DeepSeek als Zweit-Perspektive einbinden.** Verwerfen kann man die
Antwort hinterher — Nicht-Einbinden ist das Einzige, was nicht rückgängig zu
machen ist. **Merksatz: „2 KIs sehen mehr als eine."**

**Aufruf:** `cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py`
(Model `deepseek-reasoner` ist Default.)

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
**Aktueller Stand:** v0.98.29 (27.05.2026) — **P142 SWR-Freeze VOR Phase B nehmen** (voller Workflow autonom, Mike-Field-Reproduktion 12:08-12:10). Bandsperre triggered → manueller TUNE zeigt SWR 2.5 live → Log meldet „freigegeben — SWR 1.0" FALSCH. Root Cause: SWR-Freeze in `_tune_stop` wurde NACH Phase B gelesen — Phase B regelt rfpower runter → Sensor clampt auf 1.0 während Power-Drop. Variante C (R1-empfohlen): Freeze VOR Phase B mit `swr_after_match` (Phase-A-Wert). R1-ORANGE-Catch: Cancel WÄHREND Phase B würde Freeze durchreichen → Hardware-Sicherheits-Risiko → Re-Entry-Sperre setzt jetzt `_tune_last_valid_swr = None`. Final-R1 PUSH FREIGEBEN „sehr KISS-konform". Tests 2138→2149 (+11 P142, 3 alte P76-A angepasst). **Pattern-Klasse Hardware-Sicherheit 3. Iteration** (P53/P76-A/P142). v0.98.28: **P148 SWR-Anzeige nur während TX/TUNE updaten** (voller Workflow autonom). Mike-Field-Bug 27.05. 06:44: nach TUNE OK mit SWR 2.4 zeigte Anzeige „SWR 1.0" im RX-Modus (irreführend „super SWR"). Root Cause: FlexRadio pusht SWR-Meter via VITA-49 kontinuierlich, im RX ist Sensor-Default ~1.0 → überschreibt letzten echten TUNE-Wert. Mike-Wahl Option A (R1-empfohlen): letzten echten TX/TUNE-Wert halten, bei Bandwechsel Reset auf „—". 3 Änderungen: Filter in `mw_tx.py:_on_meter_update` SWR-Branch (`if is_transmitting or _tune_active`), neue Methode `control_panel.reset_swr_display()`, Reset-Aufruf in `mw_radio._on_band_changed`. P53 SWR-Watchdog UNBEEINFLUSST (liest direkt `radio._last_swr`). R1-Final PUSH FREIGEBEN „KISS sehr klein". Tests 2124→2138 (+14 P148). v0.98.27: **P145 Pattern-Check-Skript mode-aware Symmetrie** (voller Workflow autonom). R1-Empfehlung aus P141 (F6) umgesetzt: statisches AST-Tool `scripts/check_mode_symmetry.py` findet Bug-Klasse P102/P114/P135/P141 AUTOMATISCH bevor sie ins Feld kommt. 2 Checks: (1) UI-Update-Symmetrie über `_rx_mode`-Branches (nur `update_*/_refresh_*/show_*`-Prefixe, R1-F1), (2) Mode-Handler-Familien hardcoded `{"cycle_handlers": [_handle_normal_mode, _handle_diversity_operate]}`. Rekursive elif/else-Auflösung (R1-F3). Real-Codebase 0 echte Asymmetrien (2 legitime auf Whitelist mit Begründung). Standalone (Exit-Code 0/1 für CI) + Pytest-Test `test_t2_real_codebase_no_asymmetries`. R1-Final-Verdict: PUSH FREIGEBEN ✓ — „produktionsreif". P141-Bug wäre exakt gefangen worden. **Pattern-Klasse 5. Iteration** (P102/P114/P135/P141/P145) — erstes Tool das vorbeugend abdeckt. Tests 2113→2124 (+11 P145). v0.98.26: **P144 Auto-Hunt busy-station Filter** (voller Workflow autonom). Mike-Field-Bug 26.05. 17:38: Auto-Hunt picked RA5AD 1:45 Min NACH dessen RR73 an R2BRD → 5 Versuche ins Leere (2:30 Min Band-QRM) → QSO verloren (RA5AD's späte Antwort kam 15s NACH Mike's Timeout). Mike-Wahl Option 1: Abort+Skip ohne Cooldown. Filter in `mw_cycle.py:on_message_decoded` zwischen P124-Hash-Resolve und P94/OMNI/SM. `_p144_target_busy_with_other`: True wenn Auto-Hunt-Target an Fremd-Call sendet (msg.caller==target + target!=my_call + not is_cq + not manual_override). `_p144_abort_and_skip`: encoder.abort + _pending_tx_log=None + qso_sm.cancel + neue API `auto_hunt.clear_current_target()` (KEIN Cooldown) + qso_panel.add_info + debug_log. R1-V4-pro Pre-Code 2 ORANGE + 1 GELB (alle eingebaut: manual_override-Check, clear_current_target-API, P139-Logging). Final-R1 PUSH FREIGEBEN ✓ — KISS „genau richtig". Pattern-Familie 9. Iteration (P81/P122/P124/P127/P128/P129/P126/P131/P138/P140/P144). Tests 2091→2113 (+22 P144). FEATURES.md §2 erweitert. **Field-Test pending.** v0.98.25: **P147 HALT-Button stoppt Auto-Hunt SOFORT** (Hardware-Sicherheits-Fix, voller Workflow autonom). Mike-Field-Bug 27.05. 04:42: trotz 3× HALT lief Auto-Hunt weiter (Statusbar „AUTO HUNT — 8:07"), picked YO4NT/TA3ZZ/R9MW nacheinander. Root Cause: `_on_cancel` rief `on_manual_qso_end()` (setzt nur `_manual_override=False`) statt `stop_auto_hunt("manual_halt")` (SOFORT-Stop seit P122). 1-Zeilen-Tausch in `ui/mw_qso.py:404-405` + ausführlicher Bug-Geschichte-Kommentar. `on_manual_qso_end()` bleibt für Confirmed/Timeout-Pfade. R1-V4-pro 7 Findings alle non-blocker. Final-R1 PUSH FREIGEBEN 0 Mängel. Tests 2084→2091 (+7 P147 inkl. T6 Mike's 3× HALT-Idempotenz-Test). **Mike-Vertrauen-Restore:** HALT-Notbremse funktioniert wieder zuverlässig. v0.98.24: **P146 Kalibrierungs-Dialog-Titel mode-agnostisch** (voller Workflow autonom). Mike-Field-Bug 27.05. 06:34: Antennen-Kachel aktiv „DIVERSITY DX", aber Dialog-Titel „Diversity Standard". Architektur: P80 (v0.97.52) unified Gain-Store — Hardware-Gain identisch für Normal+Standard+DX, eine Kalibrierung gilt für beide Modi. `_get_mode_label()` vereinfacht: returnt einheitlich „Diversity (Standard + DX)" für rx_mode=="diversity". `scoring_mode`-Parameter bleibt funktional in Z. 534+680 (Score-Algorithmus-Wahl), nur UI-Titel-Differenzierung entfällt. R1-V4-pro 6 Findings alle non-blocker. Final-R1 PUSH FREIGEBEN 0 Mängel. Lesson: Caller-Mapping `_start_dx_tuning` Z. 1670 übersetzt `"normal"/"dx"` → `"stations"/"snr"` für Dialog — bei „toter Code"-Verdacht immer prüfen. Tests 2082→2084 (+2 P146 + 1 modifiziert). v0.98.23: **P141 Sterne-Anzeige im Diversity-Pfad** (voller Workflow autonom). Mike-Field-Bug 26.05. 17:15: Diversity 14 Stationen Median ~-18 zeigten 1★ statt 4★ (nach P120-Schwellen). Root Cause: `compute_local_conditions` + `update_local_conditions` wurden nur in `_handle_normal_mode` (mw_cycle.py:451-456) gerufen, im Diversity-Pfad fehlten sie. Pattern-Klasse mode-aware Symmetrie 4. Iteration (P102/P114/P135/P141). 2-Zeilen-Fix Variante A in `_handle_diversity_operate` (KISS, hartcodiert `_diversity_stations`). R1-V4-pro Pre-Code 6 Findings: F6 🟠 Pattern-Check-Skript-Empfehlung → als P145 ins TODO. Final-R1 PUSH FREIGEBEN 0 Mängel. **FEATURES.md §11 NEU** dokumentiert die Pattern-Klasse + Risiko-Tabelle für andere mode-aware Funktionen. Tests 2075→2082 (+7). v0.98.22: **P143 QSO-Log-Resurrection nach Bandwechsel** (voller Workflow autonom). Mike-Field-Bug 17:34: 30m-Sende-Einträge tauchten nach Bandwechsel auf 20m nach ~30s wieder im Log auf. Root Cause: `qso_panel` hat 2 Speicher (`log_view` sichtbar + `_entries` Master-SOT seit P95). `mw_radio` 3 Pfade riefen nur `log_view.clear()`, vergaßen `_entries.clear()` → Auto-Trim-Timer (30s) rief `_rerender_all()` aus `_entries` → Resurrection. Fix (Option B Mike-Wahl): Helper `qso_panel.clear_log_completely()` (`_entries.clear() + log_view.clear() + _last_omni_tx_even = None`) + 3 Aufrufer ersetzt (Band/FT-Mode/RX-On-Off). rx_mode-Switch bleibt unangetastet (P115-Spec optische Kontinuität). R1-V4-pro 6 Findings (1 ORANGE OMNI-Parity-Reset bestätigt, 5 GRÜN/GELB). Final-R1 PUSH FREIGEBEN 0 Mängel. **FEATURES.md §10 NEU** dokumentiert die Zwei-Speicher-Architektur + Resurrection-Trigger + Mike-Spec-Tabelle für welche Pfade leeren. Tests 2066→2075 (+9 P143 + 1 P131-T2 Anker-Update). v0.98.21: **P140 Cooldown-Trigger umhängen** (voller Workflow autonom). Mike-Field-Bug 26.05. (5P1KZX/IQ5VK/OE4AHG): 73 der Gegenstation verschwand VOR optischem ✓. Root Cause: P138 setzte `_recently_completed_qsos`-Cooldown in `_on_qso_complete` (= interner RR73-Send-Trigger), aber `qso_complete` und `qso_confirmed_visual` sind zwei getrennte Signale (~30-45s Abstand). Fix: Cooldown raus aus `_on_qso_complete`, rein in `_on_qso_confirmed_visual` (optisches ✓) + symmetrisch in `_on_qso_timeout` (Mike-Spec defensiv „beendet ist beendet" auch nach ✗). Defensive `if call:` Guards. R1-V4-pro 60-Cycle Pre-Code: F1 ROT war false-positive (Auto-Hunt hat EIGENEN Cooldown `_recent_qso` P61, unabhängig) — T6 verifiziert die Trennung. Final-R1: PUSH FREIGEBEN 0 Mängel. **Pattern-Familie 10. Iteration** (P81/P122/P124/P127/P128/P129/P126/P131/P138/P140) — KISS-Korrektur einer KISS-Spec. Tests 2057→2066 (+9 P140 + 1 invertiert P128-T11). FEATURES.md §8 geupdatet (neue 2-Set-Stellen-Mechanik + Auto-Hunt-Trennung + Field-Beispiel mit Vorher/Nachher). v0.98.20: **P139 Auto-Hunt Event-Logging** (Diagnose-Tool für 60s-Delay-Bug). Nutzt existierendes `core/debug_log.py`-Framework (P21 10.05.). Hooks in auto_hunt.py (start/stop/select_next/mark_pick), mw_cycle.py (start_qso), mw_qso.py (tx_started, nur bei aktivem Auto-Hunt). R1-ORANGE-Catch: STOP-Log VOR Defer-Check (sonst deferierte Stops unsichtbar). R1-GELB-Catches: NO_CANDIDATE-Reason differenziert (empty_list/score_zero) + pre/post-Affinity-Counts. Activation via Settings „Debug-Log schreiben" → `~/.simpleft8/debug_YYYY-MM-DD.log`. FEATURES.md Sektion 8a NEU dokumentiert das Framework. Tests 2042→2057. v0.98.19: P138 Whitelist raus („beendet ist beendet", Spec-Umkehr von gestern). Mike-Field-Bug: 73-Eintrag erschien NACH ✓ QSO komplett. Cooldown wird in `_on_qso_complete` (mw_qso.py:557) gesetzt = ✓-Zeitpunkt → vor ✓ kein Cooldown (73 kommt durch), nach ✓ aktiv (alles geblockt inkl. 73). P129-Whitelist `if msg.is_73 or msg.is_rr73: return False` entfernt + msg-Param raus (R1-KISS). Test-Datei `test_p129_whitelist_73.py` umbenannt zu `test_p138_block_73_after_complete.py` + Aussagen invertiert + neue T5-Tests „vor ✓ durchgelassen". Tests 2040→2042. v0.98.18: P137 Tempora-Fix (voller Workflow Variante B). Mike-Field-Bug: Log zeigte „→ Sende ..." NACH dem TX (Watt-Anzeige 0 W). P93-Defer-Mechanik fügt Eintrag in `_on_tx_finished` ein → Vergangenheit korrekt. Mike-Spec: nur Tempora-Fix im Log, KEINE Statusbar-Pre-TX. 1-Zeilen-Code-Änderung in `qso_panel.py:326`. R1-Finding F1: `mw_cycle.py:984` Pre-TX-Info bleibt Präsens (TX läuft dort noch nicht). Tests 2033→2040 (+7). v0.98.17: P136 Call-Validation Auto-Hunt (voller Workflow autonom). Mike-Field-Bug: Auto-Hunt picked „JA" aus `CQ JA HG60IPA`. **2 Schichten gefixt:** (1) Parser `core/message.py:114` erkannte Richtungs-Anrufe nur bei 4 Parts → jetzt `>=3` mit f3-Defensive. (2) Auto-Hunt-Validation via `looks_like_callsign` (public umbenannt aus `_looks_like_call`, 3-Regel-Heuristik: Länge 3-10 + ≥1 Ziffer + ≥1 Buchstabe, slash-tolerant). R1-V4-pro 6× GRÜN PUSH ohne Auflagen. Filtert JA/EU/NA/DX/TEST raus, lässt 1A0KM/4U1UN/R1A0KM durch. Tests 1999→2033 (+34). v0.98.16: P135 Decode-Statusbar (voller Workflow autonom). Mike-Field-Bug Screenshots: Decode-Anzeige sprang zwischen „39 Stationen" und „—" je nach Slot-Parität (leere Decode-Slots zeigten 0/„—" obwohl Akkumulator gefüllt). Fix: mode-aware in `_on_cycle_decoded` (diversity → `_diversity_stations`, normal → `_normal_stations`, else dx_tune → per-Slot). R1-Auflage: else-Branch für DX-Tune ergänzt. Tests 1993→1999 (+6). v0.98.15: P131 Sende-Log bei Bandwechsel verwerfen (voller Workflow autonom). Mike-Field-Bug 15m→20m: „beim Bandwechsel geht noch ein Ruf raus vom alten Band". Root Cause: P93-Defer-Mechanik (`_pending_tx_log` von `tx_started` gesetzt, in `tx_finished` als Sende-Eintrag geschrieben) — bei Bandwechsel + `encoder.abort()` blieb das Pending bestehen → verspätetes `tx_finished` im neuen Band-Kontext. R1-V4-pro ORANGE-Catch (kritisch!): simples Reset reicht NICHT wegen QueuedConnection-Race von `tx_started`-Slot. **V3 (Defense-in-Depth):** (1) `band: settings.band` Tag in `_pending_tx_log` dict, (2) Band-Match-Check in `_on_tx_finished` vor `add_tx`, (3) `_pending_tx_log = None` Reset in `_on_band_changed` außerhalb `is_transmitting`-Block. Pattern-Familie 8. Iteration (P81/P122/P124/P127/P128/P129/P126/P131). Tests 1980→1993 (+13). v0.98.14: P134 Python-Sweep entfernt (Folge-Fix zu P132+P133, voller Workflow autonom). Mike-Field-Bug nach P132: „starter beendet, App startet nicht". Root Cause: `_find_simpleft8_processes_by_cwd` (main.py Z.287-291 SCHRITT 3) killte fremde Python-Prozesse (pytest/IDE/Parent-Bash) — selber Fehlerklassen-Bug wie pgrep, P133 hatte ihn nur aus Bash entfernt, Python-Zwilling übersehen. **V3 (DeepSeek R1-Catch):** Sweep KOMPLETT raus + neuer Helper `_kill_stale_lockfile_owner` für zielgerichtete 1-PID-Prüfung in BEIDEN Pfaden (nach flock-Erfolg fängt alte App-Versionen ohne flock ab, nach BlockingIOError ersetzt inline-Logik). Pattern-Killing-Bug-Klasse vollständig beseitigt (8. Iteration P132→P133→P134). Final-R1 PUSH FREIGEGEBEN. Tests 1960→1980 (+20: 15 statisch Regression-Schutz + 5 dynamisch Mock-basiert). V4-pro 59-Cycle: 0 Halluzinationen. v0.98.13: P132 Single-Instance Architektur-Refactor (Mike-Wut + voller Workflow). Mike-Field-Bug 26.05.: 4 Zombie-Instanzen seit Mittwoch trotz Lock. Root Cause: Pattern-basiertes pgrep auf cmdline-Text fundamental falsch, P43-setproctitle hat es kaputt gemacht. **V3 (DeepSeek-validiert):** fcntl.flock atomar + lsof-CWD-basierte Identifikation. Pattern-pgrep KOMPLETT entfernt. ENTFERNT: `_kill_all_simpleft8_instances`, `kill_old_instances`, `_get_simpleft8_window_pids`+Cache, 4-Wege-Check. R1-Final-Catch (kritisch): `_free_radio_ports` hätte fremde Prozesse killen können → entfernt. Tests 1934→1949 (+15). V4-pro 58-Cycle 0 Halluzinationen. Mike-Vertrauen-Restore. v0.98.12 (gleicher Tag): **P126 Send-nach-Timeout TX-Pipeline-Race-Fix** (autonomer Workflow). Mike-Field-Bug 25.05. 3× belegt (EC3A 07:30, F1IBU 08:59, LA1YKA 13:23): nach calls_made-Limit-Timeout erschien 1 zusätzlicher Send 1 EVEN-Slot NACH ✗-Display. Race-Quellen multipel (is_grid in WAIT_REPORT/TX_CALL, _pending_hunt_reply, Encoder-Sleep). KISS-Fix in `_on_qso_timeout` (mw_qso.py): defensive `encoder.abort()` + `_pending_tx_log = None` (P127-Pattern) am Anfang der Methode — deckt ALLE Race-Quellen ab ohne state-machine-Eingriff. DeepSeek-R1 V4-pro lieferte plausible is_grid-Theorie (timeout_cycles=0-Reset verschiebt TIMEOUT), V2-Self-Review zeigte: Defer-Pfad semantisch problematisch (advance() falsch für is_grid pending) + target==my_call-Bedingung im Mike-Szenario unwahrscheinlich → KISS Option 3 only. Final-R1: PUSH FREIGEGEBEN 0 Mängel „minimalinvasiv, deckt alle Race-Quellen ab". **Pattern-Familie 7. Iteration:** P81/P122/P124/P127/P128/P129/P126 — KISS-Defensive-Stop wenn Kontext wechselt. **V4-pro 56-Cycle:** 0 Halluzinationen. Tests 1911→1921 (+10 P126 Source-Inspektion + Reihenfolge-Checks). Außerdem **FEATURES.md neu** als funktionale Detail-Doku-Referenz (Mike-Wunsch 26.05. „wie funktioniert X?") mit 3 Initial-Sektionen (Diversity DX-Filter, Auto-Hunt Defer-Familie, Hash-Resolution P124) + Anker in CLAUDE.md unter „📖 Funktionsweisen-Referenz". **Field-Test pending** (Mike erreicht morgen wieder).

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
ft8_lib/   C-Bibliothek (MIT, kgoba)
ui/        main_window.py + mw_*.py Mixins (cycle, qso, radio, tx) +
           control_panel.py, rx_panel.py, qso_panel.py, dx_tune_dialog.py,
           direction_map_widget.py
scripts/   generate_plots.py (stats → auswertung/ PNG+PDF DE+EN)
config/    settings.py (Frequenzen, Band-Configs, mode-aware get/save_dx_preset)
log/       adif.py (ADIF 3.1.7 + QRZ-API)
tests/     1727+ automatisierte Regressions-Tests
```

**Wichtige Konstanten in core/ (für Bugfixes):**
- `decoder.py:DT_BUFFER_OFFSET` — FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet)
- `encoder.py:TARGET_TX_OFFSET = -0.8s` (FlexRadio-spezifisch, kompensiert 1.3s TX-Buffer)
- `qso_state.py:MAX_STATION_CALLS = 7` (Hard-Cap WAIT_REPORT) + `MAX_RR73_RETRIES = 5`
- `diversity.py:THRESHOLD = 0.08` (8% → 70:30, sonst 50:50) + `MIN_MEASURE_STATIONS = 5`
- `auto_hunt.py` 10-Min Hard-Cap + Maus-Inaktivitäts-Timeout (5 Min)

**Bekannte UI-Bigfile:** `ui/control_panel.py` (~57 KB — größte UI-Datei).

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
- **FT2-Button versteckt** (`btn_ft2.setVisible(False)` in `control_panel.py`, 2026-05-23) — Standards-Fragmentierung Decodium vs WSJT-X-Improved-FT2. **FT2-Code (decoder/encoder/cycle/protocol) ist intakt** — FT2 = Decodium-Standard (per `core/protocol.py:9`). Reaktivierung: setVisible-Zeile löschen + `freq_frame` zurück auf `grid.addWidget(freq_frame, 0, 4, 1, 3)`.
- **Band/Modus werden nicht persistiert** (2026-05-23, Mike-Entscheidung) — App startet IMMER mit 20m+FT8 (`DEFAULTS` in `config/settings.py:49`). `load()` forciert die Werte beim Start, `save()` schliesst sie vom JSON-Dump aus. Runtime-Updates per `settings.set('band'/'mode', ...)` funktionieren weiter (`mw_radio.py:405/505`) — nur über App-Neustarts hinweg gibt es kein Merken mehr.
- **QSO-Finish-Button (`btn_advance`) versteckt** (`control_panel.py:1199`, 2026-05-23) — Mike: nie gebraucht (FT8-Timeouts MAX_STATION_CALLS=5 + 3-Min-Gesamt fangen stuck-Gegenstationen ab). Code/Signal/Handler intakt; `setEnabled`/`setText`-Calls laufen weiter auf hidden Button ohne Wirkung. HALT bleibt — andere Rolle (Sicherheits-Notbremse). Reaktivierung: `setVisible(False)`-Zeile löschen. QHBoxLayout kollabiert hidden Widget automatisch, kein Layout-Shift nötig.
- **DXTuneDialog State-Machine (P74-A v0.97.94):** Dialog kennt drei States `TUNE → GAIN_CYCLES → FINISHED`. State `TUNE` nur aktiv wenn `with_tune_phase=True` (Bandwechsel-Pipeline Fall B + KALIBRIEREN mit Tuner). Klassen-Signal `auto_tune_done = Signal(bool, float, float)` ist API-identisch mit AutoTuneDialog — `_tune_post_swr_check` (mw_tx.py:343/438/454) emittiert via Duck-Typing auf `_auto_tune_dialog` (kann jetzt beide Typen sein). Flag `_tune_phase_finished` ist Doppel-Trigger-Schutz zwischen Backup-Timer und echtem Signal — NICHT entfernen. Cancel im State 'TUNE' rotiert `parent._tune_post_check_token` VOR `_tune_stop` (sonst Signal-an-zerstörten-Dialog-Crash). AutoTuneDialog bleibt für Fall A (TUNE ohne Gain-Mess) — NICHT löschen.
- **rx_mode Setter-Symmetrie (P102 v0.97.97):** `_on_rx_mode_clicked` (User-Klick-Handler, `control_panel.py:1697`) und `set_rx_mode` (programmatischer Pfad, Z. 1725) müssen am Ende **beide** `_refresh_antenna_status_label()` aufrufen, sonst bleibt der Header-Status-Suffix der eingeklappten Antennen-Kachel stale. Im Normal-Mode läuft kein `update_diversity_ratio` aus dem Cycle-Loop → kein indirekter Refresh. Bei neuen rx_mode-Settern Refresh nicht vergessen.
- **Stale-Gain-Warning Aufruf-Pflicht (P113 v0.97.98):** `_check_stale_gain_warning` muss in BEIDEN Bandwechsel-Pfaden aufgerufen werden — Diversity-Pfad vor `return` (Z. 713), Normal-Pfad NACH `_update_statusbar()` (Z. 718, sonst überschreibt der Default-Statusbar den Toast). Schwelle strikt > 14 Tage (`STALE_GAIN_WARNING_DAYS = 14` + `days <= 14: return` → Toast ab Tag 15, R1-F2-verifiziert). Falls neue Bandwechsel-Pfade entstehen: Aufruf nicht vergessen.
- **MODUS+BAND-Status-Sync Aufruf-Pflicht (P114 v0.97.99):** `_refresh_modeband_status_label` MUSS in `_set_mode` UND `_set_band` aufgerufen werden (Symmetrie zu P97/P102, jeweils NACH `emit`). Format „— {mode} · {band}" mit Mittel-Punkt U+00B7. `lbl_mb_status` ist nur sichtbar bei `set_collapsed(True)` (analog Antenne/Radio). Bei neuen Mode/Band-Settern Refresh nicht vergessen.
- **RX-Liste/Stations-Dicts Lösch-Pfade (P115 v0.98.00):** RX-Liste (`rx_panel.table`) und Stations-Dicts (`_diversity_stations`, `_normal_stations`) werden NUR in 3 Pfaden gelöscht: `_on_band_changed`, `_on_mode_changed`, `_on_rx_panel_toggled`. `_enable_diversity`, `_disable_diversity`, `_activate_diversity_with_scoring` löschen NIE mehr (Mike-Spec: gleiches Band → optische Kontinuität wie Fortschrittsbalken, Aging-Mechanismus räumt alte Einträge automatisch nach `AGING_SLOTS_*` × slot_duration_s auf). `clear_panels`-Parameter aus P110 komplett entfernt. `qso_panel.log_view.clear()` in `_disable_diversity` bleibt (Chronik). Bei neuen Funktionen die RX-Mode-Switch oder Kalibrierung handhaben: KEIN setRowCount(0) hinzufügen.
- **Stats-Cleanup FIFO statt Datum (P116 v0.98.01):** `core/stats_cleanup.py` ersetzt 90-Tage-Datum-Cleanup durch FIFO-Sliding-Window pro `(Modus, Band, Proto, Stunde)`-Bucket mit Default N=30. 3 Funktionen: `prune_stats_to_max_per_bucket()`, `cleanup_antenna_qso_older_than_days()` (BLEIBT 90 Tage für Tages-Format), `invalidate_bandpilot_cache_if_needed()`. Bucket-Key `(str(relative_parent), hour_str)` — Stations/-Subdir ist eigener Bucket (parallel geschrieben → identische Datums → identisches Pruning). Antenna_QSO wird via `if "antenna_qso" in f.parts: continue` aus Bucket-Pruning ausgeschlossen. Bandpilot-Cache (`~/.simpleft8/bandpilot_hourly.json`) wird gelöscht wenn Buckets gepruned wurden — sonst zeigt UI veraltete Aggregate.
- **Band-Aktivitäts-Script Standalone (P117 v0.98.02):** `scripts/band_activity_summary.py` ist STANDALONE — kein Hook in `main.py` oder `generate_plots.py` (Mike-Spec). Aufruf via `./banduebersicht.sh` im Root. Bei Format-Änderungen in `statistics/` müssen `ROW_RE`/`FILE_RE` und Aggregations-Logik (inkl. `MIN_CYCLES_PER_BUCKET`) hier synchron gehalten werden — keine automatische Kopplung an `core/mode_recommender.py`. `MIN_CYCLES_PER_BUCKET=12` (R1-Catch — 30 wäre zu hoch für junge Bänder mit 5-9 Tagen). Output: `auswertung/bandaktivitaet.png` (DE) + `auswertung/en/band_activity.png` (EN). n8n-tauglich (idempotent, Exit-Code, sauberes Logging).
- **Auto-Hunt-Stop-Defer (P122 v0.98.05):** `core/auto_hunt.py` `stop_auto_hunt(reason)` deferiert 3 Reasons (`timer_expired`, `mouse_inactive_5min`, `totmann_expired`) bei aktivem QSO via `is_qso_active_callback` (Konstruktor-Param, Default `lambda: False` für Backward-Compat). `_pending_stop_reason` Runtime-State. `flush_pending_stop()` wird in 3 QSO-Ende-Handlern in `mw_qso.py` aufgerufen (HALT, qso_confirmed_visual, qso_timeout) — IMMER VOR `_flush_auto_hunt_stop_msg()` (P81 Meldung) damit Reihenfolge im Log stimmt. FIFO-First-Wins bei multiple Defers. Sofort-Stop (HALT/Band/SWR) resettet Pending. Defensive Idempotenz-Check (`if not active and pending is None: return`) verhindert doppelte Signal-Emission. Pattern reused `_qso_active_for_msg_defer()` aus P81 — keine Logik-Drift möglich.
- **Multi-Radio Hardware-Konstanten (P121 v0.98.04):** Class-Variables `tx_buffer_s`, `rx_hardware_offset_default_s`, `tune_power_w` MÜSSEN in JEDER konkreten Radio-Klasse explizit gesetzt sein (Duck-Typing, KEINE Vererbung weil FlexRadio von QObject erbt, nicht von RadioInterface). ABC-Defaults sind nur Notfall-Fallback. Settings `radio_timing` ist User-Override-Slot — Defaults kommen aus Radio. Init-Reihenfolge `_init_radio_state` MUSS VOR `_init_core_components` bleiben (sonst AttributeError: Encoder braucht `self.radio.tx_buffer_s`). TUNE-Power läuft IMMER über `self.radio.tune_power_w` (5 Pfade: `mw_tx._tune_start`, `mw_tx._start_auto_tune_for_band_change`, `mw_radio._start_tune_only`, `mw_radio._start_dx_tuning`, `mw_radio._start_dialog_tune_sequence`) — kein Settings-Override (Hardware-Safety). IC7300/IC7100-Stubs `supports_diversity=False`, `get_antennas()=["ANT1"]` — Diversity-System ist auf 2 Antennen ausgelegt, IC-Forks nutzen es nie.
- **Band-Activity Berliner Zeit (P118 v0.98.03):** `band_activity_summary.py` aggregiert auf Berliner Zeit (DST-aware via `zoneinfo.ZoneInfo("Europe/Berlin")`). `_utc_file_to_local_hour(date_str, utc_hour)` konvertiert pro File-Datum — Mai→UTC+2, Dezember→UTC+1, Wechsel-Tage automatisch über IANA-Datenbank. Pragmatik: 1 File = 1 lokale Stunde (DST-Wechsel-Tag-Edge-Cases sind 2/365 = 0.5%, statistisch irrelevant). Labels: „Stunde (Berlin)" / „Hour (Berlin)". macOS bringt tzdata via `/usr/share/zoneinfo` nativ mit — Linux/Windows-Forks bräuchten `pip install tzdata` Fallback.

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
