# SimpleFT8 — Änderungshistorie

Diese Datei wird nur ergänzt, niemals gelöscht oder überschrieben.
Format: `## YYYY-MM-DD — Kurztitel` → Änderungen darunter.

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
