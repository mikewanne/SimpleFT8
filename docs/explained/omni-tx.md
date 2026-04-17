# OMNI-TX — Automatic Slot Rotation

## In Short

OMNI-TX automatically rotates between Even and Odd slots to reach 100% of active stations instead of just 50%. Less transmitting, more listening, more QSOs.

## The Problem

Every FT8 operator only hears the opposite slot. If you transmit on Even, you only hear Odd — and vice versa. With normal CQ, you reach exactly 50% of active stations per cycle. The other half never hears you.

## How It Works

OMNI-TX alternates between two blocks:

**Block 1 (Even-first):**
```
Even TX → Odd TX → Even RX → Odd RX → Even RX
```

**Block 2 (Odd-first):**
```
Odd TX → Even TX → Odd RX → Even RX → Odd RX
```

Each block runs for 80 cycles (~100 minutes), then switches. Over both blocks, Even and Odd coverage is perfectly balanced.

## Transmit Ratio

| Mode | TX Slots | RX Slots | TX Ratio |
|------|---------|---------|----------|
| Normal (Even) | 5 of 10 | 5 of 10 | **50%** |
| OMNI-TX | 4 of 10 | 6 of 10 | **40%** |

OMNI-TX transmits 20% less, listens 20% more, but reaches both listener groups.

## Realistic Gain

- Busy bands: **20-30% more CQ responses**
- Quiet bands: 10-20% more
- Reason: Twice as many operators hear you

## QSO Behavior

When a station responds:
1. Normal QSO flow (state machine takes over)
2. Block counter resets
3. Current block stays (the slot is working well)
4. After QSO ends: OMNI-TX pattern resumes

## Auto-Hunt

When enabled, Auto-Hunt is automatically activated. Auto-Hunt responds to CQ stations using intelligent scoring (new DXCC > rare call > good SNR).

## Activation

1. Click the **version number** in the bottom-right corner
2. Confirmation dialog appears
3. When activated: **Omega symbol** appears next to the version
4. CQ button changes to "OMNI CQ"
5. Click again to deactivate

## To Observers

One frequency in the waterfall. Signal switches between Even and Odd. Looks like manual slot switching — known, accepted, unobtrusive. Technically compliant: one frequency, same transmit time as any other station.
