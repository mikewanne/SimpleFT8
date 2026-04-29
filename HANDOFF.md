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

### 🚀 v0.78 OMNI-TX — Workflow gestartet (2026-04-30)

**Status:** Schritt 0 (Code-Verifikation) abgeschlossen, V1-Entwurf als naechstes.

**Backup:** `Appsicherungen/2026-04-30_vor_omni_implementierung/` (1.2 GB)

**Design-Spec:** `docs/OMNI_TX_DESIGN.md` v3.2 — vollstaendige permanente
Spec mit 14 Sektionen. CLAUDE.md verweist drauf.

**Wichtige Befunde aus Schritt 0:**
- OMNI-TX ist **bereits zu ~70% verkabelt** im Codebase (vermutlich
  v0.50-v0.60). Logik-Schicht in `core/omni_tx.py` komplett vorhanden.
- 7 Hooks bereits da: Singleton-Init, should_tx(), on_qso_started(),
  advance() pro Cycle, Easter-Egg-Disable, Statusbar-Anzeige, Buttons.
- 8 Lucken zu schliessen — alle mit Datei:Zeile-Verweis dokumentiert
  in `docs/OMNI_TX_DESIGN.md` Sektion 14.
- Geschaetzter Aufwand: ~425 Zeilen, ~4-5 h, 6-8 atomare Commits.
- Auto-Hunt wird ebenfalls mode-coupled (Diversity-only) — Konsistenz
  mit OMNI-Strategie. Easter-Egg bleibt Test-Override fuer Mike.

**Naechste Workflow-Schritte (nach `docs/WORKFLOW.md` v1.1):**
1. Schritt 1a — V1 schreiben (`prompts/omni_v1.md`)
2. Schritt 1b/c — Self-Review → V2
3. Schritt 2 — DeepSeek-R1-Review
4. Schritt 2.5 — R1-Findings gegen Code verifizieren
5. Schritt 3 — V3 schreiben + Mike vorlegen
6. Schritt 4 — Mike-Freigabe
7. Schritt 5 — Implementation in atomaren Commits
8. Schritt 5b — Final-R1-Codereview
9. Schritt 6 — Lessons-Learned

**Mike's Design-Entscheidungen** (festgehalten in `docs/OMNI_TX_DESIGN.md`):
- UI-Logik mode-gekoppelt (Normal: btn_cq sichtbar; Diversity:
  btn_omni_cq + btn_auto_hunt sichtbar)
- Easter-Egg = Test-Bypass nur fuer Mike, nicht GitHub-publik
- Direkt-Toggle (KEIN Aktivierungsdialog — siehe Memory
  feedback_disclaimer_no_threat.md)
- 4 Stop-Reasons: manual_halt, band_change, mode_change, totmann_expired
- block_cycles=80 (Plan v3.2, aktueller Code-Default 40 wird angepasst)
- Mutually-exclusive zwischen Auto-Hunt und OMNI im 2-Button-Layout

### 🆕 Aus v0.76-Field-Test — geplant als v0.78 Bug-Cleanup-Block

1. **🟡 RX-Tag waehrend Diversity-Kalibrierung** — alle Eintraege als „A1"
   obwohl Hardware zwischen ANT1/ANT2 schaltet. UI-only-Bug (Mess-
   Algorithmus selbst korrekt). Fix: `msg.antenna = self._schedule[
   self._step][0]` vor `add_message()` setzen. (~5 Zeilen)
2. **🟠 Bestaetigungsfenster nach Kalibrierung** (`_show_calibration_done`,
   `mw_radio.py:925`) ist `setWindowModality(NonModal)` + nur `dlg.show()`
   — kann hinter Hauptfenster wandern. Fix: `setModal(True)` +
   `WindowStaysOnTopHint` + `dlg.exec()`. (~3 Zeilen)
3. **🟡 `_reset_defaults` Reset-Vervollstaendigung** (R1-Final-Review v0.76)
   — `radio_ip`, `language`, `stats_cb`, `debug_console_cb` werden aktuell
   NICHT zurueckgesetzt.

### 🆕 Aus v0.77 hinzugekommen

4. **20m FT8 Datensammlung — Ziel: 5 Tage flaechendeckend**
   - Status: 2-3 Tage je Stunde-Modi-Slot, mit Luecken (z.B. Stunde 13 UTC
     bei Diversity_Normal aktuell 1 Tag — heute hochgezogen).
   - Ziel: alle 24 Stunden × 3 Modi auf **5 Tage** flaechendeckend.
   - Strategie: „Welcher-Modus-jetzt"-Ratgeber pruefe pro Anfrage die
     Lueckenliste, schlage schwaechsten Slot vor.
   - Aufwand: ~3 Wochen Funkbetrieb (3-4 h/Tag).

### 🔥 Aus frueheren Releases

5. **Field-Test v0.74** Diversity-Bandwechsel-Bug-Fix (auch ausstehend)
6. **Field-Test v0.75** Auto-Hunt — 6 Verifikationsschritte siehe
   `prompts/auto_hunt_v3.md`.
7. **Phase 2: `btn_omni_cq`-Handler** — Button hat keinen eigenen
   `clicked`-Handler (OMNI laeuft weiter ueber bisherige Logik).
8. **Migration `main_window._psk_worker` → `core/psk_reporter`** (Konsolidierung)

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

- **Branch:** main, lokal **identisch mit origin/main** (eben gepusht)
- **HEAD:** `ffbe12e chore(release): v0.77 — Hardware-Dialog + Statistik-Methodik`
- **Tag:** kein neuer Tag (Mike entscheidet)
- **Tests:** 472/472 gruen
- **App-Start:** OK (PID 61569 lief stabil heute Nachmittag)
- **App-Version:** v0.77
- **Backup:** `Appsicherungen/2026-04-29_vor_auto_hunt/` (v0.74 Stand,
  vor Auto-Hunt). Kein neues Backup heute (Aenderungen waren UI-/Doku-
  fokussiert, keine Mess-/Algorithmus-Aenderungen).

---

Morgen: `cd SimpleFT8` ODER `cd FT8` → `claude1` → laedt automatisch alle Memories + CLAUDE.md.
