# Propagation Indicators

## In a Nutshell

Color-coded bars under each band button show current HF propagation conditions — green (good), yellow (fair), red (poor) — using HamQSL solar data with time-of-day correction for Central Europe.

## The Problem

- "Should I try 10m or 40m right now?" — every ham's daily question.
- Checking HamQSL/DXHeat/VOACAP manually breaks workflow.
- Solar conditions change throughout the day — a band "good" at noon may be dead at midnight.
- HamQSL gives global day/night ratings, but YOUR local time of day matters.

## How It Works

1. A background thread fetches XML from `https://www.hamqsl.com/solarxml.php` every 3 hours.
2. The XML contains band condition predictions: good, fair, or poor for each HF band, separately for "day" and "night."
3. SimpleFT8 applies a time-of-day correction for Central Europe (UTC-based rules per band) to pick the right rating and optionally downgrade it.
4. A 4-pixel colored bar appears under each band button.
5. Colors: green (#00CC00) = good, yellow (#FFAA00) = fair, red (#CC0000) = poor, grey = no data.

## Time-of-Day Correction (Central Europe)

HamQSL provides separate "day" and "night" predictions, but doesn't tell you when day ends and night begins for your location. That's the gap this correction fills.

The rules are based on typical Central European propagation windows. Each band has hours where it is expected to be usable ("good hours") and hours where the rating gets downgraded by one step because the band is likely dead or marginal at that time.

| Band | Good Hours (UTC) | Downgraded Hours | Reason |
|------|-----------------|------------------|--------|
| 80m  | 00-07, 20-24    | 07-20 (daytime, -1 step) | Low-band, needs darkness for long-range propagation |
| 40m  | 00-07, 19-24    | 07-19 (daytime, -1 step) | Similar to 80m but slightly wider usable window |
| 20m  | 09-20           | 00-09, 20-24 (nighttime, -1 step) | Daytime band, needs solar illumination of ionosphere |
| 15m  | 10-19           | 00-10, 19-24 (nighttime, -1 step) | Shorter daytime window than 20m |
| 10m  | 11-18           | 00-11, 18-24 (nighttime, -1 step) | Highest HF band, needs peak solar illumination |

"-1 step" means: good becomes fair, fair becomes poor, poor stays poor.

These are coarse rules. Real propagation doesn't follow a switch — 20m doesn't die at exactly 20:00 UTC. But for a quick visual indicator, coarse is fine. The alternative is showing HamQSL raw data, which says "20m: good (day), fair (night)" without telling you which one applies right now. That's less useful.

## Data Source

- **HamQSL.com** — free, no API key, no login required.
- Based on Solar Flux Index (SFI), K-Index, A-Index — these solar parameters drive ionospheric conditions.
- Data changes slowly (solar indices update every few hours), so polling every 3 hours is sufficient.
- On network error: bars turn grey and disappear. No crash, no stale data displayed.

## What It Doesn't Do

- Does not predict local propagation. A green bar on 10m means solar conditions support 10m propagation globally — it doesn't mean you will hear anyone from JO31 right now.
- Does not account for geomagnetic storms in real time (K-index is part of the data, but the time correction is static).
- 60m is not covered because HamQSL does not include it.
- Time correction is hardcoded for Central Europe. If you're in VK/ZL or JA, the "good hours" are wrong. This could be made configurable but isn't yet.

## Pros and Cons

| Pro | Contra |
|-----|--------|
| Instant visual band recommendation | Only Central Europe time correction |
| No API key or login needed | HamQSL data can be hours old |
| Automatic background updates | 60m not covered (not in HamQSL) |
| Tiny UI footprint (4px bars) | Generic prediction, not local propagation |

## Status

UNTESTED — Active since v0.23. Check: Do the colors match your experience? 80m at noon should show red. 20m at noon should show green (given decent SFI).
