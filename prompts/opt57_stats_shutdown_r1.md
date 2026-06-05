# R1-Review: OPT-57 — station_stats Writer-Thread sauberer Stop

DeepSeek-v4-pro R1-Reviewer. **SimpleFT8**, Optimierungs-Kampagne: **KISS/Robustheit
> Speed, NUR Optimierung, keine Verhaltensänderung im Laufbetrieb.** Kein TX-Pfad.

## Befund (Audit R9, ✅ bestätigt)

`core/station_stats.py`: der Statistik-Writer ist ein **Daemon-Thread** mit
`while True` + `queue.get(timeout=5)`, **ohne Stop-Mechanismus**:
```python
def __init__(self, base_dir=None):
    ...
    self._queue = queue.Queue(maxsize=1000)
    self._thread = threading.Thread(target=self._writer_loop, daemon=True)
    self._thread.start()

def _writer_loop(self):
    while True:
        try:
            entry = self._queue.get(timeout=5)
        except queue.Empty:
            continue
        try:
            self._write_entry(entry)
        except Exception as e:
            print(f"[Stats] Schreibfehler: {e}")
```
Beim App-Close (`MainWindow.closeEvent`) wird er NICHT gestoppt → als Daemon beim
Interpreter-Exit hart gekillt. Noch in der Queue liegende Einträge gehen verloren
(„unvollständige Statistik bei abruptem Schließen"). Eine Instanz:
`self._stats_logger = StationStatsLogger()` (main_window.py:209). log_cycle/
log_station_comparisons/log_antenna_qso reihen non-blocking via `put_nowait` ein.

## V1-Plan — Sentinel-Pattern (meine Wahl, statt Audit-Vorschlag „Event")

```python
_SHUTDOWN = object()   # Modul-Konstante (Sentinel)

# _writer_loop: get(timeout=5) UNVERÄNDERT, nur ein Break-Check:
    while True:
        try:
            entry = self._queue.get(timeout=5)
        except queue.Empty:
            continue
        if entry is _SHUTDOWN:
            break                     # alle FIFO-davor liegenden Einträge sind
        try:                          # dann bereits geschrieben → sauberer Drain
            self._write_entry(entry)
        except Exception as e:
            print(f"[Stats] Schreibfehler: {e}")

def shutdown(self, timeout: float = 2.0):
    """Writer sauber stoppen: Sentinel einreihen (alle davor liegenden Einträge
    werden noch geschrieben), dann mit Timeout joinen. Timeout verhindert ein
    Hängen des App-Close, falls ein Write blockiert."""
    try:
        self._queue.put(_SHUTDOWN, timeout=1.0)
    except queue.Full:
        pass                          # 1s voll geblieben → Daemon-Kill (Best-Effort)
    self._thread.join(timeout=timeout)
```
**closeEvent (`ui/main_window.py`), am Ende vor `event.accept()`** (timer+decoder
sind dann gestoppt → keine neuen Einträge mehr):
```python
    stats = getattr(self, "_stats_logger", None)
    if stats is not None:
        stats.shutdown()
    event.accept()
```

**Begründung Sentinel statt Event:** Die FIFO-Queue gibt die Drain-Garantie
gratis — alle VOR `shutdown()` eingereihten Einträge liegen vor dem Sentinel und
werden geschrieben. Ein `Event` bräuchte zusätzlich einen separaten Drain-Loop
nach dem `while`, UND ein kürzeres `get`-Polling (sonst hängt der Loop bis zu 5 s
im `get` nach `event.set()`), was den `timeout=5` (bewusst selten-Wakeup) opfert.
Im Laufbetrieb ist die Änderung neutral: der Break-Check ist nur 1 `is`-Vergleich,
nie True im Normalbetrieb.

## Fragen
1. **Sentinel vs Event** — stimmst du zu, dass Sentinel hier KISS-richtiger ist
   (FIFO-Drain-Garantie, kein Polling-Opfer)? Oder hat Event einen Vorteil, den
   ich übersehe?
2. **`put(_SHUTDOWN, timeout=1.0)`** bei (sehr seltener) voller Queue: 1 s warten,
   dann Daemon-Kill-Fallback — vertretbar? Oder Sentinel garantiert einreihen?
3. **`join(timeout=2.0)`** — verhindert Hängen beim Close. Richtig dimensioniert?
   Falls join-Timeout abläuft (Write hängt), fällt's auf Daemon-Kill zurück — ok?
4. **closeEvent-Platzierung** am Ende (nach timer/decoder-stop) — korrekt, dass
   dann keine neuen Einträge mehr kommen?
5. **Race/Verhaltensänderung im Laufbetrieb** — irgendein Risiko? Übersehenes?

Knapp, pro Punkt + Verdikt **GO** / **ÜBERARBEITEN**.
