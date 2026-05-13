# Bundle C — V1: PSK-Backoff-Reset + RX-Panel-Slot-Times

**Stand 13.05.2026 spaeter Abend, Basis v0.97.14 (Bundle B' fertig).**

Zwei voneinander unabhaengige UI/Netz-Bugs als gemeinsames Bundle —
beide klein, beide isoliert, beide ohne Architektur-Beruehrung.

## P10 — PSK-Backoff-Reset

**Symptom (Mike-Field-Test 10.05.):** PSK-Reporter-Polling geht bei
Server-Errors (502/503/Timeout) in exponentielles Backoff bis 60 Min.
Wenn der Server wieder laeuft, fragt App stundenlang nicht mehr ab —
Anzeige bleibt leer obwohl Mike gehoert wird (Direct-API-Test
10.05.: 15 Stationen weltweit hoerten DA1MHH).

**Code-Stand (verifiziert):**
- `core/psk_reporter.py:42-43`: `BACKOFF_FACTOR=1.5`, `BACKOFF_MAX_S=3600`
- `_Backoff`-Klasse Z.143-159 mit `reset()` + `fail()`
- `_run_loop` Z.278+: bei Erfolg → `reset()`, bei Fehler → `fail()`
- Aktuell kein externes Trigger zum `reset()` (z.B. bei Bandwechsel)

**V1-Loesung (KISS, Mike-Optionen 1+3 kombiniert):**

1. `BACKOFF_MAX_S` von 3600s (60 Min) auf 600s (10 Min) senken.
   Begruendung: 60 Min ist viel zu lang fuer einen Hobby-Funker der
   die App-Session ueblicherweise nur 1-3 Stunden laufen laesst.
   10 Min ist okay-Kompromiss: wenn Server kurz weg ist (Wartung),
   sind wir nicht zu aggressiv aber auch nicht „stundenlang
   verloren".
2. Neue public Methode `PSKReporterClient.reset_backoff()` — exposed
   `_backoff.reset()` von aussen, damit Bandwechsel/Modus-Wechsel/
   App-Resume das Polling-Intervall sofort wieder auf base_s
   zurueckziehen koennen.
3. Hook im `_on_band_changed` / `_on_mode_changed` (`ui/mw_radio.py`)
   ruft `self._psk_worker.reset_backoff()` wenn der Worker existiert.

**Mike-Optionen abgewaegt:**
- Option 1 (BACKOFF_MAX senken): ja, von 60 Min auf 10 Min
- Option 2 (manueller Reset-Button): nein — UI-Aufwand fuer ein
  Symptom das automatisch durch Option 3 erschlagen wird
- Option 3 (Auto-Reset bei Band/Modus): ja, an Hooks `_on_band_changed`
  und `_on_mode_changed` in mw_radio. **NICHT OMNI-Start** — das ist
  laufender Betrieb, kein Server-Recovery-Trigger

**Akzeptanzkriterien P10:**
- AK1: `BACKOFF_MAX_S` = 600 (10 Min).
- AK2: `PSKReporterClient` hat public `reset_backoff()`-Methode.
- AK3: Bandwechsel triggert `reset_backoff()` (wenn Worker existiert).
- AK4: Modus-Wechsel triggert `reset_backoff()`.
- AK5: Bestehende `_Backoff.reset()`-Tests + Logik unveraendert.

**Files:**
- `core/psk_reporter.py` (BACKOFF_MAX_S + reset_backoff-Methode)
- `ui/mw_radio.py` (Hook in _on_band_changed + _on_mode_changed)
- `tests/test_p10_psk_backoff_reset.py` NEU

## P13 — RX-Panel-Slot-Times

**Symptom (Mike-Field-Test 10.05.):** RX-Panel UTC-Spalte zeigt
krumme Wall-Time (z.B. 10:51:42) statt FT8-Slot-Boundaries
(10:51:30 oder 10:51:45).

**Bug-Wurzel (verifiziert):**

`ui/rx_panel.py:292` `add_message`:
```python
utc_new = (getattr(msg, '_utc_display', None)
           or getattr(msg, '_utc_str', None)
           or time.strftime("%H%M%S", time.gmtime()))
```

`core/decoder.py:345` setzt **nur** `m._slot_start_ts = target_slot_start`
— weder `_utc_display` noch `_utc_str`. → Wall-Time-Fallback greift.

**V1-Loesung (minimal):**

Add_message nutzt `_slot_start_ts` als bevorzugte Quelle:
```python
slot_ts = getattr(msg, '_slot_start_ts', None)
if slot_ts is not None:
    utc_new = time.strftime("%H%M%S", time.gmtime(slot_ts))
else:
    utc_new = (getattr(msg, '_utc_display', None)
               or getattr(msg, '_utc_str', None)
               or time.strftime("%H%M%S", time.gmtime()))
```

Damit:
- Real-Pfad (Decoder gibt msg mit `_slot_start_ts`) → Slot-Boundary
- Fallback (Tests, Mocks ohne Decoder) → wie bisher

**Akzeptanzkriterien P13:**
- AK1: Wenn `msg._slot_start_ts` gesetzt, UTC-Spalte = Slot-Boundary
  (z.B. 10:51:30 oder 10:51:45 fuer FT8 alle 15s).
- AK2: FT4 (7.5s) und FT2 (3.8s) zeigen entsprechende Boundaries.
- AK3: Wenn `_slot_start_ts` fehlt (alte Tests), Fallback wie bisher
  (Wall-Time).
- AK4: Bestehendes Sort-Verhalten (neueste oben, HHMMSS-String-
  Vergleich) bleibt korrekt — Slot-Boundary ist stets <= Wall-Time
  zur gleichen Slot-Zeit, keine Reihenfolgen-Inversion.

**Files:**
- `ui/rx_panel.py:288-292` (add_message)
- `tests/test_p13_rx_panel_slot_times.py` NEU

## Bundle-Strategie

Beide Punkte sind:
- klein (<1h Code je)
- isoliert (kein Cross-File-Risiko)
- hardware-frei
- ohne Architektur-Wirkung

Gemeinsamer V1→V2→R1→V3 spart ~50% Workflow-Overhead vs. 2× separat.

Atomare Commits trotzdem getrennt:
- **C1:** P10 PSK-Backoff
- **C2:** P13 RX-Panel-Slot-Times
- **C3:** APP_VERSION 0.97.15 + Doku

**Tests-Erwartung:** 1204 → ~1212 (+8: 4 P10 + 4 P13).

**APP_VERSION:** 0.97.14 → 0.97.15 (Bugfix-Bundle).

**Backup:** `Appsicherungen/2026-05-13_v0.97.14_vor_bundle_c/` —
3 Files (`core/psk_reporter.py`, `ui/mw_radio.py`, `ui/rx_panel.py`).

## Risiken fuer R1 zu pruefen

- **R1-P10**: BACKOFF_MAX_S = 600s (10 Min). Zu aggressiv? Zu lasch?
  Auswirkung auf PSK-Server-Last bei laenger andauerndem Outage.
- **R1-P10**: Thread-Safety von `reset_backoff()` — `_backoff.reset()`
  ist ein simples Attribut-Set. Worker-Thread liest `_backoff` in
  `_run_loop` Z.291 (`self._backoff.fail()`). Race? V1-Theorie: nein
  weil `_run_loop` sequenziell Erfolg/Fehler abwechselt + reset_backoff
  setzt nur das aktuelle Intervall zurueck. Aber R1 soll bestaetigen.
- **R1-P10**: Sleep-Loop in `_run_loop` Z.301-305 nutzt aktuelles
  `interval` aus letztem Iteration-Schritt. Wenn `reset_backoff()` mid-
  sleep gerufen wird, sleep laeuft bis Ende (kein Early-Wakeup). Ist
  das ein Problem? Worst-Case: 1 Iteration Sleep im alten Intervall,
  dann erst Reset wirksam.
- **R1-P13**: Decoder-Pfad ist der einzige `_slot_start_ts`-Setter?
  Wenn andere Pfade msg an rx_panel.add_message reichen ohne
  `_slot_start_ts`, fallen sie auf Fallback zurueck — ok.
- **R1-P13**: Sort-Verhalten — was wenn 2 Messages aus 2 verschiedenen
  Slots im selben Zyklus reinkommen? Slot-Boundary ist diskretisiert
  (mehrere msgs gleicher Slot haben gleichen Timestamp). Aktueller
  Sort: HHMMSS-String-Vergleich. Bei gleicher Slot-Time → erster
  Insert wins (= Reihenfolge wie sie aus Decoder kommen). Akzeptabel.

## Status

V1 fertig. Bereit fuer V2-Self-Review.
