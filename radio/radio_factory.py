"""radio_factory — Erstellt Radio-Implementierungen nach Typ.

Verwendung in main_window.py:
    from radio.radio_factory import create_radio
    self.radio = create_radio(settings)

Unterstützte Typen (settings["radio_type"]):
    "flex"   → FlexRadioInterface (SmartSDR TCP + VITA-49) [Standard]
    "ic7300" → IC7300Interface (CI-V Serial + USB Audio)   [ZUKÜNFTIG]
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
        FlexRadio-Instanz (oder künftig IC7300Interface).

    Raises:
        ValueError: Wenn radio_type unbekannt.
    """
    radio_type = settings.get("radio_type", "flex")

    if radio_type == "flex":
        from radio.flexradio import FlexRadio
        return FlexRadio(
            ip=settings.get("flexradio_ip", ""),
            port=settings.get("flexradio_port", 4992),
        )

    if radio_type == "ic7300":
        # Zukünftig: CI-V Serial + sounddevice USB Audio
        # from radio.ic7300 import IC7300Interface
        # return IC7300Interface(settings)
        raise NotImplementedError(
            "IC-7300 Interface noch nicht implementiert. "
            "Siehe radio/base_radio.py für die RadioInterface-Spezifikation."
        )

    raise ValueError(f"Unbekannter radio_type: {radio_type!r}. "
                     f"Gültige Typen: 'flex', 'ic7300'")
