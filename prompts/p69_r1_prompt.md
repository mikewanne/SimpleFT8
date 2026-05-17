# R1-Review: P69 Konfidenz-Intervalle (Bootstrap-CI)

Du bist DeepSeek-V4-pro, externer Reviewer. Du sollst keine eigenen
Code-Vorschläge schreiben — nur Findings (Bug rot, Risiko orange, Verb
gelb, Hinweis grau).

## Kontext

SimpleFT8 ist eine FT8-Software (Hobby-Projekt von DA1MHH) mit
Diversity-Antennen-Auswertung. Die README zeigt Vergleichs-Tabellen
zwischen drei Empfangsmodi (Normal, Diversity Standard, Diversity DX)
mit Pooled-Mean-Statistiken über Tausende von Zyklen. Beispiel-Zeile:

| Mode | Stations/15s (Pooled Mean) | vs Normal | Days | Cycles |
| Diversity Standard | 42.2 | **+126%** | 9 | 10,172 |

Diese „+126%" sind aktuell Punktschätzer ohne Unsicherheits-Aussage.
P69 soll Bootstrap-Konfidenz-Intervalle hinzufügen → „+126%
(95%-CI: +112% bis +141%)".

Mike (DA1MHH) ist offline; ich (Claude) ziehe das autonom durch mit
vollem V1→V2→R1→V3-Workflow. Aufgabe: V1+V2 prüfen, Findings für V3
liefern.

## V1+V2 anbei

Siehe `prompts/p69_confidence_intervals_v1.md` und
`prompts/p69_confidence_intervals_v2.md` (anbei).

## Was ich von dir will

1. **Statistische Methodik-Validierung:** Ist Block-Bootstrap nach
   (date, hour) für diese Datenstruktur die richtige Wahl? Oder gibt
   es ein offensichtlich besseres Verfahren (das ich übersehen habe)?

2. **Daten-Threshold-Heuristik (F3):** Sind n ≥ 10 Blöcke für stabiles
   Bootstrap-CI angemessen? Quellen / Faustregeln?

3. **Bootstrap-Implementations-Fallen:** Klassische Bugs die ich beim
   Schreiben dieser Funktion treffen werde? (Seed-Reproduzierbarkeit,
   ratio-CI-Schiefe, Pivotal vs. Percentile-CI etc.)

4. **Ratio-Statistik-Spezifika:** Wir berechnen Quotienten `(compare
   mean - normal mean) / normal mean * 100`. Hat das spezielle
   Eigenschaften die ich beachten muss? (Ratio-of-Means-Schiefe, etc.)

5. **Klarstellungs-Bedarf im Caveat:** Wo bin ich noch zu vage? Was
   würde ein wissenschaftlicher Reviewer kritisieren?

6. **Test-Plan-Vollständigkeit:** Decken T1-T10 die Edge-Cases ab oder
   fehlt was?

## Klassifikation

- **🔴 ROT (Bug/blockierender Defekt):** muss vor V3-Implementierung gefixt
- **🟠 ORANGE (Risiko):** mit hoher Wahrscheinlichkeit Problem im Produkt
- **🟡 GELB (Verbesserung):** kein Bug, würde Qualität heben
- **⚪ HINWEIS:** akademisch oder Geschmackssache

Halte dich kurz pro Finding — Fakten, kein Roman.

## Aus Scope (NICHT vorschlagen)

- Hierarchischer Bootstrap (V1 explizit verworfen)
- p-Werte / Hypothesen-Tests (Mike will keinen Inferenztest)
- Solar-Stratifikation (über aktuelle Datenbasis hinaus)
- Frequentist vs Bayesian Debatte
- Visualisierung der Bootstrap-Verteilung

Danke.
