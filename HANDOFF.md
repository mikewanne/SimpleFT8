# HANDOFF — SimpleFT8

---

## ⛔⛔⛔ HARDWARE-WARNUNG — HOECHSTE PRIORITAET ⛔⛔⛔

### ANT1 = TX-Antenne. IMMER. Auf jedem Band.
### ANT2 = NUR Empfangs-Zusatzantenne. NIEMALS TX!

**ANT2 (Regenrinne ~15m) ist NICHT fuer Sendeleistung ausgelegt.** TX auf
ANT2 mit 100 W = Hardware-Schaden moeglich (PA, Antennen-Pfad).

| Aktion | Antenne |
|---|---|
| Manuelle CQ-Anrufe / TUNE | **ANT1** |
| OMNI CQ (passiv) | **ANT1** |
| AUTO HUNT (aktiv, v0.75) | **ANT1** |
| Diversity RX-Pattern | beide RX, **TX nur ueber ANT1** |

**Im Code (v0.75/v0.77):** `set_tx_antenna("ANT1")` zentral abgesichert in
`Encoder.transmit()` (vor `ptt_on()`) UND vor jedem `tune_on()`-Aufruf.
**v0.77 Pflicht-Acknowledgment-Dialog beim App-Start** zeigt die Regel
explizit + Disclaimer (Modal, OK/Abbruch, OK = App startet, Abbruch =
`sys.exit(0)`).

---

## 2026-04-30 (v0.78 + v0.79) — OMNI scharfgeschaltet + Bug-Cleanup

### v0.78 (Nacht, Workflow durchgezogen)
- OMNI-TX scharfgeschaltet als **Diversity-only** Power-User-Feature
- Mode-Coupling: btn_omni_cq + btn_auto_hunt nur in „diversity"
- Auto-Hunt analog mode-coupled, neuer Reason `rx_mode_change`
- Mutually-exclusive OMNI ↔ Auto-Hunt mit `superseded`-Reason
- Stop-Hooks fuer band/ft_mode/rx_mode/totmann konsistent
- Workflow: V1 → Self-Review (17) → V2 → R1 (10, 0 Halluzinationen,
  2 echte Bugs in V2) → V3 → 7 atomare Commits → Final-R1 (11, 2 umgesetzt)
- 472 → 493 Tests gruen

### v0.79 (Vormittag, Bug-Cleanup-Tag)

**Diagnose-Falle:** R1 hatte gestern Abend ANT1-Hook in `Encoder.transmit()`
mit 90% Wahrscheinlichkeit als TX-Regression-Ursache gepegt — Test 1
heute morgen widerlegte das. Mike's Flex sendet sauber, der Empfaenger-
Icom hatte **Auto-Sequence ausgeschaltet** und sendete stur den
initial-Anruf. Memory `feedback_auto_sequence_check_first.md` angelegt.

**5 Fixes:**
- QSO-Panel CQ-Sammelanzeige raus — jede CQ einzeln im Log (`db10b2d`)
- Kalibrierungs-Bestaetigungsdialog modal + StaysOnTop (`ad24a6e`)
- RX-Tag waehrend Diversity-Kalibrierung zeigt korrekte Antenne (`a7a16de`)
- `_reset_defaults` vervollstaendigt: radio_ip / language / stats / debug (`759e49f`)
- **CQ-Toggle + Stats-Lock-Bug:** `mode_button_group.setExclusive(False)`
  statt True. Qt-Default verhindert sonst Re-Klick-Deselect → CQ-Toggle
  broken UND `btn_cq.isChecked()=True` haengen → Stats stillschweigend
  blockiert. (`d94f2e5`)

**HEAD:** `d94f2e5` (vor Version-Bump auf v0.79)

---

## 2026-04-29 (v0.77) — App-Start Hardware-Dialog + Statistik-Methodik

## Heute erledigt (chronologisch)

**Vormittag — v0.76 Settings-Tabs (1440×900-Display-Fix):**
- `ui/settings_dialog.py` von 6 GroupBoxen auf 4-Tab-`QTabWidget`
- 4 Tabs: „Station" / „TX & Schutz" / „FT8 & Diversity" / „Daten & Tools"
- Tab-Stylesheet nur auf das Widget (kein Konflikt mit Dialog-CSS)
- Hoehen-Sizing via `adjustSize()` + `resize`-Fallback (max 750 px)
- `closeEvent()` stoppt `_tx_status_timer` (Defense-in-Depth)
- 5 Smoke-Tests in `tests/test_settings_dialog_smoke.py`
- Workflow V1→V2→V3 voll durchlaufen, R1-Final-Codereview
- 4 atomare Commits

**Mittag — WORKFLOW.md v1.1 universalisiert:**
- Verschaerfte R1-Rollenanweisung (5 kritische Regeln statt 1)
- Schritt 2.5 NEU: R1-Findings gegen Code verifizieren (Pflicht)
- Schritt 5b NEU: Final-R1-Codereview als Pflicht-Schritt
- Schritt 6 NEU: Lessons-Learned (3 Fragen + Memory-Update)
- Universalisierung: Projekt-Variablen statt SimpleFT8-Hardcodes
  (Geltungsbereich auf alle Mike-Projekte erweitert)
- Mini-CHANGELOG fuer Nachvollziehbarkeit

**Nachmittag — 20m FT8 Datensammlung-Ziel diskutiert (Mike+Claude+R1):**
- Mike+R1 einig: **5 Tage flaechendeckend** statt 7-Tage-Goldstandard
- Begruendung: Diminishing Returns 5→7 nur ~15% SE-Reduktion bei doppelt
  so viel Aufwand. „5 Tage mit Luecken < 4 Tage flaechendeckend" —
  Lueckenliste schlaegt Mehr-Tage-an-bekannter-Stelle.
- Lueckenfuell-Strategie: nach Stundenliste pro Modus, schwaechster Slot
  zuerst.
- In CLAUDE.md (Statistik-Veroeffentlichung) und HANDOFF dokumentiert.

**Spaetnachmittag — v0.77 Bug-Fix-Release (2 Punkte aus v0.76-Field-Test):**
- Min/Max-Error-Bars in PDF-Berichten **entfernt** (vermischten
  Modus-Volatilitaet mit Tag-Conditions als Confounder, bei ungleicher
  Stichprobengroesse statistisch unfair).
- App-Start Hardware-Dialog mit Pflicht-Acknowledgment + Disclaimer
  (private Machbarkeitsstudie). Erste Iteration mit „Hardware-Schaden"-
  Drohton — auf Mike's Wunsch entfernt (Drohton schreckt User ab).
- README.md bekam zweisprachigen Disclaimer-Block direkt unter Badges
  (EN+DE). LICENSE (MIT mit AS-IS) bleibt — deckt rechtlich ab.
- 3 atomare Commits, **Tests 472 gruen**.

**Push nach GitHub (Mike-OK):**
- 23 Commits hochgeladen nach `https://github.com/mikewanne/SimpleFT8.git`
- Enthaelt: v0.75 (war noch ungepushed) + v0.76 + v0.77 + WORKFLOW v1.1
- HEAD: `ffbe12e chore(release): v0.77`

**Nebenher — Locator-DB-Statistik:**
- 11.120 Calls in der DB (1.368 heute neu, 9.864 heute aktualisiert)
- 43% mit 6-stelligem Locator (~70 km Praezision)
- 57% mit 4-stelligem Locator (~700 km, Tilde-Anzeige)
- Sources: 4.768 qso_log_6, 3.534 cq_4 (live aufgesammelt), 2.818 qso_log_4

**Nebenher — Architektur-Diskussion (theoretisch, nicht-Code):**
- IC-705 + Raspberry Pi 4 + Tablet-Browser-Client als „SimpleFT8-Field"
  Architektur-Skizze. ~70-110 h Aufwand fuer eine erste Version. 70-80%
  des bestehenden Codes wiederverwendbar (Decoder, Encoder, QSO-State,
  ADIF, Locator-DB). UI komplett neu (HTML5/JS via FastAPI+WebSocket).
  IC-705 per USB an Pi (NICHT per WLAN — RS-BA1 Closed-Protocol).

## Bilanz heute

- **3 Releases**: v0.76 (Tabs), v0.77 (Dialog+Methodik) + WORKFLOW v1.1
- **23 Commits** lokal → 23 Commits remote (GitHub aktuell)
- **472 Tests** gruen (467 vor heute → +5 Settings-Smoke-Tests)
- **2 Memory-Eintraege** ergaenzt
- **Statistiken** mehrfach aktualisiert (3× scripts/generate_plots.py)

## Offen / Naechste Schritte (priorisiert)

### 🐛 Akut

1. **Timeout-Cooldown fehlt** — nach `x DA1TST — Timeout` antwortet Mike's
   Flex sofort wieder auf DA1TST's naechsten CQ. Endlos-Schleife. Braucht
   V1→V3-Workflow weil State-Logik (qso_state.py). ~10-20 Zeilen.

2. **`_on_dx_tune_rejected` Normal-Branch fehlt `_stats_warmup_cycles`-
   Reset** — bei Cancel der DX-Tune-Pipeline im Normal-Modus bleibt
   Counter auf 99999 haengen. Fix: `_stats_warmup_cycles = 6` in Z.1011-1012
   else-Branch ergaenzen. (~1 Zeile)

3. **20m FT8 Datensammlung — Ziel: 5 Tage flaechendeckend**
   Strategie: bei jedem „welcher Modus jetzt" die Lueckenliste pruefen,
   schwaechsten Slot vorschlagen. Aufwand: ~3 Wochen Funkbetrieb (3-4 h/Tag).

### 🔥 Aus frueheren Releases (Field-Test ausstehend)

4. **Field-Test v0.74** Diversity-Bandwechsel-Bug-Fix verifizieren
5. **Field-Test v0.75** Auto-Hunt — 6 Verifikationsschritte siehe
   `prompts/auto_hunt_v3.md`
6. **Migration `main_window._psk_worker` → `core/psk_reporter`** (Konsolidierung)

### ⚙️ Mittelfristig

- F) Audio-Export per Slot (<1 Tag, optional)
- TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker (nicht reproduzierbar)
- Even/Odd dedizierter Timer (FT2 kritisch)
- Gain-Bias beheben (Normal-Modus Gain-Messung erzwingen)
- Tertile-Analyse Statistik
- AP-Lite Test-Pipeline (synthetische E2E-Tests)
- Per-Station DT-Offset TX
- IC-7300 Fork (TARGET_TX_OFFSET separat messen)

### 🌐 Langfristig (theoretisch diskutiert, nicht angefangen)

- **SimpleFT8-Field**: IC-705 + Pi 4 + Tablet-Browser-Client. Eigenes
  Projekt, kein Fork. ~70-110 h Aufwand. Pfad: FastAPI-Server auf Pi,
  HTML5-Frontend, USB-Anbindung IC-705. Realistischste mobile Variante.

## Warnungen & Fallen (Stand v0.77)

**Aus v0.77:**
- App-Start Hardware-Dialog ist **Pflicht-Acknowledgment** — bei Abbruch
  beendet sich App. Modal + WindowStaysOnTopHint. Inhalt aendert sich
  nicht ohne Mike-Freigabe (rechtlich relevanter Disclaimer-Text).
- Min/Max-Error-Bars wurden in `scripts/generate_plots.py` entfernt —
  **NICHT wieder einbauen** ohne neue Mess-Methodik (interleaved). Sie
  vermischten Modus-Volatilitaet mit Tag-Conditions.

**Aus v0.75 — Auto-Hunt:**
- `_auto_hunt_timer` UNABHAENGIG vom Totmannschalter — Maus/Tastatur
  reset ihn NICHT (Bot-Tarn-Schutz). Nach jedem Stop ist Pflicht-Restart.
- Race-Doppel-Check in `select_next` ist ethische Belt-and-suspenders zur
  10-Min-Hard-Cap. NICHT entfernen.
- `_MAX_ATTEMPTS = 3` in `core/auto_hunt.py:45` ist Modul-Konstante OHNE
  Verwendung in der Klasse. 3-Versuche-Logik liegt in `qso_state.py`.

**Aus v0.76 — Settings-Tabs:**
- `_reset_defaults()` setzt aktuell radio_ip/language/stats_cb/
  debug_console_cb NICHT zurueck — out-of-scope-Issue, geplant fuer v0.78.
- Tab-Stylesheet darf NICHT auf das gesamte Dialog-CSS gesetzt werden,
  sonst Konflikt — auf `self.tabs.setStyleSheet(...)` beschraenken.

## Test-Suite Status

```
./venv/bin/python3 -m pytest tests/ -q
472 passed in ~7s
```

Neu seit v0.75:
- `tests/test_auto_hunt_extended.py` (10 Funktionen, 21 Cases) — v0.75
- `tests/test_settings_dialog_smoke.py` (5 Cases) — v0.76

## Letzter bekannter guter Zustand

- **Branch:** main, lokal **vor origin/main** (v0.78 + v0.79 noch nicht gepusht)
- **HEAD:** vor Version-Bump-Commit auf v0.79 (kommt gleich)
- **Tag:** kein neuer Tag (Mike entscheidet)
- **Tests:** 493/493 gruen
- **App-Version:** v0.79 (nach Bump)
- **Backup:** `Appsicherungen/2026-04-30_vor_omni_implementierung/` (v0.77 Stand,
  vor v0.78 OMNI-Implementation, 1.2 GB)

---

Morgen: `cd SimpleFT8` ODER `cd FT8` → `claude1` → laedt automatisch alle Memories + CLAUDE.md.
