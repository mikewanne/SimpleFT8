# DT Timing Correction

[Back to README](../README.md) | [Diversity](DIVERSITY.md) | [Frequency Histogram](FREQUENCY_HISTOGRAM.md)

## What Is DT?

In FT8, every decoded message includes a **DT value** — the time offset in seconds between when the transmitting station started its slot and when you received it. Ideally DT is close to 0.0. If your clock or your radio's audio pipeline introduces a fixed delay, all received DT values will be systematically shifted.

SimpleFT8 measures this shift and compensates for it automatically.

## Two-Layer Architecture

The total timing error is split into two components:

### Layer 1 — Fixed Hardware Offset (hardcoded)

The FlexRadio SmartSDR introduces a constant audio pipeline delay. This is a known, stable hardware property that does not change between sessions. It is compensated by a fixed offset built directly into the decoder (`DT_BUFFER_OFFSET`):

| Mode | DT_BUFFER_OFFSET |
|------|-----------------|
| FT8  | 2.0 s           |
| FT4  | 1.0 s           |
| FT2  | 0.8 s           |

These values already include the 0.5 s WSJT-X protocol convention. Once subtracted, the remaining DT error is typically only ±0.3 s.

### Layer 2 — Adaptive Correction (automatic)

After the fixed offset is removed, a small residual error remains (~0.27 s for FlexRadio VITA-49). This is corrected adaptively by `core/ntp_time.py`:

1. **Measure phase** (2 cycles): Collect DT values from all decoded stations, compute median
2. **Apply correction**: Adjust the internal time by 70% of the measured median error
3. **Operate phase** (10 cycles): Transmit with the current correction applied
4. **Repeat**: Re-measure every ~150 s (FT8), save result to disk

Corrections are stored **per mode and band**: switching from 40m FT8 to 20m FT8 loads a separate saved value, so every band/mode combination converges independently and starts from a good baseline on the next session.

## Why Split into Fixed + Adaptive?

Before this approach, the entire ~0.77 s correction was handled adaptively. This had two drawbacks:
- Cold start took many cycles to converge (correction started at 0, needed to climb to 0.77 s)
- Large adaptive range meant slower, noisier convergence

By hardcoding the stable FlexRadio constant (~0.5 s), the adaptive layer only needs to handle the remaining ~0.27 s. Convergence is faster and more stable.

## Storage

Corrections are saved to `~/.simpleft8/dt_corrections.json`:

```json
{
  "FT8_20m": 0.24,
  "FT8_40m": 0.27,
  "FT4_20m": 0.25
}
```

On band or mode change, the stored value for the new combination is loaded immediately. If no value exists, the adaptive layer starts from 0 and converges within a few cycles.

## Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| Measure cycles | 2 | Cycles per measurement window |
| Operate cycles | 10 | Cycles between measurements |
| Damping | 70% | Only 70% of measured error is applied per step |
| Deadband | 50 ms | Corrections smaller than this are ignored |
| Max correction (FT8) | ±1.0 s | Safety limit |
| Max correction (FT4) | ±0.5 s | |
| Max correction (FT2) | ±0.3 s | |
| Jump detection | > 1.0 s | Full reset if DT suddenly spikes |

## TX Timing

For transmit, the FlexRadio buffers audio samples ~1.3 s before RF output. This is compensated by `TARGET_TX_OFFSET = -0.8 s` in the encoder:

```
TARGET_TX_OFFSET = 0.5 s (protocol) − 1.3 s (FlexRadio TX buffer) = −0.8 s
```

This value is FlexRadio-specific. A different radio (e.g., IC-7300) would require its own measured value.
