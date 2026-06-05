"""SimpleFT8 — atomares JSON-Schreiben (DRY-Helfer, OPT-54).

Das ``mkdir + tmp + json.dump + os.replace``-Muster lag projektweit in mehreren
Stores als Copy-Paste vor; ``core/ntp_time.py`` hatte es vergessen (nicht-atomarer
``write_text`` → ein Crash mitten im Schreiben konnte ``dt_corrections.json``
zerreissen). Dieser Helfer kapselt das Muster an EINER getesteten Stelle.

Nutzer (OPT-54): ``ntp_time``, ``awards_prefs``, ``rf_preset_store``,
``mode_recommender``, ``psk_reporter``, ``locator_db``.

Bewusst NICHT migriert (eigene, abweichende/robustere Logik behalten):
``core/preset_store.py`` (fsync + Rollback), ``log/adif.py`` (roher Text,
byte-erhaltend), ``core/rx_history.py`` (retry-/dirty-Loop ueber mehrere Dateien),
``config/settings.py`` (bewusst stdlib-rein — ein ``from core...``-Import wuerde
das schwere ``core/__init__``-Paket in jeden isolierten settings-Import ziehen).
"""

import json
import os
from pathlib import Path


def atomic_write_json(path, data, *, encoding="utf-8", **dump_kwargs) -> None:
    """Schreibt ``data`` als JSON atomar (tmp + ``os.replace``) nach ``path``.

    Erzeugt das Eltern-Verzeichnis bei Bedarf. ``dump_kwargs`` werden unveraendert
    an ``json.dump`` durchgereicht (z.B. ``indent=2`` oder
    ``separators=(",", ":")``) → die erzeugten Bytes sind bit-identisch zum
    bisherigen Inline-Code des jeweiligen Stores.

    **Wirft Exceptions bei Dateifehlern DURCH — schluckt nie selbst.** Jeder
    Aufrufer entscheidet ueber seine Fehlerbehandlung (manche Stores schlucken
    ``OSError``, andere propagieren). Wer die ``try/except``-Klammer vergisst,
    bekommt den Fehler also zu sehen — das ist Absicht.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding=encoding) as f:
        json.dump(data, f, **dump_kwargs)
    os.replace(tmp, path)
