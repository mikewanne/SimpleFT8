# Prompt V2 — Settings-Dialog auf Tabs

## Rolle (DeepSeek-Anweisung)

Du bist Senior Python-Entwickler mit Schwerpunkt Amateurfunk-Software und
PySide6 (NICHT PyQt5 — wir nutzen PySide6, Signal/Slot statt pyqtSignal/
pyqtSlot). Deine Aufgabe ist es, diesen Prompt zu kritisieren — NICHT
das Problem zu loesen. Erstelle eine strukturierte Liste mit: Luecken,
fehlenden Informationen, Unklarheiten, Widerspruechen, Verbesserungs-
vorschlaegen und offenen Fragen. Bedenke: SimpleFT8 ist ein Hobby-
Projekt (kein kommerzielles Produkt) — Overengineering ist selbst ein
Fehler den du benennen sollst. KISS schlaegt Eleganz.

## Kontext: Projektphilosophie

- Hobby-Funker-Tool, KEIN Contest-Tool. Zielgruppe: einzelner Operator
  (Mike, DA1MHH).
- Display: 1440×900 (MacBook). Verfuegbare Hoehe nach macOS-Menubar
  (25 px), Titel (28 px), Dock (80 px) ≈ 767 px netto.
- Visueller Stil: dunkles Theme (`#1a1a2e` Background, `#00AAFF` Akzent),
  modern/Neon — KEIN macOS-Default-Grau.
- Hardware-Pflicht: ANT1 = TX, ANT2 = RX-only. Hier irrelevant da rein
  UI-Refactor (kein TX-Pfad beruehrt).

## Ziel

Den `ui/settings_dialog.py` (`SettingsDialog`-Klasse) von einer monolithisch
gestapelten Form (6 GroupBoxen vertikal) auf eine `QTabWidget`-Struktur
umstellen, sodass der Dialog auf 1440×900 vollstaendig sichtbar ist und
nicht aus dem Bildschirm herausragt. Funktional unveraendert.
Save-Persistenz unveraendert.

## Akzeptanzkriterien

1. **Sichtbarkeit:** Dialog erscheint mit `setMaximumHeight(750)` und
   `setMinimumHeight(560)`. `setMinimumWidth(720)`. Default-Groesse beim
   Oeffnen ≤ 750×800 px (Qt rechnet Hoehe automatisch).

2. **Vier Tabs (Default-Vorschlag):**
   - **Tab 1 „Station"**: Rufzeichen, Locator, IP-Adresse, Sprache (4 Felder).
   - **Tab 2 „TX & Schutz"**: Sendeleistung, TX-Audio-Pegel, Anrufversuche,
     SWR-Limit, Tune-Leistung (5w/10w/20w-Buttons), RF-Presets-Tabelle inkl.
     „Band loeschen" + „Alle loeschen" (insgesamt 5 Form-Rows + Tabelle
     ~140 px + Button-Row).
   - **Tab 3 „FT8 & Diversity"**: TX-Audio-Frequenz, Max-Decode-Frequenz,
     Neueinmessung-Zyklen, Statistik-Erfassung-Checkbox (4 Felder).
   - **Tab 4 „Daten & Tools"**: CSV-Export-Button + Beschreibung, Richtungs-
     Karte oeffnen + Beschreibung, Debug-Konsole-Checkbox (3 Bloecke).
   - **Alternative 3-Tab-Variante** (falls 4 Tabs zu viel): Station, TX &
     Schutz (mit RF-Presets), FT8 & Tools (alles uebrige). Ich (Claude)
     entscheide nach Hoehen-Pruefung der Mockup-Werte; dokumentiere die
     Entscheidung im Commit.

3. **Tab-Header-Styling:** Tab-Bar in Theme-Farben, nicht macOS-Grau.
   Konkretes Stylesheet:
   ```css
   QTabWidget::pane { border: 1px solid #333; background: #1a1a2e; }
   QTabBar::tab {
       background: #222; color: #888;
       padding: 8px 16px; border: 1px solid #333;
       border-bottom: none;
       border-top-left-radius: 4px; border-top-right-radius: 4px;
       margin-right: 2px;
   }
   QTabBar::tab:selected {
       background: #1a1a2e; color: #00AAFF; border-color: #00AAFF;
   }
   QTabBar::tab:hover:!selected { background: #2a2a3e; color: #CCC; }
   ```

4. **Tab-Position:** `QTabWidget.setTabPosition(QTabWidget.North)` (oben).

5. **Initialer Tab beim Oeffnen:** Tab 1 „Station" (`setCurrentIndex(0)`).

6. **Buttons unveraendert:** „Grundeinstellungen", „Abbrechen", „Speichern"
   als feste Leiste UNTER dem `QTabWidget` (nicht in den Tabs). Auch die
   Button-Stile (`reset`, `cancel`, default) bleiben.

7. **Funktional unveraendert:**
   - `_load_values()` befuellt alle Widgets in allen Tabs.
   - `_save_and_close()` liest aus allen Tabs.
   - `_reset_defaults()` setzt Werte zurueck — User bleibt im aktuellen Tab.
   - `_refresh_rf_table()`, `_update_rf_buttons_tx_state()`,
     `_on_tune_power_clicked()`, `_on_rf_clear_band()`, `_on_rf_clear_all()`,
     `_on_export_csv_clicked()`, `_on_map_open_clicked()` bleiben unveraendert.
   - TX-Status-Polling-`QTimer` (1 s) laeuft im Hintergrund weiter, auch
     wenn Tab 2 nicht sichtbar — kein Lifecycle-Bug.

8. **Widget-Attribute behalten dieselben Namen:** `self.callsign`,
   `self.locator`, `self.radio_ip`, `self.power`, `self.tx_level`,
   `self.max_calls_combo`, `self.swr_limit`, `self.audio_freq`,
   `self.max_decode_freq`, `self.diversity_cycles`, `self.language_combo`,
   `self.stats_cb`, `self.debug_console_cb`, `self._tune_btns`,
   `self._current_tune_power`, `self.rf_table`, `self._rf_band_combo`,
   `self.btn_rf_clear_band`, `self.btn_rf_clear_all`, `self._rf_info_label`,
   `self._tx_status_timer`, `self._export_csv_btn`, `self._map_open_btn` —
   alle erreichbar wie bisher (Mike koennte Settings programmatisch initial
   setzen).

9. **GroupBox-Strategie:** Innerhalb jedes Tabs werden GroupBoxen NUR
   behalten wo sie inhaltlich Subgruppen trennen (z.B. „RF-Presets pro
   Band+Watt" in Tab 2 als interne GroupBox unterhalb der TX-Form). Bei
   einem Tab mit nur einer logischen Einheit entfaellt die aeussere
   GroupBox (Tab-Header gibt schon Gruppierung). Konkret:
   - Tab 1: keine GroupBox (4 Form-Felder direkt).
   - Tab 2: keine aeussere GroupBox; RF-Presets bleibt als interne GroupBox.
   - Tab 3: keine GroupBox.
   - Tab 4: keine GroupBox; CSV-Export + Karte + Debug-Konsole als drei
     vertikale Bloecke mit Trennlinie (`QFrame::HLine`) zwischen ihnen.

10. **Code-Struktur:** `_setup_ui()` wird aufgeteilt in:
    - `_setup_ui()` — top-level: erstellt `QTabWidget`, ruft die 4 Build-
      Methoden auf, fuegt Button-Leiste hinzu.
    - `_build_tab_station(self) -> QWidget`
    - `_build_tab_tx(self) -> QWidget`
    - `_build_tab_ft8(self) -> QWidget`
    - `_build_tab_data(self) -> QWidget`
    Jede `_build_tab_*`-Methode erstellt die Widgets, befestigt sie an
    `self.<name>` (fuer `_load_values`/`_save_and_close`), und gibt das
    Tab-Container-`QWidget` zurueck.

11. **Tab-Order (Tabulator-Taste):** Innerhalb eines Tabs durch Reihenfolge
    der `QFormLayout::addRow`-Aufrufe automatisch korrekt. Zwischen Tabs
    interessiert Tab-Order nicht (User klickt Tab-Header).

12. **Smoke-Test (NEU):** `tests/test_settings_dialog_smoke.py` —
    instanziiert `SettingsDialog` mit gemockten `Settings`, prueft:
    - `dlg.tabs.count() == 4` (oder 3 falls Alternative gewaehlt).
    - `dlg.callsign`, `dlg.power`, `dlg.audio_freq`, `dlg.stats_cb`,
      `dlg.debug_console_cb`, `dlg.rf_table` sind alle als Attribute
      erreichbar.
    - `dlg.height() <= 750` nach `dlg.show()` + `qApp.processEvents()`.
    - `_save_and_close()` legt mind. drei Werte korrekt in `Settings` ab
      (callsign, power, language).
    - Test laeuft mit `QT_QPA_PLATFORM=offscreen`.

13. **Tests gruen:** `./venv/bin/python3 -m pytest tests/ -q` muss alle
    467 bestehenden Tests + den neuen Smoke-Test gruen liefern.

14. **Manuelle Verifikation (Mike, vor Commit):**
    - Dialog auf 1440×900 oeffnen → vollstaendig sichtbar, Save-Buttons
      unten erreichbar.
    - Jeder Tab klickbar, kein Flicker beim Wechsel.
    - Jeden Tab einmal aendern → Save → erneut oeffnen → Werte persistiert.
    - Reset auf Werkseinstellungen → Werte in allen Tabs aktualisiert
      (User bleibt im Tab).
    - RF-Presets-Tabelle laedt, Clear-Buttons funktionieren.
    - CSV-Export-Button reagiert.
    - „Karte oeffnen ..." oeffnet Karte non-modal (Settings bleibt offen).

## Betroffene Dateien

- `ui/settings_dialog.py` (559 Z., Hauptarbeit) — `_setup_ui` Refactor,
  neue Build-Methoden. Keine Settings-Persistenz-Aenderung.
- `tests/test_settings_dialog_smoke.py` (NEU, ~50 Z.) — Smoke-Test.
- `ui/main_window.py:730` — Aufruf `SettingsDialog(self.settings, self)`
  UNVERAENDERT.
- `config/settings.py` — UNVERAENDERT.
- `main.py` — `APP_VERSION` von „0.75" auf „0.76" erhoehen.
- `HISTORY.md` — Eintrag zu v0.76.
- `CLAUDE.md` — Header v0.75 → v0.76, Test-Count 467 → 468.

## Randbedingungen

- **PySide6** (NICHT PyQt5). `from PySide6.QtWidgets import QTabWidget`
  ergaenzen.
- **KISS:** Keine neue Helper-Klasse pro Tab. Keine Tab-Faktory-Pattern.
  Vier Methoden in derselben Klasse — fertig.
- **Keine neuen Settings-Felder.** Keine neuen Funktionen. Reines UI-Refactor.
- **Kein Live-Apply** — Save-on-Click bleibt.
- **Kein „letzter Tab merken"** zwischen Sessions.
- **Kein Suchfeld / Settings-Search.**
- **Threading:** TX-Status-Polling-`QTimer` bleibt single-threaded GUI.
  Keine neuen Threads.
- **Persistence:** keine Aenderung am `config.json`-Format.

## Nicht im Scope

- Kein `Settings`-Klassen-Refactor.
- Keine neuen Eingabefelder.
- Keine Live-Apply-Logik.
- Kein Mobile-Layout.
- Kein Dark-Mode-Toggle (App ist immer Dark).
- Keine Lokalisierung der Tab-Header (nur DE, da App primaer DE).
- Keine Settings-Export/Import-Funktion.

## Aufwandsschaetzung

- `_setup_ui` Refactor in 4 Build-Methoden: ~1 h
- Tab-Header-Stylesheet + Hoehen-Limits: ~0.3 h
- Smoke-Test schreiben: ~0.4 h
- Manuelle Verifikation + ggf. Hoehen-Tuning: ~0.5 h
- HISTORY.md, CLAUDE.md, APP_VERSION: ~0.2 h
- DeepSeek-Final-Codereview vor letztem Commit: ~0.2 h
- **Gesamt: ~2.5-3 h.**

## Atomare Commit-Aufteilung (geplant)

1. `refactor(ui): SettingsDialog mit QTabWidget (4 Tabs)` — Hauptaenderung
   in `settings_dialog.py`.
2. `test(ui): SettingsDialog Smoke-Test` — neuer Test in `tests/`.
3. `chore(release): v0.76 — Settings auf Tabs` — `APP_VERSION`,
   HISTORY.md, CLAUDE.md.
