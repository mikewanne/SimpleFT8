# QSO Flow — How SimpleFT8 Runs a Contact

## In a Nutshell

SimpleFT8 handles the entire FT8 exchange automatically once you start it. You click a station (Hunt mode) or press CQ (CQ mode), and the state machine takes care of the message sequence, timeouts, retries, and logging.

## Two Operating Modes

| Mode | You do | SimpleFT8 does |
|------|--------|-----------------|
| **Hunt** | Click a station in the RX list | Send report, exchange confirmations, log QSO |
| **CQ** | Press the CQ button | Call CQ, answer callers, manage waitlist, log each QSO |

Both modes share the same underlying message exchange. The difference is who initiates.

## Hunt Mode — Step by Step

1. **Click a station** in the RX panel. SimpleFT8 sends your signal report to that station.
2. **Wait for report.** The other station sends their signal report back.
3. **Send R-report.** SimpleFT8 confirms by sending your report with an "R" prefix (e.g., `R-12`).
4. **Wait for RR73.** The other station confirms with RR73 or 73.
5. **Send RR73.** SimpleFT8 sends RR73 and logs the QSO to your ADIF file.
6. **Wait for 73.** SimpleFT8 waits up to 3 cycles for a final 73 confirmation, then returns to idle.

If the other station does not respond after 2 cycles, SimpleFT8 retries automatically. After the configured maximum number of attempts (default: 3), the QSO times out.

## CQ Mode — Step by Step

1. **Press CQ.** SimpleFT8 sends `CQ DA1MHH JO31` on a free frequency.
2. **Station answers.** SimpleFT8 detects the caller and begins the QSO exchange automatically.
3. **QSO completes.** The contact is logged, and SimpleFT8 checks the waitlist.
4. **Next caller.** If stations called during the QSO, the next one in the waitlist is answered immediately. Otherwise, CQ resumes.

### The Waitlist

When you are in the middle of a QSO and another station calls you, SimpleFT8 adds them to a waitlist. Both grid-based and report-based replies are accepted. After your current QSO finishes, the next station from the waitlist is answered without sending CQ again. This keeps pile-up efficiency high.

The QSO panel shows the waitlist as it updates: `Warteliste: EA3FHP, W1XY`.

## Even and Odd Slots — [E] and [O]

FT8 operates in 15-second time slots, alternating between even and odd:

| Second | Slot | Who transmits |
|--------|------|---------------|
| 0-15 | Even [E] | One side of the QSO |
| 15-30 | Odd [O] | The other side |

SimpleFT8 automatically picks the correct slot:

- **Hunt mode:** You transmit in the opposite slot of the station you clicked. If they transmitted in an even slot, you transmit in the odd slot.
- **CQ mode:** You transmit in a fixed slot (the opposite of the current cycle when you press CQ).

The slot indicator [E] or [O] in the control panel shows which slot you are using.

## RR73 Courtesy Repeat

Sometimes the other station keeps sending their R-report because they did not receive your RR73. SimpleFT8 handles this automatically:

- After sending RR73, SimpleFT8 enters WAIT_73 state.
- If the other station repeats their R-report, SimpleFT8 resends RR73 (up to 2 times).
- After 2 courtesy repeats, further messages are ignored.

This prevents endless loops while still being polite on the air.

## WAIT_73 — Waiting for Confirmation

After logging a QSO, SimpleFT8 waits up to 3 cycles for a final 73 from the other station:

- If 73 is received, the QSO is marked as confirmed in the UI.
- If no 73 arrives within 3 cycles, the QSO is still logged (RR73 was already sent), and SimpleFT8 resumes CQ or returns to idle.

The QSO is already saved to your ADIF file at the moment RR73 is sent. The WAIT_73 state only controls the UI confirmation indicator.

## Timeouts

| Timeout | Duration | What happens |
|---------|----------|--------------|
| Per-step retry | 2 cycles (~30 s) | Resends the last message |
| Global QSO timeout | 3 minutes | Aborts the QSO entirely |
| WAIT_73 timeout | 3 cycles (~45 s) | Resumes CQ or returns to idle |
| Worked-station block | 5 minutes | Same station cannot be worked again |

## Forward Jumps

SimpleFT8 handles out-of-order messages intelligently:

- If you receive RR73 while still waiting for a report, SimpleFT8 jumps ahead and sends 73 immediately.
- If you receive an R-report during your initial call, SimpleFT8 jumps directly to RR73.

This matches WSJT-X behavior and completes QSOs faster when the other station is ahead in the sequence.

## HALT Button

Press HALT to immediately stop everything: CQ mode, active QSO, and TX. The radio returns to receive-only. Use this when you need to interrupt operations immediately.

## Tips for Operators

- **In Hunt mode**, let SimpleFT8 handle the retries. Clicking the same station again while a QSO is running will restart the sequence from the beginning.
- **In CQ mode**, the waitlist makes pile-ups efficient. You do not need to manually pick callers.
- **Watch the QSO panel** for status messages. It shows every state transition, retry, and timeout.
- **Worked-station blocking** prevents duplicate QSOs for 5 minutes. If you need to work the same station again, wait for the block to expire.
