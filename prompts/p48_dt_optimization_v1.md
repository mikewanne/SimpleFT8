# P48 — DT-System aufräumen + tunen (V1)

Vier zusammenhängende Verbesserungen am DT-Korrektur-System:

- **A:** Hardware-spezifische Werte aus dem Code in Settings auslagern
- **B:** Cross-Modus-Fallback (FT4/FT2 startet mit FT8-Wert vom selben Band)
- **C:** Hardware-Default als Kaltstart (statt `0.0` → empirisch +0,26 s)
- **D:** Schnell-Konvergenz bei vielen Stationen (1 Slot statt 2)

## Hintergrund (empirisch verifiziert)

10.212 DT-Median-Einträge in Mike's Logs zeigen:

- FlexRadio-RX-Hardware-Latenz konvergiert über alle Bänder reproduzierbar
  auf **+0,26 s ± 0,04 s** (15m, 20m, 30m, 40m, 80m alle innerhalb 0,02 s).
- Verteilung immer positiv (nie negativer Roh-Median bei Erstkorrekturen).
- FT4/FT2-Daten fehlen in den Logs (zu selten gefahren) — aber die Latenz
  ist FlexRadio-VITA-49-Pipeline-Eigenschaft, theoretisch modus-unabhängig.

Aktuell hartverdrahtete Werte im Code:

| Datei:Zeile | Konstante | Wert | Was es ist |
|---|---|---|---|
| `core/encoder.py:25` | `TARGET_TX_OFFSET` | `-0,8` | `0,5 (Protokoll) − 1,3 (FlexRadio-TX-Buffer)` |
| `core/ntp_time.py:44` | `_correction` Init | `0,0` | Adaptive RX-Korrektur Startwert |

Beide sind FlexRadio-spezifisch — bei IC-7300-Fork (geplant) braucht's andere
Werte. Statt im Code zu hardcoden → Settings.

## Akzeptanzkriterien

**AK1 — Settings-Block `radio_timing`.**

In `config/settings.py` `DEFAULTS` neuer Top-Level-Eintrag:

```python
"radio_timing": {
    "tx_buffer_s": 1.3,                    # FlexRadio VITA-49 TX-Buffer-Latenz
    "rx_hardware_offset_default_s": 0.26,  # FlexRadio RX-Latenz empirisch (10.212 Messungen)
},
```

Plus Properties:

```python
@property
def tx_buffer_s(self) -> float:
    return self._data.get("radio_timing", {}).get("tx_buffer_s", 1.3)

@property
def rx_hardware_offset_default_s(self) -> float:
    return self._data.get("radio_timing", {}).get("rx_hardware_offset_default_s", 0.26)
```

Backward-Kompat: alte Configs ohne `radio_timing`-Block → Defaults aus
Properties greifen (1.3 / 0.26).

**AK2 — `core/ntp_time.py` Hardware-Default-Mechanismus.**

Neue Modul-Var + Setter:

```python
_hardware_default_offset: float = 0.0  # Default-Kaltstart-Wert (von main_window gesetzt)

def set_hardware_default(value_s: float):
    """Wird von main_window beim Start aufgerufen.
    Wenn keine gemessenen Werte und kein Cross-Modus-Fallback greift,
    nutzt _load_for_current_key() diesen Wert als Kaltstart.
    """
    global _hardware_default_offset
    _hardware_default_offset = value_s
```

**AK3 — Cross-Modus-Fallback in `_load_for_current_key`.**

Aktuell (Z.90-101): `_saved[key]` → `_saved[mode]` (Legacy) → `0.0`.

Neu (vor dem `0.0`-Fallback):

```python
# P48-B: Cross-Modus-Fallback — anderer Modus auf gleichem Band
# Priorität: FT8 > FT4 > FT2 (FT8 hat mehr Stationen → solider Wert)
sibling_priority = {
    "FT2": ["FT4", "FT8"],
    "FT4": ["FT8"],
    "FT8": [],  # FT8 ist Master
}
for sibling_mode in sibling_priority.get(_mode, []):
    sibling_key = f"{sibling_mode}_{_band}"
    sibling_val = _saved.get(sibling_key, None)
    if sibling_val is not None:
        print(f"[DT-Korr] Cross-Modus-Fallback: '{sibling_key}' "
              f"→ '{key}' = {sibling_val:+.3f}s")
        return sibling_val

# P48-C: Hardware-Default als Notfall-Kaltstart
return _hardware_default_offset
```

**AK4 — `main_window.__init__` ruft `set_hardware_default`.**

`ui/main_window.py` vor Encoder/Decoder-Init:

```python
from core import ntp_time as _ntp
_ntp.set_hardware_default(settings.rx_hardware_offset_default_s)
```

**AK5 — Encoder nutzt `tx_buffer_s` aus Settings.**

`core/encoder.py`:

- Modul-Konstante `TARGET_TX_OFFSET = -0.8` (Z.25) → entfernt.
- `Encoder.__init__` bekommt neuen Parameter `tx_buffer_s: float = 1.3`:
  ```python
  def __init__(self, audio_freq_hz: int = 1000, tx_buffer_s: float = 1.3):
      super().__init__()
      self.audio_freq_hz = audio_freq_hz
      self.target_tx_offset_s = 0.5 - tx_buffer_s  # = -0.8 für Flex (Default)
      ...
  ```
- Alle Verwendungen von `TARGET_TX_OFFSET` im Modul → `self.target_tx_offset_s`
  (Z.312, 345, 352, 358 + OMNI-Pfad Z.123 im Excerpt).
- `main_window.py:144` `Encoder(1500)` → `Encoder(1500, settings.tx_buffer_s)`.

**AK6 — Schnell-Konvergenz bei vielen Stationen.**

`core/ntp_time.py:199-204` (in `update_from_decoded`-Mess-Block):

```python
if _phase == "measure":
    _measure_buffer.append(median_dt)
    _cycle_count += 1

    # P48-D: Schnell-Konvergenz wenn 1. Slot bereits viele Stationen
    # mit kleiner Streuung hat → kein zweiter Slot zur Bestätigung nötig.
    fast_threshold = 10
    fast_max_stdev = 0.1
    can_fast = (
        _is_initial
        and _cycle_count == 1
        and len(valid) >= fast_threshold
        and statistics.stdev(valid) < fast_max_stdev
    )
    needed = 1 if can_fast else (
        INITIAL_MEASURE_CYCLES if _is_initial else STEADY_MEASURE_CYCLES
    )

    if _cycle_count >= needed:
        # ... rest unverändert
```

`fast_threshold = 10` und `fast_max_stdev = 0.1` als neue Modul-Konstanten
(nicht in Settings — interne Algorithmus-Parameter, kein Hardware-Tuning).

**AK7 — Tests.**

Neue Datei `tests/test_p48_dt_optimization.py` mit:

- **T1** — `test_settings_has_radio_timing_defaults`: frische Settings hat
  `tx_buffer_s = 1.3` und `rx_hardware_offset_default_s = 0.26`.
- **T2** — `test_settings_backward_compat_no_radio_timing_block`: alte
  Config ohne `radio_timing` lädt sauber, Defaults greifen.
- **T3** — `test_load_for_current_key_returns_hardware_default`: Kaltstart
  ohne gespeicherte Werte → `_hardware_default_offset` wird zurückgegeben.
- **T4** — `test_cross_mode_fallback_ft2_uses_ft8`: `_saved = {"FT8_30m": 0.27}`,
  Modus=FT2, Band=30m → `_load_for_current_key()` returnt 0.27.
- **T5** — `test_cross_mode_fallback_ft4_uses_ft8`: analog für FT4.
- **T6** — `test_cross_mode_no_fallback_for_ft8`: FT8 selber hat keinen
  Geschwister-Fallback (returnt Hardware-Default wenn kein eigener Wert).
- **T7** — `test_cross_mode_prefers_own_value`: wenn eigener Wert existiert,
  wird kein Cross-Modus geladen.
- **T8** — `test_encoder_tx_offset_from_buffer`: `Encoder(1500, tx_buffer_s=1.3)`
  hat `target_tx_offset_s == -0.8`. `Encoder(1500, tx_buffer_s=1.0)` hat
  `target_tx_offset_s == -0.5` (IC-7300-Simulation).
- **T9** — `test_fast_convergence_threshold`: 10+ Stationen mit Stddev < 0.1
  → `_cycle_count == 1` reicht, sofort `_phase == "operate"`.
- **T10** — `test_fast_convergence_high_stdev_blocked`: 10+ Stationen aber
  Stddev > 0.1 → wartet weiterhin auf 2 Slots.
- **T11** — `test_fast_convergence_few_stations_blocked`: 5 Stationen mit
  kleiner Stddev → wartet auf 2 Slots (weniger als 10).

**AK8 — Gesamtsuite grün.**

Erwartung: 1175 → ~1186 Tests (+11). Run mit
`QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`.

## Betroffene Module/Dateien

| Datei | Funktion / Block | Was |
|---|---|---|
| `config/settings.py` | `DEFAULTS` (Top-Level) | `radio_timing`-Block ergänzen |
| `config/settings.py` | Settings-Klasse | 2 Properties |
| `core/ntp_time.py` | Modul-Top | `_hardware_default_offset` Var |
| `core/ntp_time.py` | Modul-Funktion | `set_hardware_default()` |
| `core/ntp_time.py` | `_load_for_current_key` | Cross-Modus + Hardware-Default |
| `core/ntp_time.py` | `update_from_decoded` Mess-Block | Schnell-Konvergenz |
| `core/encoder.py` | `TARGET_TX_OFFSET` Konstante (Z.25) | Entfernen |
| `core/encoder.py` | `Encoder.__init__` | `tx_buffer_s`-Parameter |
| `core/encoder.py` | TARGET_TX_OFFSET-Verwendungen | → `self.target_tx_offset_s` |
| `ui/main_window.py` | `_init_core_components` (vor Encoder) | `_ntp.set_hardware_default(...)` |
| `ui/main_window.py` | `_init_core_components` | `Encoder(1500, settings.tx_buffer_s)` |
| `tests/test_p48_dt_optimization.py` | NEU | T1–T11 |

## Randbedingungen

- **KISS:** Module-Var + Setter statt Singleton/DI-Container.
- **Hardware-Pflicht ANT1=TX bleibt unberührt** (kein TX-Pfad-Eingriff,
  nur Buffer-Latenz-Wert wird parametrisiert).
- **Single-Operator-Tool, Mike-only.** Keine Multi-Radio-Profile-Logik.
- **Backward-Kompat:** alte Configs ohne `radio_timing` laden sauber,
  Defaults greifen — ident isch mit aktuellem Verhalten (1.3/0.26).
- **`fast_threshold=10` + `fast_max_stdev=0.1`** konservativ gewählt —
  bei FT8 abends 20m mit 30+ Stationen sicher getroffen, kein
  Falsch-Positiv bei wenig/verrauschten Daten.
- **Cross-Modus-Reihenfolge** FT8 > FT4 > FT2: empirisch FT8 hat die
  meisten Stationen, also den verlässlichsten Median.
- **OMNI-TX-Pfad nicht beeinflusst** — `_OMNI_PRETRIGGER_OFFSET_S = 1.3`
  bleibt hartkodiert (sollte aber bei IC-7300 ggf. auch parametrisiert
  werden — out of scope, separater Punkt für später).

## Nicht im Scope

- **`_WAKE_OFFSETS` / `_DT_OFFSETS` in Settings auslagern** — App-interne
  Implementation-Wahl, nicht hardware-spezifisch.
- **Self-Adapting Hardware-Default** (Mike abgelehnt: too much).
- **OMNI-`_OMNI_PRETRIGGER_OFFSET_S` parametrisieren** — separater Punkt.
- **IC-7300-Fork-Werte** — Fork ist eigene Codebase, dort kommt das eh
  separat.
- **DT-Audit-Tool** (separates kleines Tool, bei Bedarf nachschieben).
- **Statistics-Cleanup** (Mike: out of scope, kommt später).

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `config/settings.py` — `radio_timing`-Block + Properties.
2. **C2** `core/ntp_time.py` — `_hardware_default_offset` + Setter +
   Cross-Modus-Fallback in `_load_for_current_key`.
3. **C3** `core/ntp_time.py` — Schnell-Konvergenz in `update_from_decoded`.
4. **C4** `core/encoder.py` — `tx_buffer_s`-Parameter +
   `self.target_tx_offset_s`-Migration aller Verwendungsstellen.
5. **C5** `ui/main_window.py` — `set_hardware_default()` Aufruf +
   `Encoder(..., settings.tx_buffer_s)`.
6. **C6** `tests/test_p48_dt_optimization.py` NEU (T1–T11).
7. **C7** APP_VERSION 0.97.12 → 0.97.13 + HISTORY + HANDOFF + CLAUDE +
   TODO P48 erledigt + Plan-Files.

Backup vor C1: `Appsicherungen/2026-05-13_v0.97.12_vor_p48_dt_optimization/`
mit `config/settings.py`, `core/ntp_time.py`, `core/encoder.py`,
`ui/main_window.py`.

## Risiko

**MITTEL.** Mehr Touchpoints als Bundle A (5 Code-Dateien statt 2). TX-Pfad
wird angefasst (Encoder-Konstante zu Instanz-Attribut) → Hardware-relevant.
Aber: das `TARGET_TX_OFFSET = -0.8`-Verhalten ist bei Default-`tx_buffer_s=1.3`
mathematisch identisch zum heutigen Code (`0.5 - 1.3 = -0.8`). Keine
Verhaltensänderung wenn Settings auf Defaults.

**Minimierungs-Strategien:**
- Encoder-Defaults so wählen dass alter Code identisch läuft.
- Field-Test V3 §5: TX-DT prüfen (sollte unverändert ~0.0 sein).
- Cross-Modus + Hardware-Default greifen NUR bei Kaltstart neuer Band-Modus —
  Mike's gemessene Werte werden weiterhin geladen wie heute.
