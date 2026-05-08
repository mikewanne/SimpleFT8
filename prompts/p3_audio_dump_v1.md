# P3.AUDIO-DUMP-DEBUG V1 — Roh-Audio-WAV-Dump pro Slot (Diagnose)

**Stand:** 2026-05-08 nach P2.ADIF-ARCHIVE.
**Ziel:** Roh-Audio-Slots pro FT8-Zyklus als WAV-Datei rollierend
sichern (Toggle in Settings, Max-Files-Cap, FIFO-Cleanup).
**Use-Cases:** AP-Lite-Decode-Replay, ANT1/ANT2-Spektrum offline
(Inspectrum/Audacity), Decoder-Verbesserungen gegen reale Aufnahmen.
**APP_VERSION-Ziel:** unangetastet ODER +0.01 (klaeren wir in V2).

---

## 1. Mike-Anforderung (07.05.2026 + Refinement 08.05.)

> „Audio-Export per Slot: Roh-WAV-Dump 4s pro Slot fuer Forschung/
> Debug. Settings-Menupunkt im selben Tab wie Debug-Fenster-Toggle.
> Speicherort: Unterverzeichnis im SimpleFT8-Ordner, klar
> wiederauffindbar. Vorschlag: `audio_dump/{band}_{mode}/
> {YYYY-MM-DD_HH-MM-SS}_{ant}.wav`. Optional, <1 Tag Aufwand."

> Refinement 08.05.: „Rollierend sichern — max N Dateien, dann werden
> die letzten geloescht und durch die neuesten ersetzt. Toggle in
> Settings „Audio-Files fuer Debugging sichern". Erstmal nur FT8."

**Use-Case-Konkretisierung:**
1. **AP-Lite-Replay** — AP-Lite ist im Code aktiv aber „UNGETESTET"
   (CLAUDE.md). Wenn ein FT8-Slot komisch wirkt (0 Stationen während
   andere Tools 5 sehen), kann Mike die WAV offline durch den Decoder
   schicken und AP-Lite-Pfad debuggen.
2. **ANT1/ANT2-Spektrum-Vergleich offline** — Inspectrum/Audacity
   öffnen, beide Antennen als Wasserfall vergleichen, Diversity-Effekte
   sichtbar machen ohne live Stats sammeln zu müssen.
3. **Decoder-Verbesserungen testen** — neue Pass-Strategien gegen
   reale Aufnahmen statt synthetische Test-Signale.

---

## 2. Symptom / Status quo

**Aktuell:** SimpleFT8 hat KEINEN Audio-Roh-Dump. Wenn ein Slot komisch
ist, gibt's nur die Logs (`simpleft8.log`). Die Audio-Daten landen
direkt im Decoder und sind nach `_process_cycle` weg.

**Folge:** Bug-Diagnose bei Decoder-Problemen geht nur live — Mike
kann nicht „den Slot von 14:23 nochmal durchschicken".

---

## 3. Anforderungen

### 3.1 Funktional

1. **Toggle in Settings:** Tab 4 „Daten & Tools" Block 3 (bei
   Debug-Konsole) — neuer Checkbox „Audio-Slots fuer Debugging
   sichern". Default AUS. Persistent in `~/.simpleft8/settings.json`.
2. **Max-Files-Cap:** Spinbox neben Toggle, Range 50-1000, Default 200
   (= ~50 Min FT8 Single-Antenne, ~58 MB).
3. **Hook-Punkt:** `core/decoder.py:_process_cycle` Z.200 — direkt
   nach `audio_raw = np.concatenate(chunks)`. **VOR** Resample, **VOR**
   Preprocessing → Original-24kHz wird gedumpt (wichtig fuers
   Replay).
4. **Format:** WAV mono 16-bit 24000 Hz (Python `wave`-Modul, kein
   externes Lib).
5. **Verzeichnis:** `audio_dump/{band}_FT8/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav`
   (z.B. `audio_dump/40m_FT8/2026-05-08_14-23-00_ANT1.wav`).
6. **Cleanup-Strategie:** **Global** (alle Verzeichnisse zusammen) —
   bei jedem Write Anzahl WAV-Files in `audio_dump/**/*.wav` zaehlen,
   wenn > Cap → aelteste (`os.path.getmtime`) loeschen bis Cap.
7. **Modus-Filter:** NUR `mode == "FT8"`. FT4/FT2-Slots werden
   ignoriert (auch wenn Toggle an).
8. **Antennen-Info:** Im Diversity-Modus pro Slot die aktuell genutzte
   Antenne. Im Normal-Modus die Hardware-RX-Antenne aus Settings.
9. **Filename-Kollision:** Bei doppeltem Timestamp (selber Slot 2x)
   → `_v2`-Suffix.
10. **Fehler-Robustheit:** Cleanup- oder Write-Fehler crasht **nie**
    den Decoder — try/except + log.

### 3.2 Nicht-Funktional

- **Hardware-frei testbar:** WAV-Schreibfunktion + Cleanup-Logik
  isoliert testbar (keine Radio/Qt-Abhaengigkeit).
- **Performance:** Schreiben darf `_process_cycle` nicht messbar
  bremsen (< 50 ms fuer 12s @ 24kHz int16 = 576 KB).
- **Keine Threading-Komplexitaet:** Schreiben synchron im
  `_process_cycle`-Worker-Thread (laeuft eh schon im
  Daemon-Thread).
- **Atomic-Write:** `tempfile.mkstemp(dir=target_dir)` + `os.replace`
  (Pattern aus P2.ADIF-ARCHIVE wiederverwenden — bei Crash kein
  zerrissenes WAV).

---

## 4. Akzeptanzkriterien

- **AC1:** Toggle AUS → keine WAV-Dateien werden erstellt, auch bei
  vielen Zyklen.
- **AC2:** Toggle EIN → bei jedem FT8-Slot wird 1 WAV in
  `audio_dump/{band}_FT8/` erstellt mit korrektem Filename-Format.
- **AC3:** Cap = N → nach N+1 Slots ist aelteste WAV geloescht, neueste
  noch da. FIFO-Beweis.
- **AC4:** Verzeichnis `audio_dump/` + Sub-Verzeichnisse werden
  automatisch erstellt (`mkdir(parents=True, exist_ok=True)`).
- **AC5:** WAV laesst sich in Audacity oeffnen, Inhalt ist 24kHz
  mono 16-bit, Dauer ~12.6s (FT8-Slot bei 24kHz Sampling).
- **AC6:** FT4-Modus + Toggle EIN → keine WAV erstellt
  (Modus-Filter).
- **AC7:** Cleanup-Fehler (z.B. WAV-File locked) → Decoder laeuft
  weiter, Fehler im Log.
- **AC8:** 2× im selben Slot triggern (Edge-Case Test) → 2 Files
  mit `_v2`-Suffix.
- **AC9:** Settings-Persistenz: Toggle EIN, App neustarten → Toggle
  bleibt EIN. Cap-Wert wird auch persistiert.
- **AC10:** ANT1/ANT2-Filename ist korrekt — pro Slot wird der
  String passend zur aktuell aktiven Hardware-RX-Antenne gewaehlt.

---

## 5. Implementations-Skizze

### 5.1 Settings-Erweiterung (`config/settings.py`)

```python
# Neue Settings-Keys:
# - "audio_dump_enabled": bool (Default False)
# - "audio_dump_max_files": int (Default 200)
```

### 5.2 Settings-UI (`ui/settings_dialog.py`, Tab 4 Block 3)

```python
# Z.397ff erweitern:
# - QLabel "Audio-Slots fuer Debugging sichern"
#   (Tooltip: "Pro FT8-Zyklus 1 WAV-Datei in audio_dump/{band}_FT8/. Rollierend, max N Files.")
# - QCheckBox audio_dump_cb
# - QSpinBox audio_dump_max_files_spin (Range 50-1000, Default 200)
# In _load_values: setChecked + setValue
# In _on_save_clicked: settings.set(...)
```

### 5.3 Decoder-Hook (`core/decoder.py`)

```python
# Im __init__ neue Attribute:
self._audio_dump_enabled = False
self._audio_dump_max_files = 200
self._audio_dump_dir = Path("audio_dump")
self._current_antenna = "ANT1"  # wird via set_current_antenna() gesetzt
self._current_band = "20m"      # wird via set_band() gesetzt (existiert bereits)

# Neue Setter-Methoden:
def set_audio_dump_settings(self, enabled: bool, max_files: int):
    self._audio_dump_enabled = enabled
    self._audio_dump_max_files = max(50, min(1000, max_files))

def set_current_antenna(self, ant: str):
    self._current_antenna = ant  # wird von mw_cycle pro Slot gesetzt

# Hook in _process_cycle (Z.200 nach np.concatenate):
if self._audio_dump_enabled and self._mode == "FT8":
    try:
        self._dump_audio_slot(audio_raw, target_slot_start)
    except Exception as e:
        print(f"[AudioDump] Fehler: {e}")

def _dump_audio_slot(self, audio_24k: np.ndarray,
                      slot_start_utc: float) -> None:
    """WAV schreiben + FIFO-Cleanup."""
    band = self._current_band  # z.B. "40m"
    ant = self._current_antenna  # z.B. "ANT1"
    target_dir = self._audio_dump_dir / f"{band}_FT8"
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d_%H-%M-%S",
                        time.gmtime(slot_start_utc))
    path = target_dir / f"{ts}_{ant}.wav"
    if path.exists():
        path = target_dir / f"{ts}_{ant}_v2.wav"
    _atomic_write_wav(path, audio_24k, sample_rate=24000)
    _enforce_fifo_cap(self._audio_dump_dir,
                       self._audio_dump_max_files)
```

### 5.4 WAV + FIFO Helper-Modul NEU `core/audio_dump.py`

```python
"""core/audio_dump.py — Roh-Audio-Slot-Dump fuer Debug/Forschung."""
import os
import tempfile
import wave
from pathlib import Path
import numpy as np


def _atomic_write_wav(path: Path, audio_int16: np.ndarray,
                       sample_rate: int = 24000) -> None:
    """WAV atomar schreiben (tmpfile + os.replace, gleiches FS)."""
    target_dir = path.parent
    fd, tmp_path = tempfile.mkstemp(
        dir=target_dir, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(fd)
    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.astype(np.int16).tobytes())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _enforce_fifo_cap(audio_dump_root: Path, max_files: int) -> None:
    """Aelteste WAV-Files loeschen wenn Anzahl > max_files."""
    if not audio_dump_root.exists():
        return
    all_wavs = sorted(
        audio_dump_root.glob("**/*.wav"),
        key=lambda p: p.stat().st_mtime,
    )
    overflow = len(all_wavs) - max_files
    if overflow > 0:
        for p in all_wavs[:overflow]:
            try:
                p.unlink()
            except OSError:
                pass  # File-Lock o.ae., naechster Lauf raeumt nach
```

### 5.5 Antennen-Info-Pfad (`ui/mw_cycle.py`)

```python
# Im _on_cycle_decoded oder _slot_setup, BEVOR Decoder Audio bekommt:
# Aktuelle Hardware-RX-Antenne ermitteln und an Decoder geben.
ant = self._resolve_hardware_antenna(default_ant)
self.decoder.set_current_antenna(ant)
```

### 5.6 Settings → Decoder verbinden (`ui/main_window.py`)

```python
# Beim Laden + bei Settings-Save:
self.decoder.set_audio_dump_settings(
    enabled=settings.get("audio_dump_enabled", False),
    max_files=settings.get("audio_dump_max_files", 200),
)
```

---

## 6. Tests (geplant: ~12)

1. `test_atomic_write_wav_basic` — WAV laesst sich danach mit
   `wave.open` lesen, korrekte Framerate/Samples.
2. `test_atomic_write_wav_replaces_existing` — wenn Datei schon da
   ist, wird sie atomar ersetzt.
3. `test_atomic_write_wav_no_partial_on_crash` — `os.replace`
   monkeypatch → Original bleibt heil, tmpfile aufgeraeumt.
4. `test_fifo_cap_no_op_under_limit` — 50 Files, Cap 200 → nichts
   geloescht.
5. `test_fifo_cap_deletes_oldest` — 201 Files, Cap 200 → aelteste
   (kleinster mtime) geloescht, Rest da.
6. `test_fifo_cap_handles_unlink_error` — 1 File locked, andere nicht
   → keine Exception, andere werden geloescht.
7. `test_fifo_cap_global_across_band_dirs` — 100 in 20m_FT8 + 101 in
   40m_FT8 = 201 Total, Cap 200 → 1 aelteste geloescht (egal in
   welchem Sub-Dir).
8. `test_decoder_dump_disabled_no_write` (mit tmp_path Decoder-Mock)
   — Toggle aus, `_dump_audio_slot` nicht aufgerufen.
9. `test_decoder_dump_filename_format` — TS + ANT korrekt.
10. `test_decoder_dump_skips_non_ft8` — `_mode="FT4"` → kein Dump.
11. `test_decoder_dump_collision_v2_suffix` — gleicher Timestamp
    2× → erste = `..._ANT1.wav`, zweite = `..._ANT1_v2.wav`.
12. `test_settings_persistence` — Set + Save + Reload → Werte
    erhalten.

---

## 7. Offene Fragen fuer V2

1. **Antennen-Info im Normal-Modus:** Aktuelle Hardware-RX-Antenne aus
   `settings.get("rx_antenna", "ANT1")` lesen, oder gibt's einen
   besseren Pfad? `_resolve_hardware_antenna(default_ant)` wird auch
   bei Phase 2 (DXTuneDialog) verwendet — koennten wir wiederverwenden.
   → V2 verifiziert.
2. **Diversity-Pattern:** Im Diversity-Modus rotiert die Antenne pro
   Slot (70:30, 50:50). Decoder bekommt EINEN Stream — ist das
   bereits der gemergt'e oder ein einzelner Slot? Wenn gemergt: dann
   gibt's keine „echte" Antennen-Info pro Slot. Code-Verifikation:
   gibt's einen Pfad bei dem ANT1+ANT2 GLEICHZEITIG zum Decoder
   kommen? → V2 muss das pruefen.
3. **APP_VERSION-Bump:** Tool-Erweiterung am Decoder + neues Modul
   + Settings-UI = nicht trivial. Hochbumpen auf 0.95.20 oder neutral
   lassen? V2 entscheidet.
4. **Cap-Default:** 200 ist mein Vorschlag. Soll Cap-Default
   modus-abhaengig sein (FT4/FT2 produzieren mehr Slots/Min)?
   Da aktuell nur FT8 → KISS, ein Default reicht.
5. **Cleanup-Frequenz:** Bei jedem Write `_enforce_fifo_cap()`
   aufrufen, oder weniger oft (z.B. alle 10 Slots)? Bei 200 Files
   ist das `glob("**/*.wav")` < 1 ms. KISS = jedes Mal.
6. **Settings-UI:** Cap-Spinbox zeigen oder erstmal hardcoded 200?
   V2 entscheidet (Mike fragen ob Spinbox oder fix).
7. **Antennen-Info bei Toggle-OFF:** `set_current_antenna` wird auch
   gerufen wenn Dump aus ist — Overhead minimal (1 String-Set).
   Akzeptabel?

---

## 8. Workflow-Bewertung

**Trigger fuer vollen V1→V2→R1→V3-Workflow:**
- ✅ Beruehrt mehrere Schichten (Decoder, Settings, UI, neuer Modul)
- ✅ Persistence/IO neu beteiligt (WAV-Schreiben + FIFO-Cleanup)
- ✅ Threading: `_process_cycle` ist Worker-Thread, Cleanup nicht
  thread-safe wenn 2× gleichzeitig laufen → KISS-Doku reicht
- ✅ ≥2 unabhaengige Akzeptanzkriterien (10 ACs)
- ✅ Mike-Compact-Wunsch zwischen Plan und Code

**Tests-Erwartung:** 978 → ~990 (+12).

**Atomare Commits:** 1 Code-Commit + 1 Doku-Commit. Wenn V2/V3 das
in mehrere logische Einheiten splittet (z.B. Helper-Modul + Decoder-
Hook + Settings-UI), evtl. 2-3 Code-Commits.

---

## 9. Risiken

- **Disk-Bloat bei vergessenem Toggle:** durch FIFO-Cap mitigiert
  (Default 200 = max ~58 MB).
- **Decoder-Performance:** WAV-Write 12s @ 24kHz int16 = 576 KB.
  Auf SSD < 10 ms, auf HDD evtl. 50-100 ms — innerhalb
  `_process_cycle`-Worker-Thread, blockt nicht GUI. Akzeptabel.
- **Replay-Pipeline-Bruch:** Wenn `_preprocess_audio` sich aendert,
  alte WAV-Dumps decodieren evtl. anders. Doku-Hinweis: WAVs sind
  Snapshots, nicht zukunftssicher.
- **Falsche Antennen-Info:** Wenn `set_current_antenna` zu spaet
  gerufen wird, kann ein Slot mit falschem ANT-Suffix gespeichert
  werden. V2 muss das Timing pruefen.

---

**V1-Ende. V2-Self-Review folgt.**
