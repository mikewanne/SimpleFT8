# P40 — P37-Komplettierung (DeepSeek-R1-Review)

## Auftrag

P37 (RX-Antennen-Anzeige im Dynamic-Label) war ein Partial-Fix — ich
habe nur 1 von 4 Aufrufer-Stellen angefasst. Mike's Field-Test 12.05.
abends zeigt Label „● DYNAMISCH (live)" ohne den erwarteten RX-Suffix.

Pruefe V2:
1. Sind die 3 zusaetzlichen Stellen tatsaechlich Aufrufer die das Label
   ueberschreiben?
2. Race / Threading: `_diversity_current_ant` Read im GUI-Thread sicher?
3. Edge-Cases (None, A1/A2-Wechsel waehrend Update)?
4. KISS-Check.

Kurze Antwort. KP-Findings KRITISCH/SOLLTE/KOENNTE/OK.

---

## Lesson aus eigenem Memory: feedback_partial_fix_check_other_paths.md

„Wenn ein Bug in Pfad A gefixt wird, IMMER grep nach gleicher Pattern-
Klasse in B+C+..." Bei P37 hatte ich nur `mw_cycle.py:742` angefasst.

## Live-verifizierter Bug

Mike Screenshot 12.05. (Adaptive aktiv, Ratio 50:50): Label-Text =
`● DYNAMISCH (live)` ohne `— RX Ant1` / `— RX Ant2` Suffix.

## 4 Aufrufer-Stellen von `update_diversity_ratio` mit `is_dynamic=True`:

| Datei | Zeile | Wann | current_ant in P37 gefixt? |
|---|---|---|---|
| mw_cycle.py | 742 | jeder Slot | ✅ ja |
| main_window.py | 1357 `_on_dynamic_ratio_changed` | bei jedem Ratio-Wechsel | ❌ nein |
| mw_radio.py | 990 (Adaptive-Aktivierung) | Toggle AN | ❌ nein |
| mw_cycle.py | 290 (`_handle_diversity_measure`) | Mess-Phase | ❌ nein |

`_on_dynamic_ratio_changed` ist der gefaehrlichste Pfad — Signal-Slot
laeuft via Qt.QueuedConnection im GUI-Thread, ueberschreibt das mw_cycle-
Update zwischen zwei Slots.

## V2-Fix

3 Stellen erweitern um `current_ant=self._diversity_current_ant`:

```python
# main_window.py:1357 _on_dynamic_ratio_changed:
self.control_panel.update_diversity_ratio(
    new_ratio, self._diversity_ctrl.phase,
    operate_seconds_remaining=self._diversity_ctrl.seconds_until_remeasure,
    scoring_mode=self._diversity_ctrl.scoring_mode,
    is_dynamic=True,
    current_ant=self._diversity_current_ant,  # NEU
)

# mw_radio.py:990 (Adaptive-Aktivierung):
self.control_panel.update_diversity_ratio(
    "50:50", "operate",
    operate_seconds_remaining=0,
    scoring_mode=scoring_mode,
    is_dynamic=True,
    current_ant=self._diversity_current_ant,  # NEU
)

# mw_cycle.py:290 (_handle_diversity_measure, defensive):
self.control_panel.update_diversity_ratio(
    self._diversity_ctrl.ratio, self._diversity_ctrl.phase,
    measure_step=self._diversity_ctrl.measure_step,
    measure_total=self._diversity_ctrl.MEASURE_CYCLES,
    operate_seconds_remaining=self._diversity_ctrl.seconds_until_remeasure,
    scoring_mode=self._diversity_ctrl.scoring_mode,
    is_dynamic=_is_dyn,
    current_ant=self._diversity_current_ant,  # NEU
)
```

## Akzeptanzkriterien

- AK1: Adaptive aktiv + Ratio-Wechsel → Label zeigt aktuelle RX-Antenne
- AK2: Adaptive-Toggle gerade angeschaltet → Label zeigt sofort RX-Antenne
- AK3: Mess-Phase (Statik-Mode) → Label unveraendert (Mess-Step-Text wie heute)
- AK4: 1136 bestehende Tests bleiben gruen
- AK5: P37-Tests (5 Cases) weiterhin gruen

## V2-Self-Review

1. **Thread-Safety**: `_diversity_current_ant` ist `str` ("A1"/"A2") →
   atomic read/write in CPython (GIL). `_on_dynamic_ratio_changed` laeuft
   im GUI-Thread, `_diversity_current_ant` wird im Decoder-Thread
   (mw_cycle.py:720, 726) unter `with self._diversity_lock:` gesetzt.
   Read im GUI-Thread liefert konsistenten Wert.
2. **None-Schutz**: `_diversity_current_ant` koennte initial `None`
   sein (vor erstem Slot). Bereits durch `current_ant=None` Default
   in `update_diversity_ratio` abgedeckt → kein Suffix, kein Crash.
3. **`mw_radio.py:990`**: `_diversity_current_ant` wird ggf. erst
   spaeter gesetzt. Initialwert ist "A1" (mw_radio.py:249, 925). OK.
4. **`mw_cycle.py:290`** liegt im Statik-Pfad — bei Adaptive eh inaktiv.
   Aber konsistent halten falls Statik + Adaptive in Zukunft anders interagiert.

## Frage an R1

1. Race-Argument korrekt (GIL-atomic, Decoder-Lock unter Decoder-Thread,
   GUI-Thread-Read OK)?
2. Sollte zusaetzlich Test fuer den `_on_dynamic_ratio_changed`-Slot
   geschrieben werden (Integration-Test)?
3. Stelle ich noch eine vierte Aufrufer-Stelle?
4. KISS: alternativ koennte `update_diversity_ratio` `current_ant`
   als Klassen-Attribut lesen statt als Parameter — overkill?
