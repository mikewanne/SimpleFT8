# Bundle J — V3 (final, alle R1-Findings adressiert)

> Workflow: V1 → V2 (Self-Review) → R1 (DeepSeek-V4-pro) → **V3**.
> Stand: 14.05.2026 nachmittags. APP_VERSION 0.97.26 → 0.97.27.

---

## 0. R1-Findings (Auswertungs-Tabelle)

| # | Schwere | Finding | Entscheidung | Begründung |
|---|---|---|---|---|
| F1 | 🟠 Risiko | `app_version`-Parameter muss als Instanzvariable gespeichert + in `_setup_ui` genutzt werden — V2 implizit | **angenommen** | V3 spezifiziert explizit `self._app_version = app_version` + Footer-Label-Bindung. |
| F2 | 🟡 Verbesserung | „Overengineering" — alle `?`-Hints in 700×600 = zuviel Weißraum, nur Bandpilot bräuchte das | **abgelehnt** | Mike's explizite Designentscheidung: „Konsistenz > Optimum-pro-Dialog — auch kurze Erklärungen landen im 700×600-Fenster mit Weißraum. Das ist OK." (TODO Z.70-71). Memory `feedback_mike_design_overrides_convention.md` — Mike's UX-Spec schlägt R1-Konvention. |
| F3 | 🟡 Verbesserung | Vollständigeres Stylesheet für `SimpleHelpDialog` (QTextBrowser/QPushButton/QScrollBar konsistent) | **angenommen** | V3 spezifiziert vollständiges Stylesheet analog `SettingsDialog`. |
| F4 | ⚪ Hinweis | Footer-Alignment in QLabel + im addWidget-Layout doppelt = verwirrend | **angenommen** | V3 klärt: nur `addWidget(..., alignment=Qt.AlignmentFlag.AlignRight)` im Layout, KEIN `QLabel.setAlignment`. |
| F5 | 🟡 Verbesserung | `delta_db == 0` (oder < 0.05 dB) sollte als `(RX: ANT2)` ohne Pfeil angezeigt werden | **angenommen mit Modifikation** | Code-Verifikation: HYSTERESE = 1.0 dB, also delta_db < 1.0 mit best_ant=A2 kann praktisch nicht auftreten. Defensiv aufnehmen: bei `delta is None OR abs(delta) < 0.05` → `(RX: ANT2)` ohne Pfeil. Billige Defensive, schadet nichts. |
| F6 | 🟠 Risiko | Test-Mock-Pfad für `show_simple_help` — Module-Top-Import in `settings_dialog.py` Pflicht für Mock-Adressierbarkeit | **angenommen** | V3: `from ui.simple_help_dialog import show_simple_help` als Z.18 (nach bestehenden ui.-Imports). Innerhalb `_make_info_btn` Lambda-Callback nutzt diese Funktion. Mock-Pfad `ui.settings_dialog.show_simple_help`. |
| F7 | 🟡 Verbesserung | `setFixedSize(352, 196)` plattform-abhängig fragil | **abgelehnt** | KISS akzeptiert. SimpleFT8 läuft nur auf Mike's Mac. Fixed-Size ist bewusst — kein Plattform-Drift in 2026. |

**Bilanz:** 5 angenommen (4 voll, 1 modifiziert), 2 abgelehnt mit Begründung.

---

## 1. Ziel

Vier orthogonale UI-/Doku-Tweaks aus Mike-Field-Test 14.05.2026 nachmittags
+ Klärungs-Gespräch als gemeinsames Bundle einspielen.

**Punkt 1 — Connect-Modal Version + MIT-Lizenz:** Footer-Zeile unten rechts
mit `SimpleFT8 v{APP_VERSION} · MIT License` (synchron via Konstruktor-
Parameter, kein Hardcode).

**Punkt 2 — Einheitlicher Help-Dialog mit Scrollbar:** Neuer Helper
`show_simple_help(parent, title, text, *, markdown=False)` in
`ui/simple_help_dialog.py`. Alle `?`-Hints + Bandpilot-Help nutzen ihn.
Mike-Entscheidung: Konsistenz > Weißraum-Optimum.

**Punkt 3 — RX-Label `(RX: ANT2 ...)`:** Nur im ANT2-Fall mit `RX:`-Prefix.
ANT1 bleibt überall `(ANT1)` ohne Prefix. delta=0 / None → ohne Pfeil.

**Punkt 4 — Intent-Klausel im Hardware-Disclaimer:** Satz „Das Projekt dient
ausschließlich dem persönlichen Gebrauch und der Verifikation technischer
Möglichkeiten." in den Disclaimer-Text einbauen.

**Punkt 5 — APP_VERSION:** v0.97.26 → v0.97.27.

---

## 2. Akzeptanzkriterien

**AC1 — Connect-Modal Footer:**
- `ConnectStatusDialog.__init__` neuer Parameter: `app_version: str = ""`.
- Im Body: `self._app_version = app_version`.
- In `_setup_ui` am Ende (nach `btn_row`):
  ```python
  self._footer_label = QLabel(f"SimpleFT8 v{self._app_version} · MIT License")
  self._footer_label.setStyleSheet("color: #666; font-size: 9pt; background-color: transparent;")
  layout.addWidget(self._footer_label, 0, Qt.AlignmentFlag.AlignRight)
  ```
  (F4: NUR addWidget-Alignment, kein QLabel.setAlignment).
- `setFixedSize(352, 196)` (war 176, +20 px für Footer).
- `·` = U+00B7 middle-dot.
- Aufruf-Stelle (zu grep'en — vermutlich in `main.py` Startup oder
  `ui/main_window.py`): `ConnectStatusDialog(parent, app_version=APP_VERSION)`.

**AC2 — Help-Dialog einheitlich + scrollbar:**
- Neue Datei `ui/simple_help_dialog.py`:
  - Klasse `SimpleHelpDialog(QDialog)`.
  - Module-Funktion `show_simple_help(parent, title, text, *, markdown=False)`
    → instantiiert + `exec()`.
  - `setMinimumSize(700, 600)`. KEIN `setFixedSize`.
  - `QTextBrowser`-Child (automatischer Scrollbar). `setOpenExternalLinks(True)`.
  - `setWindowModality(Qt.WindowModality.WindowModal)`.
  - `setWindowTitle(title)`.
  - Wenn `markdown=True`: `browser.setMarkdown(text)`. Sonst `browser.setPlainText(text)`.
  - QPushButton „Schließen" unten rechts (HBoxLayout mit Stretch + Button).
  - **Vollständiges Stylesheet (F3):**
    ```css
    QDialog { background-color: #1a1a2e; color: #CCC; }
    QTextBrowser {
        background-color: #14142a;
        color: #CCC;
        border: 1px solid #333;
        border-radius: 4px;
        padding: 8px;
        font-family: -apple-system, "SF Pro Text", sans-serif;
        font-size: 12pt;
    }
    QPushButton {
        background: #0066AA; color: white; border: none;
        border-radius: 3px; padding: 8px 16px; font-weight: bold;
    }
    QPushButton:hover { background: #0088CC; }
    QScrollBar:vertical {
        background: #222; border: none; width: 12px;
    }
    QScrollBar::handle:vertical {
        background: #444; border-radius: 3px; min-height: 30px;
    }
    QScrollBar::handle:vertical:hover { background: #555; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    ```
  - Esc schließt via Standard-QDialog (kein Custom-Handler).
- `_make_info_btn` (`ui/settings_dialog.py:60`): ruft jetzt
  `show_simple_help(btn.window(), "Info", hint)` statt `QMessageBox.information`.
- `_show_bandpilot_help` (Z.381): ruft
  `show_simple_help(self, "Bandpilot — Hilfe", text, markdown=True)`.
- Import-Pfad (F6): `from ui.simple_help_dialog import show_simple_help`
  als Module-Top in `settings_dialog.py` (nach Zeile 17 wo bereits
  `from ui.styles import MSGBOX_STYLE` steht).

**AC3 — RX-Label umformatiert:**
- `_antenna_pref_label` in `ui/mw_qso.py:90-109`:
  - Normal-Modus: `(ANT1)` UNVERÄNDERT.
  - Diversity + best_ant == "A1": `(ANT1)` UNVERÄNDERT.
  - Diversity + best_ant == "A2" + delta is None OR `abs(delta) < 0.05`:
    `(RX: ANT2)` (NEU mit Prefix, F5).
  - Diversity + best_ant == "A2" + delta ≥ 0.05: `(RX: ANT2 ↑X.X dB)`
    (NEU mit Prefix, abs(delta) gerundet auf 1 Dezimalstelle).

**AC4 — Intent-Klausel im Disclaimer:**
- `main.py:448-451` Disclaimer-QLabel-Text wird zu:
  ```
  SimpleFT8 ist eine private Machbarkeitsstudie. Das Projekt dient
  ausschließlich dem persönlichen Gebrauch und der Verifikation
  technischer Möglichkeiten. Nutzung auf eigene Gefahr — für
  Schäden an Hardware, Antennen oder Funkgeräten wird keine
  Haftung übernommen.
  ```
- Dialog-Höhe `setFixedSize(540, 300)` → `setFixedSize(540, 340)`
  (`main.py:417`).

**AC5 — APP_VERSION:**
- `main.py:APP_VERSION = "0.97.27"`.
- HISTORY/HANDOFF/CLAUDE/TODO Header aktualisiert.

---

## 3. Betroffene Module/Dateien

| Datei | Änderungs-Art | Stellen |
|---|---|---|
| `ui/connect_status_dialog.py` | F1 + AC1: Konstruktor-Param, Instance-Var, Footer-Label am Ende `_setup_ui`, setFixedSize 176→196 | __init__ + _setup_ui |
| `main.py` (oder mw_radio.py — Aufrufstelle ConnectStatusDialog) | AC1: `app_version=APP_VERSION` mitgeben | Aufruf-Stelle via grep |
| `ui/simple_help_dialog.py` | **NEU** AC2 + F3 + F4: Klasse + Helper + komplettes Stylesheet | gesamte Datei |
| `ui/settings_dialog.py` | F6 + AC2: Import-Top, `_make_info_btn` Z.60, `_show_bandpilot_help` Z.381 | Z.18 (Import), Z.60 (Lambda), Z.392-397 (msg → show_simple_help) |
| `ui/mw_qso.py` | F5 + AC3: ANT2-Pfade mit RX-Prefix + delta-Schwelle | Z.105-109 |
| `main.py` | AC4 + AC5: Disclaimer-Text + setFixedSize 300→340 + APP_VERSION-Bump | Z.20 + Z.417 + Z.448-451 |
| `tests/test_bundle_j.py` | **NEU**: 9 Tests T1-T9 | gesamte Datei |
| Bestehende Tests | Inventur: keine `_antenna_pref_label`-Tests gefunden (`grep -rn "_antenna_pref_label" tests/` = leer), keine Anpassung nötig | — |

---

## 4. Randbedingungen

- **PySide6:** `Signal`/`Slot`. F4 berücksichtigt: keine doppelten Alignments.
- **Hardware-Pflicht:** ANT1 = TX immer. Bundle J berührt TX-Antennen-Logik
  NICHT — `core/encoder.py:389` + `ui/mw_tx.py:83` bleiben unverändert.
- **Thread-Safety:** Keine neuen Threads. `SimpleHelpDialog` läuft im GUI-
  Thread, blockierender modaler exec.
- **Modal-Wahl:** `WindowModal` für SimpleHelpDialog — analog
  `ConnectStatusDialog`. Decoder-Background-Thread läuft weiter.
- **Theme-Konsistenz:** Stylesheet vollständig (F3) — keine Theme-Drift.
- **i18n:** Deutsch-only. Bundle J fügt keine Übersetzungen hinzu.
- **MIT-Lizenz:** `LICENSE` existiert bereits.
- **Circular-Import:** `app_version` als Parameter (kein
  `from main import APP_VERSION` in `ui/connect_status_dialog.py`).
- **Reversibilität:** Reine UI-/Doku-Änderungen. Keine Migration.

---

## 5. Nicht im Scope

- i18n / Übersetzungen.
- Auto-Resize des Connect-Modals.
- Pre-TX ANT1-Guard zusätzliche Aufrufe (bereits abgedeckt).
- SWR-Live-Watchdog (P53), Auto-Tune (P54), Stats-Toggle (P52) — separat.
- Bandpilot-Hilfe-Text ändern.
- Andere `QMessageBox`-Aufrufe (Confirmation für Löschen/Reset).
- Existierende `HelpDialog` (Hauptmenü-Feature-Übersicht).

---

## 6. Testbarkeit

**Tests (`tests/test_bundle_j.py` NEU):**

- **T1 ConnectStatus-Footer:** Footer-Label existiert, `text()` matched
  `r"^SimpleFT8 v\d+\.\d+\.\d+ · MIT License$"` mit `APP_VERSION`-Substitution,
  font.pointSize() ≤ 10.
- **T2 SimpleHelpDialog baseline:** Instanz, MinimumSize ≥ 700×600,
  QTextBrowser-Child mit `toPlainText() == "Hallo"`.
- **T3 SimpleHelpDialog markdown=True:** `**bold**` rendert ohne Sternchen
  in toPlainText().
- **T4 _make_info_btn ruft show_simple_help:** Mock auf
  `ui.settings_dialog.show_simple_help`, Klick auf `?` → mock_called.
- **T5 _show_bandpilot_help ruft show_simple_help mit markdown=True:**
  analog T4, `kwargs["markdown"] is True`.
- **T6 _antenna_pref_label Diversity ANT2 mit delta:** Result enthält
  `"(RX: ANT2 ↑"`.
- **T7 _antenna_pref_label Diversity ANT2 ohne delta (delta_db=None):**
  Result `"(RX: ANT2)"` ohne Pfeil.
- **T7b _antenna_pref_label Diversity ANT2 mit delta=0.0:** Result
  `"(RX: ANT2)"` ohne Pfeil (F5-Defensive).
- **T8 _antenna_pref_label Diversity ANT1:** Result `"(ANT1)"`.
- **T9 Intent-Klausel im Disclaimer:** Disclaimer-QLabel.text() enthält
  Substring „persönlichen Gebrauch".

**Tests-Soll: 1220 → 1230 (+10 in Bundle J).**

---

## 7. Field-Test (Mike nach Push)

| F# | Was prüfen |
|---|---|
| F1 | App-Start: Connect-Modal zeigt unten rechts „SimpleFT8 v0.97.27 · MIT License" — 5-7 Sek sichtbar |
| F2 | Settings öffnen → `?`-Button neben Rufzeichen → großer dunkler Dialog 700×600 mit Scrollbar, schließbar via Esc + Schließen-Button |
| F3 | Settings → „Bandpilot — Hilfe öffnen" → gleicher Dialog mit gerendertem Markdown, scrollbar |
| F4 | Diversity-Modus, QSO mit ANT2-Pref-Station: Label `(RX: ANT2 ↑X.X dB)` im Logbuch + Status |
| F5 | Diversity-Modus, QSO mit ANT1-Pref-Station: Label `(ANT1)` ohne Prefix |
| F6 | Normal-Modus, QSO: Label `(ANT1)` |
| F7 | App-Neustart: Hardware-Disclaimer enthält neuen Satz „dient ausschließlich dem persönlichen Gebrauch" |
