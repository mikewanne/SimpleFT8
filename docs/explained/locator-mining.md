# Live Locator Mining

[Deutsch](locator-mining_de.md) | **English**

## What does this feature do?

While SimpleFT8 decodes, it extracts **Maidenhead locators
directly from CQ calls and QSO replies** — and writes them to a
persistent JSON database. On session start and on band change,
exact station positions are instantly available — no online
lookup, no waiting, no fallback to country centroids.

No other FT8 client does this in this form.

## How does it work?

### Sources

Locators come from multiple sources, with priority:

```
cq_6 > psk_6 > qso_log_6 > _4-variants
```

- **cq_6:** 6-character locator from a live received CQ
  (`CQ R9CA LO97`) — the most accurate source, because current.
- **psk_6:** 6-character locator from PSK Reporter (online
  lookup, background polling).
- **qso_log_6:** 6-character locator from own ADIF logbook
  (bootstrap at start).
- **_4-variants:** 4-character fallback when nothing better
  is available.

A better source never overwrites a worse one — a 6-character live
CQ locator stays even if a 4-character ADIF entry shows up later.

### Persistence

The DB lives at `~/.simpleft8/locator_cache.json`:

- **Auto-save every 5 minutes** during operation
- **Save on app close**
- Survives hard kills

### Bootstrap

On first start (or empty DB), ADIF logbooks are imported (e.g.
LotW, QRZ, own logbook). This fills the DB immediately with
thousands of locators.

### Threading

`core/locator_db.py` uses `threading.RLock` to handle concurrent
access from the decoder thread + PSK worker. `get()` returns a
copy — no external references to internal data.

### Mobile suffix handling

Suffixes like `/MM` (Maritime Mobile), `/AM` (Aeronautical
Mobile), or `/QRP` are flagged with `prec_km × 1.5` — these
stations move, the locator is an estimate. In the direction map
they may be filtered out.

## When is it useful?

- **Precise map display:** Instead of country centroids, exact
  positions are shown — diversity analysis becomes geographically
  correct.
- **DX trend analysis:** Who's active in which sector right now?
  Answerable instantly thanks to a live DB.
- **Logbook boost:** Known locators are pre-filled in the logbook
  on QSO entry.

## Where to find it?

The feature is always active — no UI toggles. The DB lives in
the background.

**Visible places:**

- **RX panel:** km column shows distance thanks to locator
  (otherwise empty).
- **Direction map:** all points are based on the locator DB.
- **Logbook:** locator input is pre-filled where known.
- **Log file:** `simpleft8.log` shows
  `[LocatorDB] total in DB: N` at startup.

## Status

Implemented in v0.67, ADIF bootstrap logic extended in v0.70.
Currently over 9,000 calls in the DB, growing every session.
