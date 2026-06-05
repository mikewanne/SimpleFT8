"""SimpleFT8 Settings — Laden/Speichern der Konfiguration."""

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".simpleft8"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Standard-FT8/FT4/FT2-Frequenzen pro Band
# FT2: Community-Frequenzen (DXZone/Decodium), Stand April 2026
# HINWEIS: FT2 = Decodium-Standard (4-GFSK, 41.667 Baud, Costas) —
# Profil in core/protocol.py:88. FT2-Button derzeit versteckt
# (Standards-Fragmentierung Decodium vs WSJT-X-Improved, 2026-05-23).
BAND_FREQUENCIES = {
    "80m": {"ft8": 3.573, "ft4": 3.575, "ft2": 3.578},
    "60m": {"ft8": 5.357, "ft4": 5.357, "ft2": 5.360},
    "40m": {"ft8": 7.074, "ft4": 7.047, "ft2": 7.052},
    "30m": {"ft8": 10.136, "ft4": 10.140, "ft2": 10.144},
    "20m": {"ft8": 14.074, "ft4": 14.080, "ft2": 14.084},
    "17m": {"ft8": 18.100, "ft4": 18.104, "ft2": 18.108},
    "15m": {"ft8": 21.074, "ft4": 21.140, "ft2": 21.144},
    "12m": {"ft8": 24.915, "ft4": 24.919, "ft2": 24.923},
    "10m": {"ft8": 28.074, "ft4": 28.180, "ft2": 28.184},
}

# Tune-Frequenzen: Nebenfrequenz -2 kHz (grob), stoert keine Weltfrequenz.
# FT2 nutzt den gleichen Offset wie FT8 des Bands.
TUNE_FREQS = {
    "80m_FT8": 3.571,   "80m_FT4": 3.573,
    "40m_FT8": 7.072,   "40m_FT4": 7.0455,
    "30m_FT8": 10.134,  "30m_FT4": 10.138,
    "20m_FT8": 14.072,  "20m_FT4": 14.078,
    "17m_FT8": 18.098,  "17m_FT4": 18.102,
    "15m_FT8": 21.072,  "15m_FT4": 21.138,
    "12m_FT8": 24.913,  "12m_FT4": 24.917,
    "10m_FT8": 28.072,  "10m_FT4": 28.178,
}


def get_tune_freq_mhz(band: str, mode: str) -> float | None:
    """Tune-Frequenz fuer Band+Modus. FT2 faellt auf FT8-Wert zurueck.

    Returns None wenn kein Offset-Wert hinterlegt (z.B. 60m).
    """
    m = mode.upper()
    if m == "FT2":
        m = "FT8"
    return TUNE_FREQS.get(f"{band}_{m}")


def _valid_bands(raw) -> list[str]:
    """Rohe Band-Liste defensiv validieren (OPT-64, DRY für get_/set_enabled_bands).

    Nur Strings die in ``BAND_FREQUENCIES`` sind, dedupliziert (Reihenfolge des
    ersten Auftretens erhalten). Bei nicht-Liste ODER leerem Ergebnis → Default
    (alle Bänder).
    """
    if not isinstance(raw, list):
        return list(BAND_FREQUENCIES.keys())
    valid: list[str] = []
    seen: set[str] = set()
    for b in raw:
        if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
            valid.append(b)
            seen.add(b)
    return valid or list(BAND_FREQUENCIES.keys())


DEFAULTS = {
    "callsign": "DA1MHH",
    "locator": "JO31",
    # P104 (v0.97.81): power_watts entfernt. ADIF-Log nutzt jetzt
    # control_panel._current_power_watts (aktiver Power-Preset).
    # Setting wird beim load() per pop migriert.
    "audio_input": "",
    "audio_output": "",
    "flexradio_ip": "",
    "flexradio_port": 4992,
    "band": "20m",
    "mode": "FT8",
    "auto_mode": False,
    "max_calls": 5,    # P98 (v0.97.70): 99 → 5 (FT8-Standard, Mike-Field-Test)
    # v0.99.7: Auto-Hunt ruft auch schon gearbeitete Stationen an (Diplom-Modus).
    # False (Default) = wie bisher: gearbeitete (Band+Mode-genau) ueberspringen.
    "auto_hunt_call_worked": False,
    "tune_power": 10,
    "diversity_operate_cycles": 80,  # 80/160/240 — Betriebszyklen bis Neueinmessung
    "radio_type": "flex",            # "flex"/"flexradio" = FlexRadio SmartSDR,
                                     # "ic7300"/"ic7100" = CI-V Stubs (P121 — Impl. folgt)
    "language": "de",                # "de" = Deutsch, "en" = English (Hilfe-Texte + Docs)
    # P52 (v0.97.41): stats_enabled entfernt — Stats sind immer an
    # (Bandpilot + Auswertungen brauchen sie). Migration in load().
    "debug_console_visible": False,  # Debug-Konsole ein/ausblenden
    "bandpilot_mode": "off",         # v0.88 — "off" | "auto" | "manual"
    # P48 (v0.97.13) / P121 (2026-05-25): Radio-Hardware-Konstanten kommen
    # jetzt aus der jeweiligen Radio-Klasse (siehe FlexRadio.tx_buffer_s
    # etc.). `radio_timing` ist nur noch User-Override-Slot: wer in
    # config.json explizit einen Wert schreibt, übersteuert den
    # Radio-Default. Default-Block ist leer.
    "radio_timing": {},
    # P63 (v0.97.36): Tuner-Setting + manuelle TUNE-Dauer.
    # Tuner=False (Monoband-Operator) skipt Auto-TUNE-Phase in
    # Gain-Mess-Pipeline und blendet TUNE-Button aus.
    # Dauer 15s reicht laut LDG AT-200 Pro Spec, 30s als Reserve.
    "tuner_present": True,
    "tune_duration_s": 15,
    # P54 (v0.97.44): Auto-TUNE nach Bandwechsel — schaltbar.
    # Triggert 10 W TUNE auf ANT1 nach jedem Band-Wechsel, speichert
    # zudem RFPreset-Stuetzpunkt fuer schnellere TX-Power-Konvergenz.
    "auto_tune_on_band_change": True,
    # P112 (v0.97.89): Auto-Gain-Einmessung bei Bandwechsel.
    # Default AUS — User-gesteuert via KALIBRIEREN-Button.
    # AN = bei Bandwechsel mit stale/missing Gain wird DXTuneDialog
    # automatisch gestartet (analog Auto-TUNE).
    "auto_gain_on_band_change": False,
    # 2026-06-03: Audio-Mithoer-Monitor (Diagnose) — RX-Audio auf Lautsprecher.
    # Wird normal persistiert (NICHT in der band/mode-Exclude-Liste von save()).
    "audio_monitor": False,
}


class Settings:
    """Verwaltet SimpleFT8-Konfiguration in ~/.simpleft8/config.json."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        # P34-Stufe2 (v0.97.19): Dynamic-Diversity ist Default — kein Toggle
        # mehr. Settings-Key `dynamic_diversity_enabled` aus alten Configs
        # wird silent ignoriert (nicht persistiert, nicht gelesen).
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, IOError):
                pass
        # OPT-53 (Robustheit): geladene Werte gegen die DEFAULTS-Typen absichern,
        # BEVOR die Migrationen darauf arbeiten. Eine von Hand verkorkste
        # config.json (falscher Typ) wuerde sonst blind uebernommen -> Folgefehler.
        self._validate_types()
        # P47: tote Frequenz-Keys aus alten Configs entfernen (v0.97.11+).
        # Idempotent — Dict-Pop ist No-op bei fehlendem Key.
        self._data.pop("audio_freq_hz", None)
        self._data.pop("max_decode_freq", None)
        # P52 (v0.97.41): stats_enabled-Toggle entfernt, Stats immer an.
        self._data.pop("stats_enabled", None)
        # P104 (v0.97.81): power_watts + tx_level + tx_levels_per_band
        # entfernt. ADIF nutzt aktuellen Power-Preset (ControlPanel),
        # tx_level fest auf 75% (= bisheriger Cap). Final-R1-Catch:
        # tx_levels_per_band hätte Bandwechsel-Override produziert.
        self._data.pop("power_watts", None)
        self._data.pop("tx_level", None)
        self._data.pop("tx_levels_per_band", None)
        # P80 (v0.97.52): normal_presets nach unified PresetStore migriert.
        # Idempotent (Pop ist No-op bei fehlendem Key). Migration der Werte
        # selbst laeuft in PresetStore.__init__ (migrate_legacy_files).
        self._data.pop("normal_presets", None)
        # P71 (v0.97.47): tune_duration_s Whitelist 5/10/15 — alter Wert 30
        # (oder beliebig) → Fallback 15. Idempotent.
        _td = self._data.get("tune_duration_s")
        if _td is not None and _td not in (5, 10, 15):
            self._data["tune_duration_s"] = 15
        # 2026-05-23: Band/Modus nicht mehr persistieren — App startet
        # immer mit DEFAULTS (20m FT8). Mike-Entscheidung: simpler Start,
        # verhindert auch versehentliches Starten im versteckten FT2.
        self._data["band"] = DEFAULTS["band"]
        self._data["mode"] = DEFAULTS["mode"]
        # P121 (2026-05-25): radio_timing-Block Default-Migration.
        # Wenn der Block exakt den alten FlexRadio-Defaults entspricht
        # (1.3 / 0.26 und KEINE anderen Keys), wird er auf {} reduziert
        # damit die Werte als "Radio-Default" gelten und spätere
        # Default-Änderungen am Radio greifen. Sobald ein Wert abweicht
        # ODER ein zusätzlicher Key drin ist → Block bleibt als
        # User-Override erhalten.
        rt = self._data.get("radio_timing", {})
        _legacy_p48 = {"tx_buffer_s": 1.3, "rx_hardware_offset_default_s": 0.26}
        if rt == _legacy_p48:
            self._data["radio_timing"] = {}
        self._migrate_bandpilot_settings_v088()

    def _validate_types(self):
        """Bekannte Settings-Felder gegen ihren ``DEFAULTS``-Typ absichern (OPT-53).

        JSON kann beliebige Typen liefern (von Hand falsch editierte config.json).
        Weicht ein geladener Wert vom Typ seines Defaults ab, wird der Default
        behalten + eine Meldung ausgegeben.

        - **Iteriert nur ueber ``DEFAULTS``** → dynamische/persistierte Keys
          ausserhalb (``enabled_bands``, ``tx_slot_lock``,
          ``normal_tx_freq_per_band``, Preset-Strukturen) bleiben unberuehrt.
        - **``type(x) is type(default)`` statt ``isinstance``** → trennt bewusst
          ``bool`` von ``int``: ``isinstance(True, int)`` ist ``True``, ein
          versehentliches ``"flexradio_port": true`` wuerde sonst durchrutschen.
        - Im Normalbetrieb (korrekte config) 0 Aenderung.
        """
        for key, default_val in DEFAULTS.items():
            if type(self._data.get(key)) is not type(default_val):
                print(f"[Settings] '{key}': Typ "
                      f"{type(self._data.get(key)).__name__} statt "
                      f"{type(default_val).__name__} → Default {default_val!r}")
                self._data[key] = default_val

    def _migrate_bandpilot_settings_v088(self):
        """v0.87 → v0.88 Migration: alte Bandpilot-Keys → bandpilot_mode.

        Idempotent: Vorhandensein der ALTEN Keys triggert die Migration.
        Nach Migration sind sie weg → zweiter Lauf ist No-op.
        Loescht alten Cache ``bandpilot_summary.json``.
        """
        has_old_keys = ("bandpilot_enabled" in self._data
                        or "bandpilot_diversity_pref" in self._data)
        if not has_old_keys:
            return  # frische Config oder schon migriert
        old_enabled = self._data.pop("bandpilot_enabled", None)
        self._data.pop("bandpilot_diversity_pref", None)
        self._data["bandpilot_mode"] = "auto" if old_enabled is True else "off"

        old_cache = Path.home() / ".simpleft8" / "bandpilot_summary.json"
        if old_cache.exists():
            try:
                old_cache.unlink()
            except OSError:
                pass  # nicht kritisch

        # OPT-50 (Robustheit): save() ist der EINZIGE crashende Pfad dieser
        # Migration (mkdir/open/json.dump/os.replace). Ein Plattenfehler beim
        # Start darf die App NIE crashen. Fail-silent + idempotent: die
        # In-Memory-Migration ist bereits erfolgt; schlägt save() fehl, bleibt
        # die alte Datei → has_old_keys triggert beim naechsten Start erneut.
        # Muster wie core/preset_store.py (migrate_legacy_files-Kapselung).
        try:
            self.save()
        except Exception as exc:
            print(f"[P88] Bandpilot-Migration: save() fehlgeschlagen "
                  f"(fail-silent, wird beim naechsten Start erneut versucht): {exc}")

    def save(self):
        """Atomarer Write via tmp+replace (R1-Finding 2026-05-04)."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            # 2026-05-23: band/mode nicht persistieren (immer DEFAULTS beim Start).
            _to_save = {k: v for k, v in self._data.items() if k not in ("band", "mode")}
            json.dump(_to_save, f, indent=2)
        os.replace(tmp, CONFIG_FILE)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    # Bundle E (v0.97.22): TX-Slot-Lock (Mike SmartSDR-Style).
    # Werte: "none" (beide Slots), "even", "odd". Nur in Normal-Modus wirksam,
    # in Diversity ist die UI ausgeblendet (State bleibt persistiert).
    def get_tx_slot_lock(self) -> str:
        """Liefert TX-Slot-Lock-Wert aus Settings. Default "none"."""
        raw = self._data.get("tx_slot_lock", "none")
        if raw not in ("none", "even", "odd"):
            return "none"
        return raw

    def set_tx_slot_lock(self, lock: str) -> None:
        """Setzt TX-Slot-Lock. Caller ruft `save()`."""
        if lock not in ("none", "even", "odd"):
            lock = "none"
        self._data["tx_slot_lock"] = lock

    # P50 (v0.97.20): Bänder-Sichtbarkeit
    def get_enabled_bands(self) -> list[str]:
        """Liefert die Liste der im Band-Panel sichtbaren Bänder.

        Default: alle 9 Bänder. Defensiv gefiltert gegen ungültige
        Einträge (kein String, nicht in ``BAND_FREQUENCIES``, Duplikate).
        Bei leerer/komplett-ungültiger Liste → Fallback auf Default.
        """
        return _valid_bands(self._data.get("enabled_bands"))

    def set_enabled_bands(self, bands: list[str]) -> None:
        """Setzt die Liste der sichtbaren Bänder.

        Defensiv: ungültige Einträge werden ignoriert. Bei leerer
        resultierender Liste → Default (alle 9). Persistiert NICHT
        automatisch — Caller ruft ``save()``.
        """
        self._data["enabled_bands"] = _valid_bands(bands)

    @property
    def callsign(self):
        return self._data["callsign"]

    @property
    def locator(self):
        return self._data["locator"]

    # P104 (v0.97.81): power_watts-Property entfernt — ADIF nutzt
    # ControlPanel._current_power_watts (aktiver Power-Preset).

    @property
    def band(self):
        return self._data["band"]

    @property
    def mode(self):
        return self._data["mode"]

    # P48 (v0.97.13) → P121 (2026-05-25): Radio-Hardware-Konstanten
    # liefert jetzt die Radio-Klasse (z.B. FlexRadio.tx_buffer_s = 1.3).
    # Diese Methoden geben NUR den User-Override zurück (None wenn nicht
    # explizit gesetzt). Aufrufer fallen bei None auf radio.tx_buffer_s /
    # radio.rx_hardware_offset_default_s zurück.
    def get_user_tx_buffer_override(self) -> Optional[float]:
        """User-Override für tx_buffer_s aus dem radio_timing-Block.

        Returns None wenn nicht explizit gesetzt → Default vom Radio.
        Returns float wenn User in config.json manuell einen Wert pflegt.
        """
        val = self._data.get("radio_timing", {}).get("tx_buffer_s")
        return float(val) if val is not None else None

    def get_user_rx_hardware_offset_override(self) -> Optional[float]:
        """Analog für rx_hardware_offset_default_s. None = Radio-Default."""
        val = self._data.get("radio_timing", {}).get("rx_hardware_offset_default_s")
        return float(val) if val is not None else None

    @property
    def frequency_mhz(self):
        """Aktuelle Frequenz basierend auf Band und Modus."""
        band = self._data["band"]
        mode = self._data["mode"].lower()
        return BAND_FREQUENCIES.get(band, {}).get(mode, 14.074)

    # ── Gain Presets (getrennt: Standard + DX) ───────────────────

    def get_dx_preset(self, band: str, mode: str = None) -> dict | None:
        """Standard-Gain-Preset laden. mode-spezifisch wenn vorhanden, sonst Band-Fallback."""
        presets = self._data.get("dx_presets", self._data.get("standard_presets", {}))
        if mode:
            specific = presets.get(f"{band}_{mode}")
            if specific is not None:
                return specific
        return presets.get(band)

    def get_gain_preset(self, band: str, mode: str = "standard", ft_mode: str = None) -> dict | None:
        """Gain-Preset laden. mode='standard'/'dx', ft_mode='FT8'/'FT4' fuer mode-spez. Key."""
        key = "dx_gain_presets" if mode == "dx" else "dx_presets"
        presets = self._data.get(key, {})
        if ft_mode:
            specific = presets.get(f"{band}_{ft_mode}")
            if specific is not None:
                return specific
        return presets.get(band)

    def save_normal_preset(self, band: str, gain: int, rxant: str = "ANT1"):
        """[DEPRECATED P80, v0.97.52] No-op — Persistenz uebernimmt jetzt
        ``PresetStore.save_gain(band, ...)`` im unified Store.
        """
        print(f"[P80] DEPRECATED settings.save_normal_preset({band}, "
              f"gain={gain}) gerufen — Aufrufer auf "
              f"_gain_store.save_gain umstellen.")

    def get_normal_tx_freq(self, band: str) -> int:
        """Manuell eingestellte TX-Frequenz pro Band fuer Normal-Modus.

        Wird bei Bandwechsel geladen und beim Klick im Histogramm /
        Spinbox-Aenderung gespeichert. Default 1500 Hz (WSJT-X-Default).
        """
        per_band = self._data.get("normal_tx_freq_per_band", {})
        return int(per_band.get(band, 1500))

    def save_normal_tx_freq(self, band: str, freq_hz: int):
        """TX-Frequenz fuer Band speichern (Normal-Modus, manuelle Auswahl)."""
        if "normal_tx_freq_per_band" not in self._data:
            self._data["normal_tx_freq_per_band"] = {}
        self._data["normal_tx_freq_per_band"][band] = int(freq_hz)
        self.save()

    def save_dx_preset(self, band: str, rxant: str, gain: int,
                       ant1_avg: float = 0, ant2_avg: float = 0,
                       ant1_gain: int = None, ant2_gain: int = None,
                       scoring: str = "standard", mode: str = None):
        """Gain-Preset speichern. scoring='standard' (Stationen) oder 'dx' (SNR).

        Standard → in 'dx_presets' (Legacy-Key, Rueckwaertskompatibel)
        DX → in 'dx_gain_presets' (neuer Key)
        mode → bei Angabe als band_mode-Key gespeichert (z.B. '20m_FT8')
        """
        import time
        key = "dx_gain_presets" if scoring in ("dx", "snr") else "dx_presets"
        if key not in self._data:
            self._data[key] = {}
        preset_key = f"{band}_{mode}" if mode else band
        self._data[key][preset_key] = {
            "rxant": rxant,
            "gain": gain,
            "ant1_gain": ant1_gain if ant1_gain is not None else gain,
            "ant2_gain": ant2_gain if ant2_gain is not None else gain,
            "ant1_avg": round(ant1_avg, 1),
            "ant2_avg": round(ant2_avg, 1),
            "measured": time.strftime("%Y-%m-%d %H:%M"),
            "scoring": scoring,
        }
        self.save()

    # ── TX-Power pro Band ─────────────────────────────────────────

    def save_tx_power(self, band: str, rfpower: int):
        """rfpower-Wert pro Band speichern (nach TX-Konvergenz)."""
        rp = self._data.setdefault("rfpower_per_band", {})
        rp[band] = int(rfpower)
        self.save()

    def get_tx_power(self, band: str, default: int = 50) -> int:
        """Gespeicherten rfpower-Wert für ein Band laden. Clamp 10-80%."""
        val = self._data.get("rfpower_per_band", {}).get(band)
        if val is None:
            return default
        return max(10, min(80, int(val)))

    # P34-Stufe2: get_diversity_preset + save_diversity_preset entfernt —
    # Ratio wird live vom DynamicDiversityController bestimmt, nicht
    # mehr persistiert. Alte `diversity_presets`-Keys in config.json
    # werden silent ignoriert.
