# DeepSeek-R1 Review — Bundle G (Diversity Sub-Mode-Toggle)

## Kontext

SimpleFT8 (FT8-Funk-App, PySide6). Diversity-Modus hat 2 Sub-Modi
(scoring): „normal" (Standard) und „dx" (DX). Heute: User klickt DIVERSITY
während schon im Div-Modus = no-op (`if mode == self._current_rx_mode:
return` in `control_panel.py:1489`).

## Mike's Spec

Bandpilot=Aus:
- Klick DIVERSITY während Div Std → direkt → Div DX (kein Dialog)
- Klick DIVERSITY während Div DX → direkt → Div Std (kein Dialog)
- Klick DIVERSITY während Normal → bestehender Std/DX-Dialog
  (`mw_radio.py:608+`, unverändert)
- NORMAL-Klick: bisheriger Pfad

Bandpilot=Auto: alles unverändert (Bandpilot dominant).
Bandpilot=Manual: Toggle deaktivieren (User soll Manual-Dialog
nutzen).

## Architektur-Vorschlag (V2)

1. **`control_panel.py`** neues Signal `diversity_subtoggle_requested
   = Signal()`. In `_on_rx_mode_clicked`: bei `mode ==
   _current_rx_mode == "diversity"` → emit Signal statt no-op.
2. **`mw_radio.py`** neuer Slot mit 3-fach-Guard
   (bp_mode==off + nicht gain_locked + radio.ip). Toggle:
   `current = _diversity_ctrl.scoring_mode`; `new = "dx" if current ==
   "normal" else "normal"`; ruft `_activate_diversity_with_scoring(new)`
   (existiert).
3. **`main_window.py`** Signal-Connect.
4. **`tests/test_bundle_g.py` NEU** mit 7 Tests.

Aufwand: ~30 LOC + Tests.

## R1-Fragen

**R1-Q1 (OMNI/Auto-Hunt-Stop beim Sub-Mode-Toggle):**
`_on_rx_mode_changed` stoppt OMNI + Auto-Hunt nur bei `mode != old_mode`.
Bei Sub-Mode-Toggle bleibt mode=diversity → OMNI+Hunt laufen weiter.
V2-Position: pragma OK (Encoder/rx_panel sind scoring-unabhängig). Sehe
ich Risiken die ich übersehe?

**R1-Q2 (DXTuneDialog-Race bei Toggle mit fehlendem Gain):**
Toggle Std→DX mit leerem DX-Store löst DXTuneDialog (Phase 2 Gain-Mess).
Während Mess läuft OMNI's `on_cycle_start` weiter (Bundle F-Lesson:
Phase-Check raus). Encoder wird von DXTuneDialog ANT-Switches und
TX-Töne genutzt. **Encoder-Konflikt OMNI vs DXTuneDialog möglich?**

**R1-Q3 (Bandpilot=Manual während Toggle-Klick):**
Settings hat 3 Werte „off"/„auto"/„manual". V2 macht Toggle nur bei
„off". Bei „manual" wäre Toggle technisch möglich aber User-Verwirrung
(Manual-Dialog läuft separat). KISS: nur „off". Stimmst zu?

**R1-Q4 (Test-Mocking-Strategie):**
Memory-Lesson `feedback_test_critical_path_not_mock.md` Pflicht. Bundle G
testet Slot-Logik (state-Check). `_activate_diversity_with_scoring` ist
das Ziel, kein Test-Pfad → darf MagicMock werden? Oder soll 1 Test mit
echtem DiversityController + scoring_mode-Property-Check?

**R1-Q5 (Bandpilot-Pending bei Toggle):**
Bandpilot kann pending-Tupel haben das beim TX-Finish RX-Mode wechselt.
Bei Sub-Mode-Toggle ist Bandpilot=off (Voraussetzung) → kein Pending
möglich. V2 sieht das als OK. Übersehe ich was?

**R1-Q6 (Field-Test):**
F1-F7 (V2 Liste): Normal→Div→Dialog, Std→DX direkt, DX→Std direkt,
Bandpilot=auto kein Toggle, Gain-Lock kein Toggle, frischer
Std-Gain kein Dialog, leerer DX-Gain → Dialog. Reicht das?

**R1-Q7 (Sonst was?):**
Irgendwelche Edge-Cases die meine V1+V2 übersehen?

## Bitte Antwort-Format

- Score 1-10
- Findings KRITISCH/SOLLTE/KÖNNTE
- Push-Empfehlung
- Antworten auf Q1-Q7 kurz
