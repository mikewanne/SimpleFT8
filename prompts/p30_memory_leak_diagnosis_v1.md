# P30 — Memory-Leak Diagnose (Stand 12.05.2026, V1 für R1-Review)

## Auftrag an dich (DeepSeek R1)

Wir haben einen **massiven RAM-Leak** in SimpleFT8 (Python/PySide6
FT8-App für FlexRadio). Mike musste die App heute beenden — sie hatte
**124 GB Speicher** belegt (auf einem Mac mit 48 GB physischem RAM, der
Rest war komprimiert/swap). Nach Tagen-Laufzeit immer wieder dasselbe.

**Bitte prüfe meine Diagnose-Hypothese kritisch:**
1. Stimmt die Wurzel-Hypothese (`_audio_buffer_24k` Skip-Bug)?
2. Passt die Math zur beobachteten Wachstumsrate?
3. Gibt es ANDERE plausible Leak-Quellen die wir übersehen?
4. Welcher Fix ist sauber (Skip leert auch / Cap / Watchdog)?

Du bist NICHT damit beauftragt den Fix zu schreiben — nur die
Diagnose zu kritisieren und Lücken zu identifizieren.

---

## Beobachtete Wachstumsrate (Mike-Screenshots heute)

| Zeit | Python-RSS (Activity Monitor) |
|---|---|
| 06:00 | 1,79 GB |
| 13:50 | 5,96 GB |

→ **+4,17 GB / 7h50min ≈ 540 MB/h ≈ 9 MB/min**

Hochrechnung: 540 MB/h × 24h = ~13 GB/Tag.
124 GB ÷ 13 GB/Tag = ~10 Tage durchgehende Laufzeit. Passt zu
Mike's „seit Tagen". Mike läuft dauerhaft Diversity-Modus
(2 RX-Antennen).

---

## Hypothese — `_audio_buffer_24k` Skip-Bug

**`core/decoder.py` Z.76-77 (Init):**
```python
self._audio_buffer_24k = []
self._buffer_lock = threading.Lock()
```

**Z.129-138 (Audio-Feed läuft kontinuierlich):**
```python
def feed_audio(self, samples_int16: np.ndarray):
    if not self._startup_done:
        self._startup_samples += len(samples_int16)
        if self._startup_samples < 48000:  # 2s @ 24kHz
            return
        self._startup_done = True
    with self._buffer_lock:
        self._audio_buffer_24k.append(samples_int16.copy())
```

**Z.142-202 (Decode-Loop):**
```python
def _decode_loop(self):
    self._decode_busy = False
    self._decode_busy_lock = threading.Lock()

    while self._running:
        try:
            now = time.time()
            _SLOT = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(self._mode, 15.0)
            _WAKE_OFFSETS = {"FT8": 2.5, "FT4": 0.5, "FT2": 0.3}
            _WAKE = _SLOT - _WAKE_OFFSETS.get(self._mode, 1.5)
            cycle_pos = now % _SLOT
            if cycle_pos < _WAKE:
                target_slot_start = now - cycle_pos
                wait = _WAKE - cycle_pos
            else:
                target_slot_start = now - cycle_pos + _SLOT
                wait = _SLOT - cycle_pos + _WAKE
            time.sleep(wait)

            with self._decode_busy_lock:
                if self._decode_busy:
                    print(f"[Decoder] Skip Zyklus {int(time.time()/15)}: "
                          f"vorheriger Decode laeuft noch")
                    continue                         # <<< LEAK: kein Buffer-Reset!
                self._decode_busy = True

            with self._buffer_lock:
                chunks = self._audio_buffer_24k     # <<< nur HIER geleert
                self._audio_buffer_24k = []

            if not chunks:
                with self._decode_busy_lock:
                    self._decode_busy = False
                continue

            threading.Thread(
                target=self._process_cycle,
                args=(chunks, target_slot_start, _SLOT),
                daemon=True,
            ).start()

        except Exception as e:
            print(f"[Decoder] FEHLER Scheduling: {e}")
            with self._decode_busy_lock:
                self._decode_busy = False
```

**`_decode_busy=False` wird sicher gesetzt in:**
- Z.187: bei "kein Audio" → False
- Z.201: bei Exception im Loop → False
- Z.311: **finally-Block in `_process_cycle`** → garantiert auf False (bei
  Crash + bei sauberem Ende)

**Aber NICHT wenn:**
- `_process_cycle` **hängt** in ft8lib.decode (C-Library, kein Python-
  Exception) → finally läuft nie, `_decode_busy=True` bleibt
- App wird CPU-überlastet, `_process_cycle` braucht >15s → nächster Slot
  trifft `_decode_busy=True` → Skip + Buffer wächst um 720 KB

---

## Math-Check Leak-Rate

- Audio-Stream: 24 kHz × 2 Bytes = 48 KB/s
- 1 FT8-Slot = 15 s = 720 KB Audio (1 Antenne)
- Bei Diversity (2 RX-Antennen): unklar ob Decoder 2× füttert (1 Decoder-
  Instanz, aber Audio kommt von beiden Antennen über VITA-49)
- Beobachtete Rate **540 MB/h** = 9 MB/min = 12,5 Slots/min Verlust
- 12,5 Slots/min ≈ 4 FT8-Slots/min × ~3 Skips pro Slot

**Plausibel** wenn Diversity 2× Audio liefert oder Decoder regelmäßig
1-2 Skips pro Slot hat.

---

## Andere Verdächtige (eliminiert)

| Modul | Cleanup | Verdacht |
|---|---|---|
| `core/station_stats.py` | Queue Cap=1000 + lokale `rows` | niedrig |
| `core/station_accumulator.py` | aktives `del stations[k]` Aging | niedrig |
| `core/ap_lite.py _buffers` | Cap=3 (max 2,16 MB) | niedrig |
| `core/locator_db._calls` | kein Pruning, aber Math nur ~200 MB | niedrig |
| `decoder.last_audio_24k` | 1 Buffer überschrieben (720 KB konstant) | niedrig (außer Qt-Signal-Subscriber — keine gefunden) |
| `decoder.last_pcm_12k` | 1 Buffer überschrieben | niedrig |
| `qso_panel.log_view` | QTimer 30s + 300s-Window + min_threshold 5 | mittel — bei niedrigem Decode-Volumen möglich |
| `_recent_logged_calls` | nie gepruned, nur Cache-Lookup | niedrig (~10 MB Worst-Case) |

**Statistik-Disk-Verbrauch:** 5,3 MB total, 1002 Files — kein Disk-Leak.

---

## Mögliche Fix-Pfade (Hypothesen)

**Fix A — Buffer-Reset im Skip-Pfad:**
```python
if self._decode_busy:
    print("Skip Zyklus ...")
    with self._buffer_lock:           # NEU
        self._audio_buffer_24k = []   # NEU
    continue
```
Trade-off: Audio des übersprungenen Slots verloren — okay, Decoder kann
ihn eh nicht verarbeiten.

**Fix B — Buffer-Cap:**
```python
def feed_audio(self, samples_int16: np.ndarray):
    ...
    with self._buffer_lock:
        self._audio_buffer_24k.append(samples_int16.copy())
        # Cap auf ~2 Slots = 96000 Samples × 2 = ~2 MB
        total = sum(len(c) for c in self._audio_buffer_24k)
        while total > 96000 and self._audio_buffer_24k:
            self._audio_buffer_24k.pop(0)
            total = sum(len(c) for c in self._audio_buffer_24k)
```
Trade-off: ältere Chunks fallen raus, Decoder bekommt nur jüngste.

**Fix C — Watchdog für hängenden Decode:**
- Timer 30s, wenn `_decode_busy=True` länger als 30s → reset auf False
- Schutz gegen ft8lib-Hang (worst case)

**Frage an dich:** Welche Kombination ist sauber? A allein? A+C? Oder
braucht es noch was?

---

## Akzeptanz-Kriterien für späteren Fix

1. Bei `_decode_busy=True`-Skip: `_audio_buffer_24k` muss begrenzt
   bleiben (nicht monoton wachsen)
2. Bei hängendem `_process_cycle` (ft8lib-Endlos-Loop): App muss sich
   nach 30-60s selbst befreien (Watchdog)
3. KEIN Audio-Verlust im Normalbetrieb (Skip-Pfad ist Edge-Case)
4. KEINE neuen Race-Conditions zwischen `feed_audio` (VITA-49-Thread)
   und `_decode_loop` (Decoder-Thread)
5. Tests: Skip-Pfad muss durch Unit-Test abgedeckt sein

---

## Konkrete Fragen an dich (R1)

1. **Hypothese plausibel?** Ist `_audio_buffer_24k` der Hauptverdacht,
   oder übersiehst du eine größere Quelle?
2. **Math:** 540 MB/h passt zu Skip-Bug-Theorie? Oder müsste die Rate
   höher/niedriger sein?
3. **Diversity-Verdoppelung:** Wir haben EINE Decoder-Instanz
   (`ui/main_window.py:145`). Wenn Diversity 2 Antennen über VITA-49
   liefert, geht beider Audio in den Buffer? Müssen wir das prüfen?
4. **Lock-Pattern:** `_buffer_lock` und `_decode_busy_lock` sind
   getrennte Locks. Race-Condition möglich?
5. **Fix-Strategie:** A allein, A+C, oder anders?
6. **Was wir prüfen sollten BEVOR wir fixen:** Worauf sollten wir im
   Memory-Watcher achten um die Hypothese zu bestätigen/widerlegen?

Antworte strukturiert (KRITISCH / SOLLTE / KOENNTE). Wir schicken später
einen Plan V2 wenn Watcher-Daten da sind. Dieser Prompt ist **Diagnose-
Review**, nicht Fix-Plan.
