# DT Time Correction

## In a Nutshell

SimpleFT8 uses the FT8 band itself as a time reference. The median DT (delta time) from all decoded stations reveals if your computer clock is drifting — and corrects it automatically.

## The Problem

FT8 requires precise timing. The protocol tolerates about +-1 second, but decoding quality degrades noticeably beyond +-0.5 seconds. Worse, your TX timing affects how well OTHER stations can decode YOU — sloppy timing means fewer PSKReporter spots and fewer answers to your CQ.

Several things work against you:

- **NTP is good but not enough.** It synchronizes your system clock to UTC, but it does not know about the audio processing latency between your software and your radio.
- **Your FlexRadio has latency.** Audio travels from the radio through VITA-49 UDP, through the OS audio stack, into SimpleFT8. That path is not instantaneous, and the delay is not constant.
- **Small drifts accumulate.** A 50ms drift per hour is invisible at first. After 4 hours of operating, you are 200ms off — enough to measurably affect decode rates.
- **No internet = no NTP.** Portable operation, contest field days, or simply a flaky internet connection — NTP is gone, and your clock is on its own.

## How It Works

Every decoded FT8 message comes with a DT value — the time offset between when the message should have arrived (based on your clock) and when it actually arrived. The decoder calculates this automatically during sync detection.

Here is the key insight: if ONE station shows DT = +0.4s, that station might have a bad clock. But if ALL 20 stations in a cycle show DT around +0.4s, the problem is not them — it is us. Our clock is 0.4 seconds behind the band consensus.

SimpleFT8 exploits this:

1. **Collect DT values** from all decoded messages in a cycle. Discard outliers (only values between -2.0s and +2.0s are valid).
2. **Require minimum 5 stations.** Below that, the sample is too small to trust.
3. **Take the median DT.** Not the average — the median (see below for why).
4. **Apply EMA smoothing** (exponential moving average, alpha = 0.3):
   ```
   new_correction = 0.7 * old_correction + 0.3 * median_dt
   ```
5. **Dead-band: 50ms.** If the absolute median DT is less than 50ms, no update is applied. This prevents the correction from chasing measurement noise.
6. **Adjust get_time().** The correction is added to all timing calculations. TX starts at the corrected time, accounting for both clock drift AND radio latency.

## Why Median, Not Average?

Consider a cycle with 20 decoded stations:

```
DT values: +0.3, +0.4, +0.3, +0.5, +0.4, +0.3, +0.4, +0.5, +0.4, +0.3,
           +0.4, +0.3, +0.5, +0.4, +0.3, +0.4, +0.3, +0.5, +0.4, +1.8
```

That last station has DT = +1.8s — probably a broken clock on their end, or QSB mangling the sync detection.

- **Average:** (sum / 20) = +0.46s — pulled upward by the one outlier.
- **Median:** +0.4s — completely ignores the outlier.

With 20+ stations per cycle, the median is extremely robust. Even if 5 stations have terrible timing, the median still reflects the majority consensus. This is the same reason median filters are used in image processing and sensor fusion — they are naturally resistant to outliers.

## The Math

The correction update follows an exponential moving average:

```
C_new = C_old * (1 - alpha) + DT_median * alpha
```

With alpha = 0.3:

```
C_new = C_old * 0.7 + DT_median * 0.3
```

This means:

- **30% of each new measurement** feeds into the correction.
- **70% of the previous correction** is retained.
- After a sudden shift, it takes about 5-7 cycles (~75-105 seconds) to converge to the new value (time constant = 1/alpha ≈ 3.3 cycles).
- The smoothing prevents the correction from jumping around due to measurement noise, while still tracking real drift.

Dead-band filter:

```
if |DT_median| < 0.050:  → no update (measurement noise)
```

Valid DT range:

```
-2.0s <= DT <= +2.0s  → valid (used for median calculation)
outside this range    → discarded (clearly broken station or sync error)
```

## Expected Gain

- Keeps TX timing within +-100ms of band consensus. Without correction, clock drift can reach 200-500ms over several hours.
- Better timing means receiving stations decode you more reliably. That translates directly to more PSKReporter spots and more answers to CQ.
- Self-calibrating: no NTP dependency, no GPS, no internet needed. The FT8 band IS the time reference. As long as other stations are transmitting (and they always are on active bands), the correction works.
- Automatically includes radio latency. NTP only corrects your system clock — it has no idea that your FlexRadio adds 50-150ms of audio processing delay. The DT correction sees the end-to-end timing as other stations perceive it.

## Pros and Cons

| Pro | Contra |
|-----|--------|
| Self-calibrating from real band activity | Needs minimum 5 stations per cycle |
| Includes radio audio latency automatically | First ~3 cycles: no correction (building up data) |
| No internet, NTP, or GPS required | Smoothing factor 0.3 may be too slow for sudden jumps or too fast for stable clocks |
| Robust median filter ignores outlier stations | 50ms dead-band means very small drifts are never corrected |
| Works on any band with FT8 activity | On a dead band with <5 stations, correction pauses |

## Status

**UNTESTED** — Code complete (v0.21, `core/ntp_time.py`), field validation needed.

Things to verify during field testing:
- **Sign convention:** Does positive DT_median mean our clock is late or early? The code assumes late (adds positive correction). If spots get worse after enabling, the sign is wrong.
- **Smoothing factor:** 0.3 might need tuning. Too high = jittery correction. Too low = too slow to track real drift.
- **Dead-band:** 50ms might be too conservative or too aggressive. Log the raw median DT values and check.

Watch for `[DT-Korr] Median=+X.XXXs -> Korrektur=+X.XXXs (n=XX)` in the log.
