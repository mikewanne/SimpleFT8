Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P92 — Diversity-Sub-Toggle auch bei Bandpilot=AN

## 1. Ziel

Im Diversity-Modus soll der 2. Klick auf den DIVERSITY-Button **immer**
einen direkten Toggle Standard ↔ DX auslösen — unabhängig davon, ob
Bandpilot in Settings auf `off`, `auto` oder `manual` steht.

Mike-Begründung: Bandpilot ist eine Empfehlung, kein Zwang. Der User
muss seinen Diversity-Sub-Modus jederzeit überstimmen können (analog
zum bereits möglichen Wechsel NORMAL ↔ DIVERSITY).

**Mike's Workflow-Spec:** Override gilt nur, bis User selbst das Band
wechselt. Beim nächsten Bandwechsel soll Bandpilot wieder die Empfehlung
übernehmen.

**Heutiges Symptom:** bei `bandpilot_mode != "off"` ist der Sub-Toggle
gesperrt (`ui/mw_radio.py:895-897`). User muss heute über den Umweg
DIVERSITY-DX → NORMAL → DIVERSITY → Wahl-Dialog → STANDARD wechseln.

## 2. Akzeptanzkriterien

- **AC1** `_on_diversity_subtoggle_requested` toggled Std↔DX bei allen
  drei Bandpilot-Modi (`off` / `auto` / `manual`), solange Radio
  verbunden und Pipeline-Lock frei.
- **AC2** Bandpilot übernimmt nach dem manuellen Override beim nächsten
  Bandwechsel automatisch wieder die Steuerung. Implementierung:
  Bandpilot ist bereits stateless bzgl. User-Override
  (`_maybe_apply_bandpilot` in `mw_radio.py:1010-1058` prüft kein
  Override-Flag); kein neuer Code nötig. **Test:** Code-Inspection-
  Assert dass `_maybe_apply_bandpilot` keinen User-Override-State liest.
- **AC3** Im Sub-Toggle-Pfad weiterhin OMNI + Auto-Hunt stoppen (R1-K1+K2
  aus Bundle G — verhindert Encoder-Konflikt wenn Toggle einen
  DXTuneDialog auslöst und schützt vor get_free_cq_freq-Race auf
  leeres Stations-Histogramm nach `_diversity_stations = {}`).
- **AC4** Pipeline-Lock (`_gain_measure_locked`) und fehlende Radio-IP
  blocken weiterhin (Hardware-Sicherheit).
- **AC5** Bundle-G-Tests die heute „bp != off blockt" prüfen, werden
  umgeschrieben auf neues Verhalten:
  - `tests/test_bundle_g.py::test_no_toggle_when_bandpilot_auto`
    (Z.87-93) → `test_toggle_dx_to_standard_when_bandpilot_auto`
  - `tests/test_bundle_g.py::test_no_toggle_when_bandpilot_manual`
    (Z.97-103) → `test_toggle_standard_to_dx_when_bandpilot_manual`
- **AC6** Neue Tests T1-T6 in `tests/test_p92_diversity_subtoggle_bandpilot.py`
  (siehe Sektion 6).

## 3. Betroffene Module/Dateien

- `ui/mw_radio.py:879-909` `_on_diversity_subtoggle_requested` —
  Z.895-897 Block-Klausel entfernen, Docstring entsprechend aktualisieren
  (Hinweis „Nur wirksam wenn Bandpilot=off" raus).
- `tests/test_bundle_g.py` — 2 Tests umschreiben (AC5).
- `tests/test_p92_diversity_subtoggle_bandpilot.py` — NEU, 6 Tests.
- `main.py` — `APP_VERSION` 0.97.61 → 0.97.62.
- `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` — Standard-Update.

## 4. Randbedingungen

- **Threading:** Slot läuft im GUI-Thread, kein Lock nötig.
- **Hardware:** Sub-Toggle löst keinen direkten TX aus (nur RX-Mode-
  Wechsel mit ggf. anschließendem Gain-Mess-TUNE, dessen ANT1-Setup
  unverändert im bestehenden Pfad liegt). CLAUDE.md ANT1=TX-Pflicht
  bleibt erfüllt.
- **State:** Bandpilot ist stateless bzgl. User-Overrides. Bei
  `_on_band_changed` (`mw_radio.py:664`) wird `_maybe_apply_bandpilot`
  unkonditioniert aufgerufen und überschreibt den Modus, wenn
  `bp_mode != "off"` und eine Empfehlung vorliegt. Mike's „gilt bis
  Bandwechsel"-Anforderung ist damit ohne neuen Code erfüllt.
- **UX:** Kein neuer Dialog, kein Toast — der Sub-Toggle bleibt
  „silent" (analog Bundle-G `off`-Pfad).
- **Wechselwirkung Bundle-H-Pfad** (`mw_radio.py:748-803`, Klick
  NORMAL→DIVERSITY): bleibt komplett unverändert. Bei bp=auto/manual
  erscheint dort weiterhin Toast/Dialog. P92 ändert nur den 2. Klick
  innerhalb Diversity.
- **Konsistenz mit Toast/Bandpilot-Anzeige:** Wenn Bandpilot im
  bp=auto-Modus zuvor einen Toast „DX empfohlen" gezeigt hat und User
  toggled manuell zu Standard, divergiert die User-Wahl vom Toast.
  Das ist Mike's expliziter Wunsch (Override) und nicht zu „korrigieren"
  durch zusätzliche UI.

## 5. Nicht im Scope

- **Bandpilot-Logik selbst:** Empfehlungsalgorithmus, Toast/Dialog,
  Statistik-Aggregation bleiben unverändert.
- **Override-Persistenz / Sticky-Override-Flag:** explizit nicht — Mike
  will, dass Bandpilot beim nächsten Bandwechsel wieder übernimmt.
- **Bundle-H-Pfad** (NORMAL→DIVERSITY-Klick): bleibt komplett wie heute.
- **Auto-Hunt / OMNI Stop-Mechanismus:** unverändert.
- **UI-Indikation des Override-Status** (z.B. „Override aktiv"-Badge):
  nicht im Scope.

## 6. Testbarkeit

Neue Datei `tests/test_p92_diversity_subtoggle_bandpilot.py`:

- **T1** `test_toggle_standard_to_dx_when_bandpilot_auto`
  Setup `bandpilot_mode="auto"`, `scoring_mode="normal"`. Klick →
  `_activate_diversity_with_scoring("dx")` wird aufgerufen.
- **T2** `test_toggle_dx_to_standard_when_bandpilot_manual`
  Setup `bandpilot_mode="manual"`, `scoring_mode="dx"`. Klick →
  `_activate_diversity_with_scoring("normal")` wird aufgerufen.
- **T3** `test_pipeline_lock_blocks_toggle_in_all_bp_modes`
  Für jeden `bp_mode in ("off","auto","manual")` mit
  `_gain_measure_locked=True` → `_activate_diversity_with_scoring`
  wird nicht aufgerufen.
- **T4** `test_no_radio_ip_blocks_toggle_in_all_bp_modes`
  Analog T3 mit `radio.ip=None`.
- **T5** `test_omni_and_auto_hunt_stopped_on_toggle_in_bp_modes`
  OMNI active + Auto-Hunt active → beide `stop` werden mit
  `reason="scoring_toggle"` aufgerufen, dann Toggle.
- **T6** `test_maybe_apply_bandpilot_does_not_read_override_flag`
  Code-Inspection-Test: `_maybe_apply_bandpilot` (oder
  `_on_band_changed`) referenziert keinen Override-Persistenz-State
  (`grep` gegen Source dass weder „override" noch „last_user_choice"
  noch „sticky" als Variablenname auftaucht — Wächter für AC2).

Bundle-G-Tests anpassen:

- `test_no_toggle_when_bandpilot_auto` (Z.87-93) → wird durch T1 ersetzt.
  Falls einfacher: alten Test in den neuen Erwartungswert umschreiben
  und lassen, dann taucht T1 doppelt nicht auf.
- `test_no_toggle_when_bandpilot_manual` (Z.97-103) analog mit T2.

## 7. KISS-Bewertung

- **Code-Diff:** 2 Zeilen entfernen (`if bp_mode != "off": return`) +
  Docstring-Korrektur (3 Zeilen).
- **Komplexität:** keine. Bandpilot ist bereits stateless; Mike's
  „Override gilt bis Bandwechsel" ist Ist-Verhalten.
- **Risiko:** sehr klein. Einziger Side-Effect: bei bp=auto kann die
  Bandpilot-Toast-Empfehlung von der manuellen Wahl abweichen — Mike's
  expliziter Wunsch.

## Was prüfen

1. Habe ich Edge-Cases übersehen — z.B. Race zwischen Bandpilot-Auto-
   Switch und User-Sub-Toggle innerhalb derselben Slot-Iteration?
2. Sind die Tests AC-deckend, oder fehlt eine wichtige Annahme?
3. Ist der Hinweis im Docstring stark genug, dass spätere Mitleser
   verstehen, warum der Block weg ist?
4. Gibt es bei `_activate_diversity_with_scoring` einen Code-Pfad, der
   stillschweigend voraussetzt, dass Bandpilot ihn aufgerufen hat (nicht
   ein User-Toggle)? Insbesondere im Settings-Persistenz- oder
   Cache-Pfad?
5. Sollten wir zusätzlich loggen wann ein manueller Override über
   Bandpilot stattfindet — fürs Debugging?
6. KISS-Sicht: Übersehe ich, dass ein 2-Zeilen-Patch in einem so
   gefräßigen Pfad doch eine Architektur-Lücke öffnet, die wir später
   bereuen?
