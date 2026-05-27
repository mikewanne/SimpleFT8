# P149 — AP-Lite Diagnose-Modus: R1-Review-Request

**Kontext für DeepSeek:** SimpleFT8 ist eine FT8-Hobby-Funker-App
(FlexRadio + Diversity, Mike-Spec „KISS, kein Contest-Tool"). AP-Lite ist
seit v0.97.90 (22.05.2026, Option D) drin als A-Priori-Kandidaten-Matching
für marginale QSO-Decodes — rein BERATEND (kein TX, kein ADIF, nur
Info-Zeile im Panel). Mike's Treffer-Zähler steht seit 5 Tagen auf 0.

Wir wollen jetzt einen Diagnose-Modus bauen damit wir verstehen:
- Wird AP-Lite überhaupt aufgerufen, oder schlägt einer der 4 Guards immer zu?
- Wenn aufgerufen — sind die Margen knapp unter Threshold oder weit weg?
- Wie performt der Algo bei dekodierten Partnern (Decoder-Wahrheit als Soll)?

Plan-Datei `ap_lite_diagnose_v1.md` enthält:
- §1-§3: Mike's Problem + Spec
- §4: Code-Änderungen (4 Settings-Keys, ap_lite.py erweitern, mw_cycle.py
  Test-Modus + Logging, UI 4 Widgets)
- §5: Tests (18 Stück geplant)
- §6: Risiken
- §10: V2-Self-Review mit 13 Findings (2 echte Bug-Fänge eingebaut)

**Mike-Spec Kernpunkte:**
- 4 neue Settings: `ap_lite_enabled`, `ap_lite_test_mode`, `ap_lite_min_snr_db`,
  `ap_lite_strictness` (3 Stufen locker/normal/streng → margin 0.03/0.05/0.10)
- Test-Modus: AP-Lite läuft AUCH bei dekodiertem Partner, NUR Logging, KEINE
  Info-Zeile (sonst Doppel-Anzeige)
- SNR-Filter: AP-Lite nur wenn last_snr ≤ Schwelle (außer im Test-Modus)
- Debug-Log-Calls via `core.debug_log.debug_log("AP-LITE", ...)` an
  strategischen Punkten (Guards in mw_cycle + Scoring in ap_lite.py)
- UI in Tab „Daten & Tools" als GroupBox „AP-Lite (Diagnose)"

## R1 — Was wir wissen wollen

**Strenge Review-Anforderung — bitte als kritischer Reviewer** (V4-pro 60+
Cycle Erfahrung — finde echte Bugs, keine Mikro-Verbesserungen):

### F1 Ist die Test-Modus-Architektur sauber?
Im Test-Modus läuft AP-Lite parallel zum Decoder. Verlassen wir uns auf
`_partner_msg.text` als „Decoder-Wahrheit" — aber FT8-Decoder kann auch
falsche Decodes liefern (LDPC-Fehlkorrekturen, Pile-up). Wäre das eine
Falsche-Sicherheits-Aussage im Log? Wie gehen wir damit um — als „heuristische
Soll-Wert" annehmen oder explizit Confidence einbauen?

### F2 Frequenz-Quelle im Test-Modus (V2-F6)
V3-Plan: im Test-Modus nutzen wir `_partner_msg.audio_freq_hz` als
Frequenz für `correlate_candidate()` statt `qso_sm.qso.freq_hz`. Ist
das richtig? Sind die beiden Werte im normalen Pfad immer identisch oder
gibt es Drift?

### F3 SNR-Filter-Semantik
`last_snr ≤ min_snr_db` heißt: AP-Lite nur bei SCHWACHEN Signalen. Aber
`_last_snr` wird in `qso_sm` aktualisiert NACH erfolgreichem Decode. Bei
einem verpassten Slot (typischer AP-Lite-Use-Case!) ist `_last_snr` der
SNR-Wert des LETZTEN dekodierten Slots — also evtl. veraltet. Macht die
Filter-Logik so noch Sinn? Oder müsste der Filter „last_snr ≤ -X **oder**
last_snr unset" sein?

### F4 Strenge-Mapping
Wir wollen 3 Stufen: locker=0.03 / normal=0.05 / streng=0.10.
Heutiger Stand: MARGIN_MIN=0.05. Synthetisch gemessen (laut Modul-
Kommentar): „echte Nachricht → Marge ~0.11, Rauschen → Marge ≤ 0.023".

- Ist 0.03 (locker) gefährlich nah am Rauschen-Mittelwert 0.023?
- Sollten wir „streng" auf 0.15 setzen (statt 0.10) um näher am
  echten-Nachricht-Schnitt von 0.11 zu sein?
- Oder sind die synthetischen Werte überholt — sollten wir empirisch
  aus dem ersten Diagnose-Lauf neu kalibrieren?

### F5 Performance bei Test-Modus mit vielen Decodern
Annahme im V2-F5: max 1 try_rescue/Slot weil AP-Lite an QSO-State gekoppelt
ist. Korrekt? Oder gibt es einen Pfad wo mehrere QSOs gleichzeitig laufen
und try_rescue mehrfach in einem Slot triggert?

### F6 Settings-Live-Update (V2-F8/F9)
Plan: `apply_settings(settings)` einmal beim App-Start + nochmal nach
Settings-Dialog-Save. Race-Fenster: läuft während Dialog-Save gerade
`try_rescue` mit alten Werten, ist das ein Problem? Brauchen wir Lock
oder ist „nächster Slot greift" gut genug für eine Diagnose-Funktion?

### F7 Persistenz `rescue_count`
Im Test-Modus zählen wir auch unechte Treffer (gegen Decoder). Soll
`rescue_count` (`~/.simpleft8/ap_lite_stats.json`) das mitzählen? Heute
„zählt erfolgreiche AP-Lite-Treffer über App-Neustarts". Im Test-Modus
würde der Counter explodieren ohne Aussage. Vorschlag: im Test-Modus
NICHT `_save_rescue_count()` aufrufen. Oder separater Counter
`test_rescue_count`?

### F8 Hardware-Sicherheit (CLAUDE.md PFLICHT-Frage)
AP-Lite ist beratend, kein TX. Aber: triggert irgendwo ein Settings-Save
des `test_mode`-Keys einen ungewollten Side-Effect (z.B. dass beim Start
Test-Modus AN ist und Mike's QSO-Panel mit Algo-Treffern gemüllt wird)?
Anti-Stolperfalle bauen?

### F9 Backward-Compat
Bestehende ~30 ap_lite-Tests (tests/test_ap_lite_*.py) müssen alle weiter
grün bleiben. Es gibt Tests die `MARGIN_MIN` direkt importieren — bleibt
das funktional? Welche Tests werden brechen wenn try_rescue jetzt
`self.margin_min` statt `MARGIN_MIN` nutzt?

### F10 Was haben wir VERGESSEN?
Freie Antwort — schauen Sie nochmal über den V1+V2-Plan drüber. Welche
Stolperfalle sehen Sie die wir nicht im Blick haben?

## Output-Format

Pro Frage F1-F10:
- 🔴 ROT (Show-Stopper, V3-Korrektur PFLICHT)
- 🟠 ORANGE (eingebaut werden sollte, sonst ist V3 fragil)
- 🟡 GELB (nice-to-have, kann später)
- 🟢 GRÜN (passt schon im V2-Stand)

Plus ein abschließendes Verdikt: „PUSH FREIGEBEN für Code-Phase" /
„NACHBESSERUNG NÖTIG" mit den 2-3 wichtigsten Action-Items.
