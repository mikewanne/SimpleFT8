# P121 V1 — Radio-Hardware-Konstanten ans Radio binden + IC-7300/IC-7100 Stubs

## 1. Ziel

SimpleFT8 ist auf FlexRadio zugeschnitten, aber die Architektur ist
bereits halb-vorbereitet für andere Radios (`RadioInterface` ABC,
`radio_factory`, P48 hat `tx_buffer_s` parametrisiert). Mike will
**definitiv** IC-7300 UND IC-7100 als Forks integrieren — beide
CI-V-basiert, beide single-Antenne, beide ohne Diversity.

Variante A (Minimal-Refactor, ohne Hardware-Implementierung): die
Plumbing so vorbereiten dass der spätere IC-Fork nur eine neue
`radio/ic*.py`-Datei + Modell-Konstanten benötigt, kein Eingriff
mehr in `core/`, `ui/` oder `config/`.

**Konkret:**
- Radio-Hardware-Konstanten (TX-Buffer, RX-Hardware-Latenz-Default,
  TUNE-Leistung) wandern von Settings/hartcodiert zu `RadioInterface`-
  Properties. Settings bleibt als optionaler User-Override.
- `IC7300Interface` + `IC7100Interface` als Stub-Klassen, alle Methoden
  `NotImplementedError("…")` mit klarer Fehlermeldung.
- `radio_factory` instanziert Stubs (statt NotImplementedError-Raise).
- Hartcodierte „FlexRadio"-Strings im UI parametrisiert über `radio_name`.

## 2. Akzeptanzkriterien

1. `RadioInterface` hat drei neue Class-Properties mit Defaults:
   - `tx_buffer_s: float = 1.3` (Override per Subclass)
   - `rx_hardware_offset_default_s: float = 0.26`
   - `tune_power_w: int = 10`
2. `FlexRadio` setzt explizit `tx_buffer_s = 1.3`,
   `rx_hardware_offset_default_s = 0.26`, `tune_power_w = 10` als
   Class-Variables (= heutige Werte, kein Verhaltensunterschied).
3. `Encoder.__init__` zieht `tx_buffer_s` aus Radio statt Settings.
   Settings-Override-Pfad bleibt: wenn `settings.tx_buffer_s` aus
   `radio_timing`-Block gesetzt und != Radio-Default → User-Override
   gewinnt (für Power-User die experimentieren).
4. `main_window._init_core_components` zieht
   `rx_hardware_offset_default_s` aus Radio statt Settings (gleiche
   Override-Logik).
5. `mw_tx.py:171` `TUNE_POWER_W = 10` wird zu `self.radio.tune_power_w`.
6. `IC7300Interface` und `IC7100Interface` existieren als Stub-Klassen
   in `radio/ic7300.py` und `radio/ic7100.py`. Alle ABC-Methoden mit
   `raise NotImplementedError("IC-7300/IC-7100 Interface nicht
   implementiert — siehe TODO.md")`. Class-Properties gesetzt:
   - `radio_type = "ic7300"` / `"ic7100"`
   - `radio_name = "IC-7300"` / `"IC-7100"`
   - `supports_diversity = False` (Property überschrieben)
   - `tx_buffer_s = 0.5` (Schätzung USB-Audio — wird beim echten Fork
     vermessen)
   - `tune_power_w = 10`
7. `radio_factory.create_radio` instanziiert IC-Stubs (statt NotImplemented-
   Raise). Beim erstmaligen Methoden-Aufruf raisen die Stubs sauber.
8. `config/settings.py:67` Kommentar erweitert: `"ic7300"`/`"ic7100"`
   beide gültig.
9. `ui/connect_status_dialog.py` Dialog-Titel + Header verwenden
   `radio_name` statt hartcodiert „FlexRadio". Fallback wenn keine
   Radio-Instanz da: „Radio wird verbunden".
10. Alle 1806 bestehenden Tests bleiben grün.
11. Neue Tests:
    - `test_radio_interface_defaults.py` — Defaults auf ABC korrekt
    - `test_flexradio_constants.py` — FlexRadio liefert die heutigen
      Werte (Regression-Schutz)
    - `test_ic7300_stub.py` — Stub kann instanziiert werden,
      Property-Read funktioniert, Methoden-Call raised NotImplementedError
    - `test_ic7100_stub.py` — analog
    - `test_radio_factory.py` — Factory instanziiert alle drei Typen

## 3. Betroffene Module/Dateien

- `radio/base_radio.py` — Properties ergänzen (+15 LOC)
- `radio/flexradio.py` — Class-Variables explizit setzen (+5 LOC)
- `radio/ic7300.py` — NEU, ~80 LOC Stub
- `radio/ic7100.py` — NEU, ~80 LOC Stub
- `radio/radio_factory.py` — IC-Stubs einreihen (~10 LOC)
- `core/encoder.py:50-57` — `tx_buffer_s` Default-Source ändern (+3 LOC)
- `ui/main_window.py:171-172` — `tx_buffer_s` aus Radio statt Settings
- `ui/main_window.py:316-322` (`_init_core_components`) —
  `rx_hardware_offset_default_s` aus Radio
- `ui/mw_tx.py:171` — `TUNE_POWER_W=10` durch `self.radio.tune_power_w`
- `ui/connect_status_dialog.py:71,134` — Dialog-Strings parametrisieren
- `config/settings.py:67` — Kommentar ergänzen
- `tests/test_radio_interface_defaults.py` — NEU, 4 Tests
- `tests/test_flexradio_constants.py` — NEU, 3 Tests
- `tests/test_ic7300_stub.py` — NEU, 5 Tests
- `tests/test_ic7100_stub.py` — NEU, 5 Tests
- `tests/test_radio_factory.py` — NEU oder ergänzt, 3 Tests

## 4. Randbedingungen

- **CLAUDE.md Hardware-Pflicht:** ANT1=TX, ANT2 niemals TX. Diese
  Eigenschaft ist Antennen-Modell (radio.supports_diversity +
  set_tx_antenna), nicht von dieser Änderung betroffen — aber
  IC-7300/IC-7100 Stubs müssen `supports_diversity = False` setzen.
- **Threading:** keine Änderung am Threading-Modell, kein Lock-Eingriff.
- **Persistence:** `rf_preset_store.json` Format unverändert (Top-Level-
  Key `"flexradio"` bleibt, neue Keys `"ic7300"`/`"ic7100"` kommen
  automatisch dazu wenn ein IC-Stub später Werte speichert).
- **Settings-Migration:** keine. Bestehende `radio_timing`-Werte werden
  weiter als User-Override gelesen.
- **Tests:** `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest
  tests/ -q` muss grün bleiben.

## 5. Nicht im Scope

- CI-V-Protokoll-Implementierung (TCP-Serial-Befehle, Modell-IDs 0x94/0x88)
- USB-Audio-Backend (sounddevice/PortAudio)
- UI-Anpassungen für „Diversity-Kacheln ausblenden wenn
  !supports_diversity" — das ist Variante B (separate Ticket P122)
- `flexradio.py` (1528 LOC) aufsplitten — das ist Variante C, premature
- IC-7300-Tuner-Logik (AH-tune oder externer AT-180)
- Settings-UI-Aufweitung für Radio-Type-Auswahl im Settings-Dialog
- Print-String-Refactor `[FlexRadio]` → `[{radio_name}]` in `mw_radio.py`
  (Kosmetik, kein echter Wert)
- `_DT_OFFSETS` in `decoder.py:483` — WSJT-X-Protokoll, NICHT FlexRadio-
  spezifisch
- `main_window.py:340` `radio="flexradio"` Migration-Code — Migration aus
  alten FlexRadio-only-Settings, kein Refactor nötig

## 6. Testbarkeit

**Unverzichtbar:**

T1: `test_radio_interface_defaults.py::test_defaults_values` — ABC liefert
1.3 / 0.26 / 10
T2: `test_flexradio_constants.py::test_flexradio_overrides_defaults` —
FlexRadio liefert genau 1.3 / 0.26 / 10 (Regression: garantiert keine
Verhaltensänderung)
T3: `test_ic7300_stub.py::test_instantiation` — IC7300Interface() läuft
ohne Fehler
T4: `test_ic7300_stub.py::test_properties` — radio_type=="ic7300",
supports_diversity==False, tx_buffer_s definiert
T5: `test_ic7300_stub.py::test_method_raises_not_implemented` —
connect() raised NotImplementedError mit klarer Message
T6: `test_radio_factory.py::test_factory_creates_all_three` — Factory
liefert FlexRadio / IC7300 / IC7100 je nach radio_type
T7: `test_encoder_uses_radio_buffer.py` — Encoder mit Radio-Instanz
zieht `radio.tx_buffer_s`, target_tx_offset_s rechnet korrekt
T8: Regression: alle 1806 Tests bleiben grün

## Self-Review-Hinweise (V1 → V2 Schritt 1b)

**Was ich noch nicht gut habe in V1:**

- **A1 Settings-Override-Logik:** Ich habe „wenn Settings != Radio-Default
  → User-Override gewinnt" geschrieben — aber wie erkenne ich
  „User-Override"? Wenn der User die Default-Werte explizit in
  `radio_timing` lässt, sieht das wie Override aus. Saubere Lösung:
  `radio_timing`-Block ist standardmäßig **leer** im DEFAULTS-Dict; nur
  wenn User ihn füllt (manuelle config.json-Edit oder Settings-UI),
  greift Override. Heutige Defaults (1.3/0.26) wandern aus DEFAULTS
  raus → live nur via Radio.
- **A2 Migration:** Bestehende User haben aktuell `radio_timing={tx_buffer_s:
  1.3, rx_hardware_offset_default_s: 0.26}` in ihrer config.json (DEFAULTS
  von P48). Wenn diese Werte == Radio-Default, würde Override-Logik sie
  als „User-Override gleich Default" auswerten — neutral. Aber wenn ich
  DEFAULTS leer mache, könnte alte config sie noch enthalten und als
  Override gelten. Migration: bei load() `radio_timing.tx_buffer_s ==
  1.3` und `rx_hardware_offset_default_s == 0.26` → pop (gleiche
  Migration-Logik wie P104).
- **A3 Connect-Dialog:** Hat heute den FlexRadio-Connect-Worker hartcodiert
  drin? Muss ich auch entkoppeln oder bleibt der Dialog nur Anzeige?
  → Code-Check nötig vor V2.
- **A4 IC7100 hat 144/430 MHz:** Bands-Setup in config/settings.py
  `BAND_FREQS` listet aktuell nur KW-Bänder + 6m. Wenn IC7100-User
  später VHF/UHF will, müsste das ergänzt werden. NICHT in dieser
  Variante A (kommt erst beim echten IC7100-Fork mit CI-V).
- **A5 tx_buffer_s=0.5 für IC ist Schätzung:** ohne Hardware-Messung
  riskant. Mike sollte den Wert bei IC-Erstkontakt validieren — als
  Kommentar in IC*-Stubs notieren.
- **A6 ABC-Pflicht-Properties:** sollten `tx_buffer_s` etc. als
  `@property` oder `Class-Variable` definiert sein? Class-Variable ist
  KISS-er und reicht (kein dynamisches Verhalten nötig). Property-Form
  wäre overengineered.
- **A7 Connect-Status-Dialog `radio_name`-Quelle:** Dialog wird VOR
  Radio-Connect angezeigt, also Radio-Instanz noch nicht voll
  initialisiert. Aber `radio_name` ist Class-Property (kein
  Connect-State-abhängig), funktioniert.
- **A8 Tests:** Should `test_radio_factory.py` schon existieren? → grep.
  Wenn ja: ergänzen statt neu schreiben.
- **A9 Encoder + Radio-Reference-Cycle:** wenn Encoder eine Radio-Instanz
  hält → schon heute? → ja, `self._radio` in Encoder.__init__ (Z.58).
  Aber `tx_buffer_s` wird nur einmal beim Init benutzt (Z. 57), danach
  ist `target_tx_offset_s` fest. Also: kein Live-Lookup nötig, wir
  setzen `tx_buffer_s` einmal vom Radio. → einfach.
