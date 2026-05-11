# HANDOFF — SimpleFT8

## Stand 2026-05-11: P26.CONNECT-MODAL Field-Test ✅ + Tweak v0.96.10

**Code:** v0.96.10 lokal. Mike Field-Test 11.05. ✅ „funktioniert super".
**Tests:** **1070 grün**.
**Field-Test-Tweak:** Versuch-Counter raus, Fenster 20% kleiner (352×176).
**Push pending** bis Mike OK gibt — v0.95.16-0.96.10 + P2-Tool + P3 +
P21-Debug-Log + P26 zusammen.

## P26 Status

- ✅ V1 → V2 → R1 → V3 → Code → Final-R1 → Field-Test
- ✅ Mike-Approval: „funktioniert super"
- ✅ Field-Test-Tweak v0.96.10 (Versuch-Counter raus, kleineres Fenster)
- ⏳ Push ausstehend

## Was P26 fixt

Beim App-Start war heute nicht prominent sichtbar was die App tut
(FlexRadio-Suche nur als kleiner Status-Indikator rechts). Plus: keine
Möglichkeit die App ohne Radio zu starten (Test/Debug, Mike 200 km vom
Radio entfernt). Lösung: WindowModal-Dialog mit Spinner + „Versuch X
von 10", Auto-Close bei Connect, „ohne Radio weiter"-Text-Link
(klein/dezent, kein Demo-Modus-Button) + „Beenden"-Button.

**Architektur-Highlight (R1-K2-Fix):** `_start_radio()` wird via
`QTimer.singleShot(0, ...)` aus MainWindow-Init deferred — sonst würde
`dialog.exec()` den restlichen Init blockieren und Hauptfenster wäre
unsichtbar.

**Race-Schutz (R1-K1-Fix):** Worker holt lokale Dialog-Referenz +
`try/except RuntimeError` um jedes `emit`. PySide6 wirft RuntimeError
beim emit auf destroyed C++-Object — V2 hatte fälschlich „swallowed"
angenommen.

## Atomare Commits (ausstehend)

- C1 `radio/flexradio.py` `on_attempt`-Param in `auto_connect`
- C2 `ui/connect_status_dialog.py` NEU
- C3 `ui/mw_radio.py` Modal-Lifecycle in `_start_radio` + Worker
- C4 `ui/main_window.py` `_connect_dialog`-Attribut + singleShot-Defer
- C5 `tests/test_p26_connect_modal.py` NEU (14 Tests)
- C6 `main.py` APP_VERSION 0.96.8 → 0.96.9 + HISTORY/HANDOFF/CLAUDE/Memory

## Field-Test-Plan (V3 §8, 6 Punkte)

| F | Test | Erwartung |
|---|---|---|
| F1 | App-Start mit Radio AN | Modal kurz sichtbar, Spinner, „Versuch 1 von 10", schließt sofort wenn Connect da, Hauptfenster sichtbar |
| F2 | App-Start mit Radio AUS | Modal bleibt offen, Spinner, „Versuch 1...10", nach ~50s „Verbindung fehlgeschlagen" + ✗, Buttons aktiv |
| F3 | „ohne Radio weiter" mid-Connect | Modal weg, Hauptfenster sichtbar, Status „disconnected", App läuft GUI-only |
| F4 | „Beenden" Click | App schließt sofort sauber |
| F5 | Mid-Run-Disconnect (Radio aus während App läuft) | KEIN neues Modal, heutige Reconnect-Anzeige im Status-Indikator |
| F6 | Connect SEHR schnell (lokales LAN) | Modal flackert kurz auf und ist weg — kein UI-Glitch |

**Bestanden wenn:** F1-F4 sauber. F5+F6 sind Robustheits-Bonus.

## Plan-Files

- ✅ `prompts/p26_connect_modal_v1.md` (V1 initial)
- ✅ `prompts/p26_connect_modal_v2.md` (V2 Self-Review, 14 Lessons)
- ✅ `prompts/p26_connect_modal_r1_prompt.md` + `_r1.md` (Pre-Code R1: 3 KRITISCH + 3 SOLLTE)
- ✅ `prompts/p26_connect_modal_v3.md` (Compact-fest, R1-K1/K2/K3-Fixes)
- ✅ `prompts/p26_connect_modal_final_r1_prompt.md` + `_final_r1.md` („Push freigegeben")

## Naechste Aufgabe

1. **Field-Test 6 Punkte** durch Mike (App-Start mit/ohne Radio,
   Buttons, Mid-Run-Disconnect).
2. **Atomare Commits C1-C6** wenn Field-Test grün.
3. **Push** v0.95.16-0.96.9 + P2-Tool + P3 + P21 + P26 zusammen.

---

## Vorheriger Stand (v0.96.7 P23.OMNI-COUNTER-EIGEN)

**Code:** v0.96.7 — C1-C8 atomare Commits ausstehend.
**Tests:** **1049 grün** (1035 → 1049, +14 effektiv).
**Final-R1:** noch nicht gelaufen — vor Push fällig.
**Field-Test:** 5-Punkte-Plan V3 §7 F1-F5 ausstehend.

## Was P23 fixt

OMNI-CQ-Paritaets-Wechsel haengt heute am Diversity-Such-Counter (60s ×
10 = ~10 Min). Coupling zur Diversity-Mess-Mechanik: wenn Mess hängt,
kein Such-Trigger, kein Wechsel. Mike will eigenen Counter im OMNI:
sichtbar (`↻10`), zaehlt DOWN (10→1), bei 0 Auto-Flip + Reset auf
TARGET. Modus-spezifische Targets: FT8=10, FT4=20, FT2=40 (alle ~5 Min
Wallclock).

**Counter-Resets:**
- QSO eingehend (Mike: „guter Slot, neuer Anfang")
- Antennenmessung fertig (neuer Slot nach Mess)

**Stop-Trigger (heutiges Verhalten):**
- Bandwechsel
- Modus-Wechsel

## Atomare Commits (8 geplant — noch nicht gepushed)

- C1 `core/omni_cq.py` Counter-Refactor + on_search_trigger raus
- C2 `tests/test_omni_cq_signal.py` Migration (3 LOESCHEN, 6 ANPASSEN)
- C3 `ui/mw_cycle.py` Hook-Umbau (search-trigger raus, mess-reset rein)
- C4 `ui/qso_panel.py` add_tx Suffix `↻N`
- C5 `ui/mw_qso.py` _on_tx_started Counter-Read
- C6 `ui/main_window.py` Statusbar nutzt cq_remaining
- C7 `tests/test_p23_omni_counter.py` NEU — 17 Tests
- C8 `main.py` APP_VERSION 0.96.6 → 0.96.7 + HISTORY/HANDOFF/CLAUDE/Memory

## Field-Test-Plan (V3 §7, 5 Punkte)

| F | Test | Erwartung |
|---|---|---|
| F1 | App-Start FT8+OMNI | Statusbar `Ω CQ=10 (E)`, TX-Zeile endet auf `↻10` |
| F2 | 5 Min beobachten | Counter 10→9→...→1, dann Auto-Flip + `↻10` in anderer Paritaet (Log: „Paritaets-Wechsel auf Odd") |
| F3 | Modus-Wechsel zu FT4 + OMNI neu an | `Ω CQ=20` + TX-Zeile `↻20` |
| F4 | QSO eingehend | Nach QSO: Counter zurueck auf TARGET, naechste TX-Zeile `↻TARGET` |
| F5 | Antennenmessung fertig | Counter zurueck auf TARGET (kommt eh alle ~1h, kein Trigger noetig) |

**Bestanden wenn:** F1-F4 sauber. F5 in echter Mess beobachten.

## Plan-Files

- ✅ `prompts/p23_omni_counter_v1.md` (V1 initial, 10 Sektionen)
- ✅ `prompts/p23_omni_counter_v2.md` (V2 Self-Review, 8 Lessons)
- ✅ `prompts/p23_omni_counter_r1_prompt.md` + `_r1.md` (R1: 2×KRITISCH + 3×SOLLTE)
- ✅ `prompts/p23_omni_counter_v3.md` (Compact-fest, EINZIGE WAHRHEIT)

## Naechste Aufgabe

1. **Final-R1 Review** mit `tools/deepseek_review.py` (deepseek-reasoner)
   ueber alle aenderten Files.
2. **Atomare Commits C1-C8** nach Final-R1-OK.
3. **Field-Test 5 Punkte** durch Mike.
4. **Push** v0.95.16-0.96.7 + P2-Tool + P3 wenn Field-Test gruen.

## Bisheriger Stand (vor P23)

- v0.96.4 P7.OMNI-SIMPLIFY: Single-Slot-CQ. Field-Test erfolgreich (QSO mit OH3BY).
- v0.96.5 P16.UI-CLEANUP-BUNDLE: P9+P11+P15 zusammen.
- v0.96.6 P22.PRESET-ATOMARITAET + P8.MESS-MODAL: atomares Persist von
  Gain+Ratio + WindowModal-Mess-Sperre + Final-R1 KRITISCH-Fix
  (Settings-Bw-Compat schrieb auch bei Adaptiv-Stop). 8 Commits drin
  (`aac7945` bis `0614e91`).

## Vorheriger HANDOFF-Inhalt (P22+P8)

## Stand 2026-05-10 ~15:30 UTC: P22+P8 ATOMARES PERSIST + MESS-MODAL — Code fertig, Final-R1 + Field-Test pending

**Code:** v0.96.6 lokal — C1-C8 atomare Commits ausstehend (alle Aenderungen
auf disk, noch nicht committed). 8 Commits geplant.
**Tests:** **1034 grün** (1019 → 1034, +15 Pipeline+Modal-Tests).
**Final-R1:** noch nicht gelaufen — als naechste Aufgabe.
**Field-Test:** 5-Punkte-Plan V3 §8 F1-F5 ausstehend, Mike startet App selbst.
**App:** gestoppt. **Push pending** bis Final-R1 + Field-Test gruen —
v0.95.16-0.96.6 + P2-Tool + P3 zusammen.

## Was P22+P8 fixt

**Wurzel:** `presets_dx.json` / `presets_standard.json` koennen Half-State
enthalten (Phase 2 schreibt sofort, Phase 3 schreibt nur bei Erfolg). Wenn
Phase 3 haengt (z.B. Antennen-Switch greift nicht in DX), bleibt Disk-
Halbstand → Restart triggert wieder Phase-3-Versuch → endlose Schleife.

**Loesung:**
- **Atomares Persist:** `stage_gain` (Memory) + `commit_with_ratio` (atomar
  Disk) + `discard_staged` (Cancel/Crash). Phase 2 alleine produziert
  keinen Disk-Eintrag mehr.
- **Mess-Modal:** WindowModal sperrt UI waehrend Phase 3 — kein
  Bandwechsel/Modus/Hunt/CQ. Cancel-Button raeumt staged + Diversity auf.
- **Half-State-Reject:** `is_valid_gain` lehnt Eintraege ohne `ratio`-Feld
  ab → Restart faellt sauber in `gain missing`-Branch (volle Pipeline).
- **Disk-Fehler-Schutz:** alle Schreibmethoden fangen Exception, returnen
  False, App crasht nicht. Atomic write via tempfile + os.replace.

**Bewusst nicht gebaut (Mike-Klaerung):** Stall-Detector — Wurzel ist
nicht bestaetigt das es an der Antennenmessung lag (Hänger war bei
QSO-Ende = P12). Wurzel-Diagnose Antennen-Switch separat als P23.

## Atomare Commits (8 geplant — noch nicht gepushed)

- C1 `core/preset_store.py` Atomic Methods + is_valid_gain Reject + atomic save
- C2 `tests/test_preset_store.py` T1-T8 + Anpassungen (48 Tests gruen)
- C3 `ui/mess_status_dialog.py` NEU — MessStatusDialog WindowModal
- C4 `ui/mw_radio.py` Pipeline (stage vs save) + Modal-Helpers
- C5 `ui/mw_cycle.py` commit_with_ratio + Modal-Close
- C6 `ui/main_window.py` closeEvent staged-Cleanup + Modal hart schliessen
- C7 `tests/test_p22_preset_atomic.py` (NEU, 15 Tests Pipeline+Modal)
- C8 `main.py` APP_VERSION 0.96.5 → 0.96.6 + HISTORY/HANDOFF/Memory

## Field-Test-Plan (V3 §8, 5 Punkte)

| F | Test | Erwartung |
|---|---|---|
| F1 | App-Start in Diversity DX | Modal oeffnet, zeigt Antenne/Schritt/Restzeit, Hauptfenster gesperrt (Bandwechsel-Klick = kein Effekt) |
| F2 | Mess laeuft sauber durch (6 Schritte FT8) | Modal auto-close nach phase=operate. File enthaelt `gain_*` UND `ratio_*` mit gleichem Timestamp |
| F3 | Mid-Mess Cancel-Button | Modal weg, Diversity disabled, App auf Normal-Mode zurueck. File: kein neuer Eintrag |
| F4 | Mid-Mess Cmd-Q | Beim naechsten Start `is_valid_gain==False` (Half-State weg), volle Pipeline laeuft |
| F5 | Disk-Permission-Fehler (chmod 000 auf kalibrierung-Dir) | App crasht NICHT, Log-Eintrag, Modal schliesst (phase=operate erreicht), staged bleibt im Memory |

**Bestanden wenn:** F1-F4 sauber. F5 ist Bonus-Robustheit.

## Plan-Files

- ✅ `prompts/p22_preset_atomic_v1.md` (V1 initial)
- ✅ `prompts/p22_preset_atomic_v2.md` (V2 Self-Review, 15 Lessons)
- ✅ `prompts/p22_preset_atomic_r1_prompt.md` + `_r1.md` (R1 4×KRITISCH + 4×SOLLTE)
- ✅ `prompts/p22_preset_atomic_v3.md` (Compact-fest, EINZIGE WAHRHEIT)

## Mike-Klaerung dokumentiert

- **Q1 (Stall-Fallback):** NICHT bauen — Wurzel unbestaetigt. P23 separat.
- **Q2 (Bandwechsel mid-Mess):** Modal sperrt → kann nicht passieren.
- **Q3 (Adaptiv-Stop ohne Persist):** Bestehender v0.91-Cache-Schutz bleibt.

## Naechste Aufgabe

1. **Final-R1 Review** mit `tools/deepseek_review.py` (deepseek-reasoner)
   ueber alle aenderten Files. Findings einarbeiten oder ablehnen.
2. **Atomare Commits C1-C8** nach Final-R1-OK.
3. **Field-Test 5 Punkte** durch Mike.
4. **Push** v0.95.16-0.96.6 + P2-Tool + P3 wenn Field-Test gruen.

## Bisheriger P7-Stand (v0.96.4)

P7.OMNI-SIMPLIFY ist **erledigt** und im Repo. Field-Test war erfolgreich
(QSO mit OH3BY Finnland). P16 (UI-Cleanup-Bundle, v0.96.5) wurde
zwischenzeitlich committed. P22+P8 ist die naechste Stufe.

## Was P7 gefixt hat

**Wurzel-Problem (P5+P6):** TX-TX-konsekutiv in 15s-Slots passt physisch
nicht zu Encoder + Diversity. Beide Workarounds verbiegten Encoder
(P5 Pending-Queue) oder Diversity (P6 Pair-Audio).

**P7-Lösung:** Pattern ändern statt Encoder/Diversity verbiegen.
- OMNI = Single-Slot-CQ in EINER Paritaet
- Wechsel ueber Diversity-Such-Counter alle ~10 Min
- Diversity 100% unangetastet
- Code netto ~800 Zeilen weniger im Repo

## Atomare Commits

- C1 (`ac254a5`): `core/encoder.py` P5+P6 zurueckrollen (-272 Z.)
- C2 (`3f98caf`): `core/omni_cq.py` radikale Vereinfachung (305 → 246 Z.)
- C3 (`741f526`): `ui/mw_cycle.py` Such-Trigger-Hook
- C4 (`332c9f8`): `ui/main_window.py` Signal+Statusbar
- C5 (`956ef61`): Tests T1-T14 + alte raus (-524 Z. netto)
- C6 (`3111cfe`): `main.py:16` APP_VERSION → 0.96.4
- C7 (folgt): Doku-Updates

## Field-Test-Plan (V3 §6, 8 Punkte)

| F | Test | Erwartung |
|---|---|---|
| F1 | App start, Diversity, OMNI toggeln | OMNI-Start-Log + CQ-Audiofreq-Set + erster CQ in aktuellem Slot |
| F2 | 5-10 Min beobachten | CQ-Ruf in EINER Paritaet (z.B. nur Even-Slots :30/:00). Andere Slots leer im qso_panel. **Diversity-Anzeige zeigt beide Antennen wechselnd** (kein „nur eine"). |
| F3 | Statusbar checken | `Ω CQ=X (E)` oder `(O)` zeigt aktuellen Stand |
| F4 | 10 Min weiterlaufen lassen | Paritaets-Wechsel automatisch (Log: „Paritaets-Wechsel auf Odd"). qso_panel zeigt ab dann CQ in anderer Paritaet (z.B. nur Odd :45/:15) |
| F5 | Antwort kommt waehrend OMNI | OMNI pausiert, QSO laeuft normal mit voller Diversity. Nach QSO: OMNI resumed in alter Paritaet |
| F6 | 1h warten → Diversity Re-Mess (90s) | OMNI sendet **nicht** waehrend Mess (Log: kein TX-Eintrag in 90s). Nach Mess: OMNI sendet wieder |
| F7 | Bandwechsel mid-OMNI | OMNI auto-stop (band_change), App stabil |
| F8 | Mode-Wechsel auf Normal | OMNI auto-stop (mode_change), App stabil |

**Bestanden wenn:** F1-F4 sauber + F2 zeigt Diversity beide Antennen.

## Plan-Files

- ✅ `prompts/p7_omni_simplify_v1.md` (V1 initial)
- ✅ `prompts/p7_omni_simplify_v2.md` (V2 Self-Review, 12 Lessons)
- ✅ `prompts/p7_omni_simplify_v3.md` (Compact-fest, EINZIGE WAHRHEIT)
- ✅ `prompts/p7_omni_simplify_r1_prompt.md` + `_r1.md` (Pre-Code R1)
- ✅ `prompts/p7_omni_simplify_final_r1_prompt.md` + `_final_r1.md` (Post-Code R1)

## Memory-Verweise

- `project_omni_cq_spec.md` — **VERALTET** (alte 5-Slot-Spec). P7-Spec
  steht in V3 §2 + HISTORY-Eintrag. Sollte in C7 ueberarbeitet werden.
- `feedback_omni_separate_architecture.md` — gilt weiter (eigenes Modul)
- `feedback_test_critical_path_not_mock.md` — eingehalten in T1-T14

## App-Start

```bash
# Empfohlen: Doppelklick auf starter.command im Finder
# Oder Terminal:
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```

Single-Instance-Schutz aktiv (Window-Title-Check via osascript).

## Tests

`QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
→ **1008 grün** Stand v0.96.4.

## Was als nächstes geplant ist

**P8.MESS-STATUS-DIALOG** (in `TODO.md` dokumentiert):
- Modal-Dialog wenn `_diversity_ctrl.start_measure()` aufgerufen wird
- Counter, aktuelle Antenne, Restzeit
- Schließt automatisch nach Phase „operate"
- Eigener Workflow V1→V2→R1→V3 nach P7-Field-Test-Freigabe

## Nicht-vergessen

- **Symlinks aktiv:** `FT8/CLAUDE.md` + `FT8/HANDOFF.md` sind Links auf
  `SimpleFT8/CLAUDE.md` + `SimpleFT8/HANDOFF.md`. KEIN Doppel-Edit.
- **App ist gestoppt.** Mike startet sie für Field-Test selbst.
- **Push pending** bis P7 Field-Test grün.
- **OMNI in Live-Betrieb wieder OK** wenn Field-Test grün.
