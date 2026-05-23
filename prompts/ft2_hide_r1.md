# DeepSeek-Review R1 — FT2-Button verstecken + Band/Mode-State raus

## Kontext

**SimpleFT8** ist ein Hobby-Funker-Tool (FlexRadio FT8/FT4). Projekt-
Philosophie: KISS, hobby-tauglich, kein Contest-Tool. Es geht um eine
**kleine, gezielte Änderung** — kein neues Feature, kein Refactor.

**Ziel:**
1. **FT2-Button verstecken** (ohne FT2-Code zu entfernen) — Standards-
   Landschaft ist fragmentiert (Decodium vs WSJT-X-Improved-FT2),
   offizielles WSJT-X hat FT2 nicht übernommen, keine Zeit zum Pflegen.
   Mike will FT2 parken, bis sich was tut.
2. **Band/Modus-Persistenz entfernen** — App startet immer mit 20m+FT8.
   Mike-Entscheidung 23.05.2026. Nebeneffekt: niemand startet versehent-
   lich im versteckten FT2.

**Wichtige Fakten (verifiziert):**
- FT2-Code ist **Decodium-kompatibel** (per `core/protocol.py:9`: Quelle
  „Decodium (FtxFt2Stage7.cpp)"; 4-GFSK, 41.667 Baud, Costas, 103
  Symbole — passt zur Decodium-Spec).
- Notiz in `config/settings.py:12` („FT2-Decoder noch NICHT Decodium-
  kompatibel, 8-GFSK nötig") ist **faktisch falsch** und muss korrigiert
  werden.

## V1 (Vorschlag)

### Ausgangslage
- FT2 = Decodium-kompatibel (verifiziert).
- `config/settings.py:12` Notiz falsch.
- App soll immer 20m+FT8 starten.

### Lösung (6 Schritte)
1. `self.btn_ft2.setVisible(False)` in `ui/control_panel.py`. FT2-Code-
   Pfade (decoder, encoder, cycle, timing) bleiben **null Zeilen**
   angefasst. Objekt existiert weiter → `clicked.connect`/`setChecked`
   funktionieren weiter.
2. FT8/FT4 umlegen — Grid-Layout in `control_panel.py` anpassen, damit
   FT8/FT4 die freie Spalte 3 mitnehmen.
3. State-Bereinigung Band/Modus in `config/settings.py`:
   - `load()`: Band+Modus NICHT aus Datei lesen, immer DEFAULTS
     (`20m`, `FT8`).
   - `save()`: Band+Modus NICHT persistieren.
   - DEFAULTS-Werte bleiben kanonisch.
4. `settings.py:12` Kommentar korrigieren auf „FT2 = Decodium-Standard,
   4-GFSK 41.67 Baud Costas — Definition in `core/protocol.py:88`;
   Button derzeit versteckt".
5. CLAUDE.md aktualisieren (FT2-Notiz korrigieren + vermerken).
6. HISTORY.md neuer Eintrag.

### Tests
- Bestehende Suite muss grün bleiben (1734+ Tests).
- FT2-Tests die `btn_ft2`-Sichtbarkeit/Click prüfen → ggf. anpassen.
- Neu: App-Start lädt 20m FT8 unabhängig vom gespeicherten Settings-State.

### Edge-Cases
- Settings mit `mode=FT2` (von früheren Tests) → kein Crash, wird auf
  DEFAULT gezwungen.
- Reaktivierung später: `setVisible(False)`-Zeile raus + Layout zurück.

## V2 (Self-Review Findings)

**F1** — CLAUDE.md ungeprüft, ob dort wirklich falsche FT2-Notiz steht.
V3: grep zuerst.

**F2** — Layout-Plan zu pessimistisch: Qt-QGridLayout kollabiert hidden
Spalten von selbst. `setVisible(False)` allein könnte reichen → 1-
Zeilen-Fix statt 5–10. V3: Grid-Config in `control_panel.py` prüfen
(setColumnStretch vorhanden?).

**F3** — `settings.save()` nicht gelesen. Bei generischem Dict-Dump
müssten Band/Modus explizit ausgeschlossen oder beim Load ignoriert
werden. V3: load/save lesen.

**F4** — Programmatische FT2-Trigger ungeprüft. V3: `grep -rn '"FT2"'
ui/ core/` außerhalb Profilen/Frequenzen.

**F5** — Tests mit `btn_ft2`-Anfassungen ungeprüft. V3: `grep -rn
"btn_ft2\|set_mode.*FT2" tests/`.

**F6** — Behavior-Change: Entfernen der Band/Mode-Persistenz ist UX-
Regression für Nicht-Mike-Nutzer. Mike hat es explizit angeordnet, in
HISTORY als deliberate Entscheidung markieren.

**F7** — Reaktivierungs-Kommentar bei `setVisible(False)` als non-
obvious WHY gerechtfertigt.

## Was ich von dir will

Bitte **kritisch und konkret reviewen**:

1. **Stimmen die Annahmen?** File-Pfade, Zeilen, beschriebene Verhalten.
   Bitte mit Datei:Zeile widerlegen wo nötig.
2. **Ist F2 (Grid-Kollaps) korrekt** — kollabiert QGridLayout wirklich,
   wenn das einzige Widget einer Spalte `setVisible(False)` ist? Oder
   brauche ich zusätzlich `setColumnStretch(3, 0)` oder `removeWidget`?
3. **Edge-Cases die ich übersehe?** Insbesondere im Settings-Lifecycle,
   beim ersten Start mit Alt-Settings-File, beim Wechsel Normal↔Multi-
   band wenn Band/Modus nicht persistiert wird.
4. **Gibt es eine simplere Lösung** als die 6 Schritte? Oder ist
   irgendwas über-engineered?
5. **Konkrete Implementierungs-Risiken** — Race-Conditions, Test-Brüche,
   Lifecycle-Probleme, irgendwo `btn_ft2.isVisible()` oder `isEnabled()`
   in einer Code-Logik?
6. **Ist meine Behauptung wasserdicht** „setVisible(False) ändert keine
   FT2-Logik"? Oder gibt es einen Aufrufer der über die Sichtbarkeit
   Logik schaltet?

Antworte **auf Deutsch, knapp, konkret, mit Datei:Zeile** wo möglich.
Es geht um eine kleine Änderung — kein Konzept-Review, sondern ein
Implementierungs-Sanity-Check.
