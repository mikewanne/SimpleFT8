# P26.CONNECT-MODAL — V2 (Self-Review nach V1)

## Methodik V2

V1 mit "frischen Augen" gegengelesen. Stolpersteine S1-S8 aus V1 gelöst,
neue Lessons L1-L14 ergänzt. Code in `flexradio.py:89-113` und
`mw_radio.py:46-84` re-verifiziert.

## V2-Lessons (was V1 verbessert / klärt)

### L1. **Modal-Flow: blocking `exec()` ist OK**

V1-Stolperstein S2: V1 hat überlegt ob `show()` non-blocking sauberer
wäre. **V2-Antwort: `exec()` blockierend wie `MessStatusDialog`** —
Konsistenz, einfacher, WindowModal lässt Decoder/Signal-Pfade trotzdem
laufen. `_start_radio()` wird im GUI-Thread aufgerufen, `exec()` startet
eigene Event-Loop, returned bei `accept()`/`reject()`. Heute ist
`_start_radio()` der letzte Init-Schritt (kein nachfolgender Code) →
blocking unproblematisch.

### L2. **Versuch-Counter: Qt-Signal statt invokeMethod**

V1-Stolperstein S4: V1 schlug `QMetaObject.invokeMethod` vor.
**V2-Antwort: Qt-Signal `attempt_changed(int, int)` im Dialog** —
sauberer, threadsafe per Qt-AutoConnection (cross-thread → automatisch
QueuedConnection). Worker emittet via Lambda. Bei Dialog-Destroy
auto-disconnected.

```python
# Im Dialog:
attempt_changed = Signal(int, int)
self.attempt_changed.connect(self.set_attempt)  # AutoConnection

# Im Worker (in mw_radio._connect_worker):
def on_attempt(attempt, max_attempts):
    if self._connect_dialog is not None:
        self._connect_dialog.attempt_changed.emit(attempt, max_attempts)
```

Race-Schutz: `if self._connect_dialog is not None` ist nicht atomar mit
emit, aber harmlos — wenn Dialog mid-emit destroyed wird, swallowed Qt
das (disconnected Signal feuert ins Leere).

### L3. **`auto_connect`-Signatur: optional `on_attempt`-Param**

V1-Stolperstein S3: V1 sagte abwärtskompatibel via Default None.
**V2-bestätigt:** einziger Aufrufer ist `mw_radio.py:82`. Tests rufen
`auto_connect` nicht direkt auf. Optional-Param mit Default None ist
safe. Signatur:

```python
def auto_connect(
    self,
    max_retries: int = 5,
    retry_delay: float = 3.0,
    on_attempt: Optional[Callable[[int, int], None]] = None,
) -> bool:
    for attempt in range(max_retries):
        if on_attempt is not None:
            try:
                on_attempt(attempt + 1, max_retries)  # 1-indexed für UI
            except Exception:
                pass  # Modal-Tot ist kein FlexRadio-Problem
        # ... bestehender Code ...
```

### L4. **Connect-Worker-Abbruch: NICHT bauen**

V1-Stolperstein S1: V1 sagte "Daemon-Thread sterben lassen".
**V2-bestätigt + ergänzt:** auto_connect hat KEIN abort-Flag (im
Gegensatz zu `reconnect_forever`). Wenn User mid-Connect "ohne Radio
weiter" klickt, läuft Worker bis zu 50s im Hintergrund (10× discover 2s
+ sleep 3s). Wenn dann doch erfolgreich → `_on_radio_connected` läuft
normal, App geht in Normal-Betrieb über.

**Mike-OK 10.05.:** "es ist dann egal ob verbunden oder nicht" → kein
Abbruch nötig. Code-Comment im Worker erklärt das Verhalten.

**Bei "Beenden":** `QApplication.quit()` → MainLoop endet → Daemon-Thread
wird vom Python-Interpreter beim Prozess-Exit terminiert (auch in
`time.sleep`). Save.

### L5. **Hyperlink-Style: QPushButton flat + underline**

V1-Stolperstein S6: V1 fragte zwischen QLabel-Override und QPushButton-
Flat. **V2-Antwort: QPushButton mit Object-Name + Stylesheet:**

```css
QPushButton#weiterLink {
    background: transparent;
    border: none;
    color: #6a99c4;
    text-decoration: underline;
    padding: 0;
    text-align: left;
}
QPushButton#weiterLink:hover { color: #99c4e3; }
```

Vorteile: Click-Handling out-of-the-box (kein mousePressEvent override),
Keyboard-Tabstop, Accessibility. Klein und unscheinbar im dunklen Theme.

### L6. **Spinner: 3-Punkt-Animation via QTimer**

V1-Stolperstein S5: V1 sagte "KISS = 3 Punkte". **V2-bestätigt + Detail:**
QTimer 500ms zyklisch. Animation:

```
"."   →   ".."   →   "..."   →   "."   ...
```

Initial-Text: `"."`. Spinner-Label hat Fixed-Width-Font (Menlo) damit
Text nicht hin-und-her hüpft.

### L7. **Initial-Text vor erstem Callback**

V1-Lücke neu in V2: was zeigt Modal vor dem ersten `set_attempt(1, 10)`?
Worker startet mit kleiner Verzögerung (Thread-Schedule), Modal ist
sofort sichtbar. **V2-Antwort:** Initial-Label-Text "Verbindungsaufbau
läuft...". Wird beim ersten Callback überschrieben mit "Versuch 1 von 10".

### L8. **Race: Connect schneller als `exec()`**

V1-Stolperstein S8: was wenn `connected` feuert bevor Modal sichtbar?
**V2-Antwort:** `connected.connect(dialog.accept)` VOR `exec()` aufbauen.
Qt-Verhalten: `accept()` vor `exec()` aufgerufen → `exec()` returned
sofort mit `Accepted`. Verifiziert in Qt-Doku (`QDialog::done`).

Connect-Reihenfolge muss daher zwingend sein:

```python
self._connect_dialog = ConnectStatusDialog(self)
self.radio.connected.connect(
    self._connect_dialog.accept, Qt.QueuedConnection
)
threading.Thread(target=self._connect_worker, daemon=True).start()
result = self._connect_dialog.exec()
```

### L9. **`_connect_dialog` Lifecycle + Disconnect**

V1-Lücke: was passiert mit der Signal-Connection wenn Dialog destroyed?
**V2-Antwort:** Bei Dialog-Destroy disconnectet Qt automatisch. ABER:
Wenn `radio.connected` mehrmals feuern könnte (unwahrscheinlich aber
defensive), würde `accept()` auf gelöschtem Dialog crashen. Daher
explizit disconnecten nach `exec()`:

```python
result = self._connect_dialog.exec()
try:
    self.radio.connected.disconnect(self._connect_dialog.accept)
except (TypeError, RuntimeError):
    pass  # bereits disconnected oder Dialog tot
self._connect_dialog = None
```

### L10. **Failed-State Trigger**

V1-Stolperstein S7: was wenn alle 10 Versuche scheitern, aber Modal
offen ist? **V2-Plan:** `_connect_worker` ruft nach `auto_connect`-Fail
explizit `set_failed()` auf Dialog (via Signal). Modal-Text wechselt zu
"Verbindung fehlgeschlagen — Radio aus oder nicht erreichbar". Spinner-
Animation stoppt (Timer-stop). Buttons bleiben aktiv.

```python
# Dialog:
failed_signal = Signal()
self.failed_signal.connect(self.set_failed)

def set_failed(self):
    self._failed = True
    self._tick_timer.stop()
    self._spinner_label.setText("✗")  # rotes X
    self._spinner_label.setStyleSheet("color: #c44;")
    self._attempt_label.setText(
        "Verbindung fehlgeschlagen — Radio aus oder nicht erreichbar"
    )

# Worker:
ok = self.radio.auto_connect(...)
if not ok:
    self.control_panel.set_connection_status("disconnected")
    if self._connect_dialog is not None:
        self._connect_dialog.failed_signal.emit()
```

### L11. **Modal-Open im GUI-Thread, exec() blockierend**

V1-implizit: das funktioniert nur weil `_start_radio()` im GUI-Thread
läuft (`__init__` von MainWindow). **V2-explizit dokumentieren** in
Code-Comment + V3-AC. Kein anderer Aufrufer-Pfad zulässig.

### L12. **Tests: Smoke-Tests am Dialog, Integration via Mock-Self**

V1 hatte keine Test-Strategie. **V2:** zwei Test-Klassen:

1. `TestConnectStatusDialog` — Dialog-Klasse selbst-stehend testen
   (Smoke-Tests offscreen, T1-T7 aus V1)
2. `TestConnectWorkerCallback` — `_connect_worker` mit Mock-Radio
   testen ob `on_attempt` durchläuft und `set_failed` getriggert wird
   bei Fail (T8-T9)

Pattern aus `test_p22_preset_atomic.py` mit `qapp`-Fixture und
`os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`.

Erwartete Testanzahl: **8-9 Tests**, Bilanz 1056 → ~1064-1065.

### L13. **Reconnect-Pfad: KEIN Modal**

V1-AC A10. **V2 explizit verifiziert:** `_on_radio_disconnected`
(mw_radio.py:128) wird bei mid-Run-Disconnect gefeuert. Heute startet
es `_reconnect_worker` mit `reconnect_forever`. **V2-AC ergänzt:** in
diesem Pfad darf NIEMALS ein neuer ConnectStatusDialog geöffnet werden.
Reine Belt-and-Suspenders: ich öffne den Dialog ausschließlich im
`_start_radio()`-Pfad, nicht in `_on_radio_disconnected`.

### L14. **`_connect_dialog` als Attribut deklarieren**

V1 hat das implizit. **V2 explizit:** in `MainWindow.__init__` (oder
zumindest vor `_start_radio()`):

```python
self._connect_dialog: Optional[ConnectStatusDialog] = None
```

Damit `_connect_worker` safe darauf zugreifen kann.

## Aktualisierte Akzeptanzkriterien (V1-AC + V2-Ergänzungen)

A1-A12 aus V1 bleiben.

**A13 (V2-NEU):** `auto_connect` API erweitert um `on_attempt`-Optional-
Param. Bestehender Aufrufer in `mw_radio.py:82` bleibt funktional;
Tests in `test_modules.py:133+148` bleiben grün (kein direkter
auto_connect-Test vorhanden).

**A14 (V2-NEU):** `_connect_dialog` ist als `Optional[QDialog]`-Attribut
auf MainWindow deklariert. Initialisiert auf None, gesetzt in
`_start_radio()`, zurückgesetzt nach `exec()` returned.

**A15 (V2-NEU):** Failed-State stoppt Spinner-Timer, zeigt rotes X,
ändert Label. Buttons bleiben klickbar.

**A16 (V2-NEU):** Signal-Disconnect nach `exec()`-Return ist explizit
(try/except RuntimeError). Verhindert Use-after-Free wenn Worker mid-
Disconnect noch ein Signal sendet.

## Erweiterte Files-Liste

| Datei | LOC | Was |
|---|---|---|
| `ui/connect_status_dialog.py` | +130 | NEU (Dialog-Klasse mit Signals) |
| `ui/mw_radio.py` | ~+30 | Modal-Lifecycle in `_start_radio()` + Worker-Callback |
| `radio/flexradio.py` | ~+8 | `on_attempt`-Param in `auto_connect` |
| `tests/test_p26_connect_modal.py` | +220 | NEU (~9 Tests) |
| `main.py` | +1 | APP_VERSION 0.96.8 → 0.96.9 |

**Gesamt:** ~+389 LOC, davon 350 NEU (Dialog + Tests).

## Aktualisierte Tests (V2)

| T | Klasse | Was | Erwartung |
|---|---|---|---|
| T1 | Dialog | öffnen / Layout-Smoke | Title gesetzt, fixed size, WindowModal |
| T2 | Dialog | Spinner-Animation | nach 3× tick: "..." (3 Punkte) |
| T3 | Dialog | `set_attempt(3, 10)` | Label "Versuch 3 von 10" |
| T4 | Dialog | `set_failed()` | Spinner-Timer stop, "fehlgeschlagen" im Label |
| T5 | Dialog | "ohne Radio weiter" Click | `result == Rejected` |
| T6 | Dialog | "Beenden" Click | QApplication.quit Mock aufgerufen |
| T7 | Dialog | WindowModal (nicht App-Modal) | `windowModality() == WindowModal` |
| T8 | Worker | `on_attempt`-Callback | Dialog-Signal `attempt_changed.emit` aufgerufen |
| T9 | Worker | `auto_connect` Fail | Dialog-Signal `failed_signal.emit` aufgerufen |

## Stolpersteine die V3 (post-R1) noch klären muss

V2 → V3: was R1 wahrscheinlich findet:

- **Welche Atomic-Operations für Modal-Lifecycle**? (z.B. exec()-Reentrancy
  wenn `_start_radio` während eines schon offenen Dialogs nochmal
  gerufen wird — sollte nicht passieren, aber R1 würde fragen)
- **Test-Coverage für Race "Connect vor exec()"**? Pattern für Tests
  unklar — ggf. ergänzen.
- **Failed-State + erneut versuchen?** Nicht in V2 vorgesehen — Mike-Spec
  sagt nur Beenden/Weiter. R1 könnte vorschlagen "Erneut versuchen"-
  Button. → werde ich ablehnen wenn vorgeschlagen (Mike-Spec ist klar).
- **i18n**: Strings sind hardcoded deutsch. Konsistent mit Rest der App
  (kein i18n-Layer). R1-OK.
- **Logging**: heute kein structured Log für Modal-Events. Soll Modal-
  Open/Close in `simpleft8.log` landen? V3 entscheidet — vermutlich ja
  (analog `MessStatusDialog`-Pattern).
- **Backward-Compat**: alte `auto_connect`-Callers — keine außer dem
  einen in mw_radio.py. Tests grün halten.

## Offene Klärung VOR R1-Submission

Keine — V2 ist vollständig. R1 bekommt V2 als Plan-Kritik-Auftrag
(nicht das Problem lösen, nur den Plan kritisieren).
