[deepseek] ~32308 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=37670 out=6900 total=44570
# DeepSeek-R1 Bewertung: P34.DIVERSITY-DYNAMIC V2 (Self-Review)

## Zusammenfassung der Kritik

Die V2-Spezifikation ist **gut strukturiert, aber hat noch einige kritische Lücken und Entscheidungen, die in V3 geklärt werden müssen**. Besonders die **Statik-Kollision** (D.1), das **Threading-Modell** und die **Testabdeckung** sind noch nicht ausgereift. Der KISS-Ansatz „neues Modul" ist fragwürdig – ich empfehle eine schlankere Lösung innerhalb des bestehenden `DiversityController`.

Nachfolgend die Beantwortung der 16 Prüfaufträge.

---

## E.1 KISS-Bewertung

### R1-Q1 — Neues Modul vs. Flag in DiversityController

**Bewertung:** Ein separates Modul `core/dynamic_diversity.py` ist **nicht KISS**. Der `DiversityController` hat bereits eine `_phase`-Property, `choose()`, `record_measurement()`, `_evaluate()`. Ein `_dynamic_mode`-Flag plus zwei Deques + aktivierte `_evaluate_dynamic()`-Methode würde **weniger als 100 LOC** zusätzlich bedeuten, statt ~140 LOC in einem neuen Modul.

**Vorteile Flag-Ansatz:**
- Keine doppelte `_evaluate()`-Logik (Thresholds, Median, Score-Formel) – die existiert bereits in `DiversityController._evaluate()`.
- `_evaluate_dynamic()` könnte direkt `self._evaluate()` mit dynamischen Puffern aufrufen, statt beide Implementationen synchron halten zu müssen.
- Stufe 2 (Statik entfernen) wird **nicht erschwert**: dann fällt einfach die statische `_evaluate()`-Logik weg, und der `_dynamic_mode` wird zum Standard.
- Einfacherer Lifecycle: `_reset_dynamic_buffers()` ohne separates `DynamicDiversityController.reset()`.

**Nachteil:** Der `DiversityController` wird etwas größer, aber das ist vertretbar (aktuell ~500 LOC, +80 LOC sind sauber).

**Empfehlung:** **Kein neues Modul.** Integriere Dynamic als `_dynamic_buffers` + `_dynamic_active` + `_evaluate_dynamic()` (private Methode) direkt in `core/diversity.py`. Das reduziert Schnittstellen, erleichtert Tests und macht Stufe 2 einfacher.

### R1-Q2 — Score-Formel-Duplizierung

**Bewertung:** Ja, unbedingt eine **Helper-Funktion** `compute_slot_score(messages) -> float` in `core/diversity.py` einführen. Aktuell ist die Formel in `mw_cycle.py:239-241` hartcodiert (in `_handle_diversity_measure`) und wird für Dynamic erneut benötigt.

**Empfehlung:** Füge eine statische Methode oder Modul-Funktion `def slot_score(messages: list[FT8Message]) -> float:` in `core/diversity.py` hinzu. Rufe sie von `_handle_diversity_measure` und vom Dynamic-Hook auf. Das verhindert Inkonsistenzen (z.B. Filter >-20 vs. >=-20).

---

## E.2 Threading + Race-Conditions

### R1-Q3 — `_active`-Flag-Atomicity

**Bewertung:** Hochrelevant. Der Decoder-Thread ruft `record_slot()` (bzw. in V2: `_handle_dynamic_diversity`) auf, während der GUI-Thread `deactivate()` setzt. **Python-Bool-Zugriffe sind atomar** (CPython GIL schützt einzelne Bytecode-Instruktionen), aber **die Kombination aus `_active`-Prüfung und anschließendem Buffer-Zugriff ist nicht atomar**.

**Empfehlung:** Verwende einen `threading.Lock` (den bestehenden `_diversity_lock` oder einen separaten `_dynamic_lock`) für alle `_active`-Lese- und Schreibzugriffe, die mit Buffer-Operationen kombiniert sind. Ein `RLock` analog `antenna_pref.py` ist sinnvoll, da `_evaluate()` rekursiv aufgerufen werden könnte. Für die reine `_active`-Abfrage im GUI-Thread (z.B. Statusbar) reicht ein einfacher `bool` ohne Lock, aber **jegliche kritische Sektion muss geschützt sein**.

### R1-Q4 — `DiversityController.ratio`-Setter Race

**Bewertung:** Ja, es gibt ein Race: Dynamic setzt `diversity_ctrl.ratio` im Decoder-Thread, während `_on_cycle_start` im GUI-Thread `diversity_ctrl.choose()` für den nächsten Slot liest. Ohne Lock könnte der neue `ratio`-Wert halb sichtbar sein (obwohl Python Bool/str-Zugriffe atomar sind – es geht eher um **Konsistenz zwischen `ratio` und `dominant`**). Beide Properties werden in `_evaluate_dynamic()` nacheinander gesetzt; wenn dazwischen `choose()` liest, bekommt es ein inkonsistentes Paar.

**Empfehlung:** Setze `ratio` und `dominant` **atomar** mittels eines `_diversity_lock` im `DiversityController`. Die `choose()`-Methode liest beide unter demselben Lock. Das sollte auch den existierenden `_diversity_lock` in `mw_cycle._on_cycle_start` nutzen (der bereits da ist). Zusätzlich den Lock auch im Dynamic-Pfad halten, wenn `ratio` gesetzt wird.

### R1-Q5 — Statusbar-Update aus Decoder-Thread

**Bewertung:** Das vorgeschlagene Signal `ratio_changed_dynamic` mit `QueuedConnection` ist der korrekte Qt-Weg. Kein Race, da QueuedConnection die Slot-Ausführung in den GUI-Thread verschiebt. Aber: **das Signal muss an ein existierendes `QObject` gebunden werden** (z.B. `MainWindow`), und der Empfänger muss `Qt.QueuedConnection` sein (explizit setzen, da AutoConnection bei cross-thread Signals QueuedConnection nehmen sollte, aber sicherheitshalber explizit).

**Empfehlung:** Verwende `@Slot(str, str)` und `Qt.QueuedConnection` bei der Verbindung. Achte darauf, dass das Signal **nicht** das vorhandene `ratio_changed`-Signal des `DiversityController` überschreibt – sonst verdoppelt sich die Statusbar-Aktualisierung. Am besten ein separates Signal `dynamic_ratio_changed` im `DiversityController` oder ggf. im `MainWindow`-Objekt.

---

## E.3 Lifecycle + Edge-Cases

### R1-Q6 — Statische Re-Mess Kollision (D.1)

**Bewertung:** Variante **(a) Buffer beim Phase-Wechsel measure→operate leeren** ist die sauberste und KISS-konformste. Sie gibt der Statik vollen Vorrang und vermeidet jede Vermischung alter und neuer Daten. Der Nachteil (wenige Minuten Warmup nach jeder Stunde) ist akzeptabel, da Dynamic ohnehin nur ~5+1=6 Slots (ca. 90s) braucht, um die Puffer wieder zu füllen. Das ist **1000x schneller** als die heutige 1h-Statik.

**Empfehlung:** Implementiere Buffer-Leerung bei `DiversityController._on_phase_operate()` (einen neuen Hook). Alternativ: `mw_cycle.py` ruft bei `phase == "operate"` nach einer statischen Re-Mess `dynamic_ctrl.reset_buffers()`. Dokumentiere als Teil der Lifecycle-Tabelle.

### R1-Q7 — D.5 Buffer alter Werte

**Bewertung:** Akzeptabel, wenn man Buffer bei Re-Mess nicht leert (was ich aber nicht empfehle). Der Median über 5 Werte glättet alte vs. neue Daten, aber bei Wetterwechsel (z.B. Wind dreht) kann eine Stunde alte Daten die Entscheidung verzögern. Da die Re-Mess nur einmal pro Stunde stattfindet, ist das Risiko gering, aber **die Buffer-Leerung (R1-Q6) eliminiert dieses Problem vollständig**.

**Empfehlung:** Wie in R1-Q6 – Buffer leeren bei Phase-Wechsel. Dann ist D.5 irrelevant.

### R1-Q8 — D.7 scoring_mode-Wechsel

**Bewertung:** Buffer leeren ist richtig, weil Normal vs. DX unterschiedliche Score-Bereiche haben (DX filtert SNR<-10 raus). Ein Mix aus alten Normal-Scores und neuen DX-Scores wäre nicht vergleichbar. Zudem: `DiversityController` hat bereits einen `scoring_mode`-Setter, der aktuell nur die Print-Statements ändert – dort einen `_dynamic_buffers.reset()`-Aufruf einzubauen ist einfach.

**Empfehlung:** Füge `self._reset_dynamic_buffers()` im `scoring_mode`-Setter von `DiversityController` ein. Damit automatisch beim Umschalten.

---

## E.4 Tests

### R1-Q9 — Test-Coverage

**Bewertung:** V1 hatte gar keine Test-Liste. V2 erwähnt 15-20 Tests. Das ist machbar. Folgende **Test-Klassen** sind nötig:

1. **Unit-Tests für DynamicDiversityController** (bzw. `_evaluate_dynamic`):
   - `test_record_slot_normal` – eine Antenne fügt Werte hinzu
   - `test_buffer_size` – maxlen=5, alter fliegt raus
   - `test_evaluate_both_full` – beide Puffer voll, Auswertung läuft
   - `test_evaluate_not_both_full` – kein Evaluate
   - `test_evaluate_threshold` – rel_diff < 0.08 → 50:50
   - `test_evaluate_A1_better` – stärkere A1 → 70:30
   - `test_evaluate_A2_better` → 30:70
   - `test_evaluate_low_peak` – MIN_PEAK_SCORE ≤5 → 50:50
   - `test_reset` – Buffer leeren nach reset()
   - `test_activate_deactivate` – _active Flag
   - `test_scoring_mode_switch` – Buffer gelöscht

2. **Integration-Tests (mw_cycle-Hook + Settings-Toggle)**:
   - `test_hook_called_when_active` – Toggle AN + Diversity AN + Phase=operate + RX-Slot
   - `test_hook_not_called_when_toggle_off`
   - `test_hook_not_called_during_measure_phase`
   - `test_hook_not_called_tx_slot`
   - `test_hook_zero_stations` – keine Dekodierung, kein Eintrag
   - `test_settings_toggle_nonpersistent` – toggle nach Neustart wieder AUS

3. **Threading-Tests** (mit `threading.Thread` + `time.sleep`):
   - `test_parallel_record_and_deactivate` – ohne Lock müsste crashen, mit Lock nicht
   - `test_ratio_setter_race` – decoder-thread setzt ratio, main-thread liest choose()

4. **Edge-Case-Tests**:
   - D.1: `test_static_remeasure_buffer_cleared` – Phase=measure → Phase=operate, Buffer leer
   - D.2: `test_toggle_race_mid_slot` – Toggle AN während Slot läuft
   - D.3: `test_app_quit_cleanup` – kein Hängenbleiben
   - D.6: `test_zero_stations_no_entry`

**Empfehlung:** 20-25 Tests als Grundlage für V3. Vorhandene Testinfrastruktur nutzen (pytest + QtTest für Signale).

### R1-Q10 — Mock-Strategie

**Bewertung:** Bestehende Tests in `tests/test_omni_cq_signal.py` mocken den Encoder und DiversityController. Analog für Dynamic:
- `MockDecoder` (liefert messages mit SNR)
- `MockDiversityController` (simuliert `choose()`-Ergebnisse)
- `MockTimer` (cycle_duration)
- `MockRadio` (für Antennen-Commando)

**Empfehlung:** Schreibe eine `tests/conftest.py` mit Fixtures für `dynamic_ctrl` (direkt `DiversityController` mit `_dynamic_enabled=True`), `mock_messages` (verschiedene SNRs). Für Integrationstests: `MainWindow` in Test-Mode starten (siehe `tests/test_main_window.py`).

---

## E.5 UI + Settings

### R1-Q11 — Toggle nicht persistiert

**Bewertung:** Option **C** (Settings persistiert es, App-Start setzt zurück auf False) ist die **schlechteste**, weil es verwirrt: Mike setzt Toggle AN, beendet App, startet neu, sieht Toggle AUS, denkt „Bug". Option **A** (Eigene Property in MainWindow) ist KISS, aber dann fehlt der zentrale Zugriff über `self.settings`. Option **B** (RAM-only-Field in Settings-Klasse) ist am saubersten: Die `Settings`-Klasse hat ein `dynamic_diversity_enabled`-Property, das nicht in `settings.json` serialisiert wird. Beim App-Start auf `False` gesetzt.

**Empfehlung:** Implementiere **Option B**: Füge in `config/settings.py` eine Property `dynamic_diversity_enabled` hinzu, die in `__init__` den Default `False` setzt und in `_serialize`/`_deserialize` ignoriert wird. Der Settings-Dialog liest/schreibt diese Property direkt (wie andere Einstellungen auch). Das ist konsistent und erweiterbar für Stufe 2.

### R1-Q12 — Statusbar-Format

**Bewertung:** `_update_statusbar()` in `main_window.py` hat einen großen if-elif-Block. Aktuell (Stand Code nicht vollständig, aber erkennbar in mw_cycle.py) gibt es dort einen Abschnitt für OMNI-Counter (`self._omni_cq.cq_remaining_display`). **Empfehlung:** Füge den dyn-Badge direkt **nach** dem OMNI-Counter ein, getrennt durch ein Leerzeichen. Beispiel:

```python
if getattr(self, '_dynamic_ctrl', None) and self._dynamic_ctrl.active:
    dynamic_text = f"  dyn {self._diversity_ctrl.ratio}"
else:
    dynamic_text = ""
# ... bestehender Text ...
status_text = f"OMNI {omni_text}{dynamic_text}  DT {dt_text}"
```

Platz-Konflikt ist gering, da OMNI-Counter bei inaktivem OMNI leer ist. Wenn Statusbar zu lang wird, kann Mike später kürzen.

### R1-Q13 — Tooltip-Wortlaut

**Bewertung:** OK, aber ein Verbesserungsvorschlag:
> „Aktiviert die dynamische Anpassung des Antennen-Verhältnisses während des Betriebs. Ohne diese Option wird das Verhältnis nur einmal pro Stunde neu berechnet. Mit Option wird es kontinuierlich (ca. alle 1-2 Minuten) optimiert. Nur im Diversity-Modus wirksam."

Der ursprüngliche Tooltip ist auch verständlich, aber „Testphase" könnte Mike verunsichern. Da V1 die Testphase bewusst macht, ist es okay, aber für V3 (wenn Feldtest positiv) sollte der Tooltip das Wort „Testphase" entfernen. Für V2/V3: „...nachjustiert (~jede Minute). Nur im Diversity-Modus aktiv." reicht.

---

## E.6 Stufe 2 (Statik entfernen)

### R1-Q14 — Code-Stellen für Stufe 2

**Bewertung:** Eine Liste ist hilfreich für zukünftige Planung. Basierend auf dem vorhandenen Code:

| Datei:Zeile (ungefähr) | Was muss weg/refaktorisiert |
| --- | --- |
| `core/diversity.py:108-109` | `REMEASURE_INTERVAL_SECONDS = 3600` (entfernen) |
| `core/diversity.py:124-160` | `should_remeasure()`, `start_measure()`, `on_band_change()` (diese Methoden werden obsolet) |
| `core/diversity.py:150-154` | `_phase = "measure"`, `_measure_step`, `_measurements` (entfernen) |
| `core/diversity.py:199-215` | `_evaluate()` (statische Variante) – durch Dynamic-Version ersetzen |
| `core/diversity.py:218-226` | `on_operate_cycle()` (entfernen, da keine statische Betriebsphase) |
| `ui/mw_cycle.py:130-190` | `_handle_diversity_measure()` (kompletter Block entfernen, da keine statische Messung) |
| `ui/mw_cycle.py:195-240` | `_handle_diversity_operate` könnte vereinfacht werden, da keine `was_phase`-Unterscheidung mehr nötig |
| `core/preset_store.py:120-125` | `save_ratio` wird nicht mehr von Statik aufgerufen, nur noch von Dynamic |
| `config/settings.py` | `diversity_presets`-Serialisierung (optional entfernen) |

**Empfehlung:** Diese Liste in V3 als Kommentarblock aufnehmen (nicht als ausführbaren Code). Stufe 2 wird dann auf Basis dieser Liste geplant.

---

## E.7 Modulnamen + API-Design

### R1-Q15 — Modulname

**Bewertung:** Wenn man doch ein separates Modul wählt (entgegen meiner Empfehlung in R1-Q1), dann sollte der Name zur bestehenden Konvention passen: `core/diversity.py` (statisch), `core/diversity_merger.py` (existiert bereits? Nein, aber `core/diversity.py` enthält `DiversityController`). Die Konvention ist `kleinschrift_mit_unterstrich`. `core/dynamic_diversity.py` ist OK, aber besser: `core/diversity_dynamic.py` (Adjektiv vor Nomen, alphabetisch sortiert). Im Projekt gibt es `core/diversity.py` → `core/diversity_dynamic.py` wäre systematisch. Alternativ `core/live_ratio.py` – zu generisch, passt nicht zur Namenskonvention (andere Module heißen nach Funktion, nicht nach Metapher).

**Empfehlung:** **`core/diversity_dynamic.py`** (falls Modul), oder **kein Modul** (Integration in `core/diversity.py`).

### R1-Q16 — Settings-Default + Migration

**Bewertung:** Der Key `dynamic_diversity_enabled` existiert nicht in bestehenden Settings. Beim ersten Laden gibt es einen `AttributeError` oder `KeyError`, abhängig von der Settings-Implementierung. Ein `getattr` mit Default ist notwendig, aber besser: **Registration des Keys mit Default in `Settings.__init__`**.

**Empfehlung:** Füge in `Settings.__init__` den Eintrag `self._dynamic_enabled = False` hinzu. In `_serialize` und `_deserialize` muss dieser Key nicht auftauchen (RAM-only). Damit ist beim ersten Zugriff immer `False` garantiert, ohne `getattr`-Fallback. Migration entfällt.

---

## F. Weitere Beobachtungen und Lücken

### Fehlende ACs in V2

- **Kein AC für Buffer-Leerung bei Phase-Wechsel measure→operate** (siehe D.1). Muss in V3 aufgenommen werden.
- **Kein AC für TX-Schutz**: Im Dynamic-Pfad muss sichergestellt sein, dass TX-Slots nicht in den Buffer geschrieben werden (V1 §3.3 sagt bereits „TX = kein Eintrag", aber kein expliziter AC).
- **Kein AC für Initialisierung nach App-Start**: Nach App-Start ist `_dynamic_enabled=False`, auch wenn Diversity aktiv ist. Der Buffer ist leer. Sobald Mike den Toggle AN setzt, muss die Datenerfassung starten – auch wenn die statische Pipeline noch gar nicht gelaufen ist (Phase=operate gilt erst nach statischer Messung). Wenn der Toggle unmittelbar nach App-Start gedrückt wird, ist Phase=„measure"?
  - Im Code: Nach App-Start ist `DiversityController.phase="measure"` (siehe `DiversityController.reset()` setzt `self._phase = "measure"`). Also **Dynamic würde nicht starten** bis die erste statische Messung durchgelaufen ist. Das ist richtig, aber muss in ACs dokumentiert werden.

### GUI-Thread-Sperrung bei `_evaluate_dynamic()`

Der Algorithmus `_evaluate_dynamic()` verwendet `statistics.median`, das ist CPU-lastig (O(n log n) aber mit n=5 trivial). Sollte im Decoder-Thread laufen, kein Problem. Aber wenn er im GUI-Thread (z.B. über Signal) aufgerufen würde, könnte es zu kurzen Hängern kommen. **Stelle sicher, dass `record_slot()` im Decoder-Thread aufgerufen wird und `_evaluate_dynamic()` dort inline ausgeführt wird.** Die Signal-Emittierung ist dann der einzige GUI-Bridge-Call.

### Statusbar-Platz-Konflikt (F)

Ich habe in `mw_cycle.py` gesehen, dass die Statusbar bereits DT-Korrektur, OMNI-Counter und evtl. andere Infos anzeigt. Der Platz ist begrenzt. **Empfehlung:** Das `dyn 72:28` nur anzeigen, wenn Toggle AN + Diversity aktiv + Phase=operate. Wenn statische Messung läuft (Phase=measure), zeige nichts (oder „dyn ..." (ausgesetzt)). Der Platz sollte reichen, da OMNI-Counter bei inaktivem OMNI leer ist. Falls nicht, könnte man auf `72:28` (ohne „dyn") verkürzen, aber Mike versteht dann nicht, dass es dynamisch ist. Besser: Format `↻d 72:28` (↻ = Unicode-Symbol für „dynamisch", aber nicht sicher ob Fonts das haben). Alternative: farbliches Hervorheben des vorhandenen Ratios (z.B. blau wenn dynamisch, grau wenn statisch). **Vorschlag für V3:** Füge ein `style`-Attribut zum Label hinzu: `color: #3366CC; font-weight: bold` für dynamisch, normal für statisch. Dann kann das Label einfach das Ratio anzeigen, und der Benutzer sieht an der Farbe den Modus.

### Re-Mess-Stoppen während Dynamic (F)

Mike-Spezifikation sagt „beide parallel". Das bedeutet, die statische 1h-Frist läuft weiter, auch wenn Dynamic aktiv ist. Nach 1h wird eine neue statische Messung gestartet (Phase=measure), Dynamic pausiert, dann nach 6 Slots wieder Phase=operate, Dynamic läuft weiter. **Das ist korrekt und sollte so bleiben.** Die statische Messung ist unabhängig und liefert einen frischen „Referenzwert", den Dynamic überschreiben kann. Für Stufe 2 wird dieser Mechanismus komplett entfernt.

### Diversity_Standard vs. Diversity_DX – ein gemeinsamer Buffer?

Richtig: ein Buffer, weil `scoring_mode`-Wechsel den Buffer leert (D.7). Die Buffer sind nur nach Modus-Wechsel getrennt, aber der Wechsel leert sie. Die `_diversity_ctrl`-Instanz ist für den aktuellen `scoring_mode` zuständig; wenn der User im Settings-Dialog den Mode ändert, wird `scoring_mode` gesetzt, was den Buffer leert. **Das ist sauber.**

---

## G. Gesamteindruck und Empfehlung für V3

**Stärken der V2:**
- Sehr detaillierte Lifecycle-Tabelle
- Klare Edge-Case-Dokumentation (D.1–D.7)
- Konkrete Code-Verweise auf mw_cycle.py
- Score-Formel verifiziert
- 16 Prüfaufträge sind umfassend

**Schwächen (müssen in V3 behoben werden):**
1. **Entscheidung Modul vs. Flag** (R1-Q1) – ich empfehle Flag in `DiversityController` (KISS).
2. **Fehlende ACs** (Buffer-Leerung bei Phase-Wechsel, TX-Schutz, App-Start-Phase)
3. **Threading-Lock für `_active` und `ratio`/`dominant`** (R1-Q3/Q4) – muss explizit in Spec.
4. **Test-Liste fehlt komplett** – 20 Tests definieren.
5. **Settings-Persistenz-Entscheidung** (R1-Q11) – RAM-only Property.
6. **Statusbar-Platz- und Farbkonzept** noch nicht gelöst.

**Nächste Schritte für V3:**
- Entscheidungen aus R1 in die Spec einfließen lassen (durch Bennenung der Empfehlung).
- Eine **1-Seiten-Zusammenfassung** für Mike (klar, deutsch, ohne Fachjargon).
- **Implementierungs-Plan**: 6 atomare Commits wie in V1, aber jetzt mit konkreten Code-Änderungen (z.B. `core/diversity.py` Zeilen 140-160 neu, `mw_cycle.py` Zeilen 100-110 Hook).
- **Test-Liste**: 20 Testfälle mit kurzer Beschreibung.
- **Field-Test-Checkliste**: Was soll Mike nach dem Code-Einspielen testen? (Toggle an/aus, Bandwechsel, Moduswechsel, 1h-Frist abwarten, Statik/Parallelität prüfen).

---

## H. Antwort auf die 16 Fragen (Kurzfassung für direktes Zitat)

1. **R1-Q1:** Flag in `DiversityController` besser als neues Modul.  
2. **R1-Q2:** Ja, Helper `compute_slot_score(messages)` in `core/diversity.py`.  
3. **R1-Q3:** Lock nötig – `_active`-Zugriffe in `record_slot()` und `deactivate()` müssen unter Lock.  
4. **R1-Q4:** Lock für `ratio`/`dominant`-Setter + `choose()` (bestehenden `_diversity_lock` nutzen).  
5. **R1-Q5:** Signal + QueuedConnection ist korrekt. Achtung separates Signal.  
6. **R1-Q6:** Variante (a) – Buffer bei Phase-Wechsel measure→operate leeren.  
7. **R1-Q7:** Durch (a) obsolet.  
8. **R1-Q8:** Buffer leeren bei scoring_mode-Wechsel – korrekt.  
9. **R1-Q9:** 20-25 Tests nötig (Liste siehe oben).  
10. **R1-Q10:** Mock-Strategie analog `test_omni_cq_signal.py` – Decoder, Timer, DiversityController mocken.  
11. **R1-Q11:** Option B – RAM-only Property in `Settings`.  
12. **R1-Q12:** Nach OMNI-Counter einfügen, farbliche Hervorhebung (blau für dynamisch).  
13. **R1-Q13:** Tooltip ist OK, aber „Testphase" evtl. weglassen.  
14. **R1-Q14:** Liste der zu entfernenden Code-Stellen (siehe oben) in V3 aufnehmen.  
15. **R1-Q15:** `core/diversity.py` (kein Modul) oder falls doch: `core/diversity_dynamic.py`.  
16. **R1-Q16:** Key in `Settings.__init__` registrieren, nicht in Serialisierung – keine Migration nötig.

---

**Abschluss:** V2 ist ein solides Self-Review, aber die kritischen Architekturentscheidungen (Modul vs. Flag, Locking, Buffer-Leerung) müssen in V3 final festgelegt werden. Nach Umsetzung der R1-Empfehlungen ist die Spec bereit für die Implementierung.
