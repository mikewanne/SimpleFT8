# Review des OPTIMIERUNGSWORKFLOW-Plans (Meta-Review, kein Code)

Mike will, dass DU (DeepSeek) und ich gemeinsam über den **Plan** schauen, BEVOR
optimiert wird — wie ein Plan-Modus zur Sicherheit. Angehängt: `OPTIMIERUNGSWORKFLOW.md`
(der Plan) + `OPTIMIERUNG_AUDIT.md` (die Befund-Grundlage).

**Strikte Mike-Regeln:** NUR Optimierungen, keine Verhaltensänderung; Bugs nur bei
Zufallsfund; Slice-B/Icom/ft8_lib reserviert (nicht entfernen); ANT1=TX unangetastet.

## Prüf-Auftrag (knapp, konkret)
1. **Reihenfolge:** Ist Stufe 1 wirklich das Ungefährlichste? Sollte ein Punkt in eine
   andere/spätere Stufe? Gibt es eine bessere Bündelung?
2. **Versteckte Risiken in den „safe" Stufe-1-Punkten:** Kann einer davon doch das
   Verhalten ändern? Besonders prüfen:
   - OPT-06 (hanning/Filter-Taps als Modul-Konstante): Gefahr, wenn das Fenster
     mode-/längenabhängig ist (FT8 vs FT4 unterschiedliche n_fft/Slot-Länge)? Dann wäre
     EINE Konstante falsch. → Bedingung nennen, unter der es sicher ist.
   - OPT-08 (Pro-Offset int16 1×): Verändert das je das Decode-Ergebnis (Rundung)?
   - OPT-07/OPT-11 (Slot-Dicts als Konstante): irgendwo mutiert?
3. **Fehlt ein Befund** aus dem Audit im Plan, oder steht etwas drin, das man besser
   NICHT macht (Overengineering / verfrühte Abstraktion gegen die KISS-Philosophie)?
4. **Test-Strategie:** Reicht „volle Suite grün" als Sicherung, oder braucht ein
   bestimmter Punkt einen NEUEN gezielten Test (z. B. OPT-20 Decode-Referenz)? Welche?

Antworte als kompakte Liste mit klarem GO / ÄNDERN pro Punkt. Gegen die angehängten
Dateien prüfen, nicht raten.
