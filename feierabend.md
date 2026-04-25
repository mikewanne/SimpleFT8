# Feierabend-Routine – SimpleFT8

Führe diese Schritte ohne Rückfragen und ohne Kommentar durch:

## 1. CLAUDE.md aktualisieren (in BEIDEN Verzeichnissen)

Überschreibe identisch in:
- `/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8/CLAUDE.md`
- `/Users/mikehammerer/Documents/KI N8N Projekte/FT8/CLAUDE.md` → NUR die Abschnitte ab `# SimpleFT8 — Claude Kontext` (den JOHNBOY-Header davor stehen lassen)

Erste Zeile des SimpleFT8-Blocks ist immer:
"Lies nach dieser Datei sofort auch HANDOFF.md und bestätige beide mit je einer Zeile."

Danach token-dicht, nur das Wesentliche:

- Architektur & Module (aktueller Stand)
- Gain-Algorithmus & Hard-Limit –12 dBFS
- FT4/FT8 Cycle-Zeiten & Gap-Handling
- SDR-Thresholds (alle aktuellen dBFS-Werte)
- OMNI-TX Slot-Rotation Stand (PRIVAT – nicht auf GitHub!)
- UCB1-Parameter & Recalibration-Intervall
- Thread-Safety: welche Module, welche Locks
- Offene TODOs (nur echte, keine erledigten)
- Bekannte Fallen & Bugs

## 2. HANDOFF.md aktualisieren (in BEIDEN Verzeichnissen)

Überschreibe identisch — gleicher Inhalt, zwei Speicherorte:
- `/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8/HANDOFF.md`
- `/Users/mikehammerer/Documents/KI N8N Projekte/FT8/HANDOFF.md`

Inhalt:
- Heute erledigt
- Offen / Nächste Schritte (priorisiert)
- Warnungen & Fallen
- Test-Suite Status
- Letzter bekannter guter Zustand

## 3. HISTORY.md ergänzen (PFLICHT — niemals löschen!)

Datei: `/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8/HISTORY.md`

**Regel:** Nur anhängen (append), niemals bestehende Einträge entfernen oder überschreiben.

**WICHTIG:** Trage ALLE Ergänzungen, Verbesserungen und neuen Implementierungen der
aktuellen Session vollständig ein — keine Lücken. Auch kleinere Refactorings,
Bugfixes und Doku-Änderungen gehören rein.

**Format mit Versionsnummer:** `## YYYY-MM-DD vX.YY — Kurztitel`
- `APP_VERSION` aus `main.py` lesen (erste Konstante nach den Imports)
- Neue Features: APP_VERSION um +0.01 erhöhen UND in main.py eintragen
- Nur Bugfixes ohne neue Funktionalität: Version unverändert lassen
- **Warum:** Jeder HISTORY-Eintrag muss eindeutig einer Appsicherung zuordenbar sein

Inhalt pro Eintrag:
- Was wurde geändert (Datei + Beschreibung)
- Welche Bugs wurden gefixt
- Neue Features / Docs
- Test-Status (z. B. `168 passed`)

## 4. Bestätigung ausgeben

Gib exakt das aus:

```
✅ CLAUDE.md aktualisiert – SimpleFT8 + FT8/
✅ HANDOFF.md aktualisiert – SimpleFT8 + FT8/ (identische Kopie)
✅ HISTORY.md ergänzt – lückenlose Änderungshistorie
✅ Terminal schließen
✅ Morgen: cd SimpleFT8 ODER cd FT8 → claude1 → lädt automatisch
```
