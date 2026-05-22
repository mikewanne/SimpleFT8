# AP-Lite — A-Priori Rescue of Weak QSOs

## In a Nutshell

When your QSO partner is too weak to decode, AP-Lite guesses the few
possible messages and checks which one matches the received signal. "AP"
stands for *a priori* — known in advance.

## The Idea

Mid-QSO, almost everything is already known: both callsigns and the
sequence. Only a few variants remain open:

- Waiting for the report → a handful of numeric values.
- Waiting for confirmation → exactly three: `RR73`, `RRR` or `73`.

If the decoder cannot crack the partner's slot, AP-Lite generates the FT8
reference signal for each of these few variants and compares it against the
received audio. If one variant matches clearly better than all others, it
is considered recognized.

## How the Comparison Works

AP-Lite does not decode from scratch and does not combine slots. It uses two
tricks:

1. **Phase-independent comparison.** The received signal and each candidate
   are correlated in a way that does not care about the current carrier
   phase — the comparison stays stable.
2. **Small frequency search.** Real stations often sit a few hertz off the
   expected frequency; AP-Lite scans that window.

## The Decision — the Margin Test

Instead of a fixed threshold, AP-Lite checks the *gap*: the best candidate
must clearly beat the second-best.

- real message present → clear gap
- noise or a foreign signal only → practically no gap

This relative test is robust — it works even when the signal is so weak
that the absolute correlation value stays small.

## What AP-Lite Does NOT Do

AP-Lite is purely **advisory**. On a match it shows an info line in the QSO
window — nothing more. It does not log a QSO automatically and does not
trigger a transmission. The operator decides. Therefore AP-Lite cannot
"invent" a QSO that never happened.

## Benefit

AP-Lite helps in a narrow band at the very bottom: when the partner signal
is *just* too weak for the normal decoder. The gain is a few dB of
"completion insurance" — marginal QSOs that would otherwise time out. It
pays off most in diversity DX mode, where you deliberately work weak
stations.

## Status Bar Counter

At the bottom of the app you see `AP = (x)`. The x is the number of QSOs
where AP-Lite recognized a message. The counter is persisted and survives
app restarts — intended for field observation.

## Status

Active. AP-Lite is an advisory feature and does not interfere with the QSO
sequence.
