# P34.DIVERSITY-DYNAMIC — V1 (komplette Spezifikation)

**Status:** V1 — alle Mike-Klaerungen eingearbeitet, bereit fuer Self-Review (V2)
**Datum:** 2026-05-11
**Autor:** Claude (mit Mike-Spec aus Klaerungs-Dialog)
**Workflow:** V1 → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code

---

## 1. Ziel + Vision

### 1.1 Kurz

Diversity-Antennen-Verhaeltnis (ratio = `50:50` / `70:30` / `30:70`)
**im laufenden Betrieb kontinuierlich** nachfuehren statt nur einmalig
in der statischen Mess-Pipeline.

### 1.2 Mike-Vision in 3 Saetzen

> *„Ich starte die App, mache OMNI-CQ oder Hand-Funk im Diversity-Modus,
> und das Antennen-Verhaeltnis passt sich live an die Bedingungen an —
> Wind drueckt ANT2 schlechter? In 3 Minuten merkt das System es und
> stellt um. Ich muss nichts anklicken, nichts neu einmessen.
> Wenn dynamic gut laeuft (Feldtest grun), fliegt die statische
> Berechnung in einem spaeteren Schritt komplett raus."*

### 1.3 Stufen-Plan

| Stufe | Status | Was |
|---|---|---|
| **1 (V1-V3 dieser Plan)** | bauen | Dynamic parallel zur Statik. Toggle in Settings (Default AUS). Statik unangetastet. |
| **2 (spaeter, eigener Workflow)** | nach Feldtest-OK | Statische Pipeline entfernen. Dynamic wird Default. Toggle weg. |

---

## 2. Architektur-Ueberblick

### 2.1 Neues Modul: `core/dynamic_diversity.py`

Eigenstaendige Klasse `DynamicDiversityController`. Keine Aenderung an
`core/diversity.py` (statische Pipeline bleibt 1:1 erhalten). Der neue
Controller setzt aber `DiversityController.ratio` + `.dominant` direkt
wenn er einen Wechsel beschliesst — das ist die einzige Beruehrungsstelle.

### 2.2 Datenfluss

```
Slot N (Decoder-Thread)
  → mw_cycle._on_cycle_decoded
    → ermitteln: welche Antenne war im Slot aktiv? (DiversityController.choose-Result
       vom Slot-Start, bereits in mw_cycle gespeichert)
    → ermitteln: Slot-Score = sum(SNR+30) ueber alle dekodierten Stationen
    → dynamic_ctrl.record_slot(ant, score)
      → in 5er-Schiebepuffer der jeweiligen Antenne schieben (deque maxlen=5)
      → wenn beide Puffer voll → _evaluate() → Ratio ggf. setzen + Signal emittieren
  → GUI-Thread: Statusbar-Badge per QueuedConnection updaten
```

### 2.3 Hook-Punkte (konkret, Datei:Zeile)

| Hook | Datei:Zeile | Aufgabe |
|---|---|---|
| Slot-Daten erfassen | `ui/mw_cycle.py` `_on_cycle_decoded` | aktive Antenne + Score weitergeben |
| Settings-Toggle | `config/settings.py` + `ui/settings_dialog.py` | Toggle in „Diversity"-Bereich, NICHT persistiert |
| Band-Wechsel-Reset | `ui/mw_radio.set_band()` | `dynamic_ctrl.reset()` |
| Modus-Wechsel-Reset | `ui/mw_radio.set_mode()` | `dynamic_ctrl.reset()` |
| Mode→Normal Stop | `ui/mw_radio._enable_diversity(False)` | `dynamic_ctrl.deactivate()` |
| Statusbar-Badge | `ui/main_window._update_statusbar()` | Anzeige `dyn 72:28` wenn aktiv |
| Controller-Instanz | `ui/main_window.__init__` | `self.dynamic_ctrl = DynamicDiversityController(diversity_ctrl)` |

**KEINE Hooks noetig in:** `core/omni_cq.py` (entkoppelt!), `core/preset_store.py`
(keine Persistenz), `core/diversity.py` (Statik unangetastet).

---

## 3. Spezifikation Datenerfassung

### 3.1 Was wird erfasst

Pro Slot (15s FT8 / 7.5s FT4 / 3.8s FT2):

1. **Antenne:** A1 oder A2 — aus dem aktuell aktiven Diversity-Pattern
   (`DiversityController.choose()` Result, der vom Slot-Start bekannt ist
   und in mw_cycle bereits zur Antennen-Steuerung verwendet wurde).
2. **Score:** `sum(SNR+30)` ueber alle in diesem Slot dekodierten
   Stationen — identisch zur Formel der statischen Pipeline
   (`core/diversity.py:5-13`).

### 3.2 Wo gespeichert

Zwei `collections.deque(maxlen=5)`:

```python
self._buffer = {
    "A1": deque(maxlen=5),  # 5 letzte Slot-Scores fuer ANT1
    "A2": deque(maxlen=5),  # 5 letzte Slot-Scores fuer ANT2
}
```

Schiebepuffer, FIFO. Neuer Wert kommt links rein, alter rechts raus.
Kein Disk-Write — RAM-only.

### 3.3 Wann erfasst

Slot-Daten landen im Puffer **wenn und nur wenn** ALLE Bedingungen erfuellt:

- Dynamic-Toggle = AN
- Diversity-Modus aktiv (`mw_radio._diversity_enabled = True`)
- Diversity-Phase = "operate" (statische Mess ist durch)
- TX-Slot ausgeschlossen (in TX-Slots empfaengt nur eine Antenne via
  Loopback bzw. nichts — keine vergleichbaren Daten)
- mind. 1 Station dekodiert (0-Stations-Slot ergibt Score=0, unbrauchbar
  als Vergleichsbasis — Mike's Aussage: „TX = kein Eintrag")

### 3.4 Was passiert in den Bedingungen

- **OMNI-CQ an/aus:** komplett egal. Dynamic ist entkoppelt.
- **Normal-Mode (statt Diversity):** Dynamic aus (nur 1 Antenne aktiv,
  kein Vergleich moeglich).
- **QSO aktiv:** Datenerfassung laeuft weiter. Auch waehrend QSO empfaengt
  die alternierende Antenne mit. Cancel-Schutz: nur RX-Slots zaehlen.
- **Diversity-Mess (Phase „measure"):** Dynamic-Toggle wird ignoriert
  bis Phase wieder „operate" ist. Buffer wird NICHT geleert (R1 muss
  pruefen ob das richtig ist — V2 vermerkt es).

---

## 4. Spezifikation Auswertung + Ratio-Setzen

### 4.1 Wann auswerten

Nach **jedem** neuen Slot-Eintrag wird `_evaluate()` aufgerufen — VORAUSGESETZT
**beide Puffer sind voll** (je 5 Werte). Davor: keine Auswertung,
Ratio bleibt beim Startwert oder beim letzten statischen Wert.

### 4.2 Algorithmus

```python
def _evaluate(self):
    m1 = statistics.median(self._buffer["A1"])
    m2 = statistics.median(self._buffer["A2"])
    peak = max(m1, m2)

    if peak <= MIN_PEAK_SCORE:  # 5.0 wie in core/diversity.py:37
        new_ratio, new_dominant = "50:50", None
    else:
        rel_diff = abs(m1 - m2) / peak
        if rel_diff < THRESHOLD:  # 0.08 wie in core/diversity.py:33
            new_ratio, new_dominant = "50:50", None
        elif m1 >= m2:
            new_ratio, new_dominant = "70:30", "A1"
        else:
            new_ratio, new_dominant = "30:70", "A2"

    if (new_ratio, new_dominant) != (self.ratio, self.dominant):
        old = (self.ratio, self.dominant)
        self.ratio, self.dominant = new_ratio, new_dominant
        self._diversity_ctrl.ratio = new_ratio       # statische Klasse uebernehmen
        self._diversity_ctrl.dominant = new_dominant # damit choose() neue Werte nutzt
        self.ratio_changed_dynamic.emit(old[0], new_ratio)
        logger.info("[Dynamic] Ratio-Wechsel: %s → %s (m1=%.1f m2=%.1f diff=%.1f%%)",
                    old[0], new_ratio, m1, m2, rel_diff * 100)
```

### 4.3 Schwellen

- `THRESHOLD = 0.08` (8% relative Differenz) — identisch zur statischen
  Pipeline. Schutz vor Pendeln durch Median-Glaettung ueber 5 Werte.
- `MIN_PEAK_SCORE = 5.0` — bei zu schwachem Empfang Fallback 50:50.

### 4.4 Vor Buffer-voll

Solange noch nicht beide Puffer 5 Eintraege haben:
- `ratio` und `dominant` des `DiversityController` bleiben unveraendert
  (vom letzten statischen Mess-Resultat ODER 50:50 wenn nichts vorhanden).
- Die Datenerfassung laeuft trotzdem (Puffer fuellt sich).

---

## 5. Spezifikation Reset / Lifecycle

### 5.1 Trigger fuer Buffer-Leerung (`reset()`)

- **Bandwechsel** (`mw_radio.set_band()` neue Band-Konstante): Puffer beider
  Antennen leer → DiversityController wird statisch auf 50:50 gesetzt →
  in <3 Min ist Puffer wieder voll, erste dynamische Bewertung.
- **Modus-Wechsel** (FT8↔FT4↔FT2 in `mw_radio.set_mode()`): wie Bandwechsel.
- **Diversity an→aus** (`_enable_diversity(False)`): Puffer leer + Dynamic
  intern deaktiviert (`_active=False`). Bei Wieder-An: fresh start.

### 5.2 Trigger die KEIN Reset ausloesen

- **Toggle Settings AN→AUS:** Puffer behalten (falls Mike sofort wieder
  einschaltet). Aber: `_active=False`, kein neuer Eintrag bis wieder AN.
- **OMNI-CQ Start/Stop/Pause:** komplett entkoppelt, kein Effekt auf
  Dynamic-Buffer oder Active-State.
- **QSO Start/Stop:** kein Effekt. Datenerfassung laeuft RX-Slot-weise weiter.
- **Statische Re-Mess (1h-Frist):** kein Effekt auf Dynamic. ABER: waehrend
  statische Mess in Phase „measure" laeuft, blockiert Dynamic (siehe 3.4).
  Nach Phase=operate laeuft Dynamic wieder.

### 5.3 App-Start

- Buffer leer (RAM only, keine Persistenz).
- Toggle steht auf AUS (nicht persistiert — Mike muss aktiv fuer Test
  einschalten).
- Falls Mike Toggle einschaltet ohne dass Diversity aktiv ist → kein Effekt
  bis Diversity-Modus aktiviert wird.

---

## 6. UI

### 6.1 Settings-Toggle

- **Ort:** Settings-Dialog → „Diversity"-Bereich (gleicher Tab wie
  statische Schwellen).
- **Wortlaut:** „Antennen-Verhaeltnis dynamisch anpassen (Testphase)"
- **Tooltip:** „Statt 1× pro Stunde wird das Verhaeltnis im laufenden
  Betrieb kontinuierlich nachjustiert (~jede Minute). Nur im Diversity-
  Modus aktiv."
- **Default:** AUS
- **Persistenz:** **KEINE** — Toggle wird nicht in settings.json gespeichert.
  Bei jedem App-Start: AUS. Mike muss aktiv einschalten fuer jeden Testlauf.
  (Bewusste Test-Phase-Entscheidung — verhindert dass Toggle vergessen
  bleibt und Bugs falsch zugeordnet werden.)

### 6.2 Statusbar-Badge

- **Ort:** Statusbar unten, rechts neben OMNI-Counter (Position genauer in
  V2 mit Blick auf `_update_statusbar()` Code-Layout).
- **Format:** `dyn 72:28` (kompakt, 3 Buchstaben + Ratio)
  - „dyn" steht fuer „dynamisch aktiv"
  - Ratio = aktueller `DiversityController.ratio` (von Dynamic gesetzt)
- **Sichtbarkeit:**
  - sichtbar wenn Toggle AN + Diversity aktiv + Phase=operate
  - unsichtbar wenn Toggle AUS oder Diversity aus (Antennen-Panel zeigt
    dann das statische Ratio wie bisher)
- **Antennen-Panel:** bleibt 1:1 unberuehrt (zeigt weiterhin das gerade
  aktive Ratio, egal ob statisch oder dynamisch gesetzt).

### 6.3 Keine weiteren UI-Elemente in V1

Bewusst out-of-scope:
- Kein Mini-Graph der letzten 5 Buffer-Werte
- Kein Glow/Animation bei Ratio-Wechsel (kann in einem Folge-PR ergaenzt
  werden falls Mike es will)
- Keine Anzeige der Score-Werte

---

## 7. Akzeptanzkriterien (verbindlich, vollstaendig)

1. **AK1 — Statisch unangetastet:** Toggle AUS → Verhalten 1:1 wie v0.96.10.
   Keine Aenderung an `core/diversity.py` Mess-Pipeline oder
   `core/preset_store.py`.
2. **AK2 — Dynamic-Aktivierungs-Gate:** Datenerfassung nur wenn Toggle AN +
   Diversity AN + Phase=operate + RX-Slot mit >=1 Station.
3. **AK3 — Schiebepuffer:** `deque(maxlen=5)` pro Antenne. Nach 5 Eintraegen
   schiebt jedes weitere den aeltesten raus.
4. **AK4 — Auswertung gated:** `_evaluate()` wird nur ausgefuehrt wenn beide
   Puffer voll sind (je 5 Werte). Davor: keine Aenderung an
   `DiversityController.ratio`.
5. **AK5 — Pro-Slot Auswertung:** Sobald beide Puffer voll, wird nach JEDEM
   neuen Slot-Eintrag ausgewertet (Option A).
6. **AK6 — Schwellen identisch zur Statik:** `THRESHOLD=0.08`,
   `MIN_PEAK_SCORE=5.0`. Algorithmus 1:1 wie `core/diversity.py:_evaluate()`.
7. **AK7 — Reset-Trigger:** Buffer wird gelloescht bei Bandwechsel,
   Modus-Wechsel, Diversity-Aus.
8. **AK8 — Kein Reset bei:** OMNI-CQ, QSO, Toggle-Off, statische Re-Mess.
9. **AK9 — Keine Persistenz:** Weder Buffer noch Toggle werden auf Disk
   gespeichert. App-Start = Buffer leer + Toggle AUS.
10. **AK10 — Statusbar-Badge:** sichtbar wenn aktiv, Format `dyn 72:28`,
    bei Ratio-Wechsel sofort aktualisiert.
11. **AK11 — Threading:** Buffer-Update aus Decoder-Thread, Auswertung +
    GUI-Update via Signal + QueuedConnection. Thread-Safety per RLock
    analog `core/antenna_pref.py`.
12. **AK12 — Hardware-Schutz ANT1=TX:** Ratio betrifft NUR RX-Verteilung.
    `radio.set_tx_antenna("ANT1")` bleibt unangetastet. Code-Diff vor jedem
    Commit darauf pruefen.

---

## 8. Out-of-Scope (bewusst nicht in V1)

- **Persistenz** (Buffer oder Toggle auf Disk)
- **Mini-Graph** der letzten 5 Werte
- **Glow / Pulse** bei Ratio-Wechsel
- **Stufe 2** (statische Pipeline entfernen) — eigener Workflow spaeter
- **Hunt/Normal-Mode** — nur 1 Antenne aktiv, kein Vergleich moeglich
- **Anderes Scoring** (z.B. nur Stationsanzahl ohne SNR) — wir nutzen die
  bestehende `sum(SNR+30)`-Formel
- **Sampling-Tricks** bei extremen Ratios (Mike-Entscheidung: lohnt sich nicht
  weil Worst-Case-Buffer-Voll-Zeit <3.5 Min)

---

## 9. Akzeptable Trade-Offs (bewusst entschieden)

1. **Asymmetrische Buffer-Alter bei extremen Ratios:** Bei 70:30 ist der
   ANT2-Buffer ~3 Min „alt", der ANT1-Buffer ~1.5 Min. Akzeptiert weil
   selbst 3.3 Min noch 18× reaktiver ist als die heutige 1h-Statik.
2. **Median statt arithmetisches Mittel:** Mike sprach von „Durchschnitt".
   Wir nehmen Median (robuster gegen Ausreisser, 1:1 wie statisch). Wenig
   Unterschied bei 5 Werten, ausser bei 1 starkem Outlier — dann ist
   Median klarer Vorteil.
3. **Toggle nicht persistiert:** Bewusst nervig (jeder Neustart erfordert
   manuelles Anschalten) — schuetzt vor vergessenem-an-Bugs.
4. **Score-Formel uebernommen:** Wir nutzen die bestehende Score-Formel
   (`sum(SNR+30)`). Mike fragte ob Stationsanzahl UND SNR — Antwort:
   die Formel kombiniert beides intrinsisch. Klarer Code, bewaehrt.

---

## 10. Geschaetzte Komplexitaet

| Bereich | LOC (geschaetzt) |
|---|---|
| `core/dynamic_diversity.py` (neu) | ~140 |
| `ui/mw_cycle.py` Hook | ~15 |
| `ui/mw_radio.py` Reset-Hooks | ~10 |
| `ui/main_window.py` Init + Statusbar | ~30 |
| `ui/settings_dialog.py` Toggle + Tooltip | ~25 |
| `config/settings.py` Getter/Setter (non-persistent) | ~15 |
| Tests | ~250 |
| **Total** | **~480-500** |

| Atomare Commits | Inhalt |
|---|---|
| C1 | `core/dynamic_diversity.py` Klasse + Schiebepuffer + `_evaluate` |
| C2 | Tests `tests/test_dynamic_diversity.py` (Unit) |
| C3 | UI-Hooks `mw_cycle`, `mw_radio`, `main_window` |
| C4 | Settings-Dialog Toggle + non-persistent-Path |
| C5 | Statusbar-Badge in `_update_statusbar` |
| C6 | APP_VERSION-Bump + HISTORY/HANDOFF/CLAUDE/TODO |

**Total: 6 atomare Commits, geschaetzter Zeitaufwand ohne Workflow-Pausen
~5-7h Code+Tests.**

---

## 11. Hinweise an V2 / R1

Diese Sektion bleibt bewusst leer in V1 — V2 fuellt sie nach Self-Review
mit konkreten Pruefauftraegen fuer DeepSeek-R1.

---

## 12. Naechster Schritt

V2 (Self-Review):
- Lueckenfueller — was hat V1 vergessen?
- Edge-Cases auflisten die nicht in AKs stehen
- R1-Pruefauftraege formulieren (Threading, KISS, Tests, Migration)
- Code-Verifikation: Datei:Zeile-Verweise pruefen, ggf. korrigieren
