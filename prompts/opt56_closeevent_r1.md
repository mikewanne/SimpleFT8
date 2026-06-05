# R1-Review: OPT-56 — closeEvent robuster (audio_monitor-except eingrenzen + dx_tuning-Check)

DeepSeek-v4-pro als R1-Reviewer. Projekt **SimpleFT8** (Hobby-Funker, PySide6/macOS).
**Optimierungs-Kampagne: KISS/Robustheit > Speed, NUR Optimierung, KEINE
Verhaltensänderung.** ⛔ Hardware-Regel: ANT1=TX immer, ANT2=nur RX. Diesen Pfad
NICHT verändern.

## Audit-Befund R8 (war „⚠️ plausibel" = unverifiziert)
> closeEvent: (a) `dx_tuning`-Modus beim Schließen nicht zurückgesetzt;
> (b) broad `except: pass` um `audio_monitor.stop()`.

## Meine Verifikation (verify-don't-assume)

**closeEvent (`ui/main_window.py`):**
```python
def closeEvent(self, event):
    try:
        self._audio_monitor.stop()
    except Exception:          # (b) — zu breit
        pass
    ...
    self.timer.stop()
    if self._rx_mode == "diversity":      # (a) — nur diversity, nicht dx_tuning
        self._apply_normal_mode()
    self.radio.abort_reconnect()
    ...
    self.decoder.stop()
    self.radio.disconnect()               # kappt ALLE Radio-Slices/Streams hart
    ...                                    # (locator_db/rx_history/settings save je
                                           #  mit except OSError — konkret!)
    event.accept()
```

**`core/audio_monitor.py:stop()` — bereits intern robust:**
```python
def stop(self):
    """Stream stoppen + schliessen. Robust, idempotent."""
    self.active = False
    stream, self._stream = self._stream, None
    if stream is not None:
        try:
            stream.stop(); stream.close()
        except Exception:      # PortAudio-Fehler werden HIER schon geschluckt
            pass
```

**Befund (a) = Nicht-Fund:** der `_dx_tune_dialog` wird mit **`parent=self`**
konstruiert (`_open_dx_tune_dialog`) → Qt schließt/zerstört ihn beim App-Close
automatisch über die Parent-Child-Kaskade. `_rx_mode == "dx_tuning"` + der
Gain-Mess-Lock sind **reiner Laufzeit-State** (nicht persistiert — selbst band/mode
werden nicht gespeichert), beim nächsten Start frisch. `radio.disconnect()` kappt
ohnehin alle Slices/Streams. Der `_apply_normal_mode()`-Aufruf bei `diversity`
sendet ein sauberes Slice-B-Disable ans Radio VOR disconnect; die Einmessung
hinterlässt kein vergleichbares dauerhaftes HW-Setup. → **kein sinnvoller Fix-
Bedarf, kein persistenter Reststate.**

**Befund (b):** `audio_monitor.stop()` fängt seine PortAudio-Fehler **intern**
schon → der äußere `except Exception: pass` ist redundant UND verschluckt echte
Bugs (z.B. AttributeError). Der restliche closeEvent fängt überall KONKRETE
Exceptions. **Fix V1:** auf konkrete Exceptions eingrenzen, konsistent mit dem Rest:
```python
    try:
        self._audio_monitor.stop()
    except (RuntimeError, OSError):   # konkret, wie der restliche closeEvent;
        pass                          # stop() schluckt PortAudio bereits intern
```

## Fragen
1. **(a) wirklich ein Nicht-Fund?** Übersehe ich einen persistenten Reststate
   oder ein Hardware-Cleanup, das bei `dx_tuning` (anders als `diversity`) VOR
   `disconnect()` nötig wäre? (Ich will hier KEINEN TX-Pfad anfassen — OPT-59 ist
   Mike-gesperrt.)
2. **(b):** `except (RuntimeError, OSError)` die richtige Eingrenzung, oder
   anderer/zusätzlicher Typ? Oder den äußeren try/except ganz weglassen (stop()
   ist schon robust)? closeEvent darf NIE crashen — was ist robuster?
3. KISS-Urteil: OPT-56 = nur (b) umsetzen + (a) als dokumentierter Nicht-Fund —
   richtig, oder gibt es bei (a) doch etwas Sinnvolles?

Knapp, pro Punkt + Verdikt **GO** / **ÜBERARBEITEN**.
