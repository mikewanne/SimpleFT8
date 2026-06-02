# SimpleFT8 TODO — Stand 28.05.2026 (v0.98.42)

> **✅ P160 (v0.98.42):** Rechtsklick-TUNE-Override bietet jetzt 5/10/15/20s
> (5s ergänzt für Dummyload-Schutz, Mike-Wunsch). DeepSeek-R1 GO. Details →
> HISTORY v0.98.42, FEATURES §16.

> **Strategie (Mike 28.05.):** ALLE Baustellen inkl. Multiband fertigstellen,
> DANN für Icom forken (nicht parallel). Icom-Abstraktion ist durch P121
> bereits sauber (Stubs da, Diversity/VITA-49 gated) — der echte Icom-Aufwand
> (CI-V CAT + Soundkarten-Audio + PTT) braucht aber die Hardware vor Ort.

> **Diese Datei = Backlog (aktiv-offen + frisch erledigt).**
> Vollständige Historie aller Änderungen: **HISTORY.md** (nur anhängen).
> Funktions-Doku: **FEATURES.md** (Pattern-Familien, Architektur).
> Aktueller Session-Stand: **HANDOFF.md**.

---

# 🟡 P165 Phase 2 — Auto-Hunt DX-Scoring Verfeinerungen (02.06.2026, optional)

DX-Scoring (Seltenheit > Distanz > Signal) ist live ab v0.98.51 (Phase 1).
Offene optionale Verbesserungen — erst nach Field-Test entscheiden ob nötig:

- **Sonderpräfix-Auflösung** (Restrisiko): `core/geo._PREFIX_MAP` führt FT5
  (Kerguelen, Most-Wanted #8), FO/A (Clipperton) u.a. als Mutterland
  (Frankreich) → werden fälschlich als „häufig" eingestuft und landen unten.
  Fix bräuchte eine erweiterte Präfix→Entity-Tabelle. Normale DX alle korrekt
  → niedrige Prio, die Exoten bleiben vorerst Handarbeit.
- **Clublog Most-Wanted-Bonus** (verworfen für Phase 1, ggf. später): eine
  kleine statische Top-N-Entity-Liste als zusätzliche Scoring-Dimension.
  DeepSeek + Claude einig: persönliche Seltenheit reicht für ein Hobby-Tool,
  Most-Wanted veraltet + braucht Präfix→Entity-Mapping (s.o. lückenhaft).
- **Kontinent-Stufe**: bewusst weggelassen — Land-Seltenheit deckt sie ab
  (neuer Kontinent = lauter ATNO-Länder). Nur falls Field-Test zeigt dass
  feinere WAC-Steuerung gewünscht ist.
- **`_RARITY_UNKNOWN` justieren** (aktuell 2/Mitte): falls Field-Log zeigt dass
  Garbage-/„?"-Decodes zu oft hochkommen → auf 3 anheben (1-Zeilen-Tweak,
  `core/auto_hunt.py`).

---

# ⚪ Bug 2 GESCHLOSSEN-ohne-Fix (01.06.2026) — seltene Doppel-RX-Zeile im QSO-Log

Mike-Field (Screenshot LZ100LZ): zweimal exakt dieselbe Empfangs-Zeile
`12:35:30 ← Empf. DA1MHH LZ100LZ R-07` (gleicher Text, gleiche Sekunde). Sehr
selten. (Erst-Diagnose „RX+TX gleiche Zeit" war FALSCH — Mike korrigiert: beide
sind „← Empf.".)

**DeepSeek-Workflow-Diagnose:** Auf dem normalen Decode-Weg dürfte das gar nicht
entstehen — Decoder dedupliziert intern (`seen`-Set, decoder.py:445/494),
1 Decode/Slot (`_decode_busy`-Guard), nur ANT1 wird dekodiert (ANT2 =
Diversity-Messung, geht NICHT in `feed_audio`), 1 Signal-Verbindung
(mw_radio.py:61), 1 `add_rx`-Call. → seltene Timing-Race, statisch nicht
lokalisierbar.

**Wichtig (DeepSeek-Catch):** der Doppel-Decode stößt theoretisch auch
`on_message_received` (State-Machine) doppelt an → es ist NICHT „nur Anzeige".

**Verifiziert HARMLOS → bewusst NICHT gefixt (Mike-Entscheidung, KISS):**
- Logbuch korrekt: P1.7-Duplikat-Filter (`mw_qso.py:601-610`, 5-Min-Fenster)
  blockt einen zweiten ADIF-Eintrag; `qso_log._worked` ist idempotent (Set).
- Keine Doppel-Sendung (Screenshot: 1× RR73, 1× „✓ komplett").
- Einziger Effekt: seltene kosmetische Doppel-Zeile in der Live-Anzeige.
- Fix würde an nicht-reproduzierbarem Race rumdoktorn → Risiko > Nutzen.

**Falls es doch häufiger wird:** robuster Fix = Dedup in `on_message_decoded`
(Key `caller+raw+slot_start_ts`) VOR `add_rx` + `on_message_received` (schützt
Anzeige UND State-Machine) + Debug-Log. Diagnose-Prompt liegt in
`prompts/bug2_duplicate_rx_v2.md`.

---

# ✅ P159 ERLEDIGT (v0.98.41, 28.05.2026) — SWR-Clamp-1.0 aus Median filtern

Mike-Field-Bug: Bandsperre nach TUNE bewertete falsche SWR (mal „1.0"
freigegeben, mal „28.5" gesperrt — echt 2.4). Root Cause field-belegt: der
FlexRadio-Sensor liefert bei fehlendem Träger (FWDPWR≈0) exakt 1.0 (Clamp,
keine Messung); diese 1.0-Werte verfälschten den Median in
`_compute_match_swr` (14 echte 2.5-2.6 + 19 Clamp 1.0 → Median 1.0). Echte
KW-SWR sind nie exakt 1.0 (Mike-Praxis + Web). Fix KISS: `swr > 1.0`-Filter
im Median-Fenster (Median nach oben = sichere Richtung). DeepSeek-R1 GO.
**Hardware-Sicherheit 6. Iteration** (P53/P76-A/P142/P153/P154/P159). Tests
+9 (2183). **Details → HISTORY.md v0.98.41, Funktionsweise → FEATURES.md §12.**
Field-Test pending. **28.5-Fall GEKLÄRT (kein Code-Bug):** kam aus dem
Live-SWR-Watchdog während TX (mw_tx.py:882), NICHT aus dem TUNE-Median —
Mike hatte `auto_tune_on_band_change` DEAKTIVIERT → Band nie getunt → Auto-Hunt
ging roh auf TX → 28.5 → Watchdog sperrt. Lösung: Setting aktivieren (kein
Code). Alle 3 TUNE-Pfade nehmen `tune_duration_s` aus den Settings (kein
hartcodierter Wert) — Dropdown max. 15s; bei Bedarf später um 20s erweitern.

---

# ✅ P157 ERLEDIGT (v0.98.40, 28.05.2026) — RX-Liste Aging-Bug (drei Ursachen)

Beide Mike-Hypothesen bestätigt + ein dritter Bug (DeepSeek). **Bug 1
(Hauptursache, Hypothese B):** `remove_stale()` lief nur bei Decodes → bei
stillem Band keine Alterung → tote Stationen klebten. **Bug 2 (Hypothese A):**
`_slot_start_ts` (UTC-Spalte + Sortierung) wurde beim Wiederhören nicht
aktualisiert → Erst-Sichtung angezeigt. **Bug 3:** `_last_heard` nur bei
Inhalts-Änderung gesetzt → aktive Station altert raus. Fix KISS (Variante b):
`station_accumulator` setzt Zeitstempel im „bekannt"-Zweig IMMER; `mw_cycle`
neuer Aging-Block für leere Slots + DRY-Helper `_rebuild_rx_table`. DeepSeek
Design-R1 + Final-R1 PUSH FREIGEBEN. Tests +12 (2174). **Details → HISTORY.md
v0.98.40, Funktionsweise → FEATURES.md §15.** Field-Test pending.

---

# ✅ P158 — Wartende Station ins Auto-Hunt-QSO einschieben (ERLEDIGT v0.98.44, 29.05.2026)

> **ERLEDIGT v0.98.44** — voller Workflow, DeepSeek-v4-pro Design-R1 (0 Blocker)
> + Final-R1 (PUSH FREIGEBEN). Umsetzung: HISTORY.md 2026-05-29 v0.98.44,
> FEATURES.md §17 (Datenfluss), Memory `project_p158_done`. Tests 2169→2196.
> **FlexRadio Field-Test pending.** Spec unten archiviert.

**Szenario (Mike-Field, Screenshot 06:28):** Auto-Hunt fährt ein QSO mit
Station A (EB3JT). Mitten drin ruft eine FREMDE Station B (F5MYK) UNS an →
im QSO-Log-Fenster springt eine Zeile dazwischen: „← Empf. DA1MHH F5MYK IN97".
Heute geht B verloren (Auto-Hunt fixiert auf A).

**Mike-Design-Philosophie (Schlüssel):**
- **RX-Liste = AKTIV** → da jagt/filtert Mike gezielt Stationen.
- **QSO-Fenster = PASSIV/höflich** → da antwortet Mike wer *ihn* ruft.
→ Deshalb gehört der Klick ins **QSO-Log-Fenster**, NICHT in die RX-Liste.

**Mechanik (complete-then-call, NICHT cancel):**
1. Die „← Empf."-Zeile im QSO-Log wird anklickbar — ABER nur die, in denen
   ein FREMDER Call UNS ruft (`<call> DA1MHH <grid>`) UND Auto-Hunt gerade ein
   anderes QSO fährt. CQs / fremde QSOs bleiben toter Text (kein Fehlklick).
2. Klick → B in einen **Auto-Hunt-eigenen Puffer** (`_insert_pending_call`).
   NICHT der RX-Klick-Puffer `_pending_station_click` (P1.24, der bricht ab),
   NICHT die CQ-Caller-Queue.
3. Das laufende A-QSO läuft **ZU ENDE** (kein Abbruch).
4. Nach A-Ende (Erfolg ODER Timeout): Auto-Hunt pausiert (`_manual_override`),
   B wird gerufen wie ein manuell gestartetes QSO.
5. **Nach B-QSO: Auto-Hunt läuft AUTOMATISCH weiter** (Auto-Resume — DeepSeek+
   Claude einig; entspricht bestehendem `on_manual_qso_end`-Muster; Klick=
   frischer Präsenzbeweis, 10-Min-Cap läuft weiter, Bot-Tarn-Schutz gewahrt).

**Technik (DeepSeek):** QSO-Log `log_view` ist read-only QTextEdit → klickbar
via **HTML-Anchor** `<a href="hunt_insert">…</a>` + `anchorClicked(QUrl)` (KEIN
Cursor-Position-Parsing). Einschub-Zeile dezent blau/unterstrichen. Signal
`hunt_insert_station(call, grid)` von qso_panel → mw_cycle setzt Puffer.

**Edge-Cases (DeepSeek, alle via P122-Defer-Mechanik):** A→Timeout (Puffer
triggert trotzdem); B gibt auf (Pech, kein Schaden); mehrere Anrufer (letzter
Klick gewinnt, keine Liste); HALT/SWR-Sperre während Wartezeit (Puffer
verworfen, kein TX); deferred Auto-Hunt-Stop vor B-Start (Stop vollzogen,
Puffer weg).

**Aufwand:** schlank — 1 Datenstruktur `_insert_pending_call` in auto_hunt +
Signal + klickbare Log-Zeile + Trigger in QSO-Ende-Pfaden (Success+Timeout).
Severity ⚪ Feature, **Schreibtisch-tauglich** (pure State-Machine + UI, kein
TUNE/PA). **NÄCHSTER PUNKT nach dem Compact — voller Workflow.**

**Optional offen (Mike-Frage):** Einschub-Zeile zusätzlich optisch
hervorheben/blinken, damit im Eifer nicht übersehen? → in V1 mitentscheiden.

---

# 🟢 LAUFEND — Field-Test pending

## P156 — Netto-Leistung dezent anzeigen (v0.98.39, 28.05.2026)

**Was:** Kleine dunkelgraue Netto-Watt-Zahl in () zwischen W und SWR während
TX (`70 W (56) SWR 2.6`). FWD minus Reflexion (Γ²). Tooltip „netto in die
Leitung". Nur W>0. DeepSeek-validiert, Logik getestet.

**Mike-Visuell-Check (am Radio):** beim nächsten TX/TUNE schauen ob Farbe
(#666 dunkelgrau), Größe (10px), Position (zwischen W und SWR) passt. Falls
nicht → 1-Zeilen-Tweak in `control_panel.py` (netto_label StyleSheet).

## P123 — Pre-TX-Anzeige beim QSO-Start (v0.98.37, 28.05.2026)

**Was:** Auto-Hunt zeigt jetzt „Rufe X..." im QSO-Log beim Start (war
vorher der einzige stille Start-Pfad — nur debug_log). Variante A (Mike-
Wahl): kurzer Marker, kein neues Format. DeepSeek PUSH FREIGEBEN.

**Mike-Field-Test:** Auto-Hunt aktivieren → beim Picken einer Station
sollte sofort „Rufe X... (ANT1)" im QSO-Log erscheinen (nicht erst der
„Gesendet"-Eintrag ~30s später).

## P154 — Auto-TUNE SWR-Median-Fix (v0.98.36, 28.05.2026)

**Was:** Mein P153-Fix (Median statt Snapshot) saß nur im manuellen TUNE-
Pfad. Die zwei AUTO-TUNE-Pfade (`_start_auto_tune_for_band_change`,
`_start_dialog_tune_sequence`) hatten eigenes Setup ohne die Sample-
Sammlung → arbeiteten mit veralteter Startzeit → falsche Band-Sperre
(Mike-Field-Bug: „Band 20M gesperrt — SWR 8.7" obwohl real 1.4, nur
manueller TUNE funktionierte). Zwillings-Bug wie P133/P134. Fix: zentraler
Helper `_init_tune_swr_sampling` von allen 3 Pfaden + Token-Reset (R1-F1).

**Mike-Field-Test:** Bandwechsel mit automatischem TUNE → Band sollte jetzt
mit dem echten stabilen SWR bewertet werden, nicht mit einem Ausreißer.
Bei Hänger Debug-Log AN → Diagnose-Zeile „SWR-Fenster".

## P152 — Weak-Decode-Log ≤ -21 dB (v0.98.35, 28.05.2026)

**Was:** Always-on-Liste `~/.simpleft8/weak_decodes_YYYY-MM-DD.log` — jeder
Decode mit SNR ≤ -21 dB landet automatisch drin (kein Setting). Mess-
Instrument das empirisch belegt was P150 (kMin_score=4) liefert. Neues
Modul `core/weak_decode_log.py` (batched 1 File-Append/Slot, UTC, keep_days=7).
Hook in `mw_cycle._on_cycle_decoded`.

**Mike-Field-Test:** 1-2 FT8-Sessions funken → Datei schicken → ich werte
aus (Anzahl -22 bis -26 dB pro Band/Antenne). Mike sah live schon -25/-27 dB
→ P150 wirkt sichtbar.

**Format:** `HH:MM:SS | -25 dB | CALL ME -18 | 1293 Hz | 15m FT8`

## P153 — SWR-Freeze Median über stabiles Fenster (v0.98.34, 28.05.2026)

**Was:** Bandsperre-Freigabe nahm einen EINZIGEN SWR-Snapshot
(`radio.last_swr`) → erwischte Ausreißer (Tuner matchte sichtbar 2,5,
System fror >4,0 ein → Band fälschlich gesperrt). Fix: **Median über
Fenster [Dauer-3s, Dauer-1s]** (neuer Helper `_compute_match_swr()`).
<3 Samples → None → Post-Check FAIL → Band gesperrt (Hardware-Safety,
KEIN Snapshot-Fallback). Auslöser P142 (Freeze in instabile Post-Match-
Phase gezogen), P148 machte es sichtbar. Pattern-Klasse Hardware-
Sicherheit 4. Iteration (P53/P76-A/P142/P153).

**Mike-Field-Test:** beim nächsten TUNE-Hänger Debug-Log aktivieren →
Diagnose-Zeile „SWR-Fenster …" zeigt Median vs. alter Snapshot.

## P150 — Decoder-Empfindlichkeit kMin_score 10 → 4 (v0.98.32, 27.05.2026)

**Was:** `ft8_lib/libft8simple.c` Z. 114 (FT8-Pfad) Sync-Pattern-Schwelle
von 10 auf 4 gesenkt → Decoder versucht auch sehr schwache Sync-Patterns
zu retten (WSJT-X „Deep"-Niveau). FT4/FT2 bleiben bei 10 (Costas-Pattern-
Längen unterschiedlich, Score-Skala nicht 1:1).

**Mike-Field-Test:**
1. App-Neustart auf v0.98.32+
2. 1-2 FT8-Sessions auf schwierigen Bändern (40m abends, 15m flau)
3. Logbuch beobachten:
   - **Best Case:** mehr -22/-24 dB QSOs, vielleicht erstmals -25/-26 dB
   - **Worst Case:** zu viele Junk-Decodes (fremde Calls in unpassenden
     Mustern) → Schwelle auf 5 oder 6 anheben

**Rollback:** Backup unter `Appsicherungen/2026-05-27_v0.98.31_vor_p150_p151/libft8simple.dylib` —
einfach zurückkopieren, App-Restart.

**Folge-Schraube falls P150 zu wenig bringt:** `SUBTRACT_MIN_SNR=-18 → -22`
in `core/decoder.py` (schwächere Signale subtrahieren → noch tiefere darunter
freilegen).

## P151 — AP-Lite vollständig ausgebaut (v0.98.33, 27.05.2026)

**Was:** AP-Lite-Feature komplett aus dem Code entfernt. DeepSeek-V4-pro-
Konsens: Matched Filter über LDPC-Decoder hat keine Nische, Konzept
trägt nicht. Mike-Felddaten 27.05.: 0/16 MATCH bestätigte das.

**Entfernt:** `core/ap_lite.py`, 3 Test-Files, 2 Doc-Files,
`generate_reference_wave` in Encoder, `last_pcm_12k`-Buffer im Decoder,
`partner_last_snr`-Field in QSOData, 4 Settings-Keys, GroupBox + Help-Eintrag,
Statusbar-Counter, alle Aufrufer.

**Backup:** `Appsicherungen/2026-05-27_v0.98.31_vor_p150_p151/ap_lite.py` —
falls je wiederbelebt werden soll.

---

## P148 — SWR-Anzeige nur während TX/TUNE (v0.98.28, 27.05.2026)

**Was:** Filter in `mw_tx.py:_on_meter_update` SWR-Branch — Update nur
wenn `encoder.is_transmitting OR _tune_active`. Bei Bandwechsel
`reset_swr_display()` (grauer Reset auf „SWR —"). Letzter echter
TX/TUNE-Wert bleibt im RX sichtbar statt mit Sensor-Default 1.0
überschrieben.

**Mike-Field-Test:** beobachten ob die SWR-Anzeige nach TUNE/QSO den
echten Wert behält und bei Bandwechsel auf „—" zurückspringt.

**Hardware-Sicherheit:** P53 SWR-Watchdog komplett unbeeinflusst (liest
direkt `radio._last_swr` aus FlexRadio, nicht UI).

---

## P139 — Auto-Hunt-60s-Start-Delay (Field-Beobachtung)

**Beobachtung Mike 26.05.:** Auto-Hunt aktiviert → sprang erst nach
~60s (4 Slots) an. **Heute 27.05.:** 1× nach 15s gesehen (Mike: „vlt
war das mit autohund dann nur ein programm irrläufer noch nicht
abhacken ich kucke dann noch 2 oder 3 mal lieber okay").

**Diagnose-Tool da:** P139 Event-Logging (v0.98.20) — alle Auto-Hunt-
Events landen in `~/.simpleft8/debug_YYYY-MM-DD.log` wenn „Debug-Log
schreiben" in Settings aktiv. Bei Wiederauftreten Log-Snippet liefern,
dann gezielt fixen.

**Mögliche Ursachen (Hypothesen, alle ungetestet):**
- Keine `is_cq`-Stationen mit SNR ≥ MIN_SNR in den ersten Slots
- Decoder-Buffer-Aufbau in den ersten 2 Slots nach Kalibrierung
- `_recent_qso` 5-Min-Cooldown auf gerade dekodierte Stationen
- `_dx_tune_dialog`-Close-Race
- Stats-Warmup 6 Zyklen

**Severity:** 🟡 — kein Bug bewiesen, möglicherweise Normalverhalten.

---

# ✅ ERLEDIGT 27.05.2026 — P142 SWR-Freeze VOR Phase B (v0.98.29)

Mike-Field-Reproduktion 12:08-12:10: Bandsperre triggered → manueller
TUNE → Log meldete „freigegeben — SWR 1.0" obwohl Live-Widget 2.5
zeigte. Fix Variante C (R1-empfohlen): Freeze VOR Phase B nehmen
(`swr_after_match` als `_tune_last_valid_swr`). R1-ORANGE-Catch:
Cancel-während-Phase-B Edge-Case behoben (Hardware-Sicherheit).

Final-R1 PUSH FREIGEBEN „sehr KISS-konform". Tests 2138→2149 (+11
P142, 3 alte P76-A-Tests angepasst). Pattern-Klasse Hardware-
Sicherheit 3. Iteration (P53/P76-A/P142).

**Field-Test pending.**

---

## (alte AUFGESCHOBEN-Sektion war hier, jetzt erledigt)

## P142 — Bandsperre-Freigabe meldet falschen SWR-Wert (Mike Field 26.05. 17:24) — JETZT ERLEDIGT

**Mike-Anweisung 27.05.:** „radio ist zwar an ich bin aber nicht vor
ort wir müssen das aus eis legen bis ich einmal schlechtes swr
simulieren kann stecker ab dann bandsperre dann stecker dran und
tune drücken das müssen wir aufschieben".

**Repro-Schritte (wenn Mike wieder vor Ort am Radio ist):**
1. Antennen-Stecker am Radio abziehen (SWR künstlich verschlechtern)
2. TX provozieren → Bandsperre triggern (SWR-Watchdog feuert)
3. Stecker wieder dran (Match jetzt OK, SWR ~1.3 wäre echt)
4. TUNE-Button drücken → beobachten:
   - Live im Radio-Widget: SWR-Wert während TUNE (z.B. 2.5)
   - Im QSO-Log nach 2s: „Band freigegeben — SWR X.X"
   - Bug-Symptom: Log meldet 1.0 statt Live-Wert
5. Wenn Bug auftritt → Fix Variante C umsetzen (siehe unten)

**Root Cause (vollständige Analyse in FEATURES.md §9):**

TUNE-Pipeline hat 3 Stufen — Phase A (Tuner-Match bei voller Power) →
Phase B (Closed-Loop-Power-Konvergenz auf 10W) → SWR-Freeze + Post-Check.
Vermutung: Phase B regelt `rfpower` runter, SWR-Sensor sieht zu wenig
Träger → clamped auf 1.0. SWR-Freeze NACH Phase B friert die falsche
1.0 ein statt der echten 2.5 nach Phase A.

**Fix-Optionen:**
- **A:** SWR-Freeze VOR Phase B nehmen (direkt nach Tuner-Match)
- **B:** Phase-A-SWR UND Phase-B-SWR → `max()` als Freigabe-Kriterium
- **C (empfohlen):** SWR-Wert für Freigabe-Bewertung KOMMT NUR aus
  Phase A; Phase B nur für RF-Stützpunkt-Speicherung

**Severity:** 🟠 — bei Mike's swr_limit=3.0 harmlos. Aber Hardware-
Risiko-Potenzial wenn echtes SWR knapp über Limit + Clamp-Bug greift
→ Band wird fälschlich freigegeben → nächster TX defekte Antenne.

**Workflow-Pflicht:** ja. Code-Stelle `ui/mw_tx.py:255-275`. Mehrere
Phase-B-Pfade (manuell + Auto-TUNE bei Bandwechsel). FEATURES.md §9
für vollständige Pipeline-Doku.

---

# 🆕 BACKLOG — anpackbar

## 🔧 P155 — Gain-Mess-TUNE SWR-Median statt Snapshot (DeepSeek-R1-F2 aus P154)

> ⛔ **Nur vor Ort am Radio** — TUNE-Pfad, Hardware-Safety.

**Was:** Der Gain-Mess-TUNE (`_start_dx_tuning._after_tune`, mw_radio.py)
nutzt noch `swr = self.radio.last_swr` (Einzel-Snapshot) und sperrt das
Band bei `swr > swr_limit`. Gleiche Snapshot-Fragilität wie P153/P154 (ein
Ausreißer-Tick kann fälschlich sperren oder freigeben). Bei P154 bewusst
ausgegliedert (eigene 3s-Struktur, kein `_tune_stop` → kein gemeinsamer
Pfad). DeepSeek-R1-F2: separates Ticket, Scope-Creep vermeiden.

**Aufwand:** Sampling im 3s-Tune-Fenster aufsetzen
(`_init_tune_swr_sampling(3)` vor `tune_on`) + `_after_tune` auf
`_compute_match_swr()` umstellen statt `radio.last_swr`. Fenster bei 3s
Dauer ist [0, 2] (Test T7 in P153 deckt das ab). Voller Workflow Pflicht.

**Severity:** 🟠 — selteneres Szenario (KALIBRIEREN, User vor Ort), aber
gleiche Hardware-Risiko-Klasse. Konsistenz-Gewinn.

## ✅ P119 — RFPreset/Krücke entfernen ERLEDIGT (v0.98.43, 29.05.2026)

> ✅ **ERLEDIGT 29.05.2026** — Mike-Freigabe „voll autonom", voller Workflow
> (V1→V2→R1 GO→V3→Code→Final-R1 PUSH FREIGEBEN, DeepSeek-v4-pro). Entfernt:
> `_tune_converge_to_target` (Phase B), `_wait_with_event_loop`,
> `_kruecken_skalierung`, 10W-Stützpunkt-Save, `_tune_converged_rf`. Anzeige
> „auf 10 W eingeregelt"→„prüfe SWR". **SWR-Sicherheit isoliert** (Freeze läuft
> VOR Phase B — DeepSeek bestätigt). Begleitfix: Auto-TUNE-Bandwechsel-Skip
> nutzt `has_any_preset(band)` statt `has_anchor(watt=10)`. Vorab: Umbenennung
> „Auto-TUNE"→„Kontroll-TUNE" im Kalibrier-Dialog. Tests 2188→2169. Details:
> HISTORY v0.98.43 + Memory `project_p119_done`.
> **⚠ FlexRadio Field-Test am Radio pending** — die ursprüngliche „nur vor
> Ort"-Warnung gilt jetzt für die VERIFIKATION: TUNE-Verhalten + Bandsperre am
> Radio prüfen (Phase A/Match unberührt, Risiko gering). Plan unten historisch.

**Mike-Erkenntnis:** Die Live-Regelung `_auto_adjust_tx_level`
(`mw_tx.py:780`) lernt sowieso den richtigen Slider-Wert pro `(Band, Watt)`
beim ersten FT8-TX und speichert in `rf_preset_store`. Slider ist
Maximum-Begrenzer der PA → kann nie mehr senden als erlaubt. Beim Erst-TX
einfach `Slider = Watt-Zahl` → 1-2 Slot Anpassung beim allerersten Mal,
danach identisch zu heute. FT8 lebt von -20 dB SNR — Lücke praktisch null.

**Damit wird obsolet:**
- `_tune_converge_to_target` (`mw_tx.py:489-561`, ~75 LOC) — Phase-B-
  Convergenz die heute ohnehin nicht greift (FWDPWR bleibt bei 11.6W
  obwohl Soll 10W, Mike-Screenshot 25.05.)
- `_kruecken_skalierung` (`mw_tx.py:563-…`, ~50 LOC) — Premature
  Optimization
- Phase-B-Block in `_tune_stop`
- P76-B Phase-2-Label „Leistung wird auf 10 W eingeregelt …"

**Was bleibt:**
- TUNE = reiner ATU-Match-Vorgang (10W Träger, konfigurierte Dauer,
  tune_off + 2s Post-SWR-Check)
- P76-A SWR-Freeze, P63 SWR-Watchdog — Hardware-Safety
- Per-(Band, Watt) Slider-Speichern beim Live-FT8-TX

**Aufwand:** ~200 LOC netto Lösch + Test-Anpassung. Voller Workflow
Pflicht. Folge-Vorteil: massiv weniger Code = weniger Bug-Fläche
(P54+P54-FIX+P76-A+P76-B+P74-A waren alle Reaktionen auf Phase-B-
Komplexität).

---

## 🆕 Multiband-Integration (Mike 24.05.2026)

> ⛔ **NUR vor Ort am Radio anpacken** — niemals aus der Ferne.
> Grund: Slice-B aktivieren kann FlexRadio in einen Zustand bringen
> der nur per Power-Cycle / SSDR-Neustart heilbar ist.

**Status Konzept:** vollständig + DeepSeek-V4-pro-geprüft („Umsetzung
empfohlen, kein Overengineering"). Spec liegt in `multiband.md` —
Bänder-Auswahl-Modell (3-Stufen-Cycle OFF/RX/TX), Antennen-Modell
(ANT1 fix, keine Diversity), Senden Fall A/B, QSO-Puffer, TUNE-
Auslösung, 6h-Cache, F1–F7 Design-Entscheidungen.

**Umsetzungs-Phasen (jede eigener Workflow-Zyklus):**
1. **Phase A** — Slice-B-Plumbing reaktivieren (RX-only, kein UI-Switch)
2. **Phase B** — Band-Cycle-UI (3-Stufen OFF/RX/TX)
3. **Phase C** — Gemeinsame RX-Liste mit Band-Spalte + Band-Filter
4. **Phase D** — Sende-Serialisierung (TX-Flag-Swap, ATU-Recall)
5. **Phase E** — QSO-Puffer + Station-Klick-Verhalten
6. **Phase F** — TUNE-Auslösung beim Band-Hinzufügen + 6h-Cache

**Vor Phase A:** Tag `v0.98.X-pre-multiband` setzen, Push, lokales
Backup. Rollback-Anker fix.

**Berührt:** Slice-B-Code (unten — wird ADAPTIERT statt gelöscht).

---

## ⛔ NICHT LÖSCHEN — „Toter" Slice-B-Code in flexradio.py (Reserviert für Multiband, Mike 22.05.2026)

> ⛔⛔⛔ **DIESER CODE BLEIBT — SCHEINT NUR TOT** ⛔⛔⛔
>
> Slice-B-Diversity in `radio/flexradio.py` ist **NICHT zu entfernen**.
> Er ist die fertige Plumbing für das **Multiband-Feature** (siehe
> Multiband-TODO oben + `multiband.md`). Bei Multiband-Umsetzung wird
> dieser Code **adaptiert, nicht gelöscht**.
>
> **Mike-Anweisung (27.05.2026, wiederholt):** „der tote code darf
> nicht raus … wir brauchen den noch dafür nicht das der entfernt wird"
>
> **Selbst-Check für Claude:** Bei Backlog-Übersicht NIEMALS diesen
> Punkt als „auto-tauglich Refactor" empfehlen — Slice-B ist reserviert.

`radio/flexradio.py` enthält eine **zweite, unbenutzte** Diversity-
Implementierung („beide Antennen gleichzeitig" via 2. Slice + 2.
Panadapter + 2. Audio-Stream). Projektweit **kein einziger Aufrufer**
in heutiger Codebase.

**Code-Block (Zeilen-Anker Stand v0.97.90):**
- `__init__` Vars: Z. 83–87 — `_diversity_mode`, `_slice_idx_b`,
  `_rx_stream_id_b`, `_panafall_b`, `on_audio_callback_b`
- `enable_diversity()`: Z. 775–882
- `disable_diversity()`: Z. 884–920
- `set_frequency()` toter Zweig: Z. 929–930
- `set_rfgain_secondary()`: Z. 959–965
- `has_secondary_slice()`: Z. 967–969
- VITA-49-Dispatch toter Zweig: Z. 1331–1332

---

## ✅ P64 — Sim-Modus (FakeRadio + SimInjector) — ERLEDIGT v0.98.38 (28.05.2026)

Variante B (Scripted + Fake-Werte). App startet ohne FlexRadio:
```
SIMPLEFT8_FAKE_RADIO=1 ./venv/bin/python3 main.py
```
`radio/fake_radio.py` + `core/sim_injector.py` + `core/sim_mode.py`. Safety:
Sim-Decodes schreiben NICHT in weak_decode_log/station_stats. Voller Workflow,
DeepSeek Design-R1 + Final-R1. Tests +9.

### 🆕 P64-B — Sim-Ausbau (optional, falls Field-Test es einfordert)

Offene Grenzen aus P64 V1 (kein Druck, nur wenn nützlich):
- **Interaktiver QSO-Responder:** angerufene Station antwortet im Sim
  (grid→report→RR73), damit ein QSO komplett durchläuft. Braucht qso_sm-
  Kopplung im SimInjector (read-only State lesen) + ADIF-Guard (dann wird
  QSO-complete erreichbar). Eigener Workflow + R1.
- **Diversity-Messung simulieren:** dual-stream Fake-Audio/SNR pro Antenne
  (= Variante C). Aufwändig. Nur wenn Diversity-Logik remote getestet werden muss.

---

## ✅/❌ P74 — UX-Konsolidierung + Autogain-Konzept — KOMPLETT ABGESCHLOSSEN (28.05.2026)

Spec: `prompts/p74_discussion.md` (18.05.). Bilanz aller Teile:

- **P74-A Fenster-Konsolidierung** → ✅ ERLEDIGT v0.97.94 (DXTuneDialog-State-Machine).
- **P74-B(a) Auto-Re-Kalibrierungs-Warnung** → ✅ ERLEDIGT als P113 v0.97.98
  (14-Tage-Stale-Gain-Toast beim Bandwechsel).
- **P74-B(b) Live-Gain-Nachregeln** → ❌ VERWORFEN (hoch-Risiko, stört
  Funkverkehr, gegen Hobby-Philosophie).
- **P74-B(c) Cross-Band-Gain/Ratio-Interpolation** → ❌ **VERWORFEN
  28.05.2026 (Mike + Claude + DeepSeek einstimmig).** Begründung: ANT2 ist
  eine Regenrinne (random wire) — Wirkungsgrad/Impedanz UND das ANT1/ANT2-
  **ratio** (der sicherheitskritische Diversity-Wert) springen über die
  Bänder erratisch, NICHT interpolierbar. Ein geratenes ratio degradiert
  Diversity unbemerkt + ruiniert die ersten Minuten Empfang bevor gemessen
  wird → „trügerische Sicherheit", verlorene QSOs. Die transparente
  „muss gemessen werden"-Meldung ist ehrlicher und bleibt. **Nicht wieder
  vorschlagen.** (Memory `feedback_no_crossband_gain_interpolation`.)
- **P74-B(d) SNR-Live-Feinjustierung** → ❌ VERWORFEN (marginal, Komplexität
  hoch / Nutzen mittel).

→ P74 ist damit vollständig erledigt — kein offener Rest mehr.

---

## 🆕 DeepSeek-Code-Vorschläge GitHub-Review 16.05.2026 — Sichtung 27.05.2026

Bei der README-Überarbeitung (v0.97.42 GitHub-Push) hat DeepSeek-V4-pro
in 6 Brainstorm-Runden **3 Code-Vorschläge** abgesetzt. Sichtung
27.05.2026 (autonom, Git-Diff `f19d748` und HISTORY Z. 14486-14492
verifiziert):

| Vorschlag | Status |
|---|---|
| **P67** — Auto-Hunt-Cap an Operator-Presence binden | ✅ **ERLEDIGT 16.05.2026** v0.97.43 als „P67 Auto-Hunt Mouse-Inactivity-Schicht (Variante C)". 5-Min-Mouse-Inactivity zusätzlich zur 10-Min-Hard-Cap. HISTORY Z. 4012. |
| **P69** — Konfidenz-Intervalle für Diversity-Tabellen (Bootstrap) | ✅ **ERLEDIGT 17.05.2026** v0.97.46 als „P69 Block-Bootstrap-Konfidenz-Intervalle". README + PDF mit 95%-CI. HISTORY Z. 3733. |
| **P68** — OMNI-CQ continuous gap re-evaluation innerhalb Paritäts-Block | ⏸ **NICHT UMGESETZT** — bewusste KISS-Entscheidung. Aktuell: `omni_cq.py:240` ruft `_init_audio_freq()` nur EINMAL pro Session (Sticky). DeepSeek-Argument („Worst-Case 10 OMNI-Nutzer gleiche Frequenz") ist hypothetisch — OMNI ist deaktiviert + Mike hat keine Field-Symptome gemeldet. Komplexitäts-Increase ohne Bug-Druck. |

**Resultat:** 2 von 3 erledigt, 1 bewusst verworfen. Liste komplett
abgearbeitet — Ticket kann zu.

---

# ⚠️ ALTE OFFENE TICKETS — Sichtung 27.05.2026

> Stand 27.05.2026 (autonome Sichtung): Code-Verifikation aller 4 Tickets
> durchgeführt. Ergebnisse unten — alle alten Tickets sind erledigt oder
> obsolet, keine offenen Architektur-Lücken mehr.

| ID | Was | Status (verifiziert 27.05.2026) |
|---|---|---|
| ~~P30~~ | MEMORY-LEAK 124 GB | ✅ **ERLEDIGT 13.05.** — Wurzel war TTS, nicht SimpleFT8 |
| ~~P12~~ | QSO-POSTPROCESSING-ASYNC (logbook.refresh-Hang) | ✅ **ERLEDIGT durch P12-Fix 11.05.** — `_LOGBOOK_MAX_ROWS=500` (`ui/logbook_widget.py:23`). 500 Zeilen sind synchron unkritisch (~10-50ms). Kein Hang mehr seit Fix; "Sauberer Async-Refresh" wäre Architektur-Verbesserung ohne Bug-Druck → **verworfen als KISS-Verletzung**. |
| ~~P27~~ | MESS-GUARD — vor Antennen/Diversity/Gain-Mess prüfen ob Radio verbunden | ✅ **ERLEDIGT durch P63 (AC9/AC13) + P82** — `_start_dx_tuning` hat 3-fach-Guard (`band in _swr_blocked_bands`, `radio.ip`, `tuner_present`). `_start_tune_only` returnt früh ohne `radio.ip` (`mw_radio.py:1700`). Re-Check vor `tune_off` (Z. 1721) deckt Offline-Race ab. Multi-Radio-Refactor P121 hat Architektur sauberer gemacht. |
| ~~P25~~ | RADIO-IP-LATE-SETTING | ✅ **OBSOLET** — `auto_connect()` läuft als Worker mit max_retries=10. P82 (Late-Connect-Override), P90 (Worker-Abort), P91 (Dialog-Lifecycle) decken alle Race-Fenster ab. Mike-Statement 10.05.: „wird normal gesucht und gefunden" weiterhin gültig. |

**Resultat:** alle 4 Alt-Tickets können aus dem aktiven Backlog raus.

---

# ✅ Frisch erledigt (24.-27.05.2026) — kompakt mit Versions-Anker

> Details + R1-Findings + Field-Validations: **HISTORY.md** (lückenlos)
> oder Memory `~/.claude-account1/.../project_pXXX_done.md`.

## 27.05.2026 (heute, 5 Workflows autonom)

| Version | Punkt | Field-Status |
|---|---|---|
| **v0.98.28** | P148 SWR-Anzeige nur während TX/TUNE | ⏳ Pending |
| **v0.98.27** | P145 Pattern-Check-Skript mode-aware Symmetrie | ✓ Selbst-validiert (Tool) |
| **v0.98.26** | P144 Auto-Hunt busy-station Filter | ✓ Field-validiert 08:50 (EA8UP-Skip) |
| **v0.98.25** | P147 HALT stoppt Auto-Hunt SOFORT (Hardware-Sicherheits-Fix) | ⏳ Pending |
| **v0.98.24** | P146 Kalibrierungstext mode-agnostisch | ✓ Field-validiert 08:50 |
| — | P140 73-vor-✓ Field-Test | ✓ Field-validiert 07:03 (KF0MSJ-Screenshot) |
| — | P141 Sterne-Diversity Field-Test | ✓ Field-validiert 06:30 |
| — | P106 QRZ-Confirmed-Bug | ✓ Field-validiert (QRZ bestätigt QSOs) |

## 26.05.2026 (vorige Session, 8 Workflows)

| Version | Punkt |
|---|---|
| v0.98.23 | P141 Sterne-Anzeige Diversity-Pfad (mode-aware Symmetrie 4. Iteration) |
| v0.98.22 | P143 QSO-Log-Resurrection nach Bandwechsel (Helper `clear_log_completely`) |
| v0.98.21 | P140 Cooldown-Trigger umgehängt (qso_complete → qso_confirmed_visual) |
| v0.98.20 | P139 Auto-Hunt Event-Logging (Diagnose-Tool, debug_log-Framework) |
| v0.98.19 | P138 P129-Whitelist entfernt („beendet ist beendet") |
| v0.98.18 | P137 „Sende" → „Gesendet" Tempora-Fix |
| v0.98.17 | P136 Call-Validation Auto-Hunt + Parser-Fix (`>=3` statt `==4`) |
| v0.98.16 | P135 Decode-Statusbar akkumuliert (mode-aware) |
| v0.98.15 | P131 Sende-Log bei Bandwechsel verwerfen (Defense-in-Depth) |
| v0.98.14 | P134 Python-Sweep entfernt (Pattern-Killing-Bug-Klasse beseitigt) |
| v0.98.13 | P132/P133 Single-Instance Architektur-Refactor (fcntl.flock + lsof-CWD) |
| v0.98.12 | P126 Send-nach-Timeout TX-Pipeline-Race-Fix |

## 25.05.2026

| Version | Punkt |
|---|---|
| v0.98.11 | P130 GAIN_VALUES = [0, 10, 20] zurück (Low-Band-Default) |
| v0.98.10 | P129 P128-Whitelist für 73/RR73 (Live-Field-Bug-Fix) |
| v0.98.09 | P120 Sterne-Schwellen FT8-realistisch |
| v0.98.08 | P127 Sende-Log bei SWR-Abbruch verwerfen |
| v0.98.07 | P128 Empf.-Eintrag 60s blocken nach ✓ QSO |
| v0.98.06 | P124 Hash-Call `<...>` kontextuell aus QSO auflösen (Mike-KISS-Idee) |
| v0.98.05 | P122 Auto-Hunt-Stop-Defer bei aktivem QSO |
| v0.98.04 | P121 Multi-Radio-Refactor Variante A (IC-7300/IC-7100 Vorbereitung) |

## 24.05.2026

| Version | Punkt |
|---|---|
| v0.98.03 | P118 Band-Activity Berliner Zeit (DST-aware via zoneinfo) |
| v0.98.02 | P117 Band-Aktivitäts-Übersicht-Script + Shell-Wrapper |
| v0.98.01 | P116 FIFO-Sliding-Window Stats-Cleanup |
| v0.98.00 | P115 Empfangsfenster bleibt bei RX-Mode-Switch/Kalibrierung |
| v0.97.99 | P114 MODUS+BAND Status-Suffix |
| — | Diagramm-Legende Tage-Coverage ehrlicher |

## 23.05.2026

| Version | Punkt |
|---|---|
| v0.97.98 | P113 Stale-Gain-Warning bei Bandwechsel |
| v0.97.97 | P102 Antennen-Kachel-Status-Sync (mode-aware Symmetrie 1. Iteration) |
| v0.97.96 | P100 Partial-Log bei R-Report-Empfang |
| v0.97.95 | P99 WAIT_RR73 Message-Cap |
| v0.97.94 | P74-A Modal-Konsolidierung (DXTuneDialog State-Machine) |
| v0.97.93 | Re-Mess-Countdown-Anzeige pro Slot |

---

# 📚 Historie + Doku-Verweise

- **HISTORY.md** — lückenlose Versions-Historie. Bei Versions-Recherche
  oder „wann wurde X gefixt": grep dort.
- **FEATURES.md** — funktionales Lexikon mit Lookup-Tabelle. Bei Bug-
  Analyse oder „wie hängt X mit Y zusammen": ZUERST hier.
- **HANDOFF.md** — aktueller Session-Stand + nächste 1-2 Schritte.
- **CLAUDE.md** — Workflow-Regeln, Architektur, Pattern-Familien.
- **multiband.md** — Multiband-Spec (DeepSeek-V4-pro-geprüft).
- **auswertung.md** — Statistik-Methodik + Diagramm-Generierung.

**Memory-Index:** `~/.claude-account1/projects/-Users-mikehammerer-Documents-KI-N8N-Projekte-FT8/memory/MEMORY.md`
— Cycle-Memories pro Workflow mit V1/V2/R1/V3-Findings.

---

# 📊 Tag-Bilanz 27.05.2026

- **Tests:** 2075 → **2138 grün** (+63 heute)
- **Versionen:** v0.98.22 → v0.98.28 (6 Bumps)
- **DeepSeek-Verbrauch:** ~$0.08 (~7 R1-Reviews)
- **GitHub-Commits gepusht:** 9 atomare Commits
- **V4-pro-Bilanz heute:** 5 Workflows, 0 Halluzinationen
- **Field-Validierungen:** P140, P141, P144, P146, P106
- **Hardware-Sicherheits-Fix:** P147 (HALT-Notbremse Mike-Vertrauen-Restore)

---

*Stand 27.05.2026 08:50 — TODO komplett aufgeräumt (vorher 6859 Zeilen).
Erledigte Tickets vor 24.05. archiviert in HISTORY.md.*

## 🔲 „neue"-Filter + Auto-Hunt mit voller QRZ-Historie füttern (31.05.2026, Mike-Wunsch zurückgestellt)

Aktuell kennt die „schon gefunkt"-Erkennung (`log/qso_log.py` → QSOLog,
Worked-Before-Set) nur die paar hundert SimpleFT8-eigenen QSOs (Hauptordner +
`adif/hochgeladen/`), NICHT die 18.329 QSOs im QRZ-Export
(`adif/_backup_qrz_export/`, DA1MHH+DO4MHH).

**Folge:** „NEUE"-Filter (RX-Liste, nur Anzeige) + Auto-Hunt-Scoring
(neue Station = Bonus) behandeln längst gearbeitete Stationen als „neu".

**Aufgabe:** `_backup_qrz_export` zusätzlich in den Worked-Before-Set laden
(`QSOLog.load_directory(...)` in `ui/main_window.py:_init_qso_log`). DeepSeek
(31.05.): unkritisch, ~18k Calls in ein set = <1 MB / <1 s Start. Portable-
Suffixe werden schon gestrippt (`call.split("/")[0]`). Beide Calls = ein Pool.
Eigener voller Workflow. Diplome-Feature (v0.98.49) nutzt denselben Ordner schon.


## 🔲 Diplome: Fallback-Pfad-Cleanup (Mini, DeepSeek-Final-R1-Hinweis 31.05.2026)

`ui/logbook_widget.py:_on_awards_clicked`: der zweite Backup-Pfad
`Path.cwd()/"adif"/"_backup_qrz_export"` ist im Normalfall redundant zu
`self._adif_dir/"_backup_qrz_export"` (gleicher Ordner). Harmlos (nur ein
doppelter `is_dir()`-Check, kein Crash) — bei Gelegenheit vereinfachen.
Nicht-Blocker, Final-R1 hat ausdrücklich PUSH FREIGEBEN.

---

## 🔲 Diplome-Erweiterung Phase 2 (nice-to-have, v0.98.53, 02.06.2026)

Optionale Verfeinerungen nach der Diplome-Erweiterung (WAE/WPX/DXCC-Band +
Sichtbarkeit). Alles 🟡 — keine Blocker, Field-Test der v0.98.53 zuerst.

- **WAE-Genauigkeit:** aktuell Näherung über `CONT==EU`-DXCC-Entities. Falls je
  exakteres WAE gewünscht: feste WAE-Gebietsliste mit Sonder-Multipliern
  (IT9-Sizilien, GM-Shetland, eu-Russland-Distrikte) — DeepSeek+Claude einig:
  „Fass ohne Boden" für ein Hobby-Tool, nur bei echtem Bedarf.
- **WPX-Stufen:** aktuell nur Basis 300. CQ hat Endorsements (300/350/.../1000 +
  kontinental). Bei Wunsch analog zu DXCC-Tiers nachrüstbar.
- **DLD (Deutschland-Diplom):** technisch geblockt — DOK fehlt komplett in den
  FT8-QSOs. Nur möglich, wenn je eine DOK-Quelle dazukommt (z. B. Call→DOK-
  Lookup-Tabelle). Aktuell bewusst NICHT umgesetzt.
- **DXCC-Challenge/5BD auf bestätigt-Basis:** Anzeige nutzt `worked` (konsistent
  mit der DXCC-Karte). Offiziell verlangen beide LoTW-Bestätigung — bei Wunsch
  zweite confirmed-Variante.
- **`compute_awards` defaultdict statt setdefault** (DeepSeek-Final-R1-🟡, rein
  kosmetisch — bewusst gelassen, spart einen Import).

---

## 🔲 P167-Beobachtung: Caller-Queue vs deferter Einschub (🟡, 02.06.2026)

DeepSeek-Final-R1-🟡 zu P167 (Einschub-Defer): Theoretischer Race im CQ-Modus —
wenn `_resume_cq_if_needed` (synchron, vor dem Defer-Tick) eine wartende Station
aus der Caller-Queue startet UND ein P164-Einschub vorgemerkt ist, läuft im
nächsten Tick `start_qso(Einschub)`. **Kein Bug:** `start_qso` bricht das
laufende Queue-QSO sauber ab (state≠IDLE → reset) → kein paralleles QSO, und der
geklickte Einschub SOLL priorisiert sein (bewusster User-Klick). Nur
beobachtungswürdig, kein Handlungsbedarf. Falls je auffällig: Defer-Tick auch im
CQ-Queue-Pfad berücksichtigen.
