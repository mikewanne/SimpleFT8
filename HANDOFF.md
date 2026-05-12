# HANDOFF — SimpleFT8

## Stand 2026-05-12 abends: v0.97.9 P45 Stats-Guard OMNI-CQ (autonom durchgearbeitet)

**Code:** v0.97.9 — OMNI-CQ wurde im `_log_stats` nicht abgefangen →
Stats-Verfälschung während OMNI-RX-Slots. Jetzt eigener Guard-Block.
**Tests:** **1160 grün** (1156 + 4 P45).
**Backup vor Code:** `Appsicherungen/2026-05-12_v0.97.8_vor_p45_omni_stats_guard/`.
**Push:** ausstehend (Mike beim Termin) — gleich nachgeholt.

### Was Mike heute anstoßte (3 Themen):
1. **DT-Korrektur grün → Statusbar grün-Bug** — in TODO als **P44**
2. **Stats-Sperren-Check für OMNI** — **P45 erledigt** (dieser Stand)
3. **Bandpilot Normal-Reintegration** — in TODO als **P46**
   (Mike+Claude+R1 einig, Schwellen MIN_DAYS_HOUR=3 / MIN_CYCLES_HOUR=20
   bereits vorhanden, nur Code-Erweiterung nötig)

### Memory-Watcher läuft weiter
Daemon PID 81237 sampelt SimpleFT8 alle 60s nach
`~/.simpleft8/memory_watch.log`. TTS-Server bleibt aus
(`launchctl unload`).

### Vorgänger-Stand (v0.97.8)

Decoder-Diagnose-Code opt-in via `SIMPLEFT8_DECODER_DIAG=1`. R1-bestätigter
Verdacht `_audio_buffer_24k` Skip-Bug. Erste Beobachtung: RSS ~270 MB
stabil, 0 Skips → Hauptverdacht entlastet, vermutlich war 124-GB-Crash
hauptsächlich TTS.

**Code:** v0.97.8 — Decoder-Diagnose opt-in via `SIMPLEFT8_DECODER_DIAG=1`.
**Tests:** **1156 grün** (1148 + 8 neue P30-Tests).
**Backup vor Code:** `Appsicherungen/2026-05-12_v0.97.7_vor_p30_diagnostic_code/`.
**Memory-Watcher-Daemon:** PID 72060 läuft, Log `~/.simpleft8/memory_watch.log`.
**Push pending:** v0.97.8-Commits noch lokal.

### Nächster Schritt — Mike aktiviert Diagnose

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
export SIMPLEFT8_DECODER_DIAG=1
./venv/bin/python3 main.py
```

→ App 1-3 Tage in Diversity laufen lassen.
→ Auswerten: `grep "P30-DIAG" ~/.simpleft8/debug_*.log | tail -50`
→ Wenn `buf_chunks` steigt + `skips_total` steigt + `busy_held > 30s`:
  Hypothese bestätigt → P30.FIX als eigener Workflow.

### Vorgänger-Stand (v0.97.7)

**Code:** v0.97.7 + P42-README-Passage + ADIF-Aufräumen + Stats neu.
**Tests:** **1148 grün**, alles auf GitHub bis `569aa9b`.
**Field-Test heute:** Mike-Bestätigung 70:30-Pattern wird eingehalten,
Adaptive Diversity läuft sauber.

## Heute 12.05. Bilanz (Mike's „Therapie-Marathon"-Tag)

**8 Versions-Bumps in einem Tag:**

| Version | Inhalt |
|---|---|
| v0.97.0 P34 | Adaptive Diversity (Hauptfeature, slot-für-slot live) |
| v0.97.1 P35 | Startup-Bugs A/B/B5 (defer/resume, Queue-Reset, Auto-Reactivate) |
| v0.97.2 P35 D/E/F | Live-Field-Fixes (App-Start IMMER 20m FT8 Normal) |
| v0.97.3 P37 | RX-Antennen-Anzeige im „● DYNAMISCH (live)"-Label |
| v0.97.4 P38 | PID-Recycling-Schutz im starter.command |
| v0.97.5 P39 | osascript Python-Process-Filter (Browser-Tab-Bug) |
| v0.97.6 P40 | P37-Komplettierung (3 weitere current_ant-Aufrufer) |
| v0.97.7 P41 | audio_streaming-Flag — OMNI-CQ Antennen-Switch entblockt |

**Plus Doku/Daten ohne Version-Bump:**
- README + Hilfe: Adaptive-Diversity-Konzept (DE + EN)
- P42 README-Passage „Why Diversity Matters for FT8" (R1-verifizierte
  Physik: Headroom-Asymmetrie + Pol-/Sektor-Diversity)
- ADIF-Cleanup: Master-ADIFs in Backup, Jahresarchiv 2026 erstellt
- Statistiken regeneriert (DE+EN PDFs, alle PNGs)
- QRZ-Upload-Analyse + Diagnose

**Workflow-Disziplin:** **alle 9 Aufgaben** voll V1→V2→R1→V3 mit
DeepSeek durchgezogen. R1 fand kritische Fehler in:
- P41 (abort-Race mit FlexRadio-Buffer-Latenz)
- P42 (Pol-Diversity als Hauptmechanismus, nicht primaer Headroom)
- P35-AK5 (Cache-Reuse-Respekt)
- P26-K2 (Modal-exec singleShot-Defer)

## Field-Test Status

✅ Adaptive Diversity live verifiziert (70:30-Pattern eingehalten,
   slot-für-slot Wechsel)
✅ OMNI-CQ + Adaptive zusammen funktional (P41 entblockt Antennen-Switch)
✅ App-Start IMMER 20m FT8 Normal (P35-F)
✅ RX-Antennen-Label wechselt korrekt im Adaptive-Modus (P37+P40)

## Offene Punkte (nicht heute, aus TODO.md)

**🔥 Hoch:**
- **P30** MEMORY-LEAK 124 GB nach Tagen Laufzeit (KRITISCH, Diagnose
  steht aus)
- **P12** QSO-Postprocessing-Hang (Partial-Fix da, sauberer Async-Refresh
  weiter offen)
- **P27** MESS-GUARD Radio-Verbunden-Check vor Antennen-Mess
- **P25** RADIO-IP-LATE-SETTING prüfen ob obsolet

**📋 Mittel:**
- **P34-Stufe2** Statik-Pipeline komplett raus (nach 2-3 Wochen Adaptive
  Field-Test)
- **P32** RX-Panel-Spalten-Persist, **P33** QSO-fertig-Reihenfolge,
  **P24** Last-RX-Mode-Persist

**🛠 Niedrig:** P18, P20, P29

## „2-Unsichtbare-Instanzen"-Bug

Bei Debug-Sessions vor heute hatte Mike gelegentlich eine 2. Instanz im
Hintergrund laufen sehen. **NICHT identisch mit P38/P39 PID-Recycling/
Browser-Tab-Bug.** Vermutlich `atexit._release_lock_on_exit()` greift
unter Qt-Window-Close manchmal nicht. Eigener Workflow noetig — als
„offen" vorgemerkt.

## Workflow-Lessons heute

- P40 wurde Folgefix zu P37 weil Memory-Lesson `feedback_partial_fix_
  check_other_paths.md` nicht direkt angewendet — bei P40 nachgezogen.
  Bei Methoden-Signatur-Erweiterungen IMMER grep ueber alle Aufrufer.
- R1-Findings haben heute MEHRFACH kritische Fehler gefangen die ich
  uebersehen haette — Mike-Anweisung „DeepSeek IMMER bei nicht-trivialen
  Aufgaben" hat sich klar bewaehrt.
- Saubere Compact-feste Plan-Files (`prompts/p3[4-9]_*.md`,
  `prompts/p4[0-2]_*.md`) ermoeglichen nahtlose Session-Wiederaufnahme.

## Stand 2026-05-12 morgens: v0.97.7 P41 audio_streaming-Flag

**Code:** v0.97.7 lokal — OMNI-CQ blockierte Antennen-Switch ueber 20
Slots wegen zu grobem `is_transmitting`-Check. Feinerer Flag
`is_audio_streaming` (nur von ptt_on bis ptt_off True) fixt das.
**Tests:** **1148 grün** (+8 P41).
**Push:** done.

## P41 fixt OMNI-CQ Antennen-Switch-Blockade

Mike-Field-Test 12.05. morgens mit OMNI-CQ + Adaptive Diversity 30:70:
Antennen wechselten 5 Minuten lang nicht, Adaptive-Buffer einseitig
gefuellt, Label statisch „RX Ant1".

**Wurzel:** `encoder.is_transmitting` blieb durchgaengig True ueber
ganzem Worker-Lauf (Setup + Sleep + Audio). Bei OMNI-CQ alle 30s neuer
Worker → keine True-Luecke zwischen den Slots.

**Fix:** neuer feiner Flag `is_audio_streaming` der NUR von `ptt_on()`
bis `ptt_off()` True ist. Deckt 1.3s FlexRadio-Buffer-Latenz mit ab.

R1-KRITISCH: `abort()` darf Flag NICHT setzen (Race mit noch laufender
send_audio im FlexRadio-Buffer). Worker-finally setzt Flag zurueck.

## Workflow

V1 → V2 (Self-Review) → R1 (1 KRITISCH umgesetzt + 1 SOLLTE umgesetzt +
1 SOLLTE verworfen weil Bug-Wiederherstellung) → V3 → Code.
Plan-File: `prompts/p41_audio_streaming_flag_r1.md`.

**Backup vor Aenderung:** `Appsicherungen/2026-05-12_v0.97.6_vor_p41_omni_antenna_fix/`.

## Stand 2026-05-12 nachts: v0.97.6 P40 P37-Komplettierung

**Code:** v0.97.6 lokal — 3 weitere Aufrufer von `update_diversity_ratio`
reichen jetzt `current_ant` durch. Adaptive-Label zeigt RX-Antenne
verlaesslich auch bei Ratio-Wechseln.
**Tests:** **1140 grün** (+4 P40 vs v0.97.5).
**Push:** pending.

## P40 fixt P37-Partial-Fix

Mike-Field-Test 12.05. abends: Label „● DYNAMISCH (live)" zeigte den
RX-Antennen-Suffix nicht. P37 hatte nur 1 von 4 Aufrufern angefasst
(klassischer Partial-Fix, Memory-Lesson verfehlt).

**3 gefixte Stellen:**
- `main_window.py:1357` `_on_dynamic_ratio_changed` (Haupt-Übeltäter,
  bei jedem Ratio-Wechsel getriggert)
- `mw_radio.py:990` Adaptive-Aktivierung
- `mw_cycle.py:290` Mess-Pfad

## Workflow

V1 → V2 (Self-Review + Memory-Lesson zitiert) → R1 (DeepSeek, 0 KRITISCH,
1 SOLLTE→Integration-Test umgesetzt) → V3 → Code.
Plan-File: `prompts/p40_p37_completion_r1.md`.

## Stand 2026-05-12 nachts: v0.97.5 P39 Window-Title-Check Python-Filter

**Code:** v0.97.5 lokal — osascript filtert jetzt nur Python-Prozesse
(Browser-Tabs mit „SimpleFT8" im Titel matchen nicht mehr).
**Tests:** 1136 unveraendert (Bash-Script-Edit).
**Push:** mit P38-P39 zusammen pending.

## P39 fixt den eigentlichen Bug

P38 war PID-Recycling-Schutz im Fallback — korrekt, aber griff nicht
beim aktuellen Browser-Tab-Fall, weil osascript-Primaer-Check schon
falsch matcht. P39 fixt die Wurzel: nur Python-Prozesse werden gepruefte.

**Live-verifiziert 12.05.:** Chrome-Tab mit GitHub-Repo offen → osascript
returnt leer → Starter laeuft sauber durch.

## Workflow

V1 → V2 (Self-Review) → R1 (0 KRITISCH, 2 KOENNTE/SOLLTE praktisch
irrelevant) → V3 (V2 + 1 Kommentar zur PyInstaller-Zukunft) → Code.
Plan-File: `prompts/p39_window_title_python_filter_r1.md`.

## Stand 2026-05-12 nachts: v0.97.4 P38 PID-Recycling-Schutz im Starter

**Code:** v0.97.4 lokal — PID-Recycling-Bug im `starter.command` gefixt.
**Tests:** 1136 unveraendert (Bash-Aenderung, keine Python-Module).
**Push:** zusammen mit v0.97.3 P37 nach Mike-OK.

## Was P38 fixt

Mike-Screenshot 12.05.2026: Starter zeigte „SimpleFT8 laeuft bereits"
mit Process-Info `/Applications/Google Chrome.app/...`. Chrome hatte
PID 23196 vom beendeten SimpleFT8 recycled bekommen, `kill -0` meldete
„lebt", Mike wurde am Neustart gehindert.

**Fix:** `ps -p $LOCK_PID -o command=` + `grep` auf `SimpleFT8.*main\.py`
hinter dem `kill -0`. Wenn PID nicht zu SimpleFT8 gehoert → Lock
loeschen + starten.

**Wichtige Nicht-Identitaet:** Das ist NICHT der alte „2 unsichtbare
Instanzen"-Bug von Mike's Debug-Sessions. Der hatte einen Cleanup-Issue
(atexit unter Qt-Close nicht zuverlaessig) und ist ein separates
Folgeprojekt.

## Workflow

V1 → V2 (Self-Review) → R1 (0 KRITISCH, 1 SOLLTE bereits quoted) → V3 → Code.
Plan-File: `prompts/p38_pid_recycling_starter_r1.md`.

## Stand 2026-05-12 nachts: v0.97.3 P37 RX-Antennen-Anzeige im Adaptive-Label

**Code:** v0.97.3 lokal — Mike-Wunsch 12.05. nach Live-Test:
Adaptive-Phase-Label um aktive RX-Antenne erweitert.
**Tests:** **1136 grün** (+5 P37 vs v0.97.2).
**Push:** pending bis Mike OK gibt.

## Was P37 macht

Im Antennen-Panel wird das blaue Label jetzt:
- **„● DYNAMISCH (live) — RX Ant1"** wenn aktueller Slot ANT1 hört
- **„● DYNAMISCH (live) — RX Ant2"** wenn aktueller Slot ANT2 hört
- Update slot-für-slot (alle 15 s bei FT8)
- Statik-Modus unverändert (kein RX-Anhang)

So sieht Mike live dass das Diversity-Pattern wirklich slot-für-slot
wechselt und nicht starr auf einer Antenne hängt.

## Workflow V1→V2→R1→V3 (alle Schritte)

- V1+V2 (Self-Review): Spec + Code-Verifikation + Race-Check
- R1: DeepSeek-Reasoner Review → 0 KRITISCH, 1 Verbesserung (5 Tests
  statt 1) → in V3 übernommen
- V3 = V2 + erweiterte Test-Coverage
- Code: 2 Files, ~6 Zeilen
- 5 Tests grün (T1-T5 R1-Coverage)

## Plan-Files

- `prompts/p37_rx_antenna_label_r1.md` — R1-Review-Auftrag + V2-Plan

## Stand 2026-05-11 abends: v0.97.2 P35 Bug D+E+F Live-Field-Test läuft

**Code:** v0.97.2 lokal — Bug D+E+F nach v0.97.1 noch nachgezogen (Mike-
Live-Diagnose während Field-Test 11.05. abends).
**Tests:** **1131 grün** (+2 P35-Bug-E-Tests gegenüber v0.97.1).
**Push:** pending bis Mike kompletten Field-Test grün gibt.

## Mike-Live-Field-Test 11.05. abends (in Progress)

- ✅ **App-Start**: 20m FT8 Normal — kein „messen 0/6"-Hänger (Bug F greift)
- ✅ **Normal → Diversity DX**: beide Antennen aktiv, Statik-Mess sauber
- 🔄 **Dynamic-Toggle**: blau angezeigt, Buffer füllen sich
  (Log `[DYNAMIC] record_slot` zeigt Scores 99-117, A1=2/5 + A2=1/5
  bei `:55:57` — wartet auf 5/5 + 5/5 für erste evaluate)

## Was Bug D+E+F dazu fixten (v0.97.2)

- **Bug D**: `_on_band_changed` löst `on_band_change()` nur noch bei
  `rx_mode=diversity` UND `radio.ip` aus. Sonst Fallback Phase=operate.
- **Bug E**: Bandpilot überschreibt NIE Normal-Modus. Skipt wenn
  current=normal ODER target=normal. Mike-Vision: Bandpilot wählt nur
  zwischen Diversity Standard ↔ DX.
- **Bug F**: App-Start IMMER 20m FT8 Normal (hardcoded in `__init__`).
  Settings-Restore für band+mode entfernt. Mike-Anweisung 11.05.

Commits: `6347c0a` Bug D, `18db03f` Bug D+E + Tests, `91728f7` Bug F.

## Was P35 fixt

3 Bugs die Mike beim P34-Field-Test entdeckte:

- **Bug A:** Statik-Mess hing bei radio.ip=None → Antennen-Switch nur auf
  ANT1. Fix: bei radio.ip=None Init aufschieben, nach Radio-Connect via
  `_check_diversity_preset` nachholen.
- **Bug B:** `_apply_dynamic_toggle` leerte Queue + current_ant nicht →
  P34-Hook bekam alte (A1, "measure")-Einträge, Buffer A2 blieb leer.
  Fix: Queue + current_ant unter Lock VOR activate() resetten.
- **Bug B5:** Toggle verlor bei Mode-Wechsel. Mike-Q3-Wunsch: Toggle
  überlebt Session. Fix: `_activate_diversity_with_scoring` ruft
  `_apply_dynamic_toggle(True)` wenn Settings-Toggle AN.

**Plus AK5 (R1-Q4 KRITISCH):** `activate()` respektiert Cache-Reuse-Ratio.
Cache 70:30 wird NICHT mehr auf 50:50 zurückgesetzt beim Toggle AN.

## 5 atomare Commits

| # | Inhalt | Datei |
|---|---|---|
| C1 | `activate()` AK5 Cache-Reuse-Respekt + 2 Test-Anpassungen | `core/dynamic_diversity.py` + `tests/test_diversity_dynamic.py` |
| C2 | `_apply_dynamic_toggle` Queue+current_ant Reset + 11 P35-Tests | `ui/main_window.py` + `tests/test_p35_startup_bugs.py` NEU |
| C3+C4 | `_enable_diversity` Defer + Resume + Auto-Reactivate | `ui/mw_radio.py` |
| C5 | APP_VERSION 0.97.0→0.97.1 + Doku + Final-R1-Lock-Fix | `main.py`, HISTORY/HANDOFF/CLAUDE |

## Field-Test F1-F8 (Mike)

V3 §6 — Auszüge:
- **F2:** „ohne Radio weiter"-Pfad → Diversity startet sauber wenn Radio kommt
- **F4:** Cache 70:30 + Toggle AN → **bleibt 70:30** (kein 50:50-Reset)
- **F6+F7:** Toggle überlebt Mode-Wechsel (Diversity↔Diversity↔Normal)

**Bestanden wenn F1-F4 sauber, F5-F8 wie spezifiziert.**

## Plan-Files (Compact-fest)

- `prompts/p35_diversity_startup_fix_v1.md` — Initial-Entwurf
- `prompts/p35_diversity_startup_fix_v2.md` — Self-Review nach Mike-Q1-Q3
- `prompts/p35_diversity_startup_fix_r1.md` — DeepSeek-R1-Kritik
- `prompts/p35_diversity_startup_fix_v3.md` — **FINAL** mit 12 ACs + 11 Tests
- `prompts/p35_diversity_startup_fix_final_r1.md` — Final-R1 nach Code

## Push pending

v0.95.16 → v0.96.10 → v0.97.0 → v0.97.1 alle lokal. Push nach Mike's
Field-Test-OK.

## Stand 2026-05-11 nachmittags: P34.DIVERSITY-DYNAMIC v0.97.0 Code fertig

**Code:** v0.97.0 lokal — neuer Live-Modus für Antennen-Verhältnis.
**Tests:** **1111 grün** (1070 → 1111, +41).
**Push:** pending bis Mike Field-Test 12-Punkte (V3 §5) bestätigt.

## Was P34 ist

Antennen-Verhältnis (50:50 / 70:30 / 30:70) kann jetzt **im laufenden
Betrieb live** angepasst werden statt nur 1× pro Stunde mit 90-Sek-
UI-Sperre.

**Architektur ENTWEDER-ODER** (kein Parallel-Betrieb):
- Toggle AUS in Settings → Statik wie heute (100% unangetastet)
- Toggle AN → Dynamic übernimmt, Statik 1h-Frist unterdrückt

**Wo der Toggle steht:** Einstellungen → „FT8 & Diversity" → Checkbox
„Antennen-Verhältnis dynamisch anpassen (Testphase)". NICHT persistiert
— bei jedem App-Start auf AUS.

**Visuell:** Antennen-Panel Phase-Label wird **blau** („● DYNAMISCH (live)")
wenn aktiv, sonst Standard-Text „Diversity Neuberechnung in X Min."

## 9 atomare Commits — alle drin

| # | Inhalt | Datei |
|---|---|---|
| C1 | Modul-Helper + `_evaluate()` Refactor | `core/diversity.py` |
| C2 | DiversityController Hooks (`dynamic_active`, `_scoring_mode_listeners`, `should_remeasure` Check) | `core/diversity.py` |
| C3 | DynamicDiversityController NEU | `core/dynamic_diversity.py` |
| C4 | RAM-only Property `dynamic_diversity_enabled` | `config/settings.py` |
| C5 | UI-Hooks für Reset + Slot-Datenerfassung | `ui/mw_cycle.py`, `ui/mw_radio.py` |
| C6 | main_window Init + Slots + Toggle-Handler | `ui/main_window.py` |
| C7 | control_panel `is_dynamic` Param + Blau-Färbung | `ui/control_panel.py` |
| C8 | settings_dialog Toggle + Tooltip | `ui/settings_dialog.py` |
| C9 | APP_VERSION + Doku | `main.py`, HISTORY/HANDOFF/CLAUDE |

## Test-Bilanz

- `tests/test_diversity_helpers.py` NEU — 14 Tests für Modul-Funktionen
- `tests/test_diversity_dynamic.py` NEU — 15 Unit-Tests für Controller
- `tests/test_diversity_dynamic_integration.py` NEU — 12 Integration-Tests
- Statische Tests bleiben grün (AK1 erfüllt: Pipeline unangetastet)

**Total: 1070 → 1111 grün** (+41, V3-Prognose war ~1095-1100).

## Plan-Files (Compact-fest)

- `prompts/p34_diversity_dynamic_v1.md` (ENTWEDER-ODER-Spec)
- `prompts/p34_diversity_dynamic_v2.md` (Self-Review)
- `prompts/p34_diversity_dynamic_r1.md` (DeepSeek-R1, neue Architektur)
- `prompts/p34_diversity_dynamic_v3.md` (FINAL, 16 ACs, Field-Test-Checkliste)
- `prompts/p34_diversity_dynamic_*_OLD_parallel.md` (verworfene Vorgänger)

## Field-Test-Checkliste F1-F12 (Mike)

V3 §5 — Auszüge:
- F1: Toggle AUS → 100% wie heute
- F2: Toggle AN → Antennen-Panel wird blau, Ratio passt sich live an
- F3: Toggle AN während Statik-Mess → Mess bricht ab, sofort 50:50
- F4: Bandwechsel mit Toggle AN → **keine 90-Sek-Sperre mehr**
- F7: 1h ohne QSO mit Dynamic AN → keine 90-Sek-Statik-Re-Mess
- F8: Toggle AN→AUS → **keine sofortige Statik-Mess** (Mike B-Option)

**Bestanden wenn F1-F8 sauber.**

## Weiter offen (nach P34)

- ⛔ **P30 MEMORY-LEAK 124 GB nach Tagen** — eigener Workflow nötig.
  Live-Check bestätigt: RAM nicht Disk. Verdächtige Pfade in TODO P30.
- 📋 P12 sauberer Async-Refresh (Partial-Fix ist drin)
- 📋 P27 Mess-Guard (aus P26-Spec)
- 📋 **Stufe 2 P34** — Statik komplett entfernen (eigener Workflow später
  wenn Mike sich mit Dynamic wohlfühlt)

## Push pending

v0.95.16 → v0.96.10 → v0.97.0 alle lokal gesammelt. Vor Push:
1. Mike Field-Test F1-F12 für P34
2. Entscheidung P30 (angehen oder als „acceptable" abhaken)

## App starten

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```

Single-Instance-Schutz aktiv (Window-Title-Check via osascript).

## Tests laufen lassen

```bash
QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q
```

→ **1111 grün** Stand v0.97.0.

## Nicht vergessen

- **Symlinks aktiv:** `FT8/CLAUDE.md` + `FT8/HANDOFF.md` sind Links auf
  `SimpleFT8/CLAUDE.md` + `SimpleFT8/HANDOFF.md`. KEIN Doppel-Edit.
- **Push pending** bis Mike Field-Test grün.
- **Toggle AN beim Test:** muss jedes Mal aktiv eingeschaltet werden
  (NICHT persistiert — Mike-Wunsch fürs Testen).
