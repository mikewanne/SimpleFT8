# R1 — DeepSeek-V4-pro Code-Review für P54-FIX

Du bist Senior-Code-Reviewer. Sprache: Deutsch. **Dies ist ein
Code-Review, KEIN Konzept-Review.** Das Konzept ist von Mike
festgelegt und nicht zur Diskussion. Prüfe ausschließlich:
- Implementierungs-Bugs
- Race-Conditions
- Hardware-Sicherheits-Verletzungen
- Halluzinationen in V1+V2
- Edge-Cases die übersehen wurden
- Test-Coverage-Lücken

## Kontext

**Mike's Konzept:** P54 (heute Mittag gebaut) speichert beim TUNE
einen Wunschwert `(band, 10W, rf=10)` — egal was die Antenne real
macht. Das zerstört die Kalibrierungs-Philosophie der bestehenden
`RFPresetStore`-Tabelle. P54-FIX baut Closed-Loop-Convergenz in die
TUNE-Phase ein: rfpower wird hochgeregelt bis FWDPWR ≈ 10W rauskommt,
DANN speichern wir den echten Slider-Wert.

Plus: Krücken-Skalierung in `_apply_rf_preset` wenn nur 1 Stützpunkt
für ein Band existiert (z.B. nur 10W, aber User funkt 50W):
`rf = anchor_rf × (target_watt / anchor_watt) × 0.9`. Sicherheits-
Faktor 0,9 ist Mike's explizite Wahl gegen nichtlineare PA-Charakteristik
und Tuner-Verluste auf nicht-resonanten Bändern. **Nicht zur Diskussion.**

## V1+V2 Akzeptanzkriterien

(siehe `p54_fix_v1.md` + `p54_fix_v2.md` als beigelegte Files)

Zusammenfassung:
- AC1: `_tune_converge_to_target(target_w=10, duration_s=5)` Helper
- AC2: TUNE-Sequenz wird zweiphasig: Phase A (Tuner-Match, ~10s) + Phase B
  (rf-Convergenz, max 5s, max 5 Iter)
- AC3: `_tune_post_swr_check` speichert konvergierten Wert statt hart 10
- AC4: `_kruecken_skalierung` Helper in `_apply_rf_preset`
- AC5: Hardware-Schutz ANT1, SWR-Watchdog-Bypass, Slider-Clamp 1..100
- AC8: 16 Tests (T1-T16 inkl. V2-Ergänzungen)

## Pflicht-Fragen

1. **QEventLoop + QTimer.singleShot Pattern** für synchrone
   Convergenz-Schleife im GUI-Thread: ist das sauber, oder gibt's
   bessere Qt-Patterns? Re-entrant-Probleme?

2. **Cancel-Flag-Check** in jeder Iteration (V2-F1): ausreichend, oder
   muss QEventLoop.quit() expliziter Mechanismus sein?

3. **Hardware-Pflicht ANT1:** wird in Phase B nichts geändert (`set_tx_antenna`
   bleibt einmal-Call aus `_start_auto_tune_for_band_change`). Korrekt?
   Wäre ein zusätzlicher ANT1-Set in jeder Iter Belt-and-Suspenders nötig?

4. **PA-Schutz bei rfpower=1:** Wenn FWDPWR >> Ziel (z.B. 20W bei
   rf=10) → Convergenz reduziert auf rf=1 (Minimum). Bei rf=1 kann
   FWDPWR vielleicht 0.5W sein → unter Toleranz → konvergiert auf
   rf=1 für „10W". Falscher Wert wird gespeichert.
   
   Sollten wir Plausibilitäts-Check einbauen? „Wenn konvergierter
   rf < 3 oder > 50: kein Save, weil unrealistisch für 10W-Ziel"?

5. **Tuner-Match-Phase A:** 10s reichen typisch für LDG AT-200 Pro.
   Aber: was wenn Tuner-Match länger braucht (matched gar nicht in
   10s)? Dann ist Phase B mit instabiler Last → Convergenz
   unzuverlässig. Mitigation?

6. **Krücken-Sicherheits-Faktor 0,9:** Mike's Wahl, nicht zur
   Diskussion. ABER: prüfe ob die FORMEL stimmt. Bei `anchor_rf=14`
   (Anker für 10W) und `target_watt=50` → `rf = 14 × 5 × 0.9 = 63`.
   Plausibel?

7. **Krücken-Faktor bei sehr niedrigen Anker-Werten:** anchor_watt=10,
   anchor_rf=3 (sehr resonante Antenne mit niedrigem Slider) →
   target_watt=80 → rf = 3×8×0.9 = 21.6 ≈ 22. Reicht 22% Slider für 80W?
   Wahrscheinlich nicht. Aber Closed-Loop greift dann ja sowieso.
   
   Sollten wir einen Minimum-Startwert bei Krücke einbauen (z.B.
   `max(target_watt, krucke)` damit zumindest 1:1 Annahme als
   Fallback)?

8. **Test-Coverage:** 16 Tests T1-T16. Welche Edge-Cases fehlen noch?

9. **Backwards-Kompatibilität:** Existierende `rf_presets.json` mit
   den heute Mittag gebauten fälschlich harten (band, 10, rf=10)-
   Einträgen aus P54 → werden beim nächsten TUNE überschrieben.
   Kein Migration-Script nötig?

10. **Settings-Tabelle Visualisierung:** Während Convergenz läuft
    (5s Phase B), könnte ein User die Settings öffnen und die Tabelle
    inspizieren. Während dieser Zeit ist der „alte" 10W-Wert noch
    drin, der „neue" konvergiert noch. Race? Wahrscheinlich nicht
    (Store-Save passiert erst in `_tune_post_swr_check` nach Phase B).
    Bitte verifizieren.

## Antwortformat

```
## R1-Findings

### F1 (ROT/ORANGE/GELB): <Titel>
- Pfad/Symptom/Fix

## Pflicht-Fragen-Antworten
1. ...
...

## Empfehlung
Push-Status: FREIGEGEBEN / FIX / BLOCKIERT
KP (kritische Punkte): ...
```

Max 1500 Wörter. **Konzept-Diskussion (Sinnhaftigkeit der Idee) ist
nicht erwünscht — wir bauen das so, Mike hat entschieden.** Nur
Code-Qualität, Bugs, Sicherheit.
