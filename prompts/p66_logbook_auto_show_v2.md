Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6. Hobby-Funker-Tool für einen einzelnen Operator.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.
SCOPE-RESPEKT. KISS VOR DEFENSIV. Overengineering ist Fehler.

---

# P66 — Logbuch-Tab-Auto-Show: Detail bei selektierter Station

## Kontext

QSO-Panel hat 2 Tabs (QStackedWidget): „QSO" (Live-Log, index=0) und
„Logbuch" (LogbookWidget, index=1). Rechte Seite ist `_right_stack`
QStackedWidget mit ControlPanel (index=0) und QSODetailOverlay (index=1).

**Aktuelles Verhalten (Bug):**
- User selektiert Logbuch-Eintrag → Detail rechts erscheint ✓
- User wechselt zu „QSO"-Tab → Detail rechts schließt automatisch ✓
- User wechselt wieder zurück zu „Logbuch"-Tab → Tabelle zeigt
  vorherige Selektion noch blau hervorgehoben, ABER rechts bleibt
  ControlPanel — Detail kommt NICHT zurück

Screenshot vom 16.05.2026 zeigt: EA5D selektiert (blaue Zeile), rechts
aber MODUS+BAND+ANTENNE+RADIO+QSO-Section vom ControlPanel.

## Mike-Spec

„wenn ich auf logbuch gehe und es ist eine station selektiert sollte
auch rechts der logbuch eintrag erscheinen — drücke logbuch → station
ist selektiert → daten qso werden angezeigt."

## Verifizierte Code-Stellen

- `ui/mw_qso.py:1002` `_on_qso_tab_changed(index)`:
  ```python
  def _on_qso_tab_changed(self, index: int):
      if index == 0:  # QSO-Tab (nicht Logbuch)
          self._right_stack.setCurrentIndex(0)
  ```
- `ui/mw_qso.py:627` `_on_logbook_qso_clicked(record)`:
  Lädt Record in Detail-Overlay + `_right_stack.setCurrentIndex(1)` +
  triggert QRZ-Lookup in Background-Thread.
- `ui/logbook_widget.py:366` `_selected_record() → dict | None`:
  Returnt aktuell selektierten Record oder None. **Genau die API die
  wir brauchen.**
- `ui/qso_panel.py:160` `self.logbook = LogbookWidget()` —
  Hauptzugriff via `qso_panel.logbook`.

## Lösungs-Skizze

Branch `index == 1` in `_on_qso_tab_changed` ergänzen:

```python
def _on_qso_tab_changed(self, index: int):
    if index == 0:  # QSO-Live
        self._right_stack.setCurrentIndex(0)
    elif index == 1:  # Logbuch
        rec = self.qso_panel.logbook._selected_record()
        if rec:
            self._on_logbook_qso_clicked(rec)
```

3-5 Zeilen Code-Änderung.

## Akzeptanzkriterien

| AC | Was |
|---|---|
| **AC1** | `_on_qso_tab_changed(1)` mit selektiertem Record → ruft `_on_logbook_qso_clicked(record)` → `_right_stack.currentIndex() == 1` |
| **AC2** | `_on_qso_tab_changed(1)` ohne Selektion (`_selected_record() == None`) → `_right_stack`-Index bleibt unverändert (ControlPanel sichtbar) |
| **AC3** | `_on_qso_tab_changed(0)` bleibt unverändert — Overlay schließt zu Index 0 |
| **AC4** | Keine Regression: Direct-Click auf Logbuch-Eintrag (Signal `qso_clicked`) funktioniert weiter |
| **AC5** | QRZ-Lookup-Background-Thread wird beim Auto-Show wie beim Click ausgelöst (Symmetrie über `_on_logbook_qso_clicked`) |
| **AC6** | 3-4 neue Tests in `tests/test_p66_logbook_auto_show.py` (Source-Level + Mock-basiert) |
| **AC7** | APP_VERSION 0.97.41 → 0.97.42 |
| **AC8** | Backup `Appsicherungen/2026-05-16_v0.97.41_vor_p66/` |
| **AC9** | HISTORY + HANDOFF + CLAUDE + TODO + Memory aktualisiert |

## Betroffene Module/Dateien

| Datei | Aktion |
|---|---|
| `ui/mw_qso.py:1002 _on_qso_tab_changed` | elif-Branch für index==1 hinzufügen |
| `main.py` | APP_VERSION |
| `tests/test_p66_logbook_auto_show.py` | NEU |
| HISTORY, HANDOFF, CLAUDE, TODO, Memory | Updates |
| `Appsicherungen/...` | Backup |

## Randbedingungen

- **Threading:** Logbuch-Tab-Wechsel kommt aus GUI-Thread. `_selected_record()`
  liest QTableWidget — GUI-Thread, kein Lock nötig.
- **`_selected_record()` ist underscore-prefixed:** das ist "halb-privat".
  KISS: einfach aufrufen — gleicher Modul-Cluster (ui/), Mike's Codebase,
  nicht öffentliche API.
- **QRZ-Lookup:** wird via `_on_logbook_qso_clicked` getriggert (Background-
  Thread, fehlertolerant). Mehrfach-Trigger bei wiederholtem Tab-Wechsel
  ist okay — QRZ-Lookup ist idempotent + cached.
- **Hardware:** irrelevant, kein TX-Pfad.
- **State-Erhalt:** Logbuch-Tabelle-Selektion bleibt von Qt automatisch
  erhalten beim Tab-Wechsel (QStackedWidget verbirgt Widget nur, zerstört
  es nicht). Test in der Field-Phase: User selektiert EA5D, wechselt zu
  QSO, wechselt zurück — Selektion + Auto-Detail erscheinen.

## Nicht im Scope

- Logbuch-Selection-Persistierung über App-Restart
- Auto-Selektion ersten Eintrags wenn nichts selektiert ist
- Detail-Overlay-Layout-Änderungen
- QRZ-Lookup-Caching-Änderungen
- Logbook-Filter/Sort-Änderungen

## Testbarkeit

`tests/test_p66_logbook_auto_show.py` mit Mock-basiertem Test-Stil
(analog `test_p45_omni_stats_guard.py`):

| T# | Was |
|---|---|
| **T1** | `_on_qso_tab_changed(1)` mit Mock `_selected_record()=record` → `_on_logbook_qso_clicked` 1× aufgerufen mit record |
| **T2** | `_on_qso_tab_changed(1)` mit Mock `_selected_record()=None` → `_on_logbook_qso_clicked` NICHT aufgerufen, `_right_stack.setCurrentIndex` NICHT aufgerufen |
| **T3** | `_on_qso_tab_changed(0)` ruft `_right_stack.setCurrentIndex(0)` (Regression) |
| **T4** | Source-Level: `_on_qso_tab_changed` enthält `qso_panel.logbook._selected_record()` und `elif index == 1` |

Erwarteter Test-Count: 1347 + 4 = **1351 grün**.

## Mike-Field-Test (kein Radio)

| F# | Was |
|---|---|
| **F1** | App start → Logbuch-Tab klicken → eine Zeile auswählen → wechsel zu QSO-Tab → ControlPanel rechts ✓ |
| **F2** | Zurück zu Logbuch-Tab → Auswahl noch blau ✓ → rechts erscheint Detail-Overlay automatisch ✓ |
| **F3** | Logbuch-Tab klicken ohne vorherige Selektion → ControlPanel bleibt rechts (keine Auto-Action) |
| **F4** | Bestehendes Verhalten: Klick auf Logbuch-Zeile öffnet Detail (Regression) |

## Plan-Sequenz

C1: Backup
C2: `ui/mw_qso.py` Handler-Branch
C3: `main.py` APP_VERSION
C4: `tests/test_p66_logbook_auto_show.py` NEU
C5: Doku-Updates

## Offene Fragen an R1

1. Unterscheid privater Aufruf `_selected_record()` vs. neue öffentliche
   Methode `selected_record()` — KISS für Hobby-Tool oder besser sauber
   trennen?
2. Soll QRZ-Lookup beim Auto-Show wirklich nochmal triggern wenn er beim
   ersten Click schon lief und cached ist? Performance/Quota-Risiko?
3. Edge-Case: User selektiert, löscht den QSO im Logbuch, wechselt Tab —
   `_selected_record()` returnt was? (Vermutlich None weil Selektion
   geclearedt — aber prüfen)
4. Wenn `_selected_record()` Exception wirft (defekter Record-Dict),
   sollte das try/except gewrappt sein?
