# Prompt V3 — Settings-Dialog auf Tabs (Final, Mike-freigabe-fertig)

## Kontext: Projektphilosophie

- SimpleFT8 ist ein Hobby-Funker-Tool (Operator: Mike, DA1MHH). Kein
  Contest-Tool. KISS schlaegt Eleganz.
- Display: 1440×900 (MacBook). Nutzbare Hoehe nach macOS-Menubar (25 px),
  Titel (28 px), Dock (80 px) ≈ 767 px netto.
- Visueller Stil: dunkles Theme (`#1a1a2e` Background, `#00AAFF` Akzent),
  modern/Neon — KEIN macOS-Default-Grau.
- Hardware-Pflicht: ANT1 = TX, ANT2 = RX-only. Hier irrelevant da rein
  UI-Refactor (kein TX-Pfad beruehrt).

## Ziel

`ui/settings_dialog.py` (`SettingsDialog`) von monolithisch gestapelter Form
(6 GroupBoxen vertikal) auf eine `QTabWidget`-Struktur umstellen, sodass der
Dialog auf 1440×900 vollstaendig sichtbar ist. Funktional unveraendert.
Save-Persistenz unveraendert.

## Akzeptanzkriterien

### A) Sichtbarkeit & Sizing

1. `setMinimumWidth(720)`, `setMinimumHeight(560)`.
2. **Hoehen-Regelung am Ende von `_setup_ui`** statt nur `setMaximumHeight`:
   ```python
   self.adjustSize()
   if self.height() > 750:
       self.resize(self.width(), 750)
   self.setMaximumHeight(750)  # zusaetzlicher Schutz
   ```
3. Falls beim manuellen Test ein Tab inhaltlich > 600 px wird (besonders
   Tab 2 mit RF-Presets-Tabelle): das Tab-Container-Widget in eine
   `QScrollArea` einbetten (`setWidgetResizable(True)`, kein Frame).
   Default ohne ScrollArea — nur Fallback bei Bedarf.

### B) Tab-Aufteilung — Entscheidung im Code

**Regel zur Tab-Anzahl:** Nach Build aller Tabs wird die Inhaltshoehe pro
Tab via `tab_widget.sizeHint().height()` gemessen. Falls Tab „TX & Schutz"
> 500 px (Form + RF-Presets-Tabelle gestapelt) → **4 Tabs** (Default-
Variante). Sonst → **3 Tabs** (RF-Presets in TX-Tab integriert).
Entscheidung wird in `_setup_ui` einmal getroffen, im Commit dokumentiert.

#### Default 4-Tab-Variante:
- **Tab 1 „Station"**: Rufzeichen, Locator, IP-Adresse, Sprache.
  - *Begruendung Sprache hier:* Sprache ist eine einmalige Setup-
    Einstellung (wie Rufzeichen/Locator) und wird waehrend des Funk-
    Betriebs nicht geaendert. Einordnung zu „Station" ist deshalb sauberer
    als zur FT8-Betriebs-Sektion.
- **Tab 2 „TX & Schutz"**: Sendeleistung, TX-Audio-Pegel, Anrufversuche,
  SWR-Limit, Tune-Leistung (5w/10w/20w), RF-Presets-Tabelle (mit `_rf_info_label`,
  Band-Combo, „Band loeschen", „Alle loeschen").
- **Tab 3 „FT8 & Diversity"**: TX-Audio-Frequenz, Max-Decode-Frequenz,
  Neueinmessung-Zyklen, Statistik-Erfassung-Checkbox.
- **Tab 4 „Daten & Tools"**: 3 vertikale Bloecke mit `QFrame::HLine`-
  Trennern: (1) CSV-Export-Button + Beschreibung, (2) Richtungs-Karte
  oeffnen + Beschreibung, (3) Debug-Konsole-Checkbox (ohne Form-Label —
  Checkbox-Text reicht).

#### Fallback 3-Tab-Variante (falls TX-Tab klein genug):
- **Tab 1 „Station"**: wie oben.
- **Tab 2 „TX & Schutz"**: wie oben + RF-Presets.
- **Tab 3 „FT8 & Tools"**: FT8-Felder + Statistik-Checkbox + CSV-Export +
  Karte + Debug-Konsole.

### C) Tab-Widget-Struktur

4. Tab-Widget wird als `self.tabs` als Attribut gespeichert (fuer Smoke-Test
   und potenzielles spaeteres Zugreifen).
5. `self.tabs.setTabPosition(QTabWidget.North)` (Header oben).
6. `self.tabs.setCurrentIndex(0)` beim Oeffnen.
7. **Tab-Stylesheet wird ausschliesslich auf `self.tabs` gesetzt** (NICHT
   im globalen `self.setStyleSheet`-Block), um Kollisionen mit dem
   Dialog-Stylesheet zu vermeiden:
   ```python
   self.tabs.setStyleSheet("""
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
   """)
   ```

### D) Buttons & Lifecycle

8. „Grundeinstellungen", „Abbrechen", „Speichern" als FESTE Leiste UNTER
   dem `QTabWidget` (nicht in den Tabs). Button-Stile (`reset`, `cancel`,
   default) bleiben.
9. **TX-Status-Polling-`QTimer` Start am Ende von `_setup_ui`** — nachdem
   alle Tabs gebaut sind und `self.btn_rf_clear_band`/`_clear_all` existieren:
   ```python
   self._tx_status_timer = QTimer(self)
   self._tx_status_timer.timeout.connect(self._update_rf_buttons_tx_state)
   self._tx_status_timer.start(1000)
   ```

### E) Funktional unveraendert

10. `_load_values()` befuellt alle Widgets in allen Tabs (keine Reihenfolge-
    Aenderung notwendig — Widgets sind via `self.<name>` zugreifbar).
11. `_save_and_close()` liest aus allen Tabs.
12. `_reset_defaults()` setzt Werte zurueck — User bleibt im aktuellen Tab.
    Bestehendes Verhalten (Rufzeichen/Locator behalten, Rest auf DEFAULTS)
    bleibt unveraendert. Inkonsistenz dass `radio_ip`, `language`,
    `stats_cb`, `debug_console_cb` aktuell NICHT zurueckgesetzt werden,
    wird in dieser Aenderung NICHT korrigiert (out-of-scope).
13. Alle bestehenden Methoden bleiben funktional unveraendert:
    `_refresh_rf_table`, `_update_rf_buttons_tx_state`, `_on_tune_power_clicked`,
    `_on_rf_clear_band`, `_on_rf_clear_all`, `_on_export_csv_clicked`,
    `_on_map_open_clicked`.

### F) Widget-Attribute behalten dieselben Namen

14. Alle Widget-Attribute behalten ihre Namen (egal in welchem Tab sie
    landen): `self.callsign`, `self.locator`, `self.radio_ip`,
    `self.power`, `self.tx_level`, `self.max_calls_combo`,
    `self.swr_limit`, `self.audio_freq`, `self.max_decode_freq`,
    `self.diversity_cycles`, `self.language_combo`, `self.stats_cb`,
    `self.debug_console_cb`, `self._tune_btns`, `self._current_tune_power`,
    `self.rf_table`, `self._rf_band_combo`, `self.btn_rf_clear_band`,
    `self.btn_rf_clear_all`, `self._rf_info_label`, `self._tx_status_timer`,
    `self._export_csv_btn`, `self._map_open_btn`. Plus neu: `self.tabs`.

### G) GroupBox-Strategie

15. Aeussere GroupBoxen werden ueberall entfernt (Tab-Header gibt schon
    Gruppierung). EINE Ausnahme: RF-Presets in Tab 2 bleibt eine interne
    GroupBox unterhalb der TX-Form, damit RF-Presets visuell von TX-Schutz-
    Settings getrennt bleibt.
16. `_rf_info_label` bleibt in der internen RF-Presets-GroupBox, ueber der
    Tabelle (wie heute).
17. Tab 4 verwendet `QFrame` mit `setFrameShape(QFrame.HLine)` als optische
    Trennung zwischen den 3 Bloecken.

### H) Code-Struktur

18. `_setup_ui` wird aufgeteilt in:
    - `_setup_ui()` — top-level: erstellt `self.tabs`, ruft Build-Methoden,
      fuegt Button-Leiste hinzu, startet `_tx_status_timer`, fuehrt
      Hoehen-Regelung aus (`adjustSize` + ggf. `resize`).
    - `_build_tab_station(self) -> QWidget`
    - `_build_tab_tx(self) -> QWidget`
    - `_build_tab_ft8(self) -> QWidget`
    - `_build_tab_data(self) -> QWidget`  (entfaellt bei 3-Tab-Variante)

    Jede Build-Methode erstellt die Widgets, bindet sie als `self.<name>`
    an, und gibt das Tab-Container-`QWidget` zurueck.

### I) Smoke-Test (NEU)

19. `tests/test_settings_dialog_smoke.py` (~70 Z.) mit:
    - **`_FakeSettings`-Helferklasse** (dict-basiert):
      ```python
      class _FakeSettings:
          def __init__(self):
              self._d = {
                  "callsign": "TEST", "locator": "JN58XB",
                  "flexradio_ip": "", "power_watts": 50,
                  "tx_level": 100, "max_calls": 3, "swr_limit": 3.0,
                  "tune_power": 10, "audio_freq_hz": 1500,
                  "max_decode_freq": 3000, "diversity_operate_cycles": 80,
                  "language": "de", "stats_enabled": True,
                  "debug_console_visible": False,
              }
          def get(self, key, default=None): return self._d.get(key, default)
          def set(self, key, val): self._d[key] = val
          def save(self): pass
          @property
          def callsign(self): return self._d["callsign"]
          @property
          def locator(self): return self._d["locator"]
          @property
          def power_watts(self): return self._d["power_watts"]
          @property
          def max_decode_freq(self): return self._d["max_decode_freq"]
      ```
    - **Tests:**
      - `test_dialog_has_tabs_attribute`: `dlg.tabs` existiert, `count()` ∈ {3, 4}.
      - `test_widget_attributes_accessible`: alle 24+ Widget-Attribute aus AC 14
        sind als Attribute erreichbar (Schleife mit `getattr`).
      - `test_dialog_height_within_limit`: `dlg.show()` + `qapp.processEvents()`,
        dann `assert dlg.height() <= 750`.
      - `test_save_round_trip`: callsign/power/language aendern, `accept()`
        per Monkey-Patch ueberschreiben (`dlg.accept = lambda: None`),
        `_save_and_close()` aufrufen, dann `settings.get(...)` pruefen.
    - Test laeuft mit `QT_QPA_PLATFORM=offscreen` (wie bestehende UI-Tests).

### J) Tests Gesamt

20. `./venv/bin/python3 -m pytest tests/ -q` muss alle 467 bestehenden Tests
    + den neuen Smoke-Test gruen liefern.

### K) Manuelle Verifikation (Mike, vor Commit)

21. - Dialog auf 1440×900 oeffnen → vollstaendig sichtbar, Save-Buttons
      unten erreichbar.
    - Jeder Tab klickbar, kein Flicker beim Wechsel.
    - Jeden Tab einmal aendern → Save → erneut oeffnen → Werte persistiert.
    - Reset auf Werkseinstellungen → Werte in allen Tabs aktualisiert
      (User bleibt im aktuellen Tab).
    - RF-Presets-Tabelle laedt, Clear-Buttons funktionieren.
    - CSV-Export-Button reagiert.
    - „Karte oeffnen ..." oeffnet Karte non-modal (Settings bleibt offen).
    - Tab-Header in Theme-Farben (kein macOS-Grau).

## Betroffene Dateien

- `ui/settings_dialog.py` (559 Z., Hauptarbeit) — `_setup_ui` Refactor,
  4 neue Build-Methoden, neues Hoehen-Sizing, neuer Tab-Stylesheet.
- `tests/test_settings_dialog_smoke.py` (NEU, ~70 Z.).
- `ui/main_window.py:730` — Aufruf UNVERAENDERT.
- `config/settings.py` — UNVERAENDERT.
- `main.py` — `APP_VERSION` „0.75" → „0.76".
- `HISTORY.md` — Eintrag zu v0.76 (Tab-Anzahl-Entscheidung dokumentieren).
- `CLAUDE.md` — Header v0.75 → v0.76, Test-Count 467 → 468.

## Randbedingungen

- **PySide6** (NICHT PyQt5). `from PySide6.QtWidgets import QTabWidget,
  QScrollArea, QFrame` ergaenzen.
- **KISS:** Keine Helper-Klasse pro Tab. Keine Tab-Faktory-Pattern.
  Vier Methoden in derselben Klasse.
- **Keine neuen Settings-Felder.** Reines UI-Refactor.
- **Kein Live-Apply** — Save-on-Click bleibt.
- **Kein „letzter Tab merken"** zwischen Sessions.
- **Threading:** TX-Status-Polling-`QTimer` bleibt single-threaded GUI.
  Keine neuen Threads.
- **Persistence:** keine Aenderung am `config.json`-Format.

## Nicht im Scope

- Kein `Settings`-Klassen-Refactor.
- Keine neuen Eingabefelder.
- Keine Live-Apply-Logik.
- Kein Mobile-Layout.
- Kein Dark-Mode-Toggle.
- Keine Lokalisierung der Tab-Header (nur DE).
- Keine Settings-Export/Import-Funktion.
- Kein Fix der bestehenden `_reset_defaults`-Inkonsistenz (radio_ip,
  language, stats_cb, debug_console_cb werden weiterhin NICHT zurueck-
  gesetzt — separates Issue).

## Aufwandsschaetzung

- `_setup_ui` Refactor in 4 Build-Methoden: ~1 h
- Tab-Stylesheet + Hoehen-Sizing + ggf. ScrollArea-Fallback: ~0.4 h
- Smoke-Test mit `_FakeSettings` schreiben: ~0.5 h
- Manuelle Verifikation + ggf. Tab-Anzahl-Entscheidung (3 vs 4): ~0.5 h
- HISTORY.md, CLAUDE.md, APP_VERSION: ~0.2 h
- DeepSeek-Final-Codereview vor letztem Commit: ~0.2 h
- **Gesamt: ~2.5-3 h.**

## Atomare Commit-Aufteilung (geplant)

1. `refactor(ui): SettingsDialog mit QTabWidget (X Tabs)` — Hauptaenderung
   in `settings_dialog.py`. (X = 3 oder 4, je nach Hoehen-Pruefung)
2. `test(ui): SettingsDialog Smoke-Test` — neuer Test in `tests/`.
3. `chore(release): v0.76 — Settings auf Tabs` — `APP_VERSION`,
   HISTORY.md, CLAUDE.md.
