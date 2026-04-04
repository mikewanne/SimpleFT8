"""SimpleFT8 AP-Dekodierung — A-Priori Hints fuer schwache Signale.

Setzt bekannte Bits (eigenes Call, CQ, i3-Typ) als starke Hints
in die LLR-Werte BEVOR BP laeuft. Reduziert den Suchraum dramatisch:
- 28 Bits fuer bekanntes Callsign → ~4 dB Gewinn
- 3 Bits fuer i3 (Message-Typ) → ~0.5 dB extra

Gain: +2-4 dB = bis zu -26 dB SNR decodierbar.
"""

import numpy as np
from PyFT8.transmitter import pack_ft8_c28
from PyFT8.receiver import LdpcDecoder, check_crc, unpack

# LLR-Wert fuer "sicher bekannt" (hoch aber nicht unendlich)
AP_LLR_CONFIDENCE = 100.0

# LDPC Control fuer AP-Passes (mehr Iterationen erlaubt)
import PyFT8.receiver as _pyft8_rx
_AP_LDPC_CONTROL = (83, 75)  # Mehr versuchen als bei normalem BP


def _call_to_bits(callsign: str) -> list[int] | None:
    """Callsign zu 28 Bits packen."""
    try:
        val, _ = pack_ft8_c28(callsign)
        if val < 0:
            return None
        return [(val >> (27 - i)) & 1 for i in range(28)]
    except Exception:
        return None


def _set_ap_bits(llr: np.ndarray, bit_positions: list[int],
                  bit_values: list[int]) -> np.ndarray:
    """Bekannte Bits als starke Hints in LLR setzen.

    LLR > 0 → Bit 0 wahrscheinlicher
    LLR < 0 → Bit 1 wahrscheinlicher
    """
    llr_ap = llr.copy()
    for pos, val in zip(bit_positions, bit_values):
        if 0 <= pos < len(llr_ap):
            # PyFT8 Konvention: llr > 0 → Bit 1, llr < 0 → Bit 0
            llr_ap[pos] = AP_LLR_CONFIDENCE if val == 1 else -AP_LLR_CONFIDENCE
    return llr_ap


def _try_bp_with_ap(llr_ap: np.ndarray) -> str | None:
    """BP-Decode mit AP-modifizierten LLR-Werten."""
    ldpc = LdpcDecoder()
    # Mehr Iterationen fuer AP
    old_control = _pyft8_rx.LDPC_CONTROL
    _pyft8_rx.LDPC_CONTROL = _AP_LDPC_CONTROL

    try:
        ncheck0 = ldpc.calc_ncheck(llr_ap)
        if ncheck0 > _AP_LDPC_CONTROL[0]:
            return None

        llr_out, ncheck, n_its = ldpc.decode(llr_ap)
        if ncheck != 0:
            return None

        # Bits extrahieren (PyFT8: llr > 0 → bit 1)
        bits91 = 0
        for bit in (llr_out[:91] > 0):
            bits91 = (bits91 << 1) | int(bit)

        bits77 = check_crc(bits91)
        if bits77 is None:
            return None

        msg_tuple = unpack(bits77)
        # validate mag nicht existieren — direkt String bauen
        if msg_tuple and len(msg_tuple) >= 3:
            return f"{msg_tuple[0]} {msg_tuple[1]} {msg_tuple[2]}"
        return None
    except Exception:
        return None
    finally:
        _pyft8_rx.LDPC_CONTROL = old_control


def try_ap_decode(llr: np.ndarray, my_call: str = "DA1MHH",
                   recent_calls=None,
                   priority_call: str = None) -> str | None:
    """AP-Dekodierung mit verschiedenen Hint-Stufen.

    Stufen (von wenig zu viel Vorwissen):
    0. AP-priorityCall: aktiver QSO-Partner → hoechste Prioritaet
    1. AP-i3: nur Message-Typ setzen (i3=1, 3 Bits)
    2. AP-CQ: "CQ" als Callsign 1 + i3 (31 Bits)
    3. AP-myCall: eigenes Call als Callsign 2 + i3 (31 Bits)
    4. AP-myCall+CQ: CQ + eigenes Call + i3 (59 Bits!) ← staerkster Hint
    5. AP-priorityCall+myCall: QSO-Partner als C1 + eigenes Call als C2 (59 Bits)
    6. AP-recentCall: bekannte Calls als Callsign 1 oder 2

    Returns: dekodierte Nachricht oder None
    """
    if len(llr) != 174:
        return None

    # Bit-Positionen im 77/174-Bit Codeword (systematisch):
    # c28a: bits 0-27, p1a: bit 28, c28b: bits 29-56
    # p1b: bit 57, ir: bit 58, g15: bits 59-73, i3: bits 74-76
    POS_C28A = list(range(0, 28))    # Callsign 1
    POS_C28B = list(range(29, 57))   # Callsign 2
    POS_I3 = [74, 75, 76]            # Message Type

    # i3 = 1 (Standard Type 1 Message) → [0, 0, 1]
    i3_bits = [0, 0, 1]

    # CQ Bits
    cq_bits = _call_to_bits("CQ")
    # Eigenes Call Bits
    my_bits = _call_to_bits(my_call)
    # QSO-Partner Bits (hoechste Prioritaet)
    prio_bits = _call_to_bits(priority_call) if priority_call else None

    # --- Stufe 0: QSO-Partner als C1 → prioritaer wenn aktiv ---
    if prio_bits:
        llr_ap = _set_ap_bits(llr, POS_C28A + POS_I3, prio_bits + i3_bits)
        msg = _try_bp_with_ap(llr_ap)
        if msg:
            return msg
        # QSO-Partner als C1 + eigenes Call als C2 (staerkster QSO-Hint)
        if my_bits:
            llr_ap = _set_ap_bits(
                llr,
                POS_C28A + POS_C28B + POS_I3,
                prio_bits + my_bits + i3_bits,
            )
            msg = _try_bp_with_ap(llr_ap)
            if msg:
                return msg

    # --- Stufe 1: nur i3 (3 Bits) ---
    llr_ap = _set_ap_bits(llr, POS_I3, i3_bits)
    msg = _try_bp_with_ap(llr_ap)
    if msg:
        return msg

    # --- Stufe 2: CQ + i3 (31 Bits) ---
    if cq_bits:
        llr_ap = _set_ap_bits(llr, POS_C28A + POS_I3, cq_bits + i3_bits)
        msg = _try_bp_with_ap(llr_ap)
        if msg:
            return msg

    # --- Stufe 3: eigenes Call als C2 + i3 (31 Bits) ---
    if my_bits:
        llr_ap = _set_ap_bits(llr, POS_C28B + POS_I3, my_bits + i3_bits)
        msg = _try_bp_with_ap(llr_ap)
        if msg:
            return msg

    # --- Stufe 4: CQ als C1 + eigenes Call als C2 + i3 (59 Bits!) ---
    if cq_bits and my_bits:
        llr_ap = _set_ap_bits(
            llr,
            POS_C28A + POS_C28B + POS_I3,
            cq_bits + my_bits + i3_bits,
        )
        msg = _try_bp_with_ap(llr_ap)
        if msg:
            return msg

    # --- Stufe 5: bekannte Calls (deque: aktuellste zuerst) ---
    if recent_calls:
        checked = set()
        if priority_call:
            checked.add(priority_call)
        for call in list(recent_calls)[:20]:  # Max 20 Calls (DeepSeek: war 10)
            if call in checked:
                continue
            checked.add(call)
            call_bits = _call_to_bits(call)
            if not call_bits:
                continue
            # Als Callsign 1 (anrufende Station)
            llr_ap = _set_ap_bits(llr, POS_C28A + POS_I3, call_bits + i3_bits)
            msg = _try_bp_with_ap(llr_ap)
            if msg:
                return msg
            # Als Callsign 2 (empfangende Station) + CQ
            if cq_bits:
                llr_ap = _set_ap_bits(
                    llr, POS_C28A + POS_C28B + POS_I3,
                    cq_bits + call_bits + i3_bits,
                )
                msg = _try_bp_with_ap(llr_ap)
                if msg:
                    return msg

    return None
