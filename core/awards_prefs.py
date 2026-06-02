"""SimpleFT8 — Sichtbarkeit der Diplom-Karten (persistent).

Speichert die Menge der AUSGEBLENDETEN Award-Keys in
`~/.simpleft8/awards_visibility.json`. Default: nichts ausgeblendet
(alle Karten sichtbar).

Bewusst ein eigenes Mini-Modul statt das `Settings`-Objekt durch drei
Konstruktor-Ebenen (MainWindow -> qso_panel -> LogbookWidget ->
AwardsDialog) durchzureichen — entkoppelt, KISS, ohne GUI testbar. Folgt
dem bereits etablierten Muster eigener JSONs unter `~/.simpleft8/`
(dt_corrections.json, preset_store, ...).
"""

import json
import os
from pathlib import Path

# Modul-level, damit Tests ihn auf ein tmp-Verzeichnis umbiegen koennen.
_FILE = Path.home() / ".simpleft8" / "awards_visibility.json"


def load_hidden() -> set:
    """Menge der ausgeblendeten Award-Keys. Defensiv: bei jedem Fehler -> leer."""
    try:
        with open(_FILE, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    return {str(k) for k in data}


def save_hidden(hidden) -> None:
    """Ausgeblendete Keys atomar speichern. `hidden` ist ein iterable von Keys.

    Fehler werden geschluckt (Sichtbarkeit ist Komfort, kein kritischer State).
    """
    try:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(sorted(str(k) for k in hidden), f, indent=2)
        os.replace(tmp, _FILE)
    except OSError:
        pass
