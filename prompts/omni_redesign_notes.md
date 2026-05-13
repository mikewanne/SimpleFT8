# OMNI-CQ Redesign — Notizen vor Compact #1

**Datum:** 2026-05-09
**Status:** Vorbereitung für V1 (post-Compact)
**Git-Sicherung:** Tag `pre-omni-redesign` (gesetzt vor allen Änderungen)
**Ausgangslage:** v0.95.22 P1.OMNI-START — Tests 1014 grün, OMNI-Bug aber latent

---

## 1. Bug-Kontext

**Symptom (Mike-Field-Test 09.05.2026):** Klick auf btn_omni_cq → CQ wird auf
Even gesendet → sofort kommt eine Antwort auf Odd. Das hätte nicht passieren
dürfen, weil der Odd-Slot bei OMNI eine zweite TX (CQ auf Odd) sein soll —
nicht ein RX-Slot.

**Root Cause verifiziert:** `core/qso_state.py:177` — `_send_cq()` setzt
State auf `CQ_CALLING` BEVOR `send_message.emit()`. Wenn OMNI im Filter
`ui/mw_qso.py:_on_send_message` entscheidet "RX-Slot, nicht senden" und
früh returned, wird `on_message_sent()` nie aufgerufen → State bleibt in
`CQ_CALLING` → `on_cycle_end()` triggert nicht mehr (braucht `CQ_WAIT`)
→ OMNI-Loop tot nach 2 TX-Slots.

**Mike-Beschluss (09.05.2026):** Voller Refactor, kein Pflaster. Inkl.
Vereinfachung von `core/omni_tx.py` (block_cycles=80 raus).

---

## 2. Mike's korrektes OMNI-Pattern

```
Block 1: Even-TX, Odd-TX, Even-RX, Odd-RX, Even-RX
Block 2: Odd-TX,  Even-TX, Odd-RX,  Even-RX, Odd-RX
```

**Beachte:** Pattern wiederholt sich nicht innerhalb eines Blocks. Beide
Blocks zusammen ergeben die symmetrische Verteilung.

**Block-Switch:** Automatisch wenn `_slot_index` von 4 → 0 rollt (nach
jedem abgeschlossenen 5-Slot-Durchlauf). Continuous: Block 1 → Block 2 →
Block 1 → Block 2 → ...

**KEIN 80-Zyklen-Zähler.** `block_cycles` war Überrest aus alter
Diversity-`OPERATE_CYCLES` (vor v0.93). Hat in OMNI nie gehört. Raus.

---

## 3. OMNI-Verhalten

### 3.1 Beim User-Klick (OMNI-Activate)

**"Kein Slot verschwenden"-Logik:**
- Nächster Slot ist Even → start Block 1 (Pos 0=Even-TX)
- Nächster Slot ist Odd → start Block 2 (Pos 0=Odd-TX)

Erster CQ geht im allerersten verfügbaren Slot raus, nicht erst im
übernächsten.

### 3.2 Wenn Antwort kommt (im RX-Slot)

- QSO-Subroutine übernimmt (shared mit Normal-CQ, Hunt, Manual)
- OMNI pausiert: `_slot_index` wird eingefroren
- QSO läuft normal: Report → RR73 → 73 → Log

### 3.3 Nach QSO-Ende

- OMNI restart mit gleicher "kein Slot verschwenden"-Logik:
  - QSO endete auf Even-TX → next slot Odd → Block 2 (Odd-first)
  - QSO endete auf Odd-TX → next slot Even → Block 1 (Even-first)

### 3.4 Stop-Conditions (unverändert von v0.95.22)

- User-Klick auf btn_omni_cq (Toggle)
- HALT (im mw_qso `_on_cancel`)
- Mode-Wechsel (FT8/FT4/FT2)
- Band-Wechsel

---

## 4. 4-Sequencer-Architektur (Mike-Designentscheidung)

| Sequencer | Trigger | Was tut er |
|---|---|---|
| Plan A: Normal-CQ | btn_cq aktiv | CQ + erste Antwort beantworten |
| Plan B: OMNI-CQ | btn_omni_cq aktiv | CQ alternierend Even/Odd nach Pattern |
| Plan C: Auto-Hunt | btn_auto_hunt aktiv | Stationen suchen, anrufen |
| Plan D: Manual | User klickt Station | Direkt anrufen |

**Gemeinsam:** Shared QSO-Subroutine — Report → RR73 → 73 → Log.

**Wechsel zwischen Sequencern:**
- **Sofort** wenn KEIN QSO läuft
- **Pending** (nach QSO-Ende) wenn QSO läuft
- **Nur HALT** unterbricht ein laufendes QSO

**Nach QSO-Ende kehrt Steuerung zum auslösenden Sequencer zurück:**
OMNI → wieder OMNI, Hunt → wieder Hunt, etc.

---

## 5. Was raus muss aus dem Code

### `core/omni_tx.py`
- `block_cycles` Parameter + Default 80 → komplett raus
- `_cycle_count` Attribut → raus
- `_pending_switch` Mechanik → vereinfacht oder raus
- `advance()` vereinfacht: `_slot_index = (_slot_index + 1) % 5`,
  wenn slot_index zurück auf 0 → block toggle. Fertig.
- `qso_active` Parameter raus aus `advance()` (Pause-Logik kommt von außen)
- Singleton-Inkonsistenz `get_instance(block_cycles=40)` vs Default 80
  → wird durch Refactor beseitigt
- Neue Methode: `pause()` / `resume()` für QSO-Phase
- Neue Methode: `start_with_parity_for_next_slot(next_is_even: bool)` —
  wählt Block 1 oder 2 basierend auf nächster Slot-Parität

### `core/qso_state.py`
- Root Cause: `_send_cq()` Z.177 → State erst NACH `send_message.emit()`
- Trade-off: Option A (auto_cq_enabled-Flag) vs Option B (Root Cause heilen)
  → siehe §7

### `ui/mw_cycle.py:585-592`
- OMNI-Slot-Treiber NEU: nach Decoder-Cycle, **VOR** `advance()` —
  `should_tx()` prüfen, dann advance() (R1-BUG-1 verifiziert: advance
  inkrementiert sofort, danach wäre slot_index falsch)
- Reihenfolge: should_tx() → Entscheidung → advance() → slot_index weiter

### `ui/main_window.py:_on_btn_omni_cq_toggled`
- Block-Wahl per "kein Slot verschwenden"-Logik einfügen
- `_on_omni_stopped` → reset Flags

### `ui/mw_qso.py`
- `_on_send_message`: OMNI-Filter vereinfachen (R1-IMPROVEMENT)
- `_on_qso_complete`: nach QSO OMNI mit korrekter Parität wieder anwerfen

---

## 6. R1-Findings (1. Lauf, vollständig erhalten in `/tmp/r1_result.txt`)

### ✅ ANNEHMEN
- **BUG-1**: `should_tx()` muss VOR `advance()` aufgerufen werden
  (advance inkrementiert _slot_index sofort, würde sonst nächsten Slot prüfen)
- **BUG-2**: AC7 ("Block-Wechsel nach 80 Zyklen korrekt") raus — sowieso
  jetzt komplett anders (Auto-Switch jeden 5-Slot-Durchlauf)
- **RISK-3**: omni_drive_cq() Guard `if not self.cq_mode: ...`
- **HINT-2**: `_omni_target_even` muss erst NACH `_pending_reply`-Branch
  gesetzt werden (sonst hängt das Attribut bei early-return)

### ❌ ABLEHNEN
- **RISK-2** (Sequenzgrafik): Doku-Kommentar reicht
- **IMPROVEMENT-1** (start_cq mit target_even): Mike will klare Trennung
  der 4 Sequencer, omni_drive_cq() bleibt eigene Methode
- **HINT-1** (Files-Größe): war bewusst

### ✅ DESIGN-ENTSCHEIDUNG (Mike, 09.05.2026): **Option B**
- **RISK-1 ACCEPTED**: Root Cause direkt heilen — `_send_cq()` setzt State
  erst NACH `send_message.emit()`.
- Begründung: heilt die Wurzel, eliminiert das `auto_cq_enabled`-Flag,
  `_resume_cq_if_needed` funktioniert unverändert weiter, weniger Code.
- **Folge:** BUG-3 (R1 2. Lauf — `_resume_cq_if_needed` Konflikt mit Flag)
  entfällt automatisch, da kein Flag eingeführt wird.
- **Konkrete Code-Änderung:** in `_send_cq()` (qso_state.py:164-178)
  Reihenfolge umkehren: erst `send_message.emit(msg)`, DANN
  `_set_state(QSOState.CQ_CALLING)`. ⚠️ Race-Check Pflicht in V1: was
  passiert wenn der Listener von `send_message` synchron auf den State
  zugreift? Falls ja, Defense-in-Depth überlegen.

---

## 7. R1-Findings (2. Lauf, truncated in `/tmp/r1_omni.txt`, nur 1051 Bytes)

### ✅ BUG-3 ECHT
- `_resume_cq_if_needed` (Z.392-408 in qso_state.py) → ruft `_send_cq()` auf
- Wenn Option A gewählt wird: muss bei aktivem OMNI entweder
  `auto_cq_enabled` temporär setzen oder direkt OMNI-Treiber triggern
- Wenn Option B gewählt wird: Problem entfällt automatisch

### ⚠️ Truncation-Warnung
- 2. R1-Lauf war truncated nach Zeile 8 (`out=8000` Tokens, aber nur ~1000
  Zeichen gespeichert). Möglicherweise weitere Findings unbekannt.
- **Mitigation:** Bei nächstem R1 (V2-Review nach Compact) komplett neu
  reviewen lassen — saubere Bewertung des V3-Designs

---

## 8. Architektur-Skizze (für V1)

```
                    ┌─────────────────────────┐
                    │ User-Aktion oder Event   │
                    └──────────┬───────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌────────────────┐          ┌────────────────┐
        │ Sequencer-Wahl │          │ HALT (immer)   │
        └───────┬────────┘          └────────────────┘
                │
        ┌───────┴───────┬───────────┬───────────┐
        ▼               ▼           ▼           ▼
    ┌───────┐      ┌────────┐  ┌────────┐  ┌────────┐
    │Plan A │      │Plan B  │  │Plan C  │  │Plan D  │
    │NormCQ │      │OMNI-CQ │  │AutoHunt│  │Manual  │
    └───┬───┘      └───┬────┘  └───┬────┘  └───┬────┘
        │              │           │           │
        └──────────────┴───────────┴───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ Shared QSO Subroutine│
            │ Report→RR73→73→Log   │
            └──────────────────────┘
```

---

## 9. Files-Anhänge an DeepSeek (für V1)

- `core/omni_tx.py` (komplett, ~250 Zeilen)
- `core/qso_state.py` (komplett, ~700 Zeilen)
- `ui/main_window.py` (Auszug: btn_omni_cq, _on_btn_omni_cq_toggled,
  _on_omni_stopped, ~200 Zeilen)
- `ui/mw_qso.py` (Auszug: _on_send_message, _on_station_clicked,
  _on_qso_complete, ~300 Zeilen)
- `ui/mw_cycle.py` (Auszug: _on_cycle_start, _on_cycle_decoded, ~150 Zeilen)

**Wichtig:** ALLE Files vollständig anhängen, nicht nur Auszüge — verhindert
R1-Halluzinationen über fehlende Symbole (Lesson aus mehreren früheren
Reviews).

---

## 10. Test-Strategie (für V1 Akzeptanzkriterien)

Mindestens diese Tests:
1. OMNI-Activate Even-Slot → Block 1
2. OMNI-Activate Odd-Slot → Block 2
3. Pattern-Verlauf 10 Slots: E-TX, O-TX, E-RX, O-RX, E-RX,
   O-TX, E-TX, O-RX, E-RX, O-RX
4. QSO startet in Pos 2 → OMNI pausiert (slot_index frozen)
5. QSO endet Even-TX → OMNI startet Block 2 (Odd-first)
6. QSO endet Odd-TX → OMNI startet Block 1 (Even-first)
7. HALT während OMNI → IDLE, beide Flags clear
8. Mode-Wechsel → OMNI stoppt
9. Band-Wechsel → OMNI stoppt
10. Resume nach Cancel: OMNI wieder mit korrekter Parität

---

## 11. Akzeptanzkriterien (Field-Test, Mike-Bestätigung nötig)

- OMNI activate → erster CQ sofort im nächsten Slot, korrekte Parität
- 5-Slot-Pattern korrekt durchlaufen: 2 TX, 3 RX
- Antwort in RX-Slot → QSO startet, normal abgewickelt
- Nach QSO → OMNI resume, kein Slot verschwendet
- Block-Wechsel automatisch jeder 5er-Cycle
- Statusbar zeigt Even/Odd-Counter und aktiven Block

---

## 12. Was Mike NICHT will (explizite Anti-Liste)

- Quick-Fixes oder Pflaster
- Brüche im laufenden QSO (nur HALT darf unterbrechen)
- Mehrere Code-Pfade die das gleiche tun (KISS, klare Trennung der 4
  Sequencer mit shared subroutine)
- Slot-Verschwendung
- Beibehalten von block_cycles=80 (alter Diversity-Überrest)

---

## 13. Nächste Schritte (post-Compact)

**Stand 09.05.2026 nach Compact #1:**
- ✅ V1 geschrieben: `prompts/p2_omni_redesign_v1.md`
- ✅ V2 (Self-Review) geschrieben: `prompts/p2_omni_redesign_v2.md`
- ✅ **L1 KRITISCH:** Race-Check-Lücke entdeckt — naive Vertauschung in
  `_send_cq()` fixt Bug NICHT (Qt.DirectConnection bei gleichem Thread →
  emit() synchron → _set_state läuft trotzdem). **V2-Lösung: Flag-Pattern
  `_omni_skip_state_change`** — Listener setzt Flag bei RX-Skip, `_send_cq`
  checkt nach emit. KISS, Race-frei.
- ✅ V2 komplett: 15 Lessons L1-L15, 14 ACs, 19 Tests, V1→V2 Diff-Tabelle
- ⏳ **JETZT Compact #2** vor R1-Review (R1-Antworten ~10-30 KB würden
  Kontext fluten)

**Nach Compact #2 — Trigger „weiter mit OMNI-Redesign R1":**
1. V2 lesen (`prompts/p2_omni_redesign_v2.md`) — Source für R1-Prompt
2. R1-Review starten: `cat prompts/p2_omni_redesign_v2.md | ./venv/bin/python3 tools/deepseek_review.py core/omni_tx.py core/qso_state.py core/timing.py core/encoder.py ui/main_window.py ui/mw_qso.py ui/mw_cycle.py > /tmp/r1_omni_v2.txt`
3. R1-Findings prüfen (kritisch — auch R1 halluziniert)
4. V3 schreiben (Compact-fest, Mike-bezogene Präzisierungen)
5. Mike-Freigabe V3
6. Compact #3 (vor Implementation)
7. Implementation mit atomaren Commits
8. Final-R1-Code-Review
9. Field-Test mit Mike

---

## 14. Mike-Zitate (für Kontext bei späterem Re-Review)

- „ich mache doch jetzt kein pflaster" → voller Refactor, kein Quick-Fix
- „wir messen nichts mehr nach 80 zyclen" → block_cycles ist Diversity-Überrest
- „wir verlieren keinen slot" → Block-Wahl-Logik bei Activate + nach QSO
- „nur HALT darf unterbrechen" → QSO ist heilig
- „4 Sequencer + 1 shared QSO-Subroutine" → klare Architektur

