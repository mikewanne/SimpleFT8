# Intent-Klausel V3 — Finaler Plan nach R1

**Basis:** V1 + V2 + R1 (DeepSeek-V4-pro)

R1-Findings übernommen:
- F-R1-1 Wortlaut: keine Änderung
- F-R1-2 Höhe: 340 → **400** (statt 380, R1-empfohlen für HiDPI)
- F-R1-3 KISS: in `main.py` patchen (kein eigenes Modul)

## Finale AC

| # | Was |
|---|---|
| AC1 | Disclaimer-Text durch Mike-Wortlaut ersetzt |
| AC2 | „DA1MHH" als persönlicher Funkbetrieb genannt |
| AC3 | „MIT-Lizenz" explizit erwähnt |
| AC4 | „Funklizenz-Verstöße" als Haftungs-Ausschluss genannt |
| AC5 | Dialog-Höhe **540×400** (R1-F2 HiDPI-Puffer) |
| AC6 | Body unverändert (ANT1/ANT2 Cyan) |
| AC7 | Buttons unverändert |

## Code-Patch (3 Commits)

C1 `main.py:_show_hardware_warning` Z.417 Höhe 340→400 + Z.448-454 Text-Replace
C2 `tests/test_intent_klausel.py` NEU mit T1-T4 (T4 fragt `>= 400`)
C3 `main.py` APP_VERSION 0.97.36 → 0.97.37
