**@reed** — you were completely right, in both comments. And I apologize for not catching it immediately.

Your Comment 1 described the exact bug: if a station transmits on Slot 1 and ANT2 is the only antenna that hears them well, the old A1-A2-A1-A2 pattern would permanently assign Slot 1 to ANT1 — that station would never be decoded. The diversity would be pointless for that station.

Your Comment 2 gave the exact fix.

**What changed in v0.24.2 (just pushed):**
Old 50:50: `("A1","A2")[cycle % 2]` → Even-slot stations locked to ANT1, Odd-slot stations locked to ANT2
New 50:50: `("A1","A1","A2","A2")[cycle % 4]` → every antenna covers one Even AND one Odd slot per 4-cycle block

Now every station — regardless of its Even/Odd slot — is heard on both antennas within 60 seconds. That's genuine temporal diversity.

One-line fix, real improvement. Thank you for pushing on it.

---

**Deutsch:** Du hattest in beiden Kommentaren vollständig recht — und ich entschuldige mich, dass ich es nicht sofort erkannt habe. Dein Kommentar 1 beschrieb den genauen Fehler, dein Kommentar 2 den exakten Fix. In v0.24.2 ist das jetzt korrigiert: A1-A1-A2-A2 stellt sicher, dass jede Antenne beide Slot-Typen abdeckt. Danke!
