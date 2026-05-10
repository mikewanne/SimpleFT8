# P26.CONNECT-MODAL — V1 (initialer Entwurf)

## 1. Ziel

Modaler Status-Dialog beim App-Start während FlexRadio gesucht/verbunden
wird. Mit Bypass-Möglichkeit "ohne Radio weiter" damit Mike die App auch
ohne Radio starten kann (200 km vom Radio entfernt, Radio aus, Test/Debug).

Mike-Spec 10.05.2026:
- **Nur beim App-Start**, nicht bei mid-Run-Reconnect
- **Spinner + Text** "FlexRadio wird verbunden..."
- **Versuch X von 10** Anzeige (live)
- **"ohne Radio weiter"** als kleiner Text-Link unten links (klein, dezent)
- **"Beenden"** Button unten rechts (sichtbar)
- **Auto-Close** sobald `radio.connected`-Signal kommt
- **Reconnect-Pfad unangetastet** (kein Modal mid-Run)

## 2. Wurzel-Bedingung im Code

Heute (v0.96.8):
- `ui/main_window.py:213` → `self.radio = create_radio(self.settings)` (Init)
- `ui/mw_radio.py:46 _start_radio()` → startet `_connect_worker`-Thread
- `_connect_worker` ruft `self.radio.auto_connect(max_retries=10, retry_delay=3.0)`
- Bei Erfolg: `radio.connected.emit()` → `_on_radio_connected` (mw_radio.py:86)
- Bei Fehler aller 10 Versuche: `set_connection_status("disconnected")`,
  App läuft trotzdem weiter — heute halt nutzlos weil Status nur ein
  kleiner Indikator rechts oben ist und Mike bemerkt das nicht prominent

**Schwäche:** keine Information für Mike was die App gerade tut beim
Start (Sucht? Schlägt fehl?), und keine Bypass-Möglichkeit ohne Radio
zu starten.

## 3. Akzeptanzkriterien

A1. **Modal beim Start:** `ConnectStatusDialog` öffnet in `_start_radio()`
    BEVOR `_connect_worker`-Thread gestartet wird.

A2. **WindowModal (nicht ApplicationModal):** sonst frieren Decoder/Signal-
    Pfade ein. Pattern aus `MessStatusDialog` (P22).

A3. **Layout:** Titel "FlexRadio wird verbunden", animierter Spinner,
    Versuch-Counter, "ohne Radio weiter"-Link unten links, "Beenden"-Button
    unten rechts.

A4. **Spinner-Animation:** KISS — 3 rotierende Punkte (`.` → `..` → `...`)
    via QTimer 500ms, kein QMovie/GIF-Datei.

A5. **Versuch-Counter live:** Während `auto_connect` retries: "Versuch X
    von 10". Update über Callback aus `flexradio.auto_connect`.

A6. **Auto-Close bei Connect:** `radio.connected`-Signal → `dialog.accept()`.
    Modal verschwindet, App geht in Normal-Betrieb (`_on_radio_connected`
    läuft regulär).

A7. **"ohne Radio weiter"-Link:** Klick → `dialog.reject()`. App-Init geht
    weiter ohne Connect-Wartebehandlung. Connect-Worker läuft im
    Hintergrund weiter (nicht stoppbar) — wenn er später doch noch
    erfolgreich ist, läuft `_on_radio_connected` normal. Mike-OK:
    "es ist dann egal ob verbunden oder nicht".

A8. **"Beenden"-Button:** `QApplication.quit()` → App schließt sauber.

A9. **Verbindung fehlgeschlagen:** Wenn alle 10 Versuche durch sind und
    Modal noch offen → Text wechselt zu "Verbindung fehlgeschlagen —
    Radio aus oder nicht erreichbar". Buttons bleiben aktiv. Mike kann
    weiter oder beenden.

A10. **Reconnect-Pfad UNANGETASTET:** `_on_radio_disconnected` triggert
     KEIN Modal — heutiges Verhalten 1:1 (Status-Indikator + Reconnect-
     Loop im Hintergrund).

A11. **Tests-Suite:** mind. 6 neue Tests in `tests/test_p26_connect_modal.py`
     (siehe Sektion 6).

A12. **Style-Konsistenz:** dunkles Theme #16192b, Akzent #7CC, Menlo-Font,
     fixed size 440×220 (analog `MessStatusDialog` aber etwas niedriger
     weil weniger Inhalt).

## 4. Lösungs-Skizze

### 4a. `ui/connect_status_dialog.py` — NEU (~120 Zeilen)

```python
class ConnectStatusDialog(QDialog):
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

    def _setup_ui(self):
        # Style wie MessStatusDialog
        # Vertikales Layout:
        #   - Title "FlexRadio wird verbunden..."
        #   - Spinner-Label "..." (animiert)
        #   - Versuch-Label "Versuch 1 von 10"
        #   - Spacer
        #   - HBox: "ohne Radio weiter" Link links | "Beenden" Button rechts
        ...

    def _tick_dots(self):
        # 0 → "."  1 → ".."  2 → "..."  → reset
        self._dots_state = (self._dots_state + 1) % 3
        self._spinner_label.setText("." * (self._dots_state + 1))

    @Slot(int, int)
    def set_attempt(self, attempt: int, max_attempts: int) -> None:
        """Aufruf aus _connect_worker Callback (via Qt.QueuedConnection)."""
        if self._failed:
            return
        self._attempt_label.setText(f"Versuch {attempt} von {max_attempts}")

    @Slot()
    def set_failed(self) -> None:
        """Alle Versuche durch, kein Connect."""
        self._failed = True
        self._attempt_label.setText(
            "Verbindung fehlgeschlagen — Radio aus oder nicht erreichbar"
        )

    def _on_continue_without_radio(self):
        self.reject()  # User-Bypass

    def _on_quit(self):
        QApplication.quit()  # App zu

    def closeEvent(self, ev):
        self._tick_timer.stop()
        super().closeEvent(ev)
```

### 4b. `ui/mw_radio.py` — Modal-Lifecycle in `_start_radio()`

```python
def _start_radio(self):
    # ... Audio-Callback + Signal-Connections wie heute ...

    # NEU: Modal öffnen BEVOR Connect-Thread startet
    from ui.connect_status_dialog import ConnectStatusDialog
    self._connect_dialog = ConnectStatusDialog(self)
    # Auto-Close bei connected
    self.radio.connected.connect(
        self._connect_dialog.accept,
        Qt.ConnectionType.QueuedConnection
    )

    # Auto-Connect im Hintergrund mit Attempt-Callback
    self.control_panel.set_connection_status("searching")
    threading.Thread(
        target=self._connect_worker, daemon=True
    ).start()

    # Modal blockiert hier (WindowModal aber exec_ wartet auf accept/reject)
    result = self._connect_dialog.exec()
    if result == QDialog.Rejected:
        # User klickte "ohne Radio weiter" oder "Beenden" hat schon QApp.quit aufgerufen
        # Wenn weiter: App geht in GUI-only Modus. _connect_worker läuft im Hintergrund.
        print("[Connect] User: ohne Radio weiter")
    else:
        # Accepted: Connect erfolgreich, _on_radio_connected hat schon gefeuert
        pass
    self._connect_dialog = None

def _connect_worker(self):
    def on_attempt(attempt: int, max_attempts: int):
        # Aus Worker-Thread → Modal via Signal/Slot mit QueuedConnection
        if self._connect_dialog is not None:
            QMetaObject.invokeMethod(
                self._connect_dialog, "set_attempt",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(int, attempt), Q_ARG(int, max_attempts)
            )

    ok = self.radio.auto_connect(
        max_retries=10, retry_delay=3.0,
        on_attempt=on_attempt
    )
    if not ok:
        self.control_panel.set_connection_status("disconnected")
        if self._connect_dialog is not None:
            QMetaObject.invokeMethod(
                self._connect_dialog, "set_failed",
                Qt.ConnectionType.QueuedConnection
            )
```

### 4c. `radio/flexradio.py` — `auto_connect` Callback-Parameter

```python
def auto_connect(
    self,
    max_retries: int = 10,
    retry_delay: float = 3.0,
    on_attempt: Optional[Callable[[int, int], None]] = None,
) -> bool:
    for attempt in range(1, max_retries + 1):
        if on_attempt is not None:
            try:
                on_attempt(attempt, max_retries)
            except Exception:
                pass
        # ... existing connect-logic ...
```

## 5. Files (geänderte LOC-Schätzung)

| Datei | LOC | Was |
|---|---|---|
| `ui/connect_status_dialog.py` | +120 | NEU |
| `ui/mw_radio.py` | ~+25 | Modal-Open + Worker-Callback |
| `radio/flexradio.py` | ~+10 | `on_attempt`-Param in `auto_connect` |
| `tests/test_p26_connect_modal.py` | +200 | NEU (~7 Tests) |
| `main.py` | +1 | APP_VERSION 0.96.8 → 0.96.9 |

**Gesamt:** ~+356 LOC, davon 320 NEU (Dialog + Tests).

## 6. Tests (geplant, ~7)

| T | Was | Erwartung |
|---|---|---|
| T1 | Dialog öffnet bei `_start_radio()` | `_connect_dialog` ist QDialog-Instanz, `isVisible()` True |
| T2 | Auto-Close bei `connected`-Signal | `radio.connected.emit()` → Dialog `result == Accepted` |
| T3 | "ohne Radio weiter" → Reject | Click → Dialog `result == Rejected`, App läuft weiter |
| T4 | "Beenden" → QApplication.quit | Click → `quit_called` True (mit Mock) |
| T5 | Versuch-Counter Update | `set_attempt(3, 10)` → Label-Text "Versuch 3 von 10" |
| T6 | Failed-State | `set_failed()` → Label-Text enthält "fehlgeschlagen", Buttons aktiv |
| T7 | WindowModal (nicht App-Modal) | `dialog.windowModality() == WindowModal` |
| T8 | Reconnect öffnet KEIN Modal | `_on_radio_disconnected()` → kein neues Modal |

**Test-Bilanz:** 1056 → ~1064 grün.

## 7. Stolpersteine / offene Fragen für V2

S1. **Connect-Worker-Thread nicht stoppbar:** Wenn User "ohne Radio
    weiter" klickt, läuft der Worker im Hintergrund weiter und schläft
    in `time.sleep(retry_delay)`. Wenn Connect später doch erfolgreich
    ist: `_on_radio_connected` läuft normal — Mike-OK ("egal").
    **ABER:** wenn User "Beenden" klickt mit `QApplication.quit()`,
    wird der Daemon-Thread automatisch terminiert (Daemon=True). Save.

S2. **Modal-Flow `exec()` blockiert in `_start_radio()`:** Heute ist
    `_start_radio()` im GUI-Thread, blockiert nicht. Wenn ich da
    `dialog.exec()` reinpacke, blockiert der Init-Pfad. Frage: ist das
    OK, oder soll `_start_radio()` weiter non-blocking laufen und
    Modal asynchron geschlossen werden? **V2-Antwort:** non-blocking
    ist sauberer — `dialog.show()` statt `exec()`, accept/reject
    via Signal-Slot.

S3. **`auto_connect`-Signatur erweitern:** Bestehende Aufrufer in
    `tests/test_modules.py` müssen geprüft werden ob sie weiterlaufen
    (Optional-Param mit Default None ist abwärtskompatibel — sollte
    gehen).

S4. **Versuch-Counter-Update von Worker-Thread:** Cross-Thread Qt-
    Method-Call via `QMetaObject.invokeMethod` mit `QueuedConnection`
    ist Standard. Alternative: eigenes Signal `attempt_changed(int,
    int)` im MainWindow definieren, Worker emittet, Modal hört zu.
    Sauberer aber mehr Boilerplate. V2: Signal-Variante nehmen.

S5. **Spinner-Animation einfach halten:** 3 Punkte via QTimer reicht.
    Kein GIF, kein QPropertyAnimation. KISS.

S6. **"ohne Radio weiter" als Hyperlink-Style:** QLabel mit
    `setStyleSheet("color: #4a90c2; text-decoration: underline;")` +
    `mousePressEvent` override, oder QPushButton mit Style "flat" +
    underline. Frage für V2: was sieht in dunklem Theme besser aus?

S7. **Failed-State und Reconnect-Loop:** Heute startet bei `auto_connect`
    Fail KEIN Reconnect-Loop (`_on_radio_disconnected` wird nur bei
    aktivem Disconnect getriggert). Modal bleibt offen, Mike kann
    klicken. → V2 prüfen ob das stimmt oder ob ich `_reconnect_worker`
    triggern sollte. **Heutiges Verhalten beibehalten** ist Mike-Spec.

S8. **Race: Modal noch nicht offen, Connect schon erfolgreich:** Wenn
    Connect SEHR schnell durchkommt (z.B. lokale Mock im Test),
    `connected`-Signal feuert bevor `dialog.exec()` startet. Lösung:
    Signal-Slot vor `exec()` connecten, dann `exec()` returned sofort
    weil `accept()` schon gerufen wurde — geht das so? Oder muss ich
    pre-check `radio.is_connected` einbauen? **V2 klären.**

## 8. Was NICHT in P26

- **KEIN Mess-Guard** (vor Antennen/Diversity/Gain-Mess prüfen ob Radio
  verbunden) — eigenes TODO P27, eigener Workflow.
- **KEINE Demo-Modus-Logik im radio_factory** (Mock-Radio) — App läuft
  einfach mit existierendem Radio-Objekt das halt no-op weil nicht
  verbunden.
- **KEIN Modal beim Reconnect** (mid-Run-Disconnect) — heutiges
  Verhalten unangetastet.
- **KEINE Anzeige im Hauptfenster** (zusätzlich zum Modal) — TODO sagt
  "Modal ist Mike's bevorzugte Variante", reicht.

## 9. Atomare Commits (vorläufig, V3 finalisiert)

- C1 `radio/flexradio.py` `auto_connect` Callback-Param
- C2 `ui/connect_status_dialog.py` NEU
- C3 `ui/mw_radio.py` Modal-Lifecycle in `_start_radio()` + Worker-Callback
- C4 `tests/test_p26_connect_modal.py` NEU
- C5 `main.py` APP_VERSION + HISTORY/HANDOFF/CLAUDE/Memory

## 10. Test-Bilanz-Erwartung

1056 → 1064 grün (+8 P26-Tests).
