# FT2-Modus (Decodium-kompatibel)

## Was ist FT2?

FT2 ist ein ultraschneller Digitalmodus mit **3,8-Sekunden-Zyklen** — etwa 4x schneller als FT8. Entwickelt von IU8LMC (ARI Caserta, Italien), nutzt es die gleiche Kodierung wie FT4 aber mit doppelter Symbolrate.

## Kompatibilitaet

SimpleFT8 ist **kompatibel mit Decodium 3.0** (der originalen FT2-Software).

| Parameter | FT8 | FT4 | FT2 |
|-----------|-----|-----|-----|
| Zykluszeit | 15,0s | 7,5s | **3,8s** |
| Toene | 8 | 4 | **4** |
| Symbole | 79 | 105 | **105** |
| Samples/Symbol | 1920 | 576 | **288** |
| Bandbreite | ~50 Hz | ~83 Hz | **~167 Hz** |
| Empfindlichkeit | -21 dB | -17,5 dB | **-12 dB** |

**Wichtig:** Es gibt zwei inkompatible FT2-Versionen. SimpleFT8 unterstuetzt **Decodium** (4-GFSK, Costas-Sync). Es funktioniert NICHT mit "WSJT-X Improved FT2" (andere Modulation).

## Frequenzen

| Band | FT2-Frequenz |
|------|-------------|
| 80m | 3,578 MHz |
| 40m | 7,052 MHz |
| 20m | 14,084 MHz |
| 15m | 21,144 MHz |
| 10m | 28,184 MHz |

## Bedienung

1. Klicke auf **FT2** im Modus-Waehler
2. Das Radio stimmt automatisch auf die FT2-Frequenz ab
3. Der RX-Filter wird auf **4000 Hz** verbreitert (statt 3100 Hz bei FT8/FT4)
4. Die DT-Korrektur laedt den gespeicherten FT2-Wert (falls vorhanden)
5. Even/Odd-Slots funktionieren genau wie bei FT8 — nur 4x schneller

## Uhr-Genauigkeit

FT2 benoetigt **±50ms Genauigkeit** (FT8: ±200ms). SimpleFT8s DT-Korrektur erledigt das automatisch. Nach 2 Messzyklen (~8s) ist die Korrektur aktiv.

## Wann FT2 verwenden?

**Gut fuer:**
- Starke Signale, Contest-Pile-Ups
- Hoher QSO-Durchsatz (theoretisch bis 240 QSOs/Stunde)
- DXpeditionen und Sonderveranstaltungen

**Nicht ideal fuer:**
- Schwachsignal-DX (FT8 nutzen, -21 dB Empfindlichkeit)
- Baender mit wenig Aktivitaet (wenige FT2-Stationen)
- Systeme mit schlechter Zeitsynchronisation

## Technische Details

- Modulation: 4-GFSK (wie FT4)
- FEC: LDPC(174,91) mit 14-Bit CRC
- Sync: 4 Costas-Arrays (wie FT4)
- C-Library: Nativer `FTX_PROTOCOL_FT2` in ft8_lib (keine Resample-Tricks)
