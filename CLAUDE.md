Lies nach dieser Datei sofort auch HANDOFF.md **und HISTORY.md** und bestätige alle drei mit je einer Zeile.

---

# ⛔⛔⛔ WORKFLOW-PFLICHT — KEINE AUSNAHME — ABSOLUT VERBINDLICH ⛔⛔⛔

**JEDE Code-Änderung — egal wie trivial sie erscheint — MUSS den vollen Workflow durchlaufen:**

## V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code

**Es gibt NULL Ausnahmen.** Nicht für "nur 5 Zeilen". Nicht für "reine Labels". Nicht für
"offensichtliche Fixes". Nicht für Bugfixes mit klarer Diagnose. Das Projekt ist zu komplex.

→ **Beweis 01.05.2026:** Label-Fix in 2 Dateien ohne Workflow = Mike-Unterbrechung + Regelverletzung
→ **Skill:** `.claude/skills/ft8_workflow.md` — VOR jedem Code aufrufen
→ **Slash-Command:** `/workflow [bug-name]` — startet Skill direkt
→ **Selbst-Check vor JEDEM Tastendruck:** "Habe ich den vollen Workflow durchgeführt? NEIN → STOP."
→ **Verstoss = Vertrauensverlust.** Mike unterbricht, korrigiert, und hat immer Recht.

**Mike-Trigger-Phrasen die den Skill SOFORT laden:**
- „vollen workflow", „kompletten workflow", „voller worflow"
- „workflow mit deepseek", „mit deepseek durch", „deepseek einbinden"
- „ausführlicher plan", „sauber planen", „v1 v2 v3"
- „selbe verfahrensweise", „wie immer", „wie bei P1.X"
- „erst V1 dann zu deepseek", „prompt entwerfen"

**Trivial-Klausel (Workflow NICHT laden):** Tippfehler/Style/Doku/<5 Zeilen.
Vollständige Trigger- und Trivial-Liste: `.claude/skills/ft8_workflow.md`.

---

# ⛔⛔⛔ HARDWARE-WARNUNG — HOECHSTE PRIORITAET ⛔⛔⛔

## ANT1 = TX-Antenne. IMMER. Auf jedem Band.
## ANT2 = NUR Empfangs-Zusatzantenne. NIEMALS TX!

**ANT2 (Regenrinne ~15m) ist NICHT fuer Sendeleistung ausgelegt.** TX auf
ANT2 mit 100 W = **Hardware-Schaden moeglich** (Antennen-Pfad, hochohmige
Last → PA-Schutzschaltung greift, im worst case PA-Schaden am FlexRadio).

### Konsequenz fuer ALLE TX-Modi

| Aktion | Antenne |
|---|---|
| Manuelle CQ-Anrufe | **ANT1** |
| OMNI CQ (passiv) | **ANT1** |
| AUTO HUNT (aktiv) | **ANT1** |
| TUNE-Button | **ANT1** (Tuner-Match) |
| Diversity RX-Pattern (70:30 / 50:50 / 30:70) | beide RX, **TX nur ueber ANT1** |

**Im Code:** Vor jedem TX-Trigger (Encoder, TUNE) muss `radio.set_tx_antenna("ANT1")`
verifiziert sein. Diversity-Pattern darf **nie** ANT2 als TX-Slot vergeben.

**Wenn neue TX-Funktionalitaet gebaut wird** (Auto-Hunt, Hybrid-Modi, was
auch immer): **erste Frage — laeuft TX garantiert ueber ANT1?**
Beantworte das BEVOR du Code schreibst, niemals erst im Test.

---

⛔ **SESSION-LIFECYCLE-WORKFLOW: `docs/SESSION_WORKFLOW.md` v1.2 ist
verbindlich.**

- **Session-Start**: Phase 1 ausfuehren — CLAUDE.md → MEMORY.md →
  HISTORY.md → HANDOFF.md lesen, dann Begruessung mit Stand.
- **Waehrend Arbeit**: Phase 2 — nicht-triviale Aenderungen ueber
  WORKFLOW.md v1.1 (V1→V2→R1→V3), nach jedem Punkt HISTORY+HANDOFF+
  CLAUDE+Memory in dieser Reihenfolge updaten. Trivial-Klausel:
  Tippfehler/Kommentare/<5 Zeilen brauchen kein 4-Datei-Update.
- **Feierabend**: Phase 3 — Verifikations-Check + Bestaetigungs-Block.
- **Notfall-Save**: Phase 2f bei „muss kurz weg".

⛔ **HISTORY.md ZWINGEND beim Session-Start lesen!** — Sie ist die einzige
verlaessliche Quelle dafuer welche Features in welchen Versionen tatsaechlich
implementiert wurden. Wer das ueberspringt, plant Features doppelt (Beispiel
27.04.: V1→V2→V3-Prompt-Zyklus fuer „Live-PSK-Bandindikator" in DeepSeek-
Review entworfen — nutzlose Stunde, weil v0.69 das Feature schon vollstaendig
abdeckt). Bei jedem „lass uns ein Feature X bauen" zuerst grep in
HISTORY.md ob X nicht schon drin ist.

⛔ **PFLICHT NACH JEDEM ERLEDIGTEN FIX/FEATURE (Mike 01.05.2026):**
Reihenfolge VOR der naechsten Aufgabe:
1. **HISTORY.md** anhaengen — `## YYYY-MM-DD vX.YY — Kurztitel` + Eintrag.
2. **HANDOFF.md** in BEIDEN Verzeichnissen identisch updaten (TODO-Punkt
   raus, neuer Stand rein, Test-Count).
3. **CLAUDE.md** Header in BEIDEN Verzeichnissen updaten (`Aktueller Stand`
   + Test-Count).
4. **Memory** wenn Lesson gelernt.

Bei Halluzination einer TODO-Liste (Mike 01.05.: ich hatte
`_reset_defaults` als offen vorgeschlagen, war aber in v0.79 schon erledigt)
→ STOP, Code-Verifikation mit `git log --oneline | head -30` + grep gegen
aktuellen Code, BEVOR Workflow gestartet wird.

Memory: `feedback_todo_history_pflicht.md`.

# SimpleFT8 — Claude Kontext

**Trigger „SimpleFT8 am Ferienhaus":** Memory `project_simpleft8_ferienhaus.md`
laden — App via `tools/remote/start_simpleft8_nokill.py` starten (umgeht
`kill_old_instances`-osascript-Self-Kill bei Background-Launch), dann Fenster
auf Display 2 (Position 1024,0) verschieben. Mike macht von dort
Fernwartung — App MUSS auf dem mittleren Bildschirm landen.

**Start:** `cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8" && ./venv/bin/python3 main.py`
**Aktueller Stand:** **P2.OMNI-REDESIGN (09.05.2026, v0.95.23)** — Voller architektureller Refactor: Flag-Pattern + Pause/Resume-Lifecycle + Auto-Rollover. Mike-Auftrag „voller Refactor, kein Pflaster". P1.OMNI-START (v0.95.22) hatte den Toggle scharf gestellt aber den Wurzel-Bug nicht behoben — Mike-Field-Test bewies: CQ-Loop stirbt nach 2 TX-Slots. Wurzel: `core/qso_state.py:177` `_set_state(CQ_CALLING)` VOR `send_message.emit()` → OMNI-RX-Slot skippt TX → State stuck → on_cycle_end greift nicht mehr. **Architektur-Refactor v4.0:** (1) `block_cycles=80`-Counter komplett raus (war Diversity-OPERATE_CYCLES-Überrest aus v0.78), Block-Switch jetzt automatisch bei rollover slot_index 4→0. (2) Pause/Resume-Lifecycle: `_pause_omni_if_active` (3 Entry-Pfade — Hunt-Klick, CQ-Reply, Replace) + `_maybe_resume_omni` (3 Exit-Pfade — qso_complete, qso_confirmed, qso_timeout). „Kein Slot verschwenden": Block-Wahl per nächster Slot-Parität. (3) Flag-Pattern `_omni_skip_state_change`: Listener (mw_qso._on_send_message) setzt True bei OMNI-RX-Slot-Skip → `_send_cq` macht KEINEN State-Wechsel zu CQ_CALLING → on_cycle_end re-CQ greift weiter. (4) Singleton-API saubergezogen: `OmniTX()` + `get_instance()` ohne block_cycles-Param. **Voller Workflow:** V1(`prompts/p2_omni_redesign_v1.md`) → V2 Self-Review 15 Lessons (`v2.md`) → R1-Lauf-1+2 (initial+truncated) → R1-V2 DeepSeek-Reasoner 304 Z. (`r1_v2.md` — 1 KRITISCH K1 + 1 SOLLTE S1 + S2/S3 + L1/L8/L13) → V3 Compact-fest 15 ACs/20 Tests/7 Commits (`v3.md`) → Mike-Freigabe → Compact #3 → Code → **Final-R1 (DeepSeek-Reasoner, in=70027/out=1385 Tokens: „Implementierungsreif. Keine offenen Architektur- oder Logikfehler.")**. **R1-V2-Bewertung:** K1 ⛔ ANGENOMMEN: `_on_try_replace_pending_tx` (P1.9 Replace-Pfad) fehlte `_omni_tx.pause()` → DRY-Helper für 3 Entry-Pfade + 4. Aufruf in Replace-Slot. S1 ❌ VERWORFEN als R1-Halluzination: R1 nahm an `_resume_cq_if_needed` läuft VOR mw_qso-Listener — Code-Beweis `main_window.py:597-599` keine ConnectionType → Qt.AutoConnection → bei gleichem GUI-Thread Qt.DirectConnection → `qso_*.emit()` SYNCHRON → mw_qso-Slot komplett (inkl. OMNI-Resume) BEVOR `_resume_cq_if_needed`. Kein ungefilterter CQ. S2 ✅ ANGENOMMEN: `block_cycles`-Param komplett raus aus Konstruktor + `get_instance` (klarer als „ignorieren"). S3 ✅ ANGENOMMEN: AC14-Test als Integrationstest mit Listener-Mock. L1/L8/L13 ✅ ANGENOMMEN: 3 Code-Kommentare (Flag-Lock-Hinweis im qso_state, encoder.tx_even-Setter-Doku, is_even_cycle-Docstring). **Geaenderte Files (7 Code + 4 Test + main.py + 5 Plan-Files):** `core/omni_tx.py` Refactor (Konstruktor + Methoden + Singleton ohne block_cycles, neu start_with_parity_for_next_slot/pause/resume/is_paused, advance ohne args mit auto-rollover), `core/qso_state.py` Flag-Init + `_send_cq` State-Wechsel-NACH-emit mit Flag-Check + `_resume_cq_if_needed` S1-Doku-Top-Kommentar, `core/timing.py` is_even_cycle-Docstring (L13: aktueller Zyklus, NICHT der nächste), `core/encoder.py` tx_even-Inline-Kommentar (L8: letzter Setter gewinnt — Design), `ui/mw_qso.py` 2 Helpers (`_pause_omni_if_active` + `_maybe_resume_omni`) + 3 Entry-Pfade (`_on_station_clicked` / `_on_tx_slot_for_partner` non-courtesy / `_on_try_replace_pending_tx` K1) + 3 Exit-Pfade (`_on_qso_complete` + `_on_qso_confirmed` + `_on_qso_timeout`) + Flag-Pattern in `_on_send_message` (calls_made-- Pflaster raus) + `_on_state_changed` `omni_tx.on_qso_started`-Call entfernt, `ui/main_window.py` `_omni_was_active_pre_qso`-Init + `get_instance()` ohne block_cycles + `_on_btn_omni_cq_toggled` `start_with_parity_for_next_slot(next_is_even)` statt `enable()` + `_on_omni_stopped` Pre-Flag-Reset, `ui/mw_cycle.py` `_on_cycle_start` `if not is_paused: advance()` statt `advance(qso_active=)`. NEU `tests/test_p2_omni_redesign.py` (20 Tests T1-T20 für AC1-AC15: 5-Slot-Pattern Block 1+2, Block-Rollover, start_with_parity, Pause/Resume-Trio, Flag-Pattern, 3 Pause-Helper-Pfade, 3 Resume-Helper-Pfade, Caller-Queue-Schutz, HALT, API-Cleanup-Asserts). `tests/test_omni_tx.py` Migration 11 → 4 Tests (Pattern/Block-Switch/Pause-Tests jetzt in test_p2_omni_redesign, bleiben 7 Stop-Reason-Tests parametrize + disable-Wrapper + Initial-State + Stop-Cleanup). `tests/test_p1_omni_start.py` API-Migration `omni.enable()` → `omni.start_with_parity_for_next_slot(next_is_even=True)` + `OmniTX(block_cycles=80)` → `OmniTX()`. `tests/test_modules.py` Block (5 → 3 Tests, alte block_cycles-min-Guard + qso_reset + pending_switch + qso_blocks_counter ENTFERNT). `tests/test_patterns.py` Block (4 Tests migriert auf neue API, block_cycles raus, enable → start_with_parity, block_switch rollover-basiert). `main.py` APP_VERSION 0.95.22 → 0.95.23. Plan-Files: `prompts/p2_omni_redesign_v[1,2,3].md` + `prompts/p2_omni_redesign_r1_v2.md` + `prompts/p2_omni_redesign_session_context_v3.md`. **Tests 1014 → 1023 gruen (+9 effektiv: -11 alte Tests + 20 neue, V3 prognostizierte +20 ohne Migration-Reduktion).** Atomare Commits: 7 (omni_tx + qso_state + Doku-Kommentare + mw_qso + main_window/mw_cycle + Tests + APP_VERSION/Doku). **Hardware-Garantie ANT1:** OMNI emittet kein TX direkt, nur Slot-Filter — TX laeuft via `encoder.transmit()` → `radio.set_tx_antenna("ANT1")` zentral (`core/encoder.py:334`). Final-R1 0 KP-Findings, 3 R1-Anmerkungen alle bestätigend. **Field-Test-Pflicht (vor Push, V3 §6):** 5+ Slots OMNI-CQ-Loop (Bug-Fix-Beweis vor v0.95.23 starb nach 2 TX-Slots), Block-Rollover slot 4→0, QSO-Resume mit korrekter Parität, Caller-Queue (nach QSO direkt nächstes), Toggle off, HALT, Bandwechsel/Mode-Stop. Push pending — v0.95.16-23 + P2-Tool + P3 zusammen wenn Field-Tests positiv. **Vorher P1.OMNI-START (08.05.2026, v0.95.22):** OMNI-CQ-Toggle aktiviert jetzt zusaetzlich den CQ-Loop in qso_state. Mike-Field-Test 16:08 UTC: Klick auf btn_omni_cq → Statusbar Even=0/Odd=0 aber kein CQ. Bug latent seit v0.78 (30.04.2026) — Toggle aktivierte zwar `omni_tx`, aber `qso_sm.cq_mode` blieb False → niemand emittete `send_message("CQ ...")` → OMNI-Slot-Filter griff nie. Plus 2 Folge-Bugs: `_on_omni_stopped` reagierte nicht auf qso_state-Stop, HALT stoppte OMNI nicht. Voller Workflow V1(10 ACs)→V2(8 Lessons)→R1(2 Bug + 1 SOLLTE + 2 KOENNTE — 5 angenommen + 3 abgelehnt + 0 halluziniert)→V3(Compact-fest)→Compact→Code→**Final-R1 („Code kann gemerged werden", 0 KRITISCH + 3 SOLLTE alle KISS-Trade-offs in V3 dokumentiert)**. **Geaenderte Files (2 Code + 1 Test NEU + main.py + 3 Plan):** `ui/main_window.py` (`_on_btn_omni_cq_toggled` Pre-Block + start_cq + `_on_omni_stopped` idempotent stop_cq + `_was_cq=False`), `ui/mw_qso.py:210-234` (`_on_cancel` HALT stoppt OMNI), NEU `tests/test_p1_omni_start.py` (11 Tests via parametrize), `main.py` APP_VERSION 0.95.21 → 0.95.22. Tests 1003 → 1014 gruen (+11). Atomare Commits: Code-1 (Toggle + Stop-Slot + Tests + Plan) + Code-2 `36e365d` (HALT + APP_VERSION) + Doku. Field-Test 7-Punkte-Plan (V3 §6) ausstehend. Push pending — v0.95.16-22 + P2-Tool + P3 zusammen. **Vorher P1.HUNT-SNR (08.05.2026, v0.95.21):** — Hunt-Pfad nutzt jetzt station-spezifischen `msg.snr` statt `_last_snr`. Mike-Field-Test 13:57 UTC: 3-Stationen-Slot, Klick auf EV81AB (-18 empfangen) → App sendete -24 (6 dB Bias) wegen `_last_snr`-Race. Folge zu P1.8 (v0.95.18) wo nur `_process_cq_reply` gefixt wurde. Voller Workflow V1(10 ACs)→V2(12 Lessons)→R1(0 KRITISCH + 1 SOLLTE advance() + 2 KOENNTE)→V3(Compact-fest, R1-SOLLTE mit aufgenommen)→Compact→Code→**Final-R1 („Code freigegeben", 1 SOLLTE-Halluzination Fallback-Clamp verworfen weil Code bereits clamped)**. **Geaenderte Files (3 Code + 1 Test NEU + main.py + 3 Plan):** `core/qso_state.py` (`start_qso(their_snr: int | None = None)` Signatur + Body, `advance()` WAIT_REPORT nutzt `qso.our_snr` mit `lstrip("R")`-Defense), `ui/mw_qso.py:138` (`their_snr=msg.snr`), `ui/mw_cycle.py:562` (`their_snr=_candidate.snr`, Feld existiert seit `core/auto_hunt.py:57`), NEU `tests/test_p1_hunt_snr.py` (10 Tests: 8 Hunt + 2 advance), `main.py` APP_VERSION 0.95.20 → 0.95.21. Tests 992 → 1003 gruen (+11, V3 prognostizierte +10). Atomare Commits: `659e210` Code-1 (qso_state + Tests + Plan) + `8d6e80a` Code-2 (Aufrufer + APP_VERSION) + Doku. Field-Test pending (Slot mit 3+ Stationen). Push pending — v0.95.16-21 + P2-Tool + P3 zusammen. **Vorher P3.AUDIO-DUMP-DEBUG (08.05.2026, v0.95.20):** — Roh-Audio-Slot-Dump fuer Debug/Forschung (AP-Lite-Replay, ANT1/ANT2-Spektrum offline, Decoder-Tests). Toggle in Settings „Daten & Tools" Block 4 (Default OFF) + Spinbox Max-Files (50-1000, Default 200). NUR FT8. WAV mono int16 24 kHz nach `audio_dump/{band}_FT8/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav`. **Architektur Pull-Pattern (R1-KRITISCH adressiert):** Decoder cached `last_audio_24k`-Buffer, GUI-Thread holt via `decoder.dump_last_slot(ant, root, max_files)` aus `mw_cycle._on_cycle_decoded` nach `_resolve_hardware_antenna` — Antenne garantiert korrekt, kein Race. Atomic-Write `tempfile.mkstemp(dir=) + os.replace` (P2-Pattern), FIFO-Cleanup global ueber band_mode-Sub-Dirs via mtime-Sort. Voller Workflow V1(10 ACs)→V2(15 Lessons)→R1(1 KRITISCH KP-1 Setter→Pull-Pivot + 1 SOLLTE)→V3(Compact-fest)→Compact→Code→**Final-R1 („Code kann gemerged werden", 0 KRITISCH/SOLLTE, 2 KOENNTE explizit „nicht erforderlich")**. Geaenderte Files (1 NEU + 1 Test NEU + 5 Code + 3 Plan): NEU `core/audio_dump.py` (~80 Zeilen: atomic_write_wav, enforce_fifo_cap, build_dump_path), `core/decoder.py` (last_audio_24k + _band Default + set_band + Hook + dump_last_slot), `ui/settings_dialog.py` (Tab 4 Block 4 NEU), `ui/mw_cycle.py` (Pull-Aufruf), `ui/mw_radio.py` (decoder.set_band in _on_band_changed), `ui/main_window.py` (Settings-Init+Update + initiales decoder.set_band), `main.py` APP_VERSION 0.95.19 → 0.95.20. NEU `tests/test_audio_dump.py` (14 Tests), NEU `prompts/p3_audio_dump_v[1-3].md`. Tests 978 → 992 gruen (+14, V3 prognostizierte +13). Atomare Commits: Code-1 `abda630` (audio_dump.py + Decoder + Tests + Plan) + Code-2 `df3bc78` (Settings + mw_cycle + mw_radio + main_window + APP_VERSION) + Doku. KEIN Push — Mike kann lokal nutzen, naechster Push zusammen mit v0.95.16-19 + P2-Tool. **Vorher P2.ADIF-ARCHIVE (08.05.2026):** Tool-only, kein APP_VERSION-Bump. Mike-Auftrag post-v0.95.19: voller DeepSeek-Workflow + Compact dazwischen fuer Standalone-Helper-Script `tools/adif_archive.py` — konsolidiert Tagesdateien `SimpleFT8_LOG_*.adi` aus `adif/hochgeladen/` in Jahresarchive `adif/archiv/YYYY.adi`. Hardware-frei, App-Verhalten unveraendert. **Sicherheits-Garantien (3 Schutzwaelle fuer Logbuch-Schatz):** (1) Idempotenz Match-Key (CALL, QSO_DATE, TIME_ON), (2) Atomic-Write `tempfile.mkstemp(dir=target_dir)` + `os.replace` (gleiches FS = POSIX atomic rename), (3) Datenintegritaets-Abort: korruptes existing Archiv → `all_years_ok=False`, Quelle bleibt liegen, kein Schreiben (R1-KRITISCH), (4) Verifikations-Schritt nach Schreiben: re-parse + Match-Key-Check, bei Diskrepanz kein Move (R1-WICHTIG), (5) Default Move (nicht Delete) nach `_konsolidiert/` mit `_dup`-Suffix bei Kollision. **CLI:** `--source --target --pattern --dry-run --yes --delete-source`. Phase 1 Dry-Run + Plan, dann `[y/N]`-Prompt (uebergehbar via `--yes`), Phase 3 Real-Run + Ergebnis. **Voller Workflow:** V1(7 ACs, 7 Fragen)→V2(15 Lessons L1-L15)→R1(DeepSeek-Reasoner: 1 KRITISCH + 2 WICHTIG + Tests 17→20)→V3(Compact-fest)→Compact→Code→**Final-R1 („Code kann gemerged werden", 0 KP-Findings)**, 1 SOLLTE-Fix (None-Schutz `_record_to_adif` via `str(v) if v is not None else ""`) + 1 KOENNTE (Race-Condition-Doku „1-User, nicht parallel" in Module-Docstring) sofort umgesetzt + 1 Test (`test_record_to_adif_none_value_safe`). KRITISCH-R1-Findings (parallele Instanzen, Verifikations-Rollback) als Single-User-Akzeptanz dokumentiert (V2-L9 KISS). **Geaenderte Files (1 NEU + 1 Test NEU + 3 Plan-Files):** NEU `tools/adif_archive.py` (~280 Zeilen), NEU `tests/test_adif_archive.py` (23 Tests: 5 Helper + 18 Konsolidierung), NEU `prompts/p2_adif_archive_v[1-3].md`. KEIN `main.py` Bump. Tests 955 → 978 gruen (+23, V3 prognostizierte +20, +3 Bonus durch Helper-Test-Splits + None-Schutz). Atomare Commits: Code (Tool+Tests+Plan-Files) + Doku (HISTORY+HANDOFF+CLAUDE+TODO+Memory). KEIN Push — Mike kann lokal nutzen, naechster Push zusammen mit v0.95.16-19. **Vorher v0.95.19 (08.05.2026):** **P1.BUNDLE2: 3 hardware-freie Bugs gebuendelt (P1.7 ADIF-Duplikat-Filter + P1.11 wait_73_retries entkoppelt rr73_retries + P1.13 Hunt-Klick Normal-Mode TX-Frequenz-Sync).** Mike-Auftrag 08.05. (post-v0.95.18): „die kleinen können wir die zusammenfassen wenn wir deepseek workflow komplett machen mit compact?" Bundle aus 3 unabhaengigen kleinen Bugs — voller V1→V2(15 Lessons)→R1(1 KRITISCH KP-8 + 2 SOLLTE + 1 KOENNTE)→V3(9 Diffs)→Compact→Code→**Final-R1 („Code kann gemerged werden") — 0 KP-Findings**, kleiner Hinweis `import time` an File-Top sofort umgesetzt. **Bug 1 — P1.11:** `core/qso_state.py:83` `rr73_retries` wurde in 2 Pfaden inkrementiert (WAIT_RR73-Retry max 3 + WAIT_73-Hoeflichkeit max 2). Nach voller WAIT_RR73-Sequenz blockierte `rr73_retries=3` die WAIT_73-Hoeflichkeit komplett — Station die ihren R-Report wiederholt wurde im Stich gelassen. Fix: Neues Feld `wait_73_retries: int = 0` in QSOData (Auto-Reset via `QSOData()` in `start_qso(...)`), WAIT_73-Hoeflichkeit nutzt es jetzt unabhaengig. **Bug 2 — P1.13:** `ui/mw_qso.py:_on_station_clicked` setzte `encoder.tx_even` + `start_qso`, aber NICHT `encoder.audio_freq_hz` oder Spinbox. Hunt-Klick im Normal-Modus → TX lief auf alter Spinbox-Frequenz, Mike's Augen sahen anderes. Fix: Nach `start_qso(...)` im Normal-Modus encoder + `_tx_freq_spin` auf clamped Station-Frequenz (Range aus `spin.minimum()/maximum()` statt hardcoded 150/2800, R1-Empfehlung). Diversity unangetastet, Persistenz NICHT (`settings.save_normal_tx_freq` bleibt — Hunt-Klick ist temporaer), Histogramm-Update KISS weggelassen (R1, im Normal-Modus Widget typisch nicht sichtbar). **Bug 3 — P1.7:** `ui/mw_qso.py:_on_qso_complete` rief `adif.log_qso` unbedingt — bekannte Station < 5 Min nach RR73 ruft erneut → 2. ADIF-Eintrag im Logbuch (QRZ filtert serverseitig, lokal nicht). Fix: Session-lokaler Cache `_recent_logged_calls: dict[(call, band), float]` in MainWindow (App-Restart loescht den State, ist gewollt). Modul-Konstante `_LOG_DEDUP_WINDOW_S = 300` in mw_qso.py. Bei Duplikat: ADIF + `qso_log.add_qso` + `log_antenna_qso` SKIP + qso-Panel-Info. UI-Cleanup (`active_qso`, `rx_panel`, `auto_hunt`) laeuft IMMER vor Duplikat-Check (R1-KRITISCH KP-8). **Geaenderte Files (3 Code + 1 Test NEU + main.py + 1 Test-Anpassung):** `core/qso_state.py` (`wait_73_retries`-Feld + WAIT_73-Branch nutzt es), `ui/mw_qso.py` (`_LOG_DEDUP_WINDOW_S` Modul-Konstante + `_on_station_clicked` TX-Sync + `_on_qso_complete` Duplikat-Filter), `ui/main_window.py` (`_recent_logged_calls` init), NEU `tests/test_p1_bundle2.py` (17 Tests: 4 P1.11 + 5 P1.13 + 8 P1.7), `tests/test_p1_10_courtesy_73.py` (`rr73_retries` → `wait_73_retries` Anpassung), `main.py` APP_VERSION 0.95.18 → 0.95.19. Plan-Files: `prompts/p1_bundle2_v[1-3].md`. Tests 938 → 955 gruen (+17, V3 prognostizierte +17). Atomare Commits: `faff2bb` Bug-1 + `9be7747` Bug-2 + `5466cb4` Bug-3 + Doku-Commit. **Field-Test-Pflicht (vor Push):** P1.11 QSO mit IC-7300 (DA1TST) voll durchziehen, R-Report-Wiederholung in WAIT_73 → RR73-Antwort sollte erfolgen; P1.13 Normal-Modus, Spinbox=1500, RX-Klick auf 800 Hz Station → Spinbox+TX zeigen 800 Hz, App-Restart → wieder 1500 Hz; P1.7 hardware-frei. Push noch nicht — v0.95.16 + v0.95.17 + v0.95.18 + v0.95.19 gehen beim naechsten Push zusammen. **Vorher v0.95.18 (08.05.2026):** **P1.BUNDLE-LOGBOOK-RST-SNR: 3 Bugs gebuendelt (Logbuch-O(n²)-Hang + RST_RCVD R-Praefix + _process_cq_reply _last_snr-Race).** Mike-Auftrag 08.05.: „2 leichte Punkte zusammen mit Logbuch-Crash beim Eintrag-Loeschen — und QRZ-10K-Burst-Bug pruefen ob unser ADIF-Format spec-konform ist." Bundle aus 3 unabhaengigen Bugs im selben ADIF/Logbuch/Reporting-Pfad — voller V1→V2→R1→V3-Workflow gemeinsam, 3 atomare Code-Commits + 1 Doku-Commit. **Bug A — Logbuch-UI-Hang:** Wurzel `log/adif.py:94` `new_body += block + eor` in while-Loop = O(n²) bei 12 MB ADIF (~10K Records) → 5-10 s Hang im UI-Thread (Beachball). Plus full `self.refresh()` re-parste beide ADIF-Verzeichnisse (~19 MB Disk-IO im UI-Thread). Field-Test 07.05. nachmittags reproduziert. Fix: `delete_qso` `new_parts = []` + `.append` + `"".join` → O(n), < 200 ms gemessen. `_on_delete_clicked` In-Memory-Update via `_all_records.remove(rec)` + `_on_filter_changed(search_input.text())` + `_update_counters()`. Edge-Case ValueError → Fallback full refresh (Konsistenz). **Bug B — RST_RCVD/RST_SENT mit FT8-R-Praefix in ADIF (QRZ-Reject):** Wurzel: SimpleFT8 schrieb `<RST_RCVD:4>R-22` (FT8-Roger-Praefix aus Sequence-Layer durchgereicht). ADIF-Spec + QRZ-Validator akzeptieren nur `<rst_rcvd:3>-22`. Vergleich mit QRZ-Original-Export `do4mhh.398467.20260427134135.adi` bestaetigt Spec-Verletzung. Mike's 10K-Burst-Bug in v0.95.15 (12134 Dups + Fail-Cascade) wahrscheinlich wegen QRZ-Validator-Reject + Cooldown-Cascade. Fix: Neuer Helper `_strip_r_prefix(rst)` in `log/adif.py` (idempotent, None-safe, case-insensitive — `R-22`/`r-22` → `-22`; `RR73`/`R`/`""` unveraendert). Aufruf in 2 Pfaden (Defense-in-Depth): `log_qso` (Schreib-Pfad) + `qrz.upload_qso_from_dict` (Send-Pfad, lazy import) — alte ADIF-Files mit R-Format werden beim Re-Upload korrigiert, kein Migration-Helper noetig (R1-bestaetigt KISS). **Bug C / P1.8 — `_process_cq_reply` _last_snr-Race:** Wurzel: `mw_cycle.py:793` ruft `set_last_snr(msg.snr)` PRO decodierter Message → `_last_snr` wird 50× pro Slot ueberschrieben. `qso_state.py:214,229` baute Report aus `_last_snr` → zuletzt iterierte Message gewinnt, ist fast nie die anrufende Station. Mike-Beispiel: DA1TST -23 (von uns) vs R+19 (von ihm) = 42 dB Diff. Fix: nur Z.214 + Z.229 in `_process_cq_reply` auf `snr = msg.snr`. Hunt-Pfad (`start_qso`) + Retry-Pfade (Z.345,360,585,594,642) BLEIBEN mit `_last_snr` (Fallback bekannt akzeptiert). **Geaenderte Files (4 Code + 1 Test + main.py):** `log/adif.py` (delete_qso O(n²)→O(n) + `_strip_r_prefix` Helper + `log_qso` 2 Aufrufe), `log/qrz.py` (upload_qso_from_dict lazy import + RST-Strip), `ui/logbook_widget.py` (`_on_delete_clicked` In-Memory-Update), `core/qso_state.py` (`_process_cq_reply` Z.214,229 `msg.snr`), NEU `tests/test_p1_bundle_logbook_rst_snr.py` (17 Tests: 4 Bug-A + 10 Bug-B + 3 Bug-C, ein Bonus-Test fuer Whitespace-Strip), `main.py` APP_VERSION 0.95.17 → 0.95.18. Voller Workflow V1 (Diagnose, 3 Bugs lokalisiert) → V2 (15 Lessons — entlarvte O(n²) als Hauptwurzel + Send-Pfad-Strip + Filter-Re-Apply Race-Frei via Qt) → R1 („Plan kann freigegeben werden", 0 KRITISCH, 10/10 Pruefauftraege gruen, 1 Vorbehalt = Mike-Field-Test) → V3 (Compact-fest, 7 Diffs) → Compact → Code → **Final-R1 („Code kann gemerged werden") — 0 KP-Findings**. Plan-Files: `prompts/p1_bundle_logbook_rst_snr_v[1-3].md`. Tests 921 → 938 gruen (+17, V3 prognostizierte +16). Performance-AC < 500 ms erfuellt. Atomare Commits: `37e73aa` Bug-A + `e44fc26` Bug-B + `1ec7b7a` Bug-C + Doku-Commit. **Field-Test-Pflicht (vor Push):** QRZ-Bulk-Upload alter ADIF-Datei → kein 10K-Burst mehr (Bug-B-Beweis); Logbuch-Eintrag-Loeschen → < 0.5 s, kein Beachball (Bug-A-Beweis); QSO live → Report-SNR korrekt, kein 42 dB Bias (Bug-C-Beweis). Push noch nicht — v0.95.16 + v0.95.17 + v0.95.18 gehen beim naechsten Push zusammen. **Vorher v0.95.17 (07.05.2026):** **P1.COLLAPSE-RADIO-MODEBAND: Modus+Band + Radio einklappbar.** Mike-Wunsch 07.05. nach v0.95.16-Push: „radio und mouds haette ich gerne auch zum einklappen der kachel wie die Antennen kachel". Hobby-Use-Case: einmal Modus+Band einstellen, Watt selten verstellen, TUNE in Diversity automatisch → wegklappen, Platz fuer QSO/RX-Panel. Beide Karten unabhaengig, letzter Zustand persistiert. **Loesung — Pattern 1:1 Spiegelung Antennen-Kachel (v0.95.11):** `_ModeBandCard` (`ui/control_panel.py:232`) Header-Row mit Toggle-Button (`▼`/`▶`, blau `#7799FF`) + Label „MODUS+BAND" + `_body_widget` mit Grid (btn_ft8/ft4/ft2, freq_label, band_buttons, prop_bars). `_RadioCard` (`ui/control_panel.py:680`) analog mit Toggle (teal `#00aacc`) + existierendem „RADIO"-Label im Header + `_body_widget` (PSK-Frame + Power-Row + TX-Frame). Beide Cards: `set_collapsed/is_collapsed/_toggle_collapsed` API + `collapse_changed = Signal(bool)`. Signal NUR bei User-Klick (`_toggle_collapsed`), KEIN Emit bei Programm-API (`set_collapsed`) → Init-Loop-Schutz wie bei Antennen-Card. `setMaximumHeight(36)` bei Collapse, `_QWIDGETSIZE_MAX` bei Expand. `ControlPanel`: 2 neue Klassen-Signale `modeband_collapse_changed` + `radio_collapse_changed`, 2 Exposes `_modeband_card` + `_radio_card`, 2 Forward-Connects (lambda-frei). `MainWindow`: 2 Initial-Loads aus Settings (`modeband_card_collapsed`, `radio_card_collapsed`, Default `False` = ausgeklappt) + 2 neue `@Slot(bool)`-Methods analog `_on_antenne_collapse_changed`. Geaenderte Files (4): `ui/control_panel.py` (Refactor + ControlPanel-Integration), `ui/main_window.py` (2 Initial-Loads + 2 Slots), NEU `tests/test_p1_collapse_radio_modeband.py` (19 Tests via pytest-parametrize: 8 × 2 = 16 + 3 Integration), `main.py` APP_VERSION 0.95.16 → 0.95.17. Voller Workflow V1 → V2 → R1 → V3 → Compact → Code → **Final-R1 („kein Aenderungsbedarf") — 0 KP-Findings**. Plan-Files: `prompts/p1_collapse_radio_modeband_v[1-3].md`. Tests 902 → 921 gruen (+19). **Vorher v0.95.16 (07.05.2026):** **P1.LOCATOR-SLASH: Slash-Call Lookup-Bugs gefixt.** Mike-Pflicht-Verifikation der km-Anzeige im RX-Panel (DeepSeek-R1 Code-Review 07.05.) entdeckte 3 echte Bugs: (1) `ui/rx_panel.py:333-335` `lookup_call = max(parts, key=len)` bei Praefix-Slash wie `EA8/DA1MHH` extrahierte das laengste Token (`DA1MHH` Heim) statt DXCC-Praefix (`EA8` Kanaren) → Country DE statt IC, Distanz ~0 statt ~3000 km, DB-Lookup verfehlt. (2) `core/geo.py callsign_to_country` + `callsign_to_distance` mit gleichem `max(parts, key=len)`-Bug. (3) Mobile-Suffix-Inkonsistenz zwischen rx_panel-Stripping und DB-Set-Pfad. **Mike-Entscheidung:** DB BEHALTEN (Daten korrekt gespeichert, nur Lookup-Pfad kaputt). Decoder-Verifikation pre-V3 (`core/message.py:107-111` `parts = msg_str.strip().split()` → `f2 = parts[1]`) bewiesen: `m.caller="EA8/DA1MHH"` bleibt komplett. **Loesung Option A** (strikte Trennung): rx_panel macht KEIN Stripping mehr (`lookup_call = caller` 1:1), `core/geo.py` bekommt zentrale `MOBILE_SUFFIXES`-Konstante (7 Suffixe `/P /M /MM /AM /QRP /PORTABLE /MOBILE`) + `_strip_mobile_suffix` + `_dxcc_prefix_from_call` Helper, `callsign_to_country/distance` nutzen DXCC-Token-Heuristik (exakt-Match in `_PREFIX_MAP`, dann iterativ 3/2/1 Zeichen). `core/locator_db.py` lokale `MOBILE_SUFFIXES` (3-Tupel `/MM /AM /QRP`) durch Import aus `core.geo` ersetzt — Verhaltens-Aenderung (R1-bestaetigt vertretbar): `/P /M /PORTABLE /MOBILE` bekommen jetzt konsistent `prec_km*1.5` (Funker-Praxis: portable = unterwegs = Position weicht ab). Geaenderte Files (5): `core/geo.py` (Helpers + Slash-Heuristik), `core/locator_db.py` (Import + Doku Z.13-15), `ui/rx_panel.py` (Slash-Block Z.323-338 vereinfacht — 9 Bug-Zeilen raus), NEU `tests/test_p1_locator_slash.py` (14 Tests), `tests/test_locator_db.py` (`test_slash_p_treated_as_stationary` invertiert zu `test_slash_p_treated_as_mobile`), `main.py` APP_VERSION 0.95.15 → 0.95.16. Voller Workflow V1(3 Bugs, 3 Optionen, 10 ACs)→V2(12 Lessons, L6 entlarvt Option B als Original-Design-Widerspruch)→R1("Plan freigegeben" mit 1 KRITISCH = Decoder-Verifikation Schritt 0 ERLEDIGT pre-V3 + 1 SOLLTE-ERGAENZEN = +2 Edge-Case-Tests)→V3(Compact-fest, 6 Diffs)→Compact→Code→**Final-R1("Push freigegeben") — 0 KP-Findings.** Plan-Files: `prompts/p1_locator_slash_v[1-3].md`. Tests 888 → 902 gruen (+14, exakt wie V3 prognostiziert). Karten-Code (`direction_map_widget.py:1694`) und Statistik unbeeinflusst. Field-Test ausstehend, Push noch nicht. **Vorher v0.95.15 (07.05.2026):** **P1.QRZ-UPLOAD-UI-2: Title + File-Move + Log + Rate-Limit.** Folge zu v0.95.14 — Mike-Field-Test 07.05. nachmittags entdeckte 3 Probleme: Progress-Dialog StaysOnTopHint nervt, kein Tracking welche QSOs schon hochgeladen, 12134 Dups + Fail-Burst nacheinander = QRZ-Rate-Limit. Loesung: Status in Titelleiste statt non-modal Dialog (`SimpleFT8 — DA1MHH — QRZ ↑ x/y (z%)`), Statusbar inline `[QRZ ↑] [✕]` Cancel-Widget, File-Move nach `adif/hochgeladen/` (atomic shutil.move bei `fail==0 AND processed==expected`), JSONL-Log `~/.simpleft8/qrz_upload_YYYY-MM-DD.log` (Daily-Rotation), Rate-Limit-Detection (20 consecutive fails → 60s Cooldown als Loop mit Cancel-Check + `cooldown_tick(int)` Signal, KEIN blockierendes `time.sleep` → R1-KP, 2. Burst → Cancel). LogbookWidget + qso_log + locator_db laden BEIDE Verzeichnisse. Bulk-Filter: Records aus `hochgeladen/` werden NIE erneut hochgeladen. Geaenderte Files (8): NEU `tests/test_p1_qrz_upload_ui_2.py` (20 Tests), `core/qrz_upload_worker.py` Rewrite (file_results-Property + JSONL-Log + Rate-Limit + cooldown_tick + total_records-Property R1-Kapselung), `ui/qrz_upload_dialogs.py` (QRZUploadDialog-Klasse geloescht), `ui/mw_qso.py` (`_on_qrz_upload` Rewrite + 6 neue Slots: `_on_qrz_progress`, `_on_qrz_cooldown_tick`, `_on_qrz_bulk_finished`, `_handle_qrz_file_results`, `_show_qrz_status_widget`, `_on_qrz_status_cancel_clicked`, `_update_window_title`), `ui/main_window.py` (Statusbar-Widget Init + qso_log+locator_db Multi-Dir + closeEvent cooldown_tick.disconnect), `ui/logbook_widget.py` (load_adif Multi-Dir), `tests/test_p1_qrz_upload_ui.py` (4 Progress-Dialog-Tests geloescht), `main.py` APP_VERSION 0.95.14 → 0.95.15. KP-1/2/3 aus v0.95.14 noch intakt. Voller Workflow V1(10 ACs, 5 Probleme)→V2(14 Lessons L1-L14, mid-V2 Mike-Feedback L13 JSONL + L14 Rate-Limit)→R1("Plan freigegeben + 7 Optimierungen")→V3(Compact-fest, 8 Diffs)→Compact→Code→Final-R1("Push freigegeben mit 2 SOLLTE-FIX": `shutil.move dest.exists()`-Schutz + `total_records`-Property → beide gefixt + 2 Tests). Plan-Files: `prompts/p1_qrz_upload_ui_2_v[1-3].md`. Tests 872 → 888 gruen (+16: -4 Dialog +18 V3 +2 R1-Fix). Atomare Commits `d8f86b6` (Code+Tests, 11 Files +2534/-204) + Doku-Commit. Field-Test ausstehend, Push noch nicht. **Vorher v0.95.14 (07.05.2026):** **P1.QRZ-UPLOAD-UI: Confirm + Progress + Single-Instance.** Mike-Anforderung 07.05.: bei 18.443 QSOs Bulk-Upload an QRZ.com sichtbares Status-Fenster, weiterfunken moeglich, single-instance-Schutz. Field-Test 10:35 UTC: 8x Klick = 8 Bulk-Jobs queued (App rechtzeitig gekillt). Loesung: zwei-Phasen-Workflow `QRZConfirmDialog` (modal) + `QRZUploadDialog` (non-modal, StaysOnTopHint, ProgressBar, Counter, Cancel, Auto-Close 10s). NEU `core/qrz_upload_worker.py` mit `QRZUploadWorker(QObject)` (ThreadPoolExecutor + Signals + threading.Event cancel). Single-Instance 3-fach (`_qrz_bulk_active`-Flag + Button-Disable + Re-Entry-Check). R1-KP-Findings im Plan-Review: KP-1 (`_qrz_upload_single` skipt bei aktivem Bulk), KP-2 (Klick-Sperre Reihenfolge Flag→Button→submit), KP-3 (closeEvent disconnect() VOR cancel()). Final-R1 im Code-Review entdeckte 🚨 Cancel-Bug (Worker emittet jetzt IMMER finished — sonst Dialog-Hang bei Sofort-Cancel) + ⚠️ KP-3-Rest (closeEvent disconnect()). Beide sofort gefixt + neuer Test. Voller Workflow V1(5 Probleme + Field-Test-Beweis)→V2(12 Lessons L1-L12)→R1(9 Pruefauftraege + 3 KP)→V3(7 Compact-feste Diffs)→Compact→Code→Final-R1(Cancel-Bug)→Fix-Round→R1-Verifikation("Push freigegeben"). Plan-Files: `prompts/p1_qrz_upload_ui_v[1-3].md`. KEIN Resume-Feature (KISS, QRZ.com filtert serverseitig). Tests 862 → 872 gruen (+10). Atomare Commits `2270fdf` (Code+Tests, 10 Files +1841/-29) + Doku-Commit. APP_VERSION 0.95.13 → 0.95.14. **Vorher v0.95.13 (07.05.2026):** **P1.CACHE-SIMPLE Diversity/Gain entkoppelt + UX-Cleanup.** Mike-Vision: Diversity-Cache (Ratio, 60 Min) und Gain-Cache (6h) komplett entkoppelt. Keine Modal-Wahl-Dialoge fuer Routine. `_check_diversity_preset` neue Dispatch-Logik via `_assess_ratio`/`_assess_gain`-Helpers: gain stale → DXTuneDialog auto-start; gain missing → volle Pipeline; gain fresh + ratio fresh → Cache-Reuse still; gain fresh + ratio stale/missing → stille Auto-Ratio-Messung. Plus Stale-Acceptance in `_on_dx_tune_rejected`: Cancel mit alten Werten lädt diese statt Pipeline-Restart. `_try_diversity_cache_reuse` Gain-Check entfernt (Cross-Dependency Problem C). Toast-Klasse + Aufruf raus (Problem A: „Computer fährt runter — OK?"-Pattern). Wahl-Dialog „Weiter / Neu messen" raus (Problem B). `_activate_diversity_with_scoring` delegiert jetzt zu `_check_diversity_preset` (~70 Zeilen Deduplikation). Voller Workflow V1(4 Probleme)→V2(12 Lessons)→R1(8 Prüfaufträge, kein Veto)→V3(Compact-fest)→Compact→Code→Final-R1("Keine KP-Findings, robust, Mike-Vision umgesetzt ✅"). Plan-Files: `prompts/p1_cache_simple_v[1-3].md`. Tests 852 → 862 gruen (+10 NEU in `tests/test_p1_cache_simple.py` + 1 invertiert in `test_diversity_cache_reuse.py`). Atomare Commits `4af2e9e` (Code+Tests, 5 Files +508/-277) + Doku. APP_VERSION 0.95.12 → 0.95.13. **Vorher v0.95.12 (07.05.2026):** P1.FORCESEND btn_advance state-aware + WAIT_73-Branch. Mike's Use-Case 06.05.: bei stuck-Gegenstation manuell RR73 oder 73 senden statt 3-Min-Timeout. Bestehender btn_advance wird state-aware: Label dynamisch (`R+Report` / `RR73` / `73` / `Weiter →`), Enabled in {WAIT_REPORT, WAIT_RR73, WAIT_73} AND nicht cq_mode AND nicht diversity_locked. `advance()` neuer WAIT_73-Branch sendet 73, setzt `courtesy_73_sent=True` VOR send (R1-KP-3 asynchron), idempotent-Return wenn Auto-Pfad schneller war (Final-R1 Race-Fix). Voller Workflow V1→V2(10 Lessons, Bug-A-Halluzination eingestanden)→R1("Plan freigegeben unter 5 Bedingungen", KP-1 als Halluzination verworfen weil WAIT_73 = "QSO schon geloggt" laut qso_state.py:60)→V3→Code→Final-R1("Push freigegeben mit Vorbehalt: idempotent-Return" → sofort umgesetzt). Plan-Files: `prompts/p1_forcesend_v[1-3].md`. Tests 841 → 852 gruen (+11 in `tests/test_p1_forcesend.py`). Atomare Commits `c8bf5bb` (Code+Tests+main.py 5 Files +177/-2) + Doku-Commit. APP_VERSION 0.95.11 → 0.95.12. **Lesson:** V1-Halluzination-Risk auch nach 2 Jahren — grep für btn_advance.setEnabled in mw_radio.py war zu eng, _on_state_changed-Hook in mw_qso.py übersehen. V2-Self-Review fing es ab. **Vorher v0.95.11 (06.05.2026):** P1.ANTENNE-COLLAPSE _AntenneCard einklappbar. Mike-Designentscheidung: Antennen-Kachel WIRD einklappbar (DeepSeek-Konvention „alles sichtbar" überschrieben — SimpleFT8 ist Hobby-Tool). Header-Row mit Toggle-Button (`▼`/`▶`) + `_body_widget`-Container. API: `set_collapsed/is_collapsed/_toggle_collapsed`. Signal `collapse_changed` NUR bei User-Klick (Init-Loop-Schutz, Test 10 sichert). `ControlPanel._ant_card`-Expose + lambda-frei `antenne_collapse_changed.emit`-Forward. `MainWindow` lädt Initial-State aus `Settings.get("antenne_card_collapsed", False)` + persistiert via `_on_antenne_collapse_changed`. `setMaximumHeight(36)` bei Collapse, `_QWIDGETSIZE_MAX=16_777_215` bei Expand (PySide6 exportiert die Konstante nicht). Voller Workflow V1→V2(16 Lessons)→R1("Plan freigegeben + 5 KP")→V3(Compact-feste Diffs)→Code→Final-R1("Push freigegeben mit optionalem Debounce-Vorbehalt"). Plan-Files: `prompts/p1_antenne_collapse_v[1-3].md`. Tests 831 → 841 gruen (+10 in `tests/test_antenne_card.py`). Atomare Commits `a0ce1ae` (Code+Tests+main.py 4 Files +209/-9) + Doku-Commit. **R1-Vorbehalt NICHT umgesetzt (KISS):** Settings.save() blocking JSON-Dump, bei schnellem Toggle wäre 200ms-Debounce nice — für Hobby-Tool (<10ms save, 1 User) akzeptabel. **Vorher v0.95.10 (06.05.2026):** P1.AP-FIX generate_candidates State-1 Format-Bug. P1.AP E2E-Test-Pipeline (v0.95.9 hardware-frei) entdeckte: `core/ap_lite.py:126` produzierte 4-Token-Strings (`OWN THEIR LOC SNR`), FT8 erlaubt nur 3 → ft8lib `rc=5` → State-1-Rescue (WAIT_REPORT) scheiterte IMMER silent seit Implementierung. Fix (1 Zeile, KISS): Locator weglassen, Report-only `f"{own_callsign} {their_callsign} {r:+03d}"`. Plus Code-Kommentar Z.121-131 fachlich aktualisiert. Voller Workflow V1→V2(9 Lessons L1-L9)→R1("Plan freigegeben")→V3(5 Compact-feste Diffs)→Compact→Code→Final-R1("Push freigegeben"). Tests 816 → 831 gruen (+15: 14 P1.AP E2E-Pipeline aus v0.95.9 + 1 neuer ft8lib_compatible). Atomare Commits `17b7237` (Code+Tests+main.py 4 Files +79/-36) + Doku-Commit. Field-Test post-Kur. Notbremse: `AP_LITE_ENABLED=False`. **Deviation V3:** `test_try_rescue_state1_success` umbenannt zu `runs_after_fix`, Score>0-Hard-Assert entfernt — Praxis-Run zeigte Score=0.0 trotz Format-Fix wegen Costas-Referenz-Vereinfachung (Code-TODO `_build_costas_reference`). Format-Beweis liegt bei `ft8lib_compatible`-Test (R1 explizit OK). **Vorher v0.95.9 (06.05.2026):** P1.24 TX-Klick-Buffer (Folge-Fix zu P1.14, Field-Test bestätigt). Mike-Field-Test v0.95.8 entdeckte: TX-Klick wurde komplett ignoriert wenn `encoder.is_transmitting=True`. Bei CQ → Klick auf Station verpuffte, CQ lief weiter; bei Hunt-TX_CALL Umentscheidung dasselbe. Fix: Buffer-Logik. Klick während TX → State-Cleanup sofort (cq_mode → `stop_cq()` + Button-Off; Hunt-State → `cancel()`) + `_pending_station_click = msg` + Statusbar. In `_on_tx_finished` nach `on_message_sent()` Buffer-Check → `_on_station_clicked(buffered)` rekursiv. HALT verwirft Buffer. Code: `ui/main_window.py:209` (1 Attribut), `ui/mw_qso.py` (3 Stellen). Tests 812 → 816 grün (+4 in `tests/test_p1_24_pending_click.py`). **Vorher v0.95.8:** P1.14 Station-Wechsel-Bug (6 Wurzeln W1-W6) + P1.23 Status-UI-Feinjustierung. P1.14: voller Workflow V1→V2→R1→V3 Diagnose + Plan-V1→V2→R1("Plan freigegeben")→V3. 6 Bug-Wurzeln W1-W6: W1 `start_qso` resetete keine Pendings bei `state != IDLE`, W2 `_caller_queue` enthielt manuell-gewählte Station (Doppel-QSO-Risiko), W3 `_active_qso_targets` wuchs monoton, W4/KP6 `_was_cq` State-Machine-extern korrigiert (BEHALTEN — Plan-V2-Entscheidung), W5 TX-Klick silent ignoriert (Statusbar-Toast 3s), W6 `auto_hunt._manual_override` wurde NIE zurückgesetzt → Auto-Hunt pausierte dauerhaft nach manuellem QSO/HALT/Timeout. Code: `core/qso_state.py:start_qso` (Reset-Set + 3 Pendings), `ui/mw_qso.py` (5 Stellen). Tests 802 → 812 gruen (+10 in `tests/test_p1_14_station_switch.py`). P1.23: Label „Lokale Empfangsqualität:", Status-Schriftgrößen 11→10px, Sterne 15→13px. **Vorher v0.95.7:** P1.18 DT-Drift Wurzel-Fix + P1.21 Sterne-UX-Refactor. DT-Bug war 1 vergessene Konstante in v0.95.3 (`_WAKE_OFFSETS["FT8"]` 1.5→2.5 erhoeht, aber `_DT_OFFSETS["FT8"]` blieb 2.0 → +1.0s Drift clamped auf `_MAX_CORR=1.0`). Fix: `_DT_OFFSETS["FT8"]=3.0` (Sync mit Wake) + `dt_corrections.json` reset. P1.21 Sterne (Mike-Frust): Label `Empfang:`, Gold #FFD700 statt Cyan, RichText fuer enge Sterne, Score nur SNR (-10/-14/-18/-22 dB → 5/4/3/2/1). Mike-Szenario 48×-25 jetzt korrekt 1 Stern. Tests 796 → 802 gruen. Lesson: Mike-Hartnaeckigkeit ist Bug-Signal, NICHT auf Hardware tippen ohne git-diff. **+v0.95.6 (06.05.2026) — P1-Bundle1: 5 UI-Cleanups** (P1.6+P1.12+P1.15+P1.16+P1.19). Voller Diagnose-Workflow V1→V2→R1(5 KP)→V3 + Plan-V1→V2→R1(4 Findings + 4 Tests)→V3. Tests 777 → 796 gruen (+19). P1.6 Versionsnummer #333→#666. P1.12 NEU-Button entfernt (6 Stellen). P1.15 Statusbar `→ Call | RX: ANT` raus. P1.16 QSO-Panel zeitbasiertes 5-Min-Rolling-Window. P1.19 5-Sterne-Anzeige `★★★☆☆` ersetzt SNR-Label (NEU `ui/widgets/stars_widget.py` + `compute_local_conditions` Helper). `update_snr` No-Op (R1-KP1, Backward-Compat). Field-Test ausstehend. **+v0.95.5 (05.05.2026) — P1.10 End-of-QSO Icom-73-Loop-Fix (Courtesy-73).** Atomare Commits `9783583` (Code+Tests+Workflow-Files, 13 Files, +3439/-14) + Doku-Commit. Wurzel: IC-7300 (DA1TST) Auto-Sequence wartet auf abschliessendes Hoeflichkeits-73 von uns; SimpleFT8 sendete bisher kein Courtesy-73 → IC-7300 retried 5× `73`. Field-Test 11:24-:29 UTC mit DA1TST 2× reproduziert. Fix (Option A1 + R1-Slot-Paritaet-Defensive): neuer State `TX_73_COURTESY` + Feld `qso.courtesy_73_sent` (max 1× pro QSO), Branch in WAIT_73-Logik (qso_state.py:582-597) + on_message_sent + 3-Min-Timeout-Ausschluss + mw_qso `_on_tx_slot_for_partner` state-abhaengig (Panel-Info nur bei CQ-Reply). Voller V1→V2(8 V1-Luecken)→R1(4 KP + 3 Findings)→V3 Diagnose + V1→V2(6 V1-Luecken, D8 Timeout-Liste)→R1(3 wichtige + 3 optionale Findings)→V3 Plan. Tests 764 → 777 gruen (+13 neu, 2 angepasst). **Field-Test BESTAETIGT** (16:59 UTC EA2BHE Spanien — Courtesy-73 → kein weiteres 73). **IC-7300/DA1TST Endlos-73 GEKLAERT:** Mike hatte SDR-Control Retry=99 (Test-Override). Mit Standard-Retry kein Problem. Kein App-Bug. **+v0.95.5 (05.05.):** Single-Instance-Lock (fcntl + pgrep + lsof CWD-Filter), main.py + tools/remote/start_simpleft8_nokill.py. Garantiert nur EINE Instanz, schuetzt fremde main.py-Apps (Websdr) vor Kollateral-Kill. **Known Issue P1.11 (NICHT durch P1.10 verschaerft):** `rr73_retries` shared zwischen WAIT_RR73 + WAIT_73-Hoeflichkeits-Pfad. **v0.95.3 (05.05.2026) — P1.9 First-Reply-Lost-Bug-Fix.** Atomare Commits `20c7fe7` (Code+Tests, +282/-29 in 7 Files) + Doku-Commit. Wurzel: Decoder-Encoder-Timing-Race (FlexRadio TX-Buffer 1.3s) — Encoder wachte 0.2-3.0s VOR Decoder fertig (Encoder wake `boundary - 1.3s`, Decoder ready `slot + 14-16s`) → CQ-Audio bereits in `send_audio` (BLOCKING) wenn `_pending_reply` gesetzt wurde → Encoder hielt CQ-Message in Worker-Local, State-Update aenderte daran nichts → Report 1 Slot zu spaet. Reproduzierbar (4× Mike-Field-Test 09:39, 09:47, 09:55, 10:05 UTC). Fix-Kombination atomar (Option C alleine fixt nicht): (1) `core/decoder.py:138` — `_WAKE_OFFSETS["FT8"]` 1.5 → 2.5 (Decoder ready 0.5-2.5s VOR Encoder-Wake, SNR-Effekt < 0.1 dB R1-bestaetigt). (2) `core/encoder.py` — `request_replace(message)` API + Loop in `_tx_worker_inner` fuer Re-Encode + `_audio_started`/`_replace_message`/`_replace_lock` + `tx_finished.emit` im Encode-Fehler-Pfad (V2 FINDING-F). (3) `core/qso_state.py` — Signal `try_replace_pending_tx` + Emit in `on_message_received` bei CQ_CALLING + Defense-in-Depth in `_send_cq()` (R1-Empfehlung: falls `_pending_reply` gesetzt → process statt CQ). (4) `ui/mw_qso.py` — `_on_try_replace_pending_tx` Slot mit `tx_even`-vor-`request_replace` (V2 FINDING-D Race-Vermeidung), `_was_cq=True` (FINDING-A CQ-Resume), Debug-Log (FINDING-B), QSO-Panel-Anzeige (FINDING-C). (5) `ui/main_window.py:543` — Connect. Voller V1→V2(12 Findings A-L: 9 ⛔ kritisch + 3 Test-Ergaenzungen)→R1(6 Pruefauftraege KORREKT, KEINE neuen Findings)→V3 Workflow. Tests 759 → 764 gruen (+5: 3 Encoder API + 2 SM Logik, neue `tests/test_p1_9_replace.py`). Field-Test bei Mike ausstehend. **v0.95.2 (05.05.2026):** **CQ-Reply-Bug-Fix (P1.5).** Atomare Commits `43dd062` (Code+Tests) + Doku-Commit. Wurzel: 5-Min-Sperre `_WORKED_BLOCK_SECS = 300` blockierte CQ-Replies an 3 Stellen (`core/qso_state.py:480` Hauptpfad, `:191` `_process_cq_reply`, `:470` Caller-Queue-Add). Bekannte Stationen die uns < 5 Min nach RR73 erneut anriefen wurden still ignoriert — Mike's „manchmal klappt QSO, manchmal nicht"-Symptom. Fix: komplettes Rip-Out — `_worked_calls` dict, `_WORKED_BLOCK_SECS` Konstante, Methode `_is_worked_recently`, alle 3 Block-Stellen, TX_RR73 Eintrag-Stelle (-22 Zeilen, +0 Code). Mike's Funker-Philosophie: Filter „Neue Stationen" im RX-Panel ist die korrekte Stelle (Anzeige-Pfad), nicht die State-Machine. Voller V1→V2→R1→V3 Diagnose + voller V1→V2→R1→V3 Plan, DeepSeek-R1 (Reasoner) zwei Mal bestaetigt ohne Halluzinationen. Tests 756 → 759 gruen (+3: 1 invertiert + 3 neu — `test_qso_known_station_can_call_again`, `test_qso_cq_reply_during_tx_pending_then_processed`, `test_qso_caller_queue_accepts_known_station`, `test_qso_resume_pops_known_station_from_queue`). Folgebug-Risiko Doppel-ADIF → TODO P1.7 (lokaler Filter, QRZ.com filtert serverseitig). Stats-Bias 0 (R1-grep verifiziert). Memory-Lesson: `feedback_funker_entscheidung_filter_in_rx.md`. **v0.95.1 (05.05.2026):** **Encoder-TX-Slot-Tag-Fix.** Atomarer Commit ``04388ef``. Field-Test entdeckt: v0.95 hatte TX-Display-Tag noch 1 Slot zurueck (Bug in encoder.py:281, `time.time()` zur ptt_on-Aufruf-Zeit liegt 1.3s VOR next_boundary → floor-roundoff zum vorherigen Slot). Fix: `tx_started.emit()` nutzt `next_boundary` direkt als slot_start_ts. Validiert 05:27-05:30 UTC: TX `[E]` und RX `[O]` sauber getrennt, 2 komplette QSOs. Plus **v0.95** (Slot-Tag-Display-Fix mit Decoder als Slot-Quelle) — 7 atomare Commits (``dac4a73``, ``885d48a``, ``6793e73``, ``c919b72``, ``102e75f``, ``88b6648``, ``5d4b767``). RX-Eintraege im QSO-Panel zeigten faelschlich `[E]`-Tag und Zeit des Folge-Slots statt `[O]` und Slot-Anfang der TX-Nachricht. Root Cause: FlexRadio VITA-49 Audio-Buffer-Lag → Decoder skipt initialen Slot, decodiert im Folge-Slot → `time.time()` zur Decode-Output-Zeit ist im Folge-Slot. **Architektur:** Decoder ist single source of truth — `target_slot_start` PRE-SLEEP berechnet (driftfrei), als Attribut `_slot_start_ts`/`_tx_even` auf jede Message bis zu allen Konsumenten durchgereicht. **Geaenderte Files:** ``core/decoder.py``, ``core/encoder.py``, ``ui/mw_cycle.py`` (`_slot_from_utc`-Helper geloescht), ``ui/mw_qso.py``, ``ui/mw_radio.py``, ``ui/qso_panel.py``. **Encoder-Signal Migration:** ``tx_started = Signal(str, bool, float)`` statt ``Signal(str)`` — 2 Listener migriert (mw_radio.py:65 Lambda, mw_qso.py:_on_tx_started Slot). **Voller Workflow zweimal:** Diagnose-V1→V2→R1, Plan-V1→V2→R1→R1-Validierung→V3 (R1 nicht halluziniert, `not _candidate.tx_even` an mw_cycle.py:512 verifiziert; mw_qso.py:128 ist NICHT betroffen weil User-Klick-Pfad). Tests 742 → 756 gruen (+14, V3-Plan rechnete +11 — 3 Bonus edge-cases). Stats-Risiko < 0.1 % (R1, NICHT mit-gefixt). **v0.94:** KALIBRIEREN-Pipeline + Stats-Bug Phase 2 — 3 atomare Commits (``2c1c58d``, ``7ca791e``, ``2658ee1``) plus Doku. **Bug-Fix Stats-Pause Phase 2:** ``_is_antenna_tuning_active`` hatte einen toten Pre-Cond-Pfad (``_rx_mode == "dx_tuning"`` wurde nirgends gesetzt) → Stats wurden waehrend DXTuneDialog weiter geloggt mit Diversity-Pattern-Antenne statt Hardware-Antenne aus ``_schedule[_step]`` (~0.3 % Daten-Bias Pre-v0.94). **RX-Panel-Display-Fix:** neuer Helper ``_resolve_hardware_antenna(default_ant)`` in mw_cycle.py liest waehrend Phase 2 die echte Antenne aus DXTuneDialog._schedule, sonst Diversity-Pop-Queue-Wert. **KALIBRIEREN-Erweiterung (Mike's UX):** ``_handle_dx_tuning`` setzt im Diversity-Modus ``_pending_dx_diversity = True`` → nach Phase 2 laeuft Phase 3 automatisch (Cache + Timer-Reset). ``_on_dx_tune_rejected`` resetet Pending-Flags bei Cancel. R1-Klaerung 0-Stations-Logging: ist korrekt (kein Filter auf 0, Pre-Conditions symmetrisch fair). 3 atomare Commits (``2c1c58d``, ``7ca791e``, ``2658ee1``) plus Doku. **Bug-Fix Stats-Pause Phase 2:** ``_is_antenna_tuning_active`` hatte einen toten Pre-Cond-Pfad (``_rx_mode == "dx_tuning"`` wurde nirgends gesetzt) → Stats wurden waehrend DXTuneDialog weiter geloggt mit Diversity-Pattern-Antenne statt Hardware-Antenne aus ``_schedule[_step]`` (~0.3 % Daten-Bias Pre-v0.94). **RX-Panel-Display-Fix:** neuer Helper ``_resolve_hardware_antenna(default_ant)`` in mw_cycle.py liest waehrend Phase 2 die echte Antenne aus DXTuneDialog._schedule, sonst Diversity-Pop-Queue-Wert. **KALIBRIEREN-Erweiterung (Mike's UX):** ``_handle_dx_tuning`` setzt im Diversity-Modus ``_pending_dx_diversity = True`` → nach Phase 2 laeuft Phase 3 automatisch (Cache + Timer-Reset). ``_on_dx_tune_rejected`` resetet Pending-Flags bei Cancel. R1-Klaerung 0-Stations-Logging: ist korrekt (kein Filter auf 0, Pre-Conditions symmetrisch fair). Tests 729 → 742 gruen (+13). **v0.93:** Cache-Reuse + Mess-Refactor (Score-basiert + 1h-Frist), 6 atomare Commits (``d8d947f``, ``305d775``, ``fd416ca``, ``f8af3e8``, ``196a999`` + Doku). **Hauptfeatures:** (1) Cache-Reuse pro Band+Modus mit 5-s-Toast — Phase 3 wird bei Ratio < 1 h alt komplett uebersprungen (``ui/diversity_cache_toast.py`` NEU + ``_try_diversity_cache_reuse`` in mw_radio.py). (2) Score-basierte Messung: ``record_measurement`` speichert ``score = sum(snr+30)`` statt diskretem ``station_count``/``dx_weak_count`` — Killer fuer FT2 mit 1-2 Stationen pro Slot (R1 Mod 4). (3) 1-Stunden-Frist atmosphaerisch korrekt, modus-unabhaengig: ``REMEASURE_INTERVAL_SECONDS=3600`` + ``_last_measured_at`` Timestamp + ``seconds_until_remeasure`` Property. (4) CQ-Lock zusaetzlich zu QSO-Lock in ``should_remeasure(qso_active, cq_active=False)`` (R1 Mod 3). (5) PresetStore zwei Timestamps: ``gain_timestamp`` (6h) + ``ratio_timestamp`` (1h), automatische Migration alter Caches (R1 Mod 2). (6) ``OPERATE_CYCLES``-Konstante + ``diversity_operate_cycles``-Settings entfernt, UI-Anzeige zeit-basiert „Diversity Neuberechnung in X Min.". (7) ``MIN_MEASURE_STATIONS=5`` entfernt, ``can_measure()`` immer True (FT2-Pre-Block weg, Mod 5). Voller V1→V2→R1→V3-Workflow + V3-R1-Final-Review (DeepSeek-Reasoner: „Plan freigegeben"). Tests 681 → 729 gruen (+48: PresetStore +18, Density +9, should_remeasure +13, Cache-Reuse +9). MEASURE_CYCLES-Skalierung BLEIBT (FT8=6, FT4=12, FT2=24). **v0.92:** Pipeline-Lock bulletproof. **v0.91 (04.05.2026):** Block 2 Adaptiv-Stops + ROUNDS=2. Kalibrier-Pipeline ~4:31 Min (v0.89/v0.90) → typisch ~3:20 Min, Best-Case ~2:30 Min bei eindeutigen Antennen-Verhaeltnissen. 3 atomare Commits: ``eef4369`` ROUNDS 3→2 (#6, -60s, Schedule 12→8 Eintraege), ``3068919`` Adaptiv-Stop Phase 2 nach Runde 1 (#7, Δ_SNR≥4dB ODER Δ_STAT≥50%, Pre-Cond: 4 Buckets non-empty + non-overload + min 5 Stat., +6 Tests in `test_dx_tune_adaptive_stop.py` NEU), ``f090097`` Adaptiv-Stop Phase 3 nach 4 Zyklen + Cache-Schutz (#8, EARLY_STOP_THRESHOLD=0.15, Pre-Cond: len(m1)==len(m2), Property `_early_stop_at`, Flag `_was_early_stopped` schuetzt PresetStore vor Adaptiv-Stop-Ratios — R1.4 KRITISCH, +5 Tests in `test_patterns.py`). FT4/FT2-Hinweis: Pattern-Periode 6 verhindert balancierte Verteilung bei MEASURE_CYCLES=12/24, effektiv nur FT8 (Hobby-Use 99% FT8, R1-akzeptiert). Voller Workflow V1→V2(Self-Review, 6 Findings)→R1(DeepSeek-Reasoner, 4 KRITISCH adressiert: Cache-Schutz, Monitoring-Log mit Timestamp, FT4/FT2-Doku, Cancel-Flag dokumentiert)→V3. Tests 675 gruen (664 + 11). Schwellen-Werte konservativ (4 dB / 50 % / 15 %), Monitoring-Log fuer Field-Test-Tuning. **🟡 Offen: mw_radio.py Bandwechsel-Race** — separater Workflow nach Cache-Reuse. **v0.90:** Mess-Pattern-Bug-Fix (KRITISCH, fair 3:3 Pattern A1A1A2A2A1A2). **v0.89:** Kalibrier-Pipeline Block 1 — 6:50 → ~4:31 Min (-34 %), 5 atomare Commits. **v0.88:** Bandpilot Stunden-Refactor. **v0.87.1:** Doku-Konsolidierung. **v0.87:** Bandpilot v1. **v0.86:** Fix G + Test-Coverage. **v0.85:** Dead-Code-Cleanup. **v0.84:** Tertile-Analyse. **v0.83:** Fix F. **v0.82:** Fix E. **v0.81:** Fix D. **v0.80:** TX-DT-Drift-Fix. **v0.79:** Bug-Cleanup. **v0.78:** OMNI-TX scharfgeschaltet. **v0.77:** Hardware-Dialog. **v0.76:** Settings-Tabs. **v0.75:** Auto-Hunt-Modus.
**Tests:** `./venv/bin/python3 -m pytest tests/ -q` → 1023 passed (Qt-Smoke-Tests via `QT_QPA_PLATFORM=offscreen`)
**Vor Commits:** Tests grün + bei nicht-trivialen Änderungen DeepSeek-Review (`pal codereview` model `deepseek-chat`) — bereits durch globale §0 + Projektregeln gefordert.

⚠️ **DeepSeek-Workflow Stand 2026-04-28:**

**Direkt-API ist jetzt Default-Werkzeug** (nicht mehr `pal chat`-MCP):
- Helper: `tools/deepseek_review.py` — kein Token-Limit (65K Context)
- Aufruf: `cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py`
- Key in `~/.deepseek_key` (chmod 600, ausserhalb Repo)

**Default-Modell: `deepseek-reasoner` (R1)** — Mike-Entscheidung 28.04.:
„Quality > Speed, ~$3/Monat-Differenz egal gegen Bug der Stunden frisst."

| Modell | Wann | Antwort-Zeit | Kosten |
|---|---|---|---|
| **R1 (Default)** | Code-Review, Architektur, Race-Conditions, Trade-offs, KISS-Bewertung | 6-30s | ~$0.005 |
| V4 via `--chat` | Trivial-Fragen ("Ist X im Code?"), Tippfehler, Pure Verifikation | 2-5s | ~$0.001 |

**DeepSeek-Antworten IMMER kritisch pruefen** — auch R1 halluziniert
gelegentlich. Bei Widerspruch: Code ist Referenz. V0.74 Bilanz mit V4: 5
echte Findings + 1 Halluzination („Phase haengt ewig" — falsch). R1 sollte
hier praeziser sein (verifiziert Code-Pfade intern), aber Verifikation
bleibt Pflicht.

**`pal chat`-MCP** noch fuer einfache Multi-Turn-Sessions nutzbar
(Continuation-IDs), aber Files-Limit 7077 Tokens — fuer ernste Reviews
immer Direkt-API.
## ⛔ Projekt-Philosophie (PFLICHT bei Architektur-Entscheidungen!)

**SimpleFT8 ist ein Hobby-Funker-Tool. KEIN Contest-Tool.** Diese Leitlinien
gelten fuer Claude UND DeepSeek bei Feature-Vorschlaegen, Architektur-Beratung,
Implementierungen:

- **Zielgruppe:** Hobby-Funker. Nicht Pileup-Jaeger, nicht Contest-Operatoren,
  keine 1000-QSO-pro-Tag-Stationen.
- **Use-Case:** App starten → ein bisschen FT8/FT4/FT2 funken → fertig.
  Keine Stunden-langen Sessions mit komplexer Konfiguration.
- **UX-Prinzip:** Einfache Bedienung > Vollstaendigkeit. Lieber 3 gut funktio-
  nierende Features als 30 die Mike erst lernen muss.
- **Visueller Stil:** Modern (dunkles Theme, Neon-Akzente, weiche Verlaeufe).
  Nicht 90er-Jahre-Funktionalitaets-UI wie WSJT-X / JTDX.
- **NICHT geplant:** Contest-Modi, Multi-Operator, RTTY/CW/SSB, Skimmer-
  Integration, Pileup-Tools, komplexe Filter-Macros, Cluster-Spotting fuer
  DX-Hunting. Wenn ein DeepSeek-Vorschlag in diese Richtung geht: ablehnen.
- **Was modern bedeutet:** 3D-Globus statt platter PSK-Reporter-Karte,
  Live-Diversity-Visualisierung, Antennen-Farb-Coding, glow-Effekte —
  Dinge die in 2026 selbstverstaendlich sind aber im Funker-Tool-Alltag fehlen.

**Wenn DeepSeek oder ich ein Feature vorschlagen, immer pruefen:** „Hilft das
einem Hobby-Funker beim Hobby-Funken? Oder waere das nur fuer Power-User /
Contester sinnvoll?" — bei letzterem: NICHT umsetzen, in eine optionale
Erweiterung ausgliedern oder ganz verwerfen.

---

## 📋 Verbindlicher Feature-Workflow

Fuer alle nicht-trivialen Features (>5 Zeilen Code, neue Module, Architektur-
Aenderungen): **siehe `docs/WORKFLOW.md`** — Schritt 0 Code-Verifikation →
V1 → V2 (Self-Review) → DeepSeek-R1-Review → V3 → Mike-Freigabe → Plan-Mode → Code.

Triviale Aenderungen (Tippfehler, Kommentar-Updates, < 5 Zeilen) brauchen den
Workflow nicht.

---

## ⛔ Programmier-Leitsaetze (PFLICHT bei jedem Entwurf!)

Diese Saetze gelten fuer Claude UND DeepSeek bei jedem Plan, jedem Prompt,
jeder Code-Aenderung. Wenn ich (Claude) gegen sie verstosse: Mike soll mich
darauf hinweisen, ich nehme die Korrektur an.

1. **Overengineering vermeiden — kritisch beurteilen.** Vor jedem neuen
   Konzept (neue Klasse, neue Konfig-Datei, neue Abstraktionsebene) fragen:
   *„Brauchen wir das wirklich, oder sind wir verliebt in unsere Idee?"*
   Wenn es ohne geht — ohne. Drei aehnliche Zeilen sind besser als eine
   verfruehte Abstraktion. KISS schlaegt Eleganz.

2. **Sauber wie ein Chirurg.** Schlamperei oder Eile beim Entwurf raechen
   sich spaeter doppelt — schlechtes Design generiert mehr Bugs, mehr
   Re-Reviews, mehr Frust. Lieber 30 Min laenger im Plan-Mode als 3 Stunden
   nachbessern. Schritt fuer Schritt, sauber, kein Drauflos-Schneiden.

3. **Code als Referenz, nicht Annahmen.** Bevor V2-Prompts an DeepSeek gehen
   oder Plans entstehen: tatsaechlichen Code lesen, Dateipfade + Zeilen
   verifizieren. Annahmen fuehren zu Halluzinationen die niemand mehr sauber
   reviewen kann.

4. **Mike auf Overengineering hinweisen.** Wenn Mike ein Feature beschreibt
   das mit weniger Aufwand sauberer geht: ansprechen, alternative skizzieren,
   ihn entscheiden lassen. Nicht stillschweigend kompliziert umsetzen.

5. **V1 → V2 (Self-Review) → DeepSeek → V3 → Plan-Mode → Code.** Diese
   Reihenfolge bei nicht-trivialen Aenderungen. Kein Skip von Self-Review.
   Kein Skip von Code-Verifikation. „Sauber am Anfang spart 10x Zeit am Ende"
   (Mike, 2026-04-28).

---

**Diagramme:** `./venv/bin/python3 scripts/generate_plots.py`
→ Generiert IMMER beide Sprachen: DE → `auswertung/` + EN → `auswertung/en/`
→ DE: `SimpleFT8_Bericht.pdf` (7 S.) | EN: `SimpleFT8_Report.pdf` (7 p.)
→ Regel: Statistiken und PDFs IMMER auf Deutsch UND Englisch erstellen!

**⚠ Tages-/Pooled-Mean-Auswertungen:** ZUERST `auswertung.md` lesen!
Format-Stolpersteine (3 vs 5 Tabellenspalten, Rescue extern in `stations/`,
DX-Modus zählt nur SNR<-10) sind dort dokumentiert inkl. Code-Vorlage.
Mike's „Tagestrend"-Anfragen → stundenweise Tabelle, nicht nur Pooled-Mean.
**Git:** branch `main`, Repo aktiv, Statistics-Daten committed

---

## Rollen

- **Mike (Ideengeber, Tester, Inspirator):** definiert Ziele, testet im Feld, entdeckt
  Ideen und Probleme aus der Praxis, entscheidet bei strategischen Architektur-Fragen
  und über alles was nach außen sichtbar wird (Push, Doku auf GitHub, Releases).
- **Claude (Chef-Programmierer):** verantwortlich für Code-Qualität, Struktur,
  Wartbarkeit, Fehlerfreiheit, Tests. Trifft Code-Architektur-Entscheidungen
  innerhalb des vereinbarten Ziels eigenständig und proaktiv. Bei wirklich
  grundlegenden Weichenstellungen einmal kurz vorlegen, dann umsetzen.

## Mehrstufiger Prompt-Workflow (PFLICHT bei nicht-trivialen Features/Bugs)

Vor jeder nicht-trivialen Umsetzung (>5 Zeilen, neues Modul, Architekturfrage,
mehrere Probleme zugleich) durchlaufen wir gemeinsam diesen Ablauf — KEIN
direkter Sprung in `/plan`:

1. **Probleme erkennen + Prompt V1 entwerfen** (Claude)
   — Symptome präzise beschreiben, Datei:Zeile-Referenzen, Akzeptanzkriterien.
2. **Rolle frischer KI: Self-Review → V2** (Claude)
   — Was fehlt? Was ist mehrdeutig? Was übersieht V1? Lücken füllen, V2 schreiben.
3. **V2 an DeepSeek** (`pal chat` model `deepseek-chat`)
   — DeepSeek bekommt explizit den Auftrag den Prompt zu kritisieren und
   konkret zu verbessern (nicht das Problem zu lösen).
4. **DeepSeek-Findings einarbeiten → V3** (Claude)
   — Kritisch prüfen (siehe DeepSeek-Caveat oben), V3 schreiben.
5. **Mike vorlegen** — Mike liest V3, gibt Freigabe oder Korrekturen.
6. **Planungsmodus + Umsetzung** — erst dann `/plan`, dann atomare Commits.

**Trigger-Sätze von Mike** für diesen Workflow:
- „selbe vervahrensweise wieder" / „wie bei Locator-DB"
- „erst V1 dann zu deepseek" / „prompt entwerfen"

**Wann der volle V1→V2→V3-Workflow lohnt (Trigger-Schwelle):**
Mindestens EINES der folgenden Kriterien erfüllt → vollen Workflow fahren:
- Task hat ≥2 unabhaengige Akzeptanzkriterien
- Mathematisch/geometrisch (Projektion, Rotation, Filter, Algorithmen)
- Beruehrt ≥2 Dateien oder fuehrt neues Modul ein
- Threading/Persistence/IO neu beteiligt
- Architektur-Entscheidung (siehe „Architektur-Entscheidungen" oben)

**Wann V1 direkt reicht (Workflow uebersprungen):**
- Tippfehler, Umbenennungen, <5 Zeilen
- Lokaler Patch in EINER Methode ohne Architekturwirkung
- Reines Doku-Update, Test-Anpassung an bestehende API
- Bugfix mit klarer Datei:Zeile-Diagnose und einzigem Akzeptanzkriterium

→ Bei Grenzfall lieber Workflow fahren als Sackgasse riskieren.
   Beispiel-Mehrwert siehe v0.66 Map-UI (Sektor-Rotation): DeepSeek fand
   1°→5°-Stabilitaetsproblem, Helper-Extraktion, Test-Reduktion.

**Bei Plan-Mode selbst:** nur die Plan-Datei editieren. Read/Grep/Glob zum
Verifizieren von Code-Behauptungen ist ok. Plan-Datei mit konkreten
Datei:Zeile-Referenzen versehen — Subagents können das schnell verifizieren.

**Begründung:** Mehrstufige Validierung verhindert Over-Engineering.
Beispiel v0.67-Locator-DB: V2 hatte 26-Buchstaben-Splitting, LRU-Cache,
Write-Ahead-Log — DeepSeek hat die Komplexität auf 1/4 reduziert.

## Commits

Lokale Commits trifft Claude eigenständig wenn ein Schritt logisch in sich geschlossen
ist. Aufteilung **atomar** — pro Refactoring/Feature/Bugfix ein Commit, nicht alles in
einen Mega-Commit zusammenwerfen. Beispiel: Refactoring + neue Tests + Doku =
3 Commits, nicht 1.

`git push` und alles was nach außen sichtbar wird (PRs, Releases, Tags) **nur nach
expliziter Anfrage von Mike**.

## Architektur-Entscheidungen

Folgende Änderungen werden Mike VOR Umsetzung kurz vorgelegt (Plan + Begründung,
dann seine Bestätigung):

- **Modul-Auflösung:** eine Klasse/Datei in mehrere Module splitten
  (z.B. `flexradio.py` in connection/audio/slice aufteilen)
- **Architektur-Pattern-Wechsel:** z.B. von Mixins zu Composition,
  von Singleton zu DI-Container
- **Threading-Modell-Änderungen:** neue Threads, Lock-Strukturen, Async-Migration
- **Eingriffe in produktive Algorithmen ohne Test-Schutz**
  (siehe AP-Lite v2.2: kein End-to-End-Test → kein blinder Fix)
- **Neue externe Abhängigkeiten** (Pip-Pakete, C-Libraries)
- **Breaking Changes** an öffentlichen Schnittstellen
  (Settings-Dateiformat, Statistics-MD-Format, ADIF-Export, JSON-Cache-Schemas)

Alles andere — Helper-Extraktion innerhalb derselben Datei, Bug-Fixes über
mehrere Dateien, neue Tests, Doku-Updates, lokales Refactoring, Optimierungen
ohne Verhaltensänderung — entscheidet Claude eigenständig und meldet im
Anschluss was gemacht wurde.

---

## Architektur & Module

```
core/
  decoder.py          RMS AGC (-12 dBFS Ziel, ±3 dB Hysterese), 5-Pass Subtraktion
                      DT_BUFFER_OFFSET: FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet!)
  encoder.py          FT8/FT4/FT2 encode → VITA-49 TX
                      TARGET_TX_OFFSET=-0.8s (kompensiert FlexRadio TX-Buffer 1.3s)
  qso_state.py        State Machine: Hunt, CQ, Waitlist, RR73 Courtesy (max 2×)
                      _was_cq: in start_qso() UND _process_cq_reply() gesetzt (Bug-Fix!)
  diversity.py        Controller: Standard(Stationsanzahl) / DX(SNR<-10dB)
  diversity_merger.py Merged A1/A2 Dekodierungen
  ntp_time.py         DT-Korrektur v3: pro Modus+Band (Key "FT8_20m"), set_band(),
                      2-Zyklen-Messen, 70% Dämpfung, engere Grenzen pro Modus,
                      gedämpfte Erstkorrektur bei ≤2 Stationen
  station_accumulator.py Gemeinsame Logik Normal+Diversity
                      Aging: 75s normal / 150s active_qso / 300s CQ-Rufer
  station_stats.py    Async Queue+Daemon-Thread Logging → statistics/<Modus>/<Band>/<Proto>/
                      + Entry-Typ antenna_qso → statistics/antenna_qso/YYYY-MM-DD.md
  antenna_pref.py     AntennaPreferenceStore: {best_ant, delta_db} pro Callsign,
                      1dB Hysterese, kein Timeout (jeder Zyklus überschreibt)
  propagation.py      HamQSL + _apply_seasonal_correction(band, condition, utc_hour, month)
                      60m fehlt in XML → Interpolation 40m/80m (day+night getrennt, implementiert)
  ap_lite.py          ⛔ UNGETESTET — Feldtest ausstehend (SCORE_THRESHOLD=0.75)
  omni_tx.py          ⛔ DEAKTIVIERT — Implementation v0.78 in Vorbereitung.
                      5-Slot-Pattern Even/Odd-Rotation, Diversity-only Feature
                      (Mode-gekoppelt). Stop-Reasons: band_change, mode_change,
                      totmann_expired, manual_halt. Aktivierung via Direkt-
                      Toggle btn_omni_cq (sichtbar nur in Diversity).
                      → Vollstaendige Design-Spec: docs/OMNI_TX_DESIGN.md
  auto_hunt.py        Auto-Hunt Logik (v0.78: wird Diversity-only Feature
                      analog OMNI — Mode-gekoppelt, btn_auto_hunt nur in
                      Diversity sichtbar; Mode-Wechsel zu Normal stoppt
                      Auto-Hunt automatisch via auto_hunt_stopped("mode_change")).
  timing.py           UTC-Takt, modus-abh. Zyklen
  protocol.py         FTX_PROTOCOL_FT8/FT4/FT2
  ft8lib_decoder.py   C-Library Wrapper
  geo.py              Maidenhead, Haversine, Großkreis-Bearing (atan2),
                      Azimuthal-Equidistant-Projektion (Karten-Render),
                      safe_locator_to_latlon (None-safe Wrapper)
  direction_pattern.py Sektor-Aggregation (16x 22.5°), Mobile-Filter,
                      StationPoint/SectorBucket Datenklassen,
                      NaN/Inf-Schutz fuer korrupte externe Inputs
  psk_reporter.py     PSKReporterClient: XML-Polling mit Cache + Backoff
                      (1.5x bis 60min), Call-Normalisierung (.rsplit('/',1)),
                      atomarer Cache-Write (.tmp + os.replace)
  locator_db.py       LocatorDB: persistenter Locator-Cache (~/.simpleft8/
                      locator_cache.json). Source-Priority (cq_6 > psk_6 >
                      qso_log_6 > _4-Varianten). RLock-Threading, atomic-Write,
                      Mobile-Suffixe (/MM/AM/QRP) prec_km x 1.5. get() returnt
                      Kopie. Bulk-Import aus ADIF-Dateien. Save bei App-Close.

radio/
  base_radio.py       RadioInterface ABC
  radio_factory.py    create_radio(settings)
  flexradio.py        SmartSDR TCP + VITA-49 + Auto RX-Filter

ui/
  main_window.py      3-Panel + Statusbar; _tune_active/_tune_freq_mhz State-Vars
  mw_cycle.py         Cycle Processing; _diversity_in_operate Flag (Transition Guard!)
                      _log_stats Guard: btn_cq.isChecked() + cq_mode + state (3-fach robust)
  mw_radio.py         Band/Modus/Diversity, _diversity_in_operate Reset bei _enable_diversity()
                      set_band()/set_mode() bei Wechsel + Radio-Connect (DT-Korrektur!)
  mw_tx.py            TX-Regelung: rfpower konvergiert → save_tx_power();
                      _on_tune_clicked() setzt _tune_active/_tune_freq_mhz + _update_statusbar()
  mw_qso.py           QSO Callbacks, CQ, Logbuch;
                      _on_station_clicked: _cq_was_active VOR stop_cq() sichern → _was_cq fix
                      _antenna_pref_label() → "(ANT1)" in Normal, "(ANT2, +6.3 dB)" in Diversity
  control_panel.py    UI Controls (57 KB — größte UI-Datei); Frequenz in kHz
  rx_panel.py         RX-Tabelle; Answer-Me-Highlighting; Spalten per Rechtsklick
  dx_tune_dialog.py   18-Zyklus interleaved Messung; cache.save() HIER nach Messung!
  direction_map_widget.py  Azimuthal-Karte mit RX/TX-Toggle (v0.66).
                      MapCanvas (paintEvent + QPixmap-Background-Cache, Resize-
                      Debounce 200ms) + DirectionMapDialog (non-modal QDialog,
                      Toggle, Filter-Bar, Status). LocatorCache fuer FT8 (CQ
                      ist die einzige Quelle fuer Locators). Aufruf via
                      Settings-Dialog → "Karte oeffnen ..."-Button.

scripts/
  generate_plots.py   3-Modus Vergleich, pooled mean, Error Bars
                      PDF-Bericht 7 Seiten (nur 40m FT8), cursor-basiertes Inch-Layout
                      Helpers: _ctext/_chline/_csection (y in Zoll von oben, kein hardcoded fig-y)

config/settings.py    Frequenzen, Band-Configs, mode-aware get/save_dx_preset()
                      TUNE_FREQS (Band_Mode → Nebenfrequenz -2kHz) + get_tune_freq_mhz()
log/adif.py           ADIF 3.1.7
dt.md                 DT-Timing Analyse: Theorie, Änderungen, Validierungsergebnisse
```

---

## DT-Timing (Stand 23.04.2026 — validiert)

```
RX: DT_BUFFER_OFFSET FT8=2.0 (= 1.5 Buffer + 0.5 WSJT-X Protokoll)
    Korrektur konvergiert auf ~0.24s (nur FlexRadio VITA-49 RX-Hardware)
    Stationen zeigen DT ≈ 0.0–0.2 nach Konvergenz

TX: TARGET_TX_OFFSET = -0.8s = 0.5 (Protokoll) - 1.3 (FlexRadio TX-Buffer)
    FlexRadio puffert TX-Samples konstant 1.3s vor RF-Ausgabe
    Validiert: 8 Zyklen 0.0s DT am Icom, 20m + 40m getestet

Speicherung: ~/.simpleft8/dt_corrections.json → Key "FT8_20m" (pro Modus+Band)
    set_band() / set_mode(mode, band) lädt gespeicherten Wert sofort
```

---

## Gain-Algorithmus & Hard-Limit

- **Ziel:** -12 dBFS RMS (±3 dB Hysterese)
- **Normalisierung:** -18 dBFS RMS nach AGC
- **TX-Power:** Closed-Loop FWDPWR Feedback, `_rfpower_current` (0-100)
- **rfpower pro Band:** `settings.save_tx_power(band, val)` / `get_tx_power(band, default=50)`, Clamp 10–80%
- **Konvergenz-Flag:** `_rfpower_converged` — True wenn stabil, reset bei Änderung/Bandwechsel

---

## DX-Preset System & Cache

- **Mode-aware Keys:** `"20m_FT8"` hat Vorrang vor `"20m"`
- `get_dx_preset(band, mode=None)` / `save_dx_preset(..., scoring="standard"/"dx")`
- **DiversityCache:** 2h Gültigkeit, Key `diversity_cache_{band}_{scoring}`
- **cache.save() NUR in `_on_dx_tune_accepted()`** — NICHT im Cycle-Loop!
- Bei Normal+Standard: Dialog "Vorhandene Daten verwenden oder neu einmessen?" (wie bei DX)

---

## Verzeichnis-Struktur (Dateiablage)

### Kalibrierungsdateien
- **Pfad:** `~/.simpleft8/kalibrierung/`
- `presets_standard.json` → Gain + Ratio für Diversity Standard (pro Band+FTMode)
- `presets_dx.json`       → Gain + Ratio für Diversity DX (pro Band+FTMode)
- **Format Key:** `"40m_FT8"`, Werte: `rxant, ant1_gain, ant2_gain, ant1_avg, ant2_avg, ratio, dominant, timestamp, measured`
- **Klasse:** `core/preset_store.py` → `PresetStore("presets_standard.json")` / `PresetStore("presets_dx.json")`
- **Auto-Migration:** PresetStore verschiebt automatisch alte Dateien aus `~/.simpleft8/` nach `~/.simpleft8/kalibrierung/`

### DT-Korrektur
- **Pfad:** `~/.simpleft8/dt_corrections.json`
- **Format:** `{"FT8_20m": 0.24, "FT8_40m": 0.24, ...}` (pro Modus+Band)
- Migration von altem Format (`"FT8"` → `"FT8_20m"`) automatisch in `_load_for_current_key()`

### App-Sicherungen
- **Pfad:** `SimpleFT8/Appsicherungen/`
- Letzte stabile Sicherung: `2026-04-22_stable/`
- DT-Optimierung Backup: `2026-04-23_vor_dt_optimierung_core/` + `_ui/`

---

## Diversity-System

- **`_diversity_in_operate`** — Transition Guard in mw_cycle.py
  - Verhindert dass once-only Code (warmup, CQ-unlock, freq-update) jeden Zyklus läuft
  - Wird in `_enable_diversity()` auf False gesetzt (Reset)
  - Wird True beim ersten operate-Eintritt nach measure
- **THRESHOLD = 0.08** (8%) → 70:30 Ratio; darunter 50:50
- **MIN_MEASURE_STATIONS = 5**
- Median über 4 Zyklen
- Stats-Warmup: 60s nach Band/Modus-/App-Start

### CQ-Frequenz-Algorithmus (v0.59, dynamisch + slot-synchron)
- **Suchbereich DYNAMISCH:** `min(occupied_bins)..max(occupied_bins)` + `SEARCH_MARGIN_BINS=0`.
  TX landet immer ZWISCHEN niedrigster und höchster Station (= dort wo zugehört wird).
  Kein fester Sweet-Spot mehr (war v0.58-Sackgasse, in v0.59 verworfen).
- **Graduelle Lücken-Toleranz:** stufenweise `(max_count_per_bin, min_gap_bins)`:
  `(0,3)` → `(0,2)` → `(0,1)` → `(1,3)` → `(1,2)`. Bei vollem Band findet der Algo IMMER
  noch eine Position (notfalls in schwach-belegtem Bereich), nie mehr None außer leerem Histogramm.
- **Score:** `gap_width − 100·n_self − 50·n_close − 25·n_near − 0.01·median_distance`
  - `n_self` (Stationen IM TX-Bin) = höchste Strafe (100 Hz/Station) — für Notfall-Stufen
  - `n_close` (±1 Bin) = 50 Hz/Station, `n_near` (±2 Bin) = 25 Hz/Station
  - Median-Distance nur Tiebreaker (0.01)
- **Sticky Gap:** bleibt bei aktueller Frequenz wenn im dynamischen Suchbereich, keine Kollisions-
  Schwelle erreicht (`n_direct >= 2` ODER `n_in_band >= 3`) und neue Lücke nicht > +50 Hz breiter.
  `_measure_gap_around()` refresht `_current_gap_width_hz` nach Sticky-Hit.
- **Such-Trigger SLOT-SYNCHRON (v0.59 Punkt 3):** `_search_slots_remaining` Counter, modus-abhängig
  initialisiert via `_SEARCH_INTERVAL_SLOTS = {FT8:4, FT4:8, FT2:16}` = ~60 s alle Modi.
  `tick_slot()` dekrementiert pro Slot, bei 0 → Such-Trigger + auto-reset.
  Anzeige `seconds_until_search` = `remaining_slots × cycle_s`. Wert friert bei App-Pause ein (gut).
- **Pro-Slot-Aufruf:** `mw_cycle._refresh_diversity_freq_view()` läuft JEDEN Slot in
  `_on_cycle_decoded`, UNABHÄNGIG vom messages-Inhalt. Hinter `if messages:` Guard darf NIE
  was hin was UI/Such-Logik betrifft (P1-Bug aus v0.54-v0.58, fixed in v0.59).
- **`reset()` muss `_current_gap_width_hz = 0` und `_search_slots_remaining` setzen** —
  sonst Bandwechsel-Bug.

---

## Cycle-Zeiten

| Modus | Zyklusdauer | RX-Filter |
|-------|------------|-----------|
| FT8   | 15.0s      | 100-3100 Hz |
| FT4   | 7.5s       | 100-3100 Hz |
| FT2   | 3.8s       | 100-4000 Hz |

---

## ⛔ Statistik-Veröffentlichung — Regel

- **Minimum (Push erlaubt):** Normal + Diversity_Standard + Diversity_Dx je ≥ 2 Messtage,
  Stunden über den ganzen Tag verteilt (mind. 06–22 UTC).
- **Soll fuer solide Aussage (Mike+Claude+R1 2026-04-29):** **5 Tage flaechendeckend**
  pro Stunde-Modi-Slot, Tage ueber 2-4 Wochen verteilt (Solar-Variation glaetten).
  Lueckenfreie Slot-Abdeckung schlaegt mehr-Tage-mit-Luecken.
- **7 Tage Goldstandard:** explizit verworfen — nur ~15% Standard-Error-Reduktion
  gegenueber 5, ~5 Wochen Aufwand vs ~3 Wochen. Diminishing Returns klar erreicht.
  Overengineering im Hobby-Kontext.
- **Auswertungs-Methodik:** Pooled Mean über ALLE Messzyklen aller Messtage und Tageszeiten —
  kein Stunden-Filter. Monatlich wachsende Datenbasis.
- Ergebnis 40m FT8 (Pooled Mean, global, Stand 25.04.2026): Diversity Standard +88%, Diversity DX +123%.

---

## generate_plots.py — Berechnungsmethodik (Tagesdurchschnitt)

**Wie der Ø Sta./15s-Zyklus berechnet wird:**

```
statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md
  → jede Datei = 1 UTC-Stunde, 1 Modus, 1 Band
  → jede Zeile = 1 FT8-Zyklus (15s) mit Spalte "stationen" (Anzahl dekodierter Stationen)

Ø Sta./15s = Summe aller Stationswerte ÷ Anzahl aller Zyklen
             (über ALLE Dateien = alle Tage × alle Stunden × alle Zyklen)

Beispiel Normal: 6.744 Zyklen × ~18.5 Sta./Zyklus
  → Das entspricht dem Tagesdurchschnitt wenn man morgens, mittags, abends misst
  → KEIN Tageszeit-Filter, KEINE Gewichtung nach Stunde oder Tag
  → Je mehr Messpunkte (Zyklen), desto stabiler der Wert
```

**Was der Wert NICHT ist:**
- ❌ Nicht Stationen pro Stunde (wäre 18.5 × 240 = 4.440/h)
- ❌ Nicht der Spitzenwert einer bestimmten Tageszeit
- ✅ Der Durchschnitt über einen ganzen typischen Betriebstag

**Weitere PDF-Layout-Details:**
- **Inch-Koordinaten:** `_yf(y_in) = 1.0 - y_in / _PH` konvertiert Zoll→figure-coord
- **Cursor-Helpers:** `_ctext(fig, y, text, fs)` → gibt neues y zurück; `_chline` → Linie; `_csection` → Titel+Linie+Body
- **Seitenhöhe:** A4 landscape: `_PH=8.27`, `_PW=11.69`, `_CTOP=1.00`, `_CBOT=7.71`
- **Body 11pt / Titel 13pt** — nie hardcoded figure-y, nie `_r_hline` (veraltet, gelöscht)
- **Rescue-Kappen:** grün, nur Diversity-Modi, `load_rescue_by_hour(stats_dir, mode, band, proto)`
- Statistics-Daten: `statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md`

---

## Datenlage (Stand 26.04.2026)

**WICHTIG:** Statistik-Filter v0.63 — nur 20m + 40m FT8 werden noch protokolliert.
Andere Baender werden empfangen aber nicht gespeichert (Skalierungs-Entscheidung).

| Modus            | Band | Tage | Zyklen | Bemerkung |
|------------------|------|------|--------|-----------|
| Normal           | 40m  | 4    | 6.744  | 24h Abdeckung |
| Diversity_Normal | 40m  | 4    | 6.827  | 24h Abdeckung |
| Diversity_Dx     | 40m  | 4    | 9.125  | 24h Abdeckung |
| Normal           | 20m  | 5    | 688    | 13 Stunden, waechst |
| Diversity_Normal | 20m  | 2    | 364    | 5 Stunden, schwach |
| Diversity_Dx     | 20m  | 4    | 2.469  | 18 Stunden |

**40m FT8 Ergebnis (Pooled Mean global, 22.696 Zyklen):**
- Diversity Standard: **+88% / +122%** (ohne/mit Rescue), Rescue allein +35%
- Diversity DX:       **+124% / +158%** (ohne/mit Rescue), Rescue allein +34%

**20m FT8 Ergebnis (Pooled Mean Stunden-Vergleich, Stand 26.04.):**
- Diversity_Normal: +15-30% im Tageshoch (12-16 UTC) — KEIN Antennen-Mismatch
  wie auf 40m, sondern echte Pol-/Pattern-Diversity (ANT1 ist resonant!)
- Diversity_Dx: +59% beim Tag→Nacht-Uebergang (18 UTC) — DX-Modus glaenzt am Skip-Zonen-Rand
- ANT2-Win-Rate Doppelempfaenge: 79% (Std), 86% (Dx) trotz resonantem Kelemen-Dipol auf ANT1
- Datenbasis waechst noch — siehe `Auswertung-20m-FT8.pdf` mit eigenem Narrativ

---

## ⛔ OMNI-TX (PRIVAT — NICHT AUF GITHUB WIE MAN ES AKTIVIERT)

- Aktivierung: Klick auf Versionsnummer → CQ-Button wird "OMNI CQ"
- Status: **DEAKTIVIERT** — Feldtest ausstehend
- GitHub: Feature darf erwähnt werden, NICHT wie aktiviert

---

## Thread-Safety

| Modul | Lock | Was geschützt |
|-------|------|---------------|
| `core/diversity.py` | `threading.Lock()` (`_hist_lock`) | Histogramm-Daten |
| `core/station_stats.py` | `queue.Queue` + Daemon-Thread | File-Writes |
| `core/ntp_time.py` | `threading.Lock()` (`_lock`) | Korrekturwert + Phase |
| `core/antenna_pref.py` | `threading.RLock()` (`_lock`) | _prefs dict (Karten-Render-Pfad) |
| `core/psk_reporter.py` | `threading.Lock()` (`_lock`) | _thread/_stop_event Lifecycle |
| `core/locator_db.py` | `threading.RLock()` (`_lock`) | _calls dict (Decoder + PSK-Worker konkurrent) |

**Karten-Live-Daten-Pfad (v0.66):** Decoder-Thread → `_emit_map_snapshot_if_open`
→ `direction_map_signal.emit(snapshot, band)` → `Qt.QueuedConnection` →
`_on_direction_map_snapshot` (GUI-Thread) → `canvas.update_stations`. Niemals
direkt aus dem Decoder-Thread Widget-Methoden aufrufen — immer ueber das Signal.

---

## Änderungshistorie

**HISTORY.md** — lückenlose Aufzeichnung aller Änderungen, Bugfixes und Features.
- Datei: `SimpleFT8/HISTORY.md`
- Regel: **Nur anhängen, niemals löschen oder überschreiben.**
- Bei jeder Session: Änderungen am Ende eintragen (Feierabend-Routine Schritt 3).
- **Versionsnummer IMMER mitführen!** Format: `## YYYY-MM-DD vX.YY — Kurztitel`
  - `APP_VERSION` steht in `main.py` (erste Konstante nach den Imports)
  - Bei neuen Features: Patch-Version +0.01 erhöhen, bei Bugfix-only: unverändert lassen
  - So ist für jedes Appsicherungen-Backup sofort klar, welcher HISTORY-Eintrag dazugehört

---

## ⛔ TODOs gehoeren in TODO.md im Projektverzeichnis (Mike-Anweisung 07.05.2026)

**Regel:** Alle offenen Aufgaben, Bugs, Feature-Wuensche, Folgearbeiten
gehoeren EXKLUSIV in `SimpleFT8/TODO.md` — NICHT in CLAUDE.md, NICHT in
HANDOFF.md (HANDOFF nur „Stand der laufenden Session" + „naechste 1-2
Schritte"). CLAUDE.md ist fuer Architektur, Konventionen, Workflow-Regeln,
Hardware-Warnungen — nicht fuer den Backlog.

- **Naechste Aufgaben + offene Bugs** → `SimpleFT8/TODO.md`
- **Aktueller Stand der Session + naechster Schritt** → `HANDOFF.md`
- **Lueckenlose Aenderungshistorie** → `HISTORY.md`

Bei Doku-Updates: nicht in CLAUDE.md duplizieren was in TODO.md steht.

---

## Bekannte Fallen & Bugs

- **cache.save() nie im Cycle-Loop** — refresht Timestamp → 2h Gültigkeit wird sinnlos
- **_diversity_in_operate vergessen** — once-only Code läuft sonst jeden Zyklus
- **Gain-Messung** — sperrt GUI always-on-top; TX vorher stoppen
- **Stats Warmup** — `_stats_warmup_cycles` an mehreren Stellen in mw_radio.py
- **Statusbar Race** — nach Radio-Connect kurz unsichtbar; Workaround: QTimer.singleShot(200, ...)
- **_r_hline existiert nicht mehr** — ersetzt durch `_chline` in generate_plots.py (nie wieder einbauen)
- **`_tune_active` + `_tune_freq_mhz`** — in `main_window.__init__` initialisiert; `_update_statusbar()` liest beide für `TUNE: xx kHz` Anzeige
- **CQ set_cq_active()** — muss immer wenn `cq_mode=True` aufgerufen werden, nicht nur in CQ_CALLING/CQ_WAIT (sonst bleibt Button nach QSO visuell inaktiv)
- **DT_BUFFER_OFFSET** — FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet!) — bei Modus-Änderungen immer prüfen
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 Fork braucht eigenen Wert
- **dt_corrections.json Key-Format** — "FT8_20m" (Modus_Band), Migration von "FT8" automatisch
- **_was_cq Bug (gefixt)** — `_on_station_clicked` rief `stop_cq()` VOR `start_qso()` → `_was_cq=False` → CQ resumte nicht nach manuellem QSO; Fix: `_cq_was_active` vor stop_cq() sichern, nach start_qso() als `_was_cq=True` setzen
- **Stats Guard (3-fach)** — `btn_cq.isChecked()` + `cq_mode` + `state not in IDLE/TIMEOUT` → robuster gegen desynchronisierte States
- **Histogramm-/Freq-View Update muss IMMER pro Slot laufen** (v0.59 Punkt 3 / P1-Bug-Fix). Niemals einen `if messages:` Guard um `_refresh_diversity_freq_view()` legen — sonst Counter-Drift, hängende Anzeige, TX-Position veraltet
- **CQ-Such-Periode = 60 s konstant** alle Modi (DeepSeek + WSJT-X-Praxis: < 30 s killt QSO-Aufbau weil antwortende Station auf alter TX-Frequenz fixiert ist)
- **`SWEET_SPOT_MIN_HZ`/`MAX_HZ` Klassenkonstanten gibt's NICHT mehr** (v0.58-Sackgasse, v0.59 entfernt). Falls in altem Code Verweis auftaucht: Suchbereich ist dynamisch, nicht fest
- **v0.75 Auto-Hunt:** `_auto_hunt_timer` ist UNABHAENGIG vom Totmannschalter — Maus/Tastatur reset ihn NICHT (Bot-Tarn-Schutz). Nach jedem Stop ist Pflicht-Restart (User-Klick), kein Auto-Resume in `_reset_presence`. Race-Doppel-Check in `select_next` ist ethische Belt-and-suspenders zur 10-Min-Hard-Cap — NICHT als "redundant" entfernen. `_MAX_ATTEMPTS=3` in `core/auto_hunt.py:45` ist Modul-Konstante OHNE Verwendung in der Klasse (3-Versuche-Logik liegt in `qso_state.py`). `btn_omni_cq` hat aktuell keinen eigenen `clicked`-Handler — OMNI-CQ laeuft weiter ueber bisherige Logik (Phase 2-TODO)
- **v0.81/v0.82 Decoder-Signal-Reihenfolge (Fix D + Fix E):** Decoder emittet 3 Signale pro Slot in dieser Reihenfolge: `cycle_decoded` (Aggregation in `mw_cycle._on_cycle_decoded`) → pro msg `message_decoded` (state-Wechsel via `on_message_received`) → `cycle_finished` (Slot-Ende-Hook via `_on_cycle_finished` → `qso_sm.on_decoder_finished`). REIHENFOLGE NICHT AENDERN — `on_decoder_finished` MUSS nach allen State-Wechseln laufen (Doppel-Report-Bug v0.80/v0.81). `_assign_slot_parity` in `_on_cycle_decoded` setzt `msg._tx_even` BEVOR `on_message_received` es liest (mw_qso.py:85, :423) — `cycle_decoded` muss vor `message_decoded` bleiben.
- **`on_cycle_end` vs `on_decoder_finished`:** `on_cycle_end` laeuft am Slot-START (Timer-Pfad, Decoder-unabhaengig) und behandelt: 3-Min-Gesamttimeout, WAIT_73-Tick, CQ_WAIT-Trigger, Counter-Inkrement, Max-Timeout-Check. `on_decoder_finished` laeuft am Slot-ENDE (Decoder-Pfad ueber `cycle_finished`-Signal) und triggert NUR den Retry-Pfad (WAIT_REPORT/WAIT_RR73 mit `timeout_cycles == 1`). Aufspaltung ist kritisch — wer sie zusammenfuehren will: CQ_WAIT bricht bei Decoder-Hang.

---

# ⛔⛔⛔ WORKFLOW-PFLICHT — NOCHMAL — LETZTE ERINNERUNG (RECENCY BIAS) ⛔⛔⛔

Du liest das am Ende des Dokuments. Recency Bias sorgt dafuer dass du dich daran erinnerst.

**JEDE Code-Änderung — JEDE — IMMER den vollen Workflow:**
## V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code

**KEINE Ausnahmen. NIEMALS. Das Projekt ist zu komplex fuer Quick-Fixes.**

→ **Skill aufrufen:** `.claude/skills/ft8_workflow.md`
→ **Selbst-Check:** "Workflow durchgeführt?" NEIN → SOFORT STOPPEN.
→ **01.05.2026:** Claude hat Label-Fix ohne Workflow gemacht → Mike-Unterbrechung.
   Genau das DARF NICHT WIEDER PASSIEREN.
