# Bundle F — V3 (Final Plan, Compact-fest)

**Basis:** V1 + V2 + R1-Review (8/10, „Push freigegeben" nach SOLLTE-Fixes)
**Datum:** 2026-05-14 morgens

## R1-Findings Übernahme

| Finding | Status | Aktion |
|---|---|---|
| SOLLTE 1 (DXTune-Race) | **ABGELEHNT mit Begründung** | R1 hat `_gain_measure_locked` als Attribut auf `DiversityController` halluziniert. Code-grep `core/diversity.py` + `core/omni_cq.py` → KEINE Treffer. Sitzt nur in `ui/mw_radio.py`. `getattr(self._diversity, '_gain_measure_locked', False)` würde immer False liefern → de-facto kein Schutz. Memory-Lesson `feedback_r1_encoder_busy_blindspot.md` anwendbar. KISS-Position: Phase-Check raus, kein Ersatz. DXTuneDialog ist modal — User kann OMNI währenddessen nicht starten. Falls OMNI vor Mess lief: Encoder returnt `busy=False` → OMNI loggt warning, kein Hardware-Schaden. Falls Race empirisch auftaucht: separater Fix. |
| SOLLTE 2 (Layout) | ÜBERNOMMEN | Visuell prüfen ob `_sep_line()` nach `state_label` zu eng wirkt. Falls ja: `lay.setSpacing(...)`-Adjustment. Test-Anpassung F6 (Field-Test). |
| SOLLTE 3 (Field-Test F5) | ÜBERNOMMEN | F5 streichen, durch QSO-Interaktion-Test ersetzen. |
| KÖNNTE 1 (Memory-Lesson) | ÜBERNOMMEN | `feedback_test_critical_path_not_mock.md` ergänzen + Checkliste für Partial-Fix-Klasse einbauen. |
| KÖNNTE 2 (Commit-Merge) | ÜBERNOMMEN | C2+C5 mergen → 6 Commits statt 7. |

## Acceptance Criteria (16 ACs, Compact-fest)

### Code

- **AC1 (`core/omni_cq.py`):** Z.231-233 (Phase-Check Block) ersatzlos
  entfernen, inkl. `# V2-L12: kein Senden waehrend Diversity-Mess-Phase`
  Kommentar.
- **AC2 (Tests Mock-Cleanup):** Aus 4 Test-Files entfernen:
  - `tests/test_omni_cq_signal.py` Z.33 (`diversity_phase` Param in
    `_make_omni`-Helper) + Z.40 (`diversity.phase = diversity_phase`
    Setter) + Test-Funktion T5 (`test_on_cycle_start_skip_measure_phase`)
    komplett löschen
  - `tests/test_p23_omni_counter.py` Z.37+47 analog
  - `tests/test_p45_omni_stats_guard.py` Z.64 (`obj._diversity_ctrl.phase
    = "operate"`) Zeile raus
  - `tests/test_p34_elif_chain_intact.py` Z.34 (`s._diversity_ctrl.phase
    = "operate"`) Zeile raus
- **AC3 (`ui/control_panel.py` cycle_bar):**
  - Z.1150-1156 (Definition + addWidget) entfernen
  - Z.1336 (`self.cycle_bar = qso_card.cycle_bar` Alias) entfernen
  - Z.1947-1957 (`update_cycle_bar` Methode) entfernen
- **AC4 (`ui/mw_cycle.py:519`):** `self.control_panel.update_cycle_bar(
  seconds_in_cycle, cycle_duration)` Aufruf entfernen + zugehöriger
  Kontext-Code (z.B. seconds_in_cycle-Berechnung falls nur dafür).
- **AC5 (Layout-Check):** Nach AC3 visuell prüfen: zwischen `state_label`
  („Status: IDLE | DT: ...") und `_sep_line()` darunter muss optisch
  natürlicher Abstand bleiben. Wenn Layout zu eng wirkt: `lay.setSpacing`
  oder `lay.addSpacing(4)` zwischen state_label und sep_line einfügen.
  Empirischer Test via App-Start (Backup vorhanden).
- **AC6 (`ui/main_window.py` Orange):**
  - Z.500 Initial-Style: bleibt Cyan (Start-Slot Even) — kein Edit
  - Z.1269 chunk-Konstante: `"#FF66CC"` → `"#FFAA00"`, Kommentar
    „cyan / magenta" → „cyan / orange"
  - Z.495 Tooltip: „Cyan = Even, Magenta = Odd" → „Cyan = Even,
    Orange = Odd"
  - Z.486 Klassen-Kommentar: „Cyan (Even) / Magenta (Odd)" → „Cyan
    (Even) / Orange (Odd)"
  - Z.1252 Docstring `_update_slot_progress_bar`: gleicher Replace

### Tests

- **AC7 (`tests/test_bundle_d.py:212`):** `"#FF66CC"` → `"#FFAA00"`,
  Error-Msg „Expected magenta" → „Expected orange", Test-Name falls
  vorhanden mit „magenta" → „orange".
- **AC8 (NEU `tests/test_bundle_f.py`):**
  - T1: `DiversityController` hat KEIN `phase`-Attribut (Bug-Schutz
    gegen P34-Partial-Fix-Regression; nutzt **echten**
    `DiversityController`, nicht MagicMock)
  - T2: `OmniCQ.on_cycle_start` ruft `encoder.transmit` bei aktivem
    OMNI + matched parity OHNE Zugriff auf `diversity.phase` (echtes
    Diversity-Objekt statt MagicMock)
  - T3: `ControlPanel` hat KEIN `cycle_bar`-Attribut mehr (Bug-Schutz
    gegen Wiedereinbau)
  - T4: `main_window._slot_progress_bar` Style enthält `#FFAA00` für
    Odd (Color-Sanity)
  - T5: `update_cycle_bar`-Methode existiert nicht mehr in
    `ControlPanel` (grep auf hasattr)

### Backup

- **AC9:** `Appsicherungen/2026-05-14_v0.97.22_vor_bundle_f/` mit allen
  geänderten Dateien (`core/omni_cq.py`, `ui/control_panel.py`,
  `ui/main_window.py`, `ui/mw_cycle.py`, plus die 4 Test-Files +
  test_bundle_d.py).

### Atomare Commits

- **AC10 (C1):** `core/omni_cq.py` — Phase-Check raus (AC1)
- **AC11 (C2 = ehemals C2+C5):** Tests — Mock-Setters + T5 raus +
  test_bundle_f.py NEU + test_bundle_d.py Farb-Update (AC2 + AC7 + AC8)
- **AC12 (C3):** `ui/control_panel.py` + `ui/mw_cycle.py` — cycle_bar
  weg + ggf. Spacing-Fix (AC3 + AC4 + AC5)
- **AC13 (C4):** `ui/main_window.py` — Magenta → Orange + Doku
  konsistent (AC6)
- **AC14 (C5):** `main.py` APP_VERSION → 0.97.23
- **AC15 (C6):** HISTORY.md + HANDOFF.md + CLAUDE.md-Header +
  Memory-Lesson-Ergänzung (`feedback_test_critical_path_not_mock.md`)
  + MEMORY.md-Eintrag

### Field-Test (Mike)

- **AC16 Field-Test F1-F6:**

| # | Test | Erwartung |
|---|---|---|
| F1 | Diversity Std/DX, OMNI-Button klicken | **OMNI sendet sofort** (CQ-Zeile im QSO-Panel, Counter ↻10) |
| F2 | OMNI laufen lassen 5+ Min | Counter ↻9 ↻8 ↻7 ..., Paritäts-Flip nach 10 Slots, Audio-Freq sticky |
| F3 | QSO-Kachel STATUS-Block | **Kein „████░░░░ 8s"-Balken** mehr |
| F4 | Statusbar unten rechts | Kleiner 80×14 Balken, wechselt **Cyan → Orange** beim Slot |
| F5 (NEU) | OMNI aktiv, Anrufer kommt rein (QSO startet) | OMNI pausiert, nach QSO-Ende OMNI resumed, sendet wieder |
| F6 (NEU, R1-SOLLTE-2) | Layout-Check STATUS-Block | „Status: IDLE | DT" und Trennlinie darunter wirken nicht gedrängt |

## Test-Bilanz

- Vor Bundle F: **1179 grün**
- T5 in `test_omni_cq_signal.py` raus: **−1 → 1178**
- T-Mocks in 4 Files raus (selbst keine Test-Functions, nur Setup):
  **±0**
- 5 neue Tests in `test_bundle_f.py`: **+5 → 1183**
- Erwartung: **~1183 grün**

## Risiken

- **R1:** Test-Mocks-Cleanup könnte versteckte Test-Abhängigkeit treffen
  (Mock-Diversity-Objekt wird in anderen Tests reused). **Mitigation:**
  Tests komplett durchlaufen nach jedem Commit.
- **R2:** Layout-Side-Effects nach cycle_bar weg (R1-SOLLTE-2).
  **Mitigation:** AC5 empirischer Test + Spacing-Anpassung wenn nötig.
- **R3:** Mike könnte „Orange" anders interpretieren als `#FFAA00`.
  **Mitigation:** R1 bestätigt Standard, Mike kann nachregen wenn er
  visuell anderen Ton will (5-Min-Fix).

## Memory-Lesson-Ergänzung

`feedback_test_critical_path_not_mock.md` ergänzen:

```
## Bundle F — OMNI Phase-Check (14.05.2026, v0.97.22→v0.97.23)

P34-Stufe2 (13.05.) entfernte `phase` aus `DiversityController`.
`core/omni_cq.py:232` greift weiter darauf zu → AttributeError im
Qt-Slot, silently → OMNI sendet nie. 1 Tag latent weil 4 Test-Files
`diversity.phase = "operate"` als MagicMock-Attribut setzen.

**Checkliste bei Partial-Fix (z.B. Pipeline-Abriss):**
1. `grep -rn "<entfernter Name>" --include="*.py"` über GESAMTES Repo
2. Tests die `<entfernter Name>` mocken → Mock muss WEG, nicht „dann
   passiert es im Test nicht"
3. Bug-Schutz-Test schreiben: das Attribut darf NICHT existieren
   (sonst Re-Einführung führt zu erneutem stillen Bruch)
4. Bei Qt-Slots VOR-Lauf via echtes Objekt testen — MagicMock
   schluckt AttributeError nicht (gibt Sub-Mock zurück), echter Code
   raised.
```

## V3 Compact-Sicherung

Files die für Cold-Start gelesen werden müssen:
- `prompts/bundle_f_v3.md` (dieses File)
- `prompts/bundle_f_v2.md`
- `prompts/bundle_f_v1.md`
- `prompts/bundle_f_r1_prompt.md` + R1-Antwort (Inhalt in Memory)
- `CLAUDE.md` (Workflow-Pflicht)
- `HANDOFF.md` (aktueller Stand v0.97.22)

Jeder Attribut-Verweis in V3 ist gegen Code geprüft:
- `omni_cq.py:231-233` Phase-Check (verifiziert)
- `control_panel.py:1150-1156` cycle_bar Def (verifiziert)
- `control_panel.py:1336` cycle_bar Alias (verifiziert)
- `control_panel.py:1947-1957` update_cycle_bar (verifiziert)
- `mw_cycle.py:519` Caller (verifiziert)
- `main_window.py:486,495,500,1253,1269` Magenta-Stellen (verifiziert)
- `test_bundle_d.py:212` Magenta-Assertion (verifiziert)
- `_gain_measure_locked` ausschließlich in `ui/mw_radio.py` —
  R1-Halluzination bestätigt, SOLLTE-1 abgelehnt.
