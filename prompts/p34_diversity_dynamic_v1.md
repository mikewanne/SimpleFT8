# P34.DIVERSITY-DYNAMIC — V1 (Entweder-Oder-Architektur)

**Status:** V1 — Neu-Entwurf nach Klaerungs-Dialog 2026-05-11
**Vorgaenger-Versionen:** V1+V2+R1 mit „parallel"-Annahme verworfen
(`_OLD_parallel.md`-Dateien archiviert)
**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code

---

## 1. Ziel + Vision

Diversity-Antennen-Verhaeltnis im **laufenden Betrieb** kontinuierlich
nachfuehren, statt es nur einmalig in der 90-Sek-Mess-Pipeline festzulegen.

**Mike-Vision in 2 Saetzen:**

> *„Ich schalte einen Schalter ein, ab dem Moment passt sich das
> Antennen-Verhaeltnis live an die Bedingungen an — Wind, Wetter,
> Ausbreitung. Kein 90-Sekunden-Hang alle Stunde, kein UI-Sperrer, kein
> Anhalten des Betriebs."*

### 1.1 Stufen-Plan

| Stufe | Status | Was |
|---|---|---|
| **1 (V1-V3, jetzt)** | bauen | Neuer Dynamic-Modus parallel zur Statik. Toggle in Settings. ENTWEDER-ODER-Architektur. |
| **2 (spaeter, eigener Workflow)** | nach Feldtest-OK | Statische Pipeline entfernen. Dynamic wird Standard. Toggle weg. |

---

## 2. Architektur — ENTWEDER-ODER (Kern-Entscheidung)

### 2.1 Grundprinzip

**Es gibt keinen parallelen Betrieb.** Zu jedem Zeitpunkt ist EIN System
aktiv:

- Toggle AUS → **nur die statische Pipeline arbeitet** (heutiges Verhalten,
  100% unangetastet)
- Toggle AN  → **nur Dynamic arbeitet** (statische Pipeline schweigt komplett)

Dies eliminiert die Konflikte:
- Kein „wer setzt zuletzt das Verhaeltnis"
- Keine 1h-Re-Mess waehrend Dynamic laeuft (UI-Sperre faellt weg)
- Klare Code-Trennung — Statik-Klasse 100% in Ruhe, Dynamic-Klasse eigenstaendig

### 2.2 Verhalten Toggle AUS

```
App-Start:
  → Statische Pipeline initialisiert (Phase=measure, 90-Sek-Mess, UI-Sperre)
  → Verhaeltnis steht (z.B. 70:30)
  → Phase=operate

Im Betrieb:
  → Verhaeltnis bleibt 1 Stunde lang stabil
  → Nach 1h → statische Re-Mess (90 Sek UI-Sperre)
  → neues Verhaeltnis

Bandwechsel/Modus-Wechsel:
  → wie heute, statische Pipeline misst neu

Dynamic-Modul:
  → existiert als Klasse, aber `_active=False` — keine Daten, kein Effekt
```

**= 100% heutiges Verhalten.**

### 2.3 Verhalten Toggle AN

```
Toggle AN gedrueckt:
  → Aktuelles Verhaeltnis wird auf 50:50 zurueckgesetzt (Reset)
  → Dynamic-Schieberegister leer
  → Statische 1h-Frist STOP (kein Re-Mess solange Dynamic AN)
  → Dynamic faengt an Slot-fuer-Slot Daten zu sammeln

Im Betrieb:
  → Solange Schieberegister noch nicht voll (je 5 Werte pro Antenne):
    bleibt 50:50
  → Schieberegister voll (~3 Min):
    Dynamic uebernimmt, setzt Verhaeltnis basierend auf Median
  → Pro neuem Slot: Auswertung, ggf. Verhaeltnis-Wechsel
  → Keine UI-Sperre, keine Re-Mess

Bandwechsel/Modus-Wechsel:
  → Verhaeltnis zurueck auf 50:50
  → Schieberegister leer
  → In ~3 Min wieder aktiv

Toggle AUS gedrueckt:
  → Aktuelles Verhaeltnis bleibt zunaechst (z.B. 65:35 von Dynamic)
  → Dynamic-Modul deaktiviert
  → Statische 1h-Frist faengt wieder an zu ticken (vom Toggle-AUS-Moment)
  → Bei naechstem Bandwechsel/Modus-Wechsel/1h-Frist → normale Statik-Mess
```

### 2.4 Toggle-Wechsel = 50:50-Reset (klare KISS-Regel)

**Beide Richtungen:**
- Toggle AUS → AN: 50:50-Reset, Dynamic-Schieberegister leer, frischer Start
- Toggle AN → AUS: kein Reset des Verhaeltnisses (Dynamic-Letztwert bleibt
  stehen bis naechste Statik-Mess), aber Dynamic-Modul deaktiviert

**Begruendung Reset bei AUS→AN:** verhindert dass altes Statik-Verhaeltnis
mit Dynamic-Daten kollidiert. Sauberer Neustart.

---

## 3. Architektur — Modul-Trennung

### 3.1 Neues Modul: `core/diversity_dynamic.py`

Eigenstaendige Klasse `DynamicDiversityController`. **KEINE Aenderung an
`core/diversity.py` Mess-Pipeline.** Die einzige Beruehrungsstelle: Dynamic
setzt `DiversityController.ratio` + `.dominant` direkt (1 Property-Write
unter Lock).

### 3.2 Code-Wiederverwendung ueber Helper

Statt Code in der statischen Klasse zu fuschen wandern die wiederverwend-
baren Teile als **Modul-Funktionen** in `core/diversity.py` (nicht in der
Klasse — saubere Trennung):

```python
# core/diversity.py — neue Modul-Funktionen, KEINE Klassen-Aenderung

def compute_slot_score(messages) -> float:
    """Score eines Slots: sum(max(0, snr+30)) ueber SNR>-20-Stationen.

    Gleiche Formel wie statische Mess-Pipeline (mw_cycle.py:239-241).
    Beide Klassen (statisch, dynamic) rufen diese Funktion auf.
    """
    valid = [m for m in (messages or []) if m.snr is not None and m.snr > -20]
    return sum(max(0.0, float(m.snr + 30)) for m in valid) if valid else 0.0


def evaluate_ratio(median_a1: float, median_a2: float,
                    threshold: float = 0.08,
                    min_peak: float = 5.0) -> tuple[str, str | None]:
    """Verhaeltnis-Entscheidung aus 2 Medianen. Gleicher Algorithmus wie
    `DiversityController._evaluate()` (Z. 537-562). Beide nutzen diese.
    """
    peak = max(median_a1, median_a2)
    if peak <= min_peak:
        return "50:50", None
    rel_diff = abs(median_a1 - median_a2) / peak
    if rel_diff < threshold:
        return "50:50", None
    return ("70:30", "A1") if median_a1 >= median_a2 else ("30:70", "A2")
```

→ `DiversityController._evaluate()` ruft die Helper auf (statt eigene Logik
zu halten). `DynamicDiversityController._evaluate()` ruft die gleichen Helper
auf. Eine Formel, zwei Aufrufer.

### 3.3 Hook-Punkte

| Hook | Datei:Zeile | Aufgabe |
|---|---|---|
| Slot-Daten erfassen | `ui/mw_cycle.py` `_on_cycle_decoded` Z.97 | wenn Dynamic AN: aktive Antenne + Slot-Score an `dynamic_ctrl.record_slot()` |
| Settings-Toggle | `config/settings.py` + `ui/settings_dialog.py` | Toggle in „Diversity"-Bereich, NICHT persistiert |
| Toggle AUS→AN | Settings-Slot | `dynamic_ctrl.activate()` + Statik-Re-Mess pausieren |
| Toggle AN→AUS | Settings-Slot | `dynamic_ctrl.deactivate()` + Statik-Re-Mess wieder ticken lassen |
| Bandwechsel | `ui/mw_radio.set_band()` | wenn Dynamic AN: `dynamic_ctrl.reset()` |
| Modus-Wechsel | `ui/mw_radio.set_mode()` | wenn Dynamic AN: `dynamic_ctrl.reset()` |
| Diversity an→aus | `ui/mw_radio._enable_diversity(False)` | `dynamic_ctrl.deactivate()` (kein Diversity = kein Dynamic) |
| scoring_mode-Wechsel | `core/diversity.py` `scoring_mode`-Setter | wenn Dynamic AN: `dynamic_ctrl.reset()` |
| Statusbar-Faerbung | `ui/main_window._update_statusbar()` | bei Dynamic AN: bestehendes Verhaeltnis-Label in BLAU |
| Controller-Instanz | `ui/main_window.__init__` | `self.dynamic_ctrl = DynamicDiversityController(...)` |
| Statik 1h-Frist unterdruecken | `core/diversity.py.should_remeasure()` | bei Dynamic AN: returnt immer False |

**KEINE Aenderung an:** `core/omni_cq.py` (komplett entkoppelt),
`core/preset_store.py` (keine Persistenz), `core/diversity.py` Mess-Pipeline
selbst.

---

## 4. Datenerfassung (slot-fuer-slot)

### 4.1 Was

Pro Slot:
- **Antenne** (A1 oder A2) — aus `_pop_diversity_queue()` Ergebnis in mw_cycle
  (race-frei vom Slot-Start)
- **Slot-Score** — Helper `compute_slot_score(messages)`

### 4.2 Wann erfasst (Bedingungen, ALLE muessen wahr sein)

- Dynamic-Toggle = AN
- Diversity-Modus aktiv
- RX-Slot (kein TX-Slot)
- mind. 1 Station mit SNR > -20 dB dekodiert (sonst Score=0, unbrauchbar)

Falls eine Bedingung nicht erfuellt: kein Eintrag.

### 4.3 Speicher

```python
self._buffer = {
    "A1": collections.deque(maxlen=5),
    "A2": collections.deque(maxlen=5),
}
```

5er-Schieberegister pro Antenne. FIFO. Neuer Wert links rein, alter rechts raus.
**RAM-only, keine Disk-Persistenz.**

---

## 5. Auswertung

### 5.1 Wann

Nach **jedem** neuen Slot-Eintrag — VORAUSGESETZT beide Buffer voll (je 5).
Davor: 50:50 bleibt, keine Auswertung.

### 5.2 Algorithmus

```python
def _evaluate(self):
    if len(self._buffer["A1"]) < 5 or len(self._buffer["A2"]) < 5:
        return  # noch nicht beide voll
    m1 = statistics.median(self._buffer["A1"])
    m2 = statistics.median(self._buffer["A2"])
    new_ratio, new_dominant = evaluate_ratio(m1, m2)  # Helper aus diversity.py
    if (new_ratio, new_dominant) != (self._diversity_ctrl.ratio,
                                      self._diversity_ctrl.dominant):
        with self._lock:
            self._diversity_ctrl.ratio = new_ratio
            self._diversity_ctrl.dominant = new_dominant
        self.ratio_changed_dynamic.emit(new_ratio)
```

### 5.3 Schwellen

- `THRESHOLD = 0.08` — gleich wie Statik
- `MIN_PEAK_SCORE = 5.0` — gleich wie Statik

---

## 6. UI

### 6.1 Settings-Toggle

- **Ort:** Settings-Dialog → „Diversity"-Bereich (gleicher Tab wie statische
  Schwellen, unter den bestehenden Werten)
- **Wortlaut:** „Antennen-Verhaeltnis dynamisch anpassen (Testphase)"
- **Tooltip:** „Statt 1× pro Stunde wird das Verhaeltnis im laufenden Betrieb
  kontinuierlich nachjustiert (~jede Minute). Nur im Diversity-Modus aktiv."
- **Default:** AUS
- **Persistenz:** KEINE — bei jedem App-Start auf AUS. Mike muss aktiv
  einschalten fuer jeden Testlauf.

### 6.2 Statusbar — Blau-Faerbung

Das bestehende Verhaeltnis-Label in der Statusbar (zeigt z.B. „70:30") wird:

- **Toggle AUS:** normale Schrift (heute weiss / Standard-Farbe)
- **Toggle AN + Buffer voll + Dynamic aktiv:** **Blau** (z.B. `#3399CC`)

Keine zusaetzlichen Texte. Mike sieht „70:30" und an der Farbe: weiss = statisch
gemessen, blau = von Dynamic gesetzt. Sparsam, eindeutig.

### 6.3 Antennen-Panel

Bleibt 1:1 unangetastet.

---

## 7. Akzeptanzkriterien (verbindlich)

1. **AK1 — Statik-Pipeline 100% unangetastet bei Toggle AUS:** Tests aus
   `tests/test_diversity*.py` bleiben gruen ohne Aenderung.
2. **AK2 — Statik-Klasse Code-Aenderung minimal:** Nur 2 Helper-Funktionen
   neu (Modul-Ebene), `_evaluate()` ruft den Helper auf. Keine neuen
   Properties, kein Flag.
3. **AK3 — Toggle-Verhalten ENTWEDER-ODER:** Toggle AUS → Statik aktiv,
   Dynamic schweigt. Toggle AN → Dynamic aktiv, Statik 1h-Frist unterdrueckt.
4. **AK4 — Toggle AUS→AN:** Verhaeltnis auf 50:50, Schieberegister leer,
   Dynamic startet frisch.
5. **AK5 — Toggle AN→AUS:** Aktuelles Verhaeltnis bleibt, Dynamic schweigt,
   Statik-Frist tickt wieder.
6. **AK6 — Schieberegister:** `deque(maxlen=5)` pro Antenne, FIFO.
7. **AK7 — Auswertungs-Gate:** `_evaluate()` nur wenn beide Buffer voll.
8. **AK8 — Pro-Slot-Auswertung:** Sobald voll, nach jedem neuen Slot pruefen.
9. **AK9 — Schwellen identisch zur Statik:** `THRESHOLD=0.08`,
   `MIN_PEAK_SCORE=5.0`.
10. **AK10 — Reset-Trigger bei Dynamic AN:** Bandwechsel, Modus-Wechsel,
    scoring_mode-Wechsel, Diversity an→aus → Schieberegister leer + 50:50.
11. **AK11 — Kein Reset bei:** OMNI-CQ Start/Stop, QSO Start/Stop, Toggle
    AN→AUS (Verhaeltnis bleibt nur Modul aus).
12. **AK12 — Statik-1h-Frist bei Toggle AN unterdrueckt:**
    `DiversityController.should_remeasure()` returnt immer False.
13. **AK13 — Keine Persistenz:** Buffer + Toggle RAM-only. App-Start =
    leer + AUS.
14. **AK14 — Blau-Faerbung:** Statusbar-Verhaeltnis-Label blau wenn Dynamic
    aktiv UND Buffer voll. Sonst normale Farbe.
15. **AK15 — Threading:** Buffer-Operationen + ratio-Setter unter
    `RLock` (`_lock` im Dynamic-Controller). Signal-Emit via
    `Qt.QueuedConnection` an GUI-Thread.
16. **AK16 — Hardware-Schutz:** `radio.set_tx_antenna("ANT1")` unangetastet.
    Verhaeltnis nur RX-Verteilung.

---

## 8. Out-of-Scope (bewusst nicht in V1)

- **Persistenz** (Buffer oder Toggle auf Disk)
- **Mini-Graph** der letzten 5 Werte
- **Glow / Pulse-Animation** bei Verhaeltnis-Wechsel
- **Stufe 2** (Statik entfernen) — eigener Workflow spaeter
- **Hunt/Normal-Mode** — nur 1 Antenne aktiv, kein Vergleich moeglich
- **Sampling-Tricks** bei extremen Ratios
- **Konflikt-Loesungs-Logik zwischen Statik und Dynamic** — durch
  ENTWEDER-ODER-Architektur eliminiert
- **Buffer-Leerung bei statischer Re-Mess** — kommt nicht vor, weil
  Re-Mess bei Dynamic AN unterdrueckt ist

---

## 9. Akzeptable Trade-Offs (bewusst entschieden)

1. **Asymmetrische Buffer-Alter bei extremen Ratios (70:30, 30:70):**
   Worst-Case ~3.3 Min „alt" auf der seltenen Antenne. Akzeptiert weil
   noch 18× reaktiver als heutige 1h-Statik.
2. **Median statt arithmetisches Mittel:** Mike sprach von „Durchschnitt".
   Wir nehmen Median (robuster, 1:1 wie Statik). Wenig Unterschied bei 5
   Werten, ausser bei 1 Outlier — dann ist Median klarer Vorteil.
3. **Toggle nicht persistiert:** Bewusst — schuetzt vor vergessenem-an-Bugs
   waehrend Testphase.
4. **Reset bei jedem Toggle-AUS→AN:** Verhaeltnis sofort auf 50:50 statt
   altes Statik-Verhaeltnis weiterzunutzen. Saubere Trennung.
5. **Statik-1h-Frist unterdrueckt bei Dynamic AN:** Keine 90-Sek-UI-Sperren
   mehr. Falls Dynamic spinnt → Toggle AUS → Statik laeuft wieder normal.
6. **Score-Formel uebernommen:** Bewaehrte Formel aus statischer Pipeline
   via Helper. Eine Formel, zwei Aufrufer.

---

## 10. Geschaetzte Komplexitaet

| Bereich | LOC (geschaetzt) |
|---|---|
| `core/diversity.py` Helper-Funktionen | ~25 |
| `core/diversity.py` `_evaluate()` Refactor auf Helper | ~10 |
| `core/diversity.py` `should_remeasure()` Dynamic-Check | ~3 |
| `core/diversity_dynamic.py` neu | ~120 |
| `ui/mw_cycle.py` Hook | ~15 |
| `ui/mw_radio.py` Reset-Hooks + Diversity-aus | ~15 |
| `ui/main_window.py` Init + Statusbar-Blau | ~30 |
| `ui/settings_dialog.py` Toggle + Tooltip | ~25 |
| `config/settings.py` RAM-Property | ~10 |
| Tests | ~300 |
| **Total** | **~550** |

| Commit | Inhalt |
|---|---|
| C1 | `core/diversity.py` Helper `compute_slot_score` + `evaluate_ratio`, `_evaluate()` Refactor (keine Verhaltensaenderung) |
| C2 | Tests fuer Helper + Refactor-Verifikation (alle bestehenden Tests bleiben gruen) |
| C3 | `core/diversity_dynamic.py` neue Klasse + RLock + Reset-API |
| C4 | Tests `tests/test_diversity_dynamic.py` (Unit) |
| C5 | UI-Hooks: `mw_cycle`, `mw_radio`, `main_window` Init |
| C6 | Settings-Dialog Toggle + Tooltip + RAM-Property |
| C7 | Statusbar-Blau-Faerbung |
| C8 | `should_remeasure()` Dynamic-Check + Integration-Tests |
| C9 | APP_VERSION-Bump + HISTORY/HANDOFF/CLAUDE/TODO |

**Total: 9 atomare Commits, geschaetzter Zeitaufwand ohne Workflow-Pausen
~6-8h Code+Tests.**

---

## 11. Vergleich zu V1-OLD (parallel-Architektur)

Was wir uns sparen durch ENTWEDER-ODER:

| V1-OLD Problem | Loesung durch ENTWEDER-ODER |
|---|---|
| Wer setzt zuletzt das Verhaeltnis (Statik vs Dynamic Race)? | Eliminiert — nur einer aktiv |
| Statik-Re-Mess mitten in Dynamic-Betrieb | Re-Mess unterdrueckt bei Dynamic AN |
| Buffer-Leerung-Frage bei Phase-Wechsel | Faellt weg — kein Phase-Wechsel waehrend Dynamic AN |
| 3 R1-Prueffragen zur Statik-Kollision (R1-Q6, Q7, ein Teil von Q8) | Geloest durch Architektur |
| Komplexer Lifecycle (V2 Tabelle mit 13 Zeilen) | Halbiert — keine Phase-measure-Eintraege noetig |
| AC fuer „Statik schreibt, Dynamic schreibt sofort drueber" | Faellt weg |

→ V1-NEU ist deutlich kuerzer und klarer als V1-OLD.

---

## 12. Naechster Schritt

V2 (Self-Review) — frische KI-Brille, sucht Luecken in der NEUEN Architektur.
Erwartung: kuerzer als V2-OLD weil weniger Konflikt-Szenarien.

Dann R1 (DeepSeek) mit V1-NEU + V2-NEU.
Dann V3 (Final-Spec mit Implementierungs-Plan + Test-Liste +
Field-Test-Checkliste).
