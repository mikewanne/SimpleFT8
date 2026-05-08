# P3.AUDIO-DUMP-DEBUG V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-08 nach P2.ADIF-ARCHIVE.
**Workflow:** V1 → V2(15 Lessons) → R1(1 KRITISCH + 1 SOLLTE) → **V3** → Compact → Code.
**APP_VERSION:** 0.95.19 → **0.95.20**.
**Compact-fest:** Diese Datei enthaelt das vollstaendige Code-Skelett + Tests.

---

## 1. R1-Findings adressiert

| # | Severity | R1-Finding | V3-Loesung |
|---|---|---|---|
| 1 | 🔴 KRITISCH | Antennen-Setter-Aufruf-Pfad konkretisieren + Race bei mehrfachem Aufruf | **Architektur-Wechsel:** Audio-Buffer wird im Decoder als `last_audio_24k` (numpy int16 array) gespeichert. Dump passiert NICHT im Decoder-Thread, sondern im GUI-Thread via neuer Methode `decoder.dump_last_slot(ant, slot_start_utc)`. mw_cycle._on_cycle_decoded ruft das nach Z.80 (`_resolve_hardware_antenna`) — Antenne ist GARANTIERT korrekt, kein Race, kein Setter-State. |
| 2 | 🟡 SOLLTE | Mode-Race in `_dump_audio_slot` dokumentieren | Modus-Filter wandert von Decoder-Hook in mw_cycle._on_cycle_decoded — Modus + Antenne werden gemeinsam zur Aufruf-Zeit gepruft, kein Race. |

**Architektur-Verbesserung:** Statt Setter-Pattern (V1/V2) wird der Dump per **Pull-Pattern aus GUI-Thread** ausgeloest. Das eliminiert den Race komplett.

**Tests-Soll:** 978 → **991 erwartet (+13)**.

---

## 2. Vollstaendiges Code-Skelett (Compact-fest)

### 2.1 NEU `core/audio_dump.py` (~80 Zeilen)

```python
"""core/audio_dump.py — Roh-Audio-Slot-Dump fuer Debug/Forschung (P3, v0.95.20).

Use-Cases:
- AP-Lite-Decode-Replay (Bug-Diagnose ohne Live-Funkbetrieb)
- ANT1/ANT2-Spektrum-Vergleich offline (Inspectrum/Audacity)
- Decoder-Verbesserungen gegen reale Aufnahmen

Pattern:
- Atomic-Write via tempfile.mkstemp(dir=) + os.replace (P2.ADIF-ARCHIVE-Konsistenz)
- FIFO-Cleanup via mtime-Sort, global ueber alle band_mode-Sub-Dirs
- WAV: mono int16 24 kHz (Decoder-Original-Format vor Resample)
"""
from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

import numpy as np


# Projekt-Root (relativ zu dieser Datei): SimpleFT8/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DUMP_ROOT = _PROJECT_ROOT / "audio_dump"


def atomic_write_wav(path: Path, audio_int16: np.ndarray,
                     sample_rate: int = 24000) -> None:
    """WAV mono 16-bit atomar schreiben.

    Atomic-Pattern: tmpfile auf gleichem FS via tempfile.mkstemp(dir=)
    + os.replace. Bei Crash mid-write: kein zerrissenes WAV, tmpfile
    wird im except aufgeraeumt.
    """
    target_dir = path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
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


def enforce_fifo_cap(audio_dump_root: Path, max_files: int) -> int:
    """Aelteste WAV-Files loeschen wenn Anzahl > max_files.

    Returnt Anzahl geloeschter Files (fuer Tests).
    Globaler Cap ueber alle Sub-Verzeichnisse zusammen.
    Beruecksichtigt nur `*.wav` (nicht `.tmp` oder andere).
    """
    if not audio_dump_root.exists():
        return 0
    all_wavs = sorted(
        audio_dump_root.glob("**/*.wav"),
        key=lambda p: p.stat().st_mtime,
    )
    overflow = len(all_wavs) - max_files
    if overflow <= 0:
        return 0
    deleted = 0
    for p in all_wavs[:overflow]:
        try:
            p.unlink()
            deleted += 1
        except OSError:
            pass  # File-Lock o.ae., naechster Lauf raeumt nach
    return deleted


def build_dump_path(root: Path, band: str, mode: str,
                    slot_start_utc: float, ant: str) -> Path:
    """Baut Filename aus Komponenten + Kollisions-Suffix.

    Format: root/{band}_{mode}/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav
    Bei Kollision: _v2-Suffix (Edge-Case NTP-Sprung / Decoder-Restart).
    """
    import time as _time
    ts = _time.strftime("%Y-%m-%d_%H-%M-%S",
                         _time.gmtime(slot_start_utc))
    sub_dir = root / f"{band}_{mode}"
    path = sub_dir / f"{ts}_{ant}.wav"
    if path.exists():
        path = sub_dir / f"{ts}_{ant}_v2.wav"
    return path
```

### 2.2 Diff `core/decoder.py`

**Im `__init__` (nach Z.80, neue Attribute):**
```python
self.last_audio_24k: np.ndarray | None = None  # P3 v0.95.20: Roh-Slot-Buffer fuer Dump
self.last_slot_start_utc: float = 0.0           # P3 v0.95.20: TS des letzten Slots
```

**In `_process_cycle` (NACH Z.200 `audio_raw = np.concatenate(chunks)`, VOR Z.205):**
```python
# P3 v0.95.20: Roh-Audio fuer optionalen Dump puffern (kopiert wegen
# spaeter in-place Modifikation durch Noise-Floor-Normalisierung).
self.last_audio_24k = audio_raw.copy()
self.last_slot_start_utc = target_slot_start
```

**Neue Methode (am Ende der Decoder-Klasse, vor letzter Klammer):**
```python
def dump_last_slot(self, ant: str, audio_dump_root,
                   max_files: int) -> bool:
    """P3 v0.95.20: Dumpt den zuletzt verarbeiteten Slot als WAV.

    Wird vom GUI-Thread aufgerufen (mw_cycle._on_cycle_decoded) — kein
    Race weil Decoder-Thread `_process_cycle` zu diesem Zeitpunkt
    fertig ist (cycle_decoded-Signal feuerte → wir sind hier).

    Returnt True bei Erfolg, False bei Skip/Fehler.
    """
    if self.last_audio_24k is None or self._mode != "FT8":
        return False
    try:
        from core.audio_dump import (
            atomic_write_wav, enforce_fifo_cap, build_dump_path
        )
        from pathlib import Path
        root = Path(audio_dump_root)
        band = getattr(self, "_band", "20m")  # set_band() setzt das
        path = build_dump_path(root, band, "FT8",
                                 self.last_slot_start_utc, ant)
        atomic_write_wav(path, self.last_audio_24k, sample_rate=24000)
        enforce_fifo_cap(root, max_files)
        return True
    except Exception as e:
        print(f"[AudioDump] Fehler: {e}")
        return False
```

**Hinweis:** `self._band` wird bereits durch existierende `set_band()` gesetzt (V2 verifiziert). Falls noch nicht vorhanden, V3-Code-Pruefung im Code-Phase ergaenzt das Default `"20m"`.

### 2.3 Diff `ui/settings_dialog.py`

**Imports erweitern (Z.12):**
```python
from PySide6.QtWidgets import (
    ...,
    QSpinBox,  # falls noch nicht vorhanden
)
```

**Im `_build_tab_data` (NACH Block 3 Debug-Konsole, VOR `layout.addStretch()`):**
```python
        layout.addWidget(_hline())

        # Block 4: Audio-Dump (P3 v0.95.20)
        audio_lbl = QLabel(
            "Sichert pro FT8-Slot eine WAV-Datei in <b>audio_dump/{band}_FT8/</b> "
            "fuer offline Decoder-Replay und Antennen-Spektrum-Vergleich. "
            "Rollierend mit FIFO-Cleanup — alteste Datei wird ueberschrieben."
        )
        audio_lbl.setWordWrap(True)
        audio_lbl.setStyleSheet("color: #888;")
        layout.addWidget(audio_lbl)

        audio_row = QHBoxLayout()
        self.audio_dump_cb = QCheckBox("Audio-Slots fuer Debugging sichern")
        self.audio_dump_cb.setToolTip(
            "Pro FT8-Slot 1 WAV (24 kHz mono int16, ~576 KB)."
        )
        audio_row.addWidget(self.audio_dump_cb)

        audio_row.addWidget(QLabel("Max. Files:"))
        self.audio_dump_max_spin = QSpinBox()
        self.audio_dump_max_spin.setRange(50, 1000)
        self.audio_dump_max_spin.setValue(200)
        self.audio_dump_max_spin.setToolTip(
            "200 Files ≈ 50 Min FT8 Single-Antenne ≈ 58 MB.\n"
            "1000 Files ≈ 250 Min ≈ 290 MB."
        )
        audio_row.addWidget(self.audio_dump_max_spin)
        audio_row.addStretch()
        layout.addLayout(audio_row)

        # Spinbox enabled/disabled an Checkbox koppeln
        self.audio_dump_cb.toggled.connect(self.audio_dump_max_spin.setEnabled)
        self.audio_dump_max_spin.setEnabled(self.audio_dump_cb.isChecked())
```

**In `_load_values` (nach `debug_console_cb` Z.451):**
```python
        self.audio_dump_cb.setChecked(self.settings.get("audio_dump_enabled", False))
        self.audio_dump_max_spin.setValue(self.settings.get("audio_dump_max_files", 200))
        self.audio_dump_max_spin.setEnabled(self.audio_dump_cb.isChecked())
```

**In `_on_save_clicked` (nach `debug_console_visible` Z.573):**
```python
        self.settings.set("audio_dump_enabled", self.audio_dump_cb.isChecked())
        self.settings.set("audio_dump_max_files", self.audio_dump_max_spin.value())
```

**Im Reset-Pfad (nach `debug_console_cb.setChecked(False)` Z.609):**
```python
        self.audio_dump_cb.setChecked(False)
        self.audio_dump_max_spin.setValue(200)
```

### 2.4 Diff `ui/mw_cycle.py`

**In `_on_cycle_decoded` (NACH Z.80 `ant = self._resolve_hardware_antenna(ant)`):**
```python
        # P3 v0.95.20: Audio-Dump fuer Debug/Forschung. Pull-Pattern aus
        # GUI-Thread → Antenne ist garantiert korrekt fuer den just-decoded
        # Slot (kein Race mit Decoder-Thread). Modus-Filter im Decoder
        # (nur FT8). Rx_mode "dx_tuning" wird nicht gefiltert — Mike kann
        # auch Phase-2-Slots replay'en falls noetig.
        if self._audio_dump_enabled:
            from core.audio_dump import DEFAULT_DUMP_ROOT
            ant_long = "ANT1" if ant == "A1" else "ANT2"
            self.decoder.dump_last_slot(
                ant_long, DEFAULT_DUMP_ROOT, self._audio_dump_max_files
            )
```

**Wo werden `_audio_dump_enabled` + `_audio_dump_max_files` gesetzt?**
→ In `MainWindow.__init__` aus Settings, plus Update bei Settings-Save (siehe 2.5).

### 2.5 Diff `ui/main_window.py`

**Im `__init__` (bei den Initial-State-Loads aus Settings, z.B. nach `_recent_logged_calls`):**
```python
        # P3 v0.95.20: Audio-Dump-Settings (in mw_cycle._on_cycle_decoded gelesen)
        self._audio_dump_enabled = settings.get("audio_dump_enabled", False)
        self._audio_dump_max_files = settings.get("audio_dump_max_files", 200)
```

**Im Settings-Save-Handler (wo Settings-Dialog akzeptiert wird):**
```python
        self._audio_dump_enabled = self.settings.get("audio_dump_enabled", False)
        self._audio_dump_max_files = self.settings.get("audio_dump_max_files", 200)
```

### 2.6 Diff `main.py`

```python
APP_VERSION = "0.95.20"  # P3.AUDIO-DUMP-DEBUG (Audio-Slot-Dump fuer Debug/Forschung)
```

---

## 3. Tests (NEU `tests/test_audio_dump.py` — 13 Tests)

```python
"""Tests fuer core/audio_dump.py + Decoder.dump_last_slot.

Hardware-frei. Kein Qt noetig fuer Helper-Tests; Qt-offscreen fuer
Decoder-Integration.
"""
from __future__ import annotations

import os
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.audio_dump import (  # noqa: E402
    atomic_write_wav, enforce_fifo_cap, build_dump_path,
)


def _make_audio(samples: int = 1000, value: int = 1000) -> np.ndarray:
    return np.full(samples, value, dtype=np.int16)


# ── Helper-Tests ─────────────────────────────────────────────────────────


def test_atomic_write_wav_basic(tmp_path):
    path = tmp_path / "2026.wav"
    atomic_write_wav(path, _make_audio(2400), sample_rate=24000)
    assert path.exists()
    with wave.open(str(path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() == 2400


def test_atomic_write_wav_replaces_existing(tmp_path):
    path = tmp_path / "old.wav"
    atomic_write_wav(path, _make_audio(100, value=500))
    original_size = path.stat().st_size
    atomic_write_wav(path, _make_audio(2000, value=1000))
    assert path.stat().st_size > original_size


def test_atomic_write_wav_no_partial_on_crash(tmp_path, monkeypatch):
    path = tmp_path / "crash.wav"
    atomic_write_wav(path, _make_audio(100, value=500))
    original_text = path.read_bytes()

    def fail_replace(*a, **kw):
        raise OSError("simulated")
    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError):
        atomic_write_wav(path, _make_audio(200, value=1000))
    # Original muss intakt sein
    assert path.read_bytes() == original_text
    # Tmpfile aufgeraeumt
    tmps = list(tmp_path.glob(".crash.wav.*.tmp"))
    assert len(tmps) == 0


def test_atomic_write_wav_creates_parent_dir(tmp_path):
    path = tmp_path / "new_subdir" / "file.wav"
    atomic_write_wav(path, _make_audio(100))
    assert path.exists()


def test_fifo_cap_no_op_under_limit(tmp_path):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    for i in range(50):
        (sub / f"file_{i:03d}.wav").write_bytes(b"x")
    deleted = enforce_fifo_cap(tmp_path, max_files=200)
    assert deleted == 0
    assert len(list(sub.glob("*.wav"))) == 50


def test_fifo_cap_deletes_oldest(tmp_path):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    import time as _time
    for i in range(5):
        f = sub / f"file_{i:03d}.wav"
        f.write_bytes(b"x")
        os.utime(f, (1_000_000 + i, 1_000_000 + i))  # mtime aufsteigend
    deleted = enforce_fifo_cap(tmp_path, max_files=3)
    assert deleted == 2
    remaining = sorted(sub.glob("*.wav"))
    # Aelteste 2 Files (000, 001) sind weg; 002, 003, 004 bleiben
    assert remaining == [
        sub / "file_002.wav",
        sub / "file_003.wav",
        sub / "file_004.wav",
    ]


def test_fifo_cap_global_across_band_dirs(tmp_path):
    s20 = tmp_path / "20m_FT8"
    s40 = tmp_path / "40m_FT8"
    s20.mkdir()
    s40.mkdir()
    import time as _time
    # 100 Files in 20m_FT8, mtime 1000-1099
    for i in range(100):
        f = s20 / f"a_{i:03d}.wav"
        f.write_bytes(b"x")
        os.utime(f, (1000 + i, 1000 + i))
    # 101 Files in 40m_FT8, mtime 2000-2100 (juenger als alle 20m)
    for i in range(101):
        f = s40 / f"b_{i:03d}.wav"
        f.write_bytes(b"x")
        os.utime(f, (2000 + i, 2000 + i))
    # Cap 200 → 1 muss raus, das aelteste = a_000.wav (mtime 1000)
    deleted = enforce_fifo_cap(tmp_path, max_files=200)
    assert deleted == 1
    assert not (s20 / "a_000.wav").exists()
    assert (s20 / "a_001.wav").exists()  # zweitaelteste bleibt
    assert (s40 / "b_100.wav").exists()  # juengstes da


def test_fifo_cap_ignores_non_wav(tmp_path):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    # 5 echte WAV
    for i in range(5):
        (sub / f"x_{i}.wav").write_bytes(b"x")
    # Tmpfile + andere Endung — duerfen NICHT mitgezaehlt/geloescht werden
    (sub / ".x_0.wav.abc.tmp").write_bytes(b"x")
    (sub / "readme.txt").write_bytes(b"x")
    deleted = enforce_fifo_cap(tmp_path, max_files=3)
    assert deleted == 2
    assert (sub / ".x_0.wav.abc.tmp").exists()
    assert (sub / "readme.txt").exists()


def test_fifo_cap_handles_unlink_error(tmp_path, monkeypatch):
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    for i in range(5):
        (sub / f"f_{i}.wav").write_bytes(b"x")

    real_unlink = Path.unlink
    call_count = [0]
    def flaky_unlink(self, *a, **kw):
        call_count[0] += 1
        if call_count[0] == 1:
            raise OSError("locked")
        return real_unlink(self, *a, **kw)
    monkeypatch.setattr(Path, "unlink", flaky_unlink)

    deleted = enforce_fifo_cap(tmp_path, max_files=3)
    # 1 unlink schlug fehl → nur 1 erfolgreich deleted (statt 2)
    assert deleted == 1


def test_build_dump_path_basic(tmp_path):
    path = build_dump_path(tmp_path, "40m", "FT8", 1714824000.0, "ANT1")
    assert path.parent == tmp_path / "40m_FT8"
    assert path.name.endswith("_ANT1.wav")
    assert "FT8" in str(path.parent)


def test_build_dump_path_collision_v2_suffix(tmp_path):
    # Erstmal Datei anlegen
    sub = tmp_path / "20m_FT8"
    sub.mkdir()
    path1 = build_dump_path(tmp_path, "20m", "FT8", 1714824000.0, "ANT2")
    path1.write_bytes(b"x")
    # Zweiter Aufruf mit gleicher Slot-Zeit + Antenne → _v2
    path2 = build_dump_path(tmp_path, "20m", "FT8", 1714824000.0, "ANT2")
    assert path2 != path1
    assert "_v2" in path2.name


def test_build_dump_path_timestamp_format(tmp_path):
    # 2026-05-08 14:23:00 UTC = 1778250180.0
    path = build_dump_path(tmp_path, "40m", "FT8", 1778250180.0, "ANT1")
    assert "2026-05-08_14-23-00" in path.name


def test_decoder_dump_skips_non_ft8(tmp_path):
    """Decoder.dump_last_slot returnt False wenn Modus != FT8."""
    from core.decoder import Decoder
    d = Decoder(mode="FT4")
    d.last_audio_24k = _make_audio(2400)
    d.last_slot_start_utc = 1714824000.0
    d._band = "40m"
    result = d.dump_last_slot("ANT1", tmp_path, max_files=200)
    assert result is False
    # Keine WAV erstellt
    assert list(tmp_path.glob("**/*.wav")) == []


def test_decoder_dump_writes_wav_in_ft8(tmp_path):
    """Decoder.dump_last_slot schreibt WAV bei FT8 + buffer != None."""
    from core.decoder import Decoder
    d = Decoder(mode="FT8")
    d.last_audio_24k = _make_audio(24000 * 13)  # ~13 s
    d.last_slot_start_utc = 1778250180.0
    d._band = "40m"
    result = d.dump_last_slot("ANT1", tmp_path, max_files=200)
    assert result is True
    wavs = list(tmp_path.glob("**/*.wav"))
    assert len(wavs) == 1
    assert "40m_FT8" in str(wavs[0])
    assert "_ANT1.wav" in wavs[0].name
```

**Hinweis:** Die letzten 2 Tests (`test_decoder_dump_*`) testen die
Decoder-Integration ohne mw_cycle. Sie verlangen dass `Decoder.__init__`
das neue Attribut `_band` setzt — V3-Code muss das sicherstellen
(Default `"20m"` falls `set_band()` noch nie gerufen wurde).

---

## 4. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** (Verifikation):
   - `prompts/p3_audio_dump_v3.md` (diese Datei)
   - `core/decoder.py:1-90` (Init-Block + `_band`-Setting)
   - `ui/settings_dialog.py:355-405` (Tab 4 Block 3)
   - `ui/mw_cycle.py:60-95` (`_on_cycle_decoded`)
2. **NEU `core/audio_dump.py`** — Skript aus §2.1 anwenden.
3. **`core/decoder.py` Diff** — Init-Attribute + Hook in `_process_cycle`
   + neue Methode `dump_last_slot()`. **WICHTIG:** sicherstellen dass
   `_band`-Default in `__init__` gesetzt wird (z.B. `self._band = "20m"`).
4. **`ui/settings_dialog.py` Diff** — Tab 4 Block 4 Audio-Dump.
5. **`ui/mw_cycle.py` Diff** — Aufruf in `_on_cycle_decoded` nach Z.80.
6. **`ui/main_window.py` Diff** — Initial-Loads aus Settings + Update.
7. **`main.py`** — APP_VERSION 0.95.19 → 0.95.20.
8. **NEU `tests/test_audio_dump.py`** — 13 Tests aus §3.
9. **Smoke-Test:** `./venv/bin/python3 main.py` → App startet, Settings-
   Dialog oeffnen → Tab „Daten & Tools" → Block „Audio-Slots" sichtbar.
10. **Tests laufen:** `978 → 991 erwartet gruen`.
11. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P3.AUDIO-DUMP-DEBUG final-Code (v0.95.20).
    Architektur-Wechsel: Pull-Pattern aus GUI-Thread (mw_cycle._on_cycle_decoded)
    statt Setter-Pattern → kein Race. Atomic-Write + FIFO-Cleanup wie P2." | \
    ./venv/bin/python3 tools/deepseek_review.py \
    core/audio_dump.py core/decoder.py ui/mw_cycle.py \
    ui/settings_dialog.py ui/main_window.py tests/test_audio_dump.py
    ```
12. **Atomare Commits — 2 Code + 1 Doku:**
    - Code-1: `P3.AUDIO-DUMP-DEBUG: core/audio_dump.py + Decoder-Hook + 13 Tests`
    - Code-2: `P3.AUDIO-DUMP-DEBUG: Settings-UI + mw_cycle Pull + APP_VERSION 0.95.20`
    - Doku: `docs (P3.AUDIO-DUMP-DEBUG): HISTORY+HANDOFF+CLAUDE+TODO+Memory`
13. **Doku-Updates** (HISTORY + HANDOFF beide Pfade + CLAUDE beide Pfade
    + TODO-Punkt abhaken + Memory).
14. **KEIN Push noetig** — Mike kann lokal nutzen, Push zusammen mit
    v0.95.16-19 + P2-Tool + diesem Bundle.
15. **Lessons-Learned**.

---

## 5. Akzeptanz-Checkliste (final)

```
- [ ] core/audio_dump.py NEU (atomic_write_wav, enforce_fifo_cap,
      build_dump_path)
- [ ] core/decoder.py: last_audio_24k + last_slot_start_utc + _band-Default
      + dump_last_slot()-Methode + Hook in _process_cycle
- [ ] ui/settings_dialog.py: Tab 4 Block 4 (Checkbox + Spinbox + Label)
- [ ] ui/mw_cycle.py: dump_last_slot-Aufruf nach _resolve_hardware_antenna
- [ ] ui/main_window.py: Initial-Load + Update bei Settings-Save
- [ ] main.py: APP_VERSION 0.95.20
- [ ] tests/test_audio_dump.py NEU mit 13 Tests
- [ ] Smoke-Test: App startet, Settings-Dialog zeigt neuen Block
- [ ] Tests gesamt: 978 → 991 gruen
- [ ] Final-R1 ohne KP-Findings (oder kleine sofort-fixbar)
- [ ] HISTORY/HANDOFF/CLAUDE updated (beide Pfade)
- [ ] 2 Code-Commits + 1 Doku-Commit
- [ ] Memory-File ✅
- [ ] R1-KRITISCH adressiert: Pull-Pattern statt Setter (kein Race)
- [ ] R1-SOLLTE adressiert: Modus-Filter in mw_cycle (kein Race)
```

---

## 6. Risiken & Notbremse

- **Disk-Bloat bei vergessenem Toggle:** durch FIFO-Cap mitigiert
  (Default 200 = max ~58 MB). Mike erhoeht selbst falls noetig.
- **`last_audio_24k` Memory-Footprint:** ~600 KB pro Slot, dauerhaft
  im RAM gehalten. Bei 16 GB-Mac irrelevant.
- **Race bei Settings-Update:** Toggle-Wechsel waehrend Slot-Decode →
  naechster Slot honors neuer Wert, aktueller Slot evtl. nicht.
  Akzeptabel (max 1 verpasster/extra Dump).
- **WAV-Filename-Kollision bei NTP-Sprung rueckwaerts:** `_v2`-Suffix
  faengt das ab.
- **Notbremse:** Toggle in Settings auf „aus" → kein WAV-Schreiben.
  Plus: `audio_dump/`-Verzeichnis kann jederzeit von Mike geloescht
  werden (lebt nicht im `~/.simpleft8/`-State).

---

## 7. Lessons-Learned-Vorschlaege

1. **Pull-Pattern statt Setter-Pattern** bei Multi-Thread-Ist-Werten:
   Wenn ein Thread A einen Wert braucht den Thread B kennt, ruft A den
   Wert vom B-Daten-Buffer ab statt B den Wert in A reinpusht. Eliminiert
   Race komplett.
2. **R1's KRITISCH war richtig:** V2's Setter-Pattern war fragile —
   ohne R1-Plan-Review haetten wir einen Bug eingebaut der Antennen-Tags
   1 Slot zu spaet macht.
3. **Atomic-Write-Pattern wiederverwenden:** P2.ADIF-ARCHIVE hat das
   `tempfile.mkstemp(dir=) + os.replace` Pattern etabliert — P3 kopiert
   1:1, kostet nichts, schenkt 1 Schicht Sicherheit.

Memory-Vorschlaege:
- `feedback_pull_vs_setter_pattern.md` — bei Multi-Thread-Ist-Werten
  Pull-Pattern bevorzugen (R1-Lesson 08.05.).

---

## 8. Field-Test-Plan

**Hardware-frei (zumindest fuer Toggle-Smoke):**
1. App starten → Settings → Tab „Daten & Tools" → Block „Audio-Slots
   fuer Debugging sichern" sichtbar.
2. Toggle ON + Cap 50 → OK → App weiterlaufen lassen.
3. Mit echtem FT8-Funkbetrieb (ein paar Slots): pruefen ob WAVs in
   `audio_dump/{band}_FT8/` auftauchen, korrekte Antennen-Tags.
4. Cap-Test: Cap 5 setzen, 10 Slots laufen lassen → max 5 WAVs.
5. Audacity-Test: 1 WAV oeffnen → 24 kHz mono int16, ~12.6s Dauer
   (FT8-Slot).
6. Replay-Test (Forschung): 1 WAV durch `tools/decode_wav.py` (falls
   vorhanden) — liefert dieselben Stationen wie Live? (Toleranz +/-1
   Station moeglich, AP-Lite nicht-deterministisch).

**Freigabe-Kriterium:** Punkte 1-5 OK + Mike's „passt".

---

**V3-Ende. Bereit fuer Compact + Code.**
