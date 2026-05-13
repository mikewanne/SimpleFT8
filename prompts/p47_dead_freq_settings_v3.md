# P47 — Tote Frequenz-Settings + Statusbar-Filter-Anzeige entfernen (V3)

> **R1-Findings eingearbeitet:** 5 angenommen (Verhaltensänderung
> `max_decode_freq` explizit, P44-Pattern für T4 ausgeführt,
> R1-Zitat-Quelle ergänzt, Funktionsanker zusätzlich zu Zeilen,
> AK6-Klarstellung). 3 abgelehnt mit Begründung (set_band-Risiko durch
> Code-Verifikation entkräftet, Mike-Wert-Spekulation = KISS-Konflikt,
> Auto-Save in load() = unnötige Komplexität).

---

## Ziel

Zwei wirkungslose Frequenz-Settings (`audio_freq_hz` als TX-Default,
`max_decode_freq` als Decoder-Obergrenze) sowie die irreführende
Statusbar-Filter-Anzeige (`Filter: 100-3100 Hz`) ehrlich aus UI,
Settings und Anzeige entfernen. Defaults wandern als Konstanten an die
3 Code-Stellen, die sie heute aus den Settings lesen. Alte
JSON-Configs mit diesen Keys werden idempotent in `Settings.load()`
gesäubert.

## Hintergrund (Konsens Mike + Claude + R1 13.05.2026)

- **`audio_freq_hz`** (TX Audio-Frequenz, Default 1500 Hz, UI-Range
  800–2800 Hz) wirkt nur als Startwert für `Encoder.__init__`. Der
  CQ-Such-Algorithmus überschreibt `encoder.audio_freq_hz` dynamisch
  bei jedem Slot. Zweiter Lese-Ort: `Settings.get_normal_tx_freq` als
  Fallback wenn `normal_tx_freq_per_band` für ein Band leer ist.
- **`max_decode_freq`** (Default 3000 Hz, UI-Range 1000–5000 Hz) wirkt
  nur einmal beim App-Start an `Decoder(max_freq=...)`. **Code-Beweis
  (verifiziert 13.05.):** `grep '\.max_freq\s*='` über das gesamte Repo
  → genau 1 Treffer: `core/decoder.py:73` im `__init__`. Auch
  `decoder.set_band` (Z.138-144) berührt `max_freq` nicht — die Methode
  setzt nur `self._band` für den `audio_dump`-Dateinamen. Eine
  User-Eingabe von 4000 Hz wirkt also nur bis zum nächsten App-Neustart
  und auch dann nicht im laufenden Betrieb veränderbar.
- **Statusbar `_FILTERS`-Anzeige**
  (`{"FT8":"100-3100", "FT4":"100-3100", "FT2":"100-4000"}`) ist
  **aktiv irreführend**: Für FT2 zeigt sie 100-4000 Hz, der Decoder
  läuft aber faktisch auf 3000 Hz (Default unverändert beim
  Modus-Wechsel).

Aus dem dokumentierten R1-Vorab-Konsil zu diesem Thema
(`prompts/p47_filter_settings_r1.md`, 13.05.2026 vormittags):
„Tote Settings sind toter Code und verletzen das Prinzip der
geringsten Überraschung. Steuerbarkeit vortäuschen, die nicht
existiert. **Empfehlung A — alles raus.**"

## Akzeptanzkriterien

**AK1 — Settings-Keys + Properties weg.** In `config/settings.py`:

- DEFAULTS-Keys `"audio_freq_hz"` und `"max_decode_freq"` aus dem
  Dict-Literal entfernt (heute Z.60–61, im `DEFAULTS`-Block ganz oben).
- `@property audio_freq_hz` und `@property max_decode_freq` entfernt
  (heute Z.169-175).

**AK2 — Idempotente Säuberung alter Configs.** In
`Settings.load()` (heute Z.94-102) nach `self._data.update(saved)` und
**vor** `self._migrate_bandpilot_settings_v088()` zwei zusätzliche
Pops:

```python
# P47: tote Frequenz-Keys aus alten Configs entfernen (v0.97.11+).
# Idempotent — Dict-Pop ist No-op bei fehlendem Key.
self._data.pop("audio_freq_hz", None)
self._data.pop("max_decode_freq", None)
```

Save passiert beim nächsten regulären `Settings.save()`-Aufruf (z.B.
beim Bandwechsel, Settings-Dialog-Schließen). Kein Auto-Save in
`load()` nötig (KISS).

**AK3 — UI-Felder weg.** In `ui/settings_dialog.py`:

- Hint-Strings `"tx_freq"` und `"max_decode"` im `_HINTS`-Dict (Z.29–30)
  entfernt.
- QSpinbox-Init `self.audio_freq` und `self.max_decode_freq` inkl.
  `form.addRow(...)`-Aufrufe (Z.285–293, im Block der den FT8-Tab
  aufbaut) entfernt.
- Load-Pfade in der Tab-Init-Methode (`self.audio_freq.setValue(...)`,
  `self.max_decode_freq.setValue(...)`, Z.506–507) entfernt.
- Save-Pfade in `_save_and_close()` (`self.settings.set("audio_freq_hz",
  ...)`, `self.settings.set("max_decode_freq", ...)`, Z.646–647)
  entfernt.
- Reset-Default-Pfade in der „Auf Standard zurücksetzen"-Methode
  (Z.693–694) entfernt.

**AK4 — Statusbar-Filter-Anzeige weg.** In
`ui/main_window.py._update_statusbar()` (heute beginnt grob bei Z.1070):

- `_FILTERS`-Dict + `filter_str`-Berechnung (Z.1107–1109) komplett raus.
- Das Segment `f"Filter: {filter_str} Hz  |  "` aus dem zentralen
  `msg`-String (Z.1147) raus.

Reihenfolge der verbleibenden Segmente bleibt unverändert:
`Callsign | Locator | Mode Band | freq_display | mode_str + omni_str +
freq_str + ap_str`.

**AK5 — Konstanten statt Settings-Lookup an den 3 betroffenen Stellen.**

- `ui/main_window.py:144` — `Encoder(settings.audio_freq_hz)` →
  `Encoder(1500)`.
- `ui/main_window.py:145` — `Decoder(max_freq=settings.max_decode_freq)`
  → `Decoder(max_freq=3000)`.
- `config/settings.py:225` (`get_normal_tx_freq`) Fallback
  `self._data.get("audio_freq_hz", 1500)` → einfach `1500`.

**AK6 — Bestehende Tests werden angepasst.**

- `tests/test_settings_dialog_smoke.py`
  - `_FakeSettings._d` (Z.32-33): Keys `"audio_freq_hz"` und
    `"max_decode_freq"` entfernen.
  - `_FakeSettings.@property max_decode_freq` (Z.60-62): Property
    entfernen. (`audio_freq_hz` existierte hier nie als Property —
    nichts zu tun.)
  - `expected_attrs` (Z.97): `"audio_freq"` und `"max_decode_freq"`
    aus der Liste entfernen.
- `tests/test_modules.py`
  - Z.2073 + 2083: `s._data = {"audio_freq_hz": 1500}` zu
    `s._data = {}` ändern. Assertions bleiben (`get_normal_tx_freq(...)
    == 1500`) — das Verhalten ist identisch weil Fallback nun
    hartkodiert 1500 ist.

**AK7 — Neue Tests (`tests/test_p47_dead_freq_settings.py`).**

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- **T1 — `test_settings_load_drops_dead_keys`:** monkey-patch des
  Module-Levels `CONFIG_FILE` auf eine `tmp_path / "config.json"` die
  vorab `{"audio_freq_hz": 1700, "max_decode_freq": 4500,
  "callsign": "TEST"}` enthält → `Settings()` instanziieren →
  beide Keys nicht mehr in `s._data`.
- **T2 — `test_settings_no_audio_freq_property`:** `s = Settings()`
  → `hasattr(s, "audio_freq_hz") is False` und
  `hasattr(s, "max_decode_freq") is False`. (Da die Properties weg
  sind und keine `_data`-Keys mehr da sind, sollten beide hasattr-Tests
  False liefern.)
- **T3 — `test_get_normal_tx_freq_fallback_constant`:** Instanz via
  `Settings.__new__(Settings)` + `s._data = {}` →
  `s.get_normal_tx_freq("20m") == 1500` und
  `s.get_normal_tx_freq("40m") == 1500`.
- **T4 — `test_statusbar_no_filter_segment`:** Pattern analog
  `tests/test_p44_dt_indicator.py::test_dt_indicator_pattern_initial_grey`:
  ```python
  app = QApplication.instance() or QApplication([])
  win = MainWindow()
  win._update_statusbar()
  msg = win.statusBar().currentMessage()
  assert "Filter:" not in msg
  assert "100-3100" not in msg
  assert "100-4000" not in msg
  ```
  (MainWindow-Smoke darf radio_ip=leer haben — der Stargeschmack
  reicht.)

**AK8 — Gesamtsuite bleibt grün.** Erwartung: 1162 → ~1166 Tests
(+4 neu, ~5 angepasst, keine Tests gelöscht). Run mit
`QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`.

## Bewusste Verhaltensänderungen (zwei, dokumentiert)

**VÄ1 — `Settings.get_normal_tx_freq(band)` Fallback.** Bisher lieferte
das für unbekannte Bänder den vom User über die Settings-Dialog-Spinbox
einstellbaren Wert (`audio_freq_hz`, Default 1500). Künftig immer 1500.
Wirkung minimal — 1500 ist WSJT-X-Default und identisch mit dem
UI-Default-Wert. Bereits per Klick im Histogramm gesetzte
Per-Band-Werte (`normal_tx_freq_per_band`) bleiben weiterhin gültig.

**VÄ2 — `max_decode_freq` nicht mehr per UI änderbar.** Decoder
startet immer mit 3000 Hz Obergrenze. Bisher konnte ein User 4000 Hz
einstellen (UI erlaubte 1000–5000), wodurch der Decoder beim App-Start
mit `max_freq=4000` aufgebaut wurde — danach jedoch nie wieder
geändert, also auch im alten Code für FT2-Slots in der Praxis
wirkungsarm (1500 Stationen mehr theoretisch, real selten genutzt).
Mike als einziger Operator hat den Wert nach allen verfügbaren
Hinweisen (UI-Default 3000 = WSJT-X-Default) nicht verändert.

**Risiko der zwei Änderungen: LOW.** Mike-Single-User-Tool, beide
Defaults entsprechen WSJT-X-Branchen-Konvention. Per-Band-User-Werte in
`normal_tx_freq_per_band` bleiben erhalten.

## Betroffene Module/Dateien (mit Funktionsankern)

| Datei | Funktion / Block | Zeile (heute) | Was |
|---|---|---|---|
| `config/settings.py` | `DEFAULTS` (Top-Level-Dict) | 60–61 | Keys raus |
| `config/settings.py` | `Settings.load` | 99 → +pops vor 102 | 2 `pop()` ergänzen |
| `config/settings.py` | `@property audio_freq_hz` | 169–171 | Property raus |
| `config/settings.py` | `@property max_decode_freq` | 173–175 | Property raus |
| `config/settings.py` | `Settings.get_normal_tx_freq` | 225 | Fallback hartkodieren |
| `ui/settings_dialog.py` | `_HINTS` (Modul-Top) | 29–30 | 2 Hints raus |
| `ui/settings_dialog.py` | `_build_ft8_diversity_tab` (oder analoge Tab-Init-Methode) | 285–293 | 2 QSpinBox + Form-Rows raus |
| `ui/settings_dialog.py` | `_load_values` (oder Tab-Init-Werte) | 506–507 | Load-Pfad raus |
| `ui/settings_dialog.py` | `_save_and_close` | 646–647 | Save-Pfad raus |
| `ui/settings_dialog.py` | `_reset_defaults` | 693–694 | Reset-Pfad raus |
| `ui/main_window.py` | `MainWindow.__init__` (core-Components) | 144, 145 | Encoder/Decoder-Init mit Konstanten |
| `ui/main_window.py` | `MainWindow._update_statusbar` | 1107–1109, 1147 | `_FILTERS`+`filter_str`+`Filter:`-Segment raus |
| `tests/test_settings_dialog_smoke.py` | `_FakeSettings._d`, `@property max_decode_freq`, `expected_attrs` | 32–33, 60–62, 97 | Anpassen |
| `tests/test_modules.py` | `test_normal_tx_freq_default`, `test_normal_tx_freq_per_band_save_load` | 2073, 2083 | `_data = {}` |
| `tests/test_p47_dead_freq_settings.py` | NEU | — | T1–T4 |

## Randbedingungen

- **KISS:** Keine Helper-Funktionen, keine `DEFAULT_AUDIO_HZ`-Konstante,
  keine Migrationsklasse. Direkter Pop in `load()`, drei `1500` + ein
  `3000` hartcodiert. Drei ähnliche Zeilen > eine verfrühte
  Abstraktion (Mike-Programmierleitsatz #1).
- **Hardware-Pflicht ANT1=TX bleibt unberührt.** Kein TX-Pfad-Eingriff.
- **Single-Operator-Tool.** Keine Multi-Profile-Migration nötig.
- **Hobby-Tool-Philosophie:** ehrliche UI > täuschende Eingabefelder.
- **Encoder-Default-Wert `1000` (`core/encoder.py:49`)** bleibt
  unverändert (wird nur in Test-Helpern explizit auf 1500 gesetzt;
  irrelevant für App-Pfad).
- **Decoder-Default-Wert `3000` (`core/decoder.py:70`)** bleibt
  unverändert (deckt sich mit dem neuen `main_window.py:145`).
- **`decoder.set_band` berührt `max_freq` nicht** (Z.138-144,
  verifiziert) → die hartkodierte 3000 ist nach Band-Wechseln stabil.
- **Idempotenz:** Zweiter `Settings()`-Aufruf läuft schmerzfrei durch
  ohne die Keys nochmal popen zu müssen (Dict-Pop ist No-op bei
  fehlendem Key).

## Nicht im Scope

- `get_normal_tx_freq` als Konzept bleibt (Per-Band-TX-Frequenz für
  Normal-Modus) — nur der Fallback wird konstant.
- Encoder-Klassen-Default in `core/encoder.py` bleibt.
- Decoder-Klassen-Default in `core/decoder.py` bleibt.
- AP-Lite, OMNI-CQ, Diversity-Controller, CQ-Such-Algorithmus,
  TUNE_FREQS, Per-Band-TX-Frequenz-Speicherung — alle unberührt.
- Kein UI-Redesign vom FT8-Tab — nur die 2 Form-Rows raus, Rest des
  Tabs bleibt wie er war.
- Keine Tab-Umbenennung.
- Keine zentrale `DEFAULT_AUDIO_HZ`-Konstante.
- Keine Verhaltensänderung an `encoder.audio_freq_hz` während
  laufendem Betrieb (CQ-Algo überschreibt weiterhin).
- Keine Auto-Save-Logik in `Settings.load()`.

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `config/settings.py` — DEFAULTS + Properties + load-Pop +
   `get_normal_tx_freq`-Fallback.
2. **C2** `ui/settings_dialog.py` — Hints + UI-Felder + Load/Save/Reset.
3. **C3** `ui/main_window.py` — Encoder/Decoder-Init + Statusbar-Filter.
4. **C4** `tests/test_settings_dialog_smoke.py` +
   `tests/test_modules.py` — Stub-Settings, expected_attrs,
   normal_tx_freq-Tests.
5. **C5** `tests/test_p47_dead_freq_settings.py` (NEU) — T1–T4.
6. **C6** `main.py` APP_VERSION 0.97.10 → 0.97.11 +
   `HISTORY.md` + `HANDOFF.md` + `CLAUDE.md`-Header + `TODO.md` Punkt
   erledigt.

Atomares Backup vor C1:
`Appsicherungen/2026-05-13_v0.97.10_vor_p47_dead_freq_settings/` mit
den 3 betroffenen Files (`config/settings.py`,
`ui/settings_dialog.py`, `ui/main_window.py`).

## Final-R1-Codereview vor C6

Pflicht nach C5 (Tests grün), vor C6 (APP_VERSION-Bump + Doku):

```bash
echo "Reviewe die P47-Implementierung (v0.97.11) — Settings-Cleanup,
Statusbar-Filter-Anzeige raus, Encoder/Decoder-Init mit Konstanten.
Korrektheit, KISS, Tests?" | \
./venv/bin/python3 tools/deepseek_review.py config/settings.py \
ui/settings_dialog.py ui/main_window.py \
tests/test_p47_dead_freq_settings.py
```

🔴 Bug → sofort fixen | 🟠 Risiko → bewerten | 🟡 Verbesserung → meist
skip | ⚪ Hinweis → dokumentieren.

## R1-Findings-Bilanz (V2 → V3)

| Finding | Schwere | Aktion |
|---|---|---|
| `decoder.set_band` könnte `max_freq` setzen | 🟠 Risiko | **Abgelehnt** — Code-Verifikation widerlegt: Z.138-144 setzt nur `self._band`. In V3 unter Randbedingungen explizit dokumentiert. |
| Mike-Wert-Annahme spekulativ → Risiko MEDIUM | 🟠 Risiko | **Abgelehnt** — Single-User, WSJT-X-Default = UI-Default, Per-Band-Werte bleiben. Mit Audit-Log overengineering für Hobby-Tool. |
| `max_decode_freq` als Verhaltensänderung fehlt | 🟡 Unklar | **Angenommen** — VÄ2 ergänzt. |
| P44-Pattern für T4 undefiniert | 🟡 Unklar | **Angenommen** — Code-Snippet in AK7 T4 eingefügt. |
| R1-Originalton ohne Quelle | 🟡 Unklar | **Angenommen** — Quelle `prompts/p47_filter_settings_r1.md` ergänzt. |
| Feste Zeilennummern fragil | 🟢 Verbesserung | **Angenommen** — Funktionsanker zusätzlich zu Zeilen. |
| AK6 könnte expliziter sein | 🟢 Verbesserung | **Angenommen** — präzisiert (Fake hat audio_freq_hz nie als Property). |
| Commit-Mikromanagement | 🔘 Hinweis | **Beibehalten** — R1 selbst empfiehlt beibehalten. |
| Auto-Save in load() für Crash-Schutz | 🔘 Hinweis | **Abgelehnt** — KISS, Pop bleibt idempotent, nächster Save fängt's. |

## Risiko

**LOW.** Beide Settings sind faktisch wirkungslos. Statusbar-Anzeige
war irreführend, ihre Entfernung macht das Tool ehrlicher. Keine
bestehende Diversity-/CQ-/QSO-/OMNI-Logik wird berührt. Save-Pfad nicht
geändert (`Settings.save()` bleibt — Pop in `load()` reicht für
Bereinigung). Decoder-Verhalten identisch zum heutigen Default-Pfad
(3000 Hz war schon im laufenden Betrieb der einzige Wert nach
App-Start). Verhaltensänderungen sind unter VÄ1/VÄ2 dokumentiert und
beide entsprechen WSJT-X-Standard.
