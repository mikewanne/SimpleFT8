# Operator Presence Timer

## In a Nutshell

SimpleFT8 enforces a 15-minute inactivity timeout to guarantee that a licensed operator is always at the controls — no exceptions, no configuration, no workaround.

## The Problem

FT8 is highly automated by nature. Software decodes signals, picks the right response, and transmits it — all without the operator touching anything. That efficiency is a feature, but it creates a real risk: if you walk away and forget about it, your station keeps calling CQ and working contacts on its own. At that point, you're running an unattended bot, which violates amateur radio regulations in most countries.

German law is explicit about this. The operator must be able to intervene at any time. Other countries have similar rules, and the IARU recommends attended operation for all automated digital modes. SimpleFT8 takes this seriously. Rather than relying on the operator's good intentions, the software enforces presence with a hard timer.

## How It Works

- A fixed **15-minute countdown** starts whenever SimpleFT8 detects no mouse movement or keyboard input inside the application window.
- A **4-pixel-high progress bar** sits directly below the CQ button, acting as a visual indicator:
  - **Green** — more than 5 minutes remaining. Everything is fine.
  - **Yellow** — between 2 and 5 minutes remaining. You should move the mouse or press a key.
  - **Red** — less than 2 minutes remaining. CQ will stop soon.
- Any **mouse movement or keyboard activity inside the SimpleFT8 window** resets the timer to 15 minutes. Activity in other applications does not count — you must actually be looking at SimpleFT8.
- When the timer reaches zero:
  - **CQ calling stops immediately.** No new CQ transmissions are sent.
  - **No new TX sequences are started.** The station goes silent.
- **Active QSOs are always protected.** If you are mid-QSO (anywhere from TX_CALL through TX_RR73), the exchange runs to completion. SimpleFT8 never drops a QSO partner mid-contact — that would be poor operating practice and pointless.
- **After the QSO finishes**, TX remains blocked until the operator provides input (mouse or keyboard inside the window).

## Legal Background

- **Germany, Section 16 AFuV (Amateurfunkverordnung):** The operator must be able to intervene in the operation of the station at any time. Unattended automated operation is not permitted for standard amateur licenses.
- **IARU Recommendation:** Automated digital modes should be operated in attended mode. The operator should monitor the station and be ready to take control.
- **SimpleFT8 is not a bot.** It is an operator assistance tool. It automates the repetitive parts of FT8 (decoding, response selection, TX sequencing) but requires a human operator to be present. The presence timer is the mechanism that enforces this distinction.

## Pros and Cons

| Pro | Contra |
|-----|--------|
| Legal compliance with AFuV and international regulations | You need to move the mouse every 15 minutes |
| Proves that a human operator is monitoring the station | Can interrupt long unattended CQ sessions (by design) |
| QSO protection — an active contact always finishes cleanly | — |
| No configuration means no temptation to set it to 24 hours | — |

## Settings

None. The timer is fixed at 15 minutes. This is a deliberate design decision: if it were configurable, someone would set it to 999 minutes, defeating the entire purpose. The value of 15 minutes strikes a balance — long enough that normal operating doesn't trigger it, short enough that walking away actually stops the station.

## Status

Active since v0.31. Not optional. Cannot be disabled.
