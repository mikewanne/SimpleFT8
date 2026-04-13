# Frequency Drift Compensation

## In a Nutshell

Cheap QRP transceivers (QRP Labs QCX, uBITX, etc.) have unstable oscillators that drift 0.5-5 Hz during a 15-second FT8 slot. SimpleFT8 compensates this drift, recovering signals that standard decoders miss.

## The Problem

- FT8 uses 79 symbols over 12.64 seconds, each transmitted at a precise frequency.
- The LDPC decoder expects stable frequency — drift smears symbol energy across FFT bins.
- At 6.25 Hz tone spacing, even 1 Hz of drift means 16% frequency error.
- Our FlexRadio has a GNSS-locked oscillator (zero drift), but the *transmitting* station drifts.
- Result: We fail to decode signals from cheap radios that would otherwise be above the noise floor.

## How Drift Affects Decoding

FT8 tone spacing is 6.25 Hz. That number matters because it sets the scale for how much drift the decoder can tolerate before things fall apart.

- **1 Hz drift** over 12.64 seconds shifts the last symbol by 1/6.25 = **16%** of a bin width. The decoder still copes, but you are already eating into your margin.
- **3 Hz drift** shifts it by 48% — nearly half a bin. At this point the symbol lands almost exactly between two FFT bins, and decode reliability drops sharply.
- **5 Hz drift** puts you at 80%. The signal is essentially in the wrong bin for the final symbols.

LDPC error correction is powerful, but it is designed for random noise, not systematic bias. Drift does not scramble random bits — it progressively shifts every symbol in the same direction, which accumulates errors the LDPC cannot easily repair.

## How SimpleFT8 Compensates

Drift compensation runs as a second stage, after the normal decode pipeline has finished.

1. **Normal decode** runs first (standard pipeline, no drift correction).
2. **Signal subtraction** removes all successfully decoded stations from the audio.
3. On the **residual audio** (everything the normal decoder could not crack), apply linear drift correction at 4 rates: +0.5, -0.5, +1.5, -1.5 Hz/s.
4. For each corrected version, run the full decoder again.
5. Any new decodes are stations that were missed due to drift.

Because it runs on residual audio only, drift compensation never interferes with normal decodes. Stations with stable oscillators are decoded in step 1 and subtracted before step 3 even begins.

### The Math

A linear frequency drift *d* (Hz/s) produces a quadratic phase shift in the signal:

```
phi(t) = 2*pi * (f0*t + d/2 * t^2)
```

The first term is the carrier frequency. The second term is the drift — it grows with the square of time, which is why even a small drift rate causes significant frequency error by the end of a 12.64-second transmission.

To remove the drift, we multiply the signal by the complex conjugate of the drift component:

```
correction(t) = exp(-j*pi * d * t^2)
```

This cancels the quadratic phase, collapsing the drifted signal back to a fixed frequency.

Since our audio is real-valued (not complex IQ), the implementation first converts to an analytic signal using the Hilbert transform (FFT-based), applies the correction in the complex domain, then takes the real part to get back to real audio. The corrected audio then goes through the normal decode pipeline as if the station had never drifted.

### Why These Specific Drift Rates?

The four rates (+/-0.5 and +/-1.5 Hz/s) are not arbitrary:

- **+/-0.5 Hz/s** covers 0-6 Hz total drift over a 12.64s slot. This is the typical range for crystal oscillators warming up or responding to temperature changes — the most common scenario with budget QRP kits.
- **+/-1.5 Hz/s** covers 0-19 Hz total drift. This catches extreme cases: cheap LC VFOs, kits with poor thermal management, or stations operating outdoors in changing temperatures.

Together, these four rates cover an estimated 80-90% of real-world QRP station drift. We do not need to cover every possible rate — LDPC can tolerate residual error of a few percent of a bin, so getting close enough is sufficient.

## Expected Gain

- Estimated **+5-10% more decodes** on bands with QRP activity (40m, 20m).
- Strongest effect on marginal signals (-20 to -24 dB SNR) from drifting stations — these are the signals that are just barely above the decode threshold and get pushed below it by drift.
- Zero effect on stations with stable oscillators (most commercial radios). Those are already decoded in the normal pass.
- **UNTESTED** — these are theoretical estimates based on the math and typical QRP oscillator specs. Field validation is pending.

## Performance Impact

- 4 extra decode passes on residual audio (one per drift rate).
- Each pass takes approximately 100ms (C library backend, fast).
- Total additional time: ~400ms per 15-second cycle.
- Well within budget — total decode time is typically 500-1000ms, and the 15-second cycle leaves plenty of headroom.

## Pros and Cons

| Pro | Contra |
|-----|--------|
| Recovers signals from cheap QRP radios | +400ms decode time per cycle |
| Fully automatic, no user configuration needed | Theoretical: may produce rare false decodes |
| Runs on residual audio only (does not affect normal decodes) | UNTESTED — needs field testing |
| Helps the "little guy" with budget equipment | No effect on stations that do not drift |

## Status

**UNTESTED** — Implemented in v0.30, field validation pending.
Watch for `[Drift] +N Stationen` in the log to see if drift compensation is finding additional decodes.
