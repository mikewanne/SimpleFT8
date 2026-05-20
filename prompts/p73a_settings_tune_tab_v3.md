# P73-A — Settings-UX TUNE-Einstellungen konsolidieren (V3)

## 1. Ziel

TUNE-bezogene Settings unter einer visuell klaren Gruppe zusammenfassen.
Heute auf 2 Tabs verteilt — User muss zwischen ihnen springen.

**Lösung (KISS):** `QGroupBox` „TUNE-Einstellungen" innerhalb Tab
„TX & Schutz" (analog bestehende RF-Presets-GroupBox dort). Kein
neuer Tab — Tab-Anzahl bleibt 4.

**Bonus aus R1-F1 (UX-Touch):** Wenn „Antennen-Tuner verwenden"
unchecked ist, werden die drei abhängigen TUNE-Widgets (TUNE-Dauer,
Tune-Leistung, Auto-TUNE-Checkbox) disabled — visuelle Signalisierung
dass sie ohne Tuner sinnlos sind.

## 2. Akzeptanzkriterien

- **AC1** Im Tab „TX & Schutz" gibt es eine neue `QGroupBox` mit
  exaktem Titel „TUNE-Einstellungen", die folgende Widgets in dieser
  Reihenfolge enthält (eingebettetes `QFormLayout`):
  1. „Antennen-Tuner verwenden" (`tuner_present_cb`, Checkbox) —
     Master-Switch
  2. „TUNE-Dauer" (`tune_duration_combo`, ComboBox)
  3. „Tune-Leistung" (Button-Row 5/10/20 W + Info-Btn)
  4. „Auto-TUNE bei Bandwechsel" (`auto_tune_band_cb`, Checkbox)
- **AC2** Im `_build_tab_ft8`-Body wird kein `form.addRow(...)`-Aufruf
  für `tuner_present_cb` / `tune_duration_combo` / `auto_tune_band_cb`
  mehr ausgeführt. Die Widget-**Instanziierung** wandert komplett in
  `_build_tab_tx`-Body (KEINE „Verschiebung" zur Laufzeit — Widgets
  werden im neuen Eltern-Layout neu instanziiert, alte Instanziierung
  raus aus `_build_tab_ft8`). (R1-F6 präzisiert)
- **AC3** Im `_build_tab_tx`-Body wird die alte Inline-Tune-Leistung-
  Zeile aus der Hauptform entfernt (Z.240-258) — die Buttons
  `_tune_btns[5/10/20]` werden in der GroupBox neu erstellt,
  `self._tune_btns`-Dict + `self._current_tune_power` werden dort
  belegt. Heutige Aufrufer (`_on_tune_power_clicked`,
  `_set_tune_power_buttons`, `_reset_to_defaults`) bleiben unverändert.
- **AC4** SWR-Limit (`swr_limit`-ComboBox) bleibt **unverändert** in
  der TX-Schutz-Hauptform — nicht in der TUNE-GroupBox.
- **AC5** Settings-Keys + Save/Load-Logik unverändert: `tuner_present`,
  `tune_duration_s`, `auto_tune_band_change`, `tune_power`. Reine
  UI-Reorganisation, KEIN Settings-Format-Change.
- **AC6** Reset-Defaults-Pfade funktionieren unverändert (greifen auf
  Instanz-Variablen, kein Layout-Bezug).
- **AC7** GroupBox-Style wird automatisch vom Dialog-Hauptstylesheet
  übernommen (`ui/settings_dialog.py:118-122`: Cyan-Header `#00AAFF`,
  Border, Padding). Keine eigene Style-Konstante nötig. (R1-F4)
- **AC8** Widget-Instanz-Variablen (`self.tuner_present_cb`,
  `self.tune_duration_combo`, `self.auto_tune_band_cb`,
  `self._tune_btns`, `self._current_tune_power`) bleiben unter
  gleichem Namen erreichbar.
- **AC9** Tuner-Master-Switch-Logik (R1-F1):
  `tuner_present_cb.toggled.connect(...)` triggert eine Helper-Methode
  `_update_tune_widgets_enabled(checked)` die `tune_duration_combo`,
  `_tune_btns`-Items und `auto_tune_band_cb` `setEnabled(checked)` setzt.
  Bei Dialog-Init wird die Helper-Methode einmal aufgerufen mit dem
  geladenen `tuner_present`-Wert (`_load_from_settings`).

## 3. Betroffene Module/Dateien

- `ui/settings_dialog.py`:
  - `_build_tab_tx`: ~30 LOC neue GroupBox-Sektion + Master-Switch-
    Verkabelung. Alte Inline-Tune-Leistung-Zeile aus Hauptform raus.
  - `_build_tab_ft8`: ~18 LOC raus (3 Widget-Erzeugungen + addRow-
    Aufrufe). Bandpilot + alles andere unverändert.
  - Neue Helper-Methode `_update_tune_widgets_enabled(checked)`.
- `tests/test_p73a_settings_tune_groupbox.py` — NEU mit 7 Tests.
- `main.py` — `APP_VERSION` 0.97.63 → 0.97.64.
- `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` — Standard-Update.

## 4. Randbedingungen

- **Threading:** GUI-only.
- **Hardware:** Keine TX-Hardware berührt.
- **Settings-Schema:** Migration nicht nötig.
- **i18n:** Deutsch, „TUNE-Einstellungen" konsistent.
- **Widget-Lifecycle:** Instanz-Vars werden im neuen Eltern-Layout
  erzeugt, kein Re-Parent zur Laufzeit.
- **Tooltips:** Wortwörtlich beibehalten.
- **`tune_row` (QHBoxLayout):** wird in der GroupBox-QFormLayout-Zeile
  als Composite eingehängt (analog heutige Inline-Konstruktion).

## 5. Nicht im Scope

- **SWR-Limit verschieben.**
- **Settings-Format-Migration.**
- **Neuer Tab „TUNE".**
- **Tooltip-Änderungen.**
- **Reorganisation Bandpilot.**
- **RF-Presets-Tabelle.**
- **Sendeleistung / TX Audio-Pegel / Anrufversuche** verschieben.

## 6. Testbarkeit

`tests/test_p73a_settings_tune_groupbox.py` NEU:

**Mock-Setup:**
```python
@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def _mock_settings():
    s = MagicMock()
    s.get = MagicMock(side_effect=lambda k, d=None: d)
    s.set = MagicMock()
    return s

def _new_dialog(app):
    from ui.settings_dialog import SettingsDialog
    return SettingsDialog(_mock_settings(), parent=None)
```

- **T1** `test_tune_groupbox_exists_with_correct_title`
  `dialog.findChildren(QGroupBox)` → mind. eine hat Titel
  „TUNE-Einstellungen".
- **T2** `test_tune_widgets_in_tune_groupbox_via_findchild` (R1-F2)
  Aus der TUNE-GroupBox `findChildren(QWidget)` rekursiv: enthält
  `tuner_present_cb`, `tune_duration_combo`, `auto_tune_band_cb`
  (Identitätsprüfung `is dialog.tuner_present_cb` etc.).
- **T3** `test_tune_power_buttons_in_tune_groupbox`
  GroupBox `findChildren(QPushButton)` enthält alle 3 Buttons aus
  `dialog._tune_btns.values()` (Identitätsprüfung).
- **T4** `test_swr_limit_not_in_tune_groupbox` (R1-F7 vereinfacht)
  GroupBox `findChildren(QComboBox)` enthält NICHT
  `dialog.swr_limit`. (Position in Hauptform wird NICHT geprüft.)
- **T5** `test_settings_save_load_unchanged_for_tune_keys`
  Save-Load-Cycle für `tuner_present`, `tune_duration_s`,
  `auto_tune_band_change`, `tune_power`.
- **T6** `test_reset_defaults_resets_tune_widgets`
  Werte ändern → `_reset_to_defaults` → Defaults wiederhergestellt
  (`tuner_present=True`, `tune_duration_s=15`).
- **T7** `test_tuner_master_switch_disables_dependent_widgets` (R1-F1)
  Setze `tuner_present_cb.setChecked(False)`. Erwartung:
  `tune_duration_combo.isEnabled() == False`,
  `auto_tune_band_cb.isEnabled() == False`,
  alle `_tune_btns`-Buttons `isEnabled() == False`. Dann
  `setChecked(True)` → alle wieder enabled.

## 7. KISS-Bewertung

- **Code-Diff:** ~50 LOC (45 Layout-Reorganisation + 5 Master-Switch-
  Helper).
- **Komplexität:** klein. Layout-Reorganisation + 1 Helper-Methode.
- **Risiko:** klein. Settings-Schema unverändert. Master-Switch ist
  Bonus, kein Pflicht-Pfad.
- **Variante neuer Tab „TUNE":** weiter verworfen.

## R1-Findings Bilanz

| Schwere | Finding | Status |
|---|---|---|
| 🟠 F1 | Tuner-Checkbox disabled abhängige Widgets | ✅ AC9 + T7 |
| 🟠 F2 | T2 voraussetzt direkte Kinder | ✅ T2 mit `findChildren` rekursiv |
| 🟠 F3 | T3-T5 Code-Inspection-Fragilität | ✅ Layout-Walk via `findChildren`, Code-Inspection raus |
| 🟡 F4 | `_GROUPBOX_STYLE` Konstante existiert nicht | ✅ AC7 korrigiert, GroupBox-Style aus Dialog-Hauptstylesheet |
| 🟡 F5 | Widget-Reihenfolge | ✅ Verbindlich in AC1: Tuner→Dauer→Leistung→AutoTUNE |
| 🟡 F6 | AC3 mehrdeutig „neu instanziiert" | ✅ AC2+AC3 präzisiert |
| 🟠 F7 | T5 Position-Test fragil | ✅ T4 vereinfacht: nur Ausschluss von GroupBox |
| ⚪ F8 | Overengineering-Frage | ❌ Mike-Wunsch in TODO explizit dokumentiert |
