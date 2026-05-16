# OMNI-CQ — Automatic Parity Switching

## In Short

OMNI-CQ calls CQ on **one** slot parity (Even or Odd), then
automatically switches to the other parity after a mode-dependent
number of transmit attempts. Over longer periods, you reach both
listener groups instead of just one — without changing your TX duty
cycle per slot.

## The Problem

Every FT8 operator only hears the opposite slot. If you transmit on
Even, you only hear Odd — and vice versa. With normal CQ, you reach
exactly **50%** of active stations per cycle. The other half never
hears you.

## How It Works

OMNI-CQ is a **single-slot CQ** in one parity, with automatic parity
switching after a fixed number of transmit attempts per mode:

| Mode | TX attempts per parity | Duration (wallclock) |
|------|------------------------|----------------------|
| FT8 | 10 | ~5 minutes |
| FT4 | 20 | ~5 minutes |
| FT2 | 40 | ~5 minutes |

A down-counter counts from the max value to zero. At 0:
**automatic parity switch** + counter resets to the mode value. The
counter is visible in the TX line as a `↻N` suffix.

```
04:30:00 [E] → Sende CQ DA1MHH JO31 ↻10
04:30:30 [E] → Sende CQ DA1MHH JO31 ↻9
...
04:35:00 [E] → Sende CQ DA1MHH JO31 ↻1
04:35:30 [O] → Sende CQ DA1MHH JO31 ↻10   ← parity switch
```

## Transmit Ratio

OMNI-CQ does **not** change your TX duty cycle per slot. It's
single-slot CQ — same TX ratio as normal CQ on that parity. The
difference: parity rotates automatically every ~5 min.

## Realistic Gain

Over longer periods (1+ hour):

- **Busy bands:** ~15-25% more CQ responses than static single-slot
  CQ — you reach both listener groups.
- **Quiet bands:** Small effect — stations that don't hear you on
  one parity probably won't hear you on the other either.

## QSO Behavior

When a station responds:

1. OMNI pauses, normal QSO flow (state machine takes over)
2. After QSO ends: OMNI resumes on the **same** parity
3. Counter resets to TARGET (positive reinforcement:
   „good slot — keep going")

## Antenna Measurement (Diversity)

If a diversity antenna measurement starts during OMNI:

1. OMNI pauses (no TX during measurement)
2. Measurement runs (~90 s)
3. After measurement: OMNI resumes, counter resets to TARGET

## Switch Triggers Outside Counter

- **Band change:** OMNI stops (user decides manually on new band)
- **Mode change:** OMNI stops (counter would be a different size)

## Diversity-only

OMNI-CQ only works in **diversity mode**. In normal mode, the toggle
button is hidden.

## Activation

Since v0.97.30 (P55), OMNI-CQ is a **regular, visible feature** in
Diversity mode. The **OMNI CQ** button appears permanently next to the
CQ button when Diversity is active — no version-number click needed.

- **OMNI CQ button**: dark red (off), green (on)
- **Status bar** shows `Ω CQ=N (E)` or `Ω CQ=N (O)` with current counter
  and parity

*History:* Up to v0.97.29, OMNI-CQ was a hidden Easter egg, enabled by
clicking the version number. In P55 the Easter-egg logic was removed
completely — see HISTORY entry v0.97.30.

## QSO Panel Display

With OMNI active:
- Even slots in **slightly darker orange** (#E09600)
- Odd slots in **normal orange** (#FFAA00)
- On parity switch: **blank line** between blocks
- Counter suffix `↻N` on each TX line

At a glance you see how far the current parity block is and when the
next phase begins.

## To Observers in the Waterfall

One frequency, one station, normal CQ rhythm with occasional parity
switches — looks like an operator switching between Even and Odd
phases. Technically fully compliant: one TX frequency, normal
transmit time per slot.

## History

Earlier concept (v0.78–v0.96.0) was a 5-slot pattern with two
consecutive TX slots per block. Replaced with **P7.OMNI-SIMPLIFY**
(v0.96.4) by the current single-slot pattern. Reason: consecutive
TX-TX in 15-s slots caused encoder races and diversity conflicts.
Current solution is KISS — one parity, one switch counter, diversity
stays untouched.
