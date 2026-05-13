# SimpleFT8 TODO — Stand 11.05.2026 (v0.97.1, P35 fertig)

> **Mike-Regel 07.05.2026:** Offene Aufgaben gehoeren AUSSCHLIESSLICH
> in diese Datei. Nicht in CLAUDE.md, nicht in HANDOFF.md. Diese Datei
> ist die einzige Quelle fuer Backlog/Bugs/Feature-Wuensche.

---

# 🟢 STATUS-ÜBERSICHT (für neue Session)

**Aktuelle Version:** v0.97.1 (11.05.2026)
**Tests:** 1129 grün
**App-Stand:** P35.DIVERSITY-STARTUP-FIX Code fertig, Field-Test 8 Punkte
pending. Push pending — v0.95.16 - v0.97.1 + P2-Tool + P3 + P21 + P26 +
P34 + P35 lokal gesammelt.

## ✅ 11.05.2026 erledigt (v0.97.1)

| Version | Was |
|---|---|
| **v0.97.1** | **P35.DIVERSITY-STARTUP-FIX** — 3 Bugs aus P34-Field-Test gefixt. **Bug A:** `_enable_diversity` bei radio.ip=None defer + Resume via `_check_diversity_preset`. **Bug B:** `_apply_dynamic_toggle` resettet Queue+current_ant unter Lock. **Bug B5:** Settings-Toggle überlebt Session (Auto-Reactivate). **AK5 R1-Q4 KRITISCH:** activate() respektiert Cache-Reuse-Ratio (70:30 bleibt). 5 atomare Commits. Tests 1116 → 1129 (+13). Plan-Files prompts/p35_diversity_startup_fix_v[1,2,3]+r1+final_r1.md. Field-Test V3 §6 F1-F8 pending. Push pending. |
| **v0.97.0** | **P34.DIVERSITY-DYNAMIC** — Antennen-Verhältnis live im Betrieb anpassen (statt 1× pro Stunde 90s-UI-Sperre). ENTWEDER-ODER zur Statik (Toggle in Settings, NICHT persistiert). Modul `core/dynamic_diversity.py` NEU + 2 Helper-Funktionen in `core/diversity.py`. Antennen-Panel Phase-Label wird **blau** wenn aktiv. 9 atomare Commits. Tests 1070 → 1111 (+41). Plan-Files prompts/p34_diversity_dynamic_v[1,2,3]+r1.md (Compact-fest). Field-Test V3 §5 F1-F12 pending. Push pending. |

## ✅ Heute erledigt (10.05.2026)

| Version | Was |
|---|---|
| **v0.96.5** | P16.UI-CLEANUP-BUNDLE (P9+P11+P15: Remess-Countdown, Statusbar-Refresh, Antennen-Label) |
| **v0.96.6** | P22.PRESET-ATOMARITAET + **P8.MESS-MODAL** (atomares Speichern Gain+Ratio + WindowModal-Sperre während Mess) |
| **v0.96.7** | P23.OMNI-COUNTER-EIGEN (eigener Down-Counter pro Modus, sichtbar als `↻10` in TX-Display) |
| **v0.96.8** | P21.DEBUG-LOG + DIV-MEAS-RADIO-GUARD (an/aus in Settings, Skip wenn radio.ip=False) |
| **v0.96.9** | **P26.CONNECT-MODAL** (Modal beim App-Start mit Spinner + „Versuch X von 10" + „ohne Radio weiter" + „Beenden". R1-K2-Goldwert: `_start_radio` deferred via singleShot. R1-K1-Race-Fix: lokale Dialog-Referenz + try/except RuntimeError. Final-R1 „Push freigegeben") |

## 🔥 OFFEN — Hohe Priorität

| ID | Was | Aufwand | Hinweis |
|---|---|---|---|
| **P30** | MEMORY-LEAK 124 GB nach Tagen Laufzeit — Mike musste App killen | 2-3h Diagnose | **KRITISCH**. Verdacht: AP-Lite Sound-File-Aufzeichnung auf SSD. Detail unten. |
| **P12** | QSO-POSTPROCESSING-ASYNC — App hängt 1 Min nach QSO (logbook.refresh ist Wurzel) | **PARTIAL-FIX 11.05.** Logbuch nur letzte 500 (commit folgt). Sauberer Async-Refresh weiter offen | Mike-Diagnose 11.05.: logbook.refresh() lädt 20 MB ADIF jedes Mal neu |
| **P27** | MESS-GUARD — vor Antennen/Diversity/Gain-Mess prüfen ob Radio verbunden (Mike-Wunsch 10.05. 17:35: „BVOR MESSUNG SIND WIR ÜBERHAUPT VERBUNDEN?") | 1.5h Workflow | aus P26-Spec ausgegliedert |
| **P25** | RADIO-IP-LATE-SETTING — Wurzel warum `radio.ip` spät gesetzt wird | 2h Diagnose | Mike 10.05. ~18:00: „radio ist nicht spät, wird normal gesucht und gefunden" → evtl. obsolet, vor Push prüfen |

## 📋 OFFEN — Mittlere Priorität

| ID | Was | Aufwand |
|---|---|---|
| **P34-Stufe2** | Statik-Pipeline KOMPLETT entfernen (Dynamic wird Default). Erst nach mehreren Tagen erfolgreichem Field-Test der P34-Stufe1. Liste Code-Stellen siehe `prompts/p34_diversity_dynamic_v3.md` §8-Anhang. | 4-5h Workflow + eigene V1→V2→R1→V3 |
| **P32** | RX-Panel Spalten-Konfiguration persistieren — Rechtsklick-Auswahl (km/dt/Land/...) bei App-Start wiederherstellen | 1h Lite |
| **P33** | QSO-fertig-Meldung erscheint NACH nächster CQ-Zeile (Reihenfolge-Bug) — `✓ QSO komplett` sollte VOR `→ Sende CQ ↻N` im qso_panel stehen | 1-2h Workflow |
| **P24** | App soll letzten RX-Mode (Normal/Std/DX) merken — heute startet immer Normal | 1h Lite |
| **P10** | PSK-BACKOFF-RESET — Backoff von 60min auf 5min ODER Reset-Button | 1-2h |
| **P14** | DT-WERTE-ASYMMETRISCH — NTP-Korrektur-Issue | 2h Diagnose |
| **P13** | RX-PANEL-SLOT-TIMES — Wall-Time vs Slot-Boundary | 1-2h |

## 🛠 OFFEN — Niedrige Priorität

| ID | Was | Aufwand |
|---|---|---|
| ~~P18~~ | ~~DT-KORR-3X-RELOAD~~ ✅ **ERLEDIGT v0.97.12 Bundle A (13.05.2026)** |
| ~~P20~~ | ~~LOG-ROTATION simpleft8.log~~ ✅ **ERLEDIGT v0.97.12 Bundle A (13.05.2026)** |
| **P29** | OMNI-CQ QSO-Panel-Anzeige: bei Paritäts-Wechsel (Even↔Odd) Leerzeile dazwischen + Even-Slot etwas dunklere Farbe (selber Farbton, nur ein wenig dunkler) zur optischen Unterscheidung | 1h |
| **P49** | OMNI-Pretrigger aus Settings (P48-Followup): `core/omni_cq.py:_OMNI_PRETRIGGER_OFFSET_S = 1.3` ist letzte hartcodierte FlexRadio-Konstante, sollte aus `settings.tx_buffer_s` kommen für IC-7300-Fork-Kompat | 30min |
| ~~P43~~ | ~~setproctitle für Activity-Monitor-Erkennbarkeit~~ ✅ **ERLEDIGT v0.97.12 Bundle A (13.05.2026)** |
| ~~P44~~ | ~~Statusbar DT-Korrektur grün-Bug~~ ✅ **ERLEDIGT v0.97.10 (13.05.2026)** |
| **P46** | Bandpilot Normal wieder reinholen → 3-Wege-Vergleich Normal/Std/DX | 2-3h Workflow |
| ~~P47~~ | ~~Tote Frequenz-Settings + Statusbar-Filter-Anzeige entfernen~~ ✅ **ERLEDIGT v0.97.11 (13.05.2026)** |

## 📋 P47.TOTE-FREQUENZ-SETTINGS-ENTFERNEN (Mike+Claude+R1 13.05.2026)

**Konsens:** Beide Frequenz-Settings + Statusbar-Anzeige raus.

**Begründung (R1-Originalton):**

> „Tote Settings sind toter Code und verletzen das Prinzip der geringsten
> Überraschung. Steuerbarkeit vortäuschen, die nicht existiert."

**Was entfernt wird:**

1. **TX Audio-Frequenz** (Setting + UI-Eingabe + Default-Wert)
   - Wird vom CQ-Such-Algorithmus eh dynamisch überschrieben
   - File: `config/settings.py` (Key entfernen), `ui/settings_dialog.py`
     (Eingabe-Feld Tab „FT8 Diversity" raus)

2. **Max. Decode-Frequenz** (Setting + UI-Eingabe + Default-Wert)
   - Beim Modus-Wechsel automatisch gesetzt (FT8/4 → 3000, FT2 → 4000)
   - User-Eingabe wird sofort überschrieben
   - Gleiche Files wie 1.

3. **Statusbar-Anzeige „100-3100 Hz"**
   - File: `ui/main_window.py` `_update_statusbar()` — `_FILTERS` Dict
     + `filter_str`-Aufbau raus
   - Auch der `filter_str`-Einsatz im Statusbar-Text

**Migration alter Configs:**
Keine eigene Migrationslogik nötig. Settings-Objekt ignoriert unbekannte
Keys beim Laden, schreibt sie beim Save nicht zurück → alte
`tx_audio_freq` / `max_decode_freq` werden stillschweigend weggespült.

**Tests:**
- Tests die explizit auf diese Settings testen müssen entfernt werden
- grep `tx_audio_freq` und `max_decode_freq` über Tests-Verzeichnis
- Settings-Smoke-Tests bleiben sonst grün

**Aufwand:** 1-2h Workflow (V1→V2→R1→V3 + Code + Tests + Doku).

**Risiko:** LOW — beide Settings sind ohnehin wirkungslos, kein
Verhalten ändert sich für aktive Nutzung.

**Plan-File: P47-Workflow wird bei Umsetzung angelegt.**

---

## 📋 P46.BANDPILOT-NORMAL-REINTEGRATION (Mike+Claude+R1 12.05.2026)

**Aktueller Stand:** Bandpilot vergleicht nur Diversity Standard vs DX.
Mike's Vision: „ganz oder gar nicht" — wenn schon Pilot, dann alle 3 Modi.

**Konsens Mike + Claude + R1:**

> Normal wieder rein. Architektonisch sauber, UX-konsistent, fairere
> Pilot-Entscheidung. R1: „95 % der Bänder verliert Normal — aber die
> 5 % Spezialfälle (dünne Datenbasis 17m/12m, resonante 20m-Antenne in
> ruhigen Stunden, Single-Antenna-Setups) rechtfertigen den Aufwand."

**Schwellen (bereits vorhanden!):**

`core/mode_recommender.py`:
```python
MIN_DAYS_HOUR = 3        # Mindest-Messtage pro Stunde
MIN_CYCLES_HOUR = 20     # Mindest-Zyklen pro Modus
```

→ Für Normal-Reintegration: **gleiche Schwellen verwenden.** Wenn
Normal ≥3 Tage × ≥20 Zyklen pro Stunde hat, wird's in den Vergleich
aufgenommen. Sonst 2-Wege-Vergleich (Std vs DX) wie heute.

→ Ausreißer-Glättung: bereits durch Pooled Mean über alle Zyklen
gewährleistet. Bei R1's Bedenken zu „nur 2-3 Datenpunkte" greift
`MIN_CYCLES_HOUR=20` als Sicherung.

**Aufwand:** 2-3h Workflow (V1→V2→R1→V3 + Code in `core/mode_recommender.py`
+ Tests + UI-Update Settings-Dialog).

**Geplante Aenderungen:**

1. `core/mode_recommender.py` — `compare_modes()` Normal-Slot reinholen
2. `ui/main_window.py` bzw. Bandpilot-Handler — 3-Wege-Switch
3. Settings-Dialog: Bandpilot-Beschreibung anpassen
4. Tests: Normal-Wins-Szenario + Normal-Schwellen-Fail-Szenario

---

## 📋 P43.PROCTITLE — Activity-Monitor-Erkennbarkeit

**Hintergrund (12.05.2026):** Bei der P30-Memory-Leak-Diagnose tauchte
das Problem auf dass macOS Activity Monitor sowohl SimpleFT8 als auch
Qwen3-TTS als „Python" anzeigt — beide nutzen das gleiche Python-Binary.
→ Bei „128 GB Python" konnten wir nicht unterscheiden welcher Prozess
schuld war. Stellte sich raus: TTS, nicht SimpleFT8.

**Lösung — `setproctitle`-Modul:**

In `main.py` ganz oben (nach den ersten Imports):
```python
try:
    import setproctitle
    import os
    setproctitle.setproctitle(f"SimpleFT8 DA1MHH PID:{os.getpid()}")
except ImportError:
    pass  # optionales Modul, App läuft auch ohne
```

→ Activity Monitor zeigt dann `SimpleFT8 DA1MHH PID:12345` statt
nur „Python". Sofort erkennbar gegen TTS und andere Python-Apps.

**Installation:**
```bash
./venv/bin/pip install setproctitle
```
Plus Eintrag in `requirements.txt` falls vorhanden.

**Test:**
1. App starten, `ps -axo pid,command | grep SimpleFT8` → Name sollte
   `SimpleFT8 DA1MHH PID:NNN` zeigen
2. Activity Monitor öffnen → Spalte „Prozessname" zeigt es

**Aufwand:** ~30 min (5 Zeilen Code + pip install + 1 Test + Doku).

**Trivial-Klausel:** ja → KEIN voller V1→V2→R1→V3-Workflow nötig.
Direkt umsetzen wenn wir das nächste Mal eh Code anfassen.

**Risiko:** keins. `setproctitle` ist Standard-PyPI-Modul, weit
verbreitet, no-op wenn fehlt (try/except).

## 📦 Push pending

KEIN Push seit v0.95.16. Lokal gesammelt: **v0.95.16 → v0.96.9 + P2-Tool +
P3-Audio-Dump + P21-Debug-Log + P26-Connect-Modal**. Push erst wenn
Mike alle Field-Tests abgenommen hat. Aktueller Stand: P22/P23/P21/P16
field-getestet OK; P26 Field-Test ausstehend (V3 §8 6 Punkte).

## ✅ 11.05.2026 RESOLVED

- **P12 Logbuch-Hang nach QSO:** behoben via Partial-Fix (500-Cap, commit
  `d61accc`). Mike-Bestätigung 11.05. ~05:55: „Einfrieren nach qso fehler
  behoben gerade qso erfolgreich beendet. können wir abhaken."
- **P28 PSK-Bug:** OMNI-TX hat `_has_sent_cq` nicht gesetzt, PSK-Worker
  fragte nie ab. Fix in `_on_tx_started` (commit `708a521`). Mike-Field-
  Test 11.05.: „psk reporter zeigt ansehr sehr gut".
- **P31 Counter-Bug ↻9 statt ↻10:** OMNI-Counter zeigte post-decrement
  statt pre-decrement Wert + post-Flip-Parity-Race in QSO-Panel. Fix in
  `core/omni_cq.py` (commit folgt) — neues Display-Property
  `cq_remaining_display` + `cq_tx_even_display`, mw_qso + Statusbar
  lesen Display-Wert. Sequenz jetzt: ↻10 → ↻9 → ... → ↻1 → Flip → ↻10.

## ✅ Heute RESOLVED (zur Klarheit)

- **P17** (DX-Init-Hang): aufgelöst durch erfolgreichen Phase-2-Mess + P22
  Half-State-Reject + P21 Radio-Guard
- **P19** (DX-Cache-Ignoriert): gleiche Wurzel wie P17, gleiche Lösung
- **P9** (Remess-Countdown): in P16-Bundle erledigt
- **P11** (Statusbar-Parity-Refresh): in P16-Bundle erledigt
- **P15** (Antennen-Label): in P16-Bundle erledigt
- **P21** (Strukturiertes-Debug-Log): heute in v0.96.8 implementiert
- **P22** (Preset-Atomaritaet): in v0.96.6 implementiert + field-getestet
- **P23** (OMNI-Counter-Eigen): in v0.96.7 implementiert + field-getestet

---

# 📋 OFFENE WORKFLOWS (Detail-Beschreibungen)

## 🔥 P30.MEMORY-LEAK 124 GB (Mike-Notfall 11.05. ~05:25)

**🎯 KONKRETER VERDACHT (12.05. Diagnose-Sitzung):** Skip-Bug in
`core/decoder.py` Z.174-188 — `_audio_buffer_24k`-Liste wird NICHT
geleert wenn ein Decode-Slot übersprungen wird (vorheriger Decode
nicht fertig). 720 KB pro Skip-Slot, Wachstum ~432 MB/h bei
Diversity passt zu Mike's Screenshot-Math (540 MB/h). Memory-Watcher
läuft als Daemon (PID 72060), 1-2 Tage Korrelation abwarten dann
voller Workflow Fix. Detail-Diagnose: siehe HISTORY 2026-05-12.

**Symptom:** Mike musste App beenden — **124 GB Speicher**
(„speicherleak"). Problem besteht seit Tagen.

**Mike-Verdacht:** App schreibt Sound-Files zur AP-Lite-Analyse
auf SSD. Vermutlich Datei-Handles nicht geschlossen ODER Audio-
Buffer im RAM gehalten statt freigegeben.

**Klärung nach Live-Check 11.05.: RAM, NICHT Disk.**
- `~/.simpleft8/` ist 45 MB (sauber)
- `audio_dump/` existiert nicht (P3 Audio-Dump aus)
- → 124 GB sind echtes RAM-Leak, nicht SSD-Voll
- Math-Eingrenzung: ~720 KB Audio-Slot × 172.000 Slots ≈ 30 Tage
  durchgehend → passt zu „seit Tagen"

**Verdächtige Pfade (Reihenfolge nach Wahrscheinlichkeit):**
- **`core/locator_db.py` `_calls`-Dict** — wächst monoton mit jedem
  CQ-Decode, kein Cleanup. Bei Mike's Setup vermutlich riesig.
- **`log/qso_log.py` records** — alle QSOs in-memory, akkumuliert?
- **`decoder.last_audio_24k`** — wird überschrieben, aber evtl. von
  Qt-Signal-Subscribern festgehalten (`audio_dump_signal` oder
  Cycle-Pipeline)
- **`_recent_logged_calls`-Dict** (P1.7 Dedup, mw_qso) — 300s Window,
  aber wird das je gepruned?
- **AP-Lite `_buffers`** — Cap exists, aber 720 KB pro Buffer
- **`qso_panel.log_view` QTextEdit** — `_auto_trim_by_age` läuft alle
  30s, prüfen ob wirklich greift

**Diagnose-Schritte:**
1. App neu starten, Activity Monitor offen lassen, RAM-Verlauf beobachten
2. Welche Files wachsen auf SSD? `du -sh ~/.simpleft8/` und
   `du -sh audio_dump/` und `du -sh statistics/`
3. AP-Lite-Recording-Pfad finden + Output-Größe prüfen
4. Memory-Profiling via `tracemalloc` (Python-Builtin) — App startet,
   nach 30 Min Snapshot
5. **Sofort-Mitigation:** AP-Lite-Recording oder Audio-Dump
   temporär deaktivieren bis Wurzel geklärt

**Aufwand:** 2-3h Diagnose + ggf. Fix.

**Schweregrad:** **KRITISCH** — App-Crash nach Tagen, Mike kann nicht
durchgehend laufen lassen, blockt Push.

---

## 📋 P32.RX-PANEL-COLUMN-PERSIST (Mike-Wunsch 11.05. ~05:55)

**Symptom:** Im RX-Panel (Empfangsfenster) kann der User per Rechtsklick
auf die Spaltenüberschrift auswählen welche Spalten angezeigt werden
(z.B. km, dt, Zeit, Land etc.). Aber bei App-Restart geht die Auswahl
verloren — Default-Spalten kommen zurück.

**Mike-Wunsch:** Auswahl bei jedem Klick speichern, bei App-Start laden.

**Files (vermutet):**
- `ui/rx_panel.py` — `RxPanel` Klasse, Spalten-Definition + Rechtsklick-
  Menü-Handler
- `config/settings.py` — Settings-Key `rx_panel_visible_columns` (list[str])
- `ui/main_window.py` `closeEvent` — Save vor Quit
- App-Init — Load + Anwenden auf RX-Panel

**Aufwand:** ~1h Lite. Pattern wie andere Settings-Persistenz (band,
mode, power_preset, etc.).

**Schweregrad:** Niedrig — UX-Annoyance, keine Funktion betroffen.

---

## 📋 P33.QSO-COMPLETE-DISPLAY-ORDER (Mike-Wunsch 11.05. ~05:55)

**Symptom:** Im QSO-Panel erscheint die `✓ QSO mit X komplett`-Zeile
NACH dem nächsten `→ Sende CQ ↻N`-Eintrag statt davor. Beispiel
(Mike-Screenshot):
```
03:53:30 [E] ← Empf. EC3A 73       ← Empfang des 73 (QSO done)
03:54:00 [E] → Sende CQ DA1MHH ↻9  ← schon nächster CQ-TX
         ✓ QSO mit EC3A komplett   ← KOMMT ERST HIER
03:55:00 [E] → Sende CQ DA1MHH ↻8
```

**Mike-Erwartung:** `✓ QSO komplett` direkt nach Empfang-73, vor
nächstem CQ-Send.

**Wurzel (unbestätigt):** `qso_confirmed`-Signal feuert erst in
`on_message_sent` für `TX_73_COURTESY` (NACH Höflichkeits-73-Send).
Bis dahin ist der nächste Slot-Start schon getriggert und OMNI hat
einen CQ losgeschickt. Plus `add_qso_complete` hat keinen Zeitstempel
— Append-Reihenfolge im QTextEdit kann nicht durch Slot-Zeit
korrigiert werden.

**Lösungs-Optionen:**
- `qso_confirmed.emit` SOFORT bei 73-Empfang (nicht nach
  Höflichkeits-73) — aber das bricht Mike's P1.10-Fix (IC-7300
  Auto-Sequence wartet auf Höflichkeits-73)
- `add_qso_complete` mit Slot-Time-Stempel + cleverer Insertion-Order
  via QTextCursor (komplex)
- Pre-resume von OMNI verzögern bis nächster-übernächster Slot
- Eigener Workflow V1→V2→R1→V3 nötig (mehrere Abhängigkeiten:
  qso_state TX_73_COURTESY-Pfad, OMNI-Resume-Timing, qso_panel
  Append-Logik).

**Aufwand:** 1-2h Workflow.

**Schweregrad:** Niedrig (kosmetisch).

---

## 📋 P29.OMNI-CQ-PANEL-PARITY-SEPARATION (Mike-Wunsch 11.05. ~05:15)

**Symptom:** OMNI-CQ sendet im Even- UND Odd-Slot, im QSO-Panel laufen
die `→ Sende CQ DA1MHH JO31 ↻N`-Zeilen ohne optische Trennung
hintereinander. Mike will auf einen Blick sehen welche Paritäts-Phase
gerade läuft.

**Soll:**
1. Bei **Paritäts-Wechsel** (Even-Block → Odd-Block oder umgekehrt)
   eine **Leerzeile** zwischen den TX-Zeilen einfügen.
2. **Even-Sende-Zyklus etwas dunklere Farbe** (Mike: „ein wenig dunkler,
   nicht ganz dunkel — Farbe sollte beibehalten werden"). Aktuelle TX-
   Farbe ist `#FFAA00` (Orange) — Even-Variante z.B. `#CC8800` oder
   `#E09600` (selber Hue, niedrigere Lightness).

**Files (vermutet):**
- `ui/qso_panel.py` `add_tx(message, omni_remaining=None, ant_label=...)`
  bekommt neuen Param `tx_even: bool` und detektiert Paritäts-Wechsel
  via internem `_last_omni_parity`-State.
- ggf. Helper `_append_blank_line()` für die Trennzeile.

**Aufwand:** ~1h Lite — Style + State. Trivial-Klausel vermutlich
greifend (kleine UI-Änderung, keine Architektur).

**Schweregrad:** Niedrig — reine UX, keine Funktion.

---

## 📋 P24.LAST-RX-MODE-PERSIST (Mike-Wunsch 10.05. 17:10)

**Symptom:** App startet IMMER in Normal-Modus, egal in welchem Modus
sie beendet wurde (Diversity Standard / Diversity DX).

**Mike-Zitat:** „nicht schöner fix aber ein fix" (kommentiert das
aktuelle Verhalten dass NORMAL nach Restart erzwungen wird).

**Soll:** App speichert beim Beenden den aktuellen RX-Mode (`normal`,
`diversity_standard`, `diversity_dx`) in Settings und stellt ihn beim
nächsten Start wieder her.

**Files (vermutet):**
- `config/settings.py` neue Key `last_rx_mode`
- `ui/main_window.py` `closeEvent` speichert
- `ui/main_window.py` Init liest + setzt RX-Mode

**Aufwand:** ~1h Workflow-Lite (V1 + Code, kein R1 weil trivial).

**Schweregrad:** Mittel — UX-Annoyance, kein Daten-Verlust.

---

## 📋 P25.RADIO-IP-LATE-SETTING (Wurzel-Diagnose 10.05.)

**Symptom:** Beim App-Start ist `self.radio.ip` falsy (False/leer)
obwohl Audio-Stream (DAX) bereits Stationen liefert. Dauer unklar
(Sekunden? Minuten?). Trigger fuer den heute via Skip-Fix umgangenen
0/6-Hänger.

**Workaround heute (P21 v0.96.8):** `_handle_diversity_measure` skipped
wenn `radio.ip=False` → wartet bis Connection da. Sobald `radio.ip` True
wird, läuft Mess natürlich an.

**Wurzel-Frage:** WARUM ist `radio.ip` lange False?
- Reconnect-Loop läuft im Hintergrund?
- Audio-DAX-Stream und TCP-Connect sind separate Pfade?
- Initialisierungs-Reihenfolge in `MainWindow.__init__`?

**Files (vermutet):**
- `radio/flexradio.py` Connect-Logik + ip-Property
- `ui/mw_radio.py` Init + Reconnect-Mechanik

**Aufwand:** ~2h Diagnose + ggf. Fix.

**Schweregrad:** Niedrig (Workaround greift) — aber Wurzel-Bug bleibt
und kann anderswo Probleme machen.

---

## 📋 P26.MODAL-RADIO-CONNECT (Mike-Wunsch 10.05. 17:15)

**Symptom:** Während FlexRadio gesucht/verbunden wird, sieht Mike das
nicht prominent — kleine Statusmeldung rechts im UI „beachtet keiner".

**Mike-Spec:**
- Modal-Dialog im Vordergrund während Connect läuft
- KEIN OK-Button, KEIN Abbruch — nur Info „FlexRadio wird verbunden"
- Sobald Radio verbunden → Dialog ausblenden
- Alternativ ODER zusätzlich: prominente Statusmeldung rechts
  (gross, sichtbar) — aber Modal ist Mike's bevorzugte Variante

**Pattern:** analog `MessStatusDialog` aus P22/P8 — WindowModal (NICHT
ApplicationModal weil Reconnect-Logik im Hintergrund laufen muss).
Auto-Close bei Connect-Erfolg via `radio.connected`-Signal.

**Files (vermutet):**
- `ui/connect_status_dialog.py` NEU (analog `mess_status_dialog.py`)
- `ui/mw_radio.py` Open-Hook beim Connect-Start, Close-Hook bei
  `radio.connected`-Signal

**Aufwand:** ~1.5h V1+Code+Test. KEIN voller Workflow weil Pattern aus
P22 kopiert.

**Schweregrad:** Mittel — UX (verhindert Confusion bei langen
Connect-Zeiten und löst möglicherweise auch P21-Problem).

**Claude-Hinweis 17:30 UTC:** P26 löst nebenbei vermutlich auch
P25-Symptome — wenn Mike den Modal-Dialog sieht statt zu denken
„App ist tot", weiß er warum die Mess wartet. Plus: das Modal könnte
selbst die Mess-Start-Steuerung übernehmen (Mess startet erst NACH
Connect-Erfolg, sauber statt Skip-Workaround). Beim Bauen von P26
würde ich vorschlagen P21-Skip-Fix beizubehalten als Defense-in-Depth,
aber das Modal wäre der primäre Schutz. → **Wenn P26 gebaut wird,
P25 evtl. komplett obsolet.**

---

## 🔥 TOP — P7 Field-Test (Mike, post-Code)

**Status:** Code fertig (v0.96.4), Final-R1 „Push freigegeben"
(0 KRITISCH/SOLLTE/KOENNTE). Tests **1008 grün**. App gestoppt —
Mike startet selbst für Field-Test.

**Field-Test 8-Punkte-Plan (V3 §6 F1-F8):**

| F | Test | Erwartung |
|---|---|---|
| F1 | App start, Diversity, OMNI toggeln | OMNI-Start-Log + CQ-Audiofreq-Set + erster CQ in aktuellem Slot |
| F2 | 5-10 Min beobachten | CQ-Ruf in EINER Paritaet (z.B. nur Even-Slots :30/:00). Andere Slots leer im qso_panel. **Diversity-Anzeige zeigt beide Antennen wechselnd** (kein „nur eine"). |
| F3 | Statusbar checken | `Ω CQ=X (E)` oder `(O)` zeigt aktuellen Stand |
| F4 | 10 Min weiterlaufen lassen | Paritaets-Wechsel automatisch (Log: „Paritaets-Wechsel auf Odd"). qso_panel zeigt ab dann CQ in anderer Paritaet (z.B. nur Odd :45/:15) |
| F5 | Antwort kommt waehrend OMNI | OMNI pausiert, QSO laeuft normal. Nach QSO: OMNI resumed in alter Paritaet |
| F6 | 1h warten → Diversity Re-Mess (90s) | OMNI sendet **nicht** waehrend Mess. Nach Mess: OMNI sendet wieder |
| F7 | Bandwechsel mid-OMNI | OMNI auto-stop (band_change), App stabil |
| F8 | Mode-Wechsel auf Normal | OMNI auto-stop (mode_change), App stabil |

**Bestanden wenn:** F1-F4 sauber + F2 zeigt Diversity beide Antennen.

## 🚀 Push (zusammen mit Field-Test-Freigabe)

KEIN Push (origin) seit v0.95.16. Lokal gesammelt seit dann:
**v0.95.16-0.96.4 + P2-Tool**. Push erst nach Mike-Field-Test-OK
mit `git push origin main`.

---

## 📋 P8.MESS-STATUS-DIALOG (geplant nach P7)

**Mike-Wunsch 10.05.2026:** Modal-Dialog während Diversity-Mess-Phase.

**Spec:**
- Trigger: `_diversity_ctrl.start_measure()` aufgerufen → Dialog öffnen
- Modal blockierend (sperrt UI dauerhaft im Vordergrund)
- Inhalt:
  - Titel: "Diversity-Antennen werden neu eingemessen"
  - Aktuelle Antenne (A1/A2)
  - Slot-Counter (z.B. "Slot 3 von 6")
  - Restzeit (z.B. "~45s")
  - Optional: bisheriger Ratio + Live-Werte
- Schließt automatisch wenn `_diversity_ctrl.phase` zurück auf "operate"

**Workflow:** eigener V1→V2→R1→V3 nach P7 abgeschlossen.

**Files:**
- NEU `ui/mess_status_dialog.py` (QDialog Subclass analog zu existing dx_tune_dialog.py)
- `ui/mw_cycle.py` Hook nach `start_measure()` → Dialog öffnen
- `ui/mw_cycle.py` Phase-Wechsel "measure" → "operate" → Dialog schließen

**Aufwand:** ~1-2h V1+V2+R1+V3+Code

---

## 📋 P9.REMESS-COUNTDOWN-UI (Field-Test 10.05. Mike)

**Symptom:** Re-Mess-Countdown in Antennen-Panel springt in 10-Min-Blöcken
(58 → 48 → 38) statt jede Minute zu aktualisieren. Irritierend.

**Soll:** Countdown updated alle 60s (oder noch häufiger), Format
`XX min YY s` damit User Fortschritt sieht.

**Files (vermutet):**
- `ui/control_panel.py` oder `ui/antenna_card.py` — Countdown-Display
- Trigger: `_diversity_ctrl.seconds_until_search` oder analog für Re-Mess

**Aufwand:** ~30 Min (trivialer UI-Fix, vermutlich ohne vollen Workflow)

---

## 📋 P10.PSK-BACKOFF-RESET (Field-Test 10.05. Mike)

**Symptom:** App's PSK-Reporter-Polling geht bei Server-Errors (502/503/
Timeout) in exponentielles Backoff bis 60 Min. Wenn Server wieder läuft,
fragt App stundenlang nicht mehr — Anzeige bleibt leer obwohl Mike
gehört wird (Direct-API-Test 10.05.: 15 Stationen weltweit hörten DA1MHH).

**Soll (Optionen — Mike entscheidet im V1):**
1. BACKOFF_MAX von 3600s auf 300s (5 Min) senken
2. Manueller Reset-Button in UI
3. Auto-Reset bei OMNI-Start oder Mode-Wechsel

**Files:**
- `core/psk_reporter.py:42-43` BACKOFF-Konstanten
- ggf. `ui/control_panel.py` für Reset-Button
- `ui/main_window.py` für Auto-Reset-Hook

**Workaround sofort:** App neu starten → Backoff resettet.

**Aufwand:** ~1h V1→V2→R1→V3+Code

---

## 📋 P11.STATUSBAR-PARITY-REFRESH (Field-Test 10.05. Mike, P7-Folge)

**Symptom:** Nach OMNI-Paritäts-Wechsel zeigt Statusbar `Ω CQ=X (O)`
weiterhin alte Parität, obwohl `_cq_tx_even` korrekt geflipped ist.
TX-Anzeige im qso_panel ist korrekt (zeigt neue Parität).

**Diagnose:** `parity_flipped`-Signal wird emit + `_on_omni_parity_flipped`
ruft `_update_statusbar()`. Aber UI-Refresh hängt evtl. an QTimer der
zu selten läuft, oder `_update_statusbar` nutzt veraltete Werte.

**Files:**
- `ui/main_window.py` `_update_statusbar` + `_on_omni_parity_flipped`
- ggf. statusbar-Refresh-Timer prüfen

**Aufwand:** ~30 Min (UI-Bug, trivial)

---

## 📋 P12.QSO-POSTPROCESSING-ASYNC (besteht seit Wochen, Mike 10.05.)

**Symptom:** Nach jedem QSO-Ende hängt GUI 1-2 Min ("Beachball"). App
läuft weiter (Decoder-Thread arbeitet, 35-84% CPU), aber UI-Thread
ist blockiert.

**Vermutete Ursachen (alle parallel):**
- `core/psk_reporter.py` Polling im GUI-Thread mit 30-90s Timeouts
- ADIF-Save (`log/adif.py`) Disk-I/O blocking
- QRZ-Upload-Trigger (HTTPS-POST mit Timeout)
- Locator-DB-Save (atomic-Write)
- Statistik-Logging

**Soll:** Alle blocking I/O nach QSO-Ende in Worker-Thread auslagern
(`QThread` oder `concurrent.futures.ThreadPoolExecutor`).

**Files:**
- `ui/mw_qso.py` QSO-End-Handler
- `core/psk_reporter.py` (separat von P10)
- `log/adif.py`
- `core/locator_db.py`

**Aufwand:** ~2-3h V1→V2→R1→V3+Code (komplex weil mehrere Pfade)

---

## 📋 P13.RX-PANEL-SLOT-TIMES (Field-Test 10.05. Mike, besteht seit v0.95.16+)

**Symptom:** RX-Panel zeigt krumme Wall-Time-Zeiten (z.B. 10:51:42)
statt FT8-Slot-Boundaries (10:51:30 oder 10:51:45). Mike erinnert
sich an Slot-Zeiten in vorigen Versionen.

**Diagnose:** `ui/rx_panel.py:280` nutzt `msg._utc_display` oder
Fallback `time.strftime("%H%M%S", time.gmtime())`. Wenn der Decoder
`_utc_display` nicht setzt, kommt Wall-Time durch.

**Files:**
- `ui/rx_panel.py` (letzte Aenderung Commit `7e8df00` v0.95.16)
- `core/decoder.py` setzt `msg._utc_display` / `_utc_str` / `_slot_start_ts`?
- ggf. `core/message.py` Format

**Aufwand:** ~1-2h (Decoder-Pfad muss verstanden werden)

---

## 📋 P20.LOG-ROTATION (Mike-Wunsch 10.05.2026)

**Symptom:** `~/.simpleft8/simpleft8.log` wird append-only geschrieben.
Datei waechst unendlich, nach Wochen MB-gross. Bug-Diagnose im alten
Log schwierig (nicht klar welcher Tag was war).

**Soll:**
- Eine Datei pro Tag: `simpleft8-2026-05-10.log`
- Aelter als N Tage (z.B. 7) automatisch loeschen
- Aktueller Tag: `simpleft8.log` Symlink → heutige Datei

**Files:**
- `main.py:32` `_log_file = open(...)` durch `TimedRotatingFileHandler`
  oder Custom-Lösung ersetzen

**Aufwand:** ~1h

---

## 📋 P21.STRUKTURIERTES-DEBUG-LOG (Mike-Wunsch 10.05.2026)

**Symptom:** Bug-Diagnose schwierig weil Log-Eintraege oft kontextlos
sind (z.B. `[Diversity] 48 St. | A1>A2: 0` ohne Antenne/Uhrzeit).

**Soll:** An wichtigen Stellen strukturierte Eintraege mit:
- Datum + Uhrzeit (statt nur HH:MM:SS)
- Aktive Antenne (A1/A2)
- Aktuelle Mode/Band/Mess-Phase
- Encoder-Status (TX/RX/idle)

**Files:**
- `core/diversity.py` Antennen-Switch-Pfad
- `core/decoder.py` Mess-Pass-Output
- `core/encoder.py` TX-Pfad
- `core/ntp_time.py` DT-Korrektur-Pfad

**Aufwand:** ~2h Diagnose + Refactor (welche Stellen brauchen mehr Kontext?)

---

## 📋 P22.PRESET-ATOMARITAET (Mike-Analyse 10.05. nach P17/P19-Resolve)

**Mike-Analyse 14:35:** „wenn eine von beiden eintraegen verstaerkung
und/oder diversity fehlt oder fehlerhaft ist und nur einer geladen
werden kann kommt es vermutlich zu den fehler weil die app entweder
beide oder keinen wert erwartet"

**Architektur-Schwaeche:** `presets_dx.json` / `presets_standard.json`
speichert `gain_timestamp` und `ratio_timestamp` separat. Wenn Phase 1
(Verstaerker) erfolgreich aber Phase 2 (Antennenvergleich) haengt,
verbleibt Half-State (gain fresh, ratio stale). Bei jedem Restart wird
Phase 2 wieder versucht → wenn die Wurzel-Bedingung nicht weg ist
(z.B. Race), Endlos-Schleife.

**Loesungs-Optionen:**

1. **Atomares Speichern:** beide Felder zusammen oder gar nicht.
   Phase 1 schreibt nichts in File bis Phase 2 fertig ist (gespeichert
   im Memory). Wenn Phase 2 hängt → kein Disk-Write → Restart fängt
   sauber wieder vorne an.

2. **Robustheit-Fallback:** wenn Phase 2 nach N Versuchen (oder Timeout
   90s) fehlschlaegt → Default-Ratio 50:50 mit aktuellem
   ratio_timestamp speichern. App nicht in Endlos-Schleife stecken.

3. **Beides:** atomares Speichern PLUS Fallback bei Phase-2-Fehlschlag.

**Files:**
- `core/preset_store.py` `update_gain` + `update_ratio`
- `ui/mw_radio.py` `_check_diversity_preset` Half-State-Logik
- `ui/mw_cycle.py` Phase-3-Erfolgs-Pfad

**Aufwand:** ~2-3h V1→V2→R1→V3+Code.

**Schweregrad:** Hoch (latenter Bug, kann jederzeit wieder auftreten
wenn Phase 2 mal wieder haengt).

---

## ✅ P17 + P19 RESOLVED (10.05.2026 ~14:30 Field-Test Mike)

**Aufloesung:** P17 (DX-Init-Hang) und P19 (DX-Cache-Ignoriert) waren
beide Folge davon dass Phase 2 (Antennenvergleichs-Mess) NIE sauber
abgeschlossen hat fuer DX-Mode → ratio_timestamp blieb auf Default
50:50, beim Restart triggert App immer wieder Phase 2-Versuch.

**Auflöser:** Heute lief Phase 2 erstmals erfolgreich durch (ratio=30:70,
dominant=A2 in presets_dx.json gespeichert mit aktuellem
ratio_timestamp).

**Test-Bestätigung Mike 14:30:**
- App-Restart in Normal ✓
- Wechsel zu DX → alles wie es sein soll ✓
- Wechsel zu Normal → alles gut ✓
- Wechsel zu Diversity Standard → beide Antennen aktiv ✓

**Offen:** WARUM Phase 2 vorher nicht durchlief. Vermutung: zu frueher
Mode-Wechsel oder Race bei Antennen-Switch. Wenn Bug nochmal auftritt
→ Re-Diagnose.

---

## 📋 P19.DX-CACHE-IGNORIERT-BEI-MODE-WECHSEL (Field-Test 10.05. Mike) [RESOLVED]

**Symptom:** NORMAL → DIVERSITY DX wechseln macht **komplette Neu-
kalibrierung** obwohl gueltiger Cache da sein sollte (Cache 2h gueltig
laut CLAUDE.md, Mike erinnert sich an 6h).

**Soll:** Cache pruefen → wenn vorhanden + nicht stale → laden + Kali-
brierung ueberspringen. Erst wenn stale → neu kalibrieren.

**Mike-Zitat:** „die ja speichern soll und die dann 6 stunden oder so
gueltig ist er juenger wird die geladen und kalibrirung uebersprungen"

**Files (vermutet):**
- `ui/mw_radio.py` Mode-Switch zu DIVERSITY DX
- `core/diversity.py` oder `core/preset_store.py` Cache-Lade-Logik
- ggf. zusammen mit P17 (auch Diversity-DX-Init-Issue)

**Aufwand:** ~1-2h Diagnose + Fix. Vermutlich ueberlappt mit P17.

**Schweregrad:** Hoch — verhindert produktiven Wechsel zu DX.

---

## 📋 P17.DIVERSITY-DX-START-INIT-BUG (Field-Test 10.05. Mike, BLOCKIEREND)

**Symptom:** Bei App-Start direkt in **DIVERSITY DX**-Modus haengt Mess
bei `MESSEN 0/6`. Antennen-Switch greift nicht — alle Stationen werden
nur auf A1 empfangen, A2=0.

**Log-Beweis:**
```
[Diversity] 48 St. | A1>A2: 0 | A2>A1: 0 (0%) | Nur A1: 48 | Nur A2: 0
[Diversity] 50 St. | A1>A2: 0 | A2>A1: 0 (0%) | Nur A1: 50 | Nur A2: 0
```

**Konsequenz:**
- A2 sammelt keine Decode-Daten
- `_measure_step` inkrementiert nie (in `add_measurement` nur bei
  Antennen-Switch-Decode)
- Mess haengt ewig 0/6
- OMNI kann nicht senden (V2-L12 Schutz: phase != "operate")

**Workaround:** NORMAL → DIVERSITY STANDARD wechseln + Kalibrieren →
laeuft. Aber DIVERSITY DX direkt nach Start = Bug.

**Reproduzierbar:** Mike heute zweimal beobachtet (ca. 11:00 + 13:45).

**Files (vermutet):**
- `ui/mw_radio.py` Mode-Switch-Logik bei DX
- `core/diversity.py` Mess-Initialisierung
- ggf. fehlt eine Antennen-Init beim ersten Slot in DX

**Aufwand:** ~2-3h (Diagnose + Fix + Test). VORSICHT: Mike-Spec
"Diversity ist UNANTASTBAR" — nur das Init-Verhalten beim DX-Start
fixen, keine Hauptlogik aendern.

**Schweregrad:** **BLOCKIEREND** — verhindert ProduktivOnut von OMNI in DX-Modus.

---

## 📋 P18.DT-KORR-3X-RELOAD (Field-Test 10.05. Mike, Diagnose)

**Symptom:** Beim App-Start wird DT-Korrektur fuer aktuelles Band 3×
aus File geladen:
```
[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen
[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen
[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen
```

**Vermutung:** Initial-Load + Bandwechsel-Reload + Mode-Setup-Reload =
3×. Funktional egal (Wert ist deterministisch), aber ineffizient + irritiert
beim Log-Lesen.

**Aufwand:** ~30 Min Diagnose (wer ruft `_load_for_current_key()` 3×?)
+ ggf. Konsolidierung auf 1 Aufruf.

**Schweregrad:** Niedrig (kosmetisch, keine Regression).

---

## 📋 P15.ANT-LABEL-VERTAUSCHT (Field-Test 10.05. Mike)

**Symptom:** "(ANT2 ↑2.0 dB)"-Label erscheint hinter **Sende**-Eintrag
im qso_panel. FALSCH — Hardware sendet IMMER ANT1 (verriegelt). Label
gehört hinter **Empfangs**-Eintrag um zu zeigen welche Antenne RX
besser war.

**Diagnose:** `ui/mw_qso.py:90-129`:
- `_antenna_pref_label(call)` liefert " (ANT2 ↑2.0 dB)"
- Wird in `qso_panel.add_tx(message, ant_label, ...)` als ant_label
  uebergeben → Label hinter Sende-Eintrag
- Soll: `qso_panel.add_rx(message, ..., ant_label=...)` Label hinter
  Empf.-Eintrag

**Files:**
- `ui/mw_qso.py:121-129` — Label bei add_tx weg, statt bei add_rx zufuegen
- `ui/qso_panel.py:add_rx` — neuer optionaler ant_label-Param

**Aufwand:** ~30 Min trivialer UI-Fix

---

## 📋 P14.DT-WERTE-ASYMMETRISCH (Field-Test 10.05. Mike)

**Symptom:** RX-Stationen zeigen DT fast alle im Minus (-0.1 bis -1.7),
sollten ausgeglichen zwischen + und - sein. Statusbar zeigt
`DT: +0.40s (n=17)` aktive Korrektur — funktioniert nicht symmetrisch.

**Diagnose:** `core/ntp_time.py` DT-Korrektur konvergiert evtl. zu
weit in eine Richtung. Beobachtung passt nicht zu Erwartungswert
(Korrektur sollte RX-DT auf 0 zentrieren).

**Files:**
- `core/ntp_time.py` Median-Berechnung + Damping
- `core/decoder.py` `DT_BUFFER_OFFSET` (FT8=2.0)
- ggf. `dt.md` Doku als Referenz

**Aufwand:** ~2h Diagnose + Fix (Audio-Buffer-Timing-Issue)

---

## 🛠️ META: CLAUDE.md + Memory Restrukturierung

> **Analyse 09.05.2026** — CLAUDE.md ist 673 Zeilen (Ziel: ~120 Zeilen). Memory hat 57 Dateien, Index 73 Zeilen.

### Ursachen des Bloats (identifiziert)

1. **`feedback_todo_history_pflicht.md`-Regel**: "nach jedem Task → CLAUDE.md Header updaten" → nach 20+ Features
   reines Anhängen ohne Kürzen → "Aktueller Stand"-Block wächst unbegrenzt.
2. **Workflow dreifach beschrieben**: V1→V2→R1→V3 steht in CLAUDE.md (Z. 5-30), nochmal Z. 161-170,
   nochmal in 4 Memory-Feedback-Dateien + docs/WORKFLOW.md. Quelle der Wahrheit: docs/WORKFLOW.md.
3. **Philosophie + Leitsätze in CLAUDE.md**: Z. 133-199+ gehören in docs/PHILOSOPHY.md (bestehend?),
   nicht in die Kontext-Datei.
4. **DeepSeek-Tool-Details in CLAUDE.md**: Z. 109-131 (Helper-Skript, Kosten, Tabelle) → Memory oder
   docs/DEEPSEEK_WORKFLOW.md.
5. **Memory-Index-Bloat**: ~30 ✅-ERLEDIGT Project-Einträge belegen Index-Zeilen. Completed → archivieren.

### Plan (4 Schritte, KEIN Workflow nötig — das ist Doku, kein Code)

**Schritt 1 — CLAUDE.md auf ~120 Zeilen schrumpfen:**
- Behalten (fett): Workflow-Pflicht-Block (Z. 5-30), Hardware-Warnung ANT1/ANT2 (Z. 32-57),
  Session-Lifecycle-Kurzfassung (Z. 60-94), Aktueller-Stand-Header (1 kompakte Zeile), Start-Befehl.
- Raus (mit Verweis): Philosophie → `docs/PHILOSOPHY.md`, Leitsätze → `docs/PHILOSOPHY.md`,
  DeepSeek-Tool-Details → Memory `feedback_workflow_works_with_deepseek.md`,
  Feature-Workflow-Abschnitt → `docs/WORKFLOW.md` (Verweis genügt).
- Neue Prune-Regel: "Aktueller Stand = max 3 Zeilen. Alte Stände raus."

**Schritt 2 — docs/ Dateien anlegen/aktualisieren:**
- `docs/PHILOSOPHY.md` — Projekt-Philosophie + Programmier-Leitsätze (bestehende Datei prüfen)
- `docs/ARCHITECTURE.md` — Modul-Übersicht, Klassen, Signal-Flow (bestehende Datei prüfen)
- `docs/KNOWN_BUGS.md` — Offene Bugs mit Diagnose (statt in CLAUDE.md)

**Schritt 3 — Memory-Index bereinigen:**
- Alle ✅-ERLEDIGT project_*.md Einträge aus MEMORY.md entfernen (die Dateien selbst behalten)
- Nur noch ⏳-pending + ⚠️-aktiv + ⛔-PFLICHT im Index → Ziel < 40 Zeilen

**Schritt 4 — `feedback_todo_history_pflicht.md` Prune-Ergänzung:**
- Zusatz: "Beim CLAUDE.md-Update: Aktueller-Stand-Block auf max 3 Zeilen begrenzen, alten Stand raus."

### Trigger
"claude.md restrukturieren" oder "meta aufräumen" → diesen Plan ausführen.

---

## 📌 OFFEN — TOP-PRIORITAET (zuerst angehen)

### 🟡 Splashtop-Doppelklick + Single-Klick verschluckt (NEU 2026-05-08)
- **Symptom:** Mike steuert von Linux Mint Notebook fern. Im RX-Panel
  reagiert kein Klick (Hunt-Klick auf Station, Antwort-Button). In
  ForkLift kein Doppelklick zum Datei-Oeffnen. Zuhause direkt am Mac
  geht alles. → Splashtop-Client-Side-Problem auf Linux Mint, NICHT
  SimpleFT8-Bug.
- **Versuche bisher:** HID-File `/Users/Shared/SplashtopStreamer/
  com.splashtop.input.hid` Anlegen scheiterte (Permission denied,
  sudo nicht moeglich aus Claude-Sitzung).
- **Naechste Schritte:** Linux-Mint-Side: Doppelklick-Timeout in
  System-Settings auf 800ms hochsetzen, anderen Browser/Splashtop-
  Client probieren. Mac-Side: HID-File anlegen wenn Mike das selber
  via Terminal-sudo machen kann.

### 🟡 Memory-Wachstum 32 GB (NEU 2026-05-08, Diagnose laufend)
- **Symptom:** Alte App PID 31564 (v0.95.20) hatte nach ~40 Min
  Laufzeit 32 GB RSS gefressen. vmmap zeigte: 4.2M Allocations,
  96 % Heap-Fragmentation, MALLOC_SMALL (empty) 30.7 GB resident,
  Physical-Footprint-Peak 109.3 GB. KEIN klassischer Leak im Code,
  sondern **chronische Heap-Fragmentation**.
- **Aktueller Stand:** Neu gestartete v0.95.21 PID 39362 stabilisiert
  bei ~670 MB nach 38 Min — **Faktor 50× besser**. Memory-Watcher
  laeuft im Hintergrund (`/tmp/simpleft8_memwatch/memwatch_*.csv`),
  loggt alle 60 s RSS/CPU + alle 5 Min vmmap-Detail.
- **Vermutete Ursache:** ueber Stunden akkumulierte Allocations
  (Decoder-Pipeline ~1700/s) ohne Object-Pools. Kein klarer Trigger.
- **Naechste Schritte:** App 1-2 h aktiv nutzen lassen (sobald
  Splashtop-Klick wieder geht), Wachstumskurve auswerten. Wenn
  > 5 GB → V1→V2→R1→V3 fuer Object-Pool oder periodischer
  `gc.collect()`-Timer. Wenn stabil < 2 GB → kein Bug.

### Field-Test v0.95.22 P1.OMNI-START + Push-Freigabe (NEU 2026-05-08)
- [ ] **Mike-Field-Test (V3 §6, 7+1 Punkte):** Diversity, Easter-Egg an,
      btn_omni_cq sichtbar; Klick → CQ sofort auf Even, Statusbar
      `Ω Even=1 Odd=0`; naechster Slot Odd, dann 3 RX, Block-Wechsel
      nach 80; CQ-Reply → QSO normal → nach RR73 OMNI-Resume; Toggle
      off → CQ stoppt; HALT mit OMNI → alles gestoppt, Button
      entriegelt; Bandwechsel → OMNI stoppt automatisch; OMNI waehrend
      WAIT_REPORT → blockiert + Statusbar 4 s.
- [ ] Bei OK: Push-Bundle v0.95.16-22 + P2-Tool + P3 zusammen.

### Field-Test v0.95.15 P1.QRZ-UPLOAD-UI-2 + Push-Freigabe
- [ ] Mike testet im Feld: Title-Update, Statusbar-Cancel, File-Move,
      JSONL-Log, Rate-Limit-Cooldown, App-Close waehrend Cooldown
- [ ] Bei OK: Mike-Freigabe einholen → `git push origin main`
      (Commits `d8f86b6` Code+Tests + `d313b1a` Doku + `f456d04` TODO)

### P2.ADIF-ARCHIVE — Standalone Helper-Script (✅ ERLEDIGT 08.05.)
- [x] `tools/adif_archive.py` geschrieben — konsolidiert Tagesdateien aus
      `adif/hochgeladen/` in Jahresarchive `adif/archiv/YYYY.adi`.
      Voller V1→V2(15 Lessons)→R1(1 KRITISCH + 2 WICHTIG)→V3→Compact→
      Code→Final-R1(0 KP). Tests 955 → 978 gruen (+23). Tool-only,
      kein APP_VERSION-Bump. Hardware-frei testbar via `--dry-run`.

---

## ✅ P1-Bugs ERLEDIGT (08.05.2026 v0.95.18+19)

- [x] **P1.7** ✅ — Lokaler Duplikat-Filter ADIF/Logbuch (v0.95.19 Bundle2)
- [x] **P1.8** ✅ — Report-SNR-Bug `_last_snr` statt `msg.snr` (v0.95.18 Bug-C)
- [x] **P1.11** ✅ — `wait_73_retries` von `rr73_retries` entkoppelt (v0.95.19 Bundle2)
- [x] **P1.13** ✅ — TX-Frequenz-Spinbox-Sync im Normal-Modus (v0.95.19 Bundle2)

---

## 🛠 OFFEN — Quality-of-Life (alte TODOs, weiterhin gueltig)

- [ ] Even/Odd dedizierter Timer — unabhaengig vom Decoder-Thread (FT2 kritisch)
- [ ] Gain-Bias beheben — Normal-Modus Gain-Messung wenn Stats aktiv erzwingen
- [x] **CQ-Zusammenfassung Dead-Code raus** (08.05.2026): _cq_count und
      _cq_flash_timer-Reste in qso_panel.py + mw_qso.py entfernt. User-
      sichtbare Zusammenfassung war schon weg (HISTORY:2378), nur 4 Zeilen
      Backwards-compat noch vorhanden. Keine Verhaltens-Aenderung.
- [ ] Tertile-Analyse Statistik — kein Datencropping, alle Werte in 3 Drittel
<!-- VERWORFEN 07.05.2026 (Mike-Entscheidung):
     Per-Station DT-Offset TX hat keinen Nutzwert. Globaler -0.8s Offset
     reicht (FT8-Decoder-Toleranz ±2.5s). Per-Station-Offset wuerde
     symmetrische HW-Drift voraussetzen — falsche Pramisse, Risiko >
     Nutzen. -->

- [ ] IC-7300 Fork — TARGET_TX_OFFSET dort separat messen (eigener Branch)
- [x] **F) Audio-Export per Slot** ✅ ERLEDIGT 08.05.2026 (v0.95.20
      P3.AUDIO-DUMP-DEBUG): Toggle in Settings „Daten & Tools" Block 4
      + Spinbox Max-Files (50-1000, Default 200, FIFO-Cleanup). NUR FT8.
      `audio_dump/{band}_FT8/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav`. Architektur
      Pull-Pattern (R1-KRITISCH adressiert). Tests 978 → 992. Field-Test
      ausstehend.
- [ ] TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker
      (NEU 26.04., noch nicht reproduzierbar)

---

## 🗺 OFFEN — Karten-Folgemassnahmen (v0.66)

- [ ] Migration `main_window._psk_worker` → `core/psk_reporter`
- [ ] Karten-Live-Test im Feld (40m FT8 abends mit RX-Layer)
- [ ] TX-Modus Live-Test (CQ rufen + TX-Toggle, schauen ob Marker erscheint)
- [x] Mobile-Filter-Edge-Case dokumentieren (08.05.2026): bereits in
      `core/direction_pattern.py:65-72` als Code-Kommentar — Region-Calls
      wie `K1ABC/W2` werden bewusst rausgefiltert (akzeptabel laut Doku).

---

## 📊 OFFEN — Statistik & Analyse (Prio NIEDRIG)

- [ ] Diagramm-Auswertung 20m fuer GitHub (wenn genug Daten)
- [ ] ANT1 vs ANT2 SNR direkt loggen (ant1_snr, ant2_snr, delta pro Station)
- [ ] Statistik-Diagramme fuer GitHub (matplotlib aus statistics/*.md)
- [ ] Auswertung per Tertile-Analyse (Entscheidung final, kein Datencropping)
- [ ] RX-Liste: Spalten-Konfig in Settings (RX-Spalten ein/ausblendbar
      + gespeichert, Slot/Ant/DT/etc.)
- [ ] CQ-Zusammenfassung im RX-Panel ueberarbeiten (aktuell „CQ ×N" kaum sichtbar)

---

## ✅ ERLEDIGT (Aufraeum-Snapshot 07.05.2026)

- B) Band-Indikatoren live mit PSK-Reporter ✅ — v0.69 deckt Use-Case ab
- C) Richtungs-Keulen TX-Pattern-Karte ✅ — v0.66
- D) Richtungs-Keulen ANT2 RX-Rescue ✅ — v0.66
- E) CSV-Export Diversity-Daten ✅ — v0.65
- AP-Lite Test-Pipeline ✅ — v0.95.9 (P1.AP) + v0.95.10 (P1.AP-FIX)
- DT-Drift Wurzel-Fix ✅ — v0.95.7 (P1.18, `_DT_OFFSETS["FT8"]=3.0`)
- Warteliste-Screenshot ✅ — DL3AQJ-Freigabe + Einbau erledigt

---

## 🗂 ARCHIV (chronologisch, ERLEDIGTE Punkte aus alten Sessions unten)

---

## ✅ P1.24 (06.05.2026 v0.95.9) — ERLEDIGT (Field-Test bestaetigt)

**Folge-Fix zu P1.14:** TX-Klick wurde komplett ignoriert wenn
`encoder.is_transmitting=True` (während CQ-TX oder Hunt-TX_CALL). Mike
musste HALT druecken um Station-Wechsel zu erzwingen.

**Fix:** Buffer-Logik. Klick waehrend TX → State-Cleanup (stop_cq oder
cancel) sofort + Buffer + Statusbar; nach TX-Ende rekursiv neu triggern.
Aktueller TX-Slot laeuft durch, im naechsten Slot wird Station angerufen.

Code: `ui/main_window.py` (1 Attribut), `ui/mw_qso.py` (3 Stellen).
Tests 812 → 816 gruen (+4 in `tests/test_p1_24_pending_click.py`).

---

## ✅ P1.14 + P1.23 (06.05.2026 v0.95.8) — ERLEDIGT (Field-Test bestaetigt)

**P1.14 Station-Wechsel-Bug** (voller Workflow V1→V2→R1→V3 Diagnose +
Plan-V1→V2→R1→V3): 6 Bug-Wurzeln W1-W6 gefixt:
- W1: `start_qso` resetete keine Pendings bei `state != IDLE`
- W2: `_caller_queue` enthielt manuell-gewaehlte Station (Doppel-QSO)
- W3: `_active_qso_targets` wuchs monoton bei Wechseln
- W4/KP6: `_was_cq` State-Machine-extern korrigiert (BEHALTEN)
- W5: TX-Klick silent ignoriert (Statusbar-Toast 3s)
- W6: `auto_hunt._manual_override` wurde NIE zurueckgesetzt
  (Fix in `_on_cancel`, `_on_qso_confirmed`, `_on_qso_timeout`)

Tests 802 → 812 gruen (+10 in `tests/test_p1_14_station_switch.py`).

**P1.23 Status-UI:** Label „Lokale Empfangsqualitaet:" (statt „Lokaler
Empfang:"), Schriftgroessen 11→10px, Sterne 15→13px.

---

## ✅ P1.18 + P1.21 (06.05.2026 v0.95.7) — ERLEDIGT

**P1.18 DT-Drift-Wurzel:** `_DT_OFFSETS["FT8"]` 2.0 → 3.0 (Sync mit
`_WAKE_OFFSETS["FT8"]=2.5` + 0.5s WSJT-X-Protokoll). `dt_corrections.json`
reset. Erwartung: DT zurueck auf -0.1 bis +0.2 wie 23.04.

**P1.21 Sterne-UX-Refactor:** Label `Empfang:`, Gold #FFD700 statt Cyan,
RichText fuer enge Sterne, Score nur SNR (-10/-14/-18/-22 dB).
Mike-Szenario 48×-25 dB jetzt 1 Stern (war 5).

**Field-Test (Mike) ausstehend:**
- DT-Korrektur konvergiert auf ~0.24s (`dt_corrections.json` zeigt klein,
  nicht 1.0)
- Stationen zeigen DT -0.1 bis +0.2
- Sterne reagieren auf Conditions (bei -25 dB sollten 1-2 Sterne sein)
- Sterne-Optik passt zum STATUS-Block (Gold, eng zusammen)

---

## ✅ P1-Bundle1 (06.05.2026 v0.95.6) — ERLEDIGT

5 UI-Cleanups thematisch gebuendelt + voller Diagnose-Workflow + Plan-Workflow.
Tests 777 → 796 gruen (+19). Field-Test ausstehend.

- ✅ **P1.6** Versionsnummer Color #333 → #666
- ✅ **P1.12** NEU-Button (`btn_remeasure`) entfernt (6 Stellen)
- ✅ **P1.15** Statusbar `→ Call | RX: ANT` raus
- ✅ **P1.16** QSO-Panel zeitbasiertes 5-Min-Rolling-Window (statt 40 Zeilen)
- ✅ **P1.19** 5-Sterne-Anzeige `★★★☆☆` ersetzt SNR-Label

**Field-Test (Mike) noch offen:**
- App startet ohne Fehler, Versionsnummer rechts unten lesbar
- KALIBRIEREN funktioniert weiter (statt NEU)
- Bei aktivem QSO: keine `→ Call`-Anzeige
- Nach 5+ Min Funken: alte QSO-Eintraege weg
- Sterne reagieren auf Conditions (sollten zwischen 2-4 schwanken)

---

## ⭐ ALS NÄCHSTES (Priorität)

### ✅ P1.8 — Report-SNR-Bug `_last_snr` statt `msg.snr` (ERLEDIGT 2026-05-08, v0.95.18 + v0.95.21)

Wir sendeten Reports mit schlechteren dB-Werten als wir empfangen.
`_last_snr` wurde fuer jede msg im Slot ueberschrieben → letzte/schwaechste
msg-SNR gewann. v0.95.18 fixte `_process_cq_reply` (qso_state.py:214,229).
**v0.95.21 P1.HUNT-SNR** fixte den Hunt-Pfad: `start_qso(their_snr)` +
Aufrufer (mw_qso, mw_cycle) reichen `msg.snr`/`_candidate.snr` durch.
Plus `advance()` WAIT_REPORT-Branch nutzt `qso.our_snr` (R1-SOLLTE).

### 🟡 P1.11 — `rr73_retries`-Counter shared

Bestehender Bug, NICHT durch P1.10 verschaerft. `qso.rr73_retries` wird
in WAIT_RR73 UND WAIT_73-Hoeflichkeits-Pfad inkrementiert/getestet.
Fix: separates Feld `wait_73_retries` oder Reset bei WAIT_73-Eintritt.

### 🟡 P1.13 — TX-Frequenz-Spinbox-Sync Normal-Modus

Spinbox spiegelt Klick-Frequenz nicht immer korrekt (alt aus 05.05.).

### 🟢 P1.7 — Lokaler Duplikat-Filter ADIF/Logbuch

Folgebug-Risiko aus P1.5: bekannte Station < 5 Min nach RR73 ruft erneut →
zweites QSO + zweiter ADIF-Eintrag. QRZ.com filtert serverseitig, aber
lokal nicht.

### ✅ P1.CACHE-SIMPLE — Diversity/Gain entkoppelt + UX-Cleanup (ERLEDIGT 2026-05-07 v0.95.13)

Mike-Vision: Diversity-Cache (Ratio, 60 Min) und Gain-Cache (6h)
komplett entkoppelt. Keine Modal-Wahl-Dialoge fuer Routine.

**4 Probleme gefixed:**
- A) Cache-Reuse-Toast raus (Mike: „Computer faehrt runter — OK?"-Pattern)
- B) Modal-Wahl-Dialog „Weiter / Neu messen" raus an 2 Stellen
- C) Frische Ratio mit altem Gain ignoriert (Cross-Dependency-Bug)
- D) Volle Pipeline ohne Ankuendigung — jetzt Stale-Acceptance bei Cancel

**Architektur (`_check_diversity_preset` Dispatch):**
- Gain stale → DXTuneDialog auto-start (nur Abbruch). Wenn Ratio fresh:
  nach Gain-OK Cache-Reuse statt Phase 3.
- Gain missing → volle Pipeline (Gain + Ratio).
- Gain fresh + Ratio fresh → Cache-Reuse (still, kein Toast).
- Gain fresh + Ratio stale/missing → stille Auto-Ratio-Messung.

Plus Stale-Acceptance bei `_on_dx_tune_rejected`-Cancel: alte Werte
werden geladen statt Pipeline-Restart. Wenn nichts da: Diversity AUS.

**Voller Workflow:** V1 (4 Probleme) → V2 (12 Lessons) → R1 (8 Pruefauf-
traege beantwortet, kein Veto) → V3 (Compact-fest, 6 Diffs konkret) →
Compact → Code → Final-R1 („Keine KP-Findings, Code ist robust und
entspricht der Mike-Vision. ✅"). Plan-Files: `prompts/p1_cache_simple_v[1-3].md`.

**Tests 852 → 862 gruen** (+10 NEU in `tests/test_p1_cache_simple.py` +
1 invertiert in `test_diversity_cache_reuse.py`). Atomare Commits
`4af2e9e` (Code+Tests, 5 Files +508/-277) + Doku-Commit. APP_VERSION
0.95.12 → 0.95.13.

**Field-Test ausstehend.** Push noch nicht gemacht — Mike-Freigabe
einholen.

### ✅ P1.FORCESEND — btn_advance state-aware + WAIT_73-Branch (ERLEDIGT 2026-05-07 v0.95.12)

Mike-Use-Case 06.05.: bei stuck-Gegenstation manuell RR73 oder 73
senden statt 3-Min-Timeout. Bestehender `btn_advance` wird state-aware:
Label dynamisch (`R+Report` / `RR73` / `73` / `Weiter →`), Enabled in
{WAIT_REPORT, WAIT_RR73, WAIT_73} AND nicht cq_mode AND nicht
diversity_locked. `advance()` neuer WAIT_73-Branch sendet 73 mit
`courtesy_73_sent=True` VOR send (R1-KP-3 asynchron) + idempotent-
Return wenn Auto-Pfad schneller war (Final-R1 Race-Fix).

**Voller Workflow:** V1 → V2 (10 Lessons, Bug-A-Halluzination
eingestanden) → R1 („Plan freigegeben + 5 KP", KP-1 als Halluzination
verworfen) → V3 (Compact-feste Diffs) → Code → Final-R1 („Push
freigegeben mit Vorbehalt: idempotent-Return" → sofort umgesetzt).
Plan-Files: `prompts/p1_forcesend_v[1-3].md`.

**Tests 841 → 852 gruen** (+11 in `tests/test_p1_forcesend.py`).
Atomare Commits `c8bf5bb` (Code+Tests+main.py 5 Files +177/-2) +
Doku-Commit. APP_VERSION 0.95.11 → 0.95.12.

**Lesson:** V1-Halluzination-Risk auch nach 2 Jahren — grep zu eng,
`_on_state_changed`-Hook in mw_qso.py übersehen. V2-Self-Review fing
es ab.

---

### ✅ P1.ANTENNE-COLLAPSE — Antennen-Kachel einklappbar (ERLEDIGT 2026-05-06 v0.95.11)

Mike-Designentscheidung 06.05.: `_AntenneCard` (`ui/control_panel.py:421`)
WIRD einklappbar. DeepSeek hatte abgeraten — Mike überschrieb explizit
(SimpleFT8 ist Hobby-Tool, kein Contest). Hobby-Use-Case: stundenlang
auf einem Band+Modus, Antennen-Status selten gebraucht → wegklappen,
Platz für QSO/RX-Panel. Bei Bedarf aufklappen.

**Architektur:** Header-Row mit Toggle-Button `▼`/`▶` + `_body_widget`-
Container für alle bisherigen Body-Widgets. API `set_collapsed(bool)` /
`is_collapsed()` / `_toggle_collapsed()`. Signal `collapse_changed` NUR
bei User-Klick (Init-Loop-Schutz). `ControlPanel._ant_card` exposed,
forwardet via `antenne_collapse_changed.emit`. `MainWindow` lädt
Initial-State aus Settings + persistiert via Slot.

**Voller Workflow:** V1 → V2 (16 Lessons) → R1 („Plan freigegeben +
5 KP", neue Befunde KP-7 bis KP-11) → V3 (Compact-feste Diffs) → Code →
Final-R1 („Push freigegeben mit optionalem Debounce-Vorbehalt").
Plan-Files: `prompts/p1_antenne_collapse_v[1-3].md`.

**Tests 831 → 841 gruen** (+10 in `tests/test_antenne_card.py`). Atomare
Commits `a0ce1ae` (Code+Tests+main.py 4 Files +209/-9) + Doku-Commit.
APP_VERSION 0.95.10 → 0.95.11.

**Settings-Key:** `antenne_card_collapsed` (bool, default False = aufgeklappt).

---

### ✅ P1.AP-FIX — AP-Lite Kandidaten-Format-Bug (ERLEDIGT 2026-05-06 v0.95.10)

`core/ap_lite.py:126` produzierte 4-Token-Strings (`OWN THEIR LOC SNR`).
FT8 erlaubt nur 3 Tokens → ft8lib `rc=5` → State-1-Rescue scheiterte
IMMER silent seit Implementierung.

**Fix (1 Zeile, KISS):** Locator weglassen, Report-only:
```python
candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")
```
Plus Code-Kommentar Z.121-131 fachlich aktualisiert.

**Voller Workflow:** V1→V2(9 Lessons)→R1("Plan freigegeben")→V3(5
Compact-feste Diffs)→Compact→Code→Final-R1("Push freigegeben").
Plan-Files: `prompts/p1_ap_fix_v[1-3].md`.

**Tests 830 → 831 gruen** (+1 ft8lib_compatible als maschineller
Format-Schutz). Atomare Commits `17b7237` (Code+Tests+main.py) +
Doku-Commit. APP_VERSION 0.95.9 → 0.95.10.

**Field-Test:** post-Kur. Erwartung Rescue-Rate steigt. Notbremse
`AP_LITE_ENABLED=False`.

---

### ✅ P1.AP — AP-Lite synthetische E2E Test-Pipeline (ERLEDIGT 2026-05-06 v0.95.9)

`tests/test_ap_lite_e2e.py` NEU — 14 Tests mit echtem ft8lib-Encoding +
Gaussian-Rauschen. Decken correlate_candidate (clean/noisy/wrong/unrelated),
align_buffers (dt/shape/range), try_rescue E2E (-30dB fail, State-2-Ranking,
APLiteResult), Stats-Counter ab. Tests 816 → 830 gruen.

**Findings dokumentiert:**
- AP-Lite State-1-Generator ist kaputt (4-Token-Bug → P1.AP-FIX)
- Costas-Referenz-Implementation findet auch identische Buffer mit Offset
  (vereinfachte Naeherung, Code-TODO-Kommentar bestaetigt)
- SCORE_THRESHOLD=0.75 wird auch von sauberen RR73-Buffern nicht erreicht
  (~0.42), aber Ranking-Logik funktioniert

---

### ✅ P1.20 — Workflow-Template institutionalisieren (ERLEDIGT 2026-05-06 v0.95.9)

Skill `.claude/skills/ft8_workflow.md` mit explizitem Trigger-Block
erweitert (Mike-Phrasen + Auto-Trigger + Trivial-Klausel). Slash-Command
`.claude/commands/workflow.md` angelegt → `/workflow [bug-name]` startet
Skill direkt. CLAUDE.md beide Pfade verweisen auf Triggers + Slash-Command.

### ✅ P1.17 — RX-SNR-Bias (ERLEDIGT 2026-05-06 v0.95.9)

War Folge von P1.18 DT-Drift. Mike Field-Test bestaetigt: DT bei 0,26s,
SNR-Werte normal, alles gruen.

### ✅ P1.18 / P1.14 / P1.21 — alle ERLEDIGT (v0.95.7-9, Field-Test bestaetigt)

Mike 2026-05-06: „Sterne reagieren, DT-Zeit-Korrektur bei 0,26 Sekunden,
alles gruen, erledigt."

---

## 🗂 ALTE TODO-Eintraege (vor Bundle1 — zu konsolidieren)

### 🟢 P1.12 — NEU-Button im Diversity-Panel entfernen (NEU 2026-05-05)

KALIBRIEREN-Button macht seit v0.94 Phase 2 (Gain) + Phase 3 (Diversity)
automatisch. Der NEU-Button (`btn_remeasure` in `ui/control_panel.py:516`)
ist redundant — er macht nur Phase 3 alleine, was im Hobby-Funker-Alltag
selten gebraucht wird.

**Aufgabe:**
- `ui/control_panel.py:516-525` — `btn_remeasure` löschen
- `ui/control_panel.py:1023-1024` — `remeasure_clicked` Signal-Connect raus
- `ui/main_window.py:530` — Connect zu `_on_diversity_remeasure` raus
- `ui/mw_radio.py:985-997` — `_on_diversity_remeasure` Methode löschen

**Aufwand:** ~10 Zeilen, KISS, kein Workflow nötig.

---

### 🔴 P1.14 — Station-Wechsel via Klick funktioniert nicht (NEU 2026-05-06)

**Symptom (Field-Test Mike, 22:01 + 22:09 UTC):**

Mehrere kaputte Pfade — gemeinsame Wurzel: Klick auf neue Station im
RX-Panel waehrend aktiver TX bricht den laufenden TX nicht ab.

**Pfad 1 — nach Hunt-Timeout:**
- Hunt UN0GY 6× ohne Antwort → `× UN0GY — Timeout`
- Doppelklick MM8FKF (RX-Panel-Markierung) → **NICHTS**
- App sendet weiter CQ statt MM8FKF zu rufen

**Pfad 2 — waehrend laufendem CQ-Modus:**
- CQ_CALLING aktiv (CQ DA1MHH JO31)
- Doppelklick auf andere CQ-rufende Station → **NICHTS**
- Mike muss erst manuell HALT druecken, dann Station anwaehlen

**Pfad 3 — waehrend laufendem Hunt:**
- TX_CALL / WAIT_REPORT aktiv mit Station A
- Mike entscheidet sich um, klickt Station B → **NICHTS**

**Erwartetes Verhalten in ALLEN Pfaden:**
- Klick auf neue Station bricht aktuellen Zustand sauber ab
- (CQ-Modus / Hunt-QSO / Timeout)
- Bei naechstem TX-Slot wird neue Station angerufen

**Code-Pfad zu pruefen:**
- `ui/mw_qso.py:_on_station_clicked` (Z.65+) — hat zwar
  `_cq_was_active`-Logik aber Hunt-Abbruch fehlt
- `core/qso_state.py:start_qso` (Z.236+) — `state not in (IDLE, CQ_WAIT)`
  Branch wird vermutlich gar nicht erreicht
- RX-Panel Click-Handler — wird Doppelklick im aktiven QSO ueberhaupt
  weitergegeben?

**Diagnose-Schritt 1:** Logging hinzufuegen in `_on_station_clicked`
Eingang + RX-Panel-Click-Emit. Pruefen ob Event ueberhaupt durchkommt.

**Workflow:** voller V1→V2→R1→V3 — beruehrt State-Machine + UI-Click-
Handling + Encoder-Abort, mehrere Akzeptanzkriterien.

---

### 🔴 P1.18 — DT-Korrektur konvergiert nicht (Wurzel-Bug, 2026-05-06)

**Wurzel:** `core/ntp_time.py:36` `_MAX_CORR["FT8"] = 1.0` — Limit
zu eng. Mike's FlexRadio + Hardware-Setup braucht **+1.2s** Korrektur,
clamp in Z.213 reduziert auf 1.0s → DT-Korrektur „stuck" bei 1.0s.

**Beweis im Log:**
```
Feinkorrektur: Median=+0.240s ×0.7 → Δ+0.168s → Korrektur=+1.168s
Neue Messphase (Korrektur=+1.000s)  ← clamped!
Feinkorrektur: ... → Korrektur=+1.220s
Neue Messphase (Korrektur=+1.000s)  ← clamped!
```

Jede Feinkorrektur erreicht ~+1.18-1.22s, wird auf +1.000s zurueck-
geclampt. **Konvergenz unmoeglich.**

**Konsequenz — vermutlich Wurzel von P1.17 + P1.8:**
- DT-Korrektur 200ms zu klein
- Decoder samplet mit 200ms Versatz
- FT8-Decoder hochempfindlich auf Timing → alle SNR-Werte mehrere
  dB reduziert → P1.17 (alle Stationen -17 bis -25)
- Reports an Gegenstationen ebenfalls pessimistisch → P1.8

**Fix (1 Zeile):**
```python
_MAX_CORR = {"FT8": 2.0, "FT4": 1.0, "FT2": 0.5}
```

oder `_MAX_CORR["FT8"] = MAX_CORRECTION` (= 2.0, schon definiert Z.31).

**Plus:** `~/.simpleft8/dt_corrections.json` zuruecksetzen (alle Werte
1.0 sind clamped, neu konvergieren lassen).

**Aufwand:** 5 Min Code + Field-Test + Vergleich der SNR-Werte vorher/
nachher. Falls SNR um >3 dB besser → P1.17 + P1.8 gleich miterledigt.

**Workflow:** voller V1→V2→R1→V3 — kritischer Wurzel-Fix mit weit-
reichenden Konsequenzen, mehrere Akzeptanzkriterien (SNR-Verbesserung,
DT-Konvergenz, RX-Panel sauber).

---

### 🟡 P1.17 — RX-SNR-Bias verdaechtig (alle Stationen -17 bis -25 dB) (NEU 2026-05-06)
**Vermutlich GELOEST durch P1.18 — Field-Test nach P1.18-Fix.**

**Symptom (Field-Test Mike 22:09 UTC):**
22 Stationen im RX-Panel, ALLE zwischen -17 und -25 dB. Selbst nahe
Stationen schwach:
- England 415km → -21
- England 630km → -23
- Polen 846km → -18
- Bulgarien 1700km → -17

Erwartung 40m FT8 Abend: Mix aus -5 (gut) bis -24 (Decode-Schwelle).
Komplettes Fehlen besserer Werte ist verdaechtig.

**Mike's Argument:** externe Software-Vergleich (SDR-Control / IC-7300)
nicht moeglich weil andere SNR-Berechnung. Wir muessen selbst pruefen.

**Mike's Trost:** falls systematischer Bias vorliegt — **Diagramme
(Diversity vs Normal) bleiben aussagekraeftig** weil RELATIVE Vergleiche.
Aber: ABSOLUTE Werte (gemeldete Reports an Gegenstationen, Reichweite-
Stats) sind dann verfaelscht.

**Diagnose-Optionen:**

1. **PSK-Reporter-Asymmetrie:** App empfaengt PSK-Reporter-Daten
   (was andere fuer DA1MHH reporten). Vergleichen mit unseren RX-Werten
   fuer dieselben Stationen. Wenn andere uns mit -10 hoeren und wir
   sie mit -22 → asymmetrischer RX-Bias.
2. **AGC-Pegel im Log pruefen:** RMS-Ziel ist -12 dBFS. Wenn AGC
   saturiert (zu viel Verstaerkung) wird Signal vorm Decoder platt.
3. **Decoder-SNR-Berechnung Code-Review:** wo wird `msg.snr` berechnet?
   ft8lib oder eigener Code? Gibt es einen Offset der subtrahiert wird?
4. **Vergleich Diversity ANT2 (Regenrinne):** ANT2 ist viel schwaecher
   als ANT1, sollte 10-15 dB schlechter sein. Wenn ANT1 und ANT2
   aehnliche Werte zeigen → Verstaerker-/AGC-Bug.

**Auswirkung wenn Bug:**
- Reports an Gegenstationen 5-10 dB zu pessimistisch
- Reichweite-Statistiken systematisch zu niedrig
- Diversity-Vergleich bleibt valide (relativ)

**Aufwand:** Diagnose 1-2h. Falls Bug bestaetigt: Fix je nach Wurzel.

---

### 🟢 P1.20 — Workflow-Template als Standard-Pattern in Skill (NEU 2026-05-06)

**Idee Mike:** der heutige Bundle1-Workflow war besonders sauber. Das
konkrete Template als Standard-Pattern in `.claude/skills/ft8_workflow.md`
festhalten damit Claude immer gleich-strukturiert vorgeht.

**Was heute gut war (zu institutionalisieren):**

1. **Compact-Strategie:** nach V2, vor R1 — Token-effizient + Persistenz
2. **V1 = Code-Verifikation FIRST:** alle Datei:Zeile-Refs **bevor**
   Diagnose geschrieben wird (verhindert Spekulation)
3. **V2 = Tabelle der V1-Luecken:** explizit dokumentiert was V1 verpasst,
   nicht nur „erweitert"
4. **R1-Pruefauftraege konkret:** mit Nummerierung 6.1, 6.2 etc., nicht
   „schau mal drueber"
5. **Bundle-Strategie:** mehrere kleine Fixes als gemeinsamer Workflow
   wenn thematisch zusammenhaengend (z.B. UI-Cleanup)
6. **Pre-Compact-Check als eigener Task:** Files-Liste verifizieren,
   nichts darf verloren gehen
7. **Akzeptanzkriterien getrennt:** Code-Akzeptanz vs Field-Test als
   zwei Listen
8. **Workflow-Plan numeriert** mit Status-Markern (✅/→/Mike-Freigabe)

**Aufgabe:**
- `.claude/skills/ft8_workflow.md` erweitern um „Workflow-Template"-Sektion
- Bundle1 + P1.10 als Beispiele referenzieren
- Klare Vorgabe: V1 IMMER mit Code-Verifikation, V2 IMMER mit Luecken-
  Tabelle, R1 IMMER mit nummerierten Pruefauftraegen
- Compact-Trigger-Punkt explizit benennen
- Bundle-Kriterium: wann sammeln, wann separat?

**Trigger:** Nach Bundle1-Abschluss (heute Nacht oder morgen) — dann
haben wir 2 vollstaendige Workflow-Beispiele zum Destillieren.

**Aufwand:** 30 Min Skill-Erweiterung, KISS, kein eigener Workflow.

---

### 🟢 P1.19 — Lokale Conditions als Sterne-Anzeige (NEU 2026-05-06)

**Idee Mike:** SNR-Wert „-25 dB" im Status ist fuer User nicht intuitiv —
auch Mike kann nach 4 Wochen nicht spontan einordnen. Ersetzen durch
**5-Sterne-Anzeige** „Lokale Conditions" mit dunkler Outline fuer
inaktive Sterne (sichtbare Skala).

**Wichtige Abgrenzung:**
- **Bandanzeige oben (gruen/gelb/rot):** GLOBAL aus PSK-Reporter
- **Lokale Conditions (NEU):** was DU gerade empfaengst (Antenne, lokales
  Rauschen, lokale Tageszeit-Skip)
- Beide ergaenzen sich (Band gruen + lokal rot = Hardware-Problem!)

**Berechnung (KISS, 2 Faktoren):**

| Sterne | Stationen (Aging-Fenster) | Median-SNR der besten Haelfte |
|---|---|---|
| ★★★★★ | 25+ | > -12 dB |
| ★★★★☆ | 15-24 | > -15 dB |
| ★★★☆☆ | 8-14 | > -18 dB |
| ★★☆☆☆ | 3-7 | > -22 dB |
| ★☆☆☆☆ | < 3 | egal (Antenne checken) |

Schwellen werden ODER-verknuepft (eines reicht zum Hochstufen).

**UI:**
- Aktive Sterne: Neon-Cyan (#00DDFF) mit weichem Glow (passt zum Theme)
- Inaktive Sterne: dunkle Outline (#3a3a4e) — sichtbar, klare Skala
- Tooltip beim Hover: „12 Stationen, Median -16 dB"
- Position: ersetzt aktuellen `SNR: -25 dB` Eintrag im Status-Block

**Intern:** SNR-Wert weiter berechnen (Reports, DT-Korrektur, Statistik)
— nur die UI-Anzeige aendert sich.

**Wichtige Reihenfolge:** **erst P1.18 fixen** (DT-Clamp). Sonst zeigt
die Sterne-Skala mit dem aktuellen Bias systematisch zu schlechte
Werte.

**Aufwand:** ~30 Min Implementation (Berechnungs-Funktion + UI-Widget +
Theme-Styling). Voller Workflow nicht zwingend — KISS-Feature, lokal.

---

### 🟢 P1.16 — QSO-Panel-Log: 5-Min-Rolling-Window (NEU 2026-05-06)

**Symptom:** QSO-Panel-Log fuellt sich Eintrag fuer Eintrag, nach laengerer
Session unleserlich/zugemuellt. Mike's Beobachtung 22:07 UTC: 9 Minuten
Verlauf sichtbar, aelter Material ist nicht mehr relevant.

**Mike's Idee (KISS):** alle Eintraege aelter als 5 Min automatisch oben
loeschen. Juengere Eintraege ruetschen nach oben. So bleibt der Last-5-Min-
Verlauf immer sichtbar, ohne manuelles Aufraeumen.

**Code-Pfad:** `ui/qso_panel.py` — alle `add_info` / `add_rx` / `add_tx` /
`add_qso_complete` / Trenn-Linien zu Eintraegen mit Timestamp speichern.
Periodisch (z.B. via QTimer alle 30s ODER bei jedem `add_*`) Eintraege
mit `now - timestamp > 300s` entfernen.

**Edge Cases:**
- Trenn-Linien („─────"): nicht standalone loeschen, sondern mit
  zugehoerigem QSO-Block
- „CQ-Modus laeuft weiter..." sollte erhalten bleiben wenn QSO im
  Window ist
- Scroll-Position: User-Scroll respektieren (kein Auto-Reset bei Cleanup)

**Aufwand:** ~30 Zeilen, moderates Refactoring (zentrale add-Funktion +
Timestamp-Tracking + Cleanup-Timer). Voller V1→V2→R1→V3 nicht zwingend
(lokal in qso_panel.py, single Akzeptanzkriterium), aber Edge-Cases
brauchen Sorgfalt.

---

### 🟢 P1.15 — Statusbar-Anzeige „→ Call | RX: ANT" entfernen (NEU 2026-05-06)

Mike: *„die macht mich irre"*. Statusbar-Eintrag unten links zeigt
`→ SP5LST | RX: ANT1` — wird nicht gebraucht, soll komplett weg.

**Code-Pfad:** `ui/main_window.py` Statusbar-Update — Mike's Active-QSO-
Anzeige in Statusbar. Wahrscheinlich `_update_statusbar()` oder
`statusBar().showMessage()`.

**Aufwand:** ~5 Zeilen, KISS, kein Workflow.

---

### 🟡 P1.13 — TX-Frequenz-Spinbox-Sync im Normal-Modus (NEU 2026-05-05)

**Symptom:** Wenn User im Normal-Modus auf eine Station klickt (Hunt),
wird `encoder.audio_freq_hz` auf die Station-Frequenz gesetzt + Histogramm-
Marker (gelb) zeigt korrekt die neue Freq. **Aber die TX-Freq-Spinbox
in der UI zeigt weiterhin den alten manuell gesetzten Wert.**

→ User sieht TX-Freq-Spinbox=1150 Hz, Histogramm-Marker=800 Hz.

Das hatte heute (05.05.) bei der Diagnose des „Frequenz-Wechsel-Bugs"
stundenlang Verwirrung verursacht — der vermeintliche Bug war ein
UI-Sync-Issue zwischen Spinbox und Encoder.

**Code-Pfad:** `ui/mw_qso.py:_on_station_clicked` setzt
`encoder.tx_even` aber NICHT `control_panel._tx_freq_spin.setValue()`.
Ähnlich `_on_send_message` für CQ-Reply-Pfad in Diversity-Modus.

**Fix-Idee (KISS):** in `_on_station_clicked` nach `start_qso` die
Spinbox synchronisieren:
```python
if self._rx_mode == "normal" and msg.freq_hz:
    self.encoder.audio_freq_hz = msg.freq_hz
    spin = self.control_panel._tx_freq_spin
    spin.blockSignals(True)
    spin.setValue(msg.freq_hz)
    spin.blockSignals(False)
```

**Aufwand:** ~15 Zeilen (Hunt-Pfad + CQ-Reply-Pfad). Voller V1→V2→R1→V3
NICHT nötig (single Akzeptanzkriterium, lokaler Patch in einer Methode).

---

### ✅ P1.5 — CQ-Reply-Recognition-Bug (ERLEDIGT 2026-05-05, v0.95.2)

5-Min-Sperre `_WORKED_BLOCK_SECS = 300` an 3 Block-Stellen entfernt.
Voller V1→V2→R1→V3 Diagnose + Plan, R1 zwei Mal bestaetigt ohne
Halluzinationen. Tests 756 → 759 gruen. Atomarer Commit `43dd062`.
Field-Test bestaetigt: 4 QSOs in Folge, Warteliste-Pop ✓. Siehe
`HISTORY.md` v0.95.2.

---

### ✅ P1.9 — First-Reply-Lost-Bug (ERLEDIGT 2026-05-05, v0.95.3)

Decoder-Encoder-Timing-Race behoben. Atomarer Commit `20c7fe7` (Code+Tests,
+282/-29 in 7 Files) + Doku-Commit. Voller V1→V2(12 Findings A-L)→R1(6
Pruefauftraege KORREKT)→V3 Plan-Workflow. Fix-Kombination:
- `core/decoder.py:138` — `_WAKE_OFFSETS["FT8"]` 1.5 → 2.5 (SNR<0.1 dB R1)
- `core/encoder.py` — `request_replace` API + Loop + `tx_finished.emit`
  Encode-Fehler-Pfad (V2 FINDING-F)
- `core/qso_state.py` — Signal `try_replace_pending_tx` + Defense-in-Depth
  in `_send_cq()`
- `ui/mw_qso.py` — `_on_try_replace_pending_tx` Slot (V2 FINDING-A/B/C/D)
- `ui/main_window.py:543` — Connect

Tests 759 → 764 gruen (+5: 3 Encoder API + 2 SM Logik). Siehe HISTORY.md
v0.95.3. **🟡 Field-Test bei Mike ausstehend.**

---

### ✅ P1.10 — End-of-QSO Icom-73-Loop (ERLEDIGT 2026-05-05, v0.95.4)

**Code-Commit:** `9783583` (Code+Tests+Workflow-Files, 13 Files,
+3439/-14) + Doku-Commit.

**Field-Test:** ✅ BESTAETIGT 16:59 UTC mit EA2BHE Spanien (IN83) — nach
unserem Courtesy-73 KEIN weiteres 73 von Gegenstation, Auto-Sequence
sauber gestoppt. IC-7300/DA1TST Test-Setup ist Quirk (enger getakteter
Decoder), kein SimpleFT8-Bug.

**Bug-Wurzel:** IC-7300 (DA1TST) Auto-Sequence wartet auf abschliessendes
Hoeflichkeits-73 von uns. SimpleFT8 sendete bisher kein Courtesy-73 →
IC-7300 retried 5× `73`. Andere FT8-Apps (WSJT-X, JTDX, MSHV) senden
Courtesy-73 als Funkalltag-Standard.

**Fix:** neuer State `TX_73_COURTESY` + Feld `qso.courtesy_73_sent`
(max 1× pro QSO), Branch in WAIT_73 (`qso_state.py:582-597`) +
on_message_sent + 3-Min-Timeout-Ausschluss + mw_qso state-abhaengig
(Panel-Info nur bei CQ-Reply, NICHT bei Courtesy-73).

**Workflow:** voller V1→V2(8 V1-Luecken)→R1(4 KP + 3 Findings)→V3
Diagnose + Cross-Check Zweit-KI + V1→V2(6 Plan-V1-Luecken)→R1(3 wichtige
+ 3 optionale Findings)→V3 Plan. Tests 764 → 777 gruen (+13 neu, 2
angepasst).

---

### 🟡 P1.11 — `rr73_retries`-Counter shared (NEU 2026-05-05, aus Plan-R1 F1)

**Bestehender Bug, NICHT durch P1.10 verschaerft.**

`qso.rr73_retries` wird in WAIT_RR73 (`qso_state.py:346`) UND in
WAIT_73-Hoeflichkeits-Pfad (`qso_state.py:589-590`) inkrementiert/
getestet. Wenn QSO viele WAIT_RR73-Retries hatte (z.B. 2 von 3),
bleibt fuer WAIT_73-R-Report-Hoeflichkeit nichts uebrig.

**Fix-Idee:** separates Feld `wait_73_retries: int = 0` in QSOData
oder Reset bei WAIT_73-Eintritt (`_set_state` Branch).

**Aufwand:** ~1 Stunde, KISS.

**Workflow:** trivialer Bugfix mit klarem Code-Pfad — V1 reicht
laut WORKFLOW.md (single Akzeptanzkriterium).

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

### 🟡 P1.8 — Report-SNR-Bug: `_last_snr` statt `msg.snr` (NEU 2026-05-05)

**Symptom (Field-Test 09:35-:44):** wir senden Reports mit deutlich
schlechteren dB-Werten als die Gegenstation uns gibt:

| QSO | Wir senden | Gegenstation an uns | Diff |
|---|---|---|---|
| SP6AXW | -24 | R-17 | 7 dB |
| DA1TST | -23 | R+19 | **42 dB** |

42 dB-Differenz ist **zu gross** fuer reine Hardware-Asymmetrie (Mike's
ANT1=Kelemen-Dipol vs. Icom-Antenne). Mike's Frage: *„wir senden raport
mit wesendlich schlechtere wert als wir ihn empfangen?"*

**Code-Wurzel-Verdacht:** `core/qso_state.py:218` und `:233` in
`_process_cq_reply`:
```python
report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
```

`self._last_snr` wird in `ui/mw_cycle.py:751` fuer **jede** dekodierte
Message gesetzt:
```python
self.qso_sm.set_last_snr(msg.snr)
```

Decoder emit'd messages in **dekodierter Reihenfolge** (decoder.py:258-267,
nach `_decode_with_subtraction` → starkes Signal zuerst, schwaches zuletzt).
Der LAST-emit-msg setzt `_last_snr` final → das ist die SCHWAECHSTE
Station im Slot, nicht die antwortende.

**Beispiel:** im :39:00-Slot werden 5 Stationen dekodiert (HA1BF -16,
GB8VED -15, EC3A -18, DA1TST **-10**, schwache Russland-Station -23).
`_last_snr=-23` zur Zeit `_process_cq_reply` laeuft → Report fuer DA1TST
ist `-23` statt korrekt `-10`. **42 dB Bug erklaert!**

**Live-Beweis 2026-05-05 21:58 UTC (Mike-Screenshot):**
- RX-Panel: UN0GY MN83 mit dB=-16 (im :57:57-Slot dekodiert)
- TX-Sequenz: `21:58:15 UN0GY DA1MHH -23` ← falscher Report!
- Differenz 7 dB — UN0GY hat -16, wir senden -23
- Slot enthielt ~20 Stationen, schwaechste war TL8BNW JN34 mit -23
- → `_last_snr=-23` bei `_process_cq_reply` → Bug bestaetigt

**Fix:** in `_process_cq_reply` (Z. 218 + 233) `self._last_snr` durch
`msg.snr` ersetzen (msg ist der DA1TST-Reply). Analog im
`tx_slot_for_partner.emit(msg)`-Pfad checken.

**Plus:** auch in `start_qso()` (Z. 263) nutzt `_last_snr` — das ist OK
weil bei Hunt der User klickt und KEIN Slot-spezifisches msg vorliegt.

**Workflow:** voller V1→V2→R1→V3. Nicht trivial — der Pfad geht durch
die State-Machine, mehrere Stellen pruefen. **R1 muss bestaetigen ob
`msg.snr` an allen relevanten Stellen die richtige Quelle ist.**

**Prio:** mittel — kosmetisch wirkend, aber FT8-Reciprocity-Praxis ist
wichtig (echte Stationen verlassen sich auf akkurate Reports). Nicht
blockierend, aber sollte NACH P1.9 (Anfang-Bug) und P1.10 (Ende-Bug) kommen.

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

### Andere offene TODOs (Bereinigt 07.05.2026)
- [ ] Even/Odd dedizierter Timer — unabhängig vom Decoder-Thread (FT2 kritisch)
- [ ] Gain-Bias beheben — Normal-Modus Gain-Messung wenn Stats aktiv erzwingen
- [ ] CQ-Zusammenfassung RX-Liste — DeepSeek-Idee: ins QSO-Panel verschieben oder ganz raus
- [ ] Tertile-Analyse Statistik — kein Datencropping, alle Werte in 3 Drittel
- [x] **AP-Lite Test-Pipeline** — ✅ ERLEDIGT v0.95.9 (P1.AP synthetische E2E)
      + v0.95.10 (P1.AP-FIX 4-Token-Bug)
- [ ] Per-Station DT-Offset TX — encoder._station_dt_offset (nach mehr Feldtest-Daten)
- [ ] IC-7300 Fork — TARGET_TX_OFFSET dort separat messen! (eigener Branch)
- [x] **Warteliste-Screenshot** — ✅ ERLEDIGT (DL3AQJ-Freigabe + Einbau)
- [x] **DT-Korrektur konvergiert nicht** — ✅ ERLEDIGT v0.95.7 (P1.18 Wurzel-
      Fix `_DT_OFFSETS["FT8"]=3.0` Sync mit Wake-Offset)
- [ ] **NEU 26.04.:** TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker (Bug, noch nicht reproduzierbar)
- [x] **NEU 07.05. → ✅ ERLEDIGT 08.05.:** P2.ADIF-ARCHIVE Standalone-
      Helper `tools/adif_archive.py` fuer Jahresarchive aus
      `adif/hochgeladen/`. Voller Workflow durchgezogen.

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
