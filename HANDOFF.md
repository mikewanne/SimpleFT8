# HANDOFF — SimpleFT8

**Aktueller Stand:** v0.98.51 (02.06.2026) — **Auto-Hunt DX-Scoring** (voller
Workflow, 2 DeepSeek-Runden + Web-Recherche). Tests **2245 grün**. **Lokal
committet, NICHT gepusht.** Field-Test pending.

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
