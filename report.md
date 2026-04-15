# JOHNBOY Analysis Report

## Project: SimpleFT8
**Generated:** 2026-04-15 17:47:11
**Tool:** JOHNBOY v1.0.0 - Sequential Single-Pass Analysis
**Path:** /Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8

---
## ⚡ KI-BRIEFING

**Was:** Desktop GUI App | Python
**Starten:** `python3 main.py` (Port 4991)
**Kern:** `ui/control_panel.py` (1349 Z., 6 Klassen, 2 Funktionen)
**Stand:** 2733 Code-Issues · 28 TODOs · Git ✅ · kein .env · ℹ️ 3642 Anti-Pattern Warnings
---
## ⚠️ Anti-Pattern Check

### Status: 🟡 WARNUNGEN
- **Patterns geladen:** 30 (aus PROBLEME.md)
- **Dateien geprüft:** 596
- **Treffer gesamt:** 8525 (0 Errors, 3642 Warnings, 4883 Info)

### 🟡 Warnings
- `[js_deep_nesting]` **3505× gefunden** — Zeile 254: Code >6 Ebenen eingerückt — schwer lesbar und testbar
  → `ui/mw_radio.py` (L254,265,367,403,404...) | `core/ntp_time.py` (L149,150,151,152,155...) | `core/qso_state.py` (L264,292,299,300,301...) | `radio/flexradio.py` (L132,133,141,267,268...) | `ui/rx_panel.py` (L171,174,250,401,402...) +237 weitere
  → Fix: Early Returns, Guard Clauses, oder Logik in Hilfsfunktionen auslagern
- `[python_fstring_missing_f]` **62× gefunden** — Zeile 153: String mit {variable} aber ohne f-Prefix — wird NICHT interpoliert!
  → `core/qso_state.py` (L153,209,224,255,301...) | `radio/flexradio.py` (L718,723,767,1003) | `ui/mw_qso.py` (L162,171) | `core/encoder.py` (L125,166,227) | `core/ap_lite.py` (L433) +34 weitere
  → Fix: f-Prefix hinzufügen: f"Text {variable}" statt "Text {variable}"
- `[python_broad_except]` **75× gefunden** — Zeile 41: Blankes except: fängt ALLES (auch SystemExit, KeyboardInterrupt)
  → `tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-04-02_dx-progress/tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-03-31_TX-funktioniert/tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-04-01_FEIERABEND_besser-als-sdr-control/tests/tx_bruteforce.py` (L41,47,79,126,134) | `backup/2026-04-01_1700_besser-als-sdr-control/tests/tx_bruteforce.py` (L41,47,79,126,134) +10 weitere
  → Fix: except Exception: oder spezifischen Typ verwenden

### ℹ️ Info
- `[python_print_debug]` **4883× gefunden** — Zeile 90: print() Debug-Ausgabe — in Produktion logging verwenden
  → `ui/mw_radio.py` (L90,98,209,365,385...) | `core/ntp_time.py` (L52,65,92,94,151...) | `core/qso_state.py` (L39,176,181,186,217...) | `radio/flexradio.py` (L98,106,127,132,147...) | `ui/main_window.py` (L82,422,521,532) +211 weitere
  → Fix: import logging + logging.debug() statt print()

> Neue Patterns: In `johnboy/PROBLEME.md` als `## PATTERN: name` eintragen → sofort aktiv!
---
## 🤖 KI Deep-Analysis (2026-04-15)

### Architektur-Bewertung
★★☆☆☆ (2/5) Monolithische Skripte ohne klare Trennung. decode.py mischt Signalverarbeitung, Decodierung, Visualisierung und CLI-Logik. dx_tune_dialog.py koppelt UI-Logik eng mit Radio-Hardware-Steuerung.

### Versteckte Risiken
- **Race Conditions**: dx_tune_dialog.py verwendet `feed_cycle()` ohne Thread-Synchronisation bei asynchronen Radio-Events.
- **Hardware-Zustandslecks**: Tuning-Dialog setzt Radio-Parameter, bei Abbruch/Fehler bleibt Hardware in unbekanntem Zustand.
- **Speicher-Explosion**: `search_sync_coarse()` erzeugt `score_map` mit unbegrenztem Wachstum bei vielen Kandidaten.
- **Blockierende UI**: Lange STFT-Berechnungen in decode.py blockieren Hauptthread.

### Fehlende Patterns
- **Error Handling**: Keine Exception-Behandlung für Hardware-Fehler (Radio-Steuerung) oder Datei-I/O.
- **Logging**: Nur print()-Debugging, keine strukturierte Protokollierung.
- **Tests**: Keine Unit/Integration-Tests für Signalverarbeitung.
- **Dependency Injection**: Radio-Objekt direkt instanziiert, schwer mockbar.
- **Konfiguration**: Magic numbers (GAIN_VALUES, ROUNDS) hardcoded.

### Sofort-Aktionen
1. **Thread-Sicherheit**: Mutex für `feed_cycle()` und Radio-Zugriffe in dx_tune_dialog.py.
2. **Hardware-Reset**: Safe-Recovery-Prozedur bei Dialog-Abbruch.
3. **Memory-Limit**: `score_map` in `search_sync_coarse()` auf max_cand begrenzen.

### Score
4/10 – Funktionell aber fragil. Fehlende Abstraktionen führen zu Wartungsproblemen.

---
## 📄 PROJECT DOCUMENTATION

**Source:** `README.md` (284 Zeilen, 2026-04-14)

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
| Scale | 596 files, 148,858 lines |
| Technical Debt | 28 TODOs + 2733 code issues |
| Risk | LOW - Minor issues to address |

### SOFORT-AKTIONEN:
4. 🟡 **TODO CLEANUP**: Address high-priority technical debt
---
## 📝 TODO Items and Issues

### TODO Summary
- **Total TODOs:** 28
- **By Priority:** Critical: 0, Medium: 25
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
- **Total Files Analyzed:** 565
- **Total Import Statements:** 6033
- **External/Third-party Dependencies:** 7
- **Circular Dependencies:** 0 found

### External Dependencies
- **PySide6**: Used in 920 file(s)
- **numpy**: Used in 386 file(s)
- **ntplib**: Used in 40 file(s)
- **PyFT8**: Used in 496 file(s)
- **scipy**: Used in 4 file(s)
- **ldpc**: Used in 2 file(s)
- **matplotlib**: Used in 6 file(s)

### Import Statistics
- **Total Imports**: 6033
- **Local Imports**: 1347
- **Third Party Imports**: 1854
- **Builtin Imports**: 2832
- **From Imports**: 3005
- **Direct Imports**: 3028
---
## 🏗️ Code-Struktur Index

### Übersicht
- **Klassen gesamt:** 443
- **Funktionen gesamt:** 950
- **API-Endpoints gesamt:** 0

### API-Endpoints
- Keine API-Endpoints erkannt

### Datei-Index (Klassen + Funktionen)
- **ui/qso_panel.py** (208 Z.) — 1 Klassen (QSOPanel)
- **ui/mw_radio.py** (631 Z.) — 1 Klassen (RadioMixin) | 1 Funktionen (_show_info_once)
- **core/ntp_time.py** (208 Z.) — 8 Funktionen (_load_saved, _save_current, set_mode, get_time...)
- **core/qso_state.py** (599 Z.) — 4 Klassen (QSODebugLog, QSOState, QSOData...)
- **core/protocol.py** (140 Z.) — 1 Klassen (ProtocolProfile) | 1 Funktionen (get_profile)
- **radio/flexradio.py** (1442 Z.) — 1 Klassen (FlexRadio)
- **radio/base_radio.py** (241 Z.) — 1 Klassen (RadioInterface)
- **config/settings.py** (134 Z.) — 1 Klassen (Settings)
- **ui/rx_panel.py** (647 Z.) — 1 Klassen (RXPanel)
- **ui/main_window.py** (582 Z.) — 1 Klassen (MainWindow)
- **ui/control_panel.py** (1349 Z.) — 6 Klassen (FrequencyHistogramWidget, _ModeBandCard, _AntenneCard...) | 2 Funktionen (_card_ss, _sep_line)
- **core/ft8lib_decoder.py** (166 Z.) — 2 Klassen (_Ft8sResult, Ft8Lib) | 2 Funktionen (_find_lib, get_ft8lib)
- **core/diversity.py** (260 Z.) — 1 Klassen (DiversityController)
- **ui/mw_cycle.py** (403 Z.) — 1 Klassen (CycleMixin)
- **ui/mw_qso.py** (351 Z.) — 1 Klassen (QSOMixin)
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
- **Files**: 596
- **Lines of code**: 148,858
- **Scale**: Large project

### LARGE FILE BOTTLENECKS:
- **radio/flexradio.py**: 1442 lines — consider splitting
- **ui/control_panel.py**: 1349 lines — consider splitting
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
- **ui/rx_panel.py**: 647 lines — monitor size
- **ft8_lib/libft8simple.c**: 642 lines — monitor size
- **ui/mw_radio.py**: 631 lines — monitor size
- **backup_diversity_stable/control_panel.py**: 631 lines — monitor size
- **backup_diversity_v1/control_panel.py**: 631 lines — monitor size
- **backup_beta/control_panel.py**: 631 lines — monitor size
- **core/qso_state.py**: 599 lines — monitor size
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
- **ft8_lib/ft8/decode.c**: 593 lines — monitor size
- **ui/main_window.py**: 582 lines — monitor size
- **backup/2026-04-01_1510_spektrum-akkum/ui/control_panel.py**: 563 lines — monitor size
- **backup/2026-04-01_1505_AP-live/ui/control_panel.py**: 563 lines — monitor size
- **backup/2026-04-01_AP-Decoder-Fix/ui/control_panel.py**: 563 lines — monitor size
- **backup/2026-04-01_RX-TX-PSK-OSD/ui/control_panel.py**: 563 lines — monitor size
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
- **Import density**: 6033 imports — high coupling
- **External dependencies**: 1854 third-party imports
- **Avg. file size**: 249 lines — moderate
---
## 🎨 Code Quality Analysis

### Code Quality: ✅ EXCELLENT
- **Files Analyzed:** 565
- **Files with Issues:** 426
- **Total Issues:** 2733
- **Tools Available:** 2/2

**📊 Issue Breakdown by Tool:**
- **Style + Logic (flake8):** 2732
- **Type Checking (mypy):** 1

**📈 By Severity:**
- **Errors:** 2727
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
*Report Generation Time: 2026-04-15 17:47:11*
*Analysis Method: File Tracker, TODO Extractor, Git Integration, Dependency Mapper, Security Scanner, Code Quality Checker*