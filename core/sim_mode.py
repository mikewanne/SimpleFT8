"""Sim-Modus-Erkennung (P64).

Zentrale Wahrheit ob die App im Sim-Modus laeuft (FakeRadio statt echter
Hardware, siehe radio/fake_radio.py). Wird von Schreib-/Netz-Pfaden geprueft
damit Fake-Decodes NICHT die echten Daten/Netze kontaminieren:
- PSK-Reporter (globales Netzwerk — irreversibel, am wichtigsten)
- Weak-Decode-Liste (P152 — Mikes P150-Beweis-Evidenz)
- Stations-Statistik (Diagramme / Empfehlungen)

Aktivierung ueber Env-Var `SIMPLEFT8_FAKE_RADIO=1` (auch von radio_factory
genutzt um FakeRadio statt FlexRadio zu erzeugen).
"""
from __future__ import annotations

import os


def is_sim_mode() -> bool:
    """True wenn die App im Sim-Modus laeuft (Env-Var SIMPLEFT8_FAKE_RADIO=1)."""
    return os.environ.get("SIMPLEFT8_FAKE_RADIO") == "1"
