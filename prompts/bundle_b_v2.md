# Bundle B' — V2 (Self-Review): RX-Panel-Spalten + QSO-Komplett-Reihenfolge

V1 → V2 nach Self-Review aus „frischer-KI"-Perspektive.

## Kritische Befunde gegenueber V1

### Befund-1 (P33 KRITISCH): V1-Variante-A bricht OMNI-Resume

**V1 schlug vor:** `qso_confirmed.emit` SOFORT bei 73-Empfang
statt nach Courtesy-73-Send.

**Was V1 uebersehen hat:** `ui/mw_qso._on_qso_confirmed`
(Z.492-523) macht VIEL MEHR als nur `add_qso_complete`:

```python
def _on_qso_confirmed(self, qso_data):
    self.qso_panel.add_qso_complete(qso_data.their_call)  # UI
    self.qso_panel.logbook.refresh()                       # UI
    if self._auto_hunt.active:
        self._auto_hunt.on_manual_qso_end()                # Auto-Hunt
    if self.qso_sm.cq_mode:
        self.control_panel.set_cq_active(True)             # UI
        self.qso_panel.add_info("CQ-Modus läuft weiter...")
    self._maybe_resume_omni()                              # ⛔ OMNI!
```

**Folge bei Variante-A:** `_maybe_resume_omni()` wuerde im SELBEN Slot
laufen wo gerade Courtesy-73 als naechster TX vorbereitet wird → OMNI
ueberschreibt potenziell die Courtesy-Sequenz oder schickt ein
falsches CQ. Plus Auto-Hunt-Reset zu frueh.

**Korrektur fuer V2: Variante-E (2-Signal-Split):**

```python
# core/qso_state.py

# Neues Signal NEBEN dem bestehenden:
qso_confirmed_visual = Signal(object)  # NEU: ✓-Anzeige im UI sofort
qso_confirmed = Signal(object)          # BLEIBT: alle anderen Slot-Operationen

# In on_message_received bei msg.is_73 + State == WAIT_73:
self.qso_confirmed_visual.emit(self.qso)  # ✓ sofort sichtbar
if not self.qso.courtesy_73_sent:
    self.qso.courtesy_73_sent = True
    tx_msg = f"{self.qso.their_call} {self.my_call} 73"
    self._set_state(QSOState.TX_73_COURTESY)
    self.tx_slot_for_partner.emit(msg)
    self.send_message.emit(tx_msg)
    # qso_confirmed (full) feuert in on_message_sent nach Courtesy-Send
else:
    # Hypothetischer Doppelschutz — sollte nie greifen
    self.qso_confirmed.emit(self.qso)
    self._resume_cq_if_needed()
```

Plus an den anderen `qso_confirmed.emit`-Stellen jeweils auch
`qso_confirmed_visual.emit` davor:

- `qso_state.py:317` WAIT_73-Timeout (3× ohne 73 → trotzdem ✓)
- `qso_state.py:488` on_message_sent TX_73_COURTESY (Courtesy fertig)
- `qso_state.py:658` Hypothetischer Doppelschutz

ABER: an Stelle Z.317 (WAIT_73-Timeout) ist `qso_confirmed_visual` und
`qso_confirmed` quasi gleichzeitig — der Slot ist semantisch ja
auch derselbe. Loesung: beide direkt nacheinander emitten oder eine
Helper-Methode `_emit_qso_done(visual_only: bool)`.

```python
# ui/mw_qso.py:

@Slot(object)
def _on_qso_confirmed_visual(self, qso_data):
    """Schnell-Pfad: nur UI-Update bei 73-Empfang."""
    self.qso_panel.add_qso_complete(qso_data.their_call)

@Slot(object)
def _on_qso_confirmed(self, qso_data):
    """Voll-Pfad: alle anderen Operationen (nach Courtesy-Send)."""
    # add_qso_complete RAUS — wurde schon via _visual gefeuert
    self.qso_panel.logbook.refresh()
    if self._auto_hunt.active:
        self._auto_hunt.on_manual_qso_end()
    if self.qso_sm.cq_mode:
        self.control_panel.set_cq_active(True)
        self.qso_panel.add_info("CQ-Modus läuft weiter...")
    self._maybe_resume_omni()
```

**Subtilitaet:** `add_info("CQ-Modus läuft weiter...")` ist auch UI —
soll das mit ins Visual-Update? Mike's Erwartung im Screenshot zeigt
nur `✓ QSO komplett` zwischen RX-73 und naechstem CQ — das `add_info`
ist optional und kommt heute am Slot-Ende. Lasse ich im Voll-Pfad.

**Doppel-Emit-Schutz Pflicht:**

- Wenn `qso_confirmed_visual` UND danach `qso_confirmed` beide fuer
  dasselbe QSO feuern → kein `add_qso_complete` 2× (Voll-Pfad hat
  add_qso_complete RAUS).
- Wenn Timeout-Pfad (Z.317) `qso_confirmed_visual` + `qso_confirmed`
  beide direkt feuert → 1× add_qso_complete (visual) + 1× Rest (full).
  Ok.
- Wenn `is_73` empfangen wird obwohl State nicht WAIT_73 (Z.502 RR73/73
  nach Timeout/CQ) → KEIN emit, wird ignoriert. Ok.

### Befund-2 (P32): Settings-Objekt nicht direkt an RxPanel

V1 hat angenommen Settings sei in RxPanel verfuegbar. Code zeigt:
- `RxPanel.__init__` bekommt `my_call`, `my_grid`, `country_filter`
- KEIN Settings-Objekt
- `country_filter` wird als Wert reingereicht, nicht als Settings-Referenz

**Optionen V2:**

A) Settings-Referenz reinreichen (RxPanel.__init__ neuer Param
   `settings=None`).
B) Liste reinreichen + Callback raus (`hidden_cols_changed`-Signal).
C) Init nur Werte, Save ueber `main_window`-Slot.

**V2-Empfehlung: Variante C — Signal-basiert wie heute country_filter:**

```python
# ui/rx_panel.py

class RXPanel(QWidget):
    rx_toggled = Signal(bool)
    country_filter_changed = Signal(list)
    hidden_cols_changed = Signal(list)  # NEU

    def __init__(self, ..., hidden_cols: list[int] = None):
        ...
        self._hidden_cols: set = set(hidden_cols or [])
        self._setup_ui()
        # ── Spalten aus Settings anwenden (Phase 2 wegen header init) ──
        for col in self._hidden_cols:
            if 0 <= col < COL_COUNT and col != COL_MSG:
                self.table.setColumnHidden(col, True)

    def _toggle_column(self, col: int, hide: bool):
        if hide:
            self._hidden_cols.add(col)
        else:
            self._hidden_cols.discard(col)
        self.table.setColumnHidden(col, hide)
        # P32: Signal an MainWindow zum Persistieren
        self.hidden_cols_changed.emit(sorted(self._hidden_cols))
```

```python
# ui/main_window.py _setup_ui (Z.524):

self.rx_panel = RXPanel(
    my_call=self.settings.callsign,
    my_grid=self.settings.locator,
    country_filter=self.settings.get("country_filter", []),
    hidden_cols=self.settings.get("rx_panel_hidden_cols", []),  # NEU
)

# in _connect_signals():
self.rx_panel.hidden_cols_changed.connect(self._on_rx_hidden_cols_changed)

# Neuer Slot:
def _on_rx_hidden_cols_changed(self, cols: list):
    self.settings.set("rx_panel_hidden_cols", cols)
    self.settings.save()
```

**Vorteil C:** Konsistent mit `country_filter`-Pattern (Signal +
Settings-Speichern in MainWindow), kein Settings-Singleton-Import in
RxPanel, lokal getrennt.

### Befund-3 (P32 Spalten-Default-Wert)

Aktuell `_hidden_cols: set = set()` heisst „alle 9 Spalten sichtbar".
Falls der Default je auf z.B. `[COL_SLOT]` aendern soll, brauche ich
eine Migration. Aktuell nicht noetig — Default `[]` wird in Settings
gespeichert, beim Lesen kommt Liste zurueck.

Edge-Case: Was wenn Settings veraltete Spalten-Indices haben
(z.B. wenn COL_COUNT mal von 9 auf 10 erweitert wird)?

→ Filter im Init: `if 0 <= col < COL_COUNT and col != COL_MSG`. Schoenrund.

### Befund-4 (P32 Save-Performance)

V1 schlug vor: `settings.save()` bei jedem `_toggle_column`-Aufruf.
Heute speichert Settings als JSON-File-Save. Bei jedem User-Klick
1× Disk-Write — vernachlaessigbar (KB-File).

Aber: koennte der User in den Settings via Rechtsklick-Menue mehrere
Spalten in einer Sitzung toggeln? Ja klar. Acht Toggle-Klicks = acht
JSON-Writes. Trotzdem < 1ms Performance-Effekt insgesamt. OK.

### Befund-5 (P33 Test-Setup `qso_confirmed_visual`)

Bestehende Tests verbinden moeglicherweise `qso_confirmed` und
erwarten Aufruf nach Courtesy-Send-Zeitpunkt. Mit Variante-E:
- `qso_confirmed_visual` wird bei 73-Empfang gefeuert
- `qso_confirmed` BLEIBT bei Courtesy-Send-Zeitpunkt

Tests die explizit auf `qso_confirmed` nach 73-Empfang testen wuerden
brechen — aber das war zuvor schon der Fall (Logik kam erst nach
Courtesy). Realistisch: kein bestehender Test prueft genau das.

Neue Tests:
- `test_p33_qso_confirmed_visual_fires_on_73_received` — 73 in WAIT_73
  empfangen → `qso_confirmed_visual` 1× gefeuert
- `test_p33_qso_confirmed_full_fires_after_courtesy_sent` — bestehender
  Pfad bleibt
- `test_p33_no_double_visual_emit_on_timeout` — WAIT_73-Timeout-Pfad
  emittiert visual + full genau 1× jeweils
- `test_p33_visual_emit_does_not_resume_omni` — visual Emit triggert
  KEIN OMNI-Resume (sondern erst `qso_confirmed`-full)

### Befund-6 (P32 COL_MSG Bug-Schutz)

V1 hatte AK4: „`COL_MSG=6` darf nicht versteckt werden (nicht
toggelbar)". Im aktuellen Code `_TOGGLEABLE` (Z.485-488) enthaelt
COL_MSG=6 schon nicht — also Default-Verhalten ok. Beim Load aus
Settings aber: wenn User manuell `rx_panel_hidden_cols: [6]` ins JSON
schreibt, wuerde die Message-Spalte versteckt + nicht mehr toggelbar →
toter Zustand. Filter `col != COL_MSG` im Load schuetzt davor.

## Aktualisierte Akzeptanzkriterien

### P32 — RX-Panel-Spalten-Persist

- AK1: Spalten via Rechtsklick ausblenden → App quit/start → bleiben
  ausgeblendet.
- AK2: Erster Start ohne Settings-Key → alle 9 Spalten sichtbar.
- AK3: Settings mit ungueltigen Werten (`[99]`, `[-1]`, `["foo"]`) →
  kein Crash, keine versteckte Spalte. Defensive im Load-Filter.
- AK4: `COL_MSG=6` darf nicht versteckt werden — Load-Filter wirft
  `[6]` raus.
- AK5: 4× toggeln in Folge → 4× settings.save() → kein User-spuerbares
  Lag (~1ms pro Save).

### P33 — QSO-Komplett-Reihenfolge

- AK1: `✓ QSO mit X komplett` erscheint IM SELBEN Slot wie der
  `← Empf. X 73`-Eintrag im QSO-Panel (vor naechstem CQ).
- AK2: Courtesy-73-Send laeuft unveraendert weiter — kein
  Funktions-Verlust.
- AK3: `qso_confirmed_visual` feuert genau 1× pro QSO bei 73-Empfang.
- AK4: `qso_confirmed` feuert genau 1× pro QSO am Courtesy-Send-Ende
  ODER bei WAIT_73-Timeout (3× ohne 73).
- AK5: WAIT_73-Timeout-Pfad funktioniert: 3 Zyklen ohne 73 →
  `qso_confirmed_visual` + `qso_confirmed` direkt nacheinander.
- AK6: `add_qso_complete` wird genau 1× pro QSO aufgerufen (kein
  Doppel-Eintrag im Panel).
- AK7: OMNI-Resume + Auto-Hunt-Reset + CQ-Status-Update laufen
  weiterhin am Courtesy-Send-Ende (NICHT bei 73-Empfang) — keine
  Reihenfolgen-Aenderung im operativen Flow.
- AK8: Bestehende P1.10-Tests + andere QSO-Flow-Tests bleiben gruen.

## Erweiterte Risiko-Liste fuer R1

- **R1-1 (P33):** Gibt es bisherige `qso_confirmed`-Subscriber ausser
  `_on_qso_confirmed`? grep zeigt nur 1 Subscriber. ✓
- **R1-2 (P33):** Bestehende `_emit_qso_done`-Helper-Idee — sinnvoll
  zur Vermeidung von dupliziertem `visual.emit + qso_confirmed.emit`-Code
  oder Overengineering?
- **R1-3 (P33):** Sollte `qso_confirmed_visual` ein eigener Slot-Name
  haben (`add_qso_complete_now`) oder bleibt das Signal-/Slot-Pattern
  konsistent?
- **R1-4 (P33):** Naming — `qso_confirmed_visual` vs
  `qso_visually_confirmed` vs `qso_done_received`. Mike-Erfahrung in
  Memory pruefen.
- **R1-5 (P32):** Settings-Init-Reihenfolge — wird RxPanel garantiert
  NACH Settings-Load erstellt? In `main_window.__init__` ja
  (Settings ist Konstruktor-Arg).
- **R1-6 (P32):** Heisst der Settings-Key `rx_panel_hidden_cols` oder
  besser `rx_panel_visible_cols`? Mit `hidden` ist Default `[]`
  intuitiv „alles sichtbar".
- **R1-7 (P32+P33):** Bundle-Strategie OK? Beide Bugs sind UI ohne
  Architektur-Wirkung, gemeinsames Akzeptanzkriterium nicht
  vermischt.

## V1 → V2 Aenderungen

- P33 Variante-A → **Variante-E (2-Signal-Split mit
  `qso_confirmed_visual`)**. Verhindert OMNI-Resume + Auto-Hunt-Reset
  vor Courtesy-Send.
- P32 Settings-Injection → **Signal-basiert wie country_filter**.
  Kein Settings-Import in RxPanel.
- Defensive Load-Filter fuer P32 inkl. `COL_MSG` und Range-Check.
- Tests von 7 auf 11 erweitert (4 spezifische P33-Tests fuer
  Doppel-Emit + OMNI-Race).

## Status

V2 bereit fuer R1-Review.
