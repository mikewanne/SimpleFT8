# P44 Statusbar DT-Label — V2 (Self-Review)

## V1-Klarstellungen + Fundstellen

### L1 — `dt_text`-Verwendung doppelt **bestätigt**
V1-Frage 1: dt_text taucht aktuell in 2 Verwendungen auf:
- `ui/main_window.py:1083-1087` → Bestimmung von text+color
- `ui/main_window.py:1134` → `msg = f"... {dt_text}{omni_str}..."` →
  in `showMessage(msg)`

**Konsequenz:** Wenn wir P44 nur den globalen StyleSheet-Bug fixen aber
`dt_text` weiterhin im msg-String mitschicken, würde DT-Status **doppelt
auftauchen** (einmal im normalen Statusbar-Text, einmal im neuen Label).

**V2-Fix:** Z.1134 muss `dt_text` raus. Neuer msg-Aufbau:
```python
msg = (f"{self.settings.callsign}  |  {self.settings.locator}  |  "
       f"{self.settings.mode} {self.settings.band}  |  "
       f"{freq_display}  |  Filter: {filter_str} Hz  |  "
       f"{mode_str}{omni_str}{freq_str}{ap_str}")
```
(`  |  {dt_text}` raus, `omni_str` direkt nach `mode_str`)

### L2 — `dt_color`-Verwendung
Außer dem buggy `setStyleSheet(...)`-Block (Z.1088-1094) wird `dt_color`
nirgends verwendet. Nach unserem Fix wird `dt_color` nur noch in
`_dt_indicator.setStyleSheet(...)` gebraucht. Variable bleibt.

### L3 — Reihenfolge in Statusbar (V1-Frage 2)
**Aktuell links → rechts (`addPermanentWidget` reiht von links):**
```
Statistik | QRZ-Widget | Help-Button
```

**V1-Vorschlag:** Statistik → DT → QRZ → Help

**V2-Bewertung:** Sinnvoll. Statistik+DT sind beides Status-Indikatoren
(dynamisch, modus-abhängig). QRZ ist Aktions-Widget. Help ist statisch.

Gruppierung „Status-Indikatoren links | Aktions-Widgets rechts" passt.

**V2-Bestätigt:** DT direkt nach Statistik einfügen via
`addPermanentWidget` BEVOR `_qrz_status_widget` hinzugefügt wird.

→ Wichtig: `_dt_indicator` muss in `__init__` direkt nach
`_stats_indicator`-Block eingefügt werden (Z.461) UND BEVOR
`_qrz_status_widget` Z.488 platziert wird.

### L4 — Test-Pattern (V1-Frage 3)

V1 hatte voll-instanzierte MainWindow-Tests vorgeschlagen. Problem:
MainWindow braucht Radio, Settings, Decoder, Encoder etc. — zu schwer
für simple Smoke-Tests.

**V2-Lösung:** Headless-Smoke-Tests mit `QApplication` aus
`QT_QPA_PLATFORM=offscreen`:

```python
import sys
import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel


@pytest.fixture(scope="module")
def qapp():
    """Eine QApplication für alle Tests im Modul."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_dt_indicator_pattern(qapp):
    """Smoke-Test: QLabel als Permanent-Widget in Statusbar funktioniert.

    Wir testen NICHT die volle MainWindow (zu schwer), sondern den
    Pattern selbst — QLabel mit StyleSheet-Wechsel via setText/setStyleSheet.
    """
    win = QMainWindow()
    label = QLabel("DT: —")
    label.setStyleSheet(
        "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
    )
    win.statusBar().addPermanentWidget(label)
    # Default grau
    assert "color: #555" in label.styleSheet()
    assert label.text() == "DT: —"
    # Wechsel auf Korrektur (grün)
    label.setText("DT: Korrektur")
    label.setStyleSheet(
        "color: #00DD66; font-family: Menlo; font-size: 11px; padding: 0 6px;"
    )
    assert "color: #00DD66" in label.styleSheet()
    assert label.text() == "DT: Korrektur"
```

Plus 1 Integration-Test wenn Main-Window-Init in anderen Tests bereits
gemockt ist (siehe `tests/test_modules.py` Pattern). Falls Aufwand zu
hoch → 1 Smoke-Test reicht.

**V2-Test-Count:** 1160 → **1162** (+2 Tests, V1 hatte 3 angepeilt).

### L5 — CSS Padding (V1-Frage 4)
V1 schlug `padding: 0 6px` analog `_stats_indicator` vor. Im
Statusbar mit `_stats_indicator` direkt links bedeutet das:
`Statistik` (6px Padding) | `DT: Korrektur` (6px Padding) → ~12px
horizontaler Abstand zwischen den Indikator-Texten. Visuell OK,
nicht zu eng.

**V2-Bestätigt:** `padding: 0 6px` übernehmen, identisch zum Stats-
Indikator. Konsistenz > Eleganz.

## Final-Diff-Liste V2

### Diff 1 — `__init__` Z.461 erweitern (analog Stats-Indikator-Pattern)

Nach:
```python
self.statusBar().addPermanentWidget(self._stats_indicator)
```

Einfügen (V2 — gleicher Block-Style):
```python
# DT-Korrektur-Indikator (permanentes Widget, rechts in Statusbar
# direkt neben _stats_indicator). Default grau, grün bei aktiver
# Mess-Phase. Konsistent zum Stats-Indikator-Pattern.
self._dt_indicator = _QLabel("DT: —")
self._dt_indicator.setStyleSheet(
    "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
)
self.statusBar().addPermanentWidget(self._dt_indicator)
```

### Diff 2 — `_update_statusbar()` Z.1079-1094 ersetzen

Vorher:
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
        f"color: {dt_color}; font-family: Menlo; font-size: 11px; "
        f"background-color: #0a1a0a;")
else:
    self.statusBar().setStyleSheet(
        "color: #888; font-family: Menlo; font-size: 11px; background-color: #111;")
```

Nachher (P44 v0.97.10):
```python
# DT-Korrektur Status — eigenes Permanent-Widget _dt_indicator (rechts
# in Statusbar neben _stats_indicator). Globaler Statusbar-Style bleibt
# grau wie in __init__ gesetzt — nicht mehr dynamisch ändern.
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

### Diff 3 — Z.1134 `msg`-Aufbau: `{dt_text}` raus

Vorher:
```python
msg = (f"{self.settings.callsign}  |  {self.settings.locator}  |  "
       f"{self.settings.mode} {self.settings.band}  |  "
       f"{freq_display}  |  Filter: {filter_str} Hz  |  "
       f"{mode_str}  |  {dt_text}{omni_str}{freq_str}{ap_str}")
```

Nachher:
```python
msg = (f"{self.settings.callsign}  |  {self.settings.locator}  |  "
       f"{self.settings.mode} {self.settings.band}  |  "
       f"{freq_display}  |  Filter: {filter_str} Hz  |  "
       f"{mode_str}{omni_str}{freq_str}{ap_str}")
```
(`  |  {dt_text}` weg)

## Tests `tests/test_p44_dt_indicator.py` NEU (2 Tests)

```python
"""P44 Statusbar DT-Indikator als eigenes Permanent-Widget (v0.97.10).

Vorher (Bug): DT-Farbe wurde via setStyleSheet auf gesamte Statusbar
gesetzt → alle Texte grün während Korrektur.
Jetzt: DT als eigenes QLabel mit eigener Farbe (analog _stats_indicator).
"""
from __future__ import annotations
import sys
import pytest

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_dt_indicator_pattern_initial_grey(qapp):
    """DT-Indikator-Pattern: Default grau, Text 'DT: —'."""
    win = QMainWindow()
    label = QLabel("DT: —")
    label.setStyleSheet(
        "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
    )
    win.statusBar().addPermanentWidget(label)
    assert "color: #555" in label.styleSheet()
    assert label.text() == "DT: —"


def test_dt_indicator_correction_phase_green(qapp):
    """Wechsel auf 'DT: Korrektur' setzt Text + grüne Farbe nur am Label."""
    win = QMainWindow()
    label = QLabel("DT: —")
    win.statusBar().addPermanentWidget(label)
    # Statusbar bleibt grau (globaler Style unverändert)
    label.setText("DT: Korrektur")
    label.setStyleSheet(
        "color: #00DD66; font-family: Menlo; font-size: 11px; padding: 0 6px;"
    )
    assert label.text() == "DT: Korrektur"
    assert "#00DD66" in label.styleSheet()
    # Wichtig: Statusbar-Stylesheet wurde NICHT verändert
    assert "color: #00DD66" not in win.statusBar().styleSheet()
```

Tests-Count: 1160 → **1162** grün.

## Atomare Commits

**C1:** `ui/main_window.py` (Diff 1 + 2 + 3)
**C2:** `tests/test_p44_dt_indicator.py` NEU
**C3:** APP_VERSION 0.97.9 → 0.97.10 + HISTORY + HANDOFF + CLAUDE-Header

## Backup vor Code

`Appsicherungen/2026-05-13_v0.97.9_vor_p44_dt_indicator/main_window.py` + `_BACKUP_REASON.md`.

## Risiko V2-Update

| Risiko | Wahrsch | Mitigation |
|---|---|---|
| `dt_text` Doppelanzeige | **LOW** (V2 entfernt aus msg-String) | Diff 3 explizit |
| `_dt_indicator` fehlt in Tests | LOW | `hasattr`-Check in `_update_statusbar` |
| Bestehende UI-Layout-Tests rot | LOW | gleicher Pattern wie Stats-Indikator |
| Bestehende `_update_statusbar`-Aufrufe scheitern | LOW | rein additiv, kein Aufruf-Pfad neu |

## Was R1 prüfen soll

1. Ist `hasattr(self, '_dt_indicator')`-Check redundant da `__init__`
   das Attribut garantiert setzt? Oder sinnvoll für Tests/Mocking?
2. Test-Pattern: reichen QLabel-Pattern-Smoke-Tests, oder MUSS
   Integration mit `_update_statusbar()` getestet werden?
3. Diff 3: gibt's andere Verwendungen von `dt_text` im Code? (V2 hat
   nur Z.1083+1134 geprüft — sind das alle?)
4. Reihenfolge `addPermanentWidget`: Statistik→DT→QRZ→Help — UX-OK
   oder besser DT→Statistik (DT zuerst, weil häufiger relevant)?
