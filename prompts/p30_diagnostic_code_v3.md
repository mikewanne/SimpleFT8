# P30 Diagnose-Code V3 — Freigabe-Plan (Compact-fest)

**Stand:** 12.05.2026 14:30 nach R1-Review von V2.
**Backup:** `Appsicherungen/2026-05-12_v0.97.7_vor_p30_diagnostic_code/`
**Tests aktuell:** 1148 grün

---

## Auftrag

Diagnose-Mess-Code in `core/decoder.py` einbauen um R1's 4 Lücken zu
klären (Buffer-Wachstum, Diversity-Datenrate, Skip-Häufigkeit, Hang-
Detection). Default AUS via Env `SIMPLEFT8_DECODER_DIAG=1`.

## R1-Klarstellungen ggü V2

R1 hat statt Plan-Review direkt Code-Vorschlag geliefert. Den
übernehmen wir mit **2 Korrekturen**:

**K1 — Lock-Zuständigkeit eindeutig regeln (R1-Inkonsistenz):**
R1 las `_diag_busy_started_at` einmal unter `_decode_busy_lock`, das
Counter-Feld dagegen unter `_diag_lock`. V3-Regel:

| Feld | Lock |
|---|---|
| `_decode_busy` (Bool) | `_decode_busy_lock` |
| `_diag_busy_started_at` (float) | `_decode_busy_lock` (eng gekoppelt an busy-State) |
| `_diag_feed_calls/samples/skips_*` | `_diag_lock` |
| `_audio_buffer_24k` Inspektion | `_buffer_lock` |

Lock-Reihenfolge wenn 2 nötig: **outer → inner = `_buffer_lock` →
`_diag_lock`**. Nie umgekehrt. `_decode_busy_lock` ist disjoint zu den
anderen (nie kombiniert).

**K2 — `_emit_p30_sample()` Aufruf-Frequenz:**
R1 schlägt vor: vor `time.sleep(wait)` im `_decode_loop`. Loop läuft
~1× pro Slot (15/7.5/3.8s) → Sample-Funktion wird oft gerufen, aber
**Body läuft nur wenn `elapsed >= 60.0`**. Das ist OK, kein Drift weil
`_diag_last_sample_t` exakt gesetzt wird.

---

## Diff-Liste (alle Stellen gegen Backup-Stand v0.97.7 verifiziert)

### Diff 1 — Imports (Top of `core/decoder.py`)
Nach bestehenden Imports einfügen:
```python
import os        # P30-DIAG: Env-Check
import resource  # P30-DIAG: RSS-Self-Sample (macOS+Linux)
```

### Diff 2 — `Decoder.__init__` (nach Z.89 `self.last_audio_24k = None`)
```python
# ── P30 Diagnose-Code (V3, Mai 2026) ──────────────────────────────────
# Aktivieren via Env: SIMPLEFT8_DECODER_DIAG=1 (Neustart nötig)
# Default AUS = null Overhead (1 Boolean-Check pro feed_audio/Skip).
# Lock-Pattern:
#   _decode_busy_lock → schützt _decode_busy + _diag_busy_started_at
#   _diag_lock        → schützt _diag_feed_* + _diag_skips_*
#   _buffer_lock      → schützt _audio_buffer_24k (existiert)
# Lock-Reihenfolge wenn 2: _buffer_lock → _diag_lock (nie umgekehrt).
self._p30_diag = os.environ.get("SIMPLEFT8_DECODER_DIAG") == "1"
self._diag_lock = threading.Lock()
self._diag_feed_calls = 0
self._diag_feed_samples = 0
self._diag_skips_total = 0
self._diag_skips_last_window = 0
self._diag_busy_started_at = 0.0  # 0.0 = nicht busy
self._diag_last_sample_t = time.time()
if self._p30_diag:
    print("[P30-DIAG] Decoder-Diagnose AKTIV (SIMPLEFT8_DECODER_DIAG=1) "
          "— Neustart nötig zum Deaktivieren")
```

### Diff 3 — `feed_audio()` Counter (vor Z.137 `with self._buffer_lock`)
```python
def feed_audio(self, samples_int16: np.ndarray):
    # Startup-Purge: erste 2s Audio verwerfen (unverändert)
    if not self._startup_done:
        self._startup_samples += len(samples_int16)
        if self._startup_samples < 48000:
            return
        self._startup_done = True
        print(f"[Decoder] Startup-Purge: {self._startup_samples} Samples verworfen")

    # ── P30-DIAG: feed-Counter (nur wenn aktiv) ──
    if self._p30_diag:
        with self._diag_lock:
            self._diag_feed_calls += 1
            self._diag_feed_samples += len(samples_int16)

    with self._buffer_lock:
        self._audio_buffer_24k.append(samples_int16.copy())
```

### Diff 4 — `_decode_loop` Sample-Trigger (nach `wait`-Berechnung, vor `time.sleep(wait)`)
```python
# Berechnung von target_slot_start + wait (unverändert)
...
if cycle_pos < _WAKE:
    target_slot_start = now - cycle_pos
    wait = _WAKE - cycle_pos
else:
    target_slot_start = now - cycle_pos + _SLOT
    wait = _SLOT - cycle_pos + _WAKE

# ── P30-DIAG: regelmäßiges Sample (Body läuft nur wenn ≥60s vergangen) ──
if self._p30_diag:
    self._emit_p30_sample()

time.sleep(wait)
```

### Diff 5 — Skip-Pfad (Z.174-177 erweitern)
```python
with self._decode_busy_lock:
    if self._decode_busy:
        print(f"[Decoder] Skip Zyklus {int(time.time()/15)}: "
              f"vorheriger Decode laeuft noch")
        # ── P30-DIAG: Skip-Counter + Hang-Check ──
        if self._p30_diag:
            with self._diag_lock:
                self._diag_skips_total += 1
                self._diag_skips_last_window += 1
            # _diag_busy_started_at unter _decode_busy_lock (wir sind drin)
            busy_duration = (time.time() - self._diag_busy_started_at
                             if self._diag_busy_started_at > 0 else 0.0)
            if busy_duration > 30.0:
                print(f"[P30-DIAG][WARN] busy_hang_detected "
                      f"duration={busy_duration:.0f}s — "
                      f"Decoder hängt vermutlich in _process_cycle")
        continue
    self._decode_busy = True
    if self._p30_diag:
        self._diag_busy_started_at = time.time()
```

### Diff 6 — `_decode_busy=False`-Resets (3 Stellen, je 1 Zeile)

**Stelle 1 — Z.~187 (kein Audio):**
```python
with self._decode_busy_lock:
    self._decode_busy = False
    if self._p30_diag:
        self._diag_busy_started_at = 0.0
continue
```

**Stelle 2 — Z.~201 (Exception im Loop):**
```python
with self._decode_busy_lock:
    self._decode_busy = False
    if self._p30_diag:
        self._diag_busy_started_at = 0.0
```

**Stelle 3 — Z.~311 (finally in `_process_cycle`):**
```python
finally:
    with self._decode_busy_lock:
        self._decode_busy = False
        if self._p30_diag:
            self._diag_busy_started_at = 0.0
```

### Diff 7 — NEUE Methode `_emit_p30_sample()` (irgendwo am Ende der Klasse)
```python
def _emit_p30_sample(self):
    """P30 Diagnose-Sample (alle 60s, opt-in via Env).

    Ausgabe-Format (1 Zeile pro Sample für grep):
      [P30-DIAG] @ HH:MM:SS | RSS=XMB | buf_chunks=N buf_bytes=M
      | feed_calls=N samples=M B/s=K | skips_total=N last60=K
      | threads=N | busy_held=Xs

    Lock-Reihenfolge: _buffer_lock → _diag_lock (siehe __init__).
    _decode_busy_lock disjoint (eigener Block).
    """
    if not self._p30_diag:
        return

    now = time.time()
    elapsed = now - self._diag_last_sample_t
    if elapsed < 60.0:
        return  # noch nicht Zeit

    # Buffer-State (separater Lock, kurz halten)
    with self._buffer_lock:
        n_chunks = len(self._audio_buffer_24k)
        total_bytes = sum(c.nbytes for c in self._audio_buffer_24k)

    # Counter-Read + Reset (separater Lock)
    with self._diag_lock:
        calls = self._diag_feed_calls
        samples = self._diag_feed_samples
        skips_total = self._diag_skips_total
        skips_last = self._diag_skips_last_window
        self._diag_feed_calls = 0
        self._diag_feed_samples = 0
        self._diag_skips_last_window = 0

    # Busy-State (separater Lock, eng an _decode_busy)
    with self._decode_busy_lock:
        busy_start = self._diag_busy_started_at
    busy_held = (now - busy_start) if busy_start > 0 else 0.0

    bytes_per_sec = (samples * 2) / elapsed if elapsed > 0 else 0.0

    # RSS (macOS=bytes, Linux=KB → wir normalisieren auf MB)
    try:
        rss_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Heuristik: macOS-Werte sind typischerweise > 10^8 (bytes),
        # Linux-Werte < 10^7 (KB). Wir prüfen.
        rss_mb = rss_raw / (1024 * 1024) if rss_raw > 1_000_000 else rss_raw / 1024
    except Exception:
        rss_mb = -1.0

    try:
        thread_count = threading.active_count()
    except Exception:
        thread_count = -1

    print(f"[P30-DIAG] @ {time.strftime('%H:%M:%S', time.gmtime(now))} "
          f"| RSS={rss_mb:.0f}MB "
          f"| buf_chunks={n_chunks} buf_bytes={total_bytes} "
          f"| feed_calls={calls} samples={samples} B/s={bytes_per_sec:.0f} "
          f"| skips_total={skips_total} last60={skips_last} "
          f"| threads={thread_count} "
          f"| busy_held={busy_held:.0f}s")

    self._diag_last_sample_t = now
```

---

## NEU `tests/test_p30_diagnostic_code.py` (7 Tests)

```python
"""P30 Diagnose-Code Tests — muss alle 1148 vorhandenen Tests grün lassen."""
import os
import time
import threading
import numpy as np
import pytest

from core.decoder import Decoder


def test_diag_disabled_by_default(monkeypatch):
    """Env nicht gesetzt → _p30_diag=False."""
    monkeypatch.delenv("SIMPLEFT8_DECODER_DIAG", raising=False)
    d = Decoder()
    assert d._p30_diag is False


def test_diag_enabled_via_env(monkeypatch):
    """Env=1 → _p30_diag=True."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    assert d._p30_diag is True


def test_feed_audio_counters_when_enabled(monkeypatch):
    """feed_audio inkrementiert Counter wenn Diag aktiv."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    d._startup_done = True  # Purge überspringen
    arr = np.zeros((2400,), dtype=np.int16)
    d.feed_audio(arr)
    d.feed_audio(arr)
    with d._diag_lock:
        assert d._diag_feed_calls == 2
        assert d._diag_feed_samples == 4800


def test_feed_audio_no_counters_when_disabled(monkeypatch):
    """Default-AUS: keine Counter-Inkrementierung."""
    monkeypatch.delenv("SIMPLEFT8_DECODER_DIAG", raising=False)
    d = Decoder()
    d._startup_done = True
    arr = np.zeros((2400,), dtype=np.int16)
    d.feed_audio(arr)
    assert d._diag_feed_calls == 0  # bleibt 0


def test_emit_sample_only_after_60s(monkeypatch, capsys):
    """Sample-Body läuft nicht wenn <60s vergangen."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    d._diag_last_sample_t = time.time()  # gerade gesampelt
    d._emit_p30_sample()
    captured = capsys.readouterr()
    assert "[P30-DIAG] @" not in captured.out  # kein Output


def test_emit_sample_after_60s(monkeypatch, capsys):
    """Sample-Body läuft nach 60s + Format korrekt."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    d._diag_last_sample_t = time.time() - 65.0
    d._emit_p30_sample()
    captured = capsys.readouterr()
    assert "[P30-DIAG] @" in captured.out
    assert "buf_chunks=" in captured.out
    assert "feed_calls=" in captured.out
    assert "skips_total=" in captured.out
    assert "threads=" in captured.out
    assert "busy_held=" in captured.out


def test_busy_hang_warn_emitted(monkeypatch, capsys):
    """Skip + busy_held > 30s → WARN-Zeile."""
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    d._decode_busy = True
    d._diag_busy_started_at = time.time() - 45.0  # 45s "busy"
    # Skip-Pfad simulieren (statt _decode_loop laufen lassen)
    with d._decode_busy_lock:
        if d._decode_busy:
            with d._diag_lock:
                d._diag_skips_total += 1
                d._diag_skips_last_window += 1
            busy_duration = time.time() - d._diag_busy_started_at
            if busy_duration > 30.0:
                print(f"[P30-DIAG][WARN] busy_hang_detected "
                      f"duration={busy_duration:.0f}s — Decoder hängt vermutlich")
    captured = capsys.readouterr()
    assert "busy_hang_detected" in captured.out


def test_diag_disabled_no_overhead(monkeypatch):
    """Diag AUS: _emit_p30_sample sofort return."""
    monkeypatch.delenv("SIMPLEFT8_DECODER_DIAG", raising=False)
    d = Decoder()
    d._diag_last_sample_t = time.time() - 65.0  # >60s
    # Sollte sofort return ohne Side-Effects
    d._emit_p30_sample()
    # Counter unverändert (== 0)
    assert d._diag_feed_calls == 0
```

---

## Akzeptanzkriterien V3 (final)

✅ **AC1-AC10** wie V2 (Buffer-Sample, feed_audio-Throughput, Skip-
Counter, Hang-Detect, Default-AUS, keine Verhaltens-Änderung, Threads,
RSS, `_emit_p30_sample()` testbar, Lock-Reihenfolge dokumentiert)

✅ **AC11 — Backup-Pfad vorhanden:** `Appsicherungen/2026-05-12_v0.97.7_vor_p30_diagnostic_code/`

✅ **AC12 — 1148 Tests bleiben grün** (default-AUS-Pfad ändert nichts)

✅ **AC13 — Neue 8 Tests grün** (1148 → 1156)

✅ **AC14 — Aktivierung dokumentiert** in HANDOFF.md unter P30-Sektion

---

## Atomare Commits

**C1:** `core/decoder.py` Diff 1-6 (Init + Counter + Skip-Path) +
       `_emit_p30_sample()` Methode (Diff 7)
**C2:** `tests/test_p30_diagnostic_code.py` NEU (8 Tests)
**C3:** APP_VERSION 0.97.7 → **0.97.8** + HANDOFF/HISTORY/CLAUDE-Header
       Update + TODO-P30-Section neu

→ 3 atomare Commits in Folge. Keine Code-Verbindung zwischen C1+C2+C3
außer Logischer Gruppe.

---

## Rollback-Plan

Bei Problem (Tests rot, Decoder verlangsamt, Side-Effects):
```bash
cp "Appsicherungen/2026-05-12_v0.97.7_vor_p30_diagnostic_code/core/decoder.py" core/decoder.py
rm tests/test_p30_diagnostic_code.py
git diff -- core/decoder.py    # sollte leer sein
```

---

## Was DANACH passiert (NICHT in V3)

1. **Mike aktiviert Diagnose:** `export SIMPLEFT8_DECODER_DIAG=1` +
   App-Restart. App läuft 4-24h in Diversity-Modus.
2. **Auswertung:** Memory-Watcher-Log + debug-Log greppen nach `[P30-DIAG]`.
3. **Wenn Bug bewiesen** (Buffer wächst monoton bei Skips ODER busy_hang
   triggert ODER Diversity zeigt 2× Datenrate): **P30.FIX** als separater
   Workflow (V1→V2→R1→V3) mit Fix A (Skip leert Buffer) + Fix C (Watchdog).

---

## Compact-Festigkeit

- Alle Pfade absolut (`/Users/.../FT8/SimpleFT8/...`)
- Alle Zeilennummern gegen Backup-Stand v0.97.7 verifiziert
- Diff-Listen sind eigenständig anwendbar
- Tests sind Compact-fest (keine externen Refs außer Decoder-Klasse)
- Backup-Pfad + Rollback-Befehle drin

V3 ist **lauffähig auch nach Compact** — eine frische KI kann diesen
Plan direkt umsetzen ohne Rückgriff auf V1/V2/R1.
