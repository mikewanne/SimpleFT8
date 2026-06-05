# Optimierungs-Audit (2/2): VEREINFACHUNG + TOTER CODE

## Kontext
SimpleFT8 = Hobby-FT8-Tool (PySide6/FlexRadio). **Ziel: Vereinfachung + toten Code
finden.** KEIN Code ändern — nur Befund + Vorschläge mit Aufwand/Risiko.
Projekt-Philosophie: KISS, lieber 3 ähnliche Zeilen als verfrühte Abstraktion;
aber echte Duplikation/Komplexität darf weg.

## Statische Analyse hat schon vorgelegt (verifiziert gegen Live-Quellen)
**Funktionen/Methoden OHNE Code-Referenz (in den angehängten Dateien `control_panel.py`):**
`set_tx_freq`, `_group_label`, `_separator`, `_band_btn`, `_toggle_btn`,
`_on_tx_level_changed` (Zeilen via grep 0 Live-Refs).
**ungenutzte Imports control_panel:** `QSlider`, `_BTN_BASE`, `_CARD_SS`, `_DIV_PCT_YELLOW`.

## WICHTIG — NICHT als tot vorschlagen (bewusst reserviert/Framework):
- Qt-Event-Overrides (z. B. `wheelEvent`, `paintEvent`, `closeEvent`) werden vom
  Framework gerufen — nie „tot".
- Versteckte aber intakte Features (FT2-Button, `btn_advance`) bleiben.

## Frage
Schau in die angehängten Dateien (`control_panel.py` = 2388 Z., größte UI-Datei;
`mw_radio.py` = 2462 Z., größte Datei) und finde:
1. **Echten toten Code** (Helfer/Methoden die nie gerufen werden — die o.g. Kandidaten
   bestätigen/widerlegen + weitere). Pro Fund: ist es WIRKLICH tot oder per Signal/
   `getattr`/String verbunden? Gegen die Datei prüfen.
2. **Duplikation** die sich zu einem Helfer zusammenfassen ließe (z. B. wiederholte
   Button-/Style-Bau-Blöcke, Copy-Paste-Handler) — aber nur wo es WIRKLICH dupliziert
   ist, nicht verfrüht abstrahieren.
3. **Über-komplexe Methoden** (zu lang, zu viele Verantwortlichkeiten) die man ohne
   Verhaltensänderung entflechten könnte — Top 3-5 Kandidaten nennen.
4. **Inline-Style-Strings / Wiederholungen** die sich konsolidieren ließen.

Pro Fund: **Datei:Zeile, was, Vorschlag, Aufwand (S/M/L), Risiko**. Gegen die
angehängten Dateien prüfen, nicht raten. Priorisiere nach Nutzen/Aufwand. Knapp.
