# HANDOFF — SimpleFT8

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
