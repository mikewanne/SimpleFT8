# Intent-Klausel V2 Self-Review

**Basis:** `prompts/intent_klausel_v1.md`

## Halluzinations-Check

| V1-Behauptung | Verifikation | Status |
|---|---|---|
| `_show_hardware_warning` in `main.py:401` | grep bestätigt | ✓ |
| Disclaimer-Text Z.448-454 | gelesen | ✓ |
| Body-Text Z.435-440 mit ANT1/ANT2 Cyan | gelesen | ✓ |
| `setFixedSize(540, 340)` Z.417 | gelesen | ✓ |
| Buttons „Abbrechen"/„OK — verstanden" | gelesen Z.468-484 | ✓ |

Keine Halluzinationen.

## Findings

### F1 (HINWEIS) — Word-Wrap auf 540px Breite reicht für ~6-7 Zeilen

Layout-Margin (Z.424): `lay.setContentsMargins(28, 24, 28, 20)`. Verfügbare
Inner-Breite: 540-56 = 484px. Disclaimer-Padding (Z.456-457):
`padding: 8px`. Inner-Text-Breite: 484-16 = ~468px.

Bei Menlo 11pt etwa 60-65 Zeichen pro Zeile. Mike-Wortlaut ist 414
Zeichen → ~7 Zeilen. Bei Höhe 380 statt 340 hat Disclaimer-Box ~110px
Höhe → ausreichend (7 Zeilen × 14px = 98px).

→ **V3-Entscheidung:** Höhe 380. Falls Mike auf macOS visuell Text
abgeschnitten sieht → später auf 400 erhöhen.

### F2 (RISIKO) — `setFixedSize` macht Dialog non-resizable

Falls Display-Skalierung andere Font-Renderings produziert (HiDPI),
könnte Text trotzdem abgeschnitten werden. KISS-Lösung: Höhe großzügig
auf 400 ansetzen (R1 fragen ob 380 oder 400).

### F3 (RISIKO) — Anführungszeichen-Stil

Mike-Wortlaut nutzt deutsche typografische Anführungszeichen („…").
Im Python-String müssen die wörtlich da stehen. Aktueller Disclaimer
hat keine Anführungszeichen — der neue Text bekommt sie. Achten dass
die `"`-Quotes für Python korrekt escaped sind (kein Problem da
deutsche Anführungszeichen `„` und `"` sind, nicht ASCII).

### F4 (VERBESSERUNG) — Disclaimer-Box-Style behält 11pt Schrift

Aktuell `font-size: 11px` (Z.456). Bei längerem Text bleibt das ok.
Keine Änderung nötig.

### F5 (RISIKO) — `<br>` für Zeilenumbrüche nicht im Disclaimer

Body verwendet HTML mit `<br><br>` (Z.437-438). Disclaimer-Label ist
**reiner Text** ohne RichText-Format. Falls Mike explizite Umbrüche
will, müsste `setTextFormat(Qt.RichText)` gesetzt werden ODER
`setWordWrap(True)` reicht (ist Z.460 schon). Mike-Wortlaut hat
natürliche Satzgrenzen → wordWrap reicht.

→ **V3-Entscheidung:** wordWrap belassen, keine HTML.

### F6 (KISS-Check) — Disclaimer ist 1-String, eine `.text=`-Zeile

Patch ist minimal: 1 String-Replace + 1 Höhe-Zahl ändern. ~6 Zeilen
Diff. Voller Workflow ist Workflow-Pflicht-Konsequenz, nicht
inhaltliche Notwendigkeit.

## V3-Anpassungen

- Höhe **540 → 380** (F1 Berechnung, F2 KISS-Buffer ggf. 400 nach R1)
- Mike-Wortlaut wörtlich (mit deutschen Anführungszeichen)
- Body unverändert
- Buttons unverändert

## V2-Bewertung

Aufgabe ist trivial in der Code-Wirkung aber sicherheitsrelevant in
der Aussage (Funklizenz-Disclaimer). R1 soll prüfen ob der Wortlaut
juristisch sauber ist und ob die Höhe-Anpassung das richtige Maß hat.
