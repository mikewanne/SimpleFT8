# P34.DIVERSITY-DYNAMIC — V2 (Self-Review)

**Status:** V2 — Self-Review von V1-NEU (ENTWEDER-ODER-Architektur)
**Basis:** `prompts/p34_diversity_dynamic_v1.md`
**Workflow:** V2 → R1 (DeepSeek) → V3 → Plan → Code

---

## A. Was diese V2 macht

V1-NEU hat eine saubere ENTWEDER-ODER-Architektur mit deutlich weniger
Konfliktszenarien als V1-OLD. V2:

1. **Verifiziert** alle Hook-Stellen + Datei:Zeile-Verweise.
2. **Korrigiert** einen wichtigen Punkt: Das Verhaeltnis-Label ist NICHT
   in der Statusbar — es ist im Antennen-Panel (siehe B.1).
3. **Identifiziert** verbleibende Edge-Cases die V1-NEU nicht abdeckt.
4. **Formuliert** Pruefauftraege fuer DeepSeek-R1 (10 konkrete Fragen statt
   alter 16).

---

## B. Code-Verifikation (Schritt 0 Ergebnis)

### B.1 KRITISCH — Verhaeltnis-Label-Position (Korrektur an V1)

**V1 sagt** in §6.2: „Statusbar-Verhaeltnis-Label in BLAU wenn Dynamic aktiv".

**Im Code (`main_window.py:_update_statusbar` Z.1030-1112) verifiziert:**
Die Statusbar zeigt:
- Callsign, Locator, Mode, Band, Frequenz
- Filter, Mode-String, DT-Status
- OMNI-Counter (`Ω CQ=10 (E)`)
- CQ-Freq (`Freq: #5 1500Hz`)
- RX-Antennen-Praeferenz waehrend QSO (`RX: ANT1` oder `RX: ANT2 ↑6.3 dB`)
- AP-Lite-Counter

**Das Verhaeltnis `70:30` steht NICHT in der Statusbar.** Es steht im
**Antennen-Panel** (per `control_panel.update_diversity_ratio()`).

→ Mike's „Statusbar reicht — Antennen-Panel bleibt unberuehrt" passt
nicht zur Realitaet. Es gibt zwei Optionen:

**Option B.1.a:** Verhaeltnis-Label im **Antennen-Panel** blau faerben wenn
Dynamic aktiv. Strikt genommen ist das eine Panel-Aenderung, aber nur Style
(Farbe), kein Layout. Antennen-Panel-„Inhalt" (welches Verhaeltnis steht)
bleibt unberuehrt — nur die Schrift wird blau.

**Option B.1.b:** Verhaeltnis ZUSAETZLICH in die Statusbar einfuegen — z.B.
`dyn 72:28` oder `D 72:28`. Statusbar-Erweiterung, Panel unberuehrt.

**V2-Empfehlung:** **Option B.1.a** — minimaler Eingriff, kein
Statusbar-Platz-Konflikt, intuitiv (Mike schaut sowieso ins Antennen-Panel
fuers Verhaeltnis). Wenn R1 das anders sieht: B.1.b als Fallback.

### B.2 should_remeasure() Stelle

V1 §3.3 sagt: „bei Dynamic AN: returnt immer False". **Verifiziert**
`core/diversity.py:478-497`:

```python
def should_remeasure(self, qso_active: bool, cq_active: bool = False) -> bool:
    if self._phase != "operate":
        return False
    if qso_active or cq_active:
        return False
    if self._last_measured_at is None:
        return True
    return (time.time() - self._last_measured_at) >= self.REMEASURE_INTERVAL_SECONDS
```

→ Patch-Stelle eindeutig identifiziert. Ein extra Check ganz am Anfang:
```python
if getattr(self, '_dynamic_active', False):
    return False
```

Das `_dynamic_active`-Flag wird vom Dynamic-Controller gesetzt
(`activate()`/`deactivate()`-Methoden setzen es direkt auf die
DiversityController-Instanz als Attribut).

### B.3 scoring_mode-Setter Stelle

V1 §3.3 sagt: „scoring_mode-Wechsel → Buffer leeren wenn Dynamic AN".
**Verifiziert** `core/diversity.py:67-70`:

```python
@scoring_mode.setter
def scoring_mode(self, mode: str):
    if mode in ("normal", "dx"):
        self._scoring_mode = mode
```

→ Hier muss ein Hook rein:
```python
@scoring_mode.setter
def scoring_mode(self, mode: str):
    if mode in ("normal", "dx"):
        old_mode = self._scoring_mode
        self._scoring_mode = mode
        if old_mode != mode and getattr(self, '_dynamic_ctrl_ref', None):
            self._dynamic_ctrl_ref.reset()
```

Aber: `_dynamic_ctrl_ref` muss vom main_window gesetzt werden — Dependency
einfuehren. **Alternative (sauberer):** main_window haengt sich an
ein neues Signal `scoring_mode_changed` von der DiversityController.
**R1 entscheiden lassen welcher Weg sauberer ist.**

### B.4 Hook in mw_cycle._on_cycle_decoded

V1 §3.3 sagt: „nach Z.97 _handle_diversity_operate". **Verifiziert**
`mw_cycle.py:62-100`:

```python
def _on_cycle_decoded(self, messages: list):
    ...
    ant, was_phase = "A1", "operate"
    if self._rx_mode == "diversity":
        ant, was_phase = self._pop_diversity_queue()
    ant = self._resolve_hardware_antenna(ant)
    ...
    if self._rx_mode == "diversity" and was_phase == "measure":
        self._handle_diversity_measure(messages, ant)
    if self._rx_mode == "diversity" and messages:
        self._handle_diversity_operate(messages, ant)
```

Hook fuer Dynamic (neue Methode) — kommt nach dem `_handle_diversity_operate`
(weil Dynamic nur in Phase=operate aktiv ist):

```python
if (self._rx_mode == "diversity"
        and was_phase == "operate"
        and getattr(self, "_dynamic_ctrl", None) is not None
        and self._dynamic_ctrl.is_active()
        and messages):
    self._handle_dynamic_diversity(messages, ant)
```

`_handle_dynamic_diversity(messages, ant)` ruft `compute_slot_score(messages)`
+ `dynamic_ctrl.record_slot(ant, score)`. **Klar.**

### B.5 Settings-Property RAM-only

V1 §6.1 sagt: „Toggle nicht persistiert". **Verifiziert** `config/settings.py`:

- `Settings.__init__` Z.76-78 ruft `self.load()` → liest aus settings.json
- `Settings.save()` Z.114 schreibt nach settings.json
- `_data`-Dictionary speichert persistente Werte

**Saubere Implementierung:** Eigene Property `self._dynamic_enabled = False`
direkt im `__init__` setzen (vor `load()`). Niemals in `_data` schreiben,
nie in `save()` aufnehmen. Beim Toggle einfach `settings._dynamic_enabled = True/False`.

```python
def __init__(self):
    self._data = {}
    self._dynamic_enabled = False  # RAM-only, nicht persistiert
    self.load()
```

Getter/Setter:
```python
@property
def dynamic_diversity_enabled(self) -> bool:
    return self._dynamic_enabled

@dynamic_diversity_enabled.setter
def dynamic_diversity_enabled(self, value: bool):
    self._dynamic_enabled = bool(value)
```

### B.6 _enable_diversity-Hook

V1 §3.3 sagt: „Diversity an→aus → dynamic_ctrl.deactivate()". **Verifiziert**
`mw_radio.py:824` `_enable_diversity()`. Wird auch bei Mode-Wechsel zu Normal
aufgerufen (mit `False`). → Eindeutig identifizierte Stelle.

---

## C. Lifecycle-Tabelle (verbindlich)

| Ereignis | Statik-Pipeline | Dynamic-Pipeline | `DiversityController.ratio` |
|---|---|---|---|
| App-Start, Toggle AUS | initialisiert + misst (90s) | passiv (`_active=False`) | von Statik gesetzt |
| App-Start, Toggle AN nach Init | misst NICHT (Dynamic kommt erst nach Init dran) | passiv bis User Toggle | unberuehrt |
| Toggle AUS→AN | unterdrueckt (`should_remeasure=False`) | aktiviert + Buffer leer + 50:50-Reset | sofort 50:50 |
| Toggle AN→AUS | wieder regulaer | deaktiviert (Buffer egal) | bleibt beim letzten Wert |
| Slot mit Dynamic AN | passiv | record_slot + ggf. evaluate | von Dynamic ggf. gesetzt |
| Slot mit Dynamic AUS | regulaer | passiv | bleibt |
| Bandwechsel mit Dynamic AN | passiv (KEINE 90s-Sperre!) | Buffer leer + 50:50 | sofort 50:50 |
| Bandwechsel mit Dynamic AUS | regulaer (90s-Sperre) | passiv | von Statik gesetzt |
| Modus-Wechsel mit Dynamic AN | passiv | Buffer leer + 50:50 | sofort 50:50 |
| Mode→Normal (Diversity aus) | (nicht relevant — Normal-Mode) | deaktiviert | (egal, Normal-Mode) |
| scoring_mode-Wechsel (Std↔DX) mit Dynamic AN | passiv | Buffer leer + 50:50 | sofort 50:50 |
| scoring_mode-Wechsel mit Dynamic AUS | misst neu (Statik triggert) | passiv | von Statik gesetzt |
| QSO Start/Stop | passiv (was Toggle sagt) | RX-Slot-Daten weiter, TX-Slot ignoriert | unveraendert |
| OMNI-CQ Start/Stop | passiv | passiv | unveraendert |
| App-Quit | (egal, RAM weg) | (egal) | (egal) |

---

## D. Verbleibende Edge-Cases

### D.1 Toggle AN sehr frueh nach App-Start

App startet → Statik geht in Phase=measure (90s) → User toggelt Dynamic AN
**waehrend** der Mess-Phase.

**Frage:** Was passiert?
- Variante A: Toggle wartet bis Statik durch ist, dann uebernimmt Dynamic
- Variante B: Statik wird sofort abgebrochen, Dynamic startet mit 50:50
- Variante C: Toggle wird ignoriert bis Phase=operate

**V2-Empfehlung:** Variante A — sauberer. Wenn Statik laeuft, soll sie
zu Ende laufen (~60s Restzeit max). Toggle-AN merkt sich „pending", und
beim Uebergang Phase=measure → Phase=operate fuehrt main_window die
eigentliche Aktivierung durch (`dynamic_ctrl.activate()` + Verhaeltnis-Reset).

**R1 verifizieren ob das wirklich sauberer ist.**

### D.2 Toggle AN bei `_rx_mode == "normal"`

User hat Normal-Mode (keine Diversity), toggelt Dynamic AN.

**Frage:** Was passiert?
- Variante A: Toggle wird gesetzt, aber Dynamic-Controller `is_active()` returnt
  trotzdem False weil Diversity-Modus nicht da. Toggle ist „warmgelaufen" fuer
  spaeter.
- Variante B: Toggle-Wechsel zeigt Fehlermeldung „Erst Diversity einschalten".

**V2-Empfehlung:** Variante A — keine Fehlermeldung. Toggle merkt sich nur
den User-Wunsch. Wenn Mike spaeter Diversity einschaltet → Dynamic aktiviert
sich automatisch.

### D.3 Race bei Toggle AUS→AN mid-slot

Slot 0 laeuft (Decoder dekodiert), User toggelt AN, Slot 0 endet kurz danach,
`_on_cycle_decoded` laeuft.

**Frage:** Wird Slot 0 noch in Dynamic-Buffer geschrieben?
- Ja, weil `_active=True` zum Zeitpunkt von `_on_cycle_decoded`.
- Aber: Toggle wurde mitten im Slot gedrueckt → Verhaeltnis war zu Slot-Start
  noch Statik-Wert (z.B. 70:30) → Slot wurde nach Statik-Pattern empfangen.

**Frage:** Sollte Slot 0 als „uebergangs-Slot" verworfen werden?

**V2-Empfehlung:** Verwerfen. Erst der ERSTE Slot der KOMPLETT unter Dynamic-
Regime lief soll in Buffer. Implementierung: Toggle-AN setzt einen
`_skip_next_slot=True`-Flag, der nach dem ersten Slot abgebaut wird.

**R1 verifizieren ob das zu kompliziert ist** — Alternative: einfach den
ersten Slot mit reinnehmen, Median ueber 5 glaettet das eine Outlier raus.

### D.4 Statusbar-Anzeige Position (siehe B.1)

V1 hat falsche Anzeige-Position. R1 muss entscheiden:
- B.1.a Antennen-Panel-Faerbung
- B.1.b Statusbar-Erweiterung

### D.5 Was wenn Mike Toggle 5× hintereinander druckt

User klickt AN-AUS-AN-AUS-AN sehr schnell. Buffer-Resets durcheinander?

**V2-Empfehlung:** Jede AN-Aktion macht 50:50-Reset + Buffer-leer. Race ist
unproblematisch weil alle Resets das gleiche Ergebnis haben (50:50 + leer).

### D.6 Settings-Dialog OK vs. Apply

Settings-Dialog hat (in der bestehenden App) typischerweise OK + Cancel +
Apply. Was passiert wenn Mike Toggle AN setzt + Cancel druckt?

**V2-Empfehlung:** Settings-Dialog soll Toggle wie alle anderen Settings
behandeln — Cancel verwirft, OK setzt. Implementierung folgt dem
existierenden Pattern. **R1 verifizieren** dass das wirklich konsistent
ist mit anderen non-persistenten Einstellungen.

---

## E. Pruefauftraege fuer DeepSeek-R1

DeepSeek, du bekommst V2 + V1 + relevante Code-Files. **Kritisiere die
Spec, schlage Verbesserungen vor — IMPLEMENTIERE NICHT.**

### E.1 Architektur (HOECHSTE PRIORITAET)

1. **R1-Q1 — ENTWEDER-ODER vs. parallel:** V1 wechselt von der ursprueng-
   lichen „parallel"-Architektur (V1-OLD, archiviert) zu strikt ENTWEDER-ODER.
   Bewerte: ist das wirklich sauberer? Welche Risiken hat ENTWEDER-ODER die
   wir uebersehen koennten? Wuerde eine Hybrid-Loesung (z.B. Statik macht
   nur initialen Mess, danach Dynamic) Vorteile haben die wir verlieren?

2. **R1-Q2 — Neues Modul vs. Flag (revisited):** Letzte R1-Antwort (im
   parallel-Kontext) empfahl Flag in DiversityController. Mike hat das
   verworfen (Risiko fuer statische Pipeline). V1-NEU geht zurueck zu
   neuem Modul + Helper-Funktionen auf Modul-Ebene. Bewerte: ist die
   Helper-Strategie sauber genug? Gibt es Code-Duplikation die wir
   uebersehen?

### E.2 Statusbar-Korrektur (HOCH)

3. **R1-Q3 — Faerbung im Antennen-Panel vs. Statusbar-Erweiterung:**
   V2-B.1 zeigt dass das Verhaeltnis-Label NICHT in der Statusbar ist
   (Korrektur an V1). Welche Variante ist sauberer:
   - B.1.a: Antennen-Panel Verhaeltnis-Label blau wenn Dynamic aktiv
   - B.1.b: Statusbar-Erweiterung mit `dyn 72:28`
   Beachte: Mike sagte „Antennen-Panel unberuehrt" — aber eine reine
   Farb-Aenderung ist kein Layout-Eingriff. Akzeptabel oder pingelig auslegen?

### E.3 Threading (HOCH)

4. **R1-Q4 — `_dynamic_active`-Flag in DiversityController:** V2 §B.2
   schlaegt vor dass DynamicDiversityController ein Attribut
   `_dynamic_active=True` auf die DiversityController-Instanz setzt
   (damit `should_remeasure` es lesen kann). Ist dieses
   Cross-Object-Attribut-Setzen sauber, oder besser ueber Signal/Property?

5. **R1-Q5 — scoring_mode-Wechsel Hook:** V2 §B.3 zeigt zwei Wege
   (direkte Referenz vs. Signal). Welcher ist sauberer in PySide6?
   Verifiziere `tests/test_omni_cq_signal.py` als Negativ-Beispiel — dort
   wird Signal genutzt.

6. **R1-Q6 — RLock vs. Lock:** V1 spezifiziert RLock. Brauchen wir wirklich
   re-entrancy (RLock ist teurer)? Liste die Methoden auf die unter Lock
   stehen — gibt es eine die rekursiv aufgerufen wird?

### E.4 Edge-Cases (HOCH)

7. **R1-Q7 — D.1 Toggle AN waehrend Statik-Mess:** Variante A („warten")
   sauberer als Variante B („Statik abbrechen") oder Variante C („Toggle
   ignorieren")? Begruendung mit Code-Verweisen.

8. **R1-Q8 — D.3 Slot-Skip beim Toggle-Wechsel:** Lohnt sich der
   `_skip_next_slot`-Flag oder ist es zu kompliziert? Median ueber 5 sollte
   einen Outlier glaetten — ist das Argument stark genug fuer KISS-„skip
   nicht noetig"?

### E.5 Tests (MITTEL)

9. **R1-Q9 — Test-Coverage:** Konkrete Test-Liste fuer V3:
   - Unit-Tests fuer `DynamicDiversityController`
   - Integration-Tests fuer Toggle-Wechsel
   - Edge-Case-Tests fuer D.1-D.6
   - Threading-Tests
   Mindest-Anzahl ~25 Tests sollten in V3 als Liste stehen. Schlage konkrete
   Test-Namen + Test-Datei vor.

### E.6 Sonstiges (MITTEL)

10. **R1-Q10 — Modulname-Konvention:** `core/diversity_dynamic.py` vs.
    `core/dynamic_diversity.py`. Welcher passt zu `core/`-Konvention
    (`diversity.py`, `diversity_merger.py`, `direction_pattern.py`)?
    Verifiziere durch `ls core/`-Output.

---

## F. Was V3 enthalten muss

1. Verbindliche Spec ohne offene Fragen — basierend auf V1 + V2 + R1-Findings.
2. Implementierungs-Plan: 9 atomare Commits (V1 §10) mit Datei:Zeile-
   Verweisen + Reihenfolge.
3. Test-Liste (~25 Tests) mit Namen + Datei.
4. **Field-Test-Checkliste** fuer Mike (was nach Code-fertig testen?):
   - Toggle AUS → alles laeuft wie heute (Regression-Test)
   - Toggle AN → 50:50-Reset, Statusbar/Panel-Faerbung greift
   - Bandwechsel mit Dynamic AN → 50:50, keine UI-Sperre
   - 1h ohne QSO mit Dynamic AN → keine 90-Sek-Mess
   - Toggle AN→AUS mid-Betrieb → Statik uebernimmt nach Frist
   - usw.
5. 1-Seiten-Zusammenfassung in einfacher Sprache fuer Mike.

---

## G. Anhang-Files fuer R1

- `core/diversity.py` (Statik-Pipeline + Helper-Stellen)
- `ui/mw_cycle.py` (Hook-Stelle + Score-Formel)
- `ui/mw_radio.py` (Diversity-Aktivierung, scoring_mode)
- `ui/main_window.py` partial (Statusbar verifizieren, Antennen-Panel-Pfad)
- `config/settings.py` (Persistence-Layer)
- `tests/test_omni_cq_signal.py` (Negativ-Beispiel fuer Signal-Pattern)
