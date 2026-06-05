# Optimierungs-Audit SimpleFT8 — 05.06.2026

**Auftrag (Mike):** Code auf **Vereinfachung, Geschwindigkeit, toten Code** durchsuchen
(Claude + DeepSeek), Bericht mit Optimierungspotenzial. **Es wurde kein Code geändert** —
dies ist reiner Befund. Du entscheidest, was umgesetzt wird (dann jeweils voller Workflow).

**Methodik:** `pyflakes` + `vulture` (statisch, in den venv installiert, von der App nicht
importiert) → jeder Tote-Code-Kandidat **gegen die gesamte Live-Codebasis + Tests
verifiziert** (Backup-Kopien in `Appsicherungen/` bewusst ausgeschlossen — sie hätten jede
Funktion fälschlich als „benutzt" gezeigt). Dazu **2 DeepSeek-v4-pro-Reviews** (Hot-Path-
Geschwindigkeit + Vereinfachung), deren Funde gegen den echten Code gegengeprüft wurden.

**Codebasis:** 34.437 Zeilen App-Code (ohne Tests/ft8_lib). Größte Dateien:
`mw_radio.py` 2462 · `control_panel.py` 2388 · `generate_plots.py` 2019 · `main_window.py`
1819 · `direction_map_widget.py` 1777 · `flexradio.py` 1534.

---

## 🎯 Kurzfassung — Top-Empfehlung

1. **Quick-Win-Bündel (1 Sitzung, S-Aufwand, null Verhaltensrisiko):** tote Imports/
   lokale Variablen/tote UI-Helfer raus **+** 5 kleine Hot-Path-Konstanten (Slot-Dict,
   hanning-Fenster, Filter-Taps, lokaler Import, Pro-Offset-Cast). Sofort übersichtlicher
   **und** spürbar weniger Allokation pro Slot auf dem 2015er-iMac.
2. **Mittel (eigener Workflow, mit Decode-Referenztests):** Float↔Int-Pipeline im Decoder
   entzerren (größter Geschwindigkeits-Hebel) **+** Empfangskontext-Reset zentralisieren
   (entschärft zugleich die Bug-Klasse „Wechsel vergisst Reset", §11).
3. **Mit dir klären:** ob `ap_decoder.py`/`osd_decoder.py`/`diversity_merger.py` reservierte
   Zukunfts-Features sind oder weg können (sie sind nirgends verdrahtet).

---

## 1. Geschwindigkeit (Decoder-Hot-Path) — DeepSeek + verifiziert

Der Decoder läuft 1×/Slot (FT8 15 s / FT4 7,5 s / FT2 3,8 s) unter enger Frist im eigenen
Thread. Alle Funde **am echten Code bestätigt** (Zeilen geprüft).

| # | Datei:Zeile | Fund | Fix | Aufwand | Risiko |
|---|---|---|---|---|---|
| **S1** | `decoder.py` (12× `astype`, u.a. 322/334/498/507/668/722) | Audio-Array wird mehrfach zwischen `int16`↔`float32` gewandelt (je ~360 kB Kopie); in der Subtraktionsschleife 3 Offsets × bis 5 Pässe = bis 15 Extra-Konvertierungen | Audio **einmal** als `float32` halten, erst unmittelbar vor dem C-Decode auf `int16` casten | **M** | mittel (C-API erwartet int16 → Decode-Referenztests nötig) |
| **S2** | `decoder.py:360` | `from core import ntp_time` **lokal in `_process_cycle`** (pro Slot) | Top-Level-Import (wie `timing.py` es schon macht) | **S** | niedrig |
| **S3** | `decoder.py:679` + `:724-730` | `np.hanning(2048)` und die 63 Filter-Taps werden **jeden Slot neu** berechnet, obwohl audio-unabhängig konstant | als Modul-Konstanten `_PREPROC_WINDOW` / `_RESAMP_TAPS_24K` vorberechnen | **S** | niedrig |
| **S4** | `decoder.py:229` | `{"FT8":15.0,"FT4":7.5,"FT2":3.8}.get(...)` **als Literal im Scheduling-Loop** neu erzeugt | Modul-Konstante `_SLOT_LENGTHS` | **S** | niedrig |
| **S5** | `decoder.py:507` | Pro Offset (3×) `shifted.astype(np.int16)` in der Subtraktionsschleife | 1× `int16`-Kopie pro Pass statt pro Offset (3×→1×) | **S** | niedrig |
| **S6** | `decoder.py:_preprocess_audio` | `target_rms = 32767*10**(-18/20)` pro Aufruf neu | Modul-Konstante `TARGET_RMS` | **S** | niedrig |
| **S7** | `decoder.py:_decode_with_subtraction` | Dedup-Key `" ".join(msg.split())` wird **doppelt** berechnet (Dedup + new_msgs) | einmal in `r['_key']` cachen | **S** | niedrig |
| **S8** | `diversity.py:get_free_cq_freq` | Median durch Voll-Expansion aller Frequenzen in eine Liste | Median direkt kumulativ aus dem Histogramm | **S** | niedrig (Aufruf nur ~60 s → kleine Prio) |
| **S9** | `encoder.py` | Slot-Dauer-Dict `{"FT8":15.0,…}` pro Aufruf neu erstellt | `self._slot_dur` 1× in `set_protocol()` setzen | **S** | niedrig |
| **S10** | `decoder.py:_apply_offset` | `np.pad` allokiert pro Offset ein neues ~180k-Array (3×/Pass) | vorallokiertes Array + Slicing | **M** | niedrig |
| S11 | `decoder.py:feed_audio` | jedes RX-Audio-Paket wird kopiert (mehrmals/s) | Zero-Copy nur mit Architektur-Umbau | **L** | hoch — **DeepSeek selbst: kaum lohnend, lassen** |

**Mein Urteil:** S2–S6 + S9 sind die idealen Quick-Wins (alle S, risikolos, je 1-3 Zeilen,
zusammen messbar weniger Pro-Slot-Last). **S1** ist der eigentliche große Hebel, aber als
eigener Workflow mit Decode-Referenztests (Verhaltensgarantie). S11 **nicht** anfassen.

---

## 2. Toter Code

### 2a · Sofort sicher entfernbar (S, kein Risiko)

**Tote UI-Helfer in `control_panel.py`** (0 Live-Referenzen, von DeepSeek bestätigt):
`set_tx_freq` (~Z.100, `_tx_freq` bleibt immer `None`), `_group_label` (Z.1618),
`_separator` (Z.1627 — die echte Trennlinie ist `_sep_line`), `_band_btn` (Z.1635),
`_toggle_btn` (Z.1654), `_on_tx_level_changed` (Z.2101) **+ die nie emittierten Signale**
`tx_level_changed` und `preamp_changed` (Legacy).

**Ungenutzte Imports** (pyflakes, 0 Verwendung):
- `control_panel.py`: `QSlider`, `_BTN_BASE`, `_CARD_SS`, `_DIV_PCT_YELLOW`
- `settings_dialog.py`: `QTableWidget(Item)`, `QHeaderView`, `QDoubleSpinBox`, `time`,
  `DEFAULTS`, `BAND_FREQUENCIES` (+ doppelt definiert Z.16/323)
- `qso_panel.py`: `QTextEdit`, `Path` · `qso_detail_overlay.py`: `QPixmap`, `QFont`, `Qt`,
  `QTextEdit` · `rx_panel.py`: `QSizePolicy` · `help_dialog.py`: `Qt` ·
  `propagation.py`: `Tuple` · `mw_tx.py:469`: lokaler `QMessageBox` · `mw_qso.py`: `Path`
  (+ doppelt Z.6/982)

**Tote lokale Variablen** (zugewiesen, nie benutzt): `mw_radio.py` (`mw`@743, `mode`@1427,
`sst`/`te`@119, 3× `time as _time`@661/894/1845/2260), `mw_cycle.py` (`qso_busy`@392),
`main_window.py` (`freq`@1412), `dx_tune_dialog.py` (`ant2_gain`@695),
`logbook_widget.py` (`t`@46), `control_panel.py` (mehrere @1918/1932/1936/2152),
diverse `kwargs`/`pcm_data` in Radio-Stubs (gehören zur Signatur → nur die echten Stubs
betreffend, siehe 2c).

**f-Strings ohne Platzhalter** (Code-Geruch, harmlos): `mw_radio.py` 2220/2287/2293,
`mw_qso.py:236`, `mw_cycle.py:694`, `qso_detail_overlay.py:45`.

→ **Schätzung: ~150-200 Zeilen weg, reine Aufräumung, null Verhaltensänderung.**

### 2b · Mit dir klären (möglicherweise reserviert — NICHT eigenmächtig löschen)

| Modul | Status | Frage |
|---|---|---|
| `core/ap_decoder.py` (`try_ap_decode`) | **nirgends importiert** | AP = „a-priori"-Decoding (WSJT-X-Technik). Reserviert für Decode-Verbesserung oder weg? |
| `core/osd_decoder.py` (`try_osd_decode`) | **nirgends importiert** | OSD = „ordered statistics decoding". Gleiche Frage. |
| `core/diversity_merger.py` (`DiversityMerger`, `on_decoder_a/b_done`) | **nur in Tests** | Dual-Decoder-Merge (A+B) — Multiband-/Dual-RX-Reserve wie Slice-B, oder veraltet? |
| `direction_map_widget.py` (`_quat_from_axis_angle`, `_quat_mul`, `_quat_rotate`, `_paint_user_distance_rings`, `_paint_user_sector_lines`) | 0 Live-Refs | Reste einer alten 3D-Globus-Rotation? Prüfen, ob durch neue Render-Logik ersetzt. |
| diverse Einzel-Helfer (`mw_radio._show_info_once`/`_bandpilot_label`/`_start_tune_only`/`_apply_dx_preset_for_band`, `qso_panel._slot_tag`, `rx_panel.add_cycle_separator`/`_populate_separator_row`, `encoder.find_free_frequency`, `timing.seconds_until_next_cycle`, `debug_log.is_enabled`) | 0 Live-Refs | je einzeln prüfen — manche sind evtl. „mal gebraucht", manche echte Leichen |
| Nur-in-Tests-API (`settings.get_dx_preset`/`save_dx_preset`/`get_gain_preset`, `qso_log.is_worked_on_band`, `protocol.get_profile`, `ntp_time.get_status_text`, `preset_store.has_staged`, `locator_db.bulk_import_adif`/`average_precision_km`, `antenna_pref.get_delta_db`) | App-tot, Test deckt ab | meist **behalten** (öffentliche/symmetrische API) — kein Handlungsbedarf |

### 2c · KEIN toter Code (Fehlalarm der Tools — zur Klarstellung)

- **Qt-Event-Overrides** (`wheelEvent`, `mousePressEvent`, `paintEvent`, `closeEvent`,
  alle `noqa: N802`) — werden vom Framework gerufen, nicht im Code.
- **Slice-B-/Multiband-Reserve in `flexradio.py`** (`enable_diversity`, `disable_diversity`,
  `_build_vita49_packet`, `_create_stream`, `_cleanup_extra_slices`, `dx_reset`,
  `set_preamp`) — **bewusst reserviert (Mike-Spec), bleibt.**
- **Icom-Stubs** `ic7100.py`/`ic7300.py` (`kwargs`/`pcm_data`) — Fork-Reserve.
- **`base_radio.py` ABC-Methoden** — Interface, in Subklassen überschrieben.
- **`MainWindow`-Imports unter `if TYPE_CHECKING`** — für Typ-Hints, kein toter Import.

---

## 3. Vereinfachung

### 3a · Echte Duplikation → zu Helfer zusammenfassen

| Stelle | Was | Vorschlag | Aufwand | Risiko |
|---|---|---|---|---|
| `mw_radio.py` `_on_band_changed` / `_on_mode_changed` / `_on_rx_panel_toggled` | **Empfangskontext-Reset** (RX-Liste, Stations-Dicts, QSO-Panel, Counter) fast identisch kopiert | `_reset_reception_context()` extrahieren, an 3 Stellen rufen | **M** | gering |
| `control_panel.py` `_setup_ui` | 3 Karten-**Kollaps-Toggle-Buttons** (20×20, flach) identisch bis auf Farbe/Tooltip | `_make_collapse_toggle(color, hover, tooltip, slot)` | **M** | gering |

> **Bonus bei der ersten:** Genau diese kopierte Reset-/Abbruch-Logik war die Quelle der
> Bug-Klasse „Wechsel vergisst Reset/Abbruch" (zuletzt v0.98.64 FT-Modus-Wechsel). Eine
> zentrale Methode entschärft die Klasse strukturell. **Klare Empfehlung: machen.**

### 3b · Zu komplexe Methoden (Top 5, ohne Verhaltensänderung entflechtbar)

| Methode | Länge | Vorschlag | Aufwand |
|---|---|---|---|
| `control_panel._setup_ui` | ~180 Z. | in `_create_*_card()` je Karte aufteilen | M |
| `mw_radio._on_band_changed` | >130 Z. | Phasen: stop → reset → apply → auto-tune/diversity | L |
| `mw_radio._on_mode_changed` | ~100 Z. | gleichen Phasen-Helfer nutzen | L |
| `control_panel._RadioCard.__init__` | ~120 Z. | `_create_psk/_power_row/_tx_section` | M |
| `control_panel._AntenneCard.__init__` | ~100 Z. | Diversity-Ratio / Histogramm / TX-Freq trennen | M |

→ **Empfehlung: nur anfassen, wenn wir ohnehin in der Datei arbeiten** — nicht um ihrer
selbst willen (KISS). Reine Lesbarkeit, kein Funktions-Gewinn.

### 3c · Style-Strings konsolidieren (S, kein Risiko)

In `control_panel.py` wiederholen sich Inline-Styles fast identisch (nur Farbe variiert):
Karten-Header-Labels, Kollaps-Toggle-Buttons, Modus-Button-Styles (`_mode_btn_style`/
`_omni_btn_style`), Progressbar-Styles (Presence/CQ). → kleine Helfer in `ui/styles.py`
(`header_label_style(color)`, `bar_style(color)` …). Reduziert Wiederholung, erleichtert
Theme-Änderungen.

---

## 4. Priorisierte Roadmap

**Stufe 1 — Quick-Wins (1 Sitzung, S, risikolos):**
2a (tote Imports/Locals/Helfer/Signale) + Speed S2,S3,S4,S5,S6,S9 + 3c (Style-Helfer).
→ ~200 Zeilen weniger, spürbar weniger Pro-Slot-Allokation, null Verhaltensrisiko.

**Stufe 2 — echter Gewinn (je eigener Workflow):**
- Speed **S1** (Float/Int-Pipeline) — größter Geschwindigkeits-Hebel, mit Decode-Referenztests.
- **3a** Empfangskontext-Reset zentralisieren — Wartbarkeit **+** Bug-Klasse §11.

**Stufe 3 — langfristig, opportunistisch:**
3b große Methoden entflechten (nur wenn wir eh dran sind). + S10 (`_apply_offset`).

**Vor Stufe 1/2 zu klären:** 2b — sind AP/OSD/DiversityMerger reservierte Zukunft oder Müll?

---

# TEIL 2 — Ganze App, Brille KISS / Lesbarkeit / Robustheit (Mike-Priorität 05.06.)

> 3 weitere DeepSeek-Reviews (GUI/Globus/Listen · Speichern/Laden · Orchestrierung) +
> eigene Robustheits-Stichprobe. **Jeder Fund gegen den echten Code verifiziert** —
> Status: ✅ bestätigt · ⚠️ vor Fix verifizieren · ❌ Fehlalarm (raus).
> **Priorität laut Mike: Robustheit + KISS > Geschwindigkeit.**

## A · ROBUSTHEIT (höchster Wert)

| # | Datei | Fund | Status | Fix | Aufw./Risiko |
|---|---|---|---|---|---|
| R1 | `main_window.py:1271` | **PSK-Worker ruft `control_panel.update_psk_stats()` direkt aus Hintergrund-Thread** (Z.1224 startet Thread) — Qt-Widgets sind nicht thread-safe → undefiniert, Crash-Gefahr | ✅ bestätigt | GUI-Update per Qt-Signal an Main-Thread (wie `direction_map_signal`) | M / **hoch ohne Fix** |
| R2 | `config/settings.py:161` | **`load()` ruft Migration ungeschützt**, Migration ruft `save()` (Z.185) → Plattenfehler = **Crash beim App-Start** | ✅ bestätigt | `try/except` um Migration; bei Fehler nur `print`, App startet weiter | S / niedrig |
| R3 | `core/preset_store.py` `__init__` | `migrate_legacy_files()` ungeschützt → Plattenfehler crasht PresetStore-Init = App-Start | ⚠️ Muster wie R2 | `try/except` analog | S / niedrig |
| R4 | `config/settings.py:115` `load()` | **Keine Typ-Validierung** der geladenen JSON — korruptes `callsign`/`locator` (z.B. `null`) wandert still in die Settings → später TypeError/stille Fehler | ✅ Muster bestätigt | kritische Felder nach `update` per `isinstance` gegen Default prüfen | M / niedrig |
| R5 | App-weit | **~60 stille `except …: pass`** — manche berechtigt (Debug-Log darf nie crashen), aber pauschal verstecken sie echte Fehler | ✅ gezählt (eigener Fund) | durchgehen, riskante auf konkrete Exception einengen + `print` | M / niedrig |
| R6 | `core/ntp_time.py:188` | DT-Wert wird **nicht atomar** geschrieben (`write_text`); dasselbe atomare Muster ist in 5 Stores per Copy-Paste, einer (ntp_time) hat's vergessen | ✅ bestätigt (eigener Fund) | **gemeinsamer `atomic_write_json`-Helfer** (DRY **+** schließt Lücke) | S / niedrig |
| R7 | `log/adif.py` Record-Write | **CALL ohne `.upper()`** + RST nicht validiert → QRZ/LoTW können Datensätze **still abweisen** | ⚠️ vor Fix verifizieren | `call.upper()` + RST-Format prüfen | S / niedrig |
| R8 | `main_window.py` `closeEvent` | (a) `dx_tuning`-Modus beim Schließen nicht zurückgesetzt; (b) broad `except: pass` um `audio_monitor.stop()` | ⚠️ plausibel | `elif dx_tuning`-Branch + Exception eingrenzen | S / niedrig |
| R9 | `core/station_stats.py` | Writer-Thread hat **keinen sauberen Stop** (kein `Event`) → unvollständige Statistik bei abruptem Schließen | ✅ Muster | `threading.Event` + `shutdown()` | S / sehr niedrig |
| R10 | `mw_qso.py:429` `_execute_full_halt` | **leert `_p158_insertable` NICHT** (in `_on_cancel` schon, Z.198/1149) → nach STOPP evtl. veraltete klickbare Einschub-Zeilen | ✅ Lücke bestätigt, ⚠️ Severity prüfen | ggf. `_p158_insertable.clear()` ergänzen | S / niedrig |
| R11 | `mw_cycle.py:1139` `_p94_quick73_filter` | sendet 73 evtl. ohne `_abort_active_tx`-Schutz | ⚠️ **TX-Pfad — sehr genau verifizieren** | erst lesen, dann ggf. abort davor | S / **TX → vorsichtig** |

> **R1, R2, R7, R10, R11 sind die heißesten** — R1 (Thread) + R2 (Start-Crash) sind echte
> Robustheits-Löcher; R7 betrifft deine QRZ-Uploads; R10/R11 sind Zufallsfund-Bug-Verdacht
> (laut deiner Regel zu fixen — aber R11 ist TX-Pfad, da prüfe ich dreifach).

## B · KISS / LESBARKEIT

| # | Datei | Fund | Status | Vorschlag | Aufw. |
|---|---|---|---|---|---|
| K1 | `mw_cycle.py`/`mw_qso.py` u.a. | **„aktives QSO?"-Tupel `(IDLE,TIMEOUT,CQ_CALLING,CQ_WAIT)` 11× kopiert** | ✅ 11 Vorkommen | Property `qso_sm.is_busy` — eine Quelle (KISS **+** robust gegen neue States) | S |
| K2 | `config/settings.py` | **3 fast gleiche Preset-Zugriffe** (`get_dx_preset`/`get_gain_preset`/`get_normal_preset` + getrennte Keys) verwirren | ✅ | vereinheitlichen / veraltete Pfade raus | M |
| K3 | `direction_map_widget.py` | Locator-Auflösung (DB→Fallback→lat/lon→Genauigkeit) in 2 Methoden dupliziert | ✅ | Helfer `_resolve_station_position()` | S-M |
| K4 | `config/settings.py` | `get_enabled_bands`/`set_enabled_bands` Band-Validierung dupliziert | ✅ | privater `_valid_bands(raw)` | S |
| K5 | `main_window.py` `_update_statusbar` | ~80 Z., mischt Freq/Modus/OMNI/DT/Smart-Antenne | ✅ | in `_build_status_*`-Teile zerlegen | M |
| K6 | `mw_cycle.py:388` `_handle_diversity_operate` | ~80 Z., Statistik+Score+UI vermischt | ✅ existiert | Berechnung auslagern, Methode = Orchestrator | S-M |

## C · TOTER CODE (projektweit verifiziert = 0 Aufrufe)

✅ **Sicher entfernbar:** `direction_map_widget.py` (Import `azimuthal_equidistant_project`,
Methoden `_paint_user_distance_rings`, `_paint_user_sector_lines`) · `rx_panel.py`
(`_MAX_CYCLES`, `add_cycle_separator`, `_populate_separator_row`) · `qso_panel.py`
(`_slot_tag`) · `config/settings.py` (`get_normal_preset` = deprecated-Stub gibt `{}`) ·
`main_window.py` (tote `freq`-Zuweisung in `_update_statusbar`).

❌ **Fehlalarm korrigiert:** `entries_to_station_points` ist **NICHT tot** — wird in
`main_window.py:1680` genutzt (war nur nicht in den Review-Dateien sichtbar). **Bleibt.**

## D · POSITIV (vorbildlich — nicht anfassen)

`core/rf_preset_store.py` (atomar, Plausi-Checks, Auto-Backup), `core/locator_db.py`
(sauberer RLock, kopierte Einträge, atomar), `core/preset_store.py` (Stage/Commit-Pattern,
atomar — außer R3-Migration), `config/settings.py:save()` (atomar), `ui/logbook_widget.py`
(sauber). DeepSeek hat hier ehrlich „keine Funde" gesagt.

---

## Anhang — Tooling

- `pyflakes` + `vulture` wurden für die Analyse in den venv installiert (von der App nicht
  importiert). Entfernen optional: `./venv/bin/pip uninstall vulture pyflakes`.
- Re-Run: `./venv/bin/vulture core ui radio config log scripts --min-confidence 60`
  und `./venv/bin/python3 -m pyflakes core ui radio config log scripts`.
- DeepSeek-Prompts als Audit-Trail: `prompts/audit_speed.md`, `prompts/audit_simplify.md`.

*Erstellt 05.06.2026 (Claude + DeepSeek-v4-pro). Kein Code geändert — reiner Befund.*
