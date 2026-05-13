# P4.OMNI-NEUBAU — R1 Review-Auftrag

## Rolle

Du bist **DeepSeek-Reasoner (R1)**. Du reviewst V1 + V2 (Self-Review) für
einen Architektur-Refactor des OMNI-CQ-Features in SimpleFT8 (Python /
PySide6 / FT8 Amateurfunk-App).

**Wichtig:** SimpleFT8 ist ein Hobby-Funker-Tool. KISS schlägt Eleganz.
Keine Contest-Tool-Features, keine Power-User-Optimierungen, keine
Multi-User-Sicherheit. Single-User-App auf Mac.

## Vorgeschichte (kurz)

OMNI-CQ ist ein Diversity-Feature: SimpleFT8 ruft CQ abwechselnd auf
beiden Slot-Paritäten (Even UND Odd) → 100% aller aktiven Operatoren
erreichbar (statt nur 50% wie Normal-CQ).

**4 Fehlversuche v0.95.22 - v0.95.25** haben OMNI in den
`qso_state.cq_mode`-Pfad reingehackt. Alle gescheitert weil:
- Slot-Pretrigger via cycle_tick / QTimer / Cycle-Tick-Fallback
  hängen am GUI-Thread, der während Decoder-Run blockiert
- Race-Conditions zwischen `cq_mode`-State, OMNI-Slot-Filter,
  Encoder-Worker und Decoder
- Pattern-Drift +30 s bei Mike-Field-Test v0.95.25

**Mike's Vision (verbindlich, Memory `project_omni_cq_spec.md`):**
- Eigenes Modul `core/omni_cq.py` — eigener Worker-Thread mit
  absolut-UTC-Slot-Boundaries (Vorbild: `core/encoder.py:_tx_worker`)
- KEIN cycle_tick, KEIN QTimer, KEIN GUI-Thread-Polling
- KEIN qso_state.cq_mode reuse
- Bei eingehender Antwort → Übergabe an gemeinsamen Hunt-Pfad
  (`qso_state.start_qso(...)` — gleicher Eingang wie Hunt-Klick)
- 5-Slot-Pattern: Block 1 (Even-First) TX-E TX-O RX-E RX-O RX-E /
  Block 2 (Odd-First) TX-O TX-E RX-O RX-E RX-O
- Block-Wechsel automatisch nach 5 Slots
- Nach QSO: QSO endet auf Even → Block 2, endet auf Odd → Block 1.
  IMMER ab Pos 0 (nie mittendrin)
- Audiofrequenz STICKY: bleibt frei → bleibt; bleibt während QSO;
  wechselt nur wenn voll. Recheck alle 4 Blöcke (~5 Min FT8)
- Stop-Bedingungen: manual_halt, band_change, mode_change,
  rx_mode_change, totmann_expired

## Was ich von dir will

V1 ist der erste Plan. V2 ist die Self-Review als „frische KI" mit
20 Lessons L1-L20 (8 als ⛔ kritisch/wichtig, 7 als OK, 5 als
nice-to-have). V2 hat schon mehrere V1-Halluzinationen gefunden
(Listener-Pfad, atomare Encoder-API, Caller-Queue-Race).

**Dein Auftrag:**

### A — Bestätige oder korrigiere V2-Lessons L1-L20

Geh durch jede V2-Lesson und sag:
- ✅ **BESTÄTIGT** wenn V2-Befund + V2-Korrektur korrekt sind
- ⚠️ **TEILWEISE** wenn Befund stimmt aber Korrektur unvollständig/falsch
- ❌ **VERWORFEN** wenn V2 halluziniert hat
  (mit Code-Beweis: Datei:Zeile)
- ➕ **ERGÄNZUNG** wenn V2 was übersieht

**Besonders kritisch prüfen:**
- L1 (Listener-Pfad in mw_cycle nicht mw_qso) — verifiziere mit Code
- L2 (atomare encoder.transmit-API) — verifiziere Race
- L3 (`_last_qso_tx_even` aus `_on_tx_finished`) — Edge-Case Timeout
- L9 (Auto-Hunt-Coupling) — wo lebt QButtonGroup, ist das genug?
- L10 (Caller-Queue bei OMNI) — kritisch, kann zu silent ignored QSOs führen
- L13 (`time.sleep` → `_stop_event.wait`) — cancelability-Bug
- L18 (Commit-Reihenfolge) — sicher dass das funktioniert?

### B — Race-Condition-Audit

**Worker-Thread-Lifecycle:**
- pause() + stop() gleichzeitig — Race?
- start() während laufendem Worker (idempotent) — Race?
- resume_after_qso() während Worker noch nicht ausgelaufen — Race?

**Cross-Thread-Datenaustausch:**
- `encoder.tx_even` Setter aus OMNI-Worker — Race mit Encoder-Worker?
  V2-L2 schlägt atomare API vor — reicht das? Welche anderen
  Encoder-Attribute (audio_freq_hz) sind betroffen?
- `_paused`-Flag-Read im Worker-Loop — RLock reicht?
- `_caller_queue`-Read in `_maybe_resume_omni` — von welchem Thread?

**Decoder-Encoder-Timing:**
- Worker schläft bis `boundary - 1.5s`, ruft `encoder.transmit()`
- Encoder eigener Worker schläft bis `boundary - 1.3s`, beginnt Encode
- Decoder ist ready bei `boundary - 0.5s` (FT8 _WAKE_OFFSETS=2.5s)
- Marge zwischen OMNI-Worker-Wake und Encoder-Wake: 0.2s
  → ist das robust genug? Was wenn OS scheduling delay 0.3s drauflegt?

### C — Architektur-Bewertung

- 3-Schichten-Architektur (Normal-CQ qso_state.cq_mode | OMNI-CQ omni_cq.py
  NEU | gemeinsamer QSO-Hunt-Pfad qso_state.start_qso) — sauber genug?
  Oder gibt es immer noch Coupling-Punkte die nicht offensichtlich sind?
- Listener-Pfad in `mw_cycle.on_message_decoded` (nicht `mw_qso`) — V2-L1
  korrigiert das. Ist die Reihenfolge korrekt: OMNI-Antwort-Check VOR
  `qso_sm.on_message_received(msg)`? Was passiert wenn beide gleichzeitig
  reagieren wollen?
- OMNI ruft `qso_state.start_qso(...)` direkt — gleicher Eingang wie
  Hunt-Klick. Heißt das: Hunt-State-Machine (WAIT_REPORT/WAIT_RR73/...)
  funktioniert ohne Änderung? Oder gibt es Code-Pfade in qso_state die
  `cq_mode` voraussetzen für Hunt-Verlauf?

### D — Edge-Cases die V2 übersehen könnte

Suche aktiv nach Szenarien:
- App-Start während laufender FT8-Slot (cycle_pos > 12s)
- Bandwechsel mid-OMNI-TX (Encoder läuft schon zu Ende — V2-L16)
- Mode-Wechsel von Diversity zu Normal während OMNI aktiv
- Decoder-Hang oder -Crash mit OMNI aktiv
- Encoder-Crash mit OMNI aktiv (Encoder-Worker wirft Exception)
- 2 Antworten in 1 RX-Slot (Even + Odd Decoded gleichzeitig)
- Antwort an uns kommt während wir noch im TX-Slot sind
  (Decoder dekodiert RX-Slot bevor Encoder-Worker fertig)
- Caller-Queue-QSO während OMNI pausiert + dann Stop (band_change) →
  kein Resume aber `_omni_was_active_pre_qso` bleibt True?

### E — Test-Plan-Vollständigkeit

V1 §5 listet 17 Unit + 10 Integration. V2-L11 schätzt -81 alte raus + 27
neue → ~1015 Tests netto. Was fehlt? Was sollte ergänzt werden?
Welche Tests sind unnötig? Pytest-parametrize sinnvoll wo?

### F — Commit-Reihenfolge

V2-L18 schlägt vor: Tests-Migration ZUERST (C1), dann neues Modul (C2),
dann Rückbau core/ (C3), dann mw_cycle (C4), dann main_window+mw_qso (C5),
dann Stop-Trigger (C6), dann Doku+APP_VERSION (C7).

Ist diese Reihenfolge robust? Bleiben Tests grün nach jedem Commit?

### G — KISS-Bewertung

Wo hat V1+V2 möglicherweise overengineert? Wo könnte es noch einfacher?
SimpleFT8 ist Hobby-Tool — keine Contest-Robustheit nötig.

## Format deiner Antwort

Strukturiert nach A/B/C/D/E/F/G. Pro V2-Lesson eine Zeile mit
Bewertung + ggf. Begründung mit Code-Beweis. Bei eigenen neuen
Findings: Schweregrad ⛔ KRITISCH / SOLLTE / KOENNTE.

**Zum Schluss eine eindeutige Empfehlung:**
- ✅ „Plan ist bereit für V3-Konsolidierung und Mike-Freigabe"
- 🟡 „Plan braucht V3-Anpassungen (Liste folgt)"
- ⛔ „Plan hat KRITISCHE Lücken — V2 muss überarbeitet werden bevor V3"

## Token-Budget

R1 hat 65K Context. V1 (~36 KB) + V2 (~21 KB) + Spec (~5 KB) +
Code-Files (~ wahrscheinlich 30 KB total) — passt rein. Antworte
ausführlich (300-500 Zeilen ist OK), aber nicht doppelt was V2
schon korrekt analysiert hat.
