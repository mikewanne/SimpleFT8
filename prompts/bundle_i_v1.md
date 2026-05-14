# Bundle I — V1 — Settings-Spacing + QSO-komplett-Reihenfolge + OMNI-CQ-Race

**Datum:** 2026-05-14 nachmittags
**Version-Ziel:** v0.97.26
**Trigger:** Mike-Field-Test 14.05.2026 nachmittags

---

## Ziel

Drei orthogonale Befunde aus dem Field-Test 14.05.2026 nachmittags
zusammen einspielen — alle sind klein bis mittel, gemeinsame Test-Suite
„Bundle I" hält den Workflow-Overhead niedrig.

**Punkt 1 — Settings „Sichtbare Bänder" gedrungen.** Bundle D
(v0.97.21) hatte schon Spacing 6→10 erhöht. Mike's Visual-Check
14.05. Screenshot: immer noch zu eng, 3×3-Raster wirkt gedrückt,
Checkboxen kleben aneinander.

**Punkt 2 — „✓ QSO komplett" vor Courtesy-73-Sendung.** P33 (Bundle B',
v0.97.14) hatte ein 2-Signal-Split eingeführt damit die Bestätigung
nicht NACH dem nächsten CQ erscheint. Sie feuert jetzt SOFORT bei
73-Empfang — ist aber zu früh, weil das Courtesy-73 (das wir
immer senden) erst danach raus geht. Reihenfolge in der QSO-Spalte
ist heute:

```
10:11:00 [E] Empf. 73                  ← 73 vom anderen
     ✓ QSO mit X komplett              ← visual SOFORT — falsch (zu früh)
10:11:15 [O] Sende X DA1MHH 73 ↻10     ← unser Courtesy
```

Erwartet: visual NACH Courtesy-Send, also zwischen Courtesy-Zeile und
nächstem CQ. Logisch sauber weil QSO erst dann „echt durch ist".

**Punkt 4 — OMNI-CQ Race beim Mode-Wechsel.** Mike-Field-Test:
OMNI-CQ war aktiv, Mode-Wechsel zwischen Diversity-Submodi (Std↔DX)
oder Diversity↔Normal, OMNI-Schalter geht visuell aus — aber EIN
weiterer CQ-Slot wird trotzdem gesendet. Danach Funkstille (Stop
greift letztendlich). Screenshot zeigt `→ Sende CQ DA1MHH JO31` ohne
`↻N`-Suffix, also über den **normalen CQ-Pfad** (`qso_sm.cq_mode`),
nicht über OMNI selbst.

Hypothese (Schritt-0-Verifikation): `_on_rx_mode_changed` in
`ui/mw_radio.py:541-545` stoppt explizit `_omni_cq.stop` und
`_auto_hunt.stop_auto_hunt`, lässt aber `qso_sm.cq_mode` und einen
ggf. schon armed-en Encoder-Slot intakt. Race ist also zwischen
„OMNI off + Mode-Reset" und „Encoder hat nächsten CQ-Slot schon
gequeued".

---

## Akzeptanzkriterien

### Punkt 1 — Settings-Spacing

- **AC1.1** GroupBox „Sichtbare Bänder" hat luftiges 3×3-Raster mit
  klar sichtbarem Spacing zwischen allen Reihen und Spalten (≥ 16 px).
- **AC1.2** GroupBox-Innen-Margins großzügig (≥ 16 px allseits).
- **AC1.3** Checkbox-Indicator deutlich größer als Default-13×13
  (Ziel: 18×18 via Stylesheet `QCheckBox::indicator { width: 18px;
  height: 18px; }`).
- **AC1.4** Label-Font der Checkbox-Texte +1 pt gegenüber Default.
- **AC1.5** GroupBox-Breite bleibt gleich (kein Layout-Bruch im
  Settings-Tab). Höhe darf um ≤ 60 px wachsen.
- **AC1.6** Min-1-Logik aus P50 funktioniert weiterhin (letzte
  aktivierte Checkbox bleibt `setEnabled(False)`).
- **AC1.7** Reset-Button setzt Werte korrekt zurück (P50-Verhalten
  unangetastet).

### Punkt 2 — QSO-komplett-Reihenfolge

- **AC2.1** Bei normalem QSO-Abschluss (73-Empfang + Courtesy-Send):
  Reihenfolge in QSO-Panel ist `Empf. 73` → `Sende 73` → `✓ QSO
  komplett` → (nächster CQ-Slot).
- **AC2.2** Im WAIT_73-Timeout-Pfad (kein 73 vom anderen, max 3
  Cycles, `qso_state.py:357-365`): visual + full direkt
  hintereinander, kein Unterschied zu heute (kein Courtesy-Send in
  diesem Pfad).
- **AC2.3** Im Force-73-Pfad via `advance()` (manuell `QSO Finish`
  in WAIT_73, `qso_state.py:754-768`): visual nach unserem 73,
  analog AC2.1.
- **AC2.4** Doppel-Eintrag „✓ QSO komplett" im Panel ist
  ausgeschlossen (P33-Originalbug).
- **AC2.5** `qso_confirmed` (full) feuert unverändert nach
  Courtesy-Send (für OMNI-Resume, Auto-Hunt-Reset, Logbuch — siehe
  P33-Kommentare in Code).
- **AC2.6** UI-Update zwischen Empf. 73 und Sende 73 (also visuell:
  während Courtesy-Slot im Gange) zeigt KEINE Bestätigung — die
  kommt erst nach Slot-Ende.

### Punkt 4 — OMNI-CQ Race-Stop

- **AC4.1** Beim RX-Mode-Wechsel (`_on_rx_mode_changed`) wird neben
  OMNI und Auto-Hunt auch der normale CQ-Modus mit gestoppt
  (`qso_sm.stop_cq()`), sofern aktiv (`qso_sm.cq_mode`).
- **AC4.2** Mike's Symptom reproduzierbar abgedeckt durch Test:
  cq_mode=True, Encoder gequeued, `_on_rx_mode_changed("normal")`
  oder `_on_rx_mode_changed("diversity")` aufgerufen — kein
  weiterer CQ wird gesendet, kein Eintrag im QSO-Panel.
- **AC4.3** Encoder-Abort ist atomar — wenn Mode-Wechsel mid-slot
  passiert, läuft der gerade laufende TX-Slot ggf. zu Ende
  (Hardware-Sicherheit), aber KEIN weiterer Slot wird begonnen.
- **AC4.4** ANT1=TX-Pflicht: falls der laufende Slot zu Ende
  geführt wird, läuft er garantiert über ANT1 (was bei normalem CQ
  ohnehin gilt — aber Tests müssen das absichern).
- **AC4.5** Bandpilot-Pfad ist unangetastet (er triggert
  `_on_rx_mode_changed` programmatisch nach TX-finished; wir wollen
  nicht aus Versehen seinen CQ-Resume blockieren — siehe
  `_apply_bandpilot_auto` Race in mw_radio).

---

## Betroffene Module/Dateien

### Punkt 1
- `ui/settings_dialog.py:333-356` — GroupBox „Sichtbare Bänder"
  + Stylesheet für Checkbox-Indicator
- Tests: `tests/test_settings_dialog_smoke.py` Smoke-Check dass das
  Stylesheet keinen Init-Crash verursacht (nicht visuell prüfen)

### Punkt 2
- `core/qso_state.py:692` — `qso_confirmed_visual.emit` entfernen
  aus 73-Empfang-Pfad
- `core/qso_state.py:530-539` — `TX_73_COURTESY` `on_message_sent`-
  Pfad: zusätzlich `qso_confirmed_visual.emit(self.qso)` vor
  `qso_confirmed.emit(self.qso)`
- `core/qso_state.py:357-365` — WAIT_73-Timeout-Pfad unverändert
  (visual + full direkt nacheinander, kein Courtesy)
- `core/qso_state.py:754-768` — Force-73-Pfad in `advance()`:
  prüfen ob `on_message_sent` auch hier durchläuft (sollte: das
  Force-73 emittet `send_message` → wird gesendet → `on_message_sent`
  mit Status TX_73_COURTESY → triggert dann visual+full)
- Tests: `tests/test_p33_qso_komplett_reihenfolge.py` (bestehend,
  Bundle B') anpassen + neue Tests für Bundle I

### Punkt 4
- `ui/mw_radio.py:541-545` — `_on_rx_mode_changed` Stop-Block
  erweitern um `qso_sm.stop_cq()` wenn `qso_sm.cq_mode` True
- Tests: neuer `tests/test_bundle_i_omni_race.py` für AC4.1-AC4.3

---

## Randbedingungen

### Hardware-Pflicht ANT1=TX
- Punkt 4 betrifft TX-Pfad. Stop-Logik darf KEINE Antennen-
  Umschaltung erzwingen — wenn der laufende Slot zu Ende geht,
  läuft er weiter über ANT1 (Default für CQ). Kein
  `set_tx_antenna("ANT2")` irgendwo, sonst Hardware-Risiko.

### KISS
- Punkt 1: keine neue Layout-Klasse, kein Custom-Widget — nur
  Werte-Anpassung + Stylesheet-Block in der GroupBox.
- Punkt 2: Signal-Umparken, 2-Zeilen-Änderung in `qso_state.py`.
  Kein Refactor des P33-Splits.
- Punkt 4: Single-Line-Erweiterung im Stop-Block. Kein neuer
  Race-Schutz, keine Locks, kein Encoder-Abort-Refactor.

### Threading
- Punkt 4 läuft im GUI-Thread (`_on_rx_mode_changed` ist Slot).
  `qso_sm.stop_cq()` ist heute schon thread-safe (siehe
  `mw_radio.py:335,407,1038,1308`).

### Tests grün
- Vor jedem Commit: `QT_QPA_PLATFORM=offscreen ./venv/bin/python3
  -m pytest tests/ -q` → grün.
- Test-Count vor Bundle I: 1205 (v0.97.25).

### Backup vor Code-Änderung
- `Appsicherungen/2026-05-14_v0.97.25_vor_bundle_i/` anlegen
  bevor Commits losgehen.

### Doku-Pflicht nach Bundle
- HISTORY.md / HANDOFF.md / CLAUDE.md / TODO.md
- Memory wenn Lesson gelernt (z.B. Race in Stop-Block)

---

## Nicht im Scope

- **Gain-Messung vereinheitlichen (P51)** — eigener Workflow, in
  TODO.md notiert, kommt nach Bundle I.
- **Bundle-G/H Field-Tests** — separat von Mike abgenommen.
- **OMNI-CQ Architektur-Eingriff** — nur Stop-Erweiterung im
  Mode-Wechsel-Pfad. Kein Refactor von `core/omni_cq.py`.
- **P33-Architektur** (2-Signal-Split) bleibt bestehen, wird nur
  Timing angepasst.
- **PSK-Reset bei Modus-Wechsel** — heute schon korrekt (Bundle C
  P10 reagiert nur auf Protokoll + Band, nicht RX-Mode).
- **Encoder-Abort mid-Slot** — wenn Hardware schon TX, läuft Slot
  zu Ende. Kein Erzwungenes Abbrechen.

---

## Testbarkeit

### Unverzichtbare Tests

**Punkt 1 — Settings-Spacing:**
- T1.1 Settings-Dialog initialisiert ohne Crash.
- T1.2 `_band_checkboxes` hat 9 Einträge, alle in 3×3-Grid.
- T1.3 Min-1-Logik aus P50 funktioniert (mock setze 1 → letzte
  bleibt disabled).

**Punkt 2 — QSO-Reihenfolge:**
- T2.1 73 empfangen im WAIT_73: visual feuert **nicht** sofort,
  sondern erst nach `on_message_sent` für `TX_73_COURTESY`.
- T2.2 WAIT_73-Timeout (3 Cycles ohne 73): visual + full feuern
  direkt hintereinander (kein Courtesy).
- T2.3 Force-73 via `advance()`: visual + full feuern in
  `on_message_sent` für `TX_73_COURTESY`.
- T2.4 Kein Doppel-Emit von visual oder full.
- T2.5 `qso_confirmed.emit` Reihenfolge unverändert (full nach
  Courtesy-Send) für OMNI-Resume etc.

**Punkt 4 — OMNI-Race:**
- T4.1 `_on_rx_mode_changed` mit `qso_sm.cq_mode=True` ruft
  `qso_sm.stop_cq()` exakt einmal.
- T4.2 `qso_sm.cq_mode=False` nach Mode-Wechsel.
- T4.3 OMNI + normaler CQ kombiniert: Mode-Wechsel stoppt beide.
- T4.4 Mode-Wechsel ohne aktiven CQ (qso_sm.cq_mode=False) ruft
  `stop_cq()` NICHT (kein Spam, kein Fehler).
- T4.5 ANT1=TX-Sanity: nach Mode-Wechsel keine ANT-Umschaltung
  programmatisch (read-only Mock prüft set_tx_antenna-Calls).
- T4.6 Bandpilot-Pfad (`_apply_bandpilot_auto` → programmatischer
  Mode-Wechsel) ist nicht blockiert — separat testen.

---

## V1-Ende
