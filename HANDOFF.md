# HANDOFF — SimpleFT8

**🟢 START-SATZ NACH COMPACT (Mike tippt das → genau hier weiter):** „**Optimierung weiter,
autonom**" — dann `CLAUDE.md → HISTORY.md (Anker) → HANDOFF.md → OPTIMIERUNGSWORKFLOW.md`
lesen, NICHT neu planen, beim ersten offenen ☐ weiter. **⚠️ KISS-Stufe KOMPLETT** (OPT-61/63/64,
OPT-62 obsolet) — nächste offene Stufe ist **Geschwindigkeit (Mike: NACHRANGIG)** +
**große Methoden** (langfristig). Da die „sicheren/klaren" Stufen (toter Code, Robustheit,
KISS) durch sind und der Rest nachrangig/heikler (Decoder-nah) ist → **Richtungs-Abstimmung
mit Mike sinnvoll**, NICHT blind weiter. Gesperrt bis Mike-Wort: OPT-59/55/58 + Threading
OPT-52 + OPT-Q4 (save_*).

**✅ GEPUSHT (Mike-Freigabe 05.06.2026):** Die komplette Robustheits- + KISS-Kampagne
(25 Commits, v0.99.10–v0.99.19) liegt auf **`origin/main` (`e097acc`)**. 0 ungepusht,
Arbeitsbaum sauber. Rückfall-Tag `v0.99.9-pre-optimierung` (`a80eebc`) bleibt.

**Aktueller Stand:** v0.99.19 (05.06.2026) — **Optimierungs-Kampagne: Robustheits-Stufe
(OPT-50..60) UND KISS-Stufe (OPT-61/63/64, OPT-62 obsolet) ABGESCHLOSSEN.** Erledigt:
**Stufe 1 toter Code (v0.99.10)** + **3 tote Module (v0.99.11)** + **OPT-50/51
Start-Crash-Schutz (v0.99.12)** + **OPT-54 `atomic_write_json`-Helfer (v0.99.13)** + **OPT-53
Settings-Typvalidierung (v0.99.14)** + **OPT-56 closeEvent-except entschärft (v0.99.15)** +
**OPT-57 station_stats sauberer Thread-Stop (v0.99.16)** + **OPT-60 geprüft = kein
Handlungsbedarf** + **OPT-61 `is_busy`-Property (v0.99.17, KISS, 7× Dedup)**. Alles
reine/robustheits-/KISS-Änderung, **ANT1=TX unberührt**, jedes Stück DeepSeek-R1 FREIGEBEN,
Tests durchgehend grün (**aktuell 2469**). Detail → HISTORY v0.99.10–19 + Fortschritts-Log
in **`OPTIMIERUNGSWORKFLOW.md`**. Rückfall-Tag `v0.99.9-pre-optimierung`. **✅ GEPUSHT (origin/main e097acc)
(genaue Zahl via `git log --oneline origin/main..HEAD | wc -l` — aktuell ~20).**

**▶ NÄCHSTE Stufe (Mike-Richtungsentscheidung empfohlen — keine „sicheren" Punkte mehr offen):**
- **Speed (Mike: NACHRANGIG)** — Bündel 1B `OPT-05..11` (Modul-Konstanten in `decoder.py`
  vorberechnen: `np.hanning`/Filter-Taps, Slot-Dauer-Dict, target_rms; verhaltensneutrales
  Caching, aber Decoder-nah) + `OPT-20` Float/Int-Pipeline (braucht Decode-Referenztests,
  heikler) + `OPT-23/24`.
- **Große Methoden** (langfristig/opportunistisch): `OPT-65` `_update_statusbar`,
  `OPT-66` `_handle_diversity_operate`, `OPT-30..32` control_panel/mw_radio.
- **Gesperrt bis Mike-Wort:** OPT-59 (TX-Pfad) / OPT-55 / OPT-58 (Bug-Verdachte),
  OPT-52 (Threading), OPT-Q4 (`save_*`-API entfernen — Empfehlung BEHALTEN). **(Push: ✅ erledigt 05.06., origin/main e097acc.)**

**Zuletzt erledigt:** **OPT-64** (v0.99.19, `c9726b7`): KISS — Modul-Funktion `_valid_bands`
dedupliziert die Band-Validierung in `get_enabled_bands` + `set_enabled_bands` (settings.py;
Variante A, im Betrieb verhaltensneutral). DeepSeek R1 GO (Modul-Fn-Empfehlung) + Final-R1
PUSH FREIGEBEN. Tests 2461→2469 (+8 `test_valid_bands`). **→ KISS-Stufe komplett.**
**Davor OPT-63** (v0.99.18, `7f0b0e3`): `_resolve_station_position`-Helfer (Locator-Auflösung
DRY). **OPT-61** (v0.99.17, `6a48ea6`): `@property is_busy` (verify-don't-assume: real 7, nicht
„11×"). **OPT-62** (geprüft=obsolet). **OPT-57** (v0.99.16) station_stats Sentinel-Stop.
**OPT-56** (v0.99.15) closeEvent-except. **OPT-60** (geprüft). **OPT-53/54** (v0.99.13/14).

**⛔ NUR nach Mike-Rückmeldung (nichts eigenmächtig):**
- **TX-Pfad-Verdacht OPT-59** (`_p94_quick73_filter` evtl. ohne `_abort_active_tx` —
  dreifach prüfen) + **Zufallsfund-Bug-Verdachte** OPT-55 (ADIF `CALL.upper()` QRZ-Upload) /
  OPT-58 (`_execute_full_halt` leert `_p158_insertable` nicht).
- **Push?** Aktuell **10 Commits lokal ungepusht** — Push erst auf Mike-Wort.

**Reihenfolge (Plan):** Robustheit → KISS → Speed nachrangig → große Methoden. Alle
OPT-Punkte + Status: **`OPTIMIERUNGSWORKFLOW.md`**. Voller Audit-Befund: `OPTIMIERUNG_AUDIT.md`.

**Nebenbei (04.06.):** Mike hatte versehentlich die DT neu kalibriert (−0.69) →
auf 0.26 zurückgesetzt; Mike justierte selbst auf 0.22 (eigener Wert, steht so).

**🔎 Weiter offen (separat):** Auto-Hunt→OMNI-Wechsel-Dauer ~1:45 — OMNI-Diagnose-
Marker (v0.99.3) liegen; Mike reproduziert mit Debug-Log → echte Ursache lesen.

— **Vorgänger v0.99.5: WAIT_73-Horchphase nach RR73 von 3 auf 2 Slots verkürzt
(Auto-Hunt-Pause ~60→45 s, WSJT-X-konform).** `WAIT_73_MAX_CYCLES = 2` (war 3).
„2" = Untergrenze (on_cycle_end triggert am Slot-START → erster RX-Slot noch
abgewartet). Höflichkeits-73 + Nachsende-Schutz bleiben. DeepSeek Plan-R1 + Final-R1
PUSH FREIGEBEN. Tests 2398→2402. Field-Test pending (Rückfallpunkt `bfa20dd` gepusht).

— **Vorgänger v0.99.4: Einheitliche Bedienung über HALT + smartes HALT (Ruf sofort /
QSO deferred).** Modus-Buttons starten nur aus Ruhe (sonst „erst HALT"); HALT smart —
Ruf (bis `WAIT_REPORT`) → sofort, laufendes QSO (ab `TX_REPORT`) → armiert (QSO läuft +
loggt zu Ende; oranger „HALT •"), 2× HALT = sofort hart. Neu `disable_cq_resume()`
(DeepSeek-R1 gegen CQ-Wiederaufleben) + `QSO_IN_EXCHANGE_STATES`; `_on_cancel`-
Dispatcher + `_arm_deferred_halt`/`_execute_full_halt`. Tests 2387→2398 (+11). NICHT gepusht.

— **Vorgänger v0.99.3: PSK-Timer-Spin behoben (4 GB-Debug-Log-Flut) +
OMNI-Diagnose-Marker.** PSK: `_reset_psk_polling_on_change` startet den Timer
mit `start(0)`; lag die Intervall-Umschaltung hinter dem `_has_sent_cq`-Return,
spinnte der Timer endlos (4 GB/Tag + CPU). Fix: Umschaltung VOR den Return (DeepSeek
R1 6/6). Altlasten ~6 GB gelöscht. OMNI: `debug_log("OMNI",…)`-Marker an
START/STOP/PAUSE/RESUME + `on_cycle_start` (paused/parity-skip/TX/encoder-busy) +
`_maybe_resume_omni` → nächster Auto-Hunt→OMNI-Wechsel zeigt im Log exakt, warum
~1:45 vergehen. Reines Timing/Logging, ANT1/ANT2 unberührt. Tests 2384→**2387** (+3).
NICHT gepusht.

**🔎 Offene Mike-Frage (Field 03.06.) — Auto-Hunt→OMNI-Wechsel ~1:45:**
Verifizierter Teil-Befund: `omni_cq.resume_after_qso` behält die ALTE Parität →
≤1 Slot (Mikes „even→even"). Erklärt NICHT die vollen 1:45 → der größere Blocker
wird jetzt mit den OMNI-Markern (v0.99.3) beim **nächsten Wechsel sichtbar**.
**Nächster Schritt:** Mike reproduziert (Auto-Hunt→OMNI) mit aktivem Debug-Log →
`~/.simpleft8/debug_*.log` lesen → echte Ursache → gezielter Fix (voller Workflow).
Mike-Idee „nächster freier Slot egal Parität" bleibt als Quick-Win-Option (≤1 Slot).

— **Vorgänger v0.99.2: DT-Kalibrier-Knopf (⏱) nur auf FT8 sichtbar** (FT4/FT2
ausblenden, Fehlklick-Schutz; DeepSeek Final-R1 4/4). `rx_panel.set_calibrate_visible`;
`_on_mode_changed` schaltet `mode=="FT8"`; FT8-Guard bleibt Sicherheitsnetz. Tests
2380→2384. NICHT gepusht.

— **Vorgänger v0.99.1: Eingeklappter RADIO-Header: Netto-Watt +
farbiges SWR beim Senden** (voller Workflow, DeepSeek Plan-R1 GO + Final-R1 PUSH
FREIGEBEN). Die eingeklappte RADIO-Kachel zeigt beim Senden „— 80 → 58 W · SWR 1.2"
(SWR farbig per Ampel), im Empfang weiter „— 80 W". `ui/control_panel.py`: Helper
`swr_color()` (DRY mit `update_swr`); `_refresh_radio_status_label` hängt bei
`_last_watt>0` Netto-Watt (`compute_net_power`) + farbiges SWR (Rich-Text-Span) an;
Live-Trigger in `update_watt`/`update_swr`/`reset_swr_display`; `getattr`-Default für
Init-Reihenfolge. Reines Anzeige-Feature, ANT1/ANT2 unberührt. Tests 2370→**2380**
(+10 `test_radio_header_collapsed.py`). **✅ BEIDE field-validiert (Mike am Radio
03.06.):** RADIO-Header „SWR und Watt-Zahl super zu sehen"; DT-Kalibrierung (v0.99.0)
„klappt super", DT sehr gut im ±-Bereich, FT4 gut, App flüssiger (weniger Arbeit pro
Slot). NICHT gepusht.

— **Vorgänger v0.99.0: DT-Korrektur: dynamisches Dauer-Lernen
RAUS, manueller Kalibrier-Knopf REIN** (großer Umbau, voller Workflow, DeepSeek
Plan-R1 GO + Final-R1 PUSH FREIGEBEN). Die automatische DT-Lernschleife
(`core/ntp_time.py`: Mess-/Operate-Phasen, Dämpfung, Sprung-Reset, Fast-Convergence)
war fragil — Wert pendelte/sprang ins Minus, FT8→FT4→FT8-Übergang verdarb ihn →
OMNI-CQ sendete 30/60s. **Kein fester Konstanten-Wert möglich**, weil Mikes
Ferienhaus-iMac (defekte Pufferbatterie) eine um 3–5s driftende Uhr hat → es
braucht eine nachjustierbare Korrektur, aber als **bewusste Einmal-Messung auf
Knopfdruck**. `core/ntp_time.py`: Lernschleife komplett entfernt; neu
`record_samples()` (puffert nur das gleitende FT8-Fenster `deque(maxlen=3)`) +
`calibrate()→(ok,msg)` (Median+MAD der Residuen, **inkrementell** `_correction +=
median`, voller Schritt, Clamp ±1.0, **kein Negativ-Riegel** — driftende Uhr darf
negativ). ⏱-Knopf in `rx_panel` (neben 🔊), Handler `mw_radio._on_calibrate_dt`
(nur FT8, Info + Statusbar-Refresh). `get_time()`/`get_correction()` unverändert
(v0.98.63-Slot-Takt-Fix intakt). **Reines Timing/Anzeige, ANT1/ANT2 unberührt.**
Tests 2358→**2370** (+12, neu `test_dt_calibrate.py`; Lern-/Phasen-/DEADBAND-Tests
durch Kalibrier-Äquivalente ersetzt). **Field-Fix (Mike am Radio, gleiche Session):**
mehrfaches Drücken ließ den Wert klettern (Puffer wurde nach Kalibrierung nicht
geleert → Doppel-Addition) → `_recent_samples.clear()` nur im Erfolgsfall (DeepSeek
R1 bestätigt, +2 Tests). Encoder-Drift-Guard-Robustheit bleibt separates TODO. **⚠️
Mike: App NEU STARTEN** (kein Auto-Lernen mehr — DT-Wert per ⏱ setzen).
Sicherheitsanker GitHub `22f3d07` (v0.98.63, alte DT-Berechnung). NICHT gepusht,
Field-Test pending.

**Nächster Schritt (Field-Test für Mike):** App neu starten → auf FT8 warten bis
≥5 Stationen empfangen → ⏱-Knopf drücken → Info-Zeile zeigt „DT kalibriert: +0.xx s
(aus N FT8-Stationen)" → DT-Zeiten der Stationen prüfen (sollten um 0 liegen). Auf
FT4/FT2 erbt der Wert + Modus-Versatz automatisch. Bei driftender Ferienhaus-Uhr
einfach erneut ⏱ drücken.

— **Vorgänger v0.98.64: FT-Modus-Wechsel bricht laufendes QSO/TX ab (gemeinsamer
Abbruch-Helper)** (voller Workflow). Fix `ui/mw_radio.py`: Abbruch-Block in Helper
**`_abort_qso_and_tx()`** extrahiert, von allen drei Wechsel-Pfaden gerufen. Tests
2349→2358. NICHT gepusht.

— **Vorgänger v0.98.63: FT4-OMNI sendete 30s statt 15s —
Slot-Takt vom Modus-Versatz entkoppelt** (voller Workflow, 2× DeepSeek). Mike-
Field: OMNI-CQ auf FT4 sendete nur alle 30s (Log je +30s), **intermittierend**
(mal 15s mal 30s, je nachdem ob vorher FT8). **Regression aus v0.98.62.**
Diagnose: Der Cycle-Timer (`timing.py:43`) leitet den Slot-Takt aus
`ntp_time.get_time()` ab — und `get_time()` zog seit v0.98.62 den
`_MODE_DELTA["FT4"]=−0.30` mit → `cycle_start` feuerte auf FT4 zu spät (an der
Grenze) → OMNI-TX landete im aktuellen Slot dessen Sende-Frist schon vorbei war →
Encoder-Drift-Guard (`encoder.py:337`) +2 Slots, Folge-Slot „encoder busy" → 30s.
**Schwellenabhängig:** kippt sobald `_correction < 0.30` (FT4-effektiv ≤ 0); da
nur FT8 misst und der Wert um ~0.27–0.45 schwankt, flackerte es. Fix
(`core/ntp_time.py`, 1 Funktion): `get_time()` nutzt jetzt NUR die FT8-Basis
`_correction` (OHNE Delta) → Slot-Takt immer deutlich positiv → deterministisch
15s. `get_correction()` (mit Delta) bleibt für RX-Decode-Shift + Anzeige → FT4
zentriert (keine RX-Regression). Physikalisch korrekt (TX am echten Protokoll-
Slot; −0.3-TX-Versatz würde uns bei der Gegenstation mit DT −0.3 zeigen).
**Kein TX-Antennen-Eingriff, ANT1/ANT2 unberührt** (Encoder nutzt ohnehin reine
`time.time()`). DeepSeek R1 (wasserdicht) + Final-R1 **PUSH FREIGEBEN** (Schwelle
korrekt, Umsetzung exakt, keine Nebenwirkungen, Kaltstart-Edge bestätigt). Tests
2348→**2349** (Test umgedreht + neuer `test_slot_takt_invariant_but_rx_diverges`).
**✅ Field-Test BESTANDEN (Mike am Radio, 03.06.2026):** FT4-Sende-Takt wieder
korrekt (~8s Slot-Intervall, durch laufendes QSO bestätigt — kein 30s mehr),
FT4-Empfang/DT-Zeiten sehr gut. Damit erledigt. Push-Stapel v0.98.56–v0.98.63
freigegeben (Mike: „erst alles pushen, dann P124/P126 angehen").

— **Vorgänger v0.98.62: DT-Korrektur modus-abhängig (FT4-Versatz)** (voller
Workflow). FT8-DT um 0, FT4 alle ~−0.3 → `_MODE_DELTA = {FT8:0, FT4:−0.30, FT2:0}`
auf `get_correction()`; nur FT8 lernt Basis, FT4/FT2 erben + Delta. DeepSeek
Final-R1 fand P171-Migrations-Bug (FT4-only-Datei → falsche ~0-Basis) → gefixt.
**✅ Field-Test BESTANDEN:** FT4-DT −0.3→~0 (leicht +0.1), Empfang STABIL (11
Stationen, kein P168-Einbruch), FT4-QSOs liefen (LZ2II, SV7BAY). Offene
Mikrojustierung (NICHT akut): optional `_MODE_DELTA["FT4"]` −0.30→−0.20, NUR
datenbasiert. Tests →2348. NICHT gepusht. — **Vorgänger
v0.98.61: Audio-Mithör-Monitor (🔊-Toggle, Diagnose)** — RX-Audio auf Lautsprecher
als Diagnose (Decoder unangetastet via Wrapper, 48k-Ringpuffer, sounddevice).
Tests +15, PUSH FREIGEBEN, nicht gepusht. — **Vorgänger v0.98.60 P171: DT-Korrektur auf EINEN
globalen Wert** (voller Workflow). Mike: wenige Stationen auf FT4/FT2
verschlechtern den DT-Wert; die Korrektur ist die Funkgerät-Latenz und damit
modus-/band-unabhängig → nur FT8 misst, FT4/FT2 lesen, **ein Wert für alle
Bänder/Modi**. Field-Beweis: FT4_20m=0.045 war ein 1-Stationen-Ausreißer (FT8
~0.27). `core/ntp_time.py` auf einen globalen `_correction` umgebaut
(`{"dt_correction_s":0.26}`); `set_mode`/`set_band` behalten ihn;
`update_from_decoded` nur bei FT8; Migration alt→global = Median der FT8-Werte
(in-memory, kein Import-Write); Cross-Modus-Fallback/per-Modus-Logik entfernt
(übersichtlicher). DeepSeek R1 + Final-R1 **PUSH FREIGEBEN** (kein Datenverlust,
Seed/Migration robust). Tooling: `deepseek_review.py max_tokens 16K→32K` (v4-pro
sprengte das Limit). Tests 2332→**2324** (entfernte Sonderpfade). **⚠️ Mike: App
NEU STARTEN** (Migration baut dt_corrections.json um). Kein TX-Eingriff. NICHT
gepusht (auch P168 v0.98.56 + P169 v0.98.57/.58 + P170 v0.98.59 offen). —
**Vorgänger v0.98.59 P170: Upload-Move mergt bei Namens-Kollision** (voller Workflow). Mike-Field: 205 hochgeladene QSOs blieben
in der „neu"-Liste hängen, weil das Verschieben nach „fertig" (`hochgeladen/`)
bei gleichnamiger Tagesdatei **übersprang** (11 von 12 neu-Dateien hatten einen
Zwilling in hochgeladen/ — Folge der Phase-1-Migration). Fix: bei Kollision die
Records dedupliziert **mergen** (`log/adif.py:merge_adif_files`, byte-erhaltend +
atomar + `<EOH>`-Validierung), `neu/`-Datei danach löschen. DeepSeek R1 +
Final-R1 (erst NICHT FREIGEBEN wegen Newline-Byte-Erhalt → behoben) → Final-R1b
**PUSH FREIGEBEN**. Tests 2324→**2332** (+8). **Die 205 räumen sich von selbst
auf:** App neu starten → **einmal QRZ-Upload klicken** → sie gehen als Dups durch
und werden je Datei nach hochgeladen/ gemergt, „neu" leert sich. Reine
Dateioperation, kein TX-Eingriff. NICHT gepusht (auch P168 v0.98.56 + P169
v0.98.57/.58 offen). — **Vorgänger v0.98.58 P169 Phase 2: mode-genauer
Worked-Filter (Call,Band,Mode) + Auto-Hunt-Transparenz** (voller Workflow).
„Schon gearbeitet" unterscheidet jetzt die Betriebsart: eine auf 20m FT8
gearbeitete Station ist auf 20m FT4 / 15m FT8 wieder „neu" — NEUE-Filter
(RX-Liste) UND Auto-Hunt band+mode-genau. Neuer Index
`QSOLog._worked_band_mode` (effektiver Mode = SUBMODE sonst MODE; leerer Mode nie
indiziert), Live-`add_qso` gibt `settings.mode` mit, rx_panel liest Band+Mode
lazy über Provider-Callback (kein Staleness), Auto-Hunt meldet entprellt „alle N
auf {Band} {Mode} schon gearbeitet" im QSO-Log. Begleitfix: `auto_hunt.set_band`
wird bei Bandwechsel jetzt IMMER aktualisiert (war nur bei aktiver Session →
Staleness). DeepSeek R1 (6×🟡/⚪, F2+F4 angenommen, F1+F3 abgelehnt) + Final-R1
**PUSH FREIGEBEN** (0 Bugs/Risiken). Land-Seltenheit bleibt mode-blind (keine
P165-Regression). Tests **2324 grün** (+12). Kein TX-Eingriff, ANT1/ANT2
unberührt. **Damit ist P169 komplett (Phase 1 + 2).** Lokal committet,
**Push-Freigabe Mike ausstehend** (auch P168 v0.98.56 + P169 Phase 1 v0.98.57
noch nicht gepusht). Field-Test pending.

---

## Session 03.06.2026 — P171: DT-Korrektur global (v0.98.60)

**Anlass:** Mike — DT-Wert auf FT4/FT2 verschlechtert durch wenige Stationen; die
Korrektur ist Funkgerät-Latenz (modus-/band-unabhängig) → nur FT8 ermitteln, ein
Globalwert. Field-Beweis FT4_20m=0.045 (1-Stationen-Artefakt).

**Gemacht:** `core/ntp_time.py` auf einen globalen Wert umgebaut (nur FT8 misst/
schreibt, FT4/FT2 lesen; Migration alt→global = Median der FT8-Werte; Cross-
Modus-/per-Modus-Logik raus). DeepSeek R1 + Final-R1 PUSH FREIGEBEN. Tests
2332→2324.

**Nächste Schritte:**
1. **Mike: App NEU STARTEN** → Migration baut `~/.simpleft8/dt_corrections.json`
   auf den Globalwert um (Median der FT8-Werte ~0.26; FT4_20m=0.045-Müll fällt
   raus). Danach lernt nur noch FT8, FT4/FT2 fahren mit dem FT8-Wert.
2. **Push** offen: P168 v0.98.56 + P169 v0.98.57/.58 + P170 v0.98.59 +
   P171 v0.98.60 — auf Mikes Freigabe.

---

## Session 03.06.2026 — P170: Upload-Move mergt bei Kollision (v0.98.59)

**Anlass:** Mike-Frage „205 hochgeladen — werden die als fertig verschoben? sonst
häufen die sich". Verifiziert: neu/ = 205 QSOs, 11/12 Dateien kollidieren mit
gleichnamigen in hochgeladen/ → Verschieben übersprang → Stau.

**Gemacht:** `merge_adif_files` (dedup `(CALL,QSO_DATE,TIME_ON)`, byte-erhaltend,
atomar, `<EOH>`-validiert); `_handle_qrz_file_results` mergt bei Kollision statt
zu skippen. DeepSeek 2 Runden (Datensicherheit), Final-R1b PUSH FREIGEBEN. Tests
2324→2332 (+8).

**Nächste Schritte:**
1. **Mike: App neu starten, dann einmal „QRZ"-Upload klicken** → die 205 gehen
   als Dups durch + werden je Datei nach hochgeladen/ gemergt → „neu" leert sich.
   (Kein Hand-Anlegen nötig, die App macht es korrekt mit dem Fix.)
2. **Push** offen: P168 v0.98.56 + P169 v0.98.57/.58 + P170 v0.98.59 — auf
   Mikes Freigabe.

---

## Session 02.06.2026 — P169 Phase 2: mode-genauer Worked-Filter (v0.98.58)

**Anlass:** Mike — „NEUE soll ALLE Stationen filtern die ich auf DEM Band UND in
DER Betriebsart gearbeitet habe: Station auf 20m FT8 → bei NEUE auf 20m FT8 nicht
anzeigen, auf 20m FT4 anzeigen, auf 15m FT8 anzeigen." Plus: Auto-Hunt soll nicht
stumm schweigen, wenn alle gearbeitet sind.

**Gemacht (voller Workflow):** mode-genauer Index `_worked_band_mode` in
`QSOLog` (additiv), `is_worked_on_band_mode(call,band,mode)`, Live-`add_qso` mit
`settings.mode`. NEUE-Filter (rx_panel) band+mode-genau via Provider-Callback
(lazy aus settings → keine Sync-Bugs). Auto-Hunt-Worked-Filter mode-genau +
entprelltes `all_worked`-Signal → Info im QSO-Log. `set_band` bei Bandwechsel
immer (Staleness-Fix). DeepSeek R1+Final-R1 PUSH FREIGEBEN. Tests 2312→2324
(+12 `test_p169_phase2.py`). Mode-Norm: SUBMODE-vor-MODE (ADIF-Standard).

**Nächste Schritte:**
1. **Mike: App neu starten** (falls Phase-1-Neustart noch aussteht — Phase 2 ist
   reiner Code, keine Datei-Migration). NEUE-Filter testen: Station auf einem
   Band+Mode arbeiten → auf demselben Band+Mode bei NEUE weg, auf anderem
   Mode/Band sichtbar.
2. **Auto-Hunt auf vollem Band:** sollte jetzt „alle N auf {Band} {Mode} schon
   gearbeitet" im QSO-Log zeigen statt stumm zu zählen.
3. **Push** (P168 v0.98.56 + P169 v0.98.57 + v0.98.58) — auf Mikes Freigabe.

---

## Session 02.06.2026 — P169 Phase 1: erfasst/ + Import + Migration (v0.98.57)

**Anlass:** Auto-Hunt rief auf vollen Bändern nicht (Debug-Log: `all_worked_on_band`).
Mike-Analyse → ADIF-Ablage „Kraut und Rüben": Worked-Index las nur 3/8 Ordner,
nicht-rekursiv; frische QSOs zählten erst nach Upload; 95 Stationen nur in
nicht-geladenen Ordnern; doppeltes `adif/adif/`.

**Gemacht:** EINE Quelle `adif/erfasst/{neu,hochgeladen,importiert}/` (rekursiv).
Migration via `tools/migrate_adif_erfasst.py` (copy→SHA256-verify→delete + Backup-
ZIP nach Appsicherungen/, idempotent, Nicht-ADIF bleibt) — 75 .adi migriert,
9647 (Call,Band) byte-genau erhalten. 8 Code-Touchpoints umgestellt
(recursive-Load, AdifWriter→neu/, Upload neu→hochgeladen, export aus erfasst/,
Diplome via _all_records, `QSOLog.clear()`). Import-Button (validieren→importiert/
→reload). DeepSeek Migration-R1 (7 Findings→gehärtet) + Final-R1 PUSH FREIGEBEN.
Tests 2303→2312 (+9). adif/ gitignored.

**Nächste Schritte:**
1. **Mike: App neu starten** → lädt neuen Code + erfasst/ (FT4-Empfang von P168
   weiterhin gut). Auto-Hunt-„kein Ruf" war KEIN Bug, sondern P165-Filter (alle
   Stationen auf vollem Band gearbeitet) — Phase 2 macht das mode-genau + sichtbar.
2. **Phase 2** (eigener Workflow): mode-genauer Index `(Call,Band,Mode)` (SUBMODE
   sonst MODE, Leerfall nie in Index); NEUE-Filter band+mode-genau; Auto-Hunt
   nutzt's + entprellte „alle gearbeitet"-Meldung. Spec in TODO.md.
3. Push-Freigabe Mike (P168 v0.98.56 + P169 v0.98.57 lokal).

---

## Session 02.06.2026 — P168 FT4-Timing (v0.98.56, voller Workflow)

**Mike-Field (2 QSOs, ms-Log):** FT4 doppelt so langsam — unsere TX 30s statt
15s auseinander. FT4 = Zeitspar-Modus → 30s vergrault Stationen. **Root Cause:**
Decoder weckt FT4 0,5s vor Slot-Ende (absolut 14,5s) → Decode ~0,24s nach
Boundary fertig → zu spät für Audio-Start des Folge-Slots (Boundary−0,8,
FlexRadio-1,3s-Buffer) → Encoder-Drift-Guard springt +2 Slots → 30s. Decoder
weckt also STRUKTURELL nach der Sende-Frist; das Decode-Fenster hing an der
Weckzeit (`audio_12k[-slot_samples:]`).

**⚠️ 1. Versuch verworfen:** nur WAKE 0,5→1,5 → Empfang tot (0 Decodes, Field-
Crash Mike), `dt_corrections.json FT4_20m` auf −0,5 vergiftet (bereinigt auf
+0,246). Grund: früheres Wecken verschob das gekoppelte Fenster → Signal aus dem
ft8_lib-Sync-Fenster. **Lehre: Weckzeit ≠ Fenster-Position ≠ DT.**

**Echter Fix (`core/decoder.py`):** 3 Größen entkoppelt — `_WAKE_OFFSETS["FT4"]`=1,5
(früh wecken) · neuer `_WINDOW_OFFSETS` (Fenster slot-ausgerichtet [Slot−0,5;+7,0]
via `_keep_window`, Tail-Pad 1,0s NACH preprocess) · `_DT_OFFSETS` aus WINDOW
abgeleitet → FT4-DT konstant 1,0. FT8/FT2 bit-identisch (tail=0). DeepSeek
Plan-R1 (Gold: Pad nach preprocess) + Final-R1 PUSH FREIGEBEN; Paritäts-
Halluzination (/15) gegen encoder.py geprüft + verworfen. Tests 2290→2303 (+13,
inkl. FT4-Positionierungs-Äquivalenz + FT8-Decode-Rundlauf). Kein TX-Eingriff.

**Field-Test BESTANDEN (02.06. 10:25 UTC):** FT4-QSO mit SV5AZK, unsere TX exakt
15s-Takt (10:25:22→:37→:52→26:07→:22), Empfang voll (6 Stationen, −25 dB ok,
DT≈0). 30s-Bug weg, Empfang heil.
**Nächste Schritte:** Push-Freigabe Mike → `git push` (2 lokale Commits: b4e78b7
Code + efac8cb Doku; v0.98.53–55 bereits gepusht).

---

## Session 02.06.2026 — P167 Einschub-Reentrancy (v0.98.55, voller Workflow)

**Mike-Field (Log v0.98.51):** P164-Einschub (IN3BFW im QSO-Fenster geklickt)
rief die Station nach dem laufenden QSO nur EINMAL, dann Stillstand (kein Retry,
Auto-Hunt-Pause blieb). **Root Cause:** `_p158_maybe_start_inserted_call` lief
synchron in `qso_timeout.emit`/`qso_confirmed.emit`; `start_qso` setzte TX_CALL,
aber der Handler rief danach `_resume_cq_if_needed()` → `_set_state(IDLE)`,
überschrieb TX_CALL. **Fix:** Einschub in nächsten Event-Tick defern
(`_deferred_insert_msg` + `QTimer.singleShot(0, _execute_deferred_insert)`);
HALT nullt den Merker (Race-Schutz). DeepSeek Diagnose-R1 + Final-R1 PUSH
FREIGEBEN. Tests 2286→2290 (+4). Kein TX-Eingriff, ANT1/ANT2 unberührt.

**Nächste Schritte:** Field-Test (Einschub während Auto-Hunt: ruft jetzt
wiederholt + Auto-Hunt nimmt nach dem Einschub-QSO wieder auf?) · Push-Freigabe
(offene Commits: P167 + Sortier-Fix + Diplome + P166 + Vorgänger).

---

## Session 02.06.2026 — Logbuch-Sortier-Fix (v0.98.54, voller Workflow)

**Mike-Field (Screenshot):** „Datum"-Header-Klick sortierte „02.06.26" als Text
→ 01.06./02.06. über 12.05./13.05. (Tageszahl dominiert). Fix `ui/logbook_widget.py`:
`_SortableItem` sortiert nach `_SORT_ROLE`-Schlüssel — Datum `QSO_DATE+TIME_ON`
(chronologisch), km numerisch. km gleich mitgefixt.
**Claude-Catch (Test):** DeepSeek-Plan-Fallback `super().__lt__` = PySide6
RecursionError → `self.text() < other.text()`. Final-R1 PUSH FREIGEBEN 0
Beanstandungen. Tests 2278→2286 (+8). Reine UI-Sortierung, kein TX.

**Nächste Schritte:** Field-Test (Datum-Header klicken → neuestes oben?) ·
Push-Freigabe (offene Commits: Sortier-Fix + Diplome + P166 + P165 + Vorgänger).

---

## Session 02.06.2026 — Diplome-Erweiterung (v0.98.53, voller Workflow)

**Mike-Wunsch:** DARC- + weitere internationale Diplome ins Diplome-Feature
(war DXCC/WAC/WAS/WAZ) + einzelne Diplome ein-/ausblendbar. Mike-Wahl:
WAE + WPX + DXCC-Band-Tiefe, Auge-Symbol pro Karte + Klappbereich.

**Machbarkeit zuerst geprüft:** DLD nicht möglich (DOK fehlt in FT8-QSOs),
IOTA nicht möglich („N/A"). WAE/WPX/DXCC-Band aus vorhandenen Feldern ableitbar.

**Umgesetzt:**
- `core/awards.py`: WAE (CONT==EU, Ziel 70, ehrlicher Näherungs-Tooltip), WPX
  (`wpx_prefix()`, Ziel 300, alle 3 Slash-Formen gegen 25 echte Calls validiert),
  DXCC-Challenge (Entity-Band-Slots, HF 160-6m, Ziel 1000) + 5-Band-DXCC-Status.
- `core/awards_prefs.py` **neu**: Sichtbarkeits-Persistenz (eigene JSON, kein
  Settings-Durchreichen — DeepSeek-🟠).
- `ui/awards_dialog.py`: 👁-Toggle pro Karte, Klappbereich, DXCC-Erweiterungen.
  Signatur unverändert (kein Bruch).
- `tests/test_awards_expansion.py` **neu** (+23): WPX-Parser, WAE, Challenge,
  5BD, awards_prefs round-trip, GUI-Smoke (Dialog bauen/toggle/persist).

**Claude-Catch:** DeepSeek-WPX-Skizze `digit_parts[0]` falsch (`OE/DL6CGU→DL6`)
→ korrekt „kürzerer Teil = Standort-Präfix" (`OE0`). Final-R1 PUSH FREIGEBEN 0
Blocker, 1🟡 Leerzeichen-Härtung übernommen. Hardware: kein TX, ANT1/ANT2 unberührt.

**Logbuch-Stand (18329 QSOs):** WAE 63/70, WPX 1516, WAS 49/50 (1 fehlt!),
WAZ 38/40, Challenge 562/1000, 5BD: 15m ✓ Rest offen.

**Nächste Schritte:** Field-Test (Dialog öffnen, Diplome prüfen, Auge-Toggle) ·
lokal committen · Push-Freigabe (offene Commits: P166 + P165 + Diagramme +
Vorgänger + Diplome-Erweiterung).

---

## Session 02.06.2026 — RX-Doppelklick Hard-Stop (v0.98.52, voller Workflow)

**Mike-Field:** Doppelklick in der RX-Liste während Auto-Hunt rief die Station,
ließ Auto-Hunt aber weiterlaufen. Mike-Spec: bewusste Übernahme → ALLES
unterbrechen (CQ/QSO/Auto-Hunt), sofort rufen, kein Resume.
**Umsetzung:** `_on_station_clicked(msg, hard_stop=True)` + Stop-Block GANZ OBEN
(`stop_auto_hunt("manual_halt")` + P164-Merker verwerfen) — deckt alle Pfade ab.
P164-QSO-Fenster-Klick bleibt sanft (`hard_stop=False`, beide Pfade: mw_cycle
IDLE-Sofort + mw_qso Einschub). **Claude-Catch:** DeepSeek-R1-🟠 `cancel()`
verworfen (start_qso resettet schon, qso_state:297-330, P1.14). DeepSeek Final-R1
**PUSH FREIGEBEN** 0 Blocker/Findings. Hardware: TX bleibt ANT1. Tests +10
(`test_p166_*`); 5 P158-Tests auf hard_stop=False angepasst. FEATURES §17.

**Nächste Schritte:** Field-Test (Doppelklick stoppt Auto-Hunt jetzt sichtbar?)
· Push-Freigabe (Commits offen: P166 + P165 + Diagramme + Vorgänger).

---

## Session 02.06.2026 — Auto-Hunt DX-Scoring (v0.98.51, voller Workflow)

**Mike-Wunsch:** Auto-Hunt soll seltene/weite/neue DX-Perlen bevorzugen statt
lauter Europa-Nachbarn (Falkland −24 dB wurde nie gerufen). **Umgesetzt:**
- `_init_qso_log` lädt `adif/_backup_qrz_export/` (18k QSOs) → echte Historie
  (0,47 s) + `set_my_grid(settings.locator)`.
- `log/qso_log.py`: Länder-Zähler `_country_count` + `_country_band`, API
  `get_country_count` / `is_country_worked_on_band`.
- `core/auto_hunt.py`: `_score` → `_compute_priority` (Tupel `(R, band_new,
  -dist, -snr, slot)`, kleiner=höher), `country_rarity_class` (0 ATNO..4),
  `_MIN_SNR=-21` → `SNR_FLOOR=-26`, Slot=letzter Tiebreaker, Vorfilter
  „gearbeitete Station skippen", `_RARITY_UNKNOWN=2`.
- Rangfolge verifiziert: Falkland > San Marino(nah!) > Japan > USA > DL.
- DeepSeek Final-R1 **PUSH FREIGEBEN**, 0 Blocker. Hardware: TX bleibt ANT1.
- Tests +12 (`test_p165_dx_scoring.py`); angepasst test_modules/auto_hunt_
  extended/p61/p139. Prompts als Audit-Trail in `prompts/auto_hunt_scoring_*.md`.

**Nächste Schritte:** Field-Test am Radio (ruft Auto-Hunt jetzt sichtbar die
weiten/seltenen Perlen statt Europa?) · Push-Freigabe (Commits offen: P165 +
Vorgänger Doku-Wartung/Bug1/3/Bug2-Doku/Diplome/P164/P162-Revert).

**Bekanntes Restrisiko (Phase 2, TODO):** Sonderpräfixe wie FT5 (Kerguelen)
werden in der Präfix-Tabelle als Mutterland (Frankreich) geführt → fälschlich
als „häufig" eingestuft. Normale DX (Falkland/Peru/Japan/Korea…) korrekt.

---

## Session 01.06.2026 (Teil 2) — Bug 1/2/3 aus Mike-Field-Test

**Bug 1 ✅ (voller Workflow):** QSO-Log Anchor-Format blutete auf Folgezeilen
(eigene „→ Gesendet"-TX wurden klickbare Links). Fix in `ui/qso_panel.py`:
`_append_colored`/`_append_two_color` setzen ein frisches `QTextCharFormat` statt
nur `setTextColor`. DeepSeek-R1 Root-Cause ✓ — sein Ein-Zeilen-Fix reichte aber
NICHT (`setTextCursor(End)` lädt das Anchor-Format neu), kritisch geprüft +
Test-First. Final-R1 ✅. 5 Tests (`tests/test_bug1_anchor_bleed.py`). 2228→2233.
**Bug 3 ✅ (trivial):** redundanter „Maus bewegen…"-Hinweis aus 3 Meldungen
(`ui/main_window.py`: Auto-Hunt-5-Min ×2 + CQ-Presence-Totmann) entfernt.
**Bug 2 ⚪ GESCHLOSSEN-ohne-Fix:** sehr selten zwei IDENTISCHE „← Empf."-Zeilen,
gleiche Sekunde (Erst-Diagnose „RX+TX gleiche Zeit" war FALSCH — Mike korrigiert:
beide „← Empf."). Voller DeepSeek-Workflow: Decoder dedupliziert intern, 1 Decode/
Slot, nur ANT1 dekodiert (ANT2 = Diversity-Messung), 1 Signal-Verbindung →
seltene Race, statisch nicht lokalisierbar. DeepSeek-Catch: `on_message_received`
läuft theoretisch doppelt → NICHT nur Anzeige. ABER verifiziert harmlos:
P1.7-Duplikat-Filter (`mw_qso.py:601-610`) schützt das Logbuch, keine Doppel-
Sendung (Screenshot 1× ✓). Mike-Entscheidung KISS: nicht fixen (Risiko > Nutzen).
Fallback-Plan + Diagnose → TODO.md.

**Nächste Schritte:** Field-Test am Radio (Diplome-Dialog + Bug-1-Fix
sichtprüfen) · Push-Freigabe (Commits offen: Doku-Wartung + Bug1/3 + Bug2-Doku +
Diplome + P164 + P162-Revert).

---

## Session 01.06.2026 — Doku-Wartung (Commit d994687, NICHT gepusht)

Reine Infrastruktur, **kein App-Code** — Tests unberührt.
- **CLAUDE.md entschlackt** 73k→38k (unter 40k-Warnschwelle): Versions-Inline-Block
  + P-Code-Verträge nach HISTORY.md/FEATURES.md ausgelagert; DeepSeek-/Workflow-/
  Hardware-Regeln unverändert.
- **HISTORY.md rotiert** 804k→79k: nur noch letzte 30 Versionen (v0.98.20–v0.98.49),
  ältere 203 Einträge in `history/HISTORY_archiv_01.md`. **Neue Einträge ab jetzt
  OBEN anhängen** (Datei absteigend sortiert).
- **`tools/rotate_history.py`** NEU — rotiert HISTORY.md mit Byte-Verifikation +
  Backup (Dry-Run-Default, `--apply`; bei >40 Einträgen laufen lassen).
- Start-Lese-Last (CLAUDE.md + HISTORY.md) ~876k→117k.
- zshrc: `claude2`-Alias entfernt.
- Backups (löschbar nach App-Start-Check): `/tmp/CLAUDE.md.bak-vor-trim-20260531`
  + `HISTORY.md.bak-2026-06-01` (untracked im Projektordner).

---

## Letzte Session (31.05.2026)

### Diplome-Feature (NEU, v0.98.49) — voller DeepSeek-Workflow

Mike-Auftrag: DXCC-Label im Logbuch-Tab durch Button **„Diplome"** ersetzen →
Dialog mit Übersicht der 4 Diplome (gearbeitet + per LoTW bestätigt), mit
Staffelung wo offiziell vorhanden. DO4MHH (Mikes altes Klasse-E-Call) zählt mit.

**Umgesetzt:**
- `core/awards.py` (NEU): `compute_awards(records)` → pro Diplom worked+confirmed
  Sets. DXCC (Entity-Nr, Ziel 100), WAC (6 Kontinente, AN ausgeschlossen), WAS
  (50 US-States via `US_STATES`-frozenset, AK/HI drin), WAZ (40 CQ-Zonen).
  Bestätigt = NUR `LOTW_QSL_RCVD=Y`. `dxcc_tier_status()` für ARRL-Marken
  100/150/200/250/300/Honor Roll. Beide Calls = ein Pool (set-dedup).
- `ui/awards_dialog.py` (NEU): read-only Dialog, dunkles Theme, pro Diplom Karte
  + Fortschrittsbalken + „🏅 erreicht"-Badge; DXCC mit Marken-Zeile.
  Datenquellen-Hinweis (QRZ-Export DA1MHH & DO4MHH).
- `ui/logbook_widget.py` (Edit): `dxcc_label` → `btn_awards` „Diplome";
  `_on_awards_clicked` lädt `adif/_backup_qrz_export` **on-demand** dazu;
  `_update_counters` ohne dxcc_label; Import AwardsDialog.
- `tests/test_awards.py` (NEU): 16 Tests (distinct-Zählung, LoTW-Filter,
  US-State-Validierung, AN-Ausschluss, CQ-Zonen-Range, DXCC-Staffelung, robust).

**Datenquelle:** Diplome werten den QRZ-Export (`adif/_backup_qrz_export/`,
18.329 QSOs DA1MHH+DO4MHH) on-demand beim Dialog-Öffnen aus — die reichen Felder
(DXCC/CONT/STATE/CQZ/LOTW) stecken nur dort. Frische SimpleFT8-QSOs zählen erst
nach erneutem QRZ-Export mit (dokumentiert im Dialog-Hinweis).

**Staffelung (DeepSeek R1b Option A):** Nur DXCC hat eine echte numerische
ARRL-Leiter → die wird gezeigt. WAC/WAS/WAZ sind „alles-oder-nichts" → Fortschritt
+ Badge, KEINE erfundenen Bronze/Silber/Gold (Ehrlichkeit > Gamification).

**DeepSeek-Workflow:** V1→V2→Design-R1 (GO, 6 Auflagen — alle umgesetzt:
try/except DXCC, WAC ohne AN, LoTW-only, US-State-Filter, Button+on-demand,
Datenquellen-Hinweis) + R1b (Staffelung Option A). **Final-R1 (Bestätigungs-Pass)
konnte wegen Session-Tooling-Instabilität nicht eingelesen werden** — die
DeepSeek-Läufe lieferten nach ~8 Aufrufen keinen lesbaren Output mehr. Design-R1
hatte die exakten Code-Pfade aber bereits geprüft; alle Auflagen sind im Code
verifiziert + 16 Unit-Tests + 0 Regressionen. **Explizites Final-R1 vor Push
nachholen.**

**Tests:** Volle Suite **2228 passed, 0 Regression** (18.33s). 16 neue Award-Tests.

---

## ⛔ OFFEN (Stand 01.06.2026 — git-verifiziert, alter Block war veraltet)

✅ **Final-R1 (PUSH FREIGEBEN) + Commit erledigt** — `2cce619` (Code) + `1bfb292`
   (Final-R1 eingelesen, FEATURES §19). Tests 2228 grün. Diplome-Feature ist
   code- + review-seitig FERTIG.

Nur noch zwei Dinge, beide auf Mike-Seite:
1. **Push-Freigabe** — 6 Commits warten (`origin/main..HEAD`): d994687 Doku-Wartung,
   1bfb292 + 2cce619 Diplome, 725cedc + 9034884 P164, cd91712 P162-Revert.
2. **Praxistest Diplome-Dialog** (kein Radio nötig — liest nur QRZ-Export):
   Optik + reale Zahlen prüfen (DA1MHH+DO4MHH als ein Pool).

Optional (kein Blocker): redundanter Fallback-Pfad im Diplome-Code aufräumen → TODO.md.

## TODO (Mike-Wunsch, zurückgestellt)
- **„neue"-Filter + Auto-Hunt mit voller QRZ-Historie füttern:** den
  `_backup_qrz_export`-Ordner zusätzlich in `QSOLog` (`log/qso_log.py`,
  Worked-Before-Set) laden, damit NEUE-Filter + Auto-Hunt die echte 18k-Historie
  kennen (aktuell nur die paar hundert SimpleFT8-eigenen QSOs). Eigener
  Workflow. → in TODO.md.

---

## ⚠ Tooling-Warnung (diese Session durchgehend)
Bash-stdout-Display + /tmp-Scratch-Reads zeitweise leer; DeepSeek-Läufe ab
~8 Aufrufen ohne lesbaren Output; lange Befehle auto-backgrounden. **Write/Edit
+ pytest persistierten zuverlässig** (Code real geschrieben, Suite real grün).
Verifikation NUR über pytest-Returncode + grep-in-Datei, nicht der Anzeige
trauen. Lesson: Bash(write)+Read(file) NICHT im selben Message-Block (Race) —
getrennte Messages.
