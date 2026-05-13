# Bundle B' — V3: RX-Panel-Spalten-Persist + QSO-Komplett-Reihenfolge

**V3 nach R1-Review** (2 KP + 2 S + 2 K + 2 H Findings).
Code-Plan mit exakten Datei:Zeile-Anweisungen.

## R1-Findings-Bilanz

| Finding | Schwere | Aktion in V3 |
|---|---|---|
| KP-1: `visual.emit` darf NICHT in TX_73_COURTESY-Send-Pfad | 🔴 Bug | **Angenommen** — V2-Text war widerspruechlich, V3 explizit |
| KP-2: WAIT_73-Timeout-Pfad braucht explizit `visual.emit` | 🔴 Bug | **Angenommen** — V3 zeigt exakte Code-Stelle Z.317 |
| S-1: RxPanel.__init__ vollstaendiger Konstruktor | 🟠 Code-Snippet | **Angenommen** — V3 zeigt komplette Stelle |
| S-2: Hypothetischer Doppelschutz Z.658 auch `visual.emit` | 🟠 Konsistenz | **Angenommen** — minimaler Aufwand |
| K-1: 1-Signal mit `visual_only`-Parameter | 🟡 KISS | **Abgelehnt** mit Begruendung (unten) |
| K-2: `rx_panel_visible_cols` statt `hidden_cols` | 🟡 Konvention | **Abgelehnt** mit Begruendung (unten) |
| H-1: RxPanel-Init-Aufruf in MainWindow | 🔘 Hinweis | **Angenommen** — V3 zeigt vollstaendig |
| H-2: Atomare Commits — moeglich | 🔘 Bestaetigt | Geplant 3 atomare Commits |

### Abgelehnte Findings — Begruendung

**K-1 (1-Signal mit Parameter abgelehnt):**

R1 schlug `qso_confirmed.emit(qso_data, visual_only=True)` vor.
- Aktuelle Signal-Signatur ist `Signal(object)` mit 1 Param.
- Bestehende Subscriber (`_on_qso_confirmed`) wuerden Signatur-Aenderung
  brauchen.
- Slot-Aufruf-Konvention im restlichen Repo: 1 Signal pro semantischer
  Aktion (siehe `qso_complete`, `qso_timeout`, `qso_confirmed`,
  `tx_slot_for_partner`).
- 2 Signale = klare Semantik: „QSO visuell bestaetigt" vs „QSO operativ
  fertig abgewickelt".
- KISS auf falscher Ebene — Signal-Anzahl ist nicht der teure Teil,
  Verstaendnis ist es.
- **Bleibt:** 2 separate Signale `qso_confirmed_visual` +
  `qso_confirmed`.

**K-2 (`rx_panel_visible_cols` abgelehnt):**

R1 schlug `rx_panel_visible_cols` mit Default `[0..8 ohne 6]` vor.
- Default `[]` mit `hidden_cols`-Semantik = „alles sichtbar". Intuitiv.
- Default `[0,1,2,3,4,5,7,8]` (alle ausser COL_MSG) mit `visible_cols`-
  Semantik = hardcoded Liste. Bei COL_COUNT-Aenderung (Spalte hinzu)
  braeche das.
- `country_filter` ist NICHT analog — das ist eine User-Wahl, kein
  Default-Zustand.
- **Bleibt:** `rx_panel_hidden_cols: list[int]`, Default `[]`.

## P32 — RX-Panel-Spalten-Persist (V3-Endzustand)

### Code-Aenderungen

**Datei 1: `ui/rx_panel.py`**

Z.50-52 (Signals):
```python
rx_toggled = Signal(bool)
country_filter_changed = Signal(list)
hidden_cols_changed = Signal(list)  # P32: persistierte Spalten-Sichtbarkeit
```

Z.53-67 (Konstruktor + Apply-Phase) — **S-1 Vollstaendige Stelle**:
```python
def __init__(self, my_call: str = "DA1MHH", my_grid: str = "JO31",
             country_filter: list = None,
             hidden_cols: list[int] = None):
    super().__init__()
    self._my_call = my_call
    self._my_grid = my_grid
    self._cycle_message_count = 0
    self._sort_mode = "time"
    self._rx_active = True
    self._country_filter: set = set(country_filter or [])
    self._ant_filter: int = 0
    self._active_call: str = ""
    self._qso_log = None
    self._locator_db = None
    # P32: defensive Filterung von ungueltigen Settings-Werten
    valid_hidden = []
    for col in (hidden_cols or []):
        if isinstance(col, int) and 0 <= col < COL_COUNT and col != COL_MSG:
            valid_hidden.append(col)
    self._hidden_cols: set = set(valid_hidden)
    self._setup_ui()
    # P32: Spalten ausblenden NACH _setup_ui (table existiert dann)
    for col in self._hidden_cols:
        self.table.setColumnHidden(col, True)
```

Z.506-512 (`_toggle_column`):
```python
def _toggle_column(self, col: int, hide: bool):
    """Spalte ein-/ausblenden und Zustand merken."""
    if hide:
        self._hidden_cols.add(col)
    else:
        self._hidden_cols.discard(col)
    self.table.setColumnHidden(col, hide)
    # P32: persistieren via Signal an MainWindow
    self.hidden_cols_changed.emit(sorted(self._hidden_cols))
```

**Datei 2: `ui/main_window.py`**

Z.524 (RXPanel-Instantiierung):
```python
self.rx_panel = RXPanel(
    my_call=self.settings.callsign,
    my_grid=self.settings.locator,
    country_filter=self.settings.get("country_filter", []),
    hidden_cols=self.settings.get("rx_panel_hidden_cols", []),  # P32 NEU
)
```

Z.652-654 (Signal-Verbindungen, neuer Block):
```python
self.rx_panel.station_clicked.connect(self._on_station_clicked)
self.rx_panel.rx_toggled.connect(self._on_rx_panel_toggled)
self.rx_panel.country_filter_changed.connect(self._on_country_filter_changed)
self.rx_panel.hidden_cols_changed.connect(self._on_rx_hidden_cols_changed)  # P32 NEU
```

Neuer Slot (irgendwo in `main_window.py`, analog
`_on_country_filter_changed`):
```python
def _on_rx_hidden_cols_changed(self, cols: list):
    """P32: RX-Panel-Spalten-Sichtbarkeit persistieren."""
    self.settings.set("rx_panel_hidden_cols", cols)
    self.settings.save()
```

### Akzeptanzkriterien P32

- **AK1:** Spalten via Rechtsklick ausblenden → App quit/start → bleiben
  ausgeblendet.
- **AK2:** Erster Start ohne Settings-Key → alle 9 Spalten sichtbar.
- **AK3:** Settings mit ungueltigen Werten (`[99]`, `[-1]`, `["foo"]`,
  `[6]`) → Default-Filter im Konstruktor entfernt alle, kein Crash.
- **AK4:** `COL_MSG=6` darf nicht versteckt werden — Konstruktor-Filter
  wirft `6` raus.
- **AK5:** Mehrfaches Toggeln → mehrere `settings.save()`-Aufrufe → kein
  User-spuerbares Lag (JSON-File < 5 KB).

## P33 — QSO-Komplett-Reihenfolge (V3-Endzustand)

### Code-Aenderungen

**Datei 3: `core/qso_state.py`**

Z.101 (Signals — neues davor einfuegen):
```python
qso_confirmed_visual = Signal(object)  # P33: ✓-Anzeige im UI sofort bei 73-Empfang
qso_confirmed = Signal(object)         # 73 empfangen → ✓ anzeigen (BLEIBT — alle Slot-Operationen)
```

Z.313-319 (`on_cycle_end` WAIT_73-Timeout) — **KP-2 Fix**:
```python
if self.state == QSOState.WAIT_73:
    self.qso.timeout_cycles += 1
    if self.qso.timeout_cycles >= 3:
        print(f"[QSO] WAIT_73 Timeout — kein 73 empfangen, QSO trotzdem komplett")
        self.qso_confirmed_visual.emit(self.qso)  # P33 NEU
        self.qso_confirmed.emit(self.qso)
        self._resume_cq_if_needed()
    return
```

Z.483-489 (`on_message_sent` TX_73_COURTESY) — **KP-1 KEIN `visual.emit`**:
```python
elif self.state == QSOState.TX_73_COURTESY:
    # P1.10 Fix (v0.95.4): Courtesy-73 fertig gesendet.
    # qso_complete wurde bereits in TX_RR73 (oben) gefeuert — hier nur
    # qso_confirmed (UI „QSO ✓") + CQ resumen.
    # P33 (v0.97.14): qso_confirmed_visual wurde bereits beim
    # 73-Empfang in on_message_received gefeuert — KEIN visual.emit
    # hier (sonst Doppel-Eintrag im QSO-Panel).
    self._dbg.log("TX", "Courtesy-73 fertig → qso_confirmed + resume_cq")
    self.qso_confirmed.emit(self.qso)
    self._resume_cq_if_needed()
```

Z.638-659 (`on_message_received` is_73-Branch) — **Haupt-Fix P33**:
```python
elif msg.is_73 and msg.caller == self.qso.their_call:
    # 73 empfangen — QSO ist semantisch bestaetigt.
    # P33 (v0.97.14): visual.emit SOFORT damit ✓ vor naechstem CQ
    # im QSO-Panel erscheint. Full-Emit nach Courtesy-Send.
    self.qso_confirmed_visual.emit(self.qso)
    if not self.qso.courtesy_73_sent:
        self.qso.courtesy_73_sent = True
        tx_msg = f"{self.qso.their_call} {self.my_call} 73"
        self._dbg.log("TX", f"Courtesy-73 für {msg.caller}: '{tx_msg}'")
        # State VOR Slot-Signal setzen ...
        self._set_state(QSOState.TX_73_COURTESY)
        self.tx_slot_for_partner.emit(msg)
        self.send_message.emit(tx_msg)
        # qso_confirmed (full) feuert in on_message_sent nach Courtesy-Send
    else:
        # Hypothetischer Doppelschutz (S-2): visual schon oben gefeuert,
        # hier nur full + resume.
        self.qso_confirmed.emit(self.qso)
        self._resume_cq_if_needed()
```

**Datei 4: `ui/main_window.py`**

Z.676 (Signal-Connect) — neue Zeile einfuegen:
```python
self.qso_sm.qso_confirmed_visual.connect(self._on_qso_confirmed_visual)  # P33 NEU
self.qso_sm.qso_confirmed.connect(self._on_qso_confirmed)
```

**Datei 5: `ui/mw_qso.py`**

Z.492 (neuer Slot vor `_on_qso_confirmed`):
```python
@Slot(object)
def _on_qso_confirmed_visual(self, qso_data):
    """P33: Schnell-Pfad bei 73-Empfang.

    Nur UI-Update (✓ QSO komplett im Panel) — alle anderen
    Operationen (logbook.refresh, OMNI-Resume, Auto-Hunt) laufen
    weiter im _on_qso_confirmed-Slot nach Courtesy-73-Send.
    """
    self.qso_panel.add_qso_complete(qso_data.their_call)
```

Z.492-523 (`_on_qso_confirmed` modifiziert — `add_qso_complete` RAUS):
```python
@Slot(object)
def _on_qso_confirmed(self, qso_data):
    """73 empfangen UND Courtesy-Send fertig (oder WAIT_73-Timeout).

    P33 (v0.97.14): add_qso_complete RAUS — wurde bereits in
    _on_qso_confirmed_visual gefeuert. Hier alle anderen Operationen
    die NICHT vor Courtesy-Send laufen duerfen (OMNI-Resume etc.).
    """
    from core.debug_log import debug_log as _dbg
    import time as _t
    _t0 = _t.time()
    _dbg("QSO-CONF", f"START call={qso_data.their_call}")

    # add_qso_complete bereits in _on_qso_confirmed_visual — kein Aufruf hier!

    # Logbuch aktualisieren (neues QSO wurde in ADIF geschrieben)
    _t_step = _t.time()
    self.qso_panel.logbook.refresh()
    _dbg("QSO-CONF", f"logbook.refresh dt={_t.time()-_t_step:.3f}s")

    # P1.14 W6: Auto-Hunt nach erfolgreichem manuellem QSO freigeben
    if self._auto_hunt.active:
        self._auto_hunt.on_manual_qso_end()
    # CQ-Modus läuft weiter — visuell bestätigen
    if self.qso_sm.cq_mode:
        self.control_panel.set_cq_active(True)
        self.qso_panel.add_info("CQ-Modus läuft weiter...")
    # P2.OMNI-REDESIGN v4.0: OMNI nach 73-Empfang/Timeout/Courtesy-fertig resumen
    _t_step = _t.time()
    self._maybe_resume_omni()
    _dbg("QSO-CONF", f"_maybe_resume_omni dt={_t.time()-_t_step:.3f}s")
    _dbg("QSO-CONF", f"END total dt={_t.time()-_t0:.3f}s")
```

### Akzeptanzkriterien P33

- **AK1:** `✓ QSO mit X komplett` erscheint IM SELBEN Slot wie der
  `← Empf. X 73`-Eintrag im QSO-Panel (vor naechstem CQ).
- **AK2:** Courtesy-73-Send laeuft unveraendert weiter.
- **AK3:** `qso_confirmed_visual` feuert genau 1× pro QSO bei
  73-Empfang in WAIT_73 ODER bei WAIT_73-Timeout (3 Zyklen).
- **AK4:** `qso_confirmed` feuert genau 1× pro QSO am
  Courtesy-Send-Ende ODER bei WAIT_73-Timeout (direkt nach visual).
- **AK5:** `add_qso_complete` wird genau 1× pro QSO aufgerufen
  (visual-Slot triggert, full-Slot ruft nicht mehr) — kein
  Doppel-Eintrag im Panel.
- **AK6:** `_maybe_resume_omni()` laeuft NICHT vor Courtesy-Send
  (Auto-Hunt-Reset, CQ-Status-Update auch nicht).
- **AK7:** Hypothetischer Doppelschutz Z.658-Pfad funktioniert
  korrekt: visual + full direkt nacheinander, kein Crash.
- **AK8:** Bestehende P1.10-Tests + andere QSO-Flow-Tests bleiben
  gruen.

## Tests

`tests/test_p33_qso_complete_order.py` NEU mit 6 Tests:

- **T1:** `test_qso_confirmed_visual_fires_on_73_received_in_wait_73` —
  Setup State WAIT_73, simuliere msg.is_73 → visual emit 1×, full emit 0×
- **T2:** `test_qso_confirmed_full_fires_after_courtesy_73_sent` —
  nach T1, simuliere `on_message_sent` mit State TX_73_COURTESY →
  full emit 1×, KEIN 2. visual
- **T3:** `test_wait_73_timeout_emits_visual_and_full_in_order` —
  3× `on_cycle_end` in WAIT_73 → visual emit 1× DANN full emit 1×
- **T4:** `test_add_qso_complete_called_exactly_once_per_qso` — Mock
  qso_panel.add_qso_complete, durchlaufe vollen 73-Empfang +
  Courtesy + on_message_sent → genau 1× Call
- **T5:** `test_omni_resume_not_triggered_on_visual_emit` — Mock
  `_maybe_resume_omni`, simuliere visual emit → 0 Aufrufe (erst bei
  full)
- **T6:** `test_hypothetic_double_protection_path` — Setup State
  WAIT_73 mit `courtesy_73_sent=True`, simuliere weiteres is_73 →
  visual emit 1× + full emit 1× + resume_cq aufgerufen

`tests/test_p32_rx_panel_persist.py` NEU mit 5 Tests:

- **T1:** `test_hidden_cols_loaded_from_settings` — RxPanel mit
  `hidden_cols=[2, 4]` → COL_DT + COL_LAND hidden
- **T2:** `test_invalid_hidden_cols_filtered_out` — `hidden_cols=[6,
  99, -1, "foo", 2]` → nur COL_DT (2) versteckt
- **T3:** `test_toggle_emits_hidden_cols_signal` — `_toggle_column(2,
  True)` → `hidden_cols_changed` Signal mit `[2]` empfangen
- **T4:** `test_main_window_persists_on_signal` — MainWindow-Slot
  empfaengt Signal → settings.set + settings.save aufgerufen
- **T5:** `test_default_no_settings_all_visible` — `hidden_cols=None`
  → 9 Spalten alle visible

## Backup-Strategie

`Appsicherungen/2026-05-13_v0.97.13_vor_bundle_b/` mit:
- `ui/rx_panel.py`
- `ui/main_window.py`
- `ui/mw_qso.py`
- `core/qso_state.py`

(4 Files — `config/settings.py` wird NICHT angefasst, nur generische
get/set ueber bestehende API.)

## Atomare Commits

1. **C1: P32 RX-Panel-Spalten-Persist** — `ui/rx_panel.py` +
   `ui/main_window.py` + `tests/test_p32_rx_panel_persist.py`
2. **C2: P33 QSO-Komplett-Reihenfolge** — `core/qso_state.py` +
   `ui/mw_qso.py` + `ui/main_window.py` (1 Zeile Signal-Connect) +
   `tests/test_p33_qso_complete_order.py`
3. **C3: APP_VERSION 0.97.14 + Bundle-B-Doku** — `main.py` +
   HISTORY/HANDOFF/CLAUDE/TODO

**Tests-Erwartung:** 1192 → 1203 (+11: 5 P32 + 6 P33).

**APP_VERSION:** 0.97.13 → 0.97.14 (Bugfix-Bundle).

## Field-Test-Punkte fuer Mike

- **F1:** Spalten ausblenden, App-Quit, App-Start → bleiben
  ausgeblendet ✓
- **F2:** Bei QSO: `← Empf. X 73` und `✓ QSO mit X komplett`
  erscheinen im SELBEN Slot, BEVOR die naechste OMNI-CQ-Zeile
- **F3:** Nach Courtesy-73-Send: OMNI resumed wie heute, kein
  Doppel-Eintrag
- **F4:** WAIT_73-Timeout (Gegenstation sendet nie 73): nach 3 Slots
  trotzdem `✓ QSO komplett` ohne Hang

## Status

V3 fertig. Bereit fuer Mike-Freigabe und Code.
