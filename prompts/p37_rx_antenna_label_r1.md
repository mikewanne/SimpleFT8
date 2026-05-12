# P37 — RX-Antennen-Anzeige im Dynamic-Label (DeepSeek-R1-Review)

## Auftrag

Du bekommst V2 fuer ein **sehr kleines UI-Feature** (~6 Zeilen Code in 2 Dateien) in
einem FT8-Funker-Tool (SimpleFT8, Hobby-Projekt).

**Kritisiere den Plan auf Bugs, Race-Conditions, Edge-Cases.**
KEIN Methodik-Streit — Feature ist Mike-bestaetigt.

Fokus:
1. Race / Threading — habe ich was uebersehen?
2. Edge-Cases — was passiert bei Phase-Wechsel mitten im Slot?
3. Backwards-Compat — bricht was?
4. Tests — was sollte zusaetzlich abgedeckt werden?
5. KISS — kann das noch einfacher?

Kurze Antwort. Max 1-2 KP-Findings wenn welche da sind, sonst „OK".

---

## Kontext (Hobby-Tool, ENTWEDER-ODER-Architektur)

- **Aktueller Stand (v0.97.2):** Adaptive Diversity laeuft live. Antennen-Panel zeigt
  „● DYNAMISCH (live)" wenn Adaptive aktiv. Slot-fuer-slot wird `_diversity_current_ant`
  (= "A1" oder "A2") gesetzt + Hardware-Antenne via `radio.set_rx_antenna()` umgeschaltet.
- **Was Mike will:** Im Label hinter „DYNAMISCH (live)" soll zusaetzlich stehen welche
  Antenne gerade aktiv ist: „● DYNAMISCH (live) — RX Ant1" bzw. „— RX Ant2".
- **Hardware:** TX immer ANT1 (Hardware-Pflicht, ANT2 = Regenrinne nicht TX-fest).
  Das hier ist RX-Seite, kein TX-Risiko.

## Code-Stellen (verifiziert via grep)

### Schreiber `_diversity_current_ant` (mw_cycle.py)
```python
# mw_cycle.py:680 oeffnet Lock
with self._diversity_lock:
    # ... Z.711-714: in_qso check
    # ... Z.715-728: pref_ant ODER _diversity_ctrl.choose() setzt
    self._diversity_current_ant = self._diversity_ctrl.choose()  # Z.726
    # ... Z.731-749: ant_cmd-Build + control_panel.update_diversity_ratio aufruf (NOCH INNERHALB des Lock)
    # ... Z.759-767: threading.Thread → radio.set_rx_antenna (asynchron OUT of Lock, gewollt)
```

### control_panel.py:1486-1553 (relevante Stellen)
```python
def update_diversity_ratio(self, ratio: str, phase: str,
                           measure_step: int = 0, measure_total: int = 8,
                           operate_seconds_remaining: int = 0,
                           scoring_mode: str = "normal",
                           operate_cycles: int = 0, operate_total: int = 0,
                           is_dynamic: bool = False):
    # ... phase=="remeasure" / "measure" / else (operate)
    # Z.1547-1567 operate-Pfad:
    if is_dynamic:
        self._phase_label.setText("● DYNAMISCH (live)")
        self._phase_label.setStyleSheet(
            f"color:#3399CC;font-size:9px;font-family:{_FONT};"
            "font-weight:bold;"
        )
    else:
        # Statik: „Diversity Neuberechnung in X Min."
        ...
```

## V2-Plan (~6 Zeilen Code in 2 Files)

### Change 1: control_panel.py
- Neuer optionaler Parameter `current_ant: str | None = None`
- Im `is_dynamic`-Zweig: Label-Text um „ — RX Ant1" / „ — RX Ant2" erweitern wenn
  `current_ant in ("A1","A2")`. Sonst Label „● DYNAMISCH (live)" wie heute.

### Change 2: mw_cycle.py:742
- `update_diversity_ratio(...)` Aufruf wird um `current_ant=self._diversity_current_ant` erweitert.

### Akzeptanzkriterien
1. Adaptive + Slot A1 → Label „● DYNAMISCH (live) — RX Ant1"
2. Adaptive + Slot A2 → Label „— RX Ant2"
3. Mess/Remess/Statik-Phase → kein RX-Anhang (Label wie heute)
4. `current_ant=None` (Default) → kein Anhang (Backwards-Compat erhalten)
5. 1131 Tests bleiben gruen
6. 1 neuer Test: Label enthaelt „RX Ant2" bei `is_dynamic=True, current_ant="A2"`

### V2-Self-Review (bereits geprueft)
- **Race**: Lock-Block in mw_cycle.py:680 umschliesst sowohl Schreiber als auch
  `update_diversity_ratio`-Aufruf. UI-Update wird unter Lock gerendert — kein Race.
- **Mapping**: "A1"/"A2" (Kurzform Code) → "Ant1"/"Ant2" (User-Label Mike-Wunsch).
- **Backwards-Compat**: neuer Parameter mit Default `None`. Andere Aufrufer
  (z.B. mess_status_dialog) bleiben unangetastet.
- **Performance**: 1× `setText` pro 15s-Slot = bereits Status quo.

---

## Bitte gib zurueck

1. **KP-Findings** (KRITISCH / SOLLTE-FIX / KOENNTE / OK)
2. **Spezifisch zu Threading**: Stimmt mein Race-Argument? Lock umschliesst sicher beide?
3. **Test-Coverage**: Reicht 1 neuer Test oder muessen mehr Edge-Cases abgedeckt werden?
4. **KISS-Check**: Kann das noch einfacher (z.B. ohne neuen Parameter, ueber andere Quelle)?

Antwort bitte kurz, max 200 Worte.
