# Diversity Modes — Normal, Standard and DX

## All three modes at a glance

Which mode should I use? Quick answer:

| Situation | Mode |
|-----------|------|
| I only have one antenna | **Normal** |
| I want to hear as many stations as possible | **Diversity Standard** |
| I'm specifically chasing distant, weak stations | **Diversity DX** |
| I want to compare SimpleFT8 to other software | **Normal** as baseline |

### Normal — the baseline mode

Normal uses a single antenna and behaves exactly like WSJT-X, JS8Call, or any other standard FT8 software. You need it as a starting point: if you don't know how good your reception is in the first place, you can't measure progress. Measure with Normal first, then switch to Diversity — the difference is immediately visible.

### Diversity Standard — for the masses

With two antennas, the system automatically picks the antenna decoding **more stations** each round. You don't just get more from the same antenna — you automatically get the best of both. Real measurements show 15–30% more stations than Normal.

### Diversity DX — for the quiet ones

Also two antennas, but the selection criterion is different: the system picks the antenna that **catches weak signals best** — stations with a signal just above the noise floor (SNR below −10 dB). A strong local station two kilometers away doesn't count because you'd hear it anyway. What counts are the quiet signals from thousands of kilometers.

**When Standard, when DX?**
Imagine collecting bird species in a forest. Standard counts every bird — the more, the better. DX counts only the rare species deep in the forest, barely audible. If you just want to operate actively and rack up QSOs → Standard. If you're targeting a specific rare DX entity → DX.

**Why does Standard sometimes show fewer stations than DX?**
In measurements it occasionally looks like DX has more stations than Standard. That's not because DX counts better — it's the measurement timing. If Standard is measured at 07:20 (band peak) and DX at 07:50 (band already weakening), Standard shows more. Reverse can happen too. Over many measurement days this evens out. Across 6 shared measurement hours, DX beat Normal in 5 of 6 cases — for *station count*, not just weak signals.

---

## Technical summary

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

## Antenna markers in the RX panel

Each station in the RX panel shows which antenna decoded it:

- **A1** — heard only on ANT1
- **A2** — heard only on ANT2
- **A1>2** — heard on both, ANT1 had better SNR
- **A2>1** — heard on both, ANT2 had better SNR

This lets you see immediately which stations would not have been
received at all (or only worse) without the second antenna —
diversity gain visible live in the RX window.

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

## Antenna-Pref — the learning memory

Diversity is not a simple switch. After every decode cycle SimpleFT8 remembers, per callsign, which antenna received that station better — and by how many dB.

That's the point: the global Diversity decision (which antenna currently has more stations / more weak signals) is an average across everyone. But if DL3AQJ comes from northern Germany and your ANT2 points north, ANT2 might be 6 dB better for that one station — regardless of what the rest of the band says.

**How it works:**

```
Without Diversity:    Always antenna 1 — no matter what's happening.
Diversity Standard:   Every 15 s: which antenna receives more stations? Use that.
Diversity DX:         Every 15 s: which antenna hears the weakest signals? Use that.
+ Antenna-Pref:       System remembers — "DL3AQJ always comes in better on ANT2".
                      On QSO start, the right antenna is selected automatically.
```

**When does it switch?** Only at cycle boundaries (never mid-decode). During an active QSO the antenna stays fixed, the global Diversity rhythm is temporarily overridden. After QSO end: back into the normal cycle.

**No memory, no timeout.** When a station is received, the value is at most 15 seconds old — you can't get more precise. If it's not received, there's nothing to call. Historical values are useless.

**Waitlist:** When multiple stations call simultaneously, SimpleFT8 cycles between them — and each time on the matching antenna preference.

In the QSO panel you see which antenna was used: `Calling DL3AQJ (ANT2, +6.3 dB)`. In the status bar: `RX: A2 (+6.3 dB)`.

## Tips for Operators

- **Start with Standard mode** for your first session. Switch to DX mode only when actively hunting DX.
- **Run Gain Measurement first** (DX Tuning) before enabling Diversity. Diversity works best when each antenna already has its optimal preamp setting.
- **Different antennas help most.** A vertical and a dipole will give more diversity gain than two identical dipoles on the same mast.
- **Do not disable Diversity during a QSO.** The system protects active QSOs automatically and will not re-measure while you are in the middle of a contact.
- **Watch the ratio over time.** If it consistently shows 70:30 in favor of one antenna, that antenna is simply better on this band right now. If it keeps flipping, conditions are changing rapidly — Diversity is doing its job.
