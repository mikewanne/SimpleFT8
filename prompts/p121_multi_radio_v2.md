Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P121 V2 — Radio-Hardware-Konstanten ans Radio binden + IC-7300/IC-7100 Stubs

## Kontext (Lesehilfe für dich, nicht Teil der Aufgabe)

SimpleFT8 (Python/PySide6 Desktop-App, ~1806 Tests) ist ein Hobby-FT8-
Tool für einen Operator mit FlexRadio 8400M. Mike will jetzt IC-7300 UND
IC-7100 als spätere Forks integrieren. Diese Änderung ist die **Plumbing-
Vorbereitung** — keine echte CI-V-Implementierung, nur die Verlagerung
von Hardware-Konstanten und das Anlegen von Stub-Klassen.

Vorarbeit existiert:
- `radio/base_radio.py` — saubere ABC `RadioInterface` mit ~30 Methoden
  und Properties `radio_type`, `radio_name`, `supports_diversity`.
- `radio/radio_factory.py` — Factory mit Slot für `"ic7300"` (heute
  NotImplementedError-Raise).
- P48 hat `tx_buffer_s` (1.3) + `rx_hardware_offset_default_s` (0.26)
  aus dem Code in Settings (`radio_timing`-Block) parametrisiert.
- `ui/mw_tx.py:61` nutzt schon `self.radio.radio_type` als
  rf_preset_store-Key (kein Hardcode mehr dort).
- `_DT_OFFSETS` in `core/decoder.py:483` ist WSJT-X-Protokoll +
  Wake-Offset, NICHT FlexRadio-spezifisch — bleibt unverändert.

## 1. Ziel

Hardware-Konstanten von Settings/hartcodiert zur `RadioInterface`-
Hierarchie verschieben. IC-7300 + IC-7100 als Stub-Klassen anlegen
damit der spätere echte Fork nur noch eine `radio/ic*.py`-Datei + die
CI-V-Implementierung braucht, kein Eingriff in `core/`, `ui/`, `config/`.

## 2. Akzeptanzkriterien

A. **ABC-Erweiterung:** `RadioInterface` bekommt drei Class-Variables
   mit Default-Werten (KISS — keine `@property`, keine abstract):
   ```python
   tx_buffer_s: float = 1.3
   rx_hardware_offset_default_s: float = 0.26
   tune_power_w: int = 10
   ```

B. **FlexRadio explizit:** `FlexRadio`-Klasse setzt die drei Class-
   Variables explizit mit den heutigen Werten (Regression-Schutz, kein
   Verhaltens-Unterschied):
   ```python
   class FlexRadio(RadioInterface):
       radio_type = "flexradio"
       tx_buffer_s = 1.3
       rx_hardware_offset_default_s = 0.26
       tune_power_w = 10
   ```
   `radio_type = "flexradio"` ist heute schon irgendwo gesetzt
   (`mw_tx.py:61` liest `self.radio.radio_type`) — prüfen und ggf.
   konsolidieren.

C. **Encoder zieht aus Radio statt Settings:**
   - Heute (`ui/main_window.py:172`):
     ```python
     self.encoder = Encoder(1500, tx_buffer_s=settings.tx_buffer_s)
     ```
   - Neu:
     ```python
     self.encoder = Encoder(1500, tx_buffer_s=self.radio.tx_buffer_s)
     ```
   - Plus Override-Pfad: wenn User in `config.json` explizit
     `radio_timing.tx_buffer_s` != Radio-Default gesetzt hat → User-Wert
     gewinnt. Implementierung über Helper-Function in `main_window`:
     ```python
     def _resolve_tx_buffer(self) -> float:
         user_override = self.settings._data.get("radio_timing", {}).get("tx_buffer_s")
         if user_override is not None and user_override != self.radio.tx_buffer_s:
             return float(user_override)
         return self.radio.tx_buffer_s
     ```
   - DEFAULTS in `config/settings.py` wird angepasst:
     `radio_timing` kommt als leerer Dict `{}` statt mit gefüllten
     Werten — Radio liefert Defaults, Settings nur für User-Overrides.
   - Migration in `settings.load()`: bestehende `radio_timing`-Einträge
     mit den FlexRadio-Defaults (1.3 / 0.26) → silent gepopt (analog
     P104-Migration für `power_watts`).

D. **rx_hardware_offset_default analog:** `main_window._init_core_components`
   (Z. 316-322, wo `set_hardware_default(...)` gerufen wird) — Quelle
   wechseln von `settings.rx_hardware_offset_default_s` auf
   `self.radio.rx_hardware_offset_default_s` mit gleicher
   Override-Logik.

E. **tune_power_w:** `mw_tx.py:171` hartcodiertes `TUNE_POWER_W = 10`
   ersetzen durch `self.radio.tune_power_w`. KEIN Settings-Override
   (zu hardware-nah, Sicherheits-Charakter).

F. **IC7300Interface (radio/ic7300.py, NEU):**
   - Erbt von `RadioInterface`
   - Class-Variables:
     ```python
     radio_type = "ic7300"
     tx_buffer_s = 0.5    # Schätzung USB-Audio (bei echtem Fork vermessen!)
     rx_hardware_offset_default_s = 0.10  # Schätzung
     tune_power_w = 10
     ```
   - `@property radio_name` returnt `"IC-7300"`
   - `@property supports_diversity` returnt `False` (überschreibt
     ABC-Default der `len(get_antennas()) >= 2` rechnet)
   - `get_antennas()` returnt `["ANT1"]` (eine Buchse)
   - Alle anderen ABC-Methoden raisen `NotImplementedError` mit
     gemeinsamer Helper-Message:
     ```python
     raise NotImplementedError(
         "IC-7300 Interface noch nicht implementiert. "
         "Siehe TODO.md (P121) und multiband.md."
     )
     ```

G. **IC7100Interface (radio/ic7100.py, NEU):** analog F mit
   `radio_type = "ic7100"`, `radio_name = "IC-7100"`, gleichen
   Hardware-Schätzungen, gleicher NotImplementedError-Pattern. Beide
   Stubs sollen sich strukturell exakt gleichen — wenn der Fork
   kommt, kann man via gemeinsamer Helper-Klasse zusammenfassen.

H. **radio_factory.create_radio erweitern:**
   - `"flex"` oder `"flexradio"` → FlexRadio (existiert)
   - `"ic7300"` → IC7300Interface()  (statt NotImplementedError)
   - `"ic7100"` → IC7100Interface()  (NEU)
   - Unbekannt → ValueError (wie heute)

I. **connect_status_dialog parametrisiert:**
   - Konstruktor neuer optionaler Param `radio_name: str = "Radio"`.
   - Window-Titel + Header-Label nutzen diesen Wert.
   - Aufruf in `mw_radio.py:87`:
     `ConnectStatusDialog(self, app_version=APP_VERSION,
                          radio_name=self.radio.radio_name)`

J. **config/settings.py:67** Kommentar erweitern auf alle drei Typen.

K. **Alle 1806 bestehenden Tests bleiben grün.**

L. **Neue Tests (~20 Tests total):**
   - `tests/test_radio_interface_defaults.py` (3 Tests): ABC liefert
     1.3/0.26/10
   - `tests/test_flexradio_constants.py` (3 Tests): FlexRadio überschreibt
     mit denselben Werten (Regression-Anker)
   - `tests/test_ic7300_stub.py` (5 Tests): Instanziation, Properties,
     `connect()` raised NotImplementedError, `supports_diversity==False`,
     `get_antennas()==["ANT1"]`
   - `tests/test_ic7100_stub.py` (5 Tests): analog
   - `tests/test_radio_factory.py` (4 Tests): alle drei Typen +
     Unbekannt-Fall

## 3. Betroffene Module/Dateien (mit echten Zeilen-Verweisen)

- `radio/base_radio.py` — nach Zeile 27 (`radio_type = "unknown"`) drei
  Class-Variables ergänzen (~5 LOC).
- `radio/flexradio.py` — Klasse `FlexRadio` Class-Variables setzen
  (~5 LOC, vermutlich nach `radio_type`-Zeile, falls vorhanden — sonst
  oben ergänzen).
- `radio/ic7300.py` — NEU, ~80 LOC.
- `radio/ic7100.py` — NEU, ~80 LOC.
- `radio/radio_factory.py:43-48` — IC-7300 NotImplementedError-Raise
  durch Instanziation ersetzen, IC-7100-Zweig ergänzen.
- `core/encoder.py:50-57` — keine Änderung am Encoder selbst, der
  Param-Default 1.3 bleibt als Notfall-Fallback wenn Caller nichts
  übergibt. Änderung passiert in `main_window.py`.
- `ui/main_window.py:171-172` — Helper `_resolve_tx_buffer()` aufrufen
  vor Encoder-Init. Helper neu ergänzen.
- `ui/main_window.py:316-322` (`_init_core_components`) — analog
  Helper `_resolve_rx_hardware_offset()` für `set_hardware_default(...)`.
- `ui/mw_tx.py:171` — `TUNE_POWER_W = 10` → `self.radio.tune_power_w`.
- `ui/mw_radio.py:87` — Dialog-Konstruktor-Aufruf ergänzen um
  `radio_name=self.radio.radio_name`.
- `ui/connect_status_dialog.py:60` `__init__`-Signatur + Z.71+134
  Strings parametrisieren.
- `config/settings.py:67` Kommentar.
- `config/settings.py:75-78` (DEFAULTS["radio_timing"]) — Werte auf
  leeren Dict (`{}`) reduzieren oder ganz raus. Migration in
  `load()` ergänzen die alte Default-Einträge popt.
- `config/settings.py:259-261` Property `tx_buffer_s` — Verhalten
  ändern: returnt jetzt `None` wenn nicht im Dict (statt 1.3-Default).
  Aufrufer (`main_window`) prüft auf None und fragt dann das Radio.
- `tests/test_radio_interface_defaults.py` — NEU.
- `tests/test_flexradio_constants.py` — NEU.
- `tests/test_ic7300_stub.py` — NEU.
- `tests/test_ic7100_stub.py` — NEU.
- `tests/test_radio_factory.py` — NEU.

## 4. Randbedingungen

- **CLAUDE.md Hardware-Pflicht:** ANT1=TX, ANT2 nie TX. IC-7300/7100
  haben nur 1 Antennen-Buchse, `supports_diversity=False`, `get_antennas
  ()=["ANT1"]`. Die ANT1-Pflicht wird damit automatisch eingehalten.
- **Threading:** keine Änderung. Stubs werden nie threaded benutzt
  bevor echter Fork kommt.
- **Persistence:** `rf_preset_store.json` Format unverändert. Beim
  ersten echten IC-Fork würden neue Top-Level-Keys `"ic7300"`/`"ic7100"`
  dazukommen — kein Migration-Code nötig (`setdefault`-Pattern).
- **Settings-Migration:** kritisch — bestehende User haben
  `radio_timing={tx_buffer_s: 1.3, rx_hardware_offset_default_s: 0.26}`
  in ihrer `config.json` (P48-Defaults). Beim load() müssen diese
  Default-gleichen Werte gepopt werden, sonst gelten sie als
  User-Override und blockieren spätere Default-Änderungen.
- **Backward-Compat:** wer in `config.json` einen abweichenden Wert
  hat (z.B. `tx_buffer_s=1.4` für eigenen FlexRadio-Tuning) → bleibt
  als Override aktiv.
- **Tests-Pflicht:** `QT_QPA_PLATFORM=offscreen ./venv/bin/python3
  -m pytest tests/ -q` grün vor jedem Commit.
- **Stubs sind no-op-sicher:** `IC7300Interface().__init__()` darf
  keine Hardware ansprechen (kein CI-V-Open, kein Serial-Port). Nur
  Class-Variables setzen.

## 5. Nicht im Scope

- CI-V-Protokoll-Implementierung (Modell-IDs 0x94/0x88, RS232-Frames)
- USB-Audio-Backend (sounddevice/PortAudio Integration)
- UI-Anpassungen für „Diversity-Kacheln ausblenden wenn
  !supports_diversity" — separates Ticket P122 wenn IC echt kommt
- `flexradio.py` (1528 LOC) aufsplitten — Variante C, premature
- IC-Tuner-Logik (AH-tune / AT-180)
- Settings-UI für Radio-Type-Auswahl im Settings-Dialog
- Print-String-Refactor `[FlexRadio]` → `[{radio_name}]` in mw_radio.py
  (pure Kosmetik, kein Wert für IC-Fork)
- `_DT_OFFSETS` in `decoder.py:483` (WSJT-X-Protokoll, NICHT
  FlexRadio-spezifisch)
- `main_window.py:340` `radio="flexradio"` (Migration-Code aus
  alter FlexRadio-only-Settings, kein Refactor)
- VHF/UHF-Bänder für IC-7100 (kommt erst beim echten CI-V-Fork)

## 6. Testbarkeit

Pflicht-Tests:

T1 `test_radio_interface_defaults.py::test_defaults_values`
   ABC liefert `tx_buffer_s==1.3`, `rx_hardware_offset_default_s==0.26`,
   `tune_power_w==10`.

T2 `test_radio_interface_defaults.py::test_can_be_overridden_by_subclass`
   Dummy-Subclass mit `tx_buffer_s = 0.7` → Property liefert 0.7.

T3 `test_flexradio_constants.py::test_flexradio_keeps_legacy_values`
   `FlexRadio.tx_buffer_s == 1.3` und gleiche Regression für die zwei
   anderen Konstanten. Anker gegen versehentliche Änderung.

T4 `test_ic7300_stub.py::test_instantiation_no_hardware_access`
   `IC7300Interface()` läuft ohne Exception, ohne Serial-Port-Open.

T5 `test_ic7300_stub.py::test_properties`
   `radio_type=="ic7300"`, `radio_name=="IC-7300"`,
   `supports_diversity==False`, `get_antennas()==["ANT1"]`.

T6 `test_ic7300_stub.py::test_connect_raises_not_implemented`
   `connect()` raised `NotImplementedError` mit Message enthält "P121".

T7 `test_ic7300_stub.py::test_hardware_constants_set`
   `tx_buffer_s=0.5`, `tune_power_w=10` (Anker).

T8 `test_ic7100_stub.py` — analog T4-T7.

T9 `test_radio_factory.py::test_create_flex` — alt "flex" + neu
   "flexradio" beide → FlexRadio.

T10 `test_radio_factory.py::test_create_ic7300` — radio_type "ic7300"
    → IC7300Interface (kein NotImplementedError mehr).

T11 `test_radio_factory.py::test_create_ic7100` — analog.

T12 `test_radio_factory.py::test_unknown_raises_value_error` —
    "unknown" → ValueError.

T13 `test_main_window_encoder_uses_radio_buffer` (kann in bestehendes
    main_window-Test-File): main_window.encoder.target_tx_offset_s
    bleibt -0.8 wenn Radio FlexRadio und keine Override.

T14 Regression: alle 1806 Tests bleiben grün.

## Was ich (V1-Autor) bewusst entschieden habe (nicht challenged)

- **Class-Variables statt @property:** KISS, kein dynamisches Verhalten
  nötig. Subclasses überschreiben einfach Class-Variable.
- **Override-Logik per Helper im main_window:** nicht im Encoder
  selbst, damit Encoder testbar bleibt ohne Settings-Mock.
- **Stubs raisen NotImplementedError mit klarer Message inkl. P121-
  Verweis:** macht Debugging beim echten Fork einfacher.
- **Helper-Klasse `ICCivBase` für 7300+7100 NICHT jetzt:** premature,
  beim echten Fork wird sich zeigen was wirklich gemeinsam ist.
- **`tx_buffer_s = 0.5` für IC ist Schätzung:** Kommentar in IC-Stubs
  notiert, beim Fork zwingend zu vermessen.
- **`rf_preset_store.migrate_from_settings(radio="flexradio", ...)`
  bleibt hartcodiert:** Migration nur einmal aus FlexRadio-only-Zeit,
  kein Refactor-Wert.
