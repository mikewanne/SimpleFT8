# Auto-Hunt

[Deutsch](auto-hunt_de.md) | **English**

## What does this feature do?

Auto-Hunt automatically picks the next CQ station from the RX list
and starts the QSO without a manual click. When you want "let it
run" instead of clicking every 30 seconds yourself — Auto-Hunt is
the link between passive reception and serialized QSO flow.

**Important:** Auto-Hunt is Diversity-only. In Normal mode the
button is not visible. Auto-Hunt is firmly coupled to the
Diversity reception strategy.

## How does it work?

### Selection algorithm (scoring)

From the current RX list of CQ callers, the next station is chosen
by priority:

1. **New DXCC entity** — highest priority, always first
2. **Rare callsign** (frequency_in_logbook < 3)
3. **Good SNR** (> -15 dB) — quick, sure QSOs
4. **First reception today** (avoids repeats)

Within the same score group, choice is random — no deterministic
hunt order (looks more natural to observers).

### Dead-man switch (bot protection)

`_auto_hunt_timer` is INDEPENDENT of mouse/keyboard reset.
Mike's deliberate decision: Auto-Hunt should not run forever just
because the operator sits next to it and types. **Hard cap 10
minutes** from activation — then stop, mandatory restart by user
click.

Race double-check in `select_next` is belt-and-suspenders against
the 10-min hard cap (ethical guarantee).

### QSO attempts

Per station max. 3 attempts (module constant `_MAX_ATTEMPTS=3`,
implementation lives in `qso_state.py`). On timeout next station.
On success: ADIF entry, continue with next.

### Band change

On band change: Auto-Hunt is automatically stopped, cooldowns
cleared. Mode change to Normal also stops it automatically
(`auto_hunt_stopped("mode_change")`).

## When is it useful?

- **Active day, many repliers:** You don't want to click for
  hours — Auto-Hunt works quietly in the background.
- **DX sweep:** New DXCC entities are prioritized — you get the
  rare QSOs first.
- **Learning mode:** Run for a while, look at which stations the
  app picked — operational statistics.

## Where to find it?

**Visibility:** `btn_auto_hunt` is only visible in Diversity mode
(mode-coupled since v0.78).

- **Main window:** Button next to the CQ button, Diversity active
- **Click:** Activates Auto-Hunt, timer countdown in status bar
- **Click again** or stop condition: deactivates

**Hardware requirement:** All TX operations over ANT1.
Auto-Hunt does NOT pick an antenna — antenna selection is done by
the Diversity logic (see [diversity-modes.md](diversity-modes.md))
plus antenna preference per station (see
[antenna-preference.md](antenna-preference.md)).

**Status indicators:**

- 1-second polling timer for live countdown during session
- 5-second UI reflex cooldown after stop (prevents reflex click —
  user should consciously decide on restart)

## Status

Implemented in v0.75. Diversity-mode coupling added in v0.78.
Fully tested across real QSOs.
