# Intent-Klausel V1 — App-Start-Disclaimer erweitern

**Datum:** 2026-05-15 spätnachmittags
**Version:** v0.97.36 → v0.97.37 (geplant, klein)
**Status:** Trivial-Patch, voller Workflow trotzdem (Mike-Pflicht).

## Trigger

Mike-Sorge bei eventueller Veröffentlichung — Belt-and-suspenders zur
MIT-Lizenz: Intent-Klausel im Hardware-Warnungs-Bestätigungsdialog
(`main.py:_show_hardware_warning` Z.401) erweitern.

## Aktueller Disclaimer-Text (main.py Z.448-454)

```
SimpleFT8 ist eine private Machbarkeitsstudie. Das Projekt dient
ausschließlich dem persönlichen Gebrauch und der Verifikation
technischer Möglichkeiten. Nutzung auf eigene Gefahr — für
Schäden an Hardware, Antennen oder Funkgeräten wird keine
Haftung übernommen.
```

## Neuer Disclaimer-Text (Mike-Wortlaut aus TODO.md Z.979-985)

> „Dieses Projekt entstand als persönliches Bastel-Tool für meinen
> eigenen Funkbetrieb (DA1MHH). Der Quellcode steht unter MIT-Lizenz
> zur freien Verwendung — die Nutzung erfolgt jedoch ausschließlich
> auf eigene Gefahr. Keine Gewährleistung, keine Haftung für
> Hardware-Defekte, Funklizenz-Verstöße oder andere Folgen.
> ANT1 = TX-Antenne (immer). ANT2 = nur RX (NIEMALS TX, Regenrinne
> nicht für Sendeleistung geeignet)."

## Abwägung — Redundanz mit Body

Body-Label (Z.435-440) hat schon prominent (Cyan, fett) die ANT1/ANT2-
Regel. Mike-Wortlaut wiederholt das am Ende. **Lösung:** ANT1/ANT2-
Erwähnung im Disclaimer **drinlassen** als Belt-and-suspenders (Mike-
intendiert für Lizenz-Kontext). Der Body zeigt die HW-Regel; der
Disclaimer bindet sie an Lizenz-Disclaimer.

## Höhe-Risiko

Dialog hat `setFixedSize(540, 340)` (Z.417). Neuer Text ist 4 statt
3 Zeilen länger. Schätzung: Disclaimer-Box wächst um ~30-40px. Höhe
ggf. auf **540×380** anpassen.

## AC-Kriterien

| # | Was |
|---|---|
| AC1 | Disclaimer-Text in `_show_hardware_warning` durch Mike-Wortlaut ersetzt |
| AC2 | DA1MHH-Erwähnung als Bastel-Tool für eigenen Funkbetrieb |
| AC3 | MIT-Lizenz explizit genannt |
| AC4 | Funklizenz-Verstöße als ausgeschlossener Haftungs-Pfad genannt |
| AC5 | Dialog-Höhe ggf. erhöht (540×340 → 540×380) damit Text nicht abgeschnitten |
| AC6 | Existierender Body-Text (ANT1/ANT2 Cyan) bleibt unverändert |
| AC7 | „OK — verstanden"/„Abbrechen"-Buttons unverändert |

## Code-Plan (3 Commits)

| # | Datei | Was |
|---|---|---|
| C1 | `main.py:_show_hardware_warning` | Disclaimer-Text ersetzen + Höhe 540×380 |
| C2 | `tests/test_intent_klausel.py` NEU | 3-4 Source-Level-Tests |
| C3 | `main.py` APP_VERSION 0.97.36 → 0.97.37 + Doku |

## Tests (T1-T4)

- T1 Disclaimer enthält „DA1MHH"
- T2 Disclaimer enthält „MIT-Lizenz"
- T3 Disclaimer enthält „Funklizenz-Verstöße"
- T4 Dialog-Höhe ist 380 (oder höher) damit Text passt

## Field-Test (visuell durch Mike)

- App neu starten → Disclaimer-Dialog kommt mit neuem Text
- ANT1/ANT2-Body weiterhin oben sichtbar
- Text nicht abgeschnitten
- „OK — verstanden" klickt App weiter

## Aus Scope

- Persistenz „nicht mehr zeigen wenn bestätigt" (heute eh nicht, jeder
  App-Start bestätigt erneut)
- Eigenes neues Dialog-Modul `startup_disclaimer_dialog.py` (Mike-TODO
  erwähnt das als Möglichkeit, aber Code liegt heute in `main.py` → dort
  patchen, KISS)
- Übersetzung Englisch (i18n)
