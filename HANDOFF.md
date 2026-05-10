# HANDOFF — SimpleFT8

## Stand 2026-05-10 ~XX:YY UTC: P5.OMNI-PATTERN-FIX-3 ERLEDIGT, Field-Test pending

**Code:** v0.96.2 lokal commited (C1-C5 + C5a Final-R1-Korrektur + C6 Doku).
6 atomare Commits seit v0.96.1.
**Tests:** **1034 grün** (1020 → 1034, +14 von V3 prognostiziert ~1029).
**Final-R1:** „Push freigegeben. Code ist merge-bereit." (0 KRITISCH +
1 SOLLTE-FIX gefixt + 1 KOENNTE akademisch).
**Field-Test:** 7-Punkte-Plan V3 §6 F1-F7 ausstehend, Mike startet App selbst.
**App:** gestoppt. **Push pending** bis Mike-Freigabe nach Field-Test —
v0.95.16-0.96.2 + P2-Tool zusammen.

## Was P5 gefixt hat

| # | Issue | Lösung | Files |
|---|---|---|---|
| **B (kritisch)** | Pos 1 (TX nach TX) IMMER encoder-busy → 5-Slot-Pattern halb tot. Wurzel: FT8 12.64s Audio + 1.3s FlexRadio-Buffer-Drain → Race-Window <1s. | **Variante A:** `core/encoder.py` Pending-TX-Queue + Verfall (`1.5 * cycle_duration`) + **F1-Abort-Schutz**. `transmit()` bei busy → queut Pending unter `_replace_lock`. `_tx_worker` Single-Pass + Pending-Loop mit `if _abort_event.is_set(): return` VOR Re-Trigger (sonst würde `_run_one_tx_pass` das Event clearen → abort verloren). | `core/encoder.py` (~110 Z. inkl. Helper) |
| **A (kosmetisch)** | Horche-Zeit zeigt Wall-Time (`04:26:44`) statt Slot-Boundary (`:45`). Nebeneffekt: Pos 4 RX-E + `:44 [O] Horche` wirken „verschoben"/„fehlend". | `(time.time() // self.timer.cycle_duration) * self.timer.cycle_duration`. Löst alle 3 Phänomene mit (R1's Display-Bug-Diagnose). | `ui/main_window.py:760` (~10 Z. inkl. Kommentar) |

## Atomare Commits

- C1 (`229e98c`): `core/encoder.py` Pending-Queue + Verfall + F1-Abort
- C2 (`96f5714`): `tests/test_encoder_pending.py` NEU (8 Tests T1, T9-T13)
- C3 (`333411a`): `ui/main_window.py:760` Slot-Boundary
- C4 (`955aeb0`): `tests/test_main_window_slot_boundary.py` NEU + T2N
- C5 (`31f2f41`): `main.py:16` APP_VERSION → 0.96.2
- C5a (`5408534`): Final-R1-Review + Test-Werte-Korrektur
- C6 (folgt): Doku (HISTORY + HANDOFF + CLAUDE-Header + TODO + Memory)

## Field-Test-Plan (V3 §6, 7 Punkte)

| F | Test | Erwartung |
|---|---|---|
| F1 | App starten, Diversity aktiv, OMNI toggeln. | OMNI-Start-Log + CQ-Audiofreq-Set. |
| F2 | 10-Slot-Loop beobachten (2 vollständige Blöcke). | qso_panel zeigt: Block 1 TX-E :30, TX-O :45, RX-E :60, RX-O :75, RX-E :90, dann Block 2 TX-O :105, TX-E :120, RX-O :135, RX-E :150, RX-O :165. **Alle 10 Einträge auf Slot-Boundaries.** |
| F3 | Log checken `~/.simpleft8/simpleft8.log`. | KEIN `encoder.transmit busy -> ...`-Log. KEIN `Pending TX verfallen`. |
| F4 | OMNI stoppen (manual_halt). | Stop-Log + Reset State. |
| F5 | OMNI nochmal starten, Bandwechsel mid-OMNI auf 20m FT8. | OMNI stoppt automatisch (band_change). Erneut starten → läuft sauber. |
| F6 | OMNI starten, Modus auf FT4 wechseln. | OMNI stoppt (mode_change wenn auf Normal-Modus). Bei Diversity FT4: OMNI sollte sauber mit FT4-Pattern (7.5s Slots). |
| F7 | OMNI starten, eingehende Antwort auf CQ. | OMNI pausiert. QSO läuft via qso_state. Nach QSO: OMNI resumed mit Block-Wahl. |

**Bestanden wenn:** F1+F2+F3 sauber laufen ohne busy-Logs.
F4-F7 sind Regressionstests für bestehende OMNI-Mechanik.

## Plan-Files (alle vorhanden in `SimpleFT8/prompts/`)

- ✅ `p5_omni_pattern_fix3_diagnose.md` (Snapshot)
- ✅ `p5_omni_pattern_fix3_v1.md` (Snapshot)
- ✅ `p5_omni_pattern_fix3_v2.md` (Snapshot)
- ✅ `p5_omni_pattern_fix3_r1_prompt.md` (Snapshot)
- ✅ `p5_omni_pattern_fix3_r1.md` (Snapshot, in=70920 out=6985 Tokens)
- ✅ `p5_omni_pattern_fix3_v3.md` (EINZIGE WAHRHEIT für Code, Compact-fest)
- ✅ `p5_omni_pattern_fix3_final_r1_prompt.md` (Final-R1-Brief)
- ✅ `p5_omni_pattern_fix3_final_r1.md` (Final-R1-Output, in=48019 out=4683 Tokens)

## Memory-Verweise (für nachfolgende Sessions)

- `project_p5_omni_pattern_fix3.md` — Status auf „Code fertig, Field-Test pending"
- `project_omni_cq_spec.md` — Mike-Spec (verbindlich, unverändert)
- `project_p4_omni_neubau.md` — Vorgänger v0.96.1
- `feedback_r1_encoder_busy_blindspot.md` — bewährt in P5 (R1 fand Race)
- `feedback_compact_save_cold_start_test.md` — bewährt in P5 (Cold-Start fand F1)
- `feedback_test_critical_path_not_mock.md` — KEIN Worker/Sleep/Boundary-Mock
- `feedback_workflow_no_exceptions.md` — Workflow eingehalten

## App-Start

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```

- `~/.simpleft8/simpleft8.lock` (fcntl) verhindert 2. Instanz.
- App killen: `pkill -f "SimpleFT8.*main\.py"` + Lock löschen wenn nötig.

## Tests

`QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
→ **1034 grün** Stand v0.96.2.

## Nicht-vergessen-Punkte

- **Symlinks aktiv:** `FT8/CLAUDE.md` + `FT8/HANDOFF.md` sind Links auf
  `SimpleFT8/CLAUDE.md` + `SimpleFT8/HANDOFF.md`. KEIN Doppel-Edit.
- **App ist gestoppt** (Mike startet sie für Field-Test selbst).
- **Push pending** bis P5 Field-Test grün.
- **OMNI in Live-Betrieb jetzt OK** wenn Field-Test grün ist.
