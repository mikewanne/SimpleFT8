[deepseek] ~55428 Tokens, 6 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=63621 out=6251 total=69872
**KRITISCH (KP-N)**  

- **KP-1** `core/qso_state.py:on_message_sent` (Z.488 im Plan, Code ca. Z.500): Plan fordert, an **allen** `qso_confirmed.emit()`-Stellen auch `qso_confirmed_visual.emit()` davor zu setzen. Das schließt `on_message_sent` im State `TX_73_COURTESY` ein. Dort wurde `qso_confirmed_visual` aber bereits beim 73-Empfang gefeuert → zweiter `add_qso_complete`-Aufruf → doppelter Eintrag im QSO-Panel.  
  **Empfehlung:** `qso_confirmed_visual` NUR bei 73-Empfang (`WAIT_73` in `on_message_received`) und bei `WAIT_73`-Timeout (`on_cycle_end`) emitten. Nach Courtesy-Send (Z.488) darf kein weiteres visual-Update kommen – `qso_confirmed` allein reicht.

- **KP-2** `core/qso_state.py:on_cycle_end` `WAIT_73` (Z.317 im Plan): Plan schreibt in AK5 vor, dass der Timeout-Pfad (3 Zyklen ohne 73) `qso_confirmed_visual` und `qso_confirmed` emittiert. Der Plan-Text zur Code-Änderung zeigt jedoch keine Anpassung in `on_cycle_end`. Ohne diesen Fix feuert der Timeout-Pfad nur `qso_confirmed`, das visuelle Update fehlt → AK5 nicht erfüllt.  
  **Empfehlung:** In `on_cycle_end` bei `WAIT_73` (Zeile ca. 317) vor `self.qso_confirmed.emit(self.qso)` ein `self.qso_confirmed_visual.emit(self.qso)` einfügen.

---

**SOLLTE-FIX (S-N)**  

- **S-1** `ui/rx_panel.py:__init__`: Plan führt neuen Parameter `hidden_cols: list[int] = None` ein, zeigt aber nicht, wie dieser in den bestehenden Code integriert wird (aktuelle Zeile `self._hidden_cols: set = set()`). Ohne vollständige Darstellung besteht die Gefahr, dass die Initialisierung der Spalten-Sichtbarkeit (Phase 2 nach header init) nicht korrekt ausgeführt wird.  
  **Empfehlung:** Den vollständigen Konstruktor mit `hidden_cols`-Parameter dokumentieren:  
  ```python
  self._hidden_cols: set = set(hidden_cols or [])
  # nach header init:
  for col in self._hidden_cols:
      if 0 <= col < COL_COUNT and col != COL_MSG:
          self.table.setColumnHidden(col, True)
  ```

- **S-2** `core/qso_state.py:on_message_received` (hypothetischer Doppelschutz ca. Z.658): Im `else`-Zweig (courtesy_73_sent bereits True) wird `self.qso_confirmed.emit(self.qso)` ausgeführt, aber **ohne** `qso_confirmed_visual`. Da dieser Pfad hypothetisch ist (sollte nie greifen), ist es dennoch inkonsistent – im Fehlerfall fehlt das visuelle Update.  
  **Empfehlung:** Auch hier `qso_confirmed_visual.emit(self.qso)` vor dem confirmed-Emit hinzufügen.

---

**KOENNTE (K-N)**  

- **K-1** Vorschlag P33: Der 2-Signal-Split (`qso_confirmed_visual` + `qso_confirmed`) ist wartbar, aber könnte durch ein einzelnes Signal mit bool-Parameter (`visual_only=True`) vereinfacht werden. Das reduziert neue Signals/ Slots und hält den Code kompakter.  
  **Empfehlung:** Prüfen, ob `qso_confirmed.emit(qso_data, visual_only=True/False)` und ein entsprechender Slot `_on_qso_confirmed(qso_data, visual_only)` ausreicht. Dann entfällt die zweite Verbindung in `main_window.py`.

- **K-2** P32 Settings-Key: `rx_panel_hidden_cols` speichert die **ausgeblendeten** Spalten. Die restliche Codebasis (z. B. `country_filter`) speichert positive Filter (was **sichtbar** sein soll). Einheitlichkeit wäre `rx_panel_visible_cols` mit Default `[0..8]` außer `COL_MSG`.  
  **Empfehlung:** Auf `rx_panel_visible_cols` umstellen, um Konvention zu wahren.

---

**HINWEIS (H-N)**  

- **H-1** `ui/main_window.py:_setup_ui`: Der Aufruf `self.rx_panel = RXPanel(…, hidden_cols=self.settings.get("rx_panel_hidden_cols", []))` fehlt im Plan-Code. Settings-Key muss konsistent sein (aktuell `rx_panel_hidden_cols`). Bei erstem Start wird `[]` geliefert → alle Spalten sichtbar. Das ist korrekt.

- **H-2** Bundle-Strategie: P32+P32 sind unabhängig, könnten aber zwei separate Commits sein. Plan bündelt sie – das ist in Ordnung, solange die Akzeptanzkriterien getrennt prüfbar bleiben.

---

**ZUSAMMENFASSUNG:**  
- **Anzahl KRITISCH:** 2 → Bugs führen zu doppelten Panel-Einträgen bzw. fehlendem visuellen Update im Timeout-Fall.  
- **Anzahl SOLLTE:** 2 → Architektonische Lücken (fehlender Code für `on_cycle_end`, unvollständiger Konstruktor).  
- **Anzahl KOENNTE:** 2 → Overengineering (Signal-Split) / Inkonsistenz (Settings-Key) optimierbar.  
- **Anzahl HINWEIS:** 2 → Unkritische Details.  

**Plan-Status: V3 nötig** – Kritische und architektonische Mängel müssen vor Integration behoben werden. Ohne Korrektur der KP-1/KP-2 ist die Lösung nicht akzeptabel.
