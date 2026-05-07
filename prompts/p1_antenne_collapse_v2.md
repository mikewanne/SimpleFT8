# P1.ANTENNE-COLLAPSE V2 — Self-Review

**Stand:** 2026-05-06.
**Workflow:** V1 → **V2 (diese Datei)** → R1 → V3 → Plan → Code.
**Aufgabe:** V1 als „frische KI" reviewen, Lücken schließen.

---

## L1 — V1 verkennt Layout-Tücke: Body kann nicht trivial in QWidget-Container

V1 §3 schlägt vor:
> `_body_widget = QWidget()`, `_body_lay = QVBoxLayout(_body_widget)`,
> alle Body-Widgets umziehen.

Aber: V1's eigene Code-Inspektion (`ui/control_panel.py:421-590`) zeigt
dass aktuell `lay` (das Haupt-`QVBoxLayout` des `QFrame`) **direkt** alle
Widgets aufnimmt — `lay.addWidget(lbl_ant)`, `lay.addLayout(btn_row)`,
`lay.addWidget(self.dx_info)`, `lay.addWidget(self._div_widget)`,
`lay.addWidget(self._freq_hist)`, `lay.addWidget(self._tx_freq_row)`,
`lay.addLayout(cq_row_layout)`.

**V2-Korrektur:** Refactoring ist nötig — **alle bisherigen `addWidget`/
`addLayout` ausser `lbl_ant`** müssen zu `_body_lay.addWidget(...)` /
`_body_lay.addLayout(...)` umziehen. Das ist mehr als „1 Container
einfügen", das ist ein Block-Refactor von ~80 Zeilen `__init__`.

→ **In V3 explizit als Schritt 1 mit Diff-Zeilen-Range markieren.**

---

## L2 — V1 fehlt: Header-Layout statt Vertical-Stack

Aktuelles `lbl_ant` ist ein einfaches `QLabel` direkt in `lay`. Mit Toggle-
Button braucht es ein Header-`QHBoxLayout`:

```
header_row = QHBoxLayout
  ├── toggle_btn (links oder rechts)
  └── lbl_ant   ("ANTENNE", flex=1 für rechts-Variante)
lay.addLayout(header_row)
```

**V2-Korrektur:** V1 §3 muss explizit `header_row = QHBoxLayout()`
einführen, `lbl_ant` und `toggle_btn` da rein. Der Header ist NICHT
Teil des `_body_widget` (sonst würde der Header auch verschwinden →
Toggle weg, Mike kann nicht mehr aufklappen!).

---

## L3 — V1 §6 testbarkeit: Settings-Mock fehlt

V1 §6 listet 6 Tests, aber Settings-Mock-Pattern wird nicht spezifiziert.
Bestehende Test-Infrastruktur in `tests/` nutzt vermutlich pytest
`monkeypatch` oder `tmp_path` für Settings — V2/R1 müssen das prüfen.

**V2-Empfehlung:** vor V3-Plan eine `grep` auf `tests/test_p1_*.py` nach
Settings-Pattern ausführen. Falls bestehender Pattern: nutzen. Falls
nicht: minimaler `MockSettings`-Helper in der Test-Datei.

---

## L4 — V1 verpasst: btn_row-Sichtbarkeit ist STATEFUL!

`btn_row` enthält `btn_normal`, `btn_diversity`, `btn_einmessen`. Bei
manchen Modi (`btn_einmessen` wird in `mw_radio.py` enabled/disabled,
sieht aber immer sichtbar). `btn_row` selbst hat keine eigene
Visibility-Steuerung im Code (V2 nicht final überprüft).

**V2-Frage:** wenn die Kachel zu ist und KALIBRIEREN soll automatisch
laufen (z.B. nach Bandwechsel mit Cache-Miss), wird der Button gedrückt
oder nur über Code-Pfad ausgelöst? Falls Mike bei zugeklappter Kachel
keinen Klick auf KALIBRIEREN hat — kann er den Button nicht drücken.
Pre-V0.93 war KALIBRIEREN explizit Mike-getriggert. Ab v0.93 mit
Cache-Reuse läuft KALIBRIEREN auch automatisch.

**V2-Korrektur:** das ist KEIN Bug — Mike kann die Kachel jederzeit
aufklappen wenn er KALIBRIEREN braucht. Aber R1 soll das verifizieren:
gibt es Code-Pfade die `btn_einmessen` brauchen UND nur funktionieren
wenn der Button sichtbar ist? (vermutlich nicht — `clicked.emit()` geht
auch unsichtbar.)

---

## L5 — V1 verpasst: Diversity-Mode-State-Wechsel und Body-Visibility

In `_AntenneCard.__init__` wird `self._div_widget.setVisible(False)`
gesetzt — Default unsichtbar bis Diversity aktiv. Ähnlich `_freq_hist`,
`_tx_freq_row`. Diese Widgets werden je nach Modus per `setVisible`
geschaltet.

**V2-Frage:** wenn die Kachel zugeklappt wird während Diversity läuft
(`_div_widget` sichtbar), und dann beim Aufklappen der Modus inzwischen
auf Normal gewechselt hat — wird `_div_widget` korrekt versteckt?
Antwort: **Ja**, weil die Mode-Wechsel-Logik in `mw_radio.py` direkt
`_div_widget.setVisible(False)` aufruft, **unabhängig** vom Parent-
Container-Visible. Qt's `setVisible(False)` auf einem Kind-Widget bleibt
auch dann False wenn der Parent erst zugeklappt war und dann wieder
geöffnet wird.

→ **Kein Code-Eingriff nötig. R1 soll das aber explizit verifizieren.**

---

## L6 — V1 §7 Offene Frage 6 (Header-Klick) — KISS dagegen

V1 §7.6 schlägt EventFilter vor um den ganzen Header klickbar zu machen.
Das ist Overengineering für ein Hobby-Tool:
- EventFilter brauchen `installEventFilter` + `eventFilter`-Methode
- Klick-Toleranz muss eindeutig sein (auf lbl_ant ja, auf btn_row nein)

**V2-Entscheidung:** **NUR Toggle-Button klickbar.** Header-Klick ist
draussen. KISS, weniger Code, weniger Bugs.

---

## L7 — V1 verpasst: Plan-V3 muss Compact-fest sein

Mike möchte den Workflow zuende fahren auch wenn ein Compact dazwischen
kommt (Pattern aus P1.AP-FIX heute). Plan-V3 soll daher:
- Konkrete Diffs mit Datei:Zeile-Range
- Test-Diffs konkret
- Reihenfolge der Schritte (1. Refactor `_AntenneCard.__init__`,
  2. Header-Logik, 3. Toggle-Methode, 4. Settings-Integration,
  5. MainWindow-Init-Hook, 6. Tests)

**V2-Korrektur:** V3 muss ALLE Diffs Compact-fest enthalten.

---

## L8 — V1 verpasst: Bestehende Pattern für klappbare UI im Code?

Schneller Code-Check ob es schon einen `_collapse`/`_collapsed`/
`expanded`-Pattern im Repo gibt — falls ja, gleichen Stil nehmen.
**V2-Aufgabe:** vor R1-Send einmal `grep -ri "collaps\|expand" ui/` —
um sicher zu gehen kein Doppel-Pattern entsteht.

---

## L9 — V1 verpasst: Settings-Default beim Programm-ERSTSTART

Wenn `~/.simpleft8/config.json` (oder wo auch immer Settings hingespeichert
werden) noch keinen Key `"antenne_card_collapsed"` hat (frischer Install),
soll der Default `False` (= aufgeklappt) sein. `Settings.get(key, default)`
unterstützt das nativ — keine spezielle Migration nötig.

**V2-Bestätigung:** kein Migrationsschritt nötig. R1 soll prüfen ob das
auch tatsächlich so ist.

---

## L10 — V1 §6 Testabdeckung lückenhaft

V1 listet 6 Tests aber:
- **Fehlt Test 7:** `test_antenne_card_collapsed_persists_initial_state` —
  Settings hat schon `True` → bei `_AntenneCard`-Konstruktion + Init-Hook
  startet die Karte zugeklappt (kein Toggle-Klick nötig).
- **Fehlt Test 8:** `test_antenne_card_no_settings_save_during_init` —
  beim Programm-Start mit gespeichertem `True` darf Settings NICHT
  zusätzlich `set+save` aufgerufen werden (das wäre ein Init-Loop-Bug,
  der den State unnötig schreibt). Nur User-Klick triggert `save`.

**V2-Korrektur:** V3 listet 8 Tests, nicht 6.

---

## L11 — V1 verpasst: HISTORY/HANDOFF/CLAUDE-Doku-Schritte explizit listen

Mike's CLAUDE.md verlangt nach jedem erledigten Fix die 4-Datei-Doku-
Update. V1 hat das in §5 nicht erwähnt. V3 muss explizit in der
Implementations-Reihenfolge Doku-Schritte listen.

---

## L12 — V1 §4 R1-Vorbehalt-Hinweis nicht explizit als Prompt-Klausel

V1 erwähnt in §4: „R1 darf KISS-Bedenken äussern, aber das einklappbar
Ja/Nein ist NICHT verhandelbar." — aber im V2-an-R1-Send muss das
EXPLIZIT in der R1-Prompt stehen, sonst riskiert R1 mit „Mike sollte
nicht einklappen" zu antworten und der Workflow stockt.

**V2-Korrektur:** R1-Prompt-Template enthält explizit:
> „Mike's Designentscheidung steht: Kachel WIRD einklappbar. Reviewe
> nur die Umsetzung — ob Diffs korrekt, ob KISS, ob Tests reichen,
> ob Persistenz sauber. Kein Vorschlag für „andere Lösung statt
> Einklappen"."

---

## L13 — V1 nicht klar: was passiert mit der Kachel-Höhe + restlichem Layout?

Wenn Body weg ist, schrumpft die Karte. ControlPanel hat ein vertikales
QVBoxLayout (vermutlich), in dem mehrere Karten untereinander hängen.
Bei Schrumpfung muss der Restraum (RX-Panel oder QSO-Panel) das
ausgleichen — ohne Stretch-Faktoren wäre die freie Fläche unten
unsichtbar.

**V2-Frage:** prüft V3, ob `ControlPanel`-Layout `addStretch()` o.ä. hat.
Falls nicht: Antennen-Kachel-Schrumpfung erzeugt Lücke. Dann muss
V3 entweder:
- a) `ControlPanel`-Layout mit `addStretch()` ergänzen
- b) `_AntenneCard.setSizePolicy(Fixed/Maximum)` setzen damit sie
  natürlich auf Header-Höhe schrumpft

→ **R1 soll konkret prüfen `ControlPanel.__init__`-Layout-Stretch.**

---

## L14 — V1 verpasst: ChannelPanel-Größenpolitik bei Collapse

Verwandt zu L13: wenn die Kachel collapsed wird (Höhe ~28px), soll der
restliche Platz zu RX/QSO-Panel rüberwandern. Das ist KEIN Default in
Qt — `QFrame` hat `Preferred` size policy, das heißt es bleibt grob
Default-Höhe. Nach Collapse muss `setMaximumHeight` gesetzt werden,
oder `sizeHint` neu berechnet werden.

**V2-Empfehlung:** beim Collapse `setMaximumHeight(header_height +
margins)`, beim Expand `setMaximumHeight(QWIDGETSIZE_MAX)`. Sauber,
KISS, kein Layout-Hack.

---

## L15 — V1 vergessen: Toggle-Button-Tooltip

Mini-UX-Detail: Toggle-Button soll Tooltip haben (`„Antennen-Kachel
ein-/ausklappen"` oder einfach `„Einklappen"` / `„Ausklappen"`
state-abhaengig). KISS aber hilft Mike beim ersten Hover.

---

## L16 — Zusammenfassung der V2-Korrekturen für V3

1. **Body-Container-Refactor:** klare Marker für 80-Zeilen-Block-Refactor
   in `__init__`.
2. **Header-Layout** als `QHBoxLayout` mit Toggle + lbl_ant.
3. **Test-Pattern:** Settings-Mock klären (grep tests/).
4. **`btn_einmessen` invisible-vs-clickable Verifikation** durch R1.
5. **Diversity-Mode-State + Body-Visibility:** Qt-Pattern dokumentieren.
6. **Header-Klick:** ABLEHNEN, nur Button-Klick.
7. **Plan-V3 Compact-fest:** alle Diffs konkret.
8. **Bestehende Collapse-Pattern grep:** vor R1-Send.
9. **Erststart-Default:** `False`, kein Migration.
10. **8 Tests statt 6.**
11. **HISTORY/HANDOFF/CLAUDE/TODO/Memory** als Pflicht-Schritt einplanen.
12. **R1-Prompt-Klausel:** Mike-Designentscheidung NICHT verhandelbar.
13. **L13 Layout-Stretch in ControlPanel verifizieren.**
14. **L14 setMaximumHeight bei Collapse für sauberes Schrumpfen.**
15. **L15 Toggle-Button-Tooltip.**

---

## Pruefauftraege fuer R1 (DeepSeek-R1)

1. **Toggle-Position + Stil:** Header `QHBoxLayout` mit `QToolButton`
   (links oder rechts) — Argumente?
2. **Body-Container-Refactor:** Risiken beim Umzug von `lay.addWidget(...)`
   zu `_body_lay.addWidget(...)` (Signal-Connections, Parent-Inheritance)?
3. **Settings-Pattern:** generic `get/set` oder explizite Property?
4. **Init-Hook in MainWindow:** wo am saubersten? `__init__` nach
   ControlPanel-Construction?
5. **Diversity-Updates wenn Kachel zu:** Qt-Verhalten korrekt
   antizipiert in V2-L5?
6. **`setMaximumHeight`-Switch** (V2-L14): wirklich nötig oder
   `setSizePolicy`-Variante besser?
7. **Tests-Patterns:** bestehende Settings-Mock-Pattern in tests/?
   Falls ja, identifizieren.
8. **`ControlPanel`-Stretch-Issue (V2-L13):** verifizieren ob `addStretch()`
   schon vorhanden, falls nicht — neuer Code-Ort?

---

**Workflow-Status:** V2 fertig. Jetzt grep-Verifikation + R1-Send.
