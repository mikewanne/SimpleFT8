"""SimpleFT8 Station Accumulator — gemeinsame Logik fuer Normal + Diversity.

Extrahiert die duplizierte Station-Akkumulation aus mw_cycle.py.
Beide Modi nutzen dieselbe Basis (Update, Aging, Change-Detection),
Diversity fuegt Antennen-Vergleich hinzu.

Aging-Logik (v0.64): Aging-Schwellen sind in SLOTS definiert, nicht in
Sekunden — konsistent ueber alle Modi. Vorher waren 75/150/300s hartkodiert,
was bei FT2 (3.8s/Slot) eine Aging-Dauer von ~80 Slots ergab — viel zu lang
und Liste verstopft. Jetzt 7/14/20 Slots: ~3.5 verpasste Sende-Zyklen bis
Station entfernt wird, modus-konsistent.
"""

import copy
import time


# Aging-Schwellen in SLOTS (modus-aware ueber slot_duration_s in remove_stale)
AGING_SLOTS_NORMAL    = 7   # ~3.5 verpasste Sende-Zyklen → weg
AGING_SLOTS_ACTIVE    = 14  # aktiv angerufene Station (laenger weil wir sie verfolgen)
AGING_SLOTS_CQ_CALLER = 20  # CQ-Rufer bleiben laenger sichtbar (Hunt-Liste stabil)


def accumulate_stations(stations: dict, messages: list, active_qso_targets: set,
                        antenna: str = "",
                        slot_duration_s: float = 15.0) -> tuple[bool, list[dict]]:
    """Stationen akkumulieren — gemeinsame Logik fuer Normal + Diversity.

    Args:
        stations: Dict {callsign: FT8Message} — wird IN-PLACE modifiziert
        messages: Neue Nachrichten aus diesem Zyklus
        active_qso_targets: Set von Callsigns die gerade angerufen werden
        antenna: Optional "A1"/"A2" fuer Diversity (leer fuer Normal)
        slot_duration_s: Slot-Dauer des aktiven Modus (FT8=15.0, FT4=7.5, FT2=3.8).
                         Default 15.0 fuer Rueckwaerts-Test-Kompatibilitaet.

    Returns:
        (changed, comparisons) — comparisons: A1↔A2 Vergleichs-Dicts, leer bei Normal-Modus
    """
    now = time.time()
    utc_str = time.strftime("%H%M%S", time.gmtime(now))
    changed = False
    comparisons = []

    for orig_msg in (messages or []):
        key = orig_msg.caller
        if not key:
            continue

        msg = copy.copy(orig_msg) if antenna else orig_msg
        if antenna:
            msg.antenna = antenna

        existing = stations.get(key)
        if existing is None:
            # Neue Station
            msg._last_heard = now
            msg._last_changed = now
            msg._utc_display = utc_str
            stations[key] = msg
            changed = True
        else:
            # Station bekannt — hat sich was geaendert?
            snr_changed = msg.snr != existing.snr
            content_changed = (
                msg.field1 != existing.field1 or
                msg.field2 != existing.field2 or
                msg.field3 != existing.field3
            )
            ant_changed = antenna and antenna != getattr(existing, 'antenna', '')

            if snr_changed or ant_changed or content_changed:
                existing._last_heard = now
                existing._utc_display = utc_str

                # Diversity: Antennen-Vergleich
                if ant_changed and getattr(existing, 'antenna', '') in ("A1", "A2"):
                    old_ant = existing.antenna
                    # SNR pro Antenne speichern (für ΔSNR-Statistik), VOR SNR-Update
                    if antenna == "A1":
                        existing._snr_a1 = msg.snr
                        existing._snr_a2 = existing.snr
                    else:
                        existing._snr_a2 = msg.snr
                        existing._snr_a1 = existing.snr

                    # Echten A1↔A2 Vergleich erfassen
                    ant1_snr = existing._snr_a1
                    ant2_snr = existing._snr_a2
                    delta = ant2_snr - ant1_snr
                    comparisons.append({
                        "call": key,
                        "ant1_snr": ant1_snr,
                        "ant2_snr": ant2_snr,
                        "delta": delta,
                        "antenna_winner": "A2" if delta > 0 else "A1",
                    })

                    if msg.snr > existing.snr:
                        existing.antenna = f"{antenna}>{old_ant[-1]}"
                    else:
                        existing.antenna = f"{old_ant}>{antenna[-1]}"

                existing.snr = msg.snr
                if content_changed:
                    existing.raw = msg.raw
                    existing.field1 = msg.field1
                    existing.field2 = msg.field2
                    existing.field3 = msg.field3
                changed = True

    # Aging: alte Stationen entfernen
    stale = remove_stale(stations, active_qso_targets, now, slot_duration_s)
    if stale:
        changed = True

    return changed, comparisons


def _aging_limit_seconds(call: str, msg, active_qso_targets: set,
                         slot_duration_s: float) -> float:
    """Aging-Grenze in Sekunden basierend auf Slot-Dauer und Stations-Typ.

    Berechnung: AGING_SLOTS_X * slot_duration_s
      - active_qso (14 Slots): bei FT8=210s, FT4=105s, FT2=53.2s
      - CQ-Rufer  (20 Slots): bei FT8=300s, FT4=150s, FT2=76s
      - normal    ( 7 Slots): bei FT8=105s, FT4=52.5s, FT2=26.6s
    """
    if call in active_qso_targets:
        return AGING_SLOTS_ACTIVE * slot_duration_s
    if getattr(msg, 'is_cq', False):
        return AGING_SLOTS_CQ_CALLER * slot_duration_s
    return AGING_SLOTS_NORMAL * slot_duration_s


def remove_stale(stations: dict, active_qso_targets: set,
                 now: float = None,
                 slot_duration_s: float = 15.0) -> list:
    """Abgelaufene Stationen entfernen — Aging-Schwellen modus-aware.

    Args:
        stations: Dict mit FT8Messages (wird in-place modifiziert)
        active_qso_targets: Set von Callsigns die gerade angerufen werden
        now: Optional Timestamp (default time.time())
        slot_duration_s: Slot-Dauer des aktiven Modus (Default 15.0 = FT8)

    Aging-Schwellen (Slots × slot_duration_s):
      - 14 Slots wenn aktiv angerufen
      - 20 Slots fuer CQ-Rufer (Hunt-Liste stabil)
      - 7 Slots fuer alle anderen

    Returns:
        Liste der entfernten Callsigns
    """
    if now is None:
        now = time.time()
    if slot_duration_s <= 0:
        slot_duration_s = 15.0  # Defensiv: kein Crash bei ungueltigem Wert

    stale = [k for k, m in stations.items()
             if now - getattr(m, '_last_heard', now) >
                _aging_limit_seconds(k, m, active_qso_targets, slot_duration_s)]
    for k in stale:
        del stations[k]
    return stale
