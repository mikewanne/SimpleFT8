# CQ-Reply-Bug Fix — Implementations-Plan V3 (final)

**Status:** V3 = V2 + R1-Bestaetigung. R1 (DeepSeek-Reasoner) hat alle
4 Pruefauftraege freigegeben, keine Korrekturen, kein Delta.

V3 verweist auf V2 (cq_reply_fix_plan_v2.md) als verbindlichen Plan-Inhalt.

---

## R1-Review-Ergebnis (2026-05-05)

| Pruefauftrag | R1-Befund |
|---|---|
| Test 4 (resume_pops_known_station) Korrektheit | ✓ Freigegeben |
| Reihenfolge `_resume_cq_if_needed` | ✓ Freigegeben |
| Memory-Lesson-Formulierung | ✓ Freigegeben (cross-Projekt-gueltig) |
| Versions-Bump v0.95.1 → v0.95.2 | ✓ Freigegeben |

R1 bestaetigt zusaetzlich:
- Test-Count-Rechnung 759 korrekt
- Debug-Linien `DBGLOOP|DBGTX` nicht im Code (0 Treffer) — kein Cleanup
- `is_73`/`is_rr73`-Check Z. 196-199 und `cq_mode`-Check Z. 186-188
  bleiben korrekt unangetastet
- `_dbg.log` ist legitimes QSO-Logging, keine Debug-Linie — bleibt

**„Plan-V2 ist vollstaendig und implementierungsreif. Keine Korrekturen
erforderlich."** (R1-Wortlaut)

---

## Verbindlicher Plan-Inhalt

→ siehe `prompts/cq_reply_fix_plan_v2.md`

Atomare Commits:
1. `core: remove 5-min worked-recently lockout (P1.5 fix)`
2. `docs: P1.5 CQ-Reply-Bug fix dokumentation`

7 Loesch-Stellen in `core/qso_state.py`, 1 Test invertiert + 3 neue
Tests, 7 Doku-Files. Test-Count 756 → 759.

---

**V3 final. Mike-Freigabe (Option A) liegt vor. Code-Implementation
beginnt.**
