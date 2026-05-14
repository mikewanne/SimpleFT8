# Bundle I — V3 — Settings-Spacing + QSO-komplett-Reihenfolge + OMNI-CQ-Race

**Datum:** 2026-05-14 nachmittags
**Version-Ziel:** v0.97.26
**Trigger:** Mike-Field-Test 14.05.2026 nachmittags
**Aufwand-Schätzung:** klein bis mittel — ~1 Tag inkl. Tests
**V3-Status:** nach DeepSeek-V4-pro-R1-Review, 5/5 Findings adressiert

---

## R1-Review Bilanz (V2 → V3)

**Modell:** `deepseek-v4-pro` (Erstnutzung seit 14.05. Migration). Tokens
in 71.064, out 7.748, total 78.812. Antwort-Zeit ~15s. R1 hat 5 Findings
geliefert; alle 5 nach Code-Verifikation angenommen.

| # | Severity | Status | Wirkung in V3 |
|---|---|---|---|
| 1 | Bug (rot) | ✅ angenommen | `encoder.abort()` + `ptt_off()` zusätzlich im Stop-Block |
| 2 | Risiko (orange) | ✅ angenommen | AC4.3 vereinfacht — Pending-Queue gibt's nicht mehr (P7-Refactor) |
| 3 | Risiko (orange) | ✅ angenommen | T4.2 erweitert um realistisches Encoder-Armed-Szenario |
| 4 | Hinweis (grau) | ✅ angenommen | T1.4 nutzt `pixelMetric` statt String-Match |
| 5 | Unklarheit (gelb) | ✅ selbst-geklärt | `_apply_normal_mode`-Pfade Z.464 + Z.1167 sind durch existierende Stop-Blocks abgedeckt — kein Zusatz-Code |

**V4-pro-Bewertung gegenüber V3-Default (R1-reasoner) erste Beobachtung:**
sehr stark bei Code-Halluzinations-Aufdeckung (Finding 2: CLAUDE.md-Notiz
zur Pending-Queue widerlegt). Schwach bei Klärungsfragen (Finding 5
auf „R1-Klärung herbeiführen" verlagert statt selbst Code zu prüfen).
Tracking für `docs/deepseek_lessons.md`-V4-Sektion.

---

## Ziel

Drei orthogonale Befunde aus Mike-Field-Test 14.05.2026 nachmittags
zusammen einspielen — alle klein bis mittel, gemeinsame Test-Suite
„Bundle I" hält Workflow-Overhead niedrig.

### Punkt 1 — Settings „Sichtbare Bänder" gedrungen

Bundle D (v0.97.21) hatte Spacing 6→10 erhöht. Mike-Visual-Check
14.05. Settings-Dialog FT8 & Diversity-Tab: 3×3-Checkbox-Raster
wirkt weiterhin gedrückt, Checkboxen kleben aneinander. Reine
UI-Verbesserung, keine Logik-Änderung.

### Punkt 2 — „✓ QSO komplett" vor Courtesy-73-Sendung

P33 (Bundle B', v0.97.14) führte 2-Signal-Split ein:
- `qso_confirmed_visual` SOFORT bei 73-Empfang (UI-Update)
- `qso_confirmed` NACH Courtesy-Send (OMNI-Resume, Auto-Hunt-Reset,
  Logbuch)

Mike-Field-Test 14.05.: Visual-Emit ist **zu früh**. Heute:

```
10:11:00 [E] Empf. 73                  ← 73 vom anderen
     ✓ QSO mit X komplett              ← zu früh
10:11:15 [O] Sende X DA1MHH 73 ↻10     ← unser Courtesy
```

Mike-Wunsch: visual NACH Courtesy-Send (zwischen Courtesy und
nächstem CQ). Mike-Begründung: „wenn wir IMMER das 2. 73 aus
Höflichkeit senden, können wir das QSO komplett auch danach
zeigen — dann ist das sauber und vor dem nächsten CQ."

Architektur-Lösung: `qso_confirmed_visual.emit` aus
`core/qso_state.py:692` (on_message_received 73-Branch) entfernen
und in den `TX_73_COURTESY`-Branch von `on_message_sent`
(`core/qso_state.py:530-539`) verschieben — direkt vor
`qso_confirmed.emit`. `on_message_sent` wird in
`ui/mw_qso.py:400` aus `_on_tx_finished` aufgerufen (PTT-off-
Callback) → exakt der gewünschte Zeitpunkt.

### Punkt 4 — OMNI-CQ Race beim Mode-Wechsel

Mike-Field-Test 14.05.: OMNI-CQ aktiv, Mode-Wechsel zwischen
Diversity-Submodi oder Diversity↔Normal, OMNI-Schalter geht
visuell aus, **EIN** weiterer CQ-Slot wird gesendet, danach
Stille. Screenshot zeigt `→ Sende CQ DA1MHH JO31` **ohne**
`↻N`-Suffix → TX kam aus normalem CQ-Pfad (`qso_sm.cq_mode`),
nicht aus OMNI selbst.

R1-bestätigter Bug: `ui/mw_radio.py:541-545` stoppt nur OMNI +
Auto-Hunt, lässt `qso_sm.cq_mode` UND einen evtl. armed-en
Encoder-Slot intakt.

**Fix-Pattern existiert schon** in `ui/mw_radio.py:404-414`
(Bandwechsel-Pfad):

```python
# BANDWECHSEL STOPPT ALLES
if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
    self.qso_sm.stop_cq()
    self.qso_sm.cancel()
    self.control_panel.set_cq_active(False)
if self.encoder.is_transmitting:
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
```

V3-Lösung: dieses Pattern in `_on_rx_mode_changed` Z.541-545
analog einbauen (R1 Finding 1).

---

## Akzeptanzkriterien

### Punkt 1 — Settings-Spacing

- **AC1.1** GroupBox „Sichtbare Bänder" hat Spacing ≥ 16 px in
  beide Richtungen — `bands_grid.setSpacing(16)`.
- **AC1.2** GroupBox-Innen-Margins `setContentsMargins(16, 16,
  16, 16)`.
- **AC1.3** Checkbox-Indicator 18×18 via Stylesheet auf `bands_group`:
  ```css
  QCheckBox::indicator { width: 18px; height: 18px; }
  ```
- **AC1.4** Label-Font der Checkbox-Texte +1 pt (optional, kostet
  nichts wenn Stylesheet eh dran ist).
- **AC1.5** Layout-Bruch verhindert — GroupBox-Breite darf um
  ≤ 30 px wachsen. Falls Settings-Tab insgesamt breiter wird ist
  das OK.
- **AC1.6** P50-Min-1-Logik (`_on_band_visibility_toggled`)
  unangetastet.
- **AC1.7** P50-Reset-Button setzt Werte korrekt zurück.
- **AC1.8** Stylesheet-Scope: nur auf `bands_group` setzen
  (`bands_group.setStyleSheet(...)`), nicht auf Dialog-Root.
  Andere QCheckBoxes im Settings-Dialog dürfen NICHT betroffen
  sein.

### Punkt 2 — QSO-komplett-Reihenfolge

- **AC2.1** Bei normalem QSO-Abschluss (73 ODER RR73-Empfang in
  `WAIT_73` + Courtesy-Send): Reihenfolge im QSO-Panel ist
  `Empf. 73|RR73` → `Sende 73` → `✓ QSO komplett` → (nächster Slot
  ggf. CQ).
- **AC2.2** WAIT_73-Timeout-Pfad
  (`core/qso_state.py:357-365`, kein 73/RR73 vom anderen, 3
  Cycles): visual + full direkt hintereinander, unverändert.
  Kein Courtesy-Send in diesem Pfad.
- **AC2.3** Force-73-Pfad via `advance()`
  (`core/qso_state.py:754-768`): profitiert automatisch von der
  Architektur-Änderung. `advance()` → `send_message.emit(73)` →
  Encoder → `_on_tx_finished` → `on_message_sent` → State
  `TX_73_COURTESY` → visual + full feuern dort.
- **AC2.4** Kein Doppel-Eintrag „✓ QSO komplett" — visual exakt
  einmal pro QSO.
- **AC2.5** `qso_confirmed` (full) feuert wie heute NACH
  Courtesy-Send. Reihenfolge `visual` vor `full` im selben Branch
  ist OK (Qt.DirectConnection, GUI-Thread).
- **AC2.6** Während Courtesy-Slot ist Bestätigungszeile NICHT im
  Panel — direkt nach 73-Empfang in WAIT_73 hat
  `qso_confirmed_visual`-Spy 0 Calls; nach `on_message_sent` mit
  State `TX_73_COURTESY` genau 1 Call.

**Bekannte Lücke (out of scope, dokumentieren):** wenn
Courtesy-Send abgebrochen wird (User klickt QSO Finish während TX,
App-Crash, Encoder-Fehler, Mode-Wechsel mid-Slot), fehlt die
Visual-Bestätigung obwohl `qso_complete` schon in TX_RR73
gefeuert wurde und das QSO im ADIF landet. Sehr selten. Fix-Plan:
falls Mike Bedarf meldet, könnte ein Fallback in `cancel()` /
`stop_cq()` das visual-Signal nachschießen wenn `qso_complete`
schon raus war. Heute: Doku-Hinweis in HISTORY genügt.

### Punkt 4 — OMNI-CQ Race-Stop

- **AC4.1** Beim RX-Mode-Wechsel (`ui/mw_radio.py:541-545`) Stop-
  Block analog Bandwechsel-Pattern (Z.404-414):
  ```python
  if mode != old_mode:
      if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
          self._omni_cq.stop("rx_mode_change")
      if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
          self._auto_hunt.stop_auto_hunt("rx_mode_change")
      # NEU Bundle I (R1 Finding 1):
      if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
          self.qso_sm.stop_cq()
          self.qso_sm.cancel()
          self.control_panel.set_cq_active(False)
      if self.encoder.is_transmitting:
          self.encoder.abort()
          if self.radio.ip:
              self.radio.ptt_off()
      self._easter_egg_active = False
  ```
- **AC4.2** Mike-Symptom abgedeckt: `cq_mode=True` vor Mode-
  Wechsel, `_on_rx_mode_changed("diversity")` aufgerufen, danach
  `cq_mode=False`, State=IDLE, `send_message`-Spy zeigt KEINEN
  neuen Emit.
- **AC4.3** Encoder-Sicherheit: falls beim Mode-Wechsel ein
  TX-Slot aktiv ist (`is_transmitting=True`), wird `encoder.abort()`
  + `ptt_off()` aufgerufen — Hardware-Sicherheit für FlexRadio.
  **R1 Finding 2 angenommen:** P5-Pending-Queue wurde durch
  P7.OMNI-SIMPLIFY (v0.96.4) entfernt — kein Queue-Leer-Code
  nötig. `abort()` reicht.
- **AC4.4** ANT1=TX-Pflicht: Stop-Block ruft kein
  `set_tx_antenna()` auf. `encoder.abort()` und `ptt_off()` sind
  antennen-agnostisch — Hardware-RX-Antenne bleibt unverändert.
- **AC4.5** Bandpilot programmatischer Mode-Wechsel:
  `_apply_bandpilot_auto` ruft `_on_rx_mode_changed` → unser
  Stop-Block feuert auch dort. Wenn Mike CQ ruft und Bandpilot
  auf Diversity schaltet, beendet das den CQ. Mike-Spec: Bandpilot
  ist ein User-getriggertes Auto-Switch (auto-Modus = User hat
  Auto angeschaltet), CQ-Stopp dabei OK.
- **AC4.6** `_apply_normal_mode` parallele Pfade — **R1 Finding 5
  selbst-geklärt:**
  - `mw_radio.py:464` (`_on_band_changed` → `_apply_normal_mode`):
    Stop-Block in `_on_band_changed` Z.404-414 wird VORHER
    durchlaufen. CQ schon gestoppt. ✅
  - `mw_radio.py:1167` (`_disable_diversity` → `_apply_normal_mode`):
    `_disable_diversity` wird primär aus `_on_rx_mode_changed`
    Z.553 gerufen — unser neuer Stop-Block ist VORHER (Z.541-545).
    Andere Aufrufer (Z.822, 834, 1588, 1592) sind interne Übergangs-
    Pfade ohne aktiven User-CQ. ✅
- **AC4.7** Tests grün nach Fix: bestehende Tests in
  `tests/test_modules.py` für `_on_rx_mode_changed` (T4.x) +
  neue Bundle-I-Tests müssen alle durch.

### Tests (verbindlich)

**Punkt 1 — Settings-Spacing:**
- T1.1 Settings-Dialog initialisiert ohne Crash (Smoke).
- T1.2 `_band_checkboxes` hat genau 9 Einträge.
- T1.3 P50 Min-1-Logik: 1 aktiv → letzte Checkbox `setEnabled(False)`.
- T1.4 **R1 Finding 4 angenommen:** Stylesheet-Effekt nachweisen
  via `QStyle.pixelMetric(QStyle.PM_IndicatorWidth, ...)` ≥ 18
  ODER direkt Stylesheet-String der GroupBox enthält `width: 18px`
  UND `height: 18px` (defensive doppelt — pixelMetric kann je
  nach Plattform/Style differieren).
- T1.5 **Negativ-Test (AC1.8):** Stylesheet auf `bands_group`,
  nicht auf Dialog-Root — andere QCheckBoxes im Dialog haben den
  Indicator-Override NICHT.

**Punkt 2 — QSO-Reihenfolge:**
- T2.1 In `WAIT_73`: 73 empfangen → `qso_confirmed_visual`-Spy
  hat 0 Calls direkt danach. State = `TX_73_COURTESY`.
- T2.2 `on_message_sent` mit State `TX_73_COURTESY` → visual + full
  feuern beide, je 1 Call, in dieser Reihenfolge.
- T2.3 WAIT_73-Timeout (3 Cycles): visual + full feuern direkt
  nacheinander (unverändert).
- T2.4 Force-73 via `advance()` in WAIT_73: visual feuert NICHT
  bei `advance()`-Aufruf, sondern erst beim folgenden
  `on_message_sent`-Aufruf in State `TX_73_COURTESY`.
- T2.5 Kein Doppel-Emit: 73-Empfang + `on_message_sent` zusammen
  → visual genau 1×.
- T2.6 RR73 statt 73 in WAIT_73 (`is_rr73`-Branch, Z.686):
  gleiche Reihenfolge wie bei 73.

**Punkt 4 — OMNI-Race:**
- T4.1 `_on_rx_mode_changed("diversity")` mit `qso_sm.cq_mode=True`
  → `qso_sm.stop_cq()` wird genau 1× aufgerufen.
- T4.2 **R1 Finding 3 angenommen — realistisches Szenario:**
  - Setup: `qso_sm.cq_mode=True`, State=`CQ_CALLING`,
    `encoder.is_transmitting=True` (mock), `send_message`-Spy
    bereits 1× durch initialen CQ aktiv.
  - Action: `_on_rx_mode_changed("diversity")`.
  - Asserts:
    - `qso_sm.stop_cq` 1× aufgerufen
    - `qso_sm.cancel` 1× aufgerufen
    - `encoder.abort` 1× aufgerufen
    - `radio.ptt_off` 1× aufgerufen (wenn radio.ip gesetzt)
    - `qso_sm.cq_mode == False`
    - `qso_sm.state == QSOState.IDLE`
    - Nach simulierten 2 Cycle-Ticks: `send_message`-Spy
      hat KEINE neuen Calls.
- T4.3 Mode-Wechsel ohne aktiven CQ
  (`cq_mode=False`, `state=IDLE`): `stop_cq()` wird NICHT
  aufgerufen, `cancel()` wird NICHT aufgerufen (Spy 0 Calls).
- T4.4 OMNI + qso_sm.cq_mode beide an: beide gestoppt korrekt.
  Reihenfolge im Code: OMNI vor qso_sm.stop_cq (entspricht
  bestehender Stop-Block-Ordnung).
- T4.5 `radio.set_tx_antenna`-Spy: nicht aufgerufen während
  `_on_rx_mode_changed`.
- T4.6 Bandpilot programmatischer Mode-Wechsel
  (`_apply_bandpilot_auto` → `_on_rx_mode_changed`):
  `qso_sm.stop_cq` wird aufgerufen (Mike-Spec: OK).
- T4.7 `encoder.is_transmitting=False`-Edge: Stop-Block wird
  durchlaufen, `encoder.abort` wird NICHT aufgerufen (Guard
  greift).

---

## Betroffene Module/Dateien

### Punkt 1
- `ui/settings_dialog.py:333-356` — GroupBox + Stylesheet
- `tests/test_settings_dialog_smoke.py` — Smoke + T1.1-T1.5

### Punkt 2
- `core/qso_state.py:685-715` — `WAIT_73`-Branch in
  `on_message_received`: `qso_confirmed_visual.emit` (Z.692)
  **entfernen** + Kommentar-Update
- `core/qso_state.py:530-539` — `TX_73_COURTESY`-Branch in
  `on_message_sent`: `qso_confirmed_visual.emit(self.qso)` vor
  `qso_confirmed.emit(self.qso)` **hinzufügen** + Kommentar-Update
- `core/qso_state.py:357-365` — WAIT_73-Timeout: unverändert
- `core/qso_state.py:754-768` — `advance()` Force-73: kein Eingriff
  (profitiert automatisch)
- Tests: `tests/test_p33_qso_komplett_reihenfolge.py` — T1-T6
  ggf. neu erwarten (siehe Tests-Sektion), neue T2.1-T2.6 wie oben.

### Punkt 4
- `ui/mw_radio.py:541-545` — Stop-Block-Erweiterung analog
  Bandwechsel-Pattern (Z.404-414)
- Tests: `tests/test_bundle_i_omni_race.py` (NEU) für T4.1-T4.7

---

## Randbedingungen

### Hardware-Pflicht ANT1=TX (CLAUDE.md HARDWARE-WARNUNG)
- Stop-Block ruft keine Antennen-Umschaltung auf. `encoder.abort()`
  und `ptt_off()` sind antennen-neutral. Test T4.5 sichert ab.

### KISS-Pflicht (CLAUDE.md Programmier-Leitsätze)
- Punkt 1: Werte-Änderung + Stylesheet, kein Refactor.
- Punkt 2: Signal-Verschiebung 2 Zeilen.
- Punkt 4: Stop-Block-Erweiterung ~6 Zeilen analog vorhandenes Pattern.

### Threading
- `_on_rx_mode_changed` ist GUI-Thread-Slot.
- `qso_sm.stop_cq()`, `qso_sm.cancel()`, `encoder.abort()`,
  `radio.ptt_off()` sind alle bereits an mehreren Stellen
  GUI-Thread-aufgerufen → thread-safe-bekannt.

### Tests grün
- `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`
  vor jedem Commit grün.
- Vor Bundle I: 1205 (v0.97.25).
- Schätzung nach Bundle I: ~1215-1225.

### Backup vor Code-Änderung
- `Appsicherungen/2026-05-14_v0.97.25_vor_bundle_i/` anlegen.

### Doku-Pflicht nach Bundle (CLAUDE.md §0-Reihenfolge)
1. HISTORY.md anhängen — `## 2026-05-14 v0.97.26 — Bundle I`
2. HANDOFF.md updaten
3. CLAUDE.md Header (Symlink in FT8/ aktualisiert sich)
4. TODO.md (Punkte 1/2/4 erledigt-Sektion)
5. Memory wenn Lesson gelernt — Kandidaten:
   - „Stop-Block bei Mode-Wechsel muss ALLE CQ-Pfade erfassen +
     Encoder-abort + ptt_off — analog Bandwechsel-Pattern" (Punkt 4)
   - „CLAUDE.md Notiz zu encoder Pending-Queue ist veraltet (P7-
     Refactor entfernte sie). Bei R1-Prompts prüfen ob Pattern noch
     existiert." (Lesson aus V4-pro Finding 2)
   - „V4-pro First-Look: stark bei Halluzinations-Aufdeckung in
     CLAUDE.md-Notizen, schwach bei Klärungsfragen (delegiert
     statt selbst Code zu prüfen)." (docs/deepseek_lessons.md)

### Memory-Lessons relevant
- `feedback_omni_separate_architecture.md` — OMNI-Struktur respektiert
- `feedback_partial_fix_check_other_paths.md` — Z.464 und Z.1167
  geprüft + abgedeckt
- `feedback_easter_egg_features_e2e_test.md` — OMNI-Test in
  Bundle-Suite
- `feedback_r1_encoder_busy_blindspot.md` — V4-pro hat das genau
  hier ANGESPROCHEN (Finding 1), nicht verpasst → Blindspot eher
  R1-spezifisch, nicht V4

---

## Nicht im Scope

- **Gain-Messung vereinheitlichen (P51)** — eigener Workflow, in
  TODO.md notiert.
- **Bundle-G/H Field-Tests** — separate Mike-Abnahmen.
- **OMNI-CQ Architektur-Eingriff** — Stop-Erweiterung im Mode-
  Wechsel-Pfad reicht.
- **P33-Architektur** (2-Signal-Split) bleibt — nur Timing ändert
  sich.
- **PSK-Reset bei Modus-Wechsel** — heute schon korrekt.
- **Encoder-Abort mid-Slot** — wir nutzen das existierende
  `encoder.abort()` Pattern. Kein neuer Abort-Mechanismus.
- **Bekannte Lücke Punkt 2:** Courtesy-Send-Fehler → visual fehlt.
  HISTORY-Doku-Hinweis, kein Fix in Bundle I.

---

## Implementations-Reihenfolge (atomare Commits)

1. **C1 — Backup** `Appsicherungen/2026-05-14_v0.97.25_vor_bundle_i/`
   (kein Git-Commit, nur Datei-Kopie)
2. **C2 — Punkt 1 Code:** `ui/settings_dialog.py` Stylesheet +
   Werte
3. **C3 — Punkt 1 Tests:** T1.1-T1.5 in
   `tests/test_settings_dialog_smoke.py`
4. **C4 — Punkt 2 Code:** `core/qso_state.py` Signal-Verschiebung
   + Kommentar-Update
5. **C5 — Punkt 2 Tests:** T2.1-T2.6 in
   `tests/test_p33_qso_komplett_reihenfolge.py`
6. **C6 — Punkt 4 Code:** `ui/mw_radio.py` Stop-Block-Erweiterung
7. **C7 — Punkt 4 Tests:** `tests/test_bundle_i_omni_race.py` NEU
   mit T4.1-T4.7
8. **C8 — APP_VERSION + Doku:** `main.py` v0.97.26, HISTORY,
   HANDOFF, CLAUDE, TODO, Memory

Final-R1-Codereview (Schritt 5b) NACH C7, VOR C8.

---

## Mike-Freigabe gewünscht

V3 wartet auf Mike's explizites OK. Bei OK:
- Backup (C1) + Code-Implementierung (C2-C7) starten
- Tests grün halten vor jedem Commit
- Final-R1-Codereview vor C8
- HISTORY+HANDOFF+CLAUDE+TODO+Memory nach Abschluss

Bei Änderungs-Wunsch zu V3: kein Code-Eingriff bis V4.

---

## V3-Ende
