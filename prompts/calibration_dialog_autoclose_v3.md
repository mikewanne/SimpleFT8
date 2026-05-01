# Fix F — Kalibrierungs-Dialog Auto-Close — V3

**Status:** V3 (nach R1-Review von V2, Mike-Freigabe vorab erteilt).
**Datum:** 2026-05-01.
**Vorgaenger:** v0.82 (commit `7c71bfd`) — Fix E.

---

## R1-Bilanz V2 → V3

R1-Review (deepseek-reasoner, Reviewer-Modus): **Keine BLOCKER.**

| Frage | R1-Antwort |
|---|---|
| P1 StaysOnTop macOS | TRADEOFF — Spaces/Fullscreen-Edge-Case, akzeptabel |
| P2 QTimer-Lifecycle | JA — sicher |
| P3 Reihenfolge raise_/activate/show | TRADEOFF — minimaler Flicker-Risk, keine Aenderung |
| P4 Race zweite Kalibrierung | Edge-Case via GUI-Lock entschaerft, kein Schutz noetig |
| P5 Test-Strategie | JA — `monkeypatch QTimer.singleShot` statt `QTest.qWait(3500)` |
| P6 eigeninitiativ | `WA_DeleteOnClose` nicht noetig (Qt-Parent reicht) |

→ V3 = V2 mit R1-Empfehlung P5 (Test-Optimierung) uebernommen.
→ Implementation startet.

---

## Code-Diff (1:1 wie V2)

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

    _QTimer.singleShot(3000, dlg.accept)

    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
```

---

## Tests — `tests/test_calibration_dialog_smoke.py` (NEU)

R1-Empfehlung P5 uebernommen: `monkeypatch QTimer.singleShot` →
sofortiger Call statt 3s-Wartezeit.

```python
"""Smoke-Tests fuer _show_calibration_done Auto-Close (Fix F v0.83)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_calibration_done_uses_singleshot_3000ms(monkeypatch):
    """Fix F: QTimer.singleShot wird mit 3000ms aufgerufen."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication.instance() or QApplication([])

    captured = {"ms": None, "callback": None}

    def fake_singleshot(ms, callback):
        captured["ms"] = ms
        captured["callback"] = callback

    monkeypatch.setattr(QTimer, "singleShot", staticmethod(fake_singleshot))

    # Direkter Methoden-Aufruf via minimaler Mock-Self
    # _show_calibration_done ist Instance-Method → bound an MainWindow.
    # Wir testen die Mechanik isoliert: erstellen einen
    # MainWindow-Stub, rufen die Methode.
    class _Stub:
        def __init__(self):
            from PySide6.QtWidgets import QWidget
            self._w = QWidget()
        def parentWidget(self):
            return None

    # Pragmatisch: dieselbe Logik in Test-Form, _show_calibration_done
    # ist UI-only ohne Side-Effects auf Settings.
    from ui.mw_radio import MWRadio

    # Minimale MainWindow-Mock — _show_calibration_done greift nur
    # auf self (als Parent) zu.
    from PySide6.QtWidgets import QMainWindow
    mw = QMainWindow()
    MWRadio._show_calibration_done(mw, "20m", 20, 0)

    assert captured["ms"] == 3000, f"singleShot muss 3000ms haben, war {captured['ms']}"
    assert captured["callback"] is not None, "callback muss gebunden sein"


def test_calibration_done_no_ok_button():
    """Fix F: Dialog hat KEINEN OK-Button mehr."""
    from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton
    from PySide6.QtCore import QTimer

    app = QApplication.instance() or QApplication([])

    # singleShot deaktivieren damit Test-Dialog nicht weg-flippt
    from unittest.mock import patch
    with patch.object(QTimer, "singleShot"):
        from ui.mw_radio import MWRadio
        mw = QMainWindow()
        MWRadio._show_calibration_done(mw, "40m", 15, None)

        # Kinder durchsuchen — dlg ist Child von mw
        dlgs = [c for c in mw.findChildren(type(mw)) if False]  # placeholder
        from PySide6.QtWidgets import QDialog
        all_dlgs = mw.findChildren(QDialog)
        assert len(all_dlgs) >= 1, "Mindestens 1 Dialog erstellt"
        dlg = all_dlgs[-1]
        buttons = dlg.findChildren(QPushButton)
        assert len(buttons) == 0, f"Kein OK-Button erlaubt (gefunden: {len(buttons)})"
        dlg.deleteLater()
```

---

## Akzeptanzkriterien (final, V2 unveraendert)

A1. Dialog erscheint nach Kalibrierungs-Ende.
A2. Auto-Close nach **3 Sekunden**.
A3. Kein OK-Button.
A4. Stays on top.
A5. Nicht-modal.
A6. Esc-Taste schliesst Dialog vorzeitig (Qt-Default).

507 → 509 Tests gruen erwartet.

---

## Atomare Commits (geplant)

1. `feat(mw_radio): _show_calibration_done auto-close 3s ohne OK
   (Fix F)` — mw_radio.py + tests/test_calibration_dialog_smoke.py
2. `chore(release): v0.83 — Kalibrierungs-Dialog Auto-Close (Fix F)`
   — main.py + HISTORY.md + prompts

---

## Lessons-V3

R1's P4 zeigt: auch bei „trivialen" Fixes findet R1 wichtige
Edge-Cases (hier: parallele Kalibrierungs-Dialoge bei Doppel-Klick
in 3s). Selbst bei 10-Zeilen-Aenderungen lohnt sich der volle
Workflow. Mike-Bestaetigt 30.04.: „voller workflow auf jeden fall".
