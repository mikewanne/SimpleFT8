# P121 V3 — Radio-Hardware-Konstanten + IC-7300/IC-7100 Stubs

> Implementierungs-Prompt nach V1→V2→R1→V3-Workflow. R1-Findings
> (DeepSeek V4-pro) eingearbeitet — Bug 1+2+3 aufgelöst, Risiko 4
> übernommen, Verbesserung 5 übernommen, Risiko 6 abgelehnt (Sicherheit
> > Komfort), Hinweise 7-9 trivial korrigiert.

## Architektur-Klarstellung (wichtig — V2 war hier unscharf)

`radio/flexradio.py:27` definiert `class FlexRadio(QObject)` — **kein
RadioInterface-Erbe**. Vererbung über ABC ist faktisch Duck-Typing.
Class-Variables auf `RadioInterface` werden **nicht** automatisch in
`FlexRadio` sichtbar. Konsequenz für diese Implementierung:

- `RadioInterface` Class-Variables sind **Dokumentations-Vertrag +
  Stub-Fallback**.
- **Jede konkrete Radio-Klasse muss eigene Class-Variables setzen**
  (FlexRadio, IC7300, IC7100 redundant explizit).
- Kein Multi-Inheritance-Refactor (FlexRadio von QObject+ABC) jetzt —
  Metaclass-Konflikt zwischen `QObject` und `ABC` ist eigene
  Refactor-Baustelle, separates Ticket bei Bedarf.

## 1. Ziel

Hardware-Konstanten verlagern von Settings/hartcodiert in jede konkrete
Radio-Klasse. IC-7300 + IC-7100 als instanziierbare Stub-Klassen
anlegen damit späterer echter Fork nur die CI-V-Methoden füllen muss.

## 2. Akzeptanzkriterien (R1-eingearbeitet)

### A. ABC-Erweiterung — Dokumentations-Stubs

`radio/base_radio.py` nach Z.27 (`radio_type: str = "unknown"`):

```python
# Hardware-Konstanten — JEDE konkrete Subclass MUSS eigene Werte setzen.
# Diese Defaults sind Notfall-Fallback wenn jemand sie vergessen sollte.
tx_buffer_s: float = 1.3
rx_hardware_offset_default_s: float = 0.26
tune_power_w: int = 10
```

### B. FlexRadio explizit (Regression-Anker)

`radio/flexradio.py` nach Z.38 (`radio_type: str = "flexradio"`):

```python
tx_buffer_s: float = 1.3
rx_hardware_offset_default_s: float = 0.26
tune_power_w: int = 10
```

Werte = exakt die heutigen FlexRadio-Konstanten. **Keine
Verhaltensänderung** für FlexRadio-User.

### C. Init-Reihenfolge fix (R1-Bug 2)

`ui/main_window.py:82-87` — Reihenfolge umdrehen:

```python
# Vorher (kaputt nach Refactor):
# self._init_core_components()
# self._init_qso_log()
# self._init_radio_state()
# ...

# Nachher:
self._init_radio_state()       # erstellt self.radio (nur settings-abh.)
self._init_core_components()   # baut Encoder mit self.radio.tx_buffer_s
self._init_qso_log()
self._init_diversity_state()
self._init_power_state()
```

`_init_radio_state` Z.250-259 braucht nur `self.settings` (kein
Encoder/Decoder/qso_sm) → safe vorne. Verifiziert in Code-Audit Schritt 0.

### D. Encoder zieht aus Radio (mit Settings-Override-Möglichkeit)

`ui/main_window.py:172` (`_init_core_components`):

```python
# Vorher:
# self.encoder = Encoder(1500, tx_buffer_s=settings.tx_buffer_s)

# Nachher:
tx_buffer = settings.get_user_tx_buffer_override()
if tx_buffer is None:
    tx_buffer = self.radio.tx_buffer_s
self.encoder = Encoder(1500, tx_buffer_s=tx_buffer)
```

Override-Logik vereinfacht nach R1-Verbesserung 5: **wenn User
explizit `radio_timing.tx_buffer_s` in config.json gesetzt hat, gewinnt
der → KISS, kein Default-Vergleich.** Voraussetzung: Migration in
Settings.load() popt die Default-gleichen Werte (siehe E).

`config/settings.py` — neue öffentliche Methode (R1-Risiko 4 — Settings
kapselt `_data`):

```python
def get_user_tx_buffer_override(self) -> Optional[float]:
    """User-Override für tx_buffer_s aus radio_timing-Block.

    Returns None wenn nicht explizit gesetzt (= Default soll vom Radio
    kommen). Returns float wenn User in config.json manuell einen Wert
    gepflegt hat.
    """
    val = self._data.get("radio_timing", {}).get("tx_buffer_s")
    return float(val) if val is not None else None

def get_user_rx_hardware_offset_override(self) -> Optional[float]:
    """Analog für rx_hardware_offset_default_s."""
    val = self._data.get("radio_timing", {}).get("rx_hardware_offset_default_s")
    return float(val) if val is not None else None
```

### E. Settings-Migration (R1-Bug 3 — präzise)

`config/settings.py:DEFAULTS`:

```python
# Vorher:
# "radio_timing": {
#     "tx_buffer_s": 1.3,
#     "rx_hardware_offset_default_s": 0.26,
# },

# Nachher:
"radio_timing": {},   # leer — Radio liefert Defaults, hier nur User-Overrides
```

`config/settings.py:load()` — Migration nach `self._data.update(saved)`:

```python
# P121: Default-gleiche radio_timing-Werte popen damit sie nicht
# fälschlich als User-Override gewertet werden. Bedingung: ALLE Keys
# müssen exakt den ehemaligen FlexRadio-Defaults entsprechen UND es
# dürfen keine zusätzlichen Keys im Block sein. Sobald ein Wert
# abweicht ODER ein neuer Key drin ist → Block bleibt erhalten
# (User wollte was anderes / wir kennen den Key nicht).
rt = self._data.get("radio_timing", {})
LEGACY_DEFAULTS = {"tx_buffer_s": 1.3, "rx_hardware_offset_default_s": 0.26}
if rt == LEGACY_DEFAULTS:
    self._data["radio_timing"] = {}
```

Property `Settings.tx_buffer_s` (Z.259-261, exakte Zeilen vor Edit
verifizieren — R1-Hinweis 7) kann **bleiben wie sie ist** (Fallback
1.3 für Aufrufer die noch nicht migriert sind) ODER **entfernt werden**.
**Entscheidung: entfernen**, alle Aufrufer migriert (Audit zeigt nur
einen Aufrufer in main_window.py:172 — der wird in D umgestellt).
Gleiches für `Settings.rx_hardware_offset_default_s`.

### F. rx_hardware_offset analog

`ui/main_window.py:167` (`_init_core_components`):

```python
# Vorher:
# _ntp.set_hardware_default(settings.rx_hardware_offset_default_s)

# Nachher:
rx_offset = settings.get_user_rx_hardware_offset_override()
if rx_offset is None:
    rx_offset = self.radio.rx_hardware_offset_default_s
_ntp.set_hardware_default(rx_offset)
```

### G. tune_power_w (R1-Risiko 6 — bewusst keine Settings-Override)

`ui/mw_tx.py:171`:

```python
# Vorher:
# TUNE_POWER_W = 10

# Nachher (in _tune_start, vor Verwendung):
tune_power = self.radio.tune_power_w
self.radio.set_rfpower_direct(tune_power)
self.radio.tune_on()
self.statusBar().showMessage(
    f"TUNEN — {tune_power}W auf ANT1 für {duration_s}s ...", 0)
```

Hartcodierte Konstante entfällt komplett. **Kein Settings-Override**
für TUNE-Power: Sicherheits-Charakter (Hardware-Schutz, hohe SWR
während Match-Search) — User soll nicht aus Versehen 50W als
TUNE-Power ins config.json schreiben können. Mike-Entscheidung im
Workflow.

### H. IC7300Interface (radio/ic7300.py, NEU)

```python
"""IC7300Interface — Stub für späteren CI-V-Fork.

Implementiert RadioInterface-Pattern als Duck-Type (kein Erbe von
RadioInterface, da FlexRadio den gleichen Pattern macht — siehe
P121-Architektur-Klarstellung).

Alle Hardware-Methoden raisen NotImplementedError. Class-Variables
sind gesetzt damit radio_factory + UI-Layer ohne Hardware-Connect
arbeiten können (z.B. radio.radio_name für Dialog-Titel).
"""

from __future__ import annotations
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal


def _not_implemented(method: str):
    raise NotImplementedError(
        f"IC-7300 {method}() noch nicht implementiert. "
        "Siehe TODO.md (P121) — Stubs vorhanden, CI-V-Protokoll fehlt."
    )


class IC7300Interface(QObject):
    """Stub-Klasse für späteren IC-7300 CI-V + USB-Audio Fork.

    Hardware-Konstanten sind Schätzungen (USB-Audio, kein VITA-49) —
    beim echten Fork zwingend per Messung validieren!
    """

    # Radio-Identität
    radio_type: str = "ic7300"

    # Hardware-Konstanten — Schätzungen, beim Fork validieren
    tx_buffer_s: float = 0.5
    rx_hardware_offset_default_s: float = 0.10
    tune_power_w: int = 10

    # Signals (kompatibel zu FlexRadio-Erwartung)
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        # Bewusst keine Hardware-Anfassung im Konstruktor!
        self.ip = ""    # für Code-Pfade die ip-presence prüfen
        self.last_swr = 1.0

    @property
    def radio_name(self) -> str:
        return "IC-7300"

    @property
    def supports_diversity(self) -> bool:
        # IC-7300 hat 1 Antennenbuchse → keine Diversity
        return False

    def get_antennas(self) -> list[str]:
        return ["ANT1"]

    # ── Stubs für alle Hardware-Methoden ────────────────────────

    def connect(self) -> bool:                       _not_implemented("connect")
    def disconnect(self) -> None:                    _not_implemented("disconnect")
    @property
    def is_connected(self) -> bool:                  return False
    def set_frequency(self, freq_hz: int) -> bool:   _not_implemented("set_frequency")
    def get_frequency(self) -> Optional[int]:        _not_implemented("get_frequency")
    def set_mode(self, mode: str) -> bool:           _not_implemented("set_mode")
    def set_ptt(self, active: bool) -> bool:         _not_implemented("set_ptt")
    def set_tx_power(self, watts: int) -> bool:      _not_implemented("set_tx_power")
    def set_antenna(self, antenna: str) -> bool:     _not_implemented("set_antenna")
    def get_rx_audio_callback(self) -> Optional[Callable]: _not_implemented("get_rx_audio_callback")
    def send_audio(self, pcm_data: bytes) -> bool:   _not_implemented("send_audio")
    def get_meter_data(self) -> dict:                _not_implemented("get_meter_data")
    def set_rx_antenna(self, ant: str) -> None:      _not_implemented("set_rx_antenna")
    def set_tx_antenna(self, ant: str) -> None:      _not_implemented("set_tx_antenna")
    def set_rfgain(self, gain: int) -> None:         _not_implemented("set_rfgain")
```

### I. IC7100Interface (radio/ic7100.py, NEU)

Strukturell **identisch** zu IC7300Interface, abweichend nur:
- `radio_type = "ic7100"`
- `radio_name` returnt `"IC-7100"`
- Error-Message in `_not_implemented` mit "IC-7100" statt "IC-7300"

Gemeinsame Basis-Klasse `ICCivBase` **bewusst nicht jetzt** — beim
echten Fork wird sich zeigen was gemeinsam ist (DRY too early ist
Premature Optimization).

### J. radio_factory.create_radio erweitern

`radio/radio_factory.py`:

```python
def create_radio(settings: "Settings"):
    radio_type = settings.get("radio_type", "flex")

    if radio_type in ("flex", "flexradio"):
        from radio.flexradio import FlexRadio
        return FlexRadio(
            ip=settings.get("flexradio_ip", ""),
            port=settings.get("flexradio_port", 4992),
        )

    if radio_type == "ic7300":
        from radio.ic7300 import IC7300Interface
        return IC7300Interface()

    if radio_type == "ic7100":
        from radio.ic7100 import IC7100Interface
        return IC7100Interface()

    raise ValueError(f"Unbekannter radio_type: {radio_type!r}. "
                     f"Gültige Typen: 'flex'/'flexradio', 'ic7300', 'ic7100'")
```

### K. connect_status_dialog parametrisiert

`ui/connect_status_dialog.py:60` Konstruktor:

```python
def __init__(self, parent=None, app_version: str = "",
             radio_name: str = "Radio"):
    ...
    self.setWindowTitle(f"{radio_name} wird verbunden")
```

Z.134:

```python
title = QLabel(f"{radio_name} wird verbunden")
```

`ui/mw_radio.py:87` Aufrufer:

```python
self._connect_dialog = ConnectStatusDialog(
    self, app_version=APP_VERSION,
    radio_name=self.radio.radio_name,
)
```

### L. config/settings.py Doku

Z.67 Kommentar:

```python
"radio_type": "flex",  # "flex"/"flexradio" = FlexRadio SmartSDR
                        # "ic7300" / "ic7100" = CI-V (Stubs — siehe TODO P121)
```

### M. Alle 1806 Tests bleiben grün

Tests die `settings.tx_buffer_s` / `settings.rx_hardware_offset_default_s`
direkt benutzen müssen ggf. angepasst werden — Audit-Befund:

```bash
grep -rn "settings\.tx_buffer_s\|settings\.rx_hardware_offset_default_s\|\.tx_buffer_s\b" tests/ 2>/dev/null
```

Vor Code-Start ausführen, Treffer migrieren.

### N. Neue Tests (~20 Tests)

T1-T2 `tests/test_radio_interface_defaults.py` (2 Tests):
- `test_abc_defaults` — ABC liefert 1.3/0.26/10 als Fallback
- `test_subclass_can_override` — Dummy-Subclass mit eigenen Werten

T3-T5 `tests/test_flexradio_constants.py` (3 Tests):
- `test_flexradio_tx_buffer` — 1.3
- `test_flexradio_rx_hardware_offset` — 0.26
- `test_flexradio_tune_power` — 10

T6-T11 `tests/test_ic7300_stub.py` (6 Tests):
- `test_instantiation_no_hardware` — `IC7300Interface()` läuft ohne Exception
- `test_radio_type` — `radio_type == "ic7300"`
- `test_radio_name` — `radio_name == "IC-7300"`
- `test_supports_diversity_false` — False
- `test_antennas_single` — `["ANT1"]`
- `test_connect_raises_not_implemented` — Message enthält "P121" und "IC-7300"

T12-T17 `tests/test_ic7100_stub.py` (6 Tests): analog T6-T11

T18-T21 `tests/test_radio_factory.py` (4 Tests):
- `test_create_flex_legacy` — radio_type="flex" → FlexRadio
- `test_create_flex_explicit` — radio_type="flexradio" → FlexRadio
- `test_create_ic7300` — radio_type="ic7300" → IC7300Interface (kein Raise!)
- `test_create_ic7100` — radio_type="ic7100" → IC7100Interface
- `test_create_unknown_raises` — radio_type="unknown" → ValueError

T22 `tests/test_settings_radio_timing_migration.py` (3 Tests):
- `test_legacy_defaults_popped` — alter `radio_timing={1.3, 0.26}` → leerer Dict nach load()
- `test_user_override_kept` — `{1.5, 0.26}` (abweichend) → bleibt erhalten
- `test_unknown_key_keeps_block` — `{tx_buffer_s: 1.3, foo: bar}` → bleibt erhalten

T23 `tests/test_settings_overrides.py` (2 Tests):
- `test_no_override_returns_none` — leerer radio_timing → get_user_tx_buffer_override() == None
- `test_user_override_returns_value` — {1.5} → 1.5

T24 Regression: `QT_QPA_PLATFORM=offscreen pytest tests/ -q` grün.

## 3. Betroffene Dateien (mit verifizierten Zeilen)

| Datei | Zeile | Änderung | Δ LOC |
|---|---|---|---|
| `radio/base_radio.py` | nach 27 | 3 Class-Variables | +5 |
| `radio/flexradio.py` | nach 38 | 3 Class-Variables | +3 |
| `radio/ic7300.py` | NEU | Stub-Klasse | +110 |
| `radio/ic7100.py` | NEU | Stub-Klasse | +110 |
| `radio/radio_factory.py` | 24-51 | IC-Stubs einreihen | +10 -3 |
| `ui/main_window.py` | 82-87 | Init-Reihenfolge | +0 |
| `ui/main_window.py` | 167 | rx_offset Helper | +3 |
| `ui/main_window.py` | 172 | tx_buffer Helper | +3 |
| `ui/mw_tx.py` | 171, 201, 205, 208 | TUNE_POWER_W → radio | +0 -1 |
| `ui/mw_radio.py` | 87 | Dialog-radio_name | +1 |
| `ui/connect_status_dialog.py` | 60, 71, 134 | Param + Strings | +2 |
| `config/settings.py` | 67 | Kommentar | +1 |
| `config/settings.py` | 75-78 | radio_timing leer | +0 -3 |
| `config/settings.py` | load() | Migration | +6 |
| `config/settings.py` | 259-261 | tx_buffer_s Property entfernen | -7 |
| `config/settings.py` | NEU | get_user_*_override() | +10 |
| Tests x6 | NEU | 24 Tests | +180 |
| **Summe** | | | **+434 / -14** |

## 4. Randbedingungen

- **CLAUDE.md Hardware-Pflicht ANT1=TX:** IC-Stubs haben
  `get_antennas()==["ANT1"]` + `supports_diversity==False` → automatisch
  konform.
- **Threading:** keine Änderung. Stubs sind no-op.
- **Persistence:** `rf_preset_store.json` unverändert (Keys
  `"ic7300"`/`"ic7100"` kommen automatisch wenn echter Fork schreibt).
- **Backward-Compat:** P48-User mit explizit gepflegtem `radio_timing`
  abweichend vom Default → ihre Werte bleiben als User-Override aktiv.
- **Tests-Pflicht:** `QT_QPA_PLATFORM=offscreen pytest tests/ -q` grün.
- **Stubs no-op-sicher:** `IC7300Interface().__init__()` und
  `IC7100Interface().__init__()` dürfen keine Hardware-Anfassung
  (kein Serial, kein USB-Audio-Open).

## 5. Nicht im Scope

- CI-V-Protokoll-Implementierung
- USB-Audio-Backend (sounddevice)
- UI-Anpassungen für „Diversity-Kacheln ausblenden wenn
  !supports_diversity" → separates Ticket P122 wenn IC echt kommt
- `flexradio.py` (1528 LOC) aufsplitten — Variante C, premature
- IC-Tuner-Logik
- Settings-UI für Radio-Type-Auswahl
- Print-String `[FlexRadio]` → `[{radio_name}]` in mw_radio.py (Kosmetik)
- `_DT_OFFSETS` in `decoder.py:483` (WSJT-X-Protokoll)
- `main_window.py:340` `radio="flexradio"` Migration-Code
- VHF/UHF-Bänder für IC-7100
- FlexRadio von ABC erben lassen (Metaclass-Hell QObject+ABC, eigenes
  Ticket bei Bedarf)
- ICCivBase gemeinsame Basis-Klasse (premature DRY)

## 6. Testbarkeit — siehe N (24 Tests)

## R1-Findings — Bilanz

| # | R1-Severity | Status | Wie adressiert |
|---|---|---|---|
| 1 | 🔴 Bug | Adressiert (Architektur-Klarstellung) | Class-Variables redundant in jeder Subclass, ABC nur Dokumentations-Vertrag. KEIN Multi-Inheritance-Refactor jetzt. |
| 2 | 🔴 Bug | Adressiert (Init-Reihenfolge) | `_init_radio_state` VOR `_init_core_components`. Code-Audit bestätigt: keine echte Abhängigkeit. |
| 3 | 🔴 Bug | Adressiert (Migration-Spec präzise) | Exakte Bedingung: `radio_timing == {tx_buffer_s: 1.3, rx_hardware_offset_default_s: 0.26}` (komplett-gleich) → pop. Sonst beibehalten. |
| 4 | 🟠 Risiko | Adressiert (Settings-Methoden) | `get_user_tx_buffer_override()` + `get_user_rx_hardware_offset_override()` kapseln `_data`-Zugriff. |
| 5 | 🟡 Verbesserung | Übernommen | Override-Logik vereinfacht zu „if not None: return". |
| 6 | 🟠 Risiko | Abgelehnt (Begründung) | TUNE-Power ist Hardware-Sicherheit. Kein Settings-Override aus Versehens-Schutz. Mike-Entscheidung. |
| 7 | ⚪ Hinweis | Adressiert | Zeilenangaben in V3 per Code-Audit verifiziert (config/settings.py 259-261 — falls Edit-Zeit veraltet, vor Edit nochmal grep). |
| 8 | ⚪ Hinweis | Adressiert | IC-Stubs setzen `supports_diversity` explizit als Property (für Lese-Klarheit, marginale Redundanz akzeptiert). |
| 9 | 🟡 Verbesserung | Adressiert (Settings-Kapselung) | Override-Logik komplett in Settings — Helper im main_window wird trivial (3 Zeilen if/return). |

**Halluzination-Check:** keine Halluzinationen in R1-Findings — alle
9 Findings sind im Code verifizierbar oder valide Architektur-Kritik.

## Implementierungs-Reihenfolge (atomare Commits)

1. **Commit 1:** ABC + FlexRadio Class-Variables (B+A) — Regression-Anker
2. **Commit 2:** IC7300 + IC7100 Stubs (H+I) — neue Files isoliert
3. **Commit 3:** radio_factory erweitern (J)
4. **Commit 4:** Settings Migration + Helper-Methoden (E)
5. **Commit 5:** Init-Reihenfolge + Encoder/rx_offset Migration (C+D+F)
6. **Commit 6:** TUNE_POWER_W Migration (G)
7. **Commit 7:** Dialog-Parametrisierung (K)
8. **Commit 8:** Tests (N) — alle 24 in einem Commit-Block oder pro Datei
9. **Commit 9:** Doku-Updates (HISTORY, HANDOFF, CLAUDE, TODO)

Push nur auf explizite Mike-Freigabe.
