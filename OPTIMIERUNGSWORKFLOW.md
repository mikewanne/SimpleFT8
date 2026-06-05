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
| OPT-40 | Import `azimuthal_equidistant_project` + Methoden `_paint_user_distance_rings` / `_paint_user_sector_lines` (+ verwaist: `DISTANCE_RINGS_KM`, Import `SECTOR_COUNT`) | direction_map_widget.py | ☑ |
| OPT-41 | Konstante `_MAX_CYCLES` + Methoden `add_cycle_separator` / `_populate_separator_row` (+ verwaist: `_FONT_SEP`, `_COLOR_SEP`) | rx_panel.py | ☑ |
| OPT-42 | Methode `_slot_tag` | qso_panel.py | ☑ |
| OPT-43 | `get_normal_preset` (deprecated-Stub, gibt immer `{}`) + dessen Test | config/settings.py | ☑ |
| | _❌ NICHT entfernen: `entries_to_station_points` ist genutzt (main_window:1680) — Fehlalarm._ | | |

## TEIL 2 — Robustheit (höchster Wert — je eigener Workflow)
| ID | Was | Datei | Status |
|---|---|---|---|
| OPT-50 | `load()`-Migration `save()` in `try/except` → kein App-Start-Crash bei Plattenfehler (v0.99.12, +Mutationstest) | settings.py | ☑ |
| OPT-51 | `migrate_legacy_files()` in `try/except` — **war BEREITS so** (preset_store.py:175-179), verify-don't-assume | preset_store.py | ☑ |
| OPT-52 | **PSK-Worker: GUI-Update per Qt-Signal** statt direkt aus Thread (✅ Z.1271 bestätigt) | main_window.py | ☐ |
| OPT-53 | `load()`: bekannte Felder gegen DEFAULTS-Typ validiert (`_validate_types`, `type() is type()` → bool/int-Falle vermieden; dynamische Keys unberührt). v0.99.14 | settings.py | ☑ |
| OPT-54 | **`atomic_write_json`-Helfer** (DRY) + `ntp_time` atomar nachgezogen — Helfer + 5 core-Stores migriert; settings bewusst raus (core/__init__-Last). v0.99.13 | core/atomic_json.py + ntp_time.py +5 | ☑ |
| OPT-55 | ⚠️ ADIF: CALL `.upper()` + RST validieren (QRZ-Upload-Sicherheit) — **erst verifizieren** | log/adif.py | ☐ |
| OPT-56 | `closeEvent`: breites `except` um `audio_monitor.stop()` entfernt (getattr-Guard; stop() ist intern robust). dx_tuning-Teil = NICHT-FUND (parent=self, Laufzeit-State). v0.99.15 | main_window.py | ☑ |
| OPT-57 | `station_stats` Writer-Thread sauberer Stop — **Sentinel** + `shutdown(timeout=5)` (statt Event: FIFO-Drain-Garantie), closeEvent-Aufruf. v0.99.16 | station_stats.py | ☑ |
| OPT-58 | ⚠️ **Zufallsfund-Verdacht:** `_execute_full_halt` leert `_p158_insertable` nicht → veraltete Einschub-Zeilen nach STOPP. **Severity prüfen, dann ggf. `.clear()`** | mw_qso.py:429 | ☐ |
| OPT-59 | ⚠️ **TX-PFAD, dreifach prüfen:** `_p94_quick73_filter` sendet 73 evtl. ohne `_abort_active_tx` | mw_cycle.py:1139 | ☐ |
| OPT-60 | ~60 stille `except…: pass` durchgegangen → **kein systematischer Handlungsbedarf** (verify-don't-assume): **0 bare `except:`** (Hauptrisiko fehlt), 59 Blöcke davon 15 in `flexradio.py` (TX-Pfad, gesperrt), Rest überwiegend legitimes Best-Effort (Daten-Lade-Defensive, Cleanup). Massenumstellung = Busy-Work + Regressionsrisiko. Nur opportunistische Einzelfixes. | App-weit | ☑ geprüft |

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
| OPT-01 | Ungenutzte Imports entfernen (frischer pyflakes-Lauf, je gegen Live-Code verifiziert; `__init__`-Re-Exports + TYPE_CHECKING-MainWindow bewusst BEHALTEN) | core/message, propagation, debug_log, station_stats, auto_hunt(TYPE_CHECKING FT8Message), control_panel, settings_dialog, main_window, help_dialog, rx_panel, qso_detail_overlay, direction_map_widget, qso_panel, mw_qso, mw_tx(469), mw_radio(4× lokales `time`), bootstrap_ci | ☑ |
| OPT-02 | Tote lokale Variablen entfernen (pyflakes-autoritativ; Audit-Liste war ungenau — `sst/te` + control_panel-`@191x` waren NICHT tot; dafür Zusatzfunde flexradio/generate_plots/dx_tune ant1_gain) | main_window(freq), control_panel(`_SEP_SS`), mw_radio(mw, mode), logbook_widget(t), dx_tune_dialog(ant1_gain, ant2_gain), mw_cycle(qso_busy), flexradio(body), generate_plots(d_rsc) | ☑ |
| OPT-03 | Tote UI-Helfer + Legacy-Signale entfernen | control_panel: `set_tx_freq`, `_group_label`, `_separator`, `_band_btn`, `_toggle_btn`, `_on_tx_level_changed` + Signale `tx_level_changed`, `preamp_changed` (+ verwaist: Import `_SEP_COLOR`) | ☑ |
| OPT-04 | f-Strings ohne Platzhalter glätten (kosmetisch; 15 Stellen, je auf fehlende `{{`/`}}` geprüft) | qso_state(2), qrz_upload_worker, control_panel(5 inkl. 2-Literal-debug_log), mw_radio(4), mw_qso, mw_cycle, flexradio(2). **Bewusst SKIP:** qso_detail_overlay:44 + awards_dialog:191 (CSS-Templates mit escaped `{{`) | ☑ |

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
| OPT-Q1 | `core/ap_decoder.py` + `core/osd_decoder.py` — Mike-Entscheid 05.06.: nicht verlinkt + nicht FT2-relevant (rein FT8, PyFT8-LDPC) → **ENTFERNT** (v0.99.11) | ✅ ENTFERNT |
| OPT-Q2 | `core/diversity_merger.py` (+ Test) — nicht FT2-relevant, NICHT der Slice-B-Merge-Baustein (DeepSeek bestätigt) → **ENTFERNT** (v0.99.11) | ✅ ENTFERNT |
| OPT-Q3 | `direction_map_widget.py` Quaternion-Helfer (`_quat_*`, `_paint_user_distance_rings`, `_paint_user_sector_lines`) + Einzel-Helfer aus AUDIT §2b — je prüfen ob echte Leichen | ⏸ später, einzeln |

---

## 📋 FORTSCHRITTS-LOG (append-only, neueste oben)

> Pro erledigtem Punkt eine Zeile: `YYYY-MM-DD · OPT-NN · Kurz · Tests X→Y · Commit <sha>`.

- 2026-06-05 · **OPT-60 (geprüft, KEIN Code)** · ~60 stille `except: pass` app-weit
  triagiert: **0 bare `except:`** (das Hauptrisiko existiert nicht), 59 Blöcke davon
  **15 in `flexradio.py`** (TX-Pfad — gesperrt), der Rest überwiegend bewusstes
  Best-Effort (korrupte-JSON-Lade-Defensive `ntp_time`/`preset_store`, Cleanup
  `audio_monitor.stop` [in OPT-56 als robust bestätigt], UI-Guards). **Bewertung
  (verify-don't-assume + KISS): kein systematischer Handlungsbedarf** — Massen-
  umstellung wäre Busy-Work mit Regressionsrisiko, teils im gesperrten TX-Pfad.
  OPT-60 herabgestuft auf „opportunistische Einzelfixes". Kein Commit.
- 2026-06-05 · **OPT-57 (v0.99.16, Stufe 2 Robustheit, voller Workflow)** ·
  `station_stats` Writer (Daemon-Thread, `while True`, kein Stop) → Modul-Sentinel
  `_SHUTDOWN` + `shutdown(timeout=5.0)`: reiht den Sentinel ein (FIFO-Drain-Garantie
  für alle davor liegenden Einträge), joint mit Timeout. `_writer_loop` nur +
  `if entry is _SHUTDOWN: break` (get(timeout=5) unverändert → Laufbetrieb 0 Änderung).
  closeEvent ruft `_stats_logger.shutdown()` am Ende (getattr-Guard). **Sentinel statt
  Audit-„Event"** (eigene Entscheidung: FIFO-Drain gratis, kein Polling-Opfer). DeepSeek
  Plan-R1 GO (join-Timeout-Auflage kritisch geprüft: `get` hängt nicht 5s, `put` weckt
  sofort) + Final-R1 **PUSH FREIGEBEN** (Race ausgeschlossen). Tests 2434→**2438** (+4).
  Commit `9af78bb`.
- 2026-06-05 · **OPT-56 (v0.99.15, Stufe 2 Robustheit, voller Workflow)** ·
  closeEvent: breites `except Exception: pass` um `audio_monitor.stop()` entfernt →
  `getattr`-Guard (stop() ist intern robust+idempotent, das äußere except verschluckte
  echte Bugs). **Teil (a) dx_tuning = NICHT-FUND** (verify-don't-assume: `_dx_tune_dialog`
  hat `parent=self` → Qt schließt ihn; `_rx_mode`/Lock sind Laufzeit-State). DeepSeek-R1
  GO (empfahl exakt die `is not None`-Variante). Tests 2433→**2434** (+1 Mutationsbeweis).
  Commit `d6bc901`. **→ Nächster offener Punkt: KISS-Stufe (OPT-61 `is_busy`-Property).**
- 2026-06-05 · **OPT-53 (v0.99.14, Stufe 2 Robustheit, voller Workflow)** ·
  `config/settings.py:load()` übernahm geladene config.json-Werte blind
  (`update(saved)`) → neue `_validate_types()` prüft jedes **DEFAULTS**-Feld gegen
  `type(value) is type(default)` und resettet bei Mismatch auf den Default (+ Meldung),
  Aufruf vor den Migrationen. **`type() is type()` statt isinstance** = bool/int sauber
  getrennt (`flexradio_port: true` würde mit isinstance durchrutschen — Mutationsbeweis-
  Test). Iteriert nur über DEFAULTS → dynamische Keys (enabled_bands/tx_slot_lock/
  presets) unberührt. Normalbetrieb 0 Änderung. DeepSeek Plan-R1 **GO ohne Korrekturen**
  (alle DEFAULTS generisch = KISS; float→Reset akzeptabel; Platzierung vor Migrationen
  ok) + Final-R1 **PUSH FREIGEBEN**. Reines Settings-Laden, ANT1=TX unberührt. Tests
  2424→**2433** (+9 `test_settings_typecheck.py`). Commit `e36c995`. **→ Nächster offener
  Punkt: OPT-56** (closeEvent dx_tuning + breites except). OPT-52 (Threading) → Mike.
- 2026-06-05 · **OPT-54 (v0.99.13, Stufe 2 Robustheit, voller Workflow)** ·
  `core/atomic_json.py` neu (`atomic_write_json`, DRY) + `ntp_time._save_current`
  von nicht-atomarem `write_text` auf den Helfer umgestellt (**schließt die
  Atomaritäts-Lücke**) + 5 weitere core-Stores migriert (`awards_prefs`,
  `rf_preset_store`, `mode_recommender`, `psk_reporter`, `locator_db`); 3× totes
  `import os` entfernt. dump_kwargs durchgereicht → Bytes bit-identisch. **Scope-
  Korrektur ggü. Plan-R1:** `config/settings.py` NICHT migriert — beim
  Implementieren verifiziert dass `core/__init__` decoder+encoder+ft8_lib lädt →
  ein `from core…`-Import zöge das in jeden isolierten settings-Import; settings
  ist ohnehin schon atomar (DeepSeek Final-R1 segnete die Korrektur ab). Bewusst
  ausgeschlossen außerdem: `preset_store` (fsync+Rollback), `adif` (Rohtext),
  `rx_history` (retry-Loop). DeepSeek Plan-R1 GO + Final-R1 **PUSH FREIGEBEN**
  (6 Prüfpunkte). Reines File-IO, ANT1=TX unberührt. Tests 2416→**2424** (+8
  `test_atomic_json.py`). Commit `7ed850c`. **→ Nächster offener Punkt: OPT-53**
  (Settings-Typvalidierung). OPT-52 (PSK-Worker Thread→Qt-Signal) berührt
  Threading → Mike kurz vorlegen.
- 2026-06-05 · **OPT-50/51 (v0.99.12, Stufe 2 Robustheit, voller Workflow)** · App-Start-
  Crash-Schutz: `self.save()` in `settings._migrate_bandpilot_settings_v088` in
  `try/except Exception`+print (fail-silent, idempotent) — die einzige crashende Stelle der
  Migration. **OPT-51 war BEREITS erledigt** (preset_store kapselt migrate schon) →
  verify-don't-assume-Win, kein Code. DeepSeek-Plan-R1 FREIGEBEN (4 Punkte). Tests
  2415→**2416** (+1 Mutationsbeweis-Test). Commit `<opt50>`. **Damit beginnt Stufe 2 —
  die flagged OPT-55/58/59 weiterhin NUR nach Mike-Rückmeldung.**
- 2026-06-05 · **OPT-Q1/Q2 aufgelöst (v0.99.11)** · 3 tote Module entfernt nach Mike-
  Entscheid (nicht verlinkt + nicht FT2-relevant → weg): `ap_decoder` + `osd_decoder`
  (rein FT8, PyFT8-LDPC, kein Test) + `diversity_merger` (+ 10er-Test). DeepSeek-R1
  ENTFERNEN FREIGEBEN inkl. Slice-B-Unabhängigkeit (diversity_merger ≠ reservierter
  Dual-RX-Merge-Baustein; flexradio-Slice-B unberührt). README-Dateibaum angepasst,
  PyFT8 bleibt (message.py live). Tests 2425→**2415** (−10). Commit `<bundleE>`.
- 2026-06-05 · **Bundle D (OPT-04)** · 15 f-Strings ohne Platzhalter geglättet (`f`-Präfix
  weg = identische Ausgabe): qso_state(2), qrz_upload_worker, control_panel(5, inkl.
  2-Literal-`debug_log`), mw_radio(4), mw_qso, mw_cycle, flexradio(2). Jede Stelle auf
  fehlende `{{`/`}}` geprüft. **Bewusst SKIP:** qso_detail_overlay:44 + awards_dialog:191
  (CSS-Templates mit escaped `{{` → `f`-Entfernen wäre NICHT identisch; harmlos). Tests
  **2425 grün**, DeepSeek-R1 **FREIGEBEN**. Commit `<bundleD>`. **→ Stufe 1 (toter Code)
  KOMPLETT — Autonomie-Grenze erreicht, STOPP + Mike melden vor Stufe 2.**
- 2026-06-05 · **Bundle C (OPT-02)** · 10 tote lokale Variablen entfernt (pyflakes-
  autoritativ, je rechte Seite als seiteneffektfrei verifiziert → ganze Zeile weg):
  main_window `freq`, control_panel `_SEP_SS`, mw_radio `mw`+`mode`, logbook_widget `t`,
  dx_tune_dialog `ant1_gain`+`ant2_gain`, mw_cycle `qso_busy`, **flexradio `body`**
  (TCP-Response-Parser, KEIN TX/Slice-B), generate_plots `d_rsc` (nur toter DE-Block,
  EN-Block bei Z.1807 nutzt es → unberührt). pyflakes 0 tote Locals mehr, Tests **2425
  grün**, DeepSeek-R1 **FREIGEBEN** (alle RHS reine Getter, kein Seiteneffekt). Commit `<bundleC>`.
- 2026-06-05 · **Bundle B (OPT-01)** · Ungenutzte Imports projektweit entfernt (17
  Dateien): frischer `pyflakes`-Lauf, jeder Treffer gegen Live-Code verifiziert
  (`grep -cnw` = nur Import-Zeile). Inkl. 1 toter `TYPE_CHECKING`-Import
  (`auto_hunt.FT8Message`, 0 Annotation-Nutzung) + 4× tote lokale `import time as _time`
  in mw_radio. **Bewusst BEHALTEN:** `__init__.py`-Re-Exports (öffentliche Paket-API →
  Breaking Change, Mike-Sache) + 4 `TYPE_CHECKING`-MainWindow (Mixin-Typ-Hints, Audit §2c).
  pyflakes-Rest = exakt diese gewollten. Syntax-Check OK, Tests **2425 grün** (unverändert),
  DeepSeek-R1 **FREIGEBEN** (kein String-Annotation/`__all__`/getattr/Seiteneffekt-Import).
  Commit `<bundleB>`.
- 2026-06-05 · **Bundle A (OPT-03/40/41/42/43)** · Toter Code projektweit entfernt:
  6 tote control_panel-Helfer/Signale, 2 direction_map-Paint-Methoden, 2 rx_panel-
  Separator-Methoden + `_MAX_CYCLES`, `qso_panel._slot_tag`, `settings.get_normal_preset`
  (+ dessen Test). Inkl. transitive Orphans (`_SEP_COLOR`, `DISTANCE_RINGS_KM`,
  Import `SECTOR_COUNT`, `_FONT_SEP`, `_COLOR_SEP`). Jedes Symbol vorab gegen ganze
  Live-Codebasis + tests gegrep't (0 Refs). pyflakes sauber, Tests **2426→2425**
  (1 Deprecated-Test mit raus). DeepSeek-R1 **FREIGEBEN** (verhaltensneutral, keine
  dynamische Nutzung, keine transitive Leiche). Commit `<bundleA>`.
  _Notiert für später (NICHT jetzt): `control_panel._tx_freq` ist nach `set_tx_freq`-
  Entfernung konstant `None` → KISS-Inline-Kandidat (Stufe 3). `settings.save_normal_preset`
  ist Zwilling-Stub von `get_normal_preset` → bei OPT-62/K2 mitprüfen._
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
