# R1-Review: OPT-53 — Settings-Typvalidierung beim Laden

DeepSeek-v4-pro als kritischer R1-Reviewer (V1→V2→R1→V3). Projekt **SimpleFT8**
(Hobby-Funker-Tool). Laufende **Optimierungs-Kampagne**: **KISS/Robustheit > Speed,
NUR Optimierung, KEINE Verhaltensänderung im Normalbetrieb.** Kein TX-Pfad berührt.

## Befund

`config/settings.py:load()` übernimmt geladene config.json-Werte **blind**:
```python
def load(self):
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            self._data.update(saved)          # <-- blind, jeder Typ
        except (json.JSONDecodeError, IOError):
            pass
    # ... dann diverse Migrationen (pop, tune_duration_s-Whitelist, band/mode-
    #     Override, radio_timing, bandpilot) ...
```
Eine von Hand verkorkste config.json (falscher Typ, z.B. `"flexradio_port": true`
oder `"callsign": 123`) wird übernommen → Folgefehler später.

`DEFAULTS` enthält nur die Typen **str / int / bool / dict** (alle Felder unten
sind eindeutig getypt; KEIN float). Außerhalb DEFAULTS gibt es **dynamische**
persistierte Keys: `tx_slot_lock`, `enabled_bands`, `normal_tx_freq_per_band`,
Preset-Strukturen (`self._data[key]` mit variablem key). Diese haben eigene
Getter/eigene Validierung und dürfen NICHT angetastet werden.

## V1/V2-Plan

Neue Methode, aufgerufen direkt nach `self._data.update(saved)` (vor den
Migrationen):
```python
def _validate_types(self):
    """Kritische Settings-Felder gegen ihren DEFAULTS-Typ absichern.

    Weicht ein geladener Wert vom Typ des Defaults ab → Default behalten.
    `type(x) is type(default)` (NICHT isinstance) unterscheidet bewusst bool
    von int — sonst ginge ein versehentliches `true` als Port/Zahl durch
    (isinstance(True, int) == True).
    """
    for key, default_val in DEFAULTS.items():
        if type(self._data.get(key)) is not type(default_val):
            print(f"[Settings] '{key}': Typ "
                  f"{type(self._data.get(key)).__name__} statt "
                  f"{type(default_val).__name__} → Default {default_val!r}")
            self._data[key] = default_val
```
- **Iteriert über `DEFAULTS`** (nicht über `saved`) → dynamische Keys
  (tx_slot_lock/enabled_bands/presets) bleiben unberührt; nur bekannte Felder
  werden geprüft.
- `type() is type()` statt isinstance → bool/int sauber getrennt.
- Reihenfolge: VOR den bestehenden Migrationen → die arbeiten dann mit
  typkorrekten Werten (z.B. `radio_timing == _legacy_p48`-Vergleich, `band`/
  `mode`-Override sind ohnehin Default-erzwungen).
- Im Normalbetrieb (korrekte config) **0 Änderung**; nur bei echtem Mismatch
  greift der Reset.

Test `tests/test_settings_typecheck.py`: pro Kategorie ein verkorkster Typ
(str→int, **int→bool [die Falle: `flexradio_port: true` muss zurückgesetzt
werden]**, bool→int, dict→list) → Default; korrekte config bleibt unverändert;
dynamische Keys (enabled_bands etc.) bleiben erhalten.

## Fragen an dich (R1)

1. **bool/int-Falle:** `type() is type()` korrekt gelöst? Gibt es einen Fall, wo
   das ZU streng ist (legitimer Wert fälschlich verworfen)? Besonders:
   float-statt-int (config `tune_power: 10.0`) → Reset auf 10 — akzeptabel
   (kein DEFAULTS-Feld ist float), oder behandeln?
2. **Platzierung** vor den Migrationen — richtig, oder Konflikt mit einer der
   Migrationen (pop / tune_duration_s-Whitelist / band-mode-Override /
   radio_timing / bandpilot)?
3. **Scope:** ALLE DEFAULTS-Felder generisch prüfen (mein Plan) vs. nur eine
   handgepflegte „kritische" Teilmenge — was ist KISS-richtiger/robuster?
4. **`radio_timing`** (dict): nur Top-Typ geprüft, Inhalt nicht. Out-of-scope =
   KISS, oder Lücke?
5. Übersehene Verhaltensänderung / Regression / besserer Ansatz?

Antworte knapp pro Punkt + Verdikt **GO** / **ÜBERARBEITEN**. Sei kritisch.
