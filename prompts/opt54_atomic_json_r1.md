# R1-Review: OPT-54 — `atomic_write_json`-Helfer (DRY) + ntp_time-Atomaritäts-Lücke

Du bist DeepSeek-v4-pro als kritischer R1-Reviewer in einem V1→V2→R1→V3-Workflow.
Projekt: **SimpleFT8** (Hobby-Funker-Tool, PySide6/Python/macOS). Laufende
**Optimierungs-Kampagne**: Priorität **KISS / Lesbarkeit / Robustheit > Geschwindigkeit**.
Regeln: **NUR Optimierung, KEINE Verhaltensänderung im Normalbetrieb, keine Features.**
Bugs nur bei Zufallsfund. ANT1=TX-Pfad NICHT berühren (hier irrelevant — reines File-IO).

## Befund (verifiziert gegen Live-Code)

`core/ntp_time.py:188` schreibt den DT-Korrekturwert **nicht atomar**:
```python
def _save_current() -> None:
    try:
        _DT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DT_FILE.write_text(json.dumps({_SAVE_KEY: round(_correction, 4)}, indent=2))
    except Exception as e:
        print(f"[DT-Korr] Speichern fehlgeschlagen: {e}")
```
→ Crash mid-write kann `dt_corrections.json` zerreißen.

**9 andere Stores** schreiben dasselbe Muster (mkdir + tmp + `os.replace`) per Copy-Paste,
mit unterschiedlichen dump-Parametern und tmp-Strategien:

| Store | tmp | dump | Sonderlogik |
|---|---|---|---|
| awards_prefs.save_hidden | `.with_suffix(".tmp")` | `indent=2` | `except OSError: pass` außen |
| rf_preset_store._save_locked | `with_name(name+".tmp")` | `indent=2` | — |
| mode_recommender._save | `.with_suffix(".tmp")` | `indent=2`, encoding=utf-8 | — |
| settings.save | `.with_suffix(".tmp")` | `indent=2`, dict vorher gefiltert (band/mode raus) | — |
| psk_reporter._write_cache | `.with_suffix(".tmp")` | `separators=(",",":")` | — |
| locator_db.save | `with_suffix(suffix+".tmp")` | `separators=(",",":")`, utf-8 | läuft IM `self._lock`, baut data-dict |
| rx_history._flush | `.with_suffix(".tmp")` | `separators=(",",":")`, utf-8 | **retry-loop über N Dateien, dirty-Reaktivierung pro Datei bei OSError** |
| preset_store._save_locked | `NamedTemporaryFile` | `indent=2` | **fsync + Rollback-try/except** (bewusst robuster) |
| log/adif.py merge | `with_name(name+".tmp")` | **roher Text, KEIN json.dump** (byte-erhaltend, newline="") | — |

Alle dump default `ensure_ascii=True` → reine ASCII-Bytes → `encoding` praktisch irrelevant.
KEIN bestehender atomic-json-Helfer im Projekt. `config/settings.py` importiert bisher nur
stdlib; `core/` importiert nichts aus `config/` → ein stdlib-only `core/atomic_json.py`
erzeugt KEINEN Importzyklus.

## V1/V2-Plan (mein Entwurf, nach Self-Review)

**1. Neues Mini-Modul `core/atomic_json.py`** (nur stdlib):
```python
import json, os
from pathlib import Path

def atomic_write_json(path, data, *, encoding="utf-8", **dump_kwargs) -> None:
    """Schreibt `data` als JSON atomar (tmp + os.replace) nach `path`.
    Erzeugt Parent-Dir. `dump_kwargs` -> json.dump (z.B. indent=2 oder
    separators=(",",":")). Wirft Exceptions durch — der Aufrufer entscheidet
    über Fehlerbehandlung (manche schlucken, manche propagieren)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding=encoding) as f:
        json.dump(data, f, **dump_kwargs)
    os.replace(tmp, path)
```

**2. `ntp_time._save_current` damit fixen** (schließt die Lücke, erster Nutzer):
```python
def _save_current() -> None:
    try:
        atomic_write_json(_DT_FILE, {_SAVE_KEY: round(_correction, 4)}, indent=2)
    except Exception as e:
        print(f"[DT-Korr] Speichern fehlgeschlagen: {e}")
```

**3. Scope der DRY-Migration (meine vorläufige Wahl):** Helfer zusätzlich in den
**format-identischen, sonderlogik-freien** Stores nutzen:
`awards_prefs, rf_preset_store, mode_recommender, settings, psk_reporter, locator_db`.
Jeweils `**dump_kwargs` exakt durchreichen (indent=2 bzw. separators) → Ausgabe bit-identisch,
eigene try/except-Hülle bleibt außen.

**Bewusst AUSGESCHLOSSEN** (Sonderlogik, Migration brächte Risiko ohne Gewinn):
- `preset_store` (fsync+Rollback — der robusteste Pfad, soll seine Garantien behalten)
- `adif` (roher Text, kein json.dump)
- `rx_history` (enger retry-/dirty-Loop über mehrere Dateien)

**4. Test** `tests/test_atomic_json.py`: round-trip, tmp nach Erfolg weg, dump_kwargs-Durchreichung
(separators vs indent), mkdir-parents, **Exception propagiert** (Helfer schluckt nicht). Alle
bestehenden Store-Tests müssen unverändert grün bleiben (Format-Regressions-Schutz).

## Meine konkreten Fragen an dich (R1)

1. **Scope:** Ist meine Auswahl (6 migrieren, 3 ausschließen) die richtige KISS/Robustheit-
   Balance? Oder ist ein Helfer mit faktisch wenigen Nutzern Overengineering und ich sollte
   **nur ntp_time** fixen (direkt tmp+os.replace, ohne neues Modul)? Oder umgekehrt: auch
   `rx_history` migrieren (sauber im retry-Loop)? Begründe.
2. **`config/settings.py` → `core.atomic_json`:** akzeptable Kopplung, oder besser settings
   NICHT migrieren um config schlank/core-frei zu halten? (Das Util ist stdlib-only, kein Zyklus.)
3. **Helfer-Signatur:** `tmp = path.name + ".tmp"` (anhängend, `foo.json.tmp`) vs. die
   teils ersetzende `.with_suffix(".tmp")` der Bestands-Stores (`foo.tmp`) — der tmp-Name
   ändert sich für einige Stores. Ephemeral → egal, oder übersehe ich ein Risiko (z.B. zwei
   gleichnamige Stems verschiedener Endungen)? Soll der Helfer `fsync` machen (die 9 außer
   preset_store tun es NICHT — Einheitlichkeit vs. preset_store-Sonderfall)?
4. **Verhaltensänderung:** Siehst du IRGENDEINE Stelle, wo die Migration die erzeugte
   Datei (Inhalt/Bytes) verändert statt bit-identisch — besonders bei `separators`-Stores,
   `encoding`-Default, oder dem gefilterten settings-dict?
5. **locator_db im Lock:** Helfer-Aufruf innerhalb `self._lock` — Deadlock-/Reentrancy-Risiko? (Helfer kennt kein Lock.)
6. Übersehene Leiche / besseres KISS-Design, das ich nicht sehe?

Antworte strukturiert: pro Frage Urteil + Begründung, dann eine klare Gesamt-Empfehlung
(GO mit Scope X / ÜBERARBEITEN). Sei kritisch — verwerfen kann ich hinterher.
