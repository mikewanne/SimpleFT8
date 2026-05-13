# P44 Statusbar DT-Korrektur als eigenes Label — V1

## Bug

`ui/main_window.py:1088-1094` setzt bei aktiver DT-Korrektur den
**gesamten** Statusbar-`setStyleSheet` auf grünen Text:

```python
if dt_color != "#888":
    self.statusBar().setStyleSheet(
        f"color: {dt_color}; font-family: Menlo; font-size: 11px; "
        f"background-color: #0a1a0a;")
```

→ ALLE Statusbar-Texte werden grün gefärbt, nicht nur das DT-Stück.
Trotz Kommentar Z.1079 „nur DT-Label gruen, Statusbar bleibt grau".

## Mike's Vision

DT-Status als **eigenes Permanent-Widget** rechts in der Statusbar,
**direkt neben dem `_stats_indicator`**. Konsistente UX:
„dynamische Indikatoren rechts".

- `_stats_indicator`-Pattern (Z.454-461) als Vorbild
- DT-Label nur in seiner eigenen Farbe (grün/grau), nicht Statusbar-
  global
- DT-String raus aus dem zentralen Statusbar-Text-Aufbau

## Akzeptanzkriterien

**AC1 — DT als eigenes Permanent-Widget:**
Neues `self._dt_indicator = QLabel("DT: —")` direkt nach
`addPermanentWidget(self._stats_indicator)` (also Z.~462).

**AC2 — DT-Farben nur am eigenen Label:**
`_update_statusbar()` setzt `_dt_indicator.setText(dt_text)` +
`_dt_indicator.setStyleSheet(f"color: {dt_color}; ...")`.

**AC3 — Globaler Statusbar-StyleSheet bleibt grau:**
Block Z.1088-1094 (`if dt_color != "#888": setStyleSheet(...)`)
komplett raus. Statusbar bleibt grau wie in Z.450-453 initialisiert.

**AC4 — DT raus aus zentralem Text-Aufbau:**
Aktuell wird `dt_text` (z.B. „DT: Korrektur") wahrscheinlich in den
Statusbar-Message-Text gemischt. Diese Verwendung im
`statusBar().showMessage(...)` raus → DT erscheint nur noch im eigenen
Label.

**AC5 — Format/Padding analog `_stats_indicator`:**
```python
self._dt_indicator.setStyleSheet(
    "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
)
```
Default grau. Wechselt bei aktiver Korrektur zu `#00DD66`.

**AC6 — Reihenfolge in Statusbar:**
`addPermanentWidget` fügt rechts an. Aktuell: Statistik → QRZ-Widget →
Help-Button. **Neue Reihenfolge** (links-nach-rechts):
**Statistik → DT → QRZ-Widget → Help-Button**.
Begründung: Statistik + DT sind die 2 dynamischen Status-Indikatoren —
nebeneinander macht Sinn.

**AC7 — Tests:**
- Smoke-Test dass `_dt_indicator` existiert nach `__init__`
- Test dass `_update_statusbar()` Text + Farbe setzt korrekt für die
  3 Phasen (Initial/Aktiv/Korrektur)

**AC8 — Bestehende Tests 1160 bleiben grün.**

## Konkrete Diffs

### Diff 1 — `__init__` Z.461 erweitern

Nach:
```python
self.statusBar().addPermanentWidget(self._stats_indicator)
```

Neu hinzufügen:
```python
# DT-Korrektur-Indikator (permanentes Widget, rechts in Statusbar
# neben _stats_indicator). Default grau, grün bei aktiver Korrektur.
self._dt_indicator = _QLabel("DT: —")
self._dt_indicator.setStyleSheet(
    "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
)
self.statusBar().addPermanentWidget(self._dt_indicator)
```

### Diff 2 — `_update_statusbar()` Z.1079-1094 ersetzen

Vorher (BUG):
```python
# DT-Korrektur Status — nur DT-Label gruen, Statusbar bleibt grau
from core import ntp_time
dt_phase = ntp_time._phase
if ntp_time._correction == 0.0 and ntp_time._is_initial:
    dt_text, dt_color = "DT: —", "#888"
elif dt_phase == "measure":
    dt_text, dt_color = "DT: Korrektur", "#00DD66"
else:
    dt_text, dt_color = "DT: Aktiv", "#888"
# DT-Farbe in Statusbar: gruen bei Korrektur via kurzen StyleSheet-Wechsel
if dt_color != "#888":
    self.statusBar().setStyleSheet(
        f"color: {dt_color}; font-family: Menlo; font-size: 11px; background-color: #0a1a0a;")
else:
    self.statusBar().setStyleSheet(
        "color: #888; font-family: Menlo; font-size: 11px; background-color: #111;")
```

Nachher (FIX, P44 v0.97.10):
```python
# DT-Korrektur Status — eigenes Permanent-Widget rechts (nicht mehr
# global Statusbar). Konsistent mit _stats_indicator.
from core import ntp_time
dt_phase = ntp_time._phase
if ntp_time._correction == 0.0 and ntp_time._is_initial:
    dt_text, dt_color = "DT: —", "#888"
elif dt_phase == "measure":
    dt_text, dt_color = "DT: Korrektur", "#00DD66"
else:
    dt_text, dt_color = "DT: Aktiv", "#888"
if hasattr(self, '_dt_indicator'):
    self._dt_indicator.setText(dt_text)
    self._dt_indicator.setStyleSheet(
        f"color: {dt_color}; font-family: Menlo; "
        f"font-size: 11px; padding: 0 6px;"
    )
```

### Diff 3 — DT-String aus zentralem Text raus

Wenn `dt_text` irgendwo in `f"... {dt_text} ..."` im Statusbar-Message-
Aufbau verwendet wird, MUSS dieser Token rausfallen. Im Code grep nach
`dt_text` zeigt ob er noch im `showMessage`-Pfad lebt.

→ Bei V2 prüfen: wo wird `dt_text` aktuell außer in Diff-2-Bereich
verwendet? Falls in `showMessage`-String → raus.

## Files

- **Modified:** `ui/main_window.py` (Diff 1 + 2 + ggf. 3)
- **New:** `tests/test_p44_dt_indicator.py` (2-3 Tests)

## Tests-Plan

```python
def test_dt_indicator_exists_after_init(main_window):
    """_dt_indicator wird beim __init__ erstellt + ist Permanent-Widget."""
    assert hasattr(main_window, '_dt_indicator')

def test_dt_indicator_initial_state(main_window):
    """Vor erster Korrektur: DT: — in grau."""
    main_window._update_statusbar()
    assert main_window._dt_indicator.text() == "DT: —"
    assert "color: #888" in main_window._dt_indicator.styleSheet()

def test_dt_indicator_correction_phase(main_window, monkeypatch):
    """Während Mess-Phase: DT: Korrektur in grün."""
    from core import ntp_time
    monkeypatch.setattr(ntp_time, '_correction', 0.5)
    monkeypatch.setattr(ntp_time, '_is_initial', False)
    monkeypatch.setattr(ntp_time, '_phase', 'measure')
    main_window._update_statusbar()
    assert main_window._dt_indicator.text() == "DT: Korrektur"
    assert "#00DD66" in main_window._dt_indicator.styleSheet()
```

## Atomare Commits

**C1:** `ui/main_window.py` (Diff 1 + 2 + 3)
**C2:** `tests/test_p44_dt_indicator.py` NEU
**C3:** APP_VERSION 0.97.9 → 0.97.10 + HISTORY + HANDOFF + CLAUDE-Header

## Backup vor Code

`Appsicherungen/2026-05-13_v0.97.9_vor_p44_dt_indicator/` mit Vermerk.

## Risiko

| Risiko | Wahrsch | Mitigation |
|---|---|---|
| Statusbar-Layout bricht | LOW | gleiches Pattern wie `_stats_indicator` |
| `_dt_indicator` fehlt in Test-Instances | LOW | `hasattr`-Check in `_update_statusbar` |
| DT-Text taucht doppelt auf | MITTEL | V2: grep `dt_text` Verwendung prüfen |
| Bestehende Tests rot | LOW | `_update_statusbar()` ist UI-Pfad, separate Tests |

## Was V2/R1 prüfen sollten

1. Wird `dt_text` außerhalb dieses Blocks verwendet (z.B. in
   `statusBar().showMessage(...)`)? Falls ja, raus damit.
2. Reihenfolge AC6: Statistik → DT → QRZ → Help — UX-sinnvoll oder
   anders herum?
3. Test-Pattern: MainWindow voll instanziieren vs mocken?
4. CSS: `padding: 0 6px;` analog `_stats_indicator` — passt das auch
   visuell wenn beide nebeneinander stehen?
