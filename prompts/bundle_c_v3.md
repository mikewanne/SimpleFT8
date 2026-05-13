# Bundle C — V3: PSK-Backoff + RX-Panel-Slot-Times

V3 nach R1-Review (3 KP + 3 S + 2 K + 3 H).

## R1-Findings-Bilanz

| Finding | Schwere | Aktion |
|---|---|---|
| KP-1: `_slot_start_ts` muss in `add_message` UND `_set_sort` greifen | 🔴 Bug | **Angenommen** — V3 inkl. _set_sort |
| KP-2: `_Backoff` Race read-modify-write | 🔴 Bug | **Angenommen** — threading.Lock einbauen |
| KP-3: `BACKOFF_MAX_S=600` Code-Anpassung explizit | 🔴 Implementation | **Angenommen** (Code-Detail) |
| S-1: public `reset_backoff()`-Methode | 🟠 Architektur | **Angenommen** — war in V2 schon |
| S-2: `main_window.py` in Backup-Liste | 🟠 Korrekt | **Angenommen** |
| S-3: Statusbar-Pfad braucht eigenes Backoff | 🟠 Konsistenz | **Abgelehnt** mit Begruendung |
| K-1: `_psk_busy`-Flag gegen Race | 🟡 Defensive | **Abgelehnt** (KISS) |
| K-2: `int(slot_ts)` Sub-Sekunden-Rundung | 🟡 Vorsicht | **Angenommen** |
| H-1: erledigt durch KP-1 | 🔘 | OK |
| H-2: rx_history_store-Format | 🔘 | **Verifiziert non-issue** — speichert Float-Timestamps |
| H-3: `_psk_band`-Race | 🔘 | **Akzeptiert** wie V2 |

### Abgelehnte Findings — Begruendung

**S-3 (Statusbar-Pfad eigenes Backoff abgelehnt):**

R1 schlug vor, im `_psk_worker` (`ui/main_window.py:949`) auch einen
Backoff einzubauen, um PSK-Server-Last zu reduzieren.

- **Last-Effekt vernachlaessigbar:** Mike's App. 1 Request alle 5 Min,
  selbst bei 2-Stunden-Outage = max. 24 Requests. PSK-Server haelt
  taeglich 10.000+ Stationen aus.
- **UX-Kosten erheblich:** Mit Backoff sieht Mike nach Server-Recovery
  bis zu 10 Min lang keine PSK-Daten — genau der Bug den V2 mit dem
  Karten-Pfad fixen will. Statusbar ist sein primaerer Indikator.
- **Mike's KISS-Klausel:** „lieber 3 gut funktionierende Features".
  Statusbar ist „immer aktiv polls jede 5 Min" — einfach, vorhersehbar,
  funktioniert. Backoff macht es komplexer ohne realen Vorteil.
- **Trennung der Pfade ist Feature:** Karten-Pfad mit Backoff
  (Aktiv-Karte wird seltener gebraucht, kann temporaer warten) +
  Statusbar ohne Backoff (Dauer-Anzeige) ist absichtlich
  unterschiedlich.

**Bleibt:** Kein Backoff im `_psk_worker`. Sofortiger Re-Fetch bei
Band/Modus-Wechsel via `_psk_timer.start(0)` ist die einzige
P10-Aenderung am Statusbar-Pfad.

**K-1 (Race-Guard mit `_psk_busy`-Flag abgelehnt):**

R1 erwaehnt selbst „Mike's KISS-Prinzip spricht dagegen". Aktueller
Code hat schon den Race (5-Min-Timer waehrend Fetch). V3 macht es
nicht schlimmer. Worst-Case: 1× Doppel-Update von `update_psk_stats`
— harmless.

## P10 — PSK-Backoff-Reset (V3-Endzustand)

### Datei 1: `core/psk_reporter.py`

**Z.43:** `BACKOFF_MAX_S = 600` (war 3600).

**Z.143-159: `_Backoff` mit Lock (KP-2 Fix):**
```python
class _Backoff:
    """Exponentielles Backoff fuer Polling-Fehler. Thread-safe (KP-2)."""
    base_s: float
    factor: float = BACKOFF_FACTOR
    max_s: float = BACKOFF_MAX_S
    current_s: float = field(init=False)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)

    def __post_init__(self):
        self.current_s = self.base_s

    def reset(self):
        with self._lock:
            self.current_s = self.base_s

    def fail(self) -> float:
        """Naechstes Intervall setzen und zurueckgeben."""
        with self._lock:
            self.current_s = min(self.max_s, self.current_s * self.factor)
            return self.current_s
```

**Nach Z.323 neue Methode:**
```python
def reset_backoff(self) -> None:
    """P10 (v0.97.15): Backoff von aussen zuruecksetzen, z.B. bei
    Bandwechsel oder Modus-Wechsel — User-erwartete Recovery.

    Worker-Thread im Sleep wird NICHT interruptet — naechster
    Poll-Tick laeuft mit dem dann aktuellen Intervall (max 10 Min).
    """
    self._backoff.reset()
```

### Datei 2: `ui/main_window.py`

`_on_band_changed` / `_on_mode_changed` sind im Mixin `mw_radio.py`,
**nicht hier**. Aber: `_psk_timer` Property ist in main_window.
Zugriff aus Mixin via `self._psk_timer` ist OK (Mixin laeuft als
MainWindow-Instanz).

`_fetch_psk_stats` Z.939+: bei Re-Trigger den `_psk_first_fetch =
True` setzen damit `_psk_timer.setInterval` zurueck auf erste
Schnellabfrage geht. Aktuell wird das nur bei App-Start gesetzt.

**Aenderung in `_fetch_psk_stats`:** N/A — V3 macht den Re-Trigger
ueber `_psk_timer.start(0)` aus mw_radio. Aktueller `_fetch_psk_stats`
wird vom Timer gerufen → starts Worker-Thread → return.

### Datei 3: `ui/mw_radio.py`

`_on_band_changed` nach Z.359 `self.settings.set("band", band)`
einfuegen:

```python
# P10 (v0.97.15): bei Bandwechsel sofortiger PSK-Re-Fetch
# (Statusbar-Pfad) + Backoff-Reset (Karten-Pfad, falls offen).
if hasattr(self, '_psk_timer'):
    self._psk_first_fetch = True  # naechste Iteration wieder 2-Min
    self._psk_timer.start(0)       # sofortiger Trigger
if hasattr(self, '_direction_map_dialog') and self._direction_map_dialog:
    canvas = getattr(self._direction_map_dialog, '_map_canvas', None)
    if canvas and getattr(canvas, '_psk_client', None):
        try:
            canvas._psk_client.reset_backoff()
        except Exception:
            pass
```

Analog in `_on_mode_changed` (Z.261+).

**Wichtig Reihenfolge:** Settings ZUERST setzen, dann PSK-Trigger.
Sonst fetched Worker fuer altes Band.

## P13 — RX-Panel-Slot-Times (V3-Endzustand)

### Datei 4: `ui/rx_panel.py`

**`add_message` Z.288-292 (KP-1 + K-2 Fix):**
```python
def add_message(self, msg: FT8Message):
    """Neue dekodierte Nachricht hinzufuegen."""
    if not self._rx_active:
        return
    # P13 (v0.97.15): bevorzugt Slot-Boundary aus Decoder, sonst
    # Wall-Time-Fallback. K-2: int() rundet Sub-Sekunden ab.
    slot_ts = getattr(msg, '_slot_start_ts', None)
    if slot_ts is not None:
        utc_new = time.strftime("%H%M%S", time.gmtime(int(slot_ts)))
    else:
        utc_new = (getattr(msg, '_utc_display', None)
                   or getattr(msg, '_utc_str', None)
                   or time.strftime("%H%M%S", time.gmtime()))
    # ... rest wie bisher ...
```

**`_set_sort` time-Branch Z.597-598 (KP-1 Erweiterung):**
```python
elif mode == "time":
    # P13 (v0.97.15): Sort auf Slot-Start-Timestamp (Float) wenn
    # gesetzt, sonst Fallback auf alte String-Felder.
    messages.sort(
        key=lambda x: (
            getattr(x[0], '_slot_start_ts', None)
            or getattr(x[0], '_utc_display', None)
            or getattr(x[0], '_utc_str', None)
            or ''
        ),
        reverse=True,
    )
```

⚠ Mixed-Type-Sort-Risiko: wenn manche msgs `_slot_start_ts` haben
(float) und andere nicht (str-Fallback), wirft Python TypeError
beim Vergleich. **Defensive:** alle einheitlich via Float-Key:

```python
elif mode == "time":
    def _time_key(msg_tuple):
        msg = msg_tuple[0]
        ts = getattr(msg, '_slot_start_ts', None)
        if ts is not None:
            return float(ts)
        # Fallback: alte HHMMSS-Strings als float interpretieren
        s = (getattr(msg, '_utc_display', None)
             or getattr(msg, '_utc_str', None) or '0')
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0
    messages.sort(key=_time_key, reverse=True)
```

Damit ist Sort durchgehend Float-Vergleich, kein TypeError-Risiko.

### Akzeptanzkriterien

**P10:**
- AK1: `BACKOFF_MAX_S` = 600.
- AK2: `_Backoff.reset/fail` thread-safe via Lock.
- AK3: `PSKReporterClient.reset_backoff()` public.
- AK4: Bandwechsel → `_psk_timer.start(0)` + (falls Karte offen)
  `_psk_client.reset_backoff()`.
- AK5: Modus-Wechsel triggert dasselbe.
- AK6: Bestehende `_Backoff.reset/fail`-Logik semantisch unveraendert.
- AK7: Statusbar-Pfad braucht KEIN eigenes Backoff (R1-S-3 abgelehnt).

**P13:**
- AK1: `_slot_start_ts` gesetzt → UTC-Spalte = Slot-Boundary.
- AK2: FT4/FT2 zeigen entsprechende Boundaries.
- AK3: Fallback ohne `_slot_start_ts` → Wall-Time.
- AK4: Sort funktioniert sowohl mit als ohne `_slot_start_ts` ohne
  TypeError (mixed-Type-Defensive).
- AK5: `int(slot_ts)` rundet Sub-Sekunden ab (K-2).

## Tests

`tests/test_p10_psk_backoff_reset.py` NEU (~5 Tests):
- T1: `BACKOFF_MAX_S` Bug-Schutz Source-Level
- T2: `_Backoff.reset/fail` ohne Race (sequenziell + parallel via threads)
- T3: `PSKReporterClient.reset_backoff()` setzt `current_s` zurueck
- T4: Lock thread-safe (50 Iterationen, kein TypeError)
- T5: Backward-Kompat — `_Backoff.fail()` exponentielle Funktion ok

`tests/test_p13_rx_panel_slot_times.py` NEU (~5 Tests):
- T1: `msg._slot_start_ts` gesetzt → UTC = Slot-Boundary
- T2: ohne `_slot_start_ts` → Wall-Time-Fallback
- T3: FT4 7.5s-Slots → korrekte Boundaries
- T4: `int(slot_ts)` rundet Sub-Sekunden ab
- T5: `_set_sort("time")` mit mixed-msg-Typen → kein TypeError

**Tests-Erwartung:** 1204 → ~1214 (+10).

## Backup-Strategie (S-2)

`Appsicherungen/2026-05-13_v0.97.14_vor_bundle_c/` mit:
- `core/psk_reporter.py`
- `ui/main_window.py` (S-2 Fix)
- `ui/mw_radio.py`
- `ui/rx_panel.py`

4 Files.

## Atomare Commits

1. **C1: P10 PSK-Backoff** — `core/psk_reporter.py` + `ui/mw_radio.py`
   + `tests/test_p10_psk_backoff_reset.py`
2. **C2: P13 RX-Panel-Slot-Times** — `ui/rx_panel.py` +
   `tests/test_p13_rx_panel_slot_times.py`
3. **C3: APP_VERSION 0.97.15 + Doku** — `main.py` + HISTORY +
   HANDOFF + CLAUDE + TODO + Plan-Files

## Field-Test-Punkte fuer Mike

- **F1:** Bandwechsel → PSK-Statusbar zeigt innerhalb von ~5 Sek
  neue Daten (statt bis zu 5 Min Lag)
- **F2:** Modus-Wechsel → analog F1
- **F3:** RX-Panel UTC-Spalte zeigt Slot-Boundaries (z.B. 10:51:30
  statt 10:51:42) bei FT8
- **F4:** Bei FT4/FT2 entsprechende Boundaries
- **F5:** Karten-Dialog bei langem PSK-Server-Outage erholt sich
  binnen 10 Min statt 60 Min (BACKOFF_MAX)

## APP_VERSION

0.97.14 → 0.97.15 (Bugfix-Bundle).

## Status

V3 fertig. Bereit fuer Mike-Freigabe und Code.
