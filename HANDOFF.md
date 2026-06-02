# HANDOFF — SimpleFT8

**Aktueller Stand:** v0.98.57 (02.06.2026) — **P169 Phase 1: adif/erfasst/ als
einzige Worked-Quelle + ADIF-Import + Migration** (voller Workflow). EINE
rekursiv gelesene Quelle `adif/erfasst/{neu,hochgeladen,importiert}/` statt der
verstreuten Alt-Ordner. Migration der echten 18k QSOs gelaufen (copy→SHA256-
verify→delete, Backup-ZIP, 9647 (Call,Band) byte-genau erhalten, Altordner weg).
Code 8 Touchpoints umgestellt + Import-Button. DeepSeek Migration-R1 + Final-R1
PUSH FREIGEBEN. Tests **2312 grün**. **Phase 2 (mode-genauer NEUE-Filter +
Auto-Hunt-Transparenz) OFFEN — siehe TODO.** ⚠️ **Mike muss App neu starten**
(Migration hat adif/ umgebaut; laufende Alt-Instanz liest verschobene Ordner).
Lokal committet, **Push-Freigabe Mike ausstehend** (auch P168 v0.98.56 noch
nicht gepusht). Davor v0.98.56 P168 (FT4-Timing, field-validiert).

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
