# P48 — DT-System aufräumen + tunen (V2)

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

Vier zusammenhängende Verbesserungen am DT-Korrektur-System:

- **A** — Hardware-spezifische Werte (FlexRadio-TX-Buffer 1.3 s,
  FlexRadio-RX-Hardware-Latenz 0.26 s) aus dem Code in Settings auslagern.
- **B** — Cross-Modus-Fallback: `FT4_<band>` / `FT2_<band>` startet mit
  `FT8_<band>`-Wert (FT8 hat die meisten Stationen → solider Median).
- **C** — Hardware-Default als Kaltstart: statt `_correction = 0.0` als
  Notfall-Fallback nutze `rx_hardware_offset_default_s` aus Settings
  (= 0.26 für FlexRadio).
- **D** — Schnell-Konvergenz: wenn schon im 1. Mess-Slot ≥10 Stationen
  mit kleiner Streuung dabei sind → 1 statt 2 Slots warten.

## Hintergrund (empirisch verifiziert)

10.212 DT-Median-Einträge in Mike's `~/.simpleft8/archive/simpleft8-pre-rotation-2026-05-13.log`:

| Band (FT8) | N Erstkorrekturen | Roh-Median | Streuung |
|---|---|---|---|
| 15m | 4 | +0.260 s | 0.24–0.28 |
| 20m | 2 | +0.250 s | 0.24–0.26 |
| 30m | 21 | +0.260 s | 0.24–0.32 |
| 40m | 20 | +0.260 s | 0.24–0.32 |
| 80m, 10m | je 1 | +0.280 s | — |

→ FlexRadio-VITA-49-RX-Pipeline-Latenz **immer positiv, reproduzierbar
+0.26 s ± 0.04 s**. FT4/FT2-Daten fehlen (zu selten gefahren), aber Latenz
ist Hardware-/Netzwerk-Eigenschaft, theoretisch modus-unabhängig.

Aktuell hartverdrahtet:

| Datei:Zeile | Konstante | Wert | Was es ist |
|---|---|---|---|
| `core/encoder.py:25` | `TARGET_TX_OFFSET` | `-0.8` | `0.5 (Protokoll) − 1.3 (FlexRadio-TX-Buffer)` |
| `core/ntp_time.py:101` | Fallback in `_load_for_current_key` | `0.0` | Kaltstart-Default |

## Akzeptanzkriterien

**AK1 — Settings-Block `radio_timing`.**

In `config/settings.py` `DEFAULTS` neuer Top-Level-Eintrag:

```python
"radio_timing": {
    "tx_buffer_s": 1.3,                    # FlexRadio VITA-49 TX-Buffer
    "rx_hardware_offset_default_s": 0.26,  # FlexRadio RX-Latenz empirisch
},
```

Plus Properties (mit defensiver `.get()`-Kette für Backward-Kompat):

```python
@property
def tx_buffer_s(self) -> float:
    return self._data.get("radio_timing", {}).get("tx_buffer_s", 1.3)

@property
def rx_hardware_offset_default_s(self) -> float:
    return self._data.get("radio_timing", {}).get("rx_hardware_offset_default_s", 0.26)
```

Alte Configs ohne `radio_timing`-Block lesen die Defaults (1.3 / 0.26)
ohne Migration. Wenn der User Settings speichert, wird der Block dann
mit Default-Werten persistiert.

**AK2 — `core/ntp_time.py` Hardware-Default-Mechanismus.**

Neue Modul-Var + Setter (vor `_load_saved()`-Block):

```python
# P48-C: Hardware-Default fuer Kaltstart (von main_window beim App-Start
# aus settings.rx_hardware_offset_default_s gesetzt). Default 0.0 fuer
# Backward-Kompat falls der Setter nie aufgerufen wird (Test-Umgebung).
_hardware_default_offset: float = 0.0


def set_hardware_default(value_s: float):
    """Wird von main_window beim Start aufgerufen.

    Wenn keine gemessenen Werte und kein Cross-Modus-Fallback greift,
    nutzt _load_for_current_key() diesen Wert als Kaltstart.
    """
    global _hardware_default_offset
    _hardware_default_offset = float(value_s)
```

**AK3 — Cross-Modus-Fallback + Hardware-Default in `_load_for_current_key`.**

Aktuell (Z.90-101):

```python
def _load_for_current_key() -> float:
    key = _mode_key()
    val = _saved.get(key, None)
    if val is not None:
        return val
    old_val = _saved.get(_mode, None)
    if old_val is not None:
        print(f"[DT-Korr] Migration: '{_mode}' → '{key}' = {old_val:+.3f}s")
        return old_val
    return 0.0
```

Neu:

```python
# P48-B: Cross-Modus-Prioritaet — FT8 > FT4 > FT2 (FT8 hat die meisten
# Stationen, also den verlaesslichsten Median).
_SIBLING_PRIORITY = {
    "FT2": ["FT4", "FT8"],
    "FT4": ["FT8"],
    "FT8": [],  # FT8 ist Master, kein Geschwister-Fallback
}


def _load_for_current_key() -> float:
    key = _mode_key()
    val = _saved.get(key, None)
    if val is not None:
        return val
    # Legacy-Migration: alter Schluessel ohne Band
    old_val = _saved.get(_mode, None)
    if old_val is not None:
        print(f"[DT-Korr] Migration: '{_mode}' → '{key}' = {old_val:+.3f}s")
        return old_val
    # P48-B: Cross-Modus-Fallback — Geschwister-Modi auf selbem Band
    for sibling_mode in _SIBLING_PRIORITY.get(_mode, []):
        sibling_key = f"{sibling_mode}_{_band}"
        sibling_val = _saved.get(sibling_key, None)
        if sibling_val is not None:
            print(f"[DT-Korr] Cross-Modus-Fallback: '{sibling_key}' "
                  f"({sibling_val:+.3f}s) → '{key}'")
            return sibling_val
    # P48-C: Hardware-Default als Notfall-Kaltstart
    return _hardware_default_offset
```

**Wichtige Klarstellung zum Save-Verhalten:** Cross-Modus- oder
Hardware-Default-Werte landen nur im RAM (`_correction`), nicht
sofort auf Disk. Erst beim nächsten Modus/Band-Wechsel (über
`_save_current()` in `set_mode`/`set_band`) wird der dann aktuelle
Wert für die alte Kombi auf Disk geschrieben. **Das ist OK** — der
Wert ist nahe am echten Wert, Mike's Mess-Phase verfeinert ihn
ohnehin. Beim nächsten Aufruf derselben Kombi wird dieser eingelockte
Wert geladen — Cross-Modus-Fallback wird nur 1× pro neuer Kombi
durchlaufen.

**AK4 — `main_window.__init__` ruft `set_hardware_default`.**

`ui/main_window.py` in `_init_core_components` direkt nach
`self.qso_sm = ...` und **vor** `self.encoder = ...`:

```python
# P48: Hardware-Default fuer DT-Kaltstart aus Settings setzen
from core import ntp_time as _ntp
_ntp.set_hardware_default(settings.rx_hardware_offset_default_s)
```

**AK5 — Encoder nutzt `tx_buffer_s` aus Settings (TX-Buffer-Latenz).**

`core/encoder.py`:

- Modul-Konstante `TARGET_TX_OFFSET = -0.8` (Z.25) **entfernt**.
- `Encoder.__init__` (Z.49) neuer Parameter:

  ```python
  def __init__(self, audio_freq_hz: int = 1000,
               tx_buffer_s: float = 1.3):
      super().__init__()
      self.audio_freq_hz = audio_freq_hz
      # P48: TX-Audio-Vorlauf = 0.5s Protokoll - tx_buffer_s Hardware.
      # FlexRadio Default 1.3 → target_tx_offset_s = -0.8 (= alter Wert).
      self.target_tx_offset_s = 0.5 - tx_buffer_s
      ...
  ```

- Alle Verwendungen von `TARGET_TX_OFFSET` im Modul → `self.target_tx_offset_s`:
  - Z.312 `sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()`
  - Z.345 `silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - now)`
  - Z.352 `overshoot = now - (next_boundary + TARGET_TX_OFFSET)`
  - Z.358 `silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - time.time())`

- `ui/main_window.py:144` (nach P47 jetzt `Encoder(1500)`) wird zu:
  ```python
  self.encoder = Encoder(1500, tx_buffer_s=settings.tx_buffer_s)
  ```

**AK6 — Schnell-Konvergenz in `update_from_decoded`.**

In `core/ntp_time.py:199` Mess-Block, vor `needed = ...`-Berechnung:

```python
if _phase == "measure":
    _measure_buffer.append(median_dt)
    _cycle_count += 1

    # P48-D: Schnell-Konvergenz wenn 1. Slot bereits viele Stationen
    # mit kleiner Streuung hat → kein zweiter Slot zur Bestaetigung
    # noetig (Median ueber 10+ Werte mit Stddev < 0.1s ist solide).
    can_fast = (
        _is_initial
        and _cycle_count == 1
        and len(valid) >= _FAST_CONVERGENCE_MIN_STATIONS
        and statistics.stdev(valid) < _FAST_CONVERGENCE_MAX_STDEV
    )
    needed = 1 if can_fast else (
        INITIAL_MEASURE_CYCLES if _is_initial else STEADY_MEASURE_CYCLES
    )

    if _cycle_count >= needed:
        # ... rest unveraendert ab Z.205
```

Modul-Konstanten (vor `_lock`-Block, nahe den anderen Konfig-Werten):

```python
_FAST_CONVERGENCE_MIN_STATIONS = 10  # FT8 abends 20m oft 30+ Stationen
_FAST_CONVERGENCE_MAX_STDEV = 0.1    # Stationen alle nahe am gleichen DT
```

KEINE Settings-Auslagerung — interne Algorithmus-Parameter, nicht
hardware-spezifisch.

**`statistics.stdev` braucht ≥2 Werte** — bei `len(valid) >= 10` immer
erfüllt, kein Schutz nötig.

**AK7 — OMNI-Pretrigger bleibt unverändert (out of scope).**

`core/omni_cq.py` hat eine eigene Modul-Konstante `_OMNI_PRETRIGGER_OFFSET_S
= 1.3` (= |TARGET_TX_OFFSET|, dokumentiert in HISTORY). Logisch das
gleiche wie der TX-Buffer, aber für den OMNI-Pfad gebraucht. **Bei
IC-7300-Fork müsste auch diese Konstante parametrisiert werden** — wird
hier aber NICHT angepasst (Scope-Begrenzung).

Dokumentiert in TODO als Folgepunkt „P48-Followup: OMNI-Pretrigger aus
Settings".

**AK8 — Tests.**

`tests/test_p48_dt_optimization.py` NEU (11 Tests).

Test-Setup mit `monkeypatch` (kein Disk-Side-Effect — `conftest.py`
schützt schon `_DT_FILE`, aber wir monkeypatchen zusätzlich
`_saved`, `_correction`, `_hardware_default_offset`, `_mode`, `_band`,
`_phase`, `_is_initial` für Determinismus):

```python
@pytest.fixture
def fresh_ntp(monkeypatch):
    import core.ntp_time as nt
    monkeypatch.setattr(nt, "_saved", {})
    monkeypatch.setattr(nt, "_correction", 0.0)
    monkeypatch.setattr(nt, "_hardware_default_offset", 0.0)
    monkeypatch.setattr(nt, "_last_logged_load", None)
    monkeypatch.setattr(nt, "_mode", "FT8")
    monkeypatch.setattr(nt, "_band", "20m")
    monkeypatch.setattr(nt, "_phase", "measure")
    monkeypatch.setattr(nt, "_is_initial", True)
    monkeypatch.setattr(nt, "_cycle_count", 0)
    monkeypatch.setattr(nt, "_measure_buffer", [])
    yield nt
```

- **T1** — `test_settings_has_radio_timing_defaults`: frische Settings
  liefert `tx_buffer_s == 1.3` und `rx_hardware_offset_default_s == 0.26`.
- **T2** — `test_settings_backward_compat_no_radio_timing_block`: alte
  Config (tmp-Pfad) mit nur `{"callsign": "X"}` lädt → beide Properties
  liefern Defaults ohne KeyError.
- **T3** — `test_load_for_current_key_returns_hardware_default` (mit
  `fresh_ntp`): `_hardware_default_offset = 0.26`, `_saved = {}`,
  `_mode = "FT8"`, `_band = "20m"` → `_load_for_current_key() == 0.26`.
- **T4** — `test_cross_mode_fallback_ft2_uses_ft8`: `_saved = {"FT8_30m":
  0.27}`, `_mode = "FT2"`, `_band = "30m"` → `_load_for_current_key()
  == 0.27`.
- **T5** — `test_cross_mode_fallback_ft4_uses_ft8`: analog FT4 → 0.27.
- **T6** — `test_cross_mode_no_fallback_for_ft8`: `_saved = {"FT4_30m":
  0.27}`, `_mode = "FT8"`, `_band = "30m"`,
  `_hardware_default_offset = 0.26` → `_load_for_current_key() == 0.26`
  (FT8 nutzt keinen FT4-Fallback).
- **T7** — `test_cross_mode_prefers_own_value`: `_saved = {"FT2_30m":
  0.29, "FT8_30m": 0.27}`, `_mode = "FT2"`, `_band = "30m"` → 0.29
  (eigener Wert hat Vorrang).
- **T8** — `test_cross_mode_ft2_prefers_ft4_over_ft8`: `_saved =
  {"FT4_30m": 0.28, "FT8_30m": 0.27}`, `_mode = "FT2"`, `_band = "30m"`
  → 0.28 (FT4 vor FT8 in der Priorität).
- **T9** — `test_encoder_tx_offset_default_flex`:
  `Encoder(1500)` → `target_tx_offset_s == -0.8` (Default 1.3).
- **T10** — `test_encoder_tx_offset_custom_buffer`:
  `Encoder(1500, tx_buffer_s=1.0)` → `target_tx_offset_s == -0.5`
  (IC-7300-Simulation).
- **T11** — `test_fast_convergence_threshold` (mit `fresh_ntp`):
  `_hardware_default_offset = 0.0`, `_is_initial = True`,
  `update_from_decoded([0.5]*12)` (12 Stationen alle 0.5s, Stddev 0)
  → liefert True (Korrektur applied), `_phase == "operate"`,
  `_correction != 0.0`.
- **T12** — `test_fast_convergence_high_stdev_blocked` (mit `fresh_ntp`):
  12 Stationen mit Stddev > 0.1 (z.B. `[0.0, 0.5] * 6`) → liefert False
  (1. Slot, kein Update), `_phase == "measure"`.
- **T13** — `test_fast_convergence_few_stations_blocked` (mit
  `fresh_ntp`): 5 Stationen mit kleiner Stddev → liefert False (≥10
  nötig), `_phase == "measure"`.
- **T14** — `test_hardware_default_setter`: `set_hardware_default(0.3)`
  → `_hardware_default_offset == 0.3`.

Erwartung: 1175 → **~1189** (+14, V1-Plan unterschätzte um 3).

**AK9 — Gesamtsuite grün.**

Run mit `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`.

## Betroffene Module/Dateien

| Datei | Funktion / Block | Was |
|---|---|---|
| `config/settings.py` | `DEFAULTS` (Top-Level) | `radio_timing`-Block ergänzen |
| `config/settings.py` | Settings-Klasse | 2 neue Properties |
| `core/ntp_time.py` | Modul-Top | `_hardware_default_offset`, `_SIBLING_PRIORITY`, `_FAST_CONVERGENCE_*` Konstanten |
| `core/ntp_time.py` | Modul-Funktion | `set_hardware_default()` |
| `core/ntp_time.py` | `_load_for_current_key` | Cross-Modus + Hardware-Default |
| `core/ntp_time.py` | `update_from_decoded` Mess-Block | Schnell-Konvergenz |
| `core/encoder.py` | `TARGET_TX_OFFSET` Konstante (Z.25) | Entfernen |
| `core/encoder.py` | `Encoder.__init__` | `tx_buffer_s`-Parameter |
| `core/encoder.py` | 4 TARGET_TX_OFFSET-Verwendungen | → `self.target_tx_offset_s` |
| `ui/main_window.py:144` | `_init_core_components` | `_ntp.set_hardware_default(...)` + `Encoder(1500, tx_buffer_s=...)` |
| `tests/test_p48_dt_optimization.py` | NEU | T1–T14 |

## Randbedingungen

- **KISS:** Module-Var + Setter statt Singleton/DI-Container. Konstanten
  bleiben Modul-Level. Cross-Modus-Priorität als statisches Dict.
- **Hardware-Pflicht ANT1=TX bleibt unberührt** (kein TX-Pfad-Eingriff,
  nur Buffer-Latenz-Wert wird parametrisiert).
- **Single-Operator-Tool, Mike-only.**
- **Backward-Kompat:** alte Configs laden, Defaults identisch zu
  aktuellem Verhalten (1.3/0.26). Mathematisch identisch:
  `Encoder(audio_freq_hz=1500)` Default `tx_buffer_s=1.3`
  → `target_tx_offset_s = 0.5 - 1.3 = -0.8` (alter Wert).
- **`_FAST_CONVERGENCE_*` konservativ:** 10 Stationen + 0.1 s Streuung.
  Bei FT8 abends sicher getroffen, bei FT4/FT2 selten — diese Modi
  bleiben auf der 2-Slot-Pfad, kein Schaden.
- **Cross-Modus-Reihenfolge** FT8 > FT4 > FT2: empirisch FT8 hat die
  meisten Stationen, also den verlässlichsten Median.

## Nicht im Scope

- **`_WAKE_OFFSETS` / `_DT_OFFSETS` in Settings auslagern** — App-interne
  Implementation-Wahl, nicht hardware-spezifisch.
- **OMNI-`_OMNI_PRETRIGGER_OFFSET_S` parametrisieren** — Folgepunkt
  „P48-Followup", separater Workflow (kleiner Refactor, ~30 min).
- **Self-Adapting Hardware-Default** (Mike abgelehnt: too much).
- **IC-7300-Fork-Werte** (Fork ist eigener Branch, dort separat).
- **DT-Audit-Tool** (bei Bedarf später, ~20 min).
- **Statistics-Cleanup** (Mike: out of scope, kommt später).

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `config/settings.py` — `radio_timing`-Block + Properties.
2. **C2** `core/ntp_time.py` — `_hardware_default_offset` +
   `set_hardware_default` + Cross-Modus-Fallback in `_load_for_current_key`.
3. **C3** `core/ntp_time.py` — Schnell-Konvergenz in `update_from_decoded`.
4. **C4** `core/encoder.py` — `tx_buffer_s`-Parameter +
   `self.target_tx_offset_s`-Migration.
5. **C5** `ui/main_window.py` — `set_hardware_default()` + `Encoder`-Aufruf.
6. **C6** `tests/test_p48_dt_optimization.py` NEU (T1–T14).
7. **C7** APP_VERSION 0.97.12 → 0.97.13 + HISTORY + HANDOFF + CLAUDE +
   TODO P48 erledigt + Plan-Files + Followup-P49 in TODO.

Backup vor C1: `Appsicherungen/2026-05-13_v0.97.12_vor_p48_dt_optimization/`
mit `config/settings.py`, `core/ntp_time.py`, `core/encoder.py`,
`ui/main_window.py`.

## Risiko

**MITTEL.** Mehr Touchpoints als Bundle A (5 Code-Dateien). TX-Pfad wird
parametrisiert (Encoder-Konstante zu Instanz-Attribut) → Hardware-relevant.

**Minimierungs-Strategien:**

- Encoder-Default `tx_buffer_s=1.3` ergibt mathematisch identisch
  `target_tx_offset_s = -0.8` wie alter `TARGET_TX_OFFSET`. **Kein
  Verhaltensänderung** wenn Settings auf Defaults stehen.
- Settings-Backward-Kompat: `.get()`-Kette für `radio_timing`-Block
  → alte Config lädt sauber.
- Cross-Modus-Fallback + Hardware-Default greifen NUR bei Kaltstart
  neuer Mode-Band-Kombi — Mike's gemessene Werte werden weiterhin
  geladen wie heute.
- Schnell-Konvergenz greift NUR bei Erst-Mess-Phase (`_is_initial`),
  `_cycle_count == 1`, ≥10 Stationen, Stddev < 0.1s — sehr enges Fenster.
  Bei nicht-Erfüllung: identisches 2-Slot-Verhalten wie heute.

**Field-Test (optional aber empfohlen):**

1. App starten mit leerer `dt_corrections.json` → Stationen sollen ab
   1. Slot bei DT ≈ 0 ± 0.05s liegen (Hardware-Default greift sofort).
2. Bandwechsel auf neues Band → Cross-Modus-Fallback aus FT8 sollte
   FT4/FT2 sofort gut starten.
3. TX nach Korrektur → DT am Empfänger weiterhin ≈ 0 (TX-Pfad
   unverändert wenn Settings auf Defaults).
