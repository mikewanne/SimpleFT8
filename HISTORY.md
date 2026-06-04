# SimpleFT8 — Änderungshistorie

Neue Einträge kommen OBEN dazu (Datei ist nach Version absteigend sortiert);
ältere werden per `tools/rotate_history.py` ins `history/`-Archiv ausgelagert.
Gelöscht wird nie etwas. Format: `## YYYY-MM-DD vX.YY — Kurztitel`.


> **Rotation:** Diese Datei fuehrt nur die letzten 30 Versionen. Aeltere Eintraege
> stehen in `history/HISTORY_archiv_NN.md` (grep dort, falls eine alte Version
> gesucht wird). Rotiert mit `tools/rotate_history.py`. Zuletzt: 2026-06-01.

> ⚓ **SICHERHEITSANKER vor DT-Umbau (03.06.2026):** Der auf **GitHub** liegende
> Stand `origin/main` = Commit **`22f3d07` (v0.98.63)** ist die **letzte Version
> mit der alten DYNAMISCHEN DT-Wert-Berechnung** (automatisches Dauer-Lernen aus
> den FT8-Stationen: measure-/operate-Phasen, Dämpfung, Sprung-Reset in
> `core/ntp_time.py`). Diese Version wurde zuletzt am 03.06. von der 2.-Juni-
> Arbeit gepusht. **Im Notfall wiederherstellen:**
> `git checkout 22f3d07 -- core/ntp_time.py ui/mw_cycle.py` (nur DT-Schicht) oder
> `git reset --hard 22f3d07` (kompletter Rückfall, verwirft den Umbau). Ab v0.99.0
> ersetzt der **manuelle Kalibrier-Button** die dynamische Dauer-Berechnung.
> *(Lokal nicht-gepusht beim Anker: `cfab444` v0.98.64 Mode-Abbruch-Fix + 2
> Multiband-TODO-Commits — die haben die alte DT-Berechnung ebenfalls noch.)*

> ⚓ **SICHERHEITSANKER vor WAIT_73-Verkürzung (04.06.2026):** Dieser Push-Stand
> (**v0.99.4**, gepusht auf `origin/main`) ist die **letzte Version mit der langen
> Auto-Hunt-Horchphase** — nach RR73 werden **3 Slots (45 s)** auf ein 73 gewartet,
> bevor Auto-Hunt die nächste Station ruft (`core/qso_state.py on_cycle_end`,
> WAIT_73 `timeout_cycles >= 3`). Geplanter nächster Schritt: **3 → 2** (WSJT-X-
> konform, FEATURES §24). **Im Notfall zurück:** `git checkout <dieser-Commit> --
> core/qso_state.py` oder `git reset --hard <dieser-Commit>`. Begründung +
> Recherche + DeepSeek-Bestätigung: **FEATURES §24**, Backlog: **TODO.md**.
> *(Nebenbei am 04.06.: Mike hat versehentlich die DT neu kalibriert [Wert ins
> Minus, −0.69] → `~/.simpleft8/dt_corrections.json` manuell auf Hardware-Default
> 0.26 zurückgesetzt; greift nach App-Neustart.)*

## 2026-06-04 v0.99.7 — Auto-Hunt aus akkumuliertem Pool + Frische-Fenster + „gearbeitete auch anrufen"-Schalter

**Voller autonomer Workflow** (V1→V2→DeepSeek-Plan-R1 [GO, 3 Korrekturen]→V3→Code→
Tests→DeepSeek-Final-R1 [PUSH FREIGEBEN, 0 Blocker]).

**Anlass (Mike-Field, abgestimmt, vor Compact gesichert in TODO.md):** Zwei Probleme
aus einem Guss.

1. **Auto-Hunt sah nur den Moment-Slot.** `mw_cycle._run_auto_hunt(messages)` gab
   `select_next` nur die Decodes EINES 15s/7,5s-Slots. Die RX-Liste akkumuliert dagegen
   über `core/station_accumulator.py` (CQ-Rufer bis `AGING_SLOTS_CQ_CALLER=20` Slots
   sichtbar). Folge: man SIEHT eine 45s-alte CQ-Station in der Liste, Auto-Hunt
   ignoriert sie, weil sie in genau diesem Moment nicht ruft. Bei FT4 schlimmer
   (kürzere Slots). Bei leerem Decode-Slot wählte Auto-Hunt gar nichts.
2. **Kein „gearbeitete trotzdem anrufen"-Schalter.** select_next filterte gearbeitete
   Stationen (Band+Mode-genau, P169) IMMER raus — für Diplom-Jagd (z.B. 250 USA-QSOs
   im neuen Zeitraum) will Mike sie optional wieder anrufen.

**Lösung (KISS, additiv, select_next-Signatur unverändert):**

- **Pool statt Moment-Slot.** Neue Modul-Konstante `core/auto_hunt.py:AUTO_HUNT_FRESH_SLOTS
  = {"FT8":3,"FT4":3,"FT2":3}`. Neuer Helper `mw_cycle._build_auto_hunt_pool()` baut die
  frischen CQ-Rufer aus dem rx-mode-passenden Akkumulator (`_diversity_stations`):
  `is_cq` (Live-Property aus field1 → eine ins QSO gewechselte Station fällt automatisch
  raus) UND `(now - _last_heard) <= fresh*slot + 1.0` (P157 setzt `_last_heard` immer;
  +1,0 s = Jitter-Puffer, DeepSeek-R1). `_run_auto_hunt` übergibt diesen Pool an
  `select_next`. Pool ist aktuell — `accumulate_stations` läuft in `_on_cycle_decoded`
  VOR `_run_auto_hunt`. **Hauptgewinn:** Auto-Hunt wählt jetzt auch bei leerem
  Moment-Slot aus dem Pool. **„3" begründet:** eine CQ-Station ruft modus-invariant jeden
  2. Slot → 3 Slots = überall ≤1 verpasster Ruf Puffer. FT4 ruft HÄUFIGER (kürzere
  Slots), fängt man schneller — FT4 nur datenbasiert auf 4 anheben, NICHT auf Verdacht.
- **„gearbeitete auch anrufen"-Schalter.** `core/auto_hunt.py`: Instanz-Flag
  `_skip_worked=True` (Default) + Setter `set_skip_worked`. Der Worked-Filter-Block in
  `select_next` (inkl. `n_before_worked` + `all_worked`-Emit) läuft nur noch unter
  `if self._skip_worked and self._qso_log is not None:` (DeepSeek-Korrektur: alles
  geschlossen im Block, kein NameError-Pfad). `config/settings.py` DEFAULTS:
  `auto_hunt_call_worked: False`. `ui/settings_dialog.py`: Checkbox „Schon gearbeitete
  Stationen auch anrufen" (Tab „FT8 & Diversity") + load/save/reset. `mw_cycle._run_auto_hunt`
  setzt das Flag pro Slot live: `set_skip_worked(not settings.get("auto_hunt_call_worked",
  False))` → Settings-Änderung wirkt sofort, kein Dialog-Hook. **Steuert NUR Auto-Hunt** —
  der NEUE-Filter der RX-Liste bleibt der getrennte Anzeige-Filter.
- **Klarere Meldung.** `main_window._on_auto_hunt_all_worked`: „Auto-Hunt: alle N aktiven
  CQ-Rufer auf {Band} {Mode} schon gearbeitet" (N = Pool-Größe = was man sieht, nicht
  mehr 1-2 Moment-Slot). Im Diplom-Modus (`_skip_worked=False`) feuert sie bewusst nie.

**DeepSeek Plan-R1 GO** (3 Korrekturen eingebaut: +1,0 s Jitter-Puffer statt halber Slot;
Worked-Filter explizit klammern; Fallback-Pool — als Kommentar statt Log-Zeile umgesetzt,
da der Normal-Pfad effektiv tot ist [Auto-Hunt nur in Diversity] und ein Import dafür der
Overengineering-Tick wäre). **Final-R1 PUSH FREIGEBEN** (7 Prüfpunkte, 0 Blocker:
Worked-Block geschlossen, Frische defensiv, kein Race, Doppel-Pick durch
`_recent_qso`-Cooldown ausgeschlossen, Hardware unberührt).

**Reine State-/Auswahl-/Anzeige-Logik, kein TX-Pfad-Eingriff, ANT1/ANT2 unberührt**
(Auto-Hunt-TX läuft unverändert über `start_qso`). Tests 2405→**2417** (+12
`test_autohunt_pool.py`: Frische-Konstante, skip_worked-Default/Setter, Worked an=filtert/
aus=behält, all_worked-nie-im-Diplom-Modus, Pool-Frische frisch-drin/alt-raus,
is_cq-Live-Filter, +1s-Jitter-Beweis, modus-aware FT4-Fenster, Default-bei-unbekanntem-
Modus, leer-bei-allen-stale; `test_p123` T2-Mock um `_build_auto_hunt_pool`-Stub ergänzt).
**NICHT gepusht, Field-Test pending.**

## 2026-06-04 v0.99.6 — HALT→STOPP: ein zentraler Notstopp für alles (v0.99.4-Armieren raus)

**Voller Workflow (V1→V2→DeepSeek-Plan-R1 [PLAN ÜBERARBEITEN → TUNE-Träger
ergänzt] →V3→Code→Tests→Final-R1 PUSH FREIGEBEN). Mike-Wunsch, sicherheitsrelevant.**

**Anlass (Mike-Field, akut):** Auto-Hunt UND OMNI-CQ ließen sich nicht mehr
stoppen. Zwei Ursachen aus dem v0.99.4-HALT-Umbau: **(A)** Der HALT-Knopf
(`btn_cancel`) war **ausgegraut**, sobald Auto-Hunt/OMNI liefen aber gerade kein
QSO aktiv war (`mw_qso` Enable-Logik kannte nur „QSO oder Normal-CQ") + während
der Diversity-Messung → **kein Notaus**, Catch-22 mit „erst HALT drücken". **(B)**
Modus-Toggle-OFF rief das smarte `_on_cancel`, das bei laufendem QSO nur
**armierte** statt zu stoppen → Knopf-Farbe wechselte, OMNI lief weiter.

**Mike-Entscheidung:** „HALT heißt Notstopp." Button **„HALT" → „STOPP"** +
Tooltip „Alles wird sofort abgebrochen". STOPP-Knopf + Auto-Hunt-Toggle +
OMNI-Toggle rufen **alle dasselbe `_execute_full_halt()`** — kompromisslos sofort,
kein Armieren/Vormerken. Die ganze v0.99.4-Deferred-Mechanik entfernt.

**`_execute_full_halt` = Notstopp-Modul für JEDE TX-Quelle:** Encoder-TX, CQ,
laufendes QSO, OMNI, Auto-Hunt + **NEU (DeepSeek-Plan-R1-Catch):** **TUNE-Träger**
(`_tune_stop(None)` wenn `_tune_active` — der lief über einen EIGENEN Weg, NICHT
`_abort_active_tx`; bei aktivem TUNE blieb der Träger trotz STOPP an = 🔴
Sicherheitsverstoß „TX jederzeit beenden") + **Einmess-Dialog** (`_dx_tune_dialog.reject()`)
+ **Diversity-Gain-Mess-Lock** (`_set_gain_measure_lock(False)`). STOPP-Knopf
**IMMER drückbar** (`btn_cancel.setEnabled` aus `_on_state_changed` + aus beiden
mw_radio-Lock-Methoden `_set_cq_locked`/`_set_gain_measure_lock` entfernt).

**Entfernt:** `_arm_deferred_halt`, `disable_cq_resume`, `QSO_IN_EXCHANGE_STATES`,
`set_halt_armed`/`_halt_armed_style`/`_halt_armed`, IDLE-Armier-Block, „erst
HALT"→„erst STOPP". `cancel()` setzt jetzt `_was_cq=False` (DeepSeek 🟡).

**Hardware:** reine State-/UI-Logik, **kein TX-Antennen-Eingriff (ANT1=TX);** im
Gegenteil — STOPP schaltet jetzt JEDEN Träger ab (Sicherheits-PLUS). DeepSeek
Plan-R1 fand die TUNE-Lücke (Plan überarbeitet) + Final-R1 **PUSH FREIGEBEN** (alle
TX-Pfade abgedeckt, Reihenfolge sicher, idempotent, keine toten Reste). Tests
2402→**2405** (`test_halt_unified.py` neu, 14: alle TX-Quellen + Bug-A-Source-
Regression „btn_cancel nie ausgegraut"; test_p81 Text HALT→STOPP). **NICHT
gepusht, Field-Test pending.**

## 2026-06-04 v0.99.5 — WAIT_73-Horchphase nach RR73 von 3 auf 2 Slots verkürzt

**Voller Workflow (V1→V2→DeepSeek-Plan-R1→V3→Code→Tests→Final-R1; Plan-R1 0 Bugs
Off-by-one bestätigt, Final-R1 PUSH FREIGEBEN 0 Bugs/0 Risiken). Mike-Wunsch nach
Field-Beobachtung + WSJT-X-Recherche.**

**Anlass:** ~60 s Pause zwischen abgeschlossenem QSO und nächstem Auto-Hunt-Ruf
(Field 04.06.). Ursache (FEATURES §24): nach dem Senden von RR73 ist das QSO
bereits via `qso_complete` geloggt, aber `on_cycle_end` WAIT_73-Branch horchte
**3 Leer-Slots (45 s)** auf ein 73, das im verkürzten FT8-Modus meist nie kommt;
Auto-Hunt darf in der Zeit nichts picken (`qso_idle`-Guard). WSJT-X-Recherche +
DeepSeek bestätigt: der **verkürzte** Modus (RR73) wartet NICHT auf ein 73 (nur
der lange RRR-Modus) — er beobachtet genau **1 Empfangs-Slot** (Nachsende-Schutz).

**Fix (`core/qso_state.py`):** neue Modul-Konstante **`WAIT_73_MAX_CYCLES = 2`**
(mit WSJT-X- + Off-by-one-Begründung im Kommentar); der WAIT_73-Branch nutzt sie
statt der hartcodierten `3`. **„2" ist die Untergrenze:** `on_cycle_end` triggert
am Slot-START, der erste (einzig relevante) RX-Slot N+1 wird dadurch noch voll
abgewartet (73/R-Report kommen via `on_message_received`). „1" würde am N+1-START
triggern BEVOR dessen Decode das 73 sieht → 73 fiele in den IDLE-Branch (verpasst).
Höflichkeits-73-Pfad, `wait_73_retries`, `_resume_cq_if_needed`, `MAX_QSO_DURATION`-
Check **unverändert**. Pause ~60→45 s (WAIT_73-Teil 45→30 s).

**Stufe 1 von 2:** Höflichkeits-73 bleibt bewusst als **Kompatibilitäts-Brücke** zu
langen/IC-7300-Stationen (Stufe 2 = ganz entfernen wurde verworfen — null Zeitgewinn,
mehr Risiko). **Keine 2-Modi-Einstellung** (verkürzt ist voll kompatibel zum langen
Modus — FT8-Protokoll interoperabel; ein Schalter wäre Overengineering).

**Hardware:** reine Timing-/State-Logik, **kein TX-Antennen-Eingriff (ANT1=TX
unberührt).** Tests 2398→**2402** (+4 `test_wait73_threshold.py`: Konstante==2,
kein Trigger vor Schwelle, Trigger genau bei Schwelle, Off-by-one-Garantie [73 im
ersten RX-Slot gefangen, bräche bei Schwelle 1 — Mutationsbeweis]; `test_p33` T2.3
+ `test_p1_10` Test 8 konstantengerecht angepasst). **NICHT gepusht — Field-Test
pending** (Rückfallpunkt `bfa20dd` gepusht; Notfall `git checkout bfa20dd --
core/qso_state.py`).

## 2026-06-04 v0.99.4 — Einheitliche Bedienung über HALT + smartes HALT (Ruf sofort / QSO deferred)

**Voller Workflow (V1→V2→DeepSeek-Plan-R1→V3→Code→Tests→Final-R1; Plan-R1 mit 2
Korrekturen, Final-R1 PUSH FREIGEBEN 6/6). Mike-Wunsch.**

**Anlass:** Asymmetrie in der Bedienung — aus Auto-Hunt musste man **erst HALT**
drücken, bevor OMNI-CQ ging; umgekehrt (OMNI→Auto-Hunt) ging es **direkt**. Das
machte „in der Bedienung kirre" und konnte ein laufendes QSO unhöflich abbrechen.

**Lösung (Mikes Modell):** ALLES über HALT — und HALT wird intelligent.
- **Modus-Buttons (OMNI/Auto-Hunt) starten nur aus Ruhe.** Läuft der andere Modus
  oder ein Ruf/QSO → refuse + Hinweis „erst HALT" (kein direktes Supersede mehr;
  beide Buttons jetzt symmetrisch).
- **HALT smart:** ein **Ruf** (wir rufen, die Gegenstation hat NICHT geantwortet —
  Zustände bis `WAIT_REPORT`) wird **sofort** gestoppt. Ein **laufendes QSO im
  Austausch** (ab `TX_REPORT`, Rapport empfangen → wird geloggt) → **armiert**: das
  QSO läuft + loggt regulär zu Ende, dann automatisch IDLE. Info-Zeile *„HALT —
  stoppt nach QSO-Ende (QSO läuft noch)"* + oranger **„HALT •"**-Button.
- **2× HALT = sofort hart abbrechen** (Notausgang, auch mitten im QSO).

**`core/qso_state.py`:** neue **`disable_cq_resume()`** (löscht `cq_mode` + `_was_cq`
+ `_caller_queue`) — reines `stop_cq()` ließ `_was_cq`/Queue stehen, `_resume_cq_if_
needed` hätte CQ nach QSO-Ende wiederbelebt (**DeepSeek-R1-Gold-Finding**). Neue
Konstante **`QSO_IN_EXCHANGE_STATES`** = die 5 Austausch-Zustände (Rapport empfangen;
BEWUSST OHNE `TX_CALL`/`WAIT_REPORT` = Ruf).

**`ui/mw_qso.py`:** `_on_cancel` ist jetzt ein **Dispatcher** (armiert→`_execute_full_
halt` / Austausch→`_arm_deferred_halt` / Ruf→`_execute_full_halt`). `_arm_deferred_
halt` stillt Auto-Hunt/OMNI/CQ-Resume + pending-Insert, **bricht das QSO NICHT ab**
→ es läuft mangels Resume von selbst nach IDLE aus. `_execute_full_halt` = bisheriges
hartes HALT (`cancel()`+`_abort_active_tx`) + armiert-Reset. `_on_state_changed` löst
das armiert-Flag bei IDLE auf (einzige Aufhebe-Stelle).

**`ui/main_window.py`:** Modus-Button-Start-Guard (nur aus `IDLE`/`CQ_WAIT` + anderer
Modus inaktiv); OFF-Zweige delegieren an `_on_cancel()` mit `is_active()`-Re-Entry-
Schutz (**DeepSeek-R1**: stop→setChecked(False)→toggled feuert nicht erneut).
`_halt_armed`-Init. **`ui/control_panel.py`:** `set_halt_armed()` (Button-Optik).

**Reines State-/UI-Verhalten, kein TX-Antennen-Eingriff, ANT1/ANT2 unberührt.**
Tests 2387→**2398** (+11 `test_halt_unified.py`; 12 Bestands-Tests auf das neue
Verhalten angepasst: Supersede→Refuse, Source-Checks→`_execute_full_halt`, Mock-
Guards). NICHT gepusht, Field-Test pending.

## 2026-06-03 v0.99.3 — PSK-Timer-Spin behoben (4GB-Debug-Log-Flut) + OMNI-Diagnose-Marker

**Mike-Field: Debug-Logdatei war 4 GB groß; separat: Auto-Hunt→OMNI-Wechsel
dauerte ~1:45.** (DeepSeek R1 6/6 für den Log-Fix; Marker = reine Instrumentierung.)

**Teil 1 — PSK-Timer-Spin (Log-Flut + CPU):** Die tägliche Debug-Datei
(`~/.simpleft8/debug_*.log`) wuchs an EINEM Tag auf 4 GB — geflutet mit
`[PSK] SKIP — _has_sent_cq=False` (tausende Zeilen/s). **Root Cause:**
`_reset_psk_polling_on_change` (Band-/Modus-Wechsel) startet den PSK-Timer mit
`start(0)` (Sofort-Fetch); ein QTimer mit Intervall 0 feuert so schnell wie die
Event-Loop kann. In `_fetch_psk_stats` lag die Intervall-Umschaltung HINTER dem
`_has_sent_cq`-Return → solange kein CQ raus war (Bandwechsel setzt
`_has_sent_cq=False`) blieb der Timer bei 0 und spinnte endlos. **Fix:** Intervall-
Umschaltung VOR den Return ziehen → Timer verlässt das 0-Intervall nach dem ersten
Tick IMMER (egal ob CQ); Sofort-Fetch bei gesetztem `_has_sent_cq` bleibt erhalten;
Flut-SKIP-Logzeile entfernt. Die bestehende Retention (`cleanup_old_files
keep_days=1` in `main.py`) löscht alte Tage weiter — der Flood war der Größen-
Treiber, nicht fehlende Bereinigung. Altlasten (06-02 2 GB + 06-03 4 GB) manuell
gelöscht (~6 GB reclaimed; `debug_log` öffnet/schließt pro Write → gefahrlos).
Tests 2384→**2387** (+3 `test_psk_timer_no_spin.py`, Fake-Self).

**Teil 2 — OMNI-CQ Diagnose-Marker:** Um zu SEHEN (statt zu raten) warum der
Auto-Hunt→OMNI-Wechsel ~1:45 dauerte, `debug_log("OMNI", …)`-Marker an den
Lifecycle-Stellen: `omni_cq` START/STOP/PAUSE/RESUME + `on_cycle_start` (Early-
Return gesplittet: nur aktiv+pausiert loggt „slot SKIP — paused", inaktiv still;
+ „slot SKIP — parity fresh/want", „TX CQ …", „TX SKIP — encoder busy");
`mw_qso._maybe_resume_omni` (was_active/caller_queue + Pfad). Alle pro-Slot
bounded, no-op wenn Debug aus. **Reines Logging, kein Verhaltenswechsel.**

**Bekannt + verifiziert (Teil-Befund zum 1:45):** `omni_cq.resume_after_qso`
behält nach einem QSO die ALTE Parität (`_cq_tx_even`) statt den nächsten freien
Slot zu nehmen — kostet ≤1 Slot (Mikes „even→even"-Beobachtung). Das erklärt aber
NUR ≤1 Slot, nicht 1:45 → der größere Blocker wird mit den Markern beim nächsten
Wechsel sichtbar gemacht, dann gezielter Fix (separat, voller Workflow). **Kein
TX-/Antennen-Eingriff.** NICHT gepusht.

## 2026-06-03 v0.99.2 — DT-Kalibrier-Knopf (⏱) nur auf FT8 sichtbar (FT4/FT2 ausblenden)

**Voller Workflow (DeepSeek Final-R1 4/4 bestätigt). Mike-Wunsch.**

Der ⏱-Kalibrier-Knopf war bisher immer sichtbar; auf FT4/FT2 zeigte der Handler nur
eine Info „nur auf FT8". Mike: auf FT4 (und später FT2, wenn aktiviert) **ganz
ausblenden**, damit man nicht versehentlich klickt (DT wird ohnehin nur aus FT8
gemessen). Überschreibt bewusst die frühere „Info-statt-Ausblenden"-KISS-Entscheidung
— Fehlklick-Schutz ist Mike wichtiger.

- `ui/rx_panel.py`: neue Methode **`set_calibrate_visible(visible)`** →
  `btn_calibrate.setVisible` (QHBoxLayout kollabiert das versteckte Widget).
- `ui/mw_radio.py:_on_mode_changed` (zentraler Mode-Hook, deckt auch programmatische
  Pfade ab; Re-Klick/Gain-Lock-Early-Returns davor): `set_calibrate_visible(mode ==
  "FT8")`.
- `ui/main_window.py`: Initial-Sichtbarkeit mode-abhängig (Start = FT8 → sichtbar).
- FT8-Guard in `_on_calibrate_dt` BLEIBT als Sicherheitsnetz (DeepSeek: robust, nicht
  redundant — fängt einen seltenen Stray-Signal-Fall ab).

**Reines Sichtbarkeits-Feature, kein TX-/Antennen-Eingriff.** DeepSeek Final-R1: 4/4
(einziger Mode-Hook, kein Stuck-State nach Rückwechsel, Guard sinnvoll, KISS). Tests
2380→**2384** (+4 `test_calibrate_button_ft8only.py`: isHidden + Source-Wiring-Checks).
NICHT gepusht.

## 2026-06-03 v0.99.1 — Eingeklappter RADIO-Header: Netto-Watt + farbiges SWR beim Senden

**Voller Workflow (Plan-R1 GO + Final-R1 PUSH FREIGEBEN). Mike-Wunsch (heute schon
besprochen, Plan lag in `/tmp/ds_radio_header.md`).**

Die eingeklappte RADIO-Kachel zeigte bisher nur die eingestellte Leistung
(„— 80 W"). Jetzt ergänzt sie beim **Senden** die Netto-Leistung (FWD durchs SWR
runtergerechnet) + das SWR (farbig per Ampel): **„— 80 → 58 W · SWR 1.2"**. So sieht
man auch minimiert, was rausgeht. Im Empfang (kein TX) fällt der Zusatz weg → wieder
„— 80 W".

**`ui/control_panel.py`:**
- Neuer Modul-Helper **`swr_color(swr)`** (`<1.5` grün, `<2.5` gelb, sonst rot) —
  DRY: `update_swr` nutzt ihn jetzt auch (vorher inline dupliziert).
- **`_refresh_radio_status_label`** erweitert: bei `_last_watt > 0` (TX, gleicher
  Guard wie `_refresh_netto`) hängt es `→ {netto} W · SWR {x.x}` an, SWR-Teil über
  einen Rich-Text-`<span style="color:…">` eingefärbt; die Label-Grundfarbe
  (`#00aacc` türkis) bleibt für den Watt-Teil. Power `None` + TX → ohne „→"-Präfix.
- **Live-Trigger:** `update_watt`/`update_swr`/`reset_swr_display` rufen den
  Header-Refresh. Der FWDPWR-Meter (`mw_tx.py:836`) ruft `update_watt` pro Tick —
  im RX ~0 → `_last_watt`→0 → Header automatisch zurück auf „— {p} W".
- **`getattr`-Default** für `_last_watt`/`_last_swr_for_netto`: der Refresh läuft in
  `__init__` VOR deren Initialisierung (Init-Reihenfolge; mit Default abgefangen).

**Reines Anzeige-Feature, kein TX-/Antennen-Eingriff, ANT1/ANT2 unberührt.**
DeepSeek Plan-R1 GO + Final-R1 PUSH FREIGEBEN (5 Punkte, 0 Blocker; Rich-Text-
AutoText reicht, getattr-Fix sauber). Tests 2370→**2380** (+10
`test_radio_header_collapsed.py`; P156-Netto-Tests weiter grün). **✅ Field-validiert
(Mike am Radio 03.06.):** „SWR und Watt-Zahl super zu sehen". NICHT gepusht.

## 2026-06-03 v0.99.0 — DT-Korrektur: dynamisches Dauer-Lernen RAUS, manueller Kalibrier-Knopf REIN

**Großer Umbau (voller Workflow: V1→V2→DeepSeek-R1→V3→Code→Tests→Final-R1, beide
DeepSeek-Runden PUSH FREIGEBEN). Mike-Entscheidung 03.06.2026.**

**Vorgeschichte (warum):** Die automatische DT-Lernschleife in `core/ntp_time.py`
(Mess-/Operate-Phasen, Dämpfung, Sprung-Reset, Fast-Convergence) hatte sich über
Tage als fragil erwiesen — der gelernte Wert pendelte, sprang ins Minus, und ein
Modus-Wechsel-Übergang (FT8→FT4→FT8) verdarb ihn (Decoder-Race lieferte eine
verzerrte Übergangs-Mess-Runde → der Median zog die Korrektur weg). Folge: OMNI-CQ
sendete statt 15s mal 30s, mal 60s (negativer Korrekturwert → Encoder-Drift-Guard).

**Warum nicht einfach ein fester Konstanten-Wert?** Mikes Ferienhaus-iMac (2015)
hat eine **defekte Pufferbatterie** und hängt nicht dauerhaft am Strom → die
System-Uhr driftet je nach Standzeit um 3–5 Sekunden (mal vor, mal nach). Ein
fester Wert würde veralten; macOS-NTP greift erst verzögert/nur online. Es braucht
also eine **nachjustierbare** Korrektur — aber als **bewusste Einmal-Messung auf
Knopfdruck**, nicht als fragile Dauer-Regelung.

**Lösung (Mikes Modell):** Manueller Kalibrier-Knopf. Der Wert ändert sich NUR auf
Druck → stabil (kein Pendeln, kein Übergangs-Bug, kein OMNI-Takt-Problem) UND
nachjustierbar (am Ferienhaus per Klick). **Die gute alte Median+MAD-Berechnung
bleibt** — sie läuft jetzt nur manuell statt automatisch.

**`core/ntp_time.py` (Kern-Umbau):**
- **Raus:** `_phase`/`_cycle_count`/`_measure_buffer`, `update_from_decoded`
  (Lernen), Sprung-Reset (`abs(median)>1→0`), `DAMPING`, `INITIAL/STEADY_MEASURE_
  CYCLES`, `OPERATE_CYCLES`, `DEADBAND`, Fast-Convergence-Konstanten, `reset()`.
- **Neu `record_samples(dt_values)`:** puffert NUR (kein Lernen) — FT8-Slots in
  `deque(maxlen=RECENT_SLOTS=3)` (~45s gleitendes Fenster); setzt die Anzeige-
  Werte `_last_median_dt`/`_last_sample_count` für alle Modi (informativ).
- **Neu `calibrate() → (ok, meldung)`:** flacht das Fenster, `< MIN_STATIONS(5)`
  → `(False, "zu wenige FT8-Stationen …")`; sonst MAD-Filter → Median der
  Residuen → **`_correction += median`** (INKREMENTELL — die `m.dt` sind Residuen
  nach der aktuellen Korrektur, ein Klick konvergiert voll; voller Schritt, KEINE
  Dämpfung) → symmetrischer Clamp ±1.0 → `_save_current()`. **KEIN Negativ-Riegel**
  (bei vorlaufender Uhr ist ein negativer Wert legitim — Mike-Anweisung).
- `set_mode`/`set_band` leeren das Kalibrier-Fenster (frischer Start nach Wechsel).
- Unverändert: `get_time()` (reine FT8-Basis für den Slot-Takt — v0.98.63-Fix
  intakt), `get_correction()` (Basis + `_MODE_DELTA`, RX-Decode + Anzeige),
  `_load_saved()` (inkl. Migration alt→global), `_save_current()`, MAD-Filter,
  `set_hardware_default(0.26)`, `MAX_CORRECTION`.

**UI:** ⏱-Knopf in der Empfangs-Leiste (`ui/rx_panel.py`, neben 🔊, Signal
`calibrate_requested`). Handler `ui/mw_radio.py:_on_calibrate_dt` — nur auf FT8
(sonst Info „nur auf FT8 möglich"; KISS statt Button-Ausgrauen), Ergebnis in die
QSO-Info-Zeile + Statusbar sofort aktualisiert. `ui/mw_cycle.py`:
`update_from_decoded`→`record_samples`. `ui/main_window.py` Statusbar ohne `_phase`
(zeigt festen Wert oder „DT: —").

**Hardware:** reines Timing/Anzeige, **kein TX-Antennen-Eingriff** (ANT1=TX,
ANT2=RX). DeepSeek Plan-R1 GO (alle 10 Punkte) + Final-R1 PUSH FREIGEBEN (9
Prüfpunkte, 0 Blocker).

**Tests 2358→2368 (+10):** neu `test_dt_calibrate.py` (18 Tests); die Lern-/
Phasen-/DEADBAND-/`reset()`-Tests in `test_modules.py`/`test_p48_dt_optimization.py`/
`test_p14_dt_symmetry.py` durch Kalibrier-Äquivalente ersetzt (Features existieren
nicht mehr); Versions-Asserts in `test_p132`/`test_p134` von hart `0.98.x` auf
versions-agnostischen Tupel-Vergleich (`>= (0,98,14)`) umgestellt.

**Encoder-Drift-Guard-Robustheit** (gegen stabil-negativen Wert) bleibt bewusst ein
separates TODO — die Schwung-Ursache des OMNI-Bugs ist mit dem stabilen Wert weg.

**Field-Fix (gleiche Session, Mike am Radio):** Mehrfaches Drücken des ⏱-Knopfs ließ
den Wert klettern (+0.36→+0.48→…→+1.00 Clamp), obwohl dieselben Stationen am Band
waren. Ursache: `calibrate()` leerte `_recent_samples` NICHT — nach `_correction +=
median` waren die gepufferten Slots veraltet (gegen die alte Korrektur gemessen),
ein zweiter Druck vor dem Durchspülen des 3-Slot-Fensters addierte denselben Median
nochmal (Additionskette). Fix: `_recent_samples.clear()` NUR im Erfolgsfall (nach
`_save_current()`, im Lock); fehlgeschlagene Kalibrierung behält die Samples. Nächster
Druck misst frisch gegen die neue Korrektur → stabil, kein Überkorrigieren.
Inkrementelle Grundlogik bleibt korrekt (reiner State-Management-Bug). DeepSeek R1
Diagnose+Fix bestätigt. Tests +2 → **2370**.

**Sicherheitsanker** (Rückfall): GitHub `origin/main` = `22f3d07` (v0.98.63) = letzte
Version mit dynamischer DT-Berechnung. **Mike: App neu starten** (kein Auto-Lernen
mehr — DT-Wert per ⏱-Knopf setzen). NICHT gepusht, Field-Test pending.

## 2026-06-03 v0.98.64 — FT-Modus-Wechsel bricht laufendes QSO/TX ab (gemeinsamer Abbruch-Helper)

**Mike-Field-Bug:** Auto-Hunt lief auf FT8 (rief Station LY7Z). Mike klickt direkt
auf den FT4-Button (Modus-Wechsel, KEIN HALT). Auto-Hunt stoppt korrekt (Button
aus), ABER die QSO-State-Machine sendet danach noch **3× `LY7Z DA1MHH -17`** —
jetzt auf dem neuen Modus/Band (FT4/17m), wo LY7Z uns nicht hören kann.

**Diagnose (am Code verifiziert):** Es gibt drei Umschalt-Pfade in `ui/mw_radio.py`.
`_on_band_changed` und `_on_rx_mode_changed` (Normal↔Diversity) brechen ein
laufendes QSO + TX ab (`qso_sm.cancel()` + `encoder.abort()` + `ptt_off()`).
**`_on_mode_changed` (FT8↔FT4↔FT2) tat das NICHT** — es stoppte nur Auto-Hunt +
OMNI und schaltete das Protokoll um. Klassische „mode-aware Symmetrie"-Bug-Klasse
(FEATURES §11): dieselbe Aktion in 2 von 3 Pfaden, im 3. vergessen. Der RX-Mode-
Abbruch-Block trug sogar den Kommentar „R1-V4-pro Finding 1: encoder.abort() +
ptt_off() ist nötig damit kein armed-er Slot durchrutscht" — genau dieser Fix
wurde beim FT-Modus-Wechsel übersehen.

**Fix (`ui/mw_radio.py`, gemeinsamer Helper):** Der Wort-für-Wort identische
Abbruch-Block (Band + RX-Mode) in einen Helper **`_abort_qso_and_tx()`**
extrahiert (CQ-/QSO-Stop, `encoder.abort()` + `ptt_off()`, pending-TX-Log-Discard
P131). Alle **drei** Wechsel-Pfade rufen ihn jetzt → die Bug-Klasse ist
strukturell unmöglich (ein neuer 4. Pfad kann ihn nicht mehr „vergessen"). In
`_on_mode_changed`: Helper-Aufruf **vor `set_protocol`** (DeepSeek-R1: keine Race —
der TX-Worker liest `_mode` nur vor dem Sleep, nach `abort()` nicht mehr) +
**Early-Return wenn `mode == self.settings.mode`** (Re-Klick auf den aktiven
Modus-Button bricht kein QSO mehr ab). Der RX-Mode-Pfad bekommt durch den Helper
zusätzlich den pending-TX-Log-Discard (fachlich richtig — Antennen-Wechsel macht
den Log ohnehin ungültig).

**Hardware:** Reiner Stopp-Pfad, kein neuer TX, ANT1/ANT2 unberührt. Das vorher
ungewollte Senden lief über ANT1; auf ungetuntem Band hätte der SWR-Watchdog
gegriffen — gesendet werden soll es trotzdem nicht.

DeepSeek R1 (GO + 3 Ergänzungen: pending-Discard, Early-Return, Helper — alle
eingearbeitet) + Final-R1 **PUSH FREIGEBEN** (Reihenfolge sicher, Refactoring
verhaltensgleich, Early-Return sicher, Tests legitim, kein Risiko). Tests
2349→**2358** (+9 `test_mode_change_abort.py`; angepasst: `test_bundle_i.py`
[Helper im Mock mitgebunden] + `test_p131` T1/T2/T3 [Source-Inspektion auf
Helper-Struktur]). NICHT gepusht, Field-Test pending.

## 2026-06-03 v0.98.63 — FT4-OMNI sendete 30s statt 15s (Slot-Takt vom Modus-Versatz entkoppelt)

**Mike-Field (OMNI-CQ auf FT4):** Station sendete nur alle 30s statt 15s
(Log-Zeitstempel je +30s). Auf FT8 unauffällig (dort sind 30s der normale
Paritäts-Takt). Trat NACH v0.98.62 auf — und **intermittierend**: mal 15s, mal
30s, je nachdem ob Mike vorher auf FT8 war.

**Diagnose (voller Workflow, 2× DeepSeek-bestätigt):** Regression aus v0.98.62.
Der Cycle-Timer (`core/timing.py:43`) leitet den Slot-Takt aus
`ntp_time.get_time()` ab — und `get_time()` zog seit v0.98.62 den modus-
abhängigen `_MODE_DELTA["FT4"]=−0.30` mit. Dadurch feuerte `cycle_start` auf FT4
zu spät (an der Slot-Grenze statt davor), der OMNI-CQ-TX-Trigger
(`omni_cq.on_cycle_start` → `encoder.transmit`) landete im AKTUELLEN Slot dessen
Sende-Frist (Grenze−0.8) schon 0.8s vergangen war → **Encoder-Drift-Guard**
(`encoder.py:337`) sprang +2 Slots, der eigentliche Folge-Slot fand „encoder
busy" vor → effektiv 30s. **Schwellenabhängig:** kippt sobald der gelernte FT8-
Wert `_correction < 0.30` (dann FT4-effektiv ≤ 0 → Timer feuert an/nach Grenze).
Bei `_correction > 0.30` feuert er davor → 15s. Da nur FT8 misst und der Wert um
~0.27–0.45 schwankt, flackerte FT4-OMNI je nach aktuellem FT8-Messwert.

**Fix (`core/ntp_time.py`, 1 Funktion):** `get_time()` nutzt jetzt NUR die
FT8-Basis `_correction` (OHNE `_MODE_DELTA`) — der Slot-Takt läuft wieder auf der
reinen Hardware-Zeit, immer deutlich positiv → deterministisch 15s, egal wie der
Messwert steht. `get_correction()` (mit Delta) bleibt unverändert für RX-Decode-
Shift (decoder:361) + Anzeige → FT4-Empfang/Anzeige bleiben zentriert (keine
Regression). Physikalisch korrekt: der Modus-Versatz ist ein RX-/Anzeige-
Phänomen; würde man TX um −0.3 verschieben, erschiene man bei der Gegenstation
selbst mit DT −0.3. **Kein TX-Antennen-Eingriff, ANT1/ANT2 unberührt** — TX läuft
im Encoder ohnehin gegen reine `time.time()` (absoluter Protokoll-Slot).

DeepSeek R1 (Diagnose+Fix wasserdicht, kein versteckter Pfad) + Final-R1 **PUSH
FREIGEBEN** (Schwellen-Erklärung korrekt, Umsetzung exakt, keine Nebenwirkungen,
Kaltstart-Edge-Case bestätigt). Tests 2348→**2349** (`test_dt_mode_delta.py`:
`test_get_time_uses_effective_correction` umgedreht → `test_get_time_uses_base_
not_delta`, + neuer `test_slot_takt_invariant_but_rx_diverges`). **✅ Field-Test
BESTANDEN (Mike am Radio, 03.06.2026):** FT4-Sende-Takt wieder korrekt (~8s
Slot-Intervall, durch laufendes QSO bestätigt — kein 30s mehr), FT4-Empfang/
DT-Zeiten der empfangenen Stationen sehr gut.

## 2026-06-03 v0.98.62 — DT-Korrektur modus-abhängig (FT4-Versatz) + Migrations-Bug

**Mike-Field:** Auf FT8 stand die DT der Stationen sauber um 0, auf **FT4** lagen
ALLE systematisch bei ~−0.3 (mehrere Screenshots + App-Log verifiziert).
Diagnose: Der gelernte Korrekturwert (+0.29, n=11) ist **NICHT rein die
Funkgerät-Latenz** — er ist **modus-abhängig**. FT8 braucht +0.29, FT4 effektiv
~0; der Unterschied ist ein protokoll-/fenster-abhängiger Versatz (je schneller
der Modus, desto enger die Toleranz — Mike-Einsicht). P171 wandte den FT8-Wert
unkorrigiert auf FT4 an → FT4 ~0.3 überkorrigiert (Anzeige negativ, Sende-Slot
verschoben). Der alte FT4-Eigenwert (0.045) war also teilweise REAL, nicht nur
1-Stationen-Artefakt.

**Fix (`core/ntp_time.py`):** modus-abhängige effektive Korrektur. Neuer
`_MODE_DELTA = {FT8:0.0, FT4:−0.30, FT2:0.0}` (field-kalibriert, PROVISORISCH).
`get_correction()` → `_correction + _MODE_DELTA[_mode]`; `get_time()` (TX) +
`get_status_text()` (Anzeige) nutzen die effektive Korrektur. Nur FT8 LERNT die
Basis `_correction`; FT4/FT2 erben sie + festen Delta. EINE Quelle → RX-Decode-
Shift, TX-Timing UND Anzeige werden zugleich zentriert (DeepSeek-bestätigt: kein
Teilfix/„Pfusch"). F5 verifiziert (kein Pfad liest `_correction` direkt unter
Umgehung des Delta). FT2=0.0 (Button versteckt, später kalibrieren).

**DeepSeek Final-R1 fand zusätzlich einen P171-Migrations-Bug** (NICHT FREIGEBEN
→ gefixt → freigegeben): `_load_saved()` lud bei Dateien OHNE FT8-Keys den Median
ALLER numerischen Werte (inkl. FT4_20m=0.045) als falsche ~0-Basis + setzte
`_is_initial=False` (Hardware-Default blockiert). Fix: bei fehlenden FT8-Keys
NICHT migrieren (`return`, `_is_initial=True`).

**⚠️ Feld-Test (P168-Zone):** Der FT4-RX-Decode-Shift ändert sich von +0.29s auf
~0 → FT4-Decode-Fensterlage verschiebt sich um 0.29s. DeepSeek: klein ggü.
7.5s-Slot, wahrscheinlich sicher, aber **FT4-Decode-Anzahl beobachten; bei
Einbruch `_MODE_DELTA["FT4"]` zurück auf 0.0 = sofortiger Rollback.** Kein
TX-Antennen-Eingriff, ANT1/ANT2 unberührt. Tests 2339→**2348** (+9:
`test_dt_mode_delta.py` + Migrations-Test). NICHT gepusht, Feld-Test pending.

## 2026-06-03 v0.98.61 — Audio-Mithör-Monitor (🔊-Toggle, Diagnose-Feature)

**Mike-Wunsch (Field):** unabhängig per Ohr prüfen können, ob auf der Frequenz
Betrieb ist — hörst du FT8-Gezwitscher, aber die Empfangsliste bleibt leer →
Problem liegt an der App (Decode), nicht am leeren Band. Anlass: 30m-FT4-Frage
(Band war per Live-Log verifiziert wirklich leer), Mike vermisste das
NF-Mithören vom Icom 7300.

**Neu `core/audio_monitor.py` (`AudioMonitor`):** legt das empfangene RX-Audio
(24 kHz int16 mono, dasselbe das der Decoder bekommt) optional auf den
Standard-Lautsprecher. **Decoder bleibt unangetastet** — Abzweig über einen
Wrapper `mw_radio._on_rx_audio` (Decoder ZUERST, dann Monitor). Vorallokierter
numpy-Ringpuffer (GC-frei, nicht-blockierend im VITA-49-Empfangsthread =
Decode-Timing-Thread), sounddevice-OutputStream-Callback (eigener PortAudio-
Thread). **Ausgabe fest 48 kHz** (24k ×2 sample-and-hold, kein Pitch-Shift — 24k
ist auf macOS/CoreAudio nicht überall nativ). Underrun → Stille (read-Index
bleibt, kein Versatz nach TX-Pausen). `active` = GIL-atomares bool, Lock um die
Ringpuffer-Indizes.

**UI:** 🔊-Toggle in der RX-Leiste neben „NEUE" (`rx_panel.btn_audio` →
`audio_monitor_toggled`-Signal). **Persistent** (`settings["audio_monitor"]`,
Default False) — beim Start automatisch aktiv, wenn zuletzt an (QTimer-defer).
**Start-Fehler** (kein Audiogerät) → Button springt zurück + Info-Zeile
„Audio-Mithören: kein Audiogerät verfügbar". `closeEvent` → `stop()`.

**Hardware:** reiner RX-Ausgang, **kein TX, ANT1/ANT2 unberührt.** DeepSeek R1
(2🔴 feste 48k-Ausgabe + Fehler-Rückrollung, 3🟠/🟡 vorallokierter Ringpuffer/
Underrun/Lifecycle — alle eingearbeitet) + Final-R1 **PUSH FREIGEBEN** (7
Prüfpunkte verifiziert, 0 Bugs, keine Races). Tests 2324→**2339** (+15
`test_audio_monitor.py`, ohne echtes Audiogerät via Fake-sounddevice). NICHT
gepusht.

## 2026-06-03 v0.98.60 — P171: DT-Korrektur auf EINEN globalen Wert (nur FT8 misst)

**Anlass (Mike):** Beim Ermitteln der DT-Zeit auf FT4/FT2 verschlechtern die
wenigen Stationen den Wert (DT wird mit mehr Stationen genauer). Mikes These:
die DT-Korrektur ist die Funkgerät-Latenz und damit modus- (und band-)unabhängig
→ nur FT8 (viele Stationen) sollte sie ermitteln, FT4/FT2 nur lesen; ein Wert pro
Band — und da es reine Hardware ist, reicht sogar **ein Wert für alles**.

**Verifiziert (Mike + DeepSeek einig):** physikalisch korrekt. Die gelernte
Korrektur (~0.26s) ist die konstante FlexRadio-RX-/Transport-Latenz (VITA-49) —
die modus-/slot-abhängige Fensterlage liegt SEPARAT in `decoder._DT_OFFSETS`.
**Field-Beweis** in Mikes `dt_corrections.json`: fast alle FT4/FT2-Werte matchen
FT8 — einziger Ausreißer **FT4_20m=0.0451** (statt ~0.27), ein 1-Stationen-
Artefakt (`_MIN={FT8:3,FT4:1,FT2:1}` — FT4/FT2 „maßen" ab 1 Station). Ein
Globalwert ist nicht nur KISS, sondern als gepoolte FT8-Messung auch die
genaueste Schätzung der einen Konstante. Decode-Unabhängigkeit geklärt: die
Korrektur ist KEINE Voraussetzung fürs Dekodieren (Decoder sucht Sync über
Sekunden; DT wird AUS Decodes gelernt; Kaltstart = Hardware-Default 0.26).

**Gemacht (voller Workflow, `core/ntp_time.py`):**
- EIN globaler `_correction` für alle Modi/Bänder. `set_mode`/`set_band` ändern
  ihn NICHT mehr (behalten ihn; nur Mess-Phase reset). `update_from_decoded`:
  `if _mode != "FT8": return False` — nur FT8 misst/schreibt; FT4/FT2 No-op.
  `MIN_STATIONS=3` einheitlich, Clamp `MAX_CORRECTION=1.0`. Mess-/Operate-Phasen
  + Sprung-Reset + Schnell-Konvergenz nur FT8.
- Persistenz neues Format `{"dt_correction_s": <float>}`. Migration alt→global
  (Median der FT8-Werte) in `_load_saved()` — **in-memory, kein Schreiben beim
  Import** (Datensicherheit), Datei wird bei erster FT8-Messung überführt. Der
  kaputte FT4_20m=0.045 verschwindet dabei automatisch.
- `set_hardware_default` seedet nur bei leerem Zustand. **Entfernt:** `_mode_key`,
  `_load_for_current_key` (Cross-Modus-Fallback P48-B), per-Modus `_MIN`/
  `_MAX_CORR`, `_log_load_dedup` → deutlich übersichtlicher.

**DeepSeek:** R1 (3🔴/2🟠/3🟡 — `_is_initial`-Klarheit, Anzeige-Schwelle,
Save-on-exit) → gehärtet/aufgelöst (FT4/FT2 ganz raus statt Split-Schwelle;
FT8 speichert sofort → kein Datenverlust). **Tooling:** v4-pro sprengte mit dem
langen Prompt das 16K-Output-Limit (Reasoning fraß alles → leere Antwort) →
`tools/deepseek_review.py max_tokens 16K→32K`. Final-R1 **PUSH FREIGEBEN**
(kein Datenverlust, Seed/Migration robust, keine toten Referenzen; 1🟡 Migrations-
Meldung präzisiert). Reine Timing-Logik, kein TX-Eingriff, ANT1/ANT2 unberührt.
Tests **2332→2324** (per-Modus-/Cross-Modus-/Dedup-Tests entfallen, P171-Global-
Tests dazu; netto −8 durch entfernte Sonderpfade). **⚠️ Mike: App NEU STARTEN**
(Migration baut dt_corrections.json um). NICHT gepusht.

## 2026-06-03 v0.98.59 — P170: Upload-Move mergt bei Namens-Kollision (kein Stau in neu/ mehr)

**Anlass (Mike-Field):** „jetzt habe ich 205 hochgeladen, werden die dann nicht
als fertig verschoben? sonst häufen die sich in der App-Liste." Verifiziert am
echten Datenstand: `adif/erfasst/neu/` = 205 QSOs in 12 Tagesdateien, **11 davon
mit gleichnamigem Zwilling in `hochgeladen/`** (Folge der Phase-1-Migration:
Vormittags-/Nachmittags-Sessions desselben Tages landeten in beiden Ordnern).

**Root Cause:** `_handle_qrz_file_results` verschiebt nach erfolgreichem Upload
`neu/`→`hochgeladen/`, **übersprang aber bei Namensgleichheit** (`if dest.exists():
skip`) → Datei bleibt in `neu/`, QSOs häufen sich + werden bei jedem Upload erneut
angeboten. Tritt strukturell immer wieder auf (tägliche Logdateien heißen gleich:
vormittags hochgeladen, nachmittags weitergefunkt = gleicher Dateiname).

**Fix (voller Workflow, Mike-Wahl „mergen"):** bei Kollision die Records der
`neu/`-Datei dedupliziert an die vorhandene `hochgeladen/`-Datei anhängen, dann
`neu/`-Datei löschen.
- `log/adif.py:merge_adif_files(src, dest) -> (appended, skipped)` — neue pure
  Funktion. Dedup-Key `(CALL, QSO_DATE, TIME_ON)` (identisch zu
  `export_all_records`), gegen dest UND innerhalb src. **Datensicherheit:** dest
  **byte-erhaltend** (nur Anhang, kein Reserialisieren), `open(...,
  newline="")` (keine Newline-Übersetzung, auch Windows), striktes utf-8 +
  `<EOH>`-Validierung → bei kaputter Datei ValueError. **Atomar:** Temp +
  `os.replace`. Nur Blöcke mit CALL.
- `ui/mw_qso.py:_handle_qrz_file_results`: dest-exists → `merge_adif_files` statt
  skip, `src.unlink()` erst nach Merge; bei `(OSError, ValueError,
  UnicodeDecodeError)` bleiben BEIDE Dateien (kein Datenverlust); idempotent
  (Re-Run dedupt). Eigener `merged`-Zähler.

**Aktuelle 205:** kein Skript/Hand-Anlegen — nach dem Fix + 1× QRZ-Upload gehen
sie als Dups durch (fail==0) und werden je Datei gemergt, `neu/` leert sich.

**DeepSeek:** R1 (2🔴/2🟠/3🟡 — Datensicherheit) → gehärtet. Final-R1 **NICHT
FREIGEBEN** (🔴 Newline-Übersetzung bricht Byte-Erhalt auf Windows + 🟠
Doppel-Read) → behoben (`newline=""`, dest-Keys aus dest_text) → Final-R1b
**PUSH FREIGEBEN** (beide ✅, keine neuen Datenverlust-Pfade). Reine
Dateioperation, kein TX-Eingriff, ANT1/ANT2 unberührt. Tests 2324→**2332**
(+8 `test_p170_upload_merge.py` inkl. Byte-/CRLF-Erhalt + Idempotenz; bestehender
Kollisions-Skip-Test auf Merge umgestellt). NICHT gepusht.

## 2026-06-02 v0.98.58 — P169 Phase 2: mode-genauer Worked-Filter (Call,Band,Mode) + Auto-Hunt-Transparenz

**Anlass:** Phase-1-Fundament (eine Quelle `adif/erfasst/`) steht; jetzt Mikes
Kern-Wunsch — der „schon gearbeitet"-Filter soll die Betriebsart unterscheiden.
Eine auf 20m FT8 gearbeitete Station ist auf **20m FT4** und **15m FT8** wieder
ein gültiges Ziel (FT4 ist ein eigener „Sammelraum"). Zusätzlich soll Auto-Hunt
nicht mehr stumm schweigen, wenn auf Band+Mode alle gearbeitet sind.

**Gemacht (voller Workflow, V1→V2→R1→V3→Code→Final-R1, DeepSeek-v4-pro):**
- `log/qso_log.py`: neuer Index `_worked_band_mode: set[(call,band,mode)]`,
  additiv zu `_worked`/`_worked_band` (nicht entfernt). Befüllt in `load_adif`
  (**effektiver Mode = SUBMODE wenn vorhanden, sonst MODE**, `.upper()` — unser
  FT4=MFSK+SUBMODE FT4 → „FT4", QRZ-Export MODE=FT4 → „FT4", FT8 → „FT8";
  **leerer Mode wird NIE indiziert** = Wildcard-Schutz) und in
  `add_qso(call, band, mode="")`. Neue Methode `is_worked_on_band_mode(call,
  band, mode)` (leerer/None mode-Param → False). `clear()` leert ihn mit.
- `ui/mw_qso.py:657`: Live-`add_qso` gibt `self.settings.mode` mit (dasselbe
  Token wie der ADIF-Loader normalisiert → Index konsistent).
- `ui/rx_panel.py`: NEUE-Filter band+mode-genau via neuem **Provider-Callback**
  `set_band_mode_provider(fn)` mit `fn() -> (band, mode)` (lazy aus `settings`
  gelesen → eine Quelle, keine verteilten Setter, kein Staleness — bewusst gegen
  einen kombinierten Setter entschieden, DeepSeek-R1-F1; vermeidet die
  P102/P114-Sync-Bug-Klasse). Kein Provider → call-only-Fallback (Test-Setups).
- `ui/main_window.py`: Provider verdrahtet (`lambda: (settings.band,
  settings.mode)`), `all_worked`-Signal → `_on_auto_hunt_all_worked` →
  `qso_panel.add_info("Auto-Hunt: alle N Stationen auf {Band} {Mode} schon
  gearbeitet")`.
- `core/auto_hunt.py`: Worked-Filter `is_worked_on_band` → `is_worked_on_band_mode`.
  Neues Signal `all_worked = Signal(str, str, int)`, **entprellt** über
  `_all_worked_reported` (Reset NUR in `start_auto_hunt`/`set_band`/`set_mode`,
  **NICHT** pro Pick — DeepSeek-R1-F4, entspricht Mikes Spec; sonst Meldung nach
  jedem QSO auf voll-gearbeitetem Band). Emit nur wenn vor dem Worked-Filter
  Kandidaten da waren, danach keine (leeres Band → kein Emit).
- `ui/mw_radio.py:609`: `auto_hunt.set_band(band)` jetzt **IMMER** (auch bei
  inaktivem Auto-Hunt — DeepSeek-R1-F2; sonst ist `_band` beim nächsten Start
  veraltet und der Worked-Check greift aufs falsche Band), Session-Stop
  `on_band_change()` nur wenn aktiv.

**Land-Seltenheit bleibt mode-blind** (DXCC = „habe ich dieses Land gearbeitet",
mode-unabhängig) — `_country_count`/`_country_band`/`_compute_priority`
unberührt, keine P165-Regression.

**DeepSeek:** R1 (6 Findings, alle 🟡/⚪, 0 Blocker) — F2 (set_band immer) + F4
(Debounce nur start/band/mode) angenommen (vereinfachten den Plan), F1
(Provider→Setter) + F3 (_apply_filters-Trigger) abgelehnt (Callback ist gerade
robuster; RX-Tabelle wird bei Band/Mode-Wechsel ohnehin geleert). Final-R1
**PUSH FREIGEBEN** — 0 Bugs, 0 Risiken, Token-Konsistenz + Debounce + keine
Races bestätigt.

**Hardware:** reine State-/Anzeige-Logik, kein TX-Eingriff, ANT1/ANT2 unberührt.
Tests **2312 → 2324** (+12 `test_p169_phase2.py`; 4 Test-Fakes/Mocks um
`is_worked_on_band_mode` ergänzt). NICHT gepusht, Field-Test pending.

## 2026-06-02 v0.98.57 — P169 Phase 1: adif/erfasst/ als einzige Worked-Quelle + ADIF-Import + Migration

**Ausgangslage (Mike-Field):** Auto-Hunt rief auf vollen Bändern „kein Ruf raus"
— Debug-Log zeigte `all_worked_on_band`: jede CQ-Station war schon gearbeitet
(P165-Hard-Filter). Mike-Analyse deckte tiefere Unordnung auf: der Worked-Index
las nur 3 von ~8 verstreuten adif/-Ordnern (`glob` nicht-rekursiv), frische QSOs
zählten erst nach QRZ-Upload, 95 Stationen lebten NUR in nicht-geladenen Ordnern,
ein doppelt verschachteltes `adif/adif/` (Alt-Bug aus `export_all_records(adif/)`).

**Phase 1 (Ordnung+Import, voller Workflow V1→V2→R1→V3→Code→Final-R1):** EINE
rekursiv gelesene Quelle `adif/erfasst/{neu,hochgeladen,importiert}/`.
- **Migration** (`tools/migrate_adif_erfasst.py`, copy→SHA256-verify→delete, Backup-
  ZIP, idempotent, Nicht-ADIF bleibt): 75 .adi → erfasst/ (neu 11, hochgeladen 15,
  importiert 49), byte-genau verifiziert, 9647 (Call,Band) erhalten, Altordner weg.
  Klassifikation Variante A: Historie→importiert/ (kein Re-Upload), frische
  App-QSOs→neu/, hochgeladene→hochgeladen/. DeepSeek-R1 fand 7 Lücken (Call/Band-
  Verify zu schwach, Re-Run-Dups, rmtree löscht `adif_stdout.log`) → gehärtet →
  „AUSFÜHREN FREIGEBEN".
- **Code (8 Touchpoints):** `load_directory`/`parse_all_adif_files`/
  `bulk_import_directory` mit `recursive=`; qso_log+LocatorDB+Logbuch lesen nur
  noch erfasst/ rekursiv; `AdifWriter`→`erfasst/neu/`; `export_all_records` aus
  erfasst/ (nur `SimpleFT8_LOG_*`, Fremd-Historie ausgeschlossen); QRZ-Upload-
  Kandidaten = nur `erfasst/neu/`, Move neu/→hochgeladen/; Diplome nutzen
  `_all_records` direkt (Backup-Load entfällt); neuer `QSOLog.clear()` für
  Reload-ohne-Doppelzählung.
- **Import-Button** im Logbuch: ADIF wählen → validieren (≥1 CALL) → Kopie nach
  `erfasst/importiert/` (Zeitstempel-Präfix) → Index+Anzeige+LocatorDB reload
  (`adif_imported`-Signal). Manuelles Kopieren nach erfasst/ wird beim Start
  ebenfalls erfasst.
- **Final-R1 PUSH FREIGEBEN** (Upload-Filter wasserdicht, kein Re-Upload der
  18k-Historie; 2 nicht-kritische Notizen: Reload-Race + hartes cwd, vertagt).
- Tests 2303→**2312** (+9 `test_p169_erfasst.py`: rekursiv laden, clear/reload,
  export, Import-Kern, Migrations-Integration + Idempotenz). adif/ ist gitignored
  (Daten ausserhalb Git), Backup in Appsicherungen/. **Phase 2 (mode-genauer
  NEUE-Filter + Auto-Hunt-Transparenz) offen — siehe TODO.** NICHT gepusht.

## 2026-06-02 v0.98.56 — P168: FT4 sendete mit 30s-Periode statt 15s (Decode-Pfad-Fix; 1. Versuch verworfen)

**Bug (Mike-Field, 2 QSOs, ms-Log verifiziert):** FT4-QSOs liefen doppelt so
langsam — unsere aufeinanderfolgenden Sendungen waren 30s auseinander statt 15s
(07:30:07 → :37 → 07:31:07). FT4 ist GENAU der Zeitspar-Modus — 30s vergrault
Gegenstationen. Gegenstation antwortete sauber → Problem auf unserer Seite.

**Root Cause (verifiziert):** Der Decoder weckte bei FT4 0,5s vor Slot-Ende
(absolut 14,5s); der Decode der Antwort war erst ~0,24s NACH dem Slot-Boundary
fertig — zu spät für den Audio-Start des Folge-Slots (Boundary − 0,8s wegen
FlexRadio-1,3s-TX-Buffer, `TARGET_TX_OFFSET=-0.8`). Encoder-Drift-Guard
(`encoder.py:337`) sprang `+2*_SLOT` (15s) → 30s-Periode. Decoder weckt also
**strukturell nach** der Sende-Frist; das Decode-Fenster war an die Weckzeit
geklebt (`audio_12k[-slot_samples:]`), deshalb half „früher wecken" allein nicht.

**⚠️ 1. Versuch GESCHEITERT (Field-Crash, zurückgerollt):** nur
`_WAKE_OFFSETS["FT4"]` 0,5→1,5 (+ `_DT_OFFSETS` daraus abgeleitet → 2,0). Field-
Test Mike: **0 Empfang auf 15/20/30m**, FT8 ok. Ursache: früheres Wecken
verschob das mit der Weckzeit gekoppelte Decode-Fenster → Signal aus dem
ft8_lib-FT4-Sync-Fenster (+2,24s statt +1,24s, SLIDE_OFFSETS deckt nur ±0,3s) →
0 Decodes. `dt_corrections.json FT4_20m` durch die Fehl-DT auf −0,5 vergiftet
(bereinigt). **Lehre: WAKE ist KEIN freier Knopf — Weckzeit, Fenster-Position
und DT sind getrennte Größen.**

**Fix (`core/decoder.py`, voller Workflow V1→V2→R1→V3→Code→Final-R1):** die drei
vermischten Größen ENTKOPPELT.
- `_WAKE_OFFSETS["FT4"]` = **1,5** (früh wecken → Decode rechtzeitig).
- Neuer `_WINDOW_OFFSETS = {FT8:2.5, FT4:0.5, FT2:0.3}` — Decode-Fenster
  **slot-ausgerichtet** auf [Slot−0,5; Slot+7,0] (Signal an gewohnter Position),
  UNABHÄNGIG von der Weckzeit. Neuer reiner Helper `_keep_window` behält den
  Nutzbereich (slot_samples − tail_pad) end-verankert; der Post-Signal-Rest
  (`_TAIL_PAD_SAMPLES`, FT4 = 1,0s) wird **NACH** `_preprocess_audio` mit Nullen
  gefüllt (sonst verfälschten die Nullen RMS-Norm + Whitening — DeepSeek-Finding).
- `_DT_OFFSETS` jetzt aus `_WINDOW_OFFSETS` abgeleitet (NICHT `_WAKE`) → FT4-DT
  konstant **1,0**, egal wie früh geweckt wird. FT8/FT2 **Bit-für-Bit
  unverändert** (tail_pad = WAKE−WINDOW = 0).

**DeepSeek:** Plan-R1 mit echtem Gold-Finding (Tail-Pad NACH preprocess, nicht
davor) — übernommen. Final-R1 **PUSH FREIGEBEN** 0 Blocker. **Halluzination
abgefangen:** DeepSeek behauptete einen Paritäts-Bug (`int(t/slot)%2` müsse für
FT4 /15 statt /7.5) — gegen `encoder.py:381` geprüft (nutzt ebenfalls /7.5,
FT4 alterniert auf 7,5s) und VERWORFEN; /15 hätte Decoder/Encoder desynchronisiert.
Hardware: reine Decoder-Timing-Logik, **kein TX-Eingriff, ANT1/ANT2 unberührt.**
Tests **2290→2303** (+13 `test_p168_ft4_timing.py`: Konstanten/Invarianten,
`_keep_window`, FT4-Positionierungs-Äquivalenz zum Alt-Stand, FT8/FT2-Bit-
Identität, FT8-Encode→`_process_cycle`→Decode-Rundlauf, 7,5s-Paritäts-Guard).
**Field-Test am Radio BESTANDEN (02.06. 10:25 UTC):** FT4-QSO mit SV5AZK, unsere
TX exakt im 15s-Takt (10:25:22→:37→:52→26:07→:22), Empfang voll (6 Stationen
inkl. −25 dB), DT der Stationen ≈ 0. 30s-Bug behoben.

## 2026-06-02 v0.98.55 — P167: Eingeschobenes QSO (P164) hängt nach 1 Anruf — Reentrancy-Fix

**Bug (Mike-Field, v0.98.51-Log):** Auto-Hunt jagte 9A60CBM, fremde Station
IN3BFW rief Mike dazwischen an, Mike klickte IN3BFW im QSO-Fenster (P164-Einschub
„vorgemerkt"). Nach dem 9A60CBM-Timeout wurde IN3BFW **genau EINMAL** gerufen,
dann blieb das Programm stehen: kein Retry, Auto-Hunt nahm nicht wieder auf.
Log-Beleg: `[STATE] IDLE → TX_CALL` direkt gefolgt von `[STATE] TX_CALL → IDLE`.

**Root Cause (Reentrancy, voller Workflow V1→V2→R1→V3→Code→Final-R1):** Der
Einschub-Hook `_p158_maybe_start_inserted_call` startete das neue QSO **synchron
mitten im qso_state-Abschluss-Handler**. `on_decoder_finished` (Timeout-Zweig,
Z.424-426): `_set_state(TIMEOUT)` → `qso_timeout.emit()` (DirectConnection =
synchron → Einschub → `start_qso` → State TX_CALL) → **danach**
`_resume_cq_if_needed()` → kein CQ aktiv → `_set_state(IDLE)` überschrieb den
frischen TX_CALL. QSO=IN3BFW, aber State IDLE → kein Retry; `_manual_override`
(Auto-Hunt-Pause) wurde nie zurückgenommen → Auto-Hunt-Stillstand. Erfolgs-Pfad
(`on_message_sent` TX_73_COURTESY, Z.543-545) hatte dasselbe Muster.

**Fix (Option A + HALT-Race-Schutz, DeepSeek-bestätigt):** `ui/mw_qso.py` —
`_p158_maybe_start_inserted_call` startet NICHT mehr synchron, sondern parkt den
msg in `_deferred_insert_msg` und scheduled `QTimer.singleShot(0,
_execute_deferred_insert)`. Der Einschub läuft erst im nächsten Event-Tick, wenn
der qso_state-Handler komplett durch ist (State stabil IDLE) → `start_qso` →
TX_CALL bleibt. `_on_cancel` (HALT) nullt zusätzlich `_deferred_insert_msg`
(Race-Schutz, falls HALT im Tick-Fenster). Auto-Hunt-Resume bleibt erhalten
(Einschub-QSO endet normal → `on_manual_qso_end`).

**DeepSeek:** Diagnose-R1 (Root Cause bestätigt, Option A empfohlen + HALT-Schutz)
+ Final-R1 **PUSH FREIGEBEN** 0 Blocker (1🟡 Caller-Queue-Race: harmlos, da
`start_qso` jedes laufende QSO sauber abbricht + Einschub gewollt priorisiert →
TODO-Notiz). Hardware: reine GUI-Ablauf-Steuerung, kein TX-Eingriff, ANT1/ANT2
unberührt. Tests **2286→2290** (+4 `test_p167_insert_defer.py`; 4 P158-Tests
T16/T17/T19/T26 auf Defer angepasst). FEATURES §17. **Field-Test pending, NICHT
gepusht.**

## 2026-06-02 v0.98.54 — Logbuch-Tabelle: Datums- + km-Spalte chronologisch/numerisch sortieren

**Bug (Mike-Field, Screenshot):** Klick auf den „Datum"-Spaltenkopf sortierte
alphabetisch über den Anzeige-Text „DD.MM.YY" → Tageszahl dominierte, 01.06./
02.06. standen über 12.05./13.05. (Monat ignoriert). Beim Laden war die Tabelle
korrekt (Python-Sort `_all_records`, Z.288), erst der Header-Klick übernahm Qts
String-Sortierung. km-Spalte hatte denselben Bug (String statt numerisch).

**Fix (`ui/logbook_widget.py`, voller Workflow V1→V2→R1→V3→Code→Final-R1):**
- `_SortableItem(QTableWidgetItem)` mit `__lt__`: vergleicht hinterlegten
  `_SORT_ROLE`-Schlüssel (`UserRole+1` — `UserRole` ist in Spalte 0 mit dem
  QSO-Record belegt) wenn bei beiden gesetzt, sonst direkter Text-Vergleich.
- `_date_sort_key` = `QSO_DATE + TIME_ON.ljust(6,"0")` (lexikografisch ==
  chronologisch; TIME_ON-Padding gegen 4-/6-stellig-Mix — DeepSeek-🔴).
- `_km_sort_key`: `strip().lstrip("~")`, `int(s) if s.isdigit() else -1`
  (kein `int("")`-Crash — DeepSeek-🟠). Spalte gleich mitgefixt (gleicher Bug).
- Initialsort unverändert (Python befüllt absteigend → neuestes oben).

**Claude-Catch (Test fing es):** DeepSeek-Plan sah `super().__lt__(other)` als
Fallback vor — das löst in PySide6 **RecursionError** aus (C++-Basis ruft die
Python-Override erneut auf). Hätte das Sortieren nach Call/Band/Mode/Land
zerschossen. Fix: `return self.text() < other.text()`. Final-R1 bestätigte den
Fallback als korrekt + rekursionsfrei.

**DeepSeek:** Plan-R1 (🔴 TIME_ON-Padding + 🟠 km-Crash, beide umgesetzt) +
Final-R1 **PUSH FREIGEBEN** 0 Beanstandungen. Hardware: reine UI-Sortierung,
kein TX. Tests **2278→2286** (+8, `test_logbook_sort.py` inkl. Screenshot-
Reproduktion + End-to-End QTableWidget). **Field-Test pending, NICHT gepusht.**

## 2026-06-02 v0.98.53 — Diplome-Erweiterung: WAE + WPX + DXCC-Band-Tiefe + Sichtbarkeit

**Mike-Wunsch:** DARC-Diplome (WAE, DLD) und weitere erstrebenswerte internationale
Diplome ins bestehende Diplome-Feature (bisher DXCC/WAC/WAS/WAZ) + Funktion zum
Ein-/Ausblenden einzelner Diplome. Voller Workflow (V1→V2→R1→V3→Mike-Freigabe→
Code→Final-R1) mit DeepSeek v4-pro.

**Machbarkeit zuerst verifiziert (grep über QRZ-Export):** DOK fehlt komplett →
**DLD nicht automatisierbar** (Mike akzeptiert), IOTA überall „N/A" → raus.
Machbar + erstrebenswert: **WAE** (über `CONT==EU` ableitbar) + **WPX** (Präfix
aus `CALL`) + **DXCC-Band-Tiefe** (Band-Feld vorhanden).

**Umgesetzt:**
- **WAE (Worked All Europe, DARC):** Näherung über eindeutige europäische
  DXCC-Entities (`CONT=="EU"`), Ziel 70. Tooltip ehrlich als Näherung
  gekennzeichnet (kein offizielles WAE — Sonder-Multiplier wie IT9/GM-Shetland
  nicht erfassbar). Mike-Regel „nur behaupten was verifizierbar".
- **WPX (Worked All Prefixes, CQ):** neue `wpx_prefix(call)` in `core/awards.py`,
  Ziel 300. Behandelt alle 3 Slash-Formen, gegen 25 echte Log-Calls verifiziert
  (25/25): Mobil-Suffix (`F5OYA/P→F5`), Präfix-Slash vorn (`OE/DL6CGU→OE0`,
  ohne Ziffer → „0"), Regions-Ziffer (`N1UL/3→N3`). PFX-Feld ignoriert (nur 46%
  gefüllt → immer aus CALL). **Claude-Catch:** DeepSeek-R1-Skizze `digit_parts[0]`
  war falsch (hätte `OE/DL6CGU→DL6` ergeben) → kürzerer Teil = Standort-Präfix.
- **DXCC-Band-Tiefe:** DXCC-Karte erweitert um **Challenge-Zähler** (eindeutige
  (Entity,Band)-Slots, Ziel 1000, nur HF 160-6 m — 60m/2m raus) + kompakte
  **5-Band-DXCC-Zeile** (✓ ab 100 Entities je 80/40/20/15/10 m).
- **Sichtbarkeit ein-/ausblenden:** neues Mini-Modul `core/awards_prefs.py`
  (JSON `~/.simpleft8/awards_visibility.json`), KEIN Settings-Durchreichen durch
  3 Konstruktor-Ebenen (DeepSeek-R1-🟠, entkoppelt + testbar). 👁-Button pro
  Karte, Klappbereich unten mit klickbaren „wieder einblenden"-Buttons, Karten
  via `setVisible` (kein Layout-Neubau). `AwardsDialog`-Signatur unverändert.

**Echte Logbuch-Zahlen (18329 QSOs):** DXCC 157/123, WAE 63/59, WPX 1516/1147,
WAC 6/6, WAS 49/48 (einer fehlt!), WAZ 38/33, Challenge 562, 5BD nur 15m ✓.

**DeepSeek:** Plan-R1 (1🔴 WPX-Slash + 4 Findings, alle adressiert) + Final-R1
**PUSH FREIGEBEN** (0 Blocker, 3🟡 — Leerzeichen-Härtung übernommen, defaultdict/
Balken-Deckel bewusst gelassen = KISS). Hardware: reines Logdaten-Auswerten,
**kein TX, ANT1/ANT2 unberührt.** Tests **2255→2278** (+23,
`test_awards_expansion.py`). FEATURES §19 neu. **Field-Test pending, NICHT
gepusht.**

## 2026-06-02 v0.98.52 — RX-Listen-Doppelklick = harter Auto-Hunt-Stop

**Feature (Mike-Field, voller Workflow V1→V2→R1→V3→Code→Final-R1):** Doppelklick
in der Empfangsliste ist eine BEWUSSTE Übernahme durch den Operator → ALLES
unterbrechen (laufendes CQ, laufendes QSO, aktiver Auto-Hunt) und sofort die
geklickte Station rufen, KEIN Auto-Resume. Vorher pausierte der Klick Auto-Hunt
nur (`on_manual_qso_start` → `_manual_override`), `active` blieb True, Timer lief
weiter → Mike sah Auto-Hunt weiterlaufen.

**Umsetzung (KISS):** `_on_station_clicked(self, msg, hard_stop=True)` neuer
Parameter. Stop-Block GANZ OBEN (vor allen Vorab-Returns):
`if hard_stop: stop_auto_hunt("manual_halt") + _qso_pending_insert=None +
_p158_insertable.clear()`. Deckt in EINEM Block alle Pfade ab (TX-Buffer-Resume,
SWR-Sperre, Slot-Lock, Einmessen, Normal) — eleganter als DeepSeeks Vorschlag
verteilter Stops (R1-🟡 F3+F4). Der alte Pausieren-Aufruf ist jetzt
`if not hard_stop`. **Abgrenzung:** P164-Klick im QSO-FENSTER bleibt sanft
(`hard_stop=False`, pausieren + Auto-Resume) — beide P164-Pfade (`mw_cycle.
_on_hunt_insert_clicked` IDLE-Sofort + `mw_qso._p158_maybe_start_inserted_call`
Einschub). RX-Liste = bewusste Übernahme (hart); QSO-Fenster = höflich antworten
+ weiterjagen (sanft).

**Claude-Catch gegen DeepSeek-R1 (🟠 F2):** DeepSeek empfahl explizit
`qso_sm.cancel()` vor `start_qso`. VERWORFEN nach Code-Verifikation —
`qso_state.start_qso` (Z.297-330) bricht laufendes QSO bereits sauber ab
(Pending-Reset + `_set_state(IDLE)`, P1.14 KP1). Final-R1 bestätigte die
Verwerfung als korrekt.

**DeepSeek Final-R1: PUSH FREIGEBEN**, 0 Blocker, 0 Findings. Hardware: nur
Auswahl-/Stop-Logik, TX bleibt ANT1. Tests 2245 → **2255** (+10, neu
`test_p166_rx_doubleclick_hardstop.py`; angepasst test_p158: 5 Einschub-Tests auf
`hard_stop=False`). FEATURES §17 erweitert. **Field-Test pending, lokal
committet, NICHT gepusht.**

## 2026-06-02 v0.98.51 — Auto-Hunt DX-Scoring (Seltenheit > Distanz > Signal)

**Feature (Mike-Wunsch, voller Workflow V1→V2→R1→V3→Code→Final-R1, 2 DeepSeek-
Runden + Web-Recherche):** Auto-Hunt wählte bisher rein nach Neuheit + Signal-
stärke → eine laute neue Europa-Station schlug immer das seltene, schwache DX
(Mikes Falkland −24 dB wurde nie gerufen + fiel sogar durch den alten Filter
`_MIN_SNR=-21`). Jetzt **DX-Jäger-Scoring**: persönliche Land-Seltenheit (aus
der 18k-QSO-Historie) ist Leitmaß, dann Entfernung, dann Signal nur als
Stichentscheid.

**Drei Bausteine:**
- `ui/main_window.py:_init_qso_log` lädt zusätzlich `adif/_backup_qrz_export/`
  (~18.329 QSOs DA1MHH+DO4MHH) → Auto-Hunt kennt endlich die echte Historie
  (gemessen 0,47 s Parse + Länderzählung → Eager-Load unkritisch). Außerdem
  `_auto_hunt.set_my_grid(settings.locator)`.
- `log/qso_log.py`: pro Land (`callsign_to_country`, voller Call) ein QSO-Zähler
  `_country_count` + Land-Band-Set `_country_band`; neue API `get_country_count`
  + `is_country_worked_on_band`.
- `core/auto_hunt.py`: `_score` (additive Gewichte) ersetzt durch
  `_compute_priority` = lexikografisches Tupel `(R, band_new, -dist, -snr, slot)`
  (kleiner = höher). `country_rarity_class(count)`: 0 ATNO / 1–5 / 6–20 / 21–100 /
  >100. `_MIN_SNR=-21` → `SNR_FLOOR=-26` (nur Rausch-Boden — schwaches DX ist die
  Perle, FT8 dekodiert bis ~−24 dB). Slot-Affinität vom Vorfilter zum **letzten**
  Tiebreaker (anders als DeepSeek empfahl — sicherer). Expliziter Vorfilter
  „schon gearbeitete STATION (Call+Band) skippen" (keine Dublette; andere Station
  aus seltenem Land bleibt wählbar). `_RARITY_UNKNOWN=2` für unauflösbares Land.

**Verifizierte Rangfolge (Test):** Falkland VP8(−24,13041km) > San Marino
T7(−5,939km,nah!) > Japan JA(−10,9280km,30×) > USA W(−8,7611km,200×) >
Deutschland DL(+5,216km,4000×). Nahe-aber-seltene Perle (San Marino) schlägt
weit-aber-häufig (Japan) — Seltenheit ist Leitmaß, nicht Distanz.

**Mike-Kurswechsel:** Erste DeepSeek-Runde empfahl „SNR −21 lassen, schwaches DX
nicht auto-rufen" — Mike widersprach klar („die schwache hört mich oft nicht, das
ist GERADE der Sinn"). Web-Recherche bestätigte: FT8 ist Schwachsignal-DX-Modus,
Seltenheit misst man via Clublog Most-Wanted. Claude-Catch gegen DeepSeek-Runde 1:
dessen additiver +0,7-Distanzbonus hätte NICHT gereicht (SNR-Bonus reichte bis
+3,1) → lexikografische Tupel-Ordnung gewählt.

**Bewusst weggelassen (KISS, Phase 2):** Kontinent-Stufe (Land-Seltenheit deckt
sie ab), statische Most-Wanted-Liste, FT5/Sonderpräfix-Korrektur (bekanntes
Restrisiko — Kerguelen FT5 wird als Frankreich gezählt; normale DX alle korrekt).

**DeepSeek Final-R1: PUSH FREIGEBEN**, 0 Blocker, 2 🟡 (Cooldown-Schlüssel-
Inkonsistenz = Bestandscode P61, nicht berührt; `_RARITY_UNKNOWN=2` bewusst).
Hardware: nur Auswahl-Logik, TX bleibt ANT1. Tests 2233 → **2245** grün (+12,
neu `test_p165_dx_scoring.py`; angepasst test_modules/auto_hunt_extended/p61/p139).
**Field-Test pending, lokal committet, NICHT gepusht.**

## 2026-06-01 v0.98.50 — Bug 1 QSO-Log Anchor-Bleed + Bug 3 Meldungs-Kürzung

**Bug 1 (Field, voller Workflow V1→V2→R1→V3→Code→Final-R1):** Im QSO-Verlauf
blutete das HTML-Anchor-Format der klickbaren „← Empf."-Einschub-Zeile (P164)
auf nachfolgende Zeilen — eigene „→ Gesendet"-TX-Zeilen wurden optisch
(cyan/unterstrichen) UND klickbar zu Links. Root Cause: `_append_anchor_line`
(ui/qso_panel.py) hängt `<a>`-HTML via `append()` an → danach trägt das
log_view-`currentCharFormat` underline+anchorHref+isAnchor; `_append_colored`/
`_append_two_color` setzten via `setTextColor()` nur die Farbe zurück, und
`setTextCursor(End)` lädt das Anchor-Format vom Dokument-Ende neu. **DeepSeek-R1
lag bei der Root-Cause richtig, sein Ein-Zeilen-Fix (Reset nur in
`_append_anchor_line`) reichte aber NICHT** — wegen des setTextCursor-Reloads
blieb der Bleed (Test blieb rot, kritisch geprüft). **Fix:** `_append_colored` +
`_append_two_color` setzen jetzt ein frisches `QTextCharFormat(foreground=color)`
via `setCurrentCharFormat()` statt nur `setTextColor()` → kein Erben von
underline/anchor. Final-R1: ✅ alle Pfade abgedeckt, KISS, 0 Seiteneffekte.
5 neue Tests (tests/test_bug1_anchor_bleed.py) prüfen das echte QTextCharFormat
pro Zeichen (TX/RX/Info kein isAnchor/underline/href; Anchor bleibt klickbar;
auch nach `_rerender_all`). Tests 2228→2233.

**Bug 3 (trivial):** Redundanten Fortsetzungs-Hinweis „Maus bewegen … zum
Fortsetzen" aus 3 `add_info`-Meldungen (Auto-Hunt-5-Min ×2 + CQ-Presence-
Totmann) in ui/main_window.py entfernt — der jeweils erste Satz sagt es schon
indirekt (Mike).

**Bug 2 (DeepSeek-Workflow, bewusst NICHT gefixt):** Sehr selten zwei IDENTISCHE
„← Empf."-Zeilen, gleiche Sekunde (Erst-Diagnose „RX+TX gleiche Zeit" war falsch
— Mike korrigiert: beide sind „← Empf."). DeepSeek-Diagnose: Decoder dedupliziert
intern (`seen`-Set), 1 Decode/Slot (`_decode_busy`), nur ANT1 dekodiert (ANT2 =
Diversity-Messung, nicht in `feed_audio`), 1 Signal-Verbindung → seltene Race,
statisch nicht lokalisierbar. DeepSeek-Catch (wichtig): `on_message_received`
läuft dabei theoretisch doppelt → es ist NICHT „nur Anzeige". ABER verifiziert
harmlos: P1.7-Duplikat-Filter (`mw_qso.py:601-610`, 5-Min-Fenster) schützt das
Logbuch vor Doppel-ADIF, `qso_log._worked` idempotent, keine Doppel-Sendung
(Screenshot 1× RR73 + 1× ✓). Mike-Entscheidung KISS: nicht fixen (Risiko >
Nutzen). Fallback (Dedup in `on_message_decoded`) + Diagnose-Prompt in TODO.md.

## 2026-05-31 v0.98.49 — Diplome-Feature (DXCC/WAC/WAS/WAZ)

**Neu:** Logbuch-Tab DXCC-Label → Button „Diplome". Klick öffnet read-only
Dialog mit den 4 klassischen Diplomen, je „gearbeitet" + „bestätigt (LoTW)" mit
Fortschrittsbalken. DXCC zeigt die echten ARRL-Marken (100/150/200/250/300/Honor
Roll); WAC/WAS/WAZ als Fortschritt + „🏅 erreicht"-Badge (keine erfundenen
Bronze/Silber/Gold — DeepSeek R1b Option A, Ehrlichkeit > Gamification).

**Datenquelle:** QRZ-Export `adif/_backup_qrz_export/` (18.329 QSOs DA1MHH+DO4MHH,
beide Calls = ein Pool, set-dedup) — on-demand beim Dialog-Öffnen geladen, da nur
dort die Felder DXCC/CONT/STATE/CQZ/LOTW_QSL_RCVD stecken. Frische SimpleFT8-QSOs
zählen erst nach erneutem QRZ-Export (Hinweis im Dialog).

**Code:** `core/awards.py` NEU (rein/testbar: compute_awards + dxcc_tier_status +
US_STATES/WAC_CONTINENTS/DXCC_TIERS) · `ui/awards_dialog.py` NEU · `ui/logbook_widget.py`
Edit (dxcc_label→btn_awards, _on_awards_clicked on-demand, _update_counters ohne
dxcc_label, Import AwardsDialog). Bestätigt=NUR LOTW_QSL_RCVD=Y. WAS via 50er
US_STATES-Set (AK/HI drin, nicht DXCC==291). WAC ohne AN.

**Workflow:** V1→V2→Design-R1 (GO, 6 Auflagen alle umgesetzt) + R1b (Staffelung
Option A). Final-R1 (Bestätigungs-Pass) tooling-bedingt nicht eingelesen —
Design-R1 prüfte exakte Pfade, alle Auflagen im Code verifiziert. Explizites
Final-R1 vor Push nachholen.

**Tests:** 2212 → 2228 grün (+16 test_awards). 0 Regression.

**Zurückgestellt (TODO):** „neue"-Filter + Auto-Hunt mit voller QRZ-Historie
füttern (`_backup_qrz_export` in log/qso_log.py Worked-Before-Set laden).
**Field-Test pending. Lokaler Commit + Push-Freigabe stehen aus.**

### 2026-05-31 — Nachtrag v0.98.49 (Doku + Final-R1)

- **DeepSeek Final-R1: PUSH FREIGEBEN** (alle 6 Auflagen erfüllt, keine Bugs,
  KISS) — der ursprüngliche v0.98.49-Eintrag hatte Final-R1 wegen Tooling noch
  als „offen" notiert; jetzt eingelesen + bestätigt. Einziger Nicht-Blocker:
  redundanter Fallback-Pfad in `_on_awards_clicked` (→ TODO Mini-Cleanup).
- **FEATURES.md §19 NEU** (Diplome — Mechanik, Felder, Staffelung, Datenquelle,
  Stolperfallen).
- **Commit 2cce619** (saubere Trennung, Scratch-Datei per amend entfernt).
  Memory: project_diplome_done + reference_tooling_long_session_flaky.
- **Session-Tooling-Hinweis:** Bash-stdout/Datei-Lesungen kamen zeitweise leer
  (langer Kontext + Auto-Backgrounding + Read-Dedup + Write/Read-Race im selben
  Block) — Code/Disk/RAM in Ordnung (Write/Edit + pytest persistierten). Details
  + Gegenmaßnahmen: Memory reference_tooling_long_session_flaky.
## 2026-05-30 v0.98.48 — P164 Klick auf uns-rufende Station generalisiert (P158-Nachfolger)

**P164 — eine Station die UNS ruft ist im QSO-Log IMMER klickbar** (voller
DeepSeek-Workflow V1→V2→R1→V3→Code→Final-R1, beide Runden v4-pro). Generalisierung
der alten P158-Logik.

**Mike-Spec 30.05.:** „Es ist Quatsch dass Auto-Hunt aktiv sein muss. Sie ruft
uns — das ist der Punkt, damit ist sie im QSO-Fenster sichtbar. Es muss auch kein
aktives QSO mit einer anderen Station sein." Doktrin „Höflichkeit > Stationszahl"
(Memory `feedback_hoeflichkeit_vor_stationszahl`). Auftrag: „alte Logik durch neue
ersetzen, NICHT zweiten Pfad bauen."

**Vorher (P158):** Klickbar nur wenn Auto-Hunt aktiv + nicht manual_override +
aktives QSO mit anderem Call + kein 73/rr73 — sperrte Mikes YO60GW-Fall aus
(manuelles QSO lief, fremde Station rief, war nicht klickbar).

**Jetzt (P164):** Klickbar wenn Station uns ruft + kein 73/rr73 + nicht CQ-Modus
+ NICHT der aktuelle QSO-Partner (Doppel-Ruf-Schutz, Mike-Einsicht — sonst klickt
man die Station an mit der man gerade funkt → Doppel-QSO). Klick-Wirkung
**state-abhängig**: kein aktives QSO → SOFORT rufen; aktives QSO mit A → A zu
Ende, dann B einschieben, ggf. Auto-Resume.

**Architektur:** Merker `_insert_pending_call` aus `auto_hunt` ENTFERNT, ersetzt
durch `_qso_pending_insert` in MainWindow (vom Auto-Hunt entkoppelt → funktioniert
auch ohne laufende Session). EIN Klickbar-Prädikat (`_p158_is_insertable_caller`),
EIN Merker, EIN Start-Pfad (`_on_station_clicked` — alle Safety-Guards: SWR-Sperre,
Diversity, TX-Buffer, ANT1-Verriegelung intakt). Neuer Alias `ACTIVE_QSO_STATES =
HASH_RESOLVE_STATES` in qso_state.py (semantisch vom Hash-Resolve-Zweck getrennt,
DeepSeek-R1-F4).

**DeepSeek-Findings:** Plan-R1 NO-GO→GO (F2 🔴 HALT muss `_qso_pending_insert`
nullen — eingebaut in `_on_cancel`; F4 Alias). Final-R1 NACHBESSERN→behoben:
🔴 HALT-Null (war noch offen), 🔴 IDLE-Sofort-Ruf nutzt jetzt `pop(call)` statt
`clear()` (andere uns-rufende Stationen im selben Slot bleiben klickbar).
Cleanup `_qso_pending_insert` symmetrisch: Konsum, HALT, Band-/Mode-/RX-Wechsel.

**Tests:** `test_p158_insert_pending_call.py` komplett auf P164 umgeschrieben
(34 Tests, vorher 27). Volle Suite **2212 grün** (0 Regression). FEATURES.md §17
aktualisiert. **FlexRadio Field-Test pending. Lokaler Commit, NICHT gepusht.**

## 2026-05-30 v0.98.47 — P162 zurückgenommen (war KEIN Bug)

Der in v0.98.46 als „EG5SUN-Abschluss-Bug" dokumentierte Fix war eine
Fehldiagnose und wurde entfernt. **Es gab keinen Code-Fehler — der Code war die
ganze Zeit korrekt.**

Mike-Klärung am Schirm (Screenshot 10:56–10:59): Wir riefen von Hand EG5SUN
(`→ EG5SUN DA1MHH -25`). ZEITGLEICH rief uns eine völlig andere Station blind
auf Verdacht (`← DA1MHH YO60GW R-12`). Die App reagierte korrekt NICHT auf
YO60GW (≠ QSO-Partner EG5SUN); EG5SUN selbst antwortete nie → Timeout. Alles
regelkonform. Das vermeintliche „typografische Minus U+2212" existierte nie
(kein U+2212 in irgendeinem Log; Decoder liefert reines ASCII).

Entfernt: `core/message.py:is_report` zurück auf Original,
`tests/test_p162_unicode_report.py` gelöscht. Tests 2214→2205 (Vor-P162-Stand).
`core/qso_state.py` war unberührt. Kein TODO-Eintrag (kein offener Bug).

## 2026-05-30 v0.98.46 — P162 EG5SUN-Bug GELÖST: typografisches Minus (1-Zeilen-Fix, KEIN Pfad-Umbau)

**Root Cause (voller DeepSeek-Workflow, 2 Review-Runden v4-pro):** Auto-Hunt-QSO
mit EG5SUN (schwach, −25 dB) — sie bestätigte mit R-Report, App wiederholte 5×
stur den eigenen Rapport `-25` → Timeout. Ursache war KEIN fehlender Pfad und
kein State-Designfehler, sondern ein **Parsing-Loch**: der Decode-String enthielt
ein **typografisches Minus U+2212 ('−')** statt ASCII-Bindestrich. `int("−12")`
wirft `ValueError` → `is_report` lieferte **False** → der R-Report wurde von
KEINEM State-Block in `on_message_received` verarbeitet → der Slot-Ende-Retry
wiederholte stur den eigenen Rapport. Das Unicode-Minus sieht im Fenster
IDENTISCH aus wie ein ASCII-Bindestrich → unsichtbar.

**Fix (1 Zeile, `core/message.py:is_report`):** `f3 = f3.replace("−", "-")` VOR
`int()`. No-op für ASCII (kein Risiko 95%-Fälle). Der bestehende WAIT_REPORT-
R-Report-Pfad (Z.629) erkennt den Rapport dann und sendet RR73.

**Bewusst KEIN Umbau / KEIN neuer Pfad (Mike-bestätigt):** Sobald das Parsing
stimmt, arbeiten die 6 bestehenden Abschluss-Pfade korrekt. DeepSeek riet 2× vom
Rebuild ab (Pfade kodieren echte Protokoll-Nuancen). **`core/qso_state.py` ist
UNBERÜHRT (git-diff leer)** — inkl. der Mike-wichtigen Schutzlogik: Höflichkeits-
73 nur 1× (`courtesy_73_sent`), R-Report-Wiederholung max 2× dann ignoriert
(`wait_73_retries`), 60s-Ausblenden nach QSO-Ende (P128). „QSO Ende = Ende"
bleibt wie es war. KEIN 3× 73 (Mikes „3×73"-Sorge war ein Beispiel worauf man bei
einem Rebuild hätte achten müssen — genau deshalb kein Rebuild).

**Tests:** `tests/test_p162_unicode_report.py` NEU (9): Parser (ASCII+Unicode
R-Report/Plain/Grid/RR73) + State-Machine e2e (EG5SUN Unicode-R-Report→RR73,
kein Wiederhol-Loop, ASCII-Regression, Plain-Report→TX_REPORT). Volle Suite
2205→2214, 0 Regression. Rollback-Tag `v0.98.45-pre-p162`. **Field-Test pending.**

## 2026-05-29 — Doku-Fix: Statistik-Modi-Vergleich + DX erfasst ALLE Stationen

Kein Versions-Bump (reine Doku, kein Code). Anlass: Mike-Frage „Verhältnis
Diversity vs. Normal auf 15m". Dabei aufgedeckt: `auswertung.md` §5 war FALSCH
(„Diversity_Dx zählt nur SNR<-10") — hat zu einer falschen Erst-Antwort geführt.

**Code-Wahrheit (verifiziert):** Alle 3 Modi (Normal/Standard/DX) loggen die
**Gesamtzahl** aller Stationen pro Zyklus. `accumulate_stations`
(`core/station_accumulator.py:45-60`) filtert NICHT nach SNR/scoring_mode;
`_log_stats` (`ui/mw_cycle.py:456`) schreibt `len(...)`. Das `SNR<-10`-Kriterium
(`ui/mw_cycle.py:411-415`) betrifft NUR die DX-Antennen-Verhältnis-Entscheidung,
nicht die Statistik. → Alle 3 Modi sind direkt vergleichbar, DX ist für
Diagramme nutzbar.

**Korrigiert/dokumentiert:**
- `auswertung.md` §5 umgeschrieben („KORRIGIERT" + Code-Belege).
- **FEATURES.md §18 NEU:** Statistik-Diagramm-Methodik komplett — was jeder Modus
  loggt (alle Stationen), Verzeichnis-Struktur, Pooled Mean, **fairer
  date+hour-gematchter Mehrtages-Vergleich** (Pflicht gegen Tageszeit-Bias),
  Erzeugung (generate_plots.py + banduebersicht.sh, DE+EN), Rescue-Events.
- CLAUDE.md Lookup-Tabelle: §17 + §18 ergänzt.

**Referenz-Ergebnis 15m FT8 (fair, multi-tags):** Normal 100 % · Standard +46 %
(13 Blöcke/8 Tage) · DX +24 % (8 Blöcke/5 Tage). Standard > DX > Normal.

## 2026-05-30 v0.98.45 — P161 Toggle-Sortierung im RX-Header (Wechselschalter)

**Mike-Wunsch:** Die Sortierung über die Spaltenköpfe der Empfangsliste (dB,
km, UTC, Land) ging nur in EINE Richtung. Jetzt Wechselschalter: nochmal auf
dieselbe Spalte klicken → andere Richtung. Pfeil zeigt Richtung an (↓
absteigend / ↑ aufsteigend).

**Umsetzung (voller Workflow, DeepSeek-v4-pro R1 GO + Final-R1 PUSH FREIGEBEN):**
- Neuer Instanz-State `_sort_reverse` (überlebt Cycle-Rebuilds via
  `reapply_sort`). Modul-Konstanten `_COL_TO_SORT` (war 2× lokal dupliziert,
  DeepSeek-DRY) + `_DEFAULT_REVERSE` (Erst-Klick-Richtung pro Modus = exakt das
  Verhalten vor P161 → 0 Regression).
- `_on_header_clicked`: gleiche Spalte → Richtung kippen; andere Spalte →
  Default-Richtung dieses Modus.
- `_set_sort`: snr/country/time = reine Umkehr via `reverse`. **dist** zusätzlich
  stabiler **Doppel-Sort**: zweiter Sort schiebt Stationen ohne bekannte
  Entfernung (`dist_km==0` → Anzeige „-") IMMER nach unten — sonst kleben beim
  Aufsteigend-Sortieren („nächste oben", Mikes Haupt-Use-Case) die vielen
  „-"-Einträge oben. Sentinel NUR für dist (DeepSeek-R1 🟠1: bei snr/country ist
  der Unbekannt-Fall selten → reine Umkehr, KISS).
- `_update_sort_colors`: Pfeil ↓/↑ je nach Richtung auf der aktiven Spalte.

DeepSeek: R1 GO mit 3 🟠-Empfehlungen, alle umgesetzt — 🟠2 Pfeile ▾/▴ → ↓/↑
(in Menlo breitenstabil), 🟠1 Sentinel nur für dist (snr/country reine Umkehr),
🟠3 `_sort_mode`-Self-Assign in `_set_sort` bewusst belassen (reapply_sort-
Konsistenz). F4 verifiziert: kein `_sort_mode`-Reset-Pfad → `_sort_reverse`
nirgends mit-resetten. Final-R1 PUSH FREIGEBEN 0 Blocker. Tests 2196→2205 (+9).
FEATURES §15 erweitert. **Field-Test pending.**

## 2026-05-30 — P150/P152 field-validiert (Mike, −25 dB QSO YO9HB)

**Der Beweis für den AP-Lite-Ersatz.** Mike hat ein VOLLSTÄNDIGES QSO bei
−25 dB gefunkt (YO9HB, beide Richtungen durch bis RR73, „QSO komplett"). Die
Weak-Decode-Liste belegt es schwarz auf weiß:
```
06:38:12 | -25 dB | DL2FX YO9HB -20   | 1317 Hz | 20m FT8   (YO9HB gehört)
06:40:42 | -21 dB | DA1MHH YO9HB R-23 |  700 Hz | 20m FT8   (YO9HB ruft DA1MHH)
```
dB-Verteilung 30.05. Vormittag (3238 schwache Decodes ≤ -21 dB): −26: 95,
−25: 222, −24: 408, −23: 608, −22: 844, −21: 1061. → 725 Decodes bei −24 dB
oder tiefer an einem Vormittag. Das ist der empirische Nachweis, dass die
erhöhte Decoder-Empfindlichkeit (P150 `kMin_score 10→4`) die tiefen DX-Signale
direkt hereinholt — ohne den Matched-Filter-Krückstock AP-Lite (P151 ausgebaut).
P150/P152 field-bestätigt, nicht mehr pending.

## 2026-05-30 — P119 field-validiert (Mike, Gain-Messung)

Mike hat die Gain-Messung am Radio durchgeführt: Knopf zeigt „Kontroll-TUNE",
das „Leistung wird auf 10 W eingeregelt" ist weg, restlicher Ablauf ok
(„punkte sind okay"). P119 damit field-bestätigt, nicht mehr pending.

## 2026-05-29 v0.98.44 — P158 Wartende Station ins Auto-Hunt-QSO einschieben

Voller Workflow (V1→V2→R1→V3→Code→Final-R1), DeepSeek-v4-pro Design-R1 (0
Blocker) + Final-R1 (PUSH FREIGEBEN, 0 Regression). Mike-Field-Wunsch +
Highlight-Frage von Mike beantwortet (dezent).

**Was:** Fährt Auto-Hunt ein QSO mit A und eine fremde Station B ruft Mike
dazwischen (`← Empf. DA1MHH F5MYK IN97` im QSO-Log), ist diese Zeile jetzt
**anklickbar** (heller Cyan #7FE0FF + Unterstrich, Hover-Pointer). Klick →
B wird vorgemerkt → A wird ZU ENDE gefunkt (kein Abbruch) → B wird gerufen →
Auto-Hunt läuft danach **automatisch weiter**. Mike-Philosophie: RX-Liste =
aktiv jagen, QSO-Fenster = passiv höflich antworten.

**Architektur (schlank):** Der Einschub läuft am QSO-Ende über den BESTEHENDEN
manuellen Klick-Pfad `_on_station_clicked` — dadurch sind Auto-Hunt-Pause +
„Rufe B…" + **Auto-Resume nach B** alles schon vorhandene Mechanik. Kein neuer
QSO-Start- oder Resume-Code.

**5 Bausteine:**
1. `ui/qso_panel.py`: `log_view` von `QTextEdit` → **`QTextBrowser`** (API-
   identisch, liefert Link-Klicks nativ via `anchorClicked`; `setOpenLinks(False)`).
   Neues Signal `hunt_insert_clicked(str)`, `add_rx(insert_call=…)`, Helper
   `_append_anchor_line` (HTML-Anchor `huntinsert:<call>`, HTML-escaped) +
   `_on_anchor_clicked`. Korrektur eines Konzept-Fehlers: das ursprünglich
   geplante „anchorClicked" ist ein QTextBrowser-Signal (QTextEdit hat es nicht).
2. `ui/mw_cycle.py`: `_p158_is_insertable_caller(msg)` (Auto-Hunt aktiv, nicht
   manual_override, aktives QSO mit *anderem* their_call, kein 73/rr73 — genau
   der Fall den `qso_state.py:604` ignoriert) + Hook in `on_message_decoded`
   (insert_call an add_rx + Merk-Dict `_p158_insertable`) + Klick-Handler
   `_on_hunt_insert_clicked` (Guards gegen veraltete Zeile / Klick-während-B).
3. `core/auto_hunt.py`: `_insert_pending_call` + `set_pending_insert` /
   `take_pending_insert`; in `stop_auto_hunt` geleert (Session-Ende verwirft
   Puffer).
4. `ui/mw_qso.py`: `_p158_maybe_start_inserted_call()` am Ende von
   `_on_qso_confirmed` UND `_on_qso_timeout` → bei noch aktivem Auto-Hunt
   `take_pending_insert` → `_on_station_clicked(msg)`.
5. `ui/main_window.py`: `_p158_insertable`-Dict-Init, Signal-Verdrahtung,
   Dict-Cleanup in `_on_auto_hunt_stopped` (R1-🟠1).

**DeepSeek-Findings eingebaut:** 🟠1 Dict-Cleanup bei jedem Stop, 🟠2
expliziter `their_call`-Null-Check, F1 QTextBrowser statt QTextEdit-Subklasse,
F2 Hook-Timing am QSO-Ende. **Bewusst akzeptiert:** Klick auf alte Zeile +
B-funkt-nicht-mehr → evtl. erfolgloses QSO (kein Schaden, KISS).

**Eigen-Fehler während Code (gefangen):** Edit spaltete `_p144_abort_and_skip`
(Methode hatte nach `cancel()` noch clear_current_target/⏭-Meldung/debug_log) →
sofort via test_p144 (4 rote Tests) erkannt + repariert.

**FEATURES.md §17** von „GEPLANT" auf „v0.98.44 implementiert" + Datenfluss-
Sektion. **Tests 2169 → 2196** (+27 P158: Logik via Source-Extraktion + echte
QTextBrowser-Render-Tests + Signal-Roundtrip). **FlexRadio Field-Test pending.**

## 2026-05-29 — Doku: P158 Konzept geschärft (DeepSeek-Review, kein Code)

Kein Versions-Bump (reine Konzept-/Doku-Arbeit, Umsetzung folgt nach Compact).

**P158 — Wartende Station ins Auto-Hunt-QSO einschieben.** Mike-Field-Szenario:
Auto-Hunt fährt QSO mit A, fremde Station B ruft Mike dazwischen (erscheint als
`← Empf. DA1MHH B grid` im QSO-Log). Soll nicht verloren gehen.

**Mike-Design-Philosophie (Schlüssel, neu festgehalten):** RX-Liste = AKTIV
(jagen/filtern), QSO-Fenster = PASSIV/höflich (wer mich ruft, dem antworte
ich). → Klick gehört ins QSO-Log-Fenster, nicht in die RX-Liste.

**Konzept (DeepSeek-v4-pro Review: GO/BAUEN, KISS-konform):** Die „← Empf."-
Zeile im QSO-Log wird anklickbar (nur wenn fremder Call UNS ruft + Auto-Hunt
anderes QSO fährt), via HTML-Anchor (`log_view` ist read-only QTextEdit). Klick
→ Auto-Hunt-Puffer `_insert_pending_call` → laufendes A-QSO ZU ENDE (kein
Abbruch) → Auto-Hunt pausiert → B gerufen → danach Auto-Hunt **Auto-Resume**
(Claude+DeepSeek einig: wie `on_manual_qso_end`, Klick=Präsenzbeweis, 10-Min-Cap
läuft weiter). Abgegrenzt von `_pending_station_click` (P1.24, bricht ab) +
CQ-Caller-Queue. Edge-Cases über P122-Defer-Mechanik. Spec: TODO.md P158,
FEATURES.md §17 NEU, Memory `project_p158_concept`. **Umsetzung: nächster Punkt,
voller Workflow.**

## 2026-05-29 v0.98.43 — P119 Phase B (10W-Einpendeln) + Krücke entfernt

**Mike-Wunsch (am Radio, Gain-Messung-Screenshots):** Das „Leistung wird auf
10 W eingeregelt" nach dem TUNE in der Gain-Messung + die 10W→Ziel-Watt-
Hochrechnung sind überflüssig. Begründung (im Code verifiziert): Der normale
Betrieb (`_auto_adjust_tx_level`) speichert beim Einpendeln auf die echte
Ziel-Wattzahl bereits `{band}_{watts}` direkt im RF-Preset-Store. Die
10W-Krücke war nur ein grober Startwert-Schätzer für den allerersten
Bandbesuch — und traf die 10 W eh oft nicht sauber („bleibt bei 11 W").

**Vorausgegangen (gleiche Session): Umbenennung** „Auto-TUNE" → „Kontroll-TUNE"
im Kalibrier-Dialog (dx_tune_dialog.py), um Verwechslung mit dem separaten
„Auto-TUNE bei Bandwechsel" (Setting) zu vermeiden (Trivial, eigener Commit).

**Entfernt** (`mw_tx.py`): `_tune_converge_to_target` (Phase B),
`_wait_with_event_loop` (Phase-B-Helper), `_kruecken_skalierung`
(10W-Anker-Hochrechnung), 10W-Stützpunkt-Save + `_tune_converged_rf` in
`_tune_post_swr_check`. Anzeige „auf 10 W eingeregelt" → „prüfe SWR" in
beiden TUNE-Dialogen.

**Bleibt (Hardware-Sicherheit unberührt):** SWR-Freeze
(`_tune_last_valid_swr = _compute_match_swr()`, P142/P153/P159), Band-Sperre,
Post-Check, Diversity-Resume. DeepSeek-v4-pro hat bestätigt, dass der Freeze
VOR der entfernten Phase B läuft — die Band-Sperren-Bewertung ist isoliert.

**Begleitfix (DeepSeek-v4-pro 🔴 Blocker):** Auto-TUNE-Skip bei Bandwechsel
nutzt jetzt `rf_preset_store.has_any_preset(radio, band)` statt
`has_anchor(watt=10)` — sonst liefe Auto-TUNE bei jedem Bandwechsel, weil der
10W-Anker entfällt. Skippt nun auf jedem schon einmal gefunkten Band (besser).

**Workflow:** voll — V1→V2→R1(GO)→V3→Code→Final-R1 (PUSH FREIGEBEN, 🟡
`_fwdpwr_samples.clear()` verifiziert erhalten). `_tune_convergence_cancelled`
bleibt als harmloses No-op-Flag (Dialog-Cancel-Handler setzen es noch).
Tests 2188→2169 (−20 test_p54_fix obsolet, +10 test_p119, −9 Save-Tests).
**FlexRadio-spezifisch — Field-Test am Radio pending.**

## 2026-05-29 — ft8_lib gesichert: Submodul-Verweis aufgelöst (Vendoring)

**Kein App-Code, kein Versions-Bump** (Verhalten unverändert). Repo-Wartung.

**Problem (Versehen):** `ft8_lib/` war ein eingebettetes Repo (Gitlink im Index,
Modus 160000, KEIN `.gitmodules`) und zeigte auf das fremde Original
`github.com/kgoba/ft8_lib`. Dadurch waren unsere lokalen Patches NIE in
SimpleFT8/GitHub gesichert — sie existierten nur im Working-Tree auf Mike's Mac:
- **P150** (`libft8simple.c`): `kMin_score 10→4` im FT8-Pfad — war **untracked**.
- **FT2-Protokoll-Support** (`ft8/constants.h`, `common/monitor.c`, `ft8/decode.c`)
  — im Submodul-Working-Tree modifiziert, nie committed.

**Lösung (Vendoring):** `git rm --cached ft8_lib` (Gitlink raus) + `rm -rf
ft8_lib/.git` (eingebettetes Repo entfernt) + `git add ft8_lib` → 181 Dateien
jetzt normale Projektdateien im SimpleFT8-Repo. Frischer Clone enthält P150+FT2.
Build-Artefakte (`gen_ft8`, `libft8.a`, `decode_ft8`) bleiben via
`ft8_lib/.gitignore` ausgeschlossen. Inhalt verifiziert (kMin_score=4 FT8 / 10
FT4+FT2, `FTX_PROTOCOL_FT2` vorhanden).

**Backup vor Umstellung:** `Appsicherungen/2026-05-29_vor_ft8lib_vendoring/
ft8_lib_komplett.tar.gz` (43 MB, inkl. alter Git-Historie der lib).

**Commit:** `f3887a5`, gepusht auf `origin/main` (Mike-Freigabe „alles pushen").
Zuvor: 11 Python/Doku-Commits (P64/P156/P157/P159/P160 + Stats) gepusht.

**Konsequenz für künftige Sessions:** ft8_lib ist KEIN Submodul mehr.
NICHT `git submodule update` o.ä. ausführen — es sind normale Dateien.

## 2026-05-28 v0.98.42 — P160 5s zur Rechtsklick-TUNE-Override-Auswahl ergänzen

**Mike-Wunsch:** Schnell-TUNE für empfindliche Lasten (20-W-Dummyload schnell
zerschossen) — kurz Träger raus um zu sehen wie sich der SWR gerade verhält,
ohne neu einzumessen und ohne ins Settings-Menü zu gehen. Der Rechtsklick-
Override bot bisher nur 10/15/20s.

**Änderung (3 Zeilen):** `control_panel.py` Menü-Schleife `(10,15,20)` →
`(5,10,15,20)` + Docstrings; `mw_tx.py:_on_tune_override` Whitelist `(10,15,20)`
→ `(5,10,15,20)`.

**Sicherheit:** 5s ist kürzer als bestehende Werte (weniger TX-Zeit), 5W/ANT1
wie alle TUNE, und im Linksklick-Pfad (`_on_tune_clicked`, Whitelist 5/10/15)
bereits erlaubt. DeepSeek-R1 GO (Option a): kein neues Risiko, keine
Sonderbehandlung — der 5s-Override durchläuft denselben Post-Check wie der
bestehende Linksklick-5s (Median-Fenster [2s,4s]; falls Tuner in 5s nicht
eingeregelt → Band gesperrt, identisch zum vorhandenen Verhalten).

**Abgrenzung:** NUR der Override-Pfad geändert; der Setting-basierte Linksklick-
Pfad (5/10/15) bleibt unberührt. FEATURES.md §16 (TUNE-Pfade) aktualisiert.
Tests `tests/test_p160_tune_override_5s.py` (5). Tests 2183→2188 (+5).

## 2026-05-28 v0.98.41 — P159 SWR-Clamp-1.0-Werte aus Median filtern (Hardware-Sicherheit, 6. Iteration)

**Mike-Field-Bug:** Band 15M mal mit „SWR 1.0" freigegeben, mal mit „SWR 28.5"
gesperrt — echter Match war 2.4. Mike-Diagnose aus Funker-Praxis: ein SWR von
exakt 1.0 ist auf einer echten KW-Antenne praktisch unmöglich (nur Dummy-Load
gibt 1.0; resonanter Dipol ist ~73 Ω → ~1.5:1), sein bester realer Wert je: 1.2.

**Root Cause (field-belegt via Debug-Log):** Der FlexRadio-SWR-Sensor clampt bei
fehlender Vorwärtsleistung (FWDPWR≈0, kein Träger) HART auf exakt 1.0
(`radio/flexradio.py`: `if swr < 1.0: swr = 1.0`). Diese künstlichen 1.0-Werte
landeten in `_tune_swr_samples` und verfälschten den Median in
`_compute_match_swr`. Debug-Log 14:52:29, Fenster [7-9s], n=33:
```
samples = 14× [2.5-2.6 ECHT] + 19× [1.0 CLAMP]  → median=1.00
→ Band fälschlich freigegeben (echter Match 2.5-2.6)
```
Echte SWR-Werte streuen (2.5/2.6); der Clamp ist immer EXAKT 1.0 — das ist das
eindeutige Erkennungsmerkmal (Mike's Beobachtung: „echte Werte sind nie genau 1").

**Fix (KISS):** `_compute_match_swr` filtert `swr > 1.0` aus dem Median-Fenster.
Verschiebt den Median nach OBEN = immer in die SICHERE Richtung (nie fälschlich
freigeben). Bleiben < 3 echte Werte (nur Clamps = kein echter Träger) → None →
Band bleibt gesperrt. Diagnose-Log um `clamps_gefiltert`-Zähler erweitert
(Rohdaten bleiben vollständig im Log — Filter nur bei der Median-Berechnung).

**Verifikation:** Mike-Theorie per Web bestätigt (echte KW-Antenne erreicht
praktisch nie 1.0; nur Dummy-Load/verlustbehaftete Leitung täuscht 1.0 vor).
DeepSeek-R1 GO 0 Blocker: Filter hardware-sicher, Edge-Cases (alle-Clamp → None
→ gesperrt) korrekt, Schwelle `> 1.0` (nicht `>= 1.1`, sonst fielen echte gute
Matches wie 1.2 weg), keine Nebenwirkungen (P53 liest `radio._last_swr` direkt;
P142/P76-A Freeze; P148 GUI alle unberührt).

**Pattern-Klasse Hardware-Sicherheit 6. Iteration** (P53/P76-A/P142/P153/P154/P159).
Tests `tests/test_p159_swr_clamp_filter.py` (9). Tests 2174→2183 (+9).
FEATURES.md §12 als 6. Iteration ergänzt.

## 2026-05-28 v0.98.40 — P157 RX-Liste Aging-Bug (drei Ursachen, voller Workflow)

**Mike-Field-Bug:** In der Empfangsliste stehen „uralte" Stationen (bis ~17 Min),
man ruft eine an, die nicht mehr aktiv ist. Mike-Hypothese: „vielleicht senden
die noch CQ und wir aktualisieren nur die Uhrzeit nicht."

**Diagnose (V1) — drei unabhängige Ursachen, DeepSeek-R1 bestätigt + Bug 3 mitgefunden:**
- **Bug 1 (Hauptursache):** `remove_stale()` hat genau EINEN Aufrufer
  (`accumulate_stations`), der nur bei vorhandenen Decodes läuft. Wird das Band
  still (leere Slots), wird NIE gealtert → tote Stationen kleben unbegrenzt fest,
  bis der nächste Decode kommt. `_on_cycle_start` (Slot-Start) altert auch nicht.
- **Bug 2 (Mike-Hypothese bestätigt):** `_slot_start_ts` (Quelle der UTC-Spalte
  in `_populate_row` + Zeit-Sortierung `_time_key`) wurde beim Wiederhören einer
  bekannten Station NICHT aktualisiert (`accumulate_stations` setzte nur
  snr/raw/field*/_last_heard/_utc_display). → Anzeige zeigte Erst-Sichtung.
- **Bug 3 (DeepSeek):** `_last_heard` (Aging-relevant) wurde nur bei
  Inhalts-Änderung gesetzt → eine aktiv sendende Station mit stabilem SNR +
  identischem Text altert raus, obwohl sie aktiv ist.

**Fix (KISS, Variante b — bewusste Abweichung von DeepSeeks Variante c):**
1. `core/station_accumulator.py`: im „Station bekannt"-Zweig `_last_heard`,
   `_utc_display` und (defensiv) `_slot_start_ts` IMMER setzen — VOR der
   change-Prüfung (fixt Bug 2 + Bug 3). Redundante Altzeilen entfernt.
2. `ui/mw_cycle.py`: (a) `remove_stale` zum Import ergänzt; (b) neuer Helper
   `_rebuild_rx_table(stations)` zentralisiert den Tabellen-Neuaufbau (vorher in
   beiden Handlern dupliziert); (c) neuer Aging-Block in `_on_cycle_decoded` NACH
   der Modus-Verzweigung, der bei `not messages` (leerer Slot) das aktive Dict
   altert + bei Entfernung Tabelle/Decode-Count aktualisiert (fixt Bug 1).
3. `ui/rx_panel.py`: veralteten Kommentar an neues Verhalten angepasst (Doku).

**Warum Variante b statt c:** DeepSeek wollte `remove_stale` ganz aus
`accumulate_stations` rausziehen + ein `_rx_table_dirty`-Flag. Verworfen: mehr
Umbau + neuer Zustand für ein Doppel-Render-Problem, das real unsichtbar ist.
Variante b ist minimal-invasiv, kein API-Bruch (alle Aging-Tests rufen
`remove_stale` eh direkt auf), kein Doppel-Render (neuer Block greift NUR bei
leeren Slots; messages-Slots altern via `accumulate_stations` wie bisher).
DeepSeek Design-R1 + Final-R1 beide PUSH FREIGEBEN, 0 Blocker.

**Tests:** `tests/test_p157_rx_aging.py` (12 — Bug 2/3 funktional, None-Defensive,
Regression messages-Slot altert weiter, Bug 1 Source-Inspektion, DRY-Helper).
Tests 2162 → 2174 (+12). FEATURES.md §15 NEU.

## 2026-05-28 v0.98.39 — P156 Netto-Leistung dezent anzeigen (FWD minus Reflexion)

**Mike-Wunsch (erfahrener Funker):** Die angezeigten Watt sind FWDPWR
(vorlaufende Leistung Richtung Antenne), nicht was bei schlechtem SWR
effektiv durchgeht. Zusätzlich als Info eine kleine Netto-Zahl.

**Mike-Spec (nach Diskussion mit Claude + DeepSeek):** kleine, **dunkelgraue,
statische** Zahl in Klammern ZWISCHEN W und SWR (`70 W (56)  SWR 2.6`).
Kein Farbwechsel (sonst 3 farbwechselnde Werte = zu unruhig). **Nur sichtbar
wenn Leistung anliegt (W > 0).** Tooltip erklärt ehrlich.

**Physik (DeepSeek-validiert):** Γ=(SWR−1)/(SWR+1), netto = FWD·(1−Γ²).
SWR 2.6 → ~80% durch → 70 W → ~56 W. **Ehrliches Label „netto in die
Leitung", NICHT „abgestrahlt"** — der Tuner re-reflektiert das meiste und
strahlt es doch ab; Leitungs-/Antennen-Verluste sind nicht messbar
(steht im Tooltip).

**Umsetzung:** pure Funktion `compute_net_power(fwd, swr)` (modul-level
`ui/control_panel.py`), graues Sub-Label `netto_label` (#666, 10px,
statisch) zwischen watt_label/swr_label, `_refresh_netto()` auf
update_watt/update_swr (nur W>0), reset bei Bandwechsel.

**DeepSeek:** Konzept-R1 + Implementierungs-R1 beide FREIGEGEBEN (Physik
korrekt; Farbe #666 + reset-State R1-Hinweise eingebaut). Logik getestet
(8 Tests); optische Darstellung am Radio zu prüfen.

Tests 2154 → **2162 grün** (+8 P156, 1 P148-T9b präzisiert).

## 2026-05-28 v0.98.38 — P64 FakeRadio + SimInjector (Sim-Modus ohne Hardware)

**Mike-Wunsch:** SimpleFT8 ohne echtes FlexRadio starten + Fake-Decodes/SWR
einspeisen → UI/QSO-Flow/Auto-Hunt remote testen. Variante B (von 3, via
AskUserQuestion): „Scripted + Fake-Werte". Strategischer Nebennutzen:
validiert die RadioInterface-Abstraktion vor dem Icom-Fork.

**Aktivierung:** Env-Var `SIMPLEFT8_FAKE_RADIO=1` (kein UI, kein Setting):
```
SIMPLEFT8_FAKE_RADIO=1 ./venv/bin/python3 main.py
```

**Neu:**
- `radio/fake_radio.py` — `FakeRadio(QObject)`, duck-typing-kompatibel zur
  FlexRadio-Oberfläche (8 Signals + ~34 genutzte Member). `ip="SIM"` →
  App-Gates `if self.radio.ip:` = connected. Liefert KEIN Audio.
  `set_frequency` normalisiert MHz→Hz (Final-R1).
- `core/sim_injector.py` — `SimInjector` feuert pro Slot Fake-FT8Messages
  (CQ + Fremd-Wechsel, SNR variiert inkl. ≤ -24 dB) über die DECODER-Signals
  in exakter Reihenfolge `cycle_decoded → message_decoded → cycle_finished`.
- `core/sim_mode.py` — `is_sim_mode()`.
- `radio_factory`: Env-Var-Override → FakeRadio.
- `main_window._init_sim()`: SimInjector an `radio.connected` koppeln.
- `mw_radio`: `decoder.start()` im Sim gegated (kein Audio → kein Thread).

**Safety-Guards** (Sim-Daten dürfen echte Daten/Netze NICHT kontaminieren):
`weak_decode_log` (Mikes P150-Evidenz) + `station_stats` (Diagramme)
schreiben im Sim NICHT. PSK-Reporter ist read-only (fetch) → kein Guard.
Kein allgemeines Decode-Log (ALL.txt) vorhanden (verifiziert).

**DeepSeek-V4-pro:** Design-R1 GO; Final-R1 NACHBESSERN → 2 Findings behoben
(Freq-Normalisierung; ALL.txt verifiziert nicht-existent) → PUSH FREIGEBEN.
Konformität + Smoke verifiziert (MainWindow konstruiert im Sim 0.4s; 8
Fake-Decodes → 8 RX-Zeilen via echtem `_on_cycle_decoded`, Normal-Modus).

**GRENZEN V1 (→ TODO P64-B):** kein interaktiver QSO-Responder (angerufene
Station antwortet nicht); Diversity-MESSUNG nicht simuliert (braucht dual-
stream = Variante C); Slot-Intervall bei start() fixiert.

Tests 2145 → **2154 grün** (+9 P64).

## 2026-05-28 v0.98.37 — P123 Pre-TX-Anzeige beim QSO-Start (Auto-Hunt-Marker)

**Mike-Wunsch (UX):** Beim QSO-Start kurz signalisieren dass ein QSO
anfängt. Befund: Von den QSO-Start-Pfaden zeigte nur der **Auto-Hunt-Pfad
NICHTS** im QSO-Log (nur debug_log) — manueller Klick (`mw_qso.py:266`) und
CQ-Antwort zeigen schon „Rufe/Antworte X".

**Mike-Wahl (Variante A von 3 vorgelegten, via AskUserQuestion):** kurzer
Start-Marker, kein neues Format, keine persistente Anzeige (Mike mag keine
persistenten Header — P1.15).

**Fix:** `_run_auto_hunt` (mw_cycle.py) fügt VOR `start_qso` einen
`qso_panel.add_info(f"Rufe {call}...{antenna_label}")`-Eintrag ein — 1:1 wie
der manuelle Klick-Pfad. Feuert genau 1× pro QSO (nach start_qso ist state
nicht mehr idle → kein Re-Pick).

**DeepSeek-R1 (V4-pro):** PUSH FREIGEBEN, 0 Blocker. Scope bestätigt: nur
Auto-Hunt — OMNI-Listener (deaktiviertes Privat-Feature) + CQ-Edge-Fall
(Diversity-ohne-Pref) NICHT anfassen (KISS, kein Umbau bestehender Pfade).

Tests 2142 → **2145 grün** (+3 P123).

## 2026-05-28 v0.98.36 — P154 Auto-TUNE SWR-Median-Fix (Zwilling zu P153)

**Mike-Field-Bug 28.05.:** Screenshot „⚠ Band 20M gesperrt — SWR 8.7" obwohl
Radio-Widget live SWR 1.4 zeigt. Mike: „autohunt tune bekommt auch nicht den
richtigen wert. nur manuell tune das rafft er."

**Root Cause:** P153 (heute früher) baute die SWR-Sample-Sammlung für das
Median-Fenster (`_compute_match_swr`) NUR in `_tune_start` ein (manueller
TUNE-Knopf). Die beiden AUTO-TUNE-Pfade haben eigenes Setup und rufen
`_tune_start` NICHT auf:
- `_start_auto_tune_for_band_change` (mw_tx.py) — Bandwechsel-Auto-TUNE
- `_start_dialog_tune_sequence` (mw_radio.py) — DXTuneDialog-TUNE

→ `_tune_start_time` blieb STALE (vom letzten manuellen TUNE, evtl. anderes
Band) → `_on_meter_update` sammelte mit riesigem `_elapsed` → die neuen
Samples fielen aus dem Median-Fenster [Dauer-3s, Dauer-1s] → `_compute_match_swr`
lieferte None oder den Median ALTER Samples → falsche Band-Bewertung.
Pattern-Klasse wie P133/P134 (ein Pfad gefixt, dupliziertes Setup im
Zwilling übersehen).

**Fix:**
- Zentraler Helper `_init_tune_swr_sampling(duration_s)` (mw_tx.py) hält die
  3 Init-Zeilen — KISS gegen erneute Drift.
- `_tune_start` + beide Auto-TUNE-Pfade rufen ihn, jeweils VOR `_tune_active=True`
  (sonst Mini-Race im `_on_meter_update`-Guard).
- **R1-F1:** beide Auto-Pfade resetten zusätzlich `_tune_post_check_token = None`
  (P101-Symmetrie — ein latenter Post-Check vom letzten manuellen TUNE dürfte
  sonst mitten im Auto-TUNE feuern → Watchdog vorzeitig scharf + stale Eval).

**Abgegrenzt (R1-F2, separates Ticket):** Gain-Mess-TUNE
(`_start_dx_tuning._after_tune`, mw_radio.py) nutzt weiter `radio.last_swr`-
Snapshot (eigene 3s-Struktur, kein `_tune_stop`) — gleiche Bug-Klasse, aber
Scope-Creep vermieden.

**DeepSeek-V4-pro:** Design-R1 + Final-R1 beide PUSH FREIGEBEN, 0 Blocker.
**Pattern-Klasse Hardware-Sicherheit 5. Iteration** (P53/P76-A/P142/P153/P154).
Tests 2132 → **2142 grün** (+10 P154, 1 P153-T11 angepasst auf Helper).

Außerdem (Trivial, gleiche Session): **P144-Meldung gekürzt** — „⏭ X belegt
(sendet an Y) — überspringe ohne Sperre" → „⏭ X ist im QSO" (Mike-Wunsch
„kurze nachricht reicht", busy_with nur noch im Debug-Log).

## 2026-05-28 v0.98.35 — P152 Weak-Decode-Log (schwache Decodes ≤ -21 dB sammeln)

**Mike-Wunsch 28.05.:** Nach P150 (kMin_score 10→4) sieht Mike live mehr
tiefe Decodes („gerade eine -25 dB Antenne-2-Station in der Liste"). Es
gibt KEINE Vorher-Werte zum Vergleich. Mike-Idee: ab jetzt jeden schwachen
Decode in eine eigene Liste schreiben → empirischer Beweis ob der
Decoder-Fix tiefe Stationen bringt (Falkland-Klasse, DXpeditionen).

**Mike-Wahl (AskUserQuestion):** eigene Datei, IMMER an (kein Setting),
Schwelle SNR ≤ -21 dB (= alte Decoder-Grenze, alles darunter ist die
„neue" Zone die kMin_score=4 erschließt).

**Neues Modul `core/weak_decode_log.py`** (always-on, analog debug_log
aber ohne Toggle):
- `WEAK_SNR_THRESHOLD = -21` (Modul-Konstante, kein Setting)
- `log_weak_decodes(entries, band, mode)` — **batched** (1 File-Append pro
  Slot, R1-Empfehlung) statt pro-Decode
- `cleanup_old_files(keep_days=7)` — Trend über mehrere Tage
- Eigene Tagesdatei `~/.simpleft8/weak_decodes_YYYY-MM-DD.log` (UTC)
- silent-fail, thread-safe (Lock)

**Format:** `HH:MM:SS | +/-NN dB | <raw> | NNNN Hz | band mode`
Beispiel: `04:35:02 | -25 dB | CO8LY DA1MHH -18 | 1293 Hz | 15m FT8`

**Hook** in `ui/mw_cycle.py:_on_cycle_decoded` (nach `_assign_slot_parity`,
vor mode-Branches → deckt alle RX-Modi ab). Filtert `snr ≤ -21` mit
snr-None-Defensive (R1). Cleanup in `main.py` neben debug_log.

**R1-V4-pro Findings eingebaut (V1+R1 27.05. durch):**
- Batching (1 open/Slot statt pro-Decode) — konstante I/O auch bei Pile-up
- snr-None-Check (`getattr(_m, 'snr', None) is not None`) — Parser-Fail-Schutz
- UTC (FT8-Konsistenz mit debug_log), keep_days=7, Modul-Konstante kein Setting

Tests 2123→2132 (+9 P152). Live-Smoke: Format exakt wie Mike-Preview.
**Mike-Field:** Liste füllt sich automatisch → nach 1-2 Sessions schauen
ob -22/-24/-25/-26 dB Einträge auftauchen = P150 wirkt.

---

## 2026-05-28 v0.98.34 — P153 SWR-Freeze: Median über stabiles Fenster statt Snapshot

**Mike-Field-Bug 28.05.2026:** Bandwechsel 15m → gesperrt. Manueller TUNE:
Tuner matchte sichtbar auf SWR 2,5 (Anzeige zeigte es), ABER System fror
>4,0 ein → Band blieb gesperrt („SWR 4.0 > Limit 3.0"). 2. TUNE: zufällig
2,3 → frei.

**Mike-Diagnose (bestätigt durch Code):** Der Freeze nahm einen EINZIGEN
Momentan-Snapshot (`radio.last_swr`, `mw_tx.py:268`). Wenn der genau einen
Mess-/Regel-Ausreißer (4,0) erwischt obwohl der Tuner stabil bei 2,5 ist →
falscher Wert eingefroren. Mike-Worte: „er hat 2,5 gefunden aber über 4
abgespeichert, als wenn er zu früh abgespeichert oder nicht den niedrigsten
gefundenen wert".

**Auslöser-Verkettung (Mike's scharfe Beobachtung „seit P148?"):**
- Eigentlich **P142** (27.05.): zog den Freeze von „nach Phase B" (5s
  Stabilisierung) auf „nach Phase A" (direkt nach Match) → SWR-Stream
  noch am Schwanken → Snapshot fragiler.
- **P148** (27.05.) machte es nur SICHTBAR (Anzeige hält letzten echten
  Wert statt auf 1,0 zu springen — vorher sah Mike nie dass 2,5 erreicht
  wurde). Derselbe Snapshot-Mechanismus erklärt auch frühere false-1,0.

**Fix (Mike-Spec):** Statt EINEN Snapshot → **Median über Fenster
[Dauer-3s, Dauer-1s]** (= Sek. 7-9 bei 10s Tune). Fenster schließt die
Match-Suchphase (SWR fällt von hoch) UND die Übergangs-Sekunde vor
tune_off aus. Median (Mike-Entscheidung nach Min/Median-Abwägung): ein
einzelner Ausreißer kippt ihn nicht, bei echter Oszillation bleibt er
ehrlich.

**5 Code-Änderungen (alle `ui/mw_tx.py`):**
1. `import statistics`
2. `_tune_start`: `_tune_swr_samples` + `_tune_duration_s` + `_tune_start_time`
3. `_on_meter_update` SWR-Branch: `(elapsed, swr)` während `_tune_active` sammeln
4. neuer Helper `_compute_match_swr()`: Median über Fenster
5. `_tune_stop`: Helper statt Snapshot + expliziter `is None`-Check + Diagnose-Log

**R1-V4-pro 2 Hardware-Sicherheits-Nachschärfungen (zwingend):**
- **F3:** < 3 Samples im Fenster → Median nicht aussagekräftig → `None`
- **F6:** KEIN Fallback auf `radio.last_swr` (= Snapshot-Bug zurück) → `None`
  → Post-Check (`mw_tx.py:372`) behandelt None als FAIL → **Band bleibt
  gesperrt**. „Lieber nochmal TUNEN als ein falsch freigegebenes Band."

**DeepSeek-Detail-Fehler abgefangen:** R1 behauptete `None <= 3.0 == False`
— ist aber Python-`TypeError` (Absturz). Code nutzt expliziten
`swr_after_match is not None and swr_after_match <= swr_limit`. (CLAUDE.md-
Regel „DeepSeek immer kritisch prüfen" bestätigt — V4-pro halluziniert
gelegentlich Detail-Fakten.)

**Verhalten (Smoke-Test + 13 Tests verifiziert):**
- Tuner stabil 2,5 + ein 4,0-Spike → Median 2,5 → **Band frei** (Mike-Bug behoben)
- Echt schlecht 4,x durchweg → Median 4,1 → gesperrt
- Fenster < 3 Samples → None → gesperrt
- 15s Tune → Fenster 12-14; kurze 3s Tune → Fenster [0,2]

**Diagnose-Log:** `debug_log("TUNE", "SWR-Fenster [7-9s] n=5 median=2.50
snapshot=4.00 samples=[...]")` — bei aktivem Debug-Log sieht Mike Fenster-
Inhalt, gewählten Median UND was der alte Snapshot genommen hätte.

**Pattern-Klasse Hardware-Sicherheit 4. Iteration** (P53/P76-A/P142/P153).

**Cancel-Fall (Mike-Bonus-Beobachtung „stabile 2,3 + abbrechen → nimmt sie
nicht"):** by-design — Cancel während Phase B setzt `_tune_last_valid_swr =
None` (P142-Schutz). Im Scope dokumentiert, nicht geändert.

Final-R1 V4-pro PUSH FREIGEBEN ✓ 0 Mängel. 3 P142-Tests angepasst
(Quelle radio.last_swr → _compute_match_swr). Tests 2110 → 2123 (+13 P153).

---

## 2026-05-27 v0.98.33 — P151 AP-Lite vollständig ausgebaut

**Trigger:** P150 hat den richtigen Pfad gewählt (`kMin_score=4`).
DeepSeek-V4-pro-Konsens 27.05.: AP-Lite-Konzept trägt nicht — Matched
Filter über LDPC-Decoder hat keine mathematische Nische. Mike's Feld-Daten
0/16 MATCH bestätigte das. Jetzt sauber ausbauen.

**Entfernt (6 Files):**
- `core/ap_lite.py` (407 LOC Hauptmodul)
- `tests/test_ap_lite.py`
- `tests/test_ap_lite_e2e.py`
- `tests/test_p149_ap_lite_diagnose.py`
- `docs/explained/ap-lite.md`
- `docs/explained/ap-lite_de.md`

**Code-Änderungen (8 Files):**
- `core/encoder.py`: Methode `generate_reference_wave` raus
- `core/decoder.py`: `last_pcm_12k`-Buffer-Init + Update raus
- `core/qso_state.py`: `QSOData.partner_last_snr` Field + Update raus
- `ui/main_window.py`: Init + `apply_settings` + Statusbar-Counter raus
  (R1-ORANGE-Catch: `ap_str` komplett entfernt, nicht nur Variable)
- `ui/mw_cycle.py`: Aufruf + `_run_ap_lite_rescue`-Methode raus (~85 LOC)
- `ui/settings_dialog.py`: GroupBox „AP-Lite Diagnose" + 4 widgets +
  load/save 4 keys raus
- `config/settings.py`: 4 DEFAULTS-Keys + Kommentar-Block raus
- `ui/help_dialog.py`: Tupel „AP-Lite Rettung" raus

**Kommentar-Cleanup (R1-GELB):**
- `core/audio_dump.py` Z. 4: „AP-Lite-Decode-Replay" → „Decode-Replay"
- `ui/mw_cycle.py` Z. 230: „...AP-Lite-Rescue" raus
- `tests/test_slot_display.py` Z. 9: idem
- `tests/test_help_dialog_features.py` Z. 40: Sort-Beispiel
  „Auto-Hunt vor Bandpilot" statt „Anrufer-Warteliste vor AP-Lite Rettung"
- `tests/test_modules.py` Z. 2320: AP-Lite-Block-Header raus
- `ui/main_window.py` Z. 102 + 360: Kommentare angepasst

**Doku:**
- `README.md` Z. 231: Zeile „AP-Lite Rescue" aus Feature-Tabelle raus
- `README_DE.md` Z. 303, 379, 468: 3 Stellen raus
- `TODO.md`: P149-Sektion ersetzt durch P151-Eintrag, alte AP-Lite-
  Backlog-Erweiterung „QSO-Abschluss" raus

**R1-V4-pro Findings eingebaut:**
- O1 ORANGE → `ap_str` komplett entfernt (nicht nur Block, auch Format-Zeile)
- G1-G5 GELB → alle Kommentar-Cleanups durchgeführt

**Was BLEIBT:**
- HISTORY.md-Einträge zu P149/v0.98.30 (HISTORY-Regel: nur anhängen)
- Backup `Appsicherungen/2026-05-27_v0.98.31_vor_p150_p151/ap_lite.py`
- `~/.simpleft8/ap_lite_stats.json` (Mike-Datei, kann manuell gelöscht werden)
- Settings-Migration nicht nötig — alte Keys in config.json werden einfach
  ignoriert (kein Code liest sie mehr)

**Tests 2171 → 2110 grün** (-61: 3 AP-Lite-Test-Files entfernt, alle anderen
laufen weiter ohne Regression). App-Smoke-Test: alle Imports OK, 19 Help-
Features (vorher 20), Settings ohne ap_lite-Keys.

**Code-Reduktion:** ~600 LOC entfernt (Modul + Tests + UI + Settings + Docs).
Code-Pflege spart Zeit, weckt keine falschen Hoffnungen mehr, CPU-Last
spart (~85 LOC `_run_ap_lite_rescue` pro Slot lief mit). Stand 0.98.33
ist sauber und schlank.

---

## 2026-05-27 v0.98.32 — P150 Decoder-Empfindlichkeit kMin_score 10 → 4 (FT8) + AP-Lite-Diagnose-Auswertung

**Trigger:** Mike-Feld-Auswertung 27.05. abend: 3 QSOs mit AP-Lite-Test-Modus
gefunkt. Debug-Log zeigte 0/16 MATCH — AP-Lite-Algo findet nichts (Margen
~0). Mike's Logbuch-Analyse: 33 QSOs Verteilung, niedrigster SNR -24 dB
(1×) — Mike will diese „Perlen" (Falklands, DXpeditionen) HÄUFIGER sehen.

**Entscheidung (Chef-KI mit DeepSeek-V4-pro-Konsens):** AP-Lite-Konzept
trägt nicht — Matched Filter hat keine Nische gegenüber LDPC-Decoder.
Stattdessen direkte Decoder-Bremse lösen: `kMin_score` Sync-Pattern-Schwelle.

**Code-Änderung:** `ft8_lib/libft8simple.c` Z. 114 (FT8-Pfad):

```c
- const int kMin_score = 10;   // ~ -21 dB SNR-Limit
+ const int kMin_score = 4;    // ~ -24 dB Empfindlichkeit (WSJT-X Deep ≈ 2.5)
```

**R1-V4-pro O1-Catch (kritisch):** Nicht alle 3 Pfade ändern! FT4 (Z. 369)
und FT2 (Z. 513) bleiben bei 10 — Costas-Pattern-Längen unterschiedlich,
Score-Skala nicht 1:1. FT8 zuerst, FT4/FT2 nach Mike's Erfahrung
separat justieren.

**Was unverändert:** `kLDPC_iterations=50`, `kMax_candidates=140`,
Python-Subtract-Schichten (`MAX_SUBTRACT_PASSES=5`, `SUBTRACT_MIN_SNR=-18`).
Eine Schraube nach der anderen.

**Build:** `libft8simple.dylib` neu kompiliert mit `cc -O3 -DHAVE_STPCPY
-I. -dynamiclib`. MD5 alt: 514a1980… / neu: b897fdcb… verifiziert.
Build-Pipeline: kiss_fft+kiss_fftr Objekte, dann dylib linken aus
`.build/ft8/*.o + .build/common/*.o + .build/fft/*.o`.

**Smoke-Test:** 15 Test-WAVs aus `ft8_lib/test/wav/` (websdr-Samples)
durch alte + neue dylib geschickt → 127 Decodes vs 127 Decodes, alle
identisch. Keine Regression, kein Junk-Decode entstanden. Wirkungstest
kommt mit Mike's Feld-Slots (Test-WAVs haben Score >> 10).

**R1-V4-pro Findings eingearbeitet:**
- O1 ROT → FT8-Only-Änderung (FT4/FT2 unangetastet)
- G1 GELB → Backlog (Plausibilitätsprüfung)
- G2 GELB → Mike kann P30-Diagnose im Auge behalten falls Lag
- G3 GELB → Backlog (Env-Var statt hartkodiert)

**Risiko-Mitigation:** Backup `Appsicherungen/2026-05-27_v0.98.31_vor_p150_p151/`
mit alter dylib + ap_lite.py + libft8simple.c. Rollback in 10 Sekunden.

**Tests 2171/2171 grün.** Field-Test pending — Mike soll morgen schauen
ob -22/-24 dB Decode-Quote spürbar steigt.

**Folge-Ticket:** P151 — AP-Lite-Feature komplett ausbauen (siehe nächster
Eintrag, separater Commit).

---

## 2026-05-27 v0.98.31 — Settings-Tab „Daten & Tools" in ScrollArea (P149-Folge)

**Trigger:** Mike-Field-Screenshot 27.05. 18:21: AP-Lite-GroupBox (P149)
passt unten nicht mehr in den Tab — SNR-Spinbox und Strenge-Combo sind
abgeschnitten, nicht bedienbar. Tab hat jetzt 6 Blöcke (CSV-Export /
Karte / Debug-Konsole / Audio-Dump / Debug-Log / AP-Lite Diagnose).

**Fix:** Reines Layout-Wrap — Tab in `QScrollArea` einpacken. 3 Zeilen
in `ui/settings_dialog.py:_build_tab_data` (`setWidget` + `setWidgetResizable=True` +
`setFrameShape=NoFrame` für nahtloses Aussehen) + Import `QScrollArea`.

**Was unverändert:** Settings-Logik, Default-Werte, alle 4 anderen Tabs,
QGroupBox-Layout, AP-Lite-Spec. Keine Verhaltensänderung — nur Tab
bekommt Scrollbar wenn Inhalt > Dialog-Höhe.

**Smoke-Test:** `tab_widget.widget(3)` ist jetzt `QScrollArea` mit innerem
`QWidget` als Inhalt. Tests 2171/2171 grün (keine Regressions).

**Trivial-Klausel:** Pure Layout-Änderung ohne Verhaltensänderung → V1 →
Code (kein DeepSeek-R1 nötig, fällt unter „pure Refactor ohne
Verhaltensänderung" laut CLAUDE.md DeepSeek-Block).

---

## 2026-05-27 v0.98.30 — P149 AP-Lite Diagnose-Modus (Settings-justierbar + Test-Modus + Logging)

**Trigger:** Mike-Field-Beobachtung 27.05. nachmittag: AP-Lite-Counter
(`~/.simpleft8/ap_lite_stats.json`) steht seit v0.97.90 (5 Tage) auf 0.
Mike: „ich habe keine idee" + „die log datei sehen das ist viel wichtiger" +
„können wir das auf db ummünzen das ich sagen kann ab -20dB soll es greifen
oder so?" → 4 neue Settings + Test-Modus + Debug-Logging.

**Mike-Spec (im Dialog erarbeitet):**
- 4 Knöpfe in Settings (Tab „Daten & Tools"): Master-Toggle / Test-Modus /
  dB-Schwelle (-25 bis -5, Default -20) / Strenge-Combo (locker/normal/streng)
- Test-Modus: AP-Lite läuft AUCH bei dekodiertem Partner — Algo gegen
  Decoder-Wahrheit messbar. KEINE Info-Zeile (nur Debug-Log).
- Mike-Worte „mich juckt erstmal gar nicht was ich sehen kann, die log
  datei sehen das ist viel wichtiger" → UI minimal, Log umfangreich.

**Workflow autonom V1→V2(13 Findings)→R1-V4-pro(2× 🔴 + 2× 🟠)→V3→Code→Final-R1.**

**R1-Findings (alle eingebaut in V3):**
- **🔴 F3 SNR-Filter war kaputt** — `_last_snr` ist global (letzter dekodierter
  SNR irgendeiner Station). In typischem AP-Lite-Use-Case (verpasster
  Partner-Slot) blockiert ein starker Fremd-Decode AP-Lite fälschlich. **Könnte
  sogar Mike's `rescue_count: 0` erklären.** Fix: neuer Cache
  `QSOData.partner_last_snr` in `core/qso_state.py:114` — wird NUR bei
  `msg.caller == their_call` aktualisiert. Bei erster Begegnung (None) →
  SNR-Filter blockiert nicht.
- **🔴 F7 `rescue_count` Inflation im Test-Modus** — heute persistenter
  Counter zählte JEDEN margin-Treffer. Im Test-Modus mit Decoder-bestätigten
  Treffern würde Counter explodieren ohne Aussage. Fix: neuer Param
  `count_rescue: bool = True` in `try_rescue` — im Test-Modus auf False
  gesetzt.
- **🟠 F4 Strenge-Mapping konservativ** — DeepSeek-Empfehlung locker=0.04
  (Sicherheitsabstand zum Rauschen 0.023), normal=0.05 (heutiger MARGIN_MIN
  — Verhalten unverändert bei Default!), streng=0.10.
- **🟡 F1 TEST_COMPARE-Log mit Note** „decoder=reference, not ground-truth".
- **🟠 F10 Multi-Partner-Edge-Case** — `_partner_msgs = [m for m in msgs if
  caller==their]`, defensives Listing statt `any()`.

**Code (5 atomare Commits):**

- **C1:** `config/settings.py` DEFAULTS — 4 neue Keys (`ap_lite_enabled`,
  `ap_lite_test_mode`, `ap_lite_min_snr_db`, `ap_lite_strictness`).
  `core/qso_state.py` — `QSOData.partner_last_snr: float | None = None`,
  Update-Stelle in `on_message_received` am Anfang.
- **C2:** `core/ap_lite.py` — `STRICTNESS_MARGIN_MAP` + `_resolve_margin`,
  `APLite.__init__` mit Instanz-Vars, neue `apply_settings(settings)`,
  `try_rescue(count_rescue=True)` Param, Debug-Log-Calls an 8 Punkten
  (CALL/SKIP×4/SCORED/MATCH/NO_MATCH).
- **C3:** `ui/mw_cycle.py:_run_ap_lite_rescue` komplett überarbeitet —
  Test-Modus + Partner-SNR-Filter + Multi-Partner-Edge + TEST_COMPARE-Log +
  Frequenz-Quelle Test-Modus (Partner-Msg `audio_freq_hz`).
- **C4:** `ui/settings_dialog.py` — GroupBox „AP-Lite Diagnose" in Tab
  „Daten & Tools" (4 Widgets), `_load_values` + `_save_and_close` ergänzt.
  `ui/main_window.py:417` — `apply_settings(settings)` nach
  `get_instance()`, in `_on_settings_clicked` nach Dialog-OK.
- **C5:** `main.py` APP_VERSION 0.98.29 → 0.98.30, HISTORY +
  HANDOFF + CLAUDE.md Header + Memory.

**Final-R1 Verdikt:** PUSH FREIGEBEN ✓ 0 Mängel. „der Code setzt alle
R1-Findings korrekt um, alle 4 Settings fließen lückenlos in die Laufzeit
ein, apply_settings ist an beiden Punkten vorhanden, das Test-Modus-Routing
ist sauber".

**Tests 2149 → 2171 (+22, Datei `tests/test_p149_ap_lite_diagnose.py`):**
- T1-T4 Settings-Defaults + apply_settings + Strenge-Mapping
- T5-T11 Debug-Log (Skip-Reasons + SCORED-Fields)
- T12-T15 Test-Modus + count_rescue + source-level Pattern-Verifikation
- T16-T19 Partner-SNR-Cache (R1-F3 Kern-Fix)
- T20 Multi-Partner-Edge-Case (R1-F10)
- T21 TEST_COMPARE-Ground-Truth-Note (R1-F1)
- T22 Backward-Compat Modul-Konstanten

**V4-pro 69-Cycle: 0 Halluzinationen.** 4 echte Findings (2× 🔴 + 1× 🟠 +
1× 🟡) — V4-pro empirische Bilanz weiterhin stabil.

**Next Step — Mike-Field-Test:**
1. App neu starten (v0.98.30)
2. Settings → „Daten & Tools" → AP-Lite-GroupBox
3. „Debug-Log schreiben" UND „Test-Modus" UND „AP-Lite aktivieren" → AN
4. 1-2 Sessions FT8 normal funken
5. Log lesen in `~/.simpleft8/debug_YYYY-MM-DD.log`:
   - GUARD_SKIP-Verteilung → welcher Guard greift wann
   - SCORED-Margen → wie nah dran ist der Algo am Threshold
   - TEST_COMPARE-Agreement → Algo-Qualität gegen Decoder

## 2026-05-27 v0.98.29 — P142 SWR-Freeze VOR Phase B nehmen (Bandsperre-Freigabe-Fix)

**Mike-Field-Reproduktion 27.05.2026 12:08-12:10** (Bandwechsel auf
defekte Antenne):
```
1. Bandwechsel → Auto-TUNE → SWR > 3 → Bandsperre
   "⚠ Band 15M gesperrt — SWR 17.9"
2. "⚠ Auto-Hunt blockiert — Band 15M SWR-Sperre"
3. Manueller TUNE → Live-Widget zeigt SWR 2.5 (Phase A korrekt)
4. Nach TUNE: "✓ Band 15M freigegeben — SWR 1.0"  ← FALSCH!
5. 2. TUNE: "✓ TUNE OK — SWR 2.5"  ← KORREKT (rfpower vom 1. Lauf
   schon klein → Phase B konvergiert sofort → kein Power-Drop)
```

**Mike-Diagnose:** „der setzt die 1,0 nachdem ich von hand getunt habe
bei tunen zeigt er 2,5 swr ... 2 verschiedene Programmpfade???"

**Antwort:** Es ist **1 Pfad, 1 Quelle** (`_tune_last_valid_swr`),
aber 2 verschiedene Anzeigetexte je nach `was_blocked`. Der echte
Bug ist das **Timing der Freeze-Lesung** (nach Phase B statt vor).

**Root Cause:** In `ui/mw_tx.py:_tune_stop` wurde der SWR-Freeze NACH
Phase B gelesen (Z. 275 alt). Phase B (`_tune_converge_to_target`)
regelt rfpower 5s lang runter — während Power-Drop clampt der
FlexRadio-Sensor auf 1.0 (kein Träger → kein reflektierter Wert).
Der echte Phase-A-Match-Wert (`swr_after_match` aus Z. 255) wurde
nur als Schwellenwert-Check verwendet und danach verworfen.

**Fix Variante C (R1-empfohlen):** Freeze VOR Phase B nehmen — der
Phase-A-Wert wird als `_tune_last_valid_swr` gesetzt, BEVOR Phase B
läuft. Phase B beeinflusst nur noch die RF-Stützpunkt-Speicherung
(`_tune_converged_rf`), NICHT mehr den SWR-Freeze.

**R1-V4-pro Pre-Code ORANGE-Catch (kritisch):**
Cancel WÄHREND Phase B trifft die Re-Entry-Sperre
(`_tune_stop_active=True`). Dort wurde nur `_tune_convergence_cancelled
= True` gesetzt — der schon gesetzte Phase-A-Freeze wäre durchgereicht
worden → Band fälschlich freigegeben trotz User-Abbruch. **Fix
eingebaut:** `_tune_last_valid_swr = None` in Re-Entry-Sperre-Block
(Hardware-Sicherheit).

**Code-Änderungen in `ui/mw_tx.py:_tune_stop`:**

```python
# Re-Entry-Sperre (Cancel während Phase B)
if getattr(self, '_tune_stop_active', False):
    self._tune_convergence_cancelled = True
    self._tune_last_valid_swr = None  # R1-Catch
    return

# Phase A + Freeze + Phase B
if token is not None and self.radio.ip:
    swr_after_match = self.radio.last_swr
    self._tune_last_valid_swr = swr_after_match  # NEU: vor Phase B
    swr_limit = self.settings.get("swr_limit", 3.0)
    if swr_after_match <= swr_limit:
        self._tune_converged_rf = self._tune_converge_to_target(target_w=10)
    else:
        self._tune_converged_rf = None
else:
    # User-Cancel / Disconnect
    self._tune_converged_rf = None
    self._tune_last_valid_swr = None  # garantiert sauberer Stop

# Alte Zeile NACH Phase B entfernt:
# self._tune_last_valid_swr = self.radio.last_swr  # ENTFERNT (P142)
```

**Hardware-Sicherheit gestärkt:**
- Bei knapp-zu-hohem SWR (z.B. 4.5) hätte alte Logik 1.0 eingefroren
  → Band fälschlich freigegeben → TX auf defekter Antenne
- Mit P142: Phase-A-Wert 4.5 bleibt im Freeze → Band bleibt gesperrt ✓
- Cancel-Schutz: User-Abbruch während Phase B → Freeze invalidiert

**Final-R1: PUSH FREIGEBEN ✓** — „sehr KISS-konform" (2 neue Zeilen +
Verschiebung), Mike-Bug 100% gelöst, alle Edge-Cases abgedeckt,
P76-A-Logik im Post-Check unverändert.

**Tests 2138→2149 (+11 P142):** T1 Freeze VOR Phase B, T1b
swr_after_match einmal gelesen, T2 alter Post-Phase-B-Freeze entfernt,
T3 User-Cancel-Pfad None, **T4 Cancel-während-Phase-B (R1-ORANGE-Catch),**
T4b P142-Kommentar im Cancel-Block, T5 SWR > Limit Freeze-Wert bleibt
(Hardware-Safety), T6 Disconnect None, T7 P142-Kommentar mit
27.05.2026 + Phase-B-Doku, T8 Mike-Field-Szenario Phase A bleibt,
T9 Cancel-Pfad-Reihenfolge. 3 alte P76-A-Tests angepasst (Pattern
`swr_after_match` statt `radio.last_swr`).

**Pattern-Klasse:** Hardware-Sicherheits-Fix Familie 3. Iteration
(P53 SWR-Watchdog → P76-A SWR-Freeze → P142 Phase-A-Freeze). Jede
Iteration hat die SWR-Hardware-Sicherheits-Schicht verstärkt.

**Field-Test pending** — Mike hat den Repro frisch, App-Restart auf
v0.98.29 → Bandsperre triggern → manueller TUNE → Log muss „freigegeben
— SWR 2.5" zeigen statt „1.0".

---

## 2026-05-27 v0.98.28 — P148 SWR-Anzeige nur während TX/TUNE updaten

**Mike-Field-Bug 27.05. 06:44** (Screenshot 15m FT8):
- QSO-Log zeigte „✓ TUNE OK — SWR 2.4" + Kalibrierung-Eintrag
- SWR-Anzeige im Radio-Panel: **„SWR 1.0" grün** (TX=0W, RX-IDLE)
- Mike: „1.0 suggeriert super swr zur zeit auf den band"

**Root Cause:** FlexRadio pusht das SWR-Meter via VITA-49 kontinuierlich
— auch im RX wo die PA inaktiv ist. Der Sensor liefert dann Default-Werte
~1.0 (keine reflektierte Leistung → SWR≈1). Die UI hat das jedes Mal
unfilterend übernommen → letzter echter TUNE-Wert (2.4) wurde durch
Sensor-Default (1.0) überschrieben.

**Mike-Wahl Option A (R1-empfohlen):** letzten echten TX/TUNE-Wert
halten, nicht mit Sensor-Default überschreiben. Bei Bandwechsel Reset
auf „—". Alternativen B (— im RX) und C (Hybrid Tooltip) verworfen
(R1: B braucht TX-Ende-Reset, C ist Overengineering).

**Fix (voller Workflow autonom, 3 Änderungen):**

1. **`ui/mw_tx.py:_on_meter_update`** — Filter im SWR-Branch:
   ```python
   elif name == "SWR":
       if self.encoder.is_transmitting or self._tune_active:
           self.control_panel.update_swr(value)
       # sonst: letzter echter Messwert bleibt sichtbar
   ```

2. **`ui/control_panel.py`** — neue Methode `reset_swr_display()`:
   ```python
   def reset_swr_display(self):
       self.swr_label.setText("SWR —")
       self.swr_label.setStyleSheet("color: #888888; ...")
   ```

3. **`ui/mw_radio.py:_on_band_changed`** — Reset-Aufruf NACH
   `settings.set("band", band)`.

**Hardware-Sicherheit (P53 SWR-Watchdog) UNBEEINFLUSST:**
- P53 liest direkt `radio._last_swr` aus FlexRadio (flexradio.py)
- UI-Setter `update_swr` modifiziert `_last_swr` NICHT (T9b verifiziert)
- `swr_alarm` feuert mit Hardware-Wert, nicht UI-Wert
- Keine Rückkopplung UI → Hardware

**Final-R1 V4-pro: PUSH FREIGEBEN** — KISS „sehr klein" (1 if + 4 LOC
Helper + 1 Aufruf), Mike-Bug gelöst, alle Edge-Cases abgedeckt.

**Field-Verhalten danach:**
- TUNE auf 15m: SWR 2.4 (echt gemessen)
- RX nach TUNE: SWR 2.4 bleibt (kein Überschreiben durch 1.0)
- QSO sendet: SWR 1.4 (live während TX)
- RX nach QSO: SWR 1.4 bleibt
- Bandwechsel 15m → 20m: SWR — (grauer Reset)
- TUNE auf 20m: SWR 1.2 (neuer echter Wert)

**Tests 2124→2138 (+14 P148):** T1-T4 Filter-Verhalten (4 Permutationen
TX/TUNE), T5/T5b/T6 reset_swr_display Existenz+Style, T7/T7b Filter
Source-Inspektion + P148-Doku, T8/T8b Bandwechsel-Pfad mit
Reihenfolge-Check, T9/T9b P53-Watchdog-Hardware-Sicherheit, T10 Mike-
Field-Szenario komplett.

---

## 2026-05-27 v0.98.27 — P145 Pattern-Check-Skript mode-aware Symmetrie (Vorbeugung)

**R1-Empfehlung aus P141-Review** (F6 ORANGE, 27.05.): statisches AST-
Analyse-Skript das die Bug-Klasse P102/P114/P135/P141 (mode-aware
Symmetrie-Bugs) AUTOMATISCH findet bevor sie ins Feld kommen.

**Datei `scripts/check_mode_symmetry.py`** (~230 LOC, Python stdlib only).

**Zwei Check-Arten:**

**Check 1: UI-Update-Symmetrie über `_rx_mode == "..."`-Branches.**
Vergleicht NUR Methoden mit Prefix `update_*`, `_refresh_*`, `show_*`
über if/elif/else-Branches innerhalb derselben Methode (R1-F1: ohne
diese Einschränkung Whitelist-Monster).

**Check 2: Mode-Handler-Methoden-Familien.**
Vergleicht hardcoded `MODE_HANDLER_FAMILIES = {"cycle_handlers":
[_handle_normal_mode, _handle_diversity_operate]}`. Wenn UI-Update-
Methode in einem Mitglied vorkommt, im anderen fehlt → ASYMMETRIE.
**P141-Fall würde hier exakt erkannt werden** (R1-Final-R1 bestätigt).

**R1-V4-pro Pre-Code Findings (alle umgesetzt):**
- F1 🔴 Check 1 auf UI-Patterns beschränkt (`UI_UPDATE_PREFIXES`)
- F3 🔴 Geschachtelte elif/else rekursiv via `_collect_branches()`
- F2 🟠 DX-Tune-Familie bewusst NICHT in cycle_handlers (Mess-Phase
  mit Dialog, eigene Logik)
- F4 🟡 Beides: Standalone-Script (Exit-Code für CI/n8n) + Pytest-Test
- F5 🟡 0 Asymmetrien-Erwartung erfüllt

**Real-Codebase-Funde:** 2 Asymmetrien, beide legitim:
- `update_from_stations` = Diversity-only (Antennen-Prefs für Karten)
- `update_snr` = Normal-Mode avg vs Diversity-Mode per-Message (Z. 818)
→ Beide auf `WHITELIST_UI_METHODS` mit Begründung dokumentiert.

**Final-R1: PUSH FREIGEBEN ✓** — „produktionsreif". R1-Bestätigung:
P141-Bug wäre exakt gefangen worden (`update_local_conditions` matcht
`update_*`-Prefix, fehlt in `_handle_diversity_operate` → Asymmetrie).

**Aufruf:** `./venv/bin/python3 scripts/check_mode_symmetry.py`
Output: `✓ Keine mode-aware Symmetrie-Asymmetrien gefunden.` (aktueller
Stand). Exit-Code 0 OK, 1 bei Asymmetrie.

**Pytest-Integration:** `test_t2_real_codebase_no_asymmetries` schlägt
fehl wenn neuer mode-aware Bug eingeführt wird → CI-Schutz für die
ganze Bug-Klasse.

**Pattern-Klasse 5. Iteration** (P102/P114/P135/P141/**P145**) — erstes
Tool das die Klasse vorbeugend abdeckt statt jeweils einzeln zu fixen.

**Tests 2113→2124 (+11 P145):** T1 Smoke, T2 Real-Codebase 0 Asymm.,
T3 synthetisch if/elif-Asym., T4 synthetisch Handler-Familie (P141-Fall),
T5 Whitelist-Schutz, T6 3-Wege-elif (R1-F3), T7a/T7b Exit-Codes,
T8 Pattern-Klasse-Doku, T9/T9b API-Stabilität.

---

## 2026-05-27 v0.98.26 — P144 Auto-Hunt busy-station Filter (Etikette + Band-QRM-Schutz)

**Mike-Field-Bug 26.05. 17:38** (Auto-Hunt 20m FT8):
```
Empfangsfenster 15:34:00:  R2BRD RA5AD RR73   ← RA5AD beendet QSO mit R2BRD
QSO-Log:
  15:35:45 → Gesendet RA5AD DA1MHH -19   ← Auto-Hunt picked RA5AD trotzdem
  15:36:15 → Gesendet RA5AD DA1MHH -19      5x in Folge
  15:36:45 → ...
  15:37:15 → ...
  15:37:45 → ...
  ✗ RA5AD — Timeout                        ← 15:38:15
  15:38:30 ← Empf. DA1MHH RA5AD R-15      ← echte Antwort zu spät → QSO verloren
```

5 Sende-Versuche á 30s = 2:30 Min ins Leere. Etikette-Verstoß (Band-QRM) +
Zeitverschwendung. RA5AD's späte Antwort kam 15s NACH Mike's Timeout.

**Mike-Wahl Option 1:** Abort+Skip ohne Cooldown, später Retry möglich.
„Späte Antwort > 2 Slots ist FT8-untypisch" + KEIN Cooldown lässt Target
für späteren Pick verfügbar.

**Root Cause:** `core/auto_hunt.py:select_next` validierte nur
`looks_like_callsign` (P136) und `_recently_completed_qsos`-Cooldown
(P128/P138/P140) — KEINE „ist Target gerade mit anderem QSO belegt?"-Prüfung.

**Fix (voller Workflow autonom):** Filter in `ui/mw_cycle.py:on_message_decoded`
zwischen P124-Hash-Resolve und P94/OMNI/State-Machine:

```python
if self._p144_target_busy_with_other(msg):
    self._p144_abort_and_skip(
        target=self.qso_sm.qso.their_call,
        busy_with=msg.target,
    )
    return  # nicht in State-Machine geben
```

`_p144_target_busy_with_other`: True wenn Auto-Hunt aktiv + nicht
manual_override + QSO mit Target + msg.caller == target + msg.target !=
my_call + not is_cq.

`_p144_abort_and_skip`: encoder.abort + _pending_tx_log=None (P127/P131-
Pattern) + qso_sm.cancel + auto_hunt.clear_current_target (neue API,
KEIN mark_pick, KEIN Cooldown) + qso_panel.add_info(„⏭ {target} belegt
(sendet an {busy_with}) — überspringe ohne Sperre") + debug_log("HUNT",
"P144_SKIP ...") für Field-Diagnose.

**Neue API in `core/auto_hunt.py`:** `clear_current_target()` setzt nur
`_current_target = None` ohne Cooldown — Mike-Spec „Target bleibt pickbar".

**R1-V4-pro Pre-Code Findings (alle eingebaut):**
- F1 🟠 `_manual_override`-Check ergänzt (bei User-Klick entscheidet User)
- F2 🟠 `clear_current_target()` API statt direkter Privat-Zugriff
- F5 🟡 debug_log("HUNT", "P144_SKIP ...") für Field-Diagnose
- F6 🟡 Test-Erweiterung um clear_current_target + Mock-Funktional

**Final-R1: PUSH FREIGEBEN ✓** — KISS-Bewertung „genau richtig", keine
Race-Bugs, Reihenfolge korrekt. Hinweis: Edge-Case Dauer-busy-Station =
Endlos-Abort-Schleife möglich aber funktional korrekt (kein TX, keine
Verlust) — Mike-Field-Beobachtung pending.

**Pattern-Familie 9. Iteration** (P81/P122/P124/P127/P128/P129/P126/
P131/P138/P140/P144) — KISS-Defensive bei Kontextwechsel.

**Tests 2091→2113 (+22 P144):** T1-T3 RR73/R/Grid an Fremd, T4-T4b CQ,
T5 Antwort an uns, T6 anderer Caller, T7 Auto-Hunt inaktiv, T8 manual_
override (R1-F1), T8b kein QSO, T9a-g Source-Inspektion (encoder.abort/
_pending_tx_log/cancel/clear_current_target/no-mark_pick/add_info/
debug_log), T10 Reihenfolge, T11/T11b clear_current_target Code-only,
T12/T12b Funktional via Mocks (TX läuft / TX läuft nicht).

**FEATURES.md §2** wird durch P144 erweitert (9. Iteration der Defer-Familie).

**Field-Test pending** — Mike beobachtet ob „⏭ belegt"-Meldungen im
Log auftauchen + ob Dauer-busy-Edge-Case relevant wird.

---

## 2026-05-27 v0.98.25 — P147 HALT-Button stoppt Auto-Hunt SOFORT (Hardware-Sicherheits-Fix)

**Mike-Field-Bug 27.05. 04:42-04:43** (3× HALT, lief trotzdem weiter):
```
04:42:15 → Gesendet SV7BAY DA1MHH -13
HALT — alles gestoppt           ← User Klick 1
HALT — alles gestoppt           ← User Klick 2
04:42:45 → Gesendet YO4NT DA1MHH -15   ← Auto-Hunt picked weiter!
HALT — alles gestoppt           ← User Klick 3
04:43:15 → Gesendet TA3ZZ DA1MHH -20   ← weiter
04:43:30 → Gesendet R9MW DA1MHH -17    ← weiter
```
Statusbar zeigte „AUTO HUNT — 8:07" → Session lief tatsächlich noch.

**Mike-Spec:** „halt ist aber notknopf und müsste wie der name sagt
alles anhalten" — HALT ist die letzte Hardware-Sicherheits-
Verteidigung. **MUSS** zuverlässig stoppen.

**Root Cause:** `_on_cancel` (HALT-Button) rief `on_manual_qso_end()`
statt `stop_auto_hunt("manual_halt")`. `on_manual_qso_end()` setzt
nur `_manual_override=False`, `_active` bleibt True → Auto-Hunt
picked weiter Stationen.

`on_manual_qso_end` ist für den Pfad „User klickte manuell Station
während Auto-Hunt lief, QSO fertig, Auto-Hunt darf wieder picken".
HALT ist das **Gegenteil** — falscher Aufruf.

**Fix (autonomer Workflow V1→V2→R1→V3→Code→Tests→Final-R1):**

`ui/mw_qso.py:403-415` 1-Zeilen-Tausch:
```python
if self._auto_hunt.active:
    self._auto_hunt.stop_auto_hunt("manual_halt")
```

`manual_halt` ist seit P122 (v0.98.05) als SOFORT-Stop-Reason
definiert (kein Defer), cleart `_cooldown` + `_last_tx_even`.
`start_auto_hunt` resettet `_manual_override` automatisch (Z. 199)
beim Re-Start — darum kein on_manual_qso_end mehr nötig.

**R1-V4-pro Pre-Code (7 Findings):**
- F1 🟡 flush_pending_stop bleibt (KISS, no-op nach Stop)
- F2 🟢 Symmetrie OMNI/Auto-Hunt OK
- F3 🟢 on_manual_qso_end bleibt für Confirmed/Timeout-Pfade
- F4 🟢 Tests T1-T3 + 1 Zusatztest empfohlen
- F5 🟢 Kein Race (Single-Thread + Defensiv-Check in select_next)
- F6 🟢 Hardware-Sicherheit OK (TX-Abort vor Stop in Z. 398)
- F7 🟡 alten P1.14 W6-Kommentar ersetzen → umgesetzt
- Final-R1: PUSH FREIGEBEN, 0 Mängel.

**Tests 2084→2091 (+7 P147):**
- T1 Source-Inspektion (kein on_manual_qso_end()-Call mehr)
- T2 Funktional (HALT → active=False)
- T3 Regression (Re-Start nach HALT funktioniert)
- T4 on_manual_qso_end bleibt für andere Pfade
- T5 manual_halt cleart _cooldown + _last_tx_even
- T6 Defensive Idempotenz (3× HALT safe)
- T7 P147-Kommentar-Doku

V4-pro Cycle 64: 0 Halluzinationen.

**Mike-Vertrauen-Restore:** HALT-Notbremse funktioniert wieder
zuverlässig. Field-Test pending (Mike kann jederzeit HALT klicken
bei laufendem Auto-Hunt).

---

## 2026-05-27 v0.98.24 — P146 Kalibrierungs-Dialog-Titel mode-agnostisch

**Mike-Field-Bug 27.05. 06:34:** Antennen-Kachel aktiv „DIVERSITY DX",
aber Dialog-Titel zeigt „Diversity Standard — Kalibrierung 20m".
Mike-Spec: „muss der text auch so sein, also das es für beide ist,
ich weiss aber das wir einen text für beide hatten".

**Architektur-Klärung:** P80 (v0.97.52) hat den Gain-Store unified —
Hardware-Gain (ANT1+ANT2) wird einmal pro Band gespeichert, gilt für
Normal + Diversity Standard + Diversity DX. `_on_dx_tune_accepted`
(mw_radio.py:2042-2051) bestätigt das im Code: „Hardware-Gain ist
identisch — wir nehmen die standard-Auswertung". Der bestehende
Untertext „Misst gleichzeitig für Standard- und DX-Modus" (Z. 215
im Dialog) sagt das auch — nur der **große Titel** widersprach.

**Mike's Erinnerung war richtig:** der Text *war* schon mal für
beide gemeint — der `mode_label`-Untertext existiert seit P51.
Nur der Haupt-Titel wurde nie konsistent gemacht.

**Fix (autonomer Workflow V1→V2→R1→V3→Code→Tests→Final-R1):**

`_get_mode_label()` (dx_tune_dialog.py:133-149) vereinfacht:
```python
def _get_mode_label(self) -> str:
    if self.rx_mode == "normal":
        return "Gain-Messung"
    return "Diversity (Standard + DX)"  # P146 mode-agnostisch
```

Der `scoring_mode == "snr"`-Branch im Titel-Code entfernt.
**WICHTIG:** `scoring_mode` bleibt funktional aktiv in Z. 534 (
`use_snr` für `best_for(ant)`) + Z. 680 (`active` Variante) —
dort steuert es die interne Score-Algorithmus-Wahl. Nur die UI-
Titel-Differenzierung entfällt (1-Zeilen-Cleanup).

**R1-V4-pro Pre-Code (6 Findings):**
- F1 🟢 Architektur-Konsistenz mit P80
- F2 🟢 `scoring_mode`-Parameter zu Recht erhalten
- F3 🟡 String-Match-Tests angepasst
- F4 🟡 Mike's „DX zeigt Standard" wird durch generischen Text obsolet
- F5 🟢 Keine anderen UI-Texte zu ändern
- F6 🟢 Backwards-Compat unkritisch
- Final-R1: PUSH FREIGEBEN, 0 Mängel.

**Mike-Erinnerungs-Bestätigung:** R1 hat den vorhandenen
`mode_label`-Untertext „Misst gleichzeitig für Standard- und
DX-Modus" gefunden — DAS ist der Text den Mike sich erinnerte.
Jetzt konsistent zum großen Titel.

**Lesson (für mich):** Initial dachte ich „toter Code seit v0.87.1"
weil ich `scoring_mode == "snr"` auf `DiversityController.scoring_mode`
gemappt habe (`"normal"`/`"dx"`). **Korrektur via Code-Recherche:**
Caller-Mapping in `_start_dx_tuning` (mw_radio.py:1670) übersetzt
`"normal"/"dx"` → `"stations"/"snr"` für den Dialog. Lehre: bei
„toter Code"-Verdacht immer Caller-Mapping prüfen.

**Tests 2082→2084 (+2 P146, +1 modifiziert):**
- Bestehender Test invertiert (beide scoring_modes erwarten
  identischen Text)
- T NEU: Regression-Schutz alter Strings darf nicht zurückkommen
- T NEU: bestehender Untertext bleibt konsistent

V4-pro Cycle 63: 0 Halluzinationen, 1 Selbst-Korrektur „toter Code".

---

## 2026-05-27 v0.98.23 — P141 Sterne-Anzeige im Diversity-Pfad

**Mike-Field-Bug 26.05. 17:15:** Diversity Standard 15m FT8, 14
Stationen sichtbar (SNR -16..-22, Median Top-Half ~-18/-19) zeigten
„Lokale Empfangsqualität: ★☆☆☆☆" (1 Sternchen) statt rechnerisch
4★ nach P120-Schwellen.

**Root Cause:** `compute_local_conditions` + `update_local_conditions`
wurden nur in `_handle_normal_mode` (mw_cycle.py:451-456) gerufen,
nicht in `_handle_diversity_operate`. Anzeige hing auf Init-Default
1★ oder letztem Normal-Mode-Wert.

**Pattern-Klasse: mode-aware Symmetrie-Fehler** (gleicher Bug-Typ wie
P135 v0.98.16 Decode-Count). Wenn ein neuer rx_mode-Pfad eingeführt
wird müssen ALLE Control-Panel-Updates symmetrisch übernommen werden.

**Fix (autonomer Workflow V1→V2→R1→V3→Code→Tests→Final-R1):**

2-Zeilen-Einfügung in `_handle_diversity_operate` vor
`_emit_map_snapshot_if_open()`:

```python
score, n_st, median = compute_local_conditions(self._diversity_stations)
self.control_panel.update_local_conditions(score, n_st, median)
```

Variante A (hartcodiert `_diversity_stations`) statt B (defensiv
if/else) — Handler läuft nur bei `_rx_mode=="diversity"`, KISS.

**R1-V4-pro Pre-Code (6 Findings):**
- F1 🟢 Fix minimal-invasiv
- F2 🟡 Variante A bevorzugt (umgesetzt)
- F3 🟢 Performance unproblematisch
- F4 🟢 Kein Mode-Wechsel-Race (Qt single-threaded)
- F5 🟢 Platzierung semantisch korrekt
- F6 🟠 **Pattern-Check-Skript für später** — P145-Followup
  (statische Analyse: alle `_rx_mode`-Abfragen + Symmetrie-Check
  der Control-Panel-Calls)

**Final-R1: PUSH FREIGEBEN, 0 Mängel.**

**Tests 2075→2082 (+7 P141):**
- T1 Source-Inspektion Diversity-Handler
- T2 Symmetrie-Test beider Handler
- T3 Reihenfolge vor Map-Snapshot
- T4 Mike-Field-Szenario (14 Stationen → 4★)
- T4b Empty-Dict → 1★
- T5 P141-Kommentar
- T6 Variante A hartcodiert verifiziert

V4-pro Cycle 62: 0 Halluzinationen.

---

## 2026-05-26 v0.98.22 — P143 QSO-Log-Resurrection nach Bandwechsel verhindern

**Mike-Field-Bug 26.05. 17:34** (Auto-Hunt 30m → Bandwechsel 20m):
30m-Sende-Einträge tauchten nach ~30 s wieder im QSO-Log auf
obwohl 20m gewählt war und das Log direkt nach Bandwechsel sauber
leer schien. Mike-O-Ton: „macht App komisch".

**Root Cause (Architektur-Bug):** `ui/qso_panel.py` hat seit P95
(v0.97.67) zwei Speicher:
1. `log_view` (sichtbares Widget)
2. `_entries: list[dict]` (Master-SOT für Re-Render)

`ui/mw_radio.py` 3 Stellen riefen nur `log_view.clear()`,
vergaßen `_entries.clear()`:
- Z. 547 `_on_band_changed` (Bandwechsel)
- Z. 438 `_on_mode_changed` (FT-Mode FT8↔FT4)
- Z. 357 `_on_rx_panel_toggled` (RX-On/Off)

Trigger: `_cleanup_timer` (30s-Intervall) ruft
`_auto_trim_by_age` → `_rerender_all()` → zeichnet log_view aus
`_entries` neu. Alte 30m-Einträge tauchten zurück.

**Fix (autonomer Workflow V1→V2→R1→V3→Code→Final-R1):**

Option B (Mike-Wahl): Helper-Methode statt Inline-Fixes.

1. Neue Methode `qso_panel.clear_log_completely()` (vor
   `_append_colored`):
   ```python
   self._entries.clear()
   self.log_view.clear()
   self._last_omni_tx_even = None
   ```
   Reihenfolge Daten → View → State (R1-F1).

2. 3 Aufruf-Stellen in `mw_radio.py` ersetzen
   `log_view.clear()` → `clear_log_completely()`.

3. Docstring dokumentiert: NICHT bei rx_mode-Switch
   (Normal↔Diversity) aufrufen (P115-Spec optische Kontinuität).

**Mike-Spec für Pfade (klar verbalisiert 26.05.):**

| Aktion | leer? |
|---|---|
| Bandwechsel | JA |
| FT-Mode-Wechsel (FT8↔FT4) | JA ("stationen haben keine bedeutung mehr") |
| RX-Mode-Wechsel (Normal↔Diversity) | NEIN (P115) |
| RX-On/Off-Toggle | JA |

**R1-Findings (Pre-Code):**
- F1 🟡 Reihenfolge Daten→View→State (umgesetzt + T5 verifiziert)
- F2 🟢 Thread-Safety ohne Lock (Qt single-threaded)
- F3 🟠 `_last_omni_tx_even`-Reset zwingend (T1 verifiziert)
- F4 🟢 _rerender_all nach Helper harmlos
- F5 🟡 Cleanup-Timer-Race harmlos (Early-Exit)
- F6 🟢 Mike-Spec perfekt umgesetzt
- Final-R1: PUSH FREIGEBEN, 0 Mängel.

**Tests 2066→2075 (+9 P143 + 1 P131-T2 angepasst weil Anker
`log_view.clear()` ersetzt durch `clear_log_completely()`).**

V4-pro Cycle 61: 0 Halluzinationen.

FEATURES.md sollte neue Sektion bekommen die das Helper-Pattern
+ die QSO-Log-Zwei-Speicher-Architektur dokumentiert — folgt
in einem Aufräum-Update.

---

## 2026-05-26 v0.98.21 — P140 Cooldown-Trigger an optischen ✓-Zeitpunkt umhängen

**Mike-Field-Bug 26.05. (5P1KZX, IQ5VK, OE4AHG belegt):** Bei 3 QSOs
hintereinander wurde das 73 der Gegenstation NICHT mehr im QSO-Log
gezeigt obwohl es VOR dem optischen „✓ QSO komplett" ankam.

**Root Cause:** P138 (gleicher Tag) setzte den `_recently_completed_qsos`-
Cooldown in `_on_qso_complete` — das ist aber der **interne** State-
Machine-Trigger der sofort beim eigenen RR73-Send feuert, NICHT der
**optische ✓-Zeitpunkt** (`qso_confirmed_visual` Signal). Die zwei
Trigger sind absichtlich getrennt seit längerem:

| Signal | Wann | Was es macht |
|---|---|---|
| `qso_complete` | sofort beim eigenen RR73-Send | Hardware/State-Cleanup (Auto-Hunt-Pause, ADIF) |
| `qso_confirmed_visual` | nach Empfang von 73 oder Courtesy-73-fertig | rendert optisches „✓ QSO komplett" |

Cooldown an `qso_complete` setzte zu früh → blockte das 73 der
Gegenstation das zwischen RR73 und optischem ✓ ankam.

**Fix (autonomer Workflow V1→V2→R1→V3→Code→Final-R1):**

1. Cooldown-Set ENTFERNT aus `_on_qso_complete` (mw_qso.py:559+).
   P140-Kommentar erklärt warum + verweist auf neuen Set-Ort.
2. Cooldown-Set EINGEFÜGT in `_on_qso_confirmed_visual` (Z. 654+)
   nach `add_qso_complete` — semantisch korrekt: erst optisches ✓
   anzeigen, dann Block-Filter aktivieren.
3. Cooldown-Set EINGEFÜGT in `_on_qso_timeout` (Z. 974+) nach
   `add_timeout` — Mike-Spec defensiv „beendet ist beendet" auch
   nach ✗ (Symmetrie zum Visual-Pfad).
4. Defensive `if their_call:` Guards in beiden neuen Set-Stellen.

**R1-Findings:**
- F1 🔴 (false positive aber wichtig dokumentiert): Auto-Hunt hat
  EIGENEN Cooldown `_recent_qso` (P61), unabhängig von dieser
  Liste. T6 verifiziert die Trennung.
- F2 🟠 (akzeptiert): R-Report-Lücke vor ✓ — State-Machine ignoriert
  R-Report in WAIT_RR73 sowieso. Visuelle Anzeige als KISS-Trade-off.
- F3 🟡 (KISS): Kein Helper für duplizierten Set-Code in Visual+Timeout.
- F4-F6 🟢: Reihenfolge, Defensive-Check und Timeout-Pfad bestätigt.
- Final-R1: PUSH FREIGEBEN, 0 Mängel.

**Pattern-Familie 10. Iteration** (P81/P122/P124/P127/P128/P129/P126/
P131/P138/P140) — KISS-Korrektur einer KISS-Spec.

**Tests 2057→2066 (+9 P140 + 1 invertiert P128-T11).**

V4-pro Cycle 60: 1 false-positive Finding (F1 Auto-Hunt-Cooldown
Sorge), 0 echte Halluzinationen — Pattern-Bilanz bleibt 1 falsch-
positiv ~2%.

FEATURES.md §8 wurde GEUPDATET — neue Tabelle mit 2 Set-Stellen,
Auto-Hunt-Cooldown-Trennung dokumentiert, Field-Beispiel mit
P140-Vorher/Nachher hinzugefügt (Mike-Anweisung 26.05.: nach
nicht-trivialem Fix FEATURES.md ergänzen, sonst tote Datei).

---

## 2026-05-26 v0.98.20 — P139 Auto-Hunt Event-Logging via debug_log

**Mike-Field-Bug (mehrfach):** Auto-Hunt springt mit unvorhersehbarer
Verzögerung an (~30-60s, einmal 8 Min nach SWR-Sperre-Freigabe). Bisher
keine Diagnose-Daten — wir wussten nicht WO die Sekunden verloren gingen.

**Lösung:** Komplettes Auto-Hunt-Event-Logging über das **existierende**
`core/debug_log.py`-Framework (P21 v0.96.8, Mike 10.05.). Kein neues
Logging-System, nur Hooks in die Auto-Hunt-Pfade. Mike-Erinnerung war
korrekt: „grundgerüst für log debbuging müsste noch vorhanden sein".

**Hooks (voller Workflow V1→V2→R1→V3→Code→Final-R1):**

`core/auto_hunt.py`:
- `start_auto_hunt`: `HUNT START band/mode/duration`
- `stop_auto_hunt`: `HUNT STOP reason=... [DEFERRED]` **VOR Defer-Check**
  (R1-ORANGE-Catch: sonst sind deferierte Stops unsichtbar bis QSO-Ende)
- `select_next`: Eingangsparameter (msgs/qso_idle/presence/active/override),
  alle 4 Early-Return-Reasons, alle 5 Skip-Reasons in Filter-Schleife
  (empty_call/not_callsign/recent_qso_cooldown/fail_cooldown/low_snr),
  **pre/post-Affinity-Counts** (R1-GELB-F3 Catch), **NO_CANDIDATE mit
  reason-Differenzierung** (empty_list vs score_zero, R1-GELB-F2 Catch),
  PICKED-Event mit allen Diagnose-Feldern
- `mark_pick`: `HUNT MARK_PICK call=...`

`ui/mw_cycle.py:_run_auto_hunt`:
- `HUNT START_QSO target/freq/tx_even` nach select_next

`ui/mw_qso.py:_on_tx_started`:
- `HUNT TX_STARTED msg/tx_even` **nur wenn Auto-Hunt aktiv**
  (kein Spam bei manuellem TX / OMNI)

**Alle Hooks try/except-gewrappt** — `debug_log` darf NIE App crashen
(P21-Anforderung).

**R1-V4-pro PUSH FREIGEGEBEN.** 3 Findings übernommen:
- F1 ORANGE: STOP-Log vor Defer-Check (kritisch)
- F2 GELB: NO_CANDIDATE-Reason differenziert (empty_list/score_zero)
- F3 GELB: pre/post-Affinity-Counts

**APP_VERSION:** 0.98.19 → 0.98.20

**Tests 2042 → 2057** (+15):
- `tests/test_p139_auto_hunt_event_logging.py` NEU (15 Tests):
  T1-T12 Source-Inspektion (alle Hooks + Reihenfolge + Reasons),
  T13-T15 Mock-basierte Verifikation dass debug_log mit Category
  „HUNT" gerufen wird

**FEATURES.md:** Sektion 8a NEU „Debug-Log-Datei für Bug-Diagnose"
mit Aktivierungs-Anleitung, allen Kategorien-Tabelle (ANT/BAND/DIV/
OMNI/QSO-DONE/HUNT), Cleanup-Hinweis, typischen Workflows, Auto-Hunt-
Diagnose-Beispiel.

**Was Mike jetzt tun kann:**
1. Settings → „Debug-Log schreiben" AN
2. Auto-Hunt-Klick → 60s warten → App schließen
3. `~/.simpleft8/debug_2026-05-26.log` durchgehen → exakte Diagnose
   wo die Sekunden verloren gehen

