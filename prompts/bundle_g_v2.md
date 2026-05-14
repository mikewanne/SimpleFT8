# Bundle G — V2 (Self-Review)

**Basis:** `bundle_g_v1.md`

## Findings

### L1 — Scoring-Mode-Werte verifiziert

Code-grep `core/diversity.py:82`: `scoring_mode in ("normal", "dx")`.
„normal" = Diversity Standard, „dx" = Diversity DX. V1-Plan korrekt.

### L2 — `_activate_diversity_with_scoring` durchläuft Cache-Dispatch

`mw_radio.py:633` ruft `_activate_diversity_with_scoring(scoring)` → setzt
`_rx_mode="diversity"`, `_diversity_stations={}`, Label, dann
`_check_diversity_preset` → bei missing Gain in Ziel-Store → DXTuneDialog.

**Konsequenz:** Toggle DX → Std mit leerem Standard-Gain-Store löst
Mess aus. Das ist gewollt (ohne Gain keine sinnvolle Antennen-Mischung).
Falls Mike's W2 (Gain-Sharing) später kommt, ist Mess hier obsolet.
**OK für jetzt.**

### L3 — OMNI-CQ + Auto-Hunt bei Sub-Mode-Toggle

`_on_rx_mode_changed` Z.541-544 stoppt OMNI + Auto-Hunt NUR bei
`mode != old_mode`. Bei Sub-Mode-Toggle bleibt `mode == "diversity"`,
OMNI+Hunt laufen weiter.

**Risiko-Analyse:**
- OMNI: nutzt `_diversity` indirekt für `get_free_cq_freq`, aber Encoder
  hat eigenen State. Toggle setzt `_diversity_stations={}` aber nicht
  Encoder. Sub-Mode-Wechsel sollte OMNI nicht stören (Encoder
  unbetroffen).
- Auto-Hunt: arbeitet auf rx_panel-Daten, nicht direkt auf scoring_mode.
  Toggle sollte transparent sein.
- DXTuneDialog bei Toggle mit fehlendem Gain: modal blockt alles inkl.
  OMNI-Slot-Tick? **Verifizieren.** `_gain_measure_locked`-Flag wird
  während Phase 2 gesetzt → blockiert RX-Mode-Wechsel. Aber OMNI-
  Slot-Tick prüft das nicht.

**Pragma-Entscheidung:** Bundle G OMNI+Hunt UNVERÄNDERT lassen. Falls
Mike Probleme sieht: separater Fix. Memory: Bundle G Mike-Spec war
„Toggle ohne Dialog" — nicht „Toggle stoppt alles".

### L4 — Bandpilot „manual" Mode

`bandpilot_mode` hat 3 Werte: `"off"`, `"auto"`, `"manual"`. V1 sagt nur
„Auto = kein Toggle". Was bei „manual"?

**Manual-Mode:** User klickt im Manual-Dialog auf Recommendation. Der
Manual-Dialog erscheint asynchron (nicht jeder Diversity-Klick).
Toggle-Verhalten:
- `bp_mode == "off"` → **Toggle JA**
- `bp_mode == "auto"` → kein Toggle (Bandpilot entscheidet)
- `bp_mode == "manual"` → ??? — Konservativ: kein Toggle (User soll
  Manual-Dialog nutzen)

**V3-Entscheidung:** Toggle nur bei `bp_mode == "off"`. R1-Bestätigung.

### L5 — Tests mit echtem DiversityController

Memory-Lesson `feedback_test_critical_path_not_mock.md`: kritischer
Pfad nicht mocken. Bundle G testet hauptsächlich:
- `_on_diversity_subtoggle_requested` Slot-Logik (state-Check)
- Signal-Verdrahtung

Slot-Test kann mit MagicMock für `_activate_diversity_with_scoring`
arbeiten (das ist Ziel-Funktion, nicht Test-Pfad). Aber 1 Sanity-Test
mit echtem DiversityController um `scoring_mode`-Property zu prüfen.

### L6 — Signal-Naming

`diversity_subtoggle_requested` ist klar genug. Alternative
`scoring_toggle_requested` wäre kürzer aber weniger explizit.
**V3-Entscheidung:** bleibt bei V1-Namen.

### L7 — Bandpilot-Pending während Toggle

Bandpilot-Pending-Tupel (5-elementig) wird beim normalen RX-Mode-Wechsel
verworfen via Bundle E R1-F3. Bei Sub-Mode-Toggle wird `_on_rx_mode_changed`
NICHT gerufen — Pending bleibt. Bandpilot kann beim TX-Finish auf alten
Sub-Modus zurückwechseln.

**Risiko:** klein, weil Bandpilot=off Voraussetzung für Toggle ist —
also kann keine Pending-Bandpilot-Aktion existieren wenn Toggle erlaubt.
**OK.**

### L8 — Visual-Feedback bei Toggle

`_activate_diversity_with_scoring` setzt `btn_diversity.setText(
"DIVERSITY DX" oder "DIVERSITY")`. Bei Toggle DX→Std würde Label
„DIVERSITY DX" → „DIVERSITY" wechseln. **OK, automatisch.**

### L9 — Field-Test-Erweiterung

V1 F1-F5 ist gut. Ergänzen:
- F6: Toggle DX→Std mit frischem Standard-Gain → kein DXTuneDialog,
  direkt Live-Mode (heute durch Cache-Logik)
- F7: Toggle Std→DX mit fehlendem DX-Gain → DXTuneDialog erscheint
  (heutiger Cache-Pfad, kein Bug)

### L10 — Dokumentation

`docs/explained/bandpilot_de.md` + `bandpilot.md` erwähnen heute die
Bandpilot-Modi. Toggle-Logik gehört dort NICHT rein (Toggle ist
Manuel-Pfad). Aber Memory + HISTORY + HANDOFF müssen Bundle G
dokumentieren.

## V3-Pflicht

- AC1: Signal `diversity_subtoggle_requested = Signal()` in
  `control_panel.py`
- AC2: Early-exit-Branch in `_on_rx_mode_clicked` ersetzen durch
  Toggle-Request-Emit
- AC3: Slot `_on_diversity_subtoggle_requested` in `mw_radio.py` mit
  3-fach-Guard (bp_mode, gain_lock, radio.ip)
- AC4: Signal-Connect in `main_window.py`
- AC5: 7 Tests in `test_bundle_g.py`
- AC6: APP_VERSION → 0.97.24 + Doku + Memory
