# P4.OMNI-NEUBAU — Final-R1 Review

## Rolle

Du bist **DeepSeek-Reasoner (R1)**. Du reviewst **V3 (Compact-fest)** für
den OMNI-CQ-Architektur-Refactor in SimpleFT8.

## Vorgeschichte

V1 → V2 (Self-Review, 20 Lessons) → R1 (du, erste Runde, 17/20 ✅
bestätigt + 5 neue Findings R1-R5) → **V3 (vorliegend, alle Findings
eingearbeitet)**.

Diese Final-Runde prüft V3 auf **Implementierungsreife**. Es ist die
letzte Hürde vor Compact + Code-Phase.

## Was du wissen musst

**R1-Findings die in V3 angeblich adressiert sind:**

| ID | Finding | V3-Adressierung |
|---|---|---|
| R1 | `_OMNI_TX_PRELEAD_S=1.5s` zu knapp (0.2s Marge) | AC-R1: 2.0s (0.7s Marge) |
| R2 | Listener fehlt `encoder.tx_even` vor `start_qso` | AC-R2: `mw_cycle.on_message_decoded` setzt `not msg._tx_even` analog Hunt-Klick mw_qso:171-176 |
| R3 | `resume_after_qso` ohne Worker-Join | AC-R3: joint alten Worker vor `start()` |
| R4 | `_omni_was_active_pre_qso` nicht reset bei Stop | AC-R4: `_on_omni_stopped` setzt explizit False |
| R5 | 2 Antworten in 1 RX-Slot — zweite ignoriert | AC-R5: dokumentiert (akzeptabel) |

**V2-Lessons L1-L20:** alle in V3 §2/§3/§4 verbaut.

## Was ich von dir will

### A — V3 Implementierungsreife

Geh durch V3 §3 (Schnittstellen-Diffs):
- §3.1 `core/encoder.py` atomare `transmit`-API
- §3.2 `core/qso_state.py` Rückbau
- §3.3 `ui/main_window.py` OMNI-Init + Toggle + Stop-Trigger
- §3.4 `ui/mw_qso.py` Pause/Resume + HALT
- §3.5 `ui/mw_cycle.py` Listener-Pfad + Pretrigger raus
- §3.6 OMNI-RX-Slot „Horche..."

**Pro Section:** sind die Diffs konkret genug zum Coden? Fehlt was?
Gibt es Code-Pfade/Branches die V3 übersieht?

### B — Adressierungs-Verifikation R1-R5

Wurden meine eigenen Findings R1-R5 sauber adressiert?
- **R1 (PRELEAD 2.0s):** in §2.1 Konstante + §2.2 Worker-Loop verbaut. ✓?
- **R2 (encoder.tx_even im Listener):** §3.5 mw_cycle.on_message_decoded
  setzt `encoder.tx_even = not their_even` vor `start_qso`. ✓?
  **Kritisch:** funktioniert das mit `msg._tx_even`-Attribut? Ist das
  garantiert gesetzt am `FT8Message`?
- **R3 (resume joint Worker):** §2.5 `resume_after_qso` joint + setzt
  `_running=False` für sauberen `start()`. ✓?
- **R4 (Stop reset Flag):** §3.3 `_on_omni_stopped` setzt
  `_omni_was_active_pre_qso=False`. ✓?
- **R5:** AC-R5 dokumentiert. ✓?

### C — Neue Race-Conditions die V3 einführen könnte

V3 macht Code-Änderungen — könnten neue Races entstehen?
- Listener-Pfad in `mw_cycle.on_message_decoded` setzt `encoder.tx_even`
  und ruft danach `qso_state.start_qso(...)`. Ist das sicher?
- `_pause_omni_if_active` + Listener-Pfad: wenn beide gleichzeitig
  laufen — Race auf `_omni_was_active_pre_qso`?
- `_maybe_resume_omni` Caller-Queue-Pop-Pfad: setzt `encoder.tx_even`
  und ruft `start_qso` — Race mit Encoder-Worker?

### D — Test-Plan-Vollständigkeit (V3 §5)

20 Unit + 14 Integration = 34 Tests neu, 81 alt raus → netto ~1017.
- Decken die Tests AC-R1 bis AC-R5 ab?
- Race-Tests genug? (T20 `test_resume_joins_old_worker` — reicht das?)
- Edge-Case-Tests fehlen?

### E — Commit-Reihenfolge V3 §9

8 Commits:
- C1: alte Tests RAUS
- C2: NEU `core/omni_cq.py` + Unit-Tests
- C3: atomare `encoder.transmit`
- C4: Rückbau `qso_state.py`
- C5: Rückbau `mw_cycle.py`
- C6: Anschluss `main_window` + `mw_qso` + Listener + 14 Integration-Tests
- C7: Stop-Trigger `mw_radio`
- C8: `omni_tx.py` löschen + APP_VERSION + Doku

**Bleiben Tests nach JEDEM Commit grün?**
- Nach C1: weniger Tests, alle alten Tests die OMNI nutzen sind weg → keine Brokens?
- Nach C2: neues Modul + 20 Unit-Tests grün, aber NIEMAND ruft es auf → werden trotzdem alle existing tests grün?
- Nach C3: encoder API erweitert (kwargs), backward-compat → grün?
- Nach C4: qso_state Reste raus — gibt es noch tests die `_omni_skip_state_change` referenzieren?

### F — KISS-Bewertung

V3 hat 23 ACs, 34 Tests, 8 Commits. Für ein Hobby-Tool noch im Rahmen
oder schon overengineered? Wo könnte man weiter vereinfachen?

## Format

Strukturiert nach A/B/C/D/E/F. Pro V3-Sektion eine Bewertung.

**Zum Schluss:**
- ✅ „V3 ist implementierungsreif. Compact + Code freigegeben"
- 🟡 „V3 braucht kleine Anpassungen vor Compact (Liste folgt)"
- ⛔ „V3 hat kritische Lücken — V4 nötig"

Antworte ausführlich aber präzise (200-400 Zeilen ist OK).
