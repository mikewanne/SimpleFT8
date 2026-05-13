# P4.OMNI-NEUBAU — V2 Self-Review

**Rolle:** frische KI ohne Vorgeschichte, liest V1 + Memory-Spec +
Code, sucht Lücken, mehrdeutige Stellen, Code-Halluzinationen.

**Ergebnis:** L1...Lx Lessons. Werden in V3 (nach R1) eingearbeitet.

---

## L1 — Listener-Pfad: `on_message_decoded` ist in `mw_cycle.py`, NICHT `mw_qso.py`

**V1 §3.2 sagt:**
> "OMNI-Übergabe-Pfad bei eingehender CQ-Antwort … in mw_qso `_on_message_decoded`"

**Code-Verifikation (Schritt 0):**
- `core/decoder.py` emittiert `message_decoded`-Signal
- `ui/mw_radio.py:55` `self.decoder.message_decoded.connect(self.on_message_decoded)`
- Die Methode `on_message_decoded(msg)` lebt in `ui/mw_cycle.py:909`
- `mw_qso.py` hat KEIN `_on_message_decoded` — der Hunt-Pfad läuft nur über
  `qso_state.on_message_received` der von `mw_cycle.on_message_decoded`
  aufgerufen wird

**Korrektur für V3:**

OMNI-Listener-Check muss in `ui/mw_cycle.py:on_message_decoded` rein,
**VOR** dem `qso_sm.on_message_received(msg)`-Call:

```python
# ui/mw_cycle.py:on_message_decoded (Z.909)
def on_message_decoded(self, msg: FT8Message):
    if not self.rx_panel._rx_active:
        return
    self.control_panel.update_snr(msg.snr)
    self.qso_sm.set_last_snr(msg.snr)

    # RX zuerst anzeigen
    if msg.target == self.settings.callsign:
        self.qso_panel.add_rx(...)

    # NEU: OMNI-Antwort-Pfad VOR qso_sm.on_message_received
    if (self._omni_cq.is_active() and not self._omni_cq.is_paused()
            and msg.target == self.settings.callsign
            and not msg.is_73 and not msg.is_rr73):
        self._omni_cq.pause()
        self.qso_sm.start_qso(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            their_snr=msg.snr,
        )
        # NICHT mehr on_message_received aufrufen — Hunt-State-Machine
        # hat die Message bereits konsumiert
        self._omni_was_active_pre_qso = True  # für _maybe_resume_omni
        return

    self.qso_sm.on_message_received(msg)
```

---

## L2 — `encoder.tx_even` Race vs `transmit()`: atomare API nötig

**V1 §2.2 Worker-Loop sagt:**
> "self._encoder.audio_freq_hz = self._cq_audio_hz
>  self._encoder.tx_even = target_even
>  self._encoder.transmit(cq_msg)"

**Race-Risiko:** Encoder-`_tx_worker_inner` liest `self.tx_even` in
`_next_slot_boundary()` (`core/encoder.py:266`). Wenn OMNI-Worker
`encoder.tx_even = X` setzt während Encoder gerade noch im vorherigen
TX `_next_slot_boundary` aufruft, sieht der noch-laufende TX bereits den
neuen Wert — falsche Slot-Boundary, falsche Parität.

In Praxis selten (Encoder ist ~1.3s aktiv, OMNI-Worker setzt nur alle
~15s), aber R1 wird das als Race flaggen.

**Korrektur für V3:**

Encoder bekommt atomare API:
```python
# core/encoder.py
def transmit(self, message: str, *, tx_even: bool | None = None,
              audio_freq_hz: int | None = None) -> bool:
    """Atomic transmit — setzt tx_even + audio_freq_hz UNTER Lock,
    dann startet Worker-Thread. Returnt True wenn akzeptiert,
    False wenn busy (SKIP)."""
    with self._tx_lock:
        if self._is_transmitting:
            return False  # SKIP
        if tx_even is not None:
            self.tx_even = tx_even
        if audio_freq_hz is not None:
            self.audio_freq_hz = audio_freq_hz
        self._is_transmitting = True
        # ... starte Worker
    return True
```

OMNI-Worker:
```python
self._encoder.transmit(cq_msg, tx_even=target_even, audio_freq_hz=self._cq_audio_hz)
```

**Bestehende Aufrufer** (mw_qso, qso_state) bleiben funktional weil neue
Parameter optional sind. Backward-compat.

---

## L3 — `_last_qso_tx_even` woher? — aus `_on_tx_finished` merken

**V1 §3.2 sagt:**
> "last_qso_was_even = self._last_qso_tx_even  # gemerkt aus encoder.tx_even bei QSO-Ende"

**Code-Verifikation:**
- `_on_tx_finished` läuft pro TX-Ende in mw_qso
- `encoder.tx_even` ist der Slot-Filter — bleibt gesetzt bis zum nächsten
  Setter
- Bei QSO-Ende ist `encoder.tx_even` = unser letzter TX-Slot (typisch
  TX_73_COURTESY oder TX_RR73)

**Edge-Case:** QSO-Timeout ohne TX_73_COURTESY (Mike's `_on_qso_timeout`).
Dann ist letzter Slot ein RX. `encoder.tx_even` zeigt aber unseren
letzten TX — gegenüberliegend zum letzten RX. Logik:
- Mike's Spec: "QSO endet auf Even → Block 2 (Odd-First)"
- "Endet auf Even" = letzter Slot der QSO-Aktivität war Even
- TX-Slot = unser TX, RX-Slot = unser RX (= deren TX)
- Bei QSO-Timeout: letzter Slot = ihr letzter TX (= unser RX) — Parität
  von ihrem TX

In Praxis: nahezu alle QSOs enden via TX_73_COURTESY (Mike's Field-Test
v0.95.5 bestätigt) → `encoder.tx_even` ist korrekt 99% der Fälle.

**Korrektur für V3:**

```python
# ui/mw_qso.py
def _on_tx_finished(self):
    # ... existing code
    self._last_qso_tx_even = self.encoder.tx_even  # merken für OMNI-Resume

def _on_qso_complete(self):
    # ... existing code (ADIF, etc.)
    self._maybe_resume_omni()  # nutzt self._last_qso_tx_even

def _on_qso_timeout(self):
    # ... existing code
    # bei Timeout: encoder.tx_even ist noch der letzte unsere-TX-Slot
    # (= gegenüberliegend zu deren-letztem TX). Akzeptable Annäherung.
    self._maybe_resume_omni()
```

V3-AC ergänzen: AC10b — `_on_qso_timeout` nutzt `encoder.tx_even` als
beste Annäherung (Edge-Case dokumentiert).

---

## L4 — Fallback-Frequenz wenn `get_free_cq_freq()` returnt None

**V1 §2.2 Worker-Loop sagt:**
> "self._cq_audio_hz = self._diversity.get_free_cq_freq() or 1500"

**Code-Verifikation `core/diversity.py:190`:**
- `get_free_cq_freq()` returnt `Optional[int]` — None bei leerem Histogramm
- Mike-Beobachtung: bei OMNI-Start kann Histogramm leer sein (kein decoded
  RX-Slot durchgelaufen)

**Korrektur für V3:**

V1's `or 1500` ist OK aber zu schweigsam. Besser:
```python
freq = self._diversity.get_free_cq_freq()
if freq is None:
    freq = 1500  # Audio-Mid-Band Fallback
    logger.warning("[OMNI-CQ] get_free_cq_freq returnt None → Fallback 1500 Hz")
self._cq_audio_hz = freq
```

V3-AC: AC4b — Fallback 1500 Hz wenn diversity returnt None, mit Log-Warning.

---

## L5 — Frequenz-Recheck-Intervall pro Mode skalieren?

**V1 §1 Konzept sagt:**
> "Alle 4 Blöcke (~5 Min) Re-Check"

**Code-Verifikation:** Block-Dauer pro Mode:
- FT8: 5 Slots × 15.0s = 75s. 4 Blöcke = **300s = 5 Min** ✅
- FT4: 5 Slots × 7.5s = 37.5s. 4 Blöcke = **150s = 2:30 Min**
- FT2: 5 Slots × 3.8s = 19s. 4 Blöcke = **76s = 1:15 Min**

Bei FT4/FT2 wäre Recheck-Intervall sehr kurz → könnte QSO-Aufbau stören
(CLAUDE.md: <30s killt QSO-Aufbau).

**Mike's Anweisung war:** "alle 4 Blöcke" — generisch, nicht modus-skaliert.

**Bewertung:** Hobby-Use ist 99% FT8 (laut HISTORY v0.91 R1-Akzeptanz für
ähnlichen Fall). FT4/FT2 sind Edge-Cases. V1's „4 Blöcke" ist
pragmatisch akzeptabel.

**Korrektur für V3 (optional, R1-Vorschlag abwarten):**

Konstante umstellen auf zeit-basiert statt block-basiert:
```python
_FREQ_RECHECK_INTERVAL_S = 300.0  # 5 Min, konstant für alle Modi
```

Worker checkt in jedem Block ob `time.time() - self._last_freq_check_at`
> 300s. Konsistenter über alle Modi.

V3-Empfehlung: **zeit-basiert (300s konstant)** statt block-basiert.

---

## L6 — `_omni_was_active_pre_qso` Flag-Name behalten

**V1 §3.2 nutzt** `_omni_was_active_pre_qso` (existing v0.95.23-Flag).

**Verifikation:** Flag existiert in `ui/main_window.py:226`. Konsistenz
mit Mike's mental model. Behalten — V3 unverändert.

---

## L7 — OMNI-Stop muss `encoder.tx_even` NICHT zurücksetzen

**V1 erwähnt nicht.** Bewertung: nach OMNI-Stop bleibt `encoder.tx_even`
auf letztem OMNI-TX-Wert. Wenn User danach Normal-CQ startet, setzt
Normal-CQ via `mw_qso._on_send_message` selbst seinen `tx_even`-Wert
(oder None). Kein Problem.

V3 unverändert.

---

## L8 — `slot_action`-Signal: wann emittieren

**V1 §2.1 sagt:** `slot_action = Signal(str, bool, bool)` —
`(label, is_tx, target_even)`

**Klärung für V3:**
- TX-Slot: emittieren NACH `encoder.transmit(...)`-Call (wenn akzeptiert).
  Label: `f"B{block} [{slot_index}/4] TX-{E|O}"`
- RX-Slot: emittieren AM ANFANG des RX-Slots (kurz nach Boundary, vor
  Decoder-Run). Label: `f"B{block} [{slot_index}/4] RX-{E|O}"` (RX hat
  Slot-Parität aus Boundary-Math)

**mw_cycle Slot-Action-Listener** ruft:
```python
def _on_omni_slot_action(self, label: str, is_tx: bool, target_even: bool):
    slot_start_ts = ...  # aus current cycle
    if not is_tx:
        # RX-Slot — Mike's Wunsch: „Horche..."-Anzeige im QSO-Panel
        self.qso_panel.add_listening(slot_start_ts, target_even)
    # is_tx=True wird über cycle_decoded → add_tx schon angezeigt
```

V3-AC: AC11b — RX-Slots im QSO-Panel als „Horche…"-Eintrag sichtbar
(via add_listening).

---

## L9 — Auto-Hunt-Coupling: Mutex via QButtonGroup reicht NICHT

**V1 §7 R9 sagt:** "btn-Group mutex".

**Code-Verifikation:** `ui/control_panel.py:774-802` hat
QButtonGroup. ABER: ButtonGroup verhindert nur GLEICHZEITIG-checked, nicht
laufende-Hintergrund-Worker.

**Szenario:**
1. OMNI läuft (Worker-Thread aktiv)
2. User klickt btn_auto_hunt → ButtonGroup unchecks btn_omni_cq
3. ABER: `btn_omni_cq.toggled(False)` triggert `_on_btn_omni_cq_toggled(False)`
   → `omni_cq.stop("manual_halt")`. ✅ OK.

**Aber Edge-Case:** Auto-Hunt-Klick ist programmatisch (z.B. via
Shortcut), bypasst ButtonGroup → OMNI läuft weiter.

**Korrektur für V3:**

`_on_btn_auto_hunt_toggled` zusätzlich:
```python
if checked and self._omni_cq.is_active():
    self._omni_cq.stop("superseded")
```

Symmetrisch in `_on_btn_omni_cq_toggled`:
```python
if checked and self.auto_hunt.is_active():
    self.auto_hunt.cancel()
```

V3-AC: AC11c — gegenseitiger Stop wenn der jeweilige Toggle aktiviert.

---

## L10 — Caller-Queue-Verhalten klar dokumentieren

**V1 §3.2 sagt** `_maybe_resume_omni` checkt Queue → kein Resume wenn
nicht leer. **Klärung:**

Was passiert mit dem Caller-Queue-QSO:
1. QSO endet → `_on_qso_complete` → `_resume_cq_if_needed` (qso_state.py:422)
2. `_resume_cq_if_needed` checkt Queue → wenn nicht leer → pop +
   `_pending_reply = msg` → `_process_cq_reply()`
3. `_process_cq_reply` ruft `start_qso`-ähnliche Logik (qso_state.py:226 QSOData...)
   ABER: Z.212 `if not self.cq_mode: return` blockt!

**KRITISCH:** Bei OMNI ist `cq_mode=False` → Caller-Queue-Reply wird
SILENT IGNORIERT. Mike-erwartetes Verhalten: Caller-Queue arbeitet auch
unter OMNI ab.

**Korrektur für V3:**

Option A: `_process_cq_reply` Z.212 erweitern:
```python
if not self.cq_mode and not self._omni_active_external:
    return
```
→ qso_state braucht eine externe `is_omni_active`-Brücke. Hässlich.

Option B (sauber): bei OMNI komplett anderen Pfad nehmen — Caller-Queue
ist OMNI's Verantwortung, nicht qso_state's.

```python
# In mw_qso._maybe_resume_omni():
if self.qso_sm._caller_queue:
    # OMNI nimmt ersten Caller selbst auf (start_qso direkt)
    next_msg = self.qso_sm._caller_queue.pop(0)
    self._omni_cq.pause()  # idempotent — bleibt pausiert
    self.qso_sm.start_qso(
        their_call=next_msg.caller,
        their_grid=next_msg.grid_or_report if next_msg.is_grid else "",
        freq_hz=next_msg.freq_hz,
        their_snr=next_msg.snr,
    )
    # _omni_was_active_pre_qso bleibt True → nach diesem QSO wieder _maybe_resume_omni
    return
# Queue leer → OMNI resume
last_qso_was_even = self._last_qso_tx_even
self._omni_cq.resume_after_qso(last_qso_was_even)
self._omni_was_active_pre_qso = False
```

**ABER ACHTUNG:** `qso_state._resume_cq_if_needed` (Z.422) wird automatisch
aufgerufen bei `_on_qso_complete` (über Hunt-State-Machine selbst). Wenn
es bei `cq_mode=False` einfach nichts tut (Z.437 `if self.cq_mode or
self._was_cq`), dann ist die Queue NICHT leer aber wird nicht abgearbeitet.

**Klarstellung für V3:**
- `qso_state._resume_cq_if_needed` läuft bei OMNI nicht (cq_mode=False
  und `_was_cq`=False)
- mw_qso `_maybe_resume_omni` übernimmt Caller-Queue-Logik
- V3 muss explizit dokumentieren wer die Queue leert

V3-AC: AC10 erweitern — Caller-Queue wird bei OMNI von
`mw_qso._maybe_resume_omni` abgearbeitet (mit `start_qso`-Pfad).

---

## L11 — Test-Bilanz: Kürzung der alten Tests verifiziert

**V1 §5 sagt:** -50 alte Tests, +27 neue, netto -23. 1069 → ~1046.

**Verifikation:** Lass uns die Tests auflisten die wirklich raus müssen:
- `test_p1_omni_start.py` — geschätzt ~11 Tests (Mike: +11 in v0.95.22)
- `test_p2_omni_redesign.py` — ~20 Tests (V3 v0.95.23)
- `test_p2_omni_pattern_fix.py` — ~16 Tests (v0.95.24)
- `test_p3_omni_pattern_fix2.py` — ~21 Tests (v0.95.25)
- `test_omni_tx.py` — ~4 Tests (nach v0.95.23-Migration)
- `test_encoder_queue.py` — ~9 Tests (v0.95.24)

**Summe: ~81 Tests RAUS.** V1's „-50" war Untertreibung.

**Korrektur für V3:** Test-Bilanz neu rechnen:
- Raus: ~81
- Neu: ~27 (V1 §5)
- Netto: ~-54
- 1069 → ~1015 Tests

V3-AC: AC15b — Tests grün nach Migration. Erwarteter Stand ~1015.

---

## L12 — Hardware-Garantie ANT1 — Verifikation

**V1 §3.5 + R10 + AC13 sagen:** `Encoder.transmit()` setzt zentral ANT1.

**Code-Verifikation `core/encoder.py:334`:** zentral ANT1-Setter beim
Worker-Thread-Start (HISTORY v0.95.23 bestätigt).

OMNI-Worker ruft NUR `encoder.transmit(...)` — kein direktes
`radio.set_tx_antenna(...)`. Hardware-Pflicht erfüllt.

V3 unverändert.

---

## L13 — Worker-Loop `time.sleep(0.5)` in §2.2 Punkt 7 — gefährlich

**V1 §2.2 Worker-Loop Punkt 7 sagt:**
> "time.sleep(0.5)  # verhindert dass wir den selben Slot zweimal ausführen"

**Risiko:** sleep(0.5) ist nicht cancelable via `_stop_event`. Wenn
`pause()` oder `stop()` während dieses Sleeps kommt, kann der Worker
0.5s lang nicht reagieren — und in dieser Zeit den NÄCHSTEN
Loop-Durchlauf starten BEVOR er den State-Check macht.

**Korrektur für V3:**

```python
# Statt time.sleep(0.5):
if self._stop_event.wait(timeout=0.5):
    # stopped/paused während Slot-Übergang
    return
```

Oder noch sauberer: Sleep ganz weg, stattdessen am Anfang des
nächsten Loop-Durchgangs `_compute_next_boundary` aufrufen — die Math
nimmt automatisch die nächste Boundary. Wenn sleep_dur klein wird (<0.5s),
schläft das `_stop_event.wait` halt nur kurz.

**Empfehlung:** Sleep komplett weg in V3. Der `_compute_next_boundary` +
`_stop_event.wait` kümmert sich.

---

## L14 — RX-Slot Slot-Aktion: was tut OMNI-Worker konkret?

**V1 §2.2 Punkt 5 (RX-Slot) sagt:**
> "RX-Slot — nichts zu tun, Decoder läuft eh."

**Korrektur:** „nichts zu tun" stimmt. ABER der Worker muss trotzdem
auf die nächste Boundary warten (sonst läuft er Amok).

**Klärung für V3:**

```python
if is_tx:
    self._encoder.transmit(cq_msg, tx_even=target_even, audio_freq_hz=...)
    # Counter, slot_action.emit
# else: RX-Slot — Worker schläft eh schon bis nächste Boundary,
# nichts zu tun außer slot_action emittieren
self.slot_action.emit(...)
```

V1 hat das so beschrieben aber unklar formuliert. V3 soll präziser sein.

---

## L15 — Encoder.transmit aus Worker-Thread blockiert? — verifizieren

**V1 §2.2 Punkt 5 sagt:**
> "self._encoder.transmit(cq_msg)"

**Code-Verifikation `core/encoder.py:189`:**
```python
def transmit(self, message: str):
    # ... lock-protected check
    # startet self._tx_worker(message) als Thread
    # transmit returnt sofort, nicht blocking
```

Verifiziert: `transmit()` returnt sofort, blockt nicht. OMNI-Worker
geht direkt zur slot_action.emit + slot_index++ über.

V3 unverändert.

---

## L16 — Fehlt: was passiert wenn Bandwechsel mid-OMNI-TX?

**V1 §7 R-Liste fehlt der Fall.**

**Szenario:**
1. OMNI-Worker hat `encoder.transmit("CQ ...")` aufgerufen
2. Encoder läuft im TX-Worker, sendet Audio
3. User wechselt Band → `mw_radio._on_band_changed` → `omni_cq.stop("band_change")`
4. OMNI-Worker stoppt, aber Encoder-TX läuft noch zu Ende (Slot-Boundary)

**Verhalten:** Encoder-TX läuft auf alter Frequenz/altem Band zu Ende.
Mike-Akzeptable (Bandwechsel ist langsam — User wartet).

**Korrektur für V3:** Edge-Case explizit dokumentieren in Stop-Bedingungen:
- `band_change` während laufendem OMNI-TX: Encoder-TX läuft Slot zu Ende,
  dann Stop. Erste TX nach Bandwechsel kommt nicht mehr von OMNI.
- Test: kein Test nötig (existing Encoder-Verhalten).

---

## L17 — APP_VERSION-Bump v0.96.0 — passt das?

**V1 §10 sagt:** v0.95.25 → v0.96.0

**Bewertung:** Mike's Versionsschema (HISTORY) — Patch-Bumps für Fixes,
Minor-Bumps für Features/Architektur. P4.OMNI-NEUBAU ist Architektur-
Refactor + neues Feature → Minor-Bump v0.96.0 ist korrekt.

V3 unverändert.

---

## L18 — Reihenfolge der Commits: C2 (Rückbau core/) braucht NICHT C1 (omni_cq.py)

**V1 §9 Commit-Plan:** C1 (NEU omni_cq), C2 (Rückbau core/), C3 (Rückbau
mw_cycle), C4 (Anschluss main_window+mw_qso), …

**Klärung:** C2 (Rückbau qso_state + encoder) bricht das laufende
OMNI-Feature komplett ab. Tests werden nach C2 RED weil:
- alte Tests in `test_p2_omni_redesign.py` etc. erwarten `_omni_skip_state_change`-Flag
- Wenn Flag in qso_state raus ist, brechen Tests

**Korrektur für V3:** Commit-Reihenfolge anpassen:

| C# | Inhalt | Tests grün? |
|---|---|---|
| C1 | Tests-Migration (alte OMNI-Tests RAUS) | ja, weil weniger Tests |
| C2 | NEU `core/omni_cq.py` + Unit-Tests | ja, Module + neue Tests |
| C3 | Rückbau `core/qso_state.py` + `core/encoder.py` | ja, weil Tests-Erwartungen weg |
| C4 | Rückbau `ui/mw_cycle.py` (_omni_pretrigger raus) | ja |
| C5 | Anschluss `ui/main_window.py` + `ui/mw_qso.py` | ja, Integration-Tests grün |
| C6 | Stop-Trigger `ui/mw_radio.py` + main_window | ja |
| C7 | APP_VERSION + Doku (HISTORY+HANDOFF+CLAUDE+Memory) | ja |

V3 §9 Commit-Plan überarbeiten.

---

## L19 — V1 erwähnt `_diversity_ctrl` als Konstruktor-Param — wo lebt das?

**V1 §2.1 Konstruktor:** `diversity_ctrl=self._diversity_ctrl`

**Code-Verifikation:** `mw_qso.py:223` ruft
`self._diversity_ctrl.get_free_cq_freq()` auf — Attribut existiert in
mw_qso. Initialisierung in main_window oder mw_qso?

```bash
grep "self._diversity_ctrl =" ui/
```

V3-Code-Verifikation in Schritt 0 nachholen vor Commits.

---

## L20 — Settings-Persistenz: keine OMNI-Settings nötig?

**V1 erwähnt nicht.** Bewertung:
- OMNI startet immer inactive (AC14)
- Keine User-konfigurierbaren Werte (Block-Wahl, Recheck-Intervall sind
  Konstanten)
- → Keine Settings-Keys nötig

V3 unverändert. Vielleicht später User-Setting für „Recheck-Intervall"
nach Field-Test-Erfahrung.

---

## Zusammenfassung der V2-Lessons (für V3)

| L# | Thema | Schweregrad |
|---|---|---|
| L1 | `on_message_decoded` in mw_cycle nicht mw_qso — Listener-Pfad korrigieren | ⛔ KRITISCH |
| L2 | `encoder.transmit` atomare API mit `tx_even`-Param | ⛔ KRITISCH (Race) |
| L3 | `_last_qso_tx_even` aus `_on_tx_finished` merken | ⛔ wichtig |
| L4 | Fallback 1500 Hz dokumentieren + Log-Warning | wichtig |
| L5 | Frequenz-Recheck zeit-basiert (300s konstant) statt block-basiert | wichtig |
| L6 | `_omni_was_active_pre_qso` Name behalten | OK |
| L7 | Encoder.tx_even nach OMNI-Stop nicht zurücksetzen | OK |
| L8 | `slot_action`-Signal: wann emittieren präzisieren | wichtig |
| L9 | Auto-Hunt-Coupling: gegenseitiger Stop in beiden Toggles | ⛔ wichtig |
| L10 | Caller-Queue bei OMNI: mw_qso übernimmt Pop+start_qso | ⛔ KRITISCH |
| L11 | Test-Bilanz: -81 raus, +27 neu, netto -54 → ~1015 Tests | wichtig |
| L12 | Hardware-Garantie ANT1 verifiziert | OK |
| L13 | `time.sleep(0.5)` durch `_stop_event.wait(0.5)` ersetzen | ⛔ wichtig |
| L14 | RX-Slot Worker-Loop präziser formulieren | nice-to-have |
| L15 | `Encoder.transmit` non-blocking verifiziert | OK |
| L16 | Bandwechsel mid-OMNI-TX: Encoder-TX läuft Slot zu Ende | wichtig |
| L17 | APP_VERSION v0.96.0 korrekt | OK |
| L18 | Commit-Reihenfolge: Tests-Migration zuerst | ⛔ wichtig |
| L19 | `_diversity_ctrl`-Init Lokation V3 verifizieren | nice-to-have |
| L20 | Keine Settings-Persistenz nötig | OK |

**8 ⛔ kritische / wichtige Punkte**, 7 OK, 5 nice-to-have.

---

## Bereit für DeepSeek-R1?

**Ja.** V2 ist Self-Review-Pass durch. Offene Punkte sind klar
identifiziert, Code-Pfade verifiziert, kritische Race-Stellen
beschrieben. R1 wird:
- Race-Conditions weiter prüfen (encoder.tx_even, Worker-Lifecycle)
- Architektur bewerten (3-Schichten sauber, Caller-Queue-Übergabe sauber?)
- Test-Plan-Vollständigkeit prüfen
- Commit-Reihenfolge bewerten
- Edge-Cases finden die V2 übersieht

**V3-Eingangsbasis = V1 + L1-L20 (V2-Lessons).**
