# Fix F — Kalibrierungs-Dialog Auto-Close (3s, kein OK-Button) — V1

**Status:** V1 (Erstentwurf, vor Self-Review).
**Datum:** 2026-05-01.
**Vorgaenger:** v0.82 (commit `7c71bfd`) — Fix E Decoder-Signal-Reihenfolge.

---

## 0. Kontext

Aktuell zeigt `mw_radio._show_calibration_done` (Z.949-996) am Ende
einer Diversity-Kalibrierung einen modalen Dialog mit OK-Button.
Mike muss klicken, sonst blockiert der Workflow.

Mike's Wunsch (2026-05-01): kein OK-Button mehr, Dialog schliesst
sich nach 3 Sekunden automatisch. Bleibt aber weiterhin im
Vordergrund (`WindowStaysOnTopHint`). Nicht-modal damit Mike das
Hauptfenster bedienen kann waehrend der Dialog noch sichtbar ist.

**Dauer-Begruendung 3s statt 2s:** Mike bleibt 3s sicher genug zur
Kenntnisnahme auch bei kurzem Wegblick. 2s ist riskant. Mike's
Use-Case ist Hobby-Funk (kein Contest-Tempo).

**Vorgeschichte:** v0.79 R1-Review-Fix hatte den Dialog von
non-modal+`show()` zu modal+`exec()` umgestellt, weil das non-modal-
Fenster hinter dem Hauptfenster wandern konnte. Fix F dreht das
teilweise zurueck — non-modal mit `show()`, aber:
1. `WindowStaysOnTopHint` (war schon da, bleibt) verhindert
   Hinten-Wandern.
2. `raise_()` + `activateWindow()` als Defense-in-Depth.
3. Auto-Close via `QTimer.singleShot(3000, dlg.accept)`.

---

## 1. Problem im Code

### 1.1 Aktueller Stand

```python
# ui/mw_radio.py:949-996
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    dlg = QDialog(self)
    dlg.setWindowTitle("Kalibrierung abgeschlossen")
    dlg.setModal(True)
    dlg.setWindowFlag(_Qt.WindowType.WindowStaysOnTopHint, True)
    dlg.setStyleSheet("QDialog, QWidget { background-color: #16192b; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 16)
    lay.setSpacing(10)
    # ... Labels ...
    btn = QPushButton("OK")
    btn.clicked.connect(dlg.accept)
    # ... layout ...
    dlg.exec()    # <-- MODAL BLOCK
```

### 1.2 Aenderungen Fix F

```python
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    dlg = QDialog(self)
    dlg.setWindowTitle("Kalibrierung abgeschlossen")
    dlg.setWindowFlag(_Qt.WindowType.WindowStaysOnTopHint, True)
    # KEIN setModal(True)
    dlg.setStyleSheet("QDialog, QWidget { background-color: #16192b; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 16)
    lay.setSpacing(10)
    # ... Labels (unveraendert) ...
    # OK-Button ENTFERNT
    # Optional: dezenter Hinweis "schliesst in 3s"

    # Auto-Close nach 3s
    from PySide6.QtCore import QTimer as _QTimer
    _QTimer.singleShot(3000, dlg.accept)

    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
```

---

## 2. Akzeptanzkriterien

### A — Funktional

A1. **Dialog erscheint nach Kalibrierungs-Ende** — wie heute, am
    Ende von `_on_calibration_complete` (oder analog).
A2. **Dialog schliesst sich nach 3 Sekunden automatisch** — kein
    User-Klick noetig.
A3. **Kein OK-Button mehr** — leerer Bereich darunter.
A4. **Stays on top** — Dialog bleibt vorne auch wenn Mike das
    Hauptfenster anklickt.
A5. **Nicht-modal** — Mike kann waehrend der 3s das Hauptfenster
    bedienen (band wechseln, CQ klicken).

### B — Side-Effect-frei

B1. Kalibrierungs-Logik selbst (ant1_g / ant2_g Berechnung,
    Save-Pfad) unveraendert. Nur das End-Popup wird modifiziert.
B2. Bestehende Aufrufer von `_show_calibration_done`
    (mw_radio.py:930, :947) unveraendert — die Methode ruft sich
    asynchron mit `show()` statt blockierend mit `exec()`. Caller
    laeuft ohne Wartezeit weiter.
B3. Settings-Tab (v0.76) und Settings-Dialog (v0.77) nicht
    betroffen.

### C — Robustheit

C1. **Wenn Mike Kalibrierung abbricht waehrend Dialog offen:** der
    Dialog ist schon zu wenn Abbruch kommt (3s vergehen schnell).
    Akzeptabel — Edge-Case selten.
C2. **App-Close waehrend Dialog offen:** QTimer ist Child von
    QApplication, wird beim App-Close aufgeraeumt. dlg ist Child
    von self (MainWindow), wird auch aufgeraeumt.
C3. **Tests:** alle 507 bestehenden Tests gruen. Neuer Test:
    `test_calibration_done_auto_close_after_3s` — Mock-basiert,
    pruefe dass nach `QTimer.singleShot` der Dialog `.accept()`
    bekommt.

---

## 3. Code-Diff-Skizze (komplette neue Methode)

```python
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    """Auto-Close-Info-Popup 'Kalibrierung abgeschlossen' — 3s, kein OK.

    v0.83 Fix F: non-modal + Auto-Close, Mike kann waehrend der 3s
    weiterarbeiten. WindowStaysOnTopHint + raise_/activateWindow
    ersetzen das alte Modal-Verhalten gegen Hinten-Wandern.

    v0.79 (vorher): Modal + exec() weil non-modal hinter Hauptfenster
    verschwand. Mit raise_+activateWindow + StaysOnTopHint sollte das
    nicht mehr passieren.
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

    # Auto-Close nach 3s
    _QTimer.singleShot(3000, dlg.accept)

    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
```

Geloescht: OK-Button + QHBoxLayout + Import QPushButton.
Geaendert: `dlg.setModal(True)` weg, `dlg.exec()` → `dlg.show()`,
`QTimer.singleShot(3000, dlg.accept)` neu, `raise_/activateWindow`
neu.

---

## 4. Frage an R1 (Reviewer)

R1, du bist Senior-Reviewer fuer einen UI-Fix. Pruefe gegen
ANGEHAENGTEN Code (`ui/mw_radio.py`) und beantworte:

**P1 (StaysOnTop ohne Modal — sicher gegen Hinten-Wandern?):** v0.79
hatte das Problem dass non-modal-Dialoge hinter das Hauptfenster
wandern. Mit `WindowStaysOnTopHint` + `raise_()` + `activateWindow()`
sollte das nicht mehr passieren. R1, ist diese Kombination
verlaesslich auf macOS oder gibt es Window-Manager-Edge-Cases?

**P2 (QTimer-Lifecycle):** `QTimer.singleShot(3000, dlg.accept)` —
wenn dlg vor Ablauf der 3s manuell geschlossen wird (z.B. via Esc),
feuert der Timer trotzdem nach 3s und ruft `accept()` auf einem
schon geschlossenen Dialog. Ist das ein Problem oder no-op?

**P3 (Race-Condition: zweite Kalibrierung in 3s):** Wenn Mike
hypothetisch eine zweite Kalibrierung in den 3s startet, wuerden
zwei Dialoge gleichzeitig sichtbar sein. Ist das ein Problem oder
wirklich nur theoretisch (Kalibrierung dauert Minuten, nicht 3s)?

**P4 (Test-Strategie):** Wie kompakt kann der Test sein? Idealerweise
ohne MainWindow-Setup. Mock fuer QDialog? `QSignalSpy` auf
`dlg.accepted`?

**P5 (Esc-Taste / Ctrl-W):** Default-Behavior von QDialog — Esc
schliesst Dialog. Soll das so bleiben? Mike koennte Esc druecken um
schneller weiterzumachen. Wahrscheinlich JA, lassen.

**P6 (eigeninitiativ):** Wenn dir noch was auffaellt — z.B. ob der
Style-Hint noch passt fuer einen Dialog ohne Buttons — nenn es.

---

## 5. Out-of-Scope

- Konfigurierbare Dauer (Settings: 1/2/3/5 Sekunden Slider) —
  spaeter falls Mike das will.
- "Schliesst in 3 ... 2 ... 1" Countdown im Dialog — Spielerei,
  KISS-violiert.
- Replace `_show_calibration_done` durch generische
  `_show_auto_close_dialog`-Methode — erst wenn weitere Dialoge
  diesen Pattern brauchen (KISS).

---

## 6. Aufwandsschaetzung

| Schritt | h |
|---|---|
| Code-Aenderung (~10 Zeilen) | 0.3 |
| 1 Test | 0.5 |
| HISTORY.md + atomare Commits | 0.3 |
| Final-R1-Codereview | 0.3 |
| **Gesamt** | **~1.5 h** |

---

## 7. Migration / Backwards-compat

- Keine API-Aenderung, keine Settings-File-Aenderung.
- Bestehende Aufrufer (`mw_radio.py:930, :947`) unveraendert. Aber:
  Caller hat jetzt KEIN Block mehr — `_show_calibration_done`
  returnt sofort statt 5+ Sekunden auf User-Klick zu warten. Falls
  ein Caller nach `_show_calibration_done` Code hatte der vom
  Dialog-Close abhing, muesste der angepasst werden. Code-Lookup
  zeigt: keine Caller machen das.
