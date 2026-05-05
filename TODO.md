# SimpleFT8 TODO — Stand 28.04.2026 (v0.73)

---

## ⭐ ALS NÄCHSTES (Priorität)

### ✅ P1.5 — CQ-Reply-Recognition-Bug (ERLEDIGT 2026-05-05, v0.95.2)

5-Min-Sperre `_WORKED_BLOCK_SECS = 300` an 3 Block-Stellen entfernt.
Voller V1→V2→R1→V3 Diagnose + Plan, R1 zwei Mal bestaetigt ohne
Halluzinationen. Tests 756 → 759 gruen. Atomarer Commit `43dd062`.
Field-Test ausstehend (Mike). Siehe `HISTORY.md` v0.95.2.

---

### 🟢 P1.6 — Versionsnummer-Anzeige fehlt (2026-05-05)

Mike sieht `SimpleFT8 v0.95(.1)` unten rechts im Control-Panel nicht mehr.
Code ist unveraendert (`ui/control_panel.py:1086`). Vermutlich Layout-
Glitch, evtl. durch Display-2-Setup oder Resize abgeschnitten.

**Trivial-Diagnose:** Resize-Test, evtl. Layout-Anchoring pruefen.

---

### 🟢 P1.7 — Lokaler Duplikat-Filter ADIF/Logbuch (2026-05-05)

**Hintergrund:** P1.5-Fix entfernt 5-Min-Sperre nach QSO. Bekannte Stationen
duerfen wieder anrufen (Mike's Funker-Entscheidung-Philosophie). Aber:
wenn dieselbe Station < 5 Min nach RR73 nochmal anruft (z.B. ihr 73 ist
nicht angekommen), wuerde ein zweites QSO entstehen → zweiter ADIF-Eintrag
+ zweiter qso_log-Eintrag.

**QRZ.com filtert serverseitig** (Duplikat-Check Call+Band+Mode+Date+Time
liefert `RESULT=FAIL REASON=duplicate` zurueck, im Code in
`ui/mw_qso.py:386-392` als `dup` gezaehlt). Aber **lokal sind die Eintraege
trotzdem da**.

**Aufgabe:**
- Duplikat-Check in `log/adif.py` vor `log_qso()`-Schreiben.
- Logik: gleicher Call + gleiches Band + gleicher Modus binnen 60 Min
  → entweder updaten (latest wins) oder skip + Info-Log.
- UI-Hinweis im QSO-Panel ("Doppel-QSO mit X erkannt — uebersprungen").
- `qso_log.add_qso` analog absichern.

**Trivial-Mittel:** ~1 Tag Aufwand. Kein eigener Workflow — KISS.

---

### ✅ ERLEDIGT P1 — v0.95 + v0.95.1 QSO-Panel Slot-Tag/Zeit-Display-Fix (2026-05-05)

7 atomare Commits (``dac4a73``..``5d4b767``). Decoder als single source
of truth fuer Slot-Quelle. Tests 742 → 756 gruen. Voller V1→V2→R1→V3-
Workflow zweimal. Field-Test offen (siehe HANDOFF.md).

Original-Beschreibung (zur Doku):

### 🔴 P1 (war offen) — QSO-Panel Slot-Tag/Zeit-Display falsch (2026-05-05)

**Symptom Field-Test 03:38-:40 UTC:** RX und TX erscheinen mit identischem
Slot-Tag `[E]` und Zeit, obwohl FT8 das physikalisch ausschliesst. QSO mit
DA1TST/R6OK/PY7ZZ liefen real korrekt (IC-7300 DT 0.0-0.1 s) — reine
Anzeige-Anomalie. RX-Eintraege haengen 1 Slot hinterher und vergeben das
EVEN-Tag des Folge-Slots statt das ODD-Tag des TX-Slots der Nachricht.

**Root Cause (R1-bestaetigt + Log-verifiziert):**
- `ui/qso_panel.py:147-177` `_slot_tag()` + `add_rx()` nutzen
  `time.time()` zum Decoder-Output-Zeitpunkt
- Decoder-Output kommt 1 Slot zu spaet weil Audio-Buffer-Lag (FlexRadio
  VITA-49). Decode selbst <0.2 s, aber `Zu wenig Audio: X < 90000` im Log
  → Skip, Decode dann erst im Folge-Slot
- `time.time()` zur Decode-Output-Zeit liegt damit im Folge-Slot

**Loesung Option A (R1-Empfehlung, von uns erweitert):**
- Decoder ermittelt `slot_start_ts` aus Wake-Zeit und setzt es als
  Attribut auf jede Message (sichere Quelle, unabhaengig von GUI-Lag)
- `_assign_slot_parity` nutzt Decoder-gesetzten Wert statt
  `is_even_cycle()` zur Aufruf-Zeit
- `add_rx`/`add_tx` bekommen `tx_even` + `slot_start_ts` durchgereicht

**Dokumente:**
- V1: `prompts/qso_panel_slot_display_v1.md`
- V2: `prompts/qso_panel_slot_display_v2.md`
- R1: `prompts/qso_panel_slot_display_r1.md`
- V3: noch zu schreiben → Mike-Freigabe vor Code

**Stats-Risiko:** R1-bewertet < 0.1 % falsche Slots am Stundenrand,
symmetrisch verteilt → kein Bias in Pooled-Mean. **Historische Daten
nicht korrigieren.**

---

### 🟡 P2 — Reply-Lag durch Audio-Buffer-Latenz (2026-05-05)

**Beobachtung Field-Test:** Bei R6OK-QSO antwortet DA1MHH mit Report erst
:45:30 statt :45:00 (1 Slot zu spaet). Folge: R6OK haelt Mike's Antwort
fuer ausgeblieben und sendet seinen CQ-Reply :45:15 ODD nochmal — wirkt
fuer Mike wie „doppelte Antwort".

**Vermutete Wurzel:** Selbe wie P1 — Audio-Buffer-Lag bei FlexRadio
VITA-49. Decoder-Output kommt 1 Slot zu spaet → State-Machine-Reaktion
+ TX-Pipeline-Trigger landen im uebernaechsten Slot statt im naechsten.

**Wichtig:** Erst nach P1-Fix angreifen — das korrekte Slot-Display
zeigt erst dann zuverlaessig wieviel Lag wirklich da ist und ob die
Hypothese „selbe Wurzel" stimmt. Vielleicht reduziert sich der Reply-
Lag bereits auf < 1 Slot wenn die Anzeige stimmt.

**Mogliche Eingriffe (sofern nach P1 noch noetig):**
- Wake-Offset im Decoder vergroessern (aktuell `_WAKE = SLOT - 1.5s`,
  evtl. SLOT - 2.5s) — gibt Audio-Buffer mehr Zeit voll zu werden
- VITA-49 Jitterbuffer-Konfiguration im FlexRadio-Connector pruefen
- Audio-Pre-Fetch / Buffer-Pacing untersuchen

**Risiko hoch** — Hardware-naher Eingriff, eigener Workflow nach P1.

---

### ✅ ERLEDIGT — v0.90 Mess-Pattern-Bug-Fix (2026-05-04)

`core/diversity.py:86` auf fair 3:3 (``("A1","A1","A2","A2","A1","A2")``)
korrigiert — Option C aus V3. 3 atomare Commits, Tests 664 gruen.
Voller Workflow V1→V2→R1→V3 mit 2 R1-KRITISCH-Findings (End-to-End-Test,
Bandwechsel-Race-Hinweis behalten). Siehe HISTORY.md v0.90-Eintrag und
``prompts/v090_v3.md`` fuer Details.

**Statistik-Disclaimer:** Alle Pre-v0.90 Diversity-Daten haben strukturellen
Mess-Bias 4:2. Pooled-Mean +88 %/+124 % bleibt valide; absolute ANT2-Win-Rate
war konservativ unterschaetzt. Field-Test-Erwartung: ANT2-Win-Rate steigt
von ~4 % auf ~15-25 % auf 40 m FT8.

---

### ✅ ERLEDIGT — v0.92 Lock-Audit (2026-05-04)

Atomarer Commit `9b9303d` + Doku-Sync. R1-Audit-Findings adressiert.

**5 Edits in `ui/mw_radio.py`:**
1. `_set_gain_measure_lock` — setzt `self._gain_measure_locked` Flag
2. `_on_band_changed` — Frueh-Return wenn Flag aktiv
3. `_on_mode_changed` — gleiches
4. `_on_rx_mode_changed` — gleiches (R1-NEU-Finding!)
5. `_enable_diversity` — Lock VOR `_diversity_ctrl.reset()`

**Tests +6** in `tests/test_lock_coverage.py` (NEU): 675 → 681 gruen.

**R1-Halluzinationen verworfen:** btn_rx-Schutz (kein btn_rx im Code),
Bandpilot-Pending (KISS-Argument).

**Bandwechsel-Race aus v0.90 R1-Verdacht final geloest.**

**Diskussions-Trail:** `prompts/lock_audit_v1.md`, `_v2.md`, `_r1.md`, `_v3.md`
**Memory:** `project_lock_audit_pending.md`

---

### 🟢 v0.93 Cache-Reuse + Mess-Refactor — Plan steht, Implementation pending (2026-05-04)

**Status:** Voller V1→V2→R1→V3-Workflow + Folge-R1 zur FT2-Statistik.
Mike's Vision konsequent durchziehen mit R1's 4 Modifikationen.
Reihenfolge: NACH v0.92 Lock-Audit.

**Mike's Vision (R1-bestaetigt):**
1. **1 h Auto-Refresh** statt 15 Min Zyklen-Counter (atmosphärisch korrekt)
2. **Cache-Reuse pro Band+Modus** bei Bandwechsel (5-s-Toast, kein Klick)
3. **Normal-Modus raus** aus Cache-System („Normal ist normal")
4. **OPERATE_CYCLES Konstante weg** + Settings-Option `diversity_operate_cycles` weg
5. **`_MULT` für OPERATE_CYCLES weg** (zeit-basiert obsolet)
6. **Pattern fair 3:3 bleibt** unverändert (v0.90)

**R1's 4 KRITISCHE Modifikationen:**
- **Mod 1:** `_MULT` für MEASURE_CYCLES BEHALTEN (FT8=6, FT4=12, FT2=24)
  — FT2 in 6 Zyklen × 3.8 s = 23 s waere zu kurz fuer Statistik
- **Mod 2:** PresetStore zwei Timestamps (`gain_timestamp` 6h + `ratio_timestamp` 1h)
- **Mod 3:** CQ-Lock zusätzlich zu QSO-Lock in `should_remeasure()`
- **Mod 4 (KILLER):** `score` (= sum(snr+30)) statt `station_count` speichern
  — adressiert Mike's FT2-Sorge (1-2 Stationen pro Slot → diskrete Werte
  {0,1,2} → keine Auflösung). Mit Score: kontinuierliche Werte, Median
  statistisch robust auch bei dünner Dichte. **Eine Zeile umstellen**
  (`record_measurement` Z.381) — Score wird schon übergeben, nur ignoriert.

**R1's Bonus-Modifikationen:**
- **Mod 5:** `MIN_MEASURE_STATIONS = 5` ENTFERNEN (`can_measure()` immer True)
  — bei FT2 oft Block-Trigger, mit Score-Umstellung obsolet
- **Mod 6 (optional):** `scoring_mode` vereinheitlichen — DX-Modus obsolet
  weil SNR-Score eh feiner als `dx_weak_count`. Kann später separat.

**Code-Stellen:**
```
core/diversity.py:27       OPERATE_CYCLES = 60          → ENTFERNEN
core/diversity.py:29       MIN_MEASURE_STATIONS = 5     → ENTFERNEN
core/diversity.py:374-385  record_measurement           → score statt station_count
core/diversity.py:421-453  _evaluate                    → peak-Schwelle anpassen (5.0)
core/diversity.py:461      should_remeasure(qso_active) → +cq_active
core/preset_store.py:19    VALIDITY_SECONDS = 6*3600    → splitten in gain/ratio
core/preset_store.py:99    is_valid()                   → ratio/gain unterscheiden
core/preset_store.py:139   save_ratio()                 → ratio_timestamp setzen
ui/main_window.py:822      OPERATE_CYCLES aus Settings  → ENTFERNEN
ui/mw_radio.py:821-824     _MULT für OPERATE_CYCLES    → ENTFERNEN (MEASURE_CYCLES bleibt)
ui/mw_radio.py:_on_band_changed   → Cache-Check VOR _diversity_ctrl.on_band_change()
ui/mw_cycle.py:220        save_ratio() bereits da, _was_early_stopped-Schutz aus v0.91 #8
```

**Aufwand:** ~4.5 h (V3 + Code + Tests + Doku-Sync v0.93).

**Trigger nach Compact:** „Refactor starten" oder „v0.93 starten" oder
„Score zuerst" (nur Mod 4 als Quick-Win).

**Diskussions-Trail:**
- V1: `prompts/cache_reuse_refactor_v1.md`
- V2: `prompts/cache_reuse_refactor_v2.md` (7 Self-Review-Findings)
- R1: `prompts/cache_reuse_refactor_r1.md` (Mike-Vision + 3 Mods)
- Dichte-V1: `prompts/cache_reuse_dichte_problem.md` (FT2-Statistik-Problem)
- Dichte-R1: `prompts/cache_reuse_dichte_r1.md` (Score-Insight!)

**Memory:** `project_diversity_cache_reuse.md`

**Was BLEIBT unveraendert:**
- Phase 2 Gain-Messung (separate 6 h Validity)
- Phase 3 fair 3:3 Pattern (v0.90)
- v0.91 Adaptiv-Stops (Phase 2 + Phase 3)
- v0.91 Cache-Schutz (`_was_early_stopped`)
- Manueller „NEU"-Button

---

### ✅ GELÖST durch v0.93-Refactor — OPERATE_CYCLES wird komplett entfernt

Aufgenommen in den Cache-Reuse + Mess-Refactor-Plan (siehe oben).
Mike's Vision: 1 h Auto-Refresh atmosphärisch korrekt, OPERATE_CYCLES
und `_MULT`-Skalierung weg, Settings-Option weg. R1-bestaetigt.

Wird mit v0.93 erledigt — Trigger „Refactor starten" / „v0.93 starten".

---

### 🆕 Radio-Erreichbarkeits-Check beim App-Start (2026-05-04, Mike)

**Problem:** Wenn das FlexRadio aus ist, startet die App still und versucht
nur via Reconnect-Loop alle 60 s neu zu verbinden. User merkt das erst nach
einer Weile (Log-Eintrag `[Radio] FlexRadio Verbindung fehlgeschlagen: timed
out` + `[FlexRadio] Reconnect #N in 60s ...`).

**Gewuenschtes Verhalten:**
- Beim App-Start einmal pruefen ob konfiguriertes Radio erreichbar ist
  (TCP-Connect zur Radio-IP/Port mit kurzem Timeout, z. B. 2-3 s).
- Falls nicht erreichbar: nicht-modalen Dialog/Toast oben anzeigen
  („FlexRadio nicht erreichbar — Radio einschalten und auf Verbindung
  warten" o. ä.). Nicht blockierend (App soll weiterlaufen, Reconnect
  weiterversuchen).
- Bei spaeterem Erfolg-Verbinden den Hinweis automatisch verschwinden lassen.

**Code-Stellen (V1-Skizze, R1 in eigenem Workflow):**
- `radio/flexradio.py` — neue Methode `is_reachable(timeout=2.0)` die einen
  TCP-Connect-Test macht ohne Login.
- `ui/main_window.py` `_init_radio()` oder direkt nach Settings-Load —
  Reachability-Check + Toast.
- Toast-Klasse evtl. wiederverwendbar (z. B. aehnlich `BandpilotAutoToast`
  aber persistent bis Verbinden klappt).

**Aufwand:** ~30-60 min Code + Workflow V1→V3.
**Status:** OPEN — eigener V1→V3-Zyklus nach Block-2-Erfolg.

---

### ✅ ERLEDIGT — Block 2 Kalibrier-Pipeline-Optimierung (v0.91, 2026-05-04)

Pipeline ~4:31 Min (v0.89/v0.90) → typisch ~3:20 Min, Best-Case ~2:30 Min.

**3 atomare Commits:**
- `eef4369` ROUNDS 3→2 (#6, -60 s, Schedule 12→8 Eintraege)
- `3068919` Adaptiv-Stop Phase 2 nach Runde 1 (#7, -30 bis -60 s,
  Δ_SNR≥4 dB ODER Δ_STAT≥50 %, +6 Tests)
- `f090097` Adaptiv-Stop Phase 3 nach 4 Zyklen + Cache-Schutz
  (#8, -30 s, EARLY_STOP_THRESHOLD=0.15, Cache-Schutz R1.4 KRITISCH, +5 Tests)

**Voller V1→V2→R1→V3-Workflow durchgezogen.** R1-Findings adressiert:
Cache-Schutz, Monitoring-Log mit Timestamp, FT4/FT2-Doku, Cancel-Flag dokumentiert.

**Tests:** 664 → 675 gruen.

**Schwellen konservativ tuned (R1-bestaetigt):** Field-Test liefert
Daten fuer evtl. Senken auf 12 % (R1-Empfehlung). Monitoring-Log mit
ISO-Timestamp eingebaut.

**FT4/FT2-Hinweis:** Pattern-Periode 6 verhindert balancierte Verteilung
bei MEASURE_CYCLES=12/24, Pre-Condition len-equal verhindert Stop —
effektiv profitiert nur FT8 (Hobby-Use 99 % FT8, R1-akzeptiert).

**Status:** ERLEDIGT. Field-Test Block 1+2 wartet auf Mike.

---

### 🆕 Reiter „Geraet" in Settings — Sauberer Remote-Shutdown + Auto-Start (03.05.2026)

**Hintergrund (Web-Recherche 2026-05-03):**
- KEIN offizieller SmartSDR-API-Befehl fuer Power-On/Off (FlexRadio
  Staff bestaetigt, Daemon "In Review" seit Dez 2019, nicht umgesetzt).
- KEIN offizieller SSH-Zugang zum Linux des Radios.
- **Saubere Linux-Shutdown-Methode = REM ON Jack Open-Circuit.** Das
  ist KEIN AC-Cut, sondern ein Soft-Trigger an die Radio-CPU
  (~15-20s sauberer Shutdown, dann safe).
- Empfohlene Hardware: **Shelly 1 / Shelly Plus 1** (~15€,
  ESP-basiert, lokale HTTP-API ohne Cloud-Zwang) als IP-Relais
  am REM ON Jack.

**Mike's offene Frage:** welche Hardware (Shelly schon vorhanden?
neu kaufen? andere Marke?). RCA-Adapter mit Drahtenden zu
Relais-Kontakten — fertig kaufen oder loeten?

**Geplanter Tab „Geraet" (nach Mike-Entscheidung Hardware):**

```
Tab "Geraet":
- Sauber herunterfahren (Shelly Relais am REM ON):
  - Shelly-IP + Auth-Token (optional)
  - "Verbindung testen"-Button
  - "Radio sauber herunterfahren"-Button
    -> Stoppt TX, schliesst Decoder, oeffnet REM ON via HTTP,
       wartet 20s auf Linux-Shutdown
- Auto-Start nach Stromausfall:
  - Hardware-Setting im Shelly: "Restore last state" oder
    "Always on" -> Relais bei Stromrueckkehr "zu" -> REM ON
    shorted -> Radio bootet automatisch
  - "Setup-Anleitung oeffnen"-Button
```

**Aufwand-Schaetzung (nach V1->V2->R1->V3-Workflow):**
- core/shelly_client.py: HTTP-Client mit Auth, ~80-120 Zeilen
- ui/settings_dialog.py: neuer Tab "Geraet", ~80 Zeilen
- core/safe_shutdown.py: TX-Stop + Decoder-Close + Shelly-
  Trigger + 20s-Warten, ~60 Zeilen
- tests/test_shelly_client.py: HTTP-Mock, ~60 Zeilen
- docs/explained/remote-shutdown_de.md + .md: Setup-Anleitung
  + Hardware-Skizze
- Hardware-Setup (Mike): Shelly konfigurieren, RCA-Adapter
  loeten oder Adapter-Kit, im Settings IP eintragen
- Gesamt: ~3-4h Code + Hardware-Beschaffung Mike

**Status: WAITING fuer Mike's Hardware-Entscheidung.**

---

**Mike's offene Map-UI-Punkte aus v0.68-Field-Test — ALLE ERLEDIGT:**
- ✅ Punkt 3 (Zeit-Dropdown) — erledigt v0.68
- ✅ Punkt 4 (Band-Dropdown) — erledigt v0.68
- ✅ Punkt 5 (Sektor-Rotation) — erledigt v0.68 + Folgekorrektur
- ✅ Punkt 1 (Propagations-Balken Pulsieren) — erledigt v0.69
- ✅ Punkt 6 (Stations-Count Tooltip "37 / 46 Stationen") — erledigt v0.70
- ✅ Punkt 2 (PSK-Reporter Reichweiten-Sektoren TX) — erledigt v0.71

**v0.73 Release-Bilanz (28.04.2026):**
- 💾 **Persistenter RX-History-Cache:** pro (band, mode) 60 Min Empfangs-
  daten in `~/.simpleft8/cache/rx_history/{band}_{mode}.json`. Karte zeigt
  beim Open + Bandwechsel sofort die letzte Stunde — auch nach App-Restart.
- 🧹 **Karten-UI-Aufraeumung:** Time-Window-Combo + Band-Combo raus
  (waren tote/halbtote UI-Deko). simpleFT8-Style: Karte zeigt aktives
  Band, 60 Min hardcoded.
- 🧪 6 atomare Commits, 430 → 442 Tests gruen, V1→V2→V3 mit DeepSeek-
  Reviewer (5 echte Findings uebernommen, 4 verworfen).

**v0.72 Release-Bilanz (28.04.2026):**
- 🎨 **Karten-Theme-Toggle (Aurora / Dark):** QComboBox in DirectionMapDialog,
  Aurora bleibt Default. Dark-Mode = schwarzes Land + mittel-graues BG +
  flacher Disk + dezent graue Coastlines (Mike-Inspiration aus QSO-Landkarte
  mit VP8FLY/ZL4AS-Verbindungen).
- 💾 Settings-Key `direction_map_theme` persistiert ueber App-Restarts.
- 🛡️ DeepSeek-Findings (4): AK harmonisiert, Aliase belassen, disk_fill statt
  Skip, QComboBox statt Toggle-Button, Commits 2→3 aufgeteilt.
- 🧪 4 neue Tests, 426 → 430 gruen.

**v0.71 Release-Bilanz (27.04.2026):**
- 🌍 **TX-Reichweiten-Sektoren:** Karten-TX-Modus zeigt Sektor-Wedge-Laenge
  jetzt nach max-Distanz pro Sektor statt Cluster-Dichte. VK6-Spot (16000 km)
  erzeugt langen Wedge, dichter Iberien-Cluster bleibt bescheiden.
- 🛡️ NaN/Inf-Guard in `SectorBucket.max_distance_km` — DeepSeek-Review hat
  echten Edge-Case gefunden (NaN propagiert sonst durch paintEvent).
- 🧪 4 neue Tests, 422 → 426 gruen.

**v0.70 Release-Bilanz (27.04.2026):**
- 🐛 **Kritischer Bugfix:** `is_grid` Property-Aufruf mit Klammern → seit v0.67
  silent TypeError, Live-Locator-Feed komplett tot. **Jetzt aktiv** — DB
  waechst live mit jedem CQ/Antwort.
- 💾 Auto-Save LocatorDB alle 5 Min — kein Datenverlust bei Hard-Kill
- 🪟 Ant-Spalte 'A1' im Normal-Modus
- 🔍 Stations-Count Tooltip auf Karte
- 📊 LocatorDB-Stand: **7.991 Calls** aus DA1MHH+DO4MHH-ADIF (854 KB JSON)

**Naechstes Feature:**
- 🔜 **Settings-Dialog auf Tabs umstellen** (28.04.2026) — aktuell 6 GroupBoxes
  vertikal gestapelt (Station/TX/RF-Presets/FT8/Export/Karte), Hoehe ~900-1000 px,
  passt nicht auf Mike's 1440×900 Display. Plan: 3 Tabs (Station / TX / FT8)
  mit max 500-600 px pro Tab. Aufwand 1-2 h. *Nach Bug-Fix Diversity-
  Bandwechsel.*

**Andere offene TODOs:** siehe Liste unten.

**ENTFALLEN — Feature B (PSK-Reporter Band-Indikatoren) gestrichen:**
Bei der V1→V2-Workflow-Diskussion am 27.04. mit Mike kam raus, dass das
gesuchte „pulsierende Bandoeffnungs/-schliessungs"-Feature bereits in
**v0.69** vollstaendig implementiert ist:
- Saison-Fenster pro Band+Saison in `core/propagation.py:_SEASONAL_SCHEDULE`
- Lookahead 60 Min via `get_conditions_at(60)`
- Pulsation NUR fuer aktives Band, andere statisch
- Cross-Fade Ist-Farbe ↔ Trend-Farbe

PSK-Reporter Live-Daten sind dafuer **nicht noetig**. Wenn HamQSL-Daten
ungenau wirken: Saison-Fenster in `_SEASONAL_SCHEDULE` justieren (rein
Werte-Aenderung, kein Code).

**Field-Test BESTANDEN ✅ (28.04.2026, Mike):**
- ✅ **v0.69-Pulsation auf 40m sichtbar** — Mike hat den Bandwechsel-
  Pulse beim Wechsel auf 40m im Feld bestaetigt. Feature funktioniert
  wie spezifiziert.
- ✅ **v0.72 Dark-Mode auf Karte** — „erdkugel map sieht geil aus
  funktioniert auch super" (Mike-Original-Quote). Theme-Toggle +
  Persistenz live verifiziert.

**Pulsations-Zeiten Spring (April-Mai), Berlin-Zeit UTC+2 (Referenz):**
  | Band | Oeffnen | Schliessen |
  |------|---------|------------|
  | 10m  | 10-11 MESZ | 18-19 MESZ |
  | 12m  | 09-10 MESZ | 19-20 MESZ |
  | 15m  | 08-09 MESZ | 21-22 MESZ |
  | 17m  | 07-08 MESZ | 22-23 MESZ |
  | 20m  | 06-07 MESZ | 23-00 MESZ |
  | 30m  | 04-05 MESZ | 00-01 MESZ |
  | 40m  | 16-17 MESZ | 09-10 MESZ |
  | 80m  | 18-19 MESZ | 08-09 MESZ |
  Caveat: Pulse triggert nur wenn HamQSL fuer dieses Band innerhalb-
  Fenster „good" oder „fair" liefert (sonst poor↔poor = kein Wechsel
  sichtbar).

**Field-Test offen:**
- ✅ **v0.67 Locator-DB Praezisionstest:** sichtbar in der Karte — 50/53
  Stationen mit Position nach Restart, Ø Genauigkeit 74 km. JSON
  persistiert. Erfolgreich.
- **v0.69 Pulsier-Animation:** subjektiv-Test bei Tageszeit-Uebergang
  (z.B. 16-17 UTC fuer 40m winter close): fuehlt sich der Cross-Fade
  beruhigend an? Falls zu auffaellig: `fade=2000`/`hold=4000` in
  `_start_pulse` (`ui/control_panel.py:_ModeBandCard._start_pulse`).
- **v0.70 Live-Locator-Feed:** ueber laengere Empfangs-Session
  beobachten ob die DB sichtbar waechst. Erwartung: pro Stunde 5-15
  neue Calls mit prec_km=5 (CQ-Calls + Antworten mit Grid).
- **v0.71 TX-Reichweiten-Pattern:** Karte → SENDEN-Modus an einer
  guten 40m-Abend-Session. Erwartung: dunkler-orange Iberien-Wedge
  (kurze Distanz, viele Stationen), leuchtend-gelber USA-Wedge (lange
  Distanz, weniger Spots). Falls TX-Sektoren bei wenigen Spots zu
  unruhig wirken: Min-Floor (z.B. 20% max_wedge_r) erwaegen.

---

## 🔬 Antennen-Diversity Daten-Sammlung (Prio NIEDRIG, Stand 27.04.2026)

**Stand der Erkenntnis (n=2 Baender):**
- 40m FT8 (off-band fuer ANT1 Kelemen Trap-Dipol): Diversity Standard
  +88 %, Diversity DX +124 % vs Normal. Robuste Datenbasis (~22.700 Zyklen).
- 20m FT8 (resonant ANT1): Diversity Standard −23 %, Diversity DX −33 %.
  Daten noch duenn (~3.000-3.600 Zyklen je Modus, schiefe Stunden).

**Mike-These:** „Auf resonanter ANT1 verliert Diversity, off-band gewinnt
sie." DeepSeek-Bedenken (gerechtfertigt):
- Pol-Diversity bei HF-Skywave ist durch Faraday-Rotation eh randomisiert
  → vert/horz-Argument schwaecher als gedacht
- Regenrinne 15 m hat band-abhaengige Pattern (1.4 λ auf 20m vs 2.1 λ auf
  15m) — koennte ANT2-Performance pro Band stark verschieben
- Wetter (nasse Rinne) verschiebt Wirkungsgrad um 1-2 dB → schwer zu
  isolieren ohne Wetter-Tracking

**Test-Roadmap (kein Zeitdruck — Daten sammeln wenn Mike sowieso funkt):**

| Band | ANT1-Status | Erwartung | Prio | Daten-Soll |
|---|---|---|---|---|
| **17m FT8** | off-band | Diversity gewinnt (wie 40m) | hoch | 3+ Tage, 06–22 UTC |
| **15m FT8** | **resonant** | Diversity verliert (wie 20m) — kritischer Test | hoch | 3+ Tage, 08–18 UTC |
| **12m FT8** | off-band | Diversity gewinnt | mittel | 2+ Tage |
| **80m FT8** | off-band | Diversity gewinnt | mittel | 2+ Tage Nacht |
| **10m FT8** | resonant | nur bei Bandoeffnung — Spo-E saisonal | niedrig | gelegentlich |

Wichtig: **Statistik-Filter v0.63 prueft nur 20m/40m FT8.** Fuer die anderen
Baender muss Mike entscheiden ob das geaendert wird (Filter erweitern auf
{17m, 15m, 12m, 80m, 10m}) oder ob die Daten als CSV-Export reichen.
→ **TODO bei Beginn der 17m-Phase:** Stats-Filter erweitern.

**Entscheidungs-Punkt nach 5 Baendern:**
Wenn die Heuristik „off-band gewinnt, resonant verliert" sich
bestaetigt → kleinen Info-Tooltip an Diversity-Aktivierung
(neutral formuliert, kein Verhaltenseingriff). Wenn nicht → gar nichts
implementieren, App bleibt neutral.

DeepSeek-Empfehlung dokumentiert: **Tooltip-Text wenn implementiert wird:**
> „Der Diversity-Vorteil haengt stark von deiner Antennen-Kombination,
> Band, Wetter und Tageszeit ab. Am besten testest du selbst pro Band,
> ob es dir hilft."

---

## NEXT FEATURES — Plan vom 26.04.2026 (Brainstorming Mike + Claude + DeepSeek)

Reihenfolge nach Priorität. Quick-Wins zuerst, USP-Killer-Features parallel als Strategie.

---

### A0) Locator-DB persistent (v0.67) — ✅ **ERLEDIGT 27.04.2026**

Persistenter Locator-Cache aus CQ/PSK/ADIF mit Source-Priority. 6 atomare
Commits, 28 Tests, DeepSeek-codereviewed. Karte und rx_panel ziehen aus
der DB. Save bei App-Close (atomar). Siehe HISTORY.md v0.67.

---

### A) Aging in Slots statt Sekunden (Bug-Fix) — ✅ **ERLEDIGT v0.64 (26.04.2026)**

Umgesetzt mit Werten 7/14/20 (DeepSeek-Korrektur, 5/10/20 waere auf FT4 zu aggressiv).

---

### A-OLD-DOC) Aging Original-Plan (zur Doku)

**Problem:** `core/station_accumulator.py` nutzt Aging in Sekunden:
- 75s normal / 150s active_qso / 300s CQ-Rufer
- FT8 (15s/Slot) → 5/10/20 Slots ✓
- FT4 (7.5s) → 10/20/40 Slots ✓
- FT2 (3.8s) → **20/40/79 Slots** ❌ deutlich zu lang!

**Fix:** Aging in SLOTS umrechnen. Konstanten:
```python
AGING_SLOTS_NORMAL    = 5   # 5 Slots = 75s FT8 / 37.5s FT4 / 19s FT2
AGING_SLOTS_ACTIVE    = 10
AGING_SLOTS_CQ_CALLER = 20
```
Bei jedem Decode-Cycle aktuelle Slot-Nummer einfließen lassen statt timestamp.

**Test:** Es gibt bereits Aging-Tests — anpassen (Slot-Counter statt time.time).

---

### B) Band-Indikatoren live mit PSK-Reporter ergänzen — ✅ **GESTRICHEN 27.04.2026** (v0.69 deckt Use-Case bereits ab)

> Mike's eigentlicher Wunsch (pulsierende Bandoeffnungs-/Schliessungs-
> Indikatoren am aktiven Band) ist bereits in v0.69 vollstaendig
> implementiert via `core/propagation.py:_SEASONAL_SCHEDULE` + Lookahead
> 60 Min. Live-PSK-Daten sind dafuer **nicht noetig**. Bei ungenauen
> HamQSL-Werten: Saison-Fenster in `_SEASONAL_SCHEDULE` justieren.
> Original-Plan unten zur Doku, NICHT umsetzen.

**[Original-Plan zur Doku] Foundation ist mit v0.66 schon da:** `core/psk_reporter.py` (XML-Polling, Cache,
Backoff, Threading) ist wiederverwendbar. Brauchen nur eine zweite Query-Variante
mit `mode=FT8&lastMinutes=5` (ohne senderCallsign-Filter) für Aktivitaets-
Aggregat pro Band — das passt in eine erweiterte `PSKReporterClient.fetch_activity()`-
Methode.

**Status quo:** Bestehende kleine Balken UNTER den Band-Buttons (rot/gelb/grün)
basieren nur auf HamQSL Solar Flux + Tageszeit + saisonale Korrektur (`core/propagation.py`).

**Neu:** PSK-Reporter Live-Aktivität dazu:
- Zeigt nicht nur "theoretisch sollte das offen sein" sondern "weltweit X Stationen GERADE aktiv, Trend ↗/↘"

**API (verifiziert mit DeepSeek):**
- Endpoint: `https://pskreporter.info/cgi-bin/psk-find.pl?mode=FT8&lastMinutes=5&callback=json`
- 1 Request liefert ALLE Bänder → Client-seitig pro Band aggregieren
- Polling: alle 2 Min (safe, JTAlert/GridTracker machen es genauso)
- Pro Spot: `senderCallsign`, `band`, `timestamp`, `receiverLocator`, `snr`

**Trend-Erkennung:**
- 2-Fenster-Approach: `last_5_min` vs `prev_5_min` (unique Calls)
- Ratio > 1.15 → "rising" (Band öffnet)
- Ratio < 0.85 → "falling" (Band macht zu)

**Visualisierung — neu (Mike's Idee):**
- Bestehende Farb-Balken bleiben (HamQSL-Berechnung)
- Bei steigendem Trend → **pulsierender Balken**, je näher zur "Öffnung" desto schneller
- `QPropertyAnimation` auf eigenes `QWidget.paintEvent` (kein setStyleSheet wegen Performance)
- Speed: 300-2000ms Cycle, mit Trend-Stärke skaliert

**Code-Skeleton aus DeepSeek:**
```python
# core/psk_reporter.py — neu
class PSKReporterClient:
    POLL_S = 120
    URL = "https://pskreporter.info/cgi-bin/psk-find.pl"
    
    def fetch_global_activity(self, mode="FT8", minutes=5):
        # JSONP parsen, Spots pro Band aggregieren
        ...
    
    def get_band_trend(self, band): ...  # rising/falling/stable
    def get_band_count(self, band): ...  # aktuelle unique Calls
```

```python
# ui/band_indicator.py — neu
class BandIndicatorWidget(QWidget):
    pulse_factor = Property(float, ...)
    def set_trend(self, strength: float): ...  # -1.0 bis +1.0
    def paintEvent(self, e): ...  # Alpha-pulsierende Farbe
```

---

### C) Richtungs-Keulen-Karte — TX-Pattern — ✅ **ERLEDIGT v0.66 (26.04.2026)**

Umgesetzt als Variante (b) **Weltkarte mit Sektor-Overlay** (Azimuthal-Equidistant-
Projektion mit JO31 als Center, 16 Sektoren à 22.5°, Coastlines aus Natural Earth
110m). TX-Modus nutzt PSK-Reporter Reverse-Lookup (`senderCallsign=...&mode=FT8`).
SNR-Skala dunkles Orange → Hellgelb. Aufruf via Settings → "Karte oeffnen ..."

Architektur in 10 atomaren Commits (siehe HISTORY.md v0.66):
- `core/geo.py` erweitert (Bearing, Projektion, safe_locator)
- `core/psk_reporter.py` (Polling, Cache, Backoff, Call-Normalisierung)
- `core/direction_pattern.py` (Sektor-Aggregation, Mobile-Filter)
- `core/antenna_pref.py` Thread-Safe (RLock + snapshot)
- `assets/ne_110m_land_antimeridian_split.geojson` (116 KB, 5143 Punkte)
- `tools/build_coastlines.py` (Pure-Python, kein shapely-Dev-Dep)
- `ui/direction_map_widget.py` (MapCanvas + DirectionMapDialog)
- Hook in `mw_cycle._handle_diversity_operate` + `_handle_normal_mode`
- Cross-Thread-Signal `direction_map_signal` mit Qt.QueuedConnection

+141 Tests (220 → 361). Alle Module DeepSeek-codereviewed.

---

### C-OLD-DOC) TX-Pattern-Karte Original-Plan (zur Doku)

**Idee Mike:** Statt PSK-Reporter Punkte/Kreise zu zeigen → Stationen nach **Großkreis-Richtung gruppieren in 16 Sektoren** (à 22.5°). Jeder Sektor wird zu einer **Keule**.

**Was du daraus lernst:**
- "Heute Süd-Ausbreitung dominiert — 25 Stationen, max 8000 km"
- "Nichts nach W → 10m sinnlos"
- "Skip-Zone heute bei 1500-3000km in Sektor 4"

**Datenquelle: PSK-Reporter Reverse-Lookup**
- Endpoint: `?callsign=DA1MHH&mode=FT8&lastMinutes=60` → wer hat MICH gehört
- Pro Spot: `receiverLocator` + `snr`
- Sub-Minute Latenz (5-30s typisch)

**Algorithmus:**
1. Maidenhead-Locator → Lat/Lon (Standard-Formel)
2. Großkreis-Azimut von JO31 → empfänger-Lat/Lon
3. Sektor-Bin: `int(bearing / 22.5) % 16`
4. Pro Sektor: Anzahl Empfänger, Ø SNR, max Entfernung

**Rendering (Optionen, Mike entscheidet):**
- (a) **Polar-Diagramm** (Rosenkreis): kompakt, sauber
- (b) **Weltkarte mit Sektor-Overlay**: Keulen vom Zentrum (Herne) als gefüllte Kegel
- (c) **Hybrid**: Karte mit Punkten + Polar-Histogramm in der Ecke
- Empfehlung: **(b) — visuell stärkster Effekt**, QPainter-basiert

**Bonus: TX-Pattern zeigt was ANT1 (Sender) leistet** — durch Resonanz zeigt die TX-Keule auch die optimal genutzten Lobes des Kelemen-Dipols.

---

### D) Richtungs-Keulen — ANT2 RX-Pattern — ✅ **ERLEDIGT v0.66 (26.04.2026)**

Als EMPFANG-Modus im selben Karten-Widget umgesetzt. Live-Daten kommen
aus `mw_cycle` (Diversity + Normal). Antenna-Farbcode pro Station:
- Blau `#4488FF` = nur ANT1
- Cyan-Grün `#00CCAA` = ANT2 dominiert
- Leuchtgrün `#44FF44` = Rescue (snr_a1 ≤ -24 UND snr_a2 > -24)

Sektor-Wedges mischen Antennen-Farben gewichtet. LocatorCache merkt sich
Locator pro Call ueber die Session (FT8 hat Locator nur in CQ-Nachrichten).

---

### D-OLD-DOC) RX-Pattern Original-Plan (zur Doku)

**Idee Mike:** Für ANT2 KEINE PSK-Reporter-Daten (wir senden nicht über ANT2!) sondern **lokale Rescue-Daten** visualisieren.

**Was zeigen:**
- Wo hört ANT2 was ANT1 NICHT hört? (= Rescue: ANT1 < -24 dB, ANT2 dekodiert)
- Diese Stationen pro Sektor zählen → Keule

**Datenquelle (lokal!):**
- `core/antenna_pref.py` hat bereits `_snr_a1` / `_snr_a2` pro Call
- `statistics/Diversity_*/{band}/FT8/stations/*.md` hat Rescue-Spots historisch
- Filter: `a1_snr <= -24 AND a2_snr > -24`

**Rendering:**
- Gleiches Sektor-Diagramm wie C, aber mit ANT2-Farbe (kontrastierend zu TX-Pattern)
- Idealerweise im **selben Diagramm** überlagert: ANT1-TX-Keule + ANT2-RX-Rescue-Keule
- Zeigt sofort: "ANT1 strahlt nach SO, aber ANT2 fängt Norden ab"

**Algorithmus-Code-Skeleton (DeepSeek):**
```python
# core/rx_pattern.py — neu
class RXPatternAnalyzer:
    SECTORS = 16
    
    def update_from_rescue_spots(self, decoded_stations):
        for s in decoded_stations:
            if not s.locator: continue
            bearing = grid_bearing(MY_GRID, s.locator)
            sector = int(bearing / (360 / self.SECTORS)) % self.SECTORS
            if s.snr_ant1 <= -24 and s.snr_ant2 > -24:
                self.sectors[sector]["rescue"] += 1
```

---

### E) CSV-Export Diversity-Daten — ✅ **ERLEDIGT v0.65 (26.04.2026)**

Umgesetzt: Standalone-Script `scripts/export_diversity_csv.py` PLUS UI-Integration
im Settings-Dialog mit QFileDialog → Verzeichnis-Wahl. 4 CSVs, 675 Datensaetze.

---

### E-OLD-DOC) CSV-Export Original-Plan (zur Doku)

**Idee:** Pro QSO eine CSV-Zeile mit allen Diversity-Metadaten:
```
callsign, mode, band, timestamp_utc, freq_hz, ant1_snr, ant2_snr, 
selected_ant, delta_db, dt_correction, qso_complete
```

**Use Cases:**
- Wissenschaftliche Auswertung (Paper über 79-86% ANT2-Win-Rate trotz resonanter ANT1!)
- Externe Visualisierungs-Tools (Excel, Tableau, Pandas)
- Antennen-Optimierungs-Hinweise sammeln

**Implementierung:**
- Erweitern: `core/station_stats.py` um `export_diversity_csv(path, band, mode, days)`
- Menüpunkt im UI: "Datei → Diversity-Daten exportieren..."
- Default-Pfad: `~/Documents/SimpleFT8_Export/diversity_{band}_{date}.csv`

**ADIF-Vendor-Extension VERWERFEN** (DeepSeek-Vorschlag): andere Tools wie HRD/DXLab ignorieren das eh. Reines CSV reicht.

---

### F) Audio-Export per Slot (für Forschung/Debug) — **<1 Tag**

**Idee:** Roh-IQ pro Slot (4 sec PCM WAV) optional mitschneiden.

**Use Cases:**
- AP-Lite Feldtest: "warum hat AP-Lite die Station verpasst?" → Audio nachhören
- Antennen-Vergleich: Slot von ANT1 + Slot von ANT2 als WAV → Spektrum-Analyse offline
- Inspectrum / Audacity / Matlab Forschung

**Implementierung:**
- Toggle in Settings: "Roh-IQ-Audio mitschreiben (groß!)"
- Pfad: `audio_dump/{band}_{mode}/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav`
- 4 Sekunden Slot-Capture-Buffer im `radio/flexradio.py` ergänzen
- Ringpuffer mit max 7 Tagen (alte Files automatisch löschen)
- Alternativ: nur bei "interessanten" Decodes (Rescue, neuer DXCC, Mike's Wahl)

---

## ABHAENGIGKEITEN / REIHENFOLGE

```
A (Aging-Bug)              ✅ erledigt v0.64
B (PSK-Indikatoren)        ←  als nächstes — Foundation steht (psk_reporter.py)
C (TX-Pattern-Karte)       ✅ erledigt v0.66
D (RX-Pattern ANT2)        ✅ erledigt v0.66 (im selben Widget)
E (CSV-Export)             ✅ erledigt v0.65
F (Audio-Export)           ←  unabhängig, jederzeit
```

**Aktueller Stand 26.04.2026:** 4 von 6 Plan-Features umgesetzt. Verbleibend:
- **B** als Nächstes (1-2 Tage) — Live-Aktivitaets-Indikatoren unter den
  Band-Buttons. Foundation `core/psk_reporter.py` ist da.
- **F** als optionales Forschungs-Feature.

---

## NICHT WEITERVERFOLGT (verworfen am 26.04.2026)

- ❌ Smart CQ Prediction (DeepSeek): Daten zu dünn, würde False-Confidence erzeugen
- ❌ RX-Mute Anzeige während TX (DeepSeek): unnötig, FT8-Funker wissen das eh
- ❌ Cross-Band-Empfehlung "geh auf 40m": Architektur unterstützt nur 1 Band aktiv
- ❌ ADIF-Vendor-Extension: andere Tools ignorieren proprietäre Felder
- ❌ DT-Heatmap im Histogramm: für FT8 bei DT<2s nicht praxis-kritisch (zurückgestellt, evtl. später)
- ❌ Antennen-Pref Hysterese auf 2 dB anheben: nach Feldtest entscheiden, aktuell `>=` 1 dB OK
- ❌ Band-Aktivität Sparkline (15-min): Idee von DeepSeek, durch B+Pulsation faktisch schon ersetzt

---

## OFFENE TODO (alte Liste, weiter aktuell)

### Karten-Feature v0.66 — Folgemassnahmen
- [ ] **Migration `main_window._psk_worker` → `core/psk_reporter`** —
  bewusst zurueckgestellt im Karten-Sprint (out-of-scope-Markierung im Code).
  Beide Pfade nutzen jetzt parallel die XML-API. Konsolidierung sinnvoll
  bevor Feature B (Band-Indikatoren) das dritte Mal denselben Code braucht.
- [ ] **Karten-Live-Test im Feld** — App starten, RX-Modus auf 40m FT8 abends,
  prüfen: Coastlines korrekt orientiert? Punkte plausible Locator-Position?
  Antenna-Farbcode wechselt sichtbar zwischen Stationen?
- [ ] **TX-Modus Live-Test** — DA1MHH/CQ rufen, dann TX-Toggle, schauen ob
  PSK-Reporter Spots in 1-2 Min erscheinen.
- [ ] **Mobile-Filter-Edge-Case dokumentieren** — Region-Calls wie `K1ABC/W2`
  werden mit-gefiltert (regex `/[A-Z0-9]{1,4}$`). Bewusst akzeptiert, im
  Docstring vermerkt. Falls in Praxis ein Region-Call regelmaessig fehlt:
  Whitelist statt Regex.

### Andere offene TODOs
- [ ] Even/Odd dedizierter Timer — unabhängig vom Decoder-Thread (FT2 kritisch)
- [ ] Gain-Bias beheben — Normal-Modus Gain-Messung wenn Stats aktiv erzwingen
- [ ] CQ-Zusammenfassung RX-Liste — DeepSeek-Idee: ins QSO-Panel verschieben oder ganz raus
- [ ] Tertile-Analyse Statistik — kein Datencropping, alle Werte in 3 Drittel
- [ ] AP-Lite Test-Pipeline — synthetische E2E-Tests vor jedem Code-Fix
- [ ] Per-Station DT-Offset TX — encoder._station_dt_offset (nach mehr Feldtest-Daten)
- [ ] IC-7300 Fork — TARGET_TX_OFFSET dort separat messen!
- [ ] Warteliste-Screenshot — sobald DL3AQJ antwortet
- [ ] **NEU 26.04.:** TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker (Bug, noch nicht reproduzierbar)

---

## HEUTE ERLEDIGT (15.04.2026)

### Bugs gefixt
- [x] FT4 Einmessen: `CYCLE_SAMPLES_12K` → `self._slot_samples`
- [x] FT2 C-Library: `FTX_PROTOCOL_FT2` nativ (288 sps, kein Resample), Decodium-kompatibel bestaetigt
- [x] Diversity 50:50: Einzelmessungen, Median, 8% Schwelle, Standard/DX Modi
- [x] QSO komplett + Timeout: `WAIT_73` in Ausnahmeliste
- [x] RR73 Hoeflichkeit: max 2x wiederholen wenn Station weiter R-Report sendet
- [x] Detail-Overlay: schliesst bei Tab-Wechsel, Delete-Signal verbunden
- [x] DT-Korrektur bei Modus-Wechsel: Wert wird jetzt BEHALTEN (`keep_correction=True`)

### Neue Features
- [x] Diversity Standard/DX: Button zeigt "DIVERSITY DX", DX zaehlt schwache Stationen (SNR<-10)
- [x] Info-Dialoge: Gain-Messung + Diversity mit "Nicht mehr anzeigen"
- [x] CQ Sweet Spot: 800-2000 Hz statt gesamter Bereich
- [x] OMNI-TX: CQ-Button zeigt "OMNI CQ" wenn aktiviert
- [x] Even/Odd Spalte: "E"/"O" in RX-Liste
- [x] FT2 Frequenzen: DXZone Community-Frequenzen (40m=7.052, 20m=14.084, etc.)
- [x] RX-Filter automatisch: FT8/FT4=100-3100Hz, FT2=100-4000Hz beim Modus-Wechsel
- [x] Button "EINMESSEN" → "GAIN-MESSUNG"
- [x] DT-Korrektur beschleunigt: 2 Zyklen statt 4, 10 Betrieb statt 20, 70% Daempfung

---

## PRIO NIEDRIG — Doku/Test-Pipeline (Stand 2026-04-25)

> Mike-Entscheidung: „lassen wir so weil es super und robust schon seit Tagen läuft."
> Nur Doku korrigieren wenn ohnehin am GitHub gearbeitet wird; Test-Pipeline später,
> wenn AP-Lite real angefasst wird. Code bleibt unverändert.

### 1. Doku korrigieren: „UCB1 Bandit" ist im Code NICHT implementiert
**Betroffen:** `docs/DIVERSITY_DE.md`, `docs/DIVERSITY.md`, `README.md`, `README_DE.md` (alle GitHub-sichtbar!)

**Problem:** Doku verkauft die Diversity-Antennen-Wahl als „UCB1 (Upper Confidence Bound) Multi-Armed-Bandit". Tatsächlich implementiert `core/diversity.py::_evaluate()` jedoch **Median über 4 Messungen pro Antenne + 8 %-Schwellwert** (siehe Zeile 348-378). Kein Reward-Tracking, keine Confidence-Bound-Formel, kein kontinuierliches Lernen.

**Was tatsächlich passiert:**
- 8 Mess-Zyklen (4× A1, 4× A2)
- Median pro Antenne (robust gegen Ausreißer)
- `|s1-s2|/peak < 8%` → 50:50, sonst 70:30 zur besseren Antenne
- Nach 60 Operate-Zyklen → Neueinmessung

**Aufgabe:**
- DIVERSITY_DE.md / DIVERSITY.md: Abschnitt „UCB1 Adaptives Verhältnis" umschreiben → ehrlich „Median + 8 %-Schwellwert" benennen
- README.md / README_DE.md: gleiche Stellen prüfen + korrigieren
- UEBERGABE.md: Erwähnung „Temporal Polarization Diversity" bleibt (ist OK), nur Bandit-Sprache raus
- **Marke „Temporal Polarization Diversity" bleibt** — das Antennen-Wechsel-Konzept stimmt, nur die Bezeichnung der Entscheidungslogik ist Marketing-Quark

**Begründung Code lassen:** Aktuelle Logik läuft seit Tagen robust und stabil; UCB1 würde bei nur 2 Antennen + hoher Reward-Varianz (Fading) keinen spürbaren Vorteil bringen, aber Wartung erschweren.

**Tests:** Bereits ab v0.55 abgesichert — 7 neue Tests in `tests/test_modules.py` decken `_evaluate()` ab (Threshold-Verhalten, A1/A2-Dominanz, DX-Mode, Phase-Übergänge, Operate-Filter).

**Aufwand:** ~30 Min reine Doku-Arbeit, kein Code.

---

### 2. AP-Lite v2.2 Test-Pipeline bauen (vor jeglichem Code-Fix!)
**Betroffen:** `core/ap_lite.py`, `tests/test_modules.py` (neue Datei `tests/test_ap_lite_pipeline.py` denkbar)

**Problem:** AP-Lite ist live (`AP_LITE_ENABLED = True`) aber laut eigenem Docstring + CLAUDE.md komplett ungetestet. Im Code stehen drei explizite TODOs vom Autor:
1. `_build_costas_reference`: „Aktuell: vereinfachte Näherung" — kein echtes 7×3-Costas-Pattern mit FSK-Tönen
2. `align_buffers`: „Validieren! Insbesondere Phasenkorrektur für kohärente Addition" — Phase wird aktuell NICHT korrigiert; bei kohärenter Addition kritisch (sonst Auslöschung statt Verstärkung)
3. `SCORE_THRESHOLD = 0.75` — geraten, nie kalibriert
4. Zusatz-Verdacht: `encoder.generate_reference_wave()` muss echte FT8-Symbole produzieren — Stub-Verhalten würde Korrelation zu Müll machen

**Reihenfolge unverhandelbar:**
1. **ZUERST** synthetische End-to-End-Tests bauen — verrauschtes FT8-Signal generieren → 2 Slots erzeugen → durch `try_rescue` schicken → prüfen ob die richtige Nachricht rauskommt
2. Dann zeigen die Tests welcher der 4 Verdachtspunkte tatsächlich Bugs sind
3. Dann gezielt fixen mit Test als Schutznetz
4. Erst dann Feldtest

**Warum nicht direkt fixen:** Ohne Test ist jede „Verbesserung" Schuss ins Blaue — könnte einen funktionierenden Teil kaputt machen oder einen anderen Bug übersehen.

**Aufwand Pipeline:** ~1-2 h. Brauchen FT8-Signal-Generator (vermutlich über vorhandenen `Encoder.generate_reference_wave`), AWGN-Rauschen-Helfer, Test-Cases mit unterschiedlichen SNR-Bereichen.

**Aufgabe für nächste Session:** Test-Pipeline aufsetzen und als Baseline laufen lassen — dann sehen wir was wirklich kaputt ist.

---

## OFFEN — Naechste Schritte

### CQ-Frequenz-Algorithmus (core/diversity.py)
- [x] **Auswahllogik Score-basiert (v0.58):** `_score_gap()` ersetzt Median-Distance — Lückenbreite
  dominiert (1 Hz = 1 Punkt), Nachbarn ±1 Bin = 50 Hz Strafe pro Station, ±2 Bins halb so viel,
  Median-Distance nur als 0.01-Tiebreaker.
- [x] **Fester Sweet-Spot 800-2000 Hz (v0.58):** `SWEET_SPOT_MIN_HZ=800` / `MAX_HZ=2000` —
  TX-Frequenz nur noch im Sweet-Spot. Median wird nur über Sweet-Spot-Stationen berechnet.
- [x] **Modus-abhängige Dwell + Recalc (v0.58):** `set_mode()` setzt FT8=4z, FT4=8z, FT2=16z
  Dwell (~60 s einheitlich), Recalc = 5 × Dwell = ~300 s.
- [~] **Frequenzwechsel im Statistics-Modus sperren — VERWORFEN (Mike-Entscheidung 25.04.2026):**
  Variance, kein Bias. Wechsel mitteln sich über 22.000+ Zyklen raus, treffen alle Modi gleich.
  Sticky-Gap (50 Hz) + verfeinerte Kollision reduzieren Wechsel-Frequenz ausreichend.
- [x] **Kollisionserkennung verfeinert (v0.58):** `n_direct >= 2` ODER `n_in_band >= 3`
  (n_in_band inkl. current_bin). QSO-Schutz unverändert.
- [x] **Sticky Gap (v0.58):** Bleibt bei aktueller Frequenz wenn im Sweet-Spot, keine
  Kollisions-Schwelle erreicht und neue Lücke nicht > +50 Hz breiter. `_measure_gap_around()`
  refresht aktuelle Lück-Breite nach Sticky-Hit. `reset()` setzt `_current_gap_width_hz=0`.

### Propagation (core/propagation.py)
- [x] **60m Propagations-Balken:** Interpolation aus 40m+80m implementiert in
  `core/propagation.py::_fetch_raw()` (L181-190). Mittelwert per _CONDITION_ORDER-Index,
  day+night getrennt. (23.04.2026 erledigt)

### UI-Verbesserungen (SPAETER)
- [x] **Statusbar DT-Anzeige:** Zeigt `DT: —` / `DT: Korrektur` (grün) / `DT: Aktiv` —
  kein exakter Wert mehr. Implementiert in main_window.py::_update_statusbar() (Zeile 558-565).
- [x] **Statusbar Mode+Filter:** Zeigt `FT8 40m | 14074.000 kHz | Filter: 100-3100 Hz` —
  Filter-String pro Modus in _FILTERS dict. Implementiert in _update_statusbar() (Zeile 573-609).
- [ ] **Spalten-Konfig in Settings:** RX-Spalten ein/ausblendbar + gespeichert/geladen (Slot, Ant, DT, etc.)

### RX-Liste (UI)
- [x] **Sortierung UTC absteigend:** Bereits implementiert — `rx_panel.py:276` sorted insert mit absteigendem HHMMSS-Vergleich + `_set_sort("time", reverse=True)`. (2026-04-25 verifiziert)
- [ ] **CQ-Zusammenfassung ueberarbeiten:** Aktuell werden CQ-Rufe zu "CQ ×N" zusammengefasst — kaum sichtbar.
  Optionen (Mike entscheidet):
  (a) CQ-Rufe ins QSO-Panel verschieben: erste Zeile "CQ", ab 5× nur noch "CQ ×6" mit aktualisierter Zahl
  (b) CQ-Rufe komplett aus RX-Liste entfernen (sauberere Liste, weniger Ablenkung)
- [x] **Alte CQ-Rufe automatisch loeschen:** CQ-Rufer bekommen 300s Aging (5 Min) in
  `core/station_accumulator.py::remove_stale`, nicht-CQ bleibt bei 75s, active_qso bei 150s.
  Test: `test_accumulator_cq_longer_aging`. (23.04.2026 erledigt)

- [x] **Answer-Me Highlighting (DeepSeek-Idee):** Wenn eine Station unser Callsign in ihrer Nachricht
  sendet (z.B. "DA1MHH -07"), Zeile in der RX-Liste GELB hinterlegen. Verhindert dass wir ein QSO-Angebot
  uebersehen wenn gerade viel Traffic ist. Prio: hoch — direkter Nutzwert beim Pileup.
  (25.04.2026 erledigt — v0.57: Farbe `#5A4A10` Gold + Bold an 3 Stellen in `ui/rx_panel.py`)

### Statistik & Analyse (nach mehr Messdaten)
- [ ] **DIAGRAMM-AUSWERTUNG 20m — für GitHub (wenn genug Daten vorhanden):**
  Zwei Diagramme, Skripte fertig unter `tools/`:
  1. `tools/plot_20m_stations.py` — Stationsanzahl über Zeit: Normal / Div Standard / Div DX
     Aufruf: `./venv/bin/python3 tools/plot_20m_stations.py --date 2026-04-21`
  2. `tools/plot_ant2_performance.py` — ANT2 Performance stündlich:
     Oben: Ant2 Win-Rate % (wie oft ANT2 besser als ANT1)
     Unten: Ø ΔSNR gesamt + Ø ΔSNR wenn A2 gewinnt (in dB)
     Aufruf: `./venv/bin/python3 tools/plot_ant2_performance.py --band 20m --date 2026-04-21`
  **Wann ausführen:** Nach A/B-Test 20m (alle 10 Min Normal ↔ Div DX ab ~10:00 UTC).
  Mind. 3 Stunden Daten → dann Diagramme generieren + in STATISTICS.md oder README einbetten.
  Vorläufige Ergebnisse (2026-04-20, wenig Daten):
    Normal Ø 35.4 St. | Div Standard Ø 37.7 (+6%) | Div DX Ø 41.5 (+17%)
    ANT2 Win-Rate 20m: ~27-29% | 40m Nacht: 21-31% | Ø ΔSNR -0.29 dB (A1 leicht dominant)

- [ ] **ANT1 vs ANT2 SNR direkt loggen:** Pro Station beide SNR-Werte erfassen (ant1_snr, ant2_snr, delta).
  Aktuell: nur "Ant2 Wins" als Zaehler. Ziel: "ANT2 war im Schnitt +X dB besser bei Y% der Stationen".
- [ ] **Statistik-Diagramme fuer GitHub:** matplotlib-Script das aus statistics/*.md automatisch
  SVG/PNG-Charts generiert (Normal vs Diversity_Normal vs Diversity_Dx, pro Band + Uhrzeit).
  Einbetten in README oder eigene STATISTICS.md.
- [ ] **Auswertung per Tertile-Analyse — KEIN Datencropping (Entscheidung final):**
  Alle Messwerte behalten, in drei gleich grosse Drittel aufteilen, Normal vs Diversity pro Tertile
  separat vergleichen. Kein Wegwerfen von Extremwerten.
  - Unteres Drittel (33%): Schlechte Bedingungen — bringt Diversity ueberhaupt was?
  - Mittleres Drittel (33%): Alltagsbetrieb — typischer Gewinn im Normalbetrieb
  - Oberes Drittel (33%): Spitzentage / Sporadic-E — steigert Diversity noch weiter oder Saettigung?
  Begruendung: Gerade die oberen Messtage (DX-Oeffnungen) zeigen den groessten Diversity-Effekt.
  Die wegzuwerfen wuerde das erreichte Ergebnis beschneiden. Tertile behält ALLE Daten, basiert
  auf Raengen — bimodale Verteilung (Normal-Tage vs Sporadic-E) kein Problem.
  Implementierung: pandas.qcut(stations, q=3) → pro Label [low/medium/high] Mittelwert + Diff %.
  Script liest aus statistics/*.md, vergleicht Modi pro Tertile, gibt Tabelle aus.
- [ ] **WICHTIG — Gain-Bias beheben (faire Vergleiche!):** DX-Modus macht VOR dem Start IMMER
  automatisch eine Gain-Messung (optimierter Empfangspegel). Normal-Modus nur freiwillig.
  → DX startet systematisch mit besserem Gain → DX sieht im Vergleich kuenstlich besser aus.
  Fix: Wenn Statistik-Erfassung aktiv ist, Gain-Messung fuer ALLE Modi erzwingen (nicht nur DX).
  Wahrscheinlich nur ein Flag in der Gain-Logik — geringer Aufwand, grosser Effekt auf Fairness.

- [ ] **Gain-Bias Compensator (DeepSeek-Idee):** Parallel-Dekodierungen (beide Antennen hören gleiche
  Station) nutzen um systematischen SNR-Offset zwischen ANT1 und ANT2 zu messen. Über viele Stationen
  mitteln → Offset in dB speichern → bei Diversity-Auswahl-Schwelle abziehen. Macht Vergleich fair
  auch OHNE vorher beide Gain-Messungen abzugleichen. Komplex aber elegant — für spätere Phase.

### Bugs
- [ ] **VERMUTLICHER BUG — Freie TX-Frequenz im Normal-Modus (unregelmäßig):**
  Beobachtung (Mike, 2026-04-25): Im Normal-Modus wird die freie TX-Frequenz aus dem
  Histogramm manchmal NICHT gesetzt — kein Marker im Histogramm sichtbar, TX bleibt auf
  alter Frequenz. Im CQ-Modus funktioniert `get_free_cq_freq()` + Histogramm-Marker
  zuverlässig (`mw_qso.py:109–115`).
  Verdacht: Timing-Problem oder Überschneidung mit Band/Modus-Wechsel — noch nicht
  reproduzierbar. **Kein Code-Fix bis weiteres Auftreten dokumentiert ist.**
  Nächste Schritte: Konsolen-Ausgabe `[CQ] TX-Frequenz auf X Hz` beobachten, ob
  `get_free_cq_freq()` None zurückgibt oder der Wert gleich dem aktuellen ist.

- [x] **RX-Liste + QSO-Fenster nicht geleert bei Wechsel (BUG):**
  Jetzt gelöscht in: Band-Wechsel, Modus-Wechsel, Normal↔Diversity
  (_on_rx_mode_changed), _enable_diversity, _disable_diversity,
  RX ON/OFF (_on_rx_panel_toggled). (23.04.2026 erledigt)

- [ ] **Even/Odd Slot-Anzeige asynchron (FT2/FT4/FT8 pruefen):** Die Even/Odd-Anzeige oben im
  QSO-Fenster springt bei FT2 (3,75s Zyklen) moeglicherweise nicht exakt mit der echten Slot-Zeit um.
  Bei FT8 (15s) und FT4 (7,5s) ebenfalls verifizieren. Anzeige muss IMMER exakt der Slot-Zeit
  entsprechen, sonst ist sie wertlos.
  DeepSeek-Verdacht: Timing/Threading-Problem (nicht Logik-Fehler). FT2 hat kuerzestes Fenster
  (3,75s), daher dort am kritischsten. Loesung: eigenen dedizierten Timer fuer Slot-Anzeige,
  unabhaengig vom Decoder-Thread.
- [x] **Warteliste:** Queue akzeptiert jetzt Grid + Report (EA3FHP-Fix, v0.36)
- [x] **Logbuch-Loeschen:** Funktioniert (bestaetigt 15.04)
- [x] **km Fallback:** Callsign-Prefix Naeherung (~km) im Logbuch eingebaut (v0.37)

### Gain-Messung Scoring (UNTERSUCHEN)
- [ ] **Scoring-Logik pruefen:** Zeigt "optimal" Gain mit WENIGER Stationen als andere Gains.
  Aktuell: waehlt nach bestem Top-5 SNR. Aber Stationsanzahl wird daneben angezeigt → verwirrend.
  Optionen: (a) Scoring klar beschriften "Bester SNR", (b) Stationsanzahl statt SNR als Kriterium,
  (c) Kombination aus beiden, (d) Alle Zyklen-Durchschnitt pruefen (nur letzte Messung oder Schnitt?)
- [x] **Logging:** Jede Messung protokollieren fuer spaetere Analyse
  (25.04.2026 erledigt — v0.57: `_log_gain_result()` in `ui/mw_radio.py`, append-only `~/.simpleft8/gain_log.md`,
  loggt Normal-Kalibrierung + Diversity-Messung mit UTC + Band/Mode + ANT1/ANT2 Gains + Ø SNRs)

### Feldtest (NUR MIT RADIO)
- [ ] **FT2 Feldtest:** Ein bestätigtes QSO gefahren (Decodium-kompatibel bestaetigt). Ausführliches Testen auf 40m (7.052 MHz) / 20m (14.084 MHz) steht noch aus — DT-Korrektur, Timing-Randfahlle, laengere Sessions.
- [ ] **DT-Korrektur v2:** Konvergenz pruefen (soll jetzt 3-6 Min statt 12-18 Min dauern)
- [ ] **AP-Lite Threshold:** 0.75 kalibrieren → dann `AP_LITE_ENABLED = True`
- [ ] **OMNI-TX + Auto-Hunt:** Integriert (Easter Egg: Klick auf Versionsnummer). Feldtest ausstehend.
  GitHub: Darf als Feature "Optimierter CQ-Ruf (OMNI-TX)" erwaehnt werden, aber NICHT wie man es aktiviert.
  TODO: EN+DE README/Hilfe-Seite erstellen mit: Was ist OMNI-TX, wie funktioniert es (Even+Odd abwechselnd),
  was erwartet man (mehr Chancen gehoert zu werden), Einschraenkungen (Double-TX-Pausen).

### TX-Optimierungen — PRIO NIEDRIG
- [ ] **Per-Station DT-Offset beim QSO-Anruf (encoder._station_dt_offset):**
  Wenn Station X mit DT=+1.2s angerufen wird, die eigene TX um +1.2s verschieben →
  Signal landet im Zentrum ihres Decode-Fensters. Globale DT-Korrektur (ntp_time) bleibt
  unberührt. Nach QSO-Ende/Abbruch automatisch reset auf 0.0.
  Implementierung: `encoder._station_dt_offset = station.dt` beim Ansprechen,
  `encoder._station_dt_offset = 0.0` in qso_state auf IDLE/TIMEOUT.
  Kein Diversity-Feature — reine TX-Pfad-Optimierung.
  > Mike-Entscheidung 2026-04-25: PRIO NIEDRIG — erst nach mehr Feldtest-Daten.

### Langfristig
- [ ] IC-7300 Fork: `radio/ic7300.py` implementieren
- [ ] QSO-Resume bei App-Neustart

> "Band Map (visuelle Frequenz-Belegung)" gestrichen 2026-04-25 — das vorhandene
> Diversity-Histogramm mit TX-Cursor (control_panel) deckt den FT8-relevanten
> 100–1550 Hz-Bereich bereits ab. Ein separater Wasserfall über das gesamte Band
> ist für FT8 nicht nötig.
- [x] **RF-Power-Presets pro Band+Watt (lernendes System):** ERLEDIGT in v0.56 (2026-04-25)
  Implementierung: `core/rf_preset_store.py` mit Hybrid-Lade-Strategie (exakter Treffer →
  lineare Interpolation/Extrapolation → Default), atomic JSON-Write, Plausibilitäts-Warnung,
  Migration aus altem `rfpower_per_band`-Eintrag. Pro Radio (FlexRadio jetzt, IC-7300 später)
  separate Tabelle. UI: SettingsDialog-Section "RF-Presets" mit Tabelle + Reset-Buttons
  (disabled während aktivem TX). Selbstheilend: bei jedem Konvergenz-Übergang wird
  überschrieben. Tests 178 → 197 grün. Siehe HISTORY.md "v0.56".

---

## ERLEDIGTE FEATURES (Kurzform)

### 15.04.2026
- FT2 nativ + Decodium-kompatibel (Source Code verifiziert: NN=103, NSPS=288, 4-GFSK)
- FT2 QSO erfolgreich abgeschlossen (Empfang + Senden funktioniert)
- Diversity Standard/DX Modi + DX-Score (schwache Stationen <-10dB)
- QSO-Bugs: WAIT_73 Timeout, RR73 Hoeflichkeit (max 2x), Overlay
- DT-Korrektur v2: schneller, gedaempft, pro Modus gespeichert (~/.simpleft8/dt_corrections.json)
- RX-Filter automatisch pro Modus (FT8/FT4=3100Hz, FT2=4000Hz)
- CQ Frequenz Sweet Spot (800-2000 Hz)
- OMNI-TX CQ Button, Even/Odd Spalte RX + QSO-Panel [E]/[O]
- CQ-Zeilen zusammengefasst (CQ ×24 statt 24 Einzelzeilen)
- QSO-Panel Auto-Trim (max 40 Zeilen)
- Even/Odd Anzeige modus-abhaengig (nicht mehr hardcoded 15s)
- FT2 Frequenzen DXZone (40m=7.052, 20m=14.084)
- Info-Dialoge mit "Nicht mehr anzeigen"

### 14.04.2026
- FT4/FT2 Integration (Decoder, Encoder, Timing, UI)
- DT-Korrektur kumulative Strategie
- Presence Timer, Auto-Hunt, Diversity Fixes

### 13.04.2026
- Propagation-Balken (HamQSL), Radio-Abstraktion getestet
- AGC deaktiviert (kollidiert mit Noise-Floor-Norm)
- Drift-Kompensation entfernt (0 Nutzen)

### 12.04.2026
- Radio-Abstraktion komplett (v0.25-v0.28)
- main_window.py Split (1755→473 Zeilen, 4 Mixins)
- AP-Lite v2.2, OMNI-TX Hooks, DeepSeek Full Review
