# FT2 Mode — Ultra-Fast Digital Communication

## In a Nutshell

FT2 is a digital mode with 3.8-second cycles — four times faster than FT8's 15-second cycles. It is designed for strong-signal situations where you want speed, not weak-signal performance. SimpleFT8 supports FT2 for receive and transmit, compatible with Decodium 3.0 by IU8LMC.

## What Is FT2?

FT2 is the fastest member of the FT-mode family:

| Property | FT8 | FT4 | FT2 |
|----------|-----|-----|-----|
| Slot time | 15.0 s | 7.5 s | 3.8 s |
| Signal duration | 12.64 s | 4.94 s | 2.47 s |
| Tone spacing | 6.25 Hz | 20.83 Hz | 41.67 Hz |
| Bandwidth per signal | ~50 Hz | ~83 Hz | ~167 Hz |
| Samples per symbol | 1920 | 576 | 288 |
| Sensitivity | -21 dB | -17.5 dB | -12 dB |
| Speed factor vs. FT8 | 1x | 2x | 4x |

All three modes share the same message structure: 77-bit payload, LDPC(174,91) coding, 4-GFSK modulation. The only difference is speed (symbol rate and slot timing).

## Compatibility

SimpleFT8's FT2 implementation is compatible with **Decodium 3.0** by IU8LMC. This is important because there are different FT2 implementations:

| Software | Compatible? | Notes |
|----------|-------------|-------|
| Decodium 3.0 (IU8LMC) | Yes | Primary FT2 software, same protocol |
| WSJT-X Improved FT2 | No | Different protocol variant, not compatible |
| WSJT-X standard | No | Does not support FT2 at all |

Make sure the stations you want to work are also using Decodium 3.0 or a compatible implementation.

## FT2 Frequencies

FT2 has its own community-agreed dial frequencies, separate from FT8 and FT4:

| Band | FT2 Dial (MHz) | FT8 Dial (MHz) | FT4 Dial (MHz) |
|------|----------------|-----------------|-----------------|
| 80m | 3.578 | 3.573 | 3.575 |
| 60m | 5.360 | 5.357 | — |
| 40m | 7.052 | 7.074 | 7.047 |
| 30m | 10.144 | 10.136 | 10.140 |
| 20m | 14.084 | 14.074 | 14.080 |
| 17m | 18.108 | 18.100 | 18.104 |
| 15m | 21.144 | 21.074 | 21.140 |
| 12m | 24.923 | 24.915 | 24.919 |
| 10m | 28.184 | 28.074 | 28.180 |

SimpleFT8 sets the correct dial frequency automatically when you switch to FT2 mode.

## Technical Details

### Modulation

FT2 uses 4-GFSK (Gaussian Frequency Shift Keying) with 4 tones, identical to FT4. The symbol rate is doubled compared to FT4:

- **288 samples per symbol** at 12 kHz sample rate = 41.667 symbols/second
- **103 total symbols** per transmission: 87 data + 16 sync
- **4 Costas sync arrays** for time and frequency synchronization
- **FEC:** LDPC(174,91) with 14-bit CRC — same error correction as FT8 and FT4

### Timing Requirements

Because FT2 cycles are only 3.8 seconds, timing accuracy is critical:

- **Required clock accuracy:** +-50 ms (compared to +-200 ms for FT8)
- SimpleFT8's DT correction handles this automatically after 2 measurement cycles (~8 seconds)
- NTP synchronization is strongly recommended

If your clock is off by more than ~100 ms, decoding will fail or be unreliable.

### RX Filter

SimpleFT8 automatically widens the RX filter to **4000 Hz** when in FT2 mode (compared to 3100 Hz for FT8/FT4). This is necessary because FT2 signals are ~167 Hz wide — more than three times wider than FT8 signals. With the standard 3100 Hz filter, you would miss stations at the edges of the passband.

### Signal Duration and Pause

Each FT2 slot is 3.8 seconds:
- Signal: 2.47 seconds (103 symbols x 288 samples / 12000 Hz)
- Pause: 1.33 seconds (available for async TX window)

The 1.33-second pause between signal end and the next slot start is where the system switches from TX to RX or starts the decoder.

## When to Use FT2

FT2 is the right choice when:

- **Signals are strong.** FT2's wider bandwidth means less weak-signal sensitivity (-12 dB vs. FT8's -21 dB). Use it when SNR is above roughly -5 dB.
- **You want speed.** A complete QSO takes about 20 seconds instead of 1-2 minutes in FT8. Theoretical throughput: up to 240 QSOs/hour.
- **Contest or pile-up operation.** Fast turnaround means more QSOs per hour.
- **Band opening is short.** When a brief sporadic-E opening appears, FT2 lets you work more stations before it closes.
- **DXpeditions and special events.** High throughput for rare callsigns.

FT2 is **not** the right choice when:

- **Signals are weak.** Below -10 dB SNR, FT8 will decode where FT2 cannot.
- **You are working DX on marginal paths.** FT8's 15-second slot accumulates more energy.
- **Few stations are on the frequency.** If activity is low, FT8 has more users and better chances of finding a QSO partner.
- **Poor clock synchronization.** Systems without NTP may struggle with the tight timing.

## Switching Modes in SimpleFT8

1. Select **FT2** from the mode selector in the control panel.
2. SimpleFT8 automatically adjusts: dial frequency, RX filter width, TX timing, and slot duration.
3. The cycle timer in the status bar shows 3.8-second cycles instead of 15-second cycles.
4. DT correction loads the stored FT2 value (if a previous measurement exists).
5. All QSO flow logic (Hunt, CQ, waitlist) works identically — just faster.

Switch back to FT8 or FT4 at any time. The mode change takes effect at the next cycle boundary.

## Tips for Operators

- **Check activity first.** FT2 is less widely used than FT8. Check the FT2 frequencies before switching — if nobody is there, switch back to FT8.
- **Use NTP sync.** Timing errors that are harmless in FT8 can cause missed decodes in FT2.
- **Expect wider signals in the waterfall.** Each FT2 signal is ~167 Hz wide, so fewer stations fit in the passband compared to FT8.
- **QSO completion is fast.** Pay attention — a full CQ + QSO can happen in under 30 seconds.
- **Same QSO flow.** Everything you know about Hunt mode, CQ mode, and the waitlist applies to FT2. The protocol is identical, only the clock runs faster.
