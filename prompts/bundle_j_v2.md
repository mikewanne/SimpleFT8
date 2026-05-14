# Bundle J — V2 (nach Self-Review)

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

## Self-Review-Findings aus V1 → eingearbeitet in V2

| # | Finding aus V1-Selbstkritik | Wirkung |
|---|---|---|
| SR1 | AC3 Format-Inkonsistenz: Mike's Zitat „so sieht jeder boah der kommt im empfang mit regenrinne" betrifft NUR den ANT2-Fall. ANT1 ist die normale Antenne — unauffällig. V1 schlug `(RX: ANT1)` für Diversity+ANT1-Pref vor → inkonsistent mit „Mike will RX: bei ANT2 zeigen". | AC3 angepasst: Diversity+ANT1-Pref → `(ANT1)` (gleich wie Normal), nur ANT2-Pref kriegt `(RX: ANT2 ...)` Prefix. |
| SR2 | T9 case-sensitive Wortlaut-Test ist brüchig — bei späterem Doku-Refactor breakt Test. | T9 prüft nur Substring „persönlichen Gebrauch" (robuster + sprachlich eindeutig). |
| SR3 | Modal-Wahl `ApplicationModal` vs `WindowModal` für SimpleHelpDialog nicht geklärt. Settings-Dialog ist eh modal, Help wird aus Settings heraus geöffnet. | Empfehlung `WindowModal` — blockt nur Settings-Window, kein Eingriff in Decoder-/Encoder-Pfade (Konsistenz mit `ConnectStatusDialog`-Pattern). |
| SR4 | Bestehende `_antenna_pref_label`-Tests in `tests/` müssen identifiziert + angepasst werden. V1 nannte „suche nach `(ANT2 ↑`" ohne konkrete Test-Pfade. | V2 ergänzt: vor Code-Änderung `grep -rn "(ANT2 ↑" tests/` + `grep -rn "(ANT2)" tests/` ausführen + Liste pflegen. |
| SR5 | `_make_info_btn` Z.46-63 nutzt Closure `lambda: QMessageBox.information(btn.window(), "Info", hint)`. Test T4 muss patchen — `unittest.mock.patch("ui.settings_dialog.show_simple_help")` wenn der Helper drinnen importiert wird. | V2 spezifiziert Import-Pfad: `from ui.simple_help_dialog import show_simple_help` (Module-Top in `settings_dialog.py`). Mock-Pfad damit klar. |
| SR6 | Footer-Layout im `ConnectStatusDialog`: V1 sagte `setAlignment(Qt.AlignBottom \| Qt.AlignRight)` — aber Footer-Label wird in `_setup_ui` nach `btn_row` adden = passt nicht zu „unten rechts". | V2: Footer geht als eigene Zeile NACH `btn_row` ans Layout-Ende, Label bekommt `setAlignment(Qt.AlignRight)`. Fixed-Size 352×176 → 352×196 (20 px Reserve für Footer). |

---

## 1. Ziel

Vier orthogonale UI-/Doku-Tweaks aus Mike-Field-Test 14.05.2026 nachmittags
+ Klärungs-Gespräch als gemeinsames Bundle einspielen, voller V1→V2→R1→V3-
Workflow mit DeepSeek-V4-pro.

**Punkt 1 — Connect-Modal Version + MIT-Lizenz:** Im `ConnectStatusDialog`
(beim App-Start während FlexRadio-Connect, 5-7 Sek sichtbar) **unten rechts
in der Ecke** eine kleine Zeile mit Versionsnummer (synchron mit
`main.py:APP_VERSION`) und „MIT License"-Hinweis. Schrift klein (9-10 pt),
gedeckt grau (`#666`), dezent.

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
ANT2 gesendet?"). Klarstellung: das ist nur die **bevorzugte RX-Antenne**.
Neues Format **nur für ANT2-Fall**: `(RX: ANT2 ↑6.3 dB)` bzw. `(RX: ANT2)`.
ANT1-Pref bleibt `(ANT1)` ohne Prefix (Normal-Modus + Diversity-ANT1
identisch — siehe SR1).

**Punkt 4 — Intent-Klausel im Hardware-Disclaimer:** `main.py:448-451`
Disclaimer-Text um einen Satz ergänzen der ausdrücklich klarstellt:
„Das Projekt dient ausschließlich dem persönlichen Gebrauch und der
Verifikation technischer Möglichkeiten." Dialog-Höhe `setFixedSize(540, 300)`
→ `setFixedSize(540, 340)`.

**Punkt 5 — APP_VERSION-Bump:** v0.97.26 → v0.97.27.

---

## 2. Akzeptanzkriterien

**AC1 — Connect-Modal Footer sichtbar:**
- `ConnectStatusDialog` zeigt unten rechts eine Footer-Zeile
  `SimpleFT8 v{APP_VERSION} · MIT License` (Format exakt, `·` ist U+00B7
  middle-dot).
- Schrift: 9 pt, Farbe `#666`.
- Eigenes `QLabel` mit `setAlignment(Qt.AlignmentFlag.AlignRight)`,
  nach `btn_row` ans `QVBoxLayout` gehängt.
- Synchron mit `main.py:APP_VERSION` — `from main import APP_VERSION` ODER
  `APP_VERSION` als Konstruktor-Parameter (V2-Wahl: **Parameter** — vermeidet
  Circular-Import Risk: `ui/connect_status_dialog.py` wird in `main.py`
  imported, der Reverse-Import wäre Test-Stolperfalle).
- `setFixedSize(352, 196)` (war 176, +20 px für Footer).

**AC2 — Help-Dialog einheitlich + scrollbar:**
- Neue Datei `ui/simple_help_dialog.py`:
  - Klasse `SimpleHelpDialog(QDialog)`.
  - Module-Funktion `show_simple_help(parent, title, text, *, markdown=False)`
    — instantiiert + `exec()`.
  - Mindest-Größe 700×600 px via `setMinimumSize(700, 600)`. KEIN `setFixedSize`.
  - `QTextBrowser`-Child (automatischer Scrollbar, Markdown-fähig via
    `setMarkdown(text)` wenn `markdown=True` sonst `setPlainText(text)`).
  - StyleSheet: Hintergrund `#1a1a2e`, Text `#CCC`, Border `#333`
    (gleiches Theme wie `SettingsDialog`).
  - `setWindowModality(Qt.WindowModality.WindowModal)` (SR3) —
    blockt nur Parent-Window, Decoder-Thread läuft weiter.
  - Esc-Key schließt automatisch via `QDialog.reject()` (kein Custom-Handler
    nötig — Standard-QDialog-Verhalten).
  - Close-Button unten rechts (QPushButton „Schließen").
- `_make_info_btn` (`ui/settings_dialog.py:60`): ruft jetzt
  `show_simple_help(btn.window(), "Info", hint)` statt `QMessageBox.information`.
- `_show_bandpilot_help` (Z.381): ruft `show_simple_help(self, "Bandpilot —
  Hilfe", text, markdown=True)`.
- Import-Pfad: `from ui.simple_help_dialog import show_simple_help` als
  Module-Top-Import in `settings_dialog.py` (SR5 — Test-Mock-Pfad klar).

**AC3 — RX-Label umformatiert:**
- `_antenna_pref_label` in `ui/mw_qso.py:90-109`:
  - Normal-Modus: `(ANT1)` UNVERÄNDERT.
  - Diversity + ANT1-Pref: `(ANT1)` UNVERÄNDERT (SR1).
  - Diversity + ANT2-Pref ohne delta: `(RX: ANT2)` (NEU mit Prefix).
  - Diversity + ANT2-Pref mit delta: `(RX: ANT2 ↑X.X dB)` (NEU mit Prefix).
- Test-Inventur (SR4): vor Code-Änderung `grep -rn "ANT2 ↑\|ANT2)" tests/`
  ausführen, alle Treffer in Bundle-J-Code anpassen.

**AC4 — Intent-Klausel im Disclaimer:**
- `main.py:448-451` Disclaimer-QLabel-Text:
  ```
  SimpleFT8 ist eine private Machbarkeitsstudie. Das Projekt dient
  ausschließlich dem persönlichen Gebrauch und der Verifikation
  technischer Möglichkeiten. Nutzung auf eigene Gefahr — für
  Schäden an Hardware, Antennen oder Funkgeräten wird keine
  Haftung übernommen.
  ```
- Dialog-Höhe `setFixedSize(540, 300)` → `setFixedSize(540, 340)`.

**AC5 — APP_VERSION:**
- `main.py:APP_VERSION = "0.97.27"`.
- HISTORY/HANDOFF/CLAUDE/TODO Header aktualisiert.

---

## 3. Betroffene Module/Dateien

| Datei | Was | Zeilen |
|---|---|---|
| `ui/connect_status_dialog.py` | Footer-Label am Ende von `_setup_ui` + setFixedSize 176→196 + Konstruktor-Parameter `app_version: str = ""` | Z.60-77 + neuer Block am Ende von `_setup_ui` |
| `ui/main_window.py` ODER `main.py` (Aufrufstelle) | `ConnectStatusDialog(parent, app_version=APP_VERSION)` Konstruktor-Param mitgeben | grep `ConnectStatusDialog(` zeigt Aufrufstelle |
| `ui/simple_help_dialog.py` | **NEU** — `SimpleHelpDialog` + `show_simple_help` | — |
| `ui/settings_dialog.py` | Import + `_make_info_btn` + `_show_bandpilot_help` umstellen | Z.10 + Z.46-63 + Z.381-397 |
| `ui/mw_qso.py` | `_antenna_pref_label` Format-Änderung (nur ANT2-Zweige) | Z.105-109 |
| `main.py` | APP_VERSION + Disclaimer-Text + 540×340-Größe | Z.20 (APP_VERSION) + Z.417 (setFixedSize) + Z.448-451 (disclaimer) |
| `tests/test_bundle_j.py` | **NEU** — 9 Tests T1-T9 | — |
| Bestehende Tests | Test-Inventur via grep + Anpassung | siehe AC3 |

---

## 4. Randbedingungen

- **PySide6:** `Signal` statt `pyqtSignal`, `Slot` statt `pyqtSlot`.
- **Hardware-Pflicht:** ANT1 = TX immer, ANT2 = RX only. Bundle J ändert NICHTS
  an der TX-Antennen-Logik. Code-Verifikation 14.05.: `core/encoder.py:389`
  + `ui/mw_tx.py:83` rufen `set_tx_antenna("ANT1")` VOR jedem `ptt_on()` /
  `tune_on()`.
- **Thread-Safety:** Keine neuen Threads/Locks. `SimpleHelpDialog` läuft im
  GUI-Thread, modaler `exec()`-Block.
- **WindowModal-Wahl:** `SimpleHelpDialog` und `ConnectStatusDialog` beide
  `WindowModal` — Decoder-Background-Thread läuft unberührt weiter.
- **App-Theme:** `#1a1a2e` Hintergrund, `#CCC` Text. Konsistenz mit Settings/
  Connect-Modal.
- **i18n:** Disclaimer + ConnectStatus + SimpleHelpDialog sind **deutsch-only**.
  Bundle J fügt keine Übersetzungen hinzu.
- **MIT-Lizenz:** `LICENSE` existiert bereits. Kein neuer File.
- **Reversibilität:** Reine UI-/Doku-Änderungen. Keine Persistenz/Migration.
- **Circular-Import:** `ConnectStatusDialog` bekommt `app_version` als
  Konstruktor-Parameter (kein `from main import APP_VERSION`).

---

## 5. Nicht im Scope

- **i18n / Übersetzungen** für Disclaimer, Connect-Modal, SimpleHelpDialog.
- **Auto-Resize** des Connect-Modals an Inhalts-Höhe.
- **Pre-TX ANT1-Guard zusätzliche Aufrufe** — bereits abgedeckt durch
  `core/encoder.py:389` + `ui/mw_tx.py:83`.
- **SWR-Live-Watchdog (P53), Auto-Tune (P54), Stats-Toggle (P52)** — separate
  Workflows.
- **Bandpilot-Hilfe-Text** ändern.
- **Andere `QMessageBox`-Aufrufe in `settings_dialog.py`** (Confirmation
  Z.511/632/653/704/795/808) — bleiben unverändert, sind echte
  ButtonRole-Dialoge.
- **Existierende `HelpDialog`-Klasse** in `ui/help_dialog.py` — bleibt
  unverändert (Hauptmenü-Feature-Übersicht, andere Funktion).

---

## 6. Testbarkeit

**Unverzichtbare Tests (in `tests/test_bundle_j.py` NEU):**

- **T1 ConnectStatus-Footer:** Footer-`QLabel` existiert, `text()` matched
  Regex `r"^SimpleFT8 v\d+\.\d+\.\d+ · MIT License$"`, Alignment hat
  `AlignRight`-Bit, font.pointSize() ≤ 10.
- **T2 SimpleHelpDialog baseline:** `dlg = SimpleHelpDialog(None,
  "Test", "Hallo")`; `dlg.minimumSize().width() >= 700`,
  `dlg.minimumSize().height() >= 600`; QTextBrowser-Child mit `toPlainText()
  == "Hallo"`.
- **T3 SimpleHelpDialog markdown:** `SimpleHelpDialog(None, "Bold",
  "**bold**", markdown=True)`; QTextBrowser `toPlainText()` enthält "bold"
  ohne Sternchen.
- **T4 _make_info_btn ruft show_simple_help:** Mock auf
  `ui.settings_dialog.show_simple_help`, Klick auf `?`-Button →
  mock_called_with kwargs/args enthält Hint-Text.
- **T5 _show_bandpilot_help ruft show_simple_help mit markdown=True:**
  analog T4, prüft `markdown=True` als kwarg.
- **T6 _antenna_pref_label Diversity ANT2 mit delta:** Result-String enthält
  `"(RX: ANT2 ↑"`.
- **T7 _antenna_pref_label Diversity ANT2 ohne delta:** Result `"(RX: ANT2)"`.
- **T8 _antenna_pref_label Diversity ANT1:** Result `"(ANT1)"` (kein RX-Prefix).
- **T9 Intent-Klausel im Disclaimer:** Substring „persönlichen Gebrauch" in
  Disclaimer-QLabel.text() (SR2 — case-sensitive aber robust gegen kleine
  Wortlautänderungen).

**Bestehende Tests anpassen (SR4):**
- Inventur-Schritt: `grep -rn "ANT2 ↑\|(ANT2)" tests/`.
- Erwartete Treffer (basierend auf bisherigen Bundles): wahrscheinlich
  `tests/test_modules.py` oder eigene Antenna-Tests.
- Pro Treffer: alte Erwartung `(ANT2 ↑X.X dB)` → `(RX: ANT2 ↑X.X dB)`.

**Tests-Soll: 1220 → ~1229 (+9 in Bundle J, ggf. 1-2 Anpassungen alter Tests).**
