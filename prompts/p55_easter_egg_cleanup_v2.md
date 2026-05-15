Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P55 — Easter-Egg + Diversity-CQ-Code-Leichen entfernen — V2

## 1. Ziel

Easter-Egg-Funktion und obsolete `_omni_active`-Doppel-Logik in `btn_cq`
komplett entfernen. **Frequenzwahl-Logik bleibt unverändert.**

**Mike-Spec 15.05.2026:**
- „In Diversity soll es nur OMNI CQ geben, keinen normalen CQ auch
  nicht versteckt."
- „Es gibt auch keine Easter-Egg-Funktion mehr."
- „Normal ist so als wenn es ein ganz normales FT8-Programm wäre ohne
  unsere ganzen Verbesserungen." → btn_cq in Normal als manueller CQ
  bleibt unangetastet, alle Diversity-Extras (OMNI, AUTO HUNT) in
  Diversity-Modus.

**Was heute schon korrekt ist:**
- `btn_cq` ist in Diversity bereits hidden via
  `_update_button_visibility` (`main_window.py:789`).
- Mode-Coupling-Routing funktioniert nominell richtig.

**Was Leiche ist (greift nie weil btn_cq in Diversity hidden):**
- `ControlPanel._omni_active`-Flag (`control_panel.py:1343+1674`).
- `btn_cq.setText("OMNI CQ ■")`-Branch in `_on_cq_clicked` +
  `set_cq_active` (Z.1811-1816 + 1827-1830).
- Easter-Egg-Override in `_update_button_visibility`
  (`main_window.py:785`).
- `_easter_egg_active`-Variable + `_on_easter_egg_toggle`
  (`main_window.py:333+746-769`).
- `easter_egg_toggle_clicked`-Signal + Version-Label-Click-Handler
  (`control_panel.py:1197+1356`).
- `mw_radio.py` 5× `hasattr(self, "_easter_egg_active"): ... = False`-
  Reset-Lines (Z.565+657+858+1164+1750).
- Stop-Reason `"easter_egg_off"` für `_auto_hunt`/`_omni_cq` wird nicht
  mehr produziert wenn der Easter-Egg-Pfad weg ist.

## 2. Akzeptanzkriterien

| # | Kriterium | Verifikation |
|---|---|---|
| AC1 | In Code-Verzeichnissen (`ui/`, `core/`, `radio/`) kein Auftreten von `easter_egg` oder `_easter_egg_active` im **Code** (Kommentare die historisch erklären sind OK) | grep mit `--include='*.py'` und Sichtprüfung |
| AC2 | `ControlPanel._omni_active` ist gelöscht — kein Attribut mehr | grep `_omni_active` in `control_panel.py` = 0 |
| AC3 | `_on_cq_clicked` setzt `btn_cq.setText` nur auf „CQ AKTIV ■" / „CQ RUFEN" — kein „OMNI"-Branch mehr. Gleiches für `set_cq_active` | Source-Test |
| AC4 | `_update_button_visibility` ist 2-Wege ohne Override: Normal → `btn_cq` sichtbar + OMNI+Hunt hidden; Diversity → `btn_cq` hidden + OMNI+Hunt sichtbar. **Keine** `_easter_egg_active`-Branch | Source-Test |
| AC5 | Version-Label hat keinen `mousePressEvent`-Override mehr **und** kein `PointingHandCursor` (default Cursor — Click-Affordanz weg) | Source-Test |
| AC6 | `easter_egg_toggle_clicked` als Signal in `ControlPanel` entfernt | grep = 0 |
| AC7 | Stop-Reason `"easter_egg_off"` aus `test_auto_hunt_extended.py`-Parametrisierungen entfernt (Z.81 + Z.115). Tests laufen mit verbleibenden Reasons weiter | pytest |
| AC8 | App startet sauber, Normal/Diversity-Wechsel funktioniert wie gehabt, OMNI-CQ + AUTO HUNT in Diversity weiter aktiv | Tests grün + Smoke-Test |
| AC9 | Tests grün 1258 → ≥ 1258 (Test-Code-Anpassungen Netto ±0 oder +N durch neue P55-Source-Level-Tests) | pytest |
| AC10 | Hardware-Pflicht: kein `set_tx_antenna`-Pfad berührt — pure UI-/State-Cleanup | grep diff |

## 3. Betroffene Module/Dateien

### Code-Removal

| Datei | Was | Zeilen |
|---|---|---|
| `ui/main_window.py` | `self.control_panel.easter_egg_toggle_clicked.connect(...)` raus | 324 |
| `ui/main_window.py` | `self._easter_egg_active: bool = False` raus | 333 |
| `ui/main_window.py` | `_on_easter_egg_toggle`-Methode komplett raus | 746-769 |
| `ui/main_window.py` | `_update_button_visibility` simplifizieren: `show_power_buttons = is_diversity` | 783-789 |
| `ui/control_panel.py` | `easter_egg_toggle_clicked = Signal()` raus | 1197 |
| `ui/control_panel.py` | `self._omni_active = False` raus | 1343 |
| `ui/control_panel.py` | `self._version_label.setCursor(...)` + `mousePressEvent`-Override raus | 1355-1356 |
| `ui/control_panel.py` | `self._omni_active = active` raus in `update_omni_tx` | 1674 |
| `ui/control_panel.py` | `_on_cq_clicked`: OMNI-Branch raus, nur „CQ AKTIV ■"/„CQ RUFEN" | 1811-1816 |
| `ui/control_panel.py` | `set_cq_active`: OMNI-Branch raus | 1827-1830 |
| `ui/mw_radio.py` | 5× `if hasattr(self, "_easter_egg_active"): self._easter_egg_active = False` raus | 565, 657, 858, 1164, 1750 |

### Test-Anpassung

| Datei | Was | Zeilen |
|---|---|---|
| `tests/test_bundle_i.py` | `obj._easter_egg_active = True` raus | 84 |
| `tests/test_omni_cq_integration.py` | `mw._easter_egg_active = False` raus | 135 |
| `tests/test_auto_hunt_extended.py` | `"easter_egg_off"` aus beiden Parametrize-Listen | 81, 115 |

### Neu

| Datei | Was |
|---|---|
| `tests/test_p55_easter_egg_removed.py` | 5 Source-Level-Tests AC1-AC5 als Regressions-Schutz |

## 4. Randbedingungen

### Was bleibt unverändert
- **Frequenz-Such-Logik** in `core/diversity.py` (`_SEARCH_INTERVAL_SLOTS`,
  Sticky, Suchbereich) — Mike-Spec explizit.
- `btn_cq` in **Normal** als manueller CQ — `_on_cq_clicked`-Branch ohne
  OMNI bleibt.
- `btn_omni_cq` + `btn_auto_hunt` in **Diversity** — Mechanik via
  `_update_button_visibility` bleibt.
- Mode-Coupling Normal↔Diversity bleibt.
- Versions-Label-Text + Position bleibt — nur **Click-Funktion** + Cursor
  weg.

### Stop-Reason `"easter_egg_off"`
- Wird heute nur in `_on_easter_egg_toggle` aufgerufen
  (`main_window.py:757+759`).
- Nach Entfernen dieser Methode wird der String nirgendwo mehr
  produziert.
- `_auto_hunt.stop_auto_hunt(reason)` und `_omni_cq.stop(reason)` sind
  Strings-akzeptierend ohne Whitelist — kein Replace nötig.
- Test-Parametrize-Listen können den String einfach streichen.

### RX-Mode-Wechsel-Stops bleiben
- Diversity→Normal-Wechsel ruft heute `_omni_cq.stop("rx_mode_change")`
  und `_auto_hunt.stop_auto_hunt("rx_mode_change")` in
  `mw_radio._on_rx_mode_changed:544-547` — unverändert.
- Diese decken den User-Anwendungsfall (Mode-Switch) bereits ab.

### Hardware-Pflicht
Nicht TX-relevant. Pure UI-/State-Cleanup, kein Antennen-Pfad berührt,
keine `set_tx_antenna`-Stelle in den geänderten Files.

### Commit-Reihenfolge
1. **Code-Removal pro Modul** atomar:
   - C1: `main_window.py` (Easter-Egg-Methode + Variable + Connect +
     `_update_button_visibility`)
   - C2: `control_panel.py` (Signal + `_omni_active` + Click-Handler +
     btn_cq-Branches)
   - C3: `mw_radio.py` (5 Reset-Lines)
2. **Tests-Anpassung** atomar:
   - C4: 3 bestehende Tests bereinigt (Mocks + Parametrize-Listen)
3. **Neuer Regressions-Test:**
   - C5: `test_p55_easter_egg_removed.py` (5 Source-Level-Assertions)
4. **APP_VERSION** Bump:
   - C6: `main.py` 0.97.29 → 0.97.30
5. **Doku:**
   - C7: HISTORY + HANDOFF + CLAUDE-Header + TODO + Memory + Plan-Files

## 5. Nicht im Scope

- **Frequenz-Such-Logik ändern** — Mike-Spec.
- **OMNI-CQ-Logik selbst ändern** — nur Eingangstor („Easter-Egg") raus.
- **AUTO HUNT verändern** — wird mit Diversity-Mode-Coupling so wie heute
  weiter sichtbar.
- **Bandpilot in Normal entfernen** — Mike's „normal als wenn ohne unsere
  Verbesserungen" könnte auch Bandpilot ausschließen, aber das ist
  separater Aufwand (Bandpilot greift heute schon mode-übergreifend) →
  **separates P56** wenn Mike das tatsächlich will.
- **Reihenfolge im UI-Layout** (Button-Position etc.).

## 6. Testbarkeit

### Bestehende Test-Suite (1258)
- 3 Test-Files bereinigt — keine funktionale Test-Logik berührt, nur
  Mock-State-Setzungen die einen entfernten State setzen wollten.
- `test_auto_hunt_extended.py`-Parametrisierung: `"easter_egg_off"` raus
  aus zwei Listen (Z.81+Z.115). Restliche Reasons decken Stop-Verhalten
  weiter ab.

### Neue Source-Level-Tests `test_p55_easter_egg_removed.py`

| Test | AC | Pattern |
|---|---|---|
| T1 `test_no_easter_egg_in_code` | AC1 | grep ohne Kommentare auf `_easter_egg_active`/`easter_egg_toggle` in `ui/main_window.py`/`ui/control_panel.py`/`ui/mw_radio.py` |
| T2 `test_control_panel_no_omni_active` | AC2 | inspect-Source `control_panel.py`, kein Vorkommen von `_omni_active` (außer `__pycache__`) |
| T3 `test_update_button_visibility_simple` | AC4 | inspect `main_window._update_button_visibility`-Source, prüft dass weder `_easter_egg_active` noch ein Override-Branch drin ist |
| T4 `test_version_label_no_click_handler` | AC5 | inspect `control_panel.py`-Source, kein `mousePressEvent` an `_version_label` und kein `PointingHandCursor` |
| T5 `test_no_easter_egg_signal` | AC6 | inspect-Source, `easter_egg_toggle_clicked` als Signal-Definition nicht mehr in `ControlPanel` |

Pattern: Source-Level analog T9/T10/T13 aus P53 — read der `.py`-Datei +
`assert "x" not in text` (anti-regression).

---

## Hinweise zur Self-Review (V1 → V2 angewendet)

- ✓ Versions-Label-Cursor: in AC5 jetzt explizit auch `setCursor` raus
- ✓ T1 präziser: nur Code-Auftreten, Doku/Kommentare OK
- ✓ Stop-Reason `easter_egg_off` Parametrize-Eintrag aus 2 Test-Listen
  raus (Z.81+115) — Tests funktionieren weiter mit verbleibenden Reasons
- ✓ Commit-Reihenfolge dokumentiert: Code zuerst (atomar pro Modul),
  dann Tests, dann Version+Doku
- ✓ Bandpilot-Frage als „nicht im Scope, separates P56" geparkt
