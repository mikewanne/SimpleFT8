# R1-Review Request — Bundle B' V2

Du bist DeepSeek-R1. **Pruefe diesen V2-Plan kritisch** — finde Fehler,
Luecken, Overengineering, fehlende Akzeptanzkriterien. Du sollst den
**Plan verbessern**, NICHT das Problem direkt loesen.

Antworte strukturiert:
- **KRITISCH** (KP-N): Wuerde Bug einfuehren, Datenverlust, Crash
- **SOLLTE-FIX** (S-N): Architektonisch problematisch, KISS-Verletzung
- **KOENNTE** (K-N): Optimierungs-Vorschlag
- **HINWEIS** (H-N): Klein

Pro Finding: Datei:Zeile-Referenz wenn anwendbar, konkrete Empfehlung.

Mike's Kontext-Memory:
- Hobby-Funker-Tool, nicht Contest-Tool. KISS schlaegt Eleganz.
- Memory `feedback_partial_fix_check_other_paths.md`: Bei Bug-Fix
  IMMER alle Pfade gleicher Klasse pruefen (grep nach Pattern in
  B+C+...). „Partial-Fix raecht sich."
- Memory `feedback_test_critical_path_not_mock.md`: Wenn Mock genau
  die Logik ueberschreibt die der Test pruefen soll, validiert er
  die Mock-Implementierung. Tests duerfen den kritischen Pfad NICHT
  wegmocken.
- Memory `feedback_partial_fix_check_other_paths.md`: bei P33
  Doppel-Emit-Schutz pruefen ob ALLE Pfade abgedeckt sind.

## V2-Plan zur Pruefung

[Inhalt von bundle_b_v2.md wird mit angehaengt]

## Konkrete Pruefauftraege

1. Ist die 2-Signal-Split-Loesung fuer P33 sauber oder
   overengineered? Gibt es eine einfachere Loesung die V2 uebersehen
   hat?

2. P33 Doppel-Emit-Schutz: pruefe ALLE Quellen von
   `qso_confirmed.emit` im Code (Z.317, 488, 658) — wird `visual`
   ueberall passend feuern? Insbesondere Z.658
   („Hypothetischer Doppelschutz") — wird die je erreicht? Wenn nicht,
   warum bleibt der Code?

3. P33 Reihenfolgen-Garantie: Qt-Signals sind QueuedConnection wenn
   zwischen Threads. Garantiert das dass `qso_confirmed_visual` ZUERST
   im Slot ausgewertet wird vor allen anderen Slot-Operationen?
   Oder kann es passieren dass `add_qso_complete` (visual) nach dem
   naechsten Slot-Tick laeuft?

4. P33 Test-Strategie: wie testet man dass `_maybe_resume_omni()`
   NICHT vor Courtesy-Send laeuft? Welcher Mock-Stub ist sicher
   ohne den kritischen Pfad wegzumocken?

5. P32: Settings-Key Name `rx_panel_hidden_cols` vs
   `rx_panel_visible_cols`. Welche Konvention im restlichen Repo
   ueblich? `presets_dx.json`-Schema-Konsistenz pruefen.

6. P32: Bei 8 Spalten-Toggles in Folge wird 8× `settings.save()`
   gerufen. Heutiger Settings-Save schreibt das ganze JSON neu —
   ist das ein Issue oder vernachlaessigbar (KB-File)?

7. P32: Was passiert wenn User Spalten ausblendet, App quit ohne
   Fenster-Geometrie-Save (Crash), Neustart? Settings persistiert wir
   sofort bei jedem Toggle → kein Issue. Aber: settings.save() bei
   jedem Toggle ist anders als z.B. window_geom (nur in closeEvent).
   Soll P32-Save in closeEvent oder pro Toggle? V2 hat „pro Toggle"
   gewaehlt — pruefe.

8. P32: Sollten Tests einen pyqt-offscreen-Test fuer
   `setColumnHidden`-Verhalten haben oder reichen Daten-Tests
   (Settings-Round-Trip)?

9. Bundle-Strategie: Sind P32 + P33 unabhaengig genug fuer atomare
   Commits oder gibt es eine Abhaengigkeit die ich uebersehe?

10. Backup-Strategie: V2 nennt 4 Files. Sind das alle Files die
    Bundle B' anfasst? Pruefen.

## Antwort-Format

```
KP-1: ...
S-1: ...
K-1: ...
H-1: ...

ZUSAMMENFASSUNG:
- Anzahl KRITISCH: X
- Anzahl SOLLTE: X
- Plan-Status: [Push freigegeben | V3 noetig | grundsaetzlich neu]
```
