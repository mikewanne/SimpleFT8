# P95 — Bundle V2 (Self-Review-Korrekturen über V1)

V1 in `prompts/p95_bundle_v1.md`. V2-Findings:

## Korrekturen V1→V2

### Feature A — TUNE-Rechtsklick

**A-F1 (V1 unsauber):** State-Channel über `_tune_override_duration`-
Attribut. **Sauberer:** Refactoring zu gemeinsamem Helper `_tune_start(duration_s)`:
- `_on_tune_clicked(on)` ruft `_tune_start(duration_aus_settings)`
- `_on_tune_override(duration_s)` ruft `_tune_start(duration_s)` direkt
- Kein Side-Channel-State, keine Race-Condition bei Doppel-Klick

**A-F2 (V1-Frage geklärt):** Override während aktiver TUNE — Mike-
Default: einfach stoppen, kein Auto-Restart. User klickt erneut wenn
neue Dauer gewünscht. (Vermeidet UX-Verwirrung wenn TUNE läuft und
Mike rechtsklickt → SOFORT neue 20s + Cancel des laufenden = zu viel
in einem Klick. Lieber: erst stop, dann erneut rechtsklicken.)

**A-F3 (Pipeline-Konsistenz):** `_tune_start(duration_s)` muss
`_tune_auto_stop_token` und QTimer wie heute setzen. `_tune_stop`
unverändert. SWR-Post-Check unverändert.

### Feature B — QSO-Panel Spalten-Config

**B-F1 (V1-Architektur bestätigt):** Variante B (Re-Render via
`_entries`-Liste). Mike-Wunsch „wie im Empfangsfenster" = bestehende
Einträge auch betroffen. Performance ~100 Zeilen × clear+append =
unter 50ms — irrelevant.

**B-F2 (Trim-Konsistenz):** Heute `_auto_trim_by_age` arbeitet auf
`_block_timestamps` + `log_view.document().findBlockByNumber(0)`. Bei
`_entries`-SOT müssen ALTE Einträge aus `_entries` raus. → Refactor:
`_block_timestamps` durch `_entries[i]["ts"]` ersetzen, `_auto_trim_by_age`
trimmt `_entries` + ruft `_rerender_all()`.

**B-F3 (status_label):** `_qso_count` bleibt extern (nur `add_qso_complete`
inkrementiert). `_render_entry` ändert kein `status_label`. Bei Re-Render
wird `_qso_count` NICHT neu berechnet — bleibt stabil.

**B-F4 (P29 OMNI-Parity):** `_last_omni_tx_even` muss bei Re-Render
on-the-fly aus `_entries` rekonstruiert werden. Lösung: `_render_entry`
verwendet lokalen Tracker oder Helper-Funktion `_compute_omni_parity_chain(entries)`.

**B-F5 (Persistierung-Format):** Nicht dict, sondern 2 separate Settings-
Keys analog `rx_panel_hidden_cols`:
- `qso_show_eo_tag: bool` (default True)
- `qso_show_ant_label: bool` (default True)
- 2 Signals: `eo_tag_visibility_changed = Signal(bool)`,
  `ant_label_visibility_changed = Signal(bool)`

**B-F6 (Scroll-Position):** Bei `_rerender_all`:
```python
sb = self.log_view.verticalScrollBar()
at_bottom = sb.value() >= sb.maximum() - 5
# ... clear + re-append ...
if at_bottom:
    sb.setValue(sb.maximum())
```

**B-F7 (Standard-Kontextmenü):** `log_view.createStandardContextMenu()`
liefert Copy/SelectAll. → an Custom-Menü anhängen mit Separator.

**B-F8 (Entry-Dict-Schema):**
```python
# Common
{"kind": "tx"|"rx"|"listening"|"complete"|"timeout"|"info",
 "ts": float,  # für trim
 ... }
# TX-spezifisch
{"kind": "tx", "ts": ..., "utc": str, "tag": "[E]"|"[O]", "tx_even": bool,
 "message": str, "ant_label": str, "omni_remaining": int|None}
# RX-spezifisch
{"kind": "rx", "ts": ..., "utc": str, "tag": "[E]"|"[O]",
 "message": str, "ant_label": str}
# Listening
{"kind": "listening", "ts": ..., "utc": str, "tag": "[E]"|"[O]"}
# Complete / Timeout
{"kind": "complete", "ts": ..., "their_call": str}
{"kind": "timeout", "ts": ..., "their_call": str}
# Info
{"kind": "info", "ts": ..., "text": str}
```

## Code-Skizze V2

```python
# ─── ui/control_panel.py ───
tune_override_requested = Signal(int)  # neu

# In _setup (nach self.btn_tune = QPushButton(...)):
self.btn_tune.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self.btn_tune.customContextMenuRequested.connect(
    self._on_tune_button_context)

def _on_tune_button_context(self, pos):
    if not self.btn_tune.isVisible():
        return
    menu = QMenu(self)
    menu.setStyleSheet(self._MENU_STYLE)  # gleiches Style wie rx_panel
    for sec in (10, 15, 20):
        a = menu.addAction(f"TUNE {sec}s")
        a.triggered.connect(
            lambda checked=False, s=sec: self.tune_override_requested.emit(s))
    menu.exec(self.btn_tune.mapToGlobal(pos))


# ─── ui/main_window.py ───
self.control_panel.tune_override_requested.connect(self._on_tune_override)


# ─── ui/mw_tx.py ───
def _on_tune_clicked(self, on: bool):
    """Bestehender Slot — refactored via _tune_start Helper."""
    if not self.radio.ip:
        return
    if on:
        duration_s = self.settings.get("tune_duration_s", 15)
        if duration_s not in (5, 10, 15):
            duration_s = 15
        self._tune_start(duration_s)
    else:
        self._tune_stop(None)

def _on_tune_override(self, duration_s: int):
    """P95: Rechtsklick-Override mit 10/15/20s. Setting unverändert.
    Wenn TUNE bereits läuft: stoppen, kein Auto-Restart.
    """
    if not self.radio.ip:
        return
    if duration_s not in (10, 15, 20):
        return
    if self.btn_tune.isChecked():
        self.btn_tune.setChecked(False)
        self._tune_stop(None)
        return
    self.btn_tune.setChecked(True)
    self._tune_start(duration_s)

def _tune_start(self, duration_s: int):
    """P95: gemeinsamer TUNE-Start für _on_tune_clicked + _on_tune_override.
    Pipeline vorher direkt in _on_tune_clicked — jetzt deduped.
    """
    TUNE_POWER_W = 10
    # ... bestehender Code aus _on_tune_clicked(True) Pfad
    # (Watchdog, set_frequency, set_tx_antenna ANT1, tune_on,
    #  Statusbar, QTimer.singleShot(duration_s * 1000, _tune_stop))


# ─── ui/qso_panel.py ───
class QSOPanel(QWidget):
    eo_tag_visibility_changed = Signal(bool)
    ant_label_visibility_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._qso_count = 0
        self._entries: list[dict] = []  # P95: SOT für Re-Render
        self._show_eo_tag: bool = True
        self._show_ant_label: bool = True
        self._last_omni_tx_even = None
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(30_000)
        self._cleanup_timer.timeout.connect(self._auto_trim_by_age)
        self._cleanup_timer.start()

    def add_tx(self, message, ant_label="", tx_even=None,
               slot_start_ts=None, omni_remaining=None):
        # bisheriges Slot-Resolving bleibt
        if slot_start_ts is None or tx_even is None:
            now = time.time()
            slot = getattr(self, '_cycle_duration', 15.0)
            slot_start_ts = now - (now % slot)
            tx_even = int(slot_start_ts / slot) % 2 == 0
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
        tag = "[E]" if tx_even else "[O]"
        entry = {"kind": "tx", "ts": time.time(), "utc": utc, "tag": tag,
                 "tx_even": tx_even, "message": message,
                 "ant_label": ant_label, "omni_remaining": omni_remaining}
        self._entries.append(entry)
        self._render_entry(entry)

    # add_rx, add_listening, add_qso_complete, add_timeout, add_info
    # analog — append + render_entry

    def _render_entry(self, e: dict):
        kind = e["kind"]
        if kind == "tx":
            tag_str = f"{e['tag']} " if self._show_eo_tag else ""
            line = f"{e['utc']} {tag_str}→ Sende {e['message']}"
            if e.get("omni_remaining") is not None:
                line = f"{line} ↻{e['omni_remaining']}"
                # P29 OMNI-Parity-Trennung (Tracker hier)
                if (self._last_omni_tx_even is not None
                        and self._last_omni_tx_even != e['tx_even']):
                    self._append_colored("", "#000000")
                self._last_omni_tx_even = e['tx_even']
                tx_color = "#E09600" if e['tx_even'] else "#FFAA00"
            else:
                tx_color = "#FFAA00"
            ant = e.get("ant_label", "")
            if ant and self._show_ant_label:
                self._append_two_color(line, tx_color, f" {ant}", "#888888")
            else:
                self._append_colored(line, tx_color)
        elif kind == "rx":
            tag_str = f"{e['tag']} " if self._show_eo_tag else ""
            line = f"{e['utc']} {tag_str}← Empf. {e['message']}"
            ant = e.get("ant_label", "")
            if ant and self._show_ant_label:
                self._append_two_color(line, "#44BBFF",
                                       f" {ant}", "#888888")
            else:
                self._append_colored(line, "#44BBFF")
        elif kind == "listening":
            tag_str = f"{e['tag']} " if self._show_eo_tag else ""
            self._append_colored(
                f"{e['utc']} {tag_str}← Horche …", "#666666")
        elif kind == "complete":
            self._append_colored(
                f"       ✓ QSO mit {e['their_call']} komplett", "#44FF44")
            self._append_colored("─" * 30, "#333333")
        elif kind == "timeout":
            self._append_colored(
                f"       ✗ {e['their_call']} — Timeout", "#FF4444")
            self._append_colored("─" * 30, "#333333")
        elif kind == "info":
            # Bestehende Symbol-Auto-Detect-Logik aus add_info
            self._render_info(e["text"])

    def _rerender_all(self):
        # Scroll-Position merken (B-F6)
        sb = self.log_view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 5
        self.log_view.clear()
        self._last_omni_tx_even = None  # Tracker reset
        for e in self._entries:
            self._render_entry(e)
        if at_bottom:
            sb.setValue(sb.maximum())

    def _auto_trim_by_age(self):
        # B-F2: _entries selbst trimmen statt _block_timestamps
        cutoff = time.time() - 300  # 5 min
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["ts"] >= cutoff]
        if len(self._entries) < before:
            self._rerender_all()

    def _on_log_context(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(self._MENU_STYLE)
        a_eo = menu.addAction("Even/Odd-Tag anzeigen")
        a_eo.setCheckable(True)
        a_eo.setChecked(self._show_eo_tag)
        a_eo.triggered.connect(self._toggle_eo_tag)
        a_ant = menu.addAction("Antennen-Anzeige")
        a_ant.setCheckable(True)
        a_ant.setChecked(self._show_ant_label)
        a_ant.triggered.connect(self._toggle_ant_label)
        # Standard-Aktionen anhängen (Copy etc.)
        std = self.log_view.createStandardContextMenu()
        actions = std.actions()
        if actions:
            menu.addSeparator()
            for act in actions:
                menu.addAction(act)
        menu.exec(self.log_view.mapToGlobal(pos))

    def _toggle_eo_tag(self, show: bool):
        self._show_eo_tag = show
        self._rerender_all()
        self.eo_tag_visibility_changed.emit(show)

    def _toggle_ant_label(self, show: bool):
        self._show_ant_label = show
        self._rerender_all()
        self.ant_label_visibility_changed.emit(show)


# ─── ui/main_window.py — Persistierung ───
# Nach control_panel + qso_panel angelegt:
self.qso_panel._show_eo_tag = self.settings.get("qso_show_eo_tag", True)
self.qso_panel._show_ant_label = self.settings.get("qso_show_ant_label", True)
self.qso_panel.eo_tag_visibility_changed.connect(
    lambda v: self._save_qso_setting("qso_show_eo_tag", v))
self.qso_panel.ant_label_visibility_changed.connect(
    lambda v: self._save_qso_setting("qso_show_ant_label", v))

def _save_qso_setting(self, key: str, value: bool):
    self.settings.set(key, value)
    try:
        self.settings.save()
    except OSError as e:
        print(f"[P95] settings.save fehlgeschlagen: {e}")
```

## Tests (V2 erweitert)

- **A-T1**: btn_tune Kontext-Menü zeigt 3 Actions (10s/15s/20s)
- **A-T2**: Klick „TUNE 20s" → tune_override_requested.emit(20)
- **A-T3**: _on_tune_override(20) ohne aktive TUNE → btn checked + _tune_start(20)
- **A-T4**: _on_tune_override(20) bei aktiver TUNE → btn off + _tune_stop(None)
- **A-T5**: _tune_start(20) ruft Pipeline mit 20s QTimer
- **A-T6**: Setting `tune_duration_s` unverändert nach Override
- **A-T7**: _on_tune_override(7) (nicht in Whitelist) → no-op
- **A-T8**: _on_tune_clicked(True) ohne Override nutzt Setting (Regression)
- **B-T1**: add_rx ohne ant_label → entry "rx" mit ant_label=""
- **B-T2**: add_tx mit ant_label → entry "tx" mit ant_label gesetzt
- **B-T3**: _show_eo_tag=False → _render_entry rendert ohne [E]/[O]
- **B-T4**: _show_ant_label=False → _render_entry rendert ohne (ANT...)
- **B-T5**: _toggle_eo_tag(False) → _rerender_all + Signal emit
- **B-T6**: _auto_trim_by_age trimmt alte _entries (> 5 min) + rerender
- **B-T7**: Kontextmenü auf log_view zeigt EO + Ant + Separator + Copy
- **B-T8**: Scroll-Position bei _rerender_all bleibt erhalten (at_bottom)
- **B-T9**: 6 Entry-Typen alle korrekt gerendert
- **B-T10**: Re-Render reset `_last_omni_tx_even` damit OMNI-Parity konsistent

## Offene Fragen für DeepSeek-R1

1. Variante B (Re-Render) Architektur — gibt's einen Edge-Case bei
   `_render_entry` für OMNI-Parity-Trennung den ich übersehe? P29
   verlässt sich auf sequential add_tx-Aufrufe. Bei Re-Render rekonstruiere
   ich `_last_omni_tx_even` durchlaufend — ist das sicher?

2. Ist `log_view.createStandardContextMenu()` sicher anbindbar an
   Custom-Menu, oder gibt's Ownership-Probleme (QMenu Parent)?

3. `_auto_trim_by_age` zu `_entries`-basiert umstellen — kollidiert
   das mit `_block_timestamps`-Code (gibt's noch andere Caller)?

4. Settings-Save-Pattern wie P32 (try/except OSError) übernommen ✓ —
   gibt's noch andere Failure-Modi (Disk-Full beim Schreiben von
   `qso_show_eo_tag` = True)?

5. Hardware: Override-TUNE durchläuft `_tune_start` → 10W FEST + ANT1
   verriegelt ✓ — bestätige?

6. Final-Check: edge cases, missing tests, Performance-Issues?
