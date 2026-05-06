# SimpleFT8 DT-Drift +0.76s — Wurzel-Analyse-Konsultation

**Kontext:** SimpleFT8, FT8 Hobby-Tool. FlexRadio 6500 + macOS. Mike hat
seit kurzem eine Restdrift von ~+0.76s die in `dt_corrections.json` als
1.0 (clamped auf `_MAX_CORR["FT8"]`) gespeichert wird.

**Vorher (23.04.2026, validiert in Commit `38a55b2`):**
- DT-Korrektur konvergierte auf ~0.24s
- Stationen-DT zeigte konsistent -0.1 bis +0.2

**Heute (06.05.2026, v0.95.6):**
- DT-Korrektur clamped bei 1.0s in `dt_corrections.json` für alle FT8-Bänder
- Mike empfindet DT-Werte „über 1 Sekunde"

**System-Zeit:** Mike: 100 % korrekt (NTP synced). Firmware: NICHT geändert.

## Code-Vergleich (Golden Stand vs HEAD)

| Konstante | `38a55b2` (23.04., DT validiert ✓) | HEAD (heute) | Differenz |
|---|---|---|---|
| `core/decoder.py:_DT_OFFSETS["FT8"]` (DT_BUFFER_OFFSET) | **2.0** | **2.0** | gleich ✓ |
| `core/decoder.py:_WAKE_OFFSETS["FT8"]` (Decoder-Wake) | **1.5** | **2.5** | **+1.0s** ⚠️ |

`_WAKE_OFFSETS["FT8"]` wurde von 1.5 auf 2.5 erhöht in Commit `20c7fe7`
(P1.9 First-Reply-Lost-Bug-Fix, v0.95.3, 05.05.2026). Begründung damals:
Decoder wachte 0.2-3.0s NACH Encoder fertig → Encoder-Replace-Pfad nicht
nutzbar. Fix: Decoder wacht 1s früher auf.

## Code-Kommentar Beweis (decoder.py:316-322 ist NICHT aktualisiert worden!)

```python
# dt korrigieren:
# 1) Offset-Verschiebung rueckgaengig machen (Window-Sliding)
# 2) Buffer-Offset: Decode-Loop wacht 1.5s vor Slot-Ende auf →
#    Buffer startet 1.5s VOR Slot-Start → DT um +1.5 zu hoch
# 3) WSJT-X Protokoll: TX startet bei t=+0.5s im Slot →
#    Protokoll-Offset 0.5s direkt eingerechnet (= 1.5 + 0.5)
# Ergebnis: Korrektur konvergiert nur noch auf ~0.27s (Hardware)
# statt 0.77s (Hardware + Protokoll-Offset)
_DT_OFFSETS = {"FT8": 2.0, "FT4": 1.0, "FT2": 0.8}
```

Der Kommentar sagt explizit `1.5 + 0.5 = 2.0`. Aber `_WAKE_OFFSETS["FT8"]`
ist jetzt `2.5`. Wenn die Math korrekt sein soll, müsste `_DT_OFFSETS["FT8"]`
auf `2.5 + 0.5 = 3.0` erhöht werden — wurde aber nicht.

**Mein Hypothese:** `DT_BUFFER_OFFSET` ist um 1.0s zu klein, weil bei v0.95.3
`_WAKE_OFFSETS["FT8"]` 1.5 → 2.5 erhöht wurde aber `_DT_OFFSETS["FT8"]`
nicht entsprechend mit-erhöht wurde. Daher braucht die DT-Korrektur jetzt
zusätzliche +1.0s die clamped sind auf `_MAX_CORR["FT8"]` = 1.0.

## Decoder-Audio-Pipeline (relevante Stellen)

```python
# decoder.py:145-156 (Wake + target_slot_start)
_WAKE_OFFSETS = {"FT8": 2.5, "FT4": 0.5, "FT2": 0.3}
_WAKE = _SLOT - _WAKE_OFFSETS.get(self._mode, 1.5)  # = 12.5 für FT8
cycle_pos = now % _SLOT
if cycle_pos < _WAKE:
    target_slot_start = now - cycle_pos          # selber Slot
    wait = _WAKE - cycle_pos
else:
    target_slot_start = now - cycle_pos + _SLOT  # nächster Slot
    wait = _SLOT - cycle_pos + _WAKE
time.sleep(wait)
# → Decoder wacht bei slot_pos = 12.5s (statt vorher 13.5s)
```

```python
# decoder.py:316-329 (DT-Berechnung)
_DT_OFFSETS = {"FT8": 2.0, "FT4": 1.0, "FT2": 0.8}
DT_BUFFER_OFFSET = _DT_OFFSETS.get(self._mode, 2.0)
raw_results.append({
    **r,
    "dt": r["dt"] + offset_samples / SAMP_RATE - DT_BUFFER_OFFSET,
    "freq_hz": r["freq_hz"],
})
```

```python
# core/ntp_time.py:36 (Korrektur-Clamp)
_MAX_CORR = {"FT8": 1.0, "FT4": 0.5, "FT2": 0.3}
```

## Meine 3 konkreten Fragen an dich (DeepSeek)

### Q1: Ist die Hypothese korrekt?
Hängt `DT_BUFFER_OFFSET` direkt vom `_WAKE_OFFSETS` ab? Wenn `_WAKE_OFFSETS["FT8"]`
um 1.0s erhöht wurde, muss `_DT_OFFSETS["FT8"]` ebenfalls um 1.0s erhöht werden,
damit die DT-Berechnung korrekt bleibt? Oder gibt es einen anderen Mechanismus
der das kompensiert (z.B. Audio-Buffer-Slicing, Zero-Padding) den ich übersehe?

Bitte verifiziere am Code:
- Wo wird `target_slot_start` zum Audio-Buffer in Beziehung gesetzt?
- Padding bei `audio_12k` (Z.217-225 — wenn weniger Samples als slot_samples,
  Padding hinten dazu) — verändert das die DT-Math?
- DT-Korrektur-Shift Z.227-238 (Audio-Buffer-Verschiebung statt Sleep-Offset).

### Q2: Falls Hypothese stimmt — der Fix
Reicht es, `_DT_OFFSETS["FT8"]` von 2.0 auf 3.0 zu erhöhen? Oder gibt es
Folgewirkungen (FT4/FT2 wurden NICHT geändert in P1.9, dort `_WAKE_OFFSETS`
weiterhin 0.5/0.3 = vermutlich wäre `_DT_OFFSETS` für die unverändert).

Side-Effect-Check:
- TX-Timing wird durch DT-Korrektur via `ntp_time.get_correction()` beeinflusst.
  Wenn DT-Korrektur jetzt korrekt ~0.24s wäre statt 1.0s clamped, würde TX
  um 0.76s früher gesendet → das wäre RICHTIG (entspricht dem korrigierten
  Slot-Anfang).

### Q3: Falls die Hypothese FALSCH ist — was sonst?
Hast du eine andere Erklärung für den +0.76s-Drift, der EXAKT zwischen
v0.95.3 (Wake-Offset-Änderung) und heute aufgetreten ist? Mögliche
Alternativen:
- v0.95 Slot-Source-Refactor (`_slot_start_ts` von Decoder durchgereicht)
- v0.95.1 Encoder-TX-Slot-Tag-Fix (`tx_started.emit()` mit `next_boundary`)
- v0.95.3 Encoder-Replace-Logik (`request_replace`)
- Anderer Commit zwischen 23.04. und heute

**Antworte präzise mit Code-Referenzen. Keine generischen Hypothesen.
Wenn du etwas nicht im Code findest, sag „nicht im Kontext".**

**Sprache: Deutsch.**
