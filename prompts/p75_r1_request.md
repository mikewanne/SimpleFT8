# P75 Bundle — R1-Review-Anfrage an DeepSeek-V4-pro

Du bist DeepSeek-V4-pro. P75 ist ein UI-Bundle nach Mike-Field-Test
18.05.2026 (autonomer Workflow während Mike unterwegs).

## Aufgabe

Review **`prompts/p75_button_modal_consolidation_v1.md`** (V1-Plan im
Anhang) gegen den echten Code (5 Files im Anhang). Klassifikation
🔴/🟠/🟡/⚪.

**KEY-Entscheidung in Teil C**: Variante A (Light-Touch Header-Banner)
vs Variante B (State-Machine-Dialog). Bitte begründet wählen.

**Mike's Leitlinie:** „SimpleFT8 — Name ist Programm. So viele Infos
wie nötig, so wenig wie möglich." KISS-Vorrang. Hobby-Funker-Tool,
KEIN Contest-Tool.

## Konkrete Fragen

1. **Teil A (Button-State-Reset):** Reicht `btn_tune.setChecked(False)`
   mit blockSignals oder gibt es Race-Risiko bei User-Toggle-Off in
   exakt dem Moment wenn Auto-Stop-Timer feuert? (siehe `_tune_stop`
   in mw_tx.py — token-Check ist erste Bedingung)

2. **Teil B (Style-Harmonisierung):** Eigenes Style-Cluster für TUNE
   (gelb-dezent inaktiv, grün aktiv) vs. nur denselben `_mode_btn_style`
   wie OMNI/CQ verwenden? Mike's Argument für eigenes: TUNE ist Setup-
   Aktion, nicht TX-Aktion → Farbe-Code als visuelle Klassifikation.

3. **Teil C (Variante A vs B):** Welche ist KISS-konformer für Mike's
   konkretes Symptom „viele fenster die aufploppen verwirren"?
   - A: Header-Banner im DXTuneDialog mit Übergangstext. ~30 Min Code.
     Visuell „Phase 1 → Phase 2" suggeriert.
   - B: State-Machine-Dialog (DXTuneDialog erweitert um TUNE-Phase).
     ~3-4 h Code, mehr Race-Risiko, sauberere UX.
   Bitte konkrete Empfehlung mit Begründung.

4. **Teil D (SWR-bad-QMessageBox raus):** Stattdessen
   `qso_panel.add_info(...)` als rote Zeile. Verliert man wichtige
   User-Aufmerksamkeit? Oder ist eine Statusbar-Zeile bei SWR-bad
   ausreichend?

5. **Teil E (KISS-Check FWDPWR-Reduktion):** Mike sagte „so wenig wie
   möglich". P71 hat den Status auf `ANT1, 10W → FT8 — N/Ms · SWR x.x
   · FWDPWR x.xW` erweitert. Lohnt sich FWDPWR-Live-Anzeige für Hobby-
   Funker, oder zurück auf `ANT1 10W · N/Ms · SWR x.x`? Mike hat das
   bisher nicht moniert — also vielleicht behalten?

6. **Test-Coverage:** Reicht T1-T7? Was fehlt?

## Architektur-Constraints

- Hardware-Pflicht **ANT1=TX only** für alle TX-Pfade.
- Keine Modul-Splits, keine neue Threading.
- 1453 Tests bestehend — müssen grün bleiben.
- Workflow-Pflicht: V1→V2→R1→V3→Code (Mike strikt).

## Format der R1-Antwort

- Findings F1, F2, ... mit Klassifikation + Begründung + Lösung.
- **Klare Empfehlung Variante A oder B** (1 Satz).
- Push-Freigabe-Empfehlung: „PUSH FREIGABE NACH Findings F1-Fx" oder
  konkrete Blocker.
- Halluzinations-Check: nicht-verifizierte Code-Stellen explizit
  markieren.

Max 1500 Wörter.
