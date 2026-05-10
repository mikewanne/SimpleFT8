# HANDOFF — SimpleFT8

## Stand 2026-05-10 ~12:00 UTC: P7.OMNI-SIMPLIFY ERLEDIGT, Field-Test pending

**Code:** v0.96.4 lokal commited (C1-C6 + C7 Doku). 7 atomare Commits seit v0.96.3.
**Tests:** **1008 grün** (1024 → 1008, V3-Plan war ~1005).
**Final-R1:** „Push freigegeben" — 0 KRITISCH, 0 SOLLTE-FIX, 0 KOENNTE
(„minimalistisch und KISS-konform").
**Field-Test:** 8-Punkte-Plan V3 §6 F1-F8 ausstehend, Mike startet App selbst.
**App:** gestoppt. **Push pending** bis Mike-Freigabe nach Field-Test —
v0.95.16-0.96.4 + P2-Tool zusammen.

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
