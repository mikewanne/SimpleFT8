# P1-Bundle1 V1 — UI-Cleanup-Sammel-Diagnose

**Stand:** 2026-05-06, Bundle aus 5 UI-Cleanups (P1.6, P1.12, P1.15, P1.16, P1.19).
**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code.
**Begruendung Bundle:** alle UI-Aenderungen, betreffen `control_panel.py` +
`qso_panel.py` + `main_window.py`. Gemeinsame Tests + atomarer Commit.
**App-Stand:** v0.95.5, 777 Tests gruen, App laeuft als EINE Instanz.

---

## 0. Bundle-Inhalt

| # | Sub-Aufgabe | Komplexitaet | Files |
|---|---|---|---|
| **P1.6** | Versionsnummer-Anzeige sichtbar machen | Trivial (Color-Fix) | control_panel.py |
| **P1.12** | NEU-Button (`btn_remeasure`) entfernen | Trivial (Code-Loeschung) | control_panel.py + main_window.py + mw_radio.py |
| **P1.15** | Statusbar-Anzeige `→ Call \| RX: ANT` raus | Trivial (Code-Loeschung) | main_window.py |
| **P1.16** | QSO-Panel-Log: zeitbasiertes Rolling-Window 5 Min | Mittel (Refactor) | qso_panel.py |
| **P1.19** | Sterne-Anzeige fuer „Lokale Conditions" statt SNR | Mittel (Neues Widget) | control_panel.py |

---

## 1. P1.6 — Versionsnummer-Anzeige fehlt

### Symptom
Mike sah `SimpleFT8 v0.95.x` unten rechts vor 1-2 Wochen normal, jetzt
nicht mehr sichtbar. Code unveraendert, kein Layout-Glitch.

### Wurzel (verifiziert 2026-05-06, Code-Read)
`control_panel.py:1086-1090`:
```python
self._version_label = QLabel(f"SimpleFT8 v{APP_VERSION}")
self._version_label.setStyleSheet(
    f"color: #333; font-family: {_FONT}; font-size: 10px; "
    "border: none; background: transparent;"
)
```

**`color: #333` (Dunkelgrau) auf Hintergrund `#1a1a2e` (Dunkelblau-Schwarz)**
ist fast nicht zu unterscheiden. Layout korrekt, Text wird gerendert,
aber praktisch unsichtbar.

### Fix
Color heller setzen — Vorschlag:
- `#888888` (mittelgrau, aber nicht zu prominent)
- ODER `#555555` (subtiler aber lesbar)
- ODER `#444444` (Mike's Wunsch wenn moeglich noch dezent)

Mike-Frage: gewuenschte Sichtbarkeit zwischen „dezent" (#555) und
„klar lesbar" (#888)?

### Akzeptanzkriterium
Versionsnummer rechts unten lesbar, Theme-konform (nicht zu prominent).

### Aufwand: 5 Min, 1 Zeile

---

## 2. P1.12 — NEU-Button entfernen

### Symptom
KALIBRIEREN-Button (`btn_einmessen`) macht seit v0.94 im Diversity-Modus
**beides**: Phase 2 (Gain-Messung) + Phase 3 (Diversity-Verhaeltnis).
Der NEU-Button (`btn_remeasure`) macht nur Phase 3 alleine — redundant.

### Code-Pfad (verifiziert 2026-05-06)
- `control_panel.py:516-525` — Button-Definition
- `control_panel.py:1023-1024` — Signal-Verbindung (`remeasure_clicked`)
- `control_panel.py:947` — `remeasure_clicked = Signal()`
- `main_window.py:530` — Connect zu `_on_diversity_remeasure`
- `mw_radio.py:985-997` — Handler `_on_diversity_remeasure`

### Fix
Alle 5 Code-Stellen loeschen. Plus pruefen ob Layout neu balanciert
werden muss (ohne `btn_remeasure` evtl. Stretch-Faktor anpassen).

### Akzeptanzkriterium
- NEU-Button verschwindet aus UI
- KALIBRIEREN-Button funktioniert weiter (regressionsfrei)
- Layout sauber, kein Loch

### Aufwand: 10 Min, ~15 Zeilen Loeschen

---

## 3. P1.15 — Statusbar `→ Call | RX: ANT` entfernen

### Symptom
Mike: *„die macht mich irre"*. Bei aktivem QSO erscheint im
QSO-Panel-Status (untere Zeile) ein Eintrag wie `→ SP5LST  |  RX: ANT1`
oder `→ DA1TST  |  RX: ANT2 ↑3.2 dB`.

### Code-Pfad (verifiziert 2026-05-06)
- `main_window.py:920-934` — `_on_state_changed`-Pfad fuer aktives QSO:
  ```python
  self.qso_panel.status_label.setText(f"→ {their_call}  |  {ant_text}")
  self.qso_panel.status_label.setStyleSheet(...)
  ```
- Wird getriggert wenn `state not in (IDLE, TIMEOUT, CQ_CALLING, CQ_WAIT)`

### Fix
Entweder:
1. **Code-Loeschung:** Z.917-934 komplett raus
2. **Bedingt:** nur `→ {their_call}` Teil entfernen, ANT-Info irgendwo
   anders zeigen (z.B. im QSO-Panel-Log direkt)

Mike-Wunsch klar: **„komplett weg"**. Option 1.

### Akzeptanzkriterium
- Bei aktivem QSO: keine Status-Zeile mit `→ Call | RX: ANT`
- Andere status_label-Inhalte (z.B. Logbuch-Counter) bleiben unveraendert

### Aufwand: 5 Min, ~10 Zeilen Loeschen

---

## 4. P1.16 — QSO-Panel-Log: zeitbasiertes 5-Min-Rolling-Window

### Symptom
QSO-Panel-Log fuellt sich Eintrag fuer Eintrag, nach 9+ Minuten
zugemuellt. Mike's Idee: Eintraege aelter als 5 Min loeschen, juengere
ruetschen nach oben.

### Aktueller Code (verifiziert)
`qso_panel.py:266-276`:
```python
def _auto_trim(self, max_lines: int = 40):
    """QSO-Log auf ~40 Zeilen begrenzen (~3 Min Traffic)."""
    doc = self.log_view.document()
    excess = doc.blockCount() - max_lines
    if excess > 5:
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(excess):
            cursor.movePosition(QTextCursor.MoveOperation.Down, ...)
        cursor.removeSelectedText()
        cursor.deleteChar()
```

**Aktuell: zeilenbasiert (40 Zeilen, ~3 Min Traffic).** Bei 4
QSOs/Min waeren das aber nur ~30s sichtbar. Bei wenig Traffic dagegen
30 Min Verlauf — inkonsistent.

### Fix-Idee
Zeitbasierte Loeschung:
1. Bei jedem `add_tx`/`add_rx`/`add_info` Timestamp speichern (im Block-
   Userdata oder paralleler Liste)
2. Bei jedem Append: alle Eintraege aelter als 300s entfernen
3. Trenn-Linien (`─────`) und „QSO komplett" Markierungen mit
   zugehoerigem QSO-Block loeschen, nicht standalone

### Implementierungs-Optionen

**A) Zeit-Tracking via Block-Userdata** (saubere Lösung):
- QTextEdit speichert pro Block ein Timestamp
- Bei `_auto_trim` Iteration: jeden Block pruefen, alte loeschen
- Implementierung: `QTextBlockUserData` Subclass

**B) Parallele Liste** (KISS):
- `self._block_timestamps: list[(block_index, timestamp)]`
- Bei Append: Liste anhaengen
- Bei Cleanup: Liste filtern, dann Blocks per Index entfernen
- Risiko: Index-Drift bei Cleanup

**C) Timer-basierter Cleanup** (einfach):
- QTimer alle 30s ruft `_auto_trim_by_age()`
- Liest `block_timestamps`, loescht alte
- Append schreibt nur Timestamp neu

### Edge Cases
- Trenn-Linien (`─────────────`) — gehoeren zum vorherigen QSO-Block
- „CQ-Modus laeuft weiter..." sollte nur sichtbar bleiben wenn QSO
  noch im 5-Min-Fenster ist
- User-Scroll-Position nicht verlieren bei Cleanup (sticky-bottom-Logik)

### Akzeptanzkriterium
- Eintraege aelter als 5 Min werden automatisch entfernt
- Juengere Eintraege bleiben in Reihenfolge
- Scroll-Position bleibt logisch (User-Scroll respektieren)
- Kein „flackern" beim Cleanup (Cursor-Reset stoert nicht)

### Aufwand: 30 Min, ~30 Zeilen Refactor

---

## 5. P1.19 — Sterne-Anzeige fuer „Lokale Conditions"

### Symptom / Idee
Mike: SNR-Wert „-25 dB" im Status nicht intuitiv interpretierbar.
Ersetzen durch 5-Sterne-Skala mit ausgegrauten inaktiven Sternen.

### Aktueller Code (verifiziert)
`control_panel.py:878-882` SNR-Label:
```python
self.snr_label = QLabel("SNR: — dB")
self.snr_label.setStyleSheet(...)
```

`control_panel.py:1584-1585`:
```python
def update_snr(self, snr: int):
    self.snr_label.setText(f"SNR:  {snr:+d} dB")
```

`update_snr` wird in `mw_cycle.py:750` von jeder dekodierten Message
aufgerufen.

### Fix-Idee

**Datenmodell (KISS):**
1. Sterne-Score basiert auf zwei Faktoren:
   - Anzahl Stationen im Aging-Fenster (`len(self._normal_stations)` oder
     `_diversity_stations`)
   - Median-SNR der besten Haelfte aller Stationen im Fenster
2. ODER-verknuepft: eines der Kriterien reicht

**Skala:**
| Sterne | Stationen | Median-SNR (beste Haelfte) |
|---|---|---|
| ★★★★★ | 25+ | > -12 dB |
| ★★★★☆ | 15-24 | > -15 dB |
| ★★★☆☆ | 8-14 | > -18 dB |
| ★★☆☆☆ | 3-7 | > -22 dB |
| ★☆☆☆☆ | < 3 | egal |

**UI:**
- Custom QWidget mit 5 QLabels (Sterne-Glyph U+2605)
- Aktive Sterne: Neon-Cyan `#00DDFF` mit weichem Glow
- Inaktive: Outline-Style `#3a3a4e`
- Tooltip zeigt: „X Stationen, Median Y dB"
- Position: ersetzt `snr_label` an gleicher Stelle

**Ansteuerung:**
- Bestehende `update_snr(snr)` Aufrufe behalten (intern weiter SNR
  speichern fuer Reports + DT-Korrektur)
- Plus neuer Aufruf `update_local_conditions(stations_count, median_snr)`
- Wird von `mw_cycle.py` am Slot-Ende aufgerufen mit aktuellen Daten
  aus `_normal_stations` / `_diversity_stations`

### Wichtige Reihenfolge
**P1.18 (DT-Clamp Fix) MUSS VOR P1.19 implementiert sein** — sonst
zeigt die Sterne-Skala mit dem aktuellen SNR-Bias systematisch zu
schlechte Werte. Aber: Bundle1 ist isoliert UI-Aenderung. Mike kann
Sterne-Skala bauen + nach P1.18 die Schwellen kalibrieren.

### Akzeptanzkriterium
- Sterne-Anzeige ersetzt SNR-Label visuell
- Sterne aktualisieren bei jedem Slot-Ende
- Tooltip zeigt Detail-Werte
- Theme-konform (Neon-Cyan + Outline)
- Intern: SNR-Wert weiter berechnet (kein Verlust fuer Reports)

### Aufwand: 30 Min, ~50 Zeilen (Widget + Berechnung + Anbindung)

---

## 6. R1-Pruefauftraege (Pflicht fuer DeepSeek)

### 6.1 Theme-Konsistenz
Alle 5 Aenderungen muessen zum bestehenden Theme passen:
- Hintergrund `#1a1a2e`
- Text `#CCCCCC`
- Akzente Neon-Cyan `#00DDFF`, Gold `#FFD700`, Rot `#FF4444`
- Font Menlo/Monospace

R1 soll pruefen ob die vorgeschlagenen Colors fuer P1.6 und P1.19
Theme-konform sind.

### 6.2 P1.16 Edge Cases
Liste aller Edge Cases pruefen. Insbesondere:
- Was passiert mit Trenn-Linien wenn der zugehoerige QSO-Block geloescht wird?
- Was passiert wenn User scrollt waehrend Cleanup laeuft?
- Was bei sehr aktivem Funken (>10 add_*-Aufrufe pro Min)?
- Performance — QTextEdit-Block-Operationen koennen langsam sein

### 6.3 P1.19 Berechnung
Schwellenwerte (Stationen, Median-SNR) — sind die plausibel fuer FT8 auf
40m typisch? Oder zu eng/zu locker? R1 mit FT8-Domain-Wissen.

### 6.4 P1.12 Layout
Nach Loeschung von `btn_remeasure` — bleibt das Layout sauber? Stretch-
Faktor anpassen noetig?

### 6.5 Test-Coverage
Welche Tests sollten erstellt werden? Bestehende Tests die brechen
koennten?

### 6.6 Atomarer Commit oder 5 separate?
Mike-Anforderung: Bundle = ein Commit. Aber Code-Reviewer-Sicht:
sind die 5 Aenderungen logisch zusammenhaengend genug? Oder sollten
P1.16 + P1.19 separat sein (groessere Refactors)?

---

## 7. Akzeptanzkriterien (gesamt)

- [ ] P1.6 Versionsnummer sichtbar
- [ ] P1.12 NEU-Button verschwindet, KALIBRIEREN funktioniert weiter
- [ ] P1.15 Status-Zeile `→ Call | RX: ANT` weg
- [ ] P1.16 QSO-Panel-Log mit 5-Min-Rolling-Window
- [ ] P1.19 Sterne-Anzeige ersetzt SNR-Anzeige
- [ ] Tests: bestehende 777 bleiben gruen
- [ ] Neue Tests: mindestens 5 (1 pro Sub-Aufgabe)
- [ ] App startet ohne Fehler (Smoke-Test)
- [ ] Theme konsistent

---

## 8. Out-of-Scope

- P1.18 DT-Clamp-Fix (eigener Workflow, **erst danach** P1.19 schwellen kalibrieren)
- P1.14 Station-Wechsel
- P1.8 Report-SNR
- P1.11 rr73_retries
- P1.13 TX-Spinbox-Sync
- P1.7 Doppel-ADIF-Filter
- P1.17 (vermutlich von P1.18 geloest)

---

## 9. Workflow-Plan

1. ✅ V1 (diese Datei)
2. → V2 (Self-Review als frische KI)
3. → **COMPACT** zwischen V2 und R1 (V1+V2 als Files persistiert)
4. → R1 (DeepSeek mit V2 + Code-Files)
5. → V3 (R1-Findings einarbeiten)
6. → Mike-Freigabe Diagnose-V3
7. → Plan-V1→V2→R1→V3 (mit Code-Diffs)
8. → Mike-Freigabe Plan
9. → Code + Tests + atomarer Commit + Doku-Commit

---

**V1 Ende. Naechster Schritt: V2 Self-Review.**
