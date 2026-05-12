# P30 Diagnose-Code V1 — Decoder-Instrumentierung für RAM-Leak-Beweis

## Auftrag

In `core/decoder.py` Mess-Prints einbauen die R1's 4 Diagnose-Punkte
abdecken. Default AUS (null Overhead), per Env-Variable
`SIMPLEFT8_DECODER_DIAG=1` aktivierbar. Ausgabe in vorhandenes
debug-Log mit Prefix `[P30-DIAG]`.

## Kontext

- Mike-Beobachtung 12.05.: Python-RSS 1,79 GB → 5,96 GB / 7h50min ≈
  540 MB/h. 124 GB nach ~10 Tagen → App-Freeze.
- R1-bestätigter Hauptverdacht: `core/decoder.py` Z.174-188 Skip-Pfad
  leert `_audio_buffer_24k` nicht.
- R1-Lücken: Math passt nur bedingt (Faktor 3 zu niedrig), Diversity-
  Datenpfad unklar (Stereo vs 2 Calls?), Qt-Event-Queue + hängende
  Threads nicht ausgeschlossen.
- Memory-Watcher-Daemon läuft (`tools/memory_watcher.py` PID 72060),
  loggt RSS + Modus alle 60s nach `~/.simpleft8/memory_watch.log`.
- Backup: `Appsicherungen/2026-05-12_v0.97.7_vor_p30_diagnostic_code/`

## Akzeptanzkriterien

**AC1 — Buffer-Size-Sample:** Alle 60s wird in debug_log geschrieben:
```
[P30-DIAG] buffer_24k: chunks=N total_bytes=M (bytes/min=K, RSS_proxy=...)
```
- N = `len(_audio_buffer_24k)`
- M = `sum(len(c) for c in _audio_buffer_24k) * 2` (int16 = 2 Bytes)
- K = Delta seit letztem Sample

**AC2 — `feed_audio` Throughput-Tracking:** Counter für eingehende
Bytes/Sample-Count. Alle 60s 1× zusammengefasst:
```
[P30-DIAG] feed_audio: calls=N samples=M bytes/sec=K (last_chunk_shape=...)
```
- Klärt Diversity-Frage: Wenn bytes/sec ≈ 96 KB/s → Stereo/2-Antennen;
  wenn ≈ 48 KB/s → Mono/1-Antenne.

**AC3 — Skip-Counter:** Jeder `Skip Zyklus` zählt + alle 60s 1×
Zusammenfassung:
```
[P30-DIAG] skips: total=N last_60s=K reason="busy"
```

**AC4 — `_decode_busy` Hang-Detection:** Wenn `_decode_busy=True`
länger als 30s anliegt, logge:
```
[P30-DIAG] busy_hang: duration=Xs (Decoder hängt? Watchdog-Kandidat)
```
- Zeitstempel wann `_decode_busy=True` gesetzt wurde merken
- Bei jedem Skip prüfen ob Hang-Schwelle (30s) überschritten

**AC5 — Diagnose AUS-Default:**
- Env-Variable `SIMPLEFT8_DECODER_DIAG=1` aktiviert alle 4 Messpunkte
- Default (Env nicht gesetzt): 0 Overhead, kein zusätzliches Logging
- Check 1× am Init des Decoders → boolean `_p30_diag` als Class-State

**AC6 — Keine Verhaltens-Änderung wenn AUS:**
- Tests müssen alle 1148 grün bleiben
- Keine neuen Locks/Threads für Diagnose
- Keine Verzögerung in `feed_audio` oder `_decode_loop`

## Konkrete Code-Stellen (Refs gegen aktuellen Stand verifiziert)

| Stelle | Datei:Zeile | Was |
|---|---|---|
| Init `_p30_diag` Flag | `core/decoder.py` `__init__` (Z.~80) | Env-Check + Counter-Felder |
| `feed_audio` Counter | `core/decoder.py:129-138` | Bytes/Calls inkrementieren |
| Buffer-Size-Sample | `core/decoder.py` `_decode_loop` (Z.~148-150) | Periodisch alle 60s loggen |
| Skip-Counter | `core/decoder.py:175-177` | Counter + Hang-Check |
| Hang-Detection | `core/decoder.py` Stelle wo `_decode_busy=True` gesetzt wird | Timestamp speichern |

## Implementierungs-Skizze

```python
# In __init__:
import os
self._p30_diag = os.environ.get("SIMPLEFT8_DECODER_DIAG") == "1"
self._diag_lock = threading.Lock()
self._diag_feed_calls = 0
self._diag_feed_samples = 0
self._diag_skips_total = 0
self._diag_skips_last_window = 0
self._diag_busy_started_at = 0.0
self._diag_last_sample_t = time.time()
self._diag_last_feed_bytes = 0
if self._p30_diag:
    print("[P30-DIAG] Decoder-Diagnose AKTIV (SIMPLEFT8_DECODER_DIAG=1)")

# In feed_audio() — nur wenn _p30_diag:
if self._p30_diag:
    with self._diag_lock:
        self._diag_feed_calls += 1
        self._diag_feed_samples += len(samples_int16)

# Im _decode_loop (vor time.sleep(wait)) — alle 60s Sample:
if self._p30_diag and (now - self._diag_last_sample_t) >= 60.0:
    with self._buffer_lock:
        n_chunks = len(self._audio_buffer_24k)
        total_bytes = sum(c.nbytes for c in self._audio_buffer_24k)
    with self._diag_lock:
        calls = self._diag_feed_calls
        samples = self._diag_feed_samples
        skips = self._diag_skips_last_window
        skips_total = self._diag_skips_total
        self._diag_feed_calls = 0
        self._diag_feed_samples = 0
        self._diag_skips_last_window = 0
    elapsed = now - self._diag_last_sample_t
    bytes_per_sec = (samples * 2) / elapsed if elapsed > 0 else 0
    print(f"[P30-DIAG] buffer_24k: chunks={n_chunks} total_bytes={total_bytes}")
    print(f"[P30-DIAG] feed_audio: calls={calls} samples={samples} "
          f"bytes/sec={bytes_per_sec:.0f}")
    print(f"[P30-DIAG] skips: total={skips_total} last_60s={skips}")
    self._diag_last_sample_t = now

# Im Skip-Pfad (Z.175-177) — wenn _p30_diag:
if self._p30_diag:
    with self._diag_lock:
        self._diag_skips_total += 1
        self._diag_skips_last_window += 1
    busy_duration = now - self._diag_busy_started_at
    if busy_duration > 30.0:
        print(f"[P30-DIAG] busy_hang: duration={busy_duration:.0f}s")

# Wo _decode_busy=True gesetzt wird (Z.178) — wenn _p30_diag:
if self._p30_diag:
    self._diag_busy_started_at = now
```

## Akzeptanz-Kriterien für Tests

**Test T1:** `SIMPLEFT8_DECODER_DIAG=0` (default) → Decoder verhält sich
identisch zum Backup-Stand. Tests 1148 bleiben grün.

**Test T2:** `SIMPLEFT8_DECODER_DIAG=1` + Smoke-Test (Decoder-Init +
Dummy feed_audio + Decode-Loop 60s simuliert) → Log-Zeilen mit
`[P30-DIAG]` erscheinen. **NEU** als `tests/test_p30_diagnostic_code.py`.

**Test T3:** Counters atomar (Lock korrekt) — kein Race zwischen
`feed_audio` (VITA-49-Thread) und `_decode_loop` (Decoder-Thread).

## Was NICHT in diesem V1

- **KEIN Fix** für `_audio_buffer_24k`-Leak (das kommt in P30.FIX
  nachdem Daten da sind)
- **KEINE Watchdog-Implementierung** (auch erst beim Fix)
- **KEIN App-UI** (Settings-Toggle) — Env-Variable reicht für
  Diagnose-Sprint
- **KEINE Änderungen außerhalb `core/decoder.py`** (außer Test)

## Risiko-Bewertung

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| Default-Pfad verlangsamt (1148 Tests rot) | LOW | `_p30_diag` Check ist 1 Boolean-Vergleich; nur wenn True wird inkrementiert |
| Race-Condition Diagnose-Lock vs Buffer-Lock | LOW | Locks immer in fester Reihenfolge: `_diag_lock` zuletzt nach `_buffer_lock` (oder allein) |
| Print zu viel → log-Datei explodiert | LOW | Nur 1× pro 60s = 3 Zeilen/Min × 24h = 4320 Zeilen/Tag ≈ 200 KB |
| Diagnose-Code triggert anderen Leak | NIEDRIG | Counter sind primitive int/float; keine Listen/Arrays |

## Compact-Festigkeit

Alle Datei-Pfade absolut, alle Code-Stellen mit Zeilennummern
verifiziert gegen aktuellen Stand `core/decoder.py` v0.97.7.
Backup-Pfad dokumentiert. Diese V1 ist allein-lauffähig.

---

## Offene Fragen für V2/R1

1. Sollen wir zusätzlich **`audio_12k` + `audio_work` Temporär-Arrays**
   loggen (R1-Hinweis hängende Threads)?
2. Soll **Qt-Event-Queue-Tiefe** mitgeloggt werden? (Wie? `QApplication.
   instance().eventDispatcher().processEvents` nicht trivial.)
3. **ft8lib-interner Speicher** — überhaupt prüfbar von Python aus?
   Vermutlich nein (C-Lib).
4. Format `bytes/sec` als float oder int? (Spielt für grep keine Rolle.)
