# P152 R1 — Weak-Decode-Logging Review

## Kontext

SimpleFT8 (FT8 FlexRadio Hobby-Tool). P150 hat den Decoder empfindlicher
gemacht (`kMin_score=10→4`). Wir haben KEINE Vorher-Werte. Mike-Idee:
ab jetzt jeden schwachen Decode (SNR ≤ -21 dB) in eine eigene Liste
schreiben → empirischer Beweis ob tiefe Decodes jetzt kommen.

Mike funkt gerade live (15m mau, 2 Stationen bei -22 dB) — genau der
Use-Case.

**Mike-Wahl:** Eigene Datei, IMMER an (kein Setting), Schwelle ≤ -21 dB.

## Geplantes Design

### Neues Modul `core/weak_decode_log.py`

Analog `core/debug_log.py` (siehe angehängt), ABER always-on (kein Toggle).

```python
from __future__ import annotations
import threading, time
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path.home() / ".simpleft8"
WEAK_SNR_THRESHOLD = -21
_lock = threading.Lock()

def _current_path() -> Path:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return LOG_DIR / f"weak_decodes_{today}.log"

def log_weak_decode(snr, msg_text, freq_hz, band, mode) -> None:
    try:
        with _lock:
            ts = datetime.utcnow().strftime("%H:%M:%S")
            line = f"{ts} | {snr:+d} dB | {msg_text} | {freq_hz} Hz | {band} {mode}\n"
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with _current_path().open("a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        pass

def cleanup_old_files(keep_days=7) -> int:
    # analog debug_log.cleanup_old_files, glob "weak_decodes_*.log"
    ...
```

### Hook in `ui/mw_cycle.py:_on_cycle_decoded`

Nach `_assign_slot_parity(messages)` (Z. 87), vor mode-Branches:

```python
from core.weak_decode_log import log_weak_decode, WEAK_SNR_THRESHOLD
for _m in (messages or []):
    if getattr(_m, 'snr', 0) <= WEAK_SNR_THRESHOLD:
        log_weak_decode(_m.snr, getattr(_m, 'raw', ''),
                        getattr(_m, 'freq_hz', 0),
                        self.settings.band, self.settings.mode)
```

### Cleanup in `main.py` neben debug_log (Z. 418-419)

```python
from core import weak_decode_log as _wdl
_wdl.cleanup_old_files(keep_days=7)
```

## FT8Message-Felder (verifiziert in core/message.py)

- `.snr` int, `.raw` str (z.B. "DL1ABC OE5XYZ -15"), `.freq_hz` int
- `.caller` = field2 (property)

## Decoder-Architektur-Kontext

`_on_cycle_decoded` bekommt eine BEREITS deduplizierte messages-Liste
(Decoder macht 3 Slide-Offsets + `seen`-Set-Dedup intern). Also kein
Doppel-Logging innerhalb eines Slots. Über mehrere Slots kann dieselbe
schwache Station mehrfach auftauchen — das ist gewollt (Mike will WANN/
WIE OFT sehen).

## Meine V2-Self-Review-Findings (offene Fragen an dich)

**SR1 (Batching?):** Ich rufe `log_weak_decode` pro schwacher Message auf
= 1 File-open/append/close pro Decode. Bei Pile-up (z.B. 20 schwache
Decodes/Slot) wären das 20 File-Opens pro 15s im GUI-Thread. Sollte ich
batchen (eine `log_weak_decodes(list)` die alle Zeilen eines Slots in
EINEM open schreibt)? Oder ist pro-Decode für Mike's Hobby-Use-Case
(meist wenige schwache Decodes) KISS-genug?

**SR2 (UTC vs lokal):** debug_log nutzt UTC. FT8 ist UTC-basiert. Aber
Mike denkt evtl. in lokaler Zeit beim Logbuch-Vergleich. UTC für
Konsistenz oder lokale Zeit für Mike-Lesbarkeit?

**SR3 (keep_days=7):** debug_log nutzt keep_days=1. Ich nehme 7 weil
schwache Decodes über mehrere Tage interessant sind (Trend). Sinnvoll?

## Fragen an dich

**F1:** Ist der Hook-Platz (`_on_cycle_decoded` nach assign_slot_parity)
korrekt? Laufen dort ALLE Decodes durch, oder gibt es einen früheren/
besseren Punkt (z.B. im Decoder selbst)?

**F2:** SR1 — batchen oder pro-Decode?

**F3:** SR2 — UTC oder lokal?

**F4:** Übersehe ich was? Race-Conditions? Edge-Cases (snr=None,
leeres raw, freq_hz=0)?

**F5:** Format-Vorschlag OK? `HH:MM:SS | +/-NN dB | <raw> | NNNN Hz | band mode`
Mike hat das Preview gesehen und gewählt.

**F6:** Soll WEAK_SNR_THRESHOLD eine Modul-Konstante bleiben oder besser
konfigurierbar? Mike will kein Setting — Konstante reicht?

Hart kritisch, KISS, kein Overengineering. „Weiß ich nicht" statt raten.
