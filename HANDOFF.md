# HANDOFF — SimpleFT8

**Stand 2026-05-08:** **v0.95.19 — P1.BUNDLE2: 3 hardware-freie Bugs gebuendelt.**

**P1.BUNDLE2 (NEU):** Mike-Auftrag 08.05. (post-v0.95.18): „die kleinen
können wir die zusammenfassen wenn wir deepseek workflow komplett
machen mit compact?" Bundle aus 3 unabhaengigen kleinen Bugs (P1.7 +
P1.11 + P1.13). Voller V1→V2(15 Lessons)→R1(1 KRITISCH KP-8 +
2 SOLLTE + 1 KOENNTE)→V3(9 Diffs)→Compact→Code→**Final-R1 („Code kann
gemerged werden") — 0 KP-Findings**.

**Bug 1 — P1.11 `wait_73_retries` entkoppelt von `rr73_retries`:**
- Wurzel: nach voller WAIT_RR73-Sequenz (rr73_retries=3) blockierte
  derselbe Counter die WAIT_73-Hoeflichkeit (max 2). Station die ihren
  R-Report wiederholt wurde im Stich gelassen.
- Fix: Neues Feld `wait_73_retries: int = 0` in QSOData (Auto-Reset
  via `QSOData()` in `start_qso`).

**Bug 2 — P1.13 Hunt-Klick Normal-Mode TX-Frequenz-Sync:**
- Wurzel: `_on_station_clicked` setzte `encoder.tx_even` + `start_qso`,
  aber NICHT `encoder.audio_freq_hz` oder Spinbox. → TX lief auf alter
  Spinbox-Frequenz, Mike's Augen sahen anderes.
- Fix: Nach `start_qso` im Normal-Modus encoder + Spinbox auf clamped
  Station-Frequenz (Range aus `spin.minimum()/maximum()`, R1).
  Diversity unangetastet, Persistenz NICHT, Histogramm-Update KISS weggelassen.

**Bug 3 — P1.7 ADIF-Duplikat-Filter 5-Min-Fenster:**
- Wurzel: `_on_qso_complete` rief `adif.log_qso` unbedingt — bekannte
  Station < 5 Min nach RR73 ruft erneut → 2. ADIF-Eintrag im Logbuch.
- Fix: Session-lokaler Cache `_recent_logged_calls: dict[(call, band), float]`
  in MainWindow, Modul-Konstante `_LOG_DEDUP_WINDOW_S=300` in mw_qso.py.
  Bei Duplikat: ADIF + qso_log + log_antenna_qso SKIP.
  UI-Cleanup laeuft IMMER vor Skip-Return (R1-KRITISCH).

**Geaenderte Files (3 Code + 1 Test NEU + main.py + 1 Test-Anpassung):**
- `core/qso_state.py` — `wait_73_retries`-Feld + WAIT_73-Hoeflichkeit
- `ui/mw_qso.py` — Modul-Konstante + TX-Sync + Duplikat-Filter
- `ui/main_window.py` — `_recent_logged_calls` init
- NEU `tests/test_p1_bundle2.py` (17 Tests: 4 P1.11 + 5 P1.13 + 8 P1.7)
- `tests/test_p1_10_courtesy_73.py` Anpassung (`rr73_retries` → `wait_73_retries`)
- `main.py` APP_VERSION 0.95.18 → 0.95.19

**Plan-Files:** `prompts/p1_bundle2_v[1-3].md`.

**Tests 938 → 955 gruen** (+17 wie V3 prognostizierte).

**Atomare Commits:**
- `faff2bb` Bug-1 P1.11 (qso_state.py only)
- `9be7747` Bug-2 P1.13 (mw_qso.py _on_station_clicked only)
- `5466cb4` Bug-3 P1.7 (mw_qso.py + main_window.py)
- (Doku-Commit folgt mit Tests + APP_VERSION + HISTORY/HANDOFF/CLAUDE)

**Field-Test-Pflicht (vor Push):**
- P1.11: QSO mit IC-7300 voll durchziehen, R-Report-Wiederholung in
  WAIT_73 → RR73-Antwort sollte erfolgen (vorher: ignoriert).
- P1.13: Normal-Modus, Spinbox=1500, RX-Klick auf 800 Hz Station →
  Spinbox+TX zeigen 800 Hz; App-Restart → wieder 1500 Hz.
- P1.7: hardware-frei (Tests reichen).

**Push noch nicht.** v0.95.16 + v0.95.17 + v0.95.18 + v0.95.19 gehen
beim naechsten Push zusammen.

---

**Vorher v0.95.18 (08.05.2026):** **P1.BUNDLE-LOGBOOK-RST-SNR: 3 Bugs gebuendelt.**

**P1.BUNDLE-LOGBOOK-RST-SNR:** Mike-Auftrag 08.05.: „2 leichte Punkte
zusammen mit Logbuch-Crash beim Eintrag-Loeschen — und QRZ-10K-Burst-Bug
pruefen ob unser ADIF-Format spec-konform ist." Bundle aus 3 unabhaengigen
Bugs im selben ADIF/Logbuch/Reporting-Pfad.

**Bug A — Logbuch-UI-Hang beim Eintrag-Loeschen:**
- Wurzel: `log/adif.py:94` `new_body += block + eor` in while-Loop = O(n²)
  bei 12 MB ADIF (~10K Records) → 5-10 s Hang im UI-Thread (Beachball).
  Plus full `self.refresh()` re-parste beide ADIF-Verzeichnisse (~19 MB).
- Field-Test 07.05. nachmittags reproduziert.
- Fix: `delete_qso` `new_parts = []` + `.append` + `"".join` → O(n),
  < 200 ms gemessen. `_on_delete_clicked` In-Memory-Update.

**Bug B — RST_RCVD/RST_SENT mit FT8-R-Praefix in ADIF:**
- Wurzel: SimpleFT8 schrieb `<RST_RCVD:4>R-22`, ADIF-Spec + QRZ-Validator
  akzeptieren nur `<rst_rcvd:3>-22`. Vergleich mit QRZ-Original-Export
  bestaetigt. Mike's 10K-Burst-Bug in v0.95.15 wahrscheinlich daher.
- Fix: `_strip_r_prefix` Helper in 2 Pfaden (Schreib + Send, lazy import).

**Bug C / P1.8 — `_process_cq_reply` _last_snr-Race:**
- Wurzel: `_last_snr` wird pro Slot 50× ueberschrieben. Z.214,229 nahmen
  zuletzt iterierte Message statt anrufende Station. Mike-Beispiel:
  DA1TST -23 vs R+19 = 42 dB Diff.
- Fix: nur Z.214 + Z.229 auf `snr = msg.snr`. Hunt + Retry-Pfade unveraendert.

**Geaenderte Files (4 Code + 1 Test + main.py):**
- `log/adif.py` — `delete_qso` O(n²)→O(n) + `_strip_r_prefix` + `log_qso`
- `log/qrz.py` — `upload_qso_from_dict` lazy import + RST-Strip
- `ui/logbook_widget.py` — `_on_delete_clicked` In-Memory-Update
- `core/qso_state.py` — `_process_cq_reply` Z.214,229 `msg.snr`
- NEU `tests/test_p1_bundle_logbook_rst_snr.py` (17 Tests)
- `main.py` APP_VERSION 0.95.17 → 0.95.18

**Voller Workflow** V1 (Diagnose, 3 Bugs lokalisiert) → V2 (15 Lessons —
entlarvte O(n²) als Hauptwurzel + Send-Pfad-Strip + Filter-Re-Apply
Race-Frei via Qt) → R1 („Plan kann freigegeben werden", 0 KRITISCH,
10/10 Pruefauftraege gruen) → V3 (Compact-fest, 7 Diffs) → Compact → Code
→ **Final-R1 („Code kann gemerged werden") — 0 KP-Findings**.

**Plan-Files:** `prompts/p1_bundle_logbook_rst_snr_v[1-3].md`.

**Tests 921 → 938 gruen** (+17: 4 Bug-A + 10 Bug-B + 3 Bug-C).
Performance-AC < 500 ms erfuellt.

**Atomare Commits:**
- `37e73aa` Bug-A (delete_qso O(n²) + In-Memory-Update)
- `e44fc26` Bug-B (RST R-Strip Schreib + Send)
- `1ec7b7a` Bug-C (msg.snr im CQ-Reply)
- (Doku-Commit folgt mit Tests + APP_VERSION)

**Field-Test-Pflicht (vor Push):**
- QRZ-Bulk-Upload alter ADIF-Datei → kein 10K-Burst mehr (Bug-B-Beweis).
- Logbuch-Eintrag-Loeschen → < 0.5 s, kein Beachball (Bug-A-Beweis).
- QSO live → Report-SNR korrekt (kein 42 dB Bias, Bug-C-Beweis).

**Push noch nicht.** Mike-Freigabe nach Field-Test explizit einholen.
v0.95.16 + v0.95.17 + v0.95.18 gehen beim naechsten Push zusammen.

---

**Vorher v0.95.17 (07.05.2026):** **P1.COLLAPSE-RADIO-MODEBAND: Modus+Band
und Radio einklappbar.** Pattern 1:1 Spiegelung Antennen-Kachel (v0.95.11).
4 Files. Tests 902 → 921. Voller Workflow durchgezogen, Final-R1 0
KP-Findings. Plan-Files: `prompts/p1_collapse_radio_modeband_v[1-3].md`.
Field-Test bestaetigt visuell ✅.

---

**Vorher v0.95.16 (07.05.2026):** **P1.LOCATOR-SLASH: Slash-Call Lookup-Bugs
gefixt.**

**P1.LOCATOR-SLASH (NEU):** Mike-Pflicht-Verifikation der km-Anzeige im
RX-Panel (DeepSeek-R1 Code-Review 07.05.) entdeckte 3 echte Bugs:

1. `ui/rx_panel.py:333-335` — `lookup_call = max(parts, key=len)` bei
   Praefix-Slash wie `EA8/DA1MHH` extrahierte das laengste Token (`DA1MHH`)
   statt des DXCC-Praefixes (`EA8`) → Country Deutschland statt Kanaren,
   Distanz ~0 km statt ~3000 km, DB-Lookup verfehlt Eintrag.
2. `core/geo.py callsign_to_country` + `callsign_to_distance` — gleicher
   `max(parts, key=len)`-Bug.
3. Mobile-Suffix-Inkonsistenz zwischen rx_panel-Stripping und DB-Set-Pfad.

**Mike-Entscheidung 07.05.:** **DB BEHALTEN** — Daten korrekt gespeichert,
nur Lookup-Pfad kaputt. Decoder-Verifikation pre-V3 (`core/message.py:107-111`
`parts = msg_str.strip().split()` → `f2 = parts[1]`) bewiesen: `m.caller`
bleibt komplett.

**Loesung — Option A (strikte Trennung):**
- `ui/rx_panel.py`: KEIN Suffix-Stripping mehr. `lookup_call = caller` 1:1.
- `core/geo.py`: NEU `MOBILE_SUFFIXES` (7 Suffixe), `_strip_mobile_suffix`,
  `_dxcc_prefix_from_call` Helper. `callsign_to_country/distance` nutzen
  DXCC-Token-Heuristik (exakt-Match in `_PREFIX_MAP`, dann iterativ 3/2/1).
- `core/locator_db.py`: lokale `MOBILE_SUFFIXES` (3-Tupel `/MM /AM /QRP`)
  durch Import aus `core.geo` ersetzt (jetzt 7 Suffixe). Verhaltens-
  Aenderung: `/P /M /PORTABLE /MOBILE` bekommen jetzt `prec_km*1.5`
  konsistent zu `/MM /AM /QRP` (Funker-Praxis: portable = Operator
  unterwegs = Position weicht von Heim ab). R1-bestaetigt vertretbar.

**DB bleibt unveraendert.** Karten-Code (`direction_map_widget.py:1694`)
und Statistik-Code unbeeinflusst.

**Geaenderte Files (5):**
- `core/geo.py` — Helpers + Slash-Heuristik in `callsign_to_*`
- `core/locator_db.py` — Import + Doku Z.13-15 angepasst
- `ui/rx_panel.py` — Slash-Block Z.323-338 vereinfacht (9 Bug-Zeilen raus)
- NEU `tests/test_p1_locator_slash.py` (14 Tests)
- `tests/test_locator_db.py` — `test_slash_p_treated_as_stationary`
  invertiert zu `test_slash_p_treated_as_mobile` (jetzt `prec_km == 8`)
- `main.py` APP_VERSION 0.95.15 → 0.95.16

**Voller Workflow:** V1 (3 Bugs, 3 Optionen, 10 ACs) → V2 (12 Lessons,
L6 entlarvt Option B als Original-Design-Widerspruch) → R1 („Plan
freigegeben" mit 1 KRITISCH = Decoder-Verifikation Schritt 0 ERLEDIGT
pre-V3 + 1 SOLLTE-ERGAENZEN = +2 Edge-Case-Tests) → V3 (Compact-fest,
6 Diffs) → Compact → Code → **Final-R1 („Push freigegeben") — 0
KP-Findings.** Plan-Files: `prompts/p1_locator_slash_v[1-3].md`.

**Tests 888 → 902 gruen** (+14, exakt wie V3 prognostiziert).

**Field-Test-Pflicht (post-Push):**
- App starten → Slash-Call beobachten (`EA8/...`-Aktivitaeten, `/P`-Mobile,
  `K1ABC/W2`-Region-Suffix wenn am Band).
- km-Spalte: exakte Position bei DB-Hit ODER DXCC-Distanz bei Miss —
  KEIN Heim-Country-Bias mehr.
- country-Spalte: korrektes Land.
- Karten-Pin: am DXCC-Land, nicht in Heim-DE.

**Push noch nicht.** Mike-Freigabe nach Field-Test mit echtem Slash-Call
(EA8 oder /P) explizit einholen.

---

**Vorher v0.95.15 (07.05.2026):** **P1.QRZ-UPLOAD-UI-2: Title + File-Move
+ Log + Rate-Limit.**

**P1.QRZ-UPLOAD-UI-2:** Folge zu v0.95.14 — Mike-Field-Test
07.05. nachmittags entdeckte 3 Probleme: Progress-Dialog StaysOnTopHint
nervt, kein Tracking welche QSOs schon hochgeladen, 12134 Dups +
Fail-Burst nacheinander deutet auf QRZ-Rate-Limit.

**Loesung:**
- Status in Titelleiste statt non-modal Dialog (`SimpleFT8 — DA1MHH —
  QRZ ↑ x/y (z%)`)
- Statusbar inline `[QRZ ↑ x/y (z%)] [✕]` Cancel-Widget
- File-Move: nach Bulk wird Datei nach `adif/hochgeladen/` verschoben
  (nur wenn `fail==0 AND processed==expected`). LogbookWidget +
  qso_log + locator_db laden BEIDE Verzeichnisse.
- JSONL-Log `~/.simpleft8/qrz_upload_YYYY-MM-DD.log` (Daily-Rotation,
  Mike: „log ob die daten nach qrz ok hochgeladen wurden")
- Rate-Limit-Detection: 20 consecutive fails → 60s Cooldown
  (Loop mit Cancel-Check, `cooldown_tick(int)` Signal pro Sekunde,
  KEIN blockierendes `time.sleep`) → 2. Burst → Cancel.

**R1-Fixes (Final-Review, vor Push):**
- `shutil.move` Ueberschreib-Schutz: `dest.exists()`-Check, skip + Toast
- `total_records`-Property statt direkter `_records`-Zugriff (Kapselung)

**Geaenderte Files (8):**
- NEU `tests/test_p1_qrz_upload_ui_2.py` (20 Tests)
- `core/qrz_upload_worker.py` (file_results + log + rate-limit
  + total_records)
- `ui/qrz_upload_dialogs.py` (QRZUploadDialog-Klasse weg)
- `ui/mw_qso.py` (_on_qrz_upload Rewrite + 6 neue Slots/Helpers)
- `ui/main_window.py` (Statusbar-Widget Init + qso_log+locator_db
  Multi-Dir + closeEvent cooldown_tick disconnect)
- `ui/logbook_widget.py` (load_adif Multi-Dir)
- `tests/test_p1_qrz_upload_ui.py` (4 Progress-Dialog-Tests geloescht)
- `main.py` APP_VERSION 0.95.14 → 0.95.15

**Voller Workflow:** V1 → V2 (14 Lessons L1-L14, mid-V2 Mike-Feedback
L13/L14) → R1 (Plan freigegeben + 7 Optimierungen) → V3 (Compact-fest,
8 Diffs) → Compact → Code → Final-R1 (2 SOLLTE-FIX gefixt).

**Plan-Files:** `prompts/p1_qrz_upload_ui_2_v[1-3].md`.

**Tests 872 → 888 gruen** (+16: -4 Dialog +18 V3 +2 R1-Fix).
Atomare Commits `d8f86b6` (Code+Tests, 11 Files +2534/-204) + Doku.

**KP-1/2/3 aus v0.95.14 noch intakt** (Bulk-Skip, Klick-Sperre 3-fach,
closeEvent disconnect — jetzt erweitert um cooldown_tick).

**Field-Test ausstehend.** Push noch nicht — Mike-Freigabe nach
Field-Test einholen.

**P2.ADIF-ARCHIVE folgt:** Standalone-Helper `tools/adif_archive.py`
fuer Jahresarchive `archiv/2024.adi`/`2025.adi` aus `adif/hochgeladen/`
(separater Workflow nach P1-2-Field-Test).

---

**Vorher v0.95.14 (07.05.2026):** **P1.QRZ-UPLOAD-UI: Confirm + Progress
+ Single-Instance.**

**P1.QRZ-UPLOAD-UI (NEU):** Bulk-Upload an QRZ.com mit sichtbarem
Status-Fenster, Cancel-Moeglichkeit, Single-Instance-Schutz 3-fach.
Field-Test 07.05. 10:35 entdeckte: 8x Klick = 8 Bulk-Jobs queued
(~8h Duplikat-Spam Risiko). App rechtzeitig gekillt.

**Loesung:**
- Phase 1: `QRZConfirmDialog` modal — „X QSOs hochladen?" Default Hochladen.
- Phase 2: `QRZUploadDialog` non-modal mit StaysOnTopHint, ProgressBar,
  Counter, Cancel + Auto-Close 10s.
- Worker `QRZUploadWorker` (QObject + ThreadPoolExecutor + Signals +
  threading.Event cancel).
- Single-Instance 3-fach: `_qrz_bulk_active`-Flag + Button-Disable +
  Re-Entry-Check (defensive first-line in `_on_qrz_upload`).

**R1-KP-Findings im Plan-Review:**
- KP-1: `_qrz_upload_single` skipt bei `_qrz_bulk_active=True`
- KP-2: Klick-Sperre Reihenfolge Flag → Button → submit
- KP-3: closeEvent disconnect()-vor-cancel()

**Final-R1-Findings im Code-Review (sofort gefixt):**
- 🚨 Cancel-Bug: Worker emittet IMMER finished (sonst Dialog haengt bei
  Sofort-Cancel)
- ⚠️ KP-3 Rest: closeEvent disconnect() VOR cancel()

**Geaenderte Files (10):**
- NEU `core/qrz_upload_worker.py`, `ui/qrz_upload_dialogs.py`,
  `tests/test_p1_qrz_upload_ui.py`, `prompts/p1_qrz_upload_ui_v[1-3].md`
- `ui/mw_qso.py` (`_on_qrz_upload` Rewrite + Slot + Helper +
  `_qrz_upload_single` Bulk-Skip)
- `ui/main_window.py` (closeEvent disconnect+cancel+shutdown)
- `ui/logbook_widget.py` (`_btn_upload`-Reference + Public-API)
- `main.py` APP_VERSION 0.95.13 → 0.95.14

**Voller Workflow:** V1 (5 Probleme + Field-Test-Beweis) → V2 (12 Lessons
L1-L12) → R1 (9 Pruefauftraege beantwortet, 3 KP gefunden) → V3
(Compact-fest, 7 Diffs) → Compact → Code → Final-R1 (Cancel-Bug +
KP-3-Rest gefunden) → Fix-Round → R1-Verifikation („Push freigegeben").

**Tests 862 → 872 gruen** (+10 in `tests/test_p1_qrz_upload_ui.py`).
Atomare Commits `2270fdf` (Code+Tests, 10 Files +1841/-29) + Doku-Commit.

**KEIN Resume-Feature** (KISS, QRZ.com filtert serverseitig).

**Field-Test ausstehend.** Push noch nicht gemacht — Mike-Freigabe nach
Field-Test einholen.

---

**Vorher v0.95.13 (07.05.2026):** **P1.CACHE-SIMPLE Diversity/Gain
entkoppelt + UX-Cleanup.**

**P1.CACHE-SIMPLE (NEU):** Mike-Vision: Diversity-Cache (Ratio, 60 Min)
und Gain-Cache (6h) komplett entkoppelt. Keine Modal-Wahl-Dialoge fuer
Routine-Aktionen.

**Logik (`_check_diversity_preset` Dispatch):**
- Gain stale  → DXTuneDialog auto-start (nur Abbruch). Wenn Ratio fresh:
                nach Gain-OK Cache-Reuse statt Phase 3.
- Gain missing → volle Pipeline (Gain + Ratio).
- Gain fresh + Ratio fresh → Cache-Reuse (still, kein Toast).
- Gain fresh + Ratio stale/missing → stille Auto-Ratio-Messung.

**Plus Stale-Acceptance** in `_on_dx_tune_rejected`: Cancel mit alten
Werten → laden, kein Pipeline-Restart. Wenn nichts da: Diversity AUS.

**Aenderungen mw_radio.py:**
- `_try_diversity_cache_reuse` Gain-Check entfernt
- NEU `_get_diversity_store` + `_assess_ratio` + `_assess_gain` Helpers
- `_check_diversity_preset` komplett refactort (Dispatch-Logik)
- `_on_dx_tune_accepted` `_pending_ratio_status`-Pfad
- `_on_dx_tune_rejected` Stale-Acceptance + Disable-Fallback
- `_activate_diversity_with_scoring` Wahl-Dialog raus, delegiert zu
  `_check_diversity_preset` (~70 Zeilen Code-Deduplikation)

**Toast-Cleanup (Mike: „Computer faehrt runter — OK?"-Pattern raus):**
- `ui/diversity_cache_toast.py` geloescht
- Toast-Aufruf bereits zuvor entfernt (uncommitted, jetzt mit-committed)
- Smoke-Test entfernt

**Voller Workflow:** V1 (Diagnose 4 Probleme) → V2 (Self-Review, 12 Lessons
L1-L12) → R1-Plan (8 Pruefauftraege detailliert beantwortet, kein Veto) →
V3 (Compact-fest, 6 Diffs konkret) → Compact → Code → Final-R1
(„Keine KP-Findings, Code ist robust und entspricht der Mike-Vision. ✅").
Plan-Files: `prompts/p1_cache_simple_v[1-3].md`.

**Tests 852 → 862 gruen** (+10 in `tests/test_p1_cache_simple.py` + 1
invertiert in `test_diversity_cache_reuse.py`). Atomare Commits `4af2e9e`
(Code+Tests, 5 Files +508/-277) + Doku-Commit. APP_VERSION 0.95.12 →
0.95.13.

**Field-Test ausstehend.** Push noch nicht gemacht — Mike-Freigabe nach
Field-Test einholen.

---

**Vorher v0.95.12 (07.05.2026):** **P1.FORCESEND btn_advance state-aware
+ WAIT_73-Branch.**

**P1.FORCESEND:** Mike's Use-Case bei stuck-Gegenstation: manuell
RR73 oder 73 senden statt 3-Min-Timeout. Bestehender `btn_advance`
wird state-aware:

- Label dynamisch (`R+Report` / `RR73` / `73` / `Weiter →`)
- Enabled in {WAIT_REPORT, WAIT_RR73, WAIT_73} (vorher nur erste 2)
  AND nicht cq_mode AND nicht diversity_locked
- `advance()` WAIT_73-Branch sendet 73, setzt `courtesy_73_sent=True`
  + idempotent-Return wenn Auto-Pfad schneller war (Final-R1 Race-Fix)

**Voller Workflow:** V1 → V2 (10 Lessons, Bug-A-Halluzination eingestanden)
→ R1 („Plan freigegeben unter Bedingungen 1-5", KP-1 als Halluzination
verworfen) → V3 → Code → Final-R1 („Push freigegeben mit Vorbehalt:
idempotent-Return" → sofort umgesetzt). Plan-Files:
`prompts/p1_forcesend_v[1-3].md`.

**Tests 841 → 852 gruen** (+11 in `tests/test_p1_forcesend.py`).
Atomare Commits `c8bf5bb` (Code+Tests+main.py 5 Files +177/-2) +
Doku-Commit. APP_VERSION 0.95.11 → 0.95.12.

**Lesson:** V1-Halluzination ist auch nach 2 Jahren Workflow noch real.
Grep zu eng → `_on_state_changed`-Hook übersehen. V2-Self-Review fing
es ab — Workflow funktioniert.

---

**Vorher v0.95.11 (06.05.2026):** **P1.ANTENNE-COLLAPSE _AntenneCard
einklappbar.**

**P1.ANTENNE-COLLAPSE:** Mike-Designentscheidung 06.05.: Antennen-
Kachel WIRD einklappbar (DeepSeek-Konvention „alles sichtbar" überschrieben).
Hobby-Use-Case: stundenlang auf einem Band, Kachel selten gebraucht →
wegklappen, Platz für QSO/RX-Panel.

**Architektur:** Header-Row mit Toggle-Button (`▼`/`▶`) + `_body_widget`-
Container für alle bisherigen Body-Widgets. API `set_collapsed/is_collapsed/
_toggle_collapsed`. Signal `collapse_changed` NUR bei User-Klick (nicht
bei Programm-API → Init-Loop-Schutz). `ControlPanel` forwardet via
`antenne_collapse_changed.emit`. `MainWindow` lädt Initial-State aus
Settings, persistiert User-Toggles. `setMaximumHeight(36)` bei Collapse.

**Workflow:** V1 → V2 (16 Lessons) → R1 („freigegeben + 5 KP") → V3 →
Code → Final-R1 („Push freigegeben"). Plan-Files: `prompts/p1_antenne_
collapse_v[1-3].md`.

**Tests 831 → 841 gruen** (+10 in `tests/test_antenne_card.py`).
Atomare Commits `a0ce1ae` + Doku. APP_VERSION 0.95.10 → 0.95.11.

**Settings-Key:** `antenne_card_collapsed` (bool, default False).

---

**Vorher v0.95.10 (06.05.2026):** **P1.AP-FIX generate_candidates
State-1 Format-Bug.**

**P1.AP-FIX:** P1.AP E2E-Test-Pipeline (v0.95.9, hardware-frei mit
ft8lib + Gauß-Rauschen) entdeckte den Bug: `core/ap_lite.py:126`
`generate_candidates(state=1)` produzierte 4-Token-Strings
(`OWN THEIR LOC SNR`, z.B. „DA1MHH DK5ON JO31 +05"). FT8 erlaubt nur
3 Tokens pro Frame → ft8lib lehnt jeden Kandidaten mit `rc=5` →
alle Korrelations-Scores=0 → **State-1-Rescue (WAIT_REPORT) scheiterte
IMMER silent seit AP-Lite-Implementierung**.

**Fix (1 Zeile, KISS):** Locator weglassen, Report-only:
```python
candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")
```
Plus Code-Kommentar Z.121-131 fachlich aktualisiert.

**Voller Workflow:** V1 (Diagnose) → V2 (Self-Review, 9 Lessons) → R1
(„Plan freigegeben") → V3 (5 Compact-feste Diffs) → Compact → Code →
Final-R1-Codereview („Push freigegeben, keine Vorbehalte").
Plan-Files: `prompts/p1_ap_fix_v[1-3].md`.

**Tests 830 → 831 gruen** (+1 maschineller Format-Schutz):
- `test_generate_state1_basic` — 3-Token-Asserts mit Regex
- `test_try_rescue_state1_runs_after_fix` (umbenannt) — kein silent-Block
- `test_generate_candidates_state1_format_correct` (umbenannt) — 3-Token
- `test_generate_candidates_state1_ft8lib_compatible` **NEU** — ruft
  `encoder.generate_reference_wave()` für jeden Kandidaten → ft8lib-Reject
  schlägt sofort an

**Code:** `core/ap_lite.py:121-131`. Atomare Commits `17b7237`
(Code+Tests+main.py 4 Files +79/-36) + Doku-Commit.

**APP_VERSION:** 0.95.9 → 0.95.10.

**Field-Test:** Mike ist in Kur — Test post-Rückkehr. Erwartung: Rescue-
Rate steigt. Notbremse: `AP_LITE_ENABLED=False`.

---

**Vorher v0.95.9 (06.05.2026):** **P1.24 TX-Klick-Buffer (Folge-Fix
zu P1.14, Field-Test bestätigt).** TX-Klick wurde ignoriert wenn
`encoder.is_transmitting=True`. Fix: Buffer-Logik mit State-Cleanup
+ `_pending_station_click` + Statusbar + rekursiver Replay in
`_on_tx_finished`. Tests 812 → 816 gruen.

---

**Vorher v0.95.8:** **P1.14 Station-Wechsel-Bug +
P1.23 Status-UI-Feinjustierung.**

**P1.14 (voller Workflow V1→V2→R1→V3 Diagnose + Plan-V1→V2→R1→V3):**
6 Bug-Wurzeln W1-W6:
- W1: `start_qso` resetete keine Pendings bei `state != IDLE` → Geister-
  Pendings mit alter `their_call`
- W2: angeklickte Station blieb in `_caller_queue` → Doppel-QSO-Risiko
- W3: `_active_qso_targets` wuchs monoton bei Wechseln
- W4/KP6: `_was_cq` State-Machine-extern korrigiert (Plan-V2: BEHALTEN —
  saubere Integration unmöglich, stop_cq() läuft vor start_qso())
- W5: TX-Klick silent ignoriert → Statusbar-Toast „TX aktiv – Klick
  ignoriert" (3s)
- W6: `auto_hunt._manual_override` wurde NIE zurückgesetzt — Auto-Hunt
  pausierte dauerhaft nach manuellem QSO/HALT/Timeout. Fix: `on_manual_qso_end()`
  in `_on_cancel`, `_on_qso_confirmed`, `_on_qso_timeout` (Plan-V2-Erweiterung).

Code-Änderungen: `core/qso_state.py:start_qso` (Reset-Set + 3 Pendings),
`ui/mw_qso.py` (5 Stellen: _on_station_clicked, _on_cancel,
_on_qso_confirmed, _on_qso_timeout).

**P1.23 UI-Feinjustierung:** Label „Lokale Empfangsqualität:" (statt
„Lokaler Empfang:"), Status-Schriftgrößen 11→10px, Sterne 15→13px.

Tests 802 → 812 grün (+10 in `tests/test_p1_14_station_switch.py`).
APP_VERSION 0.95.7 → 0.95.8.

---

**Vorher v0.95.7:** P1.18 DT-Drift Wurzel-Fix + P1.21 Sterne-UX-Refactor.
DT-Bug war 1 vergessene Konstante in v0.95.3 (`_WAKE_OFFSETS["FT8"]`
1.5→2.5 erhoeht, `_DT_OFFSETS["FT8"]` blieb 2.0 statt 3.0). Mike-Hartnaeckigkeit
+ git-diff + DeepSeek bestaetigt. Sterne: Label `Empfang:`, Gold #FFD700,
RichText, Score nur SNR (-10/-14/-18/-22 dB).

**Vorher v0.95.6:** P1-Bundle1 (5 UI-Cleanups: P1.6+P1.12+P1.15+P1.16+P1.19).

**Sub-Aufgaben umgesetzt:**
- **P1.6** Versionsnummer Color #333 → #666 (lesbar)
- **P1.12** NEU-Button (`btn_remeasure`) entfernt — KALIBRIEREN macht alles seit v0.94
- **P1.15** Statusbar `→ Call | RX: ANT` raus — Mike's Wunsch
- **P1.16** QSO-Panel zeitbasiertes 5-Min-Rolling-Window (statt 40-Zeilen)
- **P1.19** 5-Sterne-Anzeige `★★★☆☆` ersetzt SNR-Label (lokale Conditions)

**APP_VERSION:** 0.95.5 → 0.95.6.

**Field-Test offen:** Mike testet im Praxis-Betrieb (Sterne sollten je nach
Conditions schwanken; KALIBRIEREN funktioniert weiter).

---

**Vorheriger Stand 2026-05-05:** **v0.95.5 — Single-Instance-Lock**
(`24aba07` + `f348763` + `13c067f`). Garantiert nur EINE Instanz, schuetzt
fremde main.py-Apps (Websdr) vor Kollateral-Kill via lsof CWD-Filter.

**Vorher v0.95.4 — P1.10 Courtesy-73:** Atomare Commits `9783583`. Wurzel:
IC-7300 Auto-Sequence wartet auf abschliessendes Hoeflichkeits-73. Fix:
neuer State `TX_73_COURTESY` + Feld `qso.courtesy_73_sent`. Field-Test
BESTAETIGT (16:59 UTC EA2BHE). Tests 764 → 777 gruen.

## 🟢 OFFEN nach v0.95.4 (Liste fuer naechste Session)

### ✅ P1.10 Field-Test BESTAETIGT (Mike 16:56-:59 UTC, EA2BHE Spanien)
QSO mit EA2BHE (echte Station, Locator IN83):
- 16:59:00 RR73 → 16:59:15 EA2BHE 73 → 16:59:30 unser Courtesy-73
- KEIN weiteres 73 von EA2BHE → Auto-Sequence sauber gestoppt
- ✓ QSO komplett, CQ-Modus laeuft weiter

**Pattern bestaetigt:** Courtesy-73 funktioniert mit Standard-FT8-Apps
(WSJT-X, JTDX, MSHV). Echte Stationen weltweit akzeptieren das
abschliessende 73 sauber.

### ✅ IC-7300 Endlos-73 GEKLAERT (Mike 2026-05-05) — KEIN Bug
**Wurzel:** Mike's SDR-Control hatte **Retry=99** in den Auto-Sequence-
Einstellungen (Test-Override). Mit Retry=99 sendet SDR-Control 99× sein
73 wenn keine "QSO-Ende-Bestaetigung" kommt. Das ist **Mike's eigene
Test-Konfiguration**, kein SimpleFT8-Bug, kein SDR-Control-Bug.

**SDR-Control-Verhalten (laut Help-Text vom Entwickler):**
> „Meine App wartet nach RR73 einen Taktzyklus und antwortet, falls
> sie eine weitere 73-Nachricht korrekt empfaengt, ebenfalls mit einem
> 73 — fuer zuverlaessige QSO-Protokollierung."

Das ist **identisch zu P1.10's Courtesy-73-Logik**. Beide Apps machen
also dasselbe Standard-Verhalten. Bei Mike's Retry=99 → 99× 73-Spam.
Bei Standard-Retry (1-3) → max 3 73-Slots, sauberer Abschluss.

**Loesung:** Mike setzt SDR-Control Retry auf Standard (1) zurueck.
Kein Code-Aenderung in SimpleFT8 noetig.

**12000-QSO-Erfahrung erklaert:** Mike hatte Retry=99 erst kuerzlich
fuer Test gesetzt. Vorher mit Standard-Retry und gegen WSJT-X-Stationen
(senden 1× 73, kein Retry) gab es nie ein Problem.

### ✅ P1.9 Field-Test BESTAETIGT (Mike 11:18-:24 UTC, 2 QSOs DA1TST)
QSO 1 (11:19:45 RX → 11:20:00 Report, Replace mit -20).
QSO 2 (11:22:15 RX → 11:22:30 Report, Replace mit -23).
2/2 Replace-Pfad genommen, kein „erster Ruf ignoriert" mehr. Bug tot.

### 🟡 P1.11 — `rr73_retries`-Counter shared (NEU aus Plan-R1 F1, 05.05.)
Bestehender Bug, NICHT durch P1.10 verschaerft. `qso.rr73_retries` wird
in WAIT_RR73 (`qso_state.py:346`) UND in WAIT_73-Hoeflichkeits-Pfad
(`qso_state.py:589-590`) inkrementiert/getestet. Wenn QSO viele
WAIT_RR73-Retries hatte (z.B. 2 von 3), bleibt fuer WAIT_73-R-Report-
Hoeflichkeit nichts uebrig. Fix: separates Feld `wait_73_retries` oder
Reset bei WAIT_73-Eintritt. ~1 Stunde Aufwand, KISS.

### ✅ P1.5 Field-Test BESTAETIGT (Mike 09:35-:44 UTC, 4 QSOs in Folge)
SP6AXW + DA1TST + HA0GK (aus Warteliste) + S50XX alle erfolgreich.
Bekannte Stationen koennen wieder anrufen, Caller-Queue-Pop funktioniert.
P1.5-Symptom „App ignoriert komplett" ist weg.

### 🟡 P1.8 — Report-SNR-Bug `_last_snr` statt `msg.snr` (NEU 2026-05-05)
Wir senden Reports mit schlechteren dB-Werten als wir empfangen
(z.B. DA1TST: wir -23, er R+19 = 42 dB Diff). Wurzel: `_last_snr`
wird fuer jede msg im Slot ueberschrieben → letzte/schwaechste msg-SNR
wird verwendet. Fix: `msg.snr` direkt in `_process_cq_reply` (qso_state.py:
218, 233). Voller V1→V2→R1→V3, NACH P1.9 + P1.10. Siehe TODO.md P1.8.

### ✅ P1.6 — Versionsnummer-Anzeige (ERLEDIGT v0.95.6 / Bundle1)
Color `#333` (auf `#1a1a2e` unsichtbar) → `#666` (lesbar, Theme-konform).

### 🟢 P1.7 — Lokaler Duplikat-Filter ADIF/Logbuch (NEU 05.05.)
Folgebug-Risiko aus P1.5-Fix: bekannte Station < 5 Min nach RR73
erneut anruft → zweites QSO + zweiter ADIF-Eintrag. QRZ.com filtert
serverseitig (REASON=duplicate), aber lokal nicht. Aufgabe: Duplikat-
Check in `log/adif.py` und `qso_log.add_qso` (gleicher Call+Band+Mode
binnen 60 Min → updaten oder skip + Info-Log). ~1 Tag Aufwand, KISS.

### Field-Test offen aus v0.94 (Liste fuer naechste Session)
- **v0.94 KALIBRIEREN-Button im Diversity-Modus** → Phase 2 + Phase 3
  laufen automatisch durch, Cache + 1h-Timer frisch
- **v0.94 Stats-Pause Phase 2 verifizieren** → waehrend DXTuneDialog
  laufen darf KEIN Stats-Logging mehr (~/.simpleft8/simpleft8.log)
- **v0.94 RX-Panel-Hardware-Antenne** → waehrend Phase 2 zeigt RX-
  Panel die Antenne aus _schedule[_step] (ANT1/ANT2 als A1/A2)
- **v0.93 Cache-Reuse beim Bandwechsel innerhalb 1 h** → 5-s-Toast
- **v0.93 FT2-Score-basierte Statistik** bei duenner Stations-Dichte
- **v0.93 1h-Frist** → nach 60 Min ohne QSO/CQ automatischer Re-Measure
- **v0.91 Block 1+2 Pipeline-Dauer messen** (Best-Case ~2:30, typisch ~3:20)
- **Antennen-Drossel-Beobachtung** (Mantelwellensperre 04.05.
  ausgebaut, 8-foermige Schlaufen)

### Code-Refactor offen
- **P2 Reply-Lag durch Audio-Buffer-Latenz** (TODO.md) — nach v0.95
  Display-Fix kann Mike den ECHTEN Reply-Lag am korrekten Slot ablesen.
  Falls Lag dann noch >1 Slot: separater Workflow (Wake-Offset +
  Audio-Buffer-Tuning, hardware-nah).
- **Single-Instance-Lock im App-Code** — robuster Schutz gegen
  Doppelstart (Lockfile vs TCP-Port). Memory:
  `project_v095_single_instance_lock.md`. Aktuell nur Memory-Regel fuer
  Claude (`feedback_app_start_single_instance.md`).

### Wartung
- **~50 neue Statistics-Files** committen (auswertung/ + statistics/
  Output-Files vom heutigen generate_plots-Run plus Decoder-Logs)
- **Stats-Sammlung 5 Tage flaechendeckend** pro Stunde-Modi-Slot
  (laut Memory `project_statistics_strategy.md`)

---

Mike's Field-Test-Befund 05.05.: RX-Panel zeigte waehrend Phase 2
"A1" fuer Station die im DXTuneDialog-Bucket "ANT2 G20" landete.
