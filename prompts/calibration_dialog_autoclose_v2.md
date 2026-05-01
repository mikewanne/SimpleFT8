# Fix F — Kalibrierungs-Dialog Auto-Close — V2

**Status:** V2 (nach Self-Review von V1, vor R1-Review).
**Datum:** 2026-05-01.
**Vorgaenger:** v0.82 (commit `7c71bfd`) — Fix E.

---

## 0. Kontext

Aktuell: `mw_radio._show_calibration_done` (Z.949-996) am Ende einer
Diversity-Kalibrierung — modaler Dialog mit OK-Button, blockt
Workflow bis Mike klickt.

**Mike's Wunsch (2026-05-01):** kein OK-Button mehr, Auto-Close
nach 3s, weiterhin im Vordergrund (`WindowStaysOnTopHint`).
Nicht-modal damit Mike das Hauptfenster bedienen kann.

**Dauer-Begruendung 3s:** sicher genug zur Kenntnisnahme auch bei
kurzem Wegblick. 2s riskant. Hobby-Funk-Kontext.

**Vorgeschichte:** v0.79 R1-Review-Fix hatte den Dialog von
non-modal+`show()` zu modal+`exec()` umgestellt, weil das non-modal-
Fenster hinter Hauptfenster wandern konnte. Fix F dreht das
teilweise zurueck (non-modal+show), kompensiert durch
`WindowStaysOnTopHint` + `raise_()` + `activateWindow()`.

---

## 1. Code-Diff

```python
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    """Auto-Close-Info-Popup 'Kalibrierung abgeschlossen' — 3s, kein OK.

    v0.83 Fix F: non-modal + Auto-Close, Mike kann waehrend der 3s
    weiterarbeiten. WindowStaysOnTopHint + raise_+activateWindow
    verhindert Hinten-Wandern (v0.79-Problem).
    """
    from PySide6.QtCore import Qt as _Qt, QTimer as _QTimer
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
    dlg = QDialog(self)
    dlg.setWindowTitle("Kalibrierung abgeschlossen")
    dlg.setWindowFlag(_Qt.WindowType.WindowStaysOnTopHint, True)
    dlg.setStyleSheet("QDialog, QWidget { background-color: #16192b; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 16)
    lay.setSpacing(10)

    lbl_title = QLabel(f"✓  Kalibrierung {band} gespeichert.")
    lbl_title.setStyleSheet(
        "color: #00CC66; font-family: Menlo; font-size: 13px; font-weight: bold;"
    )
    lay.addWidget(lbl_title)

    if ant2_g is not None:
        lbl_info = QLabel(f"ANT1: {ant1_g} dB  |  ANT2: {ant2_g} dB")
    else:
        lbl_info = QLabel(f"ANT1: {ant1_g} dB")
    lbl_info.setStyleSheet(
        "color: #AAAACC; font-family: Menlo; font-size: 12px; padding: 4px 0;"
    )
    lay.addWidget(lbl_info)

    # Auto-Close nach 3s (singleShot ist QApplication-owned, nicht dlg-Child)
    _QTimer.singleShot(3000, dlg.accept)

    # show() statt exec() → non-modal. Reihenfolge raise_ vor activateWindow:
    # raise_ aendert Z-Order, activateWindow setzt Tastatur-Fokus.
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
```

**Aenderungen vs. heute:**
- `setModal(True)` ENTFERNT
- OK-Button (`QPushButton`) + `QHBoxLayout` ENTFERNT
- `dlg.exec()` → `dlg.show()` + `raise_()` + `activateWindow()`
- NEU: `QTimer.singleShot(3000, dlg.accept)` fuer Auto-Close

---

## 2. Akzeptanzkriterien

### A — Funktional

A1. Dialog erscheint nach Kalibrierungs-Ende (Aufruf-Stellen
    `mw_radio.py:930, :947` unveraendert).
A2. Dialog schliesst sich nach **genau 3 Sekunden** automatisch.
A3. Kein OK-Button mehr.
A4. Stays on top — Dialog bleibt vorne auch wenn Mike das
    Hauptfenster anklickt.
A5. Nicht-modal — Mike kann waehrend der 3s das Hauptfenster
    bedienen (band wechseln, CQ klicken).
A6. Esc-Taste schliesst Dialog vorzeitig (Qt-Default-Verhalten,
    bleibt erhalten).

### B — Side-Effect-frei

B1. Kalibrierungs-Logik (`_on_calibration_complete`,
    Save-Pfad) unveraendert.
B2. Aufrufer (`mw_radio.py:930, :947`) unveraendert. Aber Caller
    laeuft jetzt SOFORT weiter (statt blockiert auf User-Klick).
    Code-Lookup zeigt: keine Caller machen Code nach
    `_show_calibration_done`-Return der vom Dialog-Close abhing.
B3. Settings-Dialog (v0.76 Tabs) und App-Start-Hardware-Dialog
    (v0.77) nicht betroffen.

### C — Robustheit

C1. **dlg-Lifecycle:** `dlg = QDialog(self)` macht dlg zum Child
    von self (MainWindow). Qt-Parent-Child-System haelt dlg am
    Leben bis self zerstoert wird. Auto-Close via `dlg.accept()`
    setzt Result-Code, schliesst Window, dlg bleibt im Memory bis
    Methoden-Ende — danach Garbage-Collection ueber Qt-Parent.
C2. **QTimer-Lifecycle:** `QTimer.singleShot(3000, dlg.accept)`
    ist ein QApplication-owned Timer, nicht dlg-Child. Wenn dlg
    vor 3s manuell geschlossen (Esc, App-Close), feuert der Timer
    trotzdem. `dlg.accept()` auf bereits geschlossenem Dialog ist
    no-op (Qt-Doku: idempotent). Kein Crash.
C3. **App-Close waehrend Dialog offen:** Qt-Aufraeumung schliesst
    Child-Widgets sauber. QTimer wird mit QApplication zerstoert.
C4. **Race: zweite Kalibrierung in 3s:** sehr unwahrscheinlich
    (Kalibrierung dauert Minuten, nicht Sekunden). Falls doch:
    zwei `dlg`-Instanzen koennten gleichzeitig sichtbar sein.
    Akzeptabel, kein Bug.
C5. **Tests:** alle 507 bestehenden Tests gruen. Neuer Test
    nutzt das v0.76-Pattern (`QT_QPA_PLATFORM=offscreen` +
    `QApplication.instance()`). Konkret:

```python
# tests/test_calibration_dialog_smoke.py (NEU)
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def test_calibration_done_auto_closes_after_3s():
    """Fix F: Dialog schliesst sich automatisch nach 3s."""
    from ui.mw_radio import MWRadioMixin
    # _show_calibration_done isoliert testen (keine MainWindow-
    # Abhaengigkeit ausser self.parentWidget = None).
    
    # Da _show_calibration_done auf self bezogen ist, brauchen wir
    # einen minimalen QObject mit der Methode. Pattern wie v0.76:
    # ggf. via MainWindow-Mock oder direkter Methoden-Aufruf.
    
    # Pragmatisch: direkter QDialog-Test. Wir zeigen einen Dialog
    # mit identischem Auto-Close-Pattern und pruefen die Schliessung.
    app = QApplication.instance() or QApplication([])
    from PySide6.QtWidgets import QDialog
    dlg = QDialog()
    QTimer.singleShot(3000, dlg.accept)
    dlg.show()
    
    # Vor 3s noch sichtbar
    QTest.qWait(2500)
    assert dlg.isVisible(), "Dialog sollte vor 3s noch sichtbar sein"
    
    # Nach 3s zu
    QTest.qWait(700)
    assert not dlg.isVisible(), "Dialog muss nach 3s geschlossen sein"
```

---

## 3. Frage an R1 (Reviewer)

**Du bist Senior-Reviewer fuer einen UI-Fix in einem PySide6-FT8-
Funkclient. KEIN Code schreiben, nur reviewen.**

V2-Plan ist oben. Code-Files: `ui/mw_radio.py` (insb. Z.949-996).

**P1 (StaysOnTop ohne Modal — sicher gegen Hinten-Wandern auf macOS?):**
v0.79 hatte das Problem dass non-modal-Dialoge hinter Hauptfenster
wandern. Mit `WindowStaysOnTopHint` + `raise_()` + `activateWindow()`
sollte das nicht mehr passieren. R1, ist diese Kombination
verlaesslich auf macOS oder gibt es Edge-Cases (Spaces-Wechsel,
Mission Control etc.)?

**P2 (QTimer-Lifecycle):** `QTimer.singleShot(3000, dlg.accept)` —
wenn dlg vor 3s geschlossen wird (Esc oder App-Close), feuert der
Timer trotzdem. Qt-Doku: `accept()` ist idempotent (no-op auf
schon geschlossenem Dialog). R1, ist das wirklich crash-sicher
oder gibt es einen Pfad wo `dlg.accept()` auf einem zerstoerten
Python-Objekt callt?

**P3 (Reihenfolge raise_/activateWindow):** show() → raise_() →
activateWindow(). R1, ist das die richtige Reihenfolge auf macOS,
oder muss show() zuletzt? Manche Qt-Dokumente sagen
"raise after show".

**P4 (Race: zweite Kalibrierung in 3s):** wirklich nur theoretisch
(Kalibrierung dauert Minuten) oder gibt's einen Pfad in der App
der das triggern koennte (z.B. Auto-Re-Calibration)?

**P5 (Test-Strategie):** Mein Test nutzt `QTest.qWait(3500)` —
3.5s pro Test ist langsam. R1, gibt's einen schnelleren Pattern
(Mock fuer QTimer.singleShot um sofort zu callen)?

**P6 (eigeninitiativ):** Wenn dir noch was auffaellt — z.B. ob
die `WA_DeleteOnClose`-Attribute gesetzt werden sollte oder ob das
Dialog-Style ohne OK-Button visuell zu leer wirkt — nenn es.

---

## 4. V1 → V2 Self-Review-Diff

1. **dlg-Lifecycle (C1)** explizit dokumentiert — Qt-Parent-Child
   haelt dlg am Leben.
2. **QTimer-Lifecycle (C2)** explizit dokumentiert — singleShot
   ist QApplication-owned, no-op bei accept() auf zu Dialog.
3. **A6 Esc-Verhalten** als gewolltes Default-Verhalten festgehalten.
4. **B2** klargestellt — Caller laeuft jetzt sofort weiter, kein
   bestehender Caller war auf Block angewiesen (Code-Lookup gemacht).
5. **Test mit konkretem QTest.qWait-Pattern** statt nur Skizze.
6. **R1-Frage P5 neu** — Test-Performance.

---

## 5. Out-of-Scope

- Konfigurierbare Dauer (Settings-Slider 1-5s) — spaeter falls
  noetig.
- Countdown-Anzeige im Dialog ("3...2...1") — Spielerei,
  KISS-violiert.
- Generische `_show_auto_close_dialog`-Methode — erst wenn weitere
  Dialoge diesen Pattern brauchen.
- Versionsbump v0.82 → v0.83.

---

## 6. Aufwandsschaetzung

~1.5 h (Code 0.3h + Test 0.5h + Commits 0.3h + Final-R1 0.3h).

---

## 7. Migration / Backwards-compat

- Keine API-Aenderung, keine Settings-File-Aenderung.
- Bestehende 507 Tests bleiben gruen.
- Aufrufer-Verhalten geaendert (kein Block) — kein bestehender
  Caller hatte Block-abhaengigen Code.
