# Final-R1 Review fuer P14 (deepseek-reasoner)

V1→V2→R1 (5/10, 2 KRITISCH) → V3 mit allen R1-Findings → Code → JETZT Final-R1.

## Was wurde umgesetzt

**Aenderungen in `core/ntp_time.py`:**

1. **DEADBAND 0.05 → 0.02** (R1-KRITISCH-F1: Anti-Einfrier am Rand)
2. **Neue Helper-Funktion `_filter_outliers_mad(values, k=2.5)`** (R1-SOLLTE-F3):
   - Hampel-Filter (MAD-basiert)
   - Edge-Cases: n<7 Identity, MAD=0 Identity, <3 uebrig nach Filter Identity
3. **In `update_from_decoded`:**
   - `filtered = _filter_outliers_mad(valid)` vor Median-Berechnung
   - `median_dt = statistics.median(filtered)`
   - Optionales Debug-Logging via `SIMPLEFT8_DT_DEBUG=1` (R1-KOENNTE-F6)
4. **DAMPING bleibt 0.7** (R1-SOLLTE-F4: KISS)
5. **Fast-Path-stdev bleibt ungetrimmt** (R1-HINWEIS-F8 dokumentiert)

**Neue Tests** (`tests/test_p14_dt_symmetry.py`, 10 Tests):
- T1 Mike's 20 Werte → filtered_median im Totband
- T2 n<7 Identity
- T3 MAD=0 Identity
- T4 n=10 mit realistischer Streuung + 1 Outlier → Outlier raus
- T5 Notnagel min3 uebrig
- T6 DEADBAND-Konstante 0.02
- T7 **R1-F2-SANITY-ANKER**: einfacher Median ueber Mike's 20 Werte ×2 Slots → _correction 0.27 → 0.20 (Wurzel-Test, MAD-Filter via monkeypatch zu Identity)
- T8 Mit aktivem MAD-Filter: Mike's Daten → _correction bleibt 0.27 (im Totband)
- T9 Debug-Log Opt-In
- T10 Debug-Log Default-Off

**Bestehender Test angepasst:** `tests/test_modules.py::test_ntp_deadband` — Wert 0.05 → 0.01 (sonst nicht mehr im Totband).

**APP_VERSION:** 0.97.15 → 0.97.16

**Tests:** 1217 → 1227 grün (+10 P14).

## Was DU pruefen sollst

Vollstaendiges Review der Code-Aenderung gegen:

1. **R1-F1 erfuellt?** DEADBAND-Reduktion sauber, kein Side-Effect?
2. **R1-F2 erfuellt?** Sanity-Test (T7) prueft das Richtige? Ist `monkeypatch.setattr(nt, "_filter_outliers_mad", lambda values, k=2.5: list(values))` legitime Bypass-Methode?
3. **R1-F3 erfuellt?** MAD-Filter-Implementation korrekt? Edge-Cases (n<7, MAD=0, <3 uebrig) sauber?
4. **R1-F6 erfuellt?** Debug-Logging vernuenftig? Default-Off?
5. **Thread-Safety:** `_filter_outliers_mad` pure function — kein Lock noetig. `_DT_DEBUG` Modul-Konstante (read-only nach Import). OK?
6. **Performance:** MAD ist 2× median + 1× list-comp. Bei n=20 vernachlaessigbar. OK?
7. **Backward-Kompat:** `dt_corrections.json`-Format unveraendert. Bestehende gespeicherte Werte bleiben gueltig. OK?
8. **Test-Qualitaet:** Decken Tests genug ab? T7 ist wesentlicher Anker (Wurzel-Schutz) — geprueft?
9. **Code-Style:** Kommentare lesbar, Konventionen eingehalten?
10. **Mike's Symptom geloest?** Bei Mike's 20-Werte-Verteilung: filtered_median ~0 → kein Update → Korrektur 0.27 bleibt. Real-Effekt: Mike sieht beim naechsten Slot dass Outliers gefiltert, RX-Panel-Median bleibt ~0.

## Format

Tabelle:

| Schwere | Finding | Datei:Zeile | Empfehlung |

Schweregrade: **KRITISCH** (Push blockiert) | **SOLLTE-FIX** (vor Push fixen) | **KOENNTE** (Nice-to-have) | **HINWEIS** (Info)

Am Ende:
- **Gesamtbewertung 1-10**
- **„Push freigegeben" ODER „Push blockiert wegen X"**

Sei kritisch — wenn was nicht passt, sag es.
