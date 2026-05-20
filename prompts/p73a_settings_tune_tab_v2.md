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

# P73-A — Settings-UX TUNE-Einstellungen konsolidieren (V2)

## 1. Ziel

TUNE-bezogene Settings unter einer visuell klaren Gruppe zusammenfassen.
Heute verteilt auf 2 Tabs:
- **„TX & Schutz":** Tune-Leistung (5/10/20 W Buttons,
  `_build_tab_tx` Z.240-258)
- **„FT8 & Diversity":** Tuner-Checkbox (`tuner_present_cb` Z.324),
  TUNE-Dauer (`tune_duration_combo` Z.331), Auto-TUNE-bei-Bandwechsel
  (`auto_tune_band_cb` Z.344)

→ User muss zwischen Tabs springen um alle TUNE-Aspekte einzustellen.

**Lösung (KISS):** `QGroupBox` „TUNE-Einstellungen" innerhalb Tab
„TX & Schutz" (analog bestehende RF-Presets-GroupBox dort). Kein
neuer Tab — bleibt bei 4 Tabs total. Tab-Anzahl-Konstanz schlägt
visuelle Mehr-Tab-Hierarchie (Mike-UX-Prinzip Hobby-Tool).

## 2. Akzeptanzkriterien

- **AC1** Im Tab „TX & Schutz" gibt es eine neue `QGroupBox` mit
  exaktem Titel „TUNE-Einstellungen", die folgende Widgets in dieser
  Reihenfolge enthält (eingebettetes `QFormLayout` analog
  `_build_tab_tx`-Hauptform):
  1. „Antennen-Tuner verwenden" (`tuner_present_cb`, Checkbox)
  2. „TUNE-Dauer" (`tune_duration_combo`, ComboBox)
  3. „Tune-Leistung" (Button-Row 5/10/20 W mit Info-Btn)
  4. „Auto-TUNE bei Bandwechsel" (`auto_tune_band_cb`, Checkbox)
- **AC2** Im `_build_tab_ft8`-Body wird kein `form.addRow(...)`-Aufruf
  für `tuner_present_cb` / `tune_duration_combo` / `auto_tune_band_cb`
  mehr ausgeführt. Die Widget-Erstellung wandert komplett in
  `_build_tab_tx`.
- **AC3** Im `_build_tab_tx`-Body wird die alte Inline-Tune-Leistung-
  Zeile entfernt (Z.240-258 alte Position) und die ganze Logik
  (Buttons + `_tune_btns`-Dict + `_current_tune_power`) innerhalb der
  GroupBox neu instanziiert.
- **AC4** SWR-Limit (`swr_limit`-ComboBox) bleibt **unverändert** in
  der TX-Schutz-Hauptform — nicht in der TUNE-GroupBox.
- **AC5** Settings-Keys + Save/Load-Logik unverändert: `tuner_present`,
  `tune_duration_s`, `auto_tune_band_change`, `tune_power`. Reine
  UI-Reorganisation, KEIN Settings-Format-Change.
- **AC6** Reset-Defaults-Pfade (`_reset_to_defaults`-Methode + alle
  per-Widget-Defaults) funktionieren unverändert.
- **AC7** GroupBox-Style folgt bestehendem Pattern aus
  `_GROUPBOX_STYLE` (Cyan-Header `#00AAFF`, dunkler BG `#16192b`).
- **AC8** Widget-Instanz-Variablen (`self.tuner_present_cb`,
  `self.tune_duration_combo`, `self.auto_tune_band_cb`,
  `self._tune_btns`, `self._current_tune_power`) bleiben unter
  gleichem Namen erreichbar — sonst brechen save/load/reset.

## 3. Betroffene Module/Dateien

- `ui/settings_dialog.py`:
  - `_build_tab_tx`: ~25 LOC neue GroupBox-Sektion mit eingebettetem
    QFormLayout für die 4 TUNE-Widgets. Alte Inline-Tune-Leistung-
    Zeile aus Hauptform entfernen.
  - `_build_tab_ft8`: ~18 LOC raus (Widget-Instantiierung + addRow für
    3 Widgets). Bandpilot-Sektion + alles andere unverändert.
- `tests/test_p73a_settings_tune_groupbox.py` — NEU mit 5-6 Tests.
- `main.py` — `APP_VERSION` 0.97.63 → 0.97.64.
- `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` — Standard-Update.

## 4. Randbedingungen

- **Threading:** GUI-only, Settings-Dialog im GUI-Thread.
- **Hardware:** Keine TX-Hardware berührt. Reine UI-Reorg.
- **Settings-Schema:** Migration nicht nötig (Keys identisch).
- **i18n:** Deutsch. „TUNE-Einstellungen" konsistent mit „TX & Schutz".
- **Widget-Lifecycle:** Widgets werden im neuen Eltern-Layout
  instanziiert, nicht „verschoben". Damit keine Re-Parent-Issues.
- **Bestehende Aufrufer:** `_reset_to_defaults`-Methode greift auf
  Instanz-Variablen — Layout-Wechsel hat keinen Effekt.
- **Tooltips:** Wortwörtlich beibehalten (eingespielt mit Mike).
- **`tune_row` (QHBoxLayout):** wird Bestandteil der GroupBox-
  QFormLayout-Zeile. Buttons + Info-Btn + Stretch wie heute.

## 5. Nicht im Scope

- **SWR-Limit verschieben** — bleibt in TX-Schutz-Hauptform.
- **Settings-Format-Migration** — keine Keys umbenannt.
- **Neuer Tab „TUNE"** — verworfen zugunsten der GroupBox (KISS,
  Tab-Anzahl-Konstanz).
- **Tooltip-Änderungen**.
- **Reorganisation Bandpilot** — bleibt in „FT8 & Diversity".
- **RF-Presets-Tabelle** — bleibt unter eigener GroupBox in
  „TX & Schutz" wie heute.
- **Sendeleistung (allg.) / TX Audio-Pegel / Anrufversuche** verschieben
  — bleiben in TX-Schutz-Hauptform.

## 6. Testbarkeit

`tests/test_p73a_settings_tune_groupbox.py` NEU:

**Setup:**
```python
from PySide6.QtWidgets import QApplication, QGroupBox, QFormLayout
from ui.settings_dialog import SettingsDialog

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def _new_dialog(app, settings_obj=None):
    settings = settings_obj or _mock_settings()
    return SettingsDialog(settings, parent=None)
```

- **T1** `test_tune_groupbox_exists_with_correct_title`
  Suche alle `QGroupBox`-Children → mindestens eine hat Titel
  „TUNE-Einstellungen".
- **T2** `test_tune_widgets_are_children_of_tune_groupbox`
  Die GroupBox aus T1 enthält als Child-Widgets:
  `tuner_present_cb`, `tune_duration_combo`, `auto_tune_band_cb`,
  und mindestens 3 QPushButton-Children mit Text "5W"/"10W"/"20W".
- **T3** `test_ft8_tab_no_longer_contains_tune_widgets`
  Code-Inspection-Test: `_build_tab_ft8`-Source enthält keinen
  `addRow`-Aufruf mit `tuner_present_cb`, `tune_duration_combo`
  oder `auto_tune_band_cb`. (Sichert AC2 ohne Layout-Walken.)
- **T4** `test_tx_tab_main_form_no_longer_contains_tune_power`
  Code-Inspection: `_build_tab_tx`-Source enthält
  `tune-leistung`-addRow NICHT mehr in der Haupt-Form, sondern nur
  in der GroupBox-Sektion (per String-Suche zwischen GroupBox-
  Konstruktor-Aufruf und `layout.addWidget(group)`).
- **T5** `test_swr_limit_remains_in_main_form`
  Code-Inspection: SWR-Limit-addRow steht VOR der TUNE-GroupBox-
  Konstruktion (= TX-Schutz-Hauptform).
- **T6** `test_settings_save_load_unchanged_for_tune_keys`
  Save-Load-Cycle für `tuner_present`, `tune_duration_s`,
  `auto_tune_band_change`, `tune_power`. Werte identisch nach Roundtrip.
- **T7** `test_reset_defaults_resets_tune_widgets`
  Werte ändern → `_reset_to_defaults` → Defaults wieder gesetzt
  (`tuner_present=True`, `tune_duration_s=15`, `tune_power=10`).

## 7. KISS-Bewertung

- **Code-Diff:** ~45 LOC verschoben (Widget-Instantiierung von
  `_build_tab_ft8` nach `_build_tab_tx` in eine neue GroupBox).
- **Komplexität:** keine — pure Layout-Reorganisation.
- **Risiko:** klein. Settings-Schema unverändert, alle Instanz-Vars
  bleiben gleich.
- **Variante neuer Tab „TUNE":** verworfen. 4 Tabs sind Mike-getestet,
  Tab-Wechsel-Overhead bei 5 Tabs unverhältnismäßig.

## Was prüfen

1. Reihenfolge der 4 Widgets in der GroupBox — Tuner-Checkbox an
   1. Stelle gut? Oder eher TUNE-Dauer zuerst weil häufiger geändert?
2. Sollte „Antennen-Tuner verwenden"-Checkbox visuell die anderen
   3 Widgets disablen wenn unchecked? (Heute sind sie immer enabled.)
3. Test-Strategie: Layout-Walk vs Code-Inspection (T3+T4+T5).
   Layout-Walk ist robuster gegen Refactoring, aber komplexer.
   Code-Inspection ist KISS aber fragil bei Whitespace-Änderungen.
4. Gibt es einen Edge-Case wenn beim Dialog-Reopen die Widgets
   re-instanziiert werden — bricht da was?
5. Bandpilot bleibt in „FT8 & Diversity" — sollte er nicht eher zu
   TUNE wandern weil er auch TX-bezogen entscheidet? (Mike-Spec klar
   nein, aber als R1-Frage erlaubt.)
6. KISS-Sicht: lohnt sich die GroupBox überhaupt, oder ist die heutige
   2-Tab-Verteilung doch okay weil Mike die Settings einmal einstellt
   und nie wieder anfasst?
