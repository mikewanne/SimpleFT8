# Audit (KISS / Lesbarkeit / Robustheit) — ganze App

## Auftrag (Mike-Priorität, 05.06.2026)
SimpleFT8 = Hobby-FT8-Tool (PySide6/FlexRadio, älterer iMac). Wir optimieren die GANZE
App. **Priorität Nr. 1: KISS, Lesbarkeit, Robustheit — WICHTIGER als Mikrosekunden.**
Geschwindigkeit nur erwähnen, wenn sie mit Vereinfachung zusammenfällt. **Kein Code
ändern — nur Befund.**

## Worauf es ankommt (in dieser Reihenfolge)
1. **Robustheit** — fragile/fehleranfällige Stellen: fehlende/zu breite `except`,
   stille Fehler, Speichern/Laden ohne Validierung, Races, Reihenfolge-Abhängigkeiten,
   Zustände die auseinanderlaufen können, „magische" Annahmen.
2. **Lesbarkeit / KISS** — über-komplexe oder zu lange Methoden, verschachtelte
   Bedingungen, unklare Namen, Code der „cleverer als nötig" ist, Copy-Paste-Duplikation
   die EINE Quelle haben sollte.
3. **Toter Code** — nie gerufene Funktionen/Methoden/Zweige (gegen die Datei prüfen:
   wirklich tot oder per Signal/`getattr`/Qt-Override verbunden?).

## WICHTIG — Projekt-Philosophie + Tabus
- **KISS schlägt Eleganz.** KEINE verfrühte Abstraktion vorschlagen — 3 ähnliche Zeilen
  sind besser als eine unnötige Klasse/Konfig. Nur wo es WIRKLICH dupliziert/komplex ist.
- **NICHT als tot/entfernbar vorschlagen:** Qt-Event-Overrides (`paintEvent`/`wheelEvent`/
  `closeEvent`, `noqa: N802`), Slice-B-Reserve in flexradio, Icom-Stubs, ft8_lib,
  `if TYPE_CHECKING`-Imports. ANT1=TX-Logik nicht anfassen.
- Hobby-Tool, kein Contest-Tool — keine Feature-Vorschläge.

## Ausgabe pro Fund
**Datei:Zeile · Kategorie (Robustheit/KISS/ToterCode) · was · warum es schadet ·
konkreter einfacherer/robusterer Vorschlag · Aufwand (S/M/L) · Risiko.**
Gegen die angehängten Dateien prüfen, nicht raten. Nach Nutzen priorisieren. Knapp.
Wenn eine Datei sauber ist: das auch sagen (nicht künstlich Funde erfinden).
