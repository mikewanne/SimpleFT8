# JOHNBOY Analysis Report

## Project: SimpleFT8
**Generated:** 2026-04-13 07:28:42
**Tool:** JOHNBOY v1.0.0 - Sequential Single-Pass Analysis
**Path:** /Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8

---
## ⚡ KI-BRIEFING

**Was:** Desktop GUI App | Python
**Starten:** `python3 main.py` (Port 4991)
**Kern:** `ui/control_panel.py` (1320 Z., 6 Klassen, 2 Funktionen)
**Stand:** 2698 Code-Issues · 29 TODOs · Git ✅ · kein .env · ℹ️ 3627 Anti-Pattern Warnings
---
## ⚠️ Anti-Pattern Check

### Status: 🟡 WARNUNGEN
- **Patterns geladen:** 30 (aus PROBLEME.md)
- **Dateien geprüft:** 595
- **Treffer gesamt:** 8483 (0 Errors, 3627 Warnings, 4856 Info)

### 🟡 Warnings
- `[python_fstring_missing_f]` **61× gefunden** — Zeile 148: String mit {variable} aber ohne f-Prefix — wird NICHT interpoliert!
  → `ui/mw_qso.py` (L148) | `core/ap_lite.py` (L428) | `radio/flexradio.py` (L718,723,767,997) | `core/encoder.py` (L116,160,217) | `core/qso_state.py` (L153,209,224,255,298...) +34 weitere
  → Fix: f-Prefix hinzufügen: f"Text {variable}" statt "Text {variable}"
- `[js_deep_nesting]` **3491× gefunden** — Zeile 367: Code >6 Ebenen eingerückt — schwer lesbar und testbar
  → `ui/main_window.py` (L367,502,506,507,512...) | `ui/control_panel.py` (L998,999,1107,1108) | `core/decoder.py` (L161,162,172,246,248...) | `ui/mw_cycle.py` (L58,64,79,118,119...) | `ui/mw_radio.py` (L199,210,298,334,335...) +234 weitere
  → Fix: Early Returns, Guard Clauses, oder Logik in Hilfsfunktionen auslagern
- `[python_broad_except]` **75× gefunden** — Zeile 41: Blankes except: fängt ALLES (auch SystemExit, KeyboardInterrupt)
  → `tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-04-02_dx-progress/tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-03-31_TX-funktioniert/tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-04-01_FEIERABEND_besser-als-sdr-control/tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-04-01_1700_besser-als-sdr-control/tests/tx_bruteforce.py` (L41,47,79,126,134) +10 weitere
  → Fix: except Exception: oder spezifischen Typ verwenden

### ℹ️ Info
- `[python_print_debug]` **4856× gefunden** — Zeile 27: print() Debug-Ausgabe — in Produktion logging verwenden
  → `ui/mw_qso.py` (L27,41,62,91,148...) | `ui/main_window.py` (L82,403,486,497) | `tests/test_modules.py` (L387,390,394,395,396...) | `core/decoder.py` (L132,136,161,170,183...) | `ui/mw_cycle.py` (L81,259,324) +210 weitere
  → Fix: import logging + logging.debug() statt print()

> Neue Patterns: In `johnboy/PROBLEME.md` als `## PATTERN: name` eintragen → sofort aktiv!
---
## 🤖 KI Deep-Analysis (2026-04-13)

### Architektur-Bewertung
★★☆☆☆ (2/5) — Monolithische decode.py ohne klare Trennung von Signalverarbeitung, Decodierung und UI. Globale Variablen statt Dependency Injection. Fehlende Abstraktion für Radio-Hardware.

### Versteckte Risiken
- **Race Conditions**: DXTuneDialog.feed_cycle() wird asynchron aufgerufen ohne Thread-Synchronisation.
- **Hardware-Zustand**: Radio-Einstellungen (Antenne/Gain) werden direkt manipuliert, keine Rollback-Logik bei Abbruch.
- **Speicherlecks**: decode.py lädt gesamte WAV-Datei in RAM, keine Streaming-Architektur für große Dateien.
- **Nicht-atomare Operationen**: In search_sync_coarse() wird score_map während Iteration modifiziert (del score_map[key]).

### Fehlende Patterns
- **Error Handling**: Keine Exception-Handling für Hardware-Fehler (Radio-IO) oder decode-Fehler.
- **Logging**: Statt print()-Debugging fehlt strukturiertes Logging mit Levels.
- **Tests**: Keine Unit-Tests für Signalverarbeitungs-Algorithmen.
- **Konfiguration**: Hardgecodete Parameter (GAIN_VALUES, ROUNDS) statt Konfigurationsdatei.

### Sofort-Aktionen
1. **Thread-Sicherheit**: DXTuneDialog mit QMutex/Locks absichern, Radio-Operationen in Main-Thread serialisieren.
2. **Error-Handling**: Try-catch in decode.py für Datei-I/O und Signalverarbeitung, Fehler an UI melden.
3. **Dependency Injection**: Radio-Interface abstrahieren, Mock für Tests ermöglichen.

### Score
4/10 — Funktionierender Prototyp, aber nicht produktionsreif. Fehlende Wartbarkeit und Robustheit.

---
## 📄 PROJECT DOCUMENTATION

**Source:** `README.md` (266 Zeilen, 2026-04-13)

SimpleFT8 — The Autonomous FT8/FT4 Client for FlexRadio
[English](#english) | [Deutsch](#deutsch)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

---
## 🧭 Projekt-Typ & Einstiegspunkte

### Erkannter Typ: Desktop GUI App  🟢 (high confidence)

**Frameworks:** PyQt, Pytest
**Sprachen:** Python
**Ports:** 4991, 4992

### Einstiegspunkte
- **main.py** (Zeile 134) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup_diversity_stable/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup_diversity_v1/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup_beta/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup_alpha/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-02_dx-progress/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_FEIERABEND_besser-als-sdr-control/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_1700_besser-als-sdr-control/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-02_dx-tune/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_1530_preamp-toggle/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-02_km-prefix-single-cycle/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_1710_dx-switch/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_1510_spektrum-akkum/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_1505_AP-live/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_AP-Decoder-Fix/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-02_single-cycle-dx-fix/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-02_session-start/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-03-31_TX-funktioniert/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`
- **backup/2026-04-01_RX-TX-PSK-OSD/main.py** (Zeile 106) — Main entry (if __name__ == "__main__")  
  `python3 main.py`

### Start-Befehle
- `python3 main.py`

---
## 🎯 EXECUTIVE DASHBOARD

### HEALTH: 🟡 MONITOR CLOSELY
| Metrik | Status |
|--------|--------|
| Security | LOW |
| Code Quality | 9.5/10 ✅ EXCELLENT |
| Maintainability | 6.0/10 |
| Git | ✅ Git repo on main |
| Scale | 595 files, 147,839 lines |
| Technical Debt | 29 TODOs + 2698 code issues |
| Risk | LOW - Minor issues to address |

### SOFORT-AKTIONEN:
4. 🟡 **TODO CLEANUP**: Address high-priority technical debt
---
## 📝 TODO Items and Issues

### TODO Summary
- **Total TODOs:** 29
- **By Priority:** Critical: 0, Medium: 26
- **By File:** decoder.py(1), decoder.py(1), decoder.py(1)

### TODO Items by Location
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen
- **decoder.py:141** - TODO: Spektrum-Akkumulierung spaeter einbauen

### Priority Actions
1. **Focus on ap_lite.py:** 3 TODOs - highest concentration
2. **Critical Items:** 0 FIXME/HACK items need immediate attention
---
## 🌿 Git Repository Status

### Repository Information
- **Status:** ✅ Git repository active
- **Current Branch:** main
- **Remote:** No remote configured
---
## 🔗 Dependency Analysis

### Dependency Overview
- **Total Files Analyzed:** 564
- **Total Import Statements:** 6011
- **External/Third-party Dependencies:** 7
- **Circular Dependencies:** 0 found

### External Dependencies
- **PySide6**: Used in 918 file(s)
- **numpy**: Used in 388 file(s)
- **ntplib**: Used in 40 file(s)
- **PyFT8**: Used in 496 file(s)
- **scipy**: Used in 4 file(s)
- **ldpc**: Used in 2 file(s)
- **matplotlib**: Used in 6 file(s)

### Import Statistics
- **Total Imports**: 6011
- **Local Imports**: 1343
- **Third Party Imports**: 1854
- **Builtin Imports**: 2814
- **From Imports**: 2989
- **Direct Imports**: 3022
---
## 🏗️ Code-Struktur Index

### Übersicht
- **Klassen gesamt:** 440
- **Funktionen gesamt:** 953
- **API-Endpoints gesamt:** 0

### API-Endpoints
- Keine API-Endpoints erkannt

### Datei-Index (Klassen + Funktionen)
- **ui/mw_qso.py** (309 Z.) — 1 Klassen (QSOMixin)
- **ui/main_window.py** (547 Z.) — 1 Klassen (MainWindow)
- **ui/control_panel.py** (1320 Z.) — 6 Klassen (FrequencyHistogramWidget, _ModeBandCard, _AntenneCard...) | 2 Funktionen (_card_ss, _sep_line)
- **tests/test_modules.py** (402 Z.) — 2 Klassen (FakeSettings, BadSettings) | 35 Funktionen (test_agc_loud_signal, test_agc_normal_signal, test_agc_clipping_protection, test_agc_silence...)
- **core/decoder.py** (479 Z.) — 1 Klassen (Decoder) | 5 Funktionen (_apply_agc, _reconstruct_signal, _apply_offset, _preprocess_audio...)
- **core/drift.py** (116 Z.) — 3 Funktionen (_to_analytic, apply_drift_correction, generate_drift_variants)
- **ui/mw_cycle.py** (360 Z.) — 1 Klassen (CycleMixin)
- **ui/mw_tx.py** (139 Z.) — 1 Klassen (TXMixin)
- **ui/mw_radio.py** (554 Z.) — 1 Klassen (RadioMixin)
- **core/ap_lite.py** (459 Z.) — 3 Klassen (FailedDecodeBuffer, APLiteResult, APLite) | 5 Funktionen (generate_candidates, _build_costas_reference, align_buffers, correlate_candidate...)
- **ui/dx_tune_dialog.py** (378 Z.) — 1 Klassen (DXTuneDialog) | 1 Funktionen (_build_interleaved_schedule)
- **radio/base_radio.py** (229 Z.) — 1 Klassen (RadioInterface)
- **radio/flexradio.py** (1436 Z.) — 1 Klassen (FlexRadio)
- **core/ntp_time.py** (131 Z.) — 5 Funktionen (get_time, get_correction, get_status_text, update_from_decoded...)
- **core/encoder.py** (235 Z.) — 1 Klassen (Encoder)
---
## ⚙️ Config-Snapshot

### Erkannte Config-Dateien
backup_diversity_v1/settings.py, config/settings.py, backup_diversity_stable/settings.py, backup_alpha/settings.py, backup/settings.py, backup/2026-04-02_dx-progress/config/settings.py, backup/2026-03-31_TX-funktioniert/config/settings.py, backup/2026-04-01_FEIERABEND_besser-als-sdr-control/config/settings.py ... (+33 weitere)

### Ports
**4991, 4992**

### URLs & Hosts
- Keine URLs erkannt

### Feature-Flags
- Keine Feature-Flags erkannt

### .env Keys (Werte maskiert)
Keine .env Datei

- requirements.txt: 6 Packages (PySide6, numpy, sounddevice, ntplib, pyserial, paho-mqtt)
- requirements.txt: 7 Packages (PySide6, numpy, sounddevice, ntplib, PyFT8, pyserial, paho-mqtt)
- requirements.txt: 7 Packages (PySide6, numpy, sounddevice, ntplib, PyFT8, pyserial, paho-mqtt)
- requirements.txt: 7 Packages (PySide6, numpy, sounddevice, ntplib, PyFT8, pyserial, paho-mqtt)
- requirements.txt: 7 Packages (PySide6, numpy, sounddevice, ntplib, PyFT8, pyserial, paho-mqtt)
- requirements.txt: 7 Packages (PySide6, numpy, sounddevice, ntplib, PyFT8, pyserial, paho-mqtt)
- requirements.txt: 7 Packages (PySide6, numpy, sounddevice, ntplib, PyFT8, pyserial, paho-mqtt)
- requirements.txt: 7 Packages (PySide6, numpy, sounddevice, ntplib, PyFT8, pyserial, paho-mqtt)
---
## ⚡ Performance Impact Analysis

### CODEBASE SCALE:
- **Files**: 595
- **Lines of code**: 147,839
- **Scale**: Large project

### LARGE FILE BOTTLENECKS:
- **radio/flexradio.py**: 1436 lines — consider splitting
- **ui/control_panel.py**: 1320 lines — consider splitting
- **backup_diversity_stable/flexradio.py**: 1297 lines — consider splitting
- **backup_diversity_v1/flexradio.py**: 1297 lines — consider splitting
- **backup_beta/flexradio.py**: 1297 lines — consider splitting
- **ft8_lib/ft8/message.c**: 1155 lines — consider splitting
- **backup_alpha/flexradio.py**: 1132 lines — consider splitting
- **backup/flexradio.py**: 1132 lines — consider splitting
- **backup/2026-04-02_km-prefix-single-cycle/radio/flexradio.py**: 1129 lines — consider splitting
- **backup/2026-04-02_single-cycle-dx-fix/radio/flexradio.py**: 1129 lines — consider splitting
- **backup/2026-04-02_dx-progress/radio/flexradio.py**: 1126 lines — consider splitting
- **backup/2026-04-02_dx-tune/radio/flexradio.py**: 1107 lines — consider splitting
- **backup/2026-04-01_FEIERABEND_besser-als-sdr-control/radio/flexradio.py**: 1000 lines — monitor size
- **backup/2026-04-01_1710_dx-switch/radio/flexradio.py**: 1000 lines — monitor size
- **backup/2026-04-02_session-start/radio/flexradio.py**: 1000 lines — monitor size
- **backup/2026-04-01_1700_besser-als-sdr-control/radio/flexradio.py**: 999 lines — monitor size
- **backup/2026-04-01_1530_preamp-toggle/radio/flexradio.py**: 999 lines — monitor size
- **backup/2026-04-01_1510_spektrum-akkum/radio/flexradio.py**: 999 lines — monitor size
- **backup/2026-04-01_1505_AP-live/radio/flexradio.py**: 999 lines — monitor size
- **backup/2026-04-01_AP-Decoder-Fix/radio/flexradio.py**: 999 lines — monitor size
- **backup/2026-04-01_RX-TX-PSK-OSD/radio/flexradio.py**: 999 lines — monitor size
- **backup/2026-03-31_TX-funktioniert/radio/flexradio.py**: 875 lines — monitor size
- **backup_diversity_stable/main_window.py**: 798 lines — monitor size
- **backup_diversity_v1/main_window.py**: 782 lines — monitor size
- **backup_beta/main_window.py**: 777 lines — monitor size
- **backup_alpha/main_window.py**: 677 lines — monitor size
- **backup/main_window.py**: 667 lines — monitor size
- **ui/rx_panel.py**: 641 lines — monitor size
- **backup_diversity_stable/control_panel.py**: 631 lines — monitor size
- **backup_diversity_v1/control_panel.py**: 631 lines — monitor size
- **backup_beta/control_panel.py**: 631 lines — monitor size
- **backup_alpha/control_panel.py**: 598 lines — monitor size
- **backup/control_panel.py**: 598 lines — monitor size
- **backup/2026-04-01_1700_besser-als-sdr-control/ui/control_panel.py**: 598 lines — monitor size
- **backup/2026-04-01_1530_preamp-toggle/ui/control_panel.py**: 598 lines — monitor size
- **backup/2026-04-02_dx-progress/ui/control_panel.py**: 594 lines — monitor size
- **backup/2026-04-01_FEIERABEND_besser-als-sdr-control/ui/control_panel.py**: 594 lines — monitor size
- **backup/2026-04-02_dx-tune/ui/control_panel.py**: 594 lines — monitor size
- **backup/2026-04-02_km-prefix-single-cycle/ui/control_panel.py**: 594 lines — monitor size
- **backup/2026-04-01_1710_dx-switch/ui/control_panel.py**: 594 lines — monitor size
- **backup/2026-04-02_single-cycle-dx-fix/ui/control_panel.py**: 594 lines — monitor size
- **backup/2026-04-02_session-start/ui/control_panel.py**: 594 lines — monitor size
- **ft8_lib/ft8/decode.c**: 592 lines — monitor size
- **core/qso_state.py**: 586 lines — monitor size
- **backup/2026-04-01_1510_spektrum-akkum/ui/control_panel.py**: 563 lines — monitor size
- **backup/2026-04-01_1505_AP-live/ui/control_panel.py**: 563 lines — monitor size
- **backup/2026-04-01_AP-Decoder-Fix/ui/control_panel.py**: 563 lines — monitor size
- **backup/2026-04-01_RX-TX-PSK-OSD/ui/control_panel.py**: 563 lines — monitor size
- **ui/mw_radio.py**: 554 lines — monitor size
- **ui/main_window.py**: 547 lines — monitor size
- **backup/2026-04-02_dx-progress/ui/main_window.py**: 529 lines — monitor size
- **backup/2026-04-02_km-prefix-single-cycle/ui/main_window.py**: 526 lines — monitor size
- **backup/2026-04-02_dx-tune/ui/main_window.py**: 523 lines — monitor size
- **backup/2026-04-02_single-cycle-dx-fix/ui/main_window.py**: 522 lines — monitor size
- **backup/2026-04-01_1700_besser-als-sdr-control/ui/main_window.py**: 521 lines — monitor size
- **backup/2026-04-01_1530_preamp-toggle/ui/main_window.py**: 521 lines — monitor size
- **backup/2026-04-01_1510_spektrum-akkum/core/decoder.py**: 518 lines — monitor size
- **backup/2026-04-01_FEIERABEND_besser-als-sdr-control/ui/main_window.py**: 514 lines — monitor size
- **backup/2026-04-01_1710_dx-switch/ui/main_window.py**: 514 lines — monitor size
- **backup/2026-04-02_session-start/ui/main_window.py**: 514 lines — monitor size
- **backup_diversity_stable/decoder.py**: 507 lines — monitor size
- **backup_diversity_v1/decoder.py**: 507 lines — monitor size
- **backup_beta/decoder.py**: 507 lines — monitor size
- **backup_alpha/decoder.py**: 507 lines — monitor size
- **backup/decoder.py**: 507 lines — monitor size
- **backup/2026-04-02_dx-progress/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-01_FEIERABEND_besser-als-sdr-control/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-01_1700_besser-als-sdr-control/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-02_dx-tune/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-01_1530_preamp-toggle/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-02_km-prefix-single-cycle/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-01_1710_dx-switch/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-02_single-cycle-dx-fix/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-02_session-start/core/decoder.py**: 507 lines — monitor size
- **backup/2026-04-01_1505_AP-live/core/decoder.py**: 502 lines — monitor size
- **backup/2026-04-01_AP-Decoder-Fix/core/decoder.py**: 502 lines — monitor size

### COMPLEXITY ASSESSMENT:
- **Import density**: 6011 imports — high coupling
- **External dependencies**: 1854 third-party imports
- **Avg. file size**: 248 lines — moderate
---
## 🎨 Code Quality Analysis

### Code Quality: ✅ EXCELLENT
- **Files Analyzed:** 564
- **Files with Issues:** 423
- **Total Issues:** 2698
- **Tools Available:** 2/2

**📊 Issue Breakdown by Tool:**
- **Style + Logic (flake8):** 2697
- **Type Checking (mypy):** 1

**📈 By Severity:**
- **Errors:** 2692
- **Warnings:** 6

**🔥 Top Problem Files:**
- **tx_bruteforce.py**: 660 issues
- **ldpc.py**: 515 issues
- **step6_tx_verify.py**: 255 issues
- **__init__.py**: 190 issues
- **control_panel.py**: 156 issues
---
## 🔒 Security: ✅ Keine Findings
---
## 📋 Recommendations

• Prioritize addressing high-priority TODO items to reduce technical debt and improve code maintainability.
---

---

*Generated by JOHNBOY v1.0.0 - Sequential Single-Pass Analysis*
*Report Generation Time: 2026-04-13 07:28:42*
*Analysis Method: File Tracker, TODO Extractor, Git Integration, Dependency Mapper, Security Scanner, Code Quality Checker*