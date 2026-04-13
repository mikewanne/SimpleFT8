# AP-Lite v2.2 — Weak QSO Rescue

## In a Nutshell

When your QSO partner's signal is too weak to decode, AP-Lite combines two consecutive failed decode attempts to recover the message — gaining ~4-5 dB effective SNR.

## The Problem

- You are in a QSO, your partner sent their report, but the decoder cannot crack it.
- After max retries, the QSO times out — frustrating for both sides.
- The signal IS there (you can see its trace in the waterfall), just too weak for a single slot.
- Standard FT8 decoders give up and move on. The QSO dies.

## How It Works

AP-Lite exploits a basic property of FT8: when a message is not confirmed, the sender repeats it. That repetition is not wasted — it carries the same information again, buried in different noise. AP-Lite combines both attempts.

1. **First decode fails.** AP-Lite saves the raw PCM audio buffer (the full 12.64-second window).
2. **Partner repeats** (FT8 standard behaviour: repeat until confirmed). Second decode also fails.
3. **Alignment.** AP-Lite aligns the two buffers using Costas sync arrays — the known 7-tone synchronization pattern that every FT8 message contains. The search window is +-8 samples in time and +-1.5 Hz in frequency, which accounts for small clock and oscillator differences between cycles.
4. **Coherent addition.** Both aligned buffers are added sample-by-sample. The signal adds constructively (same waveform, deterministic), while noise adds incoherently (random, uncorrelated between cycles).
5. **Candidate correlation.** The combined buffer is correlated against a set of candidate messages — messages that AP-Lite knows to expect based on the current QSO state.
6. **Decision.** If the best correlation score is >= 0.75, the message is accepted and the QSO continues.

## The Math

Two independent observations of the same signal with independent noise:

```
x1 = s + n1
x2 = s + n2
```

After coherent addition:

```
x_combined = x1 + x2 = 2s + (n1 + n2)
```

Signal power scales as the square of the amplitude factor:

```
P_signal = (2)^2 * P_s = 4 * P_s    → +6 dB
```

Noise power adds (independent, uncorrelated):

```
P_noise = P_n + P_n = 2 * P_n    → +3 dB
```

Net SNR gain:

```
SNR_gain = 6 dB - 3 dB = 3 dB (theoretical minimum from averaging)
```

In practice, AP-Lite achieves ~4-5 dB because the Costas-weighted correlation gives extra weight to the sync-tone positions (where SNR is highest), squeezing out an additional 1-2 dB beyond the raw averaging gain.

The 3 dB theoretical gain is the same principle behind stacking antennas or averaging in radio astronomy — nothing exotic, just the law of large numbers applied to signal processing.

## Candidate Generation

AP-Lite is not a blind decoder. It knows WHAT to look for because it knows where the QSO stands:

- **WAIT_REPORT state:** The expected message is a signal report. AP-Lite generates candidates across a window of +-5 dB around the expected SNR, e.g.: `DA1MHH DK5ON -15`, `DA1MHH DK5ON -14`, ..., `DA1MHH DK5ON -10`. That is 11 candidates (one per dB step from -20 to -10).
- **WAIT_RR73 state:** The expected messages are `DA1MHH DK5ON RR73`, `DA1MHH DK5ON RRR`, or `DA1MHH DK5ON 73`. That is exactly 3 candidates.

Fewer candidates means a lower false positive rate. In WAIT_RR73, the chance of a random noise pattern matching one of only 3 specific FT8-encoded messages at >= 0.75 correlation is negligible.

## Why 0.75?

The correlation threshold is a tradeoff:

- **Too low (e.g. 0.5):** False positives — noise matches a candidate by accident, the QSO logs a contact that never actually happened.
- **Too high (e.g. 0.95):** The feature never triggers — you needed 4-5 dB gain, but you are rejecting everything below near-perfect correlation.
- **0.75** is a conservative starting point chosen before field testing. It will be calibrated based on real-world data: record the correlation scores of known-good and known-bad decodes, then set the threshold at the optimal separation point.

## Pros and Cons

| Pro | Contra |
|-----|--------|
| +4-5 dB saves marginal QSOs that would otherwise time out | Only works during active QSOs (needs state info for candidates) |
| Zero false alarm risk in WAIT_RR73 (only 3 possible messages) | Correlation threshold 0.75 needs field calibration |
| Fully automatic, no user interaction needed | Adds ~5ms processing per failed decode attempt |
| Candidate-based: knows WHAT to look for, not blind search | Cannot help with CQ decoding (too many unknown messages) |
| Uses data that would otherwise be thrown away (failed buffers) | Requires partner to repeat (standard FT8 behaviour, but not guaranteed) |

## Status

**UNTESTED** — Code complete (v0.22 skeleton, v0.26 full implementation), disabled by default (`AP_LITE_ENABLED = False` in `core/ap_lite.py`).

Enable after field-test calibration of the 0.75 correlation threshold. Watch for `[AP-Lite]` log entries once enabled.
