# Kalibrierungs-Pipeline Optimierung — Plan v1 (Stand 2026-05-04)

## Ziel

Pipeline beim Diversity-Setup von **6:50 Min** auf **typisch ~3:20 Min**
verkürzen, ohne die Mess-Genauigkeit substantiell zu verlieren.

## Sicherungspunkt VOR Optimierung

- **GitHub Release:** [v0.88.1](https://github.com/mikewanne/SimpleFT8/releases/tag/v0.88.1)
- **Git Tag:** `v0.88.1` (push'd 2026-05-04)
- **Lokale Sicherung:** `Appsicherungen/2026-05-04_v0.88.1_vor_kalibrier_optimierung/`
- **Tests-Stand:** 659 grün
- **Rollback:** `git checkout v0.88.1`

## Aktuelle Pipeline (was getriggert wird beim Klick auf Diversity Standard/DX)

1. **Phase 1 — TUNE** (5 s): `radio.tune_on()` mit `tune_power` (default 10 W)
   auf ANT1, dann `tune_off()` + Power zurueck
2. **Skip-First-Cycle** (15 s): `_skip_first = True` ignoriert ersten
   Teil-Zyklus
3. **Phase 2 — DX-Tune-Dialog** (270 s = 18 Zyklen × 15 s):
   - `_build_interleaved_schedule()` baut 6 Kombis × 3 Runden = 18 Eintraege
   - Pro Zyklus: `messages[].snr` sammeln, Top-5-Schnitt
   - Overload-Check (>+20 dB ODER Varianz <1.5)
   - DX-Modus: bestes Top-5-SNR pro Antenne
   - Standard-Modus: meiste Stationen pro Antenne
4. **Phase 3 — Diversity-Einmessen** (120 s = 8 Zyklen):
   - `DiversityController.MEASURE_CYCLES = 8`
   - 4×A1 + 4×A2 → Median, Schwelle 8 % → 70:30 oder 50:50

**Total:** 5 + 15 + 270 + 120 = **410 s = 6:50 Min**

## DeepSeek-R1-Diskussion (2026-05-04)

R1 hat 8 Optimierungs-Vorschlaege gemacht. Mike's Boss-Entscheidung:
- ❌ Phase-2-Daten fuer Phase-3-Ratio wiederverwenden — RAUS (zu hohes
  Mess-Bias-Risiko, ohne Feld-Validation nicht entscheidbar)
- ✅ Alle 8 anderen Vorschlaege drin

Volle R1-Antwort: `/tmp/calibration_r1_response.md` (ggf. neu querien
nach Compact: `cat /tmp/calibration_optimize_briefing.md | tools/deepseek_review.py
ui/dx_tune_dialog.py core/diversity.py`)

## Optimierungen — Block 1 (sicher, ~30 min Code)

| # | Was | Wo | Aktuell | Neu | Ersparnis | Risiko |
|---|---|---|---|---|---|---|
| 1 | Skip-First-Cycle entfernen | `ui/dx_tune_dialog.py:60` `_skip_first = True` | wird ignoriert | direkt messen | -15 s | minimal |
| 2 | TUNE 5 s → 3 s | `ui/mw_radio.py:1002` + `ui/mw_radio.py:1053` `QTimer.singleShot(5000, ...)` | 5 s | 3 s | -2 s | gering (FlexRadio internal Tuner schafft <1 s) |
| 3 | Gain-Stufen 3 → 2 (10/20 dB) | `ui/dx_tune_dialog.py:22` `GAIN_VALUES = [0, 10, 20]` | 3 Werte | `[10, 20]` als Default, 0 nur bei Overload | -90 s | gering (Overload-Check fängt es) |
| 4 | Phase 3: 8 → 6 Zyklen | `core/diversity.py:26` `MEASURE_CYCLES = 8` | 8 (4 pro Antenne) | 6 (3 pro Antenne) | -30 s | gering |
| 5 | Cache 2 h → 6 h | `core/preset_store.py` (PresetStore.is_valid) | 2 h | 6 h (TTL hochsetzen) | weniger Pipeline-Laeufe pro Tag | niedrig |

**Block 1 Ersparnis: ~2:15 Min sicher.**

## Optimierungen — Block 2 (mittel, ~1 h Code + Test)

| # | Was | Wo | Aktuell | Neu | Ersparnis | Risiko |
|---|---|---|---|---|---|---|
| 6 | N=3 → N=2 pro Kombi | `ui/dx_tune_dialog.py:23` `ROUNDS = 3` | 3 Runden | 2 Runden | -60 s (in Kombi mit #3: -150 s) | mittel (σ/√N — N=2 reicht für 10-dB-Schritte) |
| 7 | Adaptiv-Stop Phase 2 | `ui/dx_tune_dialog.py:_finish + zwischendrin` | immer 3 Runden | nach Runde 1 abbrechen wenn Δ > 4 dB SNR oder > 50 % Stationen pro Antenne | -30 bis -120 s | mittel (Schwellen evt. Feldjustage) |
| 8 | Adaptiv-Stop Phase 3 | `core/diversity.py:choose / _finalize` | immer 8/6 Zyklen | nach 4 Zyklen abbrechen wenn Δ > 15-20 % | -30 s | mittel |

**Block 2 Ersparnis: ~1:00 bis 2:00 Min zusätzlich.**

## Erwartete Pipeline-Dauer nach Block 1+2

- **Best-Case** (alles greift, Adaptiv-Stop früh): **~2:30 Min** (-63 %)
- **Typisch** (Adaptiv-Stop nach 2/3 der Runden): **~3:20 Min** (-52 %)
- **Worst-Case** (kein Adaptiv-Stop, alles voll messen): **~4:35 Min** (-33 %)

## Workflow-Anweisung

Pro Block: V1 → V2 (Self-Review) → R1-Review → V3 → Plan → atomare Commits → Tests grün → Final-R1 → Push.

**Block 1 zuerst** (sicher, klare Wins). Tests müssen weiter 659+ grün sein.
**Block 2** danach mit eigenem V1→V3-Zyklus weil mittel-Risk.

## Code-Stellen die angepasst werden (Quick-Reference)

```
ui/dx_tune_dialog.py:
  - Zeile 22: GAIN_VALUES = [0, 10, 20]            → [10, 20] (#3)
  - Zeile 23: ROUNDS = 3                           → 2 (#6)
  - Zeile 60: self._skip_first = True              → entfernen (#1)
  - _finish(): adaptiv-Stop-Logik (#7)

core/diversity.py:
  - Zeile 26: MEASURE_CYCLES = 8                   → 6 (#4)
  - choose() / Finalize-Logik: adaptiv-Stop (#8)

ui/mw_radio.py:
  - Zeile 1002: QTimer.singleShot(5000, _after_tune) → 3000 (#2)
  - Zeile 1053: QTimer.singleShot(5000, _after_tune) → 3000 (#2)

core/preset_store.py:
  - is_valid()-TTL: 2*3600 → 6*3600 (#5)
```

## Testabdeckung-Lücken (vor Optimierung)

- `dx_tune_dialog._build_interleaved_schedule()` hat keinen Test
  → Mit dem Refactor wäre ein Test sinnvoll (Schedule-Länge bei
  verschiedenen `GAIN_VALUES`/`ROUNDS`)
- `DiversityController.MEASURE_CYCLES` als Konstante getestet?
  → Falls nicht: Test ergänzen mit Schwellenwert
- Adaptiv-Stop braucht eigene Tests pro Block

## Aktuelles Setup (Mike-spezifisch)

- ANT1 = Kelemen DP-201510 (Trap-Dipol, resonant 20m, off-band 40m)
- ANT2 = Regenrinne ~15m L-Form (NUR RX!)
- FlexRadio FLEX-8400M mit SmartSDR-internem Tuner
- Hobby-Funker, kein Contest

## Nach Compact: hier weitermachen

Der nächste Anlauf nach Compact: `Block 1 starten — V1 für Optimierungen #1, #2, #3, #4, #5`. Daten-Ersparnis-Tabelle und Code-Stellen oben sind die Quelle.

## Verwandte Memory-Einträge

- `project_kalibrier_optimierung.md` (wird beim nächsten Step erstellt)
- `feedback_workflow_no_exceptions.md` (Workflow-Pflicht)
