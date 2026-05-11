# P34.DIVERSITY-DYNAMIC — V2 (Self-Review)

**Status:** V2 — Self-Review nach V1, bereit fuer DeepSeek-R1
**Datum:** 2026-05-11
**Basis:** V1 `prompts/p34_diversity_dynamic_v1.md` (komplette Spec mit
allen Mike-Klaerungen vom Dialog 2026-05-11).

---

## A. Was diese V2 anders macht als V1

V1 ist bereits eine komplette Spec mit 12 ACs + 4 Sektionen Lifecycle/UI/Score.
V2 fuegt hinzu:

1. Konkrete **Hook-Stellen** mit verifizierten Datei:Zeile-Verweisen (in V1 stand
   `mw_cycle._on_cycle_decoded` — V2 prueft das im Code und nennt das richtige
   Helper-Methodengebot).
2. **Edge-Cases** die V1 nicht in den ACs hatte (App-Quit, Toggle-Race, Statische
   Re-Mess Kollision, Toggle-OFF-vs-Active-State Inkonsistenz).
3. **R1-Pruefauftraege** (16 konkrete Fragen statt 8 grobe).
4. **Score-Formel** verifiziert aus bestehendem Code (`mw_cycle.py:239-241`).
5. **Lifecycle-Tabelle** als verbindliche Referenz fuer Implementierung.

---

## B. Code-Verifikation (Schritt 0 Ergebnis)

### B.1 Hook-Punkt fuer Datenerfassung

V1 sagte: `ui/mw_cycle.py _on_cycle_decoded`. **Verifiziert** Z.62-100. Aber
konkreter:

- Z.71-79: `ant, was_phase = self._pop_diversity_queue()` ergaenzt durch
  `ant = self._resolve_hardware_antenna(ant)` — DIESES `ant` ist der
  Slot-Ground-Truth.
- Z.96-97: `_handle_diversity_operate(messages, ant)` — laeuft nur wenn
  `messages` nicht-leer ist + Phase=operate. **Hier hinzufuegen:** Dynamic-Hook.

**Genauer Hook-Aufruf (V2-Vorschlag):**

```python
# In ui/mw_cycle.py _on_cycle_decoded, nach Z.97 _handle_diversity_operate:
if (self._rx_mode == "diversity"
        and self._diversity_ctrl.phase == "operate"
        and getattr(self, "_dynamic_enabled", False)
        and messages):
    self._handle_dynamic_diversity(messages, ant)
```

Plus neue Methode `_handle_dynamic_diversity(self, messages, ant)` in CycleMixin
(analog `_handle_diversity_measure` Z. 233ff).

### B.2 Score-Formel — VERIFIZIERT

`mw_cycle.py:239-241` macht in Phase „measure":

```python
valid = [m for m in (messages or []) if m.snr is not None and m.snr > -20]
score = sum(max(0.0, float(m.snr + 30)) for m in valid) if valid else 0.0
```

V1 sagte „sum(SNR+30)" — V2 praezisiert: **SNR-Filter > -20** + Clamp `max(0.0, ...)`.
Das ist die EXAKTE Formel die Dynamic uebernehmen muss, sonst sind die Werte nicht
mit den statischen Mess-Daten vergleichbar.

### B.3 Aktuelle Antenne pro Slot

`self._diversity_current_ant` (`mw_radio.py:235, 841`) wird beim Slot-Start gesetzt.
ABER: in `mw_cycle._on_cycle_decoded` ist `ant` aus `_pop_diversity_queue()` der
**echte Slot-Wert** vom Slot-Start (queue speichert pro Slot). Das ist
RACE-FREI weil queue im Decoder-Thread konsumiert wird mit dem Slot der gerade
fertig dekodiert wurde.

→ V1 AK11 (Threading) wird durch Nutzung von `ant` aus `_pop_diversity_queue()`
korrekt erfuellt.

### B.4 Diversity-Phase-Wechsel waehrend Dynamic laeuft

`_handle_diversity_measure` (Z.233ff) wird aufgerufen wenn `was_phase=="measure"`.
Sobald Phase=operate, laeuft `_handle_diversity_operate` (Z.346 weiter).

Dynamic laeuft NUR in Phase=operate (V1 §3.3). Bei statischer Re-Mess:
1. Phase wechselt zu „measure" → kein Dynamic-Hook
2. Statische Pipeline fuellt 6 Mess-Werte → setzt `_diversity_ctrl.ratio`
3. Phase wechselt zurueck zu „operate" → Dynamic wieder aktiv
4. **PROBLEM:** Dynamic-Buffer hat Werte aus VOR der Re-Mess. Statische
   Re-Mess hat moeglicherweise eine andere Ratio gesetzt als das, was
   Dynamic gerade ermittelt hatte. Wenn Dynamic ueber `_evaluate()` sofort
   nach einem neuen Wert ausgeloest wird, ueberschreibt es das frische
   Statik-Ergebnis.

→ **Edge-Case fuer V2 explizit dokumentieren** (siehe D.1).

---

## C. Lifecycle-Tabelle (verbindlich)

| Ereignis | `_buffer` | `_active` | `DiversityController.ratio` |
|---|---|---|---|
| App-Start | leer | False | unangetastet (statisch oder Default) |
| Toggle AN | leer | True | unangetastet bis Buffer voll |
| 1. Slot in Phase=operate | 1 Wert in A1 oder A2 | True | unangetastet |
| Beide Puffer voll (>=5 je) | voll | True | von `_evaluate()` ggf. neu gesetzt |
| Slot mit 0 Stationen | unveraendert | True | unveraendert |
| TX-Slot | unveraendert | True | unveraendert |
| Bandwechsel | leer | True (falls Toggle AN) | von set_band-Logik → 50:50 |
| Modus-Wechsel | leer | True (falls Toggle AN) | von set_mode-Logik → 50:50 |
| Diversity AUS | leer | False | (egal, Diversity weg) |
| Mode→Normal | leer | False | (egal, Normal-Mode) |
| Toggle AUS | **bleibt** | False | bleibt beim letzten Wert |
| Toggle AN→AUS→AN | **bleibt** | True | re-aktivierung mit altem Buffer |
| Statische Re-Mess Start (Phase=measure) | unveraendert | True | von Statik gesetzt |
| Statische Re-Mess Ende (Phase=operate) | unveraendert | True | von Statik gesetzt — **Dynamic darf NICHT sofort ueberschreiben!** |
| QSO Start | unveraendert | True | unveraendert |
| QSO Ende | unveraendert | True | unveraendert |
| App-Quit | (egal, RAM weg) | (egal) | (egal) |

---

## D. Edge-Cases (V1 hatte nicht alle in AKs)

### D.1 Statische Re-Mess Kollision (HOCH)

**Problem:** Wenn statische Re-Mess gerade in Phase=measure laeuft, Buffer
behaelt seine alten Werte. Sobald Phase=operate, kommt der erste neue Slot →
`_evaluate()` triggert → setzt evtl. anderes Ratio als die Statik gerade
ermittelt hat.

**Loesungs-Vorschlag fuer V3:** Dynamic-Buffer wird beim Phase-Wechsel
`measure → operate` mit einer **Warmup-Periode** gestartet (z.B. 5 Slots
Stats-Warmup). In diesen 5 Slots wird zwar erfasst aber NICHT ausgewertet.
Danach: normale Auswertung. Alternativ: Buffer auch bei Phase-Wechsel
leeren (klarer „Statik-Resultat hat Vorrang" Pattern).

→ **R1 muss entscheiden welche Variante besser ist.**

### D.2 Toggle-Race (MITTEL)

Mike toggelt im Settings-Dialog mitten in einem Slot AN. Was passiert:

- Slot 0: Toggle AN gedrueckt
- Slot 0 Ende: `_on_cycle_decoded` laeuft, prueft `_dynamic_enabled` = True
- Slot 0 wird in Buffer geschrieben
- Aber: `_active`-State im Dynamic-Controller war beim Slot-Start False

→ Toggle-AN sollte `dynamic_ctrl.activate()` aufrufen die intern
`_active=True` setzt + alle Bedingungen wieder pruefen.

### D.3 App-Quit-Pfad (NIEDRIG)

V1 §5.3 sagt „App-Start = leer". App-Quit braucht keinen expliziten Stop,
da RAM-Daten sowieso weg sind. **R1 pruefen ob das wirklich so ist** oder
ob z.B. der RLock irgendwo offen bleibt und das app-quit blockt.

### D.4 Toggle-AUS waehrend Auswertung laeuft (NIEDRIG)

Slot-Hook in Decoder-Thread laeuft gerade `_evaluate()`. Im GUI-Thread
toggelt Mike AUS. Wenn `_active=False` mitten in `_evaluate()` gesetzt
wird, was passiert? **R1 pruefen:** Atomare Wahrnehmung von `_active`?

### D.5 Buffer halb-voll und Phase=measure greift (MITTEL)

Mike startet App, Toggle AN, Dynamic laeuft 3 Slots (Buffer hat 2-3
Werte je), dann triggert statische Re-Mess (1h-Frist abgelaufen oder
Mike loest aus). Phase=measure → Dynamic pausiert (kein record_slot mehr).
6 Slots spaeter → Phase=operate → Dynamic-Buffer hat noch die alten
2-3 Werte. Slot 7: neuer Eintrag → A1 hat jetzt 4 Werte. Wartet auf 5.

→ Saubere Auswertung erst bei Buffer voll. Aber: die 2-3 alten Werte
sind aus der Zeit VOR der Re-Mess. Sind sie noch repraesentativ?

Bei Bedingungs-Aenderung (Wetter z.B.) waeren sie veraltet. Aber:
Median ueber 5 Werte glaettet alte vs neue raus. **Trade-off,
KISS-akzeptabel.**

→ Alternative: Phase-Wechsel measure→operate leert Buffer.
**R1 entscheiden lassen** ob KISS-Vorteil von „Buffer behalten" das
Risiko alter Werte ueberwiegt.

### D.6 0-Stations-Slot (definiert in V1 §3.3 als „kein Eintrag")

V1 sagt: kein Eintrag wenn 0 Stationen. Logisch — kein Score, keine
Vergleichsbasis. **V2 verfeinert:** auch wenn 1 Station mit SNR <= -20
dekodiert wurde, ist `valid`-Liste leer (Score=0). Auch das = kein Eintrag.

### D.7 Wechsel zwischen scoring_mode (Normal ↔ DX) waehrend Dynamic

`DiversityController.scoring_mode` kann sich aendern (Normal → DX). Dynamic-
Buffer hat Werte aus altem Modus. Beim Wechsel: Buffer leeren oder behalten?

V1 hat das nicht abgedeckt. **V2-Vorschlag:** Buffer leeren bei
scoring_mode-Wechsel (analog Bandwechsel) weil verschiedene Modi
unterschiedliche Charakteristik haben (DX filtert SNR<-10, Normal nicht).
**R1 verifizieren.**

---

## E. Pruefauftraege fuer DeepSeek-R1 (16 konkrete Fragen)

DeepSeek, du bekommst diese Spec + die genannten Code-Files. **Kritisiere
die Spec, schlage Verbesserungen vor — IMPLEMENTIERE NICHT.**

### E.1 KISS-Bewertung (HOECHSTE PRIORITAET)

1. **R1-Q1 — Brauchen wir ein neues Modul `core/dynamic_diversity.py` oder
   reicht ein zusaetzlicher Modus in `DiversityController`?** V1 sagt
   „neues Modul, Statik unangetastet". Bewerte ob die Trennung wirklich
   noetig ist oder ob ein `_dynamic_mode`-Flag in der bestehenden Klasse
   sauberer waere. Beruecksichtige: Stufe 2 (Statik entfernen) soll spaeter
   moeglich sein.

2. **R1-Q2 — Score-Formel-Duplizierung:** V1 plant `sum(max(0, snr+30))` in
   Dynamic separat. `mw_cycle.py:239-241` hat sie schon. Sollten wir eine
   Helper-Funktion `compute_slot_score(messages) -> float` in `core/diversity.py`
   einfuehren, die beide nutzen?

### E.2 Threading + Race-Conditions (HOCH)

3. **R1-Q3 — `_active`-Flag-Atomicity:** Wenn Decoder-Thread `record_slot()`
   ausfuehrt und gleichzeitig GUI-Thread `deactivate()` setzt `_active=False`
   — wird der laufende `record_slot()` korrekt durchlaufen oder muessen wir
   das in einem RLock kapseln?

4. **R1-Q4 — `DiversityController.ratio`-Setter Race:** Dynamic setzt
   `diversity_ctrl.ratio` aus Decoder-Thread. `mw_cycle._on_cycle_start`
   liest `diversity_ctrl.choose()` im GUI-Thread fuer naechsten Slot.
   Race-Risiko? Brauchen wir Lock?

5. **R1-Q5 — Statusbar-Update aus Decoder-Thread:** Pattern muss sein:
   Signal `ratio_changed_dynamic.emit()` mit QueuedConnection → GUI-Slot
   `_update_statusbar()`. Verifizieren dass das nicht das `slot_changed`
   oder andere Statusbar-Signal-Race triggert.

### E.3 Lifecycle + Edge-Cases (HOCH)

6. **R1-Q6 — D.1 Statische Re-Mess Kollision:** Welche Loesungs-Variante
   ist sauberer:
   - (a) Buffer beim Phase-Wechsel measure→operate **leeren** (Statik
     bekommt vollen Vorrang, Dynamic startet komplett neu)
   - (b) Buffer **behalten**, aber 5-Slot-Warmup vor erster Auswertung
   - (c) Buffer behalten, sofort weiterauswerten — Dynamic darf Statik
     ueberschreiben

7. **R1-Q7 — D.5 Buffer alter Werte:** Im Worst-Case (3 Werte vor Re-Mess +
   2 neue nach Re-Mess) kann der Median 60% alte + 40% neue Daten sein.
   Akzeptabel oder Buffer-Leerung bei Phase-Wechsel sauberer?

8. **R1-Q8 — D.7 scoring_mode-Wechsel:** Buffer bei Normal↔DX-Wechsel
   leeren oder behalten? Begruendung mit Blick auf Score-Vergleichbarkeit.

### E.4 Tests (HOCH)

9. **R1-Q9 — Test-Coverage:** Welche Test-Klassen fehlen in V1? Liste
   schreiben mit:
   - Unit-Tests (DynamicDiversityController allein)
   - Integration-Tests (mw_cycle-Hook + Settings-Toggle)
   - Threading-Tests (record + activate parallel)
   - Edge-Case-Tests (alle D.1-D.7)
   Mindest-Anzahl 15-20 Tests sollten in V3 als Liste stehen.

10. **R1-Q10 — Mock-Strategie:** Wie testen ohne Decoder + Radio? V1 hat
    keinen konkreten Mock-Plan. Pattern aus bestehenden Tests
    (z.B. `tests/test_omni_cq_signal.py`) zeigen wie das geht.

### E.5 UI + Settings (MITTEL)

11. **R1-Q11 — Toggle nicht persistiert:** Wie technisch implementieren?
    - Option A: Eigene Property in `MainWindow` (`self._dynamic_enabled`),
      Settings-Dialog setzt direkt.
    - Option B: `Settings`-Klasse hat Field das nicht in settings.json
      landet (z.B. RAM-only-Field).
    - Option C: Settings persistiert es, App-Start setzt zurueck auf False.
    Welche ist sauberer?

12. **R1-Q12 — Statusbar-Format:** `dyn 72:28` als Text. Wo genau in
    `_update_statusbar()` einfuegen? Existiert dort schon ein
    OMNI-Counter-Block? Code-Verweis wenn moeglich.

13. **R1-Q13 — Tooltip-Wortlaut:** „Statt 1× pro Stunde wird das Verhaeltnis
    im laufenden Betrieb kontinuierlich nachjustiert (~jede Minute). Nur
    im Diversity-Modus aktiv." — verstaendlich fuer Mike? Verbesserungs-
    vorschlag.

### E.6 Stufe 2 (Statik entfernen, spaeter)

14. **R1-Q14 — Sauberer Aus-Pfad:** Wenn Stufe 2 spaeter Statik entfernt,
    welche Code-Stellen muessen weg/refaktorisiert werden? Liste mit
    Datei:Zeile (ohne den Code zu schreiben — Inventar fuer spaeter).
    Zweck: V1 darf Stufe 2 nicht erschweren.

### E.7 Modulnamen + API-Design

15. **R1-Q15 — Modulname:** `core/dynamic_diversity.py` vs Alternative
    Namen (z.B. `core/diversity_dynamic.py`, `core/live_ratio.py`).
    Welcher Name passt am besten zu bestehender Naming-Konvention
    (siehe `core/`-Inhalt — `diversity.py`, `diversity_merger.py`).

16. **R1-Q16 — Settings-Default + Migration:** Settings.json hat aktuell
    keinen Dynamic-Key. Beim ersten Laden fehlt er → Default False
    (V1 §6.1). Migration noetig oder reicht `getattr(settings,
    'dynamic_diversity_enabled', False)`?

---

## F. Lücken die V2 nicht klärt (für R1)

- **Statusbar-Platz-Konflikt:** OMNI-Counter belegt Position. Statusbar
  ist meist eh „voll". R1 soll im Code (`main_window.py:_update_statusbar`)
  schauen und konkreten Vorschlag machen.
- **Re-Mess-Stoppen waehrend Dynamic aktiv:** Soll die statische 1h-Frist
  ueberhaupt noch greifen wenn Dynamic-Toggle AN ist? Mike-Spec sagt
  „beide parallel" → statische Re-Mess laeuft weiter. R1 bestaetigen.
- **Diversity_Standard vs Diversity_Dx:** Beide haben eigene Buffer? Oder
  ein gemeinsamer Buffer? V1 hat das nicht klargestellt. **V2-Vorschlag:**
  ein Buffer, weil scoring_mode-Wechsel den Buffer leert (siehe D.7).
  R1 verifizieren.

---

## G. Naechster Schritt

V2 + V1 + relevante Code-Files → DeepSeek-R1 via
`tools/deepseek_review.py`.

**Anhang-Files fuer R1:**
- `core/diversity.py` (statische Pipeline)
- `core/omni_cq.py` (entkoppelt — als Negativ-Beispiel fuer „keine Kopplung")
- `core/preset_store.py` (Persistenz-Layer)
- `ui/mw_cycle.py` (Hook-Stelle, Score-Formel)
- `ui/mw_radio.py` (Diversity-Aktivierung, Antennen-Switch)
- `ui/main_window.py` partial (Statusbar)

R1-Antwort wird in `prompts/p34_diversity_dynamic_r1.md` gespeichert,
dann V3 (Final-Spec) geschrieben mit allen R1-Findings.

---

## H. Was V3 fuer Mike enthalten muss

- 1-Seiten-Zusammenfassung in einfacher Sprache (wie Mike's
  Klaerungs-Dialog)
- Verbindliche Spec ohne offene Fragen
- Konkreter Implementierungs-Plan (Commits + Files + Zeilen)
- Test-Liste (15-20 Tests)
- Field-Test-Checkliste fuer Mike (was er nach Code-fertig testen muss)
