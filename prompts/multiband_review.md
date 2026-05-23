# DeepSeek-Review: Multiband-Konzept (SimpleFT8)

Du bekommst `multiband.md` — das fertig durchgesprochene Konzept für eine
neue Funktion „Multiband" in SimpleFT8. Bitte **kritisch und unabhängig
bewerten**. Es ist ein KONZEPT-Review, kein Code-Review — es gibt noch
keinen Code.

## Kontext

**SimpleFT8** ist ein Hobby-Funker-Tool für FT8/FT4 mit FlexRadio.
Projekt-Philosophie: **KISS, Hobby-Tool, KEIN Contest-Tool.** Zielgruppe
ist der Gelegenheits-Funker — App starten, ein bisschen funken, fertig.
Lieber 3 gut funktionierende Features als 30 komplizierte.

**Hardware:** FlexRadio 8400M — Direct-Sampling-SDR mit **einer SCU**
(digitalisiert den ganzen KW-Bereich) und **zwei Slice-Receivern**.
Eine SCU kann nur eine Antenne zur Zeit. ANT1 = Sende-Antenne (immer),
ANT2 = nur Empfang (Hardware-Schaden bei TX auf ANT2). Interner
relais-basierter ATU, der Tuning-Lösungen pro Band speichert.

**Multiband in einem Satz:** Empfang von zwei Bändern gleichzeitig
(je ein Slice), beide Stationslisten in einem Fenster; klickt man eine
Station an, springt der Sender auf deren Band — beschleunigt durch
vorab gecachte Tune-/Gain-Werte.

## Was ich von dir will

Lies das Konzept und bewerte kritisch:

1. **Technische Korrektheit** — stimmt die Argumentation zu SCU/Slices,
   FT8-Slot-Timing, ATU-Verhalten, dem Ein-Sender-Konflikt? Sind
   irgendwo physikalische oder logische Denkfehler drin?
2. **Lücken** — was wurde vergessen, was ist unterspezifiziert, welche
   Fälle/Interaktionen fehlen?
3. **Overengineering / KISS** — ist irgendwas zu komplex für ein
   Hobby-Tool? Geht etwas einfacher?
4. **Umsetzungs-Risiken** — wo wird die Implementierung wahrscheinlich
   schwierig oder fehleranfällig (Threading, Slot-Timing, Decoder-Last,
   FlexRadio-API)?
5. **Passt es zum Hobby-Tool?** — oder ist Multiband eher ein
   Contest-/Power-User-Feature, das man ablehnen sollte?

Bitte **konkret und nummeriert**, mit Begründung. Wenn das Konzept gut
ist, sag es klar; wenn nicht, sag genauso klar warum. Antworte auf
Deutsch.
