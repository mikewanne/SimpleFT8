# Final-R1 (Bestätigungs-Pass): OPT-54 `atomic_write_json` — fertiger Diff

Du bist DeepSeek-v4-pro im **Final-R1**: der Code ist geschrieben, Tests grün
(**2424 passed**, +8 neue). Prüfe den FERTIGEN Diff auf Verhaltensneutralität,
übersehene Regression, Push-Tauglichkeit. Plan-R1 hattest du mit GO bestätigt.

## Scope-KORREKTUR seit Plan-R1 (wichtig, dein Urteil dazu)

Du hattest in Plan-R1 empfohlen, AUCH `config/settings.py` zu migrieren
(„marginale Kopplung"). **Ich habe das verworfen** nach einem Befund, den ich
beim Implementieren verifiziert habe:

`core/__init__.py` ist NICHT leer — es lädt beim Import `decoder` + `encoder`
(schwer, zieht die ft8_lib-C-dylib). Ein Top-Level-`from core.atomic_json import …`
in `config/settings.py` würde also bei **jedem isolierten settings-Import** (viele
Tests importieren settings ohne core) erstmals das schwere core-Paket mitziehen.
Die 5 **core**-Stores zahlen diese `core/__init__`-Last ohnehin (sie SIND core) →
für sie gratis. Nur settings (in `config/`, bewusst stdlib-rein) wäre betroffen.

→ **settings.py NICHT migriert** (bleibt stdlib-rein, ist ohnehin schon atomar →
kein Robustheits-Defizit). Final-Scope: Helfer + ntp_time + 5 core-Stores.
**Frage: Stimmst du der Scope-Korrektur zu?**

## Der Helfer (`core/atomic_json.py`, neu)

```python
def atomic_write_json(path, data, *, encoding="utf-8", **dump_kwargs) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding=encoding) as f:
        json.dump(data, f, **dump_kwargs)
    os.replace(tmp, path)
```
(Docstring stellt klar: wirft Exceptions DURCH, schluckt nie selbst.)

## Diff der 6 Stores

```diff
# ntp_time._save_current — DIE LÜCKE (war write_text = nicht atomar):
-        _DT_FILE.parent.mkdir(parents=True, exist_ok=True)
-        _DT_FILE.write_text(json.dumps({_SAVE_KEY: round(_correction, 4)}, indent=2))
+        atomic_write_json(_DT_FILE, {_SAVE_KEY: round(_correction, 4)}, indent=2)
   (try/except Exception + print bleibt außen)

# awards_prefs.save_hidden (indent=2, import os entfernt — war nur für os.replace):
-        _FILE.parent.mkdir(...); tmp = _FILE.with_suffix(".tmp")
-        with open(tmp,"w") as f: json.dump(sorted(...), f, indent=2); os.replace(tmp,_FILE)
+        atomic_write_json(_FILE, sorted(str(k) for k in hidden), indent=2)
   (try/except OSError: pass bleibt außen)

# rf_preset_store._save_locked (indent=2, import os entfernt):
+        atomic_write_json(self._path, self._data, indent=2)

# mode_recommender._save (indent=2, encoding war utf-8, import os entfernt):
+        atomic_write_json(self._path, self._data, indent=2)

# psk_reporter.save_cache (separators=(",",":"), expliziter mkdir entfernt → Helfer):
-        self._cache_path.parent.mkdir(...)   # entfernt, data-build bleibt
+        atomic_write_json(self._cache_path, data, separators=(",", ":"))

# locator_db.save (separators=(",",":"), encoding war utf-8, LÄUFT IM self._lock):
     with self._lock:
-        self._path.parent.mkdir(...); data = {...}
-        tmp = with_suffix(suffix+".tmp"); open(...,"utf-8"); json.dump(...separators); os.replace
+        data = {...}
+        atomic_write_json(self._path, data, separators=(",", ":"))
         self._dirty = False
```

## Meine Selbst-Prüfung (bestätige oder widerlege je Punkt)

1. **Bit-Identität der Bytes:** alle `dump_kwargs` durchgereicht (indent=2 bzw.
   separators). `encoding="utf-8"`-Default vs. vorher teils ohne encoding → JSON
   `ensure_ascii=True` (default) erzeugt reine ASCII-Bytes → encoding irrelevant.
   Kein Store setzt ensure_ascii=False/sort_keys. → bit-identisch?
2. **tmp-Name ändert sich** für einige Stores (`foo.tmp` → `foo.json.tmp`), weil
   der Helfer ANHÄNGT statt `.with_suffix` zu ersetzen. tmp ist ephemer (sofort
   per os.replace verbraucht). → harmlos?
3. **psk_reporter/locator_db:** der explizite `mkdir` (vorher VOR dem data-Build)
   ist jetzt IM Helfer (nach data-Build). data-Build hat keine FS-Abhängigkeit →
   Reihenfolge egal. locator_db: Helfer läuft IM `self._lock` (kein eigenes Lock
   im Helfer) → kein Deadlock. → korrekt?
4. **import os entfernt** in rf_preset_store/mode_recommender/locator_db (pyflakes
   bestätigt: os.replace war die letzte os-Nutzung). ntp_time/psk_reporter behalten
   os (anderswo genutzt). → sauber?
5. **Robustheits-Gewinn:** nur ntp_time ändert echtes Verhalten (jetzt atomar bei
   Crash) — das ist OPT-54s Zweck, keine ungewollte Verhaltensänderung. → ok?
6. Übersehene Regression / Verhaltensänderung irgendwo?

Antworte knapp pro Punkt + klares Verdikt: **PUSH FREIGEBEN** oder
**NICHT FREIGEBEN (Grund)**.
