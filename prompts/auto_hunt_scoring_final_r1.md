FINAL-REVIEW (R1) — Umsetzung des Auto-Hunt-DX-Scorings (P165) ist fertig
codiert + alle Tests gruen (2245 passed, 0 Regression). Pruefe den ANGEHAENGTEN
finalen Code kritisch auf Bugs, Edge-Cases, Regressionen — bevor lokal committet
+ (nach Operator-Freigabe) gepusht wird. KISS-Hobby-Tool, EIN Operator.

================================================================================
WAS UMGESETZT WURDE (gegen das vereinbarte Konzept pruefen)
================================================================================
Ziel: Auto-Hunt bevorzugt seltene/weite/neue DX-Stationen statt lauter
Europa-Nachbarn. Schwaches Signal ist KEIN Ausschluss mehr (FT8 = Schwachsignal-
DX-Modus).

1. log/qso_log.py: pro Land (callsign_to_country, VOLLER Call) ein QSO-Zaehler
   `_country_count` + Land-Band-Set `_country_band`. Neue API
   `get_country_count(country)` + `is_country_worked_on_band(country, band)`.
   Gefuettert in load_adif + add_qso.

2. core/auto_hunt.py:
   - `_MIN_SNR=-21` ENTFERNT → `SNR_FLOOR=-26` (nur Rausch-/Geister-Boden).
   - Modul-Funktion `country_rarity_class(count)` → 0..4
     (0=ATNO, 1=1-5, 2=6-20, 3=21-100, 4=>100).
   - `_RARITY_UNKNOWN=2` fuer Land "?" / fehlendes qso_log.
   - `set_my_grid(grid)` + `self._my_grid`.
   - `_score` ENTFERNT → `_compute_priority(c)` liefert lexikografisches Tupel
     `(R, band_new, -dist, -snr, slot)` (kleiner = hoehere Prioritaet).
   - select_next: SNR-Filter `< SNR_FLOOR`; Slot-Affinitaets-VORFILTER entfernt
     (Slot ist jetzt LETZTE Tupel-Dim); expliziter Vorfilter "schon gearbeitete
     STATION (Call+Band) skippen"; Sortierung per `_compute_priority`.
   - `_HuntCandidate.score`-Feld entfernt.

3. ui/main_window.py: `adif/_backup_qrz_export/` (18k QSOs) wird in
   `_init_qso_log` per load_directory geladen (gemessen 0.47s, Eager-Load).
   `_auto_hunt.set_my_grid(settings.locator)` nach set_qso_log.

================================================================================
VERIFIZIERTE WORKED-EXAMPLES (Test test_full_ranking_matches_deepseek_table)
================================================================================
my_grid=JO31. Historie: DL 4000x(20m), JA 30x(20m), USA 200x(40m); VP8+T7 nie.
Rangfolge IST: VP8 Falkland(-24,13041km) > T7 San Marino(-5,939km,nah!) >
JA Japan(-10,9280km) > USA W(-8,7611km) > DL(+5,216km). = exakt erwartet.

================================================================================
PRUEF-FRAGEN
================================================================================
Q1. Korrektheit `_compute_priority`: ist die Tupel-Ordnung sauber? Kann ein
    None/Typfehler auftreten (callsign_to_distance None, snr None, country "")?
    (snr wird in select_next auf -30 default-gesetzt wenn None, BEVOR der
    Candidate gebaut wird.)
Q2. Vorfilter "schon gearbeitete STATION skippen": korrekt dass eine ANDERE
    Station aus demselben (seltenen) Land waehlbar bleibt? Wird band-spezifisch
    korrekt geprueft (self._band)? Verschleiert der Filter etwas?
Q3. Konsistenz Historie↔Live: load_adif nutzt callsign_to_country(VOLLER Call),
    _compute_priority ebenso callsign_to_country(c.call). Gleicher Schluessel?
    Slash-Calls (EA8/DL1ABC)?
Q4. _RARITY_UNKNOWN=2: ist "neutral=Mitte" fuer '?' richtig, oder Garbage-Decode-
    Risiko (unbekannter Call wird wie 'selten' behandelt)? Lieber 3/4?
Q5. Slot als LETZTE Tupel-Dim (statt Vorfilter): Nebenwirkungen? select_next
    laeuft nur im IDLE → kein Rhythmus-Problem? `_last_tx_even` wird weiter
    gesetzt + in start/stop reset — toter Zustand oder ok?
Q6. Performance: _compute_priority pro Kandidat pro Slot ruft callsign_to_country
    + callsign_to_distance (Praefix-dict-Lookups). Kandidatenzahl pro Slot klein.
    Vertretbar?
Q7. Regressionen: Recent-QSO-Cooldown (P61), Defer (P122), HALT (P147),
    Race-Doppelcheck — alle unberuehrt? (Tests gruen, aber Logik-Blick.)
Q8. Hardware: Aenderung betrifft nur die AUSWAHL — TX bleibt ANT1. Bestaetige
    dass kein TX-Pfad/Antennen-Pfad beruehrt ist.

FORMAT: (1) Verdikt (PUSH FREIGEBEN / BLOCKER), (2) Antworten Q1-Q8 knapp mit
Datei:Zeile, (3) Severity-Tabelle 🔴/🟠/🟡/⚪ falls Findings.

Angehaengt: core/auto_hunt.py (final), log/qso_log.py (final).
