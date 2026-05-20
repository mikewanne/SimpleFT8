# P92 — Diversity-Sub-Toggle auch bei Bandpilot=AN (V3)

## 1. Ziel

Im Diversity-Modus soll der 2. Klick auf den DIVERSITY-Button **immer**
einen direkten Toggle Standard ↔ DX auslösen — unabhängig davon, ob
Bandpilot in Settings auf `off`, `auto` oder `manual` steht.

Mike-Begründung: Bandpilot ist eine Empfehlung, kein Zwang. Der User
muss seinen Diversity-Sub-Modus jederzeit überstimmen können (analog
zum bereits möglichen Wechsel NORMAL ↔ DIVERSITY).

**Override-Lifetime (präzisiert nach R1-F3):** Der manuelle Sub-Modus
gilt, bis irgendein Bandwechsel ausgelöst wird (typischerweise vom
User über die Band-Buttons, programmatische Bandwechsel gibt es im
Diversity-Pfad heute nicht — Auto-Hunt/OMNI wechseln das Band nicht).
Bei jedem Bandwechsel ruft `_on_band_changed` automatisch
`_maybe_apply_bandpilot(band)`; das überschreibt den Modus genau dann,
wenn `bp_mode != "off"` UND eine Empfehlung vorliegt. Ohne Empfehlung
bleibt der manuell gewählte Sub-Modus bestehen (R1-F4).

**Heutiges Symptom:** bei `bandpilot_mode != "off"` ist der Sub-Toggle
gesperrt (`ui/mw_radio.py:895-897`). User muss heute den Umweg
DIVERSITY-DX → NORMAL → DIVERSITY → Wahl-Dialog → STANDARD nehmen.

## 2. Akzeptanzkriterien

- **AC1** `_on_diversity_subtoggle_requested` toggled Std↔DX bei allen
  drei Bandpilot-Modi (`off` / `auto` / `manual`), solange Radio
  verbunden und Pipeline-Lock frei.
- **AC2** Wenn beim nächsten Bandwechsel `bp_mode != "off"` **und** der
  Bandpilot eine gültige Empfehlung liefert, übernimmt er den Modus
  automatisch wieder. Andernfalls (rec=None oder bp=off) bleibt der
  manuell gewählte Sub-Modus aktiv. Implementierung: Bandpilot ist
  bereits stateless bzgl. User-Override (`_maybe_apply_bandpilot` in
  `mw_radio.py:1010-1058` prüft kein Override-Flag); kein neuer Code
  nötig.
- **AC3** Im Sub-Toggle-Pfad weiterhin OMNI + Auto-Hunt stoppen (R1-K1+K2
  aus Bundle G — verhindert Encoder-Konflikt wenn Toggle einen
  DXTuneDialog auslöst und schützt vor get_free_cq_freq-Race auf leeres
  Stations-Histogramm nach `_diversity_stations = {}`).
- **AC4** Pipeline-Lock (`_gain_measure_locked`) und fehlende Radio-IP
  blocken weiterhin (Hardware-Sicherheit).
- **AC5** Bundle-G-Tests die heute „bp != off blockt" prüfen, werden
  umgeschrieben auf neues Verhalten:
  - `tests/test_bundle_g.py::test_no_toggle_when_bandpilot_auto`
    (Z.87-93) → `test_toggle_standard_to_dx_when_bandpilot_auto`
    (Setup `scoring_mode="normal"`, Erwartung `_activate_diversity_with_scoring("dx")`)
  - `tests/test_bundle_g.py::test_no_toggle_when_bandpilot_manual`
    (Z.97-103) → `test_toggle_dx_to_standard_when_bandpilot_manual`
    (Setup `scoring_mode="dx"`, Erwartung `_activate_diversity_with_scoring("normal")`)
- **AC6** Neue Tests T1-T7 in `tests/test_p92_diversity_subtoggle_bandpilot.py`
  (siehe Sektion 6).
- **AC7** Tooltip in `ui/control_panel.py:1978-1981` an `btn_diversity`
  anpassen: „(nur bei Bandpilot=Aus)" entfernen.

## 3. Betroffene Module/Dateien

- `ui/mw_radio.py:879-909` `_on_diversity_subtoggle_requested` —
  Z.895-897 Block-Klausel entfernen, Docstring entsprechend aktualisieren
  (Hinweis „Nur wirksam wenn Bandpilot=off" raus, kurze Begründung
  P92 mit Mike-Spec einbauen).
- `ui/control_panel.py:1978-1981` — Tooltip an `btn_diversity` anpassen
  (R1-F2): „(nur bei Bandpilot=Aus)" raus.
- `tests/test_bundle_g.py` — 2 Tests umschreiben (AC5).
- `tests/test_p92_diversity_subtoggle_bandpilot.py` — NEU, 7 Tests.
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
  unkonditioniert aufgerufen und überschreibt den Modus genau dann,
  wenn `bp_mode != "off"` UND eine Empfehlung vorliegt. Ohne Empfehlung
  bleibt der manuelle Sub-Modus aktiv (R1-F4). Mike's „gilt bis
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
  Das ist Mike's expliziter Wunsch (Override) und wird nicht durch
  zusätzliche UI „korrigiert".

## 5. Nicht im Scope

- **Bandpilot-Logik selbst:** Empfehlungsalgorithmus, Toast/Dialog,
  Statistik-Aggregation bleiben unverändert.
- **Override-Persistenz / Sticky-Override-Flag:** explizit nicht — Mike
  will, dass Bandpilot beim nächsten Bandwechsel wieder übernimmt.
- **Bundle-H-Pfad** (NORMAL→DIVERSITY-Klick): bleibt komplett wie heute.
- **Auto-Hunt / OMNI Stop-Mechanismus:** unverändert.
- **UI-Indikation des Override-Status** (z.B. „Override aktiv"-Badge):
  nicht im Scope.
- **Log-Output für Override:** nicht im Scope (KISS, Debug-Bedarf gering).
- **Test-Konsolidierung** (Bundle-G + P92 in einer Datei): bewusst
  separat — P92-Tests stehen für sich, das erleichtert künftiges
  Suchen/Entfernen.

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
  Code-Inspection: `_maybe_apply_bandpilot`/`_on_band_changed`
  referenziert keinen Override-Persistenz-State (`grep` gegen Source
  dass weder „override" noch „last_user_choice" noch „sticky" als
  Variablenname auftaucht — Wächter für AC2).
- **T7** `test_bandpilot_takes_over_on_bandchange_after_manual_override`
  (R1-F5 Integration-Test):
  1. Setup `bandpilot_mode="auto"`, `scoring_mode="normal"`.
  2. Manueller Sub-Toggle → `scoring_mode="dx"`.
  3. Bandwechsel simulieren via `_on_band_changed("40m")` mit
     gemocktem Bandpilot der `decision_mode=diversity_normal`
     empfiehlt (=Empfehlung Standard).
  4. Assert: `_set_rx_mode_direct("diversity_normal")` wird aufgerufen
     (Bandpilot übernimmt wieder).
  - Zweiter Sub-Case: Bandpilot liefert rec=None → Bandpilot greift
    nicht ein, manuell gewählter DX-Modus bleibt aktiv.

Bundle-G-Tests anpassen (AC5):

- `test_no_toggle_when_bandpilot_auto` (Z.87-93) → umschreiben in
  `test_toggle_standard_to_dx_when_bandpilot_auto`.
- `test_no_toggle_when_bandpilot_manual` (Z.97-103) → umschreiben in
  `test_toggle_dx_to_standard_when_bandpilot_manual`.

## 7. KISS-Bewertung

- **Code-Diff:** 2 Zeilen entfernen (`if bp_mode != "off": return`) +
  Docstring-Korrektur (3 Zeilen) + Tooltip-Patch (1 Zeile).
- **Komplexität:** keine. Bandpilot ist bereits stateless.
- **Risiko:** sehr klein. Side-Effects:
  - Bei bp=auto kann die Bandpilot-Toast-Empfehlung von der manuellen
    Wahl abweichen — Mike's expliziter Wunsch.
  - Override-Lifetime: gilt bis zum nächsten Bandwechsel, **bei dem der
    Bandpilot eine gültige Empfehlung hat**. Ohne Empfehlung (rec=None
    oder bp=off) bleibt der manuelle Sub-Modus aktiv. (R1-F7 / AC2)

## R1-Findings Bilanz

| Schwere | Finding | Status |
|---|---|---|
| 🔴 F1 | Testnamen Setup-Inkonsistenz | ✅ Angenommen (AC5) |
| 🔴 F2 | Tooltip-Text in control_panel.py | ✅ Angenommen (AC7) |
| 🟠 F3 | „Bandwechsel"-Definition | ✅ Präzisiert (Ziel) |
| 🟠 F4 | AC2 Empfehlungs-Bedingung | ✅ Präzisiert (AC2) |
| 🟠 F5 | Integration-Test fehlt | ✅ Angenommen (T7) |
| 🟡 F6 | Tests konsolidieren | ❌ Abgelehnt — separate Datei = bessere Wartbarkeit; spätere Entfernung der P92-Spezifik ohne Bundle-G-Kollateralschaden |
| ⚪ F7 | KISS-Text präzisieren | ✅ Angenommen (Sek. 7) |
