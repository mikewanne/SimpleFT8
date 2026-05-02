# Caller Waitlist

[Deutsch](waitlist_de.md) | **English**

## What does this feature do?

When you call CQ and multiple stations reply simultaneously, you
normally lose all but one — you have to manually pick, the others
give up. SimpleFT8 puts all repliers into a **waitlist** and works
them off automatically after the current QSO. Nobody gets forgotten.

## How does it work?

When the app is in CQ mode (`btn_cq` active) and multiple stations
reply in the same slot, the QSO state machine registers all
repliers:

- **Grid reply** (`DA1MHH DK5ON JO31`) — the standard first reply
- **Report reply** (`DA1MHH DK5ON -15`) — direct report without
  grid (common with DX and contesters)

Both types go into the waitlist. After the current QSO completes
(RR73 or 73 received/sent), the state machine checks the waitlist:

1. List exists, at least one entry → reply to next station
   automatically (same flow as manual click)
2. Per QSO max. 3-5-7-99 attempts (Settings, "Call attempts")
3. On timeout (~3 min) → entry discarded, next from list

The list does not survive a band change — it is cleared on band
switch (new context).

## When is it useful?

- **DX pile-ups:** Several stations calling at the same time — you
  serve all of them without anyone having to abort.
- **Contest mode:** Repliers are serialized, the counter goes up
  fast.
- **Active day:** 5–10 replies per CQ are normal — the waitlist
  makes them all reachable.

## Where to find it?

- **QSO panel:** When the waitlist has entries, a hint
  `Waitlist: 3 stations` appears in the QSO status.
- **Main window:** Active in CQ mode, no separate toggle — the
  waitlist is always active when `btn_cq` is on.
- **Auto-Hunt synergy:** With Auto-Hunt active, CQ callers in the
  RX list are also worked off automatically (see
  [auto-hunt.md](auto-hunt.md)).

**Hardware requirement:** All replies are sent over ANT1 (TX) —
automatically, regardless of the Diversity RX antenna.

## Operator visibility

The operator sees the current station and the number of waiting
stations in the QSO panel. On request, the operator can manually
skip the list or abort the active QSO — the next station will
then be contacted immediately.

Mike's proof (DL3AQJ): real QSO on 40m FT8 — F1IQH calls during
the active QSO with DL3AQJ. F1IQH is automatically placed in the
waitlist and answered immediately after the DL3AQJ QSO completes.
No manual intervention. Screenshot in
`docs/screenshots/warteliste_qso.png`.
