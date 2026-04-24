# Frequency Histogram & CQ Frequency Selection

[Back to README](../README.md) | [Diversity](DIVERSITY.md) | [DX Tuning](DX_TUNING.md) | [DT Correction](DT_CORRECTION.md)

## What You See

The histogram in the top-right panel shows which audio frequencies (150–2800 Hz) are currently occupied by other stations. It reflects exactly the same stations visible in the RX table — no more, no less.

**Color coding:**
- **Gray** — one station in this 50 Hz slot
- **Orange** — two to three stations
- **Red** — four or more stations (congested)
- **Yellow marker** — your proposed CQ frequency (a free gap)

## Data Source: Real-Time, 1:1 with the RX Table

The histogram is rebuilt from the station accumulator every decode cycle. The station accumulator holds stations for:
- **75 seconds** — normal stations
- **150 seconds** — stations involved in your active QSO
- **300 seconds** — CQ callers

This means the histogram naturally covers several recent cycles, including both Even and Odd slots. If a station ages out of the RX table, it also disappears from the histogram. What you see in the histogram matches what you see in the RX panel.

## How the Free CQ Frequency Is Found

SimpleFT8 scans the full audio range (150–2800 Hz) for gaps — frequency ranges with no active stations. A gap must be at least 150 Hz wide to be considered usable.

From all valid gaps, the one **closest to the median activity frequency** is chosen. If most stations are around 1200 Hz, the algorithm picks the nearest free slot to that center of gravity — not the nearest slot to 0 Hz or 3000 Hz.

**If no gap is found** (extremely busy band), the current TX frequency is kept unchanged.

## When the Frequency Is Recalculated

| Trigger | Condition |
|---------|-----------|
| **First use** | On first CQ after switching band or mode |
| **Collision** | ≥ 3 stations appear within ±50 Hz of your TX frequency (after a minimum of 3 cycles dwell) |
| **Timer** | Every 10 cycles (~150 s for FT8, ~75 s for FT4, ~38 s for FT2) |
| **QSO protection** | No recalculation while a QSO is active |

The algorithm is intentionally conservative: it stays on a chosen frequency as long as it remains free, and only moves when forced.

## Technical Details

| Parameter | Value |
|-----------|-------|
| Bin width | 50 Hz |
| Search range | 150–2800 Hz |
| Minimum gap | 150 Hz (3 bins) |
| Recalculation interval | 10 cycles |
| Minimum dwell | 3 cycles before collision check |
| QSO protection | Active while QSO state is not IDLE/TIMEOUT |
