# P95 — Bundle: TUNE-Rechtsklick + QSO-Panel Spalten-Config (V1)

## Mike-Spec (20.05.2026 nach P94)

**A) TUNE-Rechtsklick:** Rechtsklick auf TUNE-Button → Auswahl 10s,
15s, 20s → TUNE startet sofort mit dieser Dauer, **unabhängig vom
Settings-Wert**. One-shot, Settings bleiben unverändert.

**B) QSO-Panel Rechtsklick Spalten-Konfig:** Rechtsklick im QSO-Fenster
→ Toggle für „Even/Odd-Anzeige" und „Antennen-Anzeige" mit
**speichern/laden** (analog RX-Panel-Header-Rechtsklick).

## Code-Realität (verifiziert 20.05.2026)

### Feature A — TUNE-Button
- `ui/control_panel.py:899` definiert `self.btn_tune = QPushButton("TUNE")`
- `ui/main_window.py:1354` connectet `self.btn_tune.clicked.connect(self._on_tune_clicked)`
- `ui/mw_tx.py:78-140` `_on_tune_clicked(self, on: bool)`:
  - Z.99: `duration_s = self.settings.get("tune_duration_s", 15)`
  - Z.100-101: Whitelist `if duration_s not in (5, 10, 15): duration_s = 15`
  - Z.123: `radio.set_rfpower_direct(TUNE_POWER_W=10)`
  - Z.124: `radio.tune_on()`
  - Z.135-137: `QTimer.singleShot(duration_s * 1000, lambda: self._tune_stop(_token))`

### Feature B — RX-Panel-Pattern
- `ui/rx_panel.py:195-196`:
  ```python
  hdr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
  hdr.customContextMenuRequested.connect(self._on_header_context_menu)
  ```
- `ui/rx_panel.py:531-552` `_on_header_context_menu`: QMenu mit
  `setCheckable(True)` Actions pro Spalte; Toggle ruft `_toggle_column`
  + emittet `hidden_cols_changed`-Signal an MainWindow für Settings.

### Feature B — QSO-Panel heute
- `ui/qso_panel.py:29` `class QSOPanel(QWidget)` — **QTextEdit**, KEIN Table!
- `add_tx` (Z.209), `add_rx` (Z.254), `add_listening` (Z.283),
  `add_qso_complete` (Z.297), `add_timeout` (Z.306), `add_info` (Z.311)
  formatieren strings direkt mit Tag/Antenne und schreiben via
  `_append_colored` / `_append_two_color` ins `log_view`.
- Format `add_rx` (Z.276-281):
  ```
  HH:MM:SS [E] ← Empf. CALL DA1MHH -10  (ANT2, +6.3 dB)
  ```
  — `[E]` / `[O]` Tag und `(ANT...)` Suffix sind beide reine String-
  Bestandteile, keine Zellen.

## Vorschlag V1

### Feature A — TUNE-Rechtsklick (KISS, ~25 LOC)

1. **`ui/control_panel.py`** btn_tune:
   ```python
   self.btn_tune.setContextMenuPolicy(Qt.CustomContextMenu)
   self.btn_tune.customContextMenuRequested.connect(
       self._on_tune_button_context)
   ```

2. **Neuer Slot in `control_panel.py`:**
   ```python
   tune_override_requested = Signal(int)  # Signal: duration_s

   def _on_tune_button_context(self, pos):
       menu = QMenu(self)
       menu.setStyleSheet(...)  # gleicher Style wie rx_panel
       for sec in (10, 15, 20):
           action = menu.addAction(f"TUNE {sec}s")
           action.triggered.connect(
               lambda checked=False, s=sec: self.tune_override_requested.emit(s))
       menu.exec(self.btn_tune.mapToGlobal(pos))
   ```

3. **`ui/main_window.py`:**
   ```python
   self.control_panel.tune_override_requested.connect(self._on_tune_override)
   ```

4. **`ui/mw_tx.py` neuer Handler:**
   ```python
   def _on_tune_override(self, duration_s: int):
       """P95: Rechtsklick-Override — TUNE mit expliziter Dauer.
       Whitelist (5,10,15,20). Setting tune_duration_s bleibt unverändert.
       """
       if not self.radio.ip:
           return
       if duration_s not in (10, 15, 20):
           return  # KISS: ignorieren statt clamp
       # Wenn TUNE schon läuft: Toggle off
       if self.btn_tune.isChecked():
           self._on_tune_clicked(False)
           return
       # btn_tune visuell checken + Pipeline manuell mit Override starten
       self.btn_tune.setChecked(True)
       self._tune_override_duration = duration_s
       self._on_tune_clicked(True)  # Pipeline läuft mit Override-Dauer
   ```

   **Variante 1 (sauber):** `_on_tune_clicked` bekommt Override-Mechanik:
   ```python
   def _on_tune_clicked(self, on: bool):
       ...
       override = getattr(self, '_tune_override_duration', None)
       if override is not None:
           duration_s = override
           self._tune_override_duration = None
       else:
           duration_s = self.settings.get("tune_duration_s", 15)
           if duration_s not in (5, 10, 15):
               duration_s = 15
       ...
   ```

### Feature B — QSO-Panel Spalten-Config (Variante B, Re-Render, ~80 LOC)

**Architektur-Entscheidung (V1 schlägt vor):** Mike will Verhalten „wie
im Empfangs-Fenster" — dort werden BESTEHENDE Zeilen ein/ausgeblendet
(setColumnHidden auf QTableWidget). Im QSO-Panel ist log_view ein
QTextEdit (Text). Drei Optionen:

- **A: Nur neue Einträge betroffen** (~20 LOC, KISS aber inkonsistent
  zu Mike's „wie im Empfangsfenster"-Anweisung)
- **B: Re-Render bei Toggle** (~80 LOC, konsistent — `_entries`-Liste
  als SOT, log_view komplett neu zeichnen bei Toggle). Performance:
  max ~100 Zeilen aktiv → irrelevant.
- **C: QTextEdit → QTableWidget Refactoring** (~500+ LOC,
  Overengineering — abgelehnt per CLAUDE.md §1)

**V1-Empfehlung: Variante B.**

**Implementierung Variante B:**

1. **`ui/qso_panel.py`** neue Felder:
   ```python
   self._entries: list[dict] = []  # SOT für Re-Render
   self._show_eo_tag: bool = True
   self._show_ant_label: bool = True
   col_visibility_changed = Signal(dict)  # {"eo_tag": bool, "ant_label": bool}
   ```

2. **Refactoring `add_tx` / `add_rx` / `add_listening` / `add_qso_complete` /
   `add_timeout` / `add_info`:** statt direkt `_append_*` zu rufen,
   `self._entries.append({...})` + Helper `self._render_entry(entry)`.

3. **`_render_entry(entry: dict)`** rendert basierend auf Visibility-Flags:
   ```python
   def _render_entry(self, e: dict):
       kind = e["kind"]  # "tx" | "rx" | "listening" | "complete" | "timeout" | "info"
       if kind in ("tx", "rx", "listening"):
           utc = e["utc"]
           tag = f"{e['tag']} " if self._show_eo_tag else ""
           # ... String aufbauen ohne Tag wenn _show_eo_tag=False
           # ... ant_label nur wenn self._show_ant_label
           ...
   ```

4. **`_rerender_all()`:**
   ```python
   def _rerender_all(self):
       self.log_view.clear()
       for e in self._entries:
           self._render_entry(e)
   ```

5. **Rechtsklick auf log_view:**
   ```python
   self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
   self.log_view.customContextMenuRequested.connect(self._on_log_context)

   def _on_log_context(self, pos):
       menu = QMenu(self)
       menu.setStyleSheet(...)  # gleicher Style wie rx_panel
       a_eo = menu.addAction("Even/Odd-Tag anzeigen")
       a_eo.setCheckable(True)
       a_eo.setChecked(self._show_eo_tag)
       a_eo.triggered.connect(
           lambda checked: self._toggle_eo_tag(checked))
       a_ant = menu.addAction("Antennen-Anzeige")
       a_ant.setCheckable(True)
       a_ant.setChecked(self._show_ant_label)
       a_ant.triggered.connect(
           lambda checked: self._toggle_ant_label(checked))
       # plus Standard-QTextEdit-Aktionen (Copy etc.) als Separator
       menu.addSeparator()
       std = self.log_view.createStandardContextMenu()
       for action in std.actions():
           menu.addAction(action)
       menu.exec(self.log_view.mapToGlobal(pos))

   def _toggle_eo_tag(self, show: bool):
       self._show_eo_tag = show
       self._rerender_all()
       self.col_visibility_changed.emit(
           {"eo_tag": show, "ant_label": self._show_ant_label})

   def _toggle_ant_label(self, show: bool):
       self._show_ant_label = show
       self._rerender_all()
       self.col_visibility_changed.emit(
           {"eo_tag": self._show_eo_tag, "ant_label": show})
   ```

6. **Persistierung in `ui/main_window.py`:**
   ```python
   # Load nach __init__:
   qso_vis = self.settings.get("qso_col_visibility",
                                {"eo_tag": True, "ant_label": True})
   self.qso_panel._show_eo_tag = qso_vis.get("eo_tag", True)
   self.qso_panel._show_ant_label = qso_vis.get("ant_label", True)

   # Connect für Save:
   self.qso_panel.col_visibility_changed.connect(
       lambda vis: self.settings.set("qso_col_visibility", vis))
   ```

## Tests (`tests/test_p95_bundle.py`)

- **A-T1:** Rechtsklick-Menü auf btn_tune zeigt 10/15/20s
- **A-T2:** Klick auf „TUNE 20s" → `tune_override_requested.emit(20)`
- **A-T3:** `_on_tune_override(20)` mit btn nicht checked → checked + Pipeline mit duration=20
- **A-T4:** `_on_tune_override(20)` mit btn schon checked → off-Pfad
- **A-T5:** Override duration_s=20 wird in `_on_tune_clicked` korrekt durchgereicht
- **A-T6:** Setting `tune_duration_s` bleibt unverändert nach Override
- **A-T7:** Override duration_s NICHT in (10,15,20) → ignoriert (no-op)
- **B-T1:** `_show_eo_tag=False` → neue add_rx rendert ohne `[E]`/`[O]`
- **B-T2:** `_show_ant_label=False` → add_rx rendert ohne `(ANT2 ...)`
- **B-T3:** `_entries`-Liste enthält alle 6 Entry-Typen nach Aufrufen
- **B-T4:** Toggle ruft `_rerender_all` + clear log_view + neu zeichnen
- **B-T5:** `col_visibility_changed`-Signal feuert mit korrektem dict
- **B-T6:** Settings-Load setzt initial-State

## V1-Findings / Selbst-Check

- ⚠ Hardware: TUNE-Override muss 10W FEST (manueller TUNE-Pfad,
  P63 AC5). Override-Pipeline geht durch `_on_tune_clicked` → 10W
  bleibt ✓.
- ⚠ Override während aktiver TUNE: Toggle-Logik prüft `btn_tune.isChecked()`
  und ruft off-Pfad. Aber: Wenn User-TUNE läuft mit 15s und rechtsklickt
  „TUNE 20s" → soll das: (a) abbrechen + neuer Start, (b) abbrechen +
  nichts, (c) ignorieren während TUNE läuft? Mike entscheiden.
  V1-Default: (b) — abbrechen, kein Auto-Restart (User muss erneut wählen).
- ⚠ Whitelist 20s neu — nicht in `_tune_post_swr_check` oder Auto-Tune
  greifbar (die nutzen Setting-Pfad). Override umgeht Whitelist → ok.
- ⚠ `_entries` wachsen unbegrenzt während Session. Auto-Trim heute via
  `_auto_trim_by_age` (5 min). Bei Re-Render: trim auch `_entries`!
  Sonst Memory-Leak + Re-Render dauert länger.
- ⚠ HTML-Performance: log_view ist QTextDocument. `clear()` +
  N×append ist O(N) pro Re-Render. Bei ~100 Zeilen: <50ms — ok.

## Workflow

V1 (jetzt) → V2 Self-Review → R1 DeepSeek → V3 Mike-Freigabe → Code
+ Tests → Final-R1 → atomare Commits → Doku.

KISS-Prinzip: Feature A ~25 LOC, Feature B Variante B ~80 LOC,
Tests ~140 LOC. APP_VERSION 0.97.66 → 0.97.67.
