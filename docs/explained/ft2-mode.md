# FT2 Mode (Decodium-Compatible)

## What is FT2?

FT2 is an ultra-fast digital mode with **3.8-second cycles** — roughly 4 times faster than FT8. Developed by IU8LMC (ARI Caserta, Italy), it uses the same encoding as FT4 but at double the symbol rate.

## Compatibility

SimpleFT8's FT2 implementation is **compatible with Decodium 3.0** (the original FT2 software).

| Parameter | FT8 | FT4 | FT2 |
|-----------|-----|-----|-----|
| Cycle time | 15.0s | 7.5s | **3.8s** |
| Tones | 8 | 4 | **4** |
| Symbols | 79 | 105 | **105** |
| Samples/Symbol | 1920 | 576 | **288** |
| Bandwidth | ~50 Hz | ~83 Hz | **~167 Hz** |
| Sensitivity | -21 dB | -17.5 dB | **-12 dB** |

**Important:** There are two incompatible FT2 versions. SimpleFT8 supports **Decodium** (4-GFSK, Costas sync). It does NOT work with "WSJT-X Improved FT2" (different modulation).

## Frequencies

| Band | FT2 Frequency |
|------|--------------|
| 80m | 3.578 MHz |
| 40m | 7.052 MHz |
| 20m | 14.084 MHz |
| 15m | 21.144 MHz |
| 10m | 28.184 MHz |

## How to Use

1. Click **FT2** in the mode selector
2. Radio tunes to the FT2 frequency automatically
3. RX filter widens to **4000 Hz** (vs 3100 Hz for FT8/FT4)
4. DT correction loads stored FT2 value (if available)
5. Even/Odd slots work exactly like FT8 — just 4x faster

## Clock Accuracy

FT2 requires **50ms clock accuracy** (vs 200ms for FT8). SimpleFT8's DT correction handles this automatically. After 2 measurement cycles (~8s), the correction is active.

## When to Use FT2

**Good for:**
- Strong signals, contest-style pile-ups
- High QSO throughput (up to 240 QSOs/hour theoretical)
- DXpeditions and special events

**Not ideal for:**
- Weak-signal DX (use FT8 instead, -21 dB sensitivity)
- Bands with low activity (few FT2 stations on most bands)
- Systems with poor clock sync

## Technical Details

- Modulation: 4-GFSK (same as FT4)
- FEC: LDPC(174,91) with 14-bit CRC
- Sync: 4 Costas arrays (same as FT4)
- C library: Native `FTX_PROTOCOL_FT2` in ft8_lib (no resampling tricks)
