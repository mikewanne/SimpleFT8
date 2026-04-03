#!/usr/bin/env python3
"""Schritt 1: TCP-Verbindung zum FlexRadio — nur verbinden und lauschen.

Macht:
1. Discovery per UDP Broadcast (findet Radio automatisch)
2. TCP-Verbindung auf Port 4992
3. Greeting lesen (Version + Handle)
4. 30 Sekunden lang alles mitloggen was das Radio sendet

Keine Befehle, kein Audio, kein DAX — nur zuhören.
"""

import socket
import time
import sys


def discover(timeout=3.0):
    """FlexRadio im Netzwerk finden per UDP Discovery."""
    print("[Discovery] Lausche auf UDP 4992...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.bind(("", 4992))

        data, addr = sock.recvfrom(1024)
        sock.close()

        text = data.decode("utf-8", errors="replace")
        info = {"ip": addr[0]}
        for field in text.split():
            if "=" in field:
                k, v = field.split("=", 1)
                info[k] = v

        model = info.get("model", "FlexRadio")
        nickname = info.get("nickname", "")
        serial = info.get("serial", "?")
        version = info.get("version", "?")
        print(f"[Discovery] {model} '{nickname}' (SN:{serial}) @ {info['ip']}")
        print(f"[Discovery] Firmware: {version}")
        return info

    except socket.timeout:
        print("[Discovery] Kein Radio gefunden (Timeout)")
        return None
    except OSError as e:
        print(f"[Discovery] Fehler: {e}")
        return None


def tcp_connect(ip, port=4992):
    """TCP-Verbindung aufbauen und Greeting lesen."""
    print(f"\n[TCP] Verbinde zu {ip}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect((ip, port))
    sock.settimeout(0.5)
    print("[TCP] Verbunden!")

    # Greeting lesen (V=Version, H=Handle, S=Status)
    greeting = {}
    buffer = ""
    deadline = time.time() + 3.0
    while time.time() < deadline:
        try:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                prefix = line[0]
                print(f"  [{prefix}] {line}")
                if prefix == "V":
                    greeting["version"] = line[1:]
                elif prefix == "H":
                    greeting["handle"] = line[1:]
        except socket.timeout:
            if "handle" in greeting:
                break

    return sock, greeting


def listen(sock, duration=30):
    """Lauschen was das Radio von sich aus sendet."""
    print(f"\n[Listen] Lausche {duration}s lang (keine Befehle)...")
    print("-" * 60)

    start = time.time()
    line_count = 0
    buffer = ""

    while time.time() - start < duration:
        try:
            data = sock.recv(4096)
            if not data:
                print("\n[Listen] Verbindung vom Radio geschlossen!")
                return False
            buffer += data.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line:
                    elapsed = time.time() - start
                    print(f"  {elapsed:6.1f}s | {line[:120]}")
                    line_count += 1
        except socket.timeout:
            continue
        except (socket.error, OSError) as e:
            print(f"\n[Listen] Verbindung verloren: {e}")
            return False

    print("-" * 60)
    print(f"[Listen] {line_count} Zeilen in {duration}s empfangen")
    print(f"[Listen] Verbindung ist noch offen = STABIL")
    return True


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    # 1. Radio finden
    radio = discover()
    if not radio:
        print("\nRadio nicht gefunden. Laeuft es? Gleiches Netzwerk?")
        sys.exit(1)

    # 2. TCP verbinden
    sock, greeting = tcp_connect(radio["ip"])
    if not greeting.get("handle"):
        print("\nKein Handle bekommen — Radio hat uns nicht akzeptiert")
        sock.close()
        sys.exit(1)

    print(f"\n[OK] Handle: {greeting['handle']}")
    print(f"[OK] Version: {greeting.get('version', '?')}")

    # 3. Lauschen (ohne Befehle!)
    stable = listen(sock, duration)

    sock.close()
    print(f"\n{'ERGEBNIS: STABIL' if stable else 'ERGEBNIS: VERBINDUNG VERLOREN'}")


if __name__ == "__main__":
    main()
