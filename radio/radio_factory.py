"""radio_factory — Erstellt Radio-Implementierungen nach Typ.

Verwendung in main_window.py:
    from radio.radio_factory import create_radio
    self.radio = create_radio(settings)

Unterstützte Typen (settings["radio_type"]):
    "flex" / "flexradio" → FlexRadio (SmartSDR TCP + VITA-49)
    "ic7300"             → IC7300Interface (Stub, P121 — CI-V + USB Audio folgt)
    "ic7100"             → IC7100Interface (Stub, P121 — CI-V + USB Audio folgt)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings


def create_radio(settings: "Settings"):
    """Radio-Instanz gemäß radio_type in den Settings erstellen.

    Args:
        settings: Settings-Objekt mit flexradio_ip, flexradio_port, radio_type.

    Returns:
        FlexRadio, IC7300Interface oder IC7100Interface.

    Raises:
        ValueError: Wenn radio_type unbekannt.
    """
    # P64: Sim-Modus (Env-Var SIMPLEFT8_FAKE_RADIO=1) hat Vorrang vor dem
    # Settings-radio_type → App startet ohne echte Hardware (FakeRadio +
    # SimInjector, siehe radio/fake_radio.py).
    from core.sim_mode import is_sim_mode
    if is_sim_mode():
        from radio.fake_radio import FakeRadio
        print("[SIM] FakeRadio aktiv (SIMPLEFT8_FAKE_RADIO=1) — keine Hardware.")
        return FakeRadio()

    radio_type = settings.get("radio_type", "flex")

    if radio_type in ("flex", "flexradio"):
        from radio.flexradio import FlexRadio
        return FlexRadio(
            ip=settings.get("flexradio_ip", ""),
            port=settings.get("flexradio_port", 4992),
        )

    if radio_type == "ic7300":
        # P121: Stub. CI-V-Implementierung folgt in eigenem Ticket.
        from radio.ic7300 import IC7300Interface
        return IC7300Interface()

    if radio_type == "ic7100":
        # P121: Stub. CI-V-Implementierung folgt in eigenem Ticket.
        from radio.ic7100 import IC7100Interface
        return IC7100Interface()

    raise ValueError(f"Unbekannter radio_type: {radio_type!r}. "
                     f"Gültige Typen: 'flex'/'flexradio', 'ic7300', 'ic7100'")
