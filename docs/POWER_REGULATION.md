# Auto TX Power Regulation

[Back to README](../README.md) | [Diversity](DIVERSITY.md) | [DX Tuning](DX_TUNING.md)

## The Problem

You set 75W on the power slider. The radio shows 42W on the meter. Every ham operator knows this frustration.

The reason: `rfpower` on the FlexRadio (and most modern transceivers) sets the PA's maximum capability, but the actual output depends on the audio drive level reaching the PA. With DAX digital audio, the chain includes `mic_level`, software gain, DAX driver gain, and band-dependent PA characteristics. Each link can reduce the actual output.

Different bands behave differently. 20m might give you 66W at the same settings where 40m gives 53W. Weather affects SWR, which affects power. Common-mode currents (Mantelwellen) add another variable.

## How SimpleFT8 Solves This

SimpleFT8 uses a closed-loop feedback system:

1. **You select** the desired power (e.g., 70W) via button
2. **During TX**, the FWDPWR meter on the radio reports actual watts
3. **After each TX cycle** (~15 seconds), SimpleFT8 compares actual vs. target
4. **The audio drive is adjusted** automatically for the next cycle
5. **Within 2-3 cycles** (~30-45 seconds), the output converges to the target

The adjustment uses a P-controller with the square-root relationship between power and amplitude: to increase power by 10%, you increase amplitude by ~5% (since P is proportional to V squared).

## Clipping Protection

Increasing the audio drive too far causes clipping — hard distortion that creates splatter and interferes with adjacent stations. SimpleFT8 monitors the audio peak level before it reaches the radio:

- **Peak < 90%**: Safe, green indicator
- **Peak 90-100%**: Approaching limit, yellow indicator
- **Peak > 100%**: Clipping detected, red "CLIP!" indicator — auto-regulation stops increasing

This ensures your signal stays clean even as the system pushes for maximum power delivery.

## Per-Band Calibration

The optimal audio drive level varies by band. SimpleFT8 saves the calibrated value for each band. When you switch from 20m to 40m, the saved 40m drive level is loaded instantly — no need to wait for convergence again.

If conditions change (wet antenna, temperature shift), the continuous feedback loop detects the power drop and re-adjusts within a few cycles.

## The TX Status Display

The RADIO card shows all relevant TX metrics in one framed area:

- **TUNE** button + **Watt display**: Current forward power
- **Peak**: Audio peak level (headroom before clipping)
- **TX bar**: Current auto-adjusted drive level (0-150%)
- **SWR**: Antenna match quality

*(Screenshot of TX Status during transmission will be added)*

## Technical Details

### Control Algorithm

```
measured_watts = average(FWDPWR samples during TX cycle)
ratio = target_watts / measured_watts          (clamped 0.5 - 2.0)
amplitude_factor = sqrt(ratio)                 (P ∝ V²)
correction = Kp * (amplitude_factor - 1.0)     (Kp = 0.4)
correction = clamp(correction, -0.15, +0.15)   (max step per cycle)
new_level = current_level * (1.0 + correction)
new_level = clamp(new_level, 0.05, 1.50)       (absolute limits)
```

Safety rules:
- If measured > target * 1.05 and correction would increase: reduce instead
- If audio peak >= 0.95 and correction would increase: hold current level
- Changes < 1% are ignored (prevents oscillation)

### Audio Drive Chain

```
PyFT8 encoder (12kHz float32)
  → Resample to 24kHz
  → Multiply by tx_audio_level (0.05 - 1.50)
  → Clip to [-1.0, +1.0]
  → Convert to int16 big-endian
  → VITA-49 packets to radio
```

Additionally, `transmit set mic_level=X` (0-100) is sent to the radio's internal gain stage. For tx_audio_level 0-1.0, mic_level scales linearly. Above 1.0, mic_level stays at 100 and only software gain increases.

### Why Two Gain Stages?

The radio's `mic_level` controls the analog gain before the PA. The software `tx_audio_level` controls the digital signal level. Using both gives more range:
- **0-100%**: mic_level does the work, software at unity gain
- **100-150%**: mic_level at maximum, software provides additional boost
- The `np.clip` ensures the int16 output never overflows, even at 150%
