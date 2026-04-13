# Signal Processing Pipeline

## In a Nutshell

SimpleFT8 uses a multi-stage signal processing pipeline to extract weak FT8 signals from noise. Three key techniques work together: **Anti-Alias Resampling**, **Spectral Whitening**, and **Multi-Pass Signal Subtraction**. An additional **Window Sliding** step catches stations with timing errors.

The entire pipeline runs automatically every 15-second cycle. No user tuning required.

## The Problem

Raw audio from the FlexRadio arrives via VITA-49 at 24 kHz sample rate. FT8 decoding needs 12 kHz. Between "audio in" and "decoded callsigns out", several things can go wrong:

- **Aliasing** from naive sample rate conversion folds high-frequency noise into the FT8 passband
- **Uneven noise floor** (QRM, birdies, power supply hash) biases the decoder toward cleaner frequencies
- **Strong signals masking weak ones** -- a -5 dB station is invisible next to a +15 dB station in the same cycle
- **Timing errors** -- not every station has perfect GPS sync; some are off by a few hundred milliseconds

A single-pass decoder with simple downsampling misses a significant number of stations. SimpleFT8's pipeline addresses each of these problems.

## Anti-Alias Resampling (24 kHz to 12 kHz)

### Why

FT8 occupies 0--3000 Hz audio bandwidth. The decoder (ft8_lib) expects 12 kHz sample rate. The FlexRadio delivers 24 kHz via VITA-49/DAX.

The naive approach -- drop every other sample -- creates **aliasing**: any energy between 6 kHz and 12 kHz (the upper half of the 24 kHz spectrum) folds back into 0--6 kHz and lands right on top of your FT8 signals. Even though FT8 signals live below 3 kHz, noise and spurious signals above 6 kHz will alias down and raise the noise floor.

### How

SimpleFT8 applies a low-pass filter **before** decimation:

1. Design a 63-tap FIR filter with cutoff at 6 kHz (= Nyquist of the target 12 kHz rate)
2. Window: Hamming (good sidelobe suppression, simple to compute)
3. Filter the 24 kHz audio
4. Then decimate by factor 2 (keep every other sample)

### The Math

The filter coefficients are computed as a windowed sinc function:

```
h[n] = sinc(2 * fc * (n - 31)) * hamming(n)     for n = 0..62
```

Where `fc = 6000 / 24000 = 0.25` (normalized cutoff frequency). The sinc function is the ideal low-pass impulse response; the Hamming window truncates it to 63 taps without creating large sidelobes.

After filtering, every second sample is kept: `output = filtered[::2]`.

### What You Get

A clean 12 kHz signal where everything above 6 kHz has been removed **before** downsampling. No aliasing artifacts, no folded-in noise. The 63-tap length is a good compromise between filter quality and processing time.

## Spectral Whitening

### Why

In the real world, the noise floor is not flat across the FT8 passband. Some frequencies carry more noise than others -- local QRM sources, switching power supplies, LED drivers, or simply the shape of the receiver's noise figure. A station at -21 dB next to a birdie has effectively a worse SNR than the same -21 dB station on a clean frequency, even though the decoder sees the same reported power.

### How

Spectral whitening normalizes each frequency bin by its local noise level, making the noise floor flat ("white") across all frequencies.

Implementation (Overlap-Add method):

1. Chop the audio into overlapping frames: **2048-point FFT**, **50% overlap** (hop size 1024), Hanning window
2. For each frame, compute the magnitude spectrum
3. For each frequency bin, take the **median** of a sliding window of 31 neighboring bins -- this estimates the local noise floor
4. Divide each spectral bin by its local noise floor estimate
5. Clamp the gain to a maximum of **100x** (prevents extreme amplification in near-silent bins)
6. Inverse FFT back to time domain, overlap-add to reconstruct the audio

### The Math

For frequency bin `k` in frame `m`:

```
noise_floor[k] = median(|S[k-15]|, |S[k-14]|, ..., |S[k+15]|)
S_white[k] = S[k] * min(1 / noise_floor[k], 100)
```

The 31-bin median window is wide enough to smooth out individual signals but narrow enough to track frequency-dependent noise variations. The median (rather than mean) is robust against the signals themselves -- a strong FT8 tone in one bin does not inflate the noise estimate of its neighbors.

### What You Get

After whitening, a -22 dB station sitting next to a local QRM source has the same chance of being decoded as a -22 dB station on a perfectly clean frequency. In high-QRM environments (40m evenings, contest weekends), this can mean 10--20% more decoded stations. On quiet bands, the effect is smaller.

**Trade-off**: Whitening can slightly reduce the effective SNR of very strong signals on already-clean frequencies. In practice, those signals decode fine anyway, so the trade-off is worthwhile.

## Multi-Pass Signal Subtraction (up to 5 Passes)

### Why

This is the biggest single improvement in the pipeline. The basic idea: after decoding the strongest stations, **remove them** from the audio and decode again. Stations that were previously hidden behind stronger ones now become visible.

Think of it like peeling layers off an onion. Pass 1 gets the strong stations. Pass 2, with those removed, gets the next layer. And so on.

### How

1. **Pass 1**: Decode the audio normally. Get a list of decoded messages with their frequencies, timing, and SNR.
2. **Reconstruct**: For each decoded message (with SNR >= -18 dB), mathematically regenerate the FT8 signal using the encoder at the exact same frequency and timing.
3. **Subtract**: Remove the reconstructed signal from the audio waveform.
4. **Pass 2**: Decode the residual audio. New stations that were previously masked now appear.
5. **Repeat** up to 5 passes total. Each pass typically yields fewer new stations (diminishing returns).

The minimum SNR threshold of -18 dB ensures we only subtract signals that were decoded with reasonable confidence. Subtracting a wrongly-decoded signal would add noise rather than remove it.

### What You Get

Typical improvement: **+30--50% more decoded stations** compared to a single-pass decode. The gain is largest on busy bands (20m/40m during daylight) where many stations overlap. On quiet bands with only a few stations, there is less to subtract and the gain is smaller.

**Trade-off**: Each pass takes decoder time (~50--100 ms per pass). With 5 passes, total decode time is roughly 200--500 ms per cycle instead of ~50 ms. On a modern Mac, this is well within the 15-second FT8 cycle.

In rare cases, an imperfect signal reconstruction can remove a small amount of energy from a neighboring station. In practice, this has not been observed to cause missed decodes.

## Window Sliding (+/-0.3s Offsets)

### Why

FT8 messages are 12.64 seconds long within a 15-second slot. The decoder assumes the signal starts at a specific time (DT = 0). But not every station has accurate timing -- some are 100-300 ms early or late. A station with DT = +0.35s may be right at the edge of the decoder's search window and get missed.

### How

SimpleFT8 decodes the audio at three time offsets:

| Offset | Samples at 12 kHz | Effect |
|--------|-------------------|--------|
| 0 | 0 | Normal decode position |
| +0.3s | +3600 | Catches late stations |
| -0.3s | -3600 | Catches early stations |

The audio is shifted by the offset before each decode attempt. Results from all three offsets are merged and deduplicated (first occurrence wins).

### What You Get

Typically **+5--10% more decoded stations**, mostly marginal stations with imperfect timing. The DT values in the decode results are corrected back to account for the applied offset, so displayed timing remains accurate.

## Pipeline Summary

The full pipeline for each 15-second FT8 cycle:

```
VITA-49 Audio (24 kHz int16)
  |
  v
Noise-Floor Normalization (target: median abs ~300)
  |
  v
Anti-Alias Low-Pass Filter (63-tap Sinc, Hamming, fc=6 kHz)
  |
  v
Decimate by 2 --> 12 kHz
  |
  v
RMS Auto-Gain Control (target -12 dBFS, +/-3 dB hysteresis)
  |
  v
DC Offset Removal
  |
  v
Spectral Whitening (2048-pt FFT, 50% overlap, 31-bin median)
  |
  v
RMS Normalization (-18 dBFS)
  |
  v
Window Sliding (0, +0.3s, -0.3s)
  |
  v
ft8_lib C Decoder (Costas sync, LDPC 50 iterations, CRC check)
  |
  v
Signal Subtraction (reconstruct + subtract, up to 5 passes)
  |
  v
Drift Compensation (+/-0.5, +/-1.5 Hz/s linear drift correction)
  |
  v
Result Fusion + Deduplication
```

## Expected Gain

| Technique | Typical Improvement |
|-----------|-------------------|
| Signal Subtraction (5 passes) | +30--50% more decodes |
| Spectral Whitening | +10--20% in high-QRM environments |
| Window Sliding | +5--10% marginal stations |
| Combined | Up to 2x more stations vs. basic single-pass decoder |

These are **estimates** from controlled tests on 20m and 40m. Real-world gain depends on band conditions, time of day, QRM level, and number of active stations. On a quiet band with 5 stations, you will not see 2x improvement. On a busy 40m evening with 30+ stations and local QRM, the full pipeline makes a very noticeable difference.

## Pros and Cons

| Pro | Con |
|-----|-----|
| Significantly more decodes per cycle | Higher CPU usage (~200--500 ms vs. ~50 ms per cycle) |
| Fully automatic, no operator tuning needed | Signal subtraction can rarely subtract a tiny amount of energy from neighboring stations |
| Spectral whitening handles QRM effectively | Whitening may slightly reduce SNR of strong signals on clean frequencies |
| Window sliding catches timing-impaired stations | Three decode attempts per pass increase processing time |
| All techniques are well-established in DSP literature | Reconstruction quality depends on encoder accuracy |

## Status

Tested and stable since v0.5. Signal Subtraction, Spectral Whitening, and Anti-Alias Resampling form the core of SimpleFT8's decode advantage. Drift compensation was added later (v0.24) and is still considered experimental.
