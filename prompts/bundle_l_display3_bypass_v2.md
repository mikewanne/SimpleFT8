# Bundle L V2 Self-Review

**Basis:** `prompts/bundle_l_display3_bypass_v1.md`

## Halluzinations-Check

| V1-Behauptung | Verifikation | Status |
|---|---|---|
| `main.py:530` `window.show()` | grep bestätigt | ✓ |
| `tools/remote/start_simpleft8_nokill.py:216` `window.show()` | grep bestätigt | ✓ |
| `_on_continue_without_radio` Z.211 ruft `self.reject()` | gelesen | ✓ |
| `_on_quit` Z.215 ruft `QApplication.quit() + reject()` | gelesen | ✓ |
| Display 3 = Position (2944, 0) | Memory-Update bestätigt | ✓ |

Keine Halluzinationen.

## Findings

### F1 (RISIKO) — 2 Caller-Pfade müssen synchronisiert werden

V1-Risiken §3: `main.py` UND `start_simpleft8_nokill.py` rufen
`window.show()`. Wenn Display-Move nur in `main.py` rein kommt, fehlt
er im Wrapper.

**Lösung:** Helper-Methode in `MainWindow`, gerufen nach `show()`:

```python
# In MainWindow:
def move_to_remote_display(self):
    """Mike-Wunsch 15.05.-10.06.2026: Fenster auf Display 3 (Position
    2944,0) verschieben für Remote-Fernwartung."""
    self.move(2944, 0)
```

Beide Caller rufen nach `show()`:
```python
window.show()
window.move_to_remote_display()
```

KISS: 1 Methode, 2 Aufrufer.

### F2 (RISIKO) — Display 3 nicht angesteckt = Fenster offscreen

Wenn Mike das Display absteckt, ist (2944, 0) keine sichtbare Position.
Qt-Verhalten: Fenster bleibt offscreen — UNSICHTBAR. Mike sieht App
nicht und denkt sie ist abgestürzt.

**Defensiv:** Vor `move()` prüfen ob ein Screen an (2944, 0) existiert.
Wenn nicht → Move skip, Fenster bleibt auf Main-Display.

```python
def move_to_remote_display(self):
    from PySide6.QtGui import QGuiApplication
    target_x, target_y = 2944, 0
    # Prüfen ob ein Screen die Position abdeckt
    for screen in QGuiApplication.screens():
        geom = screen.geometry()
        if geom.contains(target_x, target_y):
            self.move(target_x, target_y)
            print(f"[Display3] Fenster auf Display 3 verschoben (2944,0)")
            return
    print("[Display3] Display 3 nicht angeschlossen — bleibe auf Main")
```

### F3 (HINWEIS) — Connect-Modal kommt VOR Hauptfenster

`_show_hardware_warning` Dialog + `ConnectStatusDialog` kommen ja BEVOR
`window.show()`. Wenn Mike das Hardware-Modal nicht sieht weil's auf
Main-Display steht, klickt er kein OK → App bleibt blockiert.

**Akzeptanz:** Hardware-Modal soll am Main-Display bleiben (User sieht
es zuerst). NACH OK + Connect läuft Hauptfenster auf Display 3.
Dialog-Position bleibt unverändert (Qt wählt Center-of-Main).

Mike sagt explizit „die app soll immer auf bildschirm 3 zu sehen sein"
— bezieht sich auf das Hauptfenster, nicht auf Modal-Dialoge. KISS.

### F4 (VERBESSERUNG) — Bypass-Button-Text anpassen?

`_on_continue_without_radio` macht jetzt Quit. Button-Text „ohne Radio
weiter" suggeriert noch immer „App läuft weiter". Mike-Antwort nicht
explizit. KISS: Text belassen — Mike weiß was der Button macht (er
hat's ja angefordert). Falls UX-Bug → später ändern.

### F5 (KISS-Check) — Bundle bleibt klein

A+B sind orthogonal, ~10 Zeilen Code gesamt. Bundle macht Sinn weil
gemeinsamer Field-Test (App starten → Display 3 sichtbar UND wenn
„ohne Radio weiter" → App quit).

## V3-Anpassungen

- F1: Helper `MainWindow.move_to_remote_display()` mit Display-Erkennung
- F2: Defensive `QGuiApplication.screens()` Check
- F3: Modal-Position unverändert (Hardware-Modal bleibt Main-Display)
- F4: Button-Text „ohne Radio weiter" belassen
- F5: Bundle als atomare 3 Commits

## R1-Open-Points

1. Macht F2-Defensive Sinn oder ist hartkodiertes `move(2944, 0)` ohne
   Check besser (KISS)?
2. Soll der Helper-Name `move_to_remote_display` heißen oder generischer
   `move_to_preferred_display`?
3. Settings-Migration nach 10.06.2026: Mike will dann wahrscheinlich
   wieder Default-Verhalten. Sollen wir gleich einen Settings-Toggle
   einbauen? Oder Magic-Konstante mit „revert after 10.06"-Kommentar?
