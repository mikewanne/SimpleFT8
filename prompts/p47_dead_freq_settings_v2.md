# P47 — Tote Frequenz-Settings + Statusbar-Filter-Anzeige entfernen (V2)

> **Pflicht-Kopf für DeepSeek-R1-Review:**
>
> Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
> und PySide6 (`Signal` statt `pyqtSignal`, `Slot` statt `pyqtSlot`). Das
> Projekt ist ein Hobby-Funker-Tool für einen einzelnen Operator —
> NICHT Multi-Tenant.
>
> Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem
> lösen. Strukturierte Liste: Lücken, Unklarheiten, Widersprüche,
> Verbesserungen.
>
> KRITISCHE REGELN:
> 1. **SCOPE-RESPEKT:** Was explizit als out-of-scope markiert ist NICHT
>    als Finding melden.
> 2. **KISS VOR DEFENSIV:** Komplexität nur wenn Wahrscheinlichkeit > 50 %.
> 3. **PROJEKT-BEZUG:** Jedes Finding am konkreten Use-Case messen.
> 4. **FORMAT:** Tabelle `Schwere | Finding | Datei:Zeile | Empfehlung`.
>    Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) /
>    Hinweis (grau).
>
> Overengineering ist selbst ein Fehler den du benennen sollst.

---

## Ziel

Zwei wirkungslose Frequenz-Settings (`audio_freq_hz` als TX-Default und
`max_decode_freq` als Decoder-Obergrenze) sowie die irreführende
Statusbar-Filter-Anzeige (`Filter: 100-3100 Hz`) ehrlich aus UI,
Settings und Anzeige entfernen. Defaults wandern als Konstanten in die
Code-Pfade, die sie heute aus den Settings lesen. Alte JSON-Configs
mit diesen Keys werden idempotent gesäubert.

**Hintergrund (Konsens Mike + Claude + R1 13.05.2026):**

- `audio_freq_hz` (TX Audio-Frequenz, Default 1500 Hz, UI-Range 800–2800)
  wird nur als Startwert für `Encoder.__init__` genutzt — der
  CQ-Such-Algorithmus überschreibt `encoder.audio_freq_hz` dynamisch
  bei jedem Slot. Zusätzlicher Lese-Ort: `Settings.get_normal_tx_freq`
  (`config/settings.py:225`) als Fallback wenn `normal_tx_freq_per_band`
  für ein Band leer ist.
- `max_decode_freq` (Default 3000 Hz, UI-Range 1000–5000) wird nur
  einmal beim App-Start an `Decoder(max_freq=...)` gegeben.
  **`decoder.max_freq` wird nirgends im Code neu gesetzt** —
  Code-Verifikation 13.05.: `grep '\.max_freq\s*='` über das gesamte
  Repo ergab genau einen Treffer: `core/decoder.py:73` im Init. Eine
  User-Eingabe wirkt also nur bis zum nächsten App-Neustart.
- Die Statusbar-Anzeige
  `_FILTERS = {"FT8":"100-3100", "FT4":"100-3100", "FT2":"100-4000"}`
  ist **aktiv irreführend**: Für FT2 zeigt sie 100–4000 Hz, der Decoder
  läuft aber faktisch auf 3000 Hz (Default bleibt unverändert beim
  Modus-Wechsel).

R1-Originalton: „Tote Settings sind toter Code und verletzen das
Prinzip der geringsten Überraschung. Steuerbarkeit vortäuschen, die
nicht existiert."

## Akzeptanzkriterien

**AK1 — Settings-Keys + Properties weg.** `audio_freq_hz` und
`max_decode_freq` aus `DEFAULTS` (`config/settings.py:60-61`) und aus
den `@property`-Wrappern (`config/settings.py:170-175`) entfernt.

**AK2 — Idempotente Säuberung alter Configs.** In `Settings.load()`
nach `self._data.update(saved)` zwei zusätzliche Pops:

```python
# P47: tote Frequenz-Keys aus alten Configs schmeißen (v0.97.11+)
self._data.pop("audio_freq_hz", None)
self._data.pop("max_decode_freq", None)
```

→ Eingebaut **vor** `_migrate_bandpilot_settings_v088()` damit die
Migrationsroutine selbst nicht mit den Keys interagieren kann. Idempotent
(zweiter Lauf no-op). Save passiert anschließend beim nächsten regulären
`save()`-Aufruf — kein Auto-Save in `load()` nötig (KISS).

**AK3 — UI-Felder weg.** TX Audio-Frequenz-Spinbox und
Max. Decode-Frequenz-Spinbox aus `ui/settings_dialog.py` Tab „FT8 &
Diversity" entfernt, inklusive:

- Hint-Strings `tx_freq` und `max_decode` im `_HINTS`-Dict
  (`ui/settings_dialog.py:29-30`).
- QSpinBox-Init `self.audio_freq` und `self.max_decode_freq`
  (Z.285–293) inkl. `form.addRow(...)`-Aufrufe.
- Load-Pfade `self.audio_freq.setValue(...)` und
  `self.max_decode_freq.setValue(...)` (Z.506–507).
- Save-Pfade `self.settings.set("audio_freq_hz", ...)` und
  `self.settings.set("max_decode_freq", ...)` (Z.646–647).
- Reset-Default-Pfade (Z.693–694).

**AK4 — Statusbar-Filter-Anzeige weg.** Aus `_update_statusbar()` in
`ui/main_window.py`:

- `_FILTERS`-Dict + `filter_str`-Berechnung (Z.1107–1109) weg.
- `Filter: {filter_str} Hz  |  ` aus dem zentralen `msg`-String
  entfernen (Z.1147).

Reihenfolge der verbleibenden Segmente bleibt identisch
(Callsign | Locator | Mode Band | freq_display | mode_str + omni_str +
freq_str + ap_str).

**AK5 — Konstanten statt Settings-Lookup an den 3 betroffenen Stellen.**

- `ui/main_window.py:144` — `Encoder(settings.audio_freq_hz)` →
  `Encoder(1500)`.
- `ui/main_window.py:145` — `Decoder(max_freq=settings.max_decode_freq)`
  → `Decoder(max_freq=3000)`.
- `config/settings.py:225` — `get_normal_tx_freq` Fallback
  `self._data.get("audio_freq_hz", 1500)` → einfach `1500`.

**AK6 — Tests werden angepasst, nicht stehengelassen.**

- `tests/test_settings_dialog_smoke.py:32-33` — Keys `audio_freq_hz` +
  `max_decode_freq` aus `_FakeSettings._d` entfernen.
- `tests/test_settings_dialog_smoke.py:60-62` — `@property
  max_decode_freq` auf Mock entfernen.
- `tests/test_settings_dialog_smoke.py:97` — `"audio_freq",
  "max_decode_freq"` aus `expected_attrs` entfernen.
- `tests/test_modules.py:2073` und `tests/test_modules.py:2083` —
  `s._data = {"audio_freq_hz": 1500}` zu `s._data = {}` ändern. Tests
  verifizieren weiterhin Default 1500 (jetzt hartkodiert).

**AK7 — Neue Tests (`tests/test_p47_dead_freq_settings.py`).**

- **T1 — `test_settings_load_drops_dead_keys`:** Settings-Objekt mit
  vorab präparierter `config.json` (tmp-Dir) die `audio_freq_hz=1700`
  und `max_decode_freq=4500` enthält → nach `Settings()` sind beide
  Keys nicht mehr in `_data`.
- **T2 — `test_settings_no_audio_freq_property`:** Frische
  `Settings()`-Instanz hat keine `audio_freq_hz`- und keine
  `max_decode_freq`-Property mehr (AttributeError beim Zugriff).
- **T3 — `test_get_normal_tx_freq_fallback_constant`:** ohne
  per-Band-Eintrag liefert `get_normal_tx_freq("20m")` weiterhin 1500
  (jetzt aus Konstante).
- **T4 — `test_statusbar_no_filter_segment`:** QApplication-Fixture +
  MainWindow-Smoke (analog P44-Pattern), nach `_update_statusbar()`
  enthält `statusBar().currentMessage()` weder `"Filter:"` noch
  `"100-3100"` noch `"100-4000"`.

**AK8 — Gesamtsuite bleibt grün.** Erwartung: 1162 → ~1166 Tests
(+4 neu, ~5 angepasst). Run mit `QT_QPA_PLATFORM=offscreen
./venv/bin/python3 -m pytest tests/ -q`.

## Bewusste Verhaltensänderung (klein, dokumentiert)

`Settings.get_normal_tx_freq(band)` lieferte bisher für unbekannte
Bänder einen vom User über die Settings-Dialog-Spinbox einstellbaren
Wert (Range 800–2800 Hz). Künftig immer 1500 Hz. Wirkung: minimal —
1500 ist der WSJT-X-Default-Wert. Wer 1300 oder 1700 individuell
eingestellt hatte, bekommt jetzt bei neuen Bändern (ohne
per-Band-Eintrag) 1500. Bereits per Klick im Histogramm gesetzte
Per-Band-Werte (`normal_tx_freq_per_band`) bleiben weiterhin gültig.

## Betroffene Module/Dateien (Zusammenfassung)

| Datei | Zeile(n) | Was |
|---|---|---|
| `config/settings.py` | 60, 61 | DEFAULTS-Keys raus |
| `config/settings.py` | 170–175 | Properties `audio_freq_hz`, `max_decode_freq` raus |
| `config/settings.py` | 99/102 | In `load()` nach `update(saved)` zwei `pop()`-Zeilen (vor `_migrate_bandpilot…`) |
| `config/settings.py` | 225 | Fallback → `1500` (Konstante) |
| `ui/settings_dialog.py` | 29, 30 | Hint-Strings raus |
| `ui/settings_dialog.py` | 285–293 | Spinbox-Init + Form-Rows raus |
| `ui/settings_dialog.py` | 506, 507 | Load-Pfad raus |
| `ui/settings_dialog.py` | 646, 647 | Save-Pfad raus |
| `ui/settings_dialog.py` | 693, 694 | Reset-Pfad raus |
| `ui/main_window.py` | 144 | `Encoder(1500)` |
| `ui/main_window.py` | 145 | `Decoder(max_freq=3000)` |
| `ui/main_window.py` | 1107–1109 | `_FILTERS` + `filter_str` raus |
| `ui/main_window.py` | 1147 | `Filter:`-Segment raus |
| `tests/test_settings_dialog_smoke.py` | 32–33, 60–62, 97 | Stub + expected_attrs anpassen |
| `tests/test_modules.py` | 2073, 2083 | `_data = {}` statt mit toter Key |
| `tests/test_p47_dead_freq_settings.py` | NEU | T1–T4 |

## Randbedingungen

- **KISS:** Keine Helper-Funktionen, keine `DEFAULT_AUDIO_HZ`-Konstante,
  keine Migrationsklasse. Direktes Pop in `load()`, drei `1500` + ein
  `3000` hartcodiert. Drei ähnliche Zeilen > eine verfrühte
  Abstraktion (Mike-Programmierleitsatz #1).
- **Hardware-Pflicht ANT1=TX bleibt unberührt.** Kein TX-Pfad-Eingriff.
- **Single-Operator-Tool.** Keine Multi-Profile-Migrations-Strategie nötig.
- **Hobby-Tool-Philosophie:** Ehrliche UI > täuschende Eingabefelder.
- **Encoder-Default-Wert `1000` in `core/encoder.py:49`** bleibt
  unverändert (wird in vielen Test-Helpers explizit auf 1500 gesetzt;
  Klassen-Default ist nicht relevant für App-Pfad).
- **Decoder-Default-Wert `3000` in `core/decoder.py:70`** bleibt
  unverändert (deckt sich mit dem neuen `main_window.py:145`).
- **Idempotenz:** Zweiter `Settings()`-Aufruf läuft schmerzfrei durch
  ohne die Keys nochmal popen zu müssen (Dict-Pop ist No-op bei
  fehlendem Key).

## Nicht im Scope

- `audio_freq_hz_for_band` (existiert nicht — nur ähnlich benannt:
  `get_normal_tx_freq` mit Band-Argument). Per-Band-TX-Frequenz für
  Normal-Modus bleibt voll erhalten.
- Encoder-Klasse Default-Wert in `core/encoder.py` (`audio_freq_hz:
  int = 1000`) bleibt.
- Decoder-Klasse Default-Wert in `core/decoder.py` (`max_freq:
  int = 3000`) bleibt.
- AP-Lite, OMNI-CQ, Diversity, CQ-Algorithmus, TUNE_FREQS,
  Per-Band-Frequenz-Speicherung: alle unberührt.
- Kein UI-Redesign vom FT8-Tab — nur die 2 Form-Rows raus, Rest des
  Tabs bleibt wie er war.
- Keine Umbenennung des Tabs.
- Keine zentrale `DEFAULT_AUDIO_HZ`-Konstante.
- Keine Verhaltensänderung an `encoder.audio_freq_hz` während
  laufendem Betrieb (CQ-Algorithmus überschreibt weiterhin).

## Testbarkeit (Detail)

- **T1:** tmp-Config-File mit toten Keys → nach `Settings()` weg.
  Setup via Monkey-Patch von `CONFIG_FILE` oder Settings-Subclass.
- **T2:** `hasattr(Settings(), "audio_freq_hz") is False`.
  Property-Check direkt.
- **T3:** Settings-Instanz mit `_data = {}` (oder per Init) →
  `get_normal_tx_freq("20m") == 1500`.
- **T4:** MainWindow-Smoke mit QApplication-Fixture (analog P44), nach
  `_update_statusbar()` Assert
  `"Filter:" not in win.statusBar().currentMessage()`.

Suite-Erwartung: **1162 → ~1166** (4 neu).

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `config/settings.py` — DEFAULTS + Properties + load-Pop +
   `get_normal_tx_freq`-Fallback.
2. **C2** `ui/settings_dialog.py` — Hints + UI-Felder + Load/Save/Reset.
3. **C3** `ui/main_window.py` — Encoder/Decoder-Init + Statusbar-Filter.
4. **C4** `tests/test_settings_dialog_smoke.py` + `tests/test_modules.py`
   — Stub-Settings, expected_attrs, normal_tx_freq-Tests.
5. **C5** `tests/test_p47_dead_freq_settings.py` (NEU) — T1–T4.
6. **C6** APP_VERSION 0.97.10 → 0.97.11 in `main.py` + `HISTORY.md` +
   `HANDOFF.md` + `CLAUDE.md`-Header + `TODO.md` Punkt erledigt.

Atomares Backup vor C1: `Appsicherungen/2026-05-13_v0.97.10_vor_p47_dead_freq_settings/`
mit den 3 betroffenen Files (`config/settings.py`, `ui/settings_dialog.py`,
`ui/main_window.py`).

## Risiko

**LOW.** Beide Settings sind faktisch wirkungslos (CQ-Algo
überschreibt TX-Freq, Decoder-Max wird nie geändert). Statusbar-Anzeige
war irreführend, ihre Entfernung macht das Tool ehrlicher. Keine
bestehende Diversity-/CQ-/QSO-/OMNI-Logik wird berührt. Save-Pfad nicht
geändert (`Settings.save()` bleibt wie er war — Pop in `load()` reicht
für Bereinigung).

**Mini-Verhaltensänderung in `get_normal_tx_freq` für Bands ohne
Per-Band-Eintrag** (1500 Hz statt User-Wert) ist dokumentiert; Mike als
einziger Operator hat den Default-Wert nach allen verfügbaren
Hinweisen (UI-Default 1500 = WSJT-X-Default) ohnehin nicht verändert.
