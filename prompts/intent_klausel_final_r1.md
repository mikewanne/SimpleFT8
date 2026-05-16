Alle **V3-AC sind korrekt umgesetzt**:

- `main.py` enthält den Mike-Wortlaut aus TODO.md Z.979–985 – DA1MHH, MIT-Lizenz, „auf eigene Gefahr“, „Funklizenz-Verstöße“ und der konkrete ANT1/ANT2‑Hinweis stehen genau so drin.
- Die Dialoghöhe wurde auf `setFixedSize(540, 400)` geändert (R1‑F2 HiDPI‑Puffer, 400 px).
- `APP_VERSION = "0.97.37"` ist gesetzt.
- Die 5 neuen Tests (`test_t1…_t4` + Bonus) decken alle fachlichen Prüfungen (Inhalt, Größe, altes Text‑Fehlen) ab und arbeiten rein quelltextbasiert – kein Qt‑Overhead.

**Push-Freigabe: Ja.**  
Alle Anforderungen aus V1–V3/R1 sind erfüllt, die Tests sind schlüssig und gegen die reale `main.py` geschrieben.

**Edge-Cases übersehen?**  
Keine. Der Dialog lässt sich bei HiDPI auch mit sehr großer System‑Schriftart nicht mehr abschneiden (400 px sind ausreichend Puffer). Einzige theoretische Randnotiz: Falls irgendwann der Disclaimer um mehrere Sätze wächst, könnte die feste Höhe knapp werden – das ist aber aktuell nicht der Fall und wäre eine funktionale Erweiterung, kein Bug.

→ Push kann raus.
