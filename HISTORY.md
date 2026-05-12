# SimpleFT8 — Änderungshistorie

Diese Datei wird nur ergänzt, niemals gelöscht oder überschrieben.
Format: `## YYYY-MM-DD — Kurztitel` → Änderungen darunter.

---

## 2026-05-12 v0.97.3 — P37 RX-Antennen-Anzeige im Adaptive-Label

**Mike-Wunsch 12.05.2026** nach Live-Test der Adaptive Diversity: das
Phase-Label „● DYNAMISCH (live)" soll zusaetzlich anzeigen welche
RX-Antenne gerade aktiv ist. Mike-Zitat: „so sieht man immer schon das
im diversity modus auch nach pattern empfangen wird und nicht nur starr
nach antenne".

**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Code.
R1-Findings: 0 KRITISCH, 1 Test-Coverage-Verbreiterung (5 statt 1 Test).

**Code-Aenderung (~6 Zeilen + 5 Tests):**
- `ui/control_panel.py:1486` `update_diversity_ratio()`: neuer optionaler
  Parameter `current_ant: str | None = None`. Wenn `is_dynamic=True` UND
  `current_ant in ("A1","A2")` → Label-Text um „ — RX Ant1"/„ — RX Ant2"
  erweitert. Sonst Label „● DYNAMISCH (live)" wie heute.
- `ui/mw_cycle.py:742` Aufruf erweitert: `current_ant=self._diversity_current_ant`.
  Lock-Block (Z.680) umschliesst weiterhin sowohl Schreiber als auch
  UI-Update → kein Race.

**Tests (`tests/test_p37_rx_antenna_label.py` NEU, 5 Tests, R1-Coverage):**
- T1 `current_ant="A1"` → Label enthaelt „RX Ant1"
- T2 `current_ant="A2"` → Label enthaelt „RX Ant2"
- T3 `current_ant=None` → kein Anhang (Backwards-Compat)
- T4 `current_ant="X"` (ungueltig) → kein Anhang (Robustheit)
- T5 `is_dynamic=False` → statisches Label, kein Anhang

**Test-Bilanz: 1131 → 1136 gruen** (+5 P37).

**Plan-File:** `prompts/p37_rx_antenna_label_r1.md`.

## 2026-05-11 v0.97.2 — P35 Bug D+E+F (Live-Field-Test 11.05. abends)

**Mike-Field-Test 11.05. nach v0.97.1** entdeckte 3 weitere Bugs die alle
am App-Start-Pfad lagen:

- **Bug D (Mike-Live-Diagnose):** `_on_band_changed` lief beim App-Start
  unabhängig vom rx_mode → `_diversity_ctrl.on_band_change()` triggerte
  Phase=measure obwohl rx_mode=normal oder radio.ip=None. UI zeigte
  „MESSEN 0/6"-Hänger.
  - **Fix** (`ui/mw_radio.py:397+`): `on_band_change()` nur bei
    `rx_mode=diversity` UND `radio.ip` vorhanden. Sonst Phase=operate
    als Fallback.

- **Bug E (Mike-Vision):** Bandpilot überschrieb Mike's Normal-Modus-
  Entscheidung am App-Start automatisch zu Diversity. Mike: „der
  bandpilot soll nur untercheiden nach werten ist dx besser oder
  Diversity standart. das hat mit dem start nix zu tun ob er diversity
  oder normal modus startet".
  - **Fix** (`ui/mw_radio.py:736`, `:770`): `_maybe_apply_bandpilot`
    skipt wenn `current_mode=normal`. `_apply_bandpilot_auto` skipt
    wenn `target=normal` (Defensive).

- **Bug F (Mike-Anweisung):** Settings persistierten band+mode aus
  letzter Session → App-Start in 40m FT4 + Diversity → Mess-Pipeline
  in falschem Kontext.
  - **Fix** (`ui/main_window.__init__`): App-Start IMMER 20m FT8 Normal-
    Modus erzwingen. `settings._data["band"]="20m"`, `["mode"]="FT8"`.
    Settings die erhalten bleiben: callsign, locator, flexradio_ip,
    power_preset, tx_level, presets-Cache, bandpilot_mode, audio_dump.

**Test-Anpassungen (`tests/test_mw_radio_bandpilot.py`):**
- 4 Tests von `current="normal"` auf `"diversity_normal"` umgestellt
- 2 NEU: `test_bandpilot_skips_when_current_is_normal`,
  `test_bandpilot_rejects_normal_target`

**Test-Bilanz: 1129 → 1131 grün** (+2 Bug-E-Tests).

**Commits:** `6347c0a` (Bug D), `18db03f` (Bug D+E + Tests), `91728f7`
(Bug F).

**Field-Test 11.05. abends (Mike live):**
- ✅ App-Start funktioniert einwandfrei (Bug F greift)
- ✅ Umschalten auf Diversity keine Probleme (Bug A behoben)
- ✅ Beide Antennen aktiv (Statik-Mess läuft sauber)
- 🔄 Dynamic-Umschaltung läuft gerade

**Push pending** bis Mike kompletten Field-Test grün gibt.

## 2026-05-11 v0.97.1 — P35.DIVERSITY-STARTUP-FIX (3 Bugs nach P34-Field-Test)

**Mike-Field-Test 11.05.2026** entdeckte 3 Bugs nach P34.DIVERSITY-DYNAMIC:

- **Bug A — Statik-Mess haengt bei radio.ip=None**:
  Wenn Mike „ohne Radio weiter" im P26-Modal klickt oder App-Start vor
  Radio-Connect zu Diversity führt → `_handle_diversity_measure` skipt
  (P21-Fix) → step bleibt 0 → Antennen-Queue füllt sich nur mit
  (A1, "measure")-Einträgen → spätere Slots laufen nur auf ANT1.

- **Bug B — `activate()` leert Queue + current_ant nicht**:
  Mein P34 `_apply_dynamic_toggle` resettet `_diversity_ant_queue` und
  `_diversity_current_ant` nicht. Bei Toggle AN mitten in hängender
  Mess-Phase bleiben (A1, "measure")-Einträge im Queue, P34-Hook
  überspringt (was_phase != "operate") → Buffer A2 NIE gefüllt obwohl
  ANT2 mehrfach geswitcht wird.

- **Bug B5 — Diversity↔Diversity-Wechsel deaktiviert Dynamic**:
  Mike's Toggle ging beim Mode-Wechsel verloren. Mike-Wunsch (Q3):
  Toggle überlebt Session, nur App-Quit + manuelles AUS deaktiviert.

**Workflow:** V1 → V2 → R1 → V3 → 5 atomare Commits → Final-R1 → Field-Test.

**Code-Änderungen:**
- `core/dynamic_diversity.py` `activate()` (AK5, R1-Q4 KRITISCH):
  Cache-Reuse-Ratio respektieren — NUR auf 50:50 zurücksetzen wenn
  aktuell 50:50/None. Cache-Wert (70:30/30:70) bleibt erhalten.
- `ui/main_window.py` `_apply_dynamic_toggle` + `_init_diversity_state`:
  Queue + current_ant Reset unter `_diversity_lock` BEVOR activate().
  `_pending_diversity_init=None` Init.
- `ui/mw_radio.py` `_enable_diversity`: Defer bei radio.ip=None
  (`_pending_diversity_init=scoring`, Phase=operate, Ratio=50:50).
- `ui/mw_radio.py` `_on_radio_connected`: Resume via
  `_check_diversity_preset` (NICHT `_enable_diversity` direkt → R1-Q7
  voller Cache+Gain-Pfad). Idempotenz: Flag VOR Resume auf None.
- `ui/mw_radio.py` `_activate_diversity_with_scoring`: Auto-Reactivate
  via `_apply_dynamic_toggle(True)` wenn `settings.dynamic_diversity_enabled`.
- `ui/mw_radio.py` `_enable_diversity` Z.887-890: Queue+current_ant
  unter Lock (Final-R1-Threading-Concern aus Alt-Code).

**Tests (`tests/test_p35_startup_bugs.py` NEU, 11 Tests):**
- 3x Bug A (defer, resume, idempotent)
- 4x Bug B (Queue Reset, Cache-Ratio preserve/reset)
- 4x Bug B5 (Auto-Reactivate, Settings-Toggle survives)

**P34-Tests angepasst (`tests/test_diversity_dynamic.py`):**
- `test_activate_resets_ratio` → `test_activate_keeps_cache_ratio`
  (P35-AK5: 70:30 bleibt, nicht 50:50-Reset)
- Plus `test_activate_resets_5050_ratio` + `test_activate_with_none_ratio_becomes_5050`

**Test-Bilanz: 1116 → 1129 grün** (+13: 11 P35 + 2 P34-Anpassung).

**Final-R1: „Push freigegeben"** nach Lock-Fix in `_enable_diversity`.

**Field-Test pending** (Mike, F1-F8 in V3 §6). Push pending bis Field-Test grün.

**Plan-Files:** prompts/p35_diversity_startup_fix_v[1,2,3]+r1+final_r1.md.

## 2026-05-11 v0.97.0 — P34.DIVERSITY-DYNAMIC (Code fertig, Field-Test pending)

**Mike-Vision:** Antennen-Verhältnis im laufenden Betrieb live anpassen statt
nur 1× pro Stunde mit 90-Sek-UI-Sperre. Hobby-Tool-Vereinfachung.

**Architektur:** ENTWEDER-ODER zur statischen Pipeline (kein Parallel-Betrieb):
- Toggle AUS → Statik wie heute (100% unangetastet)
- Toggle AN → Dynamic übernimmt, Statik 1h-Frist unterdrückt

**Code:**
- `core/diversity.py`: 2 Modul-Helper `compute_slot_score()` + `evaluate_ratio()`
  (eine Formel, beide Pipelines nutzen). `_evaluate()` Refactor auf Helper
  (kein Verhaltens-Eingriff). Neue Property `dynamic_active` + Setter +
  `_scoring_mode_listeners` Callback-Liste. `should_remeasure()` returnt
  False wenn `dynamic_active=True`.
- `core/dynamic_diversity.py` NEU (~190 LOC): DynamicDiversityController als
  QObject mit Signal `ratio_changed_dynamic`. 5er-Schiebepuffer pro Antenne
  (`collections.deque(maxlen=5)`). Slot-für-Slot-Erfassung in `record_slot()`.
  Auswertung in `_evaluate_locked()` sobald beide Buffer voll → Median +
  `evaluate_ratio` Helper → setzt `diversity_ctrl.ratio/.dominant` atomar
  unter Lock. Lifecycle: `activate()` (50:50-Reset + ggf. Statik-Mess
  abbrechen) / `deactivate()` (Ratio bleibt + `_last_measured_at` refresh =
  Mike B-Option gegen sofortige Re-Mess nach Toggle-AUS) / `reset()`
  (Buffer leer + 50:50, bei Band/Mode/scoring-Wechsel).
- `ui/mw_cycle.py`: Slot-Datenerfassung-Hook nach `_handle_diversity_operate`.
- `ui/mw_radio.py`: Reset-Hooks in `_on_mode_changed`, `_on_band_changed`,
  `_disable_diversity`.
- `ui/main_window.py`: `_dynamic_ctrl`-Instanz in `__init__`, Signal-Connect
  via `Qt.QueuedConnection`, neue Slots `_on_dynamic_ratio_changed` +
  `_apply_dynamic_toggle`.
- `ui/control_panel.py`: `update_diversity_ratio()` neuer Param `is_dynamic`
  → Phase-Label „● DYNAMISCH (live)" in Blau (#3399CC) wenn aktiv.
- `ui/settings_dialog.py`: QCheckBox „Antennen-Verhältnis dynamisch anpassen
  (Testphase)" + Tooltip + Apply ruft `parent._apply_dynamic_toggle()`.
- `config/settings.py`: RAM-only Property `dynamic_diversity_enabled`
  (default False, NICHT in `_data`, NICHT in `save()`).

**Spec:** prompts/p34_diversity_dynamic_v3.md (Compact-fest, 16 ACs,
9 Commits, 26 Tests, Field-Test-Checkliste F1-F12).

**Workflow:** V1 → V2 → R1 → V1-NEU (Mike-Pivot zu ENTWEDER-ODER) →
V2-NEU → R1-NEU („deutlich weniger Findings — saubere Architektur zahlt
sich aus") → V3 → Mike-Freigabe → 9 atomare Commits → Tests.

**Test-Bilanz: 1070 → 1111 grün** (+41: 14 Helper + 15 Unit + 12
Integration). Über V3-Prognose (~1095-1100).

**Field-Test pending** (Mike, 12 Punkte F1-F12 in V3 §5). Push pending bis
Field-Test grün. Stufe 2 (Statik komplett entfernen) als separater
Workflow später wenn Mike sich mit Dynamic wohlfühlt.

**Wichtigste Mike-Entscheidungen während Klärung:**
- Erste R1-Antwort empfahl Flag in DiversityController (KISS). Mike
  verworfen: Risiko für statische Pipeline. → Neues Modul + Helper-Funktionen
  auf Modul-Ebene als Kompromiss (kein Fummeln in der Klasse).
- Architektur vom „parallel mit Krücken" zu ENTWEDER-ODER umgestellt
  (Mike erkannte den Konflikt selbst).
- B-Option: `_last_measured_at = time.time()` bei `deactivate()` verhindert
  90-Sek-UI-Sperre direkt nach Toggle-AUS.

## 2026-05-11 — Session-Bilanz (mehrere Trivial-Fixes + Debug-Logs + P12-Hotfix)

Kein APP_VERSION-Bump — alles inkrementelle Fixes/Logs auf v0.96.10.

### UI-Tweaks (Field-Test 11.05.)

- **`b19eb22`** Diversity-Anzeige nur Minuten (Sekunden raus —
  springt nicht mehr optisch) + OMNI-CQ-Button eigener Style: grün
  wenn aktiv, dunkelrot wenn inaktiv.
- **`b6cf531`** QSO-Panel Spalten schmaler — `→ Sende X`, `← Empf. X`,
  `← Horche …` mit nur 1 Leerzeichen (vorher 2-3 Block-Spaces).
- **`47feac1`** ConnectStatusDialog (P26) bekommt Lucide
  `radio-tower`-SVG (ISC-Lizenz, MIT-kompatibel) — 48×48 in #7CC links
  vom Spinner. Layout-Umbau: HBox top_row mit Icon + VBox text_col.
- **`5498f0d`** P29 OMNI-CQ Panel-Paritäts-Trennung — bei Even↔Odd-
  Wechsel Leerzeile, Even-TX in `#E09600` (selber Hue wie `#FFAA00`,
  ein wenig dunkler) zur optischen Unterscheidung. Nur im OMNI-Pfad,
  Normal-CQ bleibt einheitlich.

### Debug-Logs (P28-Bisection-Pattern erweitert)

- **`f9fe8b3`** PSK-Pipeline Debug-Logs in `_fetch_psk_stats` +
  `_psk_worker` (Kategorie `PSK`): SKIP/TRIGGER/REQUEST/RESPONSE/
  PARSED/UPDATE/ERROR. Live-Test via curl bestätigte: API liefert
  14 Reports DA1MHH 40m FT8 in 10 Min — Bug muss in App-Pfad sein.
- **`894f7cb`** QSO-Hang Debug-Logs mit Wallclock-Timing in
  `_on_qso_complete` + `_on_qso_confirmed` (Kategorien `QSO-DONE`,
  `QSO-CONF`). dt-Werte pro Step machen den Hänger lokalisierbar.

### Bug-Fixes via Debug-Log-Diagnose

- **`708a521` P28 PSK-Bug-Fix** — Wurzel: OMNI-CQ ruft `encoder.transmit()`
  direkt (umgeht `_on_send_message`) → `_has_sent_cq` blieb False →
  PSK-Worker fragte nie ab. Latenter Bug seit OMNI-Refactor. Fix in
  `_on_tx_started` (feuert für JEDEN TX-Pfad): bei `CQ `-Prefix
  `_has_sent_cq=True`. Beweis im Log:
  `03:18:27 [PSK] SKIP — _has_sent_cq=False` obwohl Mike "die ganze
  zeit cq" via OMNI rief.
- **`d61accc` P12 Partial-Fix** — Hänger nach QSO ~60s via Log-Diagnose
  als `logbook.refresh()` lokalisiert (RR73-Pfad nur 5 ms, dann nach
  `add_qso_complete` Stillstand). Wurzel: `load_adif()` parst ~20 MB
  ADIF (12.8 MB + 6.6 MB ≈ 100k Records) komplett neu + QTableWidget
  mit allen Rows + DXCC/km pro Row. Mike-Lösung: **Logbuch nur letzte
  500 QSOs** in der Tabelle. `_all_records` ungekürzt (Counter bleiben
  korrekt), Display + Filter auf `_LOGBOOK_MAX_ROWS = 500` gekappt.
  Sortierung neueste zuerst (`QSO_DATE` + `TIME_ON` desc). Sauberer
  Async-Refresh bleibt offen.

### Neue TODOs (kritisch)

- **`96a7557` P29** OMNI-Panel-Paritäts-Separation — schon umgesetzt
  (`5498f0d`).
- **`620cdcd` P30 MEMORY-LEAK 124 GB nach Tagen** — Mike musste App
  killen. Live-Check zeigt: `~/.simpleft8/` 45 MB, `audio_dump/`
  existiert nicht. → 124 GB sind **RAM, nicht SSD** (Mike's
  Sound-File-Verdacht entkräftet). Math: ~720 KB Audio-Slot × 172.000
  Slots ≈ 30 Tage durchgehend. Verdächtige Pfade in TODO P30
  priorisiert: locator_db `_calls`, qso_log records,
  decoder.last_audio_24k, Dedup-Dict, AP-Lite-Buffers, qso_panel-
  TextEdit. Eigener Workflow nötig.

### Test-Bilanz

**1070 grün durchgehend** (P26 14 Tests stabil, alle anderen Suites
unverändert).

### Plan-/Workflow-Files

Keine neuen V1-V3-Workflow-Files — alle Heute-Fixes Trivial-Klausel
(<5-20 Zeilen, KISS, Style/Debug-Logs).

### Mike-Disziplin-Note

P30 Memory-Leak ist der einzige verbleibende **kritische** Blocker
vor Push. Logbuch-Hänger ist Partial-Fix (`d61accc`), PSK-Bug
behoben (`708a521`). v0.95.16 → v0.96.10 + Heute-Fixes + P2-Tool +
P3-Audio-Dump + P21-Debug-Log + P26-Connect-Modal bleiben lokal
gesammelt für Push.

---

## 2026-05-11 v0.96.10 — P26.CONNECT-MODAL Field-Test-Tweak

**Auslöser:** Mike-Field-Test 11.05.: „Text reicht FlexRadio wird
verbunden, Text Versuch 1 von kann raus dafür Fenster 20 Prozent kleiner
in Breite und Höhe aber funktioniert super".

**Trivial-Klausel:** Style-Anpassung, < 10 Zeilen — kein Workflow.

### Code

- `ui/connect_status_dialog.py`:
  - `setFixedSize(440, 220)` → `(352, 176)` (20% kleiner B+H)
  - `_attempt_label` initial leerer Text + `setVisible(False)`
  - `set_attempt(...)` ist jetzt **no-op** (Worker emittet weiterhin
    `attempt_changed`, Slot tut nichts — API-Kompat)
  - `set_failed()` setzt Label sichtbar via `setVisible(True)`
    (Failed-Text bleibt: „Verbindung fehlgeschlagen — Radio aus
    oder nicht erreichbar")

### Tests

- T1 prüft neue Size 352×176 + Label `isHidden()`
- T3 prüft no-op-Verhalten (Text leer, Label hidden)
- T4 prüft Failed-State macht Label sichtbar
- T8 angepasst auf no-op
- `isHidden()` statt `isVisible()` weil Tests ohne `dialog.show()`
  laufen

**Test-Bilanz: 1070 → 1070 grün** (Anzahl gleich, Inhalte angepasst).

---

## 2026-05-10 v0.96.9 — P26.CONNECT-MODAL

**Auslöser:** Mike-Wunsch 10.05.2026 17:15 UTC. „Während FlexRadio
gesucht/verbunden wird, sieht man das nicht prominent — kleine
Statusmeldung rechts beachtet keiner. Modal mit Spinner. Plus: Bypass
für Test/Debug, weil Mike auch ohne Radio (200 km weg, ausgeschaltet)
die App starten will."

**Zweck:** Modaler Status-Dialog beim App-Start während FlexRadio-
Connect-Versuch. Zeigt Spinner + „Versuch X von 10". Schließt sich
automatisch wenn `connected`-Signal kommt. User kann jederzeit „ohne
Radio weiter" (kleiner Text-Link, App läuft GUI-only) oder „Beenden"
(App schließt) klicken. Nur beim App-Start, nicht bei mid-Run-Reconnect.

### Code

- **`ui/connect_status_dialog.py` (NEU, ~165 Z.):** `ConnectStatusDialog`
  WindowModal-Dialog. Cross-thread Qt-Signals `attempt_changed(int, int)`
  + `failed_signal()`. 3-Punkt-Spinner-Animation via QTimer 500ms.
  Failed-State stoppt Spinner, setzt rotes ✗, ändert Label auf
  „Verbindung fehlgeschlagen — Radio aus oder nicht erreichbar". Style
  konsistent mit `MessStatusDialog` (P22).
- **`ui/main_window.py`:** `_connect_dialog`-Attribut früh deklariert
  (Worker-Thread-Zugriff). `_start_radio()` wird **NICHT mehr direkt aus
  `__init__`** aufgerufen sondern via `QTimer.singleShot(0, self._start_radio)`
  deferred, damit `window.show()` zuerst läuft und Modal über sichtbarem
  Hauptfenster aufgeht (R1-K2-Fix).
- **`ui/mw_radio.py` `_start_radio` + `_connect_worker`:** Modal vor
  Worker-Thread-Start, `radio.connected.connect(dialog.accept,
  QueuedConnection)` für Auto-Close. `dialog.exec()` blockiert GUI-Thread
  (WindowModal lässt Decoder-Signale weiterlaufen). Cleanup nach Return:
  Signal-Disconnect + `_connect_dialog = None`. Worker holt **lokale**
  Dialog-Referenz (R1-K1-Fix für Race), emittet via `try/except RuntimeError`.
- **`radio/flexradio.py` `auto_connect`:** Optional-Param
  `on_attempt: Optional[Callable[[int, int], None]] = None`. 1-indexed
  Aufruf am Beginn jedes Versuchs. Exceptions im Callback geschluckt
  (Modal-Tot ist kein FlexRadio-Problem).

### Tests

`tests/test_p26_connect_modal.py` (NEU, 14 Tests):
T1-T7 Layout/Smoke, T8-T9 Signal/Slot, T10 emit nach Dialog-Destroy
(R1-K1-Race), T11 connected-emit während exec() (R1-K3-Race), T12-T14
auto_connect Callback + Abwärtskompatibilität.

**Test-Bilanz: 1056 → 1070 grün** (+14 wie V3 prognostizierte).

### Workflow

V1 → V2 (14 Lessons) → R1 (3 KRITISCH + 3 SOLLTE) → V3 (Compact-fest,
EINZIGE WAHRHEIT) → Code → Final-R1 („Push freigegeben", 0 KRITISCH +
2 SOLLTE für „nächstes Major-Release"). Plan-Files
`prompts/p26_connect_modal_v[1,2,3].md` + `_r1.md` + `_final_r1.md`.

### R1-Lessons (für künftige Modal-Patterns)

**K2 (Goldwert):** `exec()` in MainWindow-Init-Pfad → blockiert restliche
`__init__`-Steps + `window.show()` → User sieht nur Modal ohne Hauptfenster.
Fix: `QTimer.singleShot(0, fn)` deferred. Dieses Pattern ist Pflicht für
JEDEN Modal-Open-Aufruf der innerhalb von `MainWindow.__init__` liegt.

**K1:** PySide6 Signal-Emit nach C++-Object-Destroy wirft `RuntimeError`
(NICHT „swallowed", wie V2 fälschlich annahm). Worker-Pattern
verbindlich: lokale Referenz + `try/except RuntimeError` um jedes
`emit`. Auch wenn `self._connect_dialog is not None` geprüft wird —
zwischen Check und Call ist nicht atomar.

### Field-Test

V3 §8 6 Punkte F1-F6 ausstehend (Mike startet App selbst). Push
pending bis Field-Test grün — v0.95.16-0.96.9 + P2-Tool + P3 +
P21-Debug-Log + P26 zusammen.

---

## 2026-05-10 v0.96.8 — P21.DEBUG-LOG + DIV-MEAS-RADIO-GUARD

**Auslöser:** Mike-Field-Test 16:30 UTC v0.96.7: bei App-Start in
Diversity haengt MESSEN bei `0/6`, nur ANT1 dekodiert. Reproduzierbar
nach jedem App-Restart. Mike: „du stocherst da wie doof rum, mache ein
log wo das reingeschrieben wird was man auswerten kann" + „mach es zum
an und abwählen in den einstellungen wie Debug LOG schreiben".

**Mike-Strategie:** strategische Bisection-Debug-Punkte → wenn Eintrag X
da, Code lief bis dahin; wenn X fehlt, Bug VOR Stelle X. KISS, klassisches
Funker-Vorgehen („wo bricht der Signalweg?").

### Teil 1: P21.DEBUG-LOG Infrastruktur

**Code:**
- `core/debug_log.py` (NEU, 95 Zeilen): `debug_log(category, message)`
  Helper. 1 Datei pro Tag (`~/.simpleft8/debug_YYYY-MM-DD.log`),
  thread-safe, no-op wenn deaktiviert (kein Disk-Write). Cleanup beim
  App-Start: Dateien älter als gestern werden gelöscht.
- `ui/settings_dialog.py`: Block 5 in „Daten & Tools" mit Checkbox
  „Debug-Log schreiben" + sofort-Apply via `_dbg.set_enabled()`.
- `main.py`: `cleanup_old_files(keep_days=1)` + `set_enabled()` beim
  App-Start.
- `tests/test_debug_log.py` (NEU, 7 Tests): disabled no-op, enabled
  writes, cleanup keeps_recent + skips_unparseable + empty,
  disk-error no-crash.

**Strategische Debug-Punkte:**
- `_on_band_changed`: Anfang + IGNORED-Pfad + `on_band_change()`-Call
  + `_check_diversity_preset`-Call.
- `_check_diversity_preset`: Cache-Status (ratio + gain) + Branch-
  Entscheidung (gain_stale|missing|fresh).
- `_enable_diversity`: Pfad-Marker (CACHE-REUSE vs PHASE-MEASURE).
- `mw_cycle.py:_on_cycle_start`: Antennen-Switch SKIP-Pfade
  (encoder.is_transmitting | radio.ip | rx_active), SWITCH plan
  (vor Thread-Start), SWITCH done/FAILED (im Thread).
- `_handle_diversity_measure`: vor + nach `record_measurement`
  (ant + stations + score + step_pre/post).

### Teil 2: DIV-MEAS-RADIO-GUARD (Bug-Fix via Debug-Log-Diagnose)

**Diagnose aus Debug-Log:**
```
14:52:57.041 [ANT] SKIP — radio.ip=False rx_active=True
```
Beim App-Start ist `radio.ip` noch `False` (TCP-Connect noch nicht
durch), Audio-Stream läuft aber bereits über DAX (separater Pfad).
Antennen-Switch konnte nicht ausgeführt werden, aber `record_measurement`
lief trotzdem mit `ant=A1` (current_ant default) → Counter
inkrementierte mit falschen Daten → Mess endete mit garbage oder hing.

**Mike-Spec 17:00 UTC:** „Mess erst NACH Verbindung starten. Sobald
Radio verbindet, soll Mess natürlich anlaufen."

**Fix (`ui/mw_cycle.py:_handle_diversity_measure`):**
```python
if not self.radio.ip:
    _dlog("DIV-MEAS", "SKIP — radio.ip=False, warte auf Verbindung")
    return
```

Plus Korrektur eines fehlerhaften vorigen Edit-Versuchs: SKIP-Pfad-Log
und Antennen-Switch-Block waren in `if/elif` mit verschobener
Einrückung ineinander verschachtelt. Jetzt korrekt: SKIP-Log
unabhängig vor dem if-Block.

**Field-Test 17:03 UTC (Mike):**
1. App neu gestartet → MESSEN lief sauber durch (Pattern A1, A1, A2,
   A2, A1, A2 in 6 Slots, Phase wechselte measure → operate um 15:03:27)
2. P22 Atomic-Persist verifiziert: `presets_standard.json` 20m_FT8
   bekam **frischen** ratio_timestamp (15:03:27) + neue Werte
   (`30:70`, dominant `A2` — vorher 70:30/A1).
3. App neu gestartet (immer noch initial in Normal-Modus, kein
   schöner Fix → P24-TODO „letzten Modus merken"), Wechsel auf
   Diversity Standard → **Cache-Reuse-Pfad sauber:** Verstärker +
   Antennen-Verhältnis übersprungen (beide Werte frisch < 6h / < 1h),
   beide Antennen sofort aktiv.

**Atomare Commits (3):**
- `5c5128e` P21.DEBUG-LOG: Helper-Modul + Settings-Toggle + App-Start Init
- `b621f12` P21.DEBUG-LOG: Strategische Debug-Punkte
- `54cb7b5` P21.DIV-MEAS-RADIO-GUARD: Mess wartet auf Radio-Verbindung

**Test-Bilanz:** 1049 → 1056 grün (+7 Debug-Log-Tests).

**Workflow:** **KEIN voller V1→V2→R1→V3** weil Logging-Mechanik trivial
+ Mike-Spec eindeutig + Mike explizit „mach es". Nach Field-Test +
Bug-Diagnose: Skip-Fix als KISS-Patch ohne Workflow (Mike-Spec klar +
1 if-Block). Workflow-Lite ist OK wenn alle drei Bedingungen erfüllt.

**Offene Folge-TODOs:**
- P24 (NEU): App soll sich letzten RX-Mode merken (Normal/Diversity-
  Standard/DX) statt immer auf Normal zu starten.
- P25 (NEU): Diagnose warum `radio.ip` beim App-Start spät gesetzt wird
  obwohl Audio-Stream (DAX) bereits läuft. Connect-Pfad-Untersuchung.
  Skip-Fix verhindert Hänger, aber Wurzel ist nicht gefixt.

---

## 2026-05-10 v0.96.7 — P23.OMNI-COUNTER-EIGEN

**Auslöser:** Mike-Vorschlag 10.05.2026 nach P22-Code-Phase: OMNI-CQ-
Paritaets-Wechsel haengt heute am Diversity-Such-Counter (60s ×
`_OMNI_FLIP_AFTER_SEARCHES=10` = ~10 Min). Coupling zur Diversity-Mess-
Mechanik macht OMNI brüchig — wenn Mess hängt, kein Such-Trigger, kein
Wechsel. Mike will eigenen Counter: sichtbar, robust, unabhängig.

**Mike-Spec:**
- Counter pro Modus: FT8=10, FT4=20, FT2=40 (alle ~5 Min Wallclock)
- Counter zaehlt DOWN nach jedem TX. Bei 0: flip + Reset auf TARGET
- QSO eingehend → Counter Reset auf TARGET (positiv-Verstaerkung)
- Antennen-Mess fertig → Counter Reset auf TARGET ("neuer Slot")
- Bandwechsel/Modus-Wechsel → OMNI **stop** (heutiges Verhalten)
- Display: TX-Zeile bekommt Suffix `↻N` (z.B. `13:30:45 [O] →  Sende
  CQ DA1MHH JN58  ↻10`)
- Statusbar: `Ω CQ=10 (E)` mit Down-Counter

**Code-Änderungen:**
- `core/omni_cq.py`:
  - `_OMNI_TARGETS = {"FT8": 10, "FT4": 20, "FT2": 40}` neu
  - `_OMNI_FLIP_AFTER_SEARCHES = 10` weg
  - `_search_trigger_count` Feld weg, `on_search_trigger` Methode weg
  - `_cq_count` (UP) → `_cq_remaining` (DOWN) + `_cq_target`
  - `cq_count` Property → `cq_remaining` + `cq_target`
  - `start()`: target aus `timer.mode` abgeleitet
  - `on_cycle_start`: nach erfolgreichem TX dekrementieren, bei
    `remaining == 0` Auto-Flip + Reset, **GENAU 1 Emit pro Slot**
    (kein Zwischen-0 für UI-Flicker)
  - `resume_after_qso`: Counter Reset auf TARGET + Emit
  - `reset_counter_after_measure`: NEU — aus mw_cycle bei measure→operate
- `ui/mw_cycle.py`:
  - `_omni_cq.on_search_trigger()`-Hook in `_refresh_diversity_freq_view`
    (Z. 163-166) WEG
  - `_omni_cq.reset_counter_after_measure()`-Aufruf im Phase-Übergang
    measure→operate NEU
- `ui/qso_panel.py:add_tx`: optional `omni_remaining`-Parameter,
  Suffix `  ↻{n}` an Hauptzeile (KISS, ohne neuen Helper)
- `ui/mw_qso.py:_on_tx_started`: bei aktivem OMNI `omni.cq_remaining`
  durchreichen
- `ui/main_window.py`: `_on_omni_cq_count_changed` Parameter
  `count → remaining`. Statusbar nutzt `cq_remaining`.

**Tests:**
- `tests/test_omni_cq_signal.py` migriert: T8/T8b/T14 (search_trigger-
  Tests) **gelöscht**, T1/T3/T4/T10/T12/busy_encoder **angepasst**
  (cq_count → cq_remaining), Rest bleibt (16 grün, vorher 19).
- `tests/test_p23_omni_counter.py` NEU: 17 Tests T1-T16 + Bonus.

**Atomare Commits (8):**
- C1 `core/omni_cq.py` Counter-Refactor
- C2 `tests/test_omni_cq_signal.py` Migration
- C3 `ui/mw_cycle.py` Hook-Umbau (search-trigger raus, mess-reset rein)
- C4 `ui/qso_panel.py` add_tx Suffix
- C5 `ui/mw_qso.py` _on_tx_started Counter-Read
- C6 `ui/main_window.py` Statusbar-Update
- C7 `tests/test_p23_omni_counter.py` NEU
- C8 `main.py` APP_VERSION 0.96.6 → 0.96.7 + HISTORY/HANDOFF/CLAUDE/Memory

**Test-Bilanz:** 1035 → 1049 grün (+14 effektiv: 17 neue P23 - 3
gelöschte search_trigger).

**Workflow:** V1 → V2 (8 Self-Review-Lessons) → R1 (2 KRITISCH K1-K2 +
3 SOLLTE S1-S3 + 2 KOENNTE) → V3 (alle K + S adressiert: K1 Tests-
Migration explizit pro Test, K2 KISS-Variante ohne neuen
`_append_three_color`-Helper, S1 T7 Spy-Pattern explizit, S2 T17
Streichung dokumentiert, S3 erledigt durch K2). Mike-Klärung 3 Fragen
(Counter-Werte, Stop bei Bandwechsel, Pause bei Mess) vorweg geklärt.

**Field-Test pending (V3 §7, 5 Punkte F1-F5):**
F1 App-Start FT8+OMNI → Statusbar `Ω CQ=10 (E)`, TX-Zeile `↻10`
F2 5 Min beobachten → Counter 10→1, dann Auto-Flip + `↻10` in anderer Parität
F3 Modus-Wechsel zu FT4 → OMNI stop, neu an → `↻20`
F4 QSO eingehend → nach QSO Counter zurück auf TARGET
F5 Antennenmessung fertig → Counter zurück auf TARGET

**Plan-Files:**
- `prompts/p23_omni_counter_v1.md` (V1 initial, 10 Sektionen)
- `prompts/p23_omni_counter_v2.md` (V2 Self-Review, 8 Lessons)
- `prompts/p23_omni_counter_r1_prompt.md` + `_r1.md` (R1)
- `prompts/p23_omni_counter_v3.md` (Compact-fest, EINZIGE WAHRHEIT)

---

## 2026-05-10 v0.96.6 — P22.PRESET-ATOMARITAET + P8.MESS-MODAL

**Auslöser:** Mike-Diagnose 14:35 nach P17/P19-Resolve: Half-State im
`presets_dx.json` / `presets_standard.json` führt nach App-Restart zu
endlosen Phase-3-Versuchen wenn die Wurzel-Bedingung (z.B. Antennen-Switch
greift nicht) noch da ist. Phase 2 schreibt sofort persistent, Phase 3
schreibt nur bei Erfolg → Disk-Halbstand bei Hang/Crash/Cancel.

**Lösung — zwei zusammenhängende Bausteine:**

1. **Atomares Persist (P22):** Phase-2-Werte landen erst im Memory-Buffer
   (`stage_gain`). Phase-3-Erfolg committed Gain + Ratio gemeinsam
   (`commit_with_ratio`). Hang/Cancel/App-Quit → discard, kein Disk-Write.
   `is_valid_gain` lehnt Half-State (gain ohne ratio) explizit ab.
2. **Mess-Modal (P8):** WindowModal-Dialog während Phase 3 sperrt
   Hauptfenster (kein Bandwechsel/Modus/Hunt/CQ möglich), zeigt aktuelle
   Antenne + Schritt + Restzeit. Cancel-Button räumt staged + Diversity auf.

**Robustheit:**
- R1-K1: staged wird erst nach erfolgreichem `os.replace` aus dem
  Buffer entfernt. Bei Disk-Fehler bleibt staged für Retry, in-memory
  rollback.
- R1-K3: `save_gain` / `save_ratio` / `commit_with_ratio` fangen Disk-
  Exceptions, returnen False, App crasht nicht.
- Atomic File Write: `tempfile.NamedTemporaryFile` + `os.fsync` +
  `os.replace` (P2-Pattern). Verhindert korrupte JSON bei Mid-Write-Crash.
- WindowModal (NICHT ApplicationModal) — Decoder-Signale kommen weiter
  durch.
- App-Quit `closeEvent` cleart staged in beiden Stores.

**Bewusst nicht gebaut (Mike-Klärung 10.05.):**
- KEIN Stall-Detector / Auto-Fallback. Mike-Zitat: „Q1 ist nicht
  bestätigt das es an der Antennenmessung lag." Wurzel-Diagnose
  (Antennen-Switch greift nicht beim Mess-Start in DX) wird separat als
  P23 behandelt.

**Code-Änderungen:**
- `core/preset_store.py` (+158 Zeilen): `stage_gain`, `commit_with_ratio`,
  `discard_staged`, `discard_all_staged`, `has_staged`. `is_valid_gain`
  Half-State-Reject. Atomic `_save_locked`. `save_gain`/`save_ratio`
  Exception-Catch + Rollback + `bool` return.
- `ui/mess_status_dialog.py` (NEU, 158 Zeilen): MessStatusDialog
  WindowModal mit Tick-Timer, Cancel-Button, set_cycle_dur Helper.
- `ui/mw_radio.py` (+92 Zeilen): `_on_dx_tune_accepted` Pipeline-Pfad
  entscheidet zwischen `save_gain` (Normal/Cache-Reuse) und `stage_gain`
  (Diversity volle Pipeline). `_open_mess_status_dialog`,
  `_on_mess_status_cancelled`, `_close_mess_status_dialog` Helper.
  Modal-Open in `_enable_diversity` Phase=measure-Pfad.
- `ui/mw_cycle.py` (+24 Zeilen): `save_ratio` → `commit_with_ratio`
  mit Fallback. Adaptiv-Stop-Branch ruft `discard_staged`. Modal-Close
  beim Phase-Wechsel measure→operate.
- `ui/main_window.py` (+18 Zeilen): `closeEvent` cleart staged in beiden
  Stores + schliesst Modal hart falls offen.
- `tests/test_preset_store.py` (+150 Zeilen): T1-T8 + multi_band-Test.
  Bestehende Tests die Half-State-toleranz prüften → angepasst auf
  vollständigen Eintrag.
- `tests/test_p22_preset_atomic.py` (NEU, 290 Zeilen): T9-T18 Pipeline +
  Modal + Lifecycle.

**Atomare Commits (8):**
- C1 `core/preset_store.py` Atomic Methods
- C2 `tests/test_preset_store.py` T1-T8 + Anpassungen
- C3 `ui/mess_status_dialog.py` NEU
- C4 `ui/mw_radio.py` Pipeline + Modal-Helpers
- C5 `ui/mw_cycle.py` commit + Modal-Close
- C6 `ui/main_window.py` closeEvent staged-Cleanup
- C7 `tests/test_p22_preset_atomic.py` Pipeline+Modal-Tests
- C8 `main.py` APP_VERSION 0.96.5 → 0.96.6 + HISTORY/HANDOFF/Memory

**Test-Bilanz:** 1019 → 1034 grün (+15 nach Anpassung der 2 Half-State-
Tests, +13 neue PresetStore-Tests, +15 neue Pipeline+Modal-Tests).

**Workflow:** V1 → V2 (15 Self-Review-Lessons) → R1 (4 KRITISCH K1-K4 +
4 SOLLTE S1-S4 + 3 KOENNTE C1-C3) → V3 (R1-K1/K2/K3 angenommen,
K4 entfällt mit Stall-Detector-Verzicht; S1/S2/S3 angenommen;
S4/C1-C3 abgelehnt mit Begründung). Mike-Klärung Q1=nicht bauen,
Q2=Modal sperrt UI, Q3=Adaptiv-Stop weiter ohne Persist.

**Field-Test pending (V3 §8, 5 Punkte F1-F5):**
F1 App-Start DX → Modal öffnet, UI gesperrt.
F2 Mess läuft sauber durch → Modal auto-close, File hat beide Timestamps.
F3 Mid-Mess Cancel → discard, Diversity disabled, kein Half-State.
F4 Mid-Mess Cmd-Q → beim Restart `is_valid_gain==False`, volle Pipeline.
F5 Disk-Permission-Fehler → App crasht nicht, staged bleibt im Memory.

**Plan-Files:**
- `prompts/p22_preset_atomic_v1.md` (V1 initial)
- `prompts/p22_preset_atomic_v2.md` (V2 nach Self-Review)
- `prompts/p22_preset_atomic_r1_prompt.md` + `_r1.md` (DeepSeek-R1)
- `prompts/p22_preset_atomic_v3.md` (Compact-fest, EINZIGE WAHRHEIT)

---

## 2026-05-10 v0.96.4 — P7.OMNI-SIMPLIFY: Single-Slot + Such-Counter

**Auslöser:** P5 (Pending-Queue, v0.96.2) und P6 (Pair-Audio, v0.96.3)
lösten Pos-1-Encoder-Race nicht sauber:
- P5 Field-Test: Pending-Verfall (29.8s > 22.5s) → Pos 1 nie gesendet, Pattern halb tot
- P6 Field-Test: 27.6s durchgehend `_is_transmitting=True` blockt Diversity-
  Antennen-Switching → Mike sieht „nur eine Antenne"

**Wurzel:** TX-TX-konsekutiv in 15s-Slots passt physisch nicht zu Encoder
+ Diversity. Beide Workarounds verbiegen Encoder/Diversity um das alte
Pattern zu retten.

**Mike-Spec 10.05.:** Pattern ändern statt Encoder/Diversity verbiegen.
Diversity ist UNANTASTBAR (Kern-USP).

**Lösung:**
- OMNI = Single-Slot-CQ in EINER Paritaet (Even ODER Odd)
- Wechsel ueber existierenden Diversity-Such-Counter alle ~10 Min
  (`_OMNI_FLIP_AFTER_SEARCHES = 10` × 60s/Such bei FT8)
- Kein TX waehrend Diversity-Mess-Phase (90s alle 1h)
- Sticky Audio-Frequenz ueber Paritaets-Wechsel hinweg
- Counter pausiert automatisch bei QSO via existing `reset_search_counter()`

**Code-Aenderungen:**
- `core/encoder.py`: P5+P6 zurueckgerollt (-272 Zeilen). transmit_pair,
  _tx_pair_*, _pending_*, _run_one_tx_pass, _compute_target_slot WEG.
- `core/omni_cq.py`: 305 → 246 Zeilen (-19%). 5-Slot-Pattern + Block 1/2 +
  _pair_in_progress WEG. Neu: on_search_trigger, flip_tx_parity,
  cq_count_changed (1 Counter), parity_flipped Signals.
- `ui/mw_cycle.py:160`: 1-Zeile-Hook nach `tick_slot()==True` →
  `_omni_cq.on_search_trigger()`
- `ui/main_window.py`: Statusbar `Ω CQ=X (E/O/—)` statt Even/Odd-Doppel-
  Counter. _on_omni_slot_action vereinfacht zu pass.

**Robustheit:**
- V2-L9 / R1-SF-2: Fresh-Compute is_even aus `time.time()` (Schutz gegen
  P6-Beobachtung 14s Signal-Latenz)
- R1-SF-1: on_search_trigger prueft `_paused` (Defense-in-Depth)
- R1-SF-3: T14 Test fuer pause-noop

**Workflow:** V1 → V2 (Self-Review, 12 Lessons) → R1 (DeepSeek-Reasoner,
„V3 freigegeben für Code", 0 KRITISCH + 3 SOLLTE-FIX integriert) → V3
Compact-fest → Mike-Freigabe → Code C1-C7 → Final-R1 („Push freigegeben",
0 KRITISCH/SOLLTE/KOENNTE — minimalistisch und KISS-konform).

**Atomare Commits (7):**
- C1 (`ac254a5`): encoder.py P5+P6 zurueckrollen (-272 Z.)
- C2 (`3f98caf`): omni_cq.py radikale Vereinfachung (305 → 246 Z.)
- C3 (`741f526`): mw_cycle.py Such-Trigger-Hook (1 Zeile)
- C4 (`332c9f8`): main_window.py Signal+Statusbar
- C5 (`956ef61`): tests neu T1-T14 + alte raus (-524 Z. netto)
- C6 (`3111cfe`): APP_VERSION 0.96.3 → 0.96.4
- C7: Doku (HISTORY + HANDOFF + CLAUDE + TODO + Memory + Spec)

**Tests:** 1024 → **1008 grün** (-16 netto: 13 alte raus, 19 neue rein).
V3-Plan war ~1005, +3 Bonus.

**Code-Bilanz:** netto **~800 Zeilen weniger Code** im Repo (Encoder + OMNI
+ Tests).

**APP_VERSION:** v0.96.3 → v0.96.4. Push pending bis Mike-Field-Test grün.

**P8.MESS-STATUS-DIALOG:** geplant nach P7 (Modal-Dialog während 90s
Diversity-Mess-Phase). In `TODO.md` dokumentiert.

---

## 2026-05-10 v0.96.2 — P5.OMNI-PATTERN-FIX-3: Encoder-Pending-Queue + Slot-Boundary-Display

**Auslöser:** Field-Test 10.05.2026 ~06:30 UTC (v0.96.1) zeigte 2 Issues:
- Issue B (kritisch): Pos 1 (TX-nach-TX) IMMER busy (3× im Log
  reproduziert), Pattern halb tot.
- Issue A (kosmetisch): `add_listening`-Zeit zeigt Wall-Time
  (`time.time()`) statt UTC-Slot-Boundary `:00`/`:15`/`:30`/`:45`.

**Wurzel Issue B (R1-bestätigt):** FT8 12.64s Audio + 1.3s
FlexRadio-Buffer-Drain + PTT-Off + Thread-Jitter → `_is_transmitting=False`
fällt bei `:42.8-:44.5`. Pos 1 cycle_start `:45` hat Race-Window
0-2.2s, in Praxis < 1s wegen Buffer-Drain → 100% busy.

**Lösung Variante A (R1-Empfehlung, KISS-konform):** Encoder-Queue mit
Pending-Verfall. `transmit()` queut Pending statt `return False`.
Worker-Finally konsumiert Pending direkt via `_run_one_tx_pass`-Loop.
Verfall-Schwelle `1.5 * cycle_duration` (FT8: 22.5s). `_pending_tx +
_pending_queued_at` UNTER `_replace_lock` (R1-KRITISCH gegen Race).

**F1-KRITISCH (Cold-Start-Test entdeckt):** Abort-Race im Pending-Loop —
`_run_one_tx_pass` cleart `_abort_event` und setzt `_is_transmitting=True`.
Wenn `abort()` zwischen Pass-1 und Pending-Re-Trigger feuert, geht abort
verloren. **Fix:** `if self._abort_event.is_set(): return` VOR Re-Trigger.

**Lösung Issue A:** `main_window.py:760` `add_listening(time.time(), ...)`
→ `add_listening((now // cycle_dur) * cycle_dur, ...)`. Löst gleichzeitig
die Phänomene "Pos 4 RX-E fehlt" und ":44 [O] Horche" durch korrekte
Slot-Boundary-Anzeige (R1's Display-Bug-Diagnose: Wall-Time-Verschiebung
um 0.1-0.4s ließ Einträge "verschoben"/"fehlend" wirken). 1 Stein, 3 Fliegen.

**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek-Reasoner) → V3
(Compact-fest) → Cold-Start-Test → Mike-Freigabe → Code → Final-R1 →
Field-Test pending. Plan-Files: `prompts/p5_omni_pattern_fix3_*`.

**Atomare Commits (6):**
- C1 (`229e98c`): `core/encoder.py` Pending-TX-Queue + Verfall + F1-Abort-Schutz
- C2 (`96f5714`): `tests/test_encoder_pending.py` NEU (T1, T9-T13, 8 Tests)
- C3 (`333411a`): `ui/main_window.py:760` Slot-Boundary in `add_listening`
- C4 (`955aeb0`): `tests/test_main_window_slot_boundary.py` NEU (T7+T8) +
  `tests/test_omni_cq_signal.py` ERWEITERT (T2N Pending-Counter)
- C5 (`31f2f41`): `main.py:16` APP_VERSION 0.96.1 → 0.96.2
- C5a (`5408534`): Final-R1-Review + Test-Werte-Korrektur (R1's SOLLTE-FIX)

**Final-R1-Bilanz:** 0 KRITISCH + 1 SOLLTE-FIX (parametrize-Werte
rechnerisch korrigiert) + 1 KOENNTE (FT2-Floating-Point akademisch).
R1-Quote: „Push freigegeben. Code ist merge-bereit."

**Tests:** 1020 → **1034 grün** (+14, V3 prognostizierte ~1029,
+5 Bonus durch Test-Splits T11a+b, T12+b, T7-Querschnitt).

**APP_VERSION:** v0.96.1 → v0.96.2. Push pending bis Mike-Freigabe nach
Field-Test 7-Punkte-Plan F1-F7 (V3 §6).

**R1-Blindspot-Lesson aktiviert:** Bei TX-TX-Konsekutiv-Plänen MUSS R1
explizit nach Encoder-Throughput gefragt werden. Bei P4-V5 hatte R1 das
verpasst → Field-Test-Bug. P5-Prompt hatte die Pflicht-Frage explizit
enthalten — R1 hat den Race korrekt diagnostiziert.

**Cold-Start-Test bewährt:** F1 KRITISCH wurde NUR durch Cold-Start-Test
nach Compact-Vorbereitung gefunden — R1 + Self-Review hatten ihn
übersehen. Bestätigt `feedback_compact_save_cold_start_test.md`.

---

## 2026-05-10 — P5.OMNI-PATTERN-FIX-3 vorbereitet (kein Code-Bump)

**Auslöser:** Field-Test v0.96.1 (P4-V5) ~06:30 UTC zeigte zwei Issues:

1. **Issue B (kritisch):** Pos 1 (TX nach TX) IMMER encoder-busy →
   Pattern halb tot. Log: `[OMNI-CQ] encoder.transmit busy -> Slot
   B1 [1/4] TX-O uebersprungen` (3× pro Toggle-Run reproduziert).
   Pos 4 RX-E fehlt zusätzlich im qso_panel-Display.
2. **Issue A (kosmetisch):** Horche-Zeile zeigt Wall-Time
   (z.B. `04:26:44`) statt UTC-Slot-Boundary (`:45`).

**Wurzel Issue B:** Encoder-Worker-Thread setzt `_is_transmitting=False`
im `finally` ~:43.5-:44 (FT8 15s Slot, TX-Audio :30-:43.5). Pos 1
cycle_start kommt :45 — Race-Window 0.5-1.5s. Praxis: bei FT8 ist
Pos 1 IMMER busy. V3 §8 (P4-V5 Out-of-Scope) hatte Encoder-Queue +
Mid-Cycle-Pretrigger explizit verboten — der Race ist
architektonisch eingebaut.

**R1-Blindspot dokumentiert:** R1 hat in P4-V5 Klärungsfrage 3
(Decoder-Blockade) Variante A „kein Schutz" als KISS abgesegnet,
aber den Encoder-Throughput-Race nicht erkannt. Neue Pflicht-Lesson
`feedback_r1_encoder_busy_blindspot.md` mit Checkliste für künftige
Pläne mit konsekutiven TX-Slots.

**Vorbereitete Files (kein Code-Bump, nur Doku/Plan):**

- `prompts/p5_omni_pattern_fix3_diagnose.md` — Compact-feste Diagnose:
  Symptome, Wurzel-Analyse, 4 Lösungsoptionen A-D mit Trade-offs,
  AC-Vorschlag (B1-B6 + A1-A2 + Z1-Z2), R1-Fragen-Liste.
- `memory/project_p5_omni_pattern_fix3.md` — Trigger-File mit 16-Punkt-
  Anleitung. Triggers: „omni pattern fix3 starten" oder „p5 starten".
- `memory/feedback_r1_encoder_busy_blindspot.md` — neue Pflicht-Lesson.
- `memory/MEMORY.md` — Index ergänzt mit P5-Trigger + Lesson.
- `HANDOFF.md` — Stand aktualisiert (P5 vorbereitet, fresh-Instanz
  übernimmt).
- `TODO.md` — P5 als TOP-Item.

**Lösungsoptionen für P5 (R1 zur Bewertung in V2-Workflow):**

| Option | Kern | Trade-off |
|---|---|---|
| A | Encoder-Queue zurück | Wenig OMNI-Code, V3-§8-Verbot kippen |
| B | Mid-Cycle-Pretrigger via cycle_tick | Wie P2.OMNI-PATTERN-FIX, V3-§8 kippen |
| C | Pattern auf 3 Slots (1 TX) | Mike-Spec ändern, kein Race |
| D | TX-Slots nicht-konsekutiv (Pos 0 + Pos 2) | Mike-Spec ändern, Encoder-Idle dazwischen |

Mike-Empfehlung (mein Vorschlag): **Variante A** — KISS-konform,
keine Mike-Spec-Änderung, einziger Verstoß: P4-V3-§8-Verbot kippen
(gerechtfertigt durch Field-Test-Evidence).

**APP_VERSION-Plan:** v0.96.1 → v0.96.2 (Patch-Bump nach P5-Code).

**Push-Status:** weiterhin KEIN Push seit v0.95.16. Lokal v0.95.16-0.96.1
+ P2-Tool. Push wartet bis P5 Field-Test grün.

**Tests aktuell:** 1020 grün (unverändert seit v0.96.1 C9).

---

## 2026-05-10 — Symlinks für CLAUDE.md + HANDOFF.md (kein Code-Bump)

Mike hat manuell `FT8/CLAUDE.md` und `FT8/HANDOFF.md` als Symlinks auf
die echten Dateien in `SimpleFT8/` gesetzt:

```
FT8/CLAUDE.md  -> SimpleFT8/CLAUDE.md
FT8/HANDOFF.md -> SimpleFT8/HANDOFF.md
```

Damit entfällt die „in BEIDEN Verzeichnissen identisch updaten"-Regel.
Folgende Stellen wurden bereinigt (Pflicht-Doku, kein Workflow-Skip
da Doku-only):

- `SimpleFT8/CLAUDE.md` — Reihenfolge-Block reduziert auf 1 Pfad +
  Symlink-Hinweis.
- `SimpleFT8/feierabend.md` — komplett umgeschrieben, nur SimpleFT8/-Pfade.
- `SimpleFT8/docs/SESSION_WORKFLOW.md` — Datei-Matrix + Phase 2 + Phase 3
  Bestätigungs-Block: alle „beide Pfade"-Hinweise raus.
- `memory/MEMORY.md` — Index-Eintrag angepasst.
- `memory/feedback_todo_history_pflicht.md` — Sequenz auf 1 Pfad +
  Symlink-Hinweis.
- `memory/feedback_session_lifecycle.md` — Phase 2 Block.

Historische Dateien (`prompts/*_v[1-3].md`, `project_*_in_progress.md`)
wurden nicht angefasst — sind Snapshots.

---

## 2026-05-10 v0.96.1 — P4.OMNI-NEUBAU V5: Worker-Thread-Bug gefixt durch Signal-Refactor

**Auslöser:** Field-Test 09.05.2026 mit Mike (v0.96.0) zeigte Pattern komplett
kaputt — Pos 2/3/4 alle in einem Slot statt verteilt über 45 s. Wurzel:
Worker-Loop in `core/omni_cq.py` rief `_advance_state` direkt nach `emit`,
nächste Iteration berechnete `_compute_next_boundary` mit `now` der noch
VOR der gerade verarbeiteten Boundary lag → lieferte dieselbe Boundary →
`sleep_dur ≤ 0` → emit sofort. Pos 2/3/4 rasten in EINEM Slot durch.

**Lessons-Learned (zentral):** Die 37 Worker-Tests waren grün weil ein
Helper `_block_worker_boundaries` genau die sleep-Logik überschrieb die
der Test eigentlich prüfen sollte (Worker schläft 100 s in `stop_event.wait`,
kritischer Pfad nie getriggert). Tests die den kritischen Pfad wegmocken
sind keine Tests. Memory: `feedback_test_critical_path_not_mock.md`.

**Architektur-Refactor (V5, Mike-Vorschlag):** kopiere wie Normal-CQ
funktioniert — nutze `FT8Timer.cycle_start`-Signal das 1× pro 15 s-Slot
emittet. `OmniCQ.on_cycle_start(@Slot int, bool)` läuft im GUI-Thread.
Kein Worker-Thread, keine Sleep-Logik, keine Boundary-Berechnung.

**Workflow:** V1 (236 Z.) → V2 (370 Z., 6 Self-Review-Findings + 3
Mike-Klärungen) → R1 DeepSeek-Reasoner („Spezifikation durchdacht und
weitgehend widerspruchsfrei", 10 Findings + 3 Klärungs-Stellungnahmen
alle Variante A KISS) → V3 (476 Z., Compact-fest, 22 Tests T1-T22) →
Cold-Start-Test (10/10 Code-Pfade verifiziert).

**core/omni_cq.py (337 → ~250 Z., komplett umgeschrieben):**
- `start()` IMMER Block 1 (R1-bestätigt KISS, AC5). Idempotent.
- 5-Slot-Pattern (TX-TX-RX-RX-RX). Block 1 Even-First, Block 2 Odd-First.
  Auto-Rollover bei `_slot_index 4 → 0` (`_advance_state`).
- `on_cycle_start(cycle_num, is_even)`: Defense-Guard
  `if not _active or _paused: return`, Pattern-Decision via `_slot_index`,
  TX (Pos 0/1) → `encoder.transmit(msg, tx_even=..., audio_freq_hz=...)`,
  RX (Pos 2/3/4) → `slot_action.emit(label, is_tx=False, is_even)`.
- `pause()` setzt `_paused=True`, `_active` bleibt — Slot-Index friert ein.
- `resume_after_qso(last_was_even)`: Block-Wahl (Even → Block 2,
  Odd → Block 1), Pre-Check `if not _paused: return`, ab Pos 0,
  `_cq_audio_hz` BLEIBT (AC14).
- Frequenz-Sticky 1× am ersten TX setzen, fest bis `stop()` (AC13).
- `encoder.transmit` busy (False): kein Counter, kein `slot_action`,
  `_slot_index` advanced trotzdem (AC10/AC11, KISS).
- 5 Signals: `omni_started`, `omni_stopped(reason)`,
  `slot_action(label, is_tx, target_even)`, `cq_freq_changed(int)`,
  `counter_changed(even, odd)`.

**ui/mw_cycle.py:** 1 Zeile am Ende von `_on_cycle_start` (nach
`qso_sm.on_cycle_end()`, vor Diversity-Block) — `hasattr`-Guard für
isolierte Test-Setups.

**Tests:**
- `tests/test_omni_cq_worker.py` GELÖSCHT (37 Tests obsolet, Worker-Mock
  versteckte kritischen Pfad).
- `tests/test_omni_cq_signal.py` NEU — 22 Test-Funktionen T1-T22,
  durch parametrize 31 effektive Tests. KEIN Worker-Mock, KEIN Sleep-Mock,
  KEIN Boundary-Mock — Tests rufen `on_cycle_start` direkt auf.
- `tests/test_omni_cq_integration.py` migriert (`_compute_next_boundary`-
  Lambda raus, kein Thread mehr).

**Test-Bilanz:** 1026 → 1020 grün (V3 erwartete ~1010, parametrize +9).

**Hardware:** OMNI emittet kein TX direkt — `encoder.transmit()` setzt
zentral `radio.set_tx_antenna("ANT1")` (`core/encoder.py:363`).

**APP_VERSION:** 0.96.0 → 0.96.1 (Patch-Bump: Bug-Fix Architektur-Refactor).

**2 atomare Commits:**
- C9: `core/omni_cq.py` Refactor + Tests + 1-Zeile-Connect.
- C10: APP_VERSION + Doku (HISTORY + HANDOFF beide + CLAUDE beide + Memory).

**Plan-Files:** `prompts/p4_omni_neubau_v5_signal_v[1,2,3].md` + `_r1.md`.

**Field-Test (Mike, V3 §6 17 Punkte F1-F17) + Push pending.**

---

## 2026-05-09 — DeepSeek-R1-Workflow-Optimierung + Tool-Fixes

**Auslöser:** Analyse der DeepSeek-Integration (128K-Upgrade-Session) — zwei
stille Bugs in den Review-Scripts + veraltete Stellen in Doku gefunden.

**tools/deepseek_review.py:**
- `temperature: 0.3` entfernt — R1 unterstützt den Parameter nicht, wurde
  stillschweigend ignoriert.
- `max_tokens` 8000 → 16000 — R1 verbraucht 4-8K Tokens intern für seine
  Reasoning-Chain; bei 8000 blieben nur 2-3K für die eigentliche Antwort.
- Warnschwelle 60K ("65K") → 110K ("128K").

**tools/deepseek_review_high.py:**
- `temperature: 0.3` entfernt.

**docs/WORKFLOW.md → v1.2:**
- Context-Limit 65K → 128K (~512KB Code).
- Ergänzt: R1 hat kein "lost in the middle"-Problem (MoE + MLA Architektur).
- Neue Guideline: Files >500 Zeilen splitten oder relevante Sektion extrahieren.

**CLAUDE.md:**
- Z. 238: `pal chat model deepseek-chat` → `tools/deepseek_review.py` (veraltet seit 28.04.).
- Context-Angabe 65K → 128K.
- Modul-Tabelle: `omni_tx.py` DEAKTIVIERT → aktueller Stand `omni_cq.py` v0.96.0+.

**TODO.md:**
- META-Abschnitt: CLAUDE.md + Memory Restrukturierungsplan (Trigger: "claude.md restrukturieren").

---

## 2026-05-09 v0.96.0 — P4.OMNI-NEUBAU: eigenständiger OMNI-Worker, kein qso_state-Hack mehr

**Architektur-Refactor nach 4 Fehlversuchen v0.95.22-25.** OMNI-CQ ist
jetzt ein eigenes Modul `core/omni_cq.py` mit eigenem Worker-Thread und
absolut-UTC-Slot-Boundaries (Vorbild `core/encoder.py:_tx_worker`). Kein
`qso_state.cq_mode`-Hack, kein `cycle_tick`-Pretrigger, keine
Encoder-Queue.

**3-Schichten-Architektur (V3 §1):**
- Normal-CQ → `qso_state.cq_mode` (unverändert)
- OMNI-CQ → `core/omni_cq.OmniCQ` (NEU, eigener Worker)
- Gemeinsamer QSO-Hunt-Pfad bei eingehender Antwort: Listener in
  `mw_cycle.on_message_decoded` ruft `qso_state.start_qso(...)` —
  selbe State-Machine wie Hunt-Klick.

**Voller Workflow:** Schritt 0 (Code-Verifikation) → V1 → V2 (20
Lessons L1-L20) → R1 (DeepSeek-Reasoner: 17/20 ✅ + 5 Findings R1-R5)
→ V3 (961 Z., Compact-fest, alle Findings eingearbeitet) → Final-R1
(„V3 ist implementierungsreif, 0 KP, 4 nicht-blockierende Hinweise
F-1..F-4") → Cold-Start-Test (Mike) fand 4 weitere ⛔-Bugs in V3
(`self._timer` falsch, `my_call`/`my_grid` als Attribut existieren
nicht, `auto_hunt.cancel()` existiert nicht, RX-Slot-Parität
hardcoded) → V3 §0.5 NEU mit verifizierter Code-Pfad-Tabelle → Mike-
Freigabe → Compact → Code (8 atomare Commits).

**8 atomare Commits:**
- **C1** (`b813c53`) Migration alte OMNI-Tests RAUS — 6 Files / ~87
  Tests gelöscht (test_p1_omni_start, test_p2_omni_redesign,
  test_p2_omni_pattern_fix, test_p3_omni_pattern_fix2, test_omni_tx,
  test_encoder_queue).
- **C2** (`678fc44`) NEU `core/omni_cq.py` (~340 Z.) — `OmniCQ(QObject)`
  mit Signals (omni_started/stopped, slot_action, cq_freq_changed,
  counter_changed), 5-Slot-Pattern (TX-TX-RX-RX-RX), Block 1 Even-First
  / Block 2 Odd-First, Sticky-Frequenz mit Recheck alle 4 Blöcke, R1
  R1-R3 Defense (PRELEAD 2.0s, encoder.tx_even im Listener, Worker-
  Join in resume_after_qso). Plus `tests/test_omni_cq_worker.py` mit
  37 Unit-Tests (T1-T20 + 2 Bonus + parametrize-Splits).
- **C3** (`1d76457`) `encoder.transmit(message, *, tx_even=None,
  audio_freq_hz=None) -> bool` — atomare API, Setter unter
  `_replace_lock` zusammen mit is_transmitting-Check. Queue
  (`_pending_tx_message`) + Outer-Loop in `_tx_worker` raus (war
  P2-OMNI-Workaround, nicht mehr nötig). P1.9 `request_replace` bleibt.
- **C4** (`037806c`) Rückbau `core/qso_state.py` — `_omni_skip_state_change`
  + `_was_pretriggered` Flags + on_cycle_end-CQ_WAIT-Pretrigger-Schutz
  raus. `_send_cq()` wieder linear: emit + `_set_state(CQ_CALLING)`.
- **C5** (`b58c5df`) Rückbau `ui/mw_cycle.py` — `_omni_pretrigger_check`
  + `_omni_pretrigger_fire_impl` + `_OMNI_PRETRIGGER_OFFSET_S` raus.
  `_on_cycle_start` ohne `omni_tx.advance()` und QTimer-Start. Plus
  Cleanup in `main_window.py` (QTimer-Init + Connect zu nicht-
  existierender Methode raus) + `mw_qso.py` (defensiver
  `qso_sm._was_pretriggered=False` raus).
- **C6** (`aa622b8`) Anschluss `main_window.py` (OmniCQ-Init + 4
  Signal-Slots, `_on_btn_omni_cq_toggled` Rewrite ohne
  `qso_sm.start_cq()`, R1 R4 Defense in `_on_omni_stopped`, neue Slots
  `_on_omni_freq_changed` / `_on_omni_counter_changed` /
  `_on_omni_slot_action`, `_update_statusbar` Ω migriert) +
  `mw_qso.py` (`_pause_omni_if_active` API, `_maybe_resume_omni` mit
  Caller-Queue-Pop V2-L10, `_on_tx_finished` `_last_qso_tx_even`
  V2-L3, `_on_send_message` OMNI-Bypass-Block KOMPLETT raus,
  `_on_cancel` HALT auf omni_cq.stop) + `mw_cycle.on_message_decoded`
  (Listener-Pfad mit `_pause_omni_if_active` + `encoder.tx_even = not
  msg._tx_even` + `qso_state.start_qso`, R1 R2!). Plus 14
  Integration-Tests `tests/test_omni_cq_integration.py` (I1-I14 mit
  `_FakeMW(QSOMixin, CycleMixin)`-Helper).
- **C7** (`19cbada`) Stop-Trigger `mw_radio.py` (3 Stellen:
  `_on_mode_changed` → mode_change, `_on_band_changed` → band_change,
  `_on_rx_mode_changed` → rx_mode_change). Auto-Hunt-Coupling +
  Totmann + HALT in `main_window` wurden bereits in C6 mitmigriert.
- **C8** (dieser) Löschen `core/omni_tx.py` (~250 Z.) + 7 OMNI-TX-
  Direktreferenz-Tests aus `test_modules.py` und `test_patterns.py`.
  APP_VERSION 0.95.25 → 0.96.0. Doku (HISTORY+HANDOFF+CLAUDE+Memory).

**Geänderte Files:** 15 Code/Test (1311 +, 2045 −, netto -734 Zeilen).
NEU: `core/omni_cq.py`, `tests/test_omni_cq_worker.py`,
`tests/test_omni_cq_integration.py`. GELÖSCHT: `core/omni_tx.py`,
`tests/test_p1_omni_start.py`, `tests/test_p2_omni_redesign.py`,
`tests/test_p2_omni_pattern_fix.py`, `tests/test_p3_omni_pattern_fix2.py`,
`tests/test_omni_tx.py`, `tests/test_encoder_queue.py`.

**Test-Bilanz:** 1069 → 1026 grün (-43 netto). C1 -87, C2 +37, C6 +14,
C8 -7. Alle Tests nach jedem Commit grün.

**R1-Findings R1-R5 (alle in V3+Code adressiert):**
- R1 ⛔ `_OMNI_TX_PRELEAD_S`=2.0 (von 1.5 — 0.7s Marge zu Encoder-Wake)
- R2 ⛔ `mw_cycle.on_message_decoded` setzt `encoder.tx_even = not
  msg._tx_even` VOR `start_qso` (analog mw_qso:171-176)
- R3 ⚠️ `resume_after_qso` joint alten Worker (Defense-in-Depth)
- R4 ⚠️ `_on_omni_stopped` setzt `_omni_was_active_pre_qso=False`
- R5 dokumentiert: 2 Antworten in 1 RX-Slot — zweite ignoriert (akzeptabel)

**Final-R1-Hinweise F-1..F-4:** alle in V3 §4 dokumentiert,
nicht-blockierend, kein zusätzlicher Code-Change nötig.

**Hardware-Garantie ANT1:** OMNI emittet kein TX direkt — ruft
`encoder.transmit(...)` auf, der zentral
`radio.set_tx_antenna("ANT1")` setzt (`core/encoder.py:334`). Kein
Extra-Check nötig.

**Field-Test-Pflicht (Mike, vor Push):** V3 §6 17-Punkte-Plan F1-F17
(10-Slot-Loop = Pattern-Beweis, Block-Wechsel slot 4→0, CQ-Antwort
mid-OMNI mit Resume + Block-Wahl, alle 5 Stop-Reasons,
Auto-Hunt-Coupling in beide Richtungen, RX-Slot „Horche...",
Caller-Queue mit OMNI-pausiert).

**Push pending** — v0.95.16-0.96.0 + P2-Tool zusammen wenn Field-Test
positiv.

---

## 2026-05-09 v0.95.25 — P3.OMNI-PATTERN-FIX-2: QTimer-Pretrigger + Button-Label + RX-Slot-Horche

**Mike-Field-Test v0.95.24, 09.05.2026 11:55-12:00 UTC:** OMNI-Pattern
hat alle ~75s nur 1 TX statt der erwarteten 2-TX-3-RX-Sequenz. Plus
Button-Label „OMNI CQ" zeigt nicht ob OMNI aktiv → Mike klickt mehrfach.
Plus QSO-Panel still in 3 von 5 Slots → kein Lebenszeichen.

**4 Probleme:**
1. **GUI-Tick-Latency** (KRITISCH) — Decoder blockiert GUI-Thread →
   `cycle_tick` kommt erst bei `cycle_pos=14.89s` rein. Pretrigger
   feuert zu spaet → Encoder `silence_secs = 15.0 - 1.3 - 14.89 = -1.19`
   → overshoot=1.19s > 0.3s → v0.80 Fix B Drift-Schutz schiebt 2 Slots
   weiter → Pattern verschoben.
2. **Button-Label statisch** — `QPushButton("OMNI CQ")` zeigt nicht ob
   aktiv. Mike klickt mehrfach aus Unsicherheit → permanenter
   `manual_halt`.
3. (verworfen V2-L3) — V1 hatte User-Start-Drift-Schutz mit
   `_OMNI_USER_START_GUARD_S = 1.5s` geplant. V2 zeigte via Code-
   Verifikation `core/encoder.py:_next_slot_boundary`: bei mid-cycle
   Toggle-On waehlt Encoder den NAECHSTEN passenden Slot mit
   `silence_secs > 14s` → kein Drift. User-Start-Delay verworfen, spart
   2 Tests + Race-Risk.
4. **RX-Slots stumm** — Mike sieht im QSO-Panel keine Lebenszeichen
   in 3 von 5 Slots des OMNI-Patterns.

**Loesung (R1-bestaetigt, V3 Plan):**

1. **QTimer.singleShot mit Qt.PreciseTimer** (`ui/main_window.py:__init__`):
   Persistente Instanz-Variable `_omni_pretrigger_timer` mit
   `setSingleShot(True)` + `setTimerType(Qt.TimerType.PreciseTimer)`
   + timeout-Connect zu `_omni_pretrigger_fire_impl` (Mixin-Methode in
   CycleMixin). In `mw_cycle._on_cycle_start` mit
   `delay_ms = (cycle_duration - 1.3s) * 1000` gestartet wenn OMNI
   active + nicht paused. Restart-Semantik: `start()` nach `start()`
   ersetzt alten Timeout. Garantiertes Timing ~50ms genau gegen
   >1500ms bei cycle_tick-Signal-Queue (durch Decoder-Blocking).

2. **Cycle-Tick-Pretrigger als Fallback** (`mw_cycle._omni_pretrigger
   _check`): refactored zu Defense-in-Depth mit Schwelle `dur - 0.5s`.
   Greift nur wenn `_omni_pretriggered=False` (= QTimer hat NICHT
   gefeuert). Log-Marker `[OMNI-Pretrigger-FALLBACK]`.

3. **Button-Label dynamisch** (`ui/control_panel.py:update_omni_tx`):
   Button-Text wechselt synchron mit Ω-Symbol-Visibility:
   `active=True` → „OMNI CQ (aktiv)", `active=False` → „OMNI CQ".
   `hasattr`-Guard fuer Init-Race.

4. **`add_listening`** (`ui/qso_panel.py`): Neue Methode mit Format
   `HH:MM:SS [E/O] ←  Horche  …` in Grau (#666666). Aufruf in
   `mw_qso._on_send_message` RX-Slot-Skip-Pfad (zusaetzlich zu
   bestehendem `print` + `_omni_skip_state_change=True`).
   Spam-begrenzt durch existierendes `_auto_trim_by_age(300)`.

**Voller Workflow:**
V1 (`prompts/p3_omni_pattern_fix2_v1.md`) →
V2 15 Lessons (`p3_omni_pattern_fix2_v2.md`, V2-L3 verwirft V1's
User-Start-Drift-Schutz) →
R1 DeepSeek-Reasoner („V2 ist bereit für die Umsetzung", 0 KP, alle
15 Lessons bestätigt) →
V3 Compact-fest 15 ACs / 10 Tests / 3 atomare Commits
(`p3_omni_pattern_fix2_v3.md`) → Mike-Freigabe → Code (3 Commits) →
**Final-R1 (DeepSeek-Reasoner, in=82409/out=1593 Tokens: „Der Compact
ist bereit für die Umsetzung. Ich sehe keine inhaltlichen Lücken oder
Widersprüche.", 0 KP-Findings, alle ACs verifiziert + Risiken
mitigiert)**.

**R1-Final-Findings:** alle 4 Problem-Loesungen bestaetigt, alle 6
Risiken (R1-R6) mitigiert. „Field-Test mit 10-Slot-OMNI-Loop ist der
finale Beweis."

**Geaenderte Files (5 Code + 1 Test NEU + main.py + 4 Plan-Files):**

- `ui/main_window.py` (Commit 1):
  - `__init__`: `_omni_pretrigger_timer = QTimer(self)` mit
    `setSingleShot(True)` + `setTimerType(Qt.TimerType.PreciseTimer)`
    + `timeout.connect(self._omni_pretrigger_fire_impl)`
  - `_on_omni_stopped`: `self._omni_pretrigger_timer.stop()`
    zentral fuer alle Stop-Reasons (manual_halt, ft_mode_change,
    band_change, rx_mode_change, totmann_expired, easter_egg_off,
    superseded — alle laufen ueber `omni_stopped`-Signal).

- `ui/mw_cycle.py` (Commit 1):
  - `_omni_pretrigger_fire_impl` NEU — gemeinsame Logik fuer QTimer +
    Fallback (peek_next + tx_even + `_was_pretriggered=True` +
    `_send_cq`). Idempotent ueber `_omni_pretriggered`-Flag.
  - `_on_cycle_start` ergaenzt: `if active+!paused: timer.start(delay_ms)`
    mit Mathematik-Kommentar (V2 L2 sicheres Fenster
    `[dur-1.3, dur-0.8]` 500ms breit).
  - `_omni_pretrigger_check` refactored zu Fallback-Pfad mit Schwelle
    `dur - 0.5s` und Log-Marker `[OMNI-Pretrigger-FALLBACK]`.

- `ui/control_panel.py` (Commit 2):
  - `update_omni_tx` ergaenzt: `btn_omni_cq.setText(...)` synchron mit
    Ω-Symbol-Visibility und Versions-Label-Color.

- `ui/qso_panel.py` (Commit 3):
  - `add_listening(slot_start_ts: float, tx_even: bool)` NEU —
    schreibt formatierte Zeile in Grau.

- `ui/mw_qso.py` (Commit 3):
  - `_on_send_message` RX-Slot-Skip-Pfad ruft
    `qso_panel.add_listening(slot_start, is_even)` mit time.time()-
    basiertem Slot-Start.

- `main.py` APP_VERSION 0.95.24 → 0.95.25.

- NEU `tests/test_p3_omni_pattern_fix2.py` (21 Tests):
  - T1, T1b: QTimer-Schedule mit korrekter Delay (FT8 13700ms /
    FT4 6200ms)
  - T11, T12: kein Timer-Start bei inactive/paused OMNI
  - T10: Restart-Semantik (2x cycle_start → 2x start)
  - T2, T2b, T2c: Fire-Impl Pre-Conds, Idempotenz, RX-Slot-Skip
  - T8, T8b, T8c: Fallback-Schwelle, Doppel-Trigger-Schutz,
    below-threshold-no-fire
  - T3, T3b, T3c: Button-Text aktiv/inaktiv/synced mit `_omni_active`
  - T6: RX-Slot-Skip ruft add_listening (Integration mit
    `_on_send_message`)
  - T7, T7b, T7c: add_listening Format Even/Odd/Timestamp aus
    `slot_start_ts`
  - T9, T9b: `_on_omni_stopped` cancelt Timer fuer alle 7
    Stop-Reasons (manual_halt, ft_mode_change, band_change,
    rx_mode_change, totmann_expired, easter_egg_off, superseded)
  - Plus Sanity-Constant-Test (`_OMNI_PRETRIGGER_OFFSET_S == 1.3`)

- Plan-Files: `prompts/p3_omni_pattern_fix2_v[1-3].md`.

**Tests:** 1048 → **1069 gruen** (+21, V3 prognostizierte +10 — mehr
Defense-Tests gefunden in T1b, T2b/c, T3b/c, T7b/c, T8b/c, T9b).

**Atomare Commits (3 Code + 1 Doku):**
- Commit 1 (QTimer+Fallback, alle main_window/mw_cycle Aenderungen +
  Tests T1, T2, T8, T10, T11, T12 + V1/V2/V3 Plan-Files)
- Commit 2 `8b11266` (Button-Label, control_panel + 3 T3-Tests)
- Commit 3 `9ce831a` (Horche+APP_VERSION, qso_panel/mw_qso/main.py +
  6 T6/T7/T9-Tests)
- Commit 4 (Doku, dieser): HISTORY+HANDOFF+CLAUDE+Memory.

**Push pending** — v0.95.16-25 + P2-Tool + P3 zusammen wenn Field-Test
positiv.

**Field-Test-Pflicht (Mike, V3 §6, 7 Punkte vor Push):**
1. Activate Test: Button-Text → „OMNI CQ (aktiv)", erste TX naechster Slot
2. 5-Slot-Pattern Block 1: Sende [E], Sende [O], 3x „Horche …"
3. 5-Slot-Pattern Block 2: Sende [O], Sende [E], 3x „Horche …"
4. **10-Slot-Loop (KRITISCH):** Pattern bleibt EXAKT — Drift-Beweis
   ohne +30s wie v0.95.24
5. Toggle off: Button-Text → „OMNI CQ", QSO-Panel still
6. HALT mid-OMNI: alles gestoppt, Button → „OMNI CQ"
7. Mode/Band-Wechsel: OMNI stoppt, QTimer canceled

**Lessons:**
- GUI-Thread-Blocking durch Decoder ist real und unvermeidbar im
  aktuellen Design. QTimer mit `Qt.PreciseTimer` umgeht das, weil die
  Eventloop-Prioritaet hoeher ist als reguläre Signal-Slots.
- V2-L3 zeigt: vorzeitige Loesung in V1 kann durch Code-Verifikation
  als unnoetig entlarvt werden. Encoder waehlt mid-cycle Toggle-On
  selbststaendig den naechsten passenden Slot — kein User-Start-Drift.
- Defense-in-Depth (Cycle-Tick-Fallback) kostet wenig + schuetzt vor
  unbekannten Edge-Cases. Log-Marker erlaubt Field-Diagnose.
- `update_omni_tx` als zentrale Stelle fuer Button-State-UI vermeidet
  doppelte Setter-Pfade (single-source-of-truth).

---

## 2026-05-09 v0.95.24 — P2.OMNI-PATTERN-FIX: Mid-Cycle-Pretrigger + Encoder-Queue

**Mike-Field-Test v0.95.23, 09.05.2026 08:34-08:37 UTC:** OMNI-CQ-Pattern
verschoben um +30s. TX nur in Pos 0 jedes Blocks, RX-Slots kollabiert.
Erwartete 5-Slot-Sequenz Block 1 (E-TX, O-TX, E-RX, O-RX, E-RX) wurde
zu langem Lueckenmuster mit nur jedem 5. Slot TX.

**Wurzel:** `_send_cq` lief am Slot-START via `on_cycle_end` →
`_next_slot_boundary` berechnet TX-Slot fuer aktuellen oder naechsten
Slot, dann Sleep bis kurz vor TX-Boundary. Bei Slot-Start-Aufruf liegt
`overshoot=0.8s > 0.3s` (v0.80 Fix B Schwelle) → Drift-Schutz schiebt
TX um 2 Slots weiter. OMNI-Pattern verliert Block-Synchronitaet.

**Loesung (R1-bestaetigt):**
1. **Encoder-Queue (Commit 1):** `core/encoder.py:transmit()` queut zweite
   Message in `_pending_tx_message` statt SKIP. Worker-Loop `_tx_worker`
   liest Queue nach jedem Inner-Run und sendet rekursiv ohne Thread-
   Restart. `abort()` und Replace-Pfad in `_tx_worker_inner` verdraengen
   die Queue (Notaus-Semantik / Plan-Wechsel).
2. **Mid-Cycle-Pretrigger (Commit 2):** `ui/mw_cycle.py:_omni_pretrigger
   _check` bei `cycle_pos > duration - 1.3s` ausgeloest, ruft
   `omni_tx.peek_next()` (NEU, ohne State-Mutation) → setzt
   `encoder.tx_even` + `qso_sm._was_pretriggered=True` + `qso_sm._send_cq()`.
   `qso_state.on_cycle_end` CQ_WAIT-Branch skipt zweites `_send_cq` wenn
   Flag True. Encoder hat Sleep-Vorlauf > 0 → kein v0.80 Drift-Schutz.

**Voller Workflow:**
V1 (`prompts/p2_omni_pattern_fix_v1.md`) →
V2 16 Lessons + L17-Race (`prompts/p2_omni_pattern_fix_v2.md`) →
R1 DeepSeek-Reasoner empfiehlt Variante 2 Encoder-Queue
(`prompts/p2_omni_pattern_fix_r1.md`) →
V3 Compact-fest 18 ACs / 16 neue Tests / 3 atomare Commits
(`prompts/p2_omni_pattern_fix_v3.md`) → Mike-Freigabe → Compact #4 →
Code (3 Commits) → **Final-R1 (DeepSeek-Reasoner, in=71310/out=2456
Tokens: „Plan ist fertig zur Implementierung. ... Go for it!", 0
KP-Findings, 5 Hinweise alle als KISS-Trade-offs / Bestaetigungen)**.

**R1-Final-Findings (alle adressiert oder bewusst KISS verworfen):**
- Logging bei Re-Trigger im selben Cycle (Cosmetic, KISS verworfen —
  Flag verhindert Trigger korrekt, kein Log noetig).
- `on_cycle_end` Reset im CQ_WAIT (R1 BESTAETIGT korrekt).
- `peek_next` bei inactive OMNI (R1 BESTAETIGT, Aufrufer prueft active).
- Mode-abhaengiger Pretrigger-Offset 1.3s (R1-Mathe: FT4/FT2
  `sleep_dur > 0` immer eingehalten — keine Mode-Differenzierung noetig).
- `tx_finished` nach jedem Inner-Run kein Doppel-Trigger (R1 BESTAETIGT).

**Geaenderte Files (5 Code + 2 Test NEU + main.py + 4 Plan-Files):**

- `core/encoder.py` (Commit 1):
  - `__init__`: `_pending_tx_message: str | None = None` (geschuetzt
    durch `_replace_lock`).
  - `transmit()`: SKIP-Zweig bei `_is_transmitting` durch Queue-Pfad
    ersetzt (`with _replace_lock: _pending_tx_message = message`).
  - `_tx_worker`: Outer-Loop `while True:` liest `_pending_tx_message`
    nach jedem Inner-Run, sendet weiter ohne Thread-Restart.
    `_is_transmitting` bleibt im Loop True damit weitere `transmit()`
    weiter queuen koennen.
  - `abort()`: `with _replace_lock: _pending_tx_message = None` —
    Notaus leert Queue.
  - `_tx_worker_inner` Replace-Pfad: zusaetzlich `_pending_tx_message =
    None` — Replace verdraengt Queue (Plan-Wechsel-Semantik).

- `core/omni_tx.py` (Commit 2):
  - `peek_next()` NEU: returnt
    `(next_slot_index, next_block, target_even, is_tx)` OHNE
    State-Mutation. Rollover bei `next_slot_index == 0` schaltet Block
    um. Paritaet analog zu `should_tx`.

- `core/qso_state.py` (Commit 2):
  - `__init__`: `_was_pretriggered: bool = False`-Flag mit Doku
    (Lebenszyklus: gesetzt von mw_cycle, reset von qso_state, beide
    GUI-Thread → kein Lock).
  - `on_cycle_end` CQ_WAIT-Branch: bei `_was_pretriggered=True` Flag
    reset, KEIN zweites `_send_cq` (sonst Doppel-TX im selben Slot).
    Sonst klassischer Pfad unveraendert.

- `ui/main_window.py` (Commit 2):
  - `_init` ergaenzt: `_omni_pretriggered: bool = False`-Flag
    (Reentrancy-Schutz GUI-Thread, da `_on_cycle_tick` ~10 Hz feuert
    und Schwelle ~13 Ticks breit ist).
  - `_on_omni_stopped`: `_omni_pretriggered = False` Reset bei
    OMNI-Stop (Re-Start sauber).

- `ui/mw_cycle.py` (Commit 2):
  - Modul-Konstante `_OMNI_PRETRIGGER_OFFSET_S = 1.3` (= |TARGET_TX_OFFSET|
    + 0.5, FlexRadio-TX-Buffer-Latenz).
  - `_on_cycle_tick`: ruft `_omni_pretrigger_check(sic, dur)`.
  - `_omni_pretrigger_check` NEU: 5 Pre-Conds (`_omni_pretriggered`-Flag
    + `omni.active && !is_paused` + `qso_sm.cq_mode` +
    `state in (IDLE, CQ_WAIT, CQ_CALLING)` + Schwellen-Fenster). TX-Slot:
    `peek_next` → `encoder.tx_even` + `qso_sm._was_pretriggered=True` +
    `qso_sm._send_cq()`. RX-Slot: nur Flag setzen (Pattern-Slot via
    `advance` weitergerueckt).
  - `_on_cycle_start`: `_omni_pretriggered = False` Reset fuer naechsten
    Cycle.

- `ui/mw_qso.py` (Commit 2):
  - `_on_send_message` CQ-Pfad: Pretrigger-Bypass-Pfad (wenn
    `_was_pretriggered=True`): nur Counter-Inkrement, kein
    `should_tx`-Check (Pretrigger hat naechsten-Slot bereits validiert).
    Klassischer Pfad bleibt fuer Toggle-Initial-CQ + Resume-Initial-CQ.
  - `_on_cancel` HALT: defensive `qso_sm._was_pretriggered = False`.

- NEU `tests/test_encoder_queue.py` (Commit 1, 9 Tests):
  - 3× Queue-Pfad (Active-TX, Last-One-Wins, Idle-Path).
  - 2× Replace-Verdraengt-Queue (request_replace + Replace-Pfad-
    Simulation).
  - 2× Abort-Verdraengt-Queue (Standard + idempotent).
  - 2× Init/Lock-Lifecycle (Init-None + gemeinsames `_replace_lock`).

- NEU `tests/test_p2_omni_pattern_fix.py` (Commit 3, 16 Tests):
  - T1-T6: `peek_next()` (Block 1 Pos 0/1, Rollover, Block 2 Pos 0,
    no-mutation, RX-Tuple).
  - T7-T11: `_was_pretriggered` Flag (Init False, Skip-Effect, Reset-
    Effect, klassischer Pfad, CQ_WAIT-only-Wirkung).
  - T12-T16: `_OMNI_PRETRIGGER_OFFSET_S=1.3`, peek_next idempotent,
    inactive OMNI, paused OMNI, vollstaendige 5-Slot-Sequenz mit
    Block-Wechsel.

- `main.py` APP_VERSION 0.95.23 → 0.95.24.

- Plan-Files: `prompts/p2_omni_pattern_fix_v[1-3].md` +
  `prompts/p2_omni_pattern_fix_r1.md`.

**Tests:** 1023 → **1048 gruen** (+25 effektiv: +9 Encoder-Queue
[Commit 1] + +16 Pattern-Fix [Commit 3]). V3 prognostizierte +16 (T9-T11
Encoder-Queue als 3 Tests gefuehrt — Defense-Tests gefunden).

**Atomare Commits (3 Code + 1 Doku):**
- Commit 1 `6a86764`: encoder.py Queue + tests/test_encoder_queue.py NEU
  + 4 Plan-Files.
- Commit 2 `337e4ca`: omni_tx peek_next + main_window/mw_cycle/mw_qso/
  qso_state Pretrigger.
- Commit 3 `0ab90a8`: tests/test_p2_omni_pattern_fix.py NEU +
  main.py APP_VERSION.
- Commit 4 (Doku, dieser): HISTORY+HANDOFF+CLAUDE+Memory.

**Push pending** — v0.95.16-24 + P2-Tool + P3 zusammen wenn Field-Test
positiv.

**Field-Test-Pflicht (Mike, V3 §8):**
1. Activate Test: OMNI-Toggle bei Slot N (Even/Odd egal) → erste TX im
   naechsten Slot. Slot-Tag korrekt.
2. Pattern Block 1: aktivieren so dass next_is_even=True → erwartet TX
   Even, TX Odd, RX, RX, RX in 5 aufeinanderfolgenden Slots.
3. Pattern Block 2: aktivieren so dass next_is_even=False → erwartet TX
   Odd, TX Even, RX, RX, RX.
4. **10-Slot-Loop (KRITISCHER BUG-FIX-BEWEIS):** 2 volle Blocks. Pattern
   bleibt EXAKT — kein +30s Drift wie in v0.95.23.
5. QSO-Reply mid-OMNI → QSO normal → nach RR73 OMNI-Resume mit Pos 0.
6. Caller-Queue: nach QSO direkt naechstes QSO ohne OMNI-Resume.
7. Toggle off → OMNI stoppt, Pre-Flag reset.
8. HALT mid-OMNI → alles stoppt, kein Resume.
9. Bandwechsel/Mode-Wechsel → OMNI stoppt automatisch.

**Lessons:**
- Drift-Schutz aus v0.80 ist Slot-Start-spezifisch — bei Mid-Cycle-
  Triggern faellt er weg, weil Encoder Sleep-Vorlauf hat.
- Pretrigger ist universelles Pattern fuer „TX im naechsten Slot
  einplanen ohne Drift" — zukuenftige Auto-Hunt-Verbesserungen koennten
  davon profitieren.
- DeepSeek-R1-Mathe bei Mode-Variation (FT4/FT2 Pretrigger-Schwelle):
  korrekte Verifikation aller Modi statt KISS-Hack.
- Encoder-Queue-Refactor funktioniert nahtlos mit P1.9 Replace-Logic
  (separates Lock fuer beide, gleiches `_replace_lock`).

---

## 2026-05-09 v0.95.23 — P2.OMNI-REDESIGN: Voller Refactor (Flag-Pattern + Pause/Resume + Auto-Rollover)

**Mike-Auftrag 09.05.2026:** Voller Refactor, kein Pflaster. P1.OMNI-START
(v0.95.22, 08.05.) hatte den OMNI-CQ-Toggle scharf geschaltet — Mike-Field-
Test zeigte: CQ-Loop stirbt nach 2 TX-Slots. Bug latent seit v0.78
(30.04.2026).

**Wurzel (Code-Verifikation 09.05.):**
- `core/qso_state.py:177` `_send_cq()` setzt `_set_state(CQ_CALLING)` VOR
  `send_message.emit(msg)`. Bei OMNI-RX-Slot returnt der Listener
  (`mw_qso._on_send_message`) ohne TX → State ist bereits CQ_CALLING →
  `on_cycle_end()` greift nicht mehr → CQ-Loop tot.
- Plus: 80-Counter-Block-Switch (Diversity-OPERATE_CYCLES-Überrest aus v0.78).
- Plus: `_on_try_replace_pending_tx` (P1.9 Replace-Pfad) inkonsistent —
  pausierte OMNI nicht (R1-V2 K1-Befund).

**Voller Workflow:**
V1 (`prompts/p2_omni_redesign_v1.md`) →
V2 Self-Review 15 Lessons (`prompts/p2_omni_redesign_v2.md`) →
R1-Lauf-1+2 (initial+truncated) →
R1-V2 DeepSeek-Reasoner 304 Z. (`prompts/p2_omni_redesign_r1_v2.md`) →
V3 Compact-fest 15 ACs/20 Tests/7 Commits (`prompts/p2_omni_redesign_v3.md`) →
Mike-Freigabe → Compact #3 → Code → **Final-R1 („Code freigegeben.
Keine Architektur- oder Logikfehler. Implementierungsreif.")**.

**R1-V2-Findings (mit V3-Bewertung):**
- K1 ⛔ ANGENOMMEN: `_on_try_replace_pending_tx` fehlte `_omni_tx.pause()`
  → DRY-Helper `_pause_omni_if_active` für 3 Entry-Pfade.
- S1 ❌ VERWORFEN als R1-Halluzination: R1 nahm an `_resume_cq_if_needed`
  läuft VOR mw_qso-Listener. Code-Beweis `main_window.py:597-599` keine
  ConnectionType → AutoConnection → bei gleichem GUI-Thread DirectConnection
  → `qso_*.emit()` SYNCHRON → mw_qso-Slot komplett (inkl. OMNI-Resume) BEVOR
  `_resume_cq_if_needed`. Kein ungefilterter CQ.
- S2 ✅ ANGENOMMEN: `block_cycles`-Param komplett raus aus Konstruktor +
  `get_instance` (klarer als „ignorieren").
- S3 ✅ ANGENOMMEN: AC14-Test als Integrationstest mit Listener-Mock.
- L1/L8/L13 ✅ ANGENOMMEN: 3 Code-Kommentare (Flag-Lock-Hinweis,
  encoder.tx_even-Setter-Doku, is_even_cycle-Docstring).

**Geaenderte Files (7 Code + 4 Test + main.py + 4 Plan-Files):**

- `core/omni_tx.py` (Refactor — Commit 1):
  - `block_cycles`-Param + `_cycle_count` + `_pending_switch` + `enable()`
    + `on_qso_started()` + `cycles_until_block_switch` ENTFERNT.
  - NEU `start_with_parity_for_next_slot(next_is_even)` (Block-Wahl per
    nächster Slot-Parität — „kein Slot verschwenden").
  - NEU `pause()` / `resume()` / `is_paused()` (QSO-Pause friert
    `_slot_index` ein).
  - `advance()` ohne `qso_active`-Param, Block-Switch automatisch bei
    rollover (slot_index 4→0).
  - `get_instance()` ohne block_cycles-Param.
- `core/qso_state.py` (Flag-Pattern — Commit 2):
  - `_omni_skip_state_change: bool = False` Init.
  - `_send_cq()`: State-Wechsel kommt NACH `emit()`, Flag-Check verhindert
    State-Wechsel zu CQ_CALLING bei OMNI-RX-Slot.
  - `_resume_cq_if_needed()`: S1-Doku-Top-Kommentar (DirectConnection-
    Annahme dokumentiert für künftigen Multi-Thread-Refactor).
- `core/timing.py` (Doku — Commit 3): `is_even_cycle()` Docstring (aktueller
  Zyklus, NICHT der nächste — Aufrufer invertieren mit `not is_even_cycle()`).
- `core/encoder.py` (Doku — Commit 3): `tx_even`-Inline-Kommentar (letzter
  Setter gewinnt — Design-bedingt, jeder Pfad setzt für seinen TX die
  korrekte Parität).
- `ui/mw_qso.py` (Helper + Pfade — Commit 4):
  - NEU `_pause_omni_if_active()` Helper (DRY für 3 Entry-Pfade).
  - NEU `_maybe_resume_omni()` Helper (DRY für 3 Exit-Pfade).
  - 3 Entry-Pfade: `_on_station_clicked`, `_on_tx_slot_for_partner`
    (nur wenn nicht courtesy), `_on_try_replace_pending_tx` (K1-Fix).
  - 3 Exit-Pfade: `_on_qso_complete`, `_on_qso_confirmed`, `_on_qso_timeout`.
  - `_on_send_message`: Flag-Pattern statt `calls_made -=1`-Pflaster.
  - `_on_state_changed`: `omni_tx.on_qso_started()` Call entfernt.
  - `_on_qso_complete` Duplikat-Pfad ruft auch `_maybe_resume_omni()`.
- `ui/main_window.py` (Anpassungen — Commit 5):
  - `_omni_was_active_pre_qso: bool = False` Init.
  - `get_instance()` ohne block_cycles.
  - `_on_btn_omni_cq_toggled`: `start_with_parity_for_next_slot(next_is_even)`
    statt `enable()`.
  - `_on_omni_stopped`: setzt zusätzlich `_omni_was_active_pre_qso = False`
    (Stop-while-QSO → kein Resume).
- `ui/mw_cycle.py` (Pause-Check — Commit 5):
  - `_on_cycle_start`: `if not _omni_tx.is_paused(): _omni_tx.advance()`
    statt `_omni_tx.advance(qso_active=_in_qso)`.
- NEU `tests/test_p2_omni_redesign.py` (Commit 6): 20 Tests T1-T20 für
  AC1-AC15 (5-Slot-Pattern, Block-Rollover, start_with_parity, Pause/Resume,
  Flag-Pattern, 3 Pause-Helper-Pfade, 3 Resume-Helper-Pfade, Caller-Queue-
  Schutz, HALT, API-Cleanup).
- `tests/test_omni_tx.py` (Migration — Commit 6): von 11 Tests auf 4 Tests
  geschrumpft — Pattern/Block-Switch/Pause sind jetzt in test_p2_omni_redesign.
  Bleiben: 7 Stop-Reason-Tests (parametrize) + disable-Wrapper + Initial-State
  + Stop-Cleanup.
- `tests/test_p1_omni_start.py` (Migration — Commit 6): API-Migration
  `enable()` → `start_with_parity_for_next_slot(next_is_even=True)`,
  `OmniTX(block_cycles=80)` → `OmniTX()`.
- `tests/test_modules.py` (partielle Migration — Commit 6): 5 OMNI-Tests
  reduziert auf 3 (block_cycles-min-Guard + qso_reset + pending_switch +
  qso_blocks_counter ENTFERNT — Funktionalität in test_p2_omni_redesign).
- `tests/test_patterns.py` (Migration — Commit 6): 4 OMNI-Tests migriert auf
  neue API (block_cycles raus, enable → start_with_parity, block_switch
  rollover-basiert).
- `main.py` APP_VERSION 0.95.22 → 0.95.23.
- Plan-Files: `prompts/p2_omni_redesign_v[1,2,3].md`,
  `prompts/p2_omni_redesign_r1_v2.md`,
  `prompts/p2_omni_redesign_session_context_v3.md`.

**Tests:** 1014 → **1023 gruen (+9)**, V3 prognostizierte +20 — Differenz
durch Migration: 11 alte test_omni_tx Tests → 4 neue (-7), test_modules
5 → 3 (-2). Effektiv: -11 alte, +20 neue, +0 patterns/p1_omni_start = +9.

**Final-R1 (DeepSeek-Reasoner, in=70027/out=1385 Tokens):**
> Der V3-Plan ist implementierungsreif und adressiert alle Kritikpunkte aus
> R1-V2. Die beigefügten Code-Dateien spiegeln den Plan exakt wider. Die
> Tests sind strukturiert und decken die ACs ab. ... Es gibt keine offenen
> Architektur- oder Logikfehler.

3 kleine R1-Anmerkungen:
- `next_is_even = not timer.is_even_cycle()` Berechnung — im Code korrekt.
- `_main_window._omni_was_active_pre_qso`-Reference im Plan-Snippet — im
  finalen Code direkt `self._omni_was_active_pre_qso` (QSOMixin ist Teil
  von MainWindow). R1 hat das im Code-Review konsistent bestätigt.
- `_maybe_resume_omni` Slot-Index-Reset → korrekt für Resume-Pfad
  („kein Slot verschwenden" — nächster Slot wird sauber gewählt).

**Atomare Commits (Plan-Reihenfolge V3 §12):**
1. `core/omni_tx.py` Refactor (block_cycles raus, neue API)
2. `core/qso_state.py` Flag-Pattern + Doku
3. `core/timing.py` + `core/encoder.py` Doku-Kommentare
4. `ui/mw_qso.py` Helper + 3 Entry- + 3 Exit-Pfade
5. `ui/main_window.py` + `ui/mw_cycle.py` Anpassungen
6. Tests migrieren + neue Tests
7. APP_VERSION 0.95.23 + Doku (HISTORY+HANDOFF+CLAUDE+Memory)

**Field-Test-Pflicht (vor Push):**
- Diversity, Easter-Egg an, btn_omni_cq sichtbar.
- Klick btn_omni_cq → CQ sofort, Statusbar `Ω Even=1 Odd=0`.
- 5 Slots durchlaufen → CQ-Loop läuft weiter (Bug-Fix-Beweis: vor v0.95.23
  starb der Loop nach 2 TX-Slots).
- Block-Wechsel automatisch bei Rollover (slot 4→0).
- CQ-Reply → QSO normal → nach RR73 OMNI-Resume mit korrekter Parität.
- Caller-Queue voll: nach QSO bleibt OMNI pausiert, nächstes QSO sofort.
- Toggle off → CQ stoppt, OMNI inaktiv.
- HALT mit OMNI aktiv → alles gestoppt, kein Resume.
- Bandwechsel → OMNI stoppt automatisch.

**Push pending** — v0.95.16-23 + P2-Tool + P3 zusammen wenn Field-Tests
positiv.

---

## 2026-05-08 v0.95.22 — P1.OMNI-START: OMNI-CQ-Toggle aktiviert jetzt CQ-Loop

**Mike-Field-Test 08.05.2026 16:08 UTC** (Diversity, Easter-Egg lange aktiv):
Klick auf `btn_omni_cq` → Button gedrueckt + Statusbar zeigt zusaetzlich
`Even=0 Odd=0` → **aber kein CQ wird gesendet**. Auch nach mehreren Zyklen
nichts. Bug latent seit v0.78 (30.04.2026) wo OMNI-TX scharfgeschaltet
wurde. Plus 2 Folge-Bugs entdeckt.

**Wurzeln (Code-Verifikation 08.05.):**

W1 — `ui/main_window.py:676-689` `_on_btn_omni_cq_toggled`: setzte nur
`omni_tx.active=True` (Slot-Filter aktiviert), aber `qso_sm.cq_mode`
blieb `False` → niemand rief `_send_cq()` → keine
`send_message.emit("CQ ...")` → `_on_send_message` wurde nie gerufen →
OMNI-Slot-Filter griff nie → kein TX. In Diversity ist `btn_cq` versteckt
(`main_window.py:672`), Mike konnte `cq_mode=True` gar nicht manuell
aktivieren. OMNI musste das selbst tun — tat es aber nicht.

W2 — `ui/main_window.py:691-703` `_on_omni_stopped`: setzte nur
Button-State zurueck, kein `qso_sm.stop_cq()` → `cq_mode` blieb `True`
wenn OMNI extern gestoppt (band_change, totmann_expired, easter_egg_off
etc.). Plus `_was_cq` blieb haengen → ungewolltes Auto-Resume nach
QSO-Ende wenn User OMNI bewusst gestoppt hatte.

W3 — `ui/mw_qso.py:211-230` `_on_cancel` (HALT-Button): stoppte CQ + QSO
+ TX + Auto-Hunt aber NICHT OMNI → Inkonsistenz nach HALT, Button-State
versus Modul-State auseinander.

**Voller Workflow:** V1(10 ACs, 7 Fragen) → V2(8 Lessons L1-L8, alle
V1-Fragen via grep beantwortet) → R1(DeepSeek-Reasoner: 2 Bug + 1 SOLLTE
+ 2 KOENNTE — 5 angenommen + 3 abgelehnt + 0 halluziniert) → V3
(Compact-fest, R1-SOLLTE `_was_cq=False` mit aufgenommen) → Compact →
Code → **Final-R1 („Code kann gemerged werden", 0 KRITISCH + 3 SOLLTE
alle als KISS-Trade-offs in V3 dokumentiert: `_was_cq`-Setter
verschoben (V3 §5), Doppel-`stop_cq`-Defense-in-Depth gewollt,
Doppelklick-Schutz Mike-irrelevant da Splashtop kein Doppelklick
liefert)**.

**Geaenderte Files (2 Code + 1 Test NEU + main.py + 3 Plan-Files):**

- `ui/main_window.py` `_on_btn_omni_cq_toggled` (Z.676-714, +25 Zeilen):
  - Pre-Block bei `state not in (IDLE, CQ_WAIT)` → Toggle revert via
    `blockSignals(True) / setChecked(False) / blockSignals(False)` +
    Statusbar-Hinweis 4s „OMNI-CQ nur startbar wenn kein aktives QSO
    laeuft — erst laufendes QSO beenden".
  - Konsistent mit `qso_state.py:152` `start_cq()`-Akzeptanz-Bedingung.
  - Bei OK: zusaetzlich `qso_sm.start_cq()` rufen — nun greift
    OMNI-Slot-Filter weil `_send_cq()` `send_message.emit("CQ ...")`
    triggert.
- `ui/main_window.py` `_on_omni_stopped` (Z.716-743, +5 Zeilen):
  - `if qso_sm.cq_mode: qso_sm.stop_cq()` — idempotenter CQ-Loop-Stop
    fuer ALLE Stop-Reasons (band_change, ft_mode_change, rx_mode_change,
    totmann_expired, easter_egg_off, superseded, manual_halt).
  - `qso_sm._was_cq = False` — R1-SOLLTE: kein Auto-Resume nach
    Stop-while-QSO. KISS-Akzeptanz fuer State-Machine-Internal-Setzung
    (V3 §5 dokumentiert, Final-R1 SOLLTE-Punkt 1 verworfen).
- `ui/mw_qso.py` `_on_cancel` (Z.210-234, +3 Zeilen):
  - `if _omni_tx.active: _omni_tx.stop_omni_tx("manual_halt")` ergaenzt.
  - Statusbar-Text auf „HALT — CQ, QSO, TX, OMNI gestoppt" erweitert.
  - Docstring um OMNI-Erwaehnung erweitert.
  - Reihenfolge gewollt: stop_cq + cancel zuerst (eigene UI-Cleanup),
    danach OMNI-Stop. Final-R1 SOLLTE-Punkt 2 (Doppel-`stop_cq` durch
    `_on_omni_stopped`-Slot) als Defense-in-Depth verworfen.
- NEU `tests/test_p1_omni_start.py` (11 Tests via parametrize):
  - 1 Start: Toggle on bei IDLE → omni.active + cq_mode + CQ emittet.
  - 1 Stop: Toggle off → omni stop + cq_mode=False + _was_cq=False.
  - 6 parametrized Stop-Reasons (band_change, ft_mode_change,
    rx_mode_change, totmann_expired, easter_egg_off, superseded).
  - 1 Block-while-QSO: WAIT_REPORT-Klick → Toggle nicht aktiviert.
  - 1 HALT mit OMNI: cancel-Sequenz stoppt OMNI.
  - 1 Reply-Resume Backward-compat: `_process_cq_reply` setzt
    `_was_cq=True` (damit `_resume_cq_if_needed` nach QSO-Ende
    OMNI-CQ resumen kann solange OMNI nicht extern gestoppt wird).
- `main.py` APP_VERSION 0.95.21 → 0.95.22.
- Plan-Files NEU: `prompts/p1_omni_start_v[1-3].md`.

**Tests:** 1003 → **1014 gruen (+11)**, V3 prognostizierte +7 (paramet-
rize zaehlt 6 Reasons als 6 Tests statt 1). Backward-compat: bestehende
`tests/test_omni_tx.py` weiter gruen (kein Eingriff in `omni_tx.py`).

**Atomare Commits:** Code-1 (Toggle + Stop-Slot + 11 Tests + V1-V3
Plan-Files) + Code-2 (HALT + APP_VERSION) + Doku-Commit (HISTORY +
HANDOFF + CLAUDE + TODO + Memory).

**Hardware-Garantie ANT1:** OMNI emittet kein TX direkt, nur Slot-Filter.
TX laeuft via `encoder.transmit()` → `radio.set_tx_antenna("ANT1")`
zentral (`core/encoder.py:334`). Kein direkter Hardware-Eingriff durch
OMNI-Aenderung. Final-R1 Pruefauftrag 7 bestaetigt.

**Field-Test-Plan (vor Push):** Diversity, Easter-Egg an, btn_omni_cq
sichtbar; Klick → CQ sofort auf Even, Statusbar `Ω Even=1 Odd=0`,
naechster Slot Odd, Block-Wechsel nach 80; CQ-Reply → QSO normal → nach
RR73 OMNI-Resume; Toggle off → CQ stoppt; HALT mit OMNI → alles
gestoppt; Bandwechsel → OMNI stoppt automatisch; OMNI waehrend
WAIT_REPORT → blockiert + Statusbar 4s.

**Push pending** — v0.95.16 + v0.95.17 + v0.95.18 + v0.95.19 + v0.95.20
+ v0.95.21 + v0.95.22 + P2-Tool + P3 zusammen wenn Mike Field-Tests
positiv.

---

## 2026-05-08 v0.95.21 — P1.HUNT-SNR: Hunt-Pfad nutzt msg.snr statt _last_snr

**Mike-Field-Test 08.05.2026 13:57 UTC:** Slot mit 3 Stationen (EV81OB -15,
**EV81AB -18**, LZ81ZZ -23). Mike klickt EV81AB → App sendet
`EV81AB DA1MHH -24` (6 dB falsch). Wurzel: `_last_snr` wird vom Decoder pro
decodierter Message ueberschrieben (mw_cycle.py:805). `start_qso` liest
`_last_snr` → zuletzt iterierte Station gewinnt, fast nie die geklickte.

**Folge-Bug zu P1.8 (v0.95.18):** Damals war `_process_cq_reply` gefixt
(`msg.snr` direkt), Hunt-Pfad explizit ausgelassen mit Annahme „geklickte
Station ist meist die staerkste". Mike's 3-Stationen-Slot widerlegt das.

**Voller Workflow:** V1(7 offene Fragen, 10 ACs) → V2(12 Lessons L1-L12,
alle V1-Fragen via grep beantwortet) → R1(DeepSeek-Reasoner: 0 KRITISCH +
1 SOLLTE = `advance()` R-Report-Bug + 2 KOENNTE optional) → V3(Compact-
fest, R1-SOLLTE mit aufgenommen) → Compact → Code → **Final-R1 („Code
freigegeben", 1 SOLLTE-Halluzination Fallback-Clamp verworfen weil Code
bereits via `> -30 else "R-10"` clamped)**.

**Geaenderte Files (3 Code + 1 Test NEU + main.py + 3 Plan-Files):**
- `core/qso_state.py`:
  - `start_qso(their_snr: int | None = None)` — Signatur erweitert,
    Body nutzt `their_snr if not None else _last_snr`. Backward-compat
    via Default `None`. Reports `f"{snr:+03d}" if snr > -30 else "-10"`
    (gleich wie bisher).
  - `advance()` WAIT_REPORT-Branch (R1-SOLLTE) — `qso.our_snr` zuerst
    (R-Praefix dazu via `lstrip("R")`-Defense), fallback `_last_snr` nur
    wenn `our_snr` leer. Verhindert dass Force-Send-Pfad (P1.FORCESEND
    v0.95.12) bei zwischenzeitlich decodierten Stationen falschen R-Report
    schickt.
- `ui/mw_qso.py:138` — Hunt-Klick `their_snr=msg.snr` durchreichen.
- `ui/mw_cycle.py:562` — Auto-Hunt `their_snr=_candidate.snr` (Feld
  existiert seit `core/auto_hunt.py:53-57`).
- NEU `tests/test_p1_hunt_snr.py` (10 Tests: 8 Hunt + 2 advance).
- `main.py` APP_VERSION 0.95.20 → 0.95.21.
- Plan-Files: `prompts/p1_hunt_snr_v[1-3].md`.

**Tests:** 992 → 1003 gruen (+11, V3 prognostizierte +10 — 1 Bonus durch
Test-Baseline). Bestehende Tests alle weiter gruen (Backward-compat-Beweis).

**Atomare Commits:** `659e210` Code-1 (qso_state + Tests + Plan-Files) +
`8d6e80a` Code-2 (mw_qso + mw_cycle + APP_VERSION) + Doku-Commit.

**Field-Test-Pflicht (vor Push):** Slot mit 3+ Stationen, Klick auf mittlere
SNR-Station → Report MUSS station-spezifisch sein. Auto-Hunt-Sekundaer-Test:
Hunt-Reports muessen `_candidate.snr` entsprechen.

**Push noch nicht** — v0.95.16-21 + P2-Tool + P3 + Bundle gehen beim
naechsten Push zusammen.

**Lesson:** Bei P1.X-Bug-Fix-Patterns immer pruefen ob alle Pfade gleicher
Klasse mit-gefixt werden — v0.95.18 fixte `_process_cq_reply`, Hunt-Pfad
blieb explizit, Mike's Field-Test 3 Wochen spaeter zeigt den gleichen Bug.
Memory: `feedback_partial_fix_check_other_paths.md`.

---

## 2026-05-08 v0.95.20 — P3.AUDIO-DUMP-DEBUG: Roh-Audio-Slot-Dump fuer Debug/Forschung

**Mike-Auftrag 08.05.:** Toggle in Settings, rollierender FIFO-Cap (50-1000),
NUR FT8, voller DeepSeek-Workflow + Compact dazwischen. Use-Case: AP-Lite-
Replay, ANT1/ANT2-Spektrum offline (Inspectrum/Audacity), Decoder-Tests
gegen reale Aufnahmen.

**Voller Workflow:** V1(10 ACs, 7 offene Fragen, 12 Tests) → V2(15 Lessons
L1-L15, Pfad-Resolution + Spinbox-Bindung + Modus-Filter) → R1(DeepSeek-
Reasoner: 1 KRITISCH + 1 SOLLTE) → V3(Compact-fest mit **Architektur-
Wechsel zu Pull-Pattern statt Setter** — eliminiert Race komplett) → Compact
→ Code → **Final-R1 („Code kann gemerged werden", 0 KRITISCH/SOLLTE,
2 KOENNTE optional)**.

**R1-KRITISCH adressiert:** V2 hatte Setter-Pattern (`decoder.set_current_
antenna(ant)` aus `mw_cycle._on_cycle_decoded`) → Race weil Antennen-Setter
NACH Decoder-Thread-Dump lief. Pivot zu Pull-Pattern: Decoder cached
`last_audio_24k` als Buffer, GUI-Thread holt via `decoder.dump_last_slot(
ant, root, max_files)`. Kein Race weil Decoder-Thread bei `cycle_decoded`-
Signal fertig ist.

**Architektur:**
- NEU `core/audio_dump.py` (~80 Zeilen): `atomic_write_wav` (`tempfile.
  mkstemp(dir=) + os.replace`, P2-Pattern), `enforce_fifo_cap` (mtime-Sort,
  global ueber band_mode-Sub-Dirs), `build_dump_path` (root/{band}_{mode}/
  YYYY-MM-DD_HH-MM-SS_ANT.wav, `_v2`-Suffix bei Kollision).
- `core/decoder.py`: `last_audio_24k` Buffer + `last_slot_start_utc`
  + `_band` Default `"20m"` + `set_band(band)` + Hook in `_process_cycle`
  nach `np.concatenate` (`audio_raw.copy()` weil spaeter in-place modifiziert)
  + `dump_last_slot(ant, root, max_files)` Pull-Methode mit Modus-Filter
  (nur FT8, sonst `return False`).
- `ui/settings_dialog.py`: Tab 4 „Daten & Tools" Block 4 NEU mit Checkbox
  + Spinbox 50-1000/Default 200 + Toggle-Bindung lambda-frei + Reset.
- `ui/mw_cycle.py`: Pull-Aufruf in `_on_cycle_decoded` nach `_resolve_
  hardware_antenna` (Z.80) — `getattr`-Schutz fuer alte Sessions.
- `ui/mw_radio.py`: `decoder.set_band(band)` in `_on_band_changed` analog
  `ntp_time.set_band`.
- `ui/main_window.py`: `_audio_dump_enabled` + `_audio_dump_max_files`
  initial aus Settings + Update bei Settings-Save + initiales
  `decoder.set_band(settings.band)`.
- `main.py`: APP_VERSION 0.95.19 → 0.95.20.

**Sicherheits-Garantien:**
- **Atomic-Write:** tmpfile auf gleichem FS via `dir=target_dir` →
  `os.replace` ist atomar. Bei Crash mid-write: tmpfile via try/except
  aufgeraeumt, kein zerrissenes WAV.
- **FIFO-Cleanup:** global ueber `**/*.wav` mit mtime-Sort, ignoriert
  `.tmp` und non-WAV. Default-Cap 200 ≈ 50 Min FT8 ≈ 58 MB.
- **Modus-Filter:** `dump_last_slot` returnt `False` ausserhalb FT8.
- **Robust:** try/except verhindert App-Crash bei Disk-voll/File-Lock.

**Settings-UI:** Tab „Daten & Tools" → Block 4 → Checkbox „Audio-Slots
fuer Debugging sichern" (Default OFF) + Spinbox „Max. Files" (50-1000,
Default 200, enabled-bound an Checkbox).

**Speicherort:** `audio_dump/{band}_FT8/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav`,
absolut via `Path(__file__).resolve().parent.parent / "audio_dump"`.
WAV mono int16 24 kHz (Decoder-Original-Format vor Resample).

**Geaenderte Files (1 NEU + 1 Test NEU + 5 Code + 3 Plan-Files):**
NEU `core/audio_dump.py`, NEU `tests/test_audio_dump.py` (14 Tests:
4 atomic + 5 fifo + 3 build + 2 Decoder-Integration), `core/decoder.py`,
`ui/settings_dialog.py`, `ui/mw_cycle.py`, `ui/mw_radio.py`,
`ui/main_window.py`, `main.py`. NEU `prompts/p3_audio_dump_v[1-3].md`.

**Tests 978 → 992 gruen** (+14, V3 prognostizierte +13 — +1 Bonus durch
zusaetzlichen Edge-Case-Test).

**Atomare Commits:** Code-1 (`audio_dump.py` + Decoder + Tests + Plan-Files)
+ Code-2 (Settings-UI + mw_cycle Pull + mw_radio + main_window + main.py)
+ Doku.

**KEIN Push** — Mike kann lokal nutzen (Toggle aktivieren + funken),
naechster Push zusammen mit v0.95.16-19 + P2-Tool + diesem Bundle.

**Field-Test-Plan:**
1. App starten → Settings → Tab „Daten & Tools" → Block „Audio-Slots"
   sichtbar.
2. Toggle ON + Cap 50 → OK → ein paar FT8-Slots laufen lassen.
3. WAVs in `audio_dump/{band}_FT8/` pruefen (korrekte Antennen-Tags).
4. Cap-Test: bei 10 Slots max 5 WAVs.
5. Audacity: 1 WAV oeffnen → 24 kHz mono int16, ~12.6 s.

**Lessons-Learned:**
- **Pull-Pattern statt Setter-Pattern** bei Multi-Thread-Ist-Werten:
  Wenn Thread A einen Wert braucht den Thread B kennt, holt A den Wert
  vom B-Daten-Buffer ab statt B den Wert in A reinpusht. Eliminiert
  Race komplett. Memory-Vorschlag: `feedback_pull_vs_setter_pattern.md`.
- **R1's KRITISCH war richtig:** V2's Setter-Pattern war fragile, ohne
  R1-Plan-Review haetten wir einen Bug eingebaut der Antennen-Tags
  1 Slot zu spaet macht.
- **Atomic-Write-Pattern wiederverwenden:** P2.ADIF-ARCHIVE etablierte
  `tempfile.mkstemp(dir=) + os.replace` — P3 kopiert 1:1, kostet nichts,
  schenkt 1 Schicht Sicherheit.

---

## 2026-05-08 — P2.ADIF-ARCHIVE Standalone-Tool (Tool-only, kein APP_VERSION-Bump)

**Mike-Auftrag 08.05. (post-v0.95.19):** Voller DeepSeek-Workflow + Compact
fuer P2.ADIF-ARCHIVE (Standalone-Helper-Script, war seit 07.05. in TODO).
Tool konsolidiert hochgeladene QSO-Tagesdateien (`SimpleFT8_LOG_*.adi`)
aus `adif/hochgeladen/` in Jahresarchive `adif/archiv/YYYY.adi`.

Voller Workflow V1(Diagnose, 7 ACs, 7 offene Fragen)→V2(Self-Review,
15 Lessons L1-L15, alle V1-Fragen beantwortet)→R1(DeepSeek-Reasoner,
1 KRITISCH + 2 WICHTIG + Tests 17→20)→V3(Compact-fest, vollstaendiges
Script + 20 Tests, alle R1-Findings adressiert)→Compact→Code→**Final-R1
(„Code kann gemerged werden") — 0 KP-Findings**, 1 SOLLTE-Fix (None-Schutz
in `_record_to_adif`) + 1 KOENNTE (Race-Condition-Doku) sofort umgesetzt.

**Sicherheits-Garantien (3 Mike-Schutzwaelle fuer Hobby-Schatz-Logbuch):**
1. **Idempotenz** via Match-Key `(CALL, QSO_DATE, TIME_ON)` (gleich wie
   `delete_qso` in `log/adif.py`). Re-Run derselben Quelle schreibt keine
   Duplikate, schluckt sie still im `skipped_duplicates`-Counter.
2. **Atomic-Write** via `tempfile.mkstemp(dir=target_dir)` +
   `os.replace`. Tmpfile MUSS auf gleichem Filesystem liegen
   (R1-WICHTIG, deshalb `dir=target_dir` statt Default-`/tmp`) — sonst
   ist der „atomic rename" nicht atomar. Bei Crash mid-write: existing
   Archiv bleibt heil, tmpfile wird via try/except aufgeraeumt.
3. **Datenintegritaets-Abort:** Existing Archiv wird vor jedem Write
   geparst. Schlaegt das fehl (korrupte Datei) → `all_years_ok=False`,
   Quelle bleibt liegen, Fehler im Summary, kein Schreiben. R1-KRITISCH:
   Mike's Logbuch darf NIE durch korruptes existing-Archiv ueberschrieben
   werden. Quelle bleibt fuer manuellen Eingriff.
4. **Verifikations-Schritt nach Schreiben:** Nach `os.replace` wird das
   neue Archiv re-geparst, Match-Keys verglichen mit `expected_keys`.
   Bei Diskrepanz (z.B. Disk-Korruption beim Schreiben) → `all_years_ok=
   False`, kein Move/Delete der Quelle. R1-WICHTIG.
5. **Default Move (nicht Delete):** Quelle wandert nach
   `adif/archiv/_konsolidiert/` statt geloescht zu werden (V2-L1
   Sicherheits-Default). `--delete-source` als opt-in. Bei Re-Run
   gleicher Datei: `_dup`-Suffix verhindert Overwrite (V3-Test
   `test_konsolidiert_dest_collision`).

**CLI-Flags (V2-L2 + L6 + L10):**
- `--source PATH` (Default: `adif/hochgeladen`)
- `--target PATH` (Default: `adif/archiv`)
- `--pattern GLOB` (Default: `SimpleFT8_LOG_*.adi`, ignoriert QRZ-Exports)
- `--dry-run` (Plan-Summary, kein Schreiben)
- `--yes` (Confirm-Prompt ueberspringen, fuer Skript-Automation)
- `--delete-source` (LOESCHEN statt verschieben — opt-in)

Phase 1 immer Dry-Run mit Plan-Ausgabe, dann `[y/N]`-Prompt
(uebergehbar via `--yes`), Phase 3 Real-Run mit Ergebnis-Summary.

**Geaenderte Files (1 NEU + 1 Test NEU + 3 Plan-Files):**
- NEU `tools/adif_archive.py` (~280 Zeilen, vollstaendiges Script
  mit `_record_key`, `_record_year`, `_record_to_adif` Helpers,
  `_atomic_write_archive`, `consolidate`, `_format_summary`, `main`)
- NEU `tests/test_adif_archive.py` (23 Tests: 5 Helper + 18 Konsolidierung)
- NEU `prompts/p2_adif_archive_v[1-3].md` (V1+V2+V3 Plan-Dokumente)
- KEIN `main.py` Bump — Tool-only, App-Verhalten unveraendert.

**V2-Highlights (Self-Review entlarvt 15 V1-Luecken L1-L15):**
- L1: Default-Verhalten Quelle = Move (sicher) statt Delete
- L6: Glob `SimpleFT8_LOG_*.adi` strikt → QRZ-Exports unangetastet
- L7: Atomic-Write Pflicht (Strg+C-Schutz)
- L9: Lockfile NICHT noetig (KISS, 1-User-Hobby, V3-explizit verworfen)
- L12: Verifikations-Schritt vor Move
- Tests-Soll von 10 (V1) ueber 15 (V2 Edge-Cases) auf 17 (V2 Helper-
  Tests) auf 20 (V3 R1-Empfehlung)

**R1-Plan-Review (DeepSeek-Reasoner) entlarvte 3 Findings:**
- 🔴 KRITISCH: Korruptes existing Archiv → V3 muss Abbruch garantieren
  (try/except + `all_years_ok=False`-Pfad)
- 🟡 WICHTIG: Tmpfile MUSS auf gleichem Filesystem
  (`tempfile.mkstemp(dir=target_dir)` statt `/tmp`)
- 🟡 WICHTIG: Verifikations-Schritt nach Schreiben (re-read +
  Match-Key-Check)
- 🔵 OPTIONAL: Tests 17 → 20

**Final-R1 (Code-Review) bestaetigt freigabe-bereit:**
- 0 KP-Findings, „Code kann gemerged werden"
- 1 SOLLTE: `_record_to_adif` None-Schutz → fixed via
  `str(v) if v is not None else ""` + neuer Test
- 1 KOENNTE: Race-Condition-Doku → fixed in Module-Docstring
- 2 KRITISCH (parallele Instanzen + Verifikations-Rollback) explizit als
  Single-User-Akzeptanz dokumentiert (V2-L9 KISS-Entscheidung)

**Tests 955 → 978 gruen (+23, V3 prognostizierte +20):**
- 5 Helper-Tests (`_record_key`/`_record_year`/`_record_to_adif`)
- 14 Konsolidierungs-Tests (Single-Year, Multi-Year, Idempotent, Dry-
  Run, Move/Delete, Glob-Filter, Korrupte Files, Header-Once,
  Atomic-Write, Atomic-No-Partial, Korruptes-Existing, Verifikations-
  Diskrepanz, Missing-Year, Konsolidiert-Collision)
- 2 CLI-Tests (Dry-Run + --yes)
- 1 None-Schutz-Test (Final-R1 SOLLTE)
- 1 Bonus durch Helper-Test-Splits

**Atomare Commits:**
- Code: `P2.ADIF-ARCHIVE: Standalone-Tool tools/adif_archive.py + 23 Tests`
- Doku: `docs (P2.ADIF-ARCHIVE): HISTORY+HANDOFF+CLAUDE+TODO+Memory`

**KEIN Push-Plan** — Mike kann lokal nutzen, Push zusammen mit
v0.95.16-19 (alle bisher pending).

**Lessons:**
- R1's KRITISCH-Befund „korruptes existing Archiv" haette ich allein
  uebersehen. Drei-Schritt-Pruefung (parse-existing → write → re-parse-
  verify) ist Goldstandard fuer Datei-Konsolidierungs-Tools.
- `tempfile.NamedTemporaryFile()` Default-Pfad `/tmp` ist auf macOS
  haeufig anderes Filesystem als Projektordner → `os.replace`
  faellt auf cross-FS-Copy zurueck, NICHT atomar. R1 fing das.
- Tests-Soll skalierte 10→15→17→20→23. Helper-Tests + Edge-Cases
  finden mehr Bugs als pauschale „mehr Tests".
- KISS-Lockfile-Verzicht (V2-L9) korrekt — fuer Mike's
  1-User-Workflow ist Atomic-Write ausreichend, Race-Condition-Risiko
  in Doku transparent.


## 2026-05-08 v0.95.19 — P1.BUNDLE2: 3 hardware-freie Bugs gebuendelt

**Mike-Auftrag 08.05. (post-v0.95.18):** „die kleinen können wir die
zusammenfassen wenn wir deepseek workflow komplett machen mit compact?"
→ Bundle aus 3 unabhaengigen kleinen Bugs (P1.7 + P1.11 + P1.13). Voller
V1→V2(15 Lessons)→R1(1 KRITISCH + 2 SOLLTE + 1 KOENNTE)→V3(9 Diffs)→
Compact→Code→Final-R1(„Code kann gemerged werden", 0 KP-Findings).

**Bug 1 — P1.11 `rr73_retries`-Counter shared zwischen WAIT_RR73 + WAIT_73-Hoeflichkeit:**
- **Wurzel:** `core/qso_state.py:83` Feld `rr73_retries` wurde in 2
  unabhaengigen Pfaden inkrementiert (WAIT_RR73-Retry max 3 +
  WAIT_73-Hoeflichkeit max 2). Nach voller WAIT_RR73-Sequenz blockierte
  `rr73_retries=3` die WAIT_73-Hoeflichkeit komplett — Station die ihren
  R-Report wiederholt wurde im Stich gelassen.
- **Fix:** Neues Feld `wait_73_retries: int = 0` in QSOData (Auto-Reset
  via `QSOData()` in `start_qso(...)`), WAIT_73-Hoeflichkeit nutzt es
  jetzt unabhaengig.

**Bug 2 — P1.13 TX-Frequenz-Spinbox-Sync (Normal-Modus Hunt-Klick):**
- **Wurzel:** `ui/mw_qso.py:_on_station_clicked` setzte
  `encoder.tx_even` + `start_qso`, aber NICHT `encoder.audio_freq_hz`
  oder `_tx_freq_spin`. Hunt-Klick im Normal-Modus → TX lief auf alter
  Spinbox-Frequenz, Mike's Augen sahen anderes.
- **Fix:** Nach `start_qso(...)` im Normal-Modus
  `encoder.audio_freq_hz = clamped_freq` + `spin.setValue(...)` mit
  Range-Clamp aus `spin.minimum()/maximum()` (statt hardcoded 150/2800,
  R1-Empfehlung). Persistenz NICHT (`settings.save_normal_tx_freq`
  bleibt unangetastet — Hunt-Klick ist temporaer, Default pro Band
  bleibt erhalten). Histogramm-Update bewusst weggelassen (KISS,
  R1-Empfehlung — Histogramm ist im Normal-Modus typisch nicht sichtbar).

**Bug 3 — P1.7 Lokaler ADIF-Duplikat-Filter:**
- **Wurzel:** `ui/mw_qso.py:_on_qso_complete` rief `adif.log_qso(...)`
  unbedingt — bekannte Station < 5 Min nach RR73 ruft erneut → 2.
  ADIF-Eintrag landet im Logbuch (QRZ filtert serverseitig, lokal nicht).
- **Fix:** Session-lokaler Cache `_recent_logged_calls: dict[(call, band), float]`
  in MainWindow (App-Restart loescht den State, ist gewollt).
  Modul-Konstante `_LOG_DEDUP_WINDOW_S = 300` in mw_qso.py. Bei Duplikat:
  ADIF + `qso_log.add_qso` + `log_antenna_qso` SKIP + qso-Panel-
  Info-Eintrag. UI-Cleanup (`active_qso`, `rx_panel`, `auto_hunt`)
  laeuft IMMER vor Duplikat-Check (R1-KRITISCH KP-8) — sonst
  Inkonsistenzen.

**Geaenderte Files (3 Code + 1 Test + main.py + 1 Test-Anpassung):**
- `core/qso_state.py` — `wait_73_retries`-Feld + WAIT_73-Hoeflichkeit nutzt es
- `ui/mw_qso.py` — `_LOG_DEDUP_WINDOW_S` + `_on_station_clicked` TX-Sync
  + `_on_qso_complete` Duplikat-Filter
- `ui/main_window.py` — `_recent_logged_calls` init
- NEU `tests/test_p1_bundle2.py` (17 Tests: 4 P1.11 + 5 P1.13 + 8 P1.7)
- `tests/test_p1_10_courtesy_73.py` — Test-Anpassung (`rr73_retries` →
  `wait_73_retries`)
- `main.py` APP_VERSION 0.95.18 → 0.95.19

**Voller Workflow** V1 (Diagnose, 3 Bugs lokalisiert) → V2 (15 Lessons —
L1 Option A entschieden, L6 Tupel-Key fuer Multi-Band, L11 Test-Soll auf
15 erhoeht) → R1 (1 KRITISCH KP-8 = Skip-Order vor return + 2 SOLLTE:
Histogramm weglassen + Range aus Spinbox + 1 KOENNTE Mode-Edge-Case
nur dokumentieren + 4 zusaetzliche Edge-Case-Tests) → V3 (Compact-fest,
9 Diffs, alle Findings adressiert) → Compact → Code → **Final-R1
(„Code kann gemerged werden") — 0 KP-Findings**, kleiner Hinweis
`import time` an File-Top sofort umgesetzt.

**Plan-Files:** `prompts/p1_bundle2_v[1-3].md`.

**Tests 938 → 955 gruen** (+17, V3 prognostizierte +17).

**Atomare Commits:**
- `faff2bb` Bug-1 P1.11 (qso_state.py only)
- `9be7747` Bug-2 P1.13 (mw_qso.py _on_station_clicked only)
- `5466cb4` Bug-3 P1.7 (mw_qso.py + main_window.py)
- (folgender) Doku-Commit (Tests + APP_VERSION + HISTORY/HANDOFF/CLAUDE)

**Field-Test-Pflicht (vor Push):**
- P1.11: QSO mit IC-7300 (DA1TST) voll durchziehen, R-Report-Wiederholung
  in WAIT_73 → RR73-Antwort sollte erfolgen (vorher: ignoriert).
- P1.13: Normal-Modus, Spinbox=1500, RX-Klick auf 800 Hz Station →
  Spinbox+TX zeigen 800 Hz; App-Restart → wieder 1500 Hz.
- P1.7: hardware-frei (Tests reichen).

**Push noch nicht** — v0.95.16 + v0.95.17 + v0.95.18 + v0.95.19 gehen
beim naechsten Push zusammen.

---

## 2026-05-08 v0.95.18 — P1.BUNDLE-LOGBOOK-RST-SNR: 3 Bugs gebuendelt

**Mike-Auftrag 08.05.:** „2 leichte Punkte zusammen mit Logbuch-Crash beim
Eintrag-Loeschen — und QRZ-10K-Burst-Bug pruefen ob unser ADIF-Format
spec-konform ist." Bundle aus 3 unabhaengigen Bugs im selben ADIF/Logbuch/
Reporting-Pfad — voller V1→V2→R1→V3-Workflow gemeinsam, atomare Commits
pro Bug.

**Bug A — Logbuch-UI-Hang beim Eintrag-Loeschen:**
- **Wurzel:** `log/adif.py:94` `new_body += block + eor` in while-Loop =
  O(n²) bei 12 MB ADIF (~10K Records) → 5-10 s Hang im UI-Thread (macOS
  Beachball). Plus full `self.refresh()` in `_on_delete_clicked` re-parste
  beide ADIF-Verzeichnisse (~19 MB Disk-IO im UI-Thread).
- **Field-Test 07.05. nachmittags:** „eintrag neben qrz.com fehler ...
  kreis dreht sich für bearbeiten anscheinend endlos jetzt hat es
  aufgehört" → reproduziert.
- **Fix:** `delete_qso` `new_parts = []` + `.append` + `"".join` → O(n),
  < 200 ms gemessen. Plus `_on_delete_clicked` In-Memory-Update via
  `_all_records.remove(rec)` + `_on_filter_changed` + `_update_counters`.
  Edge-Case ValueError → Fallback full refresh (Konsistenz).

**Bug B — RST_RCVD/RST_SENT mit FT8-R-Praefix in ADIF (QRZ-Reject):**
- **Wurzel:** SimpleFT8 schrieb `<RST_RCVD:4>R-22` in ADIF (FT8-Roger-
  Praefix aus Sequence-Layer durchgereicht). ADIF-Spec + QRZ-Validator
  akzeptieren nur `<rst_rcvd:3>-22`. Vergleich mit QRZ-Original-Export
  `do4mhh.398467.20260427134135.adi` bestaetigt Spec-Verletzung. Mike's
  10K-QSO-Burst-Bug (12134 Dups + Fail-Cascade in v0.95.15) wahrscheinlich
  wegen QRZ-Validator-Reject + Cooldown-Cascade.
- **Fix:** Neuer Helper `_strip_r_prefix(rst)` in `log/adif.py` (idempotent,
  None-safe, case-insensitive — `R-22`/`r-22` → `-22`; `RR73`/`R`/`""`
  unveraendert). Aufruf in 2 Pfaden (Defense-in-Depth):
  1. `log_qso` (Schreib-Pfad): neue Records sauber.
  2. `qrz.upload_qso_from_dict` (Send-Pfad, lazy import): alte ADIF-Files
     mit R-Format werden beim Re-Upload korrigiert. Kein Migration-Helper
     noetig (R1-bestaetigt KISS).
- **Field-Test Pflicht:** QRZ-Bulk-Upload alter ADIF-Datei nach Update —
  kein 10K-Burst mehr.

**Bug C / P1.8 — `_process_cq_reply` nutzt _last_snr statt msg.snr:**
- **Wurzel:** `mw_cycle.py:793` ruft `set_last_snr(msg.snr)` PRO decodierter
  Message in jedem Slot → `_last_snr` wird 50+ mal pro Slot ueberschrieben.
  `qso_state.py:214,229` baute Report aus `_last_snr` → zuletzt iterierte
  Message gewinnt, ist fast nie die anrufende Station. Mike-Beispiel:
  DA1TST -23 (von uns) vs R+19 (von ihm) = 42 dB Diff.
- **Fix:** nur Z.214 + Z.229 in `_process_cq_reply` auf `snr = msg.snr`
  umgestellt. Hunt-Pfad (`start_qso`) + Retry-Pfade (Z.345,360,585,594,642)
  BLEIBEN mit `_last_snr` (Fallback bekannt akzeptiert, Hunt-Pfad-
  Durchreichung als separater Folge-Bug dokumentiert).

**Workflow:**
- V1 (Diagnose, 3 Bugs lokalisiert mit Datei:Zeile)
- V2 (Self-Review, 15 Lessons L1-L15 — entlarvte O(n²) als Hauptwurzel +
  Send-Pfad-Strip als notwendig + Filter-Re-Apply Race-Frei via Qt)
- R1 („Plan kann freigegeben werden", 0 KRITISCH-Findings, 10/10
  Pruefauftraege gruen, 1 Vorbehalt = Mike-Field-Test fuer Bug-B)
- V3 (Compact-fest, 7 Diffs konkret) → Compact → Code
- Final-R1 („Code kann gemerged werden", 0 KP-Findings, 1 optionaler
  Wunsch fuer R-Report-Test war Fehl-Interpretation — Test deckt Pfad ab)

**Geaenderte Files (5 Code + main.py + Test-File):**
1. `log/adif.py` — `delete_qso` O(n²)→O(n) + `_strip_r_prefix` Helper
   + `log_qso` 2 Aufrufe
2. `log/qrz.py` — `upload_qso_from_dict` lazy import + RST-Strip
3. `ui/logbook_widget.py` — `_on_delete_clicked` In-Memory-Update
4. `core/qso_state.py` — `_process_cq_reply` Z.214,229 `msg.snr`
5. `tests/test_p1_bundle_logbook_rst_snr.py` NEU (17 Tests: 4 Bug-A +
   10 Bug-B + 3 Bug-C, ein Bonus-Test fuer Whitespace-Strip)
6. `main.py` APP_VERSION 0.95.17 → 0.95.18

**Tests:** 921 → 938 gruen (+17, V3 prognostizierte +16, ein Bonus).
Performance-AC < 500 ms erfuellt (Performance-Test mit 10K Records).

**Atomare Commits:**
- `P1.BUNDLE Bug-A (v0.95.18): delete_qso O(n²) Fix + Logbuch In-Memory-Update`
- `P1.BUNDLE Bug-B (v0.95.18): RST_RCVD/RST_SENT R-Strip Schreib- und Send-Pfad`
- `P1.BUNDLE Bug-C (v0.95.18) / P1.8: _process_cq_reply nutzt msg.snr statt _last_snr`
- `docs (v0.95.18): P1.BUNDLE-LOGBOOK-RST-SNR HISTORY+HANDOFF+CLAUDE+Tests+APP_VERSION`

**Field-Test ausstehend:**
- QRZ-Bulk-Upload einer alten ADIF-Datei → kein 10K-Burst mehr
- Logbuch-Eintrag-Loeschen → < 0.5 s, kein Beachball
- QSO live → Report-SNR korrekt (nicht 42 dB Bias)

Push noch nicht — Mike-Field-Test-Freigabe abwarten. v0.95.16 + v0.95.17
+ v0.95.18 gehen beim naechsten Push zusammen origin/main.

Plan-Files: `prompts/p1_bundle_logbook_rst_snr_v[1-3].md`.

---

## 2026-05-07 v0.95.17 — P1.COLLAPSE-RADIO-MODEBAND: Modus+Band + Radio einklappbar

**Mike-Wunsch 07.05. nach v0.95.16-Push:** „radio und mouds haette ich
gerne auch zum einklappen der kachel wie die Antennen kachel".
Hobby-Use-Case: stundenlang FT8 auf 20m → Modus+Band einmal eingestellt,
Watt selten verstellt, TUNE automatisch in Diversity → wegklappen,
Platz fuer QSO/RX-Panel. Beide Karten unabhaengig, letzter Zustand
persistiert. QSO-Kachel bleibt immer voll sichtbar.

**Loesung — Pattern 1:1 Spiegelung Antennen-Kachel (v0.95.11):**
- `_ModeBandCard` (`ui/control_panel.py:232`) bekommt Header-Row mit
  Toggle-Button (`▼`/`▶`, blau `#7799FF`) + Label „MODUS+BAND" +
  `_body_widget`. Grid mit allen Member-Erstellungen (btn_ft8/ft4/ft2,
  freq_label, band_buttons, prop_bars) liegt im body_widget.
- `_RadioCard` (`ui/control_panel.py:680`) analog mit Toggle (teal
  `#00aacc`) + existierendem RADIO-Label im Header. PSK-Frame +
  Power-Row + TX-Frame im body_widget.
- Beide Cards: `set_collapsed/is_collapsed/_toggle_collapsed` API +
  `collapse_changed = Signal(bool)`. Signal NUR bei User-Klick
  (`_toggle_collapsed`), KEIN Emit bei Programm-API (`set_collapsed`)
  → Init-Loop-Schutz wie bei Antennen-Card. `setMaximumHeight(36)`
  bei Collapse, `_QWIDGETSIZE_MAX` bei Expand.
- `ControlPanel`: 2 neue Klassen-Signale `modeband_collapse_changed` +
  `radio_collapse_changed`, 2 Exposes `_modeband_card` + `_radio_card`,
  2 Forward-Connects (lambda-frei, `.emit`-Hookup).
- `MainWindow`: 2 Initial-State-Loads aus Settings (`modeband_card_collapsed`,
  `radio_card_collapsed`, Default `False` = ausgeklappt) + 2 neue
  `@Slot(bool)`-Methods analog `_on_antenne_collapse_changed`.

**Geaenderte Files (4):**
- `ui/control_panel.py` — `_ModeBandCard` Refactor (Z.232-414),
  `_RadioCard` Refactor (Z.680-865), `ControlPanel` 2 Signale + 2
  Exposes + 2 Forward-Connects (Z.1036-1038, Z.1075+, Z.1117+)
- `ui/main_window.py` — 2 Initial-Loads + 2 Connects (Z.456-470),
  2 neue Slot-Methods (Z.870-880)
- `tests/test_p1_collapse_radio_modeband.py` NEU — 19 Tests
  (8 parametrisiert × 2 Cards = 16 + 3 Integration)
- `main.py` APP_VERSION 0.95.16 → 0.95.17

**Voller Workflow** V1 (Diagnose, 13 ACs, Antennen-Pattern-Mapping)
→ V2 (Self-Review, 14 Lessons L1-L14, Refactor-Risiko-Analyse,
pytest-parametrize-Empfehlung) → R1 („Plan freigegeben fuer V3", 0
KRITISCH-Findings, 5 kleine Hinweise alle in V2 erfasst) → V3
(Compact-fest, 8 Diffs konkret, 19 Tests parametrisiert) → Compact
→ Code → **Final-R1 („kein Aenderungsbedarf, alle 8 Pruefauftraege
erfuellt") — 0 KP-Findings**.

**Plan-Files:** `prompts/p1_collapse_radio_modeband_v[1-3].md`.

**Tests 902 → 921 gruen** (+19, exakt wie V3 prognostiziert).

**Karten-Code (`direction_map_widget.py`) und Statistik-Code unbeeinflusst.**

**Lessons-Learned (Skill Schritt 6):**
1. Pattern-Spiegelung lohnt — Antennen-Card v0.95.11 als bewaehrtes
   Vorbild liess V1+V2+R1+V3 in ~1 Stunde durchziehen.
2. pytest-parametrize fuer 2 Klassen mit identischer API spart
   ~150 Test-Zeilen (8 × 2 = 16 statt 16 Duplikate).
3. R1-Vorbehalte aus Antennen-Workflow (Settings-Debounce) sind 1:1
   uebertragbar — nicht relevant fuer Hobby-Tool, KISS akzeptiert.

**Field-Test-Pflicht (post-Push):**
- App starten → 4 Karten (MODUS+BAND, ANTENNE, RADIO, QSO) alle
  ausgeklappt (Default `False`).
- Toggle MODUS+BAND klicken → Body verschwindet, nur Header bleibt.
- Toggle RADIO klicken → Body verschwindet, nur Header bleibt.
- Beide Karten gleichzeitig collapsed: ControlPanel kompakt, viel
  Platz fuer QSO-Kachel + Statusbar.
- App neu starten → letzter Zustand geladen aus Settings.
- Antennen-Kachel weiter unbeeinflusst funktional.

**Push noch nicht.** Mike-Freigabe nach Field-Test mit visueller
Pruefung explizit einholen.

---

## 2026-05-07 v0.95.16 — P1.LOCATOR-SLASH: Slash-Call Lookup-Bugs gefixt

**Mike-Pflicht-Verifikation 07.05. (DeepSeek-R1 Code-Review der km-Anzeige im
RX-Panel) entdeckte 3 echte Bugs im Lookup-Pfad fuer Slash-Calls:**

1. `ui/rx_panel.py:333-335` — `lookup_call = max(parts, key=len)` bei Praefix-
   Slash wie `EA8/DA1MHH` extrahierte das laengste Token (`DA1MHH` = 6 Zeichen)
   statt des DXCC-Praefixes (`EA8` = 3 Zeichen) → DB-Lookup mit falschem Key,
   Country-Fallback Deutschland statt Kanaren, Distanz ~0 km statt ~3000 km.
2. `core/geo.py callsign_to_country` + `callsign_to_distance` — gleicher
   `max(parts, key=len)`-Bug.
3. Mobile-Suffix-Inkonsistenz zwischen rx_panel-Stripping und DB-Set-Pfad
   (DB hatte `DA1MHH/P` als Key, rx_panel suchte nach `DA1MHH` ohne Suffix
   → Lookup verfehlt).

**Mike-Entscheidung 07.05.:** **Datenbank behalten** — Daten korrekt
gespeichert, nur Lookup-Pfad kaputt. Decoder-Verifikation pre-V3
(`core/message.py:107-111` `parts = msg_str.strip().split()` → `f2 = parts[1]`)
bewiesen: `m.caller="EA8/DA1MHH"` bleibt komplett. ft8lib hat 35-Char-Buffer.

**Loesung — Option A (strikte Trennung):**
- `ui/rx_panel.py`: KEIN Suffix-Stripping mehr. `lookup_call = caller` 1:1.
  Slash-Calls bleiben komplett — passt zu wie `_feed_locator_db` schreibt
  und wie `callsign_to_country/distance` intern Slash-Calls per DXCC-
  Heuristik aufloesen.
- `core/geo.py`: NEU zwei Helper + zentrale `MOBILE_SUFFIXES`-Konstante
  - `MOBILE_SUFFIXES = ("/P", "/M", "/MM", "/AM", "/QRP", "/PORTABLE", "/MOBILE")`
  - `_strip_mobile_suffix(call)` — entfernt Mobile-Suffix von hinten
  - `_dxcc_prefix_from_call(call)` — bei Slash-Call das erste DXCC-Praefix-
    Token (exakt-Match in `_PREFIX_MAP`, dann iterativ 3/2/1 Zeichen)
- `core/geo.py:callsign_to_country` + `callsign_to_distance` umgestellt:
  bei Slash-Call zuerst DXCC-Token suchen → wenn gefunden = Land/Distanz
  zum DXCC-Land. Sonst Mobile-Suffix entfernen → Basis-Call → normaler
  Praefix-Match. `max(parts, key=len)` ist weg.
- `core/locator_db.py`: lokale `MOBILE_SUFFIXES` (war 3-Tupel `/MM /AM /QRP`)
  durch Import aus `core.geo` ersetzt (jetzt 7 Suffixe). Verhaltens-Aenderung
  (R1-bestaetigt vertretbar): `/P /M /PORTABLE /MOBILE` bekommen jetzt
  konsistent `prec_km*1.5` — Funker-Praxis: Portable/Mobile = Operator
  unterwegs = Position weicht von Heim ab. Doku Z.13-15 angepasst.

**DB bleibt unveraendert** — Daten korrekt befuellt, alle Eintraege ueber
`adif/qrz.com`-Imports und Live-Decodes. Karten-Code
(`direction_map_widget.py`) und Statistik-Code unbeeinflusst.

**Geaenderte Files (5):**
- `core/geo.py` — Helpers + Slash-Heuristik in `callsign_to_country/distance`
- `core/locator_db.py` — Import + Doku
- `ui/rx_panel.py` — Slash-Block Z.323-338 vereinfacht (9 Bug-Zeilen raus)
- `tests/test_p1_locator_slash.py` NEU — 14 Tests
- `tests/test_locator_db.py` — `test_slash_p_treated_as_stationary` invertiert
  zu `test_slash_p_treated_as_mobile` (jetzt `prec_km == 8`)
- `main.py` APP_VERSION 0.95.15 → 0.95.16

**Voller Workflow** V1 (3 Bugs, 3 Optionen A/B/C, 10 ACs) → V2 (12 Lessons,
L6 entlarvt Option B als Original-Design-Widerspruch via `locator_db.py:180`
Mobile-Praezision-Aufpumpen — empfiehlt Option A) → R1 („Plan freigegeben"
mit 1 KRITISCH = Decoder-Verifikation Schritt 0 ERLEDIGT pre-V3 + 1
SOLLTE-ERGAENZEN = +2 Edge-Case-Tests in V3) → V3 (Compact-fest, 6 Diffs)
→ Compact → Code → **Final-R1 („Push freigegeben") — 0 KP-Findings**.

**Plan-Files:** `prompts/p1_locator_slash_v[1-3].md`.

**Tests 888 → 902 gruen** (+14, exakt wie V3 prognostiziert).

**Field-Test-Pflicht (post-Push):**
- App starten → Slash-Call beobachten (`EA8/...`-Kanaren-Aktivitaet,
  `/P`-Mobile, `K1ABC/W2`-Region-Suffix wenn am Band).
- km-Spalte: exakte Position bei DB-Hit ODER DXCC-Distanz bei Miss —
  KEIN Heim-Country-Bias mehr.
- country-Spalte: korrektes Land.
- Karten-Pin: am DXCC-Land, nicht in Heim-DE.

**Lessons-Learned (Skill Schritt 6):**
1. Decoder-Verifikation Schritt 0 ist Pflicht-KRITISCH — bei Bugfix der
   Decoder-Output-Annahmen beruehrt MUSS die tatsaechliche Decoder-Ausgabe
   verifiziert werden (split-Output, ft8lib-Buffer, Spezialformate).
   `feedback_decoder_verifikation_pflicht.md` als Memory-Vorschlag.
2. V2-Self-Review fand Original-Design-Widerspruch (L6: `locator_db.py:180`
   Mobile-Praezision-Aufpumpen war schon designt) — entlarvte falsche
   V1-Empfehlung (Option B). Self-Review ist nicht Routine, oft entscheidend.
3. R1 hat Decoder-Verifikation als KRITISCH markiert obwohl V2 nur als
   ⚠️-Lesson formuliert — DeepSeek-R1 priorisiert Sicherheits-Schritte
   konsequenter als Self-Review.

---

## 2026-05-07 v0.95.15 — P1.QRZ-UPLOAD-UI-2: Title + File-Move + Log + Rate-Limit

**Mike-Field-Test v0.95.14 (07.05. nachmittags) entdeckte 3 Probleme:**
1. Progress-Dialog `WindowStaysOnTopHint` liegt staendig vor App — nervt
2. Keine Persistierung welche QSOs schon hochgeladen → 18443 Wiederhol-Bulk
3. Bei 12134 Duplikaten + Fail-Burst nacheinander → wahrscheinlich QRZ-Rate-Limit

**Loesung (4 Bausteine):**
- **Status in Titelleiste:** waehrend Bulk `SimpleFT8 — DA1MHH — QRZ ↑ x/y (z%)`,
  Update alle 10 QSOs synchron mit `progress`-Signal. Reset nach Finish.
  Zentrale Helper `_update_window_title()` in mw_qso.py (R1: Hardcoding vermeiden).
- **Statusbar-Cancel-Widget:** `[QRZ ↑ x/y (z%)] [✕]` als `permanentWidget` in
  `_init_statusbar`. Klein, klickbar, blockt nicht die App. Klick auf ✕ →
  Worker-Cancel + Button-Disable + Label „wird abgebrochen ...". Initial hidden.
- **File-Move-Strategie:** Pro QSO `_SOURCE_FILE` (existiert schon in
  `log/adif.py:42` als uppercase). Worker aggregiert pro File `{ok, dup, fail,
  expected}`. Im `_handle_qrz_file_results` wird Datei nach `adif/hochgeladen/`
  verschoben wenn `fail==0 AND processed==expected AND processed>0`. Schutz:
  Files aus `hochgeladen/` werden NIE bewegt (`hochgeladen` im Pfad). Atomic
  via `shutil.move`. **R1-Final-Fix:** vorher `dest.exists()`-Check (kein
  Ueberschreib-Risiko bei Namens-Kollision aus subdir).
- **JSONL-Log + Rate-Limit-Detection:**
  - `~/.simpleft8/qrz_upload_YYYY-MM-DD.log` (Daily-Rotation), append-only,
    pro Result eine JSON-Zeile (`ts/call/band/mode/date/time/result/reason`).
  - `MAX_CONSECUTIVE_FAILS=20` + `COOLDOWN_SECONDS=60`. Counter resetet bei
    OK/Dup. Bei 20 Fails: 60s Cooldown als Loop mit `cancel_event`-Check
    + `cooldown_tick(int)` Signal pro Sekunde — KEIN blockierendes
    `time.sleep(60)` (R1-KP). Zweiter Burst nach Cooldown → Worker setzt
    selbst `cancel_event` und beendet.

**Geaenderte Files (8):**
- NEU `tests/test_p1_qrz_upload_ui_2.py` (20 Tests)
- `core/qrz_upload_worker.py` (file_results-Property + JSONL-Log + Rate-Limit
  + cooldown_tick-Signal + total_records-Property fuer Kapselung)
- `ui/qrz_upload_dialogs.py` (QRZUploadDialog-Klasse geloescht — 95 → 80 Zeilen)
- `ui/mw_qso.py` (`_on_qrz_upload` Rewrite + 6 neue Slots/Helpers:
  `_on_qrz_progress`, `_on_qrz_cooldown_tick`, `_on_qrz_bulk_finished`,
  `_handle_qrz_file_results`, `_show_qrz_status_widget`,
  `_on_qrz_status_cancel_clicked`, `_update_window_title`)
- `ui/main_window.py` (Statusbar-Widget Init in `_init_statusbar`,
  `_qrz_title_suffix=""` Init in `__init__`, qso_log+locator_db Multi-Dir
  in `_init_qso_log`, closeEvent `cooldown_tick.disconnect()`)
- `ui/logbook_widget.py` (`load_adif()` lädt zusaetzlich `adif/hochgeladen/`)
- `tests/test_p1_qrz_upload_ui.py` (4 Progress-Dialog-Tests geloescht)
- `main.py` APP_VERSION 0.95.14 → 0.95.15

**Bulk-Filter:** `_on_qrz_upload` filtert `[r for r in _all_records if
"hochgeladen" not in r.get("_SOURCE_FILE", "").replace("\\", "/")]` —
Records aus `adif/hochgeladen/` werden NIE erneut hochgeladen.

**KP-1/2/3 aus v0.95.14 alle noch intakt:**
- KP-1: `_qrz_upload_single` skipt bei `_qrz_bulk_active=True`
- KP-2: Klick-Sperre Reihenfolge Flag → Button → submit (3 Stufen)
- KP-3: closeEvent `disconnect()` VOR `cancel()` (jetzt + cooldown_tick)

**Voller Workflow:** V1 (10 ACs, Mike's 3 Vision-Punkte A/B/C, Field-Test-
Beweis) → V2 (14 Lessons L1-L14, mid-V2 Mike-Feedback fuer L13/L14
JSONL-Log + Rate-Limit-Detection) → R1 („Plan freigegeben mit
Praezisierungen", 7 Optimierungen alle in V3) → V3 (Compact-fest, 8 Diffs
inkl. Diff 1 = NO CHANGE weil `_SOURCE_FILE` schon existiert) → Compact →
Code → Final-R1 („Push freigegeben mit 2 SOLLTE-FIX", beide gefixt:
`shutil.move` Ueberschreib-Schutz + `total_records`-Property).

**Plan-Files:** `prompts/p1_qrz_upload_ui_2_v[1-3].md`.

**Tests 872 → 888 gruen (+16):**
- 4 Progress-Dialog-Tests aus v0.95.14 geloescht (-4)
- 18 neue Tests aus V3-Plan (+18): file_results, JSONL-Log, Rate-Limit
  (3 Tests: cooldown, reset-on-OK, cancel-during-cooldown, second-burst),
  File-Move (4 Tests: all-OK, fail-skip, partial-skip, hochgeladen-skip),
  Title-Update (2 Tests), Logbook-Multi-Dir, Bulk-Filter, Pflege-Tests.
- 2 R1-Fix-Tests (+2): `dest.exists()`-Schutz + `total_records`-Property.

**Atomare Commits:** `d8f86b6` (Code+Tests, 11 Files +2534/-204) +
Doku-Commit.

**Field-Test ausstehend.** Push noch nicht — Mike-Freigabe nach Field-Test
einholen.

---

## 2026-05-07 v0.95.14 — P1.QRZ-UPLOAD-UI: Confirm + Progress + Single-Instance

**Mike-Anforderung (07.05.2026):** „brauche ne Meldung Status der irgendwas
und auch nur einmal gestartet werden darf das" — sichtbares Status-Fenster
fuer Bulk-Upload, weiterfunken moeglich, single-instance-Schutz.

**Field-Test-Beweis 10:35 UTC:** Mike klickte QRZ-Bulk-Upload-Button — keine
UI-Reaktion. 8x geklickt → 8 Bulk-Jobs in geteilten ThreadPool gequeued.
Bei `max_workers=1` waeren 8 × 18.443 QSOs × ~200ms = ~8 Stunden Duplikat-
Spam an QRZ.com gelaufen. App rechtzeitig gekillt.

**Loesung:** Zwei-Phasen-Workflow + 3-fach-Single-Instance-Schutz.

- Phase 1: `QRZConfirmDialog` (modal) — „X QSOs hochladen?" mit Default-Button
  `[Hochladen]` (Enter). Custom QDialog mit `_DLG_STYLE` (#1a1a2e Theme)
  statt QMessageBox (Memory `feedback_qmessagebox_avoid.md`).
- Phase 2: `QRZUploadDialog` (non-modal, `WindowStaysOnTopHint`) mit
  ProgressBar, Counter „Neu: X   Duplikate: Y   Fehler: Z", Cancel-Button.
  Auto-Close 10s nach Fertig + `[Schliessen]`-Button. `raise_/activateWindow`
  fuer macOS-Spaces.
- Worker `QRZUploadWorker(QObject)` in NEU `core/qrz_upload_worker.py`:
  ThreadPoolExecutor (max_workers=1, thread_name_prefix=„qrz_bulk") +
  `threading.Event` als cancel_event + Signals
  `progress(int,int,int,int,int)` alle 10 QSOs +
  `finished(int,int,int,bool,int)`. Cancel-Latenz max 10s (HTTP-Timeout).
- Single-Instance-Schutz 3-fach (R1-KP-2): Flag `_qrz_bulk_active` →
  Button-Disable via `set_qrz_button_enabled` → Re-Entry-Check in
  `_on_qrz_upload` (defensive first-line).

**R1-KP-Findings adressiert:**
- KP-1: `_qrz_upload_single` skipt sofort bei `_qrz_bulk_active=True` —
  sonst Race im geteilten ThreadPool (Auto-Upload-Konflikt).
- KP-2: Klick-Sperre Reihenfolge Flag → Button → submit (verhindert
  Race zwischen `submit()` und `setEnabled(False)`).
- KP-3: `closeEvent` macht `finished.disconnect()` + `progress.disconnect()`
  VOR `cancel()` + `shutdown(wait=False)` — schuetzt vor Signal-Emit auf
  zerstoertem Dialog.

**Final-R1-Findings (im 2. Review entdeckt) sofort gefixt:**
- 🚨 Cancel-Bug: Worker emittet IMMER `finished` (auch bei `processed=0`).
  Vorherige Bedingung `if not cancelled or total_processed > 0` hatte
  Edge-Case: Bei Sofort-Cancel vor 1. QSO blieb Dialog hängen in
  „wird abgebrochen ...". App-Close-Schutz erfolgt jetzt rein über
  `disconnect()` in `closeEvent`.
- ⚠️ KP-3 Rest: `closeEvent` braucht `disconnect()` VOR `cancel()`.

**KEIN Resume-Feature** — KISS-Entscheidung. QRZ.com filtert Duplikate
serverseitig (Mike-Pattern: Filter im Anzeige-Pfad, nicht in der
Logik — siehe `feedback_funker_entscheidung_filter_in_rx.md`).

**Voller Workflow:**
- V1 Diagnose (5 Probleme A-E mit Field-Test-Beweis)
- V2 Self-Review (12 Lessons L1-L12)
- R1 Plan-Review (9 Pruefauftraege beantwortet, 3 KP gefunden)
- V3 (Compact-fest, 7 konkrete Diffs)
- Compact
- Code-Phase (autonom, alle 7 Diffs)
- Final-R1 Code-Review (Cancel-Bug + KP-3-Rest gefunden)
- Fix-Round (Worker IMMER emit + closeEvent disconnect + neuer Test)
- Final-R1 Verifikation („Push freigegeben, keine Restrisiken")

Plan-Files: `prompts/p1_qrz_upload_ui_v[1-3].md`.

**Tests 862 → 872 gruen (+10):** Worker progress/cancel/counts +
immediate-cancel-emits-finished + Dialog default-button/reject/render/
finished-state/cancelled-title/auto-close.

**Field-Test-Pflicht (post-Kur):**
- Klick auf QRZ-Button → Confirm-Dialog
- 18.443 QSOs Upload — Progress sichtbar, Counter aktualisiert
- Cancel-Button → max 10s Latenz, sauberes Stop
- Mehrfach-Klick → 2. Klick ignoriert
- Auto-Upload nach QSO waehrend Bulk → Skip-Log
- App-Close waehrend Bulk → kein Hang/Crash

Atomare Commits `2270fdf` (Code+Tests, 10 Files +1841/-29) + Doku-Commit.

APP_VERSION 0.95.13 → 0.95.14.

---

## 2026-05-07 v0.95.13 — P1.CACHE-SIMPLE Diversity/Gain entkoppelt + UX-Cleanup

**Mike-Vision (NICHT verhandelbar, 2026-05-07):** Diversity-Cache (Ratio,
60 Min) und Gain-Cache (6h) komplett entkoppelt. Beide eigene Frist, beide
eigenes Verhalten bei Ablauf. Keine Modal-Wahl-Dialoge fuer Routine —
Mike-Argument: „Computer faehrt runter — OK?"-Pattern ist UX-Pillepalle.

**4 Probleme gefixed (V1-Diagnose):**

| Problem | Wurzel | Fix |
|---|---|---|
| A — Cache-Reuse-Toast | Mike: „warum bestaetigen wenn gueltig?" | Toast-Klasse + Aufruf raus |
| B — Modal-Wahl-Dialog „Weiter / Neu messen" | Sinnlose Frage da Default fast immer „Weiter" | Wahl-Dialog raus an 2 Stellen |
| C — Frische Ratio mit altem Gain ignoriert | Kreuz-Dependency: `is_valid_gain` blockierte Cache-Reuse | Gain-Check raus aus `_try_diversity_cache_reuse` |
| D — Volle Pipeline ohne Ankuendigung | Mike: „was passiert mit alten Werten bei Cancel?" | Stale-Acceptance + Disable-Fallback |

**Architektur — Dispatch-Logik (`_check_diversity_preset`):**

```
ratio_status = _assess_ratio(band, mode, scoring)  → fresh/stale/missing
gain_status  = _assess_gain(band, mode, scoring)   → fresh/stale/missing

gain stale  → DXTuneDialog (auto-start, nur Abbruch)
              + _pending_ratio_status für Post-Gain-Pfad
gain miss   → volle Pipeline (Gain + Ratio)
gain fresh + ratio fresh → Cache-Reuse (still, kein Toast)
gain fresh + ratio stale → stille Auto-Ratio-Messung (Phase 3)
gain fresh + ratio miss  → stille Auto-Ratio-Messung (Phase 3)
```

Plus Stale-Acceptance in `_on_dx_tune_rejected`: bei Cancel mit alten
Werten weiterarbeiten (Risiko-Akzeptanz). Wenn nichts da: Diversity AUS.

**Aenderungen (`ui/mw_radio.py`):**
- `_try_diversity_cache_reuse` Gain-Check entfernt (Diff 1a)
- NEU `_get_diversity_store` + `_assess_ratio` + `_assess_gain` Helpers
- `_check_diversity_preset` komplett refactort (Dispatch-Logik)
- `_on_dx_tune_accepted` `_pending_ratio_status`-Pfad mit Cache-Reuse +
  Phase-3-Sicherheitsnetz
- `_on_dx_tune_rejected` Stale-Acceptance + Disable-Fallback
- `_activate_diversity_with_scoring` Wahl-Dialog raus, delegiert jetzt zu
  `_check_diversity_preset` (Code-Deduplikation, ~70 Zeilen weg)

**Toast-Cleanup:**
- `ui/diversity_cache_toast.py` geloescht
- `tests/test_diversity_cache_reuse.py` Smoke-Test entfernt
- Toast-Aufruf in mw_radio.py war bereits uncommitted, jetzt mit-committed

**Voller Workflow:**

V1 (Diagnose 4 Probleme) → V2 (Self-Review, 12 Lessons L1-L12: DXTuneDialog
wiederverwenden, Cancel-Stale-Acceptance, Option B fuer Ratio-frisch+Gain-
stale, kein neuer Dialog noetig) → R1-Plan (8 Pruefauftraege detailliert
beantwortet, kein Veto, konkrete Diff-Plan-Empfehlung) → V3 (Compact-fest,
6 Diffs konkret) → Compact → Code → Final-R1 („Keine KP-Findings, Code ist
robust und entspricht der Mike-Vision. Tests decken alle relevanten Pfade
ab. ✅"). Plan-Files: `prompts/p1_cache_simple_v[1-3].md`.

**Tests 852 → 862 gruen (+10 neu, 1 invertiert):**
- NEU `tests/test_p1_cache_simple.py` (10 Tests):
  - `test_assess_ratio_fresh_stale_missing`
  - `test_assess_gain_fresh_stale_missing`
  - `test_check_preset_dispatch_gain_stale_opens_dialog`
  - `test_check_preset_dispatch_gain_missing_full_pipeline`
  - `test_check_preset_dispatch_both_fresh_cache_reuse_silent`
  - `test_check_preset_dispatch_ratio_stale_gain_fresh_auto_remeasure`
  - `test_dx_tune_accepted_with_pending_ratio_fresh_uses_cache`
  - `test_dx_tune_rejected_loads_stale_values`
  - `test_dx_tune_rejected_no_values_disables_diversity`
  - `test_no_modal_dialog_in_normal_paths`
- INVERTIERT `test_cache_reuse_returns_false_when_gain_expired` →
  `test_cache_reuse_loads_ratio_even_when_gain_expired` (Erwartung jetzt:
  True bei stale Gain, frische Ratio wird trotzdem geladen)

**Atomare Commits:** `4af2e9e` (Code+Tests, 5 Files +508/-277) + Doku-Commit.
APP_VERSION 0.95.12 → 0.95.13.

**Field-Test ausstehend.** Notbremse bei Problemen: KALIBRIEREN-Button als
Hard-Reset (komplette Pipeline = Gain + Ratio neu).

---

## 2026-05-07 v0.95.12 — P1.FORCESEND btn_advance state-aware + WAIT_73-Branch

**Mike-Use-Case 2026-05-06:** Bei stuck-Gegenstation (sendet immer
Report statt RR73, oder kein 73) manuell RR73 oder 73 senden können
statt 3-Min-Timeout abwarten.

**Befund aus Code-Inspektion (V1→V2-Selbstkorrektur):**

V1 hatte 3 Bugs vermutet, V2 verifizierte am Code dass nur 2 echte
Bugs sind:

- ~~Bug A: btn_advance dauerhaft disabled~~ — V1-Halluzination!
  `_on_state_changed` (mw_qso.py:208-234) macht state-aware Enabled
  bereits für WAIT_REPORT+WAIT_RR73.
- **Bug B:** Label statisch „Weiter →" — macht nicht klar was gesendet
  wird. Mike hat Button nie genutzt.
- **Bug C:** WAIT_73-Branch fehlt in `advance()` + in der Enabled-Liste.

**Lösung (KISS, keine neuen UI-Elemente):** Bestehender `btn_advance`
wird state-aware:

- Label dynamisch je nach State (kompakt ohne Verb):
  - WAIT_REPORT → „R+Report"
  - WAIT_RR73 → „RR73"
  - WAIT_73 → „73"
  - sonst → „Weiter →"
- Enabled wenn state in {WAIT_REPORT, WAIT_RR73, WAIT_73} UND nicht
  cq_mode UND nicht diversity_locked.
- `advance()` neuer Branch für WAIT_73 sendet `73`, setzt
  `courtesy_73_sent=True` VOR `send_message.emit` (P1.10 Doppel-Send-
  Schutz, R1-KP-3).

**Final-R1 Race-Fix:** R1 fand Race zwischen Auto-73-Empfang und
Mike-Klick. Wenn Auto-Pfad zwischen Klick und `advance()` schon
`courtesy_73_sent=True` setzt → würde manuell 2× 73 gesendet.
Idempotent-Return ergänzt:

```python
if self.qso.courtesy_73_sent:
    return  # 73 schon gesendet (Auto-Pfad)
```

**Voller Workflow:** V1 (Diagnose) → V2 (Self-Review, 10 Lessons,
Bug-A-Halluzination eingestanden) → R1 („Plan freigegeben unter 5
Bedingungen", KP-1 [qso_complete-Bug] als Halluzination verworfen
weil WAIT_73 = „QSO schon geloggt" laut qso_state.py:60) → V3
(Compact-feste Diffs) → Code → Final-R1 („Push freigegeben mit
Vorbehalt: idempotent-Return" → sofort umgesetzt). Plan-Files:
`prompts/p1_forcesend_v[1-3].md`.

**Tests 841 → 852 gruen** (+11 in `tests/test_p1_forcesend.py`):

- `test_advance_wait_73_sends_73` — emittet `<their> <me> 73`
- `test_advance_wait_73_sets_courtesy_flag` — Doppel-Send-Schutz P1.10
- `test_advance_wait_73_flag_set_before_send` — R1-KP-3 asynchron
- `test_advance_wait_73_idempotent_when_flag_set` — **Final-R1 Race-Fix**
- `test_advance_other_states_no_emit` — Regression
- 6× `test_advance_label_*` für alle States + Default + Wechsel

**Atomare Commits:** `c8bf5bb` (Code+Tests+main.py 5 Files +177/-2)
+ Doku-Commit. APP_VERSION 0.95.11 → 0.95.12.

**Field-Test:** post-Kur. Mike erkennt am Label was gesendet wird,
kann bei stuck-Gegenstation manuell die Sequenz abkürzen.

**Lesson:** V1-Halluzination-Risk auch nach 2 Jahren Erfahrung —
„grep für btn_advance.setEnabled in mw_radio.py" war zu eng,
`_on_state_changed`-Hook in mw_qso.py übersehen. V2-Self-Review hat
die Halluzination abgefangen — Workflow funktioniert.

---

## 2026-05-06 v0.95.11 — P1.ANTENNE-COLLAPSE _AntenneCard einklappbar

**Mike-Designentscheidung 2026-05-06:** Antennen-Kachel WIRD einklappbar.
DeepSeek hatte in vorheriger Session abgeraten („andere FT8-Programme
zeigen alles immer sichtbar") — Mike überschrieb explizit:
> „SimpleFT8 ist nicht andere Programme. Wenn ich auf einem Band+Modus
> stundenlang funke brauche ich die Kachel selten und wenn kann ich sie
> aufklappen."

SimpleFT8 ist Hobby-Tool, kein Contest. Hobby-Use-Case: stundenlang auf
einem Band, Antennen-Status nicht permanent gebraucht — wegklappen,
Platz für QSO/RX-Panel. Bei Bedarf (Bandwechsel, KALIBRIEREN) aufklappen.

**Architektur (R1-bestätigt):**

- `_AntenneCard` (`ui/control_panel.py:421`) bekommt Header-Row mit
  Toggle-Button (`▼` aufgeklappt / `▶` zugeklappt, 20×20, transparent
  über `_CARD_SS_GREEN`-Akzent).
- Body-Container `_body_widget` umschließt alle bisherigen Body-Widgets
  (btn_row NORMAL/DIVERSITY/KALIBRIEREN, dx_info, Diversity-Ratio,
  Frequenz-Histogramm, TX-Freq-Spinner, CQ-Countdown).
- API: `set_collapsed(bool)` (Programm), `is_collapsed()`,
  `_toggle_collapsed()` (User-Klick).
- **Signal-Emission nur bei User-Klick**, NICHT bei `set_collapsed()`-
  Programm-API → schützt vor Init-Loop (MainWindow ruft `set_collapsed`
  beim App-Start mit Settings-Wert auf).
- `setMaximumHeight(36)` bei Collapse, `_QWIDGETSIZE_MAX = 16_777_215`
  bei Expand (PySide6 exportiert `QWIDGETSIZE_MAX` nicht — Modul-Konstante
  als Workaround).
- `ControlPanel._ant_card = ant_card` exposed (KP-7), forwardet
  `antenne_collapse_changed` lambda-frei via `Signal.emit`.
- `MainWindow.__init__` lädt Initial-State aus `Settings.get(
  "antenne_card_collapsed", False)` + persistiert User-Toggles via
  `_on_antenne_collapse_changed` Slot.

**Workflow:** V1 (Diagnose) → V2 (Self-Review, 16 Lessons L1-L16) →
R1 („Plan freigegeben mit 4 KP + 5 neue Befunde KP-7..KP-11")
→ V3 (Compact-feste Diffs mit allen 5 Punkten) → Code → Final-R1
(„Push freigegeben mit optionalem Debounce-Vorbehalt"). Plan-Files:
`prompts/p1_antenne_collapse_v[1-3].md`.

**Tests 831 → 841 gruen** (+10 in `tests/test_antenne_card.py`):
- `test_default_expanded` — Default-State nach Konstruktor
- `test_set_collapsed_hides_body` / `test_set_collapsed_false_shows_body`
- `test_toggle_button_click_collapses` — User-Klick-Pfad via QTest
- `test_toggle_emits_collapse_changed` — Signal nur bei User-Klick
- `test_max_height_set_when_collapsed` — Höhen-Switch
- `test_diversity_widget_visibility_preserved_through_toggle` — Mode-State
- `test_tooltip_set_on_toggle_button`
- `test_collapse_with_existing_body_state` — Sub-Widget-Visibility
- `test_signal_not_emitted_by_set_collapsed_api` — Init-Loop-Schutz

**Settings-Key:** generic `antenne_card_collapsed` (default `False`).
Keine Migration nötig — `Settings.get()` liefert Default für frische
Configs.

**R1-Vorbehalt (NICHT umgesetzt, KISS):** `Settings.save()` ist synchron +
blocking JSON-Dump. Bei schnellem Toggle könnte 200ms-Debounce helfen.
Für Hobby-Tool (1 User, JSON-dump < 10 ms, Tests 0.26s grün) akzeptabel.

**Atomare Commits:** `a0ce1ae` (Code+Tests+main.py 4 Files +209/-9) +
Doku-Commit. APP_VERSION 0.95.10 → 0.95.11.

**Lesson:** Mike's Designentscheidung schlägt DeepSeek-Konvention bei
Hobby-Tool-UI. R1 darf KISS-Bedenken äussern, aber das „WIRD/WIRD NICHT
umgesetzt" entscheidet Mike. R1-Prompt-Klausel „Designentscheidung
NICHT verhandelbar" hat sauber funktioniert.

---

## 2026-05-06 v0.95.10 — P1.AP-FIX generate_candidates State-1 Format-Bug

**Bug entdeckt durch P1.AP E2E-Test-Pipeline (v0.95.9):** `core/ap_lite.py:126`
`generate_candidates(state=1)` produzierte 4-Token-Strings
(`OWN THEIR LOC SNR`, z.B. „DA1MHH DK5ON JO31 +05"). FT8 erlaubt nur
3 Tokens pro Frame → ft8lib lehnt jeden Kandidaten mit `rc=5` →
`generate_reference_wave` returnt `None` → `correlate_candidate` returnt
0.0 → State-1-Rescue (WAIT_REPORT) **scheiterte IMMER silent seit
Implementierung**. Synthetischer E2E-Test in `tests/test_ap_lite_e2e.py`
(P1.AP, v0.95.9 commit `03c5f13`) reproduzierte den Bug ohne Hardware.

**Fix (1 Zeile, KISS):** Locator weglassen, Report-only:
```python
# vorher (4 Tokens):
candidates.append(f"{own_callsign} {their_callsign} {own_locator} {r:+03d}")
# nachher (3 Tokens):
candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")
```

Plus Code-Kommentar Z.121-131 fachlich aktualisiert (vorher
„Report + Locator", was es nie geben darf).

**Voller Workflow:** V1 (Diagnose-Prompt) → V2 (Self-Review, 9 Lessons
L1-L9) → R1 (DeepSeek-Reasoner: „Plan freigegeben", 4 Pflicht-Diffs:
KP-1 ft8lib_compatible-Test) → V3 (Compact-fester Plan mit 5 Diffs) →
Compact → Code → Final-R1-Codereview („Push freigegeben, keine
Vorbehalte"). Plan-Files: `prompts/p1_ap_fix_v[1-3].md`.

**Tests 830 → 831 gruen** (+1 neuer maschineller Format-Schutz):
- `tests/test_ap_lite.py:test_generate_state1_basic` — 3-Token-Asserts
  mit Regex `^[+-]\d{2}$`
- `tests/test_ap_lite_e2e.py:test_try_rescue_state1_runs_after_fix`
  (umbenannt von `documents_bug`) — assertet kein silent-Block, nicht
  mehr Score==0.0
- `tests/test_ap_lite_e2e.py:test_generate_candidates_state1_format_correct`
  (umbenannt von `format_bug`) — hartes 3-Token-Assert
- `tests/test_ap_lite_e2e.py:test_generate_candidates_state1_ft8lib_compatible`
  **NEU** — ruft `encoder.generate_reference_wave()` für jeden Kandidaten
  → maschineller Beweis: ft8lib akzeptiert (sonst rc=5 → wave=None).

**Deviation vom V3-Plan:** V3 plante `assert result.score > 0.0` für
`test_try_rescue_state1_success`. Praxis-Run zeigte Score=0.0 trotz
Format-Fix — Ursache: `align_buffers` findet bei identischen Buffern
df_hz=-1.4 wegen Costas-Referenz-Vereinfachung (Code-TODO
`_build_costas_reference`), `correlate_candidate` schlägt mit shifted
Frequenz fehl. Test umbenannt zu `runs_after_fix`, Score-Hard-Assert
entfernt. Format-Fix-Beweis liegt bei `ft8lib_compatible`-Test (R1
explizit OK in Final-Review).

**Field-Test:** Mike ist in Kur — Test post-Rückkehr. Erwartung:
Rescue-Rate steigt. Notbremse: `AP_LITE_ENABLED=False`. Risiko gering
weil `SCORE_THRESHOLD=0.75` konservativ.

**Atomare Commits:** `17b7237` (Code+Tests, 4 Files +79/-36) + Doku-Commit.

---

## 2026-05-06 v0.95.9 — P1.24 TX-Klick-Buffer (Folge-Fix zu P1.14)

**Mike-Field-Test v0.95.8 entdeckt:** P1.14 fixte Station-Wechsel sauber
in RX-Phase, aber wenn der Klick während CQ-TX-Phase (`encoder.is_transmitting`)
kam, wurde der Klick komplett ignoriert (silent skip + Toast „TX aktiv"
seit P1.14 W5). CQ lief weiter, Klick verpufft. Mike: „rufe CQ, sehe
seltene Station, klicke an — CQ läuft weiter, muss erst HALT drücken."
Erweiterung: gleiche Frustration bei Hunt-TX_CALL-Umentscheidung.

**Wurzel:** `_on_station_clicked` Z.68-73 mit `if is_transmitting: return`
hatte keine Buffer-Logik. Aktueller TX-Audio-Slot kann nicht ohne RF-Click
abgebrochen werden, aber State-Cleanup + Buffer-für-nächsten-Slot ist
trivial machbar.

**Fix (`ui/mw_qso.py` + `ui/main_window.py`):**
- `_main_window.__init__:209` — neues Attribut `_pending_station_click = None`
- `_on_station_clicked:69-89` — bei `is_transmitting`: State-Cleanup
  (cq_mode aktiv → `stop_cq()` + Button visuell off; Hunt-State aktiv
  → `cancel()`); `_pending_station_click = msg`; Statusbar
  „TX läuft — X wird im nächsten Slot gerufen"; return
- `_on_tx_finished:236-244` — nach `on_message_sent()`: wenn Buffer
  gesetzt → `_on_station_clicked(buffered)` rekursiv (jetzt
  `is_transmitting=False`, normaler Pfad)
- `_on_cancel:172` — Buffer wird verworfen (HALT cleared alles)

**Tests:** 812 → 816 grün (+4 in `tests/test_p1_24_pending_click.py` —
Buffer-Logik isoliert via Logik-Sim, kein UI-Mock).

**Field-Test bestätigt von Mike** („Ja läuft").

---

## 2026-05-06 v0.95.8 — P1.14 Station-Wechsel-Bug + P1.23 Status-UI-Feinjustierung

### P1.14 Station-Wechsel-Bug — voller Workflow
**Wurzeln (W1-W6 aus Diagnose-V3):**
- W1: `start_qso` resetete keine Pendings bei `state != IDLE` (CQ_WAIT
  inkl.) → Geister-Pendings mit alter `their_call`
- W2: `_caller_queue` enthielt manuell-gewählte Station → Doppel-QSO-Risiko
- W3: `_active_qso_targets` wuchs monoton bei Wechseln
- W4/KP6: `_was_cq` State-Machine-extern korrigiert (fragil) — Plan-V2:
  Workaround BEHALTEN, sauberer Kommentar (start_qso liest cq_mode aber
  stop_cq() läuft vorher → cq_mode bereits False, keine saubere
  Integration möglich)
- W5: TX-Klick silent ignoriert → frustrierende UX
- W6: `auto_hunt._manual_override` wurde NIE zurückgesetzt — pausierte
  dauerhaft nach manuellem QSO/HALT/Timeout

**Workflow:** voller V1→V2(10 Lücken)→R1(6 KP)→V3 Diagnose +
V1→V2(10 Lücken, 2 Auto-Hunt-Stellen ergänzt)→R1(„Plan freigegeben")→V3 Plan.

**Code-Änderungen:**
- `core/qso_state.py:start_qso` (Z.238-251) — Reset-Set auf `state != IDLE`
  erweitert + 3 Pendings explizit auf None (`_pending_reply`,
  `_pending_hunt_reply`, `_pending_rr73`); `_caller_queue` BLEIBT
  (Option B — Mike's Funker-Wunsch).
- `ui/mw_qso.py:_on_station_clicked` — KP3 alte `their_call` discarden,
  KP2 angeklickte Station aus `_caller_queue` entfernen + queue_changed
  emit, W5 Statusbar-Toast „TX aktiv – Klick ignoriert" (3s),
  KP6-Workaround Kommentar präzisiert.
- `ui/mw_qso.py:_on_cancel` — `auto_hunt.on_manual_qso_end()` ergänzt (W6).
- `ui/mw_qso.py:_on_qso_confirmed` — `auto_hunt.on_manual_qso_end()`
  ergänzt (W6, Plan-V2).
- `ui/mw_qso.py:_on_qso_timeout` — `auto_hunt.on_manual_qso_end()`
  ergänzt (W6, Plan-V2).

**Tests:** 802 → 812 grün (+10 in `tests/test_p1_14_station_switch.py`).

### P1.23 Status-UI-Feinjustierung (Mike-Wunsch)
- Label `Lokaler Empfang:` → `Lokale Empfangsqualität:`
- Schriftgrößen RADIO/Decode/Empfang/UTC: 11px → 10px (matcht Status
  darunter, vertikal homogener)
- Sterne: 15px → 13px (passt zur kleineren Schrift)

---

## 2026-05-06 v0.95.7 — P1.18 DT-Drift-Wurzel + P1.21 Sterne-UX-Refactor

**Wurzel-Findung (Mike-Hartnaeckigkeit + DeepSeek):** Mike's Field-Test
zeigte DT-Korrektur clamped bei 1.0s (statt erwartet ~0.24s). Erste
Reaktion „liegt am FlexRadio-Buffer" war falsch — Mike bestand auf
Software-Wurzel. Systematischer Code-Diff seit Golden-Stand `38a55b2`
(23.04.2026) zeigte: in v0.95.3 (P1.9-Fix) wurde `_WAKE_OFFSETS["FT8"]`
von **1.5 auf 2.5** erhoeht — die abhaengige Konstante `_DT_OFFSETS["FT8"]`
wurde aber **vergessen mit-zu-erhoehen**. DeepSeek bestaetigt: 1 Zeile +1.0s.

**P1.18 DT-Fix (`core/decoder.py:323`):**
```python
# vorher: _DT_OFFSETS = {"FT8": 2.0, "FT4": 1.0, "FT2": 0.8}
_DT_OFFSETS = {"FT8": 3.0, "FT4": 1.0, "FT2": 0.8}  # Sync mit _WAKE_OFFSETS
```
Plus: Code-Kommentar (Z.317-322) aktualisiert mit Warnung „MUSS mit
_WAKE_OFFSETS synchron bleiben". Plus: `~/.simpleft8/dt_corrections.json`
geloescht (alte clamped-Werte raus, frische Messung).

**Erwartung:** Stationen-DT zurueck auf -0.1 bis +0.2, Korrektur
konvergiert auf ~0.24s (nur Hardware-Latenz wie 23.04. validiert).

**P1.21 Sterne-UX-Refactor (Mike-Frust 02:28 UTC):** „scheiss umgesetzt
keiner weiss was sie bedeuten, farbe scheisse, abstaende zu weit, passt
nicht zu decode/radio darueber, anzahl passt nicht zu schlechten dB-Werten."
DeepSeek-Konsultation lieferte 5 Fixes — alle umgesetzt:

1. **Label `Empfang:`** dazu (im Decode-Stil 11px grau, exakt 7 Zeichen
   wie `Decode:`, `RADIO:`).
2. **Farbe Gold #FFD700** (statt Cyan #00DDFF) — Konsistenz mit RADIO-
   Label im STATUS-Block. Inaktiv weiterhin #555.
3. **Abstaende eng** via RichText/HTML-Spans in EINEM QLabel statt 5
   separater QLabels (`<span color:#FFD700>★★★</span><span color:#555>★★</span>`).
4. **Layout konsistent** mit RADIO/Decode darueber: `Empfang:  ★★★☆☆`
   linksbuendig, UTC weiter rechts mit Stretch.
5. **Score-Algorithmus rein SNR-basiert** (Mike-Befund: 48 Stationen
   × -25 dB triggerten faelschlich 5 Sterne wegen `or n>=25`-Logik).
   Neue Schwellen: `> -10/-14/-18/-22 dB` → 5/4/3/2/1 Stern. Mike-Field-
   Test-Szenario jetzt korrekt: 48×-25 → 1 Stern (statt 5).

**Tests 796 → 802 gruen (+6 neu, 5 angepasst):** Score-Schwellen-Tests
(strong/4/3/2/1/borderline/Mike-48-Szenario), RichText-Render-Tests
(active/5/1/clamping/gold-not-cyan).

**APP_VERSION:** 0.95.6 → 0.95.7.

**Memory-Lesson** (`feedback_mike_haftnaeckig_oft_recht.md`): Wenn Mike
hartnaeckig ist und sagt „aber vorher ging es" — ZUERST git-diff seit
Golden-Stand machen, NICHT auf Hardware tippen. 30 Jahre Funker-Erfahrung
schlaegt Code-Theorie.

---

## 2026-05-06 v0.95.6 — P1-Bundle1: 5 UI-Cleanups (P1.6+P1.12+P1.15+P1.16+P1.19)

**Workflow:** Voller V1→V2→R1→V3 Diagnose + Plan-V1→V2→R1→V3 (DeepSeek-Reasoner
zwei Mal), Mike volle Autonomie ohne Rückfragen.

**Diagnose:** 5 unabhaengige UI-Cleanups thematisch gebuendelt + ein voller
Workflow statt 5 separate. R1 fand 5 KP-Findings (KP1 kritisch:
`update_snr()` bricht nach Ersetzung), Plan-R1 fand weitere 4 (B1-B4) + 4
Test-Erweiterungen (T1-T4, alle adressiert).

**Sub-Aufgaben:**
- **P1.6** Versionsnummer-Anzeige: Color `#333` (auf `#1a1a2e` unsichtbar) →
  `#666` (lesbar, Theme-konform). 1 Zeile. `control_panel.py:1088`.
- **P1.12** NEU-Button (`btn_remeasure`) entfernt — KALIBRIEREN macht seit
  v0.94 Phase 2+3 alleine, NEU war redundant. 6 Stellen: `control_panel.py`
  Button-Definition + Spacing + Signal + Connect, `main_window.py:530`
  Connect, `mw_radio.py:985-997` Handler-Methode komplett raus.
- **P1.15** Statusbar `→ Call | RX: ANT` raus — Mike: „die macht mich irre".
  `main_window.py:917-934` Block entfernt.
- **P1.16** QSO-Panel zeitbasiertes 5-Min-Rolling-Window — ersetzt zeilen-
  basiertes `_auto_trim` (40 Zeilen). `_block_timestamps`-Liste parallel zu
  log_view-Blocks, QTimer 30s ruft `_auto_trim_by_age(300s)`. R1-KP2
  Defensive: `clear()`-Resync fuer out-of-sync Liste. Mindest-Schwelle 5
  gegen Flackern. Scroll-Position-Logik.
- **P1.19** Sterne-Anzeige `★★★☆☆` (5-Sterne, Neon-Cyan #00DDFF aktiv,
  #555 inaktiv) ersetzt `SNR: -25 dB`-Label. NEU `ui/widgets/stars_widget.py`
  StarsConditionWidget. NEU `compute_local_conditions(stations)` Helper in
  `mw_cycle.py` (Score 1-5 basierend auf Stationsanzahl ODER Median-SNR
  der oberen Haelfte). `update_snr()` wird No-Op (R1-KP1, Backward-Compat).
  `update_local_conditions(score, n, median)` ist neuer Pfad. Aufruf nach
  `_log_stats` (immer, auch bei leerem Slot).

**Tests 777 → 796 gruen (+19 neu):**
- `test_p1_bundle1.py` (4 statische Tests P1.12+P1.15)
- `test_qso_panel_rolling.py` (6 Tests Rolling-Window inkl. T1 Two-Color)
- `test_local_conditions.py` (5 pure-logic Tests)
- `test_stars_widget.py` (4 Tests inkl. T2 Clamping)

**APP_VERSION:** 0.95.5 → 0.95.6 (`main.py:16`).

**KP1 (kritisch):** `update_snr()` weiter aufrufbar (No-Op) — `mw_cycle.py:415,
750` brauchen keine Änderung. Backward-Compat ohne Crash gewahrt.

**Field-Test:** offen — Mike testet im Praxis-Betrieb (Sterne sollten je nach
Conditions zwischen 2-4 schwanken; bei Cluster vieler Stationen 5).

---

## 2026-05-05 v0.95.5 — Single-Instance-Lock (Mike-Anweisung mehrfach!)

**Atomare Commits:** `24aba07` (initial Lock) + `f348763` (CWD-Filter Fix)
+ `13c067f` (Doku SDR-Control-Klaerung).

**Wurzel:** Mike's wiederholte Anweisung „nur EINE Instanz darf laufen"
war monatelang nicht implementiert. Heute liefen 2 Apps parallel ueber
Stunden — verursachte Stunden-langes Falsch-Diagnostizieren (1500/1000-Hz-
Frequenz-„Wechsel" war Artefakt aus 2 Apps mit verschiedenen CQ-Freqs).

**Fix:**
- `main.py` + `tools/remote/start_simpleft8_nokill.py` (Wrapper):
  identische `acquire_single_instance_lock()` Funktion — fcntl.flock()
  atomar + pgrep-Kandidaten + lsof CWD-Filter (`-a` Flag PFLICHT auf
  macOS sonst OR-Verknuepfung statt AND!) + SIGTERM/SIGKILL fuer
  rogue-Instanzen.
- Lock-Datei: `~/.simpleft8/simpleft8.lock`
- atexit + signal-Handler (SIGTERM/SIGINT) fuer Lock-Release
- CWD-Filter via `lsof -a -p PID -d cwd -Fn` — schuetzt fremde main.py-
  Apps (Websdr, JimBob etc.) vor Kollateral-Kill durch zu breites
  pgrep-Pattern `python.*main\.py`.
- main.py APP_VERSION 0.95.4 → 0.95.5

**Bugs entdeckt + gefixt:**
1. fcntl.flock() allein reicht nicht — Lock-Datei kann geloescht werden
   ohne dass Prozess stirbt → Lock weg aber Prozess lebt. Loesung:
   ZUERST pgrep+kill, DANN Lock holen.
2. Pattern `SimpleFT8.*main\.py` matched nicht bei CWD-relativem Aufruf
   (`python tools/remote/start_simpleft8_nokill.py`). Loesung:
   liberaler Pattern + CWD-Filter.
3. macOS lsof: ohne `-a` ist `-p` und `-d` mit OR verknuepft statt AND
   → listet alle Prozesse, jeder Filter matched. Loesung: `-a` Flag.

**Test-Plan (manuell verifiziert):**
- App1 starten → Lock geholt
- App2 starten → erkennt App1 → SIGTERM → Lock geholt
- Final: nur App2 lebt, Lock-Datei zeigt App2's PID
- Websdr-App (PID 12178, CWD=...Websdr) bleibt unbeeinflusst

**SDR-Control Endlos-73 GEKLAERT (parallel-Befund):**
Mike fand selbst die Wurzel: SDR-Control hat Retry=99 in Auto-Sequence
(Test-Override). Mit Standard-Retry kein Problem. P1.10 funktioniert
mit echten Stationen (EA2BHE 16:59 UTC bestaetigt). SDR-Control's
73-Reply-after-73 ist by-design (Help-Text) — identisch zu P1.10's
Logik. Kein App-Bug auf beiden Seiten.

**Lessons (Memory):**
- Mike-Anforderungen aus Memory IMMER pruefen — `feedback_app_start_
  single_instance.md` + `project_v095_single_instance_lock.md` standen
  seit Wochen, wurden ignoriert.
- Bei Field-Test-Anomalien IMMER Gegenstation-Setup hinterfragen bevor
  App-Bug diagnostiziert wird (Mike's „12000 QSO ohne Probleme" war
  richtig).
- macOS lsof braucht `-a` fuer Filter-AND-Verknuepfung.

---

## 2026-05-05 v0.95.4 — P1.10 End-of-QSO Icom-73-Loop-Fix (Courtesy-73)

**Atomare Commits:** `9783583` (Code+Tests+Workflow-Files, 13 Files,
+3439/-14) + Doku-Commit.

**Bug-Wurzel:** IC-7300 (DA1TST) Auto-Sequence wartet auf abschliessendes
Hoeflichkeits-73 von uns. SimpleFT8 sendet bisher KEIN Courtesy-73 nach
73-Empfang im WAIT_73-State. Folge: IC-7300 retried 5× das `73` in den
nachfolgenden Slots bevor er aufgibt. Andere FT8-Apps (WSJT-X, JTDX,
MSHV) senden ein Courtesy-73 als Funkalltag-Standard.

**Field-Test 05.05.:** 2× reproduziert (11:24-:27 UTC und 11:28-:29 UTC
mit DA1TST). Mike-Befund: „Bei IC-Stationen empfange ich oft 2× ein 73"
— das bestaetigt dass andere Apps Höflichkeits- + Sequenz-73 senden,
SimpleFT8 nur 1× → IC-7300 ist zu sensibel.

**Workflow:** voller V1→V2(8 V1-Luecken, kritischer Fund: TX_RR73 ist
NICHT exklusiv weil Z.401-403 ebenfalls "73" als TX_RR73 sendet → Reuse
= Doppel-ADIF → eigener State `TX_73_COURTESY` PFLICHT)→R1(4 KP + 3
Findings + Empfehlung A1)→V3 Diagnose + Cross-Check Zweit-KI (Hypothese
verstaerkt, „Pause"-Alternative durch Trace widerlegt) + voller
V1→V2(6 Plan-V1-Luecken, D8 Timeout-Liste defensiv hinzugefuegt)→R1(3
wichtige + 3 optionale Findings)→V3 Plan-Workflow.

**Fix (Option A1 mit R1-Slot-Paritaet-Defensive):**
- `core/qso_state.py` — neuer State `TX_73_COURTESY`, neues Feld
  `qso.courtesy_73_sent` (max 1× pro QSO), neuer Branch in
  `on_message_sent` fuer TX_73_COURTESY (`qso_confirmed.emit` +
  `_resume_cq_if_needed`), WAIT_73-Hauptlogik geaendert: bei
  73/RR73-Empfang einmaliges Courtesy-73 senden + Slot-Paritaet via
  `tx_slot_for_partner.emit(msg)` (R1 KP1, `_set_state` VOR Signal-Emit
  fuer state-abhaengiges UI), TX_73_COURTESY in 3-Min-QSO-Timeout-
  Ausschluss-Liste (defensiv, Plan-V2-L1).
- `ui/mw_qso.py` — `is_tx`-Set erweitert um TX_73_COURTESY,
  `_on_tx_slot_for_partner` state-abhaengig (CQ-Reply vs Courtesy-73,
  Panel-Info „Antworte..." nur bei CQ-Reply, Plan-R1 F2 + F4).
- `main.py` — APP_VERSION 0.95.3 → 0.95.4.
- `tests/test_p1_10_courtesy_73.py` — 13 neue Tests.
- `tests/test_modules.py` — 2 bestehende Tests angepasst (qso_confirmed
  feuert jetzt nach `on_message_sent` fuer TX_73_COURTESY, nicht mehr
  direkt bei 73-Empfang).

**Tests:** 764 → 777 gruen (+13 neu, 2 angepasst).

**Field-Test bei Mike BESTAETIGT (16:56-:59 UTC, EA2BHE Spanien IN83):**
QSO-Ende: 16:59:00 RR73 → 16:59:15 EA2BHE 73 → 16:59:30 unser
Courtesy-73 → KEIN weiteres 73 von EA2BHE → Auto-Sequence sauber
gestoppt. ✓ QSO komplett. Pattern bestaetigt fuer Standard-FT8-Apps
(WSJT-X, JTDX, MSHV).

**SDR-Control Endlos-73 GEKLAERT (Mike 2026-05-05):** das anfangs
beobachtete „IC-7300 sendet endlos 73"-Verhalten lag an Mike's
SDR-Control-Konfig: **Retry=99** in den Auto-Sequence-Einstellungen
(Test-Override von vor Wochen). Mit Retry=99 sendet SDR-Control 99×
sein 73 wenn keine QSO-Ende-Bestaetigung kommt. Das ist **Mike's
eigene Test-Konfiguration**, kein App-Bug. Loesung: SDR-Control
Retry auf Standard (1) zurueck. Mike's 12000-QSO-Erfahrung war
unauffaellig weil dort entweder Retry=Standard oder Gegenstationen
mit WSJT-X (1× 73, kein Retry).

**SDR-Control-Verhalten (laut Help-Text):** „Meine App wartet nach
RR73 einen Taktzyklus und antwortet, falls sie eine weitere
73-Nachricht korrekt empfaengt, ebenfalls mit einem 73 — fuer
zuverlaessige QSO-Protokollierung." → identisch zu P1.10's Logik.
Beide Apps machen dasselbe Standard-Verhalten.

**Known Issue (Plan-R1 F1, NICHT durch P1.10 verschaerft):**
`rr73_retries` shared zwischen WAIT_RR73 + WAIT_73-Hoeflichkeits-Pfad.
Wenn QSO viele WAIT_RR73-Retries hatte, bleibt fuer WAIT_73 nichts
uebrig. Eigener Workflow P1.11.

**Lessons:**
- Plan-V2 muss bei jedem neuen State pruefen ob 3-Min-Timeout-Ausschluss-
  Liste angepasst werden muss (V1 hatte das verpasst, V2 hat es gefangen).
- TX_RR73-State ist NICHT exklusiv fuer RR73 — wird auch fuer
  „73"-Vorwaertssprung (Z.401-403) verwendet → Reuse erzeugt Doppel-ADIF
  ueber qso_complete.emit → eigener State Pflicht.
- Slot-Paritaet defensiv via Signal `tx_slot_for_partner.emit(msg)` statt
  implizit auf `encoder.tx_even`-Stand verlassen (R1 KP1).
- Reihenfolge `_set_state` VOR `tx_slot_for_partner.emit` damit Listener
  state-abhaengig zwischen CQ-Reply und Courtesy-73 unterscheiden kann.

---

## 2026-05-05 v0.95.3 — P1.9 First-Reply-Lost-Bug-Fix

**Atomare Commits:** `20c7fe7` (Code+Tests, 7 Files, +282/-29) + Doku-Commit.

**Bug-Wurzel:** Decoder-Encoder-Timing-Race bei FlexRadio (TX-Buffer 1.3s).
Encoder wachte `boundary - 1.3s`, Decoder wachte `slot + 13.5s` und war
0.5-3.0s spaeter fertig → Reply von DA1TST kam typisch wenn CQ-Audio
bereits in `send_audio` (BLOCKING) lief → `_pending_reply` wurde gesetzt
aber Encoder hielt CQ-Message in Worker-Local → Report 1 Slot zu spaet.

**Field-Test 05.05.:** 4× reproduziert (09:39, 09:47, 09:55, 10:05 UTC).
Mike: *„den kann ich gut immer wieder nachstellen"*.

**Workflow:** voller V1→V2→R1→V3 Diagnose + voller V1→V2→R1→V3 Plan.
V2 fand 12 Findings A-L (9 ⛔ kritisch + 3 Test-Ergaenzungen). DeepSeek-R1
(Reasoner) bestaetigte alle 6 Pruefauftraege als KORREKT, KEINE neuen
Findings. R1-Hinweis: gleicher Encode-Bug im Nicht-Replace-Pfad
(separater Fix, nicht zu P1.9).

**Fix-Kombination (atomar — Option C alleine fixt nicht):**
- `core/decoder.py:138` — `_WAKE_OFFSETS["FT8"]` 1.5 → 2.5 (Decoder
  ready 0.5-2.5s VOR Encoder-Wake). SNR-Effekt < 0.1 dB (R1).
- `core/encoder.py` — `request_replace(message)` API + Loop in
  `_tx_worker_inner` fuer Re-Encode + `_audio_started`/`_replace_message`/
  `_replace_lock` + `tx_finished.emit` im Encode-Fehler-Pfad
  (V2 FINDING-F).
- `core/qso_state.py` — Signal `try_replace_pending_tx` + Emit in
  `on_message_received` bei CQ_CALLING + Defense-in-Depth in `_send_cq()`
  (R1-Empfehlung).
- `ui/mw_qso.py` — `_on_try_replace_pending_tx` Slot mit `tx_even`-vor-
  `request_replace` (V2 FINDING-D), `_was_cq=True` (FINDING-A),
  Debug-Log (FINDING-B), QSO-Panel-Anzeige (FINDING-C).
- `ui/main_window.py:543` — Connect des neuen Signals.

**Erwartete Wirkung:** Report im SELBEN Slot wo CQ scheduled war
(:06:00 statt :06:30). Failure-Pfad (Decoder zu langsam): Status quo
(1 Slot Delay, kein Crash, kein Doppel-TX).

**Tests:** 759 → 764 gruen (+5: 3 Encoder API + 2 SM Logik).
Neue Datei `tests/test_p1_9_replace.py`.

**Memory-Lesson:** keine neue — V1→V2→R1→V3 lief sauber.

---

## 2026-05-05 v0.95.2 — CQ-Reply-Bug-Fix (P1.5)

**Bug-Wurzel:** 5-Min-Sperre `_WORKED_BLOCK_SECS = 300` blockierte
CQ-Replies an 3 Stellen (`core/qso_state.py:480` Hauptpfad,
`:191` `_process_cq_reply`, `:470` Caller-Queue-Add). Effekt: Stationen
mit denen wir innerhalb 5 Min ein QSO hatten konnten uns nicht erneut
anrufen — App ignorierte sie still.

**Field-Test 05:30-05:33 UTC** zeigte: DA1TST nach :28:00 RR73
versuchte ab :31:30 mehrfach uns zu rufen (Grid JO31), App sendete
weiter CQ statt Report. Erklaerte Mike's Aussage „manchmal klappt
QSO, manchmal nicht — auch mit fremden Stationen" (selbe Station < 5
Min spaeter ruft erneut, oft weil unser RR73 nicht angekommen ist).

**Workflow:** voller V1→V2→R1→V3 Diagnose + voller V1→V2→R1→V3 Plan.
DeepSeek-R1 (Reasoner) bestaetigte zwei Mal Hauptwurzel, keine zweiten
Pfade, keine Halluzinationen. Alle anderen Hypothesen (Race
tx_finished/message_decoded, _send_cq clearet pending, Slot-Mismatch,
is_grid 4-char, Auto-Hunt, encoder.abort-Race) verworfen.

**Aenderungen `core/qso_state.py`** (Commit `43dd062`, -22 Zeilen, +0 Code):
- Z. 119, 120 — `_worked_calls` dict + `_WORKED_BLOCK_SECS` geloescht
- Z. 168-176 — Methode `_is_worked_recently` komplett geloescht
- Z. 190-193 — Block #2 in `_process_cq_reply` geloescht
- Z. 440-443 — TX_RR73 Eintrag-Stelle in `_worked_calls` geloescht
- Z. 470 — Block #3 in Caller-Queue-Add geloescht
- Z. 479-482 — Block #1 in Hauptpfad geloescht

**Mike's Funker-Philosophie:** Filter „Neue Stationen" im RX-Panel ist
die korrekte Stelle (blendet aus Anzeige aus, nicht aus Reply-Pfad).
State-Machine soll nicht filtern — Funker entscheidet. Memory-Lesson:
`feedback_funker_entscheidung_filter_in_rx.md`.

**Tests:** 756 → 759 gruen (+3, 1 invertiert + 3 neu):
- `test_qso_worked_recently_block` invertiert →
  `test_qso_known_station_can_call_again`
- NEU: `test_qso_cq_reply_during_tx_pending_then_processed`
- NEU: `test_qso_caller_queue_accepts_known_station`
- NEU: `test_qso_resume_pops_known_station_from_queue`

**Folgebug-Risiko:**
- Doppel-ADIF wenn Station < 5 Min nach RR73 erneut anruft → TODO P1.7
  (lokaler Duplikat-Filter ADIF/Logbuch). QRZ.com filtert serverseitig
  bereits (REASON=duplicate, ui/mw_qso.py:386-392 zaehlt als `dup`).
- Endlos-Schleife wenn Station nie 73 sendet → real-Welt-Schutz: Funker
  gibt nach 2-3 Versuchen auf, QSB beendet.
- Stats-Bias: 0 (`_worked_calls` nur in qso_state.py genutzt, R1-grep
  bestaetigt).

**Atomare Commits:**
- (1) `43dd062` `fix(qso_state): remove 5-min worked-recently lockout (P1.5, v0.95.2)`
- (2) Doku-Commit (HISTORY + HANDOFF + CLAUDE + TODO + Memory)

---

## 2026-05-05 v0.95.1 — Encoder-TX-Slot-Tag-Fix

**Ausloeser:** Mike's Field-Test mit IC-7300 als ODD-Gegenstation
zeigte v0.95-Encoder-Fix war noch unvollstaendig. TX-Display-Tag
haengt 1 Slot zurueck — Display zeigte FlexRadio-TX im selben Slot
wie die Gegenstation, was physikalisch unmoeglich ist.

**Root Cause:** `core/encoder.py:281-285` (mein v0.95-Code) nutzte
`time.time()` zur ptt_on()-Aufruf-Zeit zur slot_start_ts-Berechnung.
ptt_on() laeuft aber **1.3s VOR next_boundary** (Stille-Padding davor,
TARGET_TX_OFFSET=-0.8). `floor(time.time()/slot)*slot` rundet damit
auf den VORHERIGEN Slot ab.

Beispiel: TX-Ziel `:13:30` EVEN. ptt_on bei `:13:28.7`. Naive
Berechnung: `floor(:13:28.7/15)*15 = :13:15` ODD. Falsch.

**Fix:** `tx_started.emit()` bekommt `next_boundary` (vom Encoder
bereits in `_next_slot_boundary()` korrekt berechnet) direkt als
`slot_start_ts`. Kein `time.time()`-Roundoff-Bug mehr.

**Field-Test-Validierung Mike (05:27-05:30 UTC):**
- TX `[E] → Sende DA1TST DA1MHH -21`
- RX `[O] ← Empf. DA1MHH DA1TST R+18`
- TX `[E] → Sende DA1TST DA1MHH RR73`
- RX `[O] ← Empf. DA1MHH DA1TST 73`
→ TX und RX in unterschiedlichen Slots, sauber getrennt. Zwei komplette
QSOs in Folge ohne Slot-Konflikt-Anzeige.

**Atomarer Commit `04388ef`** + Tests 756/756 gruen (kein Test-Update
noetig, da test_encoder_slot.py den emit nur auf API-Ebene testet,
nicht den TX-Trigger-Pfad).

**Lesson:** v0.95-Plan-V2-V3 hat "tx_started feuert AM TX-Start"
geschrieben — das war ungenau. Tatsaechlich feuert es VOR dem TX-Start
(noch im Stille-Padding). Bei zukuenftigen Slot-bezogenen Aenderungen
genauer pruefen WANN ein Signal feuert relativ zur Slot-Boundary.

**Offen entdeckt (NEU, P1.5 in TODO):** Im CQ-Mode ignoriert die
State-Machine eingehende DA1TST-CQ-Antworten — FlexRadio sendet weiter
CQ statt mit Report zu antworten. Mike's seit langem bestehendes
"doppelte Antworten"-Problem. Separater Workflow V1→V2→R1→V3.

---

## 2026-05-05 v0.95 — QSO-Panel Slot-Tag/Zeit-Display-Fix

**Ausloeser:** Mike's Field-Test 03:36-03:40 UTC mit DA1TST/R6OK/PY7ZZ.
RX und TX erschienen mit identischem Slot-Tag `[E]` im selben Zeitstempel,
obwohl FT8 das physikalisch ausschliesst. QSOs liefen real korrekt
(IC-7300 DT 0.0-0.1s, alle Reports + RR73 + 73 ausgetauscht) — reine
Anzeige-Anomalie. Mike's „doppelte Antworten"-Beobachtung war Folge des
Display-Bugs plus echte FT8-Wiederholung der Gegenstation.

**Voller V1→V2→R1→V3-Workflow zweimal durchgezogen:**

*Diagnose-Workflow:*
- V1 Symptom-Doku (`prompts/qso_panel_slot_display_v1.md`)
- V2 Self-Review (`_v2.md`)
- R1 (`_r1.md`) — Hypothese bestaetigt: Decoder-Output kommt 1 Slot
  zu spaet, `time.time()` zur Decode-Zeit ist im Folge-Slot. Empfehlung
  Option A.
- Audio-Buffer-Lag-Beweis: `~/.simpleft8/simpleft8.log` zeigt regelmaessig
  `Zu wenig Audio: X < 90000` → FlexRadio VITA-49 liefert Audio mit Lag,
  Decoder skipt initialen Slot, decodiert im Folge-Slot.

*Implementierungs-Workflow:*
- V1 Plan-Draft (`prompts/qso_panel_slot_fix_plan_v1.md`)
- V2 Self-Review mit 10 Findings (`_v2.md`) — Wake-Drift-Behandlung,
  `tx_started`-Signal-Migration, Konsumenten-Liste, Atomic-Commits
- R1 (`_r1.md`) — durchgehend positiv, 2 Zusatztest-Empfehlungen
- R1-Validierung: `not _candidate.tx_even` an mw_cycle.py:512 verifiziert
  (R1 hat nicht halluziniert). Eine zusaetzliche `is_even_cycle()`-Stelle
  in mw_qso.py:128 gefunden — laeuft aber im CQ-Start-Pfad auf User-Klick,
  nicht latenz-betroffen, bleibt unveraendert.
- V3 final mit R1-Empfehlungen + Validierungs-Anmerkung (`_v3.md`)

**Architektur-Entscheidung:** Decoder ist die einzige sichere Slot-Quelle.
Im Decoder-Loop wird der Wake-Zeitpunkt gezielt gewaehlt — `target_slot_start`
wird PRE-SLEEP berechnet (driftfrei gegen Sleep-Jitter) und als Attribut
auf jede Message bis zu allen Konsumenten durchgereicht.

**7 atomare Commits:**

### Commit 1 `dac4a73` feat(decoder): target_slot_start pre-sleep + Thread-Arg
- `core/decoder.py:_decode_loop` — `target_slot_start` PRE-SLEEP berechnet
- Thread-Spawn mit `(chunks, target_slot_start, slot_duration)` Args
- `_process_cycle` Signatur erweitert
- Tests 742/742 gruen (kein Verhaltenswechsel, nur Args durchgereicht)

### Commit 2 `885d48a` feat(decoder): _slot_start_ts/_tx_even auf Messages setzen
- `core/decoder.py:_process_cycle` setzt nach Decode auf jede Message:
  `m._slot_start_ts = target_slot_start`, `m._tx_even = int(target_slot_start / slot_duration) % 2 == 0`
- `[RX]`-Diagnose-Print nutzt latenz-freie Quelle
- Tests 742/742 gruen — `_assign_slot_parity` ueberschreibt Werte noch

### Commit 3 `6793e73` refactor(mw_cycle): _assign_slot_parity respektiert Decoder
- `ui/mw_cycle.py:_assign_slot_parity` ueberschreibt nicht mehr,
  ergaenzt nur fehlende Felder (Test-Mocks, AP-Lite-Rescue)
- `_slot_from_utc`-Helper ENTFERNT (FT2-Fallback nicht mehr noetig —
  Decoder liefert fuer alle Modi)
- Tests 742/742 gruen — Decoder-Werte werden jetzt respektiert

### Commit 4 `c919b72` feat(qso_panel): add_rx/add_tx mit slot_start_ts/tx_even
- Beide Methoden bekommen optionale Parameter `tx_even`/`slot_start_ts`
- Wenn gesetzt: korrekter Slot-Tag + Zeitstempel des TX-Slots
- Fallback (Default `None`) bleibt rueckwaerts-kompatibel
- Tests 742/742 gruen

### Commit 5 `102e75f` feat(encoder): tx_started mit slot_start_ts/tx_even
- `tx_started`-Signal: `Signal(str, bool, float)` (war `Signal(str)`)
- Encoder berechnet pre-emit `slot_start_ts` aus TX-Trigger-Zeit
- 2 Listener migriert: `mw_radio.py:65` Lambda, `mw_qso.py:_on_tx_started`
- `mw_qso.py:59` reicht Werte zu `add_tx` durch
- Tests 742/742 gruen
- ⚠️ Vor Commit: `grep -rn "tx_started\.connect" --include="*.py"` durchgefuehrt
  (R1-Empfehlung, alle Listener gefunden)

### Commit 6 `88b6648` refactor(mw_cycle): add_rx mit Decoder-Slot-Feldern
- `ui/mw_cycle.py:on_message_decoded` reicht `msg._tx_even` und
  `msg._slot_start_ts` an `qso_panel.add_rx` durch
- `getattr`-Fallback (None) fuer Tests/Mocks ohne Decoder-Felder

### Commit 7 `5d4b767` test(slot): 14 neue Tests
- `tests/test_slot_display.py` (7 Tests): add_rx/add_tx + _assign_slot_parity
- `tests/test_decoder_slot_source.py` (4 Tests): target_slot_start
  Drift-Robustheit + Mode-Konsistenz + Message-Attribute + FT2
- `tests/test_encoder_slot.py` (2 Tests, R1-Empfehlung): Signal-Signatur
  + Listener-Args
- `tests/test_auto_hunt_extended.py` (1 Test): Decoder-gesetzter
  `_tx_even` korrekt durchgeschleift
- Tests **742 → 756 (+14, V3-Plan rechnete +11)** — 3 Bonus-Tests fuer
  edge-cases (`add_rx_explicit_even_overrides_wallclock`, `_assign_slot_parity_partial_fields`,
  `tx_started_listener_gets_all_three_args`)

**R1-Validierung:** Keine Halluzinationen festgestellt.
- `not _candidate.tx_even` Logik an mw_cycle.py:512 verifiziert
- `tx_started.connect`-grep: 2 Listener gefunden (mw_radio.py:65 + 68),
  beide migriert
- `mw_qso.py:128` `is_even_cycle()` ist NICHT betroffen (User-Klick-Pfad)

**Stats-Risiko (R1-bewertet):** `core/station_stats.py:113-117` nutzt
`time.gmtime()` zur Aufrufzeit fuer Stunden-Datei. Maximaler Bias < 0.1 %
(symmetrisch verteilt), kein Pooled-Mean-Effekt. **NICHT Teil dieses Fixes**
— separates TODO falls je relevant. Historische Daten bleiben unkorrigiert.

**Bekannter Float-Issue (vorbestehend):** `int(slot_start_ts / 3.8) % 2`
fuer FT2 ist Float-bedingt nicht stabil bei aufeinanderfolgenden Slots.
Selber Issue im alten `_slot_from_utc`-Code, durch diesen Fix nicht
verursacht. Mike funkt praktisch FT8, daher unkritisch.

**Erwartung Field-Test:**
- RX-Eintraege im QSO-Panel zeigen ODD-Tag (statt faelschlich EVEN) fuer
  Nachrichten der Gegenstation
- RX-Zeitstempel = Slot-Start des TX-Slots (z.B. `03:38:15 [O]` statt
  `03:38:30 [E]`)
- TX-Anzeige unveraendert
- Auto-Hunt funktioniert weiter (R1: Fix korrigiert, bricht nicht)
- „Doppelte Antworten"-Optik geht weg — eine FT8-Wiederholung der
  Gegenstation und Mike's TX im naechsten Slot sind dann visuell sauber
  getrennt

**Lessons:**
1. **Pre-sleep-Berechnung kritisch:** `time.time()` post-sleep ist drift-
   anfaellig (Sleep-Jitter, OS-Scheduler). Slot-Start vor sleep berechnen,
   nach sleep nur noch verwenden.
2. **Decoder als single source of truth:** Wake-Zeit ist die einzige
   Stelle wo „welcher Slot gehoert das Audio" verlustfrei bekannt ist.
   Alle Konsumenten ueber Message-Attribute versorgen statt eigene
   Wallclock-Berechnungen.
3. **R1 + Code-Validierung Pflicht:** R1's Auto-Hunt-Analyse liess sich
   per `grep` verifizieren (`not _candidate.tx_even` an mw_cycle.py:512).
   Eine `is_even_cycle()`-Stelle gefunden die R1 nicht erwaehnte —
   nicht latenz-betroffen, aber wichtig zu pruefen.

---

## 2026-05-05 v0.94 — KALIBRIEREN-Pipeline + Stats-Bug Phase 2

**Ausloeser:** Mike's Field-Test 2026-05-05 nach v0.93-Release. Im
Diversity-Modus zeigte das RX-Panel waehrend laufender Phase-2-Gain-
Messung "A1" fuer eine Station, die im DXTuneDialog im Bucket
"ANT2 Gain 20 dB" (-22 dB, CU2JX) gespeichert wurde. Mike's Doppel-
Frage: Stimmen die Statistiken trotzdem? + Sollte der KALIBRIEREN-
Button auch die Diversity-Antennen-Messung starten?

**Voller Workflow durchgezogen:**
- V1 (`prompts/kalibrieren_v0.94_v1.md`) — 4 Akzeptanzkriterien
- R1 (`prompts/kalibrieren_v0.94_r1.md`, deepseek-reasoner) — alle
  4 Punkte mit Ja bestaetigt, 0-Stations-Logging-Sorge entwarnt
  (filter NICHT auf 0, Pre-Conditions sind symmetrisch fair)
- V3 (`prompts/kalibrieren_v0.94_v3.md`) — Self-Review 5 Findings,
  Atomar-Plan 4 Commits

**3 atomare Commits + Doku-Sync:**

### Commit 1: `2c1c58d` Stats-Pause Phase 2 Bug-Fix
- `ui/mw_cycle.py:633-648` `_is_antenna_tuning_active` erweitert um
  `if getattr(self, '_dx_tune_dialog', None) is not None: return True`
- Frueher tot: `_rx_mode == "dx_tuning"` wurde nirgends gesetzt
  (nur Kommentar in `main_window.py:204`)
- Folge Pre-v0.94: ~0.3 % der Stats-Daten waren mit Diversity-Pattern-
  Antenne markiert statt Hardware-Antenne. Pooled-Mean-Auswertung
  bleibt valide (Bias zu klein), aber technisch falsch.
- Tests +4 in `test_phase2_stats_pause.py` NEU

### Commit 2: `7ca791e` RX-Panel zeigt Hardware-Antenne in Phase 2
- `ui/mw_cycle.py` NEU `_resolve_hardware_antenna(default_ant) -> str`:
  bei aktivem `_dx_tune_dialog` lese ant_long aus `_schedule[_step]`,
  konvertiere "ANT1"/"ANT2" → "A1"/"A2" (kurze Form). Defensive
  try/except gegen IndexError/AttributeError/TypeError.
- `_on_cycle_decoded` ruft `_resolve_hardware_antenna(ant)` VOR den
  `_handle_diversity_*`-Aufrufen → ant ist immer korrekt
- Tests +5 in `test_phase2_antenna_display.py` NEU

### Commit 3: `2658ee1` KALIBRIEREN RX-Modus-spezifisch (Mike's UX)
- `ui/mw_radio.py:1079` `_handle_dx_tuning` erweitert:
  * Wenn `_rx_mode == "diversity"` → `_pending_dx_diversity = True` +
    `_pending_diversity_scoring = scoring` → nach Phase 2 laeuft
    Phase 3 automatisch durch (nutzt bestehenden Pipeline-Mechanismus
    aus `_activate_diversity_with_scoring`)
  * Sonst (Normal): nur Phase 2 (Status quo)
- `_on_dx_tune_rejected` resetet Pending-Flags bei Cancel — sonst
  startet Phase 3 beim naechsten Diversity-Aktivieren ungewollt
- Tests +4 in `test_kalibrieren_pipeline.py` NEU

**Tests:** 729 → 742 gruen (+13).

**0-Stations-Logging Klarstellung (R1-bestaetigt):**
- `core/station_stats.py:96` `log_cycle` filtert NICHT auf
  `station_count == 0` → schreibt auch leere Slots
- `_log_stats` Pre-Conditions (Warmup, Tuning, CQ, QSO) sind
  symmetrisch fair: Normal und Diversity werden gleich behandelt
- Bei schlechten Bedingungen (Normal=0, Diversity=3) werden BEIDE
  Slots geloggt → Pooled-Mean bleibt fair. Mike's Sorge unbegruendet.

**Was BLEIBT unveraendert:**
- v0.92 Pipeline-Lock (Bandwechsel/Mode/RX-Mode-Race)
- v0.93 Score-basierte Messung + Cache-Reuse + 1h-Frist
- v0.91 Adaptiv-Stops Phase 2/3
- v0.90 Pattern fair 3:3

**Lessons:**
1. **R1-Antwort prueft Premise:** Mike's "0-Stations werden nicht
   geloggt"-Sorge wurde durch Code-Verifikation entkraeftet, BEVOR ein
   Fix implementiert wurde. Sparte 1-2 h vergebliche Refactor-Zeit.
2. **Tote Code-Pfade aus alten Plänen:** `_rx_mode = "dx_tuning"` als
   Konzept war nur in Kommentaren — in der Implementierung nie
   umgesetzt. Lesson: bei Pre-Cond-Checks immer `grep` ob die
   Pre-Cond auch wirklich gesetzt wird.
3. **Wiederverwendung bestehender Pipeline-Flags spart Code:**
   `_pending_dx_diversity` existierte bereits fuer
   `_activate_diversity_with_scoring`-Pfad — Mike's KALIBRIEREN-
   Erweiterung brauchte nur 5 Zeilen statt einer neuen Pipeline.

---

## 2026-05-04 v0.93 — Cache-Reuse + Mess-Refactor (Score-basiert + 1h-Frist)

**Hintergrund:** Mike wollte den Diversity-Mess-Mechanismus pragmatisch
umbauen. Ziel: zeit-basierter Re-Measure (1 h, atmosphaerisch korrekt),
Cache-Reuse pro Band+Modus mit 5-s-Toast statt Standard-Dialog, Score-
basierte Statistik (Killer fuer FT2 mit duenner Decoder-Dichte).

**Voller Workflow durchgezogen:**
- V1 (`prompts/cache_reuse_refactor_v1.md`) — Mike-Vision konkret formuliert
- V2 (`prompts/cache_reuse_refactor_v2.md`) — Self-Review, 7 Findings
  (`_MULT` fuer MEASURE_CYCLES, CQ-Lock, Timestamp-Konflikt, App-Start-Cache,
  Bandpilot-UX, `_was_early_stopped`, Tests-Migration)
- R1 (`prompts/cache_reuse_refactor_r1.md`, deepseek-reasoner) — 4 Mods
  bestaetigt (MEASURE_CYCLES bleibt, 2 Timestamps, CQ-Lock, KISS-Verbesserung)
- Dichte-V1+R1 (`prompts/cache_reuse_dichte_*.md`) — Score-Insight
  (KILLER fuer FT2): `score = sum(snr+30)` statt `station_count` ist
  1-Zeilen-Aenderung, loest Mike's Sorge ueber duenne Stations-Dichte
- V3 (`prompts/cache_reuse_refactor_v3.md`) — Synthese aller Findings
- V3-R1-Final-Review (`cache_reuse_refactor_v3_r1_review.md`) — Plan
  freigegeben, kein V4 noetig. Optionaler Hinweis zu defensive None-Pruefung
  in `should_remeasure` integriert.

**6 atomare Commits:**

### Commit 1: `d8d947f` PresetStore zwei Timestamps + Migration
- `core/preset_store.py`:
  - `GAIN_VALIDITY_SECONDS = 6h` + neu `RATIO_VALIDITY_SECONDS = 1h`
  - `is_valid_gain()`, `is_valid_ratio()`, `get_*_age_minutes()`
  - `save_gain()` setzt `gain_timestamp`; `save_ratio()` setzt
    `ratio_timestamp` (vorher: kein Timestamp-Update — V2 Finding 3!)
  - `_load()` Migration: alter `timestamp` → beide Felder gespiegelt,
    idempotent
  - Alte `is_valid()`/`get_age_minutes()` als Aliase auf gain-Variante
- Tests +18 in `test_preset_store.py` NEU

### Commit 2: `305d775` Score statt station_count + MIN_STATIONS weg
- `core/diversity.py`:
  - Mod 4 (KILLER): `record_measurement` speichert `score` (sum(snr+30))
    statt diskreter `station_count`/`dx_weak_count` — kontinuierliche
    Werte, Median liefert auch bei FT2-1-2-Stationen-Slot Aufloesung
  - Mod 5: `MIN_MEASURE_STATIONS = 5` ENTFERNT, `can_measure()` immer True
  - `MIN_PEAK_SCORE = 5.0` ersetzt 1.0-Schwelle in `_evaluate` +
    `_check_phase3_early_stop` (SNR-Skala statt Stueckzahl)
- Tests +9 in `test_diversity_density.py` NEU
  (FT2-Density, peak<=5 → 50:50-Fallback, Adaptiv-Stop mit Score)
- Tests angepasst: 7 in `test_patterns.py` (score=N*15 statt
  station_count=N), 3 in `test_modules.py`, 1 in `test_diversity_bandwechsel.py`

### Commit 3: `fd416ca` zeit-basiertes should_remeasure + CQ-Lock
- `core/diversity.py`:
  - `REMEASURE_INTERVAL_SECONDS = 3600`
  - `_last_measured_at` Property (gesetzt in `_evaluate`, geloescht in
    `reset()`)
  - `should_remeasure(qso_active, cq_active=False)`:
    * Phase=operate Pre-Cond
    * QSO oder CQ aktiv → False (Mod 3)
    * `_last_measured_at` None → True (R1 defensive Hinweis)
    * Sonst zeit-basiert (>=3600 s)
- `ui/mw_cycle.py`: `qso_active` sauber von `cq_active` getrennt
- Tests +13 in `test_should_remeasure.py` NEU

### Commit 4: `f8af3e8` Cache-Reuse + 5-s-Toast bei Bandwechsel (Hauptfeature)
- `ui/diversity_cache_toast.py` NEU (5s self-close, analog Bandpilot-Toast)
- `ui/mw_radio.py`:
  - `_try_diversity_cache_reuse(band, ft_mode, scoring) -> bool` —
    Pre-Cond ratio_valid AND gain_valid, lädt entry["ratio"]+"dominant",
    ruft `_enable_diversity` mit cache-Args, zeigt Toast
  - `_enable_diversity` erweitert um `cached_ratio`/`cached_dominant`/
    `cached_age_seconds` (kw-only): wenn gesetzt → Phase=operate,
    KEIN Lock (kein Phase 3)
  - `_check_diversity_preset` + `_activate_diversity_with_scoring` rufen
    `_try_diversity_cache_reuse` VOR Standard-Dialog
- Tests +9 in `test_diversity_cache_reuse.py` NEU
  (Whitebox via MagicMock-self, Toast-Smoke)

### Commit 5: `196a999` OPERATE_CYCLES + Settings-Option entfernen
- `core/diversity.py` `OPERATE_CYCLES = 60` Konstante entfernt
- `core/diversity.py` `seconds_until_remeasure` property NEU (zeit-basiert)
- `ui/mw_radio.py` Z.821-824: `_MULT` fuer OPERATE_CYCLES entfernt,
  MEASURE_CYCLES-Skalierung bleibt (R1 Mod 1)
- `ui/main_window.py`: OPERATE_CYCLES-Update aus Settings-Pfad raus,
  `_block_cycles` als fester OMNI-TX-Default 80
- `ui/mw_cycle.py`: `update_diversity_ratio` mit `operate_seconds_remaining`
  statt `operate_cycles/operate_total`
- `ui/control_panel.py`: UI zeigt jetzt "Diversity Neuberechnung in X Min."
  mit Farb-Schwellen <=2/<=10/sonst
- `ui/settings_dialog.py`: "Neueinmessung nach: <Zyklen>"-UI komplett raus
- `core/omni_tx.py`: Kommentar praezisiert (eigene OMNI-TX-Konstante)
- Tests angepasst: `test_operate_cycles_multiplier` → `test_measure_cycles_multiplier`,
  `diversity_operate_cycles` aus `test_settings_dialog_smoke.py` raus

### Commit 6: Doku-Sync + Tests-Migration
- HISTORY.md (dieser Eintrag)
- HANDOFF.md beide Pfade
- CLAUDE.md beide Pfade — Aktueller Stand v0.93
- Memory `project_diversity_cache_reuse.md` als ERLEDIGT
- MEMORY.md Index-Update
- main.py APP_VERSION 0.92 → 0.93
- `test_load_preset_removed_from_diversity_controller` umgeschrieben:
  v0.74 entfernte GLOBALEN Cache-Pfad — band-spezifischer Cache-Reuse
  seit v0.93 erlaubt (V2 Finding 7 adressiert)

**Tests:** 681 → 729 gruen (+48: PresetStore +18, Density +9,
should_remeasure +13, Cache-Reuse +9, sonstige Anpassungen netto -1).

**Was BLEIBT unveraendert:**
- Phase 2 Gain-Messung (separate 6 h Validity)
- Phase 3 fair 3:3 Pattern (v0.90)
- v0.91 Adaptiv-Stops + Cache-Schutz `_was_early_stopped`
- v0.92 Pipeline-Lock (Bandwechsel-Race-Fix)
- Manueller „NEU"-Button fuer Re-Measure
- Auto-Hunt, OMNI-TX, Bandpilot-Logik

**Lessons:**
1. **Score-Insight war R1's wichtigster Fund.** Mike's Hinweis „weniger
   Stationen bei FT4/FT2" fuehrte zu separater Dichte-R1-Diskussion, die
   den 1-Zeilen-Fix (`score` statt `station_count`) entdeckte.
2. **Cache-Reuse-Reihenfolge:** Ratio-Cache VOR Gain-Dialog, beide Pfade
   (`_check_diversity_preset` + `_activate_diversity_with_scoring`).
3. **API-Aliase fuer Migration** — `is_valid()` als Alias fuer
   `is_valid_gain()` verhindert Breakage in 4 mw_radio.py-Aufrufstellen
   waehrend Commit 1.
4. **R1's defensive None-Hinweis war wertvoll** — `if _last_measured_at
   is None: return True` schuetzt vor App-Start-Edge-Case.

---

## 2026-05-04 v0.92 — Pipeline-Lock bulletproof (Bandwechsel-Race-Fix)

**Hintergrund:** R1 hatte in v0.90 einen Bandwechsel-Race-Verdacht in
`mw_radio.py` geaeussert: laufender Slot konnte nach `on_band_change()`
reset noch Decode-Daten liefern → `record_measurement` mit altem
Antennen-State auf neuem Band → Mess-Daten-Leck zwischen Baendern.

**Mike's KISS-Argument:** „Waehrend Messung lauft, soll ALLES geblockt
sein ausser Cancel." Wenn Lock dicht ist → Token-Pattern unnoetig.

**Voller Workflow durchgezogen:**
- V1 (`prompts/lock_audit_v1.md`) — Code-Verifikation + Befunde
- V2 (`prompts/lock_audit_v2.md`) — Self-Review, 6 Findings vs V1,
  konkreter Race-Pfad dokumentiert
- R1 (`prompts/lock_audit_r1.md`, deepseek-reasoner) — bestaetigt Mike's
  KISS-Variante. **NEU R1-Finding:** `_on_rx_mode_changed` braucht auch
  Lock-Check (V1+V2 hatten den vergessen). R1's btn_rx-Vorschlag
  verworfen (Code-Verifikation: kein btn_rx im control_panel).
- V3 (`prompts/lock_audit_v3.md`) — alle R1-Findings adressiert,
  Implementierungsplan mit 5 Fixes + 7 Tests.

**Atomarer Commit `9b9303d` — 5 Edits in `ui/mw_radio.py`:**

1. `_set_gain_measure_lock(self, locked)` (Z.1080) — setzt
   `self._gain_measure_locked` Flag (einzige Quelle der Wahrheit fuer
   programmatischen Lock-Schutz).

2. `_on_band_changed(self, band)` (Z.265) — Frueh-Return wenn Flag aktiv:
   ```python
   if getattr(self, '_gain_measure_locked', False):
       current = self.settings.band
       print(f"[Bandwechsel ignoriert: Pipeline laeuft, bleibe auf {current}]")
       self.control_panel._set_band(current)  # UI-Sync zurueck
       return
   ```

3. `_on_mode_changed(self, mode)` (Z.199) — gleiches mit
   `self.settings.mode` und `self.control_panel._set_mode(current)`.

4. `_on_rx_mode_changed(self, mode)` (Z.371) — gleiches mit
   `self._rx_mode` und `self.control_panel.set_rx_mode(current)`
   (R1-Finding!).

5. `_enable_diversity` (Z.811-813) — Reset-Reihenfolge umgekehrt:
   Lock VOR `_diversity_ctrl.reset()` (statt umgekehrt). Schliesst
   Race-Window in dem laufende Slots ins frische `_measurements`-Bucket
   schreiben koennten.

**Tests +6 in `test_lock_coverage.py` NEU:**
- `test_lock_flag_set_when_locked`
- `test_lock_flag_cleared_when_unlocked`
- `test_band_change_blocked_during_lock`
- `test_mode_change_blocked_during_lock`
- `test_rx_mode_change_blocked_during_lock`
- `test_enable_diversity_locks_before_reset` (Reihenfolge-Verifikation
  via call-tracking auf gemeinsamem Manager-Mock)

**Tests:** 675 → 681 gruen (+6).

**R1-Halluzinationen verworfen:**
- „btn_rx absichern" — kein btn_rx im `control_panel.py`
- Bandpilot-Pending-Mechanismus (R1 als optional markiert) — KISS,
  Hobby-Use unnoetig

**Was BLEIBT unveraendert:**
- `_diversity_lock` (threading.Lock in `mw_cycle.py:184`) — schuetzt
  weiter die kritische Sektion in `record_measurement` vor parallelen
  Decoder-Threads
- Phase-Check `if self._phase != "measure"` — schuetzt Daten nach
  Pipeline-Ende (Phase=operate)

**Statistik:** Lock-Coverage-Audit war 1 zusaetzlicher R1-Pass, hat
einen 3. ungeschuetzten Handler (`_on_rx_mode_changed`) entdeckt der
in V1+V2 uebersehen worden war. Lesson: KISS-Loesungen brauchen
trotzdem R1-Audit fuer komplette Coverage.

---

## 2026-05-04 v0.91 — Block 2 Kalibrier-Pipeline-Optimierung (Adaptiv-Stops)

**Ziel:** Pipeline ~4:31 Min (v0.89/v0.90) → typisch ~3:20 Min (-26 %),
Best-Case ~2:30 Min (-45 %) bei eindeutigen Antennen-Verhaeltnissen.

**Voller Workflow durchgezogen:**
- V1 (`prompts/block2_v1.md`) — Probleme + Akzeptanzkriterien
- V2 (`prompts/block2_v2.md`) — Self-Review, 6 Findings vs V1 (Pre-Conditions
  klarer, FT4/FT2-Pattern-Edge-Case entdeckt, Property statt Konstante,
  Schwellen-Rationale begruendet, Test-Strategie konkret, Field- vs Unit-AC-Trennung)
- R1 (`prompts/block2_r1_review.md`, deepseek-reasoner) — 4 kritische +
  4 minor Findings: Cache-Schutz fuer Adaptiv-Stop-Ratios (R1.4 KRITISCH),
  Monitoring-Log mit Timestamp, FT4/FT2-Doku, Cancel-Flag dokumentieren
- V3 (`prompts/block2_v3.md`) — alle R1-Findings adressiert, Plan-Mode Go

**3 Optimierungen umgesetzt (3 atomare Commits):**

### Commit 1: `eef4369` — perf(dx_tune): ROUNDS 3→2 (#6, -60s)
- `ui/dx_tune_dialog.py:23` ROUNDS = 2 (statt 3)
- 5 Hint-Texte synchron: Docstring, Inline-Kommentar, UI-Hint × 2, step_label
- step_label nutzt ROUNDS-Konstante (statt hardcoded 3)
- Schedule = 8 Eintraege (2 Runden × 2 ANT × 2 Gain)
- Tests: 664 → 664 (keine Aenderung erwartet)

### Commit 2: `3068919` — perf(dx_tune): Adaptiv-Stop Phase 2 (#7, -30 bis -60s)
- `_check_phase2_early_stop()` nach Schritt 4 (Runde 1 Ende)
- Stop-Bedingung: Δ_SNR ≥ 4 dB ODER Δ_STAT ≥ 50 % (R1-bestaetigt konservativ)
- Pre-Conditions: alle 4 Buckets non-empty + non-overload + min 5 Stationen
- Monitoring-Log mit ISO-Timestamp fuer Schwellen-Tuning post-Feldtest
- Tests +6 (`test_dx_tune_adaptive_stop.py` NEU): 670 gruen

### Commit 3: `f090097` — perf(diversity): Adaptiv-Stop Phase 3 + Cache-Schutz (#8, -30s)
- `core/diversity.py`:
  - EARLY_STOP_FRACTION = 2/3, EARLY_STOP_THRESHOLD = 0.15
  - Property `_early_stop_at` (Modus-aware ueber MEASURE_CYCLES)
  - Flag `_was_early_stopped` (in reset() + start_measure())
  - `_check_phase3_early_stop()` — rel_diff>=15 % nach 4 Zyklen
  - record_measurement nur wenn `len(m1)==len(m2)` (FT4/FT2-Schutz)
- `ui/mw_cycle.py` (R1.4 Cache-Schutz):
  - save_ratio() wird bei `_was_early_stopped=True` UEBERSPRUNGEN
  - Adaptiv-Stop-Ratios sollen nicht 6h+ via PresetStore wiederverwendet werden
- FT4/FT2-Hinweis: Pattern-Periode 6 verhindert balancierte Verteilung bei
  MEASURE_CYCLES=12/24, Pre-Condition len-equal verhindert Stop —
  effektiv profitiert nur FT8 (R1-akzeptiert da Hobby-Use 99 % FT8)
- Tests +5 (`test_patterns.py` Erweiterung): 675 gruen

**Erwartete Pipeline:**
- Best-Case (alles greift): Tunen 3 s + Phase 2 1:00 + Phase 3 1:00 = ~2:30 Min
- Typisch: ~3:20 Min
- Worst-Case (keine Adaptiv-Stops): ~3:30 Min (= 30 s vs v0.90 dank #6 allein)

**Tests:** 664 → 675 gruen (+11: 6 fuer #7, 5 fuer #8).

**Statistik-Disclaimer:** Adaptiv-Stop-Ratios werden NICHT in PresetStore
gespeichert. Cache-Reuse-TODO (`project_diversity_cache_reuse.md`) bleibt
auf voll-gemessene Ratios beschraenkt.

**Offen:** Field-Test der Schwellen-Werte (4 dB, 50 %, 15 %). Bei zu seltenen
Triggers auf 12 % senken (R1-Empfehlung). Monitoring-Log liefert Daten.
🟡 Bandwechsel-Race in `mw_radio.py` weiter offen (separater Workflow).

---

## 2026-05-04 v0.90 — Mess-Pattern-Bug-Fix (KRITISCH, Phase-3-Bias seit v0.36 behoben)

**Bug seit Phase 3:** `core/diversity.py:86` nutzte das Pattern
`("A2","A1","A1","A2","A1","A1")` = **4× A1 + 2× A2** auf 6 Slots —
identisch mit OPERATE 70:30. ANT2 strukturell unter-gemessen → Median-
Vergleich verschoben → 8 %-Schwelle bevorzugte ANT1-Ratio.

**Erklaert teilweise** Mike's Beobachtung 4 % ANT2-Win-Rate auf 40 m FT8
(1 von 23 Stationen am 04.05.2026 13 UTC).

**Voller Workflow durchgezogen:**
- V1 (Plan-Datei `prompts/v090_mess_pattern_fix_plan.md`, 3 Optionen A/B/C)
- V2 (`prompts/v090_v2.md`, Self-Review, 6 zusaetzliche Findings inkl.
  Block-1-Doku-Bug Z.7+Z.403)
- R1 (DeepSeek-R1, 2 KRITISCH-Findings: 🔴 End-to-End-Test fehlt
  + 🔴 Bandwechsel-Race-Hinweis in HANDOFF behalten)
- V3 (`prompts/v090_v3.md`, final mit 6 ACs)

**Fix Option C (R1-Plan-Default):**
```python
return ("A1","A1","A2","A2","A1","A2")[self._measure_step % 6]
```

3:3 fair, beide Antennen mit zusammenhaengendem Even+Odd-Paar
(A1: Slots 0-1, A2: Slots 2-3), Singletons 4 (A1=even) + 5 (A2=odd).
6 Slots bleiben → MEASURE_CYCLES=6 unveraendert → Pipeline ~4:31 Min
unveraendert.

**3 atomare Commits:**
1. `473f164` Pattern-Fix + 5 neue Tests in `tests/test_patterns.py`
   (`test_measure_ratio_balanced`, `_seamless_loop`, `_closed_pairs_per_antenna`
   und 2 End-to-End-Tests fuer `_evaluate()` 50:50 + 70:30)
2. `2a3c535` Doku-Sync README.md (DE+EN) + `docs/explained/diversity-modes.md`
   (DE+EN) — alle „4 Zyklen / 8-cycle" Stellen auf 6-Zyklen-Pattern aktualisiert
3. `<pending>` APP_VERSION 0.89 → 0.90 + HISTORY/HANDOFF/CLAUDE/TODO/Memory

**R1-Findings einarbeitet:**
- 🔴 **End-to-End-Test (KRITISCH)** — `record_measurement` mit fairen/
  asymmetrischen Scores → Pruefung von `_evaluate()` Median+Ratio. Pattern-
  Test allein deckt das nicht ab; bei Aenderung an `_evaluate()` waere der
  Bug zurueckschleichen koennen.
- 🔴 **Bandwechsel-Race-Hinweis** in HANDOFF behalten (R1 hat den Verdacht
  zweimal angedeutet: laufender Slot wird nach `on_band_change` reset noch
  verarbeitet → record_measurement mit altem Antennen-State auf neuem Band
  moeglich). Separater Bug-Fix nach v0.90.
- 🟡 Code-Kommentar in `_evaluate()` mit Statistik-History
- 🟡 Geschlossene Even+Odd-Paare als eigener Test (`_closed_pairs_per_antenna`)

**Statistik-Disclaimer (PFLICHT-Lese fuer Auswertungen):**
- Alle Pre-v0.90 Diversity-Daten haben strukturellen Mess-Bias 4:2 statt 3:3.
- Pooled-Mean +88 %/+124 % bleibt valide weil ANT2 trotz Bias signifikant
  beitraegt — absolute ANT2-Win-Rate ist konservativ unterschaetzt.
- Field-Test-Erwartung: ANT2-Win-Rate auf 40 m steigt von ~4 % auf ~15-25 %
  bei aehnlich-guten Antennen.
- 50:50-Ratio wird haeufiger gewaehlt wenn echte Differenz < 8 %.

**Block-1-Doku-Bug mitfixt:**
- `core/diversity.py:7` Module-Docstring „Median ueber 4 Zyklen pro Antenne"
- `core/diversity.py:403` print „(4 Zyklen)"
- `README.md:61+581` (DE+EN) „median over 4 cycles" / „Median ueber 4 Zyklen"
- `docs/explained/diversity-modes.md` (DE+EN) „8-cycle measurement / 4 cycles"

**Tests:** 664 gruen (= 659 + 5 neue).

**Out-of-Scope (NICHT in v0.90):**
- 🟡 Bandwechsel-Race in `mw_radio.py` (separater Workflow nach v0.90)
- Block 2 (Adaptiv-Stops + ROUNDS=2): eigener V1→V3-Zyklus
- `core/diversity 2.py` (untracked Backup vom 30.04.2026): nicht angetastet

**Rollback bei Problemen:** `git checkout aec3706` (letzter Block-1-Commit).

---

## 2026-05-04 v0.89 — Kalibrier-Pipeline-Optimierung Block 1

**Pipeline 6:50 → ~4:31 Min (-2:19 Min, -34 %).** Vorbereitend fuer
Block 2 (mittel-Risk, Adaptiv-Stops) der typisch ~3:20 Min anvisiert.

**Voller Workflow durchgezogen:** V1 (Plan-Datei) → V2 (Self-Review,
2 zusaetzliche Stellen entdeckt) → R1 (DeepSeek-R1, 1 KRITISCH +
mehrere uebersehene Stellen) → V3 (final, 28 Code-Stellen +
2 Test-Anpassungen) → Mike-Freigabe → 5 atomare Commits.

**R1-KRITISCH:** `mw_radio.py:798` setzt `MEASURE_CYCLES = 8 * _MULT`
zur Laufzeit — ueberschreibt Konstante. Beide Stellen muessen synchron
geaendert werden, sonst ist AC4 wirkungslos. Ohne R1-Review uebersehen.

**5 atomare Commits:**
1. `ebddd3e` Skip-First-Cycle entfernen (-15 s)
2. `5662d76` TUNE 5s → 3s (-2 s × 2 Pfade)
3. `bea87f9` Gain-Stufen 3 → 2 — `[10, 20]` (-90 s, 18 → 12 Zyklen)
4. `3a4de56` Phase 3 MEASURE_CYCLES 8 → 6 (-30 s, 4×A1+4×A2 → 3×A1+3×A2)
5. `aec3706` Preset-Cache 2 h → 6 h (weniger Pipeline-Laeufe pro Tag)

**Tests:** 659 gruen (zwei Tests umbenannt + range-Anpassung:
`test_diversity_phase_transition_after_8_measurements` →
`_after_6_measurements`, analog `test_phase_diff_detects_measure_to_operate_transition`).

**Block 2 als naechstes (TODO.md DRINGEND-Eintrag):**
- #6 ROUNDS = 3 → 2 (-60 s)
- #7 Adaptiv-Stop Phase 2 nach Runde 1 (Δ > 4 dB / > 50 %)
- #8 Adaptiv-Stop Phase 3 nach 4 Zyklen (Δ > 15-20 %)
→ Pipeline typisch ~3:20 Min nach Block 2. Eigener V1→V3-Zyklus
nach Block-1-Feldtest.

**Rollback:** `git checkout v0.88.1` (Snapshot vor Block 1).

---

## 2026-05-04 v0.88.1 — Snapshot vor Kalibrier-Optimierung

GitHub-Release v0.88.1 + Tag + lokale Sicherung in
`Appsicherungen/2026-05-04_v0.88.1_vor_kalibrier_optimierung/`.

**Zweck:** Rollback-Anker fuer geplante Kalibrierungs-Pipeline-
Optimierungen (Pipeline 6:50 Min → typisch ~3:20 Min, 8 Schritte
in 2 Blöcken). Bei Bedarf: `git checkout v0.88.1`.

**Enthält ggu v0.88:** Tertile-Konfidenzband im Stationen-Diagramm
entfernt + Bandpilot Auto-Toast 3s → 5s. Tests 659 grün.

**Plan:** `prompts/kalibrier_optimierung_plan.md`
**Memory:** `project_kalibrier_optimierung.md`

---

## 2026-05-04 — Bandpilot Auto-Toast 3s → 5s

Mike-Feedback nach Live-Test 04.05.2026: 3 Sekunden zu kurz um die
drei Werte zu lesen.

`ui/bandpilot_dialogs.py`: `QTimer.singleShot(3000, self._safe_close)`
→ 5000. Plus: Slot-Lueckenliste Ziel-Erreicht 19 → 20.

App-Neustart erforderlich damit die neue Self-Close-Zeit greift.

---

## 2026-05-04 — Tertile-Konfidenzband im Stationen-Diagramm entfernt

**Mike's Feedback (04.05.2026):** "Korridor-Berechnung der einzelnen
Modi verwirrt durch ihre grosse Streuung."

`scripts/generate_plots.py`:
- `fill_between(xs, mins, maxs, alpha=0.15)` aus
  `create_stations_diagram` entfernt (Zeile 1024)
- p4-Subtitle (DE+EN): "schattiertes Band"-Beschreibung raus,
  ersetzt durch Hinweis auf gestrichelte Rescue-Linie
- p4-Annotation entsprechend angepasst
- Header-Modul-Doku bereinigt (Konfidenzband-Erwaehnung raus)

Tertile-Berechnung bleibt intern erhalten — die weissen Fehlerbalken
im Bar-Chart (S.5 PDF) sind nicht betroffen, nur das Linien-
Diagramm wurde entschlackt.

PDFs DE+EN regeneriert. Kein Code-Test betroffen (PNG-Output).

---

## 2026-05-04 v0.88 — Bandpilot Stunden-Refactor

**Konzept-Bruch ggu v0.87:** der globale Pooled-Mean + Aggregat
``(Diversity_Std + Diversity_DX) / 2`` ist statistisch nicht sauber
(R1-Urteil 2026-05-04: Std und DX sind keine IID-Population, Aggregat
erzeugt Bias). Ersatz durch **drei direkte Werte pro UTC-Stunde**
ohne Aggregation. Empfehlung via max-Pick mit Toleranz
``max(5%, 1 Station)`` gegen den AKTUELLEN Modus (R1-Finding A:
Toleranz nicht gegen Top-2, sondern gegen aktuellen Modus messen,
sonst Edge-Case wenn Top-1+Top-2 eng beieinander aber weit ueber
aktuell liegen).

**Workflow:** V1 (Mike-Konsens 04.05.) → V2 (Self-Review 25 neue AKs)
→ R1-Review (5 KRITISCH + 3 OPTIONAL Findings) → V3 (36 AKs konsolidiert)
→ Mike-Freigabe → 13 atomare Commits → Final-R1 (1 KRITISCH +
2 EMPFEHLUNGEN) → Fix-Commit.

**Settings v0.87 → v0.88 Migration (idempotent):**
- ``bandpilot_enabled = false`` → ``bandpilot_mode = "off"``
- ``bandpilot_enabled = true`` → ``bandpilot_mode = "auto"``
- ``bandpilot_diversity_pref`` wird verworfen
- Alter Cache ``~/.simpleft8/bandpilot_summary.json`` wird geloescht
- Plus ``Settings.save()`` jetzt atomar via ``os.replace`` (R1-Finding 1)

**Neue Dateien:**
- ``core/bandpilot_md.py`` — MD-Generator fuer
  ``auswertung/Bandpilot-<band>-FT8.md`` (24-Zeilen-Tabelle, Top-1)
- ``ui/bandpilot_dialogs.py`` — ``BandpilotAutoToast`` (3s self-close,
  parent-zentriert, Frameless+Tool, ``WA_DeleteOnClose``) +
  ``BandpilotManualDialog`` (3 Buttons, 1/2/3-Marker, Top-1 gruen,
  ●-Marker fuer aktuellen Modus)
- ``tests/test_bandpilot_md.py`` (14 Tests)
- ``tests/test_settings_migration.py`` (9 Tests, inkl. atomic-save)
- ``tests/test_mw_radio_bandpilot.py`` (19 Tests, Mock-basiert,
  inkl. R1-Final-Finding "TX-Schutz Band-Check")
- ``auswertung/Bandpilot-20m-FT8.md`` + ``Bandpilot-40m-FT8.md``
  (App-Start-generiert)
- ``prompts/bandpilot_stundenlogik_{v1,v2,v3}.md`` (Workflow-Doku)

**Refactored:**
- ``core/mode_recommender.py`` komplett neu (alte
  ``Bandpilot``/``BandpilotSummaryCache``/``aggregate_stats``/
  ``recommend(diversity_pref)`` geloescht; neu:
  ``aggregate_stats_by_hour``/``recommend_for_hour``/
  ``HourlyBandpilot``/``HourlyBandpilotCache`` mit atomarem Write
  und JSON-int-Key-Round-Trip)
- ``ui/mw_radio.py`` — ``_maybe_apply_bandpilot`` Stunden-Logik
  (off/auto/manual) + TX-Schutz mit Band-Konsistenz-Check
  (R1-Final) + Toast/Dialog-Trigger; Override-Set +
  ``_bandpilot_setting_mode``-Flag entfernt; ``_set_rx_mode_direct``
  vereinfacht
- ``ui/main_window.py`` — ``HourlyBandpilot``-Init + State-Variablen
  (``_bandpilot_pending``, ``_bandpilot_tx_connected``,
  ``_bandpilot_active_toast``/``_dialog``) +
  ``_init_bandpilot_recommendations`` fuer App-Start-MD-Generierung
- ``ui/settings_dialog.py`` — ``bandpilot_mode_combo``
  (Aus/Auto/Manuell) statt ``bandpilot_cb`` + ``bandpilot_pref_combo``
- ``config/settings.py`` — DEFAULTS auf ``bandpilot_mode="off"``
  reduziert + ``_migrate_bandpilot_settings_v088`` + atomic save
- ``scripts/generate_plots.py`` — Bandpilot-MD-Hook am Ende
- ``docs/explained/bandpilot_de.md`` + ``bandpilot.md`` komplett neu
- README.md (DE+EN): Bandpilot-Sektion + Migrations-Hinweis

**TX-Schutz (V3-AK 7):**
- Wenn ``encoder.is_transmitting``: Modus-Wechsel verzoegern bis
  ``tx_finished``-Signal
- Sofortiger Toast + Statusbar-Hinweis "wechselt nach TX-Ende"
- ``_on_bandpilot_tx_finished``: Band-Konsistenz-Check
  (R1-Final-Finding): wenn User waehrend TX das Band gewechselt
  hat → pending verwerfen, kein falscher Modus-Wechsel auf neuem
  Band

**Tests:** 616 → **659 grün** (+43: +31 mode_recommender,
+14 bandpilot_md, +9 settings_migration, +19 mw_radio_bandpilot
[inkl. R1-Final-Test], +1 settings_dialog smoke-Update). 13 atomare
Commits.

**APP_VERSION:** 0.87 → 0.88

---

## 2026-05-02 v0.87.1 — Doku-Konsolidierung + Help-Dialog-Erweiterung

**Betroffene Dateien:** `ui/help_dialog.py`, `ui/main_window.py`,
`ui/settings_dialog.py`, `tests/test_help_dialog_features.py` (neu),
`README.md`, `docs/explained/` (komplette Reorganisation), 5 neue
Doku-Features (DE+EN = 10 Files), `core/mode_recommender.py`-Pfad
in settings_dialog umgestellt.

**Was:** Komplette Doku-Konsolidierung. Vorher chaotisch verteilt
auf `docs/` (UPPER_SNAKE_CASE) + `docs/explained/` (kebab-case) +
neue `bandpilot_help_*` (mit `_help_`-Suffix). Jetzt einheitlich
`docs/explained/<feat>_de.md` + `<feat>.md` als Single Source of
Truth — App-Help-Dialog UND GitHub-README beziehen Inhalt aus
demselben Pool. 11-Phasen-Workflow streng nach `ft8_workflow`
durchgezogen mit V1→V2→R1→V3→Plan→11 atomare Commits→Final-R1.

### Migrations + Cleanups

- `docs/bandpilot_help_<de|en>.md` → `docs/explained/bandpilot_<de>.md`
  + `bandpilot.md` (neue Naming-Norm).
- `docs/POWER_REGULATION_<DE|EN>.md` → `docs/explained/power-regulation_<de>.md`
  + `.md`.
- `docs/FREQUENCY_HISTOGRAM_<DE|EN>.md` →
  `docs/explained/cq-frequency_<de>.md` + `.md` (semantisch
  klarerer Name).
- `docs/DX_TUNING_<DE|EN>.md` → `docs/explained/dx-tuning_<de>.md`
  + `.md` mit Abgrenzungs-Hinweis zu gain-measurement
  (gain-measurement = Audio-Pegel-Kalibrierung; dx-tuning =
  4.5-Min-18-Zyklus-Antennenmessung).
- `docs/DIVERSITY_<DE|EN>.md` + `DT_CORRECTION_<DE|EN>.md`
  geloescht — einzigartige Inhalte vorher in die explained/-
  Pendants gemergt:
  + diversity-modes_<de|en>: A1/A2-Markierungen-Sektion
  + dt-correction_<de|en>: zweistufige Architektur, DT_BUFFER_OFFSET-
    Tabelle, JSON-Persistenz, TX-TARGET_TX_OFFSET, Status
    "UNGETESTET" → "Validiert".
- `docs/explained/diversity-modes.md` (EN) auf DE-Stand (159 →
  163 Zeilen, +Antenna-Pref, +Three-Modes-Overview, +Bird-Beispiel).
- `docs/explained/omni-tx_<de|en>.md`: Aktivierungs-Methode
  (Klick auf Versionsnummer) entfernt — PRIVAT, durfte nicht auf
  GitHub.

### 5 neue User-Feature-Doku-Files (DE+EN, je ~80-180 Zeilen)

| Slug | Display |
|---|---|
| `antenna-preference` | Antennen-Praeferenz pro Station |
| `waitlist` | Anrufer-Warteliste |
| `direction-map` | Richtungs-Karte (3D-Globus) |
| `locator-mining` | Live Locator-DB |
| `auto-hunt` | Auto-Hunt |

### App-Code

- `ui/help_dialog.py:_FEATURES` von 11 auf **20 Features** erweitert,
  alphabetisch sortiert (case-insensitive), mit aktualisierten
  Display-Namen ("Gain-Messung (Audio-Pegel)" statt "Gain-Messung
  (DX Tuning)" — Verwechslung mit dx-tuning vermeiden).
- `ui/main_window.py:_help_btn.setToolTip("Funktionsuebersicht —
  Feature Overview")`.
- `ui/settings_dialog.py:_show_bandpilot_help` Pfad auf
  `docs/explained/bandpilot_<de|en>.md`.

### README

- Tests-Badge 563 → 616.
- Versions-Erwaehnungen v0.86 → v0.87.
- Bandpilot in "Key Innovations" + "All Features" + "In Field Test"
  + "Detailed Feature Documentation"-Tabelle (vollstaendig auf alle
  20 Features erweitert, vorher nur 5 verlinkt).
- Beide Sprachen-Sektionen (English + Deutsch) synchron.
- README_DE.md unveraendert (nicht aktiv genutzt — nicht aus
  README.md verlinkt, GitHub-Default ist README.md).

### Tests

- `tests/test_help_dialog_features.py` (neu) — 23 Tests:
  parametrisierte File-Existenz pro Feature (20),
  alphabetische Sortierung, Mindest-Anzahl, Slug-Eindeutigkeit.
- 593 → **616 grün**, 0 Regressionen.

### Workflow-Bilanz

V1 → V2 (Self-Review fand 17 Lücken) → R1 (13 Findings, 5
verifiziert + 8 angenommen) → V3 → 11 atomare Commits → Final-R1
(1 valid Finding: interner Code-Verweis aus User-Doku raus, 4
Halluzinationen abgelehnt).

### Lessons

- **R1 sieht nur die mitgesendeten Files.** Wenn man nur 6 von 40
  schickt, halluziniert R1 dass die anderen 34 fehlen. Beim Final-
  Review reichlich Files mitgeben oder explizit "die anderen
  existieren bereits" schreiben.
- **Single-Source-Migration vor Inhalts-Edits:** zuerst alle Files
  an die richtige Stelle, DANN editieren. Verlinkungen brechen
  sonst halb. Phase 2 (Migration) vor Phase 3 (EN-Update) vor
  Phase 4 (Lösch-Op).
- **Naming-Konvention strikt durchhalten:** bei Bandpilot war
  "_help_<de|en>.md" der falsche Suffix — das ist 1 Ausreißer
  reicht um Inkonsistenz zu erzeugen, also kompromisslos
  vereinheitlichen.

---

## 2026-05-01 v0.87 — Bandpilot (RX-Modus-Empfehlung pro Band)

**Betroffene Dateien:** `core/mode_recommender.py` (neu),
`tests/test_mode_recommender.py` (neu, 28 Tests),
`tests/test_settings_dialog_smoke.py` (+2 Tests),
`ui/main_window.py`, `ui/mw_radio.py`, `ui/settings_dialog.py`,
`config/settings.py`, `docs/bandpilot_help_de.md` (neu),
`docs/bandpilot_help_en.md` (neu), `main.py`.

**Was:** Bei jedem Bandwechsel waehlt der „Bandpilot" automatisch den
RX-Modus (Normal / Diversity Standard / Diversity DX) der auf diesem
Band die hoechste Pooled-Mean-Stations-Anzahl pro 15s-Slot in der
Statistik liefert. Mike-Idee: nicht jedes Band bei jedem Anstecken
manuell durchklicken — die App weiss aus den eigenen Messdaten was an
Mike's Antennenkombination (ANT1 Kelemen DP-201510 + ANT2 Regenrinne)
am besten funktioniert. Hobby-Funker-Komfort: anstecken → Band waehlen
→ ideale Konfig ist da.

**Workflow voll durchlaufen:** V1 → V2 (Self-Review) → R1 (DeepSeek-
Reasoner) → V3 → Plan (Task-Liste) → Code. Mike hat „vollstes Vertrauen
… autonom implementieren" gegeben nach finalem V3 mit Kandidat-A-
Aggregation.

### Aggregations-Methodik (Kandidat A — Mike-Entscheidung)

```
diversity_aggregate = (Diversity_Normal_Mean + Diversity_DX_Mean) / 2
recommendation     = Normal vs diversity_aggregate
```

Hintergrund: alle drei Stats-Pfade (Normal / Diversity_Normal /
Diversity_Dx) loggen dieselbe Metrik — Anzahl dekodierter Stationen
pro 15s-Slot. Damit halbiert sich die Mindest-Messzeit fuer
„Diversity": ein Tag Diversity_Normal + ein Tag Diversity_Dx ergibt
zwei Datentage fuer das Aggregat. Anfangs hatte ich faelschlich
behauptet Diversity_Dx zaehle nur SNR<-10 — Mike hat den Code-Check
verlangt und meinen Irrtum aufgedeckt (CLAUDE.md-Notiz war
ambivalent, Code zeigt: alle drei zaehlen gleich).

### Bedingungen + Algorithmus

- **MIN_DAYS = 2** pro Modus, **MIN_CYCLES = 50** pro Modus.
- Wenn ein Modus diese Schwellen nicht erreicht → **kein Auto-Switch**
  (Mike behaelt seinen Modus).
- Wenn `Normal_Mean >= diversity_aggregate` → Empfehlung = `normal`.
- Sonst Empfehlung = `diversity_normal` oder `diversity_dx`, je nach
  `bandpilot_diversity_pref`-Setting:
  - `auto` (Default): der Diversity-Modus mit dem hoeheren Mean
  - `standard`: immer Diversity_Normal
  - `dx`: immer Diversity_Dx

Live-Smoke-Test mit Mike's Daten: 40m → diversity_normal (42.4 vs 19.2),
20m → normal (Datenbasis 20m ist noch duenn → faellt zurueck auf Normal).

### Override pro Band

User-Klick auf btn_normal/btn_diversity bei aktivem Bandpilot setzt
`_bandpilot_overridden_bands.add(current_band)`. Beim naechsten
Bandwechsel ZU diesem Band greift der Override (kein Auto-Switch) und
wird zugleich geloescht. Beispiel: 40m → manuell Normal → 20m →
zurueck zu 40m: Bandpilot respektiert Override genau einmal, danach
wieder normal.

### Cache

`~/.simpleft8/bandpilot_summary.json`, TTL 24h pro Band. Aggregation
pro Band (~50ms bei 10 Tagen) wird gecached, naechster Aufruf nach 24h
re-aggregiert automatisch. Atomarer Write (`.tmp` + `os.replace`)
gegen Crashs waehrend Persistenz.

### Refactor in mw_radio.py

`_on_rx_mode_changed` hatte den Diversity-Aktivierungs-Block (60+ Zeilen)
inline. Den habe ich in `_activate_diversity_with_scoring(scoring)`
extrahiert — wird jetzt sowohl vom User-Dialog (Standard/DX-Wahl) als
auch vom Bandpilot ueber `_set_rx_mode_direct(target)` aufgerufen.
Kein Code-Duplikat. `_bandpilot_setting_mode`-Flag mit try-finally
verhindert dass programmatischer Switch einen User-Override speichert.

### UI

Settings-Dialog Tab „FT8 & Diversity":

- Neue Checkbox **„Bandpilot — RX-Modus automatisch waehlen"**
- ComboBox **„Wenn Diversity besser:"** mit Auto / Standard / DX
- ?-Button rechts oeffnet QMessageBox mit
  `docs/bandpilot_help_<de|en>.md` (sprachabh. via settings.language)

Toast-Feedback ueber `statusBar().showMessage(..., 3000)`:
`Bandpilot: Diversity Standard fuer 40m`.

### Tests

- `tests/test_mode_recommender.py` — 28 neue Tests (parse, aggregate,
  recommend, cache, end-to-end).
- `tests/test_settings_dialog_smoke.py` — 2 neue Tests (Bandpilot-
  Widgets vorhanden, Save-Round-Trip).
- Existing-Tests vom mw_radio-Refactor: alle 591 grün, kein
  Breakage durch die `_activate_diversity_with_scoring`-Extraktion.

### Defaults

`config/settings.py`:
- `bandpilot_enabled = False` (User-Opt-In, nicht aufgezwungen)
- `bandpilot_diversity_pref = "auto"`

### Tests-Bilanz

563 → **593 grün** (+28 mode_recommender, +2 settings_dialog,
0 Regressionen).

### Lessons

- **Code-Verifikation vor Premise.** Meine Annahme „Diversity_Dx
  zaehlt nur SNR<-10" war falsch — Mike hat das aufgeklaert und das
  korrekte Kandidat-A-Aggregat eingefordert. CLAUDE.md-Notizen sind
  Hilfsmaterial, der Code ist die Referenz. Memory-Eintrag wird gleich
  gepflegt.
- **Helper-Extraktion statt Flags.** Ich hatte zuerst ueberlegt
  `_bandpilot_setting_mode`-Flag im `_on_rx_mode_changed` direkt zu
  branchen. Sauberer war: den Diversity-Aktivierungs-Block in eine
  eigene Methode rauszuziehen und beide Pfade (Dialog + Direct) sie
  rufen zu lassen. KISS schlaegt Verzweigungslogik.

---

## 2026-04-30 v0.80 — TX-DT-Drift QSO-Retry-Fix (BLOCKER)

**Betroffene Dateien:** `core/encoder.py`, `core/qso_state.py`, `ui/mw_qso.py`,
`tests/test_modules.py`, `main.py`, `prompts/tx_dt_drift_v{1,2,3}.md` (neu).

**Was:** Real-Funkbetrieb war seit v0.74 unmöglich — schwache Stationen
konnten Mike's Folge-Reports nicht decodieren. 7 echte QSOs hintereinander
mit Timeout, nur lokaler Icom-Test funktionierte. Diagnose erst möglich
nach Mike's Auto-Sequence-Check (v0.79-Lesson eliminierte falsche Spur).

### Symptom (Icom-Verifikation)

| TX-Typ | DT |
|---|---|
| Folge-CQs (CQ_WAIT-Loop) | 0.0–0.1s ✓ |
| Erster Report nach RX-Antwort | 0.1s ✓ |
| **Folge-Report (WAIT_REPORT-Retry)** | **0.6–0.8s ✗** |
| **Erster CQ nach QSO-End** | **0.6–0.8s ✗** |

Auto-Sequence-Decoder verwerfen Frames > 0.5s DT.

### Wurzel-Ursache (Code-Pfad-Analyse)

`on_cycle_end` Z.501 in `_on_cycle_start` triggerte `WAIT_REPORT`-Retry bei
`timeout_cycles == 2` AM Anfang von Mike's eigenem TX-Slot (N+2). Encoder
hatte 0s Vorlauf, „Slot-Rand: sofort senden"-Pfad sendete mit overshoot
0.95s → DT 0.95s am Empfänger.

Folge-CQ war sauber, weil dort Trigger bei `timeout_cycles == 1` im RX-Slot
der Gegenstation (N+1) feuert → Encoder schedulet zu N+2 mit 14s Vorlauf.

### Workflow (V1 → V2 → R1 → V3 → Implementation → Final-R1 → Release)

V1 (initial) → Self-Review fand 8 Lücken → V2. R1-Review der V2 (deepseek-
reasoner, 5 echte Findings + 2 Overengineering + 1 Halluzination) entdeckte
**KRITISCHEN Bug:** `time.sleep()` ist nicht unterbrechbar, Fix A2 in V2
war unwirksam → V3 mit `threading.Event.wait()`. Final-R1-Review nach
Implementation entdeckte **Race-Condition** in `transmit()`/`abort()`-
Sequenz → 7. Commit als Race-Fix.

### Fixes (7 atomare Commits)

**Fix A1** (`9101573`): `qso_state.py:297, 313` — Retry triggert bei
`timeout_cycles == 1` statt `== 2`. Trigger feuert im RX-Slot, Encoder
hat 14s Vorlauf. Retry-TX-Timing bleibt identisch (Slot N+2,
WSJT-X-Cadence 30s).

**Fix A2** (`59293f0`) — KRITISCH: `core/encoder.py` cancelable sleep via
`threading.Event`. `_abort_event.wait(timeout=...)` statt `time.sleep`.
`abort()` ruft `event.set()` → sleep returnt sofort. `mw_qso.py:243-251`
ruft `abort()` vor neuem `transmit()` bei laufendem TX. R1's KRITISCHER
Finding behoben — alter Worker schlief vorher 14s weiter und sendete
veraltete Messages.

**Fix A3** (`6bf5b8c`): `qso_state.py:_set_state` resetet `timeout_cycles=0`
zentral für Wartezustände (WAIT_*, CQ_WAIT). Defense-in-Depth gegen
Counter-Race wenn `on_message_sent` nach `cycle_start` feuert (TX > 15s
durch Buffer-Drain).

**Fix B** (`46fcb91`): `encoder.py:204-216` Drift-Guard 0.3s-Schwelle
(war 5.0s). Headroom: 0.5s WSJT-X − 0.1s Encoding − 0.1s Marge. Bei
overshoot > 0.3s zum nächsten passenden Slot weiterschalten (Parity-
Erhalt: +2 Slots bei `tx_even` gesetzt, sonst +1).

**Fix C** (`67d374f`): `encoder.py:158` `_next_slot_boundary` Schwelle
`cycle_pos < 0.5s` statt `_SLOT/5` (= 3.0s bei FT8). Verhindert
Mid-Slot-Trigger von falscher Slot-Wahl.

**Race-Fix** (`07bccfd`) — R1-Final: `transmit()` joint alten TX-Thread
vor neuem Start (timeout 0.5s). Verhindert Race wo T1's `finally`
asynchron `_is_transmitting=False` setzt nachdem T2 schon `True` gesetzt
hat → State-Korruption, weitere `abort()`-Aufrufe wirkungslos.

**Release** (Commit 7): Version-Bump + HISTORY + CLAUDE.

### Tests

493 → 502 (9 neu, alle grün):
- `test_wait_report_retry_at_cycle_one`
- `test_wait_rr73_retry_at_cycle_one`
- `test_abort_during_sleep_returns_within_100ms` (R1's KRITISCH verifiziert)
- `test_state_change_during_encoder_sleep_aborts_pending_tx`
- `test_set_state_resets_counter_for_wait_states`
- `test_encoder_drift_guard_advances_slot`
- `test_encoder_no_drift_below_threshold`
- `test_next_slot_boundary_strict_threshold`
- `test_transmit_joins_old_thread_before_new` (R1-Final-Race)

### Lessons-Learned

1. **R1-Workflow rechtfertigt jeden Cent.** R1 fand zwei Bugs die ich (V2
   und Implementation) übersehen hatte. KRITISCHER Bug Race 2 (`time.sleep`
   nicht unterbrechbar) wäre in Real-Funkbetrieb katastrophal — alter
   Retry-TX hätte parallel zu neuem state-changed-TX laufen können. R1
   hat das aus dem Code direkt herausgelesen.

2. **R1 halluziniert auch.** R1's Behauptung „`timeout_cycles` wird
   nirgendwo zurückgesetzt" war falsch — Code resetet es Z.391/405/320.
   Verifikation Pflicht. Aber R1's allgemeiner Punkt zur Konsistenz war
   wertvoll → Fix A3 als Defense-in-Depth.

3. **Audio-Trim TRIM_SAMPLES**: Test-Erwartung muss Encoder-internes
   Trimming kennen (180k → 162k). Halt mich daran für künftige
   Encoder-Tests.

4. **Race-Conditions sind in Multithreading-Code IMMER mehr als sie
   scheinen.** Race-Fix wurde ERST nach R1-Final-Review entdeckt — V2/V3
   hatten den Pfad nicht analysiert. Bei threading.Event genau überlegen
   welcher Thread was wann setzt/cleart.

### Backup

`Appsicherungen/2026-04-30_vor_dt_drift_fix/` — core+ui+main.py vor
allen 7 Commits (2.2 MB Code-Only).

### Verifikation Feldtest 30.04. 10:30

**DT-Stabilität: ✓ FIX FUNKTIONIERT.** Alle TX-Frames am Icom DT 0.0–0.1s.
Der Drift-Bug ist tot. Real-Station-Test ausstehend.

**ABER neuer Bug entdeckt: Folge-Report wird DOPPELT gesendet.**

Mike's Icom-QSO mit DA1TST zeigte:
- 08:32:45 [O] Mike → "DA1TST DA1MHH -21" (erster Report) ✓
- 08:33:00 [E] DA1TST sendet R+18 (decoded am Slot-Ende ~T+29.5)
- 08:33:15 [O] Mike → "DA1TST DA1MHH -21" NOCHMAL (Doppel)
- 08:33:45 [O] Mike → "DA1TST DA1MHH RR73"

**Root-Cause-Analyse:** `on_cycle_end()` läuft AM SLOT-ANFANG (in
`_on_cycle_start`, mw_cycle.py:501), aber sollte AM SLOT-ENDE laufen
(in `_on_cycle_decoded`). Bei T+15 (Anfang [E]-Slot) feuert Fix-A1-
Retry, BEVOR die R+18-Antwort von DA1TST decoded ist (~T+29.5). Encoder
ist beim Decode bereits aus dem sleep raus → Race-Fix greift nicht
mehr. Doppel-Report wird gesendet, RR73 erst im Slot danach.

**Fix D (geplant):** `qso_sm.on_cycle_end()` von `_on_cycle_start` nach
`_on_cycle_decoded` verschieben (NACH Decoder-Loop). Saubere Architektur-
Korrektur — der Funktionsname war eh irreführend (heißt "cycle_end" aber
lief am cycle-START).

**Workflow für Fix D:** V1 → Self-Review V2 → DeepSeek-R1 → V3 → Plan-
Mode → Implementation. KEIN direkter Fix, weil Race-Conditions im
Threading-Code immer subtiler sind als sie scheinen (Lesson aus
v0.80-Workflow: R1 fand 2 Bugs die ich übersehen hätte).

App ist gestoppt — kein TX bis Fix D durch ist.

---

## 2026-04-30 v0.79 — Bug-Cleanup + CQ-Toggle/Stats-Lock-Fix

**Betroffene Dateien:** `ui/qso_panel.py`, `ui/mw_radio.py`, `ui/mw_cycle.py`,
`ui/settings_dialog.py`, `ui/control_panel.py`, `tests/test_auto_hunt_extended.py`,
`docs/TIMING_BUG_TESTPLAN_2026-05-01.md`, neue Memory
`feedback_auto_sequence_check_first.md`.

**Was:** Bug-Cleanup-Tag — vier Bugs gefixt aus v0.76-Field-Test +
v0.79-Field-Test, plus eine Auto-Sequence-Lesson aus 2h Diagnose-Falle.

### Diagnose-Falle Auto-Sequence (Vormittag, ~2h)

R1-Diagnose von gestern Abend (TX-Regression seit v0.75 mit 90%
Wahrscheinlichkeit ANT1-Hook stoert TX-Sequencing) wurde durch Test 1
(Baseline) widerlegt: Mike's Flex sendet alles sauber (Icom-Screenshot
zeigte CQ + Reports mit SNR 18-19 / DT 0). Echtes Problem: Auto-Sequence
am Icom-Test-Tool war ausgeschaltet — Icom hat stur initial-Anruf
wiederholt statt R-Report zu schicken.

→ ANT1-Hook in `Encoder.transmit()` ist unschuldig, kein Code-Fix
notwendig. Memory `feedback_auto_sequence_check_first.md` angelegt:
bei kuenftigen TX-Bug-Verdaechten ZUERST Auto-Sequence-Konfig am
Empfaenger-Tool pruefen.

### QSO-Panel Sammelanzeige raus (commit db10b2d, 30.04 02:26)

Mike-Wunsch v0.78 Field-Test: jede CQ-Wiederholung soll als eigene
Zeile im QSO-Panel sichtbar sein, statt als „CQ ×N" aggregiert.
`ui/qso_panel.py:add_tx()` schreibt jetzt jede TX-Message ins Log,
status_label-CQ-Counter und _cq_flash_timer entfernt.

### Quick-Wins (3 Bugs aus v0.76 R1-Final-Review)

1. **`ui/mw_radio.py` `_show_calibration_done`** (commit ad24a6e):
   non-modal Dialog mit `dlg.show()` konnte hinter Hauptfenster wandern.
   Fix: `setModal(True)` + `WindowStaysOnTopHint` + `dlg.exec()` (analog
   v0.77 Hardware-Acknowledgement-Pattern).

2. **`ui/mw_cycle.py` `_handle_dx_tune_mode`** (commit a7a16de): waehrend
   Diversity-Kalibrierung wurde RX-Tag stets als „A1" angezeigt obwohl
   Hardware zwischen ANT1/ANT2 schaltet. Fix: aktuelle Antenne vom
   `dx_tune_dialog._schedule[_step]` ablesen und auf `msg.antenna` setzen
   bevor `add_message()`.

3. **`ui/settings_dialog.py` `_reset_defaults`** (commit 759e49f): vier
   Widgets wurden nicht zurueckgesetzt — `radio_ip`, `language`,
   `stats_cb`, `debug_console_cb`. Defaults: leer / Deutsch / Stats-on /
   Debug-off.

### CQ-Toggle + Stats-Lock-Bug (Hauptfund Vormittag, commit d94f2e5)

Doppel-Bug seit v0.75 (commit ea7ea6e, 3-Button-Layout):
`mode_button_group.setExclusive(True)` verhindert Qt-intern dass ein
checked Button durch Re-Klick deselektiert werden kann.

Folgen:
- **CQ-Toggle broken** — Mike's Beobachtung: „CQ-Modus gestartet"
  mehrmals, nie „CQ-Modus gestoppt". Erneuter Klick triggert
  `clicked`-Signal mit `isChecked()==True` → `start_cq()` endlos.
- **Stats stillschweigend blockiert** — `btn_cq.isChecked()` bleibt
  True → `_cq_ui=True` in `_log_stats` → silent return False ohne
  Indicator-Update. Mike's Indicator blieb grau vom letzten
  Tuning/Warmup, obwohl Band+Modus+RX alles korrekt war.

Fix: `setExclusive(False)`. Mutually-exclusive zwischen OMNI ↔ Auto-Hunt
wird seit v0.78 in `main_window._on_btn_omni_cq_toggled` und
`_on_btn_auto_hunt_toggled` mit „superseded"-Reason gemacht. `btn_cq`
und Diversity-Buttons sind ohnehin nie gleichzeitig sichtbar
(mode-coupled v0.78).

Test-Update: `test_control_panel_three_mode_buttons_initially_hidden`
exclusive-Erwartung auf False geaendert.

### Bekannte Fallen ergaenzt

- **Stats-Lock**: bei Verdacht auf „Stats wird nicht geloggt" als
  ERSTES `btn_cq.isChecked()` UND `qso_sm.cq_mode` UND `qso_sm.state`
  pruefen — wenn alle False/IDLE und Stats-Indicator trotzdem grau,
  ist's ein Reset-Problem in einem der `_stats_warmup_cycles=99999`-
  Pfade (`_on_dx_tune_rejected` Z.1011-1012 setzt im Normal-Branch
  KEIN Reset — TODO-Folge).

**APP_VERSION:** 0.78 → 0.79.

**Tests:** 493 gruen (unveraendert).

---

## 2026-04-30 v0.78 — OMNI-TX scharfgeschaltet + Auto-Hunt Diversity-only

**Betroffene Dateien:** `core/omni_tx.py`, `ui/main_window.py`, `ui/mw_radio.py`,
`ui/mw_qso.py`, `tests/test_omni_tx.py` (NEU), `tests/test_auto_hunt_extended.py`,
`main.py`, `prompts/omni_v1.md`/`v2.md`/`v3.md` (NEU), `docs/OMNI_TX_DESIGN.md`
(neu am 2026-04-30 angelegt).

**Was:** OMNI-TX-Feature (5-Slot Even/Odd-Rotation) scharfgeschaltet als
**Diversity-only** Power-User-Feature — `btn_omni_cq` und `btn_auto_hunt`
sichtbar nur in RX-Modus „diversity". Direkt-Toggle, mode-gekoppelt,
mutually-exclusive zueinander. Easter-Egg-Override (Klick Versionsnummer)
bleibt als Test-Bypass im Normal-Modus, wird automatisch zurueckgesetzt
beim RX-Mode-Wechsel.

**Code-Aenderungen:**
- `core/omni_tx.py`: `OmniTX` → `QObject` mit `omni_stopped(reason)`-Signal.
  Neue Methode `stop_omni_tx(reason)` zentralisiert + `_pending_switch`-Reset
  (Bug-Fix V3 C6: sonst spruenge Block nach Re-`enable()` sofort).
  Default `block_cycles` 40 → 80 (Plan v3.2). `OMNI_TX_ENABLED`-Konstante
  entfernt (war ungenutztes Gate). `disable()` als Backwards-compat-Wrapper
  delegiert an `stop_omni_tx("easter_egg_off")`. `should_tx()`-Signatur
  vereinfacht: ungenutzter `is_even`-Parameter entfernt (R1-Final-Review).
- `ui/main_window.py`: Neue Handler `_on_btn_omni_cq_toggled`,
  `_on_omni_stopped`, `_update_button_visibility()` (Mode-Coupling-Helper).
  Easter-Egg-Toggle vereinfacht — Signal-Slots kuemmern sich um UI-Cleanup.
  Mutually-exclusive: OMNI-Klick stoppt aktiven Auto-Hunt mit `superseded`,
  und umgekehrt. Totmann-Hook (`_on_presence_tick`) ergaenzt um
  `stop_omni_tx("totmann_expired")` parallel zu existing Auto-Hunt-Stop —
  V2-Annahme „Totmann greift bei QSO nicht" wurde im R1-Review als falsch
  identifiziert (Code stoppt unconditional, laufendes QSO wird via
  `presence_can_tx()` separat zu Ende gefuehrt).
- `ui/mw_radio.py`: Stop-Hooks fuer `_on_band_changed`
  (`stop_omni_tx("band_change")`), `_on_mode_changed` (FT-Modus, Reason
  umbenannt von `mode_change` zu `ft_mode_change` plus
  `stop_omni_tx("ft_mode_change")`), `_on_rx_mode_changed` (NEUER Hook
  fuer `rx_mode_change` plus `stop_auto_hunt("rx_mode_change")` —
  v0.75 Auto-Hunt war bisher nur mode-coupled fuer FT-Modus, nicht RX-Modus).
  `_apply_normal_mode` + `_enable_diversity` rufen `_update_button_visibility()`
  am Ende. Defensive Aufruf am Ende von `_on_rx_mode_changed` ergaenzt
  (R1-Final: deckt early-return-Pfade ab).
- `main_window.py`/`mw_radio.py`: Easter-Egg-Override wird automatisch
  zurueckgesetzt bei RX-Mode-Wechsel (V3 A3).

**Reason-Tabelle (v0.78 final, OMNI + Auto-Hunt):**
- `manual_halt` — User klickt aktiven Button erneut
- `superseded` — User startet das andere Mode-Feature (OMNI ↔ Auto-Hunt)
- `band_change` — Bandwechsel
- `ft_mode_change` — FT-Modus-Wechsel (FT8/FT4/FT2)
- `rx_mode_change` — RX-Modus-Wechsel (Diversity↔Normal)
- `totmann_expired` — Presence-Timeout (15 min)
- `easter_egg_off` — Easter-Egg deaktiviert
- `timer_expired` — nur Auto-Hunt 10-Min-Hard-Cap

**Out-of-scope (TODO fuer separates Release):** `_reset_presence`-Aufruf
bei QSO-Ende. Aktuell stoppt Totmann auch ein laufendes 30-min-QSO mit
nachfolgendem CQ-Stop wenn keine Mausbewegung. Nicht kritisch im
Hobby-Kontext.

**Workflow:** V1 (`prompts/omni_v1.md`) → Self-Review (17 Findings) → V2
(`omni_v2.md`) → DeepSeek-R1 (10 Findings: 2 Bugs, 2 Risiko, 2 Verb.,
4 Hinweis, **0 Halluzinationen**) → Schritt 2.5 Code-Verifikation (R1 fand
2 echte Bugs in V2: Totmann-Verhalten + `_reset_presence`-Annahme) → V3
(`omni_v3.md`) → Mike-Freigabe → 7 atomare Commits → Schritt 5b
Final-R1-Review (11 Findings, 2 echte Verbesserungen umgesetzt) →
Lessons-Learned + Memory-Update.

**Tests:** 472 → 493 gruen (+21).
- `tests/test_omni_tx.py` NEU (11 Cases): `initial_state_inactive`,
  `default_block_cycles_is_80`, `enable_resets_state`,
  `5_slot_pattern_block1`/`block2`, `block_switch_after_block_cycles`,
  `block_switch_at_position_0_only`, `qso_resets_counter_keeps_block`,
  `stop_omni_tx_resets_pending_switch` (Bug-Fix C6), parametrize
  `omni_stopped_signal_emits_with_reason` (7 Reasons),
  `disable_delegates_to_stop_with_easter_egg_off`.
- `tests/test_auto_hunt_extended.py` ERGAENZT: parametrize-Liste der
  `stop_reasons_clear_cooldown` und `auto_hunt_stopped_signal` und
  `qso_log_unaffected_by_stop` Tests um `ft_mode_change`,
  `rx_mode_change`, `superseded` (3 neue Reasons, +10 Tests durch
  parametrize-Multiplikation).

**Mike's manuelle Verifikation (V3 Sektion 6):** ausstehend.

**Backup vor Implementation:** `Appsicherungen/2026-04-30_vor_omni_implementierung/` (1.2 GB).

---

## 2026-04-29 v0.77 — App-Start Hardware-Dialog + Statistik-Methodik-Korrektur

**Betroffene Dateien:** `main.py`, `scripts/generate_plots.py`, `README.md`,
`HISTORY.md`, `CLAUDE.md`, `auswertung/*` (PDFs neu).

### Was ist v0.77

Zwei Bug-Fix-/Verbesserungs-Punkte aus dem v0.76-Field-Test (29.04.2026)
zusammengefasst — beide trivial-Pfad-tauglich (klare Diagnose, < 30 Z. Code,
kein V1→V2→V3-Workflow noetig).

#### 1. App-Start Hardware-Sicherheitsdialog (🔴 Sicherheits-Layer)

Pflicht-Acknowledgment beim App-Start mit Inhalt:
- ANT1 = IMMER die TX-Antenne. Kann nicht anders gesetzt werden.
- ANT2 = IMMER nur Hilfs-Empfangsantenne. App nutzt sie NIEMALS zum Senden.
- Disclaimer: private Machbarkeitsstudie, keine Haftung fuer
  Hardware-Schaeden, Datenverlust, regulatorische Verstoesse.

UI: schlanker QDialog (520×300 px) im SimpleFT8-Dark-Theme, NICHT QMessageBox
(zu plump fuer Apps mit eigenem Style). Modal + `WindowStaysOnTopHint`
+ `dlg.exec()`. „OK — verstanden" → App startet, „Abbrechen" → `sys.exit(0)`.

Erste Iteration hatte einen rot-umrandeten „Hardware-Schaden moeglich"-
Kasten — auf Mike's Wunsch entfernt (Funker wissen das, Drohton schreckt
ab). Stattdessen kompakter grauer Disclaimer-Block. Funktional reicht
das zusammen mit der **MIT-License (AS-IS-Klausel)** + dem neuen
zweisprachigen **Disclaimer-Block in README.md** unter den Badges.

#### 2. Min/Max-Error-Bars im PDF-Bericht entfernt (🟡 Methodik-Korrektur)

Die bisherigen Bars vermischten drei Variablen und waren methodisch unfair:
1. Modus-Volatilitaet (was wir wissen wollten)
2. Tag-Conditions (Solar/Storm — Confounder, weil Modi an unterschiedlichen
   Tagen gemessen wurden)
3. Stichprobengroesse (Modi haben unterschiedliche `n_days`)

Folge: Diversity-Bars konnten riesig erscheinen NICHT weil Diversity volatil
ist, sondern weil die Mess-Tage stuermisch waren. Bei kleiner Stichprobe
(N=2) ist Min/Max ausserdem trivial = einfach die zwei Werte. Ausreisser-
empfindlich.

Pooled Mean ueber 4-5+ Tage ist statistisch belastbar genug. Bars suggerierten
Praezision die in der Mess-Methodik nicht steckt — schlechter als gar keine
Bars. Wirklich saubere Modus-Vergleiche brauchten interleaved-Messung
(wie in DX-Tune-Kalibrierung), fuer Stunden-/Tagesstatistik nicht praktikabel.

PDFs (DE+EN, 40m+20m FT8) neu generiert — saubereres Layout ohne Bars.

### Workflow

Beide Aenderungen gingen direkt durch (Trivial-Pfad), ohne V1→V2→V3.
Begruendung: klare Diagnose, kleine Aenderungs-Surface, keine Architektur-
Wirkung. WORKFLOW v1.1 erlaubt Skip explizit fuer diese Faelle.

DeepSeek-R1 wurde nur fuer die Methodik-Diskussion (5 vs 7 Tage Daten-
sammlung) konsultiert — **kein Code-Review noetig** wegen Trivial-Charakter.

### Atomare Commits

1. `b6f965f` `refactor(plots): Min/Max-Error-Bars entfernen` — `generate_plots.py`
   + alle PDFs/PNGs frisch.
2. `8f2a103` `feat(safety): App-Start Hardware-Dialog + Disclaimer` —
   `main.py` (Dialog) + `README.md` (Disclaimer-Block) + Tests-Badge
   442→472 aktualisiert.
3. (dieser Commit) `chore(release): v0.77 — Hardware-Dialog +
   Statistik-Methodik` — APP_VERSION, HISTORY, CLAUDE.md.

### Test-Status

```
./venv/bin/python3 -m pytest tests/ -q
472 passed in ~7s
```

Keine neuen Tests — Dialog ist auf User-Acknowledgment ausgelegt (kann
nur manuell geprueft werden, modal mit `exec()`), Methodik-Aenderung
ist Plot-Code (nicht test-pflichtig).

### Bekannt-Out-of-Scope (separate v0.78-Issues)

- 🟡 **RX-Tag waehrend Diversity-Kalibrierung** — `_handle_dx_tune_mode`
  setzt `msg.antenna` nicht auf aktuelle Schedule-Antenne. UI-only-Bug,
  Mess-Algorithmus selbst korrekt.
- 🟠 **Bestaetigungsfenster nach Kalibrierung** (`_show_calibration_done`)
  ist non-modal + nicht-on-top — kann hinter Hauptfenster wandern.
  Fix: `setModal(True)` + `WindowStaysOnTopHint` + `dlg.exec()`.

---

## 2026-04-29 v0.76 — Settings-Dialog auf Tabs (1440x900-Fix)

**Betroffene Dateien:** `ui/settings_dialog.py`,
`tests/test_settings_dialog_smoke.py` (neu), `main.py`, `CLAUDE.md`,
`prompts/settings_tabs_v2.md` + `_v3.md` (neu).

### Was ist v0.76

Reines UI-Refactor: Settings-Dialog wird von monolithisch gestapelter
Form (6 GroupBoxen vertikal, ~800 px hoch) auf vier `QTabWidget`-Tabs
umgestellt — Dialog passt jetzt vollstaendig auf Mike's 1440×900-Display
(max 750 px Hoehe, gemessen 560 px nach Build). Funktional unveraendert.

**Tab-Aufteilung:**
- Tab 1 „Station": Rufzeichen, Locator, IP-Adresse, Sprache.
- Tab 2 „TX & Schutz": Sendeleistung, TX-Audio-Pegel, Anrufversuche,
  SWR-Limit, Tune-Leistung, RF-Presets-Tabelle (interne GroupBox).
- Tab 3 „FT8 & Diversity": TX-Audio-Frequenz, Max-Decode-Frequenz,
  Neueinmessung-Zyklen, Statistik-Erfassung-Checkbox.
- Tab 4 „Daten & Tools": CSV-Export + Beschreibung, Karte oeffnen +
  Beschreibung, Debug-Konsole-Checkbox (3 Bloecke mit `QFrame::HLine`-
  Trennern).

**Tab-Anzahl-Entscheidung (4 statt R1-Faustregel-3):** Tab 2 hat
sizeHint().height() = 462 px (knapp unter R1-Schwellwert 500 px), wuerde
also nominell die 3-Tab-Variante triggern. Bewusste Abweichung: 3-Tab
„FT8 & Tools" muesste FT8-Settings + Statistik-Checkbox + CSV-Export +
Karte + Debug-Konsole zusammenpressen — UX-mässig ueberfrachtet. 4 Tabs
sind logisch sauberer.

### Workflow

V1 → V2 (Self-Review, ~10 Schwachstellen erkannt) → DeepSeek-R1
(19 Findings, 12 angenommen, 7 abgelehnt) → V3 → Mike-Freigabe →
Code (3 Implementierungs-Commits) → Final-R1-Codereview (4 Findings,
1 fix integriert „Timer-Stop in closeEvent", 3 out-of-scope/abgelehnt).

### Atomare Commits

1. `7727fc9` `refactor(ui): SettingsDialog mit QTabWidget (4 Tabs)` —
   Hauptaenderung in `settings_dialog.py`. Build-Methoden
   `_build_tab_station/tx/ft8/data() -> QWidget`, neuer Tab-Stylesheet,
   Hoehen-Sizing via `adjustSize` + `resize`-Fallback,
   `closeEvent()`-Timer-Stop (Defense-in-Depth gegen R1-Lifecycle-Finding).
2. `f4aad88` `test(ui): SettingsDialog Smoke-Test (5 Test-Cases)` —
   neuer Test-File mit `_FakeSettings`-Mock, Tabs-Existenz, Widget-
   Erreichbarkeit, Hoehen-Limit, Save-Round-Trip, initialer Tab.
3. `b7eaf5d` `docs(prompts): Settings-Tabs V2/V3` — Workflow-Doku.
4. (dieser Commit) `chore(release): v0.76 — Settings auf Tabs` —
   APP_VERSION, HISTORY.md, CLAUDE.md.

### Test-Status

```
./venv/bin/python3 -m pytest tests/ -q
472 passed in ~7s
```

(467 → 472 dank 5 neuer Smoke-Tests in `test_settings_dialog_smoke.py`.)

### Bekannt-Out-of-Scope (separate Issues)

- `_reset_defaults()` setzt `radio_ip`, `language`, `stats_cb`,
  `debug_console_cb` NICHT zurueck (war im alten Code auch schon so —
  R1 hat es im Final-Review wieder gefunden). Bewusst out-of-scope
  dieses UI-Refactors (V3 hat das explizit ausgeklammert). Wenn das
  gefixt werden soll: separater Commit.
- `_load_values()` mischt `settings.callsign` (Property) und
  `settings.get("flexradio_ip")` (Dict-API). Bestehendes Pattern,
  out-of-scope.

---

## 2026-04-29 v0.75 — Auto-Hunt-Modus (Easter-Egg, 10-Min-Hard-Stop)

**Betroffene Dateien:** `core/auto_hunt.py`, `core/encoder.py`, `ui/main_window.py`,
`ui/mw_radio.py`, `ui/mw_tx.py`, `ui/control_panel.py`,
`tests/test_modules.py`, `tests/test_auto_hunt_extended.py` (neu),
`main.py`, `CLAUDE.md`.

### Was ist v0.75

Easter-Egg-aktivierter Auto-Hunt-Modus: Klick auf Versionsnummer →
3-Button-Layout `[CQ RUFEN] [OMNI CQ] [AUTO HUNT]` erscheint im QSO-Bereich.
Klick auf AUTO HUNT startet eine **fest 10 Minuten** lange Session, in der
SimpleFT8 automatisch CQ-Rufer scannt und anruft. Der Timer ist von
Maus/Tastatur entkoppelt (Bot-Tarn-Schutz, Defense-in-Depth zum
Totmannschalter).

### Workflow-Reflexion (V1 → V2 → DeepSeek-R1 → V3)

Erstmals den verbindlichen `docs/WORKFLOW.md`-Prozess voll durchlaufen:

- **V1** (`prompts/auto_hunt_v1.md`): erster Entwurf, 18 Akzeptanzkriterien.
- **V2** (Self-Review): 12 eigene Schwachstellen erkannt, neu geschrieben mit
  25 Akzeptanzkriterien.
- **DeepSeek-R1-Review** (`tools/deepseek_review.py --reasoner`): 31 Findings
  zurueck, davon **12 angenommen** (Plan-Verbesserungen) und **5 begruendet
  abgelehnt** (Race-Doppel-Check als ethische Belt-and-suspenders behalten,
  KISS-Begruendungen).
- **V3** (`prompts/auto_hunt_v3.md`): Final-Plan, Mike-Freigabe.
- **Plan-Mode**: Code-Verifikationen vor Commit 1 fanden 1 echte Luecke
  (`mw_tx.py:83` ohne ANT1-Guard) und 1 V3-Halluzination (`_MAX_ATTEMPTS=3`
  ist nur Modul-Konstante, nicht in der Klasse verwendet → AC C6 gestrichen).

### Implementierung — 10 atomare Commits

1. `feat(safety): ANT1-Guard in Encoder.transmit() + mw_tx.tune_on()` —
   defensives `set_tx_antenna("ANT1")` zentral. Schliesst echte Luecke im
   TUNE-Pfad (`mw_tx.py:83`).
2. `refactor(auto_hunt): AutoHunt erbt von QObject` — Signal-Foundation.
3. `refactor(auto_hunt): enable/disable + _pause_remaining entfernen` —
   alte API durch zeitgesteuerte ersetzt.
4. `feat(auto_hunt): start_auto_hunt + stop_auto_hunt + Signal + Timer` —
   QTimer single-shot 600_000ms, `auto_hunt_stopped(reason)`-Signal,
   reason-basierte Cleanup-Logik (totmann_expired laesst Cooldowns +
   `_last_tx_even` erhalten fuer User-Restart).
5. `feat(auto_hunt): Slot-Affinitaet + Race-Doppel-Check` — `_last_tx_even`-
   Filter mit Fallback, zweiter `active`-Check direkt vor Return.
6. `feat(safety): Totmann-Integration triggert stop_auto_hunt('totmann_expired')` —
   ueberlappende Abschalt-Mechanismen (10-Min-Hard-Cap + 15-Min-Totmann).
7. `refactor(ui): omni_tx_clicked → easter_egg_toggle_clicked Signal-Rename`.
8. `feat(ui): 3-Button-Layout im QSO-Bereich` — mutually exclusive
   `QButtonGroup`, btn_omni_cq + btn_auto_hunt initial hidden, nur via
   Easter-Egg sichtbar. TUNE bleibt SEPARAT (kein Group-Member).
9. `feat(ui): Auto-Hunt-Lifecycle (Easter-Egg + Countdown + 5s UI-Cooldown)` —
   1s-Polling fuer Live-Countdown, 5s-Reflexions-Cooldown nach Stop,
   Mode-Wechsel-Hook in `mw_radio._on_mode_changed`.
10. `chore(release): v0.75 — Auto-Hunt-Modus` (dieser Commit).

### Test-Bilanz

- **446 → 467 gruen** (+21 statt geplanten +10 dank parametrize-Bonus
  ueber 6 Stop-Reasons).
- Neuer Test-File: `tests/test_auto_hunt_extended.py`
  (10 Test-Funktionen, 21 Test-Cases inkl. parametrized).
- Bestehender Test umgebaut: `test_autohunt_band_change_clears_cooldown` →
  `test_autohunt_band_change_stops_session_and_clears_cooldown` (neue Semantik:
  band_change stoppt Session via `stop_auto_hunt`).

### Sicherheits-Schichten (Defense-in-Depth)

| Mechanismus | Trigger | Effect |
|---|---|---|
| 10-Min-Hard-Stop | `_auto_hunt_timer.timeout` | `stop_auto_hunt("timer_expired")` |
| Totmannschalter | 15 Min keine Maus → `_on_presence_tick` | `stop_auto_hunt("totmann_expired")` |
| Manueller HALT | User klickt btn_auto_hunt | `stop_auto_hunt("manual_halt")` |
| Easter-Egg-Off | User Klick Versionsnummer | `stop_auto_hunt("easter_egg_off")` |
| Bandwechsel | `on_band_change()` | `stop_auto_hunt("band_change")` |
| Mode-Wechsel | `mw_radio._on_mode_changed` | `stop_auto_hunt("mode_change")` |

ANT1-Pflicht ist zentral via `Encoder.transmit()` + alle `tune_on()`-Pfade
abgesichert (`mw_tx.py:83` Luecke geschlossen).

### DeepSeek-R1-Final-Review-Findings

R1 (Reasoner) hat 4 Findings zurueckgegeben:

1. **„Band-Wechsel-Hook fehlt"** — abgelehnt als Halluzination. R1 sah nur
   `core/auto_hunt.py` + `ui/main_window.py` (nicht `mw_radio.py`). Der Hook
   ist in `mw_radio.py:297-299` korrekt verbunden — `set_band(band)` +
   `on_band_change()` werden bei aktivem Auto-Hunt gerufen.
2. **„Doppelter `active`-Check redundant im single-threaded GUI"** — bewusst
   behalten. Mike's ethische Belt-and-suspenders zur 10-Min-Hard-Cap. Nicht
   entfernen.
3. **„UI-Cooldown laeuft nach Easter-Egg-Off weiter"** — angenommen, gefixt
   in `_on_easter_egg_toggle` else-Zweig: `_auto_hunt_cooldown_timer.stop()`
   + Button-State zurueck zu Idle wenn Button versteckt wird.
4. **„`btn_omni_cq` ohne `clicked`-Handler"** — als Phase 2 vermerkt
   (siehe unten).

### Bekannte Einschraenkungen (Phase 2)

- `btn_omni_cq` hat aktuell keinen eigenen `clicked`-Handler — OMNI-CQ
  laeuft weiterhin ueber bisherige Logik. Phase 2: dedizierter Handler
  fuer mutually-exclusive Modus-Aktivierung.

### Post-Release Hotfix (`f6d30ab`)

Beim ersten v0.75-App-Restart aufgetauchter Latent-Bug in der `MainWindow`-
Init-Reihenfolge:

```
Z.64  _connect_signals          → band_changed.connect(_on_band_changed)
Z.76  _set_band(settings.band)  → feuert band_changed Signal SOFORT
       └→ _on_band_changed → mw_radio.py:341 _update_propagation_ui
            └→ AttributeError: '_prop_error_shown' fehlt
Z.82  _init_propagation_polling → setzt _prop_error_shown = False (zu spaet!)
```

Der Bug war auch in v0.74 latent vorhanden, wurde aber durch eine andere
Trigger-Reihenfolge nicht ausgeloest. Beim v0.75-Restart in Mike's Setup
zur Live-Session reproduzierbar.

**Fix:** `hasattr`-Guard am Anfang von `_update_propagation_ui` —
early-return bei zu fruehem Aufruf, der naechste 60s-Polling-Tick oder
naechste Bandwechsel ruft die Methode dann sauber. Saubere Init-
Reihenfolge waere besser, aber Risk/Aufwand-Verhaeltnis spricht fuer den
defensiven Guard (KISS, 5 Zeilen, kein bestehender Pfad veraendert).

**Tests:** 467 weiter gruen.

---

## 2026-04-29 — Tooling: DeepSeek Direkt-API + R1 als Default

**Betroffene Dateien:** `tools/deepseek_review.py` (neu), `CLAUDE.md`,
`~/.deepseek_key` (chmod 600, ausserhalb Repo).

### Hintergrund

Bei v0.74-Review (28.04.) zeigte sich der pal-MCP-Engpass: File-Attachments
sind auf 7077 Tokens limitiert, kompletter `mw_radio.py` (43 KB) passt
nicht rein. Wir mussten Inline-Snippets in den Prompt einbauen — funktionierte,
aber nicht skalierbar fuer groessere Reviews.

### Loesung: Direkt-API-Helper

`tools/deepseek_review.py` — Pure-stdlib (urllib + json), liest Prompt aus
stdin, haengt optionale Files mit Pfad-Header an, schickt direkt an
`api.deepseek.com/v1/chat/completions`. **65K Context** (~260 KB Code) statt
7077 Tokens — kompletter `mw_radio.py` + `diversity.py` + `preset_store.py`
passen problemlos rein.

```bash
cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py
cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py --chat file.py
```

Key liegt in `~/.deepseek_key` (chmod 600). Niemals im Repo.

### Modell-Wahl: R1 als Default (Mike-Entscheidung)

| Modell | Default? | Antwort-Zeit | Kosten | Stark fuer |
|---|---|---|---|---|
| **`deepseek-reasoner` (R1)** | ✅ JA | 6-30s | ~$0.005 | Code-Review, Architektur, Race-Conditions, KISS-Trade-offs, mathematische Korrektheit |
| `deepseek-chat` (V4) via `--chat` | Opt-in | 2-5s | ~$0.001 | Trivial-Fragen ("Ist X im Code?"), Tippfehler, Pure Verifikation |

**Mike-Begruendung 28.04.2026:** „Quality > Speed, ~3 EUR/Monat-Differenz
egal gegen einen Bug der Stunden frisst."

V0.74-Bilanz mit V4: 5 echte Findings + 1 Halluzination („Phase haengt
ewig" — falscher Alarm, durch Code-Verifikation in `mw_cycle.py:159`
widerlegt). R1 sollte Halluzinations-Rate senken weil R1 Code-Pfade
intern verifiziert. Bewahrheitet sich erst ueber mehrere Reviews.

### `pal chat`-MCP weiter nutzbar

Fuer einfache Multi-Turn-Sessions mit Continuation-IDs. Aber: ernste Reviews
mit grossen Files immer ueber Direkt-API.

### Verifikation

Smoke-Test mit 3 Files (1799 Zeilen, 20K Tokens) sauber durchgelaufen.
Identische Schlussfolgerung von V4 und R1 bei einfacher Verifikations-Frage
("ist load_preset weg?"). R1-Antwort: 6.2s, knapper formuliert mit
mehr internem Reasoning.

---

## 2026-04-28 v0.74 — Diversity-Bandwechsel: Ratio-Cache-Bug behoben

**Betroffene Dateien:** `ui/main_window.py`, `ui/mw_radio.py`, `ui/mw_cycle.py`,
`core/diversity.py`, `tests/test_diversity_bandwechsel.py` (neu),
`tests/test_modules.py`, `main.py`, `HISTORY.md`, `CLAUDE.md`.

### Der Bug

Bei Bandwechsel (z.B. 40m → 20m) mit aktiver Diversity wurde das alte
Ratio aus dem 2h-Cache geladen. Bei Mike's asymmetrischer Antennen-
Konfiguration (ANT1 = Kelemen Trap-Dipol resonant 20/15/10m, ANT2 =
Regenrinne ~15m) ist Ratio aber stark **band-spezifisch**:
- 40m off-band: ANT2 dominant 30:70 (Tuner-verlustbehaftet)
- 20m resonant: ANT1 dominant 70:30 (Trap-Dipol effektiv)

Cache uebernehmen → bis zu 60 Zyklen falsche Antennen-Wahl bis zur
naechsten Manuell-Einmessung. Mike hat das im Feldtest entdeckt.

### Trennung Gain vs. Ratio

| Eigenschaft | Was | Cache | Bei Bandwechsel |
|---|---|---|---|
| **Gain** | RMS-Pegel-Kalibrierung pro Antenne | 2h OK | Frage J/N |
| **Ratio** | Diversity-Pattern (ANT1:ANT2) | NIE | IMMER neu |

Gain ist **Hardware-Eigenschaft** (RX-Verstaerker + Antennen-Anpassung,
aendert sich nur langsam). Ratio ist **Pattern-Eigenschaft** (welche
Antenne wo besser empfaengt — abhaengig von Frequenz, Resonanz,
Tageszeit, Skip-Zone). Cache fuer Pattern ist physikalisch falsch.

### Wechsel-Matrix

| Wechsel | TUNE | Gain | Ratio |
|---|---|---|---|
| Band + Gain<2h | auto | Frage J/N | NEU |
| Band + Gain>2h | auto | auto | NEU |
| Normal→Diversity (selbes Band) + Gain<2h | auto | Frage J/N | NEU |
| Diversity Std↔DX (selbes Band) + Gain<2h | auto | Frage J/N | NEU |
| Diversity→Normal | auto | n/a | n/a |
| FT-Modus FT8↔FT4↔FT2 | auto | Frage J/N | NEU |

### Implementierung — 6 atomare Commits

1. **`feat(diversity): _start_tune_only() Helper mit Race-Token + Offline-Guard`**
   - Neuer Helper in `mw_radio.py` der nur TUNE durchfuehrt (5s Carrier,
     Tuner stimmt sich ein) und einen Callback ausloest.
   - **Race-Schutz** via `self._tune_token = object()`: wenn waehrend der
     5s ein Bandwechsel passiert, nullt `_on_band_changed` das Token —
     der ablaufende Timer prueft das Token und ignoriert seinen Callback.
     Sonst wuerde `_enable_diversity` fuer das verlassene Band gerufen.
   - **Offline-Schutz**: wenn FlexRadio waehrend TUNE offline geht, kein
     Crash bei `tune_off()`.

2. **`fix(diversity): Ratio NIE aus Cache laden — immer neu einmessen`**
   - `_enable_diversity()` (mw_radio.py:546-565) umgebaut: statt
     `load_preset()` aufzurufen (das setzte Phase=operate mit altem Ratio)
     immer `reset()` → Phase=measure.
   - Gain-Block (Z.569-584) bleibt unveraendert — der ist korrekt.
   - `_set_gain_measure_lock(True)` setzt GUI-Lock (kein manueller
     Gain-Klick, kein CQ-Start waehrend Re-Measurement).

3. **`feat(diversity): TUNE im "Weiter"-Cache-Pfad + klarer Dialog-Text`**
   - `_check_diversity_preset()` "Weiter"-Pfad ruft jetzt `_start_tune_only`
     mit Lambda-Callback auf `_enable_diversity`. ANT1 wird vor
     Re-Measurement abgeglichen (wichtig fuer off-band Trap-Dipol auf 40m).
   - Dialog-Text praezisiert: User sieht jetzt EXPLIZIT dass "Weiter" nur
     Gain uebernimmt und Ratio neu gemessen wird (5s TUNE). UX-Punkt aus
     DeepSeek-Review.

4. **`feat(diversity): GUI-Lock-Aufhebung via Phase-Diff in mw_cycle.py`**
   - `_handle_diversity_measure()` liest `phase` vor `record_measurement()`,
     erkennt nach Call den Uebergang `measure → operate` und triggert
     `_set_gain_measure_lock(False)` + `_set_cq_locked(False)`.
   - DeepSeek hatte ein neues Signal-Pattern (`_on_measure_done` Callback
     auf Controller) vorgeschlagen — Phase-Diff ist KISS-konform: nutzt
     vorhandenen pro-Slot-Hook ohne neue Abstraktion.

5. **`refactor(diversity): load_preset() entfernt — toter Code nach Fix`**
   - `core/diversity.py` Methode geloescht (nur Aufrufer war der Bug-Pfad).
   - `tests/test_modules.py:test_diversity_load_preset` geloescht.
   - DeepSeek hatte "behalten + Warnung" empfohlen — Loesch-Variante ist
     sauberer, kein toter Code im Repo.

6. **`test(diversity): 5 Tests fuer v0.74 Bandwechsel-Bug-Fix`**
   - `test_token_pattern_invalidates_old_callback` — Pure-Logic Race-Token.
   - `test_phase_diff_detects_measure_to_operate_transition` — Phase-Diff.
   - `test_load_preset_removed_from_diversity_controller` — Regression.
   - `test_reset_phase_is_measure_not_operate` — reset()-Verhalten.
   - `test_on_band_change_triggers_full_reset` — End-to-End Bandwechsel.

### Workflow-Reflexion (V1 → V2 → V3)

V1 als Roh-Entwurf von Claude. V2 als Self-Review identifizierte 12
Schwachpunkte (TUNE als 8-Schritt-Flow, Edge-Cases bei Bandwechsel
waehrend measure, GUI-Lock-Liste unvollstaendig, fehlende Tests).
V2 ging an DeepSeek-V4 (`pal chat` model `deepseek-chat`).

**DeepSeek-Findings (5 echte / 1 Halluzination):**

✅ Race-Token bei TUNE-Callback ⭐ (kritisch, eingebaut)
✅ FlexRadio-Offline-Guard in `_after_tune` (eingebaut)
✅ UX: Dialog-Text muss TUNE-Phase kommunizieren (eingebaut)
✅ Test-Luecke: T6 Bandwechsel waehrend TUNE (eingebaut als Pure-Logic)
✅ `from QTimer` Import-Position (Kosmetik, ignoriert)
❌ "Phase haengt ewig auf measure bei <5 Stationen" — falscher Alarm,
   `_evaluate()` faellt mit leeren Listen auf 50:50/operate (verifiziert
   in mw_cycle.py:159: `record_measurement` laeuft pro Slot ohne
   Conditional, auch bei 0 Stationen).

**Eigene Korrekturen gegen DeepSeek:**

- GUI-Lock-Aufhebung: Phase-Diff in mw_cycle.py (statt DeepSeek's neuer
  `_on_measure_done` Callback-Attribut auf Controller — er gab selbst zu
  "schwaches Pattern").
- `load_preset()` ganz loeschen (statt mit Warnung behalten).

**V3 als Final-Plan** mit Datei:Zeile-Verweisen, atomarer Commit-Plan,
Tests T1-T8 — dann Implementierung in 6 Commits.

### Tests
- 446 grün (vorher 442 → +5 neue, -1 geloeschter `test_diversity_load_preset`)
- `./venv/bin/python3 -m pytest tests/ -q` → 446 passed in 6.03s

### Code-Pfade verifiziert
- `mw_cycle.py:159` `record_measurement()` laeuft pro Slot, auch ohne Stationen
- `mw_radio.py:286` `on_band_change()` setzt Phase=measure (✅)
- `mw_radio.py:344` `_check_diversity_preset()` greift bei Bandwechsel UND Mode-Wechsel UND Diversity-Std/DX-Wechsel — Fix automatisch ueberall
- `mw_radio.py:240-243` `_on_mode_changed()` ruft auch `_check_diversity_preset()` (Fix greift fuer FT-Modus-Wechsel automatisch)

---

## 2026-04-27 v0.70 — Locator-DB Live-Feed (Bugfix) + Auto-Save + Map-Quality

**Betroffene Dateien:** `ui/mw_cycle.py`, `ui/main_window.py`,
`ui/direction_map_widget.py`, `tests/test_feed_locator_db.py` (neu),
`main.py`, `HISTORY.md`, `CLAUDE.md`.

### Kritischer Bugfix — Live-Locator-Feed war seit v0.67 tot

Mike-Beobachtung: Karte zeigte beim Empfang von `RA4ALY DL6YJB JO31`
weiterhin `~216` (Country-Fallback) statt der bekannten exakten Position
fuer JO31. Erwartet: Locator wird live aus der Decode-Message extrahiert
und in `LocatorDB` geschrieben.

**Root-Cause:** `core/message.py:72` definiert `is_grid` als `@property`
(nicht callable). `ui/mw_cycle.py:_feed_locator_db` rief aber
`m.is_grid()` MIT Klammern → bei jedem einzelnen Decode flog ein
`TypeError: 'bool' object is not callable`, der vom umschliessenden
`except (AttributeError, TypeError)` SILENT geschluckt wurde. Resultat:
seit v0.67 (LocatorDB-Einfuehrung) kam **nichts** aus Live-Decodes in
die DB — sie wuchs nur durch ADIF-Bulk-Import beim App-Start.

**Fix:**
- `m.is_grid` ohne Klammern (Property-Zugriff)
- Zusatzfilter `not m.is_rr73 and m.field3 != "73"` — `RR73` matcht
  is_grid struktur-gleich (Letter+Letter+Digit+Digit), ist aber
  FT8-Bestaetigung nicht Locator
- `except` nur noch `AttributeError` — TypeError wuerde ab jetzt zum
  echten Bug-Symptom statt zu schweigen

**Tests:** `tests/test_feed_locator_db.py` neu mit 6 Regressions-Tests:
CQ-Message schreibt Locator, directed-Reply mit Grid (haeufigster Fall)
schreibt Locator, Report/RR73/73 schreiben NICHT, locator_db=None kein
Crash, leere Liste kein Call.

### Neues Feature — Auto-Save LocatorDB alle 5 Min

Mike-Anforderung: bei stundenlanger Empfangs-Session sammeln sich viele
Live-Locator-Daten an. Vorher wurde das nur bei sauberem `closeEvent`
persistiert — `kill_old_instances()` macht beim naechsten App-Start
SIGKILL, was closeEvent ueberspringt. Resultat: bei jedem Restart gingen
Live-Decodes der Session verloren.

**Loesung:** `ui/main_window.py:_init_locator_db_autosave()` —
QTimer alle 300 s ruft `locator_db.save()`. Atomic-Write (.tmp + replace)
im LocatorDB ist crash-sicher. War im v0.67-Plan bewusst rausgelassen
("Hobby-Funker-Konsens, App crasht selten") — bei Mike's tatsaechlichem
Use-Case (mehrstuendige Sessions + haeufige App-Restarts) jetzt
substanziell wertvoll.

### Map-Tooltip — Stations-Count Diff (Mike's Punkt 6)

Karte zeigte 37 Stationen mit Position obwohl rx_panel 46 dekodierte —
Diff sind Stationen ohne bekannten Locator (kein CQ-Empfang, kein
PSK-Spot, kein ADIF-Eintrag). Statt das Verhalten zu aendern: Tooltip-
Loesung am Status-Label.

`ui/direction_map_widget.py:update_rx_stations(stations, total_decoded=0)`:
- bei Diff: Status `"EMPFANG: 37 / 46 Stationen."` + Tooltip-Erklaerung
  ("X mit bekannter Position aus CQ/PSK/ADIF, Y dekodiert ohne Locator,
  Z gesamt")
- ohne Diff: Status wie bisher, Tooltip leer

`ui/main_window.py:_on_direction_map_snapshot` reicht
`total_decoded=len(snapshot)` durch.

### UI-Detail — Ant-Spalte im Normal-Modus

Mike-Wunsch: RX-Tabelle soll auch im Normal-Modus die Antenne zeigen
(nicht leer). Im Normal-Modus laeuft alles ueber ANT1 (hardcoded in
`_apply_normal_mode:1028`). `ui/mw_cycle.py:_handle_normal_mode` setzt
`antenna="A1"` statt `""` in `accumulate_stations()`. 1-Zeilen-Fix.

### Datenbasis nach v0.70

LocatorDB nach DA1MHH+DO4MHH-ADIF-Import:
- **7.991 unique Calls** in `~/.simpleft8/locator_cache.json` (854 KB)
- 4.768 mit 6-stelligem Locator (Praezision 5 km)
- 3.223 mit 4-stelligem Locator (Praezision 110 km)
- ab jetzt waechst die DB live mit jedem CQ + Antwort mit Grid

**Tests:** 416 → 422 (+6 Regressions-Tests).
**Workflow-Note:** Trivial-Fixes waren is_grid (1-Zeichen + Filter),
Auto-Save (10 Zeilen), Ant-Spalte (1-Zeichen), Tooltip (~10 Zeilen).
Kein V1→V2→V3-Workflow, keine DeepSeek-Codereviews — Trigger-Schwelle
nicht erreicht. Stattdessen Pre-Commit-Codereview bei v0.69 (Pulsier-
Logik) bestaetigt: bei sauberem V3-Plan findet Pre-Commit-Review oft
nichts Wertvolles mehr.

### Diversity-Auswertung Stand 27.04.2026

- **40m FT8** (off-band ANT1 Trap-Dipol): Diversity Standard +88 %,
  Diversity DX +124 % vs Normal — robuste Datenbasis (~22.700 Zyklen)
- **20m FT8** (resonant ANT1): Diversity Standard −23 %, Diversity DX
  −33 % — Datenbasis duenn (~3.000-3.600 Zyklen je Modus, schiefe
  Stunden-Verteilung), Aussage wackelt noch

Test-Roadmap fuer Heuristik-Validierung in TODO.md festgehalten:
17m/12m/80m (off-band), 15m (resonant) → bei n=5 Baendern entscheiden
ob neutraler Info-Tooltip implementiert wird oder App neutral bleibt.

---

## 2026-04-27 v0.69 — Propagations-Trend-Pulsieren

> ⭐ **WICHTIG fuer kuenftige Sessions:** dieser Eintrag dokumentiert
> das **Bandoeffnungs-/Bandschliessungs-Pulsations-Feature** unter den
> Band-Buttons. **NUR das aktive Band pulsiert** — andere Baender springen
> nur in der Farbe um. Pulsation = weicher Cross-Fade Ist-Farbe ↔ Trend-
> Farbe. Triggert 60 Min vor Wechsel an Saison-Fenster-Boundary
> (`core/propagation.py:_SEASONAL_SCHEDULE`). Live-PSK-Daten oder externe
> APIs sind dafuer NICHT noetig — alles laeuft aus HamQSL + lokaler
> Saison-Heuristik. Wenn jemand nochmal anfaengt einen „Live-Band-Indikator"
> mit PSK-Reporter zu planen: stop, das System ist schon da.

**Betroffene Dateien:** `core/propagation.py`, `ui/control_panel.py`,
`ui/main_window.py`, `ui/mw_radio.py`, `tests/test_propagation_trend.py` (neu),
`main.py`, `CLAUDE.md`.

### Problem (Mike-Anfrage 27.04.2026)
Mike wollte bei den Propagations-Farbbalken unter den Band-Buttons ein
visuelles Signal wenn in der naechsten Stunde eine Bandoeffnung oder
-schliessung bevorsteht. Hartes Blinken wurde explizit abgelehnt
(„kriegt man einen an der Murmel"). Loesung: weicher Cross-Fade
zwischen Ist-Farbe und Trend-Farbe — beruhigend, nicht nervtoetend.

### Workflow (V1 → V2 → V3 → Plan-Mode → Implementation)
Mehrstufiger Prompt-Workflow gemaess CLAUDE.md durchlaufen:
1. **V1:** erster Prompt-Entwurf (Claude). Datei:Zeile-Refs verifiziert
2. **V2 (Self-Review):** drei eigene Findings korrigiert — Drift-Risk
   `get_conditions_at(0)` ↔ `get_conditions()`, Bandwechsel-Lag (60s),
   Anim-Restart-Flacker-Risk. Lookahead-Granularitaet von Stunden auf
   Minuten umgestellt.
3. **V3 (DeepSeek-Review):** DeepSeek fand 2/9 Punkte berechtigt
   (KISS-Reuse via `if minutes_ahead==0`, Single-Animation statt
   SequentialGroup). 1× Halluzination — DeepSeek behauptete
   `_apply_seasonal_correction` existiere nicht (existiert bei
   `core/propagation.py:113`). Mike's CLAUDE.md-Warnung bewahrheitete sich.
4. **Plan-Mode:** Plan-Datei erstellt + genehmigt
5. **Pre-Commit-Codereview** vor Commit 3: DeepSeek fand 7 Punkte —
   ALLE als falsch/over-defensiv eingestuft (Threading-Spekulation
   verifiziert: alles GUI-Thread; State-Vergleich missverstanden
   als QColor.rgba() statt String-Tupel; bereits stop+start_pulse-
   Sequenz nicht erkannt). Keine Aenderungen uebernommen.

### Architektur

**Hook A — `core/propagation.py`:** neue Public-API
`get_conditions_at(minutes_ahead: int = 0) -> Optional[Dict[str, str]]`.
- minutes_ahead=0 → `_evaluate_conditions(raw)` reuse (drift-frei)
- minutes_ahead>0 → `target = now + timedelta(minutes_ahead)`,
  day/night-Flag und `_apply_seasonal_correction` mit verschobenem
  `utc_hour`/`month`
- `get_conditions()` als 1-Zeilen-Wrapper

**Hook B — `_PulseBar` Custom Widget (control_panel.py):**
QFrame+setStyleSheet ist nicht mit QPropertyAnimation kompatibel.
Loesung: QWidget-Subclass mit `color`-QProperty (QColor) + paintEvent
mit drawRoundedRect. Ersetzt 2× QFrame in `_ModeBandCard.prop_bars`.
Reines Refactor (Commit 2 isoliert): Tests bleiben gruen.

**Hook C — Trend-Logik (`_ModeBandCard.update_propagation`):**
- neue Signatur `(conditions, active_band: Optional[str] = None)`
- pro Band:
  - inaktives Band ODER `cond_now == "grey"` → statisch + `_stop_pulse`
  - aktives Band: `cond_30/cond_60 = get_conditions_at(30/60)`
  - `cond_now == cond_60` → statisch + `_stop_pulse`
  - `fast = (cond_30 != cond_now AND cond_30 == cond_60)`
  - State-Vergleich `_pulse[band]['state'] == new_state` →
    `continue` (kein Restart-Flacker beim 60s-Polling)
  - sonst: `_stop_pulse` + `_start_pulse`
- `_start_pulse`: einzelne QPropertyAnimation mit 5 Keyframes
  (a → a-hold → b → b-hold → a) + InOutSine + LoopCount(-1)
- `_stop_pulse`: idempotent via `pop+deleteLater`
- Cycle-Times: slow 3 s/1 s, fast 1.5 s/0.5 s

**Hook D — `ui/main_window.py:525`:** `active_band=self.settings.band`
durchreichen an `update_propagation`.

**Hook E — `ui/mw_radio.py:_on_band_changed`:**
`self._update_propagation_ui()` direkt vor dem Diversity-Branch —
verhindert 60s-Lag bis zur naechsten Animation-Aktualisierung.

### Tests
411 → 416 (+5 in `tests/test_propagation_trend.py`):
- T1 `test_get_conditions_at_zero_equals_now` — Reuse-Verifikation
- T2 `test_get_conditions_at_60min_band_opens` — 40m winter
  open_h=14, FakeDatetime auf 13:30 UTC: now=poor, +60=good
- T3 `test_get_conditions_at_returns_none_without_cache`
- T4 `test_pulse_started_only_for_active_band` — nur active_band
  hat laufende `QAbstractAnimation.State.Running`
- T5 `test_no_pulse_when_trend_equals_now` — kein Trend → kein Pulse

### Out-of-Scope (bewusst)
- HamQSL Polling-Intervall reduzieren (3 h bleibt)
- Trend-Animation fuer NICHT-aktive Baender
- Sonnensturm-Notfall-Indikator / orange Sonderfarbe
- >2 Geschwindigkeitsstufen
- Alpha-Pulsation oder Glow-Effekte

### Lehre fuer kuenftige V3-Workflows
Bei Pre-Commit-Codereview kann DeepSeek auch dann nichts Wertvolles
finden, wenn V1→V2→V3 sauber durchlaufen ist. Die echten Funde kamen
bei der Plan-Phase (V3). Pre-Commit nur dann nochmal lohnenswert wenn
sich die Implementation gegenueber dem Plan deutlich aendert. Sonst:
einsparen, Tests gruen reichen.

### Field-Test BESTANDEN ✅ (28.04.2026)
Mike hat den Bandwechsel-Pulse auf 40m im Feld gesehen — Cross-Fade
zwischen Ist-Farbe und Trend-Farbe funktioniert. Damit ist auch die
Diskussion vom 28.04. (Mike's „Live-Band-Indikator"-Wunsch, der
faelschlich als neues Feature B geplant wurde) endgueltig erledigt:
das System ist da, sichtbar, und tut was es soll.

---

## 2026-04-25 v0.59 — CQ-Freq Praxis-Tuning (3 Punkte + 1 Bug-Fix)

**Betroffene Dateien:** `core/diversity.py`, `ui/mw_cycle.py`, `ui/main_window.py`, `ui/control_panel.py`, `tests/test_modules.py`, `main.py`

### Problem (Mike-Beobachtung am Radio, v0.58 nach Feldtest)
v0.58 hatte 5 Sub-Tasks A-E + DeepSeek-Fixes — mechanisch sauber, aber funkpraktisch nicht. Drei Punkte mussten Punkt-für-Punkt überarbeitet werden:

1. Fester Sweet-Spot 800-2000 Hz war Quatsch — TX landete am leeren Rand statt bei der Aktivität
2. Algorithmus blieb bei vollem Band auf alter (jetzt vollen) Position hängen
3. Timer-Anzeige sprang chaotisch wegen elapsed-time-Logik die nur bei messages != [] tickte

### Punkt 1 — Suchbereich dynamisch (Commit 334a246)

`SWEET_SPOT_MIN_HZ` / `SWEET_SPOT_MAX_HZ` Klassenkonstanten entfernt. Suchbereich pro Cycle berechnet aus `min(occupied_bins)..max(occupied_bins)` + `SEARCH_MARGIN_BINS`. Median über alle Stationen, Sticky-Check folgt dem dynamischen Bereich.

### Punkt 1b — Graduelle Lücken-Toleranz für volles Band (Commit c4fa032)

Bei 70+ Stationen gab's keine Lücke ≥150 Hz mehr → `None` → kein Wechsel → TX hängte fest. Fix: stufenweise `(max_count_per_bin, min_gap_bins)` Toleranz:
- (0, 3) Standard 150 Hz echt frei
- (0, 2) 100 Hz echt frei
- (0, 1) 50 Hz echt frei (Notfall)
- (1, 3) 150 Hz mit max 1 Stat./Bin (Sehr-Notfall)
- (1, 2) 100 Hz mit max 1 Stat./Bin (Extreme)

Score-Funktion erweitert: Stationen IM eigenen Bin (`n_self`) kosten 100 Hz pro Station (schlimmste Kollision). Damit landet TX in der Notfall-Stufe NICHT auf einer Station.

### Punkt 1c — SEARCH_MARGIN_BINS = 0 (Commit 419ab52)

Mike-Beobachtung: TX landete rechts von der letzten Station weil Margin = 2 den Bereich künstlich um 100 Hz erweiterte. Margin auf 0 = exakt min..max der Stationen.

### Punkt 3 — Slot-Counter + Histogramm-Refresh jeden Slot (Commit af9dfb8)

Mike's Idee 1:1: einfacher Loop `x = 60: tick: x-1: if x=0 then suche: reset`. DeepSeek bestätigte: Variante "Slot-Counter" ist sauberer als Wallclock-basierte Lösung (kein Drift, friert bei App-Pause korrekt ein).

`core/diversity.py`:
- `_SEARCH_INTERVAL_SLOTS = {"FT8": 4, "FT4": 8, "FT2": 16}` (=~60 s alle Modi)
- `_CYCLE_S` lookup für Sekunden-Umrechnung
- `tick_slot()` -> bool, dekrementiert + auto-reset
- `seconds_until_search` property = `remaining_slots * cycle_s`
- `set_mode()` macht harten Reset des Counters
- `update_proposed_freq()` vereinfacht: keine elapsed-time-Logik mehr (40 Zeilen Code raus)
- Entfernt: `_min_dwell_s`, `_recalc_interval_s`, `_last_check_time`, `_last_change_time`, `_last_recalc_time`

`ui/mw_cycle.py`:
- Neue Methode `_refresh_diversity_freq_view()` läuft JEDEN Slot in `_on_cycle_decoded`, UNABHÄNGIG vom messages-Inhalt → fixt P1 (Histogramm-Update Guard) implizit
- `sync_from_stations` + `tick_slot` + ggf. `update_proposed_freq` + UI-Update
- Doppel-Calls in `_handle_diversity_operate` entfernt

`ui/main_window.py`: `_tick_cq_countdown` liest `seconds_until_search`.
`ui/control_panel.py`: ProgressBar Range 0-15 → 0-60, Farbschwellen 5/10 → 15/30.

### Tests
197 (v0.57) → 211 grün. Test-Anpassungen pro Punkt:
- Punkt 1: 4 Tests umgeschrieben (Sweet-Spot statisch → dynamisch), 1 neu
- Punkt 1b: 3 Tests umgebaut (Erwartung "None" → "findet immer Position")
- Punkt 3: 5 alte Tests (`_min_dwell_s`, Kollisions-Logik) durch 4 neue (`tick_slot`, `seconds_until_search`, QSO-Schutz) ersetzt

### Funkpraktisch
- 60 s konstant für alle Modi (DeepSeek + Internet-Konsens: < 30 s killt QSO-Aufbau)
- Suche slot-synchron, keine Wallclock-Drift
- Anzeige tickt ehrlich 60→0
- Kein QSO mehr verloren weil TX hängt: Algorithmus findet IMMER eine Position (notfalls mit ≤1 Station drumherum)

### Atomare Commits
- `334a246` Punkt 1 (dynamischer Suchbereich)
- `c4fa032` Punkt 1b (graduelle Toleranz)
- `419ab52` Margin = 0
- `af9dfb8` Punkt 3 (Slot-Counter + P1-Fix)

---

## 2026-04-25 v0.58 — CQ-Frequenz-Algorithmus Score-basiert (Sweet-Spot 800-2000 Hz)

**Betroffene Dateien:** `core/diversity.py`, `tests/test_modules.py`, `ui/mw_radio.py`, `main.py`

### Änderungen

**`core/diversity.py` — fünf Sub-Tasks (A-E):**
- **A) Score-Funktion `_score_gap()`**: ersetzt die Median-Distance-Auswahl. Score = Lückenbreite (Hz) − 50·n_close − 25·n_near − 0.01·median_distance_hz. Lückenbreite dominiert, Nachbarn in ±1 Bin kosten 50 Hz pro Station, Nachbarn in ±2 Bins halb so viel; Median-Distance ist nur Tiebreaker.
- **B) Fester Sweet-Spot 800-2000 Hz** (`SWEET_SPOT_MIN_HZ`/`MAX_HZ`): TX-Frequenz wird nur noch im Sweet-Spot gewählt, nicht mehr dynamisch um die belegten Bins herum. Median wird nur über Stationen IM Sweet-Spot berechnet (sonst Verzerrung). Sweet-Spot komplett leer → Mitte als Default-Median.
- **C) `set_mode(mode)` API + modus-abhängige Dwell**: FT8=4 Zyklen, FT4=8, FT2=16 → ~60 s einheitlich. Recalc = 5 × Dwell → ~300 s. `_min_dwell_s` und `_recalc_interval_s` werden modus-abhängig gesetzt; Klassenkonstanten `MIN_DWELL_S`/`RECALC_INTERVAL_S` bleiben als Fallback-Defaults.
- **D) Verfeinerte Kollisionserkennung**: alte Schwelle `>=3 Nachbarn in ±1 Bin` ersetzt durch `n_direct >= 2 ODER n_in_band >= 3` (n_in_band inkl. current_bin). Schlägt früher an wenn Nachbarsignale auftauchen.
- **E) Sticky Gap mit reset()-Fix**: `_current_gap_width_hz` neu im State, in `reset()` auf 0 gesetzt. Sticky bleibt bei aktueller Frequenz solange sie im Sweet-Spot ist, keine Kollisions-Schwelle erreicht und neue Lücke nicht > +50 Hz breiter ist. `_measure_gap_around()` misst die echte aktuelle Lücke nach Sticky-Hit (sonst veralteter Vergleichswert).

**`ui/mw_radio.py` — `set_mode()` Aufrufe:**
- `_on_mode_changed()`: nach `self.settings.set("mode", mode)` und `self.timer.set_mode(mode)` neu `self._diversity_ctrl.set_mode(mode)` aufgerufen.
- `_on_radio_connected()`: nach `_ntp.set_mode(mode, band)` neu `self._diversity_ctrl.set_mode(mode)` für Verbindungs-Initialisierung.

**`main.py`:**
- `APP_VERSION = "0.57"` → `"0.58"`

### DeepSeek-Review (deepseek-chat, thinking high)
3 Issues gefunden, alle gefixt vor Release-Bump:
1. **HIGH** — Sticky-Schwelle (`n_direct >= 3`) und Kollisions-Schwelle (`n_direct >= 2 ODER n_in_band >= 3`) waren inkonsistent → bei n_direct == 2 verpuffte Kollision ohne Frequenzwechsel. Fix: Sticky übernimmt die Kollisions-Schwelle exakt.
2. **MEDIUM** — Sticky-Pfad refreshte `_current_gap_width_hz` nicht → bei aufeinanderfolgenden Sticky-Hits Vergleich gegen veralteten Wert. Fix: neue Helper `_measure_gap_around(bin_idx)` aktualisiert die echte Lück-Breite im Sweet-Spot.
3. **LOW (Test)** — `test_collision_2_in_direct_neighbors` prüfte nur `_last_change_time`. Mit dem HIGH-Fix nun stärker: prüft Frequenz-Wechsel.
4. **CRITICAL (defensiv)** — `update_proposed_freq` greift auf `self._freq_histogram` ohne Lock zu. Aktuell sicher (sync läuft im selben Thread), aber `dict()`-Snapshot kostet nichts und schützt vor zukünftigen Threading-Änderungen.

### Tests
197 → 211 grün (14 neue: 3 Score, 2 set_mode, 6 Sticky, 2 Kollision, 1 QSO-Schutz). Plan im Prompt sagte "≥214" — Rechenfehler im Prompt (14 + 197 = 211, nicht 214).

### Atomare Commits
- `b7a06b5` Sub-Task A+B (Score + Sweet-Spot)
- `b15c62a` Sub-Task C (modus-abhängige Dwell + set_mode())
- `255b0f9` Sub-Tasks D+E (Kollision + Sticky + reset()-Fix)
- `06afbd8` DeepSeek-Review-Fixes (Logik-Konflikt + Sticky-Width + Test + Threading)
- `___` (dieser Commit) Release-Bump 0.58 + HISTORY/TODO/CLAUDE

---

## 2026-04-25 v0.57 — Answer-Me Highlighting + Gain-Messung Logging

**Betroffene Dateien:** `ui/rx_panel.py`, `ui/mw_radio.py`, `main.py`

### Änderungen

**`ui/rx_panel.py` — Answer-Me visuell sichtbar machen:**
- Farbe `_COLOR_ANSWER_ME_BG`: `#2A1F00` (fast identisch mit Active-Call `#2A1500`) → `#5A4A10` (klares Gold) — endlich unterscheidbar im dunklen UI
- Bold-Logik in `_apply_active_highlight` (L268): `setBold(is_active)` → `setBold(is_active or is_answer_me)` — bei zyklischem Refresh
- Bold beim direkten Einfügen in `_populate_row` (L419-426) — Answer-Me ist sofort sichtbar, nicht erst nach dem nächsten Highlight-Refresh

**`ui/mw_radio.py` — Gain-Messung Logging:**
- Top-Level Import: `from pathlib import Path`
- Neue Methode `_log_gain_result(r, band, ft_mode)` am Klassenende: append-only Markdown-Eintrag in `~/.simpleft8/gain_log.md` mit UTC-Zeitstempel, Band, FT-Mode, Diversity/Standard-Scoring-Label, ANT1/ANT2-Gains, beste Antenne, ANT1/ANT2 Ø SNR
- Aufruf in `_on_dx_tune_accepted` direkt nach `_set_gain_measure_lock(False)` und VOR dem `if self._rx_mode == "normal":` Block — beide Modi (Normal-Kalibrierung + Diversity-Messung) werden geloggt
- Cancel/Reject loggt NICHT (Hook nur in `_on_dx_tune_accepted`, nicht `_on_dx_tune_rejected`)
- Format: menschenlesbares Markdown, Mike kann es im Editor öffnen für Drift-Analyse über Wochen/Monate

**`main.py`:**
- `APP_VERSION = "0.56"` → `"0.57"`

### DeepSeek-Review (deepseek-chat, thinking high)
0 Issues. Bold-Reset bei State-Übergängen sauber, defensive `r.get()`-Defaults verhindern KeyError, UTF-8 explizit für Ø-Zeichen, Hook-Position richtig vor early-return. `~/.simpleft8/` wird durch `main.py:18-19` zuverlässig angelegt. Threading nicht relevant (Qt-UI-Thread, eine App-Instanz).

### Tests
197 passed (keine Regression — kein App-Code in Test-Pfaden geändert, nur UI-Erweiterungen).

### Atomare Commits
1. `fix(ui): Answer-Me Highlighting — Farbe #5A4A10 + Bold an 3 Stellen`
2. `feat(radio): Gain-Messung Logging → ~/.simpleft8/gain_log.md`
3. `chore(release): bump APP_VERSION 0.56 → 0.57 + HISTORY + TODO`

---

## 2026-04-25 v0.56 — PDF S.3: Erklärung funkerverständlich (kein Jargon)

**Betroffene Dateien:** `scripts/generate_plots.py`, `auswertung/Auswertung-40m-FT8.pdf`, `auswertung/en/Report-40m-FT8.pdf`

### Hintergrund
S.3-Tabelle war für einen Funker-Leser nicht selbsterklärend: Spalte hieß "/Zyklus" aber Note sprach von "Stunden-Durchschnitt" → Widerspruch. Dazu Statistik-Jargon ("Pooled Mean") der außerhalb der Fachliteratur nicht bekannt ist.

### Änderungen
- Spaltenheader: `Ø Stat./Zyklus` → `Ø Sta./15s-Zyklus` (Zykluslänge explizit)
- `p3_header_subtitle`: "Pooled Mean über alle Messtage" → "Tagesdurchschnitt über 4 Messtage, alle Tageszeiten"
- `p3_note1`: Klar auf Deutsch: "So viele Stationen pro 15s-Zyklus im Schnitt, gemittelt über alle Messpunkte aus 4 Messtagen und allen Tageszeiten (morgens, mittags, abends). Das ist der echte Tagesdurchschnitt — kein Filter."
- `p1_summary_body` (DE+EN): "Pooled Mean" → "Durchschnitt über alle Messpunkte, 4 Messtage, alle Tageszeiten"
- PDFs (DE+EN) neu generiert und gepusht

---

## 2026-04-25 v0.56 — Statistik-Korrektur: Pooled Mean global (kein Stunden-Filter)

**Betroffene Dateien:** `scripts/generate_plots.py`, `CLAUDE.md`, `README.md` (DE+EN), PDFs regeneriert

### Hintergrund
Session 2 hatte `_combo_summary_fair()` mit (date,hour)-Schnittmenge implementiert — dies lieferte +35.5%/+58% statt +88%/+123%. Ursache: Mike hat nur ein Funkgerät und kann nie zwei Modi gleichzeitig am selben Tag und in derselben Stunde messen. Die 18–21 gemeinsamen Slots waren ein nicht repräsentativer Bias. Richtige Methodik: alle Zyklen aller Messtage direkt poolen — kein Stunden-Filter. Mike: "du nimmst alle daten standart und teilst die ergebnisse durch die anzahl der erfassten tage... egal welche stunde welche bedingungen."

### Änderungen

**`scripts/generate_plots.py`:**
- `_combo_summary_fair()` vereinfacht: wrapper um `_combo_summary()`, gibt `n_avg_common = Normal.avg` zurück — keine (date,hour)-Schnittmenge mehr
- `_r_ergebnisse_page()`: Spalte "Gem. Stunden" → "Mess-tage" (zeigt `n_days`)
- TEXTS (DE+EN): p3_header_subtitle, p3_col_labels, p3_note1 — klar erklärt was Ø Stat./Zyklus bedeutet: "typischer Stunden-Durchschnitt eines ganzen Messtages, über alle Tage und Tageszeiten gepoolt". p1_summary_body + p7_fazit_body: "zeitfaire Auswertung / gemeinsame Messtunden" → korrekte Formulierung

**`README.md`:** Zahlen korrigiert: +36%/+57% → +88%/+122% (Std), +58%/+82% → +123%/+157% (DX), Spalte "Gem. Stunden" → "Tage"

**`CLAUDE.md`:** Statistik-Regel: Methodik-Text von "nur gemeinsame Stunden" auf "Pooled Mean global" korrigiert, Zahlenwert aktualisiert

### Git
- 1 Commit (Korrektur-Fix), Tests: 197 passed (kein Python-App-Code geändert)

---

## 2026-04-25 v0.56 — Statistik: Zeitfaire Auswertung (gemeinsame Stunden)

**Betroffene Dateien:** `scripts/generate_plots.py`, `CLAUDE.md`, `README.md` (DE+EN), `auswertung/Auswertung-40m-FT8.pdf`, `auswertung/en/Report-40m-FT8.pdf`

### Hintergrund
Die bisherige Ergebnistabelle (S.3) im PDF nutzte Pooled Mean über ALLE Zyklen, unabhängig von der Tageszeit. Das war methodisch problematisch: Wenn Normal tagsüber und Diversity DX abends gemessen wird, kann der Tageszeit-Effekt (Ausbreitung) die Zahlen verfälschen. Mike erkannte das Problem und stellte die Forderung: Nur Stunden vergleichen, in denen beide Modi gleichzeitig gemessen wurden.

### Änderungen

**`scripts/generate_plots.py`:**
- Neue Funktion `_combo_summary_fair(stats_dir, band, protocol)` — berechnet Pooled Mean nur über Stunden, in denen Normal UND der jeweilige Diversity-Modus gleichzeitig gemessen wurden. Für jede Diversity-Mode wird zusätzlich der Normal-Mittelwert auf dieselben Stunden eingeschränkt (`n_avg_common`) — dieser dient als fairer Referenzwert für Prozent-Vergleiche.
- `_r_ergebnisse_page()` (S.3): verwendet `fair_summary` statt `summary`. Spalte "Messtage" → "Gem. Stunden". `vs Normal` berechnet gegen `n_avg_common`.
- `_r_title_page()`, `_r_rescue_page()`, `_r_fazit_page()`: verwenden jetzt ebenfalls `fair_summary` für alle %-Angaben. `_r_methodik_page()` (S.2) behält globale Zyklenanzahlen.
- `create_pdf_report()`: berechnet `fair_summary` zusätzlich zu `summary`, leitet es an die richtigen Seiten weiter.
- TEXTS (DE+EN): p3_header_subtitle, p3_col_labels, p3_note1 aktualisiert. p1_summary_body + p7_fazit_body mit Methodik-Hinweis ergänzt.
- PDF-Umbenennung: `SimpleFT8_Bericht.pdf` → `Auswertung-40m-FT8.pdf` / `SimpleFT8_Report.pdf` → `Report-40m-FT8.pdf` (Band im Dateinamen für spätere Multi-Band-Erweiterung).

**Ergebnis 40m FT8 (22.618 Zyklen, 4–5 Tage):**
- Im aktuellen Datensatz haben alle Modi 24h Abdeckung → fair_summary = global_summary
- Zahlen: Diversity Standard +88%/+122%, Diversity DX +123%/+157% (ohne/mit Rescue)
- Methodik ist zukunftssicher: sobald Modi zu unterschiedlichen Tageszeiten gemessen werden, filtert `_combo_summary_fair()` automatisch korrekt

**`README.md` (DE + EN):**
- Tabelle: aktualisierte Zahlen (+88%/+123%), 22.618 Zyklen, neue Spalte "Gem. Stunden"
- Methodologie-Hinweis hinzugefügt (Stand 2026-04-25)
- PDF-Links auf neue Dateinamen aktualisiert

**`CLAUDE.md`:**
- Neue Sektion "⛔ Statistik-Veröffentlichung — Regel": Verbot anderer Bänder ohne Datenbasis (≥2 Tage, ganzer Tag), Hinweis auf gemeinsame-Stunden-Methodik und bekannte 40m-Ergebnisse

### Git
- 2 Commits, pushed to origin/main
- Tests: 197 passed (keine Regression — kein Python-Code in App geändert)

---

## 2026-04-25 v0.56 — RF-Power-Presets pro Band+Watt

**Betroffene Dateien:** `core/rf_preset_store.py` (NEU), `radio/base_radio.py`, `radio/flexradio.py`, `ui/main_window.py`, `ui/mw_tx.py`, `ui/mw_radio.py`, `ui/settings_dialog.py`, `tests/test_rf_preset_store.py` (NEU)

### Hintergrund
Closed-Loop FWDPWR-Feedback tastet pro Band/Watt-Wechsel von rfpower=50 hoch zur Zielleistung. Dauert 3–4 Zyklen (~45–60 s FT8) bis Konvergenz — schlecht für QSO-Erfolg, ineffizient. Mike hat den Wunsch geäußert, den konvergierten rfpower-Wert pro (Band, Watt-Stufe) zu persistieren, sodass beim nächsten Wechsel direkt der bekannte Wert geladen werden kann. System ist selbstheilend: bei Vereisung/Tauwetter/Kabelwackler überschreibt die nächste Konvergenz den alten Wert. IC-7300-Fork-tauglich durch separaten Top-Level-Key pro Radio.

### Architektur (5 Schichten)
1. **`core/rf_preset_store.py` (NEU):** `RFPresetStore` mit Hybrid-Lade-Strategie (exakter Treffer / lineare Interpolation+Extrapolation / None), atomic JSON-Write via `os.replace`, Plausibilitäts-Warnung bei >20% Δ zwischen gespeichert vs interpoliert, Migration aus altem `rfpower_per_band` (idempotent), Validierung 0 ≤ rf ≤ 100, `.bak.YYYYMMDD-HHMMSS` bei korruptem JSON.
2. **`radio/base_radio.py` + `flexradio.py`:** Klassen-Konstante `radio_type: str = "flexradio"` (ABC default `"unknown"`) — Top-Level-Key in `rf_presets.json`.
3. **`ui/main_window.py::_init_power_state`:** RFPresetStore-Instanz + neue `_was_converged` Hilfsvar + Migration-Aufruf.
4. **`ui/mw_tx.py`:** Neuer Helper `_apply_rf_preset()`, Lade-Trigger bei Watt-Wechsel mit Race-Schutz für alten (band, watts), Save-Trigger refactored mit `_was_converged` (1× pro Konvergenz-Zyklus), `settings.save_tx_power()` bleibt für Backward-Compat.
5. **`ui/mw_radio.py`:** Lade-Trigger an Bandwechsel + Radio-Connect.
6. **`ui/settings_dialog.py`:** Neue GroupBox "RF-Presets pro Band+Watt" — Tabelle (Band / Watt / RF / Letzte Speicherung), "Band löschen" + "Alle löschen" mit Bestätigungs-Dialog, Buttons disabled während aktivem TX (1 s Polling).

### Datenformat `~/.simpleft8/rf_presets.json`
```json
{
  "flexradio": {
    "40m": {"30": {"rf": 24, "ts": 1735203015.5},
            "80": {"rf": 67, "ts": 1735206015.0}}
  },
  "ic7300": {}
}
```

### DeepSeek codereview (deepseek-chat, thinking high)
1× Low-Severity Bug bestätigt: `getattr(...) or settings.get(...)` falsy-Trap bei watts=0 → ersetzt durch explizites `is None`-Check. Andere DeepSeek-Hinweise (kritisch laut Tool) waren False Positives — Reihenfolge in `_on_power_changed` ist korrekt (alter `_power_target` + alter `_rfpower_current` werden vor Settings-Update gespeichert).

### Tests 178 → 197 grün
Neue `tests/test_rf_preset_store.py` mit 19 Tests: exact_match, empty, interpolation, extrapolation oben/unten, single_point_fallback, overwrite, radio_isolation, clear_band, clear_all, plausibility_warning, corrupt_json+bak, atomic_write, invalid_rf, oscillation, band_change_isolation, range_clipping, migration, persistence.

### Atomare Commits
1. `feat(core): RFPresetStore — pro (radio, band, watt) konvergierten rf-Wert persistieren`
2. `feat(radio): radio_type Klassen-Konstante als Top-Level-Key`
3. `feat(tx): RFPresetStore in TX-Closed-Loop integriert (load + save bei Konvergenz)`
4. `feat(ui): SettingsDialog — Section "RF-Presets" mit Reset-Buttons`
5. `chore(release): bump APP_VERSION 0.55 → 0.56 + HISTORY + TODO`

### Out of Scope (für spätere Versionen)
- Polynom-/Spline-Fit über ≥3 Stützpunkte (KISS, linear reicht; bei IC-7300-Fork prüfen)
- Temperatur-/SWR-Tagging der Werte
- Auto-Detection Antennen-Tausch
- Event-Bus / RFPresetController-Schicht (Overengineering, direkter Aufruf in mw_tx genügt)

---

## 2026-04-25 — Prozess/Doku (kein Code-Change)

**Betroffene Dateien:** `CLAUDE.md`, `TODO.md`, `tests/test_modules.py`

### CLAUDE.md erweitert
- **Rollen** definiert: Mike = Ideengeber/Tester/Inspirator, Claude = Chef-Programmierer (verantwortlich für Code-Qualität, Struktur, Wartbarkeit)
- **Commits** Regel: lokale Commits autonom + atomar (1 Refactor/Feature/Bugfix = 1 Commit), `git push` nur auf explizite Anfrage
- **Architektur-Entscheidungen** Liste: was Mike vorgelegt wird (Modul-Auflösung, Pattern-Wechsel, Threading-Änderungen, Eingriffe in produktive Algorithmen ohne Tests, neue Abhängigkeiten, Breaking Changes) vs was Claude eigenständig entscheidet
- **Vor Commits**-Zeile ergänzt: Tests grün + DeepSeek-Review bei nicht-trivialen Änderungen (verweist auf §0)

### TODO.md PRIO HOCH (Stand 2026-04-25)
- **Punkt 1: Doku „UCB1 Bandit" korrigieren** — Code implementiert tatsächlich Median+8%-Schwelle, nicht UCB1. 5 Dateien betroffen (DIVERSITY_DE/EN, README_DE/EN, UEBERGABE). ~30 Min reine Doku.
- **Punkt 2: AP-Lite v2.2 Test-Pipeline** — vor jeglichem Code-Fix synthetische End-to-End-Tests bauen (FT8-Generator + AWGN). Erst dann zeigen Tests welche der 4 Verdachtspunkte echte Bugs sind. ~1-2 h.

### Tests aufgestockt 168 → 178
- 7 neue Tests für `core/diversity.py::_evaluate()`: Threshold-Verhalten, A1/A2-Dominanz, DX-Mode, Phase-Übergänge, Operate-Filter
- 3 neue Tests für AP-Lite v2.2: `_correlate` ohne Encoder, `_align_buffers` Costas-Reference, Costas-Pattern-Position

### DeepSeek V4-Setup
- DeepSeek V4 ist am 24.04.2026 erschienen (zwei Modelle: `deepseek-v4-flash`, `deepseek-v4-pro` Reasoning)
- `~/.claude/custom_models.json` neu angelegt für Pal-MCP-Routing
- `~/.claude/settings.json` aktualisiert: `permissions.defaultMode: "plan"`, `effortLevel: "xhigh"`, `model: "opusplan"`

---

## 2026-04-25 v0.55 — Refactoring: Mega-Methoden zerlegt

**Betroffene Dateien:** `ui/mw_cycle.py`, `ui/main_window.py`

### Hintergrund
DeepSeek V4-Pro (Reasoning-Modell, neu erschienen 24.04.) wurde für Architektur-Review hinzugezogen. V4-Pro identifizierte zwei Mega-Methoden als gröbste Verstöße gegen Lesbarkeit; Vorschlag: 1:1-Auslagerung in private Helper, ohne Verhaltensänderung. Drei weitere Refactoring-Kandidaten (flexradio.py aufsplitten, qso_state.on_message_received zerlegen, generate_plots.py modularisieren) wurden bewusst abgelehnt — premature abstraction, hohes Regressionsrisiko ohne Tests.

### Änderungen
- `ui/mw_cycle.py::_on_cycle_decoded()` von **276 Zeilen → 27 Zeilen**, 9 Helper extrahiert:
  - `_assign_slot_parity`, `_update_dt_correction`, `_pop_diversity_queue`
  - `_handle_diversity_measure`, `_handle_diversity_operate`
  - `_handle_normal_mode`, `_handle_dx_tune_mode`
  - `_run_ap_lite_rescue`, `_run_auto_hunt`
- `ui/main_window.py::__init__()` von **186 Zeilen → 42 Zeilen**, 12 Helper extrahiert:
  - `_apply_dark_theme`, `_init_core_components`, `_init_qso_log`
  - `_init_radio_state`, `_init_diversity_state`, `_init_power_state`
  - `_init_optional_features`, `_init_psk_polling`, `_init_propagation_polling`
  - `_init_presence_watchdog`, `_init_cq_countdown_timer`, `_init_statusbar`

### Garantien
- **Verhalten identisch:** alle 168 Tests grün vor und nach Refactoring
- **Reihenfolge erhalten:** alle State-Initialisierungen in Original-Sequenz
- **Bekannte Fallen unberührt:** Diversity-Transition-Guard `_diversity_in_operate`, Stats-Guard 3-fach (btn_cq + cq_mode + state), `cache.save()` nur in `_on_dx_tune_accepted`
- **Backup:** `Appsicherungen/2026-04-25_vor_mw_cycle_refactor/` (mw_cycle.py + main_window.py)

### Was NICHT angefasst wurde (begründete Ablehnung)
- `radio/flexradio.py` — 50 Methoden teilen TCP/UDP-State, kein Test, Aufsplittung wäre premature abstraction
- `core/qso_state.py::on_message_received` (157 L) — sitzt direkt im geschäftskritischen QSO-Pfad; keine Methodenebene-Tests, Refactoring ohne Schutznetz zu riskant
- `scripts/generate_plots.py` — Standalone-Script, kein Test, kein externer Mehrwert durch Modularisierung
- `ui/control_panel.py` Card-Klassen — sinnvoller nächster Schritt, aber 2 h Aufwand + Regressionsrisiko ohne UI-Tests; auf später vertagt

---

## 2026-04-23 (Abend) — DT-Timing vollständig korrigiert

**Betroffene Dateien:** `core/decoder.py`, `core/encoder.py`, `core/ntp_time.py`, `ui/mw_radio.py`

### Architektur-Änderung
- DT-Gesamtfehler (~0,77 s) in zwei Schichten aufgeteilt:
  - **Festwert** `DT_BUFFER_OFFSET` (FT8=2,0 / FT4=1,0 / FT2=0,8) — bekannte FlexRadio-Konstante, hardcodiert
  - **Adaptiv** `ntp_time.py` — konvergiert auf ~0,27 s Restfehler
- Vorteil: Kaltstart beginnt nahe am Zielwert, kleinerer Regelbereich → schnellere Konvergenz

### Bugfixes
- FT2 Even/Odd: `_slot_from_utc()` auf 3,8 s-Arithmetik korrigiert (war 7,5 s)
- Tune-Anzeige: `_tune_active` vor `set_frequency()` gesetzt
- PSK bei Bandwechsel: gelöscht + Timer-Reset + Interval 300 s (5 min Rate-Limit)
- Stats-Guard: pausiert bei CQ-Modus und laufendem QSO
- 15m Diversity: Preset laden oder Warnung "bitte KALIBRIEREN"
- 3 veraltete Tests auf neues Key-Format "FT8_20m" angepasst

### TX-Timing
- `TARGET_TX_OFFSET = -0,8 s` — kompensiert FlexRadio TX-Buffer 1,3 s
- Validiert: 8 Zyklen 0,0 s DT am Icom, 20m + 40m getestet

### Neue Docs
- `dt.md` erstellt (Theorie, Änderungen, Messergebnisse)

**Tests:** 167 passed

---

## 2026-04-23 (Nacht) — 3 kleine Features

**Betroffene Dateien:** `core/propagation.py`, `ui/mw_radio.py`, `core/station_accumulator.py`, `tests/test_modules.py`

### Features
1. **60m Propagation** — Interpolation 40m/80m war bereits implementiert, nur Docs angepasst
2. **RX-Liste leeren bei Antennen/Diversity-Wechsel** — `_on_rx_panel_toggled`, `_enable_diversity`, `_disable_diversity`
3. **Alte CQ-Rufe auto-löschen (>5 Min)** — neues Aging-Limit 300 s für CQ-Rufer in `station_accumulator.py`

### Tests
- `test_accumulator_aging` auf nicht-CQ-Message geändert
- Neuer Test `test_accumulator_cq_longer_aging`

**Tests:** 168 passed

---

## 2026-04-23 (Nacht II) — Stats-Guard Bug gefixt

**Betroffene Dateien:** `ui/mw_qso.py`, `core/qso_state.py`, `ui/mw_cycle.py`

### Root Cause (durch DeepSeek-Analyse gefunden)
In `_on_station_clicked` (manueller Klick auf Station während CQ):
1. `stop_cq()` setzte `cq_mode=False`
2. `start_qso()` speicherte `_was_cq = self.cq_mode = False` (schon False!)
3. Nach QSO-Ende: `_resume_cq_if_needed()` sah beide False → CQ wurde nicht resumed + Stats geloggt fälschlicherweise

### Fixes
- `mw_qso.py::_on_station_clicked` — `_cq_was_active` VOR `stop_cq()` sichern, nach `start_qso()` als `_was_cq=True` setzen
- `qso_state.py::_process_cq_reply` — `self._was_cq = True` explizit setzen
- `mw_cycle.py::_log_stats` — Guard um `btn_cq.isChecked()` erweitert (3-fach robust: Button + cq_mode + State)

**Tests:** 168 passed

---

## 2026-04-23 (Nachmittag) — Histogramm-Umbau + Bugfixes + Docs

**Betroffene Dateien:** `core/diversity.py`, `ui/mw_cycle.py`, `tests/test_modules.py`, `docs/`

### Architektur-Änderung: Histogramm 1:1 mit RX-Fenster

**Problem vorher:** Das Frequenz-Histogramm akkumulierte Daten über viele Zyklen und vergaß nie. Nutzer sah 5 Stationen im RX-Fenster, Histogramm zeigte 26 (historische Daten). Freie Frequenz wurde auf Basis veralteter Daten berechnet.

**Lösung:** Histogramm wird nach jedem Dekodierzyklus aus dem `station_accumulator` neu aufgebaut — exakt dieselbe Datenbasis wie das RX-Fenster. Der Accumulator hält Stationen 75–300 s (je nach Typ) und deckt damit automatisch mehrere Zyklen inkl. Even+Odd ab.

**Änderungen `core/diversity.py`:**
- `record_freq()` entfernt (akkumulierend, falsch)
- `_freq_histogram`, `_hist_lock` (threading.Lock) entfernt
- `_recalc_interval = 20` entfernt (tote Variable, nie gelesen)
- `import threading` entfernt
- `sync_from_stations(stations: dict)` neu — baut Histogramm 1:1 aus aktuellem Stationsstand
- `get_free_cq_freq()`: Search-Window auf vollen Bereich [150–2800 Hz] erweitert (vorher nur belegter Bereich)
- `get_free_cq_freq()`: Fallback-Bug gefixt — `None` statt Median-Frequenz wenn keine Lücke (Median lag mitten im belegten Bereich → Kollision → Oszillation)
- `update_proposed_freq()`: Lock in Kollisionserkennung entfernt
- `get_histogram_data()`: Lock entfernt
- `start_measure()`: `_freq_histogram = {}` entfernt (übernimmt sync_from_stations)

**Änderungen `ui/mw_cycle.py`:**
- Alle `record_freq()` Calls entfernt (3 Stellen: Messphase, Betriebsphase, Normal-Modus)
- Diversity-Betriebsphase: `accumulate_stations` kommt jetzt VOR Histogram-Update (war danach → Histogramm war einen Zyklus veraltet)
- `sync_from_stations(self._diversity_stations)` nach `accumulate_stations`
- Normal-Modus `_update_histogram()`: `sync_from_stations(self._normal_stations)`, `if messages:` Guard entfernt

**Änderungen `tests/test_modules.py`:**
- Hilfsfunktion `_make_stations(*freqs)` hinzugefügt
- 6 Tests von `record_freq()` auf `sync_from_stations()` umgestellt
- Assertions angepasst an neues Verhalten (Search-Window [150–2800]):
  - `test_cq_freq_high_activity`: prüft nun `freq < 1000 or freq > 2000` (Gap außerhalb des belegten Bereichs)
  - `test_cq_freq_stays_inside_occupied` → umbenannt in `test_cq_freq_finds_gap_outside_occupied`
  - `test_cq_freq_fallback_no_gap`: füllt jetzt alle Bins [150–2850 Hz], prüft `freq is None`

### Neue Docs (4 Dateien)
- `docs/FREQUENCY_HISTOGRAM.md` (EN) — Visualisierung, Algorithmus, Timing
- `docs/FREQUENCY_HISTOGRAM_DE.md` (DE)
- `docs/DT_CORRECTION.md` (EN) — Festwert + Adaptiv, Parameter, TX-Timing
- `docs/DT_CORRECTION_DE.md` (DE)

### CLAUDE.md + feierabend.md
- CLAUDE.md: Abschnitt "Änderungshistorie" + Verweis auf HISTORY.md ergänzt
- feierabend.md: Schritt 3 "HISTORY.md ergänzen" als Pflicht eingefügt

**Tests:** 168 passed

---

## 2026-04-24 — Workflow-Optimierung: opusplan als Standard

**Betroffene Dateien:** `~/.claude/settings.json`

### Änderung
- `"model": "opusplan"` dauerhaft in globaler Claude Code settings.json gesetzt
- **Verhalten:** Opus (claude-opus-4-7) übernimmt die Planungsphase, Sonnet (claude-sonnet-4-6) die Implementierung — automatisch, kein manueller Wechsel nötig
- **Grund:** Komplexere Aufgaben profitieren von Opus-Reasoning beim Planen, Sonnet ist für Code-Ausführung vollkommen ausreichend und schneller

---

## 2026-04-24 — Antennen-Label in TX-Zeilen des QSO-Panels

**Betroffene Dateien:** `ui/qso_panel.py`, `ui/mw_radio.py`, `ui/mw_qso.py`

### Feature
- TX-Zeilen im QSO-Panel zeigen jetzt Empfangsantenne + SNR-Delta:
  `11:47:00 [E] →  Sende   OE7RJV DA1MHH -23   ANT1 Δ7.0dB`
- Orange (Nachricht) + Grau (Label) auf einer Zeile — via `QTextCharFormat`
- Nur im Diversity-Modus, nur wenn `delta_db` bekannt
- CQ-Zeilen unverändert

### Technische Umsetzung
- `qso_panel.py::add_tx(message, ant_label="")` — rückwärtskompatible Erweiterung
- `qso_panel.py::_append_two_color()` — neue Hilfsmethode für zweifarbige Zeilen
- `mw_radio.py` — Lambda durch `self._on_tx_started` ersetzt (direkter Slot, sauberer)
- `mw_qso.py::_on_tx_started()` — liest `qso_sm.qso.their_call` + `_antenna_prefs.get_pref()`

**Tests:** 168 passed

---

## 2026-04-24 v0.48 — CQ-Freq nur noch im belegten Bandbereich

**Betroffene Dateien:** `core/diversity.py`, `tests/test_modules.py`

### Bugfix
- `get_free_cq_freq()` suchte bisher im vollen [150–2800 Hz] Fenster
- Resultat: TX landete bei 2125 Hz obwohl alle Stationen bei 400–1100 Hz clusterten
- **Fix:** Search-Window = `[min(belegte Bins) – 2, max(belegte Bins) + 2]`, geclippt auf absolute Grenzen
- 2-Bin Rand (100 Hz) damit auch die allererste/letzte Lücke knapp außerhalb noch gefunden wird
- Test `test_proposed_freq_updates` auf Stationen mit echter innerer Lücke umgestellt

**Tests:** 168 passed

---

## 2026-04-24 v0.53 — Diversity-Panel UI-Politur

**Betroffene Dateien:** `ui/control_panel.py`

### Fixes & Verbesserungen
- **Label:** "Diversity Neuberechnung in X Zyklen" (fehlende "in" ergänzt)
- **Zentrierung:** 36px Spacer links in phase_row balanciert NEU-Button → Text exakt mittig
- **Nähe:** `phase_row` ohne oberen Margin — Label näher an Ratio-Zeile
- **DX-Counts:** `35 DX  01 DX` Format (2-stellig, Leerzeichen vor "DX", `--` wenn kein Wert noch)
- **Balkenfarbe:** Dunkelrot `#882222` → Mittelrot `#CC3333` → Hellrot `#FF5555` (heller = dringender)
- **Hintergrund Balken:** `#1a1010` (passt zu Rotton statt Grün-Dunkel)

**Tests:** 168 passed

---

## 2026-04-24 v0.52 — CQ-Freq zeitbasiert + Platz-Suche-Balken + Antennenwahl-Label

**Betroffene Dateien:** `core/diversity.py`, `ui/control_panel.py`, `ui/mw_cycle.py`

### Features
- **Label-Umbenennung:** "Neucheck in X" → "Antennenwahl in X" — verständlich für Funker
- **Neuer Countdown-Balken:** "Platz-Suche in Xs" — zeigt wann die freie TX-Frequenz neu berechnet wird (Sekunden, schrumpfend 120→0)
- **CQ-Freq Timing zeitbasiert:** Statt zyklus-basiert (FT2: 10×3.8s=38s!) jetzt:
  - Zeit-Fallback: 120s (für alle Modi gleich — FT8/FT4/FT2)
  - Minimum Dwell: 15s (kein Bounce-Back bei Kollision)
  - Kollisionserkennung: jedes Zyklus prüfen, bei ≥3 Nachbarn + 15s Dwell reagieren

### Technische Details
- `diversity.py`: `import time` + `RECALC_INTERVAL_S=120`, `MIN_DWELL_S=15`
- `diversity.py`: `_cycles_since_recalc` → `_last_recalc_time` + `_last_change_time` (float Unix-Zeit)
- `diversity.py`: neues Property `seconds_until_recalc` → int 0–120
- `control_panel.py`: `_cq_freq_lbl` + `_cq_freq_bar` im AntCard, Proxy in ControlPanel
- `control_panel.py`: neue Methode `update_cq_freq_countdown(remaining_s)`
- `mw_cycle.py`: 3 Aufrufstellen ergänzt (measure, operate, normal)

**Tests:** 168 passed

---

## 2026-04-24 v0.51 — Diversity Countdown-Balken + besseres Label

**Betroffene Dateien:** `ui/control_panel.py`

### Feature
- OPERATE-Phase: Label `"Neu in X Zyklen"` → `"Neucheck in X"` (verständlich für den Funker)
- Neuer schmaler Countdown-Balken (6 px) unter dem Label — schrumpft von 60→0
- Farbwechsel synchron mit Text: grün (>15), gelb (≤15), orange (≤5)
- Balken verschwindet automatisch in MESSEN- und NEUEINMESSUNG-Phase
- `QProgressBar` mit dynamischem Stylesheet, kein Custom-Widget nötig
- Proxy-Anbindung über `ant_card._operate_bar` in `ControlPanel.__init__()`

**Tests:** 168 passed

---

## 2026-04-24 v0.50 — freq_label Farbwechsel Grün ↔ Gelb (Tune-Feedback)

**Betroffene Dateien:** `ui/control_panel.py`, `ui/mw_radio.py`, `ui/mw_tx.py`

### Feature
- `freq_label` (oben links) zeigt Frequenz jetzt farbcodiert:
  - **Normal:** Grün (#00CC66) + Arbeitsfrequenz
  - **Tune aktiv:** Gelb (#FFD700) + Tune-Frequenz (z.B. -2 kHz Offset)
- Neue Methode `control_panel.set_freq_display(freq_mhz, tune_active=False)` — zentrales Farb-Update
- `_update_frequency()` delegiert an `set_freq_display()` (Band/Mode-Wechsel → automatisch Grün)
- `_on_mode_changed()` in mw_radio.py → `set_freq_display(..., False)`
- `_on_tune_clicked()` in mw_tx.py → `set_freq_display(..., True/False)` je nach Tune-State
- Tune-Sonderfall `tune_freq=None` (60m ohne Offset) → Gelb + Arbeitsfreq (korrekt)

**Tests:** 168 passed

---

## 2026-04-24 v0.49 — Versionsanzeige UI automatisch synchron

**Betroffene Dateien:** `ui/control_panel.py`, `main.py`

### Fix
- Versionsanzeige unten rechts zeigte hardcodiert "v0.26"
- `control_panel.py` importiert jetzt `APP_VERSION` aus `main.py`
- Label: `f"SimpleFT8 v{APP_VERSION}"` — ab jetzt automatisch korrekt
- `main.py` APP_VERSION auf 0.49 erhöht

**Tests:** 168 passed

---

## 2026-04-24 v0.54 — CQ-Freq Countdown sekündlich + glatt

**Betroffene Dateien:** `core/diversity.py`, `ui/control_panel.py`, `ui/mw_cycle.py`, `ui/main_window.py`

### Problem vorher
Countdown sprang z.B. 119→108→119 weil per-Zyklus-Updates die 120s-Range unregelmäßig aktualisierten (FT8=15s, FT4=7.5s, FT2=3.8s). Kein gleichmäßiges Runterzählen.

### Lösung
- **Neues Property `seconds_until_next_check`** in `diversity.py` — zählt 15→0 ab `_last_check_time`
- **`_last_check_time`** in `reset()` ergänzt; in `update_proposed_freq()` gesetzt:
  - Bei Erstberechnung
  - Jedes Mal wenn MIN_DWELL_S abgelaufen ist (ob Kollision oder nicht) → Display immer zurück auf 15
- **1-Sekunden QTimer** (`_cq_countdown_timer`) in `main_window.__init__()` → `_tick_cq_countdown()`
  - Aktiv nur wenn `_rx_mode == "diversity"` und `cq_freq_hz is not None`
  - Sonst: Widget ausgeblendet via `set_cq_countdown_visible(False)`
- **3 per-Zyklus-Calls** `update_cq_freq_countdown()` aus `mw_cycle.py` entfernt
- **Range** 0-120 → 0-15, Label: `"Prüfe nächste freie TX Frequenz in: X Sek."`
- **Neue Methode** `control_panel.set_cq_countdown_visible(bool)`
- **Farb-Schwellen** angepasst: ≤5s → #FF5555, ≤10s → #CC3333, sonst #882222
- **Hintergrund** korrigiert: `#1a1010` (war fälschlich `#1a2a1a`)

**Tests:** 168 passed

---

## 2026-04-24 v0.54 — README Antennenfotos + Transparenz-Caveat + PDF-Update

**Betroffene Dateien:** `README.md`, `scripts/generate_plots.py`, `docs/fotos/`

### README
- Neue Sektion "Antenna Setup" / "Antennensetup" (DE+EN) mit 2 Fotos:
  - `docs/fotos/Gesamt.png` — Gesamtansicht Haus, beide Antennen sichtbar
  - `docs/fotos/Gesamt_Farbe.png` — Annotiert: Gelb=ANT1, Rot=ANT2
- ANT1: Kelemen DP-201510, vertikal gespannter Mehrband-Halbwellendipol (20m/15m/10m),
  Einspeisepunkt an Dachgaube, 1:1-Balun, ein Arm hoch zur Dachspitze, einer runter
- ANT2: Regenrinne ~15m L-Form (5m waagerecht + 8m senkrecht + 2m waagerecht),
  zwischen λ/4 und λ/2 für 40m, nie als Antenne installiert — einfach angeklemmt
- Rohdaten-Link: `statistics/` Ordner (214 Dateien, jeder Zyklus geloggt)
- Messtage aktualisiert: 11.896 → 18.425 Zyklen, 3-4 → 4-5 Messtage

### Transparenz-Caveat (DE+EN, README + PDF)
- ANT1 auf 40m außerhalb Auslegungsband (20m/15m/10m) → suboptimal
- ANT2 (Regenrinne) auf 40m günstiger durch Länge/Form → erklärt großen Gewinn
- Ergebnisse als Obergrenze deklariert — nicht übertragbar auf andere Setups
- 20m-Folgetests angekündigt (ANT1 dort resonant, 20m generell besser)

### generate_plots.py PDF-Texte
- `p1_caveat`: Antennencaveat auf Titelseite (DE+EN)
- `p2_setup_body`: "mornings only" entfernt, aktueller Tagesbereich 05-23 UTC
- `p3_note2`: Obergrenze-Hinweis bei Ergebnistabelle (DE+EN)
- `p7_cannot_body`: Übertragbarkeit explizit verneint (DE+EN)
- `p7_next_body`: 20m-Folgetests angekündigt (DE+EN)
- "über beide Messtage" → "über alle Messtage" (DE+EN)

### Strategie für weitere Datensammlung
- Abfrage alle 2-3h welcher Modus die dünnste Abdeckung hat
- Ziel: Lücken bei 15-23 UTC für alle drei Modi schließen
- Diversity Standard als nächstes (14-16 UTC, 15h+16h = je 1 Tag)

**Tests:** 168 passed

---

## 2026-04-25 v0.54 — 20m Messungen gestartet + Nachtdaten Diversity DX

**Keine Code-Änderungen — nur Datensammlung**

### Datenlage Stand 25.04.2026 Vormittag
- **Diversity DX 40m**: Nachtlücke geschlossen — 15 neue Stunden (18–09 UTC)
- **20m gestartet**: Normal + Diversity parallel zu 40m
- **40m gesamt**: 22.251 Zyklen (Normal 6.793 / Div.Standard 6.542 / Div.DX 8.916)

### Strategie
- Alle 2-3h Modus prüfen, Lücken in Berliner Zeit (CEST=UTC+2) schließen
- 40m Restlücken: 08 CEST (Div.Standard), 12-13 CEST (Div.Standard), 21-23 CEST (Normal+Div.Standard)
- 20m: Tagsüber Normal sammeln, dann Diversity

**Tests:** 168 passed

---

## 2026-04-25 v0.56 — Session-Abschluss: Doku, Refactoring, Prompt v0.57

**Keine neuen Features — Version bleibt 0.56**

### Code-Änderungen
- `ui/mw_cycle.py`: CycleMixin refactored — `_on_cycle_decoded` in 5 Helper-Methoden
  aufgeteilt (`_assign_slot_parity`, `_update_dt_correction`, `_pop_diversity_queue`,
  `_handle_diversity_measure`, `_handle_diversity_operate`). Gleiche Logik, besser lesbar.
- `tests/test_modules.py`: 8 neue Tests — 7× `DiversityController._evaluate`
  (Median+8%-Schwelle, A1/A2-Dominanz, DX-Mode, Phase-Übergänge) + 1× AP-Lite
  `_build_costas_reference` Energie-Test. **197 passed** (vorher 168→178→197).

### Doku & Prozess
- `feierabend.md`: Explizit "ALLE Ergänzungen der Session in HISTORY.md" ergänzt
- `CLAUDE.md`: Rollen + Commit-Richtlinien + DeepSeek-V4-Warnung (neues Modell,
  Antworten kritisch prüfen) + Tests→197 aktualisiert
- `TODO.md`: RX-Sortierung als [x] (war bereits implementiert), Per-Station DT-Offset
  auf PRIO NIEDRIG, vermutlicher Bug TX-Freq Normal-Modus als offener Punkt eingetragen,
  Band Map gestrichen, RF-Presets als [x] abgehakt

### Statistiken & Auswertung
- Neue Messungen 25.04.2026: Diversity_Normal/40m (09–12h), Diversity_Dx/40m (08–14h),
  Diversity_Dx/20m (12–15h), Diversity_Normal/20m (12–15h), Normal/20m (12–15h) UTC
- PDFs neu generiert: `auswertung/SimpleFT8_Bericht.pdf` (DE) +
  `auswertung/en/SimpleFT8_Report.pdf` (EN) mit allen 25.04-Daten

### Nächste Session — Implementierungs-Prompt v0.57 bereit
- Aufgabe 1: Answer-Me Highlighting — `rx_panel.py` Farbe `#5A4A10` + Bold an 3 Stellen
- Aufgabe 2: Gain-Messung Logging → `~/.simpleft8/gain_log.md`
- Prompt vollständig, DeepSeek-reviewed, commitbereit

## 2026-04-26 v0.60 — CQ-Counter QSO-Reset (Punkt 3)

**Problem (Mike's Feldbeobachtung):** Der 60s-Slot-Counter (`_search_slots_remaining`)
in `DiversityController` tickte auch waehrend aktivem QSO weiter. Wenn er auf 0 fiel,
wurde zwar via `qso_active=True` der Frequenzwechsel verhindert, ABER der Counter
wurde auto-resettet — danach konnte sehr bald (Restslots) wieder gewechselt werden.
Risiko: Frequenzsprung mitten im laufenden QSO.

**Fix:**
- `core/diversity.py`: neue Methode `reset_search_counter()` setzt
  `_search_slots_remaining` auf modus-spezifischen Vollwert (FT8=4, FT4=8, FT2=16).
- `ui/mw_cycle.py:_refresh_diversity_freq_view()`: bei `qso_busy=True` wird
  `reset_search_counter()` aufgerufen statt `tick_slot()`. Damit hat der Funker
  nach QSO-Ende immer volle ~60s Karenzzeit, kein Mid-QSO-Frequenzsprung mehr
  moeglich.
- Tests: 2 neue Tests (`test_reset_search_counter_restores_full_value` +
  `test_reset_search_counter_prevents_mid_qso_jump`). Suite 213 grün.

**DeepSeek-Review:** kritisch geprueft, "Critical Race Condition" verworfen
(das Pattern ist konsistent mit bestehendem `tick_slot()` — Lock haelt der Caller).
Andere Issues betrafen Pre-existing Code, nicht den Fix.

## 2026-04-26 v0.60 — Info-Box Normal-Preset alt (Punkt 1)

**Idee (Mike):** Beim Wechsel zum Normal-Modus soll ein Hinweis erscheinen wenn
das letzte Einmessen lange her ist. KALIBRIEREN-Button bleibt manuell —
nur eine Info-Box, kein Auto-Eingriff. Diversity bleibt das Alleinstellungs-
merkmal mit der vollen Auto-Pipeline.

**Implementation:**
- `ui/main_window.py:_init_radio_state()`: neues Set `_normal_preset_warned_bands`
  (pro Session/Band einmal warnen, kein Spam bei jedem Bandwechsel).
- `ui/mw_radio.py:_apply_normal_mode()`: bei `age_days > 30` → Info-Dialog mit
  Empfehlung den KALIBRIEREN-Button zu druecken. Bestehende 7-Tage-Markierung
  in `dx_info` (orange "Xd alt!") bleibt unveraendert.
- `_show_normal_preset_age_info()`: QMessageBox mit dem Dark-Theme der App.
- Aufrufstelle: `_apply_normal_mode()` wird bei App-Start, Bandwechsel und
  Modus-Wechsel zu Normal aufgerufen — Dialog greift an allen drei Stellen.
- Tests: 213 grün (UI-Dialog ohne Tests — manuelle Verifikation am Radio).

## 2026-04-26 v0.61 — Antenna-Pref Fix + Live-QSO-Anzeige

**Bug (Mike's Feldbeobachtung):** Im Diversity-Modus zeigte die RX-Liste fuer
viele Stationen 'A2>1' (ANT2 1 dB besser als ANT1) — beim Anrufen erschien aber
'(ANT1, +1.0 dB)'. Empfangsantenne wurde NICHT auf ANT2 umgeschaltet, der
Diversity-Vorteil ging verloren.

**Root Cause:** Hysterese in `core/antenna_pref.py` nutzte strict `>` statt `>=`.
Bei delta_db=+1.0 (sehr haeufiger Praxisfall, genau auf der 1-dB-Schwelle) fiel
der Code zurueck auf A1, obwohl der station_accumulator korrekt 'A2>1' geliefert
hatte. Inkonsistenz zwischen RX-Liste und Pref-Store.

**3-fach Fix:**

1. **Hysterese korrigiert** (`core/antenna_pref.py`):
   - `if delta > HYSTERESIS_DB` → `>=`. Bei delta=+1.0 wird jetzt korrekt A2 gewaehlt.
   - Docstring erweitert: Asymmetrie ist gewollt (A1=Default, nur A2 braucht Schwelle).

2. **Label-Format vereinheitlicht** (3 Stellen, alle DRY ueber `_antenna_pref_label`):
   - ANT1-Default: `(ANT1)` — schlicht, kein dB
   - ANT2 ueber Schwelle: `(ANT2 ↑X.X dB)` — Pfeil ↑ = Diversity-Gewinn
   - Statt verwirrendem `(ANT1, +1.0 dB)` (mehrdeutig) und `ANT1 Δ1.0dB` (kryptisch).
   - `_on_tx_started` (mw_qso.py) nutzt jetzt `_antenna_pref_label` statt eigene Logik.
   - Statusbar (main_window.py) gleiche Logik.

3. **Live-Anzeige im QSO-Panel** (`main_window._update_statusbar`):
   - Waehrend aktivem QSO ueberschreibt `qso_panel.status_label`:
     `→ CALL  |  RX: ANT2 ↑1.0 dB` (gruen, fett wenn ANT2-Gewinn)
     `→ CALL  |  RX: ANT1` (grau wenn ANT1-Default)
   - Update pro Cycle — Pref-Wert kann sich waehrend QSO aendern.
   - Reset uebernimmt `qso_panel.add_qso_complete` (setzt Counter + grauen Style).

**Cleanup (DeepSeek-Review-Punkt):**
- `qso_panel._cq_flash_timer` wird in `add_tx` (Non-CQ-Pfad) und
  `add_qso_complete` gestoppt — sonst koennte er nach 2s die Live-QSO-Anzeige
  ueberschreiben mit dem CQ-orange-Style.

**Tests:** 216 passed (213 + 3 neue: Hysterese genau auf Schwelle / unter
Schwelle / A1 deutlich besser).

**Statistiken:** auswertung/Bericht-*.pdf (DE) + auswertung/en/Report-*.pdf (EN)
neu generiert, alle Baender + Modi.

## 2026-04-26 v0.62 — Normal-Modus = WSJT-X-Standard (manuelle TX-Frequenz)

**Mike's Argumentation:** Normal-Modus soll wie WSJT-X funktionieren. Dort waehlt
der Funker die TX-Frequenz manuell. Auto-Suche ist USP des Diversity-Modus —
keine Mischung. Statistik-Vergleich wird sauberer wenn Normal "nackt" laeuft.
Histogramm bleibt im Normal sichtbar als Wasserfall-Ersatz (alle 15s).

**Aenderungen:**

1. **FrequencyHistogramWidget** (`control_panel.py`):
   - Neues Signal `tx_freq_clicked(int)` — Klick-Position → TX-Freq in Hz.
   - `mousePressEvent`: rundet auf 50-Hz-Bin-Raster (wie WSJT-X).
   - `set_clickable(bool)`: Pointer-Cursor + Tooltip im Normal, Standard im Diversity.
   - `_last_freq_lo/hi` werden im paintEvent gemerkt fuer Klick→Hz-Konvertierung.

2. **Spinbox unter Histogramm** (`_AntennaCard`):
   - QSpinBox 150-2800 Hz, Step 50, Default 1500 (WSJT-X-Default).
   - Pfeile hoch/runter zur Feinjustierung.
   - Forwarding `_tx_freq_row` + `_tx_freq_spin` im ControlPanel.

3. **Modus-abhaengige UI** (`_apply_rx_mode_visibility`):
   - Normal: Spinbox sichtbar, Histogramm klickbar, kein CQ-Auto-Countdown.
   - Diversity: Spinbox versteckt, Histogramm nicht klickbar (Auto-Suche), CQ-Countdown sichtbar.
   - Initial-Aufruf in ControlPanel.__init__ damit Normal-Modus von Start an
     korrekt konfiguriert ist.

4. **Persistenz pro Band** (`config/settings.py`):
   - `get_normal_tx_freq(band)` / `save_normal_tx_freq(band, hz)`.
   - Default 1500 Hz (faellt auf globalen `audio_freq_hz` zurueck).
   - Speicherort: `normal_tx_freq_per_band` dict in config.json.

5. **Auto-Suche im Normal-Modus deaktiviert**:
   - `mw_cycle._update_histogram`: kein `update_proposed_freq()` mehr im Normal.
     TX-Marker wird auf `encoder.audio_freq_hz` (manuell) gesetzt.
   - `mw_qso._on_cq_clicked`: nur Diversity nutzt `get_free_cq_freq()`.
     Im Normal-Modus laeuft CQ auf der manuell gewaehlten Frequenz.

6. **Slots in `mw_radio`**:
   - `_on_normal_tx_freq_clicked` / `_on_normal_tx_freq_spin_changed`.
   - `_set_normal_tx_freq(hz, source)` synchronisiert Klick + Spinbox via
     `blockSignals` (kein Endlos-Loop).
   - `_apply_normal_mode` laedt gespeicherte Frequenz pro Band.

**Tests:** 218 grün (216 + 2 neue: `test_normal_tx_freq_default` +
`test_normal_tx_freq_per_band_save_load`). GUI-Smoke-Test verifiziert
Mode-Switching (Klick-Modus an/aus).

**DeepSeek-Review:** Issues betrafen pre-existing diversity.py (Sticky-/
Kollisions-Schwellen) — nicht v0.62. Code-Quality-Bewertung: solide Modularitaet.

## 2026-04-26 v0.63 — 20m FT8 PDF + Stats-Filter (nur 20m+40m FT8)

**Mike's Strategie-Entscheidung:** Nur noch 20m + 40m FT8 protokollieren.
Andere Baender und Modi werden zwar weiterhin empfangen, aber nicht mehr in
statistics/ gespeichert. Skaliert sonst nicht (Aufwand fuer PDF-Auswertung).

**Aenderungen:**

1. **Stats-Filter** (`core/station_stats.py`):
   - Klassen-Konstante `LOGGED_BANDS = {"20m", "40m"}`.
   - `log_cycle`, `log_station_comparisons`, `log_antenna_qso` returnen
     fruehzeitig wenn `band not in LOGGED_BANDS`.

2. **20m FT8 PDF** (`scripts/generate_plots.py`):
   - Neues Override-Layer `TEXTS_20M_OVERRIDE` mit komplett anderem Narrativ
     (DE + EN). Auf 20m ist ANT1 RESONANT — kein Antennen-Mismatch wie auf 40m.
     Diversity-Gewinn entsteht durch echte Polarisations-/Pattern-Diversity.
   - `_texts_for(band, lang)` mergt Default-Texte mit Band-Override.
   - `create_pdf_report` nimmt `band, protocol` als Parameter.
   - `main()` generiert beide PDFs (40m + 20m) pro Sprache.

3. **20m-Narrativ** (Schwerpunkte):
   - Asymmetrischer Vorteil: Resonante TX (Stationen hoeren mich) + RX-Diversity
     (ich hoere sie zurueck) → loest klassisches asymmetrisches QSO-Problem.
   - ANT2 (Regenrinne) gewinnt 79-86% der Doppelempfaenge mit Ø +4 dB —
     trotz resonantem ANT1.
   - Theorie: Faraday-Rotation skaliert mit f² → Polarisations-Diversity wirkt
     auf 20m staerker als auf 40m.
   - Qualitativ wertvoller als 40m: weniger absoluter Gewinn, aber bei
     bereits guter Antenne erzielt → uebertragbar auf andere Setups.
   - Caveat: 20m-Datenbasis noch duenner, waechst weiter.

**PDFs neu generiert:**
- `auswertung/Auswertung-40m-FT8.pdf` (DE)
- `auswertung/Auswertung-20m-FT8.pdf` (DE) ← NEU
- `auswertung/en/Report-40m-FT8.pdf` (EN)
- `auswertung/en/Report-20m-FT8.pdf` (EN) ← NEU

**Tests:** 218 passed (unveraendert — keine Logik-Aenderungen die Tests treffen).

**Statistik-Daten (20m FT8 Stand 2026-04-26):**
- Normal: 5 Tage, 688 Zyklen
- Diversity_Normal: 2 Tage, 364 Zyklen
- Diversity_Dx: 4 Tage, 2469 Zyklen
- ANT2-Win-Rate Doppelempfang: 79% (Std), 86% (Dx) — **Diversity wirkt auch bei resonanter ANT1!**

## 2026-04-26 v0.64 — Aging-Bug-Fix: Aging in Slots statt Sekunden

**Problem (DeepSeek-Befund):** Aging-Schwellen in `core/station_accumulator.py`
waren in fixen Sekunden hartkodiert (75/150/300s normal/active/CQ). Bei
verschiedenen Modi ergab das stark unterschiedliche Slot-Anzahlen:

| Modus | Slot-Dauer | Alte Aging-Slots | Problem |
|-------|-----------|------------------|---------|
| FT8 | 15.0s | 5/10/20 | OK (Design-Wert) |
| FT4 | 7.5s | 10/20/40 | doppelt zu lang |
| FT2 | 3.8s | ~20/40/79 | DEUTLICH zu lang — Liste verstopft! |

Bei FT2-Betrieb behielt die Liste ~80 Slots alte Eintraege. Konsequenz:
veraltete Decodes ueberlagerten aktuelle Aktivitaet.

**Fix:**
- `core/station_accumulator.py`: Konstanten in SLOTS, modus-konsistent.
  - `AGING_SLOTS_NORMAL    = 7`   (~3.5 verpasste Sende-Zyklen)
  - `AGING_SLOTS_ACTIVE    = 14`
  - `AGING_SLOTS_CQ_CALLER = 20`
- Neuer Helper `_aging_limit_seconds(call, msg, active_qso_targets, slot_duration_s)`.
- `remove_stale(...)` + `accumulate_stations(...)` um Parameter `slot_duration_s` erweitert
  (Default 15.0 fuer Rueckwaerts-Test-Kompatibilitaet).
- `ui/mw_cycle.py`: 2 Aufrufstellen uebergeben jetzt `self.timer.cycle_duration`.

**DeepSeek-Validierung (continuation_id 625b1dab):**
- Werte 7/14/20 statt 5/10/20: meine erste Idee waere auf FT4 zu aggressiv
  gewesen (RR73-Hoeflichkeits-Sequenz braucht 6-8 Slots).
- Architektur-Option (b) "Parameter durchreichen" einstimmig empfohlen
  gegenueber globalen Settings oder Hardcoding.

**Modus-Wechsel-Robustheit:** `_last_heard` bleibt Sekunden-Timestamp. Beim
Vergleich wird die Aging-Schwelle aus AKTUELLER Slot-Dauer berechnet.
FT8→FT2-Wechsel raeumt schnell auf — bewusstes Verhalten.

**Tests:** 220 grün (218 + 2 neue).
- `test_accumulator_aging_ft2_short_window` — bei FT2 nach 30s weg, bei FT8 nicht.
- `test_accumulator_aging_mode_switch_robustness` — Stationen verschwinden korrekt nach Modus-Wechsel.
- `test_accumulator_aging` angepasst (110s statt 80s wegen 7-Slot-Schwelle bei FT8).

## 2026-04-26 v0.65 — CSV-Export Diversity-Daten + Stats-Update

**Feature:** Standalone-Script `scripts/export_diversity_csv.py` exportiert
alle Antennen-Vergleichs-Daten aus `statistics/Diversity_*/{band}/FT8/stations/`
nach CSV. Use Cases:
- Wissenschaftliche Auswertung (Pandas, R, Excel) der 79-86% ANT2-Win-Rate
- Veroeffentlichung der Daten als Funkamateur-Paper
- Antennen-Optimierungs-Analysen offline

**Format:** `date, time_utc, callsign, ant1_snr_db, ant2_snr_db, delta_db,
band, mode, scoring_mode, antenna_winner`. Hysterese 1.0 dB → A2-Winner ab Δ ≥ +1.0.

**Output (Test-Lauf 26.04.2026):**
- `auswertung/diversity_data_20m_FT8_Diversity_Normal.csv` — 34 Zeilen
- `auswertung/diversity_data_20m_FT8_Diversity_Dx.csv` — 97 Zeilen
- `auswertung/diversity_data_40m_FT8_Diversity_Normal.csv` — 228 Zeilen
- `auswertung/diversity_data_40m_FT8_Diversity_Dx.csv` — 316 Zeilen
- **Gesamt: 675 Datensaetze**

**Aufruf (CLI):** `./venv/bin/python3 scripts/export_diversity_csv.py`

**UI-Integration (Mike's Idee waehrend der Session):** Im Einstellungs-Dialog
neue GroupBox "Datenexport" mit Button "Diversity-Daten exportieren …".
Klick → `QFileDialog.getExistingDirectory` → Verzeichnis-Auswahl → Export
laeuft im GUI-Thread (typisch 200-500ms) → Ergebnis-Dialog mit Anzahl
Dateien + Datensaetze. Letzter Pfad wird in `csv_export_dir` Setting
persistiert.

**Refactor:** `export_diversity_csv.py` `export_all(output_dir)` Helper extrahiert,
sowohl von CLI als auch UI nutzbar. Standalone-Script bleibt als Power-User-Backup.

**Stats-Updates:** PDFs neu generiert (DE+EN, 40m+20m FT8) mit aktuellem Datenstand.

Tests: 220 passed (unveraendert, Script-Standalone ohne Test-Pflicht — Output verifiziert
+ GUI-Smoke-Test der Settings-Dialog-Integration ok).

---

## 2026-04-26 v0.66 — Richtungs-Karte mit RX/TX-Toggle (Feature C+D)

Neues USP-Feature: Azimuthal-Equidistant-Welt-Karte mit eigenem Locator als Center,
zwei Modi (EMPFANG/SENDEN), Sektor-Aggregation in 16 Wedges à 22.5°. Karte ist
nicht-modal, parallel zum Hauptfenster nutzbar, vom Einstellungs-Dialog aus zu
oeffnen ("Richtungs-Karte" GroupBox → "Karte oeffnen ..."-Button).

**Implementiert in 10 atomaren Commits ueber 1 Session:**

1. **`core/geo.py`** erweitert um `great_circle_bearing`, `azimuthal_equidistant_project`,
   `safe_locator_to_latlon` (None-safe Wrapper). 26 neue Tests (Bearing-Quadranten,
   360°-Range, Antipode-Clip, Locator-Edge-Cases). DeepSeek-Codereview eingearbeitet.

2. **`core/antenna_pref.py`** Thread-Safety nachgeruestet. `threading.RLock` schuetzt
   alle Methoden, neue `snapshot()`-Methode liefert unabhaengige dict-of-dict-Kopie
   fuer Render-Pfade. 7 neue Tests (concurrent read/write, snapshot-Independence,
   clear-mid-update Konsistenz).

3. **Coastline-Asset** `assets/ne_110m_land_antimeridian_split.geojson` (116 KB, 129
   LineStrings, 5143 Punkte). Build-Script `tools/build_coastlines.py` generiert
   das Asset aus Natural Earth 110m via urllib + json (Pure Python, kein shapely
   noetig). Antimeridian-Splits: lon-Sprung > 180° → Linie auftrennen.

4. **`core/psk_reporter.py`** wiederverwendbarer XML-Polling-Client mit Cache,
   Backoff (1.5x bis 60min Cap), Call-Normalisierung (`.rsplit('/',1)[0]` strippt
   /P /MM /QRP). Atomarer Cache-Write (.tmp + os.replace). 35 Tests inkl.
   XML-Parser mit/ohne Namespace, Backoff-Sequenz, Thread-Lifecycle, Callback-
   Crash-Robustness. Bestehender `main_window._psk_worker` bleibt unangetastet.

5. **`core/direction_pattern.py`** Sektor-Aggregation. `aggregate_sectors()`
   mit Call-Dedup pro Sektor, `is_mobile()` regex-Filter, NaN/Inf-Schutz.
   `StationPoint`/`SectorBucket` dataclasses. 27 Tests.

6. **`ui/direction_map_widget.py`** UI-Skeleton: `MapCanvas` (QWidget mit paintEvent,
   QPixmap-Background-Cache, Resize-Debounce 200ms) + `DirectionMapDialog` (QDialog
   non-modal, Toggle RX/TX, Filter-Bar Zeit/Band/Layer-Checkboxes, Status-Label).
   Coastlines + Distanzringe + Compass + Sektorlinien werden in Background-Pixmap
   gecached. 21 Smoke-Tests in QT_QPA_PLATFORM=offscreen.

7. **Live-Layer + RX-Hook (7a + 7b):**
   - 7a: paintEvent erweitert um Sektor-Wedges (16 drawPie, count→Laenge, gewichteter
     ANT1/ANT2/Rescue-Farb-Mix) und Stations-Punkte (Farbe nach Antenne, Groesse
     nach SNR linear 3..8px). LocatorCache (Session-stabil, FT8 hat Locator nur
     in CQ-Nachrichten). `snapshot_to_station_points` mit Mobile-Filter, Rescue-
     Klassifikation (snr_a1 ≤ -24 UND snr_a2 > -24).
   - 7b: `MainWindow.direction_map_signal` als Cross-Thread-Bridge
     (Decoder-Thread → GUI-Thread, Qt.QueuedConnection). `_build_map_snapshot`
     liest aktuelle Stations-Akkumulatoren, `_emit_map_snapshot_if_open` nur
     wenn Dialog visible. Hooks am Ende von `_handle_diversity_operate` und
     `_handle_normal_mode`.

8. **TX-Modus mit PSK-Reporter integriert.** SENDEN-Toggle startet PSKReporterClient,
   Cache-Spots werden sofort gerendert (kein API-Wait). `_psk_spots_signal` /
   `_psk_error_signal` mit QueuedConnection fuer Worker→GUI-Marshalling.
   `_spots_to_station_points` mit normalize_call + Locator-Cache + Dedup.
   closeEvent stoppt Polling sauber. 5 neue Tests.

9. **Settings-GroupBox + Karten-Button + Geometrie-Persistenz.** Neue GroupBox
   "Richtungs-Karte" im Einstellungs-Dialog (analog zu Datenexport-GroupBox v0.65).
   Klick auf "Karte oeffnen …" → MainWindow.open_direction_map mit default_mode
   aus Settings. Karten-Geometrie wird in `direction_map_geometry` (hex-bytes)
   und `direction_map_default_mode` persistiert.

10. **Doku** — APP_VERSION 0.65 → 0.66, HISTORY.md, CLAUDE.md aktualisiert.

**DeepSeek-Codereview** wurde fuer **alle 5** nicht-trivialen Module durchgefuehrt
(geo, antenna_pref, psk_reporter, direction_pattern, direction_map_widget).
Findings systematisch eingearbeitet — u.a. NaN-Inf-Schutz in aggregate_sectors,
on_spots-Callback try/except in _run_loop, RLock-Begruendung im Code dokumentiert,
Thread-Marshalling-Pflicht in update_stations-Docstring, sleep-loop max(0)-Guard.

**Architektur-Stops mit Mike abgesprochen:**
- shapely als Dev-Only (build_coastlines.py) — spaeter sogar weggelassen, Pure-Python
- RLock vs Lock fuer AntennaPreferenceStore: RLock gewaehlt (defensive)

**Was NICHT implementiert wurde** (bewusst):
- OpenStreetMap-Tiles, QtWebEngine, pyproj, shapely-Runtime
- JSONP-API (XML-API existing _psk_worker erweitert)
- requests-Library (urllib stattdessen, konsistent zur Codebase)
- Initial-Lade aus historischen `statistics/`-Daten (Locator-Lookup luecken-haft)
- Migration des bestehenden `_psk_worker` zu `core/psk_reporter` — separater Folge-Commit

**Tests:** 361 passed (220 → 361, +141 neu).

**Bekannte Limitations:**
- TX-Modus zeigt nur Stationen wo Locator im PSK-Report enthalten ist (sehr
  haeufig der Fall, aber nicht 100%).
- RX-Modus baut Locator-Cache aus CQ-Nachrichten. Stationen die nie CQ rufen
  (nur Antworten) erscheinen erst auf der Karte wenn Mike sie via QSO erfasst.
- Mobile/Maritime Calls (/P /MM /AM /QRP) werden im RX-Modus gefiltert; im
  TX-Modus strippt normalize_call das Suffix → Stations-Plain-Call landet im
  Cache mit dem von PSK gemeldeten Locator.
- Antipode-Bereich (>18000 km von JO31) wird nicht gerendert — starke Verzerrung
  bei azimuthal-equidistant-Projektion.

## 2026-04-27 v0.67 — Persistenter Locator-Cache (LocatorDB)

**Ziel:** Eine schlanke, persistente JSON-DB sammelt alle gesehenen Locators
(eigene CQ-Decodes, PSK-Reporter-Spots, ADIF-Bulk-Import vom QSO-Log) mit
Source-Priorisierung und ueberlebt App-Restarts. Karte und rx_panel ziehen
beide aus dieser DB. Bei jeder Session werden mehr Stationen praezise.

**KISS-Prinzip nach DeepSeek-Plan-V3** — V2 hatte 26-Buchstaben-Splitting,
LRU-Cache, Write-Ahead-Log: alles raus. Eine JSON-Datei (~/.simpleft8/
locator_cache.json), in-memory waehrend Laufzeit, save() nur bei App-Close
(bei Crash gehen ein paar Decodes verloren — kommen bei naechster Session
wieder rein, akzeptabel fuer Hobby-Funker-Tool).

**Neues Modul:** `core/locator_db.py` (~250 Zeilen inkl. Docstrings)
- `LocatorEntry` dataclass (locator/source/prec_km/first_ts/last_ts)
- `LocatorDB`: get/get_position/set/load/save/bulk_import_adif/_directory
- Source-Priority numerisch (cq_6=600 > psk_6=500 > qso_log_6=400 > _4=100..300)
- 6-stellig wird nie durch 4-stellig ueberschrieben (Priority-Tabelle)
- first_ts immutable, nur last_ts wird aktualisiert
- Mobile-Suffixe (/MM /AM /QRP) → `prec_km × 1.5`; /P bleibt full precision
- `threading.RLock` zentral (Decoder + PSK-Worker konkurrent)
- Atomic-Write (.tmp + os.replace) — wiederverwendet aus core/psk_reporter.py
- get() returnt **Kopie** via `LocatorEntry(**asdict(e))` — Caller-Mutation safe
- Korrupte JSON beim Load → leeres Dict, App startet trotzdem
- `encoding="utf-8"` explizit (DeepSeek-Empfehlung gegen Windows-Locale)

**Hooks (5 Stellen):**
1. `mw_cycle._handle_normal_mode` → `_feed_locator_db(messages)`
2. `mw_cycle._handle_diversity_operate` → analog
3. `direction_map_widget._on_psk_spots_received` → `db.set("psk")` pro Spot
4. `_init_qso_log` → `bulk_import_directory()` aus <cwd>/adif/ + adif_import_path
5. `closeEvent` → `db.save()` (atomar)

**UI-Aenderungen:**
- `StationPoint.prec_km` neues Feld (Default 110, backwards-compatible)
- `_paint_stations`: Country-Fallback (prec_km > 110) → 50% Alpha,
  voller Glow nur bei DB-Treffern
- Disclaimer-Label reduziert auf einzeiliges `"Ø Genauigkeit: X km"`,
  wird live aktualisiert bei jedem update_rx/update_tx
- `rx_panel.set_locator_db()` Setter — exakte km auch fuer Reports/RR73
  wenn Locator irgendwann mal in CQ/PSK gesehen wurde (kein ~-Praefix)

**Tests:** 28 neue Tests in `tests/test_locator_db.py`:
- CRUD, Source-Priority-Matrix (psk vs cq, 4 vs 6, qso_log vs cq)
- first_ts immutable, atomic-write Crash-Recovery
- Threading-Stress (5 Threads × 50 sets)
- Slash-Calls (/P, /MM, /AM)
- ADIF-Bulk-Import (Datei + Verzeichnis)
- 405 → 407 Tests gruen.

**6 atomare Commits:**
1. `core/locator_db.py` + 26 Tests (DeepSeek-codereviewed: encoding="utf-8" Fix)
2. Hooks `mw_cycle._feed_locator_db` + PSK-Spot-Hook im Karten-Widget
3. ADIF-Bulk-Import in `_init_qso_log` (+2 Tests)
4. `direction_map_widget` Migration: `LocatorDB` parallel zum LocatorCache,
   `prec_km` an StationPoint, Glow-Alpha-Dimming bei Country-Fallback,
   "Ø Genauigkeit"-Label
5. `rx_panel`: km-Spalte zieht aus DB vor Country-Fallback
6. APP_VERSION + HISTORY (dieser Commit)

**Architektur-Defaults (V3-Plan, in Plan-Mode mit Mike abgesprochen):**
- ✅ Save NUR bei App-Close (nicht periodisch) — Hobby-Funker-konform
- ✅ Outline-DICKE statt Farbe verworfen — Mike's "Glow zurueck"-Feedback
   aus v0.66 hat Vorrang. Statt Outline: Country-Fallback dimmt Alpha.
- ✅ Disclaimer reduziert auf "Ø Genauigkeit: X km"

**Bekannte Limits:**
- LocatorCache (in direction_map_widget) bleibt vorerst als Fallback erhalten —
  spaeterer Cleanup-Commit moeglich wenn alle Codepfade migriert sind.
- DB ueberschreibt sich selbst bei jedem set(), kein TTL-Cleanup. Bei ~10000
  Calls ~500 KB JSON, ok. Phase 2 erst falls > 5 MB.
- ADIF-Bulk-Import laeuft bei jedem App-Start ueber alle .adi-Dateien — bei
  1000 Records ~300 ms, kein Performance-Problem.

**Was NICHT implementiert wurde** (bewusst, gegen Hobby-Funker-Philosophie):
- Online-Lookup QRZ/HamQTH (Privacy)
- Cluster/DX-Spotting
- Manuelles Korrektur-UI (WSJT-X-konform: Decode = Wahrheit)
- TTL-Cleanup, LRU-Cache, Write-Ahead-Log (Phase 2 nur falls noetig)

## 2026-04-27 — Doku-Updates + Statistik (v0.67, kein Version-Bump)

Nach v0.67-Implementierung kamen noch drei dokumentations-getriebene Commits
und ein Push:

- **Statistik-Update + PDF-Regeneration:** Neue 20m FT8-Daten von 26.04.2026
  (Diversity_Normal/Diversity_Dx/Normal). PDFs (DE+EN) frisch generiert.

- **Antennen-Bezeichnung korrigiert (Mike-Feedback):** Recherche bestaetigte
  Kelemen DP-201510 ist ein Multiband-**Trap-Dipol** (Sperrkreis-Dipol) mit
  koaxialen Sperrkreisen, *kein* Faecher-Dipol. Korrektur in:
  - `scripts/generate_plots.py` (alle DE+EN-Strings)
  - `README.md` (englische + deutsche Section)
  - PDF-Berichte (DE+EN) neu generiert mit korrektem Wording
  Quellen: WiMo (Hersteller), Funktechnik Dathe, Funkshop, DX Engineering.

- **WSJT-X-Vergleichstabellen entfernt** — Hobby-Funker-Philosophie:
  - "Why SimpleFT8 vs. WSJT-X?" / "Warum SimpleFT8 statt WSJT-X?" Sections
    durch lockeren Hobby-Funker-Vorstellungstext ersetzt (DeepSeek-Umformulierung).
  - Neuer Header: "Why SimpleFT8?" / "Warum gibt es SimpleFT8?"
  - "Normal: 1 Antenne, wie WSJT-X" → "klassisches Single-Antenna-Setup"
    (in Plot-Erklaerungen DE+EN).
  - WSJT-X-Acknowledgments behalten als Hommage an die Pioniere.

- **Test-Counts + Versionsnummern** im README aktualisiert: 159/162 → 407,
  v0.26 → v0.67. Neue Features (Karte v0.66, Locator-DB v0.67) in Tested-
  Working-Listen ergaenzt.

- **Push:** 38 Commits (v0.66 + v0.67 + Stats + README) auf GitHub
  https://github.com/mikewanne/SimpleFT8 main.

**Stand:** v0.67, 407 Tests gruen, GitHub aktuell.

## 2026-04-27 — Statistik-Update + Feierabend (v0.67, kein Version-Bump)

**Statistiken aktualisiert:**
- Neue 20m FT8 Daten von 26.04. (Stunde 23) und 27.04. (Stunden 00-06,
  Diversity_Normal) — Nachtmessung von Mike.
- 40m FT8: 22.696 Zyklen, 4 Messtage (unveraendert seit v0.66).
- 20m FT8: 8.461 Zyklen, Zeitraum bis 27.04. (waechst kontinuierlich).
- PDFs (DE+EN) frisch generiert via `scripts/generate_plots.py`.

**Feierabend-Routine:**
- HANDOFF.md (beide Pfade: `SimpleFT8/` + `FT8/`) komplett neu fuer v0.67 mit
  Architektur-Diagramm Locator-DB + Test-Status + Warnungen + Naechste Schritte.
- TODO.md auf v0.67-Stand: neuer "MORGEN ALS NAECHSTES"-Block mit Field-Test-
  Plan fuer LocatorDB.
- CLAUDE.md (beide Pfade) bestaetigt identisch + aktuell.
- Memory aktualisiert:
  * `project_antenna_setup.md` korrigiert (Trap-Dipol statt Faecher-Dipol)
  * NEU `feedback_plan_mode_workflow.md` — Mike's V1→V2→DeepSeek→V3→/plan
  * NEU `feedback_github_browser_cache.md` — bei "GitHub nicht aktuell"
    erst WebFetch checken, Negationen vermeiden

**Stand:** v0.67, 407 Tests gruen, alle Doku-Dateien fuer Feierabend up-to-date.

---

## 2026-04-27 v0.68 — Map-UI Bugfixes (Dropdowns + Sektor-Rotation)

Drei UI-Bugs in der Richtungs-Karte (v0.66) behoben. V1→V2→V3-Workflow mit
DeepSeek-Review durchlaufen, anschliessend Plan-Mode + atomare Commits.
Workflow-Etablierung in `CLAUDE.md` dokumentiert (inkl. Trigger-Schwelle:
voller Workflow ab >=2 Akzeptanzkriterien ODER Mathe ODER >=2 Dateien).

### Aufgabe 3+4 — Filter-Dropdowns abgeschnitten
- `window_combo` ("3 Std") und `band_combo` ("Aktuelles") wurden vorher
  abgeschnitten weil keine `setSizeAdjustPolicy()` gesetzt war.
- Fix: beide ComboBoxes in `ui/direction_map_widget.py` auf
  `QComboBox.AdjustToContents` — wachsen automatisch mit dem laengsten Item,
  robust gegen DPI-Skalierung.
- Test: `test_dialog_dropdowns_adjust_to_contents`.

### Aufgabe 5 — Sektoren rotieren nicht mit Globus
- Vorher: Sektor-Wedges in `_paint_sector_wedges()` zeichneten mit absoluten
  Bildschirmkoordinaten (`mid_deg = b.index * SECTOR_WIDTH_DEG`) — Norden war
  immer Bildschirm-oben, ignorierte Globus-Drehung.
- Bug-Symptom: Beim Drehen der Karte zeigten die Sektoren weiter nach oben
  obwohl die geographische Verteilung der Stationen gedreht war.
- Fix: Neuer Helper `_screen_north_deg()` projiziert einen 5°-Hilfspunkt
  nordwaerts vom User mit `_project()` und leitet aus der Bildschirm-Differenz
  das aktuelle Bildschirm-Bearing des Nordens ab. Wert wird in
  `_paint_sector_wedges()` einmal pro Frame als Offset auf
  `b.index * SECTOR_WIDTH_DEG` addiert.
- Edge-Cases:
  - User auf Globus-Rueckseite: `_user_screen_pos()` ist None → existierender
    Skip greift.
  - User nahe Pol (`abs(lat) > 85°`): Fallback Norden=oben.
  - 5°-Hilfspunkt verdeckt: Fallback Norden=oben.
- Tests:
  - `test_screen_north_aligned_default_view` — Default-View → Norden ~ 0°
  - `test_screen_north_changes_with_globe_rotation` — `_view_lon += 90°` →
    Norden > 30° vom Bildschirm-oben weg
  - `test_paint_sector_wedges_safe_when_user_hidden` — `_view_lat = -85°` →
    User unsichtbar, kein Crash

### DeepSeek-Codereview vor Commit 2
DeepSeek fand einen Bug: `lat > 85.0` ist asymmetrisch — der Suedpol war
nicht abgedeckt. Fix: `abs(lat) > 85.0`. Funktion liefert jetzt fuer Nord-
und Suedpol denselben Fallback. Rest des Helpers war mathematisch korrekt
(atan2-Vorzeichen, Y-down-Konvention).

### CLAUDE.md / Workflow-Doku
Mehrstufiger Prompt-Workflow festgehalten:
1. Probleme erkennen + V1 entwerfen
2. Self-Review als frische KI → V2
3. V2 an DeepSeek (Prompt-Critique, nicht Implementierung)
4. DeepSeek-Findings einarbeiten → V3
5. Mike vorlegen
6. Plan-Mode + atomare Commits

Trigger-Schwelle definiert: voller Workflow nur wenn nicht-trivial.
Bei reinen Tippfehlern / Lokal-Patches: V1 reicht.

### Commits
- `400eb03` docs(claude): mehrstufigen Prompt-Workflow + Trigger-Schwelle
- `5ab1763` fix(map): Dropdowns Zeit/Band auf AdjustToContents
- `2d08282` fix(map): Sektoren folgen Globus-Rotation
- `<HEAD>` chore(release): v0.68 — APP_VERSION + HISTORY + CLAUDE.md

### Bewusst NICHT umgesetzt (Out-of-Scope)
- Punkt 1 (Mike): Pulsieren der Propagations-Balken bei Bandoeffnung —
  separates Feature, eigener Plan
- Punkt 2 (Mike): PSK-Reporter Reichweiten-Sektoren im TX-Modus
  (TX-Pattern-Karte, USP-Killer) — separater Plan
- Punkt 6 (Mike): Stations-Count 37 vs 46 (Karte filtert nach Locator,
  rx_panel zaehlt alle Decodes) — vermutlich Tooltip-Loesung,
  separater Plan
- QPainterPath fuer Sektor-Verzerrung am Globus-Rand — KISS, akzeptiert
  (Sektoren bleiben in 30 % der Disc, Verzerrung optisch unauffaellig).

**Stand:** v0.68, 411 Tests gruen (+4 ggue. v0.67). Map-UI ist drag-fest.

### Field-Test-Folgekorrekturen (v0.68 hotfix, gleicher Tag)
Nach App-Restart fand Mike zwei Restprobleme die ich am Schreibtisch nicht
verifizieren konnte:

1. **Dropdown-Popup-Items immer noch abgeschnitten** — `AdjustToContents`
   regelte nur die geschlossene Combo, nicht die Popup-View. Workaround:
   `view().setMinimumWidth(view().sizeHintForColumn(0) + 30)` nach allen
   `addItem`-Aufrufen. +30 statt initialer +16, weil "Aktuelles" wegen
   des Pfeil-Indikators mehr Platz braucht.

2. **Sektor-Toleranz optisch zu gross beim Drehen** — der 5°-Hilfspunkt
   gab bei 400px-Globus nur ~22 Pixel Hebel. Pixel-Quantisierung im
   `atan2` verlor dadurch 2-3° Genauigkeit. Mike sah die obere Station
   mal links, mal rechts vom Sektor.
   → 10°-Hilfspunkt: ~44 Pixel Hebel, Genauigkeit < 1°. Pol-Cutoff von
   85° auf 80° angepasst (10° + 80° = 90° max, sicher).

Commit: `7b117a8` fix(map): v0.68 Folgekorrekturen — Popup-Padding + Sektor-Hebel.

**Lehre fuer kuenftige UI-Fixes:** AdjustToContents reicht NIE allein —
Popup-View braucht eigenes setMinimumWidth. Bei Bearing-aus-Pixel-Helfer
groesseren Hebel waehlen (10-15°) als naive Mathematik suggeriert.


## 2026-04-27 v0.71 — TX-Reichweiten-Sektoren (PSK-Reporter Distanz-Mapping)

**TODO Punkt 2 erledigt** — Karten-Sektor-Wedges im SENDEN-Modus zeigen
jetzt **Reichweiten-Pattern** statt Cluster-Dichte.

### Was ist neu

**Vorher (v0.70):** TX-Sektor-Wedge-Laenge skalierte mit Anzahl gehoerter
Stationen pro Sektor — identisch zu RX. Resultat: PSK-Reporter Cluster
wie Iberien/UK dominierten optisch, ein Spot aus VK6 (16000 km)
verschwand neben 50 Spots aus 1500 km.

**Jetzt (v0.71):** TX-Wedge-Laenge skaliert mit der **maximalen Distanz**
der Stationen im Sektor. Mike sieht auf einen Blick wo sein Signal
hinkommt — nicht wer es zufaellig oft empfaengt. Spot aus Australien
ergibt langen Wedge, dichter Iberien-Cluster bleibt bescheiden.
RX-Modus unveraendert (count-basiert ist dort die richtige Metrik).

### Architektur (4 atomare Commits)

1. **`feat(direction_pattern)`** — `SectorBucket.max_distance_km` neu,
   gefuellt in `aggregate_sectors()` als max ueber dedupliziertes Call-
   Set. NaN/Inf-Guard zwingend (sonst propagiert NaN durch paintEvent).
   4 neue Tests in `test_direction_pattern.py`.

2. **`fix(direction_map)`** — `distance_km` zwingend in `StationPoints`
   populiert, direkt im Canvas in `update_stations()` (NACH Konvertierung,
   da `_my_pos` dort bereits verfuegbar ist). Spart Konverter-API-
   Aenderung + Test-Updates.

3. **`feat(direction_map)`** — `_paint_sector_wedges` mode-aware:
   - TX: `r = max_wedge_r * (b.max_distance_km / global_max)`
   - RX: `r = max_wedge_r * (b.count / max_count)` (unveraendert)
   - Farb-Lerp avg_snr → TX_COLOR_LOW/HIGH unveraendert.

4. **`chore(release)`** — APP_VERSION 0.70→0.71, Doku.

### Workflow

V1 → V2 (Self-Review: NaN-Guards, Edge-Cases, Konverter-Pfade ergaenzt)
→ DeepSeek-Reviewer-Auftrag (3 echte Punkte: NaN-Guard zwingend,
AK3 Over-Engineering streichen, log10-Tradeoff diskutiert →
linear bleibt fuer Mike's "gross = weit"-Intuition) → V3 → Umsetzung.

DeepSeek-Halluzination: behauptete Wedge-Cache-Invalidate-Risk und
Commit-Aufteilung wegen RX-Test-Bruch. Beides per Code-Verifikation
widerlegt — kein Wedge-Cache vorhanden, RX-Tests greifen `distance_km`
nicht ab. **Code ist Referenz, DeepSeek ist Berater.**

### Tests

422 → 426 gruen (+4):
- `test_aggregate_sectors_max_distance` — max ueber 3 Stationen
- `test_aggregate_sectors_max_distance_zero_when_no_stations`
- `test_aggregate_sectors_max_distance_dedup_first_wins`
- `test_aggregate_sectors_max_distance_skips_non_finite` — NaN/Inf-Robustheit

### Field-Test offen

- TX-Reichweiten-Pattern bei Live-PSK-Daten beobachten — typische
  40m-Abendsession sollte dunkler-orange Iberien-Wedge (kurze Distanz,
  viele Stationen) gegen leuchtend-gelben USA-Wedge (lange Distanz,
  wenige Spots) zeigen.
- Falls TX-Sektoren bei wenigen Spots zu unruhig wirken: weiches
  Min-Floor (z.B. 20% max_wedge_r) erwaegen — fuer's erste linear
  belassen.


## 2026-04-28 v0.72 — Karten-Theme-Toggle (Aurora / Dark)

**Mike-Wunsch:** Dark-Mode-Variante fuer den Globus, Inspiration aus
einer fremden QSO-Landkarte (schwarzes Land, mittel-graues BG, dezent
graue Coastlines, gelber User-Stern). Bestehender Aurora-Look soll
unangetastet bleiben — Toggle, nicht Ersetzung.

### Architektur (3 atomare Commits)

1. **`feat(direction_map): theme dicts + Aliase + MapCanvas.set_theme()`**
   - `THEME_AURORA` + `THEME_DARK` + `THEMES` dict in
     `direction_map_widget.py`. Keys: bg, bg_center, land_fill,
     land_fill_high, coast_halo, coast_core, rings, compass,
     sector_lines, user, user_glow, hint, use_aurora (bool),
     disk_fill (None | hex).
   - 12 alte Modul-Konstanten als Backwards-Compat-Aliase auf
     `THEME_AURORA[...]` belassen (DeepSeek-Korrektur — Tests +
     externe Importe geschuetzt).
   - `MapCanvas._theme` Field, `set_theme(name)` Methode mit
     fallback auf "aurora" bei ungueltigem Namen (kein silent
     ignore, DeepSeek-Korrektur).
   - 4 neue Tests: theme_default_is_aurora, set_theme_dark_changes,
     set_theme_invalid_falls_back_to_aurora, set_theme_invalidates_bg.

2. **`feat(direction_map): paint-Methoden theme-aware + UI-Combo + Settings`**
   - 8 paint-Methoden auf `self._theme[...]` umgestellt.
   - `_paint_aurora`: early-return bei `not use_aurora` (Dark).
   - `_paint_globe_disk`: bei `disk_fill is None` → 3D-RadialGradient
     + Atmospheric-Limb (Aurora). Bei `disk_fill="#hex"` → flacher
     einfarbiger Disk ohne Limb (Dark) — DeepSeek-Korrektur, Globus
     bleibt sichtbar (statt komplett zu skippen).
   - `QComboBox` in DirectionMapDialog Filter-Bar zwischen Band-Combo
     und Stations/Sektoren-Checkboxes (DeepSeek-Korrektur, statt
     QPushButton-Toggle).
   - Settings-Key `"direction_map_theme"`, Default "aurora",
     Type-Validierung + Fallback bei ungueltigem Wert.
   - Sofortige Persistenz bei Combo-Wechsel (nicht erst beim Close).

3. **`chore(release): v0.72`** — APP_VERSION 0.71→0.72, HISTORY.md,
   CLAUDE.md.

### Workflow

V1 → V2 (Self-Review fuegte 10 fehlende Punkte hinzu: konkrete Theme-
Keys, use_aurora/disk_fill-Flags, Robust-Fallbacks, Aurora-Hardcodes)
→ DeepSeek-Reviewer-Auftrag (4 echte Punkte gefunden: AK3/5
harmonisieren, Aliase belassen statt entfernen, disk_fill statt
use_3d_disk Skip, QComboBox statt Toggle-Button, Commits aufgeteilt
2→3) → V3 → Plan-Mode + Umsetzung.

### Tests

426 → 430 gruen (+4 Theme-Tests). Stations-Farben, Antennen-Codes,
Heatmap, Sektor-Wedges sind NICHT theme-aware (KISS — funktionieren
auf beiden Hintergruenden).

### Field-Test BESTANDEN ✅ (28.04.2026)

Mike hat das Theme-Toggle live verifiziert — Originalzitat:
„erdkugel map sieht geil aus funktioniert auch super". Wechsel
sofort sichtbar, Persistenz ueber Restart bestaetigt.


## 2026-04-28 v0.73 — Persistenter RX-History-Cache + Karten-UI-Aufraeumung

**Mike-Wunsch:** Karte soll beim Open sofort die letzte Stunde Empfangs-
daten zeigen — auch nach App-Restart. Bisher war alles in-memory mit
30-Min-TTL und beim Schliessen weg. Plus: simpleFT8-Konformitaet —
Combos in der Filter-Bar die nichts (oder nicht voll) tun, sollen weg.

### Architektur (6 atomare Commits)

1. **`feat(rx_history): RxHistoryStore module + 10 Tests`**
   - `core/rx_history.py` neu: `RxEntry` dataclass + `RxHistoryStore`
     mit RLock + Dirty-Tracking + atomic-write.
   - 60 Min TTL beim Save UND Load (>3600s alt raus).
   - JSON-Format `{"version":1, "band":"40m", "mode":"FT8", "entries":[...]}`.
   - File-Naming: `{band}_{mode}.json` in `~/.simpleft8/cache/rx_history/`.
   - 10 Tests inkl. OSError-Handling, Schema-Version-Check, korrupte JSONs.

2. **`feat(main_window): RxHistoryStore Lifecycle`**
   - `__init__`: Store erstellen + `load_all()`.
   - Existing Auto-Save-Timer (LocatorDB v0.70): erweitert um
     `rx_history_store.save()` — eine Stelle, KISS.
   - `closeEvent`: finaler Save parallel zu LocatorDB.

3. **`feat(mw_cycle): Decoder-Hook RxHistoryStore.add_entry`**
   - Neue Methode `_feed_rx_history(messages, antenna)` parallel zu
     `_feed_locator_db`.
   - None-safe (`if rx_history_store is None: return`) — atomar
     unabhaengig von Commit 2.
   - Aufrufe in `_handle_normal_mode` (antenna="A1") und
     `_handle_diversity_operate` (antenna=ant).

4. **`feat(direction_map): RX-History beim Open + Bandwechsel + 60min TTL`**
   - `STATION_TTL_S = 30*60` → `60*60` (konsistent mit Persist-TTL).
   - Neuer Modul-Helper `entries_to_station_points(entries, locator_db)`:
     RxEntry → StationPoint, Locator-Lookup priorisiert
     `locator_db.get_position` (exakte km), Mobile-Filter.
   - `main_window.open_direction_map`: ruft `_reload_rx_history_on_map(band)`
     vor `show()` — Karte hat sofort Daten.
   - `mw_radio._on_band_changed`: wenn Karte offen → reload.

5. **`refactor(direction_map): Time-Window-Combo + Band-Combo raus`**
   - `band_combo` "Aktuelles/Alle": Property nirgends ausgewertet (toter Code).
   - `window_combo` (10/30/60/180 Min): Wert nur beim Polling-Start
     wirksam, Live-Wechsel im laufenden Dialog wirkungslos.
   - Beide komplett entfernt + Properties geloescht. `_start_tx_polling`:
     `window_min=60` hardcoded.
   - 2 alte Tests umgeschrieben + 2 neue Smoke-Tests.

6. **`chore(release): v0.73`** — APP_VERSION 0.72→0.73, HISTORY, CLAUDE.

### Workflow

V1 → V2 (Self-Review fuegte 8+ fehlende Punkte hinzu: Konkretes Daten-
modell, Threading-Locks, Auto-Save-synchron, Cold-Start-Verhalten,
Bandwechsel-atomar) → DeepSeek-Reviewer-Auftrag (5 echte Findings:
Dirty-Tracking als set, Commit-Reihenfolge atomar via None-safe Hook,
Write-Error-Handling, Bandwechsel atomar via existing update_stations,
Cache Band-agnostisch ohne LOGGED_BANDS-Filter).

DeepSeek-Verworfen: JSON → SQLite (Mike-KISS-Wunsch JSON, konsistent
zu LocatorDB), Dedup im Store (Canvas dedupt eh), Lock-Contention-
Sorgen (Decode-Frequenz < 1/s), `_handle_ft2/ft4_mode`-Halluzination
(gibt's nicht — Modus orthogonal zu Reception-Mode).

### Tests

430 → 442 gruen (+12: 10 RxHistory-Tests + 2 Smoke-Tests fuer entfernte
Combos, 2 alte Tests umgeschrieben).

### Field-Test offen

- App-Restart-Test: vor Restart 30m FT8 + 40m FT8 empfangen, App
  schliessen, neu starten, Karte oeffnen → 30m oder 40m angezeigt mit
  letzten 60 Min Empfangsdaten.
- Bandwechsel-Test: Karte offen, Wechsel 40m→20m → Karte zeigt sofort
  20m-Cache aus Disk + Live-Daten obendrauf.
- 60-Min-TTL: nach 1h+ keine Decode → Stationen verschwinden aus Karte.
- ~/.simpleft8/cache/rx_history/ enthaelt nach Save: bis zu 5 Files
  (LOGGED_BANDS × FT8) plus eventuell weitere Baender wenn Mike auf
  60m/80m/12m geht.


## 2026-04-30 v0.81 — Doppel-Report-Bug-Fix (Fix D)

**Symptom (Feldtest 30.04. nach v0.80-Release):**
Nach erfolgreichem TX-DT-Drift-Fix (v0.80) tauchte ein zweiter,
latenter Bug auf — der **Doppel-Report im QSO-Verlauf**:

```
08:32:45 [O] Mike → "DA1TST DA1MHH -21"        (initial-call)
08:33:00 [E] DA1TST → R+18                      (Antwort, decoded ~T+29.5s)
08:33:15 [O] Mike → "DA1TST DA1MHH -21"        (DOPPEL-Report!)
08:33:45 [O] Mike → "DA1TST DA1MHH RR73"       (endlich)
```

QSO-Pacing 6 Slots statt der ueblichen 4.

**Root Cause:**
`qso_sm.on_cycle_end()` lief in `mw_cycle.py:_on_cycle_start` (Z.501)
am SLOT-START — also BEVOR der Decoder die Antwort der Gegenstation
sehen konnte (Decoder gibt erst bei T+13.5s im Slot Bescheid).
Mit Fix A1 aus v0.80 (Retry-Trigger bei `timeout_cycles == 1` statt
`== 2`) wurde das sichtbar: der Retry feuerte VOR der Antwort →
Doppel-Report.

**Workflow (V1 → V2 → DeepSeek-R1 → V3):**
- V1 (Erstentwurf, ~280 Zeilen): "on_cycle_end komplett ans Slot-Ende
  verschieben"
- V2 (Self-Review, ~330 Zeilen): 3 Lueckenfunde, Position praezisiert,
  Pause-Edge-Case neu formuliert
- DeepSeek-R1-Review (Reviewer-Modus): **1 BLOCKER (P6) eigeninitiativ**
  — V2-Plan haette `CQ_WAIT`-Trigger und 3-Min-Gesamttimeout gebrochen
  bei Decoder-Hang/Skip. R1-Empfehlung: Aufspaltung statt
  Komplett-Verschiebung.
- V3 (Aufspaltung): nur den Retry-Pfad ans Slot-Ende, der Rest bleibt
  am Slot-START. R1-Findings P2 (FT4/FT2 Drift-Guard) und P3 (cross-
  sender Race) als Trade-offs akzeptiert.

**Fix-Implementation (3 atomare Commits):**

1. **`refactor(qso_state)`:** Neue Methode `on_decoder_finished()` mit
   dem Retry-Pfad fuer WAIT_REPORT/WAIT_RR73 (`timeout_cycles == 1`).
   `on_cycle_end()` behaelt: 3-Min-Gesamttimeout, WAIT_73-Tick,
   CQ_WAIT-Trigger, Counter-Inkrement, Max-Timeout-Check. Tests
   angepasst.
2. **`feat(mw_cycle)`:** `qso_sm.on_decoder_finished()` Aufruf in
   `_on_cycle_decoded` NACH den Message-Handlern, VOR
   `_refresh_diversity_freq_view`/`_run_ap_lite_rescue`/
   `_run_auto_hunt`. `_on_cycle_start` unveraendert.
3. **`chore(release)`:** v0.80 → v0.81, HISTORY.md + APP_VERSION.

**Tests:**
- `tests/test_modules.py`: 502 → 505 (3 neue Fix-D-Tests).
- 2 bestehende v0.80-Tests angepasst (testen jetzt
  `on_decoder_finished` statt `on_cycle_end` fuer den Retry-Pfad).
- Neue Tests:
  - `test_on_decoder_finished_skips_retry_when_state_advanced` —
    Kern-Fix-Verifikation
  - `test_on_cycle_end_no_longer_triggers_retry` — Regression-Schutz
  - `test_on_decoder_finished_safe_without_qso` — qso=None safety

**R1-Findings akzeptiert (dokumentiert, keine Code-Aenderung):**
- **P2 FT4/FT2 Drift-Guard:** Encoder-Vorlauf nach Fix:
  FT8 ~1.3s ✓, FT4 ~0.5s knapp, FT2 ~0.3s → Drift-Guard skipt zu
  N+2/N+4. Akzeptabel weil Gegenstation mehrere Slots wartet.
- **P3 cross-sender Race:** `cycle_start` (Timer-Thread) vs
  `cycle_decoded` (Decoder-Thread) — theoretisch race, praktisch
  selten (Decoder typ. <3s, Slot 15s).
- **P4 auto_hunt-Reihenfolge:** unveraendert. `auto_hunt` liest
  `qso_sm.state` weiterhin am Slot-Ende, jetzt direkt nach
  `on_decoder_finished` fuer maximale Aktualitaet.

**Verifikation noch ausstehend:**
- Real-QSO mit 2. Station auf Icom-Empfaenger: 4-Slot-QSO-Pacing
  (initial → R+18 → RR73 → 73) statt 6-Slot-Pacing.
- Mehrere QSOs hintereinander ohne Doppel-Report.

**Lessons (V1 → V3):**
- DeepSeek-R1 Reviewer-Modus muss klar geframed sein („du sollst
  KEINEN Code schreiben, nur reviewen") — sonst switcht R1 in
  Implementer-Modus. Erste R1-Anfrage hat Plan akzeptiert ohne die
  5 Reviewer-Fragen zu beantworten.
- Wenn man R1 explizit als Reviewer fragt, findet er BLOCKER die
  in der Self-Review uebersehen wurden (hier P6 CQ_WAIT-Regression).
- Aufspaltung statt Komplett-Verschiebung ist die richtige Strategie
  bei Logik die teils Decoder-abhaengig, teils Decoder-unabhaengig
  ist. KISS-konform.


## 2026-04-30 v0.82 — Doppel-Report-Bug-Fix Korrektur (Fix E)

**Status:** Fix D v0.81 hat den Doppel-Report-Bug NICHT geloest.
Im Real-QSO-Test zeigte sich derselbe Bug am Icom-Empfaenger:

```
095345 Mike → DA1TST DA1MHH -23     (initial-call)
095400 DA1TST → R+19                 (Antwort)
095415 Mike → DA1TST DA1MHH -23     (DOPPEL! — bug bleibt)
095430 DA1TST → R+19                 (nochmal)
095445 Mike → DA1TST DA1MHH RR73    (endlich)
```

Im SimpleFT8-Log dokumentiert (09:54:13): Retry feuert ZUERST,
dann erst kommt R+19-Verarbeitung. Genau die Reihenfolge die Fix
D verhindern sollte.

**Root Cause Fix-D-Annahme war FALSCH:**
Fix D V3 nahm an, `_handle_normal_mode` ruft `on_message_received`
direkt → State wird gewechselt VOR `on_decoder_finished`.

Realitaet: `on_message_received` haengt am SEPARATEN
`message_decoded`-Signal des Decoders. Decoder emittet zuerst
`cycle_decoded` (= `_on_cycle_decoded` mit Fix-D-Retry-Trigger),
DANN pro msg `message_decoded` (= `on_message_received` mit
State-Wechsel). Qt-Queue-FIFO laeuft der Retry-Trigger VOR den
State-Wechseln.

**Workflow voll durchlaufen (V1 → V2 → DeepSeek-R1 → V3):**
- prompts/decoder_signal_order_v1.md (~330 Zeilen, Erstentwurf)
- prompts/decoder_signal_order_v2.md (Self-Review +
  3-Min-Gesamttimeout/CQ_WAIT-Klarstellung, try/finally-Frage,
  Race cycle_start vs cycle_finished dokumentiert)
- DeepSeek-R1-Review (Reviewer-Modus): KEIN BLOCKER. Alle 5
  Tradeoffs akzeptiert (Decoder-Hang, Race, try/finally).
- prompts/decoder_signal_order_v3.md (R1-Bilanz dokumentiert)

**Fix-Implementation (3 atomare Commits):**

1. **`feat(decoder)`:** Neues Signal `cycle_finished = Signal()` in
   `Decoder` (decoder.py:107). In `_process_cycle` emittet nach
   allen `message_decoded`-Calls (auch im else-Branch fuer leere
   Slots). 1 neuer Test fuer Reihenfolge-Garantie.
2. **`feat(mw_cycle)`:** `_on_cycle_finished()` haengt am neuen
   Signal, ruft `qso_sm.on_decoder_finished()`. Aufruf in
   `_on_cycle_decoded` ENTFERNT (war Fix D's falsche Position).
   `mw_radio.py` 1 neue connect-Zeile.
3. **`chore(release)`:** v0.81 → v0.82.

**Reihenfolge im GUI-Thread (Qt-FIFO pro Sender = Decoder):**
1. `_on_cycle_decoded(messages)` — Aggregation, `_assign_slot_parity`
2. Pro msg: `on_message_decoded` → `on_message_received` (state-Wechsel)
3. `_on_cycle_finished()` → `on_decoder_finished` sieht finalen state ✓

**Tests:** 505 → 507 (2 neue Fix-E-Tests).
- `test_decoder_signal_order_cycle_finished_last` —
  Reihenfolge-Garantie: cycle_decoded → message_decoded[*] → cycle_finished
- `test_decoder_cycle_finished_emits_on_empty_slot` —
  cycle_finished emittet auch bei leeren Slots

**R1-Findings akzeptiert (dokumentiert, keine Code-Aenderung):**
- P1 Decoder-Hang: skipt cycle_finished → on_decoder_finished
  laeuft nicht. CQ_WAIT/Gesamttimeout in on_cycle_end (Slot-START)
  tickt unabhaengig weiter.
- P4 Race cycle_start(N+1) vs cycle_finished(N): unterschiedliche
  Sender (Timer vs Decoder), theoretisch race, praktisch selten.
- P5 try/finally um Decoder-Emit-Sequenz: NEIN — bei Exception
  Slot ueberspringen sicherer als Halb-State-Tick.

**Verifikation noch ausstehend:**
- Real-QSO mit 2. Station auf Icom-Empfaenger: 4-Slot-QSO-Pacing
  und KEIN -XX-Doppelsenden nach R-Report.

**Lessons (Mike's Erinnerung "du arbeitest nicht den deepseek
workflow"):**
- Bei jedem Bugfix der NACH einem fehlgeschlagenen Bugfix kommt:
  Workflow nicht abkuerzen. V1→V2→R1→V3 durchziehen, KEIN
  "Quick-Fix"-Pfad.
- Eile fuehrt zu Annahmefehlern wie Fix D V3 (nahm an
  `_handle_normal_mode` ruft `on_message_received` direkt — tut
  es nicht).
- DeepSeek-R1 muss explizit als REVIEWER geframed werden, sonst
  switcht es in Implementer-Modus. War im 2. R1-Review von Fix-D
  bereits gelernt — und in V2-Reviewer-Frage hier wieder bestaetigt.


## 2026-05-01 v0.83 — Kalibrierungs-Dialog Auto-Close (Fix F)

**Mike's Wunsch:** "Verbesserung kalibrirung abgeschlossen muss mit
okay bestätigt werden und ist immer im vordergrund, im vordergrund
lassen okay weg nur 3 sekunden zur kenntnissnahme und dann fenster
weg verbessert den workflow".

**Aenderung in `mw_radio._show_calibration_done`:**
- `setModal(True)` ENTFERNT
- OK-Button + QHBoxLayout ENTFERNT
- `dlg.exec()` → `dlg.show()` + `raise_()` + `activateWindow()`
- NEU: `QTimer.singleShot(3000, dlg.accept)` Auto-Close nach 3s
- WindowStaysOnTopHint bleibt (gegen Hinten-Wandern, v0.79-Lesson)

**Workflow voll V1 → V2 → DeepSeek-R1 → V3:**
- prompts/calibration_dialog_autoclose_v1.md
- prompts/calibration_dialog_autoclose_v2.md
- prompts/calibration_dialog_autoclose_v3.md (R1-Bilanz: keine BLOCKER,
  P5-Test-Optimierung uebernommen, P3-Flicker-Risk akzeptiert,
  P4-Doppel-Klick-Edge via GUI-Lock entschaerft)

**Tests:** 507 → 510 (3 neue Smoke-Tests in
tests/test_calibration_dialog_smoke.py):
- test_calibration_done_uses_singleshot_3000ms (R1-P5-Pattern:
  monkeypatch QTimer.singleShot statt QTest.qWait)
- test_calibration_done_no_ok_button (Regression-Schutz)
- test_calibration_done_non_modal (Verifikation Mike kann weiterarbeiten)

**Atomare Commits (2):**
1. feat(mw_radio): _show_calibration_done auto-close 3s ohne OK
2. chore(release): v0.83 — Kalibrierungs-Dialog Auto-Close (Fix F)

**R1-Trade-offs akzeptiert (dokumentiert):**
- P1: WindowStaysOnTopHint deckt nicht 100% gegen macOS-Spaces-/
  Mission-Control-Edge-Cases ab — Hobby-Funk-Use-Case akzeptabel.
- P3: show()→raise_()→activateWindow() koennte minimalen Flicker
  haben (R1's Hinweis "show() last") — keine Aenderung,
  Standard-Pattern.
- P4: Doppel-Klick auf Kalibrieren-Button in 3s wuerde 2 Dialoge
  zeigen — durch `_set_gain_measure_lock(True)` waehrend
  Kalibrierung GUI-seitig entschaerft.

**Lessons:**
- Auch bei „trivialen" 10-Zeilen-Aenderungen findet R1 wichtige
  Edge-Cases (P4 Doppel-Klick, P5 Test-Performance). Voller
  Workflow rentiert sich auch hier.
- Mike-Bestaetigt 30.04.: „voller workflow auf jeden fall" — heute
  bestaetigt durch Anwendung auf den kleinsten Fix der Woche.



## 2026-05-01 v0.84 — Tertile-Analyse Statistik (Feature H)

**Mike's TODO seit Mai 2026:** Pooled-Mean-Statistik mit Konfidenzband
ohne Datencropping.

**Problem heute:** `scripts/generate_plots.py:_aggregate` (Z.848-866)
nutzte `min/max` der TÄGLICHEN Mittelwerte als shaded band. Bei 1
Tag: `min == max == pooled_mean` → Band null breit. Bei 2 Tagen
schmal. Effektiv Datencropping — hunderte Cycle-Werte werden auf
1-2 Tagesmittel reduziert, dann Min/Max davon.

**Loesung:** 33%/67%-Tertile aller Cycle-Werte direkt. Bei 1 Tag
mit ≥3 Zyklen zeigt das Band echte Slot-zu-Slot-Streuung.

**Kritisches R1-Finding (V2-Review):** das shaded band wurde gar
nicht GEZEICHNET — `mins/maxs` aus `_hours_x` wurden in keine
Plot-Funktion eingespeist. Mein V2-Plan haette nur tote
Berechnungen produziert. Final-V3 hat `fill_between` in
`create_stations_diagram` aktiviert.

**Aenderungen:**
- `_aggregate`: `statistics.quantiles(cycles, n=3, "inclusive")`
  fuer t33/t67. Schluessel `min`/`max` behalten (KISS, Konsumenten
  unveraendert). `daily_means`-Berechnung entfernt (R1-P6 obsolet).
- `create_stations_diagram`: NEU `ax.fill_between(xs, mins, maxs,
  alpha=0.15, zorder=2)` direkt nach der Mean-Linie.
- PDF-Texte (DE+EN): „shaded band = day-to-day variation" → „shaded
  band = middle third of slots (33%–67% tertiles)".
- Header-Doku: „Konfidenzband: 33%–67%-Tertile der Cycle-Werte".

**Workflow voll V1 → V2 → DeepSeek-R1 → V3:**
- prompts/tertile_analysis_v1.md (Erstentwurf, Test-Werte falsch
  gerechnet — V2 korrigiert)
- prompts/tertile_analysis_v2.md (Self-Review, exakte Test-Werte
  via `statistics.quantiles` verifiziert)
- DeepSeek-R1: 5 Tradeoffs/JA + **1 BLOCKER P6** (shaded band wird
  gar nicht gezeichnet, plus daily_means obsolet)
- prompts/tertile_analysis_v3.md (R1-BLOCKER eingebaut: fill_between
  in create_stations_diagram)

**Tests:** 510 → 514 (4 neue in tests/test_aggregate_tertiles.py):
- test_aggregate_tertiles_basic (12 Cycles, exakte t33/t67)
- test_aggregate_tertiles_fallback_under_3 (< 3 Cycles → pooled_mean)
- test_aggregate_tertiles_zero_cycles_skipped (0 Cycles)
- test_aggregate_tertiles_multiday (n_days korrekt aus dict)

**Statistik-Regenerierung:**
- Alle PNG/PDF-Outputs (DE+EN) erfolgreich neu generiert.
- Pooled-Mean-Linien unveraendert → Diversity-Gewinn-Zahlen
  (+88% / +124% auf 40m FT8) bleiben korrekt.
- Shaded Band visuell jetzt aussagekraeftig auch bei wenigen
  Messtagen.

**Atomare Commits:**
1. feat(plots): _aggregate Tertile (33%/67%) statt Min/Max der
   Tagesmittel
2. feat(plots): shaded band in create_stations_diagram aktivieren
   + PDF-Texte
3. chore(release): v0.84 — Tertile-Analyse Statistik (Feature H)

**R1-Trade-offs akzeptiert (dokumentiert):**
- P1 inclusive vs. exclusive: ~1% Abweichung egal bei ganzzahligen
  Station-Counts.
- P2 min/max-Keys behalten: KISS, kein Refactor.
- P4 Statistik-Push: bei naechstem Push-Text Methodenwechsel
  erwaehnen (Konfidenzband-Semantik geaendert).

**Lessons:**
- Pure-Logic-Tests testen NICHT, ob die Werte tatsaechlich
  GEZEICHNET werden. End-to-End-Verifikation ist bei Plot-Code
  Pflicht.
- R1's Final-Codereview hat den toten Code-Pfad gefunden, den ich
  ohne Reviewer-Brille nicht gesehen haette. Workflow erneut
  bestaetigt.



## 2026-05-01 v0.85 — Dead-Code-Cleanup (Cleanup I + Doc J)

**Mike's Anweisung:** "ich nehme alles mit vollen workflow ohne
mittlere aufgaben los" — alle kleinen TODOs gebuendelt.

**Entfernter Dead-Code:**

### `core/decoder.py`
- 5 `_AGC_*`-Konstanten (Z.51-55)
- `_apply_agc`-Funktion (Z.58-94, ~37 Zeilen)
- `self.input_sample_rate = 24000`-Member (Z.127, R1-P5-Finding)
- `self._agc_state = (1.0, 1.0)`-Init (Z.130)
- Auskommentierter Aufruf + Kommentar (Z.270-271)
- Header-Doku: "RMS Auto-Gain Control" durch "Noise-Floor-basierte
  Normalisierung" ersetzt (R1-Final-Review-Finding).

### `core/timing.py`
- `self._ntp_offset = 0.0`-Member (Z.36)
- TODO-Kommentar in `utc_now()` (war "ungetestet — Feldtest noetig")
- `utc_now()` vereinfacht: `return ntp_time.get_time() + self._ntp_offset`
  → `return ntp_time.get_time()`
- `sync_ntp()`-Methode (Z.62-70, nie aufgerufen)

### `tests/test_modules.py`
- 4 AGC-Tests entfernt (testeten nur die tote Funktion).

**Workflow voll V1 → V2 → DeepSeek-R1 → V3:**
- prompts/dead_code_agc_v1.md (V1 fokussiert auf AGC)
- prompts/dead_code_agc_v2.md (V2 Self-Review, Scope-Klarstellung)
- DeepSeek-R1: alles JA/NEIN klare Antworten + **P5 eigeninitiativ:
  `input_sample_rate` ist auch tot**
- Schritt-0-Verifikation fuer Doc J ergab: `sync_ntp` + `_ntp_offset`
  auch tot → V3 erweitert um timing.py
- prompts/dead_code_agc_v3.md (R1-Bilanz + Doc J integriert)

**Final-R1-Codereview:** "Alles OK" + 1 TRADEOFF (Header-Doku
inkonsistent zur entfernten AGC-Funktion) → in Folge-Commit gefixt.

**Tests:** 514 → 510 (4 AGC-Tests weg, alle anderen unveraendert).

**Atomare Commits:**
1. chore(decoder/timing): toten AGC-Code + input_sample_rate +
   sync_ntp + _ntp_offset entfernen
2. docs(decoder): Pipeline-Header an entfernte AGC-Funktion anpassen
   (R1-Final-Finding)
3. chore(release): v0.85 — Dead-Code-Cleanup

**Code-Reduzierung gesamt:** ~60 Zeilen.

**Lessons:**
- R1's P5-Initiative bringt auch in trivialen Cleanups Mehrwert
  (zusaetzlicher toter Member entdeckt).
- Schritt-0-Verifikation fuer Doc J zeigte dass der Scope groesser
  war als gedacht (`sync_ntp` + `_ntp_offset` zusaetzlich).
  V3-Erweiterung statt separater Workflow ist KISS-Win wenn der
  Cleanup-Scope thematisch zusammenpasst.



## 2026-05-01 (Doku-only) — Session-Lifecycle Workflow aktiviert

**Mike-Anweisung 01.05.2026 nach 3-Releases-Tag (v0.83 Fix F + v0.84
Feature H + v0.85 Cleanup I/J):** „stelle dir einen workflow zusammen
das wir uns erkentnisse offene punkte einstellungen wichtige sachen
bei start lesen und merken und bei feierabend sichern".

**Erstellt:** `SimpleFT8/docs/SESSION_WORKFLOW.md` v1.2 — verbindliches
Steuerdokument fuer Session-Orchestrierung analog zum Feature-Workflow
`docs/WORKFLOW.md` v1.1.

**Drei Phasen:**
- **Phase 1 (Start):** CLAUDE → MEMORY → HISTORY → HANDOFF lesen,
  Begruessung mit Stand.
- **Phase 2 (Arbeit):** Trivial direkt / Nicht-trivial via WORKFLOW
  v1.1 + 4-Datei-Update (HISTORY→HANDOFF→CLAUDE→Memory) nach jedem
  Punkt. Trivial-Klausel: <5 Zeilen brauchen keine Pflege.
- **Phase 3 (Feierabend):** Verifikations-Check + Bestaetigungs-Block.

**Workflow voll V1 → V2 (Self-Review) → R1-Review → V3 durchlaufen:**
Mike musste bei V1 mahnen weil ich den Skip selbst gemacht hatte (V1
ohne Self-Review). Wichtige R1-Findings (DeepSeek-R1 Reviewer-Modus):
- **KRITISCH P2/P7-1:** 2a↔2b-Widerspruch — V2 hatte „Trivial direkt"
  in 2a und „4-Datei-Update IMMER" in 2b → Trivial-Klausel in 2b
  explizit ergaenzt
- **P1:** MEMORY vor HISTORY in Lese-Reihenfolge (PFLICHT-Lessons
  sind strenger als Release-Verlauf)
- **P7-2:** HANDOFF.md MUSS im Backup mit drin (sonst „Heute neu
  beobachtet" verloren)
- **P4:** Versionsbump-Heuristik praezisiert: Cleanup → optional
  Patch statt Inflation

**Aktivierung (Doku-only Aenderungen, kein Versionsbump):**
- `FT8/CLAUDE.md` + `SimpleFT8/CLAUDE.md`: Header-Verweis auf
  SESSION_WORKFLOW.md mit 3-Phasen-Zusammenfassung
- `FT8/feierabend.md`: schlanker Pointer auf Phase 3
- `MEMORY.md` neu strukturiert: ⛔-PFLICHT-Eintraege ZUERST, dann
  user/feedback/project-Sektionen
- Neue Memory `feedback_session_lifecycle.md` als Pointer auf
  SESSION_WORKFLOW.md

**Lessons:**
- Workflow-Disziplin gilt auch fuer Workflow-Dokumente. V1 ohne
  Self-Review/R1 ist genau der Skip den der Workflow verbieten soll.
  Mike-Mahnung 01.05.: „hast du dir das nach den workflow noch mal
  als unabhaengige ki angeschaut ob es was zu ergaenzen oder
  optimieren gibt, hast du es zur revision nach deepseek geschickt"
  → V2 + R1-Review nachgeholt, 3 echte Findings.
- R1's KRITISCH-Finding (2a↔2b-Widerspruch) waere sonst zur
  Frust-Quelle geworden: Mike haette bei jedem Tippfehler 4 Files
  updaten muessen.


## 2026-05-01 v0.86 — Fix G: Falscher Kalibrierungstext im Normal-Modus

**Bug:** Normal-Modus + KALIBRIEREN → DXTuneDialog zeigte "Diversity Standard — Kalibrierung Xm"
statt "Gain-Messung — Kalibrierung Xm". Statusbar zeigte "DIVERSITY SETUP AKTIV".

**Root Cause:** `_get_mode_label` in `dx_tune_dialog.py` hatte nur 2 Fälle (DX/Standard),
kein dritter Fall für Normal-Modus. `scoring_mode="stations"` fiel immer in Diversity-Standard.
Statusbar-Text in `_set_gain_measure_lock` hardcodiert ohne Modus-Check.

**Fix:** Neuer `rx_mode`-Parameter in `DXTuneDialog.__init__`, neue `_get_mode_label()`-Methode,
`mw_radio._open_dx_tune_dialog` übergibt `rx_mode=self._rx_mode`, Statusbar modus-abhängig.
2 neue Smoke-Tests → 512/512 grün.

**Workflow-Lesson:** Fix wurde zunächst OHNE vollen V1→V2→R1→V3-Workflow implementiert →
Mike-Unterbrechung → Workflow nachgeholt → R1 bestätigt Korrektheit + 1 Test-Finding.
CLAUDE.md mit doppelter Workflow-Pflicht-Regel aktualisiert (kein Ausnahme mehr).


## 2026-05-01 v0.86+ — Test-Coverage-Erweiterung (AC-1 bis AC-4)

**Kontext:** V1→V2→R1→V3-Workflow für Test-Analyse. Mike: "lieber 100 Tests
zuviel als 1 zuwenig". R1-Review identifizierte 3 komplett ungetestete Module.

**AC-2: test_protocol.py (22 Tests)**
Parametrisierte Mathematik-Tests für FT8/FT4/FT2: symbol_duration,
signal_duration, waveform_samples, signal_duration < slot_time. get_profile()
Case-Insensitivity + Unknown-Fallback (FT8 Default). BAND_FREQUENCIES-
Vollständigkeit. FrozenInstanceError-Immutabilität (direkt + setattr).
FT4/FT2 gleiche Symbolanzahl, FT8 anders.

**AC-1: test_diversity_merger.py (10 Tests)**
DiversityMerger-Fusionslogik: A1/A2-Labels ohne Duplikat, Duplikat A1>2 und
A2>1 mit korrekten _snr_a1/_snr_a2-Feldern. Timeout-Pfade (nur A1 / nur A2).
Reset stoppt Timer + löscht Zustand. Kein Emit bei leerem Merge. Whitespace-
Normalisierung im Key. Signal emittiert exakt 1x.

**AC-3: test_ap_lite.py (24 Tests)**
generate_candidates() State 1/2/3, SNR-Clamping. APLite.on_decode_failed()
Buffer-Speicherung, Cache-Limit 3, disabled-Flag, leere/ungültige Callsigns.
try_rescue() Guards (Freq >30Hz, Timing 10-20s, State-3-keine-Kandidaten,
disabled). clear(). Singleton get_instance(). Kein Encoder/DSP.

**AC-4: test_modules.py Bereinigung**
5 AP-Lite-Duplikate aus test_modules.py entfernt (durch test_ap_lite.py
mit 24 Tests vollständig superseded). DSP-Sanity-Checks (align/costas)
in test_modules.py behalten.

**Gesamt:** 512 → 563 Tests (+56 neu, -5 Duplikate).
