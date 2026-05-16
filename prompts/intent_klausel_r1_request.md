# Intent-Klausel R1 DeepSeek-V4-pro Review Request

**Aufgabe:** App-Start-Hardware-Disclaimer-Dialog in SimpleFT8
(`main.py:_show_hardware_warning` Z.401-490) um eine Intent-Klausel
erweitern. Mike-Vorbereitung für eventuelle GitHub-Veröffentlichung.

## Lies zuerst

- `prompts/intent_klausel_v1.md` — Spec, AC1-AC7, Code-Plan, Tests
- `prompts/intent_klausel_v2.md` — Self-Review mit 6 Findings F1-F6

## Was du prüfen sollst

1. **Wortlaut juristisch sinnvoll?**

   Mike-Wortlaut (Hobby-Funker, nicht Anwalt):
   > „Dieses Projekt entstand als persönliches Bastel-Tool für meinen
   > eigenen Funkbetrieb (DA1MHH). Der Quellcode steht unter MIT-Lizenz
   > zur freien Verwendung — die Nutzung erfolgt jedoch ausschließlich
   > auf eigene Gefahr. Keine Gewährleistung, keine Haftung für
   > Hardware-Defekte, Funklizenz-Verstöße oder andere Folgen. ANT1
   > = TX-Antenne (immer). ANT2 = nur RX (NIEMALS TX, Regenrinne nicht
   > für Sendeleistung geeignet)."

   - Sind die juristischen Punkte sauber: MIT-Lizenz, Eigengefahr,
     Funklizenz-Verstöße, Hardware-Defekte?
   - Fehlt was Wichtiges (z.B. „Datenverarbeitung", „Logs", „Privacy")?
   - Ist der Ton angemessen (privat, nicht zu förmlich)?

2. **Dialog-Höhe 380 statt 340 — ausreichend?**

   Inner-Breite: 484px nach Margins. Disclaimer-Padding 8px → ~468px Text-
   Bereich. Mike-Wortlaut ca. 414 Zeichen → ~7 Zeilen bei Menlo 11pt.
   Reicht 380 oder lieber 400 für HiDPI-Sicherheits-Puffer?

3. **KISS-Check:** ist ein eigenes Dialog-Modul `startup_disclaimer_dialog.py`
   nötig (wie in TODO.md erwähnt)? Oder reicht der String-Patch in `main.py`?
   → V2-Antwort: KISS, in `main.py` patchen.

4. **Push-Empfehlung:** „Push freigegeben" oder „Nachbessern".

## Code-Stand zur Verifikation

- `main.py` Z.401-490: `_show_hardware_warning(app) -> bool`
- Z.417: `dlg.setFixedSize(540, 340)`
- Z.435-444: Body-Label mit ANT1/ANT2 Cyan (bleibt unverändert)
- Z.447-461: Disclaimer-Box (← hier patchen)

## Antwort-Format

```
## Findings
### F-R1-1 [Bug/Risiko/Hinweis]
**Was:** ...
**Empfehlung:** ...
```

Plus Push-Empfehlung am Ende.

## Wichtige Kontext-Files

1. `main.py` — der Hardware-Warning-Dialog
