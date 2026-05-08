# P1.BUNDLE2 — Diagnose V1 (3 hardware-freie Bugs)

**Stand:** 2026-05-08 nach v0.95.18 P1.BUNDLE-LOGBOOK-RST-SNR.
**Ziel:** Bundle 3 unabhaengige State-Machine + UI-Bugs in einem Workflow.
Alle hardware-frei testbar (Qt offscreen + State-Machine-Unittest).
**Vorgaenger:** v0.95.18 (P1.BUNDLE-LOGBOOK-RST-SNR), Tests 938 gruen.
**APP_VERSION-Ziel:** 0.95.19 (Patch).

---

## Bug 1 — P1.11 `rr73_retries`-Counter shared zwischen WAIT_RR73 und WAIT_73-Hoeflichkeitspfad

### Symptom
Nach voller WAIT_RR73-Sequenz (3 Retries `MAX_RR73_RETRIES`) bleibt
`qso.rr73_retries=3` haengen. Wenn die Gegenstation in WAIT_73 ihren
R-Report wiederholt (sie hat unser RR73 nicht empfangen), prueft
`qso_state.py:635` `if self.qso.rr73_retries < 2:` — bei 3 ist der
Hoeflichkeits-Retry blockiert. Die Station wird im Stich gelassen
obwohl wir noch RR73 senden duerften.

### Wurzel
`core/qso_state.py:83` Field-Definition:
```python
rr73_retries: int = 0  # Retries speziell fuer WAIT_RR73
```

Der Counter wird in 2 unabhaengigen Pfaden inkrementiert:
- **Z.365** (WAIT_RR73 Retry-Pfad nach `timeout_cycles == 1`) bis
  `MAX_RR73_RETRIES = 3`
- **Z.635-636** (WAIT_73 R-Report-Hoeflichkeit) bis `< 2` (lokal)

Beide nutzen das selbe Feld → 1. Pfad fuellt den Counter, 2. Pfad blockiert.

### Fix
Option A (sauber, KISS): Neues Feld `wait_73_retries: int = 0` in
`QSOData`, in WAIT_73-R-Report-Branch verwenden statt `rr73_retries`.

```python
# core/qso_state.py:83 (QSOData dataclass)
rr73_retries: int = 0           # Retries fuer WAIT_RR73-Pfad
wait_73_retries: int = 0        # NEU: Retries fuer WAIT_73-Hoeflichkeit (R-Report-Wiederholung)

# core/qso_state.py:635-639 (WAIT_73-Hoeflichkeit)
elif msg.is_r_report and msg.caller == self.qso.their_call:
    if self.qso.wait_73_retries < 2:        # statt rr73_retries
        self.qso.wait_73_retries += 1       # statt rr73_retries
        tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
        print(f"[QSO] Hoeflichkeit: {msg.caller} wiederholt R-Report → "
              f"sende RR73 erneut ({self.qso.wait_73_retries}/2)")
        self.send_message.emit(tx_msg)
    else:
        print(f"[QSO] {msg.caller} wiederholt R-Report — max Retries erreicht")
```

### Akzeptanzkriterien
- AC-1.1: WAIT_RR73 voller Retry-Sequenz (rr73_retries=3) blockiert
  WAIT_73-Hoeflichkeit NICHT mehr.
- AC-1.2: WAIT_73-Hoeflichkeit kann max 2× RR73 erneut senden
  unabhaengig vom WAIT_RR73-Counter.
- AC-1.3: rr73_retries bleibt nach QSO-Ende fuer Doku/Debug erhalten
  (kein impliziter Reset).

### Tests (geplant: 3)
1. `test_p1_11_rr73_retries_does_not_block_wait_73`
   – rr73_retries auf MAX gesetzt, msg.is_r_report kommt → wait_73_retries=1.
2. `test_p1_11_wait_73_max_2_retries`
   – 3× R-Report kommt → 2 RR73 raus, dritter ignoriert.
3. `test_p1_11_independent_counters`
   – beide Counter sind unabhaengig (Hilfstest).

---

## Bug 2 — P1.13 TX-Frequenz-Spinbox-Sync im Normal-Modus bei Hunt-Klick

### Symptom (Mike's TODO 2026-05-05)
„Wenn User im Normal-Modus auf eine Station klickt (Hunt), wird
`encoder.audio_freq_hz` NICHT angepasst und Spinbox zeigt weiterhin
den alten manuell gesetzten Wert. → Verwirrung beim Frequenz-Diagnose."

### Wurzel
`ui/mw_qso.py:_on_station_clicked` (Z.66-138) setzt:
- `encoder.tx_even = not their_even` (Slot-Paritaet)
- `qso_sm.start_qso(...)`

Aber NICHT:
- `encoder.audio_freq_hz = msg.freq_hz`
- `_tx_freq_spin.setValue(msg.freq_hz)`
- Histogramm-Marker-Update

Konsequenz: TX laeuft auf der ALTEN audio_freq_hz, waehrend Mike's
Augen sehen dass die Station auf einer anderen Frequenz ruft.

### Fix
In `_on_station_clicked` direkt nach `start_qso(...)` (oder davor) im
Normal-Modus die TX-Frequenz auf `msg.freq_hz` umstellen, mit
Hardware-Range-Clamp (150-2800 Hz) und Spinbox-Sync ohne Endlos-Loop:

```python
# ui/mw_qso.py:_on_station_clicked nach start_qso(...) Z.133, vor _was_cq Z.137
# P1.13 (v0.95.19): Im Normal-Modus TX-Frequenz auf Station-Frequenz
# nachziehen + UI synchronisieren (Histogramm + Spinbox).
if self._rx_mode == "normal" and msg.freq_hz:
    freq_hz = max(150, min(2800, int(msg.freq_hz)))
    self.encoder.audio_freq_hz = freq_hz
    spin = self.control_panel._tx_freq_spin
    spin.blockSignals(True)
    spin.setValue(freq_hz)
    spin.blockSignals(False)
    # Histogramm-Marker mitziehen
    hist_data = self._diversity_ctrl.get_histogram_data()
    hist_data['cq_freq'] = freq_hz
    self.control_panel.update_freq_histogram(hist_data)
    # Persistenz NICHT — Hunt-Klick ist temporaer, Spinbox bleibt
    # erhalten fuer naechstes manuelles QSO.
```

**Wichtig:** KEINE `settings.save_normal_tx_freq` — das wuerde die
manuell eingestellte Default-Frequenz pro Band ueberschreiben. Hunt-
Klick aktualisiert nur die Live-Anzeige + Encoder bis zum naechsten
manuellen Eingriff oder QSO-Ende.

### Akzeptanzkriterien
- AC-2.1: Hunt-Klick im Normal-Modus → encoder.audio_freq_hz auf
  msg.freq_hz, Spinbox zeigt msg.freq_hz, Histogramm-Marker auf msg.freq_hz.
- AC-2.2: Hunt-Klick im Diversity-Modus AENDERT NICHTS (Auto-Suche
  bleibt unberuehrt).
- AC-2.3: Frequenz-Range geclampt auf 150-2800 Hz (Hardware-Limit).
- AC-2.4: Settings.save_normal_tx_freq wird NICHT aufgerufen (Default
  pro Band bleibt erhalten).
- AC-2.5: Spinbox-Sync ohne valueChanged-Endlos-Loop (blockSignals).

### Tests (geplant: 4)
1. `test_p1_13_normal_hunt_click_updates_encoder_and_spin`
2. `test_p1_13_diversity_hunt_click_does_not_change_freq`
3. `test_p1_13_clamp_to_hardware_range` (z.B. msg.freq_hz=3500 → 2800)
4. `test_p1_13_spinbox_sync_no_loop` (signalSpy auf valueChanged)

---

## Bug 3 — P1.7 Lokaler Duplikat-Filter ADIF/Logbuch (Folge aus P1.5)

### Symptom (Mike's TODO 2026-05-05)
„Bekannte Station < 5 Min nach RR73 ruft erneut → zweites QSO startet
+ zweiter ADIF-Eintrag wird geschrieben. QRZ.com filtert serverseitig,
aber lokal landet das Doppel-QSO im Logbuch."

### Wurzel
`ui/mw_qso.py:_on_qso_complete` (Z.310-336) ruft `adif.log_qso(...)`
unbedingt — kein Duplikat-Check. `log/qso_log.py` hat zwar
`is_worked_on_band(call, band)`-API, aber das prueft seit-immer
(persistent), nicht ein Zeit-Fenster.

### Fix
Option A (KISS, Time-Window): in `_on_qso_complete` vor `adif.log_qso`
einen `recent_logged_calls: dict[str, float]`-Cache pruefen
(call → letzter log-Zeitstempel). Wenn `now - last < 300s` (5 Min):
ADIF-Schreib + qso_log.add_qso ueberspringen.

```python
# ui/main_window.py oder mw_qso.py: Init-Block
self._recent_logged_calls: dict[str, float] = {}
_LOG_DEDUP_WINDOW_S = 300  # 5 Min

# ui/mw_qso.py:_on_qso_complete vor adif.log_qso
import time
now = time.time()
call_key = qso_data.their_call.upper()
last = self._recent_logged_calls.get(call_key, 0.0)
if now - last < _LOG_DEDUP_WINDOW_S:
    print(f"[QSO] DUPLIKAT-FILTER: {call_key} schon vor "
          f"{int(now-last)}s geloggt → skip ADIF")
    self.qso_panel.add_info(f"{call_key} duplikat — skip ADIF")
    return  # KEIN log_qso, KEIN add_qso, KEIN log_antenna_qso
self._recent_logged_calls[call_key] = now
self.adif.log_qso(...)  # bestehender Call
```

**Wichtig:** Cache ist Session-lokal (kein Persist) — App-Restart
loescht den State. Das ist OK weil:
- Session-Restart = Mike triggert manuell, will Status reset
- Persistent waere over-engineered (echte Duplikate < 5 Min sind selten)

### Akzeptanzkriterien
- AC-3.1: 2× `_on_qso_complete` mit gleichem Call innerhalb 5 Min →
  nur 1 ADIF-Eintrag, nur 1 qso_log.add_qso, nur 1 log_antenna_qso.
- AC-3.2: 2× `_on_qso_complete` mit gleichem Call mit 6+ Min Abstand →
  beide ADIF-Eintraege geschrieben.
- AC-3.3: 2× `_on_qso_complete` mit verschiedenen Calls innerhalb 5 Min
  → beide geschrieben (kein Cross-Call-Block).
- AC-3.4: User-Statusbar/Panel-Info zeigt Duplikat-Skip-Info.

### Tests (geplant: 4)
1. `test_p1_7_duplicate_within_window_skipped`
2. `test_p1_7_duplicate_outside_window_logged`
3. `test_p1_7_different_calls_both_logged`
4. `test_p1_7_dedup_cache_session_local` (App-Restart-Simulation)

---

## Workflow-Bewertung

**Trigger fuer vollen Workflow erfuellt:**
- ≥2 unabhaengige ACs (3 Bugs × ≥3 ACs = ~12 ACs)
- Beruehrt 3 Dateien: `core/qso_state.py`, `ui/mw_qso.py`,
  `ui/main_window.py` + Test-File
- Mehrere Probleme zugleich (Bundle-Strategie wie v0.95.6 + v0.95.18)

**Test-Erwartung:** 938 → ~949 (+11: 3 + 4 + 4).

**Atomare Commits geplant:** 3 Code + 1 Doku.

---

## Offene Fragen fuer V2

1. **P1.11:** Soll `wait_73_retries` ein neues `QSOData`-Feld werden
   (Option A, sauber) oder einfach beim WAIT_73-Eintritt der Counter
   resetet werden (Option B, weniger Code)? V2 entscheidet.
2. **P1.13:** Soll `_diversity_ctrl.get_histogram_data()` immer
   verfuegbar sein im Normal-Modus? Oder Fallback wenn `_bins` leer?
3. **P1.7:** 5-Min-Window Default — Mike's Use-Case. Oder Setting
   konfigurierbar?
4. **P1.7:** Antennen-Stats-Log (`_stats_logger.log_antenna_qso`)
   auch skippen oder weiter loggen? V2 R1 muss klaeren.
5. **Test-Zaehlung:** Bug-Fixes sollten 938 → 949 bringen — bei 11 Tests
   reicht das? Oder lieber 1-2 mehr Edge-Cases.

---

**V1-Ende. V2-Self-Review folgt.**
