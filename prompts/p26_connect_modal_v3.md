# P26.CONNECT-MODAL — V3 (FINAL, EINZIGE WAHRHEIT)

> **Compact-fest.** Nach diesem Plan wird Code geschrieben.
> Reihenfolge V1 → V2 → R1 → V3 abgeschlossen.

## Änderungen V2 → V3 (R1-Findings eingearbeitet)

R1 hat **3 KRITISCH** + **3 SOLLTE-FIX** geliefert. Alle in V3 adressiert:

| R1-Finding | V3-Antwort |
|---|---|
| **K1**: RuntimeError bei Signal-Emit nach Dialog-Destroy (PySide6) | Worker holt lokale Dialog-Referenz, `emit` in `try/except RuntimeError` |
| **K2**: `exec()` blockiert im `__init__`-Fluss (10+ Steps nach `_start_radio`) | `_start_radio()` deferred via `QTimer.singleShot(0, ...)` — `__init__` läuft erst durch, `window.show()` zuerst, dann Modal |
| **K3**: Race `connected` vor `exec()` | Connect VOR Worker-Start, lokale Worker-Referenz, try/except — F3 löst sich mit F1-Fix |
| **S1**: disconnect try/except | Schon im V2-Plan, bleibt |
| **S2**: 2 Race-Tests fehlen | T10 + T11 ergänzt (Dialog-Destroy mid-emit, connected vor exec) |
| **S3**: Lokale Worker-Referenz | Adressiert in K1-Fix |

KOENNTE-Findings (Hyperlink, Spinner, "Erneut versuchen") alle wie V2 —
keine Änderung.

## 1. Ziel

Modaler Status-Dialog beim App-Start während FlexRadio gesucht/verbunden
wird. Mit Bypass "ohne Radio weiter" (Test/Debug, Radio aus, 200km weg).

Mike-Spec 10.05.2026:
- Nur beim App-Start, nicht bei mid-Run-Reconnect
- Spinner + Text "FlexRadio wird verbunden..."
- "Versuch X von 10" live
- "ohne Radio weiter" als kleiner Text-Link unten links
- "Beenden" Button unten rechts
- Auto-Close bei `connected`-Signal
- Reconnect-Pfad unangetastet

## 2. Architektur

### 2a. App-Start-Reihenfolge (V3 vs heute)

**Heute:**
```
main() → MainWindow.__init__:
    _setup_ui()
    _start_radio()  ← Zeile 75, startet Background-Thread (non-blocking)
    [10 weitere Init-Schritte]
window.show()
app.exec()
```

**V3:**
```
main() → MainWindow.__init__:
    _setup_ui()
    QTimer.singleShot(0, self._start_radio)  ← deferred, NICHT direkter Aufruf
    [10 weitere Init-Schritte]
window.show()                                 ← Hauptfenster zuerst sichtbar
app.exec()
    → singleShot(0) feuert
    → _start_radio() öffnet Dialog mit exec()  ← Modal über sichtbarem Hauptfenster
```

### 2b. Modal-Lifecycle

```
_start_radio:
    1. self._connect_dialog = ConnectStatusDialog(self)
    2. self.radio.connected.connect(dialog.accept, QueuedConnection)
    3. threading.Thread(target=_connect_worker, daemon=True).start()
    4. result = self._connect_dialog.exec()       ← BLOCKIERT GUI-Thread
    5. # nach Return:
    6. try: self.radio.connected.disconnect(dialog.accept) except (TypeError, RuntimeError): pass
    7. self._connect_dialog = None
    8. # Restliche Setup-Aufrufe (Audio-Callback etc.) wie heute
```

### 2c. Worker-Thread (cross-thread Signal-Emit)

```python
def _connect_worker(self):
    dlg = self._connect_dialog  # K1-Fix: lokale Referenz, atomarer Read

    def on_attempt(attempt: int, max_attempts: int):
        # K1-Fix: try/except RuntimeError gegen destroyed Dialog
        if dlg is not None:
            try:
                dlg.attempt_changed.emit(attempt, max_attempts)
            except RuntimeError:
                pass  # Dialog destroyed, Worker läuft im Demo-Modus weiter

    ok = self.radio.auto_connect(
        max_retries=10, retry_delay=3.0,
        on_attempt=on_attempt
    )
    if not ok:
        self.control_panel.set_connection_status("disconnected")
        if dlg is not None:
            try:
                dlg.failed_signal.emit()
            except RuntimeError:
                pass
```

## 3. Akzeptanzkriterien (final)

A1. **Modal beim Start (deferred):** `_start_radio()` wird via
    `QTimer.singleShot(0, self._start_radio)` aus `__init__` aufgerufen,
    nicht direkt. Hauptfenster ist sichtbar BEVOR Modal öffnet.

A2. **WindowModal:** Decoder/Signal-Pfade laufen weiter. Pattern aus
    `MessStatusDialog`.

A3. **Layout:**
    - Titel "FlexRadio wird verbunden"
    - Spinner-Label (animierte Punkte)
    - Versuch-Counter-Label
    - Spacer
    - HBox: "ohne Radio weiter" (Hyperlink-Style links) | "Beenden" (Button rechts)

A4. **Spinner:** 3-Punkt-Animation `.` → `..` → `...` via QTimer 500ms.
    Fixed-Width-Font (Menlo) damit Layout nicht hüpft.

A5. **Versuch-Counter live:** `attempt_changed`-Signal aus Worker
    triggert `set_attempt(attempt, max)`. Initial-Text vor erstem
    Callback: "Verbindungsaufbau läuft...".

A6. **Auto-Close bei `connected`:** Signal direkt mit `dialog.accept`
    verbunden (QueuedConnection wegen cross-thread-emit aus Worker).

A7. **"ohne Radio weiter":** QPushButton mit `objectName="weiterLink"`
    + Stylesheet (transparent, underline, blau-grau). Click → `reject()`.

A8. **"Beenden":** `QApplication.quit()` → App schließt sauber.

A9. **Failed-State:** Nach `auto_connect`-Fail emittet Worker
    `failed_signal`. Slot stoppt Spinner-Timer, setzt rotes "✗", ändert
    Versuch-Label auf "Verbindung fehlgeschlagen — Radio aus oder nicht
    erreichbar". Buttons bleiben aktiv.

A10. **Reconnect-Pfad UNANGETASTET:** `_on_radio_disconnected` öffnet
     KEIN Modal. Heutiges Verhalten 1:1.

A11. **`auto_connect`-Signatur:** zusätzlicher `on_attempt: Optional[
     Callable[[int, int], None]] = None` Parameter. Default None
     erhält Abwärtskompatibilität (`tests/test_modules.py:133+148`
     bleiben grün).

A12. **`_connect_dialog`-Attribut:** in `MainWindow.__init__` als
     `self._connect_dialog: Optional[ConnectStatusDialog] = None`
     vor allem anderen deklariert.

A13. **K1-Fix Race:** Worker holt lokale `dlg = self._connect_dialog`-
     Referenz EINMAL. Alle `emit`-Aufrufe in `try/except RuntimeError`
     gewrapped.

A14. **K2-Fix Defer:** `_start_radio()` wird NICHT mehr direkt aus
     `__init__` aufgerufen, sondern via `QTimer.singleShot(0, self._start_radio)`.

A15. **K3-Fix Race-vor-exec:** `connect()` VOR `Thread.start()` UND
     VOR `exec()`. Wenn Connect dennoch sehr schnell wird, ruft
     `accept()` vor `exec()` — Qt-garantiert: `exec()` returned sofort
     mit `Accepted` (`QDialog::done`-Doku).

A16. **Disconnect nach exec:** explizit
     `self.radio.connected.disconnect(dialog.accept)` in try/except
     gegen `(TypeError, RuntimeError)` nach `exec()`-Return.

A17. **Style-Konsistenz:** dunkles Theme #16192b, Akzent #7CC, Menlo,
     fixed 440×220.

## 4. Datei-Änderungen (final)

### 4a. `radio/flexradio.py:89-113` — `auto_connect` erweitern

```python
def auto_connect(
    self,
    max_retries: int = 5,
    retry_delay: float = 3.0,
    on_attempt: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """Auto-Discovery + Connect mit Retry bis Radio gefunden.

    on_attempt: Optional Callback für UI-Anzeige (1-indexed,
    aufgerufen am Anfang jedes Versuchs).
    """
    for attempt in range(max_retries):
        if on_attempt is not None:
            try:
                on_attempt(attempt + 1, max_retries)
            except Exception:
                pass  # Modal-Tot ist kein FlexRadio-Problem
        # ... bestehender Code 1:1 ...
```

LOC: ~+8.

### 4b. `ui/connect_status_dialog.py` — NEU

```python
"""SimpleFT8 ConnectStatusDialog — Modal beim App-Start während
FlexRadio gesucht/verbunden wird.

P26 (10.05.2026): User soll wissen was die App tut, und einen Bypass
haben falls Radio nicht da ist (test/debug/200km-weg).

WindowModal damit Qt-Event-Loop weiterläuft (Decoder, Reconnect-Logik).
Auto-Close bei `connected`-Signal vom Aufrufer connectet (mw_radio).
Cancel: Demo-Modus ("ohne Radio weiter") oder QApp.quit ("Beenden").
"""

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)


class ConnectStatusDialog(QDialog):
    """Modaler Status-Dialog während FlexRadio-Connect."""

    # Cross-thread Signals (emit aus Worker, Slot im GUI-Thread).
    # Qt AutoConnection erkennt Thread-Diff → QueuedConnection.
    attempt_changed = Signal(int, int)
    failed_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dots_state = 0
        self._failed = False

        self.setWindowTitle("FlexRadio wird verbunden")
        self.setFixedSize(440, 220)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        self._setup_ui()
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick_dots)
        self._tick_timer.start(500)
        self._tick_dots()  # initialer Punkt

        # Cross-thread Slots
        self.attempt_changed.connect(self.set_attempt)
        self.failed_signal.connect(self.set_failed)

    def _setup_ui(self):
        # Style analog MessStatusDialog
        self.setStyleSheet("""
            QDialog { background-color: #16192b; }
            QLabel  { background-color: transparent; color: #CCC; }
            QPushButton {
                background-color: #2a2f4a; color: #DDD;
                border: 1px solid #444; padding: 6px 14px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #3a4060; }
            QPushButton#weiterLink {
                background: transparent; border: none;
                color: #6a99c4; text-decoration: underline;
                padding: 0; text-align: left;
            }
            QPushButton#weiterLink:hover { color: #99c4e3; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel("FlexRadio wird verbunden")
        title.setFont(QFont("", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #7CC; background-color: transparent;")
        layout.addWidget(title)

        self._spinner_label = QLabel(".")
        self._spinner_label.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        self._spinner_label.setStyleSheet("color: #7CC;")
        self._spinner_label.setFixedHeight(28)
        layout.addWidget(self._spinner_label)

        self._attempt_label = QLabel("Verbindungsaufbau läuft...")
        self._attempt_label.setFont(QFont("Menlo", 11))
        layout.addWidget(self._attempt_label)

        layout.addStretch()

        btn_row = QHBoxLayout()
        self._btn_weiter = QPushButton("ohne Radio weiter")
        self._btn_weiter.setObjectName("weiterLink")
        self._btn_weiter.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_weiter.clicked.connect(self._on_continue_without_radio)
        btn_row.addWidget(self._btn_weiter)

        btn_row.addStretch()

        self._btn_quit = QPushButton("Beenden")
        self._btn_quit.clicked.connect(self._on_quit)
        btn_row.addWidget(self._btn_quit)
        layout.addLayout(btn_row)

    @Slot()
    def _tick_dots(self):
        self._dots_state = (self._dots_state + 1) % 3
        self._spinner_label.setText("." * (self._dots_state + 1))

    @Slot(int, int)
    def set_attempt(self, attempt: int, max_attempts: int) -> None:
        if self._failed:
            return
        self._attempt_label.setText(f"Versuch {attempt} von {max_attempts}")

    @Slot()
    def set_failed(self) -> None:
        self._failed = True
        self._tick_timer.stop()
        self._spinner_label.setText("✗")
        self._spinner_label.setStyleSheet("color: #c44;")
        self._attempt_label.setText(
            "Verbindung fehlgeschlagen — Radio aus oder nicht erreichbar"
        )

    def _on_continue_without_radio(self):
        self.reject()

    def _on_quit(self):
        QApplication.quit()
        self.reject()  # falls quit() den Event-Loop noch nicht beendet hat

    def closeEvent(self, ev):
        try:
            self._tick_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)
```

LOC: ~+135 NEU.

### 4c. `ui/main_window.py:75` — Defer `_start_radio`

```python
# ALT (Zeile 75):
self._start_radio()

# NEU (V3):
# K2-Fix: deferred damit __init__ erst durchläuft, window.show() zuerst,
# Modal über sichtbarem Hauptfenster (sonst exec() blockiert App-Init).
from PySide6.QtCore import QTimer as _QTimer
_QTimer.singleShot(0, self._start_radio)
```

Plus in `MainWindow.__init__` (frühe Position, vor _setup_ui):

```python
# K1+K3-Fix: Attribut früh deklariert damit Worker-Thread safe drauf
# zugreifen kann (auto_connect-Worker liest das via lokale Referenz).
from typing import Optional as _Optional
self._connect_dialog: _Optional["ConnectStatusDialog"] = None
```

LOC: ~+5 (1× Zeile ersetzt + 2 Zeilen neu).

### 4d. `ui/mw_radio.py:46-84` — Modal-Lifecycle

```python
def _start_radio(self):
    """FlexRadio verbinden + Decoder starten + Modal anzeigen.

    P26: Modal-Dialog während Connect-Versuch (max_retries=10).
    User kann "ohne Radio weiter" oder "Beenden" klicken.
    Auto-Close wenn radio.connected feuert.
    """
    # Audio-Callback + Signals verbinden (wie heute)
    self.radio.on_audio_callback = self.decoder.feed_audio
    self.radio.error.connect(lambda msg: print(f"[Radio] {msg}"))
    self.radio.connected.connect(self._on_radio_connected)
    self.radio.disconnected.connect(self._on_radio_disconnected)

    # Decoder-Signals (wie heute)
    self.decoder.message_decoded.connect(self.on_message_decoded)
    self.decoder.cycle_decoded.connect(self._on_cycle_decoded)
    self.decoder.cycle_finished.connect(self._on_cycle_finished)

    # Encoder (wie heute)
    self.encoder.set_radio(self.radio)
    self.encoder.set_decoder(self.decoder)
    self.encoder.tx_started.connect(
        lambda msg, te, sst: self.control_panel.set_tx_active(True)
    )
    self.encoder.tx_started.connect(
        self._on_tx_started, Qt.ConnectionType.QueuedConnection,
    )
    self.encoder.tx_finished.connect(self._on_tx_finished)

    # P26: Modal öffnen BEVOR Worker-Thread startet
    from ui.connect_status_dialog import ConnectStatusDialog
    self._connect_dialog = ConnectStatusDialog(self)
    self.radio.connected.connect(
        self._connect_dialog.accept,
        Qt.ConnectionType.QueuedConnection,
    )

    # Auto-Connect im Hintergrund
    self.control_panel.set_connection_status("searching")
    threading.Thread(
        target=self._connect_worker, daemon=True
    ).start()

    # Modal blockiert GUI-Thread (WindowModal: Decoder/Signals laufen weiter)
    self._connect_dialog.exec()

    # Cleanup nach exec()-Return
    try:
        self.radio.connected.disconnect(self._connect_dialog.accept)
    except (TypeError, RuntimeError):
        pass
    self._connect_dialog = None

def _connect_worker(self):
    """Verbindung im Hintergrund herstellen mit Modal-Updates."""
    # K1-Fix: lokale Referenz (atomarer Read)
    dlg = self._connect_dialog

    def on_attempt(attempt: int, max_attempts: int):
        if dlg is not None:
            try:
                dlg.attempt_changed.emit(attempt, max_attempts)
            except RuntimeError:
                pass  # Dialog destroyed (User klickte "weiter" oder "Beenden")

    ok = self.radio.auto_connect(
        max_retries=10, retry_delay=3.0, on_attempt=on_attempt
    )
    if not ok:
        self.control_panel.set_connection_status("disconnected")
        if dlg is not None:
            try:
                dlg.failed_signal.emit()
            except RuntimeError:
                pass
```

LOC: ~+30 netto.

### 4e. `tests/test_p26_connect_modal.py` — NEU

11 Tests (siehe §6).

LOC: ~+250.

### 4f. `main.py:16` — APP_VERSION

```python
APP_VERSION = "0.96.9"
```

LOC: +1.

## 5. Files-Tabelle

| Datei | LOC | Was |
|---|---|---|
| `radio/flexradio.py` | +8 | `on_attempt`-Param |
| `ui/connect_status_dialog.py` | +135 | NEU |
| `ui/main_window.py` | +5 | Defer + Attribut |
| `ui/mw_radio.py` | +30 | Modal-Lifecycle + Worker |
| `tests/test_p26_connect_modal.py` | +250 | NEU (~11 Tests) |
| `main.py` | +1 | APP_VERSION |

**Gesamt:** ~+429 LOC, davon 385 NEU.

## 6. Test-Plan (11 Tests)

| T | Klasse | Was | Erwartung |
|---|---|---|---|
| T1 | Dialog | Layout-Smoke (Title, Size, Style) | OK |
| T2 | Dialog | Spinner-Animation 3 Ticks | "..." (3 Punkte) |
| T3 | Dialog | `set_attempt(3, 10)` | "Versuch 3 von 10" |
| T4 | Dialog | `set_failed()` | Spinner-Timer stop, "fehlgeschlagen" + ✗ |
| T5 | Dialog | "ohne Radio weiter" Click | `result == Rejected` |
| T6 | Dialog | "Beenden" Click | QApp.quit Mock aufgerufen |
| T7 | Dialog | WindowModal | `windowModality() == WindowModal` |
| T8 | Dialog | Cross-thread `attempt_changed.emit` | Slot via QueuedConnection getriggert |
| T9 | Worker | `auto_connect`-Fail → `failed_signal.emit` | Mock-Radio Fail, dlg.set_failed gerufen |
| T10 | **NEU R1-S2** | emit nach Dialog-deleteLater | kein Crash (try/except greift) |
| T11 | **NEU R1-S2** | `connected`-emit vor `exec()` | `exec()` returned sofort `Accepted` |

**Test-Bilanz:** 1056 → ~1067 (+11). V3-Erwartung ±2 toleriert (Test-
Splits via parametrize möglich).

## 7. Atomare Commits

1. **C1** `radio/flexradio.py` `on_attempt`-Param
2. **C2** `ui/connect_status_dialog.py` NEU
3. **C3** `ui/mw_radio.py` Modal-Lifecycle in `_start_radio` + Worker
4. **C4** `ui/main_window.py` `_connect_dialog`-Attr + Defer via singleShot
5. **C5** `tests/test_p26_connect_modal.py` NEU
6. **C6** `main.py` APP_VERSION + HISTORY/HANDOFF/CLAUDE/Memory

## 8. Field-Test-Plan (Mike, post-Code)

| F | Test | Erwartung |
|---|---|---|
| F1 | App-Start mit Radio AN | Modal kurz sichtbar, Spinner läuft, "Versuch 1 von 10", schließt sofort wenn Connect da, Hauptfenster sichtbar |
| F2 | App-Start mit Radio AUS | Modal bleibt offen, Spinner läuft, Counter zählt "Versuch 1...10", nach ~50s "Verbindung fehlgeschlagen" + ✗, Buttons aktiv |
| F3 | "ohne Radio weiter" mid-Connect | Modal weg, Hauptfenster sichtbar, Status "disconnected", App läuft GUI-only |
| F4 | "Beenden" Click | App schließt sofort sauber |
| F5 | Mid-Run-Disconnect (Radio aus während App läuft) | KEIN neues Modal, heutige Reconnect-Anzeige im Status-Indikator |
| F6 | Connect SEHR schnell (lokales LAN) | Modal flackert kurz auf und ist weg — kein UI-Glitch |

**Bestanden wenn:** F1-F4 sauber. F5+F6 sind Robustheits-Bonus.

## 9. Was NICHT in P26

- KEIN Mess-Guard (P27, separates TODO)
- KEINE Demo-Modus-Logik im radio_factory (kein Mock-Radio, kein Fake-Daten)
- KEIN Modal beim Reconnect (mid-Run-Disconnect)
- KEINE "Erneut versuchen"-Button (Mike-Spec: nur Beenden/Weiter)
- KEINE i18n
- KEIN Logging in simpleft8.log für Modal-Events (KISS, kein Bedarf)

## 10. Test-Bilanz-Erwartung

**1056 → 1067 grün** (+11 P26-Tests). Toleranz ±2.

## 11. APP_VERSION-Bump

0.96.8 → 0.96.9.
