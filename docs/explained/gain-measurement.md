# Gain Measurement — Automatic Preamp Optimization

## In a Nutshell

DX Tuning measures the optimal preamp gain for each antenna on the current band. It takes 4.5 minutes, runs in the background, and saves the results as per-band presets that are loaded automatically on every band change.

## The Problem

Every antenna behaves differently on every band. The preamp gain setting that gives you the best weak-signal reception on 20m might add too much noise on 40m, or overdrive the ADC on 10m. Most operators set their preamp once and leave it — but conditions change with weather, time of day, and season.

Without measurement, you are guessing. With measurement, you know.

## What DX Tuning Measures

DX Tuning tests **both antennas** at **three gain settings** (0 dB, 10 dB, 20 dB) and determines:

- Which gain level produces the best average SNR on ANT1
- Which gain level produces the best average SNR on ANT2
- Which antenna + gain combination is the overall winner

The results tell you: "On 20m right now, ANT2 at 0 dB gain gives the best reception."

## How to Run a Measurement

1. Click the **DX Tuning** button in the antenna panel.
2. Optionally, use TUNE first to check SWR on your antennas.
3. The measurement dialog opens and runs automatically.
4. Wait 4.5 minutes (18 FT8 cycles). You can watch the progress in real time.
5. When finished, click **Preset speichern** to save the results.

You can abort at any time by clicking **Abbrechen**. The radio returns to its previous settings.

## How It Works Internally

The measurement runs 3 rounds of 6 cycles each (18 cycles total):

```
Round 1: ANT1@0dB → ANT2@0dB → ANT1@10dB → ANT2@10dB → ANT1@20dB → ANT2@20dB
Round 2: ANT2@0dB → ANT1@0dB → ANT2@10dB → ANT1@10dB → ANT2@20dB → ANT1@20dB
Round 3: ANT1@0dB → ANT2@0dB → ANT1@10dB → ANT2@10dB → ANT1@20dB → ANT2@20dB
```

The interleaved pattern ensures ANT1 and ANT2 are measured under nearly identical propagation conditions. The alternating round order (ANT1 first, then ANT2 first) further reduces timing bias.

For each antenna + gain combination, SimpleFT8 collects all decoded station SNR values and calculates the **Top-5 average SNR** — the mean of the five strongest signals. This metric reflects real-world DX reception quality better than total station count.

### ADC Overload Detection

If a gain setting causes ADC overloading (too many signals above +20 dB, or suspiciously low SNR variance), that combination is automatically excluded from the results. The dialog shows a warning marker for overloaded steps.

## Results and Presets

After measurement, you see a summary like:

```
ANT1:
  ANT1 Gain  0 dB:  Ø  -0.8 dB  (13 St.)
  ANT1 Gain 10 dB:  Ø  -4.6 dB  ( 8 St.)
  ANT1 Gain 20 dB:  Ø  +1.6 dB  ( 9 St.)  ←
ANT2:
  ANT2 Gain  0 dB:  Ø  +3.0 dB  (25 St.)  ←
  ANT2 Gain 10 dB:  Ø  +7.6 dB  (21 St.)
  ANT2 Gain 20 dB:  Ø  +1.2 dB  (11 St.)
```

The arrows show the optimal gain for each antenna. When you save the preset, SimpleFT8 stores both values per band. Diversity mode then uses the correct gain when switching antennas: ANT1's optimal gain when receiving on ANT1, ANT2's optimal gain when receiving on ANT2.

Presets are loaded automatically when you switch bands.

## When to Re-Measure

| Situation | Recommendation |
|-----------|----------------|
| Daily DX operation | Measure once at the start of your session |
| After antenna changes | Always re-measure (hardware changed) |
| After significant weather | Rain, ice, or storm can shift antenna performance |
| Seasonal changes | Propagation paths shift, different antennas may perform better |
| Reception seems worse than usual | Quick re-measure to verify settings |

The measurement takes only 4.5 minutes and runs in the background — you continue receiving normally. There is no reason not to measure.

## Gain Measurement vs. Diversity

These two features work together but measure different things:

| Feature | What it measures | Result |
|---------|------------------|--------|
| **Gain Measurement** | Hardware performance: which preamp setting is best for each antenna | Optimal dB gain per antenna per band |
| **Diversity** | Propagation performance: which antenna receives more stations right now | Antenna switching ratio (50:50, 70:30, etc.) |

Run Gain Measurement first to find the optimal hardware settings. Then let Diversity use those settings to switch antennas based on propagation.

## Technical Details

- TX stays on ANT1 throughout the measurement (only RX antenna switches).
- The first cycle is skipped (it may be an incomplete FT8 slot from before the measurement started).
- Gain is set via the FlexRadio SmartSDR API `rfgain` parameter.
- Each combination gets 3 measurement cycles spread across 3 rounds, for a total of 9 decoded station lists per antenna.
- Results are saved in the SimpleFT8 settings file and persist across restarts.
