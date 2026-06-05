# Final-R1 (Bestätigungs-Pass): OPT-53 Settings-Typvalidierung — fertiger Diff

DeepSeek-v4-pro Final-R1. Plan-R1 hattest du mit **GO ohne Korrekturen** bestätigt.
Code ist geschrieben, **2433 Tests grün** (+9 neu). Bestätige Verhaltensneutralität
+ Push-Tauglichkeit, oder benenne einen Blocker.

## Fertiger Diff (`config/settings.py`)

```python
# in load(), direkt nach `self._data.update(saved)` / dem try-except:
        self._validate_types()

# neue Methode (vor _migrate_bandpilot_settings_v088):
    def _validate_types(self):
        for key, default_val in DEFAULTS.items():
            if type(self._data.get(key)) is not type(default_val):
                print(f"[Settings] '{key}': Typ "
                      f"{type(self._data.get(key)).__name__} statt "
                      f"{type(default_val).__name__} → Default {default_val!r}")
                self._data[key] = default_val
```

DEFAULTS-Felder sind ausschließlich str/int/bool/dict (kein float).

## Tests (9 neu, `tests/test_settings_typecheck.py`)
- str→int, int→str, **bool/int-Falle (`flexradio_port: true` → Reset, Mutationsbeweis
  für `type() is type()`)**, bool←int, dict→list, None→Reset
- korrekte config = 0 Änderung (band/mode bewusst ausgelassen — Migration erzwingt sie)
- dynamische Keys (enabled_bands/tx_slot_lock) bleiben erhalten trotz falschem
  DEFAULTS-Feld daneben
- Vertrags-Test: alle DEFAULTS sind str/int/bool/dict (kein float)

## Prüfpunkte
1. Implementierung == freigegebener Plan (GO)? Bit-genau?
2. Verhaltensänderung NUR bei echtem Typ-Mismatch (Normalbetrieb 0 Änderung)?
3. Keine Regression mit den bestehenden Migrationen (laufen NACH `_validate_types`)?
4. Übersehenes?

Verdikt: **PUSH FREIGEBEN** oder **NICHT FREIGEBEN (Grund)**. Knapp.
