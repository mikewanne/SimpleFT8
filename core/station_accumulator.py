"""SimpleFT8 Station Accumulator — gemeinsame Logik fuer Normal + Diversity.

Extrahiert die duplizierte Station-Akkumulation aus mw_cycle.py.
Beide Modi nutzen dieselbe Basis (Update, Aging, Change-Detection),
Diversity fuegt Antennen-Vergleich hinzu.
"""

import copy
import time


def accumulate_stations(stations: dict, messages: list, active_qso_targets: set,
                        antenna: str = "") -> tuple[bool, list[dict]]:
    """Stationen akkumulieren — gemeinsame Logik fuer Normal + Diversity.

    Args:
        stations: Dict {callsign: FT8Message} — wird IN-PLACE modifiziert
        messages: Neue Nachrichten aus diesem Zyklus
        active_qso_targets: Set von Callsigns die gerade angerufen werden (150s Aging)
        antenna: Optional "A1"/"A2" fuer Diversity (leer fuer Normal)

    Returns:
        (changed, comparisons) — comparisons: A1↔A2 Vergleichs-Dicts, leer bei Normal-Modus
    """
    now = time.time()
    slot_dur = 15.0  # wird unten nicht gebraucht fuer Logik
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
    stale = remove_stale(stations, active_qso_targets, now)
    if stale:
        changed = True

    return changed, comparisons


def remove_stale(stations: dict, active_qso_targets: set,
                 now: float = None) -> list:
    """Abgelaufene Stationen entfernen.

    Aging-Limits:
      - 150s wenn aktiv angerufen (active_qso_targets)
      - 300s fuer CQ-Rufer (damit CQ-Liste nicht zuschnellt verschwindet, aber >5min weg)
      - 75s fuer alle anderen (QSO-Partner, Relay-Verkehr)

    Returns:
        Liste der entfernten Callsigns
    """
    if now is None:
        now = time.time()

    def _limit(k: str, m) -> int:
        if k in active_qso_targets:
            return 150
        if getattr(m, 'is_cq', False):
            return 300
        return 75

    stale = [k for k, m in stations.items()
             if now - getattr(m, '_last_heard', now) > _limit(k, m)]
    for k in stale:
        del stations[k]
    return stale
