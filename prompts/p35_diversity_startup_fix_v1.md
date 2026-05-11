# P35.DIVERSITY-STARTUP-FIX — V1 (Initial-Entwurf)

**Status:** V1 — Erstentwurf
**Datum:** 2026-05-11
**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code
**Trigger:** Mike-Field-Test 11.05.2026 nach P34.DIVERSITY-DYNAMIC Code-fertig

---

## 1. Problem-Beschreibung (Mike's Worte)

> *„Das Problem tritt auf wenn die App im Diversity-Modus gestartet wird,
> dann wird automatisch Diversity-Messung initiiert, die bleibt haengen
> und alles laeuft auf ANT1. Wenn ich auf Normal schalte und wieder auf
> Diversity, laeuft es sauber durch und ANT2 wird aktiviert."*

**Symptom:** Statik-Mess-Phase haengt bei step=0/6 mit phase=measure,
Antennen-Switching geht nur auf ANT1. Trifft Dynamic-Toggle-Aktivierung
mid-flight → Dynamic-Buffer A2 bleibt komplett leer obwohl ANT2 spaeter
genutzt wird.

**Workaround der Mike heute nutzt:** Wechsel Normal → Diversity → Bug verschwindet.

---

## 2. Bug-Beweise (Mike's Live-Log 11:55-11:57)

### Phase 1: Statik-Mess haengt (radio.ip war evtl. noch None)

```
11:55:14 [ANT] SWITCH plan ANT1 phase=measure step=0/6 current_ant=A1
11:55:29 [ANT] SWITCH plan ANT1 phase=measure step=0/6 current_ant=A1
11:55:44 [ANT] SWITCH plan ANT1 phase=measure step=0/6 current_ant=A1
```

3 Slots, immer ANT1, step bleibt 0, phase bleibt measure.

### Phase 2: Mike toggle Dynamic → record_slot kommt aber alle ANT1

```
11:55:52 [DYNAMIC] Statik-Mess-Phase abgebrochen
11:55:52 [DYNAMIC] activate -> Buffer leer, Ratio 50:50
11:55:57 [DYNAMIC] record_slot ant=A1 score=82.0 buffer A1=1/5 A2=0/5
11:55:59 [ANT] SWITCH plan ANT1 phase=operate
11:56:12 [DYNAMIC] record_slot ant=A1 score=129.0 buffer A1=2/5 A2=0/5
11:56:14 [ANT] SWITCH plan ANT2 phase=operate    ← ANT2 wird gewaehlt!
11:56:27 [DYNAMIC] record_slot ant=A1 score=34.0 buffer A1=3/5 A2=0/5  ← Aber ant=A1!
11:56:42 [DYNAMIC] record_slot ant=A1 score=74.0 buffer A1=4/5 A2=0/5
11:56:57 [DYNAMIC] record_slot ant=A1 score=105.0 buffer A1=5/5 A2=0/5
```

Buffer A2 NIE gefuellt obwohl ANT2 mehrfach geswitcht.

---

## 3. Bug-Wurzel (DeepSeek-Diagnose 11.05.)

### Bug A — Statik-Mess haengt bei `radio.ip=None`

**Mechanismus:**
- `_enable_diversity` (mw_radio.py:831) setzt Phase=measure + leert Queue
- `_handle_diversity_measure` (mw_cycle.py:233ff) skipt bei `not self.radio.ip:`
  → `record_measurement` wird NIE aufgerufen
- `record_measurement` waere die einzige Stelle die `_measure_step++` macht
  (`core/diversity.py:423`)
- Folge: step bleibt 0, phase bleibt measure ↔ Statik-Pattern liefert
  immer A1 weil `choose()` bei step=0 → `("A1","A1","A2","A2","A1","A2")[0] = "A1"`
- `_on_cycle_start` fuellt Queue mit `(A1, "measure")` pro Slot

**Auslöser:** App-Start mit Diversity-Modus + radio.ip noch nicht gesetzt.
Auch denkbar: kurzer Radio-Verlust mid-flight.

### Bug B — `DynamicDiversityController.activate()` leert Queue nicht

**Mechanismus:**
- `activate()` (core/dynamic_diversity.py:78) setzt Phase=operate, Ratio=50:50
- ABER: `_diversity_ant_queue` (MainWindow-Attribut) bleibt mit
  `(A1, "measure")`-Eintraegen aus Mess-Phase gefuellt
- ABER: `_diversity_current_ant` bleibt auf "A1"
- Folge: mein P34-Hook prueft `was_phase == "operate"` → bei (A1, "measure")
  uebersprungen → bis Queue abgearbeitet ist (3 Slots) → dann (A1, "operate")
  → `choose()` liefert A1 weil `_operate_cycles=0`

**Auslöser:** Toggle Dynamic AN waehrend Statik-Mess haengt.

---

## 4. Verifizierte Code-Stellen

| Datei:Zeile | Code | Relevanz |
|---|---|---|
| `core/diversity.py:73-86` | `reset()` setzt `_phase = "measure"`, `_measure_step = 0` | Statik-Mess-Init |
| `core/diversity.py:392-433` | `record_measurement` inkrementiert `_measure_step`. NUR hier! | Step-Inkrement |
| `ui/mw_cycle.py:225-234` | `_pop_diversity_queue` — Default `("A1", "operate")` bei leerer Queue | Queue-Pop |
| `ui/mw_cycle.py:247-252` | `_handle_diversity_measure` SKIP bei `not self.radio.ip` | P21-Skip (Bug-Wurzel A) |
| `ui/mw_cycle.py:684` | `_on_cycle_start` queue.append((current_ant, phase)) | Queue-Push |
| `ui/mw_radio.py:846-849` | `_enable_diversity` setzt `_diversity_current_ant="A1"`, `_diversity_ant_queue=deque()` | Reset bei Mode-Wechsel |
| `ui/mw_radio.py:1186-1187` | `_check_diversity_preset` returnt sofort bei `not self.radio.ip` | Init-Schutz |
| `core/dynamic_diversity.py:78-100` | `activate()` — KEINE Queue/current_ant-Behandlung | Bug-Wurzel B |
| `core/dynamic_diversity.py:139-144` | `record_slot` SKIP bei `not _active` | OK |

---

## 5. Loesungs-Ansaetze

### Ansatz 1 — Sofort-Fix (Bug B): `activate()` resetted Queue + current_ant

**Umsetzung:** `_apply_dynamic_toggle` in `main_window.py` macht Queue-
Cleanup vor `activate()`. Begruendung: `DynamicDiversityController` hat
keine Referenz auf MainWindow-Attribute — saubere Trennung.

```python
# In main_window._apply_dynamic_toggle, vor activate():
if enabled and not self._dynamic_ctrl.is_active():
    # P35 Fix: Queue + current_ant resetten damit alte (A1, "measure")-
    # Eintraege weg sind und neue Slots mit choose() korrekt landen.
    with self._diversity_lock:
        self._diversity_ant_queue = deque()
        self._diversity_current_ant = "A1"
    self._dynamic_ctrl.activate()
```

**Vorteil:** Mike's „Toggle mitten in haengender Mess"-Fall geht. Klein.
**Nachteil:** Bug A (Statik-Mess haengt) bleibt latent.

### Ansatz 2 — Wurzel-Fix (Bug A): Statik darf nicht haengen

**Drei Varianten:**

**2a) `_enable_diversity` aufschieben bis radio.ip da ist**
```python
# In _enable_diversity vor reset():
if not self.radio.ip:
    self._pending_diversity_init = scoring_mode
    return
```
- Wenn radio kommt: `_on_radio_connected` triggert `_enable_diversity`
  mit pending-scoring.
- **Vorteil:** Statik-Mess laeuft erst wenn Hardware bereit.
- **Nachteil:** UI bleibt waehrend Init im „Normal"-Aussehen, Diversity-
  Aktivierung verzoegert.

**2b) Mess-Phase Step-Inkrement auch bei skipped record_measurement**
```python
# In _handle_diversity_measure bei SKIP:
self._diversity_ctrl._measure_step += 1  # Fortschritt erzwingen
# → step erreicht MEASURE_CYCLES → _evaluate() → fallback ratio "50:50"
```
- **Vorteil:** Mess endet auch ohne Daten in ~90s, danach Phase=operate.
- **Nachteil:** Liefert garantiert 50:50 weil Measurements leer sind.
  Nutzlos als Ratio-Quelle.

**2c) `_on_radio_connected` triggert Diversity-Re-Init**
```python
# Am Ende von _on_radio_connected:
if self._rx_mode == "diversity":
    scoring = getattr(self._diversity_ctrl, "scoring_mode", "normal")
    self._enable_diversity(scoring_mode=scoring)
```
- **Vorteil:** Nach Radio-Connect Diversity-Init wiederholen.
- **Nachteil:** Doppel-Init wenn Diversity vorher schon initialisiert
  (mit Cache-Reuse z.B.). Muss idempotent sein.

### Ansatz 3 — Kombination: Bug A 2a + Bug B 1

**V1-Vorschlag:** Bug B sofort (10 Zeilen) + Bug A via Variante 2a
(20 Zeilen, mit `_pending_diversity_init` Flag + `_on_radio_connected`-
Hook).

---

## 6. Akzeptanzkriterien (V1 Entwurf)

1. **AK1 — Bug A behoben:** Bei App-Start im Diversity-Modus (oder
   User klickt Diversity vor Radio-Connect): keine hangende Mess-Phase.
   Phase=measure laeuft nur wenn radio.ip vorhanden.

2. **AK2 — Bug B behoben:** Toggle Dynamic AN mitten in laufender
   Mess-Phase: Queue + current_ant werden geleert. record_slot bekommt
   korrekte Antennen-Werte (A1 UND A2).

3. **AK3 — Statik-Pipeline unangetastet:** Bestehende Tests aus
   `tests/test_diversity*.py` bleiben gruen.

4. **AK4 — Dynamic-Funktion unangetastet:** P34-Tests bleiben gruen.

5. **AK5 — Idempotenz:** Mehrfacher `_enable_diversity`-Aufruf nach
   Radio-Connect fuehrt nicht zu doppelter Initialisierung.

6. **AK6 — Regression-Test:** Neue Tests fangen genau diese Bugs ab.

7. **AK7 — Mike's Workaround (Normal→Diversity) funktioniert weiter:**
   keine Verschlechterung.

8. **AK8 — Hardware-Schutz ANT1=TX:** unveraendert.

---

## 7. Klaerungsfragen fuer Mike

**Q1 — Wie genau kam Mike in den Diversity-Modus beim Start?**
- (a) App startet bereits in Diversity (persistiert) → ABER: Code zeigt
  `_rx_mode = "normal"` im `__init__`, kein Settings-Restore.
- (b) Mike klickt Diversity-Button vor radio.ip-da → `_activate_diversity_
  with_scoring` setzt `_rx_mode="diversity"`, aber `_check_diversity_preset`
  returnt sofort bei radio.ip=None.
- (c) Mike's Setup hat irgendwo einen Auto-Wechsel zu Diversity.

→ Klaerung: Mike's exakte Schritte beim App-Start die zum Bug fuehren.

**Q2 — Was soll passieren wenn Mike Diversity klickt vor Radio-Connect?**
- (a) Diversity-Aktivierung wartet bis radio.ip da ist (Variante 2a)
- (b) Diversity-Aktivierung wird abgelehnt (Toast: „Erst Radio verbinden")
- (c) Diversity-Aktivierung soll mit „warten"-Phase laufen

**Q3 — Soll bei Wechsel Diversity Standard ↔ DX der Dynamic-Toggle
erhalten bleiben?**
- Aktuell: `_disable_diversity()` ruft `_dynamic_ctrl.deactivate()` —
  Mike muss Toggle nochmal druecken.
- Mike-Wunsch fuer Sauber: Toggle bleibt aktiv solange Diversity aktiv ist
  (egal scoring_mode). Nur bei Mode→Normal Toggle aus.

---

## 8. R1-Pruefauftraege (V1-Entwurf)

**R1, du bekommst V1+V2+Code-Files. Kritisiere V2-Prompt, nicht loese.**

1. **R1-Q1 — Ansatz 2a Realismus:**
   `_pending_diversity_init`-Flag + `_on_radio_connected`-Hook —
   sauberer Architektur-Eingriff? Gibt es Race-Bedingungen wenn
   `_on_radio_connected` mehrfach feuert?

2. **R1-Q2 — Idempotenz `_enable_diversity`:**
   Kann der Aufruf in `_on_radio_connected` mit dem User-Klick-Pfad
   kollidieren? Was wenn beide gleichzeitig laufen?

3. **R1-Q3 — Queue-Reset in `_apply_dynamic_toggle`:**
   Sicher dass `_diversity_lock` der richtige Lock ist? Brauchen
   wir `_diversity_in_operate=False` auch?

4. **R1-Q4 — Bug B isoliert testen:**
   Wie testen ohne Hardware-Sim? Vorschlag Mock-Pattern fuer Queue +
   on_cycle_start-Hook.

5. **R1-Q5 — Bug A2c als Alternative:**
   Ist Re-Init in `_on_radio_connected` eventuell einfacher als
   `_pending_diversity_init`-Flag? Trade-offs.

6. **R1-Q6 — Mike's Workaround-Mechanismus verifizieren:**
   `Normal → Diversity` ruft tatsaechlich `_enable_diversity` mit
   intaktem radio.ip auf → Queue + current_ant werden geleert →
   Bug A umgangen. Bestaetigen mit Code-Trace.

7. **R1-Q7 — Diversity ↔ DX Wechsel + Dynamic-Toggle (Q3):**
   `_disable_diversity` deactiviert Dynamic auch bei Diversity↔Diversity-
   Wechsel. UX-Bug? Welche Aenderung in `_disable_diversity`?

8. **R1-Q8 — V3-Test-Coverage:**
   Welche Tests muessen geschrieben werden (Liste mit Namen +
   Datei + Beschreibung)? Mindestens 8-10 neue Tests.

---

## 9. Out-of-Scope (V1)

- **Persistence von `_rx_mode`** in Settings (Mike's App startet aktuell
  immer in „normal" → kein Persistence-Issue).
- **Diversity-Reconnect-Verhalten** bei Radio-Verlust mid-flight (separater
  Bug, kann in eigener Iteration adressiert werden).
- **Pre-Connect-UI** (Loading-Anzeige fuer Diversity-Init) — nicht noetig
  wenn Aufschub kurz ist.

---

## 10. Geschaetzte Komplexitaet

- Code: ~30-50 Zeilen
- Tests: ~150 Zeilen (Mock-Setup fuer Queue + radio.ip)
- 3-4 atomare Commits
- Geschaetzter Zeitaufwand: 2-3h

---

## 11. Naechster Schritt

V2 (Self-Review):
- Mike's Klaerungsfragen Q1-Q3 vorlaeufig beantworten basierend auf Code
- Ansatz-Wahl (1+2a vs Alternativen) konkretisieren
- R1-Pruefauftraege schaerfen
- Lifecycle-Tabelle erstellen wie in P34-V2
