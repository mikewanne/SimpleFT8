# Per-Station Antenna Preference

[Deutsch](antenna-preference_de.md) | **English**

## What does this feature do?

SimpleFT8 remembers, per callsign, which antenna delivered the best
SNR — and by how many dB. On QSO start, the correct antenna is
selected automatically, without the operator having to think about
it. This overlays the global Diversity logic for the duration of
the QSO.

## How does it work?

Diversity (Standard or DX) makes a **global** decision every 15
seconds: which antenna currently receives the most stations
(Standard) or the most weak stations (DX). That's an average across
all received calls.

But if DL3AQJ comes from northern Germany and ANT2 points north,
ANT2 might be 6 dB better **for that one station** — regardless of
what the rest of the band says.

SimpleFT8 keeps per callsign:

- **best_ant** — `"A1"` or `"A2"`
- **delta_db** — how many dB advantage the better antenna has

The value is **overwritten on every reception** — no timeout, no
cache. A station I'm hearing right now is the most accurate source.
If I can't hear it, there's nothing to call, so historical values
are useless.

**1 dB hysteresis:** So the system doesn't flip back and forth on
tiny differences, an antenna switch requires at least 1 dB delta.

**QSO protection:** Once a QSO starts, the antenna choice freezes
for that station. The global Diversity rotation pauses, both slots
run on the preferred antenna. After QSO end: back into the normal
Diversity rhythm.

**Hardware requirement:** This preference only affects reception.
TX always runs through ANT1 — regardless of which antenna is
preferred here. ANT2 (rain gutter) is not rated for transmit.

## When is it useful?

- **DX hunting:** You want to call a rare station that's currently
  clean only on one antenna — Antenna-Pref picks it automatically.
- **Waitlist:** Multiple stations calling at the same time — each
  one gets its optimal antenna.
- **QSO ping-pong:** When the partner arrives slightly differently
  between slots, the antenna stays stable.

## Where to find it?

- **QSO panel:** During an active QSO you see `Calling DL3AQJ
  (ANT2, +6.3 dB)`.
- **Status bar:** `RX: A2 (+6.3 dB)` during QSO.
- **RX panel:** The "Antenna" column shows the last reception
  status per station (A1, A2, A1>2, A2>1).

The feature is always active when Diversity is running. No
setting, no toggle — automatic learning.
