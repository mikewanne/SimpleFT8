# HANDOFF — SimpleFT8

## Stand 2026-05-10: v0.96.1 P4.OMNI-NEUBAU V5 Signal-Refactor — Code fertig, Field-Test pending

**Trigger nach Compact:** **„omni v5 field-test"** — KI lädt
`memory/project_p4_omni_neubau.md` (jetzt ✅) und führt Mike durch das
17-Punkte-Field-Test-Plan V3 §6.

## Was passiert ist (10.05.2026)

1. **C9 Code-Phase:** `core/omni_cq.py` von 337 Z. Worker-Thread auf
   ~250 Z. signal-getriggert refactored. Worker-Bug aus v0.96.0
   (Pos 2/3/4 in einem Slot) durch Architektur-Wechsel komplett
   eliminiert.
2. **Tests:** `test_omni_cq_worker.py` gelöscht (37 obsolet),
   `test_omni_cq_signal.py` NEU mit 22 Test-Funktionen → 31 effektive
   Tests durch parametrize. `test_omni_cq_integration.py` migriert.
3. **Test-Bilanz:** 1026 → **1020 grün** (V3 erwartete ~1010,
   parametrize +9).
4. **APP_VERSION-Bump:** 0.96.0 → 0.96.1.
5. **2 atomare Commits:**
   - C9 (`0368427`): Code + Tests + 1-Zeile-Connect mw_cycle + Plan-Files.
   - C10: Doku (HISTORY+HANDOFF+CLAUDE+Memory) + main.py.

## Architektur-Eckdaten V5

```
FT8Timer.cycle_start (Signal int, bool, 1× pro 15 s)
        ↓ Qt.QueuedConnection
mw_cycle._on_cycle_start(cycle_num, is_even)
        ↓ NACH qso_sm.on_cycle_end():
self._omni_cq.on_cycle_start(cycle_num, is_even)
        ↓ Defense-Guard `if not _active or _paused: return`
        ├── Pos 0/1 (TX) → encoder.transmit(msg, tx_even=..., audio_freq_hz=...)
        │                  ↓ Encoder-Thread schedulet UTC-Slot selbst
        │                  → counter_changed.emit + slot_action.emit (TX)
        └── Pos 2/3/4 (RX) → slot_action.emit (RX, is_tx=False, is_even-Signal)
        ↓ _slot_index = (slot_index + 1) % 5; bei 0 → Block wechseln
```

**Pattern verbindlich:**
- Block 1 Even-First: TX-E, TX-O, RX-E, RX-O, RX-E
- Block 2 Odd-First:  TX-O, TX-E, RX-O, RX-E, RX-O
- Toggle-Start IMMER Block 1 (KISS, R1-bestätigt)
- QSO-Resume: endet Even → Block 2, endet Odd → Block 1
- Frequenz 1× am ersten TX setzen, fest bis stop()

## Field-Test V3 §6 (Mike, Push-Voraussetzung) — 17 Punkte F1-F17

**Was zu beweisen ist:**
- 10-Slot-Loop ohne Drift, sichtbar in qso_panel
- Block 1 EXAKT TX-E, TX-O, RX-E, RX-O, RX-E (5 Slots)
- Block 2 EXAKT TX-O, TX-E, RX-O, RX-E, RX-O (5 Slots, Auto-Rollover)
- CQ-Antwort mid-OMNI: pause + QSO + RR73 + Resume mit Block-Wahl
  (Even → Block 2, Odd → Block 1)
- Caller-Queue mit OMNI-pausiert (next QSO direkt, OMNI bleibt paused
  bis Queue leer)
- Alle 7 Stop-Reasons sauber: `manual_halt`, `band_change`,
  `mode_change`, `rx_mode_change`, `totmann_expired`, `superseded`
  (Auto-Hunt-Toggle), `easter_egg_off`
- Auto-Hunt-Coupling in beide Richtungen
- RX-Slot „Horche..." sichtbar im qso_panel mit echter UTC-Slot-Parität
- Nur 1× pro Run `cq_freq_changed`-Signal (Sticky)

**Hardware-Garantie ANT1:** OMNI emittet kein TX direkt —
`encoder.transmit()` setzt zentral `radio.set_tx_antenna("ANT1")`
(`core/encoder.py:363`). Kein Extra-Check nötig.

## Memory-Verweise

- `project_p4_omni_neubau.md` — V5 ✅ Code fertig, Field-Test pending
- `project_omni_cq_spec.md` — Mike-Spec (verbindlich)
- `feedback_omni_separate_architecture.md` — 3-Schichten-Architektur
- `feedback_test_critical_path_not_mock.md` — Lesson aus v0.96.0-Bug
- `feedback_compact_save_cold_start_test.md` — Cold-Start-Test-Pflicht
- `feedback_workflow_no_exceptions.md` — Workflow-Pflicht

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

## Push-Status

KEIN Push (origin) seit v0.95.16. Lokal sind v0.95.16-0.96.1 + P2-Tool
gesammelt. Push erst nach Field-Test V5 positiv.
