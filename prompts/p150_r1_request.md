# P150 R1 — Decoder-Sensitivität durch kMin_score=10→4

## Kontext

SimpleFT8 (FT8 FlexRadio Hobby-Funker-Tool). Mike (DA1MHH) hat bei
heutiger Auswertung (33 QSOs Logbuch + AP-Lite-Diagnose) gesehen:
- Sein Decoder schafft schon -24 dB SNR (1× in 33 QSOs)
- Mike will marginale DX-Signale (Falklands, DXpeditionen) bei -22 bis -26 dB
  HÄUFIGER erkennen

AP-Lite-Experiment (eigener Matched-Filter über LDPC-Decoder) hat 0/16
Treffer geliefert. Du hast vorhin selbst gesagt: AP-Lite hat keine Nische
gegenüber LDPC-Decoder, stattdessen `kMin_score=10` senken.

## Was wir tun wollen

In `ft8_lib/libft8simple.c` an 3 Stellen (FT8, FT4, FT2):

```c
const int kMin_score = 10;   // ← in allen 3 Pfaden
```

→ ändern auf:

```c
const int kMin_score = 4;    // sicherer Startwert (WSJT-X Deep nutzt ~2.5)
```

## Was bleibt unverändert

- `kLDPC_iterations = 50` (bereits hoch)
- `kMax_candidates = 140` (bereits hoch)
- `kTime_osr = 2`, `kFreq_osr = 2` (Standard)
- Python-Seite `SUBTRACT_MIN_SNR = -18` und `MAX_SUBTRACT_PASSES = 5`
  bleiben unangetastet — eine Schraube nach der anderen

## Architektur Drumherum

Python-Schicht in `core/decoder.py` macht schon eine eigene Subtract-Loop:
```
5 Subtract-Passes × 3 Slide-Offsets (0, ±3600 Samples) × num_passes=1 in C
= 15 lib.decode-Aufrufe pro Slot
```

Bei jedem C-Aufruf macht `ft8s_decode` mit `num_passes=1` einen einzigen
Pass — also nutzen wir die interne C-Subtract-Logik NICHT, sondern die
Python-Logik. Das ist bewusstes Design.

## Build-Pipeline (validiert mit unverändertem Code, Test-Build OK)

```bash
cd ft8_lib

mkdir -p .build/fft
cc -O3 -DHAVE_STPCPY -I. -c -o .build/fft/kiss_fft.o  fft/kiss_fft.c
cc -O3 -DHAVE_STPCPY -I. -c -o .build/fft/kiss_fftr.o fft/kiss_fftr.c

cc -O3 -DHAVE_STPCPY -I. -dynamiclib -o ../libft8simple.dylib \
   libft8simple.c .build/ft8/*.o .build/common/*.o .build/fft/*.o
```

## V2-Self-Review (von mir, was ich schon bedacht habe)

1. **140-Kandidaten-Heap könnte volllaufen** bei mehr qualifizierten Sync-Patterns:
   ftx_find_candidates füllt den Heap nach Score-Reihenfolge — wenn mehr
   Sync-Patterns über Score 4 sind als 140, werden die schwächsten verworfen.
   Verhalten OK.

2. **FT4/FT2-Slots sind kürzer** als FT8 (7.5s / 3.8s vs 15s).
   Niedrigere Sync-Schwelle könnte bei kürzeren Slots stärkere
   Falsch-Decode-Wirkung haben? Oder ist Score-Skala normalisiert?

3. **App-Restart nötig** damit Mike den Unterschied sieht (dylib wird
   beim App-Start geladen). Test-Plan erwähnt das jetzt explizit.

## Fragen an dich

**F1 (kritisch):** Ist `kMin_score=4` der richtige Wert?
- 10 ist heute (zu konservativ, du hast gesagt -21 dB Limit)
- 2.5 ist WSJT-X Deep (du hast gesagt: Falsch-Decodes explodieren darunter)
- 4 ist mein Mittelweg
- Würdest du anders priorisieren? 3? 5? 6?

**F2 (Skala):** Score-Skala in kgoba's ftx_find_candidates — ist die für
FT8/FT4/FT2 gleich (Costas-Pattern-Korrelation in Waterfall) oder
unterscheidet sich die Empfindlichkeit pro Mode? Sollte ich für FT4/FT2
einen anderen Wert nehmen?

**F3 (Build):** Stimmt mein Build-Befehl? Insbesondere:
- `-O3` ist OK (kein Debug)
- `-DHAVE_STPCPY` aus dem Makefile übernommen
- Keine `-DFTX_DEBUG_PRINT` (das ist Debug-Build)
- ARM64-Apple-Silicon-Default funktioniert (Standard auf M1/M2)

**F4 (Verhalten):** Gibt es subtile Nebeneffekte die ich übersehen habe?
Z.B. Subtract-Pipeline könnte sich anders verhalten wenn mehr schwache
Decodes da sind?

**F5 (Falsch-Decode-Risiko):** Wie wahrscheinlich sind CRC-valide
Junk-Nachrichten bei kMin_score=4? Statistisch sollte CRC-14 → 1/16384
sein, aber bei tausenden Decodes pro Stunde könnte das real werden.

**F6 (Test):** Reicht meine Verifikation:
- (a) dylib lädt
- (b) Symbole sichtbar
- (c) volle Test-Suite 2171/2171 grün
- (d) optional: Audio-Dump-Replay (falls Mike welche hat)

Oder fehlt etwas Kritisches?

## Erwartet von dir

- Hart kritisches Review
- ROT/ORANGE/GELB Findings benennen
- Falls Wert anders soll: konkrete Empfehlung mit Begründung
- Falls Build-Befehl falsch: korrigieren
- KISS — kein Overengineering
- Keine Architekturänderungen außerhalb Scope
- Bei Unsicherheit "weiß ich nicht" statt raten
