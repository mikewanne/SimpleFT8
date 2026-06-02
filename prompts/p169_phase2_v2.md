Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software und
PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt ist ein
Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt KRITISIEREN — NICHT das Problem lösen.
Liefere eine strukturierte Liste: Lücken, Unklarheiten, Widersprüche,
Verbesserungen, Risiken.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50 %.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen (Hobby-FT8-Tool).
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: 🔴 Bug | 🟠 Risiko | 🟡 Verbesserung | ⚪ Hinweis.
Overengineering ist selbst ein Fehler, den du benennen sollst.

================================================================================
P169 PHASE 2 — Mode-genauer Worked-Filter (Call, Band, Mode)
================================================================================

## Kontext / Ist-Zustand (Phase 1 ist fertig, v0.98.57)

Die App erkennt „schon gearbeitete" Stationen über `log/qso_log.py` (Klasse
`QSOLog`). Quelle ist EIN rekursiv gelesener Ordner `adif/erfasst/` (~19 000
QSOs, DA1MHH+DO4MHH). Heute ist der Index **mode-blind**:
- `_worked: set[str]`            — Calls (Portable-Suffix gestrippt)
- `_worked_band: set[(call,band)]`
- `_country_count: dict[country,int]` + `_country_band: set[(country,band)]`
  (P165 DX-Scoring — LAND-Ebene, bleibt mode-blind, siehe Out-of-Scope)

Zwei Verbraucher nutzen den Worked-Status:
1. **NEUE-Filter** (RX-Liste, reine Anzeige): `ui/rx_panel.py:796-799`
   `if self.btn_new_filter.isChecked() and self._qso_log is not None:`
   `    caller = getattr(msg, 'caller', '')`
   `    if caller and self._qso_log.is_worked(caller): return True`
   → blendet eine Station auf ALLEN Bändern/Modi aus, sobald sie irgendwann
   gearbeitet wurde. rx_panel hat KEINEN Zugriff auf aktuelles Band/Mode.
2. **Auto-Hunt** (aktive CQ-Jagd): `core/auto_hunt.py:479-484`
   `candidates = [c for c in candidates`
   `              if not self._qso_log.is_worked_on_band(c.call, self._band)]`
   → überspringt Stationen, die auf DIESEM Band gearbeitet wurden — aber
   mode-blind: 20m-FT8-gearbeitet ⇒ auch auf 20m-FT4 übersprungen.

## Mike-Problem (Field, 02.06.2026)

Auf vollen Bändern (20m: ~18k QSOs) ruft Auto-Hunt „kein Ruf raus" und
verschweigt warum (still). Mike will:
(a) NEUE-Filter band+mode-genau: Station auf 20m FT8 gearbeitet ⇒ bei NEUE auf
    20m FT8 ausblenden, auf **20m FT4 zeigen**, auf **15m FT8 zeigen**.
(b) Auto-Hunt genauso: eine auf 20m FT8 gearbeitete Station ist auf 20m FT4
    wieder ein gültiges Ziel.
(c) Transparenz: wenn Auto-Hunt nichts ruft WEIL alle gearbeitet sind, einmal
    (entprellt) im QSO-Log melden „alle N auf {Band} {Mode} schon gearbeitet".

## ADIF-Mode-Fakten (verifiziert)

`log/adif.py:parse_adif_file` liefert pro QSO ein dict mit allen Feldern, u.a.
`MODE` und `SUBMODE` (sofern vorhanden). Mode-Normalisierung (ADIF-Norm,
Web-verifiziert): **effektiver Mode = SUBMODE wenn vorhanden, sonst MODE.**
- FT8 (unsere ADIF + QRZ-Export): `MODE=FT8`, kein SUBMODE → „FT8"
- FT4 (unsere ADIF, `log/adif.py:278`): `MODE=MFSK`+`SUBMODE=FT4` → „FT4"
- FT4 (QRZ-Export): `MODE=FT4`, kein SUBMODE → „FT4"
- FT2 (unsere ADIF): `MODE=MFSK`+`SUBMODE=FT2` → „FT2"
Mikes QRZ-Export: 10877×`MODE=FT8` + 1147×`MODE=FT4` (kein SUBMODE).
Live-Mode in der App: `self.settings.mode` ∈ {„FT8",„FT4",„FT2"} (Großschrift).

================================================================================
## ZIEL
================================================================================

Mode-genauer Worked-Index `(call, band, mode)` zusätzlich zu den bestehenden
Indizes (additiv, KEINE Entfernung der alten). NEUE-Filter + Auto-Hunt nutzen
ihn band+mode-genau. Plus entprellte Transparenz-Meldung im Auto-Hunt.

================================================================================
## AKZEPTANZKRITERIEN
================================================================================

1. `QSOLog` hat `_worked_band_mode: set[(call,band,mode)]`, befüllt in
   `load_adif` UND `add_qso`. Mode normalisiert (SUBMODE sonst MODE, `.upper()`).
   **Leerer Mode wird NIE indiziert** (leerer Mode = Wildcard → träfe alle Modi).
2. `QSOLog.is_worked_on_band_mode(call, band, mode) -> bool`. Leerer/None mode-
   Parameter → `False` (kein mode-genaues Urteil möglich; Caller liefert immer
   einen echten Mode).
3. `QSOLog.add_qso(call, band="", mode="")` — neuer optionaler Parameter.
   `_worked`/`_worked_band`/`_country_*` bleiben unverändert befüllt.
4. `QSOLog.clear()` (Phase-1-Reload) leert auch `_worked_band_mode`.
5. Live-Vermerk: `ui/mw_qso.py:657`
   `self.qso_log.add_qso(qso_data.their_call, band)` →
   `... add_qso(qso_data.their_call, band, self.settings.mode)`.
   (`self.settings.mode` ist daneben bei `log_qso(... mode=self.settings.mode)`
   auf Zeile 643 schon im Gebrauch.)
6. NEUE-Filter (`rx_panel._row_should_hide`) nutzt
   `is_worked_on_band_mode(caller, aktBand, aktMode)`. rx_panel bekommt Band+Mode
   über einen **Provider-Callback** `set_band_mode_provider(fn)` mit `fn() ->
   (band, mode)`, in `main_window` verdrahtet als
   `lambda: (self.settings.band, self.settings.mode)`. Wenn kein Provider gesetzt
   (Test-Setups) → Fallback auf altes call-only `is_worked(caller)`.
7. Auto-Hunt-Filter (`auto_hunt.select_next`, Zeile 481):
   `is_worked_on_band(c.call, self._band)` →
   `is_worked_on_band_mode(c.call, self._band, self._mode)`.
8. Auto-Hunt-Transparenz: neues Signal `all_worked = Signal(str, str, int)`
   (band, mode, n). In `select_next` wird es emittiert, wenn VOR dem Worked-
   Filter Kandidaten da waren, NACH dem Filter aber keine mehr — entprellt über
   `self._all_worked_reported` (bool). Reset des Flags in `start_auto_hunt`,
   `set_band`, `set_mode` und bei jedem erfolgreichen Pick. `main_window`
   verbindet das Signal mit `qso_panel.add_info(f"Auto-Hunt: alle {n} Stationen
   auf {band} {mode} schon gearbeitet")`.
9. Staleness-Fix: `auto_hunt.set_band` wird heute nur im `if active`-Zweig
   gerufen (`ui/mw_radio.py:609`) — wechselt man das Band bei inaktivem
   Auto-Hunt, ist `_band` veraltet, wenn man Auto-Hunt danach startet. Fix:
   in `main_window` direkt VOR `self._auto_hunt.start_auto_hunt(600)`
   (`ui/main_window.py:1030`) `set_band(self.settings.band)` +
   `set_mode(self.settings.mode)` pushen.
10. Tests grün: `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`.

================================================================================
## BETROFFENE DATEIEN (mit Zeilen)
================================================================================

- `log/qso_log.py` — `__init__` (16-21), `clear` (23-30), `load_adif` (32-53),
  `add_qso` (72-83), neue `is_worked_on_band_mode`.
- `ui/mw_qso.py:657` — add_qso-Aufruf mit Mode.
- `ui/rx_panel.py` — `__init__` (Provider-Feld), neuer Setter, `_row_should_hide`
  (796-799).
- `ui/main_window.py` — Provider-Wiring (nach Zeile 96
  `self.rx_panel.set_qso_log(...)`), all_worked-Signal-Connect (bei 454),
  neuer Handler, Band/Mode-Push vor start_auto_hunt (1030).
- `core/auto_hunt.py` — `__init__` (_all_worked_reported), `start_auto_hunt`
  (238-245), `set_band` (178-180), `set_mode` (182-186), `select_next`
  (Worked-Filter 479-484 + Emit), neues Signal (bei 132).

================================================================================
## RANDBEDINGUNGEN
================================================================================

- **Hardware:** reine State-/Anzeige-Logik. KEIN TX-Eingriff. ANT1/ANT2
  unberührt (Auto-Hunt sendet weiterhin nur über ANT1 — hier nicht angefasst).
- **Threading:** `select_next` läuft im GUI-Thread (Cycle-Handler). Signal-Emit
  ist Qt-konform. Kein neuer Thread, kein Lock.
- **Persistenz:** keine neuen Dateien/Schemas. `_worked_band_mode` ist reiner
  In-Memory-Index, beim Start aus `adif/erfasst/` aufgebaut (wie die anderen).
- **Konsistenz:** Live-`add_qso`-Mode (`settings.mode`, „FT8"/…) und ADIF-
  geladener Mode (SUBMODE/MODE, `.upper()`) müssen DASSELBE Token ergeben, sonst
  greift der Filter inkonsistent. Beide → `.upper()`.
- **Provider-Callback** statt verteilter `set_band`/`set_mode`-Setter in rx_panel:
  bewusst gewählt, um die in diesem Projekt wiederholt aufgetretene „Setter in
  Pfad X vergessen"-Sync-Bug-Klasse (P102/P114/P135/P141 mode-aware Symmetrie)
  zu vermeiden — eine Verdrahtungsstelle, lazy gelesen.

================================================================================
## NICHT IM SCOPE (NICHT als Finding melden)
================================================================================

- Land-Seltenheit / DXCC-Scoring (`_country_count`, `_country_band`,
  `_compute_priority`, `is_country_worked_on_band`) bleibt **mode-blind** —
  „habe ich dieses DXCC-Land gearbeitet" ist mode-unabhängig. NICHT mode-aware
  machen.
- `_worked` (call-only) und `_worked_band` (call,band) NICHT entfernen — bleiben
  für API/Tests/Zukunft. Rein additiv.
- Keine Persistenz/Settings-Migration, kein UI-Umbau, kein neues Diagramm.
- Auto-Hunt-Sonderpräfix-Auflösung (FT5 etc.), Most-Wanted-Liste — separates
  Ticket (P165 Phase 2), hier irrelevant.
- SSB/CW werden zwar korrekt indiziert (effektiver Mode), aber die App funkt nur
  FT8/FT4/FT2 — kein Handlungsbedarf, nur Korrektheit.

================================================================================
## TESTBARKEIT (unverzichtbar)
================================================================================

- `is_worked_on_band_mode`: 20m-FT8 indiziert ⇒ True für (20m,FT8), False für
  (20m,FT4) und (15m,FT8). Leerer Mode-Param ⇒ False. SUBMODE-vor-MODE-Norm
  (MFSK+SUBMODE FT4 ⇒ „FT4"; QRZ MODE FT4 ⇒ „FT4").
- Leerer Mode in `load_adif`/`add_qso` ⇒ NICHT in `_worked_band_mode`.
- `clear()` leert `_worked_band_mode`.
- Auto-Hunt: Station auf (20m,FT8) gearbeitet, `_mode="FT4"` ⇒ Kandidat bleibt;
  `_mode="FT8"` ⇒ gefiltert. all_worked-Signal feuert genau einmal (Debounce)
  und erneut nach Reset (set_band/set_mode/Pick).
- NEUE-Filter: mit Provider (20m,FT8) blendet 20m-FT8-Worked aus, zeigt
  20m-FT4-Worked. Ohne Provider → call-only-Fallback.

================================================================================
## TEST-IMPACT (bestehende Tests, die angepasst werden)
================================================================================

- `tests/test_modules.py:1893` + `tests/test_auto_hunt_extended.py:30` — Fake-
  `QSOLog` definiert `is_worked`/`is_worked_on_band`, aber NICHT
  `is_worked_on_band_mode` → muss ergänzt werden (Auto-Hunt ruft jetzt das neue).
- `tests/test_p61_autohunt_recent_qso.py:51` — Mock mit
  `is_worked_on_band.return_value=False`; braucht
  `is_worked_on_band_mode.return_value=False` (sonst liefert MagicMock einen
  truthy Mock → alle Kandidaten gefiltert).
- `tests/test_p165_dx_scoring.py:166` — `log.add_qso("VP8LP","20m")` ohne Mode;
  da Auto-Hunt jetzt mode-genau filtert (default `_mode="FT8"`), muss der Mode
  ergänzt werden (`add_qso("VP8LP","20m","FT8")`), damit die „skip worked"-
  Assertion weiter greift.

================================================================================
## OFFENE FRAGEN AN DICH (DeepSeek)
================================================================================

A) Provider-Callback vs. zwei Setter (`set_band`/`set_mode`) in rx_panel — ist
   der Callback hier die KISS-konforme Wahl oder Overengineering für 2 Strings?
B) all_worked-Debounce: Reset bei JEDEM Pick — gibt es ein Szenario, in dem das
   die Meldung zu oft/zu selten zeigt? Bessere Reset-Bedingung?
C) Empty-Mode-Semantik von `is_worked_on_band_mode` (False) — korrekt, oder
   sollte sie auf `is_worked_on_band` zurückfallen?
D) Übersehene Pfade, in denen `add_qso` ohne Mode aufgerufen wird und dadurch
   ein QSO mode-mäßig „verloren" geht?
