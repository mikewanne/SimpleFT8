# OMNI-TX — Automatische Slot-Rotation

## Kurz gesagt

OMNI-TX rotiert automatisch zwischen Even- und Odd-Slots, um 100% aller aktiven Stationen zu erreichen statt nur 50%. Weniger senden, mehr hoeren, mehr QSOs.

## Das Problem

Jeder FT8-Operator hoert immer nur den entgegengesetzten Slot. Wer auf Even sendet, hoert nur Odd — und umgekehrt. Mit normalem CQ erreichst du pro Zyklus exakt 50% der aktiven Stationen. Die andere Haelfte hoert dich nie.

## Wie es funktioniert

OMNI-TX wechselt automatisch zwischen zwei Bloecken:

**Block 1 (Even-first):**
```
Even SENDEN → Odd SENDEN → Even HOEREN → Odd HOEREN → Even HOEREN
```

**Block 2 (Odd-first):**
```
Odd SENDEN → Even SENDEN → Odd HOEREN → Even HOEREN → Odd HOEREN
```

Jeder Block laeuft 80 Zyklen (~100 Minuten), dann wird gewechselt. Ueber beide Bloecke sind Even und Odd perfekt ausgeglichen.

## Sendeanteil

| Modus | Sendeslots | Hoerslots | Sendeanteil |
|-------|-----------|-----------|-------------|
| Normal (Even) | 5 von 10 | 5 von 10 | **50%** |
| OMNI-TX | 4 von 10 | 6 von 10 | **40%** |

OMNI-TX sendet 20% weniger, hoert 20% mehr, erreicht aber beide Hoerergruppen.

## Realistischer Gewinn

- Belegte Baender: **20-30% mehr CQ-Antworten**
- Leere Baender: 10-20% mehr
- Grund: Doppelt so viele Operatoren hoeren dich

## QSO-Verhalten

Wenn eine Station antwortet:
1. Normaler QSO-Ablauf (State-Machine uebernimmt)
2. Block-Zaehler wird zurueckgesetzt
3. Aktueller Block bleibt (der Slot laeuft gerade gut)
4. Nach QSO-Ende: OMNI-TX Pattern geht weiter

## Auto-Hunt

Bei Aktivierung wird Auto-Hunt automatisch mitgestartet. Auto-Hunt beantwortet CQ-Stationen intelligent nach Scoring (neues DXCC > seltenes Call > guter SNR).

## Aktivierung

1. Klick auf die **Versionsnummer** unten rechts im Hauptfenster
2. Bestaetigungsdialog erscheint
3. Bei Aktivierung: **Omega-Symbol** (Omega) erscheint neben der Version
4. CQ-Button wechselt zu "OMNI CQ"
5. Erneuter Klick deaktiviert OMNI-TX

## Fuer Beobachter

Eine Frequenz im Wasserfall. Signal wechselt zwischen Even und Odd. Sieht aus wie manuelles Slot-Wechseln — bekannt, akzeptiert, unauffaellig. Technisch regelkonform: eine Frequenz, gleiche Sendezeit wie jede andere Station.
