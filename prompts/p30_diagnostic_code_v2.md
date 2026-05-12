# P30 Diagnose-Code V2 — Self-Review von V1

## Lücken in V1 die V2 schließt

### L1 — Hang-Detection-Timestamp wird nie zurückgesetzt
**V1-Problem:** `_diag_busy_started_at` wird nur gesetzt wenn
`_decode_busy=True`. Beim Reset auf False (Z.187, 201, 311) wird der
Timestamp NICHT zurückgesetzt → `busy_duration` würde nach erfolgreichem
Decode falsche Werte zeigen (Differenz zur letzten Busy-Set-Zeit).
**V2-Fix:** An allen 3 Stellen wo `_decode_busy=False` gesetzt wird
zusätzlich `_diag_busy_started_at = 0.0` (nur wenn `_p30_diag=True`).

### L2 — `threading.active_count()` fehlt (R1-Lücke #3)
R1 hat gewarnt: hängende `_process_cycle`-Threads halten temp Arrays
`audio_12k` (~720 KB) + `audio_work` (Kopie für Multi-Pass). Wenn 10
Threads hängen → 10 × ~2 MB = 20 MB akkumuliert.
**V2-AC7:** Im 60s-Sample zusätzlich `threading.active_count()` loggen.
Wenn > erwartet (Decoder=1 Loop + 1 ggf. _process_cycle + Qt + Audio
≈ 8-12) → Indikator für Thread-Lebewes-Stau.

### L3 — Prozess-RSS-Selbst-Sample fehlt
**V1-Lücke:** Memory-Watcher loggt RSS extern alle 60s, aber das ist
**zeitlich versetzt** zum Decoder-Sample. Direkt-Korrelation
„Buffer-Bytes ↔ RSS" wäre besser wenn beide Werte im **selben Atemzug**
gelogged werden.
**V2-AC8:** Im 60s-Sample zusätzlich:
```python
import resource
rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
# macOS: bytes, Linux: KB — Doku im Log
```
Loggt im selben `[P30-DIAG]`-Block → direkte Korrelation in einer Zeile.

### L4 — Code-Stellen sind ungefähre Angaben („Z.~80")
**V1-Problem:** AC sagt „Z.~80" / „Z.~148-150" → mehrdeutig für späteren
Code-Schritt.
**V2-Fix:** Exakte Zeilennummern aus aktuellem v0.97.7-Stand:
- `__init__` von Decoder beginnt bei Z.~50, `_audio_buffer_24k` ist
  Z.76 → DIAG-Felder direkt **nach Z.89** (`last_audio_24k` init) als
  geschlossener Block einfügen
- `feed_audio` Counter-Inkrement: **direkt vor Z.137**
  (`with self._buffer_lock:`)
- 60s-Sample: **vor Z.149** (`now = time.time()` im _decode_loop)
- Skip-Counter: **in Z.175-177**, nach `print("Skip Zyklus")`
- Busy-True-Timestamp: **direkt nach Z.178** (`self._decode_busy = True`)
- Busy-False-Reset: **direkt nach Z.187, 201, 311**

### L5 — Lock-Reihenfolge nicht explizit dokumentiert (Race-Risiko)
V1 hatte Risk-Tabelle aber keine Reihenfolge-Regel.
**V2-Regel:** `_diag_lock` ist STRIKT-INNEN. Wenn jemals beide Locks
genommen werden, dann **immer `_buffer_lock` zuerst, dann `_diag_lock`**.
Aktuell nehmen wir nie beide gleichzeitig (Diag-Schreibvorgänge sind
read-then-reset unter `_diag_lock` allein). Kommentar im Code dazu.

### L6 — Test T2 zu vage
V1 sagte „Smoke-Test mit Dummy feed_audio + 60s simuliert". Wie genau?
**V2-Test-Klärung:**
```python
def test_p30_diag_enabled(monkeypatch, capsys):
    monkeypatch.setenv("SIMPLEFT8_DECODER_DIAG", "1")
    d = Decoder()
    assert d._p30_diag is True
    # Feed Audio
    samples = np.zeros(2400, dtype=np.int16)
    d.feed_audio(samples)
    d.feed_audio(samples)
    # Manuell Sample triggern (ohne 60s warten)
    d._diag_last_sample_t = time.time() - 65  # zwingt sample
    # _decode_loop einen Tick ausführen — schwer, weil Endlos-Loop.
    # Stattdessen: Helper-Funktion `_emit_p30_sample()` extrahieren die
    # vom Loop aufgerufen wird → in Test direkt aufrufen.
```
→ **Refactor-Empfehlung:** 60s-Sample-Logik in separate Methode
`_emit_p30_sample()` extrahieren damit unit-testbar.

### L7 — Init muss `import os` haben — wo?
V1 hat `import os` im Init-Block. **V2 stellt klar:** `import os` an
Top-of-File, `import resource` nur wenn `_p30_diag=True` (lazy, weil
sonst Test-Overhead).

### L8 — `_p30_diag` wird in `__init__` einmal gesetzt — was wenn
Env nach App-Start gesetzt wird?
**V2-Klärung:** Env-Variable wird beim Decoder-Init gelesen. Wenn Mike
nach App-Start die Env setzt, muss er die App neu starten. Das ist OK
für Diagnose-Sprint (keine Live-Toggling nötig). Dokumentiert im
Init-Print: „Decoder-Diagnose AKTIV — Neustart nötig zum Deaktivieren".

### L9 — Was wenn `_p30_diag=True` UND Test-Suite läuft?
Test-Runs setzen normalerweise keine Env. Aber CI/manuelle Tests könnten
es. **V2:** Im T1 (default-AUS) explizit `monkeypatch.delenv` für
Sicherheit.

---

## Konsolidierte Akzeptanzkriterien V2 (alle V1 + 4 neue)

**AC1** — Buffer-Size-Sample (wie V1)
**AC2** — feed_audio Throughput (wie V1)
**AC3** — Skip-Counter (wie V1)
**AC4** — Hang-Detection (V1 erweitert um Timestamp-Reset)
**AC5** — Diagnose AUS-Default (wie V1)
**AC6** — Keine Verhaltens-Änderung wenn AUS (wie V1)
**AC7** *(NEU)* — `threading.active_count()` im 60s-Sample
**AC8** *(NEU)* — Prozess-RSS via `resource.getrusage` im 60s-Sample
**AC9** *(NEU)* — `_emit_p30_sample()` als separate Methode (unit-testbar)
**AC10** *(NEU)* — Lock-Reihenfolge-Kommentar im Code dokumentiert

---

## Aktualisiertes Log-Format

Eine **kompakte Block-Zeile** statt 3 Einzelzeilen, damit grep einfacher:
```
[P30-DIAG] @ HH:MM:SS | RSS=XXMb | buf_chunks=N buf_bytes=M | feed_calls=N samples=M B/s=K | skips_total=N last60=K | threads=N | busy_held=Xs
```

Beispiel:
```
[P30-DIAG] @ 14:25:00 | RSS=512MB | buf_chunks=4 buf_bytes=2880000 | feed_calls=600 samples=1440000 B/s=48000 | skips_total=0 last60=0 | threads=12 | busy_held=0s
```

Wenn `busy_held > 30s` → zusätzliche WARN-Zeile:
```
[P30-DIAG][WARN] busy_hang_detected duration=45s — Decoder hängt vermutlich in _process_cycle
```

---

## Risiko-Update (V1-Tabelle erweitert)

| Risiko | Wahrsch | Mitigation |
|---|---|---|
| Default-Pfad-Slowdown | LOW | 1 Boolean-Check pro Call |
| Race-Condition | LOW | Lock-Reihenfolge dokumentiert (AC10) |
| Log-Explosion | LOW | ~3 KB/Tag bei 60s-Intervall |
| Diagnose-Code triggert neuen Leak | NIEDRIG | Counter sind primitives, keine Listen |
| `resource.getrusage` macOS-Plattform-spezifisch | MITTEL | Doku im Log: macOS=bytes, Linux=KB; ggf. `* 1024` Korrektur |
| Test-Helper `_emit_p30_sample()` ändert App-Verhalten | LOW | Reine Refactor-Extraktion, identische Logik |

---

## Datei-Refs gegen v0.97.7 verifiziert

`core/decoder.py` Stand 12.05.2026 14:00 Uhr (Backup):
- Z.76: `self._audio_buffer_24k = []` ✓
- Z.77: `self._buffer_lock = threading.Lock()` ✓
- Z.82: `self.last_pcm_12k: np.ndarray | None = None` ✓
- Z.89: `self.last_audio_24k: np.ndarray | None = None` ✓
- Z.129: `def feed_audio(self, samples_int16):` ✓
- Z.137-138: `with self._buffer_lock: ... .append()` ✓
- Z.144: `self._decode_busy = False` (Init im _decode_loop) ✓
- Z.174-178: Skip-Pfad ✓
- Z.180-182: Buffer-Leerung ✓
- Z.187: `_decode_busy = False` (kein Audio) ✓
- Z.201: `_decode_busy = False` (Exception) ✓
- Z.311: `_decode_busy = False` (finally _process_cycle) ✓

---

## Was V2 noch NICHT klärt (für R1)

1. Soll `_diag_busy_started_at` auch beim **App-Init** auf `0.0` gesetzt
   sein? V1 hat das, aber V2 stellt klar warum: Floor-Wert beim ersten
   echten `_decode_busy=True`.
2. `import resource` auf Windows funktioniert nicht (Linux/macOS only).
   SimpleFT8 läuft aber nur auf macOS aktuell → irrelevant?
3. `psutil` als Alternative für RSS — schaut sauberer aus, ist es in
   venv? **R1 bitte einen Blick darauf werfen.**
4. **Wichtigste Frage**: Reichen diese 4 Messpunkte um den Bug zu
   beweisen? Oder fehlt was Entscheidendes?
