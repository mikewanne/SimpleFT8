# Bundle C — V2 (Self-Review): PSK-Backoff + RX-Panel-Slot-Times

V1 → V2 nach Self-Review aus frischer-KI-Perspektive.

## Kritische Befunde gegenueber V1

### Befund-1 (P10 KRITISCH): V1 zielt nur auf 1 von 2 PSK-Pfaden

V1 schlug Fix in `core/psk_reporter.py` vor. Code-Verifikation V2:

**Es gibt ZWEI separate PSK-Polling-Pfade:**

**Pfad A — `PSKReporterClient` (`core/psk_reporter.py`):**
- Hat exponential `_Backoff` (Factor 1.5, max 60 Min)
- Wird **NUR** vom Karten-Dialog (`ui/direction_map_widget.py:1657`)
  genutzt — wenn Mike die Karte explizit oeffnet
- Worker-Thread mit Sleep-Loop

**Pfad B — `_psk_worker` (`ui/main_window.py:949`):**
- **KEIN Backoff** — einfacher try/except, naechster Tick vom QTimer
- Wird **immer** beim App-Start gestartet (`_psk_timer.start(120000)`)
- Triggert Statusbar-Indikator (rechts unten) den Mike taeglich sieht
- Erste Abfrage nach 2 Min, dann alle 5 Min
- Bandwechsel triggert KEIN sofortiges Re-Fetch — User wartet bis
  zu 5 Min auf neue PSK-Daten fuer neues Band

**Mike's Symptom „App fragt stundenlang nicht ab" passt theoretisch
auf BEIDE Pfade — aber realistisch:**
- Pfad A: nur wenn Karte offen + Server-Outage waehrend offen
- Pfad B: viel haeufiger — bei Bandwechsel sieht Mike 5 Min lang
  alte Daten oder leere Statusbar

V1-Korrektur: **Fix muss BEIDE Pfade abdecken.**

### Korrigierter P10-Fix (V2)

**Fix-A (PSKReporterClient — Karten-Pfad):**
1. `BACKOFF_MAX_S` 3600 → 600 (10 Min). Sicherheits-Kappe.
2. Neue public `reset_backoff()`-Methode.

**Fix-B (`_psk_worker` — Statusbar-Pfad):**
3. Bei Bandwechsel/Modus-Wechsel: `_psk_timer.start(0)` triggert
   sofortiges Fetch (statt bis zu 5 Min zu warten).
   ABER: erst nach dem Settings-band-Wechsel (sonst fetched fuer
   altes Band). Im `_on_band_changed`-Handler nach
   `self.settings.set("band", band)` einfuegen.
4. Plus: `_psk_first_fetch = True` setzen damit naechste Iteration
   wieder auf 2-Min-Schnellinterval geht (falls Server lange
   ausfaellt).

**Wichtig Reihenfolge:** in `_on_band_changed` muss
`settings.set("band", band)` ZUERST erfolgen, dann
`_psk_timer.start(0)` → Worker liest neues Band aus settings.

Identisch in `_on_mode_changed`.

### Befund-2 (P10 Hook-Stelle)

V1 wollte Hook in `mw_radio._on_band_changed` einbauen. V2 verifiziert:
- `mw_radio._on_band_changed` Z.359: `self.settings.set("band", band)`
- Direkt danach kann der PSK-Trigger laufen
- Aber: `_psk_timer` und `_psk_worker` sind in `main_window.py` —
  Zugriff aus `mw_radio` via `self._psk_timer` ist OK (mw_radio ist
  Mixin von MainWindow).

### Befund-3 (P13 OK)

V1 hat den P13-Fix korrekt identifiziert:
- `_slot_start_ts` wird vom Decoder gesetzt (`core/decoder.py:345`)
- `rx_panel.add_message` Z.292 nutzt es nicht
- Fix: bevorzugte Slot-Quelle in `add_message`

Aber V2-Add: muss `add_message` der einzige Eintrag-Pfad sein? grep
nach anderen `setItem(..., COL_UTC, ...)`-Aufrufen:

### Befund-4 (P13 Settings-Reihenfolge fuer rx_history_store)

`rx_history_store.py` cached RX-Eintraege (v0.73). Wenn die UTC-Zeile
durchgehend Wall-Time war, hat der Cache jetzt gemischte Werte —
neue Slot-Boundaries + alte Wall-Times. Sortierung in History bleibt
ok weil HHMMSS-Vergleich. Aber: ist da was zu beachten beim Persist?

→ V2: rx_history_store speichert vermutlich nur den Anzeige-Wert
nicht den Slot-Boundary. Kein Schaden. Pruefen.

### Befund-5 (V1 R1-P10 Thread-Safety unklar)

V1 hat eine Thread-Safety-Risiko-Frage aufgelistet aber nicht
beantwortet. V2-Klaerung:

`_Backoff.reset()` setzt nur `self.current_s = self.base_s`. Single
attribute assignment in Python — atomar bei CPython (GIL). Read in
`_run_loop` Z.291 `self._backoff.fail()` ist auch atomic. **Kein
Race** auf der Datenebene.

Worst-Case: `reset_backoff()` mid-sleep gerufen → laufender Sleep
wartet bis Ende des aktuellen Intervalls. Mit BACKOFF_MAX=600 sind
das im Worst-Case 10 Min Wartezeit nach Reset. Akzeptabel — Mike's
echtes Pain-Point ist 60 Min, nicht 10 Min.

Wenn Mike eine echte Sub-Minute-Wartezeit braucht: zusaetzliches
Event `_backoff_reset_event = threading.Event()` einbauen das den
Sleep-Loop interrupted. Aber das ist V2-Overengineering — 10 Min
warst-case Latenz ist gut genug.

### Befund-6 (R1-P13 Decoder-Pfad einzige Quelle?)

V1 fragte ob Decoder der einzige `_slot_start_ts`-Setter ist. grep
unten zeigt nur `core/decoder.py:345`. Andere Pfade fuettern keine
msg an rx_panel.add_message — sicher.

Beispiel-Tests muessen evtl. FT8Message mock-en mit `_slot_start_ts`.
V2-Tests entsprechend.

### Befund-7 (Mike-KISS-Klausel)

V1 hatte 3 Optionen aus Mike's TODO erwaehnt:
1. BACKOFF_MAX senken (uebernommen)
2. Reset-Button in UI (verworfen — UI-Aufwand)
3. Auto-Reset bei Band/Modus (uebernommen)

V2 bleibt bei dieser Wahl. Aber: V2-Fix-B (Statusbar-Pfad trigger)
ist auch automatisch — also Option 3 erweitert.

## Aktualisierte Akzeptanzkriterien

### P10 — PSK-Backoff-Reset + Statusbar-Pfad-Trigger

- AK1: `BACKOFF_MAX_S` = 600 (10 Min) in `core/psk_reporter.py`.
- AK2: `PSKReporterClient.reset_backoff()` public Methode.
- AK3 (Karten-Pfad): Bandwechsel ruft `reset_backoff()` (wenn
  `_psk_client` existiert).
- AK4 (Karten-Pfad): Modus-Wechsel ruft `reset_backoff()`.
- AK5 (Statusbar-Pfad): Bandwechsel triggert sofortiges
  `_psk_worker`-Fetch (via `_psk_timer.start(0)`).
- AK6 (Statusbar-Pfad): Modus-Wechsel triggert sofortiges Fetch.
- AK7: Bestehende `_Backoff.reset/fail`-Logik unveraendert.

### P13 — RX-Panel-Slot-Times

- AK1: Wenn `msg._slot_start_ts` gesetzt, UTC-Spalte = Slot-Boundary.
- AK2: FT4 (7.5s) / FT2 (3.8s) zeigen entsprechende Boundaries.
- AK3: Wenn `_slot_start_ts` fehlt, Fallback wie bisher.
- AK4: Bestehendes Sort-Verhalten korrekt.
- AK5: rx_history_store nicht betroffen.

## Erweiterte Risiko-Liste fuer R1

- **R1-1 (P10 Fix-B)**: `_psk_timer.start(0)` — sofortiger Trigger.
  Gibt es Race wenn alter `_psk_worker`-Thread noch laeuft? V1
  startet Thread mit `threading.Thread(daemon=True).start()` in
  Z.947 — kein Lock/Synchronisation. Wenn _on_band_changed mid-Fetch
  triggert → 2 Worker laufen parallel. Aktueller Code hat schon
  diesen Race (5-Min-Timer waehrend Fetch). V2 macht es haeufiger
  aber nicht schlimmer.
- **R1-2 (P10 Fix-B)**: Settings-Band muss gesetzt sein VOR
  `_psk_timer.start(0)`. Reihenfolge in `_on_band_changed`
  Z.359-360: `settings.set("band", band)` → spaeter im selben
  Slot kommt der PSK-Trigger. OK wenn nach Z.359 eingefuegt.
- **R1-3 (P13)**: Performance — `getattr(msg, '_slot_start_ts',
  None)` + `time.strftime` pro Message. Bei 100+ Messages/Slot
  vernachlaessigbar.
- **R1-4 (P13)**: Was wenn `_slot_start_ts` ein gueltiger float ist
  aber 0? `int(0 / 15) % 2 == 0`. `time.strftime(...gmtime(0))` =
  `1970-01-01 00:00:00`. Edge-Case in Tests. Aber kommt nur bei
  Mock-Bug vor — Decoder setzt nie 0.

## V1 → V2 Aenderungen

- P10 Fix erweitert auf **beide PSK-Pfade** (PSKReporterClient +
  `_psk_worker`).
- P10 Fix-B neu: `_psk_timer.start(0)` Trigger bei Band/Modus-Wechsel
  in mw_radio Hooks.
- P10 AK5+AK6 neu fuer Statusbar-Pfad.
- P13: Klarstellung dass Decoder einzige Quelle, kein
  rx_history_store-Risiko.
- Thread-Safety V1-Fragen geklaert.

## Status

V2 bereit fuer R1-Review.
