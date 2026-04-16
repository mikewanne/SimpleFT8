# Diversity Modes — Standard vs. DX Scoring

## In a Nutshell

SimpleFT8's Diversity feature switches between two antennas every FT8 cycle to receive more stations. The **scoring mode** determines how it decides which antenna is better: Standard mode counts all stations (best for CQ and contests), DX mode counts only weak stations below -10 dB SNR (best for DX hunting).

## Two Scoring Modes

| Mode | What counts | Best for | Button shows |
|------|-------------|----------|--------------|
| **Standard** | All decoded stations (SNR > -20 dB) | CQ operation, contests, general use | DIVERSITY |
| **DX** | Only weak stations (SNR < -10 dB) | DX hunting, rare stations, long paths | DIVERSITY DX |

Toggle between modes by clicking the Diversity button. The mode is shown on the button label.

## Standard Mode — Count Everything

In Standard mode, the antenna that decodes **more total stations** is considered better. This makes sense for general operation: if ANT1 decodes 25 stations and ANT2 decodes 18, ANT1 has better overall coverage right now.

Use Standard mode when:
- Running CQ and you want to hear as many callers as possible
- Operating in a contest where every contact counts
- You simply want the best overall reception

## DX Mode — Count Weak Signals

In DX mode, only stations with SNR below -10 dB count. These are the weak, distant stations — the DX you are hunting for. A strong local station at +15 dB does not count because you will hear that station on any antenna.

Use DX mode when:
- Hunting for rare DX or new DXCC entities
- Working long-path openings where signals are marginal
- You care about reaching distant stations, not about station count

**Example:** ANT1 decodes 25 stations total, 3 of them below -10 dB. ANT2 decodes 18 stations total, 7 of them below -10 dB. In Standard mode, ANT1 wins (25 > 18). In DX mode, ANT2 wins (7 > 3) — it receives more weak DX stations.

## How the Measurement Works

Both modes use the same 8-cycle measurement process:

1. **4 cycles on ANT1** (2 even + 2 odd slots): collect scores
2. **4 cycles on ANT2** (2 even + 2 odd slots): collect scores
3. **Evaluate:** Compare median scores for each antenna

The measurement alternates: A2, A1, A2, A1, A2, A1, A2, A1 — ensuring both antennas are measured under similar propagation conditions.

### Median Scoring

SimpleFT8 uses the **median** of all measurements per antenna, not the average. The median is robust against outliers — one unusually good or bad cycle does not distort the result. With 4 measurements per antenna, the median gives a reliable picture.

### The 8% Threshold

After measurement, SimpleFT8 compares the two median scores:

```
relative_difference = |score_A1 - score_A2| / max(score_A1, score_A2)
```

| Difference | Result | Ratio |
|------------|--------|-------|
| Less than 8% | Antennas are effectively equal | 50:50 |
| 8% or more | One antenna is clearly better | 70:30 in favor of the better one |

The 8% threshold prevents unnecessary bias when both antennas perform similarly.

## Operating Ratios

Once measurement is complete, SimpleFT8 enters the **operate phase** and switches antennas according to the ratio:

| Ratio | Pattern (per 10 cycles) | Meaning |
|-------|------------------------|---------|
| **50:50** | A1, A1, A2, A2, A1, A1, A2, A2, ... | Both antennas get equal time |
| **70:30** | A1, A1, A2, A1, A1, A2, A1, A1, A2, A1 | Dominant antenna gets 7 of 10 cycles |
| **30:70** | A2, A2, A1, A2, A2, A1, A2, A2, A1, A2 | ANT2 dominant, same pattern reversed |

The 50:50 pattern uses 2-cycle blocks so both even and odd slots are covered on each antenna. The 70:30 pattern distributes the minority antenna's cycles evenly to maintain diversity benefit.

## Automatic Re-Measurement

After **60 cycles** of operation (approximately 15 minutes), SimpleFT8 automatically starts a new measurement — but only if no QSO is active. Active QSOs are never interrupted.

This ensures the antenna ratio adapts to changing propagation. What was the better antenna 15 minutes ago may not be the better antenna now.

## Band Changes

When you switch bands, the Diversity controller resets completely and starts a fresh measurement. This is necessary because antenna performance on 20m has no relation to performance on 40m.

## Reading the Display

The control panel shows the current Diversity state:

- **Measuring (4/8):** Measurement phase, step 4 of 8
- **50:50 (42/60):** Operating in equal ratio, cycle 42 of 60 until re-measurement
- **70:30 A1 (15/60):** ANT1 dominant at 70:30, cycle 15 of 60

The LED bar or ratio label changes color based on status:
- Green: dominant antenna clearly winning
- Teal/Blue: 50:50, both antennas similar
- Yellow: measurement in progress

## Tips for Operators

- **Start with Standard mode** for your first session. Switch to DX mode only when actively hunting DX.
- **Run Gain Measurement first** (DX Tuning) before enabling Diversity. Diversity works best when each antenna already has its optimal preamp setting.
- **Different antennas help most.** A vertical and a dipole will give more diversity gain than two identical dipoles on the same mast.
- **Do not disable Diversity during a QSO.** The system protects active QSOs automatically and will not re-measure while you are in the middle of a contact.
- **Watch the ratio over time.** If it consistently shows 70:30 in favor of one antenna, that antenna is simply better on this band right now. If it keeps flipping, conditions are changing rapidly — Diversity is doing its job.
