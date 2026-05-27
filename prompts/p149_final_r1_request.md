# P149 — Final-R1: Code-Check vor Commit

V3-Plan ist umgesetzt. Tests grün (2149→2171). Vor Commit/Push einmal
gegenchecken ob der Code wirklich V3-Spec entspricht oder ob V2-Findings
übersehen wurden.

**Strenger Code-Review mit Fokus auf:**

1. Sind die 2× 🔴 R1-Findings (F3 Partner-SNR, F7 count_rescue) tatsächlich
   im Code drin oder nur in Tests?
2. Werden alle 4 neuen Settings tatsächlich aus DEFAULTS gelesen und auf
   `APLite`-Instanz übertragen?
3. Wird `apply_settings` an BEIDEN Stellen aufgerufen (App-Start + Settings-
   Dialog-Save)?
4. Hat das Test-Modus-Pfad-Routing in `mw_cycle._run_ap_lite_rescue` keine
   Logikfehler (versehentliche `add_info` im Test-Modus, falsche
   Frequenz-Quelle)?
5. Bricht der Code irgendwo wenn `qso_sm.qso` None ist?
6. Backward-Compat: Tests, die `MARGIN_MIN` oder `AP_LITE_ENABLED` direkt
   importieren, sehen weiterhin korrekte Werte?

**Antwort: bitte kurz**, 3-5 Sätze pro Punkt, plus Verdikt
„PUSH FREIGEBEN" / „NACHBESSERN".
