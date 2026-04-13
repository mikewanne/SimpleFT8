# RMS Auto-Gain Control

## In a Nutshell

Automatic input level control that prevents the decoder from being overwhelmed on crowded bands (40m evenings) while maintaining sensitivity on quiet bands.

## The Problem

- 40m at 20:00 UTC: 50+ strong stations, combined audio power overloads the decoder.
- The decoder's spectral whitening expects a certain input level range.
- Too loud: whitening can't flatten the spectrum — strong signals mask weak ones.
- Too quiet: wasted dynamic range, weak signals fall below decoder threshold.
- Different bands have wildly different signal levels (80m evening vs 10m daytime).

## How It Works

- Measures RMS (Root Mean Square) power of 12 kHz audio after resampling.
- Target: -12 dBFS (= 8225 in int16 scale, roughly 25% of full scale).
- Adjusts gain slowly via EMA smoothing (alpha=0.02 — changes over ~50 cycles, not per-cycle).
- +/-3 dB hysteresis dead-band: small fluctuations don't trigger adjustment.
- Gain limits: 0.1x (-20 dB) minimum to 4.0x (+12 dB) maximum.
- Placement: AFTER 24->12 kHz resampling, BEFORE spectral whitening.

## The Math

RMS measures average signal power rather than peak amplitude. It is the right metric here because FT8 signals overlap in frequency and time — peak values tell you about the loudest station, but RMS tells you about the total energy the decoder has to deal with.

```
RMS = sqrt(mean(samples^2))
```

The AGC compares measured RMS against a fixed target and computes the gain it would need to hit that target:

```
Target RMS = 8225 (int16 scale, corresponds to -12 dBFS)
Desired gain = target / measured_rms
```

This desired gain is not applied directly. Instead, it feeds into an Exponential Moving Average (EMA) that smooths gain changes across many cycles:

```
gain_new = 0.02 * desired + 0.98 * gain_old
```

The EMA acts as a low-pass filter on gain changes. With alpha=0.02, the effective time constant is approximately 1/0.02 = 50 cycles = 50 x 15 seconds = 12.5 minutes. This means the AGC takes roughly 12 minutes to fully adapt to a new band condition.

The hysteresis prevents constant small corrections when the band is stable:

```
Ratio = desired_gain / ema_gain
Threshold = 10^(3/20) = 1.41 (i.e. 3 dB)
Update only if ratio > 1.41 or ratio < 1/1.41
```

Finally, clipping protection ensures no sample overflows int16 range:

```
output = clip(audio * gain, -32767, 32767)
```

## Why alpha=0.02 (Very Slow)?

- FT8 cycle = 15 seconds. AGC must NOT react within one cycle.
- Fast AGC would "pump": gain drops during a strong signal, recovers during the gap between signals, then drops again. This creates artificial amplitude modulation that the decoder sees as noise.
- alpha=0.02 gives an effective time constant of ~50 cycles = ~12.5 minutes.
- Adapts to slow changes (band opening/closing, day/night transitions) but ignores individual signals appearing and disappearing.
- Trade-off: When you switch bands, the AGC takes 2-3 minutes to settle. During those first cycles, the gain from the old band is still active. The gain limits (0.1x to 4.0x) prevent this from being catastrophic.

## Expected Gain

- Prevents decoder saturation on crowded bands — estimated +10-20% decodes on 40m evenings.
- Maintains sensitivity on quiet bands — weak DX not lost to insufficient gain.
- UNTESTED — estimates based on simulation, field validation needed.

## Pros and Cons

| Pro | Contra |
|-----|--------|
| Automatic, no user adjustment needed | Very slow response (~12 min time constant) |
| Prevents decoder overload on crowded bands | Interacts with existing noise-floor normalization |
| Clipping protection built-in | On silent band: gain ramps to 4x max (recovers when signals appear) |
| Band-change: adapts within 2-3 minutes | — |

## Status

UNTESTED — Active since v0.27. Watch `[AGC] Gain=X.XXx` in log.
