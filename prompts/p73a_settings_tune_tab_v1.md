# P73-A — Settings-UX TUNE-Einstellungen konsolidieren (V1)

## 1. Ziel

TUNE-bezogene Settings unter einer visuell klaren Gruppe zusammenfassen.
Heute verteilt auf 2 Tabs:
- **„TX & Schutz":** Tune-Leistung (5/10/20 W Buttons, Z.240-258)
- **„FT8 & Diversity":** Tuner-Checkbox (Z.324), TUNE-Dauer (Z.331),
  Auto-TUNE-bei-Bandwechsel (Z.344)

→ User muss zwischen Tabs springen um alle TUNE-Aspekte einzustellen.

**Lösungs-Wahl (KISS):** `QGroupBox` „TUNE-Einstellungen" innerhalb
Tab „TX & Schutz" (analog bestehende RF-Presets-GroupBox dort).
Kein neuer Tab — bleibt bei 4 Tabs total.

## 2. Akzeptanzkriterien

- **AC1** Im Tab „TX & Schutz" gibt es eine neue `QGroupBox` mit Titel
  „TUNE-Einstellungen", die folgende Widgets in dieser Reihenfolge
  enthält:
  1. „Antennen-Tuner verwenden" (Checkbox)
  2. „TUNE-Dauer" (5/10/15 s ComboBox)
  3. „Tune-Leistung" (5/10/20 W Button-Row)
  4. „Auto-TUNE bei Bandwechsel" (Checkbox)
- **AC2** Im Tab „FT8 & Diversity" entfallen genau diese 3 Widgets
  (Tuner-Checkbox, TUNE-Dauer, Auto-TUNE-Checkbox). Bandpilot bleibt
  unverändert in „FT8 & Diversity".
- **AC3** Im Tab „TX & Schutz" entfällt die alte „Tune-Leistung"-
  Zeile aus der Haupt-`QFormLayout` — sie wird in die GroupBox
  verschoben.
- **AC4** SWR-Limit bleibt unverändert in der Haupt-Form von
  „TX & Schutz" (gehört konzeptionell zu TX-Schutz, nicht nur TUNE).
- **AC5** Settings-Keys + Save/Load-Logik unverändert: `tuner_present`,
  `tune_duration_s`, `auto_tune_band_change`, `tune_power` —
  reine UI-Umordnung, kein Settings-Format-Change.
- **AC6** Reset-Defaults-Pfade (`_reset_to_defaults`) funktionieren
  unverändert (Buttons sind in derselben Class-Instanz erreichbar).
- **AC7** GroupBox-Style folgt bestehendem Pattern aus
  `_TAB_STYLE`/`_GROUPBOX_STYLE` (Cyan-Header, dunkler BG).

## 3. Betroffene Module/Dateien

- `ui/settings_dialog.py` —
  - `_build_tab_tx`: TUNE-GroupBox neu, Tune-Leistung dorthin
    verschieben.
  - `_build_tab_ft8`: 3 Widgets raus (Tuner-Checkbox, TUNE-Dauer,
    Auto-TUNE).
- `tests/test_p73a_settings_tune_groupbox.py` — NEU, 4-6 Tests.
- `main.py` `APP_VERSION` 0.97.63 → 0.97.64.
- HISTORY/HANDOFF/CLAUDE/TODO Standard-Update.

## 4. Randbedingungen

- **Threading:** GUI-only, Settings-Dialog läuft im GUI-Thread.
- **Hardware:** Keine TX-Hardware berührt. Reine UI-Reorganisation.
- **Backward-Compat:** Settings-Keys bleiben — Migration nicht nötig.
- **i18n:** Deutsch, "TUNE-Einstellungen" konsistent mit „TX & Schutz".
- **Widget-Lifecycle:** Die `QFormLayout.addRow`-Reihenfolge in
  `_build_tab_tx` muss korrekt sein; GroupBox wird via
  `layout.addWidget(group_box)` vor den RF-Presets eingefügt.
- **`_tune_btns` / `_current_tune_power` Instanz-Variablen:** Wenn
  Tune-Leistung in die GroupBox wandert, müssen diese Attribute weiter
  korrekt initialisiert werden — sie sind heute Instanz-Vars von
  `SettingsDialog`, nicht vom Layout. Wechsel des Eltern-Layouts ist
  unkritisch.

## 5. Nicht im Scope

- **SWR-Limit verschieben** — bleibt unter TX & Schutz (gehört zur
  TX-Sicherheit, nicht nur TUNE).
- **Settings-Format-Migration** — keine Keys umbenannt.
- **Neuer Tab „TUNE"** — verworfen zugunsten der GroupBox-Variante
  (KISS, weniger Tab-Wechsel-Overhead für User).
- **Tooltip-Änderungen** an verschobenen Widgets — Texte bleiben
  wortwörtlich.
- **Reorganisation Bandpilot** — bleibt unter FT8 & Diversity.

## 6. Testbarkeit

`tests/test_p73a_settings_tune_groupbox.py` NEU:

- **T1** `test_tune_groupbox_exists_in_tx_tab`
  Dialog instanziieren, alle GroupBoxes im 2. Tab durchgehen, eine
  muss Titel „TUNE-Einstellungen" haben.
- **T2** `test_tune_widgets_moved_out_of_ft8_tab`
  Im Tab „FT8 & Diversity" prüfen dass die 3 Widgets
  (`tuner_present_cb`, `tune_duration_combo`, `auto_tune_band_cb`)
  NICHT mehr im Layout des Tabs sind. (Existieren noch als Instanz-
  Variablen — nur die Layout-Zugehörigkeit ändert sich.)
- **T3** `test_tune_widgets_in_groupbox`
  Die 3 Widgets sind Kinder der TUNE-GroupBox.
- **T4** `test_tune_power_buttons_in_groupbox`
  `_tune_btns[5]`, `_tune_btns[10]`, `_tune_btns[20]` sind Kinder der
  TUNE-GroupBox.
- **T5** `test_swr_limit_stays_in_tx_tab_main_form`
  SWR-Limit-ComboBox liegt NICHT in der TUNE-GroupBox (sondern in der
  TX-Schutz-Hauptform).
- **T6** `test_settings_keys_unchanged`
  Save-Load-Cycle: setze Werte, save, neuer Dialog, load → Werte
  identisch. Sichert Settings-Schema unverändert.

## 7. KISS-Bewertung

- **Code-Diff:** ~30 LOC verschoben (Widget-Instantiierung von
  `_build_tab_ft8` nach `_build_tab_tx` in eine neue GroupBox).
- **Komplexität:** keine — pure Layout-Reorganisation.
- **Risiko:** klein. Widget-Instanz-Variablen werden in derselben
  Class-Instanz erstellt, nur Eltern-Layout ändert sich. Save/Load
  greift auf Instanz-Vars zu, nicht auf Layout.
