# HANDOFF — SimpleFT8

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
