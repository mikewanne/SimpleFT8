# OPTIMIERUNGSWORKFLOW — SimpleFT8 (Start 05.06.2026)

> **Dies ist der lebende Plan + Fortschritts-Tracker der Optimierungs-Kampagne.**
> Er überlebt Context-Compacts: bei jedem Neustart zuerst diese Datei lesen, dann
> beim ersten offenen ☐-Punkt weitermachen. Quelle der Befunde: `OPTIMIERUNG_AUDIT.md`.

---

## ⛔ REGELN (Mike, 05.06.2026 — verbindlich)

1. **NUR Optimierungen.** Ziel ist Vereinfachung / Geschwindigkeit / toter Code.
   **Keine** neuen Features, keine Verhaltensänderungen.
2. **Bugs nur bei Zufallsfund.** Wenn Claude oder DeepSeek im Zuge der Optimierung
   einen echten Bug entdecken → korrigieren (als eigener, klar markierter Commit).
   Sonst wird NICHT nach Bugs gesucht — nur optimiert.
3. **Das Ungefährlichste zuerst** (Stufe 1 vor 2 vor 3).
4. **Pro nicht-trivialem Punkt: voller Workflow** V1→V2→DeepSeek-R1→V3→Code→Tests→
   Final-R1. Triviale Punkte (ungenutzter Import, tote lokale Variable, <5 Z. ohne
   Verhaltensänderung) dürfen **gebündelt** werden — aber danach IMMER volle Testsuite
   grün + 1 DeepSeek-Sichtung pro Bündel.
5. **Tests müssen grün bleiben.** Basis bei Start: **2426** (`QT_QPA_PLATFORM=offscreen
   ./venv/bin/python3 -m pytest tests/ -q`). Nie mit roter Suite committen.
6. **Atomar committen** (pro OPT-Punkt bzw. pro Bündel ein Commit). Nach jedem Punkt:
   diese Datei (Status + Fortschritts-Log) + HISTORY/HANDOFF aktualisieren.
7. **ANT1 = TX bleibt unangetastet.** Kein Eingriff in Antennen-/TX-Pfad-Logik.
8. **Hardware-/Reserve-Code NICHT entfernen** (Slice-B in flexradio, Icom-Stubs,
   ft8_lib). Siehe `OPTIMIERUNG_AUDIT.md` §2c.

## ⚓ Rückfallpunkt

- Git-Tag **`v0.99.9-pre-optimierung`** (auf GitHub `origin/main`, Commit `a80eebc`).
- Komplett zurück: `git checkout v0.99.9-pre-optimierung`.
- Einzelne Datei zurück: `git checkout v0.99.9-pre-optimierung -- <pfad>`.

## 🔄 So geht es nach einem Compact weiter

1. `CLAUDE.md` → `HISTORY.md` (Anker oben) → `HANDOFF.md` → **DIESE Datei** lesen.
2. `git log --oneline origin/main..HEAD` + Testsuite-Stand prüfen (verify-don't-assume).
3. Im **Fortschritts-Log** (unten) sehen, was zuletzt erledigt wurde.
4. Beim ersten **☐ offenen** Punkt der niedrigsten offenen Stufe weitermachen.
5. **NICHT** den ganzen Plan neu erfinden — er steht hier. Nur abarbeiten.

---

## 🎯 AUSFÜHRUNGS-REIHENFOLGE (Mike-Priorität 05.06.: **KISS/Robustheit > Geschwindigkeit**)

Gilt über ALLE Punkte (Teil-1-Tabellen „STUFE 1-3" weiter unten **+** Teil-2-Tabellen direkt
hier). **Die STUFE-Nummern unten sind NICHT die Reihenfolge** — diese Liste ist es:

1. **Toter Code** (risikolos, sofort, reine Entfernung): OPT-01..04 **+** OPT-40..43.
2. **Robustheit** (höchster Wert, je eigener Workflow): OPT-50..60. ⚠️ Verdachts-Bugs
   (OPT-55/58/59) ERST verifizieren, dann fixen — OPT-59 ist TX-Pfad (dreifach prüfen).
3. **KISS / Lesbarkeit**: OPT-61..64 **+** OPT-21 (Empfangskontext-Reset) **+** OPT-12/22.
4. **Geschwindigkeit (NACHRANGIG)** — nur nebenbei, wenn wir eh in der Datei sind:
   OPT-05..11, OPT-20 (Float/Int, eigener Workflow+Decode-Tests), OPT-23, OPT-24.
5. **Große Methoden entflechten** (langfristig, opportunistisch): OPT-30..32 + OPT-65/66.

Quelle aller Befunde: `OPTIMIERUNG_AUDIT.md` (Teil 1 = Decoder/Speed + control_panel;
**Teil 2 = ganze App, KISS/Robustheit**).

---

## TEIL 2 — Toter Code (zusätzlich, projektweit auf 0 Aufrufe verifiziert)
| ID | Was | Datei | Status |
|---|---|---|---|
| OPT-40 | Import `azimuthal_equidistant_project` + Methoden `_paint_user_distance_rings` / `_paint_user_sector_lines` | direction_map_widget.py | ☐ |
| OPT-41 | Konstante `_MAX_CYCLES` + Methoden `add_cycle_separator` / `_populate_separator_row` | rx_panel.py | ☐ |
| OPT-42 | Methode `_slot_tag` | qso_panel.py | ☐ |
| OPT-43 | `get_normal_preset` (deprecated-Stub, gibt immer `{}`) | config/settings.py | ☐ |
| | _❌ NICHT entfernen: `entries_to_station_points` ist genutzt (main_window:1680) — Fehlalarm._ | | |

## TEIL 2 — Robustheit (höchster Wert — je eigener Workflow)
| ID | Was | Datei | Status |
|---|---|---|---|
| OPT-50 | `load()`-Migration in `try/except` → kein App-Start-Crash bei Plattenfehler (✅ bestätigt) | settings.py:161 | ☐ |
| OPT-51 | `migrate_legacy_files()` in `__init__` in `try/except` (analog) | preset_store.py | ☐ |
| OPT-52 | **PSK-Worker: GUI-Update per Qt-Signal** statt direkt aus Thread (✅ Z.1271 bestätigt) | main_window.py | ☐ |
| OPT-53 | `load()`: kritische Felder (`callsign`/`locator`/…) per `isinstance` validieren | settings.py:115 | ☐ |
| OPT-54 | **`atomic_write_json`-Helfer** (DRY 5 Stores) + `ntp_time` atomar nachziehen (✅) | core/ (neu) + ntp_time.py | ☐ |
| OPT-55 | ⚠️ ADIF: CALL `.upper()` + RST validieren (QRZ-Upload-Sicherheit) — **erst verifizieren** | log/adif.py | ☐ |
| OPT-56 | `closeEvent`: `dx_tuning`-Branch + breites `except` eingrenzen | main_window.py | ☐ |
| OPT-57 | `station_stats` Writer-Thread sauberer Stop (`threading.Event`) | station_stats.py | ☐ |
| OPT-58 | ⚠️ **Zufallsfund-Verdacht:** `_execute_full_halt` leert `_p158_insertable` nicht → veraltete Einschub-Zeilen nach STOPP. **Severity prüfen, dann ggf. `.clear()`** | mw_qso.py:429 | ☐ |
| OPT-59 | ⚠️ **TX-PFAD, dreifach prüfen:** `_p94_quick73_filter` sendet 73 evtl. ohne `_abort_active_tx` | mw_cycle.py:1139 | ☐ |
| OPT-60 | ~60 stille `except…: pass` durchgehen, riskante auf konkrete Exception + `print` (laufend) | App-weit | ☐ |

## TEIL 2 — KISS / Lesbarkeit
| ID | Was | Datei | Status |
|---|---|---|---|
| OPT-61 | Property `qso_sm.is_busy` statt 11× kopiertem `(IDLE,TIMEOUT,CQ_CALLING,CQ_WAIT)`-Tupel (✅ 11×) | qso_state + Aufrufer | ☐ |
| OPT-62 | 3 Preset-Zugriffe (`get_dx`/`get_gain`/`get_normal`) vereinheitlichen / veraltete Pfade raus | settings.py | ☐ |
| OPT-63 | Locator-Auflösung-Duplikat → Helfer `_resolve_station_position()` | direction_map_widget.py | ☐ |
| OPT-64 | `get_enabled_bands`/`set_enabled_bands` Validierung → `_valid_bands(raw)` | settings.py | ☐ |
| OPT-65 | `_update_statusbar` (~80 Z.) in `_build_status_*`-Teile (langfristig) | main_window.py | ☐ |
| OPT-66 | `_handle_diversity_operate` (~80 Z.) Berechnung auslagern (langfristig) | mw_cycle.py | ☐ |

---

## STUFE 1 — Quick-Wins (S-Aufwand, kein Verhaltensrisiko)

> Diese Stufe darf in **2-3 Bündeln** laufen (Dead-Code / Speed-Konstanten / Style),
> je Bündel: umsetzen → Tests grün → DeepSeek-Sichtung → 1 Commit.

### Bündel 1A — Toter Code (reine Entfernung)
| ID | Was | Datei | Status |
|---|---|---|---|
| OPT-01 | Ungenutzte Imports entfernen | control_panel, settings_dialog, qso_panel, qso_detail_overlay, rx_panel, help_dialog, propagation, mw_tx(469), mw_qso (Liste: AUDIT §2a) | ☐ |
| OPT-02 | Tote lokale Variablen entfernen | mw_radio(mw/mode/sst/te/3×_time), mw_cycle(qso_busy), main_window(freq), dx_tune_dialog(ant2_gain), logbook_widget(t), control_panel(@1918/1932/1936/2152) | ☐ |
| OPT-03 | Tote UI-Helfer + Legacy-Signale entfernen | control_panel: `set_tx_freq`, `_group_label`, `_separator`, `_band_btn`, `_toggle_btn`, `_on_tx_level_changed` + Signale `tx_level_changed`, `preamp_changed` | ☐ |
| OPT-04 | f-Strings ohne Platzhalter glätten (kosmetisch) | mw_radio 2220/2287/2293, mw_qso 236, mw_cycle 694, qso_detail_overlay 45 | ☐ |

### Bündel 1B — Speed-Konstanten (verhaltensneutrales Caching)
| ID | Was | Datei:Zeile | Status |
|---|---|---|---|
| OPT-05 | Lokaler `from core import ntp_time` → Top-Level | decoder.py:360 | ☐ |
| OPT-06 | `np.hanning(2048)` + 63 Filter-Taps als Modul-Konstanten vorberechnen | decoder.py:679 + 724-730 | ☐ |
| | _DeepSeek-Bedingung VERIFIZIERT (05.06.): `n_fft=2048` fester Literal (Z.674, modus-invariant) + `_resample_to_12k` nur mit `source_rate=24000` (Z.343) → EINE Konstante korrekt._ | | |
| OPT-07 | Slot-Dauer-Dict `{"FT8":15.0,…}` → Modul-Konstante `_SLOT_LENGTHS` | decoder.py:229 | ☐ |
| OPT-08 | Pro-Offset `astype(int16)` 3×→1× pro Pass | decoder.py:507 | ☐ |
| OPT-09 | `target_rms` → Modul-Konstante `TARGET_RMS` | decoder.py:_preprocess_audio | ☐ |
| OPT-10 | Dedup-Key doppelt berechnet → 1× cachen (`r['_key']`) | decoder.py:_decode_with_subtraction | ☐ |
| OPT-11 | Encoder Slot-Dauer-Dict → `self._slot_dur` in `set_protocol()` | encoder.py | ☐ |

### Bündel 1C — Style-Konsolidierung (optional, kosmetisch)
| ID | Was | Datei | Status |
|---|---|---|---|
| OPT-12 | Wiederholte Inline-Styles → Helfer in `ui/styles.py` (`header_label_style(color)`, `bar_style(color)` …) | control_panel | ☐ |

---

## STUFE 2 — Echter Gewinn (je eigener voller Workflow)

| ID | Was | Datei | Aufwand/Risiko | Status |
|---|---|---|---|---|
| OPT-20 | **Float↔Int-Pipeline** im Decoder entzerren (einmal float32 halten, erst vor C-Decode int16). **Mit Decode-Referenztests!** | decoder.py (12× astype) | M / mittel | ☐ |
| OPT-21 | **Empfangskontext-Reset zentralisieren** → `_reset_reception_context()`, an 3 Stellen rufen. Entschärft Bug-Klasse §11. | mw_radio (_on_band/_on_mode/_on_rx_panel_toggled) | M / gering | ☐ |
| OPT-22 | Kollaps-Toggle-Buttons → `_make_collapse_toggle(...)` | control_panel:_setup_ui | M / gering | ☐ |
| OPT-23 | Diversity-Median kumulativ aus Histogramm statt Listen-Expansion | diversity.py:get_free_cq_freq | S / niedrig | ☐ |
| OPT-24 | `_apply_offset` vorallokiertes Array statt `np.pad`-Allokation pro Offset | decoder.py:_apply_offset | M / niedrig | ☐ |

---

## STUFE 3 — Langfristig, opportunistisch (nur wenn wir eh in der Datei sind)

| ID | Was | Datei | Status |
|---|---|---|---|
| OPT-30 | `_setup_ui` in `_create_*_card()` aufteilen | control_panel (~180 Z.) | ☐ |
| OPT-31 | `_on_band_changed` / `_on_mode_changed` in Phasen zerlegen | mw_radio | ☐ |
| OPT-32 | `_RadioCard.__init__` / `_AntenneCard.__init__` in Abschnitte | control_panel | ☐ |

---

## ⏸ OFFENE ENTSCHEIDUNGEN (warten auf Mike — NICHT eigenmächtig)

| ID | Frage | Status |
|---|---|---|
| OPT-Q1 | `core/ap_decoder.py` (`try_ap_decode`) + `core/osd_decoder.py` (`try_osd_decode`) sind nirgends verdrahtet — reservierte Decode-Technik (AP/OSD) oder löschbar? | ⏸ Mike |
| OPT-Q2 | `core/diversity_merger.py` (`DiversityMerger`) nur in Tests — Multiband-/Dual-RX-Reserve wie Slice-B, oder veraltet? | ⏸ Mike |
| OPT-Q3 | `direction_map_widget.py` Quaternion-Helfer (`_quat_*`, `_paint_user_distance_rings`, `_paint_user_sector_lines`) + Einzel-Helfer aus AUDIT §2b — je prüfen ob echte Leichen | ⏸ später, einzeln |

---

## 📋 FORTSCHRITTS-LOG (append-only, neueste oben)

> Pro erledigtem Punkt eine Zeile: `YYYY-MM-DD · OPT-NN · Kurz · Tests X→Y · Commit <sha>`.

- 2026-06-05 · Audit Teil 2 · Mike-Priorität: **KISS/Robustheit > Speed**. 3 DeepSeek-
  Reviews (GUI/Globus/Listen · Speichern/Laden · Orchestrierung) + eigene Robustheits-
  Stichprobe → AUDIT Teil 2 + neue Items OPT-40..66. Schlüsselfunde gegen echten Code
  verifiziert (1 Fehlalarm raus: `entries_to_station_points`). Reihenfolge neu (Toter Code
  → Robustheit → KISS → Speed nachrangig).
- 2026-06-05 · Setup · Plan angelegt, v0.99.9 gepusht + Tag `v0.99.9-pre-optimierung`,
  Tests-Basis **2426** grün. **DeepSeek-Review des Plans: voller GO** (Reihenfolge optimal,
  alle Stufe-1-Punkte verhaltensneutral, keine Overengineering-Punkte; OPT-06-Bedingung
  verifiziert; nur OPT-20 braucht neue Decode-Referenztests — schon eingeplant).

---

*Befund-Grundlage: `OPTIMIERUNG_AUDIT.md`. Regeln: Mike 05.06.2026. Dieser Plan ist
verbindlich bis abgearbeitet — bei Compact zuerst hierher zurück.*
