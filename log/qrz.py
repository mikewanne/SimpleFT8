"""SimpleFT8 QRZ.com API Client — Logbook Upload + Callsign Lookup."""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, Optional


_LOGBOOK_URL = "https://logbook.qrz.com/api"
_XML_URL = "https://xmldata.qrz.com/xml/current/"
_USER_AGENT = "SimpleFT8/1.0 (DA1MHH)"


class QRZClient:
    """QRZ.com API Client fuer Logbook Upload und Callsign Lookup."""

    def __init__(self, api_key: str = "", username: str = "", password: str = ""):
        self.api_key = api_key        # Logbook API Key (von QRZ Settings)
        self.username = username      # XML Lookup Username
        self.password = password      # XML Lookup Password
        self._session_key = ""        # XML Session Key (wird beim Login gesetzt)

    # ── Logbook Upload ────────────────────────────────────────────

    def upload_qso(self, adif_record: str) -> Dict[str, str]:
        """Einzelnes QSO als ADIF-Record an QRZ.com Logbook senden.

        Args:
            adif_record: ADIF-formatierter String (ohne Header, mit <EOR>)

        Returns:
            Dict mit 'RESULT', 'LOGIDS', 'COUNT' oder 'REASON' bei Fehler.
        """
        if not self.api_key:
            return {"RESULT": "FAIL", "REASON": "Kein QRZ API Key konfiguriert"}

        data = urllib.parse.urlencode({
            "KEY": self.api_key,
            "ACTION": "INSERT",
            "ADIF": adif_record,
        }).encode("utf-8")

        req = urllib.request.Request(_LOGBOOK_URL, data=data, method="POST")
        req.add_header("User-Agent", _USER_AGENT)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                return self._parse_response(body)
        except Exception as e:
            return {"RESULT": "FAIL", "REASON": str(e)}

    def upload_qso_from_dict(self, record: Dict[str, str]) -> Dict[str, str]:
        """QSO-Dict (aus ADIF-Parser) an QRZ.com senden."""
        adif_parts = []
        for key, value in record.items():
            if key.startswith("_"):
                continue  # Skip interne Felder
            adif_parts.append(f"<{key.lower()}:{len(value)}>{value}")
        adif_parts.append("<eor>")
        return self.upload_qso(" ".join(adif_parts))

    def _parse_response(self, body: str) -> Dict[str, str]:
        """QRZ Logbook API Response parsen (KEY=VALUE&KEY=VALUE)."""
        result = {}
        for pair in body.strip().split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                result[key] = urllib.parse.unquote(value)
        return result

    # ── Callsign Lookup ───────────────────────────────────────────

    def _xml_login(self) -> bool:
        """XML API Login — holt Session Key."""
        if not self.username or not self.password:
            return False
        params = urllib.parse.urlencode({
            "username": self.username,
            "password": self.password,
            "agent": _USER_AGENT,
        })
        url = f"{_XML_URL}?{params}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", _USER_AGENT)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_text = resp.read().decode("utf-8")
                root = ET.fromstring(xml_text)
                ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
                session = root.find(f"{ns}Session")
                if session is not None:
                    key_el = session.find(f"{ns}Key")
                    if key_el is not None and key_el.text:
                        self._session_key = key_el.text
                        return True
                    err = session.find(f"{ns}Error")
                    if err is not None:
                        print(f"[QRZ] Login Fehler: {err.text}")
            return False
        except Exception as e:
            print(f"[QRZ] Login Fehler: {e}")
            return False

    def lookup_callsign(self, callsign: str) -> Optional[Dict[str, str]]:
        """Callsign bei QRZ.com nachschlagen — gibt Name, Grid, Land etc. zurueck."""
        if not self._session_key:
            if not self._xml_login():
                return None
        params = urllib.parse.urlencode({
            "s": self._session_key,
            "callsign": callsign,
        })
        url = f"{_XML_URL}?{params}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", _USER_AGENT)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_text = resp.read().decode("utf-8")
                root = ET.fromstring(xml_text)
                ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""

                # Session pruefen (Key noch gueltig?)
                session = root.find(f"{ns}Session")
                if session is not None:
                    key_el = session.find(f"{ns}Key")
                    if key_el is not None and key_el.text:
                        self._session_key = key_el.text
                    else:
                        # Session abgelaufen → neu einloggen
                        self._session_key = ""
                        if self._xml_login():
                            return self.lookup_callsign(callsign)
                        return None

                # Callsign-Daten extrahieren
                cs = root.find(f"{ns}Callsign")
                if cs is None:
                    return None
                result = {}
                for field in cs:
                    tag = field.tag.replace(ns, "")
                    result[tag] = field.text or ""
                return result
        except Exception as e:
            print(f"[QRZ] Lookup Fehler: {e}")
            return None
