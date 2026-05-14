# Bundle J — V1 (Connect-Modal-Branding + Help-Dialog + RX-Label + Intent-Klausel)

> Stand: 14.05.2026 nachmittags, nach Bundle I (v0.97.26). Field-Test
> Bundle I läuft, parallel bauen wir Bundle J durch.

## 1. Ziel

Vier orthogonale UI-/Doku-Tweaks aus Mike-Field-Test 14.05.2026 nachmittags
+ Klärungs-Gespräch als gemeinsames Bundle einspielen, voller V1→V2→R1→V3-
Workflow mit DeepSeek-V4-pro.

**Punkt 1 — Connect-Modal Version + MIT-Lizenz:** Im `ConnectStatusDialog`
(beim App-Start während FlexRadio-Connect, 5-7 Sek sichtbar) **unten rechts
in der Ecke** eine kleine Zeile mit Versionsnummer (synchron mit
`main.py:APP_VERSION`) und „MIT License"-Hinweis. Schrift klein (9-10 pt),
halb-transparent, dezent — User sieht „SimpleFT8 v0.97.27 · MIT License"
beim Start.

**Punkt 2 — Einheitlicher Help-Dialog mit Scrollbar:** Aktuell sind die
`?`-Hints in Settings als `QMessageBox.information` realisiert
(`ui/settings_dialog.py:60` Helper `_make_info_btn`) und der größere
Bandpilot-Help-Text als `QMessageBox` mit Markdown (Z.381
`_show_bandpilot_help`). QMessageBox ist **nicht resizable + kein Scrollbar**
→ langer Markdown wird abgeschnitten (Mike-Screenshot). Lösung: neuer
gemeinsamer Helper `show_simple_help(parent, title, text, *, markdown=False)`
in `ui/simple_help_dialog.py` (NEU) als `QDialog` mit `QTextBrowser` (700×600,
resizable, App-Theme dunkel, Esc + Close-Button). Alle bisherigen
`?`-/Help-Aufrufe in `ui/settings_dialog.py` umstellen. Konsistenz vor
Optimum-pro-Dialog (auch kurze Hints landen im 700×600 mit Weißraum).

**Punkt 3 — RX-Label `(RX: ANT2 ↑X.X dB)`:** Aktuell zeigt
`_antenna_pref_label` in `ui/mw_qso.py:90-109` im Diversity-Modus
`(ANT2 ↑6.3 dB)`. Mike-Befund: kann verwirren („wartet, er hat doch mit
ANT2 gesendet?"). Klarstellung: das ist nur die **bevorzugte RX-Antenne**
(TX bleibt immer ANT1). Neues Format: `(RX: ANT2 ↑6.3 dB)` bzw.
`(RX: ANT1)` bei Diversity+ANT1-Pref. Im Normal-Modus bleibt das Label
weg bzw. `(ANT1)` ohne RX-Prefix (Mike: „im normal modus ist immer ant1
also egal").

**Punkt 4 — Intent-Klausel im Hardware-Disclaimer:** `main.py:448-451`
Disclaimer-Text um einen Satz ergänzen der ausdrücklich klarstellt:
„Das Projekt dient ausschließlich dem persönlichen Gebrauch und der
Verifikation technischer Möglichkeiten." (Mike-Wunsch zur juristischen
Absicherung — sagt klar dass die App nicht für Dritte gedacht ist.)

**Punkt 5 — APP_VERSION-Bump:** v0.97.26 → v0.97.27 (Feature-Bundle).

---

## 2. Akzeptanzkriterien

**AC1 — Connect-Modal Footer sichtbar:**
- `ConnectStatusDialog` zeigt unten rechts in der Ecke einen Label-Text
  `SimpleFT8 v{APP_VERSION} · MIT License` (Format exakt).
- Schrift: 9 pt, Farbe `#666` (halb-transparent gegen `#16192b`-Hintergrund).
- `setAlignment(Qt.AlignBottom | Qt.AlignRight)` auf dem Label.
- Synchron mit `main.py:APP_VERSION` — kein Hardcode der Versionsnummer.
- Dialog-Höhe **darf wachsen** wenn Layout es braucht (aktuell `setFixedSize(352, 176)`
  ggf. anpassen auf z.B. `352 × 196`).

**AC2 — Help-Dialog einheitlich + scrollbar:**
- Neue Datei `ui/simple_help_dialog.py` mit Klasse `SimpleHelpDialog(QDialog)`
  und Helper-Funktion `show_simple_help(parent, title, text, *, markdown=False)`.
- Mindest-Größe 700×600 px, resizable (`setMinimumSize`, KEIN `setFixedSize`).
- `QTextBrowser` mit ScrollBar automatisch.
- App-Theme: Hintergrund `#1a1a2e`, Text `#CCC`, Border `#333`.
- Modal (`setWindowModality(Qt.WindowModality.ApplicationModal)`).
- Esc + Close-Button (mind. einer der beiden, ApplicationModal genügt für Esc).
- `_make_info_btn` (`ui/settings_dialog.py:60`) ruft den Helper statt
  `QMessageBox.information`.
- `_show_bandpilot_help` (Z.381) ruft den Helper mit `markdown=True`.

**AC3 — RX-Label umformatiert:**
- `_antenna_pref_label` in `ui/mw_qso.py:90-109`:
  - Normal-Modus: `(ANT1)` bleibt (oder leer — siehe AC3a)
  - Diversity + ANT1-Pref: `(RX: ANT1)` (neu mit Prefix)
  - Diversity + ANT2-Pref: `(RX: ANT2 ↑X.X dB)` (Prefix vor ANT2)
  - Diversity + ANT2 ohne delta: `(RX: ANT2)`
- **AC3a-Frage:** Bleibt Normal-Modus-Label `(ANT1)` weiter angezeigt? Mike-Zitat:
  „im normal modus ist immer ant1 also egal" → KISS: weglassen wäre konsequent,
  aber bestehende Tests verlangen es. **V1-Default: Normal-Modus-Label bleibt
  unverändert `(ANT1)` ohne `RX:`-Prefix**, weil:
  (a) bestehende Tests testen exakt diesen String,
  (b) Mike's Aussage „egal" heißt nicht „weg" sondern „nicht wichtig",
  (c) Symmetrie-Verlust zur Diversity-Anzeige wäre verwirrend.

**AC4 — Intent-Klausel:**
- `main.py:448-451` Disclaimer-QLabel-Text erweitert um einen Satz, z.B.:
  „SimpleFT8 ist eine private Machbarkeitsstudie. Das Projekt dient
  ausschließlich dem persönlichen Gebrauch und der Verifikation technischer
  Möglichkeiten. Nutzung auf eigene Gefahr — für Schäden an Hardware,
  Antennen oder Funkgeräten wird keine Haftung übernommen."
- Dialog-Höhe ggf. von 300 → 340 px erweitern damit Text nicht abschneidet.

**AC5 — APP_VERSION:**
- `main.py:APP_VERSION = "0.97.27"`
- HISTORY/HANDOFF/CLAUDE/TODO Header aktualisiert nach Workflow-Pflicht.

---

## 3. Betroffene Module/Dateien

| Datei | Was | Zeilen |
|---|---|---|
| `ui/connect_status_dialog.py` | Footer-Label Version+MIT, ggf. Größen-Anpassung | Z.65-77 + neuer Block am Ende von `_setup_ui` |
| `ui/simple_help_dialog.py` | **NEU** — `SimpleHelpDialog` + `show_simple_help`-Helper | — |
| `ui/settings_dialog.py` | `_make_info_btn` Z.60 + `_show_bandpilot_help` Z.381 umstellen | Z.46-63 + Z.381-397 |
| `ui/mw_qso.py` | `_antenna_pref_label` Format-Änderung | Z.90-109 |
| `main.py` | APP_VERSION + Disclaimer-Text | Z.20 + Z.448-451 |
| `tests/test_bundle_j.py` | **NEU** — 6-8 Tests für AC1-AC4 | — |
| `tests/test_settings_dialog_smoke.py` | ggf. Test-Update wenn _make_info_btn jetzt SimpleHelpDialog öffnet | (existierende Tests) |
| `tests/test_modules.py` ODER `tests/test_*_antenna*.py` | _antenna_pref_label-Tests updaten auf RX-Prefix | (existierend) |

---

## 4. Randbedingungen

- **PySide6:** `Signal` statt `pyqtSignal`, `Slot` statt `pyqtSlot`.
- **Hardware-Pflicht:** ANT1 = TX immer, ANT2 = RX only. Bundle J ändert NICHTS
  an der TX-Antennen-Logik (Code-Verifikation: `core/encoder.py:389` +
  `ui/mw_tx.py:83` rufen `set_tx_antenna("ANT1")` VOR jedem `ptt_on()` /
  `tune_on()` — bereits safe).
- **Thread-Safety:** Keine neuen Threads, keine neuen Locks nötig.
  `SimpleHelpDialog` läuft im GUI-Thread (modal, blockierender exec).
- **App-Theme:** Dunkles Theme `#1a1a2e` Hintergrund, `#CCC` Text — beim
  `SimpleHelpDialog` zwingend gleicher Stil wie Settings/Connect-Modal
  (Mike-Vorgabe „einheitlicher").
- **i18n:** Disclaimer + ConnectStatus sind aktuell **deutsch-only**. Bundle J
  fügt KEINE Übersetzungen hinzu (Scope-Disziplin) — Mike spricht deutsch,
  GitHub-Leser sehen den englischen Help-Dialog separat (`HelpDialog`).
- **MIT-Lizenz:** Datei `LICENSE` existiert bereits (`MIT License` + Copyright
  Mike Hammerer DA1MHH). Kein neuer File nötig.
- **Reversibilität:** Alle 4 Punkte sind reine UI-/Doku-Änderungen — keine
  Migration, keine Persistenz-Format-Brüche.

---

## 5. Nicht im Scope

- **i18n / Übersetzungen** für Disclaimer, Connect-Modal, SimpleHelpDialog.
- **Auto-Resize** des Connect-Modals an Inhalts-Höhe (FixedSize bleibt).
- **Pre-TX ANT1-Guard zusätzliche Aufrufe** — Verifikation: bereits abgedeckt
  durch `core/encoder.py:389` (vor jedem `ptt_on()`) und `ui/mw_tx.py:83`
  (vor `tune_on()`). Wenn User mid-session am SmartSDR auf ANT2 schaltet,
  setzt der nächste TX-Slot via Encoder die Antenne zurück auf ANT1.
- **SWR-Live-Watchdog (P53), Auto-Tune (P54), Stats-Toggle-Cleanup (P52)** —
  bleiben als separate Workflows im TODO.
- **Bandpilot-Hilfe-Text** anpassen — der Text in `docs/explained/bandpilot.md`
  bleibt unverändert. Nur die Anzeige-Komponente (Dialog statt MessageBox)
  ändert sich.
- **Andere `QMessageBox`-Aufrufe in `settings_dialog.py`** (Confirmation für
  Löschen/Reset/etc., Z.511/632/653/704/795/808 etc.) — das sind echte
  ButtonRole-Dialoge mit Ja/Nein, nicht reine Help/Info-Anzeigen. Bleiben.

---

## 6. Testbarkeit

**Unverzichtbare Tests (in `tests/test_bundle_j.py` NEU):**

- **T1 ConnectStatus-Footer:** Footer-Label existiert, Text matched
  `r"SimpleFT8 v\d+\.\d+\.\d+ · MIT License"` mit aktueller APP_VERSION,
  Alignment `Qt.AlignBottom | Qt.AlignRight`, Schriftgröße ≤ 10pt.
- **T2 SimpleHelpDialog grundlegend:** `show_simple_help(None, "Test", "Hallo")`
  öffnet QDialog, hat QTextBrowser-Child mit "Hallo" als Text, MinimumSize ≥
  700×600, resizable (kein FixedSize).
- **T3 SimpleHelpDialog markdown-Modus:** `show_simple_help(..., "**bold**",
  markdown=True)` rendert über `QTextBrowser.setMarkdown` (kein literales
  Sternchen im Display-Text).
- **T4 _make_info_btn ruft SimpleHelpDialog statt QMessageBox:** Mock auf
  `show_simple_help`, Klick auf `?`-Button → mock wurde aufgerufen mit dem
  Hint-Text.
- **T5 _show_bandpilot_help ruft SimpleHelpDialog mit markdown=True:** analog T4.
- **T6 _antenna_pref_label Diversity ANT2:** `(RX: ANT2 ↑6.3 dB)` Format.
- **T7 _antenna_pref_label Diversity ANT1:** `(RX: ANT1)` Format.
- **T8 _antenna_pref_label Normal:** `(ANT1)` Format ohne `RX:` Prefix
  (AC3a-Default).
- **T9 Intent-Klausel im Disclaimer:** Disclaimer-QLabel.text() enthält
  Substring „ausschließlich dem persönlichen Gebrauch" (case-sensitive).

**Bestehende Tests anpassen:**
- Suche nach `(ANT2 ↑` oder `(ANT2 ` Substrings in `tests/` — bei Diversity-
  Tests Format auf `(RX: ANT2 ` umstellen.
- `tests/test_settings_dialog_smoke.py` ggf. Mock-Update wenn _make_info_btn
  jetzt einen anderen Dialog öffnet (sollte aber transparent sein, da QDialog
  statt QMessageBox).

**Tests-Soll: 1220 → ~1228 (+8 in Bundle J, ggf. 1-2 Anpassungen alter Tests).**
