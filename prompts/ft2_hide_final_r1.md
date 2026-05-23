# Final-R1 — DeepSeek-Review der tatsächlich committeten FT2-Hide-Änderungen

## Kontext

V1→V2→R1→V3→C1-C4-Workflow für FT2-Button-Hide + Band/Modus-Persistenz-
Entfernung ist abgeschlossen. Du bekommst die finalen Dateien.

**Ziel der Änderung (Mike-Entscheidung 23.05.2026):**
1. FT2-Button visuell verstecken (FT2-Code-Pfade intakt lassen) wegen
   Standards-Fragmentierung (Decodium vs WSJT-X-Improved-FT2).
2. Band/Modus-Persistenz entfernen — App startet immer mit 20m+FT8.

**Verifizierte Fakten:**
- FT2-Decoder ist **Decodium-kompatibel** (4-GFSK, 41.667 Baud, Costas)
  per `core/protocol.py:9` (siehe Anhang). Mike hat bereits ein FT2-QSO
  erfolgreich geloggt.
- Alte Notiz `config/settings.py:12` „nicht Decodium-kompatibel" war
  faktisch falsch und ist korrigiert.

**R1-Hauptfund (eingearbeitet):** Mein V2-F2 „QGridLayout kollabiert
hidden Spalten" war falsch — Spalte 3 enthält in Zeile 1 noch den 15m-
Band-Button. R1 schlug freq_frame-Shift vor (Spalte 4→3) — eine Zeile
statt komplexem Re-Layout. So umgesetzt.

## Was committet wurde (C1-C4)

**C1** — `config/settings.py` + `tests/test_p52_stats_cleanup.py`:
- Z.12 Kommentar korrigiert (FT2 = Decodium-Standard).
- `load()` forciert `band`/`mode` auf `DEFAULTS` nach `update(saved)`.
- `save()` schließt `band`/`mode` aus dem JSON-Dump aus.
- test_p52::test_t7 angepasst (forced-to-DEFAULTS statt „band bleibt").

**C2** — `ui/control_panel.py`:
- `self.btn_ft2.setVisible(False)` mit Reaktivierungs-Kommentar nach
  Z.313 `grid.addWidget(self.btn_ft2, 0, 3)`.
- freq_frame von `grid.addWidget(freq_frame, 0, 4, 1, 3)` auf
  `(0, 3, 1, 3)` — füllt die freie Spalte 3 in Zeile 0.

**C3** — `tests/test_band_mode_no_persist.py` (neu, 4 Tests):
- Saved band/mode → DEFAULTS gezwungen.
- Spezialfall mode=FT2 → DEFAULT FT8.
- save() schließt band/mode aus.
- Runtime-Updates funktionieren weiter (mw_radio.py:405/505).

**C4** — Doku:
- main.py: APP_VERSION 0.97.90 → 0.97.91.
- CLAUDE.md: Aktueller Stand + 2 neue Bekannte-Fallen-Einträge.
- HISTORY.md + HANDOFF.md: neue Einträge v0.97.91.

**Tests:** 1734 → 1738 grün (+4 neue).

## Was ich von dir will

Bitte **kritisch und konkret reviewen** ob die Umsetzung sauber ist:

1. **Settings-Änderungen korrekt?** `load()` / `save()` — Reihenfolge
   der Mutationen, Idempotenz, Edge-Cases (Settings-File mit alten
   band/mode-Keys, völlig leeres File, fehlendes File).
2. **Tests vollständig?** Decken die 4 neuen Tests die wesentlichen
   Szenarien ab? Was fehlt?
3. **Layout-Änderung (control_panel.py)** korrekt umgesetzt? Hat das
   Verschieben von freq_frame irgendwelche unerwarteten Nebenwirkungen?
4. **Wasserdichte:** Bleibt FT2-Logik wirklich unangetastet? Gibt es
   irgendwo einen subtilen Pfad der jetzt bricht?
5. **Settings-Migrations-Reihenfolge:** Die neuen Zeilen
   `self._data["band"] = DEFAULTS["band"]` stehen NACH dem
   `tune_duration_s`-Check und VOR `_migrate_bandpilot_settings_v088()`
   — ist das die richtige Stelle?
6. **Kommentare/Comments korrekt** und nicht verwirrend?
7. **Sonstige Risiken** die ich übersehen habe?

Antworte auf Deutsch, knapp, konkret, mit Datei:Zeile. Kritisch sein —
es soll wirklich sauber sein.
