#!/usr/bin/env python3
"""Schritt 6: TX-Stream Verifizierung — Stream erstellen + FT8 Audio encoden.

Prueft ob:
  1. FlexRadio Discovery funktioniert
  2. 2-Schritt-Verbindung (SmartSDR-M disconnect + frisch verbinden)
  3. TX Stream (stream create type=dax_tx1) erstellt wird
  4. PyFT8 ein FT8-Signal encodieren kann
  5. KEIN tatsaechliches Senden (kein xmit 1!)

Ergebnis: TX Stream ID + Audio-Statistiken (Laenge, Peak).
"""

import socket
import struct
import time
import sys
import threading
import numpy as np

sys.path.insert(0, "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8")

from PyFT8.transmitter import pack_message, AudioOut

print("[PyFT8] Transmitter OK — pack_message + AudioOut geladen")

VITA49_HEADER_SIZE = 28
PCC_FLOAT32 = 0x03E3
SAMPLE_RATE_FT8 = 12000


def discover(timeout=3.0):
    """FlexRadio per UDP-Broadcast finden."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.bind(("", 4992))
        data, addr = sock.recvfrom(1024)
        sock.close()
        print(f"[Discovery] Radio @ {addr[0]}")
        return addr[0]
    except (socket.timeout, OSError) as e:
        print(f"[Discovery] Fehler: {e}")
        return None


class FlexConnection:
    """Minimaler TCP-Client fuer FlexRadio SmartSDR API."""

    def __init__(self, ip):
        self.ip = ip
        self.sock = None
        self.seq = 0
        self.handle = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.ip, 4992))
        self.sock.settimeout(0.5)
        buf = ""
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                buf += self.sock.recv(4096).decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.startswith("H"):
                        self.handle = line[1:].strip()
            except socket.timeout:
                if self.handle:
                    break
        print(f"[TCP] Handle: {self.handle}")

    def send(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        print(f"  >>> {cmd}")
        time.sleep(0.15)

    def send_quiet(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        time.sleep(0.15)

    def drain(self, timeout=1.0):
        """Alle wartenden TCP-Daten lesen."""
        data = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data += self.sock.recv(32768).decode("utf-8", errors="replace")
            except (socket.timeout, OSError):
                break
        return data

    def drain_and_print(self, timeout=1.0):
        """Lesen + ausgeben."""
        data = self.drain(timeout)
        lines = []
        for line in data.split("\n"):
            line = line.strip()
            if line:
                print(f"  <<< {line[:200]}")
                lines.append(line)
        return lines

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass


def disconnect_smartsdr(ip):
    """Phase 1: SmartSDR-M (Display-Client) rauswerfen."""
    print("\n" + "=" * 60)
    print("PHASE 1: SmartSDR-M disconnecten")
    print("=" * 60)

    c = FlexConnection(ip)
    c.connect()
    c.send("client gui")
    time.sleep(3)
    c.send("sub client all")
    time.sleep(1)
    data = c.drain(2.0)

    found = False
    for line in data.split("\n"):
        if "SmartSDR" in line and "0x" in line:
            for part in line.split():
                if part.startswith("0x") and part.lower() != f"0x{c.handle}".lower():
                    handle = part.rstrip(",")
                    print(f"  SmartSDR-M: {handle} -> disconnect")
                    c.send(f"client disconnect {handle}")
                    time.sleep(1)
                    c.drain(1.0)
                    found = True
                    break
            if found:
                break

    if not found:
        print("  SmartSDR-M nicht gefunden (evtl. schon weg) — weiter.")

    c.close()
    time.sleep(2)


def encode_test_ft8():
    """FT8-Testnachricht mit PyFT8 encodieren (OHNE zu senden!).

    Returns:
        tuple: (audio_12k_int16, symbols) oder (None, None)
    """
    print("\n" + "=" * 60)
    print("FT8 ENCODER TEST")
    print("=" * 60)

    # Testnachricht: CQ DA1MHH JO31
    msg_parts = ("CQ", "DA1MHH", "JO31")
    msg_str = " ".join(msg_parts)
    print(f"  Nachricht: {msg_str}")

    try:
        symbols = pack_message(msg_parts[0], msg_parts[1], msg_parts[2])
    except Exception as e:
        print(f"  FEHLER bei pack_message: {e}")
        return None, None

    if symbols is None:
        print(f"  FEHLER: pack_message gab None zurueck!")
        return None, None

    print(f"  Symbole: {len(symbols)} (erwartet: 79)")
    if len(symbols) != 79:
        print(f"  WARNUNG: Falsche Anzahl Symbole!")
        return None, None

    # Audio erzeugen (12kHz int16)
    audio_out = AudioOut()
    try:
        audio_12k = audio_out.create_ft8_wave(
            symbols, fs=SAMPLE_RATE_FT8, f_base=1000.0
        )
    except Exception as e:
        print(f"  FEHLER bei create_ft8_wave: {e}")
        return None, None

    if audio_12k is None:
        print(f"  FEHLER: create_ft8_wave gab None zurueck!")
        return None, None

    # Audio-Statistiken
    audio_float = audio_12k.astype(np.float32)
    peak = float(np.max(np.abs(audio_float)))
    duration = len(audio_12k) / SAMPLE_RATE_FT8
    rms = float(np.sqrt(np.mean(audio_float ** 2)))

    print(f"\n  Audio-Statistiken:")
    print(f"    Samples:   {len(audio_12k)}")
    print(f"    Dauer:     {duration:.2f}s (erwartet: ~12.6s)")
    print(f"    Peak:      {peak:.0f}")
    print(f"    RMS:       {rms:.0f}")
    print(f"    Dtype:     {audio_12k.dtype}")
    print(f"    Rate:      {SAMPLE_RATE_FT8} Hz")

    if peak > 0:
        print(f"\n  FT8 ENCODING ERFOLGREICH!")
    else:
        print(f"\n  WARNUNG: Audio ist Stille (Peak=0)!")

    return audio_12k, symbols


def create_tx_stream(ip):
    """Phase 2: Frisch verbinden + TX-Stream erstellen (OHNE zu senden!).

    Returns:
        tuple: (FlexConnection, tx_stream_id) oder (None, None)
    """
    print("\n" + "=" * 60)
    print("PHASE 2: Verbinden + TX Stream erstellen")
    print("=" * 60)

    c = FlexConnection(ip)
    c.connect()

    # 1. Als GUI registrieren
    print("\n--- Registrierung ---")
    c.send("client gui")
    time.sleep(5)  # Persistence abwarten
    c.drain_and_print()
    c.send("keepalive enable")
    c.drain(0.5)
    c.send("client set send_reduced_bw_dax=1")
    c.drain(0.5)

    # 2. Subscriptions
    print("\n--- Subscriptions ---")
    for sub in ["slice", "tx", "audio", "dax", "radio"]:
        c.send(f"sub {sub} all")
    time.sleep(1)
    c.drain(1.0)

    # 3. UDP Setup
    print("\n--- UDP ---")
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    udp.bind(("", 4991))
    udp.settimeout(0.1)
    udp.sendto(b"\x00", (ip, 4992))
    c.send("client udpport 4991")
    time.sleep(0.5)
    c.drain(0.5)

    # 4. Slice konfigurieren (fuer TX)
    print("\n--- Slice konfigurieren ---")
    c.send("slice tune 0 14.074")
    time.sleep(1)
    c.send("slice set 0 mode=DIGU")
    time.sleep(1)
    c.send("slice set 0 tx=1")
    c.send("interlock tx1_enabled=1")
    c.send("transmit set rfpower=50")
    c.send("slice set 0 dax=1")
    c.send("transmit set dax=1")
    c.send("dax audio set 1 slice=0")
    time.sleep(0.5)
    c.drain_and_print()

    # 5. TX Stream erstellen (DER EIGENTLICHE TEST!)
    print("\n--- TX Stream erstellen ---")
    c.send("stream create type=dax_tx1")
    time.sleep(2)
    lines = c.drain_and_print()

    # Stream-ID aus Antwort extrahieren
    tx_stream_id = None
    for line in lines:
        if "|0|" in line and line.startswith("R"):
            parts = line.split("|")
            if len(parts) >= 3 and parts[2].strip():
                try:
                    tx_stream_id = int(parts[2].strip(), 16)
                    print(f"\n  TX Stream ID: 0x{tx_stream_id:08X}")
                except ValueError:
                    pass

    # 6. Keepalive starten
    running = [True]

    def keepalive():
        while running[0]:
            time.sleep(5)
            if not running[0]:
                break
            try:
                c.send_quiet("ping")
            except OSError:
                break

    threading.Thread(target=keepalive, daemon=True).start()

    return c, udp, tx_stream_id, running


def main():
    print("=" * 60)
    print("SCHRITT 6: TX Stream Verifizierung")
    print("  Testet: Discovery → Connect → TX Stream → FT8 Encode")
    print("  SENDET NICHT! (kein xmit 1)")
    print("=" * 60)

    # 1. Discovery
    ip = discover()
    if not ip:
        print("\nFEHLER: Kein FlexRadio gefunden!")
        sys.exit(1)

    # 2. SmartSDR-M disconnecten
    disconnect_smartsdr(ip)

    # 3. FT8 Audio encodieren (unabhaengig vom Radio)
    audio_12k, symbols = encode_test_ft8()

    # 4. TX Stream erstellen
    c, udp, tx_stream_id, running = create_tx_stream(ip)

    # 5. Ergebnis
    print("\n" + "=" * 60)
    print("ERGEBNIS:")
    print("=" * 60)

    success = True

    # TX Stream Check
    if tx_stream_id:
        print(f"  [OK] TX Stream erstellt: 0x{tx_stream_id:08X}")
    else:
        print(f"  [FEHLER] TX Stream konnte nicht erstellt werden!")
        success = False

    # FT8 Encoding Check
    if audio_12k is not None and len(audio_12k) > 0:
        peak = float(np.max(np.abs(audio_12k.astype(np.float32))))
        duration = len(audio_12k) / SAMPLE_RATE_FT8
        print(f"  [OK] FT8 Audio: {len(audio_12k)} Samples, {duration:.2f}s, Peak={peak:.0f}")
    else:
        print(f"  [FEHLER] FT8 Audio-Encoding fehlgeschlagen!")
        success = False

    # Symbols Check
    if symbols is not None and len(symbols) == 79:
        print(f"  [OK] FT8 Symbole: {len(symbols)} (korrekt)")
    else:
        print(f"  [FEHLER] FT8 Symbole fehlerhaft!")
        success = False

    # TX-Audio-Format Info (was gesendet werden WUERDE)
    if audio_12k is not None and tx_stream_id:
        # Berechne was das TX-Paket waere
        audio_float = audio_12k.astype(np.float32)
        if np.max(np.abs(audio_float)) > 1.5:
            audio_float = audio_float / 32768.0
        # Resample 12kHz -> 48kHz (4x)
        audio_48k = np.repeat(audio_float, 4)
        # Mono -> Stereo
        n_stereo_samples = len(audio_48k) * 2
        n_packets = n_stereo_samples // 256
        tx_duration = n_packets * (128 / 48000.0)

        print(f"\n  TX-Audio Info (was gesendet werden WUERDE):")
        print(f"    48kHz Samples:    {len(audio_48k)}")
        print(f"    VITA-49 Pakete:   {n_packets}")
        print(f"    TX Dauer:         {tx_duration:.2f}s")
        print(f"    Format:           float32 stereo big-endian")
        print(f"    PCC:              0x{PCC_FLOAT32:04X}")
        print(f"    Stream ID:        0x{tx_stream_id:08X}")

    print(f"\n  SICHERHEIT: xmit wurde NICHT gesendet — kein HF-Ausgang!")

    if success:
        print(f"\n  SCHRITT 6 BESTANDEN: TX-Pfad ist bereit!")
        print(f"  Naechster Schritt: Echtes QSO (CQ senden + Antworten)")
    else:
        print(f"\n  SCHRITT 6 GESCHEITERT — siehe Fehler oben.")

    print("=" * 60)

    # Aufraeumen
    running[0] = False
    try:
        udp.close()
    except OSError:
        pass
    c.close()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
