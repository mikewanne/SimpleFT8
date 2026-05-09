# HANDOFF — SimpleFT8

## Stand 2026-05-09 spät: P4.OMNI-NEUBAU code-fertig, Field-Test pending

**Aktueller Stand:** v0.96.0, **1026 Tests grün**. Alle 8 atomaren
Commits gepusht in den lokalen `main`-Branch. **Push (origin) noch
nicht** — Mike entscheidet nach Field-Test.

OMNI-CQ wurde nach 4 Fehlversuchen (v0.95.22-25) **als eigenständiges
Modul** `core/omni_cq.py` neu gebaut — eigener Worker-Thread mit
absolut-UTC-Slot-Boundaries, kein `qso_state.cq_mode`-Hack. Voller
Workflow V1 → V2 (20 Lessons) → R1 (DeepSeek-R1 in=57386/out=13346,
17/20 ✅ + 5 Findings R1-R5) → V3 (961 Z. Compact-fest) → Final-R1
(„V3 ist implementierungsreif, 0 KP, 4 nicht-blockierende Hinweise
F-1..F-4") → Cold-Start-Test fand 4 weitere ⛔-Bugs in V3 → V3 §0.5
NEU mit verifizierter Code-Pfad-Tabelle → Mike-Freigabe → Compact →
Code → 1026 Tests grün.

## Geänderte Files (15 Code/Test, +1311/-2045 Zeilen)

**NEU:**
- `core/omni_cq.py` (~340 Z.) — `OmniCQ(QObject)` mit Worker-Thread,
  5-Slot-Pattern, Sticky-Frequenz, Pause/Resume-Lifecycle.
- `tests/test_omni_cq_worker.py` (37 Tests) — Unit-Tests T1-T20 +
  Bonus-Tests.
- `tests/test_omni_cq_integration.py` (14 Tests) — I1-I14 mit
  `_FakeMW(QSOMixin, CycleMixin)`-Helper (umgeht volles MainWindow-Init).

**UMGEBAUT:**
- `core/encoder.py` — `transmit(message, *, tx_even=None,
  audio_freq_hz=None) -> bool` atomare API. `_pending_tx_message`-Queue
  + `_tx_worker` Outer-Loop raus (war P2-OMNI-Workaround). P1.9
  `request_replace` bleibt.
- `core/qso_state.py` — `_omni_skip_state_change` + `_was_pretriggered`
  Flags raus. `_send_cq` wieder linear: emit + `_set_state(CQ_CALLING)`.
- `ui/main_window.py` — OmniCQ-Init mit 4 Signal-Slots,
  `_on_btn_omni_cq_toggled` Rewrite (kein `qso_sm.start_cq()` mehr,
  AC12), `_on_omni_stopped` mit R1 R4 Reset, neue Slots
  `_on_omni_freq_changed` / `_on_omni_counter_changed` /
  `_on_omni_slot_action`, Easter-Egg + Auto-Hunt-Coupling + Totmann
  + Statusbar-Ω auf `_omni_cq` migriert. QTimer-Pretrigger raus.
- `ui/mw_qso.py` — `_pause_omni_if_active` + `_maybe_resume_omni` mit
  Caller-Queue-Pop (V2-L10), `_on_tx_finished` `_last_qso_tx_even`
  (V2-L3), `_on_send_message` OMNI-Bypass-Block KOMPLETT raus,
  `_on_cancel` HALT auf `_omni_cq.stop`.
- `ui/mw_cycle.py` — Pretrigger-Logik raus, `on_message_decoded`
  Listener-Pfad NEU (R1 R2!).
- `ui/mw_radio.py` — 3 Stop-Trigger (`_on_mode_changed` /
  `_on_band_changed` / `_on_rx_mode_changed`) auf `_omni_cq.stop`.

**GELÖSCHT:**
- `core/omni_tx.py` (~250 Z., obsolet)
- `tests/test_p1_omni_start.py`, `test_p2_omni_redesign.py`,
  `test_p2_omni_pattern_fix.py`, `test_p3_omni_pattern_fix2.py`,
  `test_omni_tx.py`, `test_encoder_queue.py` (~87 Tests).
- `test_modules.py` + `test_patterns.py`: 7 Direkt-OmniTX-Tests raus.

## 8 atomare Commits

| C# | Hash | Inhalt |
|---|---|---|
| C1 | `b813c53` | Migration alte OMNI-Tests RAUS (-87 Tests) |
| C2 | `678fc44` | NEU `core/omni_cq.py` + 37 Worker-Tests |
| C3 | `1d76457` | `encoder.transmit` atomare API + Queue raus |
| C4 | `037806c` | Rückbau `core/qso_state.py` |
| C5 | `b58c5df` | Rückbau `ui/mw_cycle.py` (Pretrigger raus) |
| C6 | `aa622b8` | Anschluss main_window + mw_qso + Listener + 14 Integration-Tests |
| C7 | `19cbada` | Stop-Trigger `mw_radio.py` |
| C8 | (dieser) | Löschen `core/omni_tx.py` + APP_VERSION 0.96.0 + Doku |

Test-Bilanz: **1069 → 1026 grün** (-43 netto). Alle Tests nach JEDEM
Commit grün.

## Field-Test-Pflicht (Mike, vor Push, V3 §6 17 Punkte)

**Vorbedingungen:**
- App auf Stand v0.96.0 (`./venv/bin/python3 main.py` — APP_VERSION
  zeigt 0.96.0).
- Diversity-Modus aktiv (Vorbedingung für btn_omni_cq Sichtbarkeit).
- ANT1 als TX-Antenne verifiziert (HW-Garantie zentral via
  `encoder.transmit`).
- 40m oder 20m FT8.

**Punkte F1-F17:**
1. F1: btn_omni_cq → Statusbar zeigt „Ω Even=0 Odd=0" + Label „OMNI CQ (aktiv)".
2. F2: 10-Slot-Loop, KEIN Pattern-Drift gegenüber v0.95.25 (4 TX, 6 RX).
3. F3: Block 1 EXAKT: TX [E], TX [O], RX [E], RX [O], RX [E].
4. F4: Block 2 EXAKT: TX [O], TX [E], RX [O], RX [E], RX [O].
5. F5: CQ-Antwort mid-OMNI: OMNI pausiert + QSO + RR73 mit korrekter Slot-Parität.
6. F6: QSO endet auf Even → Resume mit Block 2 (TX-O zuerst).
7. F7: QSO endet auf Odd → Resume mit Block 1 (TX-E zuerst).
8. F8: btn_omni_cq erneut → Stop, Ω verschwindet, reason `manual_halt` im Log.
9. F9: Bandwechsel mid-OMNI → Stop reason `band_change` (laufender TX läuft Slot zu Ende).
10. F10: Mode Diversity → Normal → Stop reason `rx_mode_change`.
11. F11: 15 min ohne Eingabe + ohne QSO → Stop reason `totmann_expired`.
12. F12: 4 Blöcke Wartezeit → Log-Eintrag „Sticky" oder „Switch" mit Hz-Werten.
13. F13: RX-Slots im QSO-Panel als „Horche..." sichtbar (Format `HH:MM:SS [E/O] ←  Horche  …`).
14. F14: btn_auto_hunt klicken während OMNI aktiv → OMNI stoppt mit `superseded`.
15. F15: btn_omni_cq klicken während Auto-Hunt aktiv → Auto-Hunt stoppt.
16. F16: 2 Antworten in 1 RX-Slot — erste startet QSO, zweite ignoriert.
17. F17: Caller-Queue: während QSO läuft 2. Anrufer kommt → nach QSO direkt 2. QSO, OMNI bleibt pausiert.

## Push-Status

**KEIN Push** seit v0.95.16. Lokal sind v0.95.16-0.96.0 + P2-Tool
(`tools/adif_archive.py`) gesammelt. Nach Field-Test entscheidet Mike
ob alle zusammen gepusht werden oder ob v0.95.22-25 (alle OMNI-Versuche)
via interactive rebase / squash aus der History geräumt werden.

## App-Start

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```

- `~/.simpleft8/simpleft8.lock` (fcntl) verhindert 2. Instanz.
- App killen: `pkill -f "SimpleFT8.*main\.py"` + Lock löschen.

## Tests

`QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
→ **1026 grün** Stand v0.96.0.

## Plan-Files (P4.OMNI-NEUBAU)

- `prompts/p4_omni_neubau_v1.md` — V1 (~350 Z.)
- `prompts/p4_omni_neubau_v2.md` — V2 mit 20 Lessons L1-L20
- `prompts/p4_omni_neubau_r1_prompt.md` + `_r1.md` — R1-Review
- `prompts/p4_omni_neubau_v3.md` — **Compact-fester Plan** (961 Z.,
  einzige Wahrheit für Code-Phase, jetzt umgesetzt)
- `prompts/p4_omni_neubau_final_r1_prompt.md` + `_final_r1.md` —
  Final-R1 („implementierungsreif, 0 KP")
- `prompts/p4_omni_neubau_code_excerpts.md` — Code-Excerpts für R1
  (~120 KB, gekürzte Vollfiles)

## Memory-Verweise

Bei nächster Session relevant:
- `project_p4_omni_neubau.md` (Status: ✅ Code fertig, Field-Test pending)
- `project_omni_cq_spec.md` (Mike-Spec, verbindlich)
- `feedback_omni_separate_architecture.md` (Architektur-Vision)
- `feedback_compact_save_cold_start_test.md` (Lesson aus diesem Refactor)
- `feedback_workflow_no_exceptions.md` (Workflow-Pflicht)
