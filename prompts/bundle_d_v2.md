# Bundle D — V2 Self-Review

V1: `prompts/bundle_d_v1.md`. Selfcheck VOR R1.

---

## A. Was V1 richtig macht

- 5 Punkte sauber separiert (A-E), keine Vermischung
- Code-Verifikation Schritt 0 hat den fehlenden Slot-Balken entlarvt
  (Mike vermutete „haben wir schon" — gibt's nicht)
- Trivial-Tweaks A/B sind klar separierbar von komplexerem C/D/E
- Slot-Parity-API existiert mehrfach, kann wiederverwendet werden

---

## B. Schwachstellen / Klärungsbedarf

### B1 — Even-Filter Konflikt mit `_was_cq` / QSO-Resume

Wenn Filter auf „Even" steht und ein Even-CQ-Slot wechselt zu Hunt-QSO,
wo TX in Odd-Slot fallen würde: was passiert?

→ FT8-Convention: wenn der Operator in Even-Slot CQ ruft, antwortet
ihm jemand in Odd. Der Filter darf das nicht zerschießen. Filter ist
nur **RX-Anzeige-Filter**, nicht TX-Slot-Filter.

→ **Klärung:** Filter wirkt NUR auf das RX-Panel (Anzeige), nicht auf
QSO/CQ/TX. R1-Antwort zu Q1 sollte das bestätigen.

### B2 — Slot-Balken-Konflikt mit FT4/FT2

Bundle-D heißt zwar „15s-Slot-Balken", aber FT4=7.5s und FT2=3.8s.
Der Balken muss `cycle_dur` auslesen, nicht hardcoded 15.

→ AC11/AC12 müssen `cycle_dur` aus `core/timing.py` lesen, nicht
„15" hardcoden. Lass mich AC korrigieren in V3.

### B3 — Even/Odd-Filter visuell vs. funktional

V1-AC6 fragt ob Stationen ausgeblendet oder ausgegraut werden. Wenn
ausgeblendet, kann der User keine Stationen vergleichen oder
nachjustieren. Wenn ausgegraut, ist der Filter zahnlos.

→ **Vorschlag:** Filter blendet komplett aus (Mike's Wunsch: nur
Even-Stationen anrufen ohne Odd-Ablenkung). Aber Tooltip auf dem
Button: „Versteckt Odd-Slot-Stationen — Klick zum Beenden".

### B4 — Persistenz vs. nicht-persistent (Q3)

Mike-Use-Case: „wegen einer spezifischen Station nur Even-Slot".
Spezifisch = einmaliger Use-Case → Filter sollte NICHT
persistiert sein, sondern Default bei jedem App-Start = „both".

Auch Modus-Wechsel zurücksetzen (Q4 → AC9 ist OK).

### B5 — Slot-Filter und `_tx_even` von QSO-State

Der QSOState hat `_was_cq` und Slot-Parity-Logik für TX. Wenn User
filtert „Even", soll Bundle-D NUR die RX-Anzeige filtern, nicht TX.
TX-Logik ist davon unabhängig (Slot wird von der angerufenen Station
bestimmt).

→ Implementation: Filter in `RXPanel.add_message()` oder
`_populate_row()`. NICHT in QSOState/Encoder.

### B6 — Even/Odd-Buttons Style (Q7)

Mike's Vorlage im Screenshot: 2 farbige Tabs (EVEN grün, ODD grau).
Beide sind exclusiv (entweder oder).

→ Aber als FILTER würde ich 3-Wege brauchen: „Beide / nur Even /
nur Odd". Optionen:
- (a) 2 Toggle-Buttons exclusive (wenn beide aus = „beide")
- (b) 2 Toggle-Buttons additive (beide an = „beide", einer an = Filter)
- (c) 3-Tab: „Beide / Even / Odd"

KISS: Option (b) — User klickt EVEN → nur Even. Klick ODD → nur Odd.
Beide an oder beide aus → „Beide". Visuell: aktive Button leuchtet.

→ R1 entscheiden lassen — auch hinsichtlich Mike's Screenshot-Style.

### B7 — Test-Pattern für QSO-Panel-UI

`tests/test_qso_panel*.py` existiert? Lass mich prüfen.

### B8 — Slot-Balken-Frequenz: sekündlich vs. 500ms

Wenn 15s-Balken sekündlich aktualisiert wird, springt der Anzeige-Wert
in 1-Sekunden-Schritten — etwas ruckartig.
Wenn 500ms (synchron zu `_update_slot_display`), ist es smoother.

→ KISS: sekündlich (im bestehenden `_cq_countdown_timer`), wäre
geringfügig weniger smooth aber weniger Code.

### B9 — Bei reinem „Färbung im Slot-Balken" (kein Sekunden-Wert)

Wenn der Balken nur Parity zeigen soll (Mike-Quote: „farblich
darstellen grün / gelb"), reicht ein QLabel mit Hintergrund-Farbe.
Kein QProgressBar nötig.

Aber „Balken" suggeriert Progress (0→100% in 15s). Mike wahrscheinlich
will:
- Balken füllt sich in 15s
- Farbe wechselt nach Slot (grün/gelb)
- Reset auf 0% beim Slot-Wechsel

→ QProgressBar mit `setRange(0, cycle_dur*1000)` und sekündlicher
oder 500ms Update.

### B10 — Wenn Slot-Filter aktiv, was passiert mit OMNI/Auto-Hunt-
Buttons in Normal-Modus?

OMNI und Auto-Hunt sind Diversity-only (sichtbar nur in Diversity).
→ kein Konflikt mit Normal-Filter. ✓

---

## C. Korrigierte ACs (V2-Stand, finale Version geht in V3)

- **AC1** Settings-Block setSpacing 6 → 10
- **AC2** QGroupBox contentsMargins erhöhen für luftiges Top-Padding
- **AC3** DT 0.0-Vorzeichen-Entfernung: `if abs(round(msg.dt, 1)) < 0.05: "0.0"
  else: f"{msg.dt:+.1f}"`
- **AC4** Even+Odd als QPushButton (checkable, Style siehe R1-Q7)
- **AC5** Filter-State `_slot_filter` ∈ {"both", "even", "odd"},
  default `"both"`, NICHT persistiert (B4)
- **AC6** Filter blendet RX-Decodes des gefilterten Slots AUS
  (komplett, nicht ausgegraut — B3)
- **AC7 STRICT** Filter wirkt NUR auf RX-Anzeige, NICHT auf
  QSO/CQ/TX-Logik (B1+B5)
- **AC8** Diversity: Filter-Buttons `setVisible(False)`, Filter-State
  auf `"both"` zurückgesetzt
- **AC9** Modus zurück Normal: Filter wieder `"both"` (B4)
- **AC10** QSO/Logbuch-Buttons werden auto-breiter (`Expanding` schon
  da)
- **AC11** Statusbar `_slot_progress_bar` als QProgressBar permanent-
  widget
- **AC12** Update sekündlich aus `_tick_cq_countdown` (KISS)
- **AC13** Range 0 → `cycle_dur` (FT8=15, FT4=7.5, FT2=3.8) —
  cycle_dur-aware (B2)
- **AC14** Farbe per Slot-Parity wechselnd (siehe R1-Q5)

---

## D. Offene Fragen für R1 (Q1-Q7 aus V1 + B-Refinements)

- **Q1 (V1) Even-Filter-Wirkung:** ausblenden vs. ausgegraut →
  V2-Vorschlag: ausblenden. R1 bestätigen.
- **Q2 (V1) Auto-Hunt bei Filter:** V2-Vorschlag: Auto-Hunt arbeitet
  nur in Diversity-Modus, Filter ist Normal-only → Konflikt entfällt.
  R1 bestätigen.
- **Q3 (V1) Filter persistieren:** V2-Vorschlag: NEIN, default "both"
  bei App-Start.
- **Q4 (V1) Modus-Wechsel:** V2-Vorschlag: Filter immer reset auf
  "both" bei Diversity ↔ Normal.
- **Q5 (V1) Slot-Balken-Farben:** Mike sagt grün/gelb. Aber grün ist
  schon „aktiv-Slot-Label". Vorschlag-Liste:
  - cyan / magenta
  - grün / orange
  - blau / gelb
  - violett / lime
  Was empfiehlt R1 für ein dunkles Theme mit Neon-Akzenten, eindeutig
  unterscheidbar und nicht-kollidierend mit bestehenden
  Status-Indikatoren?
- **Q6 (V1) Balken-Form:** QProgressBar (mit Fortschritt 0-100%)
  ODER nur QLabel mit Hintergrund-Farbe (nur Parity). V2-Vorschlag:
  QProgressBar mit Farb-Wechsel je Parity.
- **Q7 (V1) Buttons-Style:** 2 Toggle exclusive vs. additive vs.
  QTabBar vs. 3 Buttons. V2-Vorschlag: Option (b) additive Toggles.
  R1 entscheiden.
- **Q8 NEU** Filter-Auswirkung auf weitere RX-Anzeigen:
  - QSO-Panel oben: zeigt nur Decodes des aktiven Slots — bleibt
    unverändert (Filter ist im RX-Panel).
  - Karten-Direction-Widget: irrelevant, zeigt Stationen ohne
    Slot-Info.
  R1 bestätigen.
- **Q9 NEU** Beim Filter-Klick: bestehende Stationen im RX-Panel
  werden „live" gefiltert (Klick versteckt) oder nur neue Decodes
  ab Klick-Zeitpunkt?
  → V2-Vorschlag: live umfiltern (alle bestehenden Zeilen prüfen,
  ausblenden falls falscher Slot).

---

## E. Architektur (V2 final, geht so in V3)

```
ui/settings_dialog.py
  ─ bands_grid.setSpacing(10) + bands_group.setContentsMargins(...)

ui/rx_panel.py
  ─ _format_dt(value) Helper: 0.0 ohne Vorzeichen
  ─ _populate_row → Filter-Check vor Anzeige basierend auf
    _slot_filter
  ─ apply_slot_filter(filter: str) → live-Re-Render

ui/qso_panel.py
  ─ _even_label/_odd_label → _btn_even/_btn_odd (QPushButton, checkable)
  ─ _slot_filter state
  ─ slot_filter_changed Signal (str)
  ─ set_slot_buttons_visible(visible: bool) → für Diversity
  ─ _update_slot_display weiterhin für aktives-Slot-Highlight aber
    auf den Buttons (nicht Labels)

ui/main_window.py (od. mw_qso.py)
  ─ qso_panel.slot_filter_changed.connect(rx_panel.apply_slot_filter)
  ─ Im _on_rx_mode_changed: qso_panel.set_slot_buttons_visible(rx_mode == "normal")
  ─ Statusbar: _slot_progress_bar (QProgressBar)
  ─ _tick_cq_countdown erweitern um Slot-Balken-Update

tests/test_bundle_d.py NEU
  T1 Settings spacing-Wert
  T2 DT 0.0-Formatter
  T3 DT +0.2-Formatter (positiv unverändert)
  T4 DT -0.5-Formatter (negativ unverändert)
  T5 RXPanel apply_slot_filter("even") → odd-Stationen versteckt
  T6 RXPanel apply_slot_filter("both") → wieder alle sichtbar
  T7 QSOPanel _btn_even click emit slot_filter_changed("even")
  T8 QSOPanel set_slot_buttons_visible(False) → versteckt
  T9 MainWindow rx_mode_change → buttons sichtbar/versteckt + Filter
     reset
  T10 Statusbar slot_progress_bar wird in _init_statusbar gebaut
  T11 Slot-Balken Farbe wechselt mit Parity
```

---

## F. Workflow-Compliance-Check

- ✅ Code-Verifikation Schritt 0 — sauber, mit Datei:Zeile
- ✅ V1 mit 14 ACs entworfen
- ✅ V2 Self-Review (B1-B10 + Q1-Q9 + AC-Korrekturen)
- ⏳ R1 als nächster Schritt mit V1+V2+Files anhängen
- ⏳ V3 nach R1-Entscheidung
- ⏳ Code in atomaren Commits
- ⏳ Final-R1
- ⏳ Doku + Memory
