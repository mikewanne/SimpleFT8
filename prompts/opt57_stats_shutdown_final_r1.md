# Final-R1 (Bestätigungs-Pass): OPT-57 station_stats sauberer Stop — fertiger Diff

DeepSeek-v4-pro Final-R1. Plan-R1 war **GO** (Sentinel-Pattern), mit einer Auflage
(join-Timeout). Code ist geschrieben, **2438 Tests grün** (+4 neu). Bestätige oder
benenne Blocker.

## Was sich ggü. Plan-R1 geändert hat
Du rietest, den join-Timeout von 2 s auf 6–7 s zu erhöhen, weil der Writer „bis zu
5 s im `get(timeout=5)` hängen" könne. **Ich habe das kritisch geprüft:** `queue.put()`
weckt einen wartenden `get()` sofort (Condition-Variable), und ein `get()` auf eine
nicht-leere Queue kehrt sofort zurück — der Sentinel wird also praktisch sofort
verarbeitet (nur Dauer eines laufenden `_write_entry`, ~ms), NICHT nach 5 s. Der echte
Hang-Fall ist ein langsamer Disk-Write, nicht das `get`. Ich habe den Timeout
trotzdem konservativ auf **`5.0 s`** gesetzt (großzügiger Drain-Puffer, begrenzter
Close-Hang) — mit korrekter Begründung im Docstring. Stimmt diese Analyse?

## Fertiger Diff

```python
# core/station_stats.py — Modul-Konstante:
_SHUTDOWN = object()   # Sentinel, FIFO-Drain-Garantie

# _writer_loop — nur ein Break-Check ergänzt (get(timeout=5) unverändert):
            entry = self._queue.get(timeout=5)   # (in try/except queue.Empty)
            ...
            if entry is _SHUTDOWN:
                break
            try:
                self._write_entry(entry)
            except Exception as e:
                print(f"[Stats] Schreibfehler: {e}")

    def shutdown(self, timeout: float = 5.0):
        try:
            self._queue.put(_SHUTDOWN, timeout=1.0)
        except queue.Full:
            pass   # 1s voll → Daemon-Kill (Best-Effort)
        self._thread.join(timeout=timeout)

# ui/main_window.py closeEvent (am Ende, nach timer.stop()+decoder.stop()+
# radio.disconnect()+settings.save(), vor event.accept()):
        stats = getattr(self, "_stats_logger", None)
        if stats is not None:
            stats.shutdown()
        event.accept()
```

## Tests (4 neu, `tests/test_stats_shutdown.py`)
- `test_shutdown_drains_queue`: 25 log_cycle → shutdown() → genau 25 Datenzeilen
  geschrieben + Thread tot (Mutationsbeweis für die Drain-Garantie)
- `test_shutdown_stops_thread`: Thread nach shutdown() nicht mehr alive
- `test_shutdown_idempotent`: 2× shutdown() kein Crash
- `test_sentinel_breaks_only_on_identity`: `object() is not _SHUTDOWN`, normaler
  Eintrag läuft durch

## Prüfpunkte
1. join-Timeout-Analyse oben korrekt (get hängt NICHT 5s; 5.0 ausreichend)?
2. Sentinel-Identitätsprüfung (`is`) race-frei, kein Verhaltensänderung im Laufbetrieb?
3. closeEvent-Platzierung + getattr-Guard korrekt?
4. Idempotenz (2× shutdown) wirklich No-op (join auf toten Thread)?
5. Übersehene Race / Regression?

Knapp, pro Punkt + **PUSH FREIGEBEN** / **NICHT FREIGEBEN (Grund)**.
