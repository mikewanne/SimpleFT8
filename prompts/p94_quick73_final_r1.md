# P94 — Final-R1 Codereview (v0.97.66 vor Push)

Du bist Senior Python-Reviewer. Schaue dir die finale Implementierung von
P94 an und gib einen klaren Push-Freigabe-Status (PUSH FREIGEBEN ✅ /
NACHBESSERN / HALT) mit kurzer Begründung.

## Was P94 macht

Mike-Field-Test 20.05.2026 v0.97.65: 9A4AA ruft 4 min nach abgeschlossenem
QSO erneut mit Report → App startet komplettes neues QSO (5 Slots Report-
Austausch) statt höfliches einmaliges 73.

Fix in `ui/mw_cycle.py`: neue Methode `_p94_quick73_filter` als
Pre-Filter VOR OMNI-Block und `qso_sm.on_message_received`. State-Machine
unverändert. Konstante `_QUICK73_WINDOW_S = 1800` (30 Min).

Plus: `core/auto_hunt.py:_RECENT_QSO_COOLDOWN_S` von 300 → 1800 (Konsistenz
mit Quick-73-Fenster). Hard-Cap-Timer (10 Min) UNCHANGED.

## R1-Brainstorm-Findings (alle eingebaut)

- ✅ Filter-Position vor OMNI-Block (verhindert OMNI-getriggerten Neuanruf)
- ✅ State-Check IDLE/CQ_WAIT/CQ_CALLING (kein Eingriff in aktives QSO)
- ✅ `audio_freq_hz`-Restore via `tx_finished`-Signal (R1-F3 ORANGE — sticky-fix)
- ✅ `tx_even = not their_even` (Gegenparität für Slot-Sync)
- ✅ `_quick73_sent` defensiv via getattr (OMNI-Integration-Test bleibt grün)
- ✅ `encoder.transmit` returnt False → Set NICHT markiert (Retry-Möglichkeit)

## Tests

12 neue Tests in `tests/test_p94_quick73.py` (T1-T12). Alle PASSED.
Suite: 1626 → 1638 (+12, alle grün).

## Bewertungs-Fragen

1. Reichen die 12 Tests die Edge-Cases ab (Encoder-Race, State-Wechsel,
   Band-Wechsel, 73/RR73-Echos)? Welche fehlt?
2. Ist die `audio_freq_hz`-Restore-Mechanik race-frei? Connect→transmit→
   disconnect bei Fehler-Path?
3. Hardware-Sicherheit: TX läuft im Quick-73-Pfad immer über ANT1
   (Diversity verriegelt) — bestätigen oder Lücke?
4. Performance: jeder Slot → Filter-Aufruf. Lookup in dict ist O(1).
   Akzeptabel? Set-Größe wächst mit Anrufen — Cleanup nur bei Window-
   Ablauf (discard). Memory-Issue möglich?
5. Mike-Etikette ✓? Wenn 9A4AA innerhalb 30 Min 5x ruft, kriegt er
   genau 1× 73 → danach Funkstille von uns. WSJT-X-konform?

Gib eine ehrliche Bewertung. Halluzinationen sind okay, Mike prüft eh
nochmal mit Field-Test.
