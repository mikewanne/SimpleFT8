# P102 — Signal-Connection bricht zur Laufzeit (kritisch, brauche R1)

## Symptom

Mike-Field-Test 21.05.2026 mit Radio AN, v0.97.76, **Debug-Log aus
`~/.simpleft8/debug_2026-05-21.log`**:

```
05:13:16.911 [P101] menu-action TUNE 10s clicked → emit signal
05:13:16.912 [P101] ControlPanel bubble: radio_card → control_panel emit s=10
                ← KEIN _on_tune_override called danach
```

User wählt im Kontextmenü „TUNE 10s". `_RadioCard.tune_override_requested.emit(10)`
feuert. Der Bubble-Helper `_bubble_tune_override(10)` läuft und ruft
`ControlPanel.tune_override_requested.emit(10)`. **Aber**
`MainWindow._on_tune_override(duration_s)` wird **NICHT** gerufen.

Linksklick auf TUNE (regulärer Pfad über `tune_clicked`-Signal mit `_on_tune_clicked`)
funktioniert einwandfrei. Nur das `tune_override_requested`-Signal kommt
nicht von `ControlPanel` an `MainWindow` an.

## Code-Pfad (verifiziert)

`ui/control_panel.py:1283`:
```python
class ControlPanel(QWidget):
    ...
    # P95 (v0.97.67): Rechtsklick-Override für TUNE-Dauer (10/15/20s)
    tune_override_requested = Signal(int)
```

`ui/control_panel.py:1440-1450` (in `ControlPanel.__init__`):
```python
self.btn_tune.clicked.connect(self._on_tune_clicked)
# P101 v0.97.75: Bubble via Helper mit debug_log (Connection-Verifikation)
def _bubble_tune_override(s: int):
    from core.debug_log import debug_log
    debug_log("P101",
              f"ControlPanel bubble: radio_card → control_panel emit s={s}")
    self.tune_override_requested.emit(s)
radio_card.tune_override_requested.connect(_bubble_tune_override)
self._tune_override_bubble = _bubble_tune_override   # Closure-Lifeline
```

`ui/main_window.py:760-764`:
```python
self.control_panel.cq_clicked.connect(self._on_cq_clicked)
self.control_panel.tune_clicked.connect(self._on_tune_clicked)  # geht!
# P95 (v0.97.67): Rechtsklick-Override für TUNE-Dauer (10/15/20s)
self.control_panel.tune_override_requested.connect(
    self._on_tune_override)
```

`ui/mw_tx.py:106-145` definiert `_on_tune_override` als Methode des
TXMixin. `MainWindow` erbt diesen Mixin.

## Was funktioniert vs. was nicht

**Funktioniert:**
- `tune_clicked` Signal (Z.761): `clicked.emit` → `_on_tune_clicked` läuft sauber.
- `_bubble_tune_override` läuft und macht `self.tune_override_requested.emit(s)`
  (Log-Beweis Z.05:13:16.912).
- Pytest-Mocks finden `_on_tune_override` und es läuft korrekt (1697 Tests grün).

**Funktioniert NICHT zur Laufzeit:**
- `ControlPanel.tune_override_requested.emit(10)` → `MainWindow._on_tune_override`
  ausgelöst werden. Die Connection in main_window.py:763 emittet nichts.

## Hypothesen

**H1:** Zwei verschiedene Signal-Objekte. Wenn `ControlPanel` z.B. dynamisch
ein eigenes Attribut überschreibt nachdem die Connection gemacht wurde
(Replacement von `tune_override_requested`), zeigt der Connect auf den
ALTEN Signal-Slot der nie emittet wird.

**H2:** Reihenfolge: `main_window.py:763` connectet VOR der `ControlPanel`-
Instanz fertig initialisiert ist? Aber `connect()` wird nach `self.control_panel = ControlPanel(...)` aufgerufen — sollte safe sein.

**H3:** Closure-/GC-Problem. `_bubble_tune_override` ist eine inner-Funktion;
durch `self._tune_override_bubble = _bubble_tune_override` halte ich eine
Referenz (war heute mein Fix). Aber vielleicht ist `self.tune_override_requested`
selbst ein bound-Method-Wrapper der GC'd wird?

**H4:** Falscher `Signal()`-Klassen-Scope. Klassen-Attribut `tune_override_requested = Signal(int)`
auf `ControlPanel`. Wenn `self.tune_override_requested` instanz-spezifisch
überschrieben würde, wäre die Connection von außen tot.

**H5:** Qt-Connection-Type. Direct vs Queued — bei thread-übergreifend
braucht's `Qt.QueuedConnection`. Aber `_bubble_tune_override` läuft im GUI-Thread,
deshalb sollte default DirectConnection okay sein.

**H6:** Es gibt ZWEI ControlPanel-Instanzen — die im `main_window.control_panel`
referenzierte und eine andere. Die Connection zeigt auf die FALSCHE.

## Was ich brauche

1. Welche der 6 Hypothesen ist plausibelste?
2. Wie verifiziere ich es im Code?
3. Robuster Fix — z.B. `_on_tune_override` direkt am Helper aufrufen
   statt über Doppel-Signal-Hop?

## Idee Variante X (KISS)

Komplett ohne 2. Signal-Hop: `_bubble_tune_override` direkt
`main_window._on_tune_override` aufrufen, oder dem `_RadioCard` einfach
einen Callback-Slot übergeben statt eines Bubbling-Signals:

```python
# In control_panel.py:
self._tune_override_callback = None  # wird vom MainWindow gesetzt

def on_tune_override_requested(self, callback):
    self._tune_override_callback = callback
    radio_card.tune_override_requested.connect(
        lambda s: callback(s) if callback else None)

# In main_window.py:
self.control_panel.on_tune_override_requested(self._on_tune_override)
```

Damit nur **ein** Connect — vom `_RadioCard.tune_override_requested` direkt
zu `MainWindow._on_tune_override`. Kein ControlPanel-Signal mehr in der Kette.

Ist das Mike-Spec-konform (KISS, kein Overengineering) und behebt H1-H6?
