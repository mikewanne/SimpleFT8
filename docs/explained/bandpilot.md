# Bandpilot — Per-Hour RX-Mode Recommendation

> **v0.88, May 2026** — Concept refactor. Instead of a global mean,
> three direct values per UTC hour, no aggregation.

## What does the Bandpilot do?

When you switch bands, the Bandpilot checks for the **current UTC
hour**: which RX mode historically delivered the most stations per
15-second slot in that hour?

Three modes are available:

- **Normal** — single antenna (ANT1)
- **Diversity Standard** — two antennas, the one with more stations wins
- **Diversity DX** — two antennas, the one with weaker DX signals wins

Unlike v0.87, **no aggregation** is performed — the three values are
compared directly. Reason: Diversity Standard and Diversity DX are
different populations (different antenna patterns, different win-rate
logic). Averaging them creates bias.

## Data basis

Hourly Markdown files in `statistics/<Mode>/<Band>/FT8/`. Each file
= one UTC hour, each row = one 15s slot with the number of decoded
stations.

Per-hour thresholds (all three modes must satisfy):

- **at least 3 measurement days** in this hour
- **at least 20 slots** in this hour

If one mode is below: silent recommendation, no switch, status bar
hint for 5 seconds ("Bandpilot: not enough data for 40m at 03 UTC").

## Settings — three behaviour modes

In the Settings dialog under "FT8 & Diversity":

| Value | Behaviour |
|---|---|
| **Off** | Bandpilot does not react. |
| **Auto (best value)** | On band change: 3-second toast centred on screen shows all three values. App switches to Top-1 automatically — if current mode is within 5% tolerance of Top-1, no switch (ping-pong protection). |
| **Manual (dialog)** | On band change: dialog appears **only** if Top-1 != current mode. Three buttons (Top-1 in green), user clicks — or cancel. |

## Tolerance rule

Auto mode only switches if the current mode is **noticeably worse**
than Top-1:

```
tolerance = max(5% of Top-1_mean, 1 station/slot)

if current_mean >= Top-1_mean - tolerance:
    no switch (ping-pong guard kicks in)
else:
    switch to Top-1 (with toast)
```

Example for 13 UTC on 40m:

| Mode | Mean |
|---|---:|
| Diversity DX (Top-1) | 50.4 |
| Diversity Standard | 48.0 |
| Normal (current) | 35.0 |

Tolerance = max(2.5, 1) = 2.5. Current mean (35.0) is 15.4 below
Top-1 → noticeably worse → switch to DX.

Another example:

| Mode | Mean |
|---|---:|
| Diversity DX (Top-1) | 50.4 |
| Diversity Standard (current) | 49.0 |
| Normal | 35.0 |

Tolerance = 2.5. Current mean (49.0) is 1.4 below Top-1 → no switch
(stay on Standard).

## TX protection

If a TX is in progress when the band changes:

1. Toast appears immediately with the recommendation
2. Status bar 5s: "Bandpilot switches to Diversity DX after TX end"
3. As soon as the `tx_finished` signal arrives: mode switch +
   short confirmation toast 1.5s "Bandpilot: mode applied"

This way no QSO is interrupted in mid-transmit.

## Markdown recommendation file

On app start (and on `scripts/generate_plots.py` runs)
`auswertung/Bandpilot-<band>-FT8.md` is regenerated — a 24-row table
(UTC 00..23) with all three values per hour plus Top-1.

This lets you see at a glance where which mode is optimal — even
without switching the app's band.

## What it does **not** do

- Does **not** recommend other bands (no "switch to 20m, more
  activity there" feature). Bandpilot only reacts after you've
  picked the band.
- Does **not** react to hour transitions while you stay on a band.
  The trigger is always a band change.
- Has **no** time hysteresis ("don't switch twice in a row") —
  this is added in a future version if needed.

## Migration v0.87 → v0.88

Existing settings are migrated automatically on first app start:

| Old | New |
|---|---|
| `bandpilot_enabled = false` | `bandpilot_mode = "off"` |
| `bandpilot_enabled = true` | `bandpilot_mode = "auto"` |
| `bandpilot_diversity_pref = ...` | discarded |

The old cache `~/.simpleft8/bandpilot_summary.json` is deleted.
New cache: `~/.simpleft8/bandpilot_hourly.json`.

The MD recommendation files are German-only for now. An English
variant under `auswertung/en/` may be added in a future version.

## Sample output

From `auswertung/Bandpilot-40m-FT8.md` (excerpt):

```
| UTC | Normal | Div Standard | Div DX | Top-1 |
|---:|---:|---:|---:|:---|
| 13 | 5·45.2 | 4·38.0 | 5·52.7 | Diversity DX |
| 14 | 5·48.1 | 5·40.5 | 5·55.2 | Diversity DX |
| ...
```

Cell format: `<days>·<mean>`. If a mode lacks data: `—` (em-dash)
or the Top-1 column shows `_zu wenig Daten_` (not enough data).
