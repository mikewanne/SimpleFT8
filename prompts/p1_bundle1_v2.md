# P1-Bundle1 V2 — Self-Review (frische KI)

**Stand:** 2026-05-06, V1-Selfreview als frische KI.
**Workflow:** V1 → **V2** (diese Datei) → R1 → V3.
**Ergebnis:** 9 V1-Luecken geschlossen, Implementations-Optionen praeziser.

---

## 0. Self-Review-Befund (V1 → V2)

| # | V1-Luecke | V2-Korrektur |
|---|---|---|
| L1 | P1.6 Color-Wahl ohne Bezug auf bestehende Konvention | ✓ Code-Konvention geprueft: Status-Texte `#666` (z.B. `qso_panel.py:111`). Empfehlung: `#666` fuer Konsistenz |
| L2 | P1.12 Layout-Folgen unklar | ✓ `phase_row` enthaelt links `_phase_label` (zentriert) + rechts `btn_remeasure`. Nach Loeschen: nur `_phase_label` uebrig — Layout bleibt sauber, kein Loch |
| L3 | P1.15 status_label wird ueberall genutzt | ✓ Verifiziert: 5 Caller von `status_label` (qso_panel.py:207, mw_qso.py:141, mw_radio.py:232+304, main_window.py:931). Nur main_window:931-934 ist `→ Call | RX: ANT`-Pfad — andere bleiben |
| L4 | P1.16 Trenn-Linien-Detail | ✓ Trenn-Linien sind **eigene Blocks** via `_append_colored("─" * 30, "#333333")`. Jeder Block hat eigenen Index → eigene Timestamp moeglich |
| L5 | P1.16 Performance bei vielen Blocks | Geprueft: QTextEdit.document().blockCount() ist O(1), Block-Iteration O(n). Bei 50 Blocks und 30s-Timer: vernachlaessigbar |
| L6 | P1.19 Sterne-Glyph Font-Support | ✓ U+2605 (★) + U+2606 (☆) in Menlo + System-Fallback verfuegbar |
| L7 | P1.19 Median-Berechnung Definition | Top-50% nach SNR, Median = Mittelwert der oberen Haelfte. Bei N=31: top-15, Median dieser 15 |
| L8 | P1.19 Update-Frequenz unklar | Pro Slot-Ende (analog `update_decode_count` in `mw_cycle.py:411`) — alle 15s im FT8-Mode |
| L9 | Test-Coverage konkret unklar | ✓ V2 §6 mit konkreten Test-Cases pro Sub-Aufgabe |

---

## 1. P1.6 — Versionsnummer-Anzeige (PRAEZISIERT)

### Wurzel
`control_panel.py:1086-1090` — `color: #333` auf `#1a1a2e` Hintergrund =
unsichtbar.

### Fix (V2-praezise)
**Color: `#666666`** (statt #333) — passt zur bestehenden Konvention:
- `qso_panel.py:111` Status-Text: `#666`
- `qso_panel.py:208` „X QSO(s) diese Session": `#666`
- `qso_panel.py:217` Info-Nachrichten: `#666666`

`#666` ist klar lesbar auf `#1a1a2e` aber dezent. Mike's bestaetigte
„Status-Texte"-Konvention.

### Tests
- Keine Unit-Tests noetig (reine UI-Color-Aenderung)
- Smoke-Test: App startet, Versionsnummer sichtbar

---

## 2. P1.12 — NEU-Button entfernen (PRAEZISIERT)

### Layout-Auswirkung verifiziert
`phase_row` (`control_panel.py:507-525`):
```python
phase_row = QHBoxLayout()
phase_row.addStretch()                      # Z.508
phase_row.addWidget(self._phase_label)      # Z.515 — zentriert
phase_row.addWidget(self.btn_remeasure)     # Z.525 — rechts → ZU LÖSCHEN
```

Nach Loeschen: `_phase_label` ist allein im Row, mit `addStretch()`
links. Visuell: Text bleibt zentriert/links, kein Loch rechts. Sauber.

### Files (5 Stellen)
1. `control_panel.py:516-525` — Button-Definition + Setup → komplett raus
2. `control_panel.py:947` — `remeasure_clicked = Signal()` → raus
3. `control_panel.py:1023-1024` — `self.btn_remeasure = ant_card.btn_remeasure` + Connect → raus
4. `main_window.py:530` — `self.control_panel.remeasure_clicked.connect(self._on_diversity_remeasure)` → raus
5. `mw_radio.py:985-997` — `_on_diversity_remeasure` Methode → komplett raus

### Tests
- Bestehende Tests pruefen: gibt es Test der `btn_remeasure` referenziert?
  Falls ja: anpassen oder loeschen
- Smoke-Test: App startet, KALIBRIEREN funktioniert weiter

---

## 3. P1.15 — Statusbar `→ Call | RX: ANT` raus (PRAEZISIERT)

### Code-Stelle (verifiziert)
`main_window.py:917-934` (Block in `_on_state_changed` o.ae.):

```python
# ZU LÖSCHEN: Z.917-934 (oder analog der state-aktiven Block)
ant_color = "#888888"
if (self._rx_mode == "diversity"
        and hasattr(self, '_antenna_prefs')):
    pref_entry = self._antenna_prefs.get_pref(their_call)
    if pref_entry and pref_entry['best_ant'] == "A2":
        delta = pref_entry.get('delta_db')
        if delta is None:
            ant_text = "RX: ANT2"
        else:
            ant_text = f"RX: ANT2 ↑{abs(delta):.1f} dB"
        ant_color = "#44FF88"
self.qso_panel.status_label.setText(f"→ {their_call}  |  {ant_text}")
self.qso_panel.status_label.setStyleSheet(...)
```

### Wichtig (V2-Fund)
Vor dem zu loeschenden Block ist vermutlich Init-Code fuer `ant_text`
und Bedingung `if their_call:`. **Nur den `setText/setStyleSheet`-Block
loeschen** der `→ Call | RX: ANT` schreibt. Andere Branches behalten.

→ R1 muss pruefen: ist die status_label-Setzung in mehrere Pfade
aufgeteilt? Welcher genau ist Mike's Aerger-Pfad?

### Tests
- Smoke-Test: bei aktivem QSO erscheint kein `→ Call`-Text mehr
- Existierende Tests fuer „X QSO(s) diese Session"-Anzeige bleiben gruen

---

## 4. P1.16 — 5-Min-Rolling-Window (IMPLEMENTIERUNGS-DETAILS)

### Aktueller Code (verifiziert)
`qso_panel.py:266-276` `_auto_trim(max_lines=40)` — zeilenbasiert.

### V2-Empfehlung: Option B mit QTextBlockUserData

**Warum Option B (parallele Liste):**
- Weniger Boilerplate als QTextBlockUserData-Subclass
- Index-Drift loesbar via Re-Build der Liste nach Cleanup

**Pseudocode:**
```python
class QSOPanel:
    def __init__(self):
        ...
        self._block_timestamps: list[float] = []  # parallel zu Block-Index
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(30_000)  # 30s
        self._cleanup_timer.timeout.connect(self._auto_trim_by_age)
        self._cleanup_timer.start()

    def _append_colored(self, text, color):
        # ... bestehender Code ...
        self._block_timestamps.append(time.time())  # NEU

    def _auto_trim_by_age(self, max_age_s: float = 300.0):
        now = time.time()
        cutoff = now - max_age_s
        # Anzahl alter Blocks bestimmen
        n_old = sum(1 for ts in self._block_timestamps if ts < cutoff)
        if n_old < 5:  # Mindest-Schwelle gegen Flackern
            return
        # Top n_old Blocks aus Document loeschen
        doc = self.log_view.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(n_old):
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar()
        # Liste synchron halten
        self._block_timestamps = self._block_timestamps[n_old:]
```

### Trenn-Linien-Behandlung
**V2-Loesung:** Trenn-Linien werden ebenfalls per `_append_colored`
geschrieben → bekommen ihren eigenen Timestamp. Wenn der QSO-Block davor
geloescht wird (alle Eintraege > 5 Min), wird die Trenn-Linie auch
geloescht (gleicher Slot oder kurz danach).

**Edge Case:** Trenn-Linie genau am Cutoff-Zeitpunkt → bleibt stehen
ohne zugehoerigen Block. Ist visuell ok (eine einzelne Linie oben).

### Scroll-Position
**V2-Loesung:**
- Vor Cleanup: `scrollbar.value()` und `scrollbar.maximum()` merken
- Bei Cleanup: nur scrollen wenn User vorher am Bottom war
- Sonst: User-Scroll behalten

### Tests
- Test: `_append_colored` einmal aufrufen → `_block_timestamps` hat 1 Eintrag
- Test: Mock `time.time()` → 10 Eintraege ueber 600s gespreizt → `_auto_trim_by_age()` → bleiben nur Eintraege < 300s
- Test: Trenn-Linien-Behandlung
- Test: Scroll-Position

---

## 5. P1.19 — Sterne-Anzeige (IMPLEMENTIERUNGS-DETAILS)

### Datenmodell verfeinert

**Score-Berechnung:**
```python
def compute_local_conditions(stations: dict) -> tuple[int, int, float]:
    """Returnt (sterne, n_stations, median_snr_top_half).

    sterne: 1-5
    median_snr_top_half: Median der oberen 50% nach SNR sortiert.
    """
    if not stations:
        return 1, 0, -99.0  # 1 Stern wenn nichts empfangen

    snrs = sorted([s.snr for s in stations.values() if hasattr(s, 'snr')],
                  reverse=True)  # absteigend
    n = len(snrs)
    top_half = snrs[:max(1, n // 2)]  # obere Haelfte (mind. 1)
    median = top_half[len(top_half) // 2] if top_half else -99.0

    # Skala (ODER-verknuepft, beide muessen nicht erfuellt sein)
    if n >= 25 or median > -12:
        return 5, n, median
    if n >= 15 or median > -15:
        return 4, n, median
    if n >= 8 or median > -18:
        return 3, n, median
    if n >= 3 or median > -22:
        return 2, n, median
    return 1, n, median
```

### UI-Widget

**StarsConditionWidget (NEU in `ui/widgets/`):**
```python
class StarsConditionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stars = []
        for i in range(5):
            lbl = QLabel("★")
            lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
            self._stars.append(lbl)
            layout.addWidget(lbl)
        layout.addStretch()

    def set_score(self, score: int, tooltip: str = ""):
        for i, lbl in enumerate(self._stars):
            if i < score:
                lbl.setStyleSheet(self._STAR_ACTIVE_STYLE)
            else:
                lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
        self.setToolTip(tooltip)

    _STAR_ACTIVE_STYLE = (
        "color: #00DDFF; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
        # Glow waere via QGraphicsDropShadowEffect — V3 entscheiden
    )
    _STAR_INACTIVE_STYLE = (
        "color: #3a3a4e; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )
```

### Anbindung

**`control_panel.py:878` SNR-Label ersetzen:**
```python
# ALT:
# self.snr_label = QLabel("SNR: — dB")

# NEU:
self.conditions_widget = StarsConditionWidget()
self._last_snr_internal = -30  # intern fuer DT-Korrektur etc.
```

**Bestehende `update_snr(snr)` Methode beibehalten** (wird fuer interne
Berechnungen weiter aufgerufen). Plus neue Methode:

```python
def update_local_conditions(self, score: int, n_stations: int, median_snr: float):
    tooltip = f"{n_stations} Stationen, Median {median_snr:+.0f} dB"
    self.conditions_widget.set_score(score, tooltip)
```

**Aufruf in `mw_cycle.py:411` (oder analog):**
```python
score, n, med = compute_local_conditions(self._normal_stations)
self.control_panel.update_local_conditions(score, n, med)
```

### Update-Frequenz
Pro Slot-Ende (analog `update_decode_count`).

### Tests
- Test: `compute_local_conditions(empty_dict)` → (1, 0, -99.0)
- Test: `compute_local_conditions(31 stations, alle -10)` → (5, 31, -10)
- Test: `compute_local_conditions(2 stations, beide -25)` → (1, 2, -25)
- Test: Sterne-Widget rendering — Smoke-Test
- Test: Tooltip-Inhalt

---

## 6. R1-Pruefauftraege (V2-erweitert)

### 6.1 Theme-Konsistenz
Alle Colors gegen bestehende Konvention:
- `#666` fuer P1.6 ✓ konsistent
- `#00DDFF` Sterne aktiv — Neon-Cyan ist im Theme
- `#3a3a4e` Sterne inaktiv — passt zu Hintergrund-Variante
- R1 pruefen: ist `#3a3a4e` zu schwach um „Outline" zu wirken?

### 6.2 Sub-Aufgaben-Konflikte
Beruehren sich die 5 Sub-Aufgaben? Kritisch:
- P1.16 modifiziert `qso_panel.py` — kein Konflikt mit anderen
- P1.19 modifiziert `control_panel.py` — Konflikt mit P1.6 (gleicher File)?
  → Antwort: getrennte Stellen (Z.1086 vs Z.878), kein Konflikt
- P1.12 modifiziert 3 Files — Konflikt? Nein, isolierte Loeschungen

### 6.3 Test-Coverage
14 neue Tests erforderlich (siehe pro Sub-Aufgabe). R1 pruefen ob Liste
vollstaendig.

### 6.4 P1.16 Performance bei intensiver Session
Mike's Praxis: ~4 QSOs/Min. Bei 5-Min-Window = 20 QSOs * ~10 Eintraege
= 200 Blocks. QTextEdit Block-Operationen O(n) → 30s-Timer iteriert
ueber 200 Eintraege → ~ms. Performance OK.

### 6.5 P1.19 Berechnungs-Schwellen
Schwellen (25+/-12, 15+/-15, etc.) sind aktuelle Schaetzung. Nach
P1.18-Fix neu kalibrieren. R1 pruefen ob Skala sinnvoll oder eng.

### 6.6 Atomarer Commit?
Mike-Anforderung: 1 Commit fuer Bundle. Code-Reviewer-Sicht:
- Total ~150 Zeilen
- 5 Sub-Aufgaben unabhaengig aber gleichthematisch (UI-Cleanup)
- Test-Coverage 14 Tests neu
- Akzeptabel fuer atomaren Commit

R1 final pruefen ob aufteilen sinnvoll waere.

### 6.7 Order von Tests
Welche Tests zuerst? Vorschlag:
1. Trivial-Tests (P1.6, P1.12, P1.15) — einfach
2. P1.16 Tests (zeitbasiert, mock time.time)
3. P1.19 Tests (compute_local_conditions + Widget)

### 6.8 Backward-Compat
- `update_snr()` weiter aufrufbar (intern noetig)
- `snr_label` Attribut wird ersetzt durch `conditions_widget`
- Tests die `snr_label.text()` testen → anpassen

---

## 7. Akzeptanzkriterien (V2-vollstaendig)

### Code-Akzeptanz
- [ ] P1.6: Versionsnummer mit Color `#666` sichtbar
- [ ] P1.12: NEU-Button + Signal + Handler komplett entfernt (5 Stellen)
- [ ] P1.15: `→ Call | RX: ANT`-Pfad in main_window.py raus
- [ ] P1.16: 5-Min-Rolling-Window in qso_panel.py via Block-Timestamps
- [ ] P1.19: StarsConditionWidget ersetzt SNR-Label visuell
- [ ] `update_snr()` weiter aufrufbar (interne Logik)
- [ ] 14 neue Tests gruen
- [ ] Bestehende 777 Tests gruen (oder angepasst wo `snr_label` referenziert)

### Field-Test
- [ ] App startet ohne Fehler
- [ ] Versionsnummer rechts unten lesbar
- [ ] KALIBRIEREN funktioniert wie zuvor
- [ ] Bei aktivem QSO: keine `→ Call`-Anzeige mehr
- [ ] Nach 5+ Min Funken: alte QSO-Eintraege im Panel verschwunden
- [ ] Sterne-Anzeige reagiert sinnvoll auf Conditions-Aenderungen

---

## 8. Workflow-Plan (V2)

1. ✅ V1
2. ✅ V2 (diese Datei)
3. → **COMPACT**
4. → R1 mit V2 + 4 Code-Files (control_panel.py + qso_panel.py +
   main_window.py + mw_radio.py)
5. → V3 (R1-Findings einarbeiten)
6. → Mike-Freigabe Diagnose-V3
7. → Plan-V1→V2→R1→V3 mit Code-Diffs
8. → Mike-Freigabe Plan
9. → Code-Implementation + Tests
10. → Atomarer Commit + Doku-Commit

---

**V2 Ende. Naechster Schritt: COMPACT, dann R1.**
