# HANDOFF — SimpleFT8

## Stand 2026-05-10 ~07:00 UTC: P5.OMNI-PATTERN-FIX-3 vorbereitet, fresh-Instanz übernimmt

**Trigger für die fresh-Instanz:** **„omni pattern fix3 starten"**
oder **„p5 starten"**

Sie liest dann:
1. `memory/project_p5_omni_pattern_fix3.md` (Trigger-File mit 16-Punkt-Anleitung)
2. `prompts/p5_omni_pattern_fix3_diagnose.md` (Compact-feste Diagnose)
3. `memory/feedback_r1_encoder_busy_blindspot.md` (NEUE Lesson)

…und beginnt mit Schritt 0 (Code-Verifikation) → V1 → V2 → R1 → V3.

## Was heute (10.05.2026) passiert ist

### Vormittag — P4.OMNI-NEUBAU V5 (v0.96.0 → v0.96.1)

- C9 (`0368427`): `core/omni_cq.py` Worker → Signal-Refactor (337 → 250 Z.).
  `test_omni_cq_worker.py` gelöscht (37 obsolet, Mock versteckte
  kritischen Pfad — Lesson `feedback_test_critical_path_not_mock.md`).
  `test_omni_cq_signal.py` NEU mit 22 Test-Funktionen (31 effektive
  Tests, KEIN Worker/Sleep/Boundary-Mock).
  `test_omni_cq_integration.py` migriert.
  `mw_cycle._on_cycle_start` 1-Zeile-Connect.
- C10 (`8244e37`): APP_VERSION 0.96.0 → 0.96.1 + Doku.
- **Tests:** 1026 → **1020 grün**.

### Mittag — Symlinks für CLAUDE.md + HANDOFF.md

Mike hat `FT8/CLAUDE.md` und `FT8/HANDOFF.md` als Symlinks auf die
echten Dateien in `SimpleFT8/` gesetzt → kein „BEIDEN Verzeichnissen
identisch updaten" mehr nötig. Regel überall (CLAUDE.md, MEMORY.md,
2 Memory-Files, SESSION_WORKFLOW.md, feierabend.md) entfernt.

### Statistik-Outputs aktualisiert

`scripts/generate_plots.py` durchgelaufen — DE+EN PDFs (40m+20m FT8),
Bandpilot-Empfehlungen, Plots 10/15/20/30/40m. Slot-Lückenliste:
`tools/slot_lueckenliste.py` → 216 Slots, 31 Ziel-erreicht.

### Field-Test v0.96.1 — Pattern-Bug gefunden

Mike hat OMNI getoggelt, qso_panel zeigte:

```
04:26:30 [E] → Sende    CQ DA1MHH JO31    ← Pos 0 ✓
04:26:44 [O] ← Horche                       ← Pos 1 SOLLTE TX-O sein!
04:26:59 [E] ← Horche                       ← Pos 2 ✓
04:27:14 [O] ← Horche                       ← Pos 3 ✓
                                            ← Pos 4 RX-E FEHLT
04:27:45 [O] → Sende    CQ DA1MHH JO31    ← Block 2 Pos 0 ✓
04:27:59 [E] ← Horche                       ← Block 2 Pos 1 SOLLTE TX-E sein!
```

Log-Beweis (`~/.simpleft8/simpleft8.log`):
```
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B2 [1/4] TX-E uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
```

**Wurzel:** Pos 1 cycle_start :45 trifft Encoder bevor `_tx_worker.finally`
`_is_transmitting=False` gesetzt hat. V3 §8 (Out-of-Scope: Encoder-Queue ❌
+ Pretrigger ❌) hat den Race architektonisch eingebaut.

**R1-Blindspot:** R1 hat in V3-Klärungsfrage 3 (Decoder-Blockade) den
Encoder-Throughput-Race nicht erkannt. Neue Pflicht-Lesson
`feedback_r1_encoder_busy_blindspot.md`.

### P5-Vorbereitung (jetzt)

- `prompts/p5_omni_pattern_fix3_diagnose.md` — Compact-feste Diagnose
  mit 4 Lösungsoptionen A-D + AC-Vorschlag + R1-Fragen.
- `memory/project_p5_omni_pattern_fix3.md` — Trigger + 16-Punkt-Anleitung.
- `memory/feedback_r1_encoder_busy_blindspot.md` — neue Pflicht-Lesson.
- MEMORY.md Index ergänzt.
- Diese HANDOFF.md.
- TODO.md (P5 als TOP-Item).
- HISTORY.md ergänzt mit Field-Test-Entdeckung.

## Aktueller Code-Stand

- v0.96.1 lokal commited (`8244e37`), KEIN Push (origin) seit v0.95.16.
  Lokal sind v0.95.16-0.96.1 + P2-Tool gesammelt. Push wartet bis P5
  Field-Test grün.
- **OMNI in Live-Betrieb NICHT nutzen** bis P5 fertig (Pattern halb
  tot wegen Pos-1-Race).
- Tests: **1020 grün**.

## P5 — 2 Issues (im selben Workflow)

| # | Issue | Lösung | Skala |
|---|---|---|---|
| **B** | Pos 1 (TX nach TX) immer encoder-busy + Pos 4 RX-E fehlt | Architektur-Fix (4 Optionen A-D) | nicht-trivial — voller Workflow |
| **A** | Horche-Zeit zeigt Wall-Time, soll Slot-Boundary `:00`/`:15`/`:30`/`:45` | `floor(time.time()/cycle_duration)*cycle_duration` (1 Zeile in `main_window.py:760`) | trivial, geht in P5 als AC mit |

**Mike-Empfehlung wahrscheinlich Variante A (Encoder-Queue zurück) —
KISS-konform, einziger Verstoß: V3-§8-Verbot kippen (gerechtfertigt
durch Field-Test-Evidence).**

**APP_VERSION-Plan:** v0.96.1 → v0.96.2.

## App-Start

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```

- `~/.simpleft8/simpleft8.lock` (fcntl) verhindert 2. Instanz.
- App killen: `pkill -f "SimpleFT8.*main\.py"` + Lock löschen.

## Tests

`QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
→ **1020 grün** Stand v0.96.1.

## Memory-Verweise (Pflicht für fresh-Instanz)

- `project_p5_omni_pattern_fix3.md` — **TRIGGER-FILE, zuerst lesen**
- `project_omni_cq_spec.md` — Mike-Spec (verbindlich)
- `project_p4_omni_neubau.md` — V5-Stand (Vorgänger)
- `feedback_r1_encoder_busy_blindspot.md` — NEUE Lesson aus heute
- `feedback_omni_separate_architecture.md` — 3-Schichten-Architektur
- `feedback_test_critical_path_not_mock.md` — Lesson aus v0.96.0-Bug
- `feedback_compact_save_cold_start_test.md` — Cold-Start-Test-Pflicht
- `feedback_workflow_no_exceptions.md` — Workflow-Pflicht
- `feedback_workflow_after_failed_fix.md` — wenn Field-Test scheitert

## Nicht-vergessen-Punkte für die fresh-Instanz

- **Symlinks aktiv:** `FT8/CLAUDE.md` + `FT8/HANDOFF.md` sind Links auf
  `SimpleFT8/CLAUDE.md` + `SimpleFT8/HANDOFF.md`. KEIN Doppel-Edit.
- **App ist gestoppt** (Mike startet sie für Field-Test selbst).
- **Push pending** bis P5 grün — v0.95.16-0.96.2 zusammen.
