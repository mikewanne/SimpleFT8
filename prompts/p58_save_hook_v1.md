# P58 — V1: SWR-Limit Save-Hook propagiert nicht zur laufenden App

## 1. Trigger

Mike-Field-Test 15.05.2026 morgens: SWR-Limit in Settings auf 1.5
geändert + gespeichert während App lief → Watchdog hat NICHT
gegriffen bei realem SWR 1.9. Terminal-Output zeigte **keine**
`[FlexRadio] SWR-Limit auf 1.5 gesetzt`-Zeile nach dem Save.

Nach App-Neustart (Settings-Datei hatte 1.5 persistiert) wurde der
Connect-Hook ausgeführt und der Print war da. Watchdog funktioniert
seitdem zuverlässig.

→ **Settings-Persistenz funktioniert. Live-Propagation an Radio
fehlt im Save-Hook.**

## 2. Wurzel-Analyse

`ui/settings_dialog.py:680-683` (Stand v0.97.30):

```python
self.settings.set("swr_limit", self.swr_limit.value())
# P53: Live an Radio propagieren wenn verbunden
parent = self.parent()
if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
    parent.radio.set_swr_limit(self.swr_limit.value())
```

`ui/main_window.py:1058`: `dialog = SettingsDialog(self.settings, self)`
→ Parent IST MainWindow. `super().__init__(parent)` in
`settings_dialog.py:89` setzt Parent korrekt.

`ui/main_window.py:245`: `self.radio = create_radio(self.settings)`
→ direktes Attribut, kein Property.

**Möglichkeiten warum Bedingung falsy ist:**

A) `self.parent()` returnt nicht MainWindow (Qt-internes Verhalten,
   Lifecycle, Race)
B) `parent.radio.ip` ist `None` obwohl Radio verbunden — der FlexRadio
   setzt evtl `ip` erst nach Vollconnect, oder es gibt Edge-Cases wo
   `ip` während kurzer Reconnect-Phasen None ist
C) Diagnose nötig — aktuell rein Hypothese

**Was wir aus Test wissen:**
- Settings.set() funktioniert (1.5 ist in JSON)
- Connect-Hook funktioniert (Print bei Restart)
- Save-Hook scheitert silent (kein Print, kein Setter-Aufruf)

## 3. Lösungs-Optionen

### Option A — Diagnose-First, dann Minimal-Fix (KISS)

1. Diagnose-Print direkt vor Bedingung:
   ```python
   parent = self.parent()
   print(f"[P58-DBG] parent={type(parent).__name__ if parent else 'None'} "
         f"radio_attr={hasattr(parent, 'radio') if parent else 'N/A'} "
         f"radio_ip={getattr(getattr(parent, 'radio', None), 'ip', 'no-radio')}")
   ```
2. Mike löst Save-Vorgang aus → Terminal verrät welche Bedingung falsy ist
3. Gezielt fixen — vermutlich 1-2 Zeilen

**Vorteil:** Wir wissen die Wurzel bevor wir umbauen.
**Nachteil:** Iteration über Mike (er muss testen).

### Option B — Signal/Slot-Pattern (sauber, zukunftssicher)

SettingsDialog emittet `live_settings_changed` Signal beim Save.
MainWindow connectet und ruft alle relevanten Live-Setter:

```python
# settings_dialog.py
live_settings_changed = Signal()

def _save_and_close(self):
    ...alle settings.set...
    self.live_settings_changed.emit()
    self.accept()
```

```python
# main_window.py:_on_settings_clicked
dialog = SettingsDialog(self.settings, self)
dialog.live_settings_changed.connect(self._apply_live_settings)
dialog.exec()

def _apply_live_settings(self):
    if self.radio.ip:
        self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))
    # Erweiterbar für zukünftige Live-Settings
```

**Vorteil:** Single source of truth, kein parent()-Lookup, zentral
für alle zukünftigen Live-Settings (P56 Gain pro Band z.B. kann
hier auch ansetzen).
**Nachteil:** mehr Code, 2 Files-Eingriff.

### Option C — Radio-Referenz im SettingsDialog-Konstruktor

```python
dialog = SettingsDialog(self.settings, radio=self.radio, parent=self)
```

Save-Hook nutzt `self.radio.set_swr_limit()` direkt.

**Vorteil:** Trivial.
**Nachteil:** SettingsDialog kennt Radio direkt — Coupling. Wenn
mehr Live-Settings kommen, wird's bald wieder hässlich.

## 4. Empfehlung

**Option B (Signal/Slot)** — sauberer Pattern, KISS-konform für
ZUKÜNFTIGE Erweiterungen. P56 (Gain pro Band) wird vermutlich auch
Live-Propagation brauchen → einmal sauber bauen, dann profitiert
P56 davon.

Option A als **Diagnose-Schritt VOR der Umsetzung** — wir wissen
warum's heute brach, das geht in die V3-Doku.

## 5. Acceptance Criteria

- **AC1:** Settings öffnen, swr_limit ändern, speichern → Terminal
  zeigt sofort `[FlexRadio] SWR-Limit auf X.X gesetzt`
- **AC2:** Beim nächsten TX greift der neue Limit-Wert (Watchdog
  triggert bei swr >= neuer_limit)
- **AC3:** Wenn Radio nicht verbunden (`radio.ip is None`) →
  Signal feuert trotzdem, Setter wird übersprungen, kein Crash
- **AC4:** Bestehender Connect-Hook in `mw_radio.py:179` bleibt
  unverändert (Setter beim App-Start mit persistiertem Wert)
- **AC5:** Diagnose-Output zeigt Mike was vorher kaputt war
  (Wurzel dokumentiert für Memory)

## 6. Test-Plan

- **T1:** Unit — `_save_and_close` emittet `live_settings_changed`
  Signal nach Settings-Schreibung
- **T2:** Integration — `_apply_live_settings` Slot ruft
  `radio.set_swr_limit()` mit aktuellem Settings-Wert
- **T3:** `radio.ip is None` → Slot überspringt Setter-Call (kein
  AttributeError)
- **T4:** Connect-Hook in mw_radio.py:179 unverändert (Regression)
- **T5:** Bestehende SWR-Watchdog-Tests grün (Final-R1-Schutz)

## 7. Files

- `ui/settings_dialog.py` — Signal-Def + emit im `_save_and_close`
  - **Save-Hook im `_save_and_close` raus** (Zeilen 681-683 löschen,
    durch Signal-emit ersetzt)
- `ui/main_window.py` — Slot `_apply_live_settings`, Connect in
  `_on_settings_clicked`
- `tests/test_p58_save_hook.py` NEU — 5 Tests

## 8. Workflow-Schritte

1. **V1** (dieses Dokument)
2. **V2 Self-Review** — Findings: gibt es Code-Pfad-Annahmen die
   falsch sind? Race-Conditions? Andere Save-Hooks die brechen
   könnten? Plus: ist Diagnose-Print überhaupt nötig (Option A) wenn
   wir eh den ganzen Pfad umbauen (Option B)?
3. **R1 V4-pro** — Architektur-Review, Klärungs-Q (z.B. weitere
   Live-Settings die heute hartcodiert sind und auch über das
   Signal sollten?), Hardware-Pflicht-Check (ANT1!)
4. **V3** — finale Spec
5. **Code** — 4-5 atomare Commits
6. **Final-R1** — Push-Freigabe
7. **Mike-Field-Test:** Settings öffnen → swr_limit ändern →
   Konsole-Print sofort sichtbar
