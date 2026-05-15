# P55 — Easter-Egg + Diversity-CQ-Code-Leichen entfernen — V3

Status: **freigegeben durch R1 (V4-pro)**, 5 Findings (1 Bug + 1 Risiko +
1 Verbesserung + 2 Hinweise), 4 angenommen, 1 mit Doku-Kommentar
akzeptiert.

Vorgänger: V1 (Self-Review), V2, R1-Review V4-pro, V3.

## 1. Ziel

Easter-Egg-Funktion und obsolete `_omni_active`-Doppel-Logik in `btn_cq`
komplett entfernen. **Frequenzwahl-Logik bleibt unverändert.**

**Mike-Spec 15.05.2026:**
- „In Diversity soll es nur OMNI CQ geben, keinen normalen CQ auch
  nicht versteckt."
- „Es gibt auch keine Easter-Egg-Funktion mehr."
- „Normal ist so als wenn es ein ganz normales FT8-Programm wäre ohne
  unsere ganzen Verbesserungen." → btn_cq in Normal als manueller CQ
  bleibt unangetastet, alle Diversity-Extras (OMNI, AUTO HUNT) bleiben
  im Diversity-Modus.

## 2. Akzeptanzkriterien

| # | Kriterium | Verifikation |
|---|---|---|
| AC1 | **Rekursive grep** in `ui/`, `core/`, `radio/` über alle `.py`: kein Vorkommen von `easter_egg` oder `_easter_egg_active` als Code-Identifier. Reine `#`-Doku-Kommentare die Historie erklären sind OK; auskommentierter Code, `# TODO: easter_egg re-enable`-Notizen oder Doc-String-Mentions sind NICHT OK | grep (siehe T1) |
| AC2 | `ControlPanel._omni_active` ist gelöscht — kein Attribut mehr | grep `_omni_active` in `control_panel.py` = 0 |
| AC3 | `_on_cq_clicked` setzt `btn_cq.setText` nur auf „CQ AKTIV ■" / „CQ RUFEN" — kein „OMNI"-Branch mehr. Gleiches für `set_cq_active` | Source-Test |
| AC4 | `_update_button_visibility` ist 2-Wege ohne Override: Normal → `btn_cq` sichtbar + OMNI+Hunt hidden; Diversity → `btn_cq` hidden + OMNI+Hunt sichtbar. **Keine** `_easter_egg_active`-Branch | Source-Test |
| AC5 | Version-Label hat keinen `mousePressEvent`-Override mehr **und** keinen `PointingHandCursor` (default Cursor — Click-Affordanz weg) | Source-Test |
| AC6 | `easter_egg_toggle_clicked` als Signal in `ControlPanel` entfernt | grep = 0 |
| AC7 | Stop-Reason `"easter_egg_off"` aus `test_auto_hunt_extended.py`-Parametrisierungen entfernt (Z.81 + Z.115). Tests laufen mit verbleibenden Reasons weiter | pytest |
| AC8 | **Smoke-Test-Checkliste** (siehe §6): App-Start, Normal↔Diversity-Wechsel, OMNI-CQ-Toggle in Diversity, AUTO HUNT-Toggle in Diversity, Klick auf Version-Label hat keinen Effekt mehr, Cursor bei Hover über Version ist default | manuell + Tests grün |
| AC9 | **`core/auto_hunt.py`** Doc-String-Verweise auf Easter-Egg entfernt (Z.81, 148, 151) — Kommentare die Stop-Reason-Liste aufzählen sollen die obsoleten Reason nicht mehr nennen | grep |
| AC10 | Hardware-Pflicht: kein `set_tx_antenna`-Pfad berührt — pure UI-/State-Cleanup | grep diff |
| AC11 | Tests grün 1258 → ≥ 1258 (Test-Code-Anpassungen Netto ±0 oder +N durch neue P55-Source-Level-Tests) | pytest |

## 3. Betroffene Module/Dateien

> **Wichtiger Hinweis (R1-F2):** Zeilennummern unten sind **ungefähr**
> (Stand v0.97.29). Identifikation primär über den genannten **Inhalt**
> via grep — nicht über die Zeilennummer.

### Code-Removal

| Datei | Was raus | Ungefähre Zeile | Grep-Anker |
|---|---|---|---|
| `ui/main_window.py` | `self.control_panel.easter_egg_toggle_clicked.connect(...)` | ~324 | `easter_egg_toggle_clicked.connect` |
| `ui/main_window.py` | `self._easter_egg_active: bool = False` | ~333 | `_easter_egg_active: bool = False` |
| `ui/main_window.py` | `_on_easter_egg_toggle`-Methode komplett (inkl. Doku-Kommentar) | ~746-769 | `def _on_easter_egg_toggle` |
| `ui/main_window.py` | `_update_button_visibility` simplifizieren: `show_power_buttons = is_diversity` (Override-Branch weg) | ~785 | `show_power_buttons = is_diversity or` |
| `ui/control_panel.py` | `easter_egg_toggle_clicked = Signal()` | ~1197 | `easter_egg_toggle_clicked = Signal` |
| `ui/control_panel.py` | `self._omni_active = False` | ~1343 | `self._omni_active = False` |
| `ui/control_panel.py` | `self._version_label.setCursor(...)` + `mousePressEvent`-Override | ~1355-1356 | `_version_label.setCursor` + `_version_label.mousePressEvent` |
| `ui/control_panel.py` | `self._omni_active = active` in `update_omni_tx` | ~1674 | `self._omni_active = active` |
| `ui/control_panel.py` | `_on_cq_clicked`: OMNI-Branch raus, nur „CQ AKTIV ■"/„CQ RUFEN" | ~1811-1816 | `if self._omni_active:` (1.) |
| `ui/control_panel.py` | `set_cq_active`: OMNI-Branch raus | ~1827-1830 | `if self._omni_active:` (2.) |
| `ui/mw_radio.py` | 5× `if hasattr(self, "_easter_egg_active"): self._easter_egg_active = False` | ~565, 657, 858, 1164, 1750 | `hasattr(self, "_easter_egg_active")` |
| **`core/auto_hunt.py`** | **R1-F1:** 3 Doc-String-Verweise auf `easter_egg_off`-Stop-Reason in Liste der akzeptierten Reasons | ~81, 148, 151 | `easter_egg_off` |

### Test-Anpassung

| Datei | Was | Ungefähre Zeile |
|---|---|---|
| `tests/test_bundle_i.py` | `obj._easter_egg_active = True` raus | ~84 |
| `tests/test_omni_cq_integration.py` | `mw._easter_egg_active = False` raus | ~135 |
| `tests/test_auto_hunt_extended.py` | `"easter_egg_off"` aus beiden Parametrize-Listen | ~81, ~115 |

### Neu

| Datei | Was |
|---|---|
| `tests/test_p55_easter_egg_removed.py` | 6 Source-Level-Tests AC1-AC6 + AC9 als Regressions-Schutz |

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
- **R1-F1:** Doc-Strings in `core/auto_hunt.py` (Z.81, 148, 151)
  zählen den Reason in einer Aufzählung auf — auch raus.

### RX-Mode-Wechsel-Stops bleiben
- Diversity→Normal-Wechsel ruft `_omni_cq.stop("rx_mode_change")` und
  `_auto_hunt.stop_auto_hunt("rx_mode_change")` in
  `mw_radio._on_rx_mode_changed:544-547` — unverändert.

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
   - C4: `core/auto_hunt.py` (3 Doc-String-Verweise — R1-F1)
2. **Tests-Anpassung** atomar:
   - C5: 3 bestehende Tests bereinigt (Mocks + Parametrize-Listen)
3. **Neuer Regressions-Test:**
   - C6: `test_p55_easter_egg_removed.py` (6 Source-Level-Assertions)
4. **APP_VERSION** Bump:
   - C7: `main.py` 0.97.29 → 0.97.30
5. **Doku:**
   - C8: HISTORY + HANDOFF + CLAUDE-Header + TODO + Memory + Plan-Files

## 5. Nicht im Scope

- **Frequenz-Such-Logik ändern** — Mike-Spec.
- **OMNI-CQ-Logik selbst ändern** — nur Easter-Egg-Eingangstor raus.
- **AUTO HUNT verändern** — bleibt sichtbar in Diversity.
- **Bandpilot in Normal entfernen** — könnte zukünftig (Mike's „normal
  als wenn ohne unsere Verbesserungen") relevant werden, **aber separat**
  (P57 wenn nötig).
- **P56 Gain pro Band** — separater Workflow.

## 6. Testbarkeit

### Bestehende Test-Suite (1258)
- 3 Test-Files bereinigt — keine funktionale Test-Logik berührt, nur
  Mock-State-Setzungen die einen entfernten State setzen wollten.
- `test_auto_hunt_extended.py`-Parametrisierung: `"easter_egg_off"` raus
  aus zwei Listen. Restliche Reasons decken Stop-Verhalten weiter ab.

### Neue Source-Level-Tests `test_p55_easter_egg_removed.py`

| Test | AC | Pattern |
|---|---|---|
| T1 `test_no_easter_egg_in_code` | AC1 | **rekursiver Walk** über `ui/`, `core/`, `radio/` mit allen `.py`. Pro Datei: lese Source, strippe `#`-Kommentar-Zeilen, dann `assert "easter_egg" not in stripped`. Dokumentations-Kommentare die mit `#` beginnen sind OK |
| T2 `test_control_panel_no_omni_active` | AC2 | inspect-Source `control_panel.py`, kein Vorkommen von `_omni_active` |
| T3 `test_update_button_visibility_simple` | AC4 | inspect `main_window._update_button_visibility`-Source, prüft dass weder `_easter_egg_active` noch ein Override-Branch drin ist |
| T4 `test_version_label_no_click_handler` | AC5 | inspect `control_panel.py`-Source, kein `mousePressEvent` an `_version_label` und kein `PointingHandCursor` |
| T5 `test_no_easter_egg_signal` | AC6 | inspect-Source, `easter_egg_toggle_clicked` als Signal-Definition nicht mehr in `ControlPanel` |
| T6 `test_auto_hunt_docstrings_clean` | AC9 | inspect `core/auto_hunt.py`-Source, `easter_egg_off` kommt nicht mehr vor (auch nicht in Doc-Strings) |

**Doku-Hinweis im Test-Header (R1-F5):**
```python
# HINWEIS: Diese Tests sind symptomatisch (rein Source-grep). Wenn künftig
# ein legitimes Feature den Identifier 'easter_egg' verwendet (sehr
# unwahrscheinlich, war historisches Konzept), müssen die Patterns hier
# nachjustiert werden. Bewusst KISS gegen Regression-Schutz.
```

### Smoke-Test-Checkliste (AC8)

Nach Code-Commits manuell in App (5 Min):

1. ☐ App startet ohne Crash, Version-Label „SimpleFT8 v0.97.30" sichtbar
2. ☐ Hover über Version-Label: **Cursor bleibt default** (kein Pointer mehr)
3. ☐ Klick auf Version-Label: **nichts passiert** (kein Konsolen-Log, keine Button-Änderung)
4. ☐ Mode-Switch Normal → Diversity: `btn_cq` weg, OMNI+Hunt erscheinen
5. ☐ Mode-Switch Diversity → Normal: OMNI+Hunt weg, `btn_cq` erscheint
6. ☐ OMNI-CQ-Start in Diversity: funktioniert wie gehabt (Frequenz-Sticky, Slot-Pattern)
7. ☐ AUTO HUNT-Start in Diversity: funktioniert wie gehabt
8. ☐ btn_cq-Klick in Normal: `CQ AKTIV ■`-Label, normaler CQ läuft

## R1-Findings — Aufnahme

| # | Schwere | Finding | Status | Begründung |
|---|---|---|---|---|
| 1 | 🔴 Bug | `core/auto_hunt.py` nicht in V2-Datei-Liste, 3 Doc-String-Verweise auf `easter_egg_off` | **Angenommen** | AC9 + T6 ergänzt, C4 Commit, Datei in §3 aufgenommen |
| 2 | 🟠 Risiko | Zeilennummern können sich verschieben | **Angenommen** | §3 mit „ungefähr"-Hinweis + Grep-Anker-Spalte |
| 3 | 🟡 Verb. | AC1 unklar bei „historische Kommentare" | **Angenommen** | AC1 präzisiert: nur `#`-Doku-Kommentare OK, kein auskommentierter Code/TODO |
| 4 | ⚪ Hinweis | AC8 Smoke-Test ohne Checkliste | **Angenommen** | AC8 + §6 Smoke-Test-Checkliste mit 8 Punkten |
| 5 | ⚪ Hinweis | T1-T5 starr bei künftigen Features | **Akzeptiert mit Doku** | KISS-Akzeptanz + Doku-Kommentar im Test-Header |

Halluzinations-Rate V4-pro: **0/5** (alle Findings verifizierbar — F1
besonders stark, Datei core/auto_hunt.py im V2 komplett vergessen).

**V4-pro 5-Cycle-Bilanz:** Bundle I (5) + J (7) + P51 (9) + P53 (4) +
P55 (5) = **30 Findings, 0 Halluzinationen, 100% verifizierbar.**
