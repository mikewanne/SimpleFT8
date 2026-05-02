# Direction Map (3D Globe)

[Deutsch](direction-map_de.md) | **English**

## What does this feature do?

A rotatable 3D globe (azimuthal equidistant projection) with
**16 directional sector wedges** showing **where propagation is
actually happening** — not just where PSK Reporter has historical
data, but what's being heard in the current slot. Antenna color
coding (ANT1/ANT2/rescue) makes each antenna's diversity
contribution instantly visible.

## How does it work?

### Two modes

- **RX mode** (default): Wedge length = unique stations from that
  22.5° azimuth heard in the last 60 minutes.
- **TX mode** (v0.71): Wedge length = max distance in km.
  A single VK6 spot at 16,000 km counts more than 50 Iberian
  spots.

### Data path

Decoder thread → `_emit_map_snapshot_if_open` →
`direction_map_signal.emit(snapshot, band)` →
`Qt.QueuedConnection` → `_on_direction_map_snapshot` (GUI thread)
→ `canvas.update_stations`. Never call widget methods directly
from the decoder thread — always through the signal (cross-thread
safety).

### Sector aggregation

`core/direction_pattern.py` aggregates station receptions into
16 sectors of 22.5° azimuth. Per sector: number of stations,
average SNR, best antenna (ANT1 or ANT2).

Mobile suffixes (`/MM`, `/AM`, `/QRP`) are filtered because
their locator precision is worse (1.5× prec_km).

### Theme

Aurora theme (light, for daytime ops) and Dark theme (night).
Toggle persisted (v0.72).

### Live data

The map dialog stays open during reception and updates per slot
with fresh decodes. On band change, the RX history for the new
band is loaded immediately (60-minute cache).

## When is it useful?

- **"Does a NA QSO make sense right now?"** — One look at the
  map: no vector pointing west → don't waste your time.
- **Diversity visualization:** Which antenna contributes most in
  which direction? ANT1 blue wedges north, ANT2 orange wedges
  south — instantly readable.
- **DX trend:** If a sector suddenly brightens, the band is
  opening in that direction. Live operational info.

## Where to find it?

The map dialog opens from the Settings dialog:
**Settings → tab "Data & Tools" → Open Map ...**

The dialog is non-modal — it stays open and updates live in
parallel with normal reception.

**Settings:**

- RX/TX toggle at the top of the map
- Aurora/Dark theme toggle
- Filter (e.g. DX-only sectors with > 1000 km distance)

**Hardware note:** In TX mode the map shows PSK Reporter reverse
lookups (who heard ME?). The TX antenna is always ANT1 — the map
makes NO antenna selection, it only visualizes what was already
received or transmitted.

## Status

Introduced in v0.66, extended with TX distance mode in v0.71,
extended with Aurora theme in v0.72. All three versions
DeepSeek-reviewed.
