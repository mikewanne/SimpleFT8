# P55 — Easter-Egg + Diversity-CQ-Code-Leichen entfernen — V1

## 1. Ziel

Easter-Egg-Funktion und obsolete `_omni_active`-Doppel-Logik in `btn_cq`
komplett entfernen. **Frequenzwahl-Logik bleibt unverändert.** Mike's
Spec 15.05.: „In Diversity soll es nur OMNI CQ geben, keinen normalen
CQ auch nicht versteckt. Es gibt auch keine Easter-Egg-Funktion mehr."

**Was heute schon korrekt ist:**
- `btn_cq` ist in Diversity bereits hidden (`main_window.py:789`
  `setHidden(is_diversity)`).
- Button-Sichtbarkeit-Routing via `_update_button_visibility`
  (`main_window.py:773`) funktioniert nominell richtig.

**Was Leiche ist (greift nie weil hidden):**
- `_omni_active`-Flag in `ControlPanel` (`control_panel.py:1343+1674`).
- `btn_cq.setText("OMNI CQ ■")`-Branch in `_on_cq_clicked` + 
  `set_cq_active` (Z.1811-1816 + 1827-1830).
- Easter-Egg-Override-Branch in `_update_button_visibility`
  (`main_window.py:785` `show_power_buttons = is_diversity or
  self._easter_egg_active`).
- `_easter_egg_active`-Variable + `_on_easter_egg_toggle` (`main_window.py:
  333+746-769`).
- `easter_egg_toggle_clicked`-Signal + Version-Click-Handler
  (`control_panel.py:1197+1356`).
- `mw_radio.py` 5× `hasattr(self, "_easter_egg_active")`-Checks
  (Z.565+657+858+1164+1750).
- Test-Mock-Stellen 3× (`test_bundle_i.py:84`,
  `test_omni_cq_integration.py:135`, `test_auto_hunt_extended.py:81+115`).

## 2. Akzeptanzkriterien

| # | Kriterium | Verifikation |
|---|---|---|
| AC1 | `grep -rn easter_egg ui/ core/ radio/` findet **0** Treffer (außer Doku-Kommentare die Historie erwähnen) | grep |
| AC2 | `grep -n _omni_active ui/control_panel.py` findet **0** Treffer | grep |
| AC3 | `grep -n "btn_cq.setText.*OMNI" ui/` findet **0** Treffer | grep |
| AC4 | `_update_button_visibility` ist simpel: Normal → btn_cq sichtbar + OMNI+Hunt hidden; Diversity → btn_cq hidden + OMNI+Hunt sichtbar. **Keine** Override-Variable mehr | Source-Test |
| AC5 | Version-Label hat keinen Click-Handler mehr (`mousePressEvent`-Override raus, `setCursor` bleibt nicht — Cursor zurück auf default) | Source-Test |
| AC6 | `easter_egg_toggle_clicked`-Signal in `ControlPanel` raus | grep |
| AC7 | `auto_hunt.stop_auto_hunt("easter_egg_off")` und `omni_cq.stop("easter_egg_off")` Reason-Strings sind weg — ersetzt durch eindeutigeren Reason wenn nötig (z.B. `mode_change`) | grep |
| AC8 | App startet sauber, Normal/Diversity-Wechsel funktioniert wie gehabt | Smoke-Test |
| AC9 | OMNI-CQ + AUTO HUNT in Diversity weiter aktiv (kein Regress) | Tests grün |
| AC10 | Tests grün 1258 → 1258 (Mock-Anpassungen, Netto ±0) | pytest |

## 3. Betroffene Module/Dateien

| Datei | Was raus | Zeilen |
|---|---|---|
| `ui/main_window.py` | `_easter_egg_active` Init + `_on_easter_egg_toggle` + Signal-Connect + Override-Branch in `_update_button_visibility` | 324, 333, 746-769, 785 |
| `ui/control_panel.py` | `_omni_active`-Flag + `btn_cq`-OMNI-Label-Branch + `easter_egg_toggle_clicked`-Signal + Version-Label-Click-Handler | 1197, 1343, 1356, 1674, 1811-1816, 1827-1830 |
| `ui/mw_radio.py` | 5× `hasattr(self, "_easter_egg_active"): self._easter_egg_active = False` Reset-Lines | 565, 657, 858, 1164, 1750 |
| `tests/test_bundle_i.py` | Mock `_easter_egg_active = True` raus | 84 |
| `tests/test_omni_cq_integration.py` | Mock `_easter_egg_active = False` raus | 135 |
| `tests/test_auto_hunt_extended.py` | `"easter_egg_off"`-Reason-String aus Test-Parametern (oder umbenennen wenn neuer Reason eingeführt wird) | 81, 115 |

## 4. Randbedingungen

### Was bleibt
- `btn_cq` in **Normal** weiterhin „CQ RUFEN" — normaler manueller CQ.
- `btn_omni_cq` + `btn_auto_hunt` in **Diversity** weiterhin sichtbar.
- Frequenz-Such-Logik 60s in Diversity (`core/diversity.py`) **unverändert**.
- Sticky-Logik, Suchbereich-Algorithmus, alles unverändert.

### auto_hunt + omni_cq Stop-Reasons
- `_on_easter_egg_toggle` rief `_auto_hunt.stop_auto_hunt("easter_egg_off")`
  und `_omni_cq.stop("easter_egg_off")` wenn Override zurückgenommen wurde.
- Wenn Easter-Egg komplett weg, fällt dieser Code-Pfad weg.
- Es gibt im RX-Mode-Wechsel-Pfad bereits ähnliche Stops mit Reasons
  `rx_mode_change` (`mw_radio.py:545+547`). Reicht.
- `"easter_egg_off"`-Reason-String dann nirgendwo mehr produziert →
  Test-Anpassung sicher.

### Hardware-Pflicht (CLAUDE.md)
Nicht TX-relevant. Pure UI-/State-Cleanup, kein Antennen-Pfad berührt.
Keine `set_tx_antenna`-Änderung.

### Versionsnummer-Label
- Heute: hat `PointingHandCursor` + `mousePressEvent`-Override.
- Nach Cleanup: nur Anzeige-Label, kein Click, default Cursor. 
- Verändert sich Optisch leicht (kein Pointer-Cursor mehr bei Hover).

## 5. Nicht im Scope

- **Frequenz-Such-Logik ändern** — Mike-Spec explizit „bleibt wie gehabt".
- **OMNI-CQ-Logik selbst ändern** — nur Easter-Egg-Eingangstor raus.
- **AUTO HUNT** verändern.
- **Architektur-Refactoring** über das Aufräumen hinaus.

## 6. Testbarkeit

- Bestehende Tests sind die Sicherung. Drei Test-Files brauchen
  Mock-Anpassung — die testen aber kein Easter-Egg-Verhalten direkt
  (sie setzen den State nur, weil er heute existiert). Nach Cleanup
  entfällt das Setzen, Tests funktionieren weiter mit den jeweiligen
  Stop-Reasons.
- Neuer Test `tests/test_p55_easter_egg_removed.py` mit 4-5 Source-
  Level-Assertions:
  - T1: `easter_egg` als Wort kommt in `ui/`, `core/`, `radio/` nicht mehr
    vor (außer im historischen Kommentar wenn nötig)
  - T2: `ControlPanel` hat kein `_omni_active`-Attribut
  - T3: `_update_button_visibility` enthält keinen `_easter_egg_active`-
    Branch (grep auf Source)
  - T4: Version-Label hat keinen `mousePressEvent`-Override (Source-grep
    auf `_version_label.mousePressEvent`)
  - T5: `easter_egg_toggle_clicked` als Signal in ControlPanel raus

## Self-Review-Notizen (V1 → V2 pending)

- ✓ Hardware-Pflicht nicht relevant (UI-only)
- ✓ Frequenz-Such-Logik explizit „bleibt" markiert
- ✓ Tests-Anpassung dokumentiert
- ? Versions-Label-Cursor: kosmetische Änderung — soll bleiben (z.B. nur
  Anzeige) oder ganz neutralisiert (default Cursor)?
- ? Was passiert mit dem hidden `btn_omni_cq` wenn Easter-Egg weg ist?
  Antwort: Wird in Diversity via `_update_button_visibility` sichtbar,
  in Normal hidden — Mechanik bleibt, nur Override-Pfad weg.
- ? Stop-Reason `easter_egg_off` für `_auto_hunt`/`_omni_cq`: muss
  Code-Pfad weg, kein Replace nötig weil mode_change-Pfad eh schon
  bei rx_mode-Wechsel feuert.
- ? Reihenfolge: Test-Anpassung VOR Code-Änderung machen damit Tests
  bei Code-Removal sofort grün bleiben.
