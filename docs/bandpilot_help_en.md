# Bandpilot — Help

## What does Bandpilot do?

When you change band, Bandpilot automatically switches to the receive
mode that has historically delivered the most decoded stations per
15-second slot on that band.

Three modes are available:

- **Normal** — single antenna (ANT1)
- **Diversity Standard** — two antennas, picks the one with more stations
- **Diversity DX** — two antennas, picks the one with weaker DX signals

## Data source

Bandpilot reads the hourly Markdown files in
`statistics/<Mode>/<Band>/FT8/`. Each file = one UTC hour, each row =
one 15s slot with the number of decoded stations.

Minimum threshold per mode: **2 measurement days and 50 slots**.
Below that, Bandpilot makes no recommendation — your manual mode stays.

## Comparison (Candidate A)

`Normal` is compared against the mean of Diversity_Normal and
Diversity_DX:

```
diversity_aggregate = (Diversity_Normal_Mean + Diversity_DX_Mean) / 2
```

If `Normal_Mean >= diversity_aggregate` → **Normal**.
Otherwise → **Diversity** with your preferred sub-mode.

## Diversity preference

If Diversity wins, your preference setting decides which sub-mode is
activated:

- **Auto** (default) — the Diversity sub-mode with the higher pooled
  mean wins
- **Standard** — always Diversity_Normal (more total stations)
- **DX** — always Diversity_DX (more weak DX signals)

## Manual override

If, after a Bandpilot recommendation, you manually switch to a different
mode (click on "NORMAL" or "DIVERSITY"), this is remembered for this
band. The next band change **to** this band will respect the override —
Bandpilot only kicks in again at the band change after that.

Example:

1. Switch to 40m → Bandpilot recommends Diversity Standard, app switches.
2. You click "Normal" manually → override set for 40m.
3. Switch to 20m → Bandpilot operates normally for 20m.
4. Switch back to 40m → Bandpilot **does not switch** (override), clears
   the flag.
5. Switch to 20m and back to 40m again → Bandpilot operates normally.

## Cache

Stats aggregation is cached per band for 24 hours
(`~/.simpleft8/bandpilot_summary.json`). After 24h the next call
re-aggregates automatically.

## Prerequisites

- Statistics logging must be active (Settings → "Enable statistics
  logging").
- At least 2 days of measurement per mode on the band.
- Currently FT8 only (FT4/FT2 are skipped by the stats logger).

## What does the status bar show?

When Bandpilot switches, the status bar briefly shows:

```
Bandpilot: Diversity Standard for 40m
```

(3 seconds, then back to the regular status bar.)
