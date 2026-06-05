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

- 2026-06-05 · Setup · Plan angelegt, v0.99.9 gepusht + Tag `v0.99.9-pre-optimierung`,
  Tests-Basis **2426** grün. **DeepSeek-Review des Plans: voller GO** (Reihenfolge optimal,
  alle Stufe-1-Punkte verhaltensneutral, keine Overengineering-Punkte; OPT-06-Bedingung
  verifiziert; nur OPT-20 braucht neue Decode-Referenztests — schon eingeplant).

---

*Befund-Grundlage: `OPTIMIERUNG_AUDIT.md`. Regeln: Mike 05.06.2026. Dieser Plan ist
verbindlich bis abgearbeitet — bei Compact zuerst hierher zurück.*
