# Final-R1 — DeepSeek-Review der committeten QSO-Finish-Hide-Aenderungen

## Kontext

V1→V2→R1→V3→C1-C3-Workflow fuer das Verstecken von `btn_advance`
(„QSO Finish") ist abgeschlossen. Du bekommst die finalen Dateien.

**Ziel:** `btn_advance` visuell verstecken — Mike hat den Button nie
gebraucht, FT8-Timeouts (MAX_STATION_CALLS=5, 3-Min-Gesamt) fangen
stuck-Gegenstationen ohnehin ab. Code/Handler/Signal bleiben intakt
(analog FT2-Hide vom Vortag). HALT bleibt unangetastet — andere Rolle.

**R1-Verdict (vor Code):** „Sauber. Kein Stolperdraht. 1-Zeilen-
Aenderung unbedenklich." HBox kollabiert hidden Widgets automatisch
→ kein Layout-Shift wie bei FT2 noetig.

## Was committet wurde (C1-C3)

**C1** (`3490903`) — `ui/control_panel.py:1199` + neuer Test:
```python
self.btn_advance.setEnabled(False)
# QSO-Finish versteckt 2026-05-23 (Mike: nie gebraucht, FT8-Timeout
# faengt stuck-Gegenstation eh ab) — Code/Handler/Signal intakt.
# HALT bleibt — verschiedene Rolle (Sicherheits-Notbremse).
# Reaktivierung: diese Zeile loeschen. HBox kollabiert hidden Widget
# automatisch, kein Layout-Shift noetig.
self.btn_advance.setVisible(False)
```
+ `tests/test_qso_finish_hidden.py` mit 3 Tests:
- `btn_advance.isHidden() is True`
- `btn_cancel.isHidden() is False`
- Signal + `click()`-Methode existieren weiter

**Self-Review-Fang beim Test-Schreiben:** isolierte Tests ohne shown
Parent-Window → `isVisible()` ist IMMER False fuer alle Widgets →
`isHidden()` ist das richtige Werkzeug (prueft den explizit gesetzten
Hidden-Flag).

**C2** (`9049680`) — TODO.md Pflege: 4 stale OFFEN-Eintraege auf
ERLEDIGT umgestellt (P52, P56 via P80, P60, Bundle H). Heading-only
+ kurzer Pointer auf HISTORY/Memory. Body bleibt.

**C3** (`e863032`) — Doku: APP_VERSION 0.97.91→0.97.92, CLAUDE.md
„Bekannte Fallen" + Aktueller Stand, HISTORY.md + HANDOFF.md neue
Eintraege.

**Tests:** 1738 → 1741 gruen (+3 neue).

## Was ich von dir will

**Sanity-Check ob die committete Umsetzung sauber ist:**

1. **`setVisible(False)`-Position** korrekt? Direkt nach
   `setEnabled(False)` im selben Block — Reihenfolge / Timing OK?
2. **Tests** vollstaendig? Decken sie was sie sollen?
3. **Wasserdichte:** Gibt es im jetzigen `control_panel.py` oder
   `mw_qso.py` einen Pfad der durch das Hide jetzt unerwartet bricht
   oder ungewollte Konsequenzen hat?
4. **Kommentar** korrekt + nicht verwirrend? Reaktivierungs-Hinweis
   klar genug fuer eine zukuenftige Session?
5. **Sonstige Risiken** uebersehen?

Antworte auf Deutsch, knapp, konkret, mit Datei:Zeile. Kritisch sein —
es soll wirklich sauber sein.
