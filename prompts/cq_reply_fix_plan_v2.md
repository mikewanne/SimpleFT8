# CQ-Reply-Bug Fix — Implementations-Plan V2 (Self-Review von V1)

**Status:** V2 = Self-Review. V1 hatte 7 Loesch-Stellen, 3 Tests, 2
atomare Commits. V2 ergaenzt: 4. Test fuer Caller-Queue-Pop-Pfad
(R1 hatte das in Diagnose-V3 Punkt 8 angesprochen), Memory-Inhalt
konkret, Debug-Linien-Status (geprueft: nicht mehr im Code).

---

## 1. Strategie (unveraendert)

- 7 Stellen + Hilfsmechanik komplett entfernen (Mike Option A)
- 1 existing Test invertieren + **3** neue Tests (V1 hatte 2 — Self-
  Review identifiziert 4. Test fuer Caller-Queue-Pop)
- 2 atomare Commits — Code+Tests, dann Doku

Version-Bump: v0.95.1 → **v0.95.2** (Bugfix-Patch).

---

## 2. Atomare Commits (unveraendert)

- Commit 1: `core: remove 5-min worked-recently lockout (P1.5 fix)`
  → qso_state.py + test_modules.py + main.py
- Commit 2: `docs: P1.5 CQ-Reply-Bug fix dokumentation`
  → HISTORY + HANDOFF×2 + CLAUDE×2 + TODO + Memory

**Reihenfolge-Begruendung (V2-Schaerfung):** Code+Tests zusammen ist
zwingend. Wenn man Tests separat machen wuerde:
- Vor Commit 1: bestehender `test_qso_worked_recently_block` ist gruen
- Nach Commit 1 (Code allein): bestehender Test ist ROT (testet aktiv
  die geloeschte Sperre)
- Bisecting wuerde Commit 1 als „rot" identifizieren und Commit 2 muesste
  sofort folgen
- → atomar = einer Schritt = ein Commit. Tests gehoeren zur Code-
  Aenderung.

---

## 3. Code-Diffs Commit 1 (unveraendert von V1, Stellen verifiziert)

V1 hatte alle 7 Stellen korrekt:

| # | qso_state.py | Was |
|---|---|---|
| 1 | Z. 119 | `_worked_calls: dict = {}` loeschen |
| 2 | Z. 120 | `_WORKED_BLOCK_SECS = 300` loeschen |
| 3 | Z. 168-176 | Methode `_is_worked_recently` loeschen |
| 4 | Z. 190-193 | Block #2 in `_process_cq_reply` loeschen |
| 5 | Z. 440-443 | TX_RR73 Eintrag-Stelle loeschen |
| 6 | Z. 470 | Block #3 in Caller-Queue-Add loeschen |
| 7 | Z. 479-482 | Block #1 in Hauptpfad loeschen |

**Diff-Summe:** -22 Zeilen, +0 Zeilen Code.

**main.py:** APP_VERSION 0.95.1 → 0.95.2.

**NICHT betroffen** (bleibt unangetastet):
- `is_73 || is_rr73`-Check in `_process_cq_reply` Z. 196-199 (ignoriert
  CQ-Antworten die RR73/73 sind, nicht Grid/Report — andere Logik)
- `cq_mode`-Check in `_process_cq_reply` Z. 186-188 (HALT-Schutz)
- Caller-Queue selbst (Z. 121, Append-Logik, Pop-Logik) — wird
  nicht entfernt, nur der Block #3 darin

---

## 4. Test-Anpassungen Commit 1 (V2: 4 Tests statt 3)

### Test 1 — `test_qso_worked_recently_block` invertieren

(unveraendert von V1: → `test_qso_known_station_can_call_again`)

### Test 2 — NEU: `test_qso_cq_reply_during_tx_pending_then_processed`

(unveraendert von V1)

### Test 3 — NEU: `test_qso_caller_queue_accepts_known_station`

(unveraendert von V1)

### Test 4 — NEU (V2): `test_qso_resume_pops_known_station_from_queue`

R1 hatte in Diagnose-V3 Punkt 8 angesprochen: Caller-Queue-Pop verlaeuft
durch `_resume_cq_if_needed` (qso_state.py:368-385) → Pop +
`_pending_reply = next_msg` + `_process_cq_reply()`. Block #2
(qso_state.py:191-193) war hier die zweite Verteidigungslinie. Nach
Fix muss bekannte Station aus Queue verarbeitet werden.

```python
def test_qso_resume_pops_known_station_from_queue():
    """_resume_cq_if_needed verarbeitet bekannte Station aus Caller-Queue.

    Vor Fix: Block #2 in _process_cq_reply blockierte den Pop-Pfad doppelt
    (zusaetzlich zu Block #3 beim Add). Nach Fix: kein Block mehr — Station
    aus Queue wird beantwortet.
    """
    from core.qso_state import QSOStateMachine, QSOState, QSOData
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._was_cq = True
    sm.qso = QSOData()  # leer

    # R3EDI war frueher gearbeitet — vor Fix waere Block #2 gegriffen
    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI KO82",
                     grid_or_report="KO82", is_grid=True)
    sm._caller_queue.append(msg)

    sent = []
    sm.send_message.connect(lambda m: sent.append(m))

    # _resume_cq_if_needed simuliert QSO-Ende mit nicht-leerer Queue
    sm._resume_cq_if_needed()

    # R3EDI muss verarbeitet sein → state=TX_REPORT
    assert sm.state == QSOState.TX_REPORT
    assert any("R3EDI" in s and "DA1MHH" in s for s in sent)
    assert len(sm._caller_queue) == 0  # Pop hat geleert
```

**Test-Count-Erwartung:** 756 - 1 (geloescht) + 1 (invertiert) + 3 (neu) = **759**.

V1 sagte 758 — Korrektur in V2: **759**.

---

## 5. Doku-Updates Commit 2

### 5.1 HISTORY.md (V1-Eintrag mit V2-Korrekturen)

Test-Count 758 → **759**. „2 neue Tests" → „3 neue Tests".

```markdown
**Tests:**
- `test_qso_worked_recently_block` invertiert →
  `test_qso_known_station_can_call_again`
- NEU: `test_qso_cq_reply_during_tx_pending_then_processed`
- NEU: `test_qso_caller_queue_accepts_known_station`
- NEU: `test_qso_resume_pops_known_station_from_queue`
- 756 → 759 gruen
```

Sonst HISTORY-Eintrag unveraendert von V1.

### 5.2 HANDOFF.md (beide Pfade) — unveraendert

### 5.3 CLAUDE.md (beide Pfade) — V2 Schaerfung

V1 fragte R1 ob langer „Stand"-Block-Eintrag analog v0.95.1 noetig ist.
**V2 entscheidet:** ja, kurzer **v0.95.2-Block** vor v0.95.1-Block:

```
**Aktueller Stand:** v0.95.2 (05.05.2026) — **CQ-Reply-Bug-Fix (P1.5).**
2 atomare Commits (Code+Tests, Doku). 5-Min-Sperre `_WORKED_BLOCK_SECS`
+ Methode `_is_worked_recently` + 3 Block-Stellen + Eintrag-Stelle in
`core/qso_state.py` komplett entfernt (-22 Zeilen, +0 Code). Bekannte
Stationen koennen wieder anrufen — Mike's Funker-Entscheidung-Linie.
Plus voller V1→V2→R1→V3 Diagnose + V1→V2→R1→V3 Plan, R1 bestaetigt
Hauptwurzel ohne Halluzinationen. **v0.95.1:** ...
```

Test-Count `756 passed` → `759 passed` global.

### 5.4 TODO.md (V2-Schaerfung)

V1 sagte „loeschen oder als ✅ markieren". V2 entscheidet konkret:

**Section „🔴 P1.5 CQ-Reply-Recognition-Bug" → komplett entfernen** aus
„ALS NAECHSTES". Optional: in einer „✅ Erledigt"-Section verlinken zu
HISTORY-Eintrag.

P1.7 (Duplikat-Filter) bleibt drin — bereits angelegt.

**Debug-Linien-Status (V2 neu):** grep nach `DBGLOOP|DBGTX` in core/
ergibt **0 Treffer** — sind bereits entfernt. Kein Cleanup-Schritt
noetig.

### 5.5 Memory `feedback_funker_entscheidung_filter_in_rx.md` (V2: konkreter Inhalt)

```markdown
---
name: Funker-Entscheidung — Filter im Anzeige-Pfad, nicht Verarbeitung
description: Bei Filter-Logik unterscheiden wo der Filter sitzt — Anzeige (RX-Panel) okay, Verarbeitungs-Pfad (State-Machine) verstoesst gegen Mike's Funker-Entscheidet-Philosophie. Aus P1.5-Diagnose 2026-05-05.
type: feedback
---

**Regel:** Wenn ein Feature Stationen / QSOs „filtern" oder „blockieren"
soll, gehoert die Logik in den **Anzeige-Pfad** (z.B. RX-Panel-Filter
„Neue Stationen"), nicht in die **State-Machine** / Verarbeitungs-
Logik.

**Why:** Mike's Hobby-Funker-Philosophie (CLAUDE.md „Projekt-
Philosophie"): „Funker entscheidet, App nicht." Stillschweigend
filternde State-Machine = „App weiss es besser"-Mechanik die Mike
ablehnt. Aus P1.5-Bugfix 2026-05-05 — `_WORKED_BLOCK_SECS = 300`
blockierte CQ-Replies an 3 Stellen, weil bekannte Stationen für 5
Min „gesperrt" waren. Mike's Position: bekannte Station ruft uns
explizit, hat meist einen Grund (kein 73 erhalten) — Funker
entscheidet manuell ob er antwortet.

**How to apply:**
- Bei neuen Filter-Features (z.B. Bandwide-Spotter, Locator-Filter,
  Distanz-Filter): **Anzeige-Filter** im RX-Panel, NICHT Verarbeitungs-
  Block in der State-Machine.
- Bei Bug-Diagnose: wenn die State-Machine still etwas ablehnt
  (`return` ohne State-Wechsel), pruefen ob das wirklich Funker-Wille
  ist oder Overengineering.
- Bei DeepSeek-Vorschlaegen die „intelligente" Filter vorschlagen:
  ablehnen wenn Anzeige-Filter ausreicht.

**Beispiele:**
- ✅ RX-Panel „Neue Stationen"-Filter (Mike-bestaetigt 2026-05-05)
- ✅ Country-Filter (Settings, beeinflusst Anzeige)
- ❌ `_WORKED_BLOCK_SECS` (war State-Machine-Block, raus in v0.95.2)
```

**MEMORY.md-Eintrag:**
```markdown
- [Funker-Entscheidung Filter im Anzeige-Pfad](feedback_funker_entscheidung_filter_in_rx.md) — Filter-Logik gehoert in RX-Panel-Anzeige, nicht in State-Machine. Aus P1.5-Bugfix 2026-05-05
```

### 5.6 prompts/cq_reply_bug_compact_notes.md

Kann nach Plan-Abschluss geloescht werden — war nur Compact-Backup vor
P1.5. **Optional, nicht kritisch.**

---

## 6. Verifikations-Schritte (V2-erweitert)

1. **Tests gruen:** `./venv/bin/python3 -m pytest tests/ -q` → **759 passed**
2. **Lint-Check (optional):** `./venv/bin/python3 -m ruff check core/qso_state.py` (falls ruff installiert)
3. **Import-Check:** `./venv/bin/python3 -c "from core.qso_state import QSOStateMachine"` → keine ImportError fuer geloeschte Methode
4. **App startet:** `./venv/bin/python3 main.py` (kurz testen, dann Ctrl+C)
5. **Field-Test post-Commit:** Mike testet DA1TST-Szenario nach Commit 1.
   - QSO 1 starten/abschliessen mit DA1TST
   - DA1TST nochmal anrufen lassen < 5 Min spaeter
   - App sollte mit Report antworten (vor Fix: ignoriert)

---

## 7. Risikoanalyse (V2 unveraendert)

V1's 6 Risiken vollstaendig. V2 bestaetigt.

Zusatz: was wenn Field-Test post-Commit das Symptom NICHT loest?
- Plan-Mode: zurueck zu Diagnose-V4 mit neuen Daten
- Sperre als Verursacher dann ausgeklammert (Mike's Worte) → nach
  zweiter Wurzel suchen (Race, Caller-Queue-Pfad, Decoder)

---

## 8. Auftrag an V3 / R1

V1 hatte 7 Pruefauftraege. V2 reduziert auf 4 zentrale (R1 hat schon
viel in Diagnose-V3 bestaetigt):

1. **Test 4 (V2-NEU) Korrektheit:** simuliert
   `test_qso_resume_pops_known_station_from_queue` den Pop-Pfad
   wirklich? Ist `sm.qso = QSOData()` setup korrekt? Oder muss
   `sm.qso.start_time` o.ae. gesetzt werden damit `_resume_cq_if_needed`
   nicht in einen anderen Branch geht?

2. **Reihenfolge `_resume_cq_if_needed`:** Z. 372 setzt
   `self.cq_mode = True` und `self.qso.timeout_cycles = 0`. Das modifiziert
   `qso` — wenn `qso` zuvor frisch ist (keine `their_call`), gibt es
   keinen Konflikt. Aber Test 4 sollte das verifizieren.

3. **Memory-Lesson-Formulierung:** beschreibt
   `feedback_funker_entscheidung_filter_in_rx.md` die Lesson korrekt
   und projekt-uebergreifend (auch fuer kuenftige Filter-Entscheidungen)?

4. **Versions-Bump v0.95.2:** Plan-V2 sagt JA (Bugfix-Patch). R1
   bestaetige oder widerlege.

KEINE neue Logik vorschlagen — nur Plan-Korrekturen.

---

## 9. Was V2 anders macht als V1

| Aspekt | V1 | V2 |
|---|---|---|
| Test-Anzahl | 3 (1 invertiert + 2 neu) | **4** (1 invertiert + 3 neu) |
| Test-Count Erwartung | 758 | **759** |
| Memory-Inhalt | Konzept-Hinweis | **Voller Memory-Text** |
| Debug-Linien-Status | „pruefen" | **gepreuft, nicht mehr im Code** |
| CLAUDE.md-Stand-Block | Frage an R1 | **Entscheidung: ja, v0.95.2-Block hinzufuegen** |
| Ungeloeschtes klargestellt | nein | **ja: is_73/is_rr73-Check Z. 196-199, cq_mode-Check Z. 186-188 bleiben** |

---

**V2 Ende. V3 = R1-Findings einarbeiten. Plan-Mode + Commits erst nach
Mike-Freigabe.**
