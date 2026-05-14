"""SimpleFT8 Main Window — 3-Fenster-Layout mit QSplitter.

Kernlogik ist in 4 Mixins aufgeteilt:
  - CycleMixin  (mw_cycle.py)  — Zyklusverarbeitung, Diversity Akkumulation
  - QSOMixin    (mw_qso.py)    — QSO-Steuerung, CQ, Station-Klick, QRZ
  - RadioMixin  (mw_radio.py)  — Radio-Verbindung, Band, Diversity, DX-Tuning
  - TXMixin     (mw_tx.py)     — TX-Regelung, Meter, SWR
"""

import math
import threading
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QMessageBox, QScrollArea, QLabel,
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer

from config.settings import Settings, BAND_FREQUENCIES
from core.timing import FT8Timer
from core.qso_state import QSOStateMachine, QSOState
from core.encoder import Encoder
from core.decoder import Decoder
from core.message import FT8Message
from core.diversity import DiversityController
from log.adif import AdifWriter
from radio.radio_factory import create_radio
from .rx_panel import RXPanel
from .qso_panel import QSOPanel
from .control_panel import ControlPanel
from .settings_dialog import SettingsDialog
from .mw_cycle import CycleMixin
from .mw_qso import QSOMixin
from .mw_radio import RadioMixin
from .mw_tx import TXMixin
from . import styles


class MainWindow(QMainWindow, CycleMixin, QSOMixin, RadioMixin, TXMixin):
    """SimpleFT8 Hauptfenster — 3 Panels horizontal."""

    # Cross-Thread-Signal fuer Karten-Update: Decoder-Thread → GUI-Thread.
    # Payload: snapshot-dict, band-string. Empfaenger: _on_direction_map_snapshot.
    direction_map_signal = Signal(dict, str)

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle(f"SimpleFT8 — {settings.callsign}")
        self._qrz_title_suffix = ""  # P1.QRZ-UPLOAD-UI-2 v0.95.15
        self.setMinimumSize(1200, 600)
        self.resize(1400, 700)
        self._apply_dark_theme()

        # P26 (10.05.2026): Connect-Modal-Attribut frueh deklariert damit
        # Worker-Thread safe darauf zugreifen kann (lokale Referenz holen).
        self._connect_dialog = None

        # P35 Bug F (Mike-Anweisung 11.05.2026): App-Start IMMER auf
        # 20m / FT8 / Normal-Modus erzwingen — kein State-Restore mehr.
        # Mike entscheidet morgens spontan was er funken will. Settings-
        # Datei behaelt andere Werte (Callsign, Locator, Gains, Presets),
        # NUR band+mode werden auf Startwerte ueberschrieben. Andere
        # Konsequenzen: bandpilot_mode/dynamic_diversity_enabled etc.
        # bleiben aus Settings.
        self.settings._data["band"] = "20m"
        self.settings._data["mode"] = "FT8"
        # _rx_mode = "normal" wird ohnehin in _init_radio_state (Z.235) gesetzt.

        # Initialisierung in fester Reihenfolge — siehe Helper-Docstrings.
        self._init_core_components()
        self._init_qso_log()
        self._init_radio_state()
        self._init_diversity_state()
        self._init_power_state()

        # UI aufbauen (benötigt Core + Diversity + Power State)
        self._setup_ui()
        self._connect_signals()
        self.rx_panel.set_qso_log(self.qso_log)
        self.rx_panel.set_locator_db(self.locator_db)

        # Optionale Features (NACH _setup_ui, weil Easter-Egg-Signal verbunden wird)
        self._init_optional_features()

        # Timer + Radio starten (NACH OMNI-TX/Auto-Hunt/AP-Lite Init!)
        self.timer.start()
        # P26 (10.05.2026): _start_radio deferred via singleShot, damit
        # __init__ erst durchlaeuft + window.show() das Hauptfenster
        # sichtbar macht, BEVOR der Connect-Modal-Dialog mit exec() den
        # GUI-Thread blockiert. Sonst saehe der User nur den Modal-Dialog
        # ohne Hauptfenster dahinter.
        from PySide6.QtCore import QTimer as _QTimerStartRadio
        _QTimerStartRadio.singleShot(0, self._start_radio)

        # UI mit gespeicherten Settings synchronisieren
        self.control_panel._set_band(settings.band)
        self.control_panel._set_mode(settings.mode)
        self.control_panel.set_power_preset(settings.get("power_preset", 10))
        # P50 (v0.97.20): Sichtbare Bänder anwenden. current_band bleibt
        # garantiert sichtbar (R1-F1 in ControlPanel.set_visible_bands).
        self.apply_visible_bands()

        # Hintergrund-Timer
        self._init_psk_polling()
        self._init_propagation_polling()
        self._init_presence_watchdog()
        self._init_locator_db_autosave()
        self._init_cq_countdown_timer()

        # Statusbar + Geometry
        self._init_statusbar()
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, self._restore_geometry)

    # ───────────────────────────────────────────────────────────────────
    # Init-Helper — extrahiert für Lesbarkeit. 1:1 Auslagerung der Original-
    # Blöcke aus __init__, keine Verhaltensänderung. Reihenfolge ist kritisch
    # (Optionale Features brauchen control_panel; _start_radio braucht alles).
    # ───────────────────────────────────────────────────────────────────

    def _apply_dark_theme(self):
        """Dark-Theme StyleSheet auf MainWindow anwenden."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #16192b;
            }
            QWidget {
                background-color: #06060c;
                color: #CCCCCC;
            }
            QSplitter::handle:horizontal {
                background-color: #555;
                width: 4px;
                border-left: 1px solid #777;
                border-right: 1px solid #333;
            }
        """)

    def _init_core_components(self):
        """Core: Timer, QSO-State-Machine, Encoder/Decoder, ADIF, Stats, Antennen-Prefs, PresetStores."""
        settings = self.settings
        self.timer = FT8Timer(settings.mode)
        self.qso_sm = QSOStateMachine(settings.callsign, settings.locator)
        # P48 (v0.97.13): Hardware-Default fuer DT-Kaltstart aus Settings.
        # Greift wenn weder eigener Wert noch Cross-Modus-Fallback existieren.
        from core import ntp_time as _ntp
        _ntp.set_hardware_default(settings.rx_hardware_offset_default_s)
        # P47 (v0.97.11): audio_freq_hz + max_decode_freq aus Settings entfernt
        # (waren tot). Encoder-Start auf 1500 Hz (CQ-Such-Algo ueberschreibt
        # ohnehin pro Slot); Decoder-Obergrenze konstant 3000 Hz.
        # P48 (v0.97.13): tx_buffer_s aus Settings (FlexRadio 1.3 default).
        self.encoder = Encoder(1500, tx_buffer_s=settings.tx_buffer_s)
        self.decoder = Decoder(max_freq=3000)
        self.decoder._my_call = settings.callsign
        # P3 v0.95.20: initiales Band setzen (sonst Default "20m" bei
        # erstem Audio-Dump-Slot vor Bandwechsel)
        self.decoder.set_band(settings.band)
        self.adif = AdifWriter()

        # Stations-Statistik Logger + Warmup
        from core.station_stats import StationStatsLogger
        from core.antenna_pref import AntennaPreferenceStore
        from core.preset_store import PresetStore
        from core.locator_db import LocatorDB
        self._stats_logger = StationStatsLogger()
        self._stats_warmup_cycles = 6
        self._antenna_prefs = AntennaPreferenceStore()

        # Persistenter Locator-Cache: gefuettert aus CQ-Decodes (mw_cycle), PSK-
        # Reporter-Spots (direction_map_widget) und ADIF-Imports (qso_log).
        # Save bei closeEvent, Load hier.
        self.locator_db = LocatorDB()
        self.locator_db.load()

        # Persistenter RX-History-Cache (v0.73): merkt sich pro (band, mode)
        # die letzten 60 Min Empfangsdaten. Beim Karten-Open zeigt die Karte
        # die letzte Stunde — auch nach App-Restart. Save: gemeinsam mit
        # LocatorDB im Auto-Save-Timer (alle 5 Min) + closeEvent.
        from core.rx_history import RxHistoryStore
        self.rx_history_store = RxHistoryStore()
        loaded = self.rx_history_store.load_all()
        if loaded:
            print(f"[RxHistory] {loaded} Eintraege aus letzter Session geladen")

        # Karten-Widget (Lazy create, Schritt 9 verbindet Button im Settings-Dialog)
        from ui.direction_map_widget import LocatorCache
        self._locator_cache = LocatorCache()
        self._direction_map_dialog = None
        # Getrennte Preset-Dateien für Standard und DX (2h-Frist pro Band+FTMode)
        self._standard_store = PresetStore("presets_standard.json")
        self._dx_store = PresetStore("presets_dx.json")
        # Einmalige Migration aus altem config.json-Format.
        # P22 Final-R1 SOLLTE-1: Exception-Wrap damit ein Disk-Fehler in
        # der Migration den App-Start nicht crasht (migrate_from_settings
        # ruft intern _save_locked auf, das bei Fehler re-raised).
        for _store, _mode in (
            (self._standard_store, "standard"),
            (self._dx_store, "dx"),
        ):
            try:
                _store.migrate_from_settings(self.settings._data, mode=_mode)
            except Exception as _exc:
                print(f"[Kalibrierung] Migration {_mode} uebersprungen: {_exc}")

    def _init_qso_log(self):
        """QSO-Verzeichnis (Worked-Before) aus aktuellem Pfad + adif_import_path laden.

        Speist anschliessend die Locator-DB einmalig aus den ADIF-Dateien —
        damit existierende QSOs als qso_log_4/_6-Quellen sofort verfuegbar sind
        (priorisiert UNTER cq und psk, also ueberschreiben CQ-Decodes spaeter).
        """
        from log.qso_log import QSOLog
        self.qso_log = QSOLog()
        self.qso_log.load_directory(Path.cwd())
        import_path = self.settings.get("adif_import_path")
        if import_path:
            self.qso_log.load_directory(Path(import_path))
        # P1.QRZ-UPLOAD-UI-2: hochgeladene QSOs auch in qso_log
        hochgeladen_dir = Path.cwd() / "adif" / "hochgeladen"
        if hochgeladen_dir.is_dir():
            self.qso_log.load_directory(hochgeladen_dir)
        print(f"[QSOLog] {self.qso_log.worked_count()} unique Calls, {self.qso_log.qso_count()} QSOs")

        # ADIF-Daten in die Locator-DB pushen (qso_log-Source, prec_km 5/110).
        # Bei wiederholten App-Starts ueberschreibt cq_6/psk_6 hoeher-priorisiert.
        # AdifWriter speichert in <cwd>/adif/, also dort als Default suchen.
        adif_dir = Path.cwd() / "adif"
        n_loc = 0
        if adif_dir.is_dir():
            n_loc += self.locator_db.bulk_import_directory(adif_dir)
        # P1.QRZ-UPLOAD-UI-2: LocatorDB auch aus hochgeladen/
        if hochgeladen_dir.is_dir():
            n_loc += self.locator_db.bulk_import_directory(hochgeladen_dir)
        if import_path:
            n_loc += self.locator_db.bulk_import_directory(Path(import_path))
        if n_loc:
            print(f"[LocatorDB] {n_loc} Locators aus ADIF importiert "
                  f"({len(self.locator_db)} total in DB)")

    def _init_radio_state(self):
        """Radio via Factory + Reconnect-Counter + DX-Tune-Dialog Slot."""
        self.radio = create_radio(self.settings)
        self._reconnect_attempts = 0
        self._reconnect_countdown = 0
        self._dx_tune_dialog = None  # Aktiver DX-Tune Dialog
        self._tune_token = None  # Race-Token: TUNE-Callbacks bei Bandwechsel ungueltig
        # Normal-Preset-Alterungs-Hinweis: pro Band einmal pro Session zeigen
        self._normal_preset_warned_bands = set()
        self._has_sent_cq = False    # PSKReporter nur nach CQ anzeigen

    def _init_diversity_state(self):
        """Diversity-Variablen + Stations-Dicts + Tune-Anzeige-State."""
        # Diversity (simpel: Antenne pro Zyklus wechseln)
        self._rx_mode = "normal"  # "normal", "diversity", "dx_tuning"
        self._diversity_stations = {}  # key → FT8Message (akkumuliert)
        self._normal_stations = {}     # key → FT8Message (Normal, 2-Min-Fenster)
        self._diversity_ctrl = DiversityController()
        # P34: DynamicDiversityController parallel zur Statik. Default _active=False
        # (Toggle in Settings, nicht persistiert). Signal-Connect via
        # Qt.QueuedConnection beim spaeteren Slot-Setup.
        from core.dynamic_diversity import DynamicDiversityController
        self._dynamic_ctrl = DynamicDiversityController(self._diversity_ctrl)
        # P35 Bug A: Flag fuer aufgeschobene Diversity-Init (radio.ip=None).
        self._pending_diversity_init = None
        self._active_qso_targets: set = set()  # Stationen im aktiven QSO → 150s Aging
        self._pending_station_click = None  # P1.24: Klick waehrend TX → Buffer fuer naechsten Slot
        self._recent_logged_calls: dict[tuple[str, str], float] = {}  # P1.7 (v0.95.19): ADIF-Dedup (call, band) → ts
        # P2.OMNI-REDESIGN v4.0 (v0.95.23): True wenn OMNI VOR aktuellem QSO
        # aktiv war — _maybe_resume_omni resumed dann nach QSO-Ende.
        # Gesetzt von _pause_omni_if_active in 3 Entry-Pfaden, geloescht
        # bei Resume oder bei OMNI-HALT/Stop.
        self._omni_was_active_pre_qso: bool = False
        # P3 v0.95.20: Audio-Dump-Settings (in mw_cycle._on_cycle_decoded gelesen)
        self._audio_dump_enabled = self.settings.get("audio_dump_enabled", False)
        self._audio_dump_max_files = self.settings.get("audio_dump_max_files", 200)
        self._diversity_lock = threading.Lock()  # Race Condition Guard
        self._tune_active = False
        self._tune_freq_mhz = None

    def _init_power_state(self):
        """Auto TX Level Regelung (zweistufig: rfpower primär, audio sekundär)."""
        from core.rf_preset_store import RFPresetStore
        self._power_target = self.settings.get("power_preset", 10)  # Watt-Ziel vom Button
        self._fwdpwr_samples = []   # FWDPWR Messwerte waehrend TX
        self._rfpower_current = 50  # Aktuell gesetzter rfpower-Wert (0-100)
        self._rfpower_converged = False  # True wenn rfpower stabil
        self._was_converged = False  # True wenn aktuelle Konvergenz schon gespeichert
        self.rf_preset_store = RFPresetStore()
        # Migration aus altem rfpower_per_band-Eintrag (idempotent)
        self.rf_preset_store.migrate_from_settings(
            self.settings._data, radio="flexradio", default_watts=self._power_target
        )

    def _init_optional_features(self):
        """OMNI-TX (Easter Egg, Feldtest), Auto-Hunt, AP-Lite — alle deaktiviert by default."""
        # OMNI-CQ: Initialisieren (deaktiviert) — eigener Worker-Thread
        # mit absolut-UTC-Boundaries (P4.OMNI-NEUBAU v0.96.0). Kein
        # qso_state.cq_mode-Hack, keine cycle_tick-Pretrigger.
        from core.omni_cq import OmniCQ
        self._omni_cq = OmniCQ(
            encoder=self.encoder,
            diversity_ctrl=self._diversity_ctrl,
            timer=self.timer,
            my_call=self.settings.callsign,
            my_grid=self.settings.locator,
        )
        self._omni_cq.omni_stopped.connect(self._on_omni_stopped)
        self._omni_cq.cq_freq_changed.connect(self._on_omni_freq_changed)
        # P7.OMNI-SIMPLIFY: cq_count_changed (1 Counter mit Paritaet) +
        # parity_flipped (UI-Notification bei Wechsel)
        self._omni_cq.cq_count_changed.connect(self._on_omni_cq_count_changed)
        self._omni_cq.parity_flipped.connect(self._on_omni_parity_flipped)
        self._omni_cq.slot_action.connect(self._on_omni_slot_action)
        # V2-L3: letzten TX-Slot fuer Block-Wahl nach QSO-Ende tracken.
        self._last_qso_tx_even: bool | None = None
        # Button-Klick → start/stop OMNI
        self.control_panel.btn_omni_cq.toggled.connect(self._on_btn_omni_cq_toggled)
        self.control_panel.easter_egg_toggle_clicked.connect(self._on_easter_egg_toggle)

        # Auto-Hunt: Initialisieren (deaktiviert, zusammen mit OMNI-TX)
        from core.auto_hunt import AutoHunt
        self._auto_hunt = AutoHunt()
        self._auto_hunt.set_qso_log(self.qso_log)
        self._auto_hunt.set_band(self.settings.band)

        # v0.75 Auto-Hunt UI-Lifecycle
        self._easter_egg_active: bool = False
        self._auto_hunt_cooldown_seconds: int = 0
        # 1s-Polling fuer Live-Countdown waehrend aktiver Session
        self._auto_hunt_polling_timer = QTimer(self)
        self._auto_hunt_polling_timer.setInterval(1000)
        self._auto_hunt_polling_timer.timeout.connect(self._on_auto_hunt_polling_tick)
        # 5s UI-Reflexions-Cooldown nach Stop (verhindert Reflex-Klick)
        self._auto_hunt_cooldown_timer = QTimer(self)
        self._auto_hunt_cooldown_timer.setInterval(1000)
        self._auto_hunt_cooldown_timer.timeout.connect(self._on_auto_hunt_cooldown_tick)
        # Signal: stop_auto_hunt(reason) → UI-Cooldown-Lifecycle
        self._auto_hunt.auto_hunt_stopped.connect(self._on_auto_hunt_stopped)
        # Button-Klick: start/stop_auto_hunt
        self.control_panel.btn_auto_hunt.toggled.connect(self._on_btn_auto_hunt_toggled)

        # AP-Lite: Initialisieren (deaktiviert, AP_LITE_ENABLED=False)
        from core import ap_lite as _ap
        self._ap_lite = _ap.get_instance(encoder=self.encoder)

        # v0.88: Bandpilot — Stunden-genaue Empfehlung (Replacement v0.87)
        from core.mode_recommender import HourlyBandpilot
        self._bandpilot = HourlyBandpilot()
        self._bandpilot_pending = None
        self._bandpilot_tx_connected = False
        self._bandpilot_active_toast = None
        self._bandpilot_active_dialog = None

        # v0.88: Bandpilot-MD-Reports beim App-Start regenerieren
        self._init_bandpilot_recommendations()

        # v0.78: Initial-Sichtbarkeit der 3 Mode-Buttons (rx_mode + Easter-Egg)
        self._update_button_visibility()

    def _init_bandpilot_recommendations(self):
        """Beim App-Start ``auswertung/Bandpilot-<band>-FT8.md`` neu generieren.

        Aktuell loggt das Stats-Logger nur 20m + 40m FT8 (Stats-Filter v0.63).
        Pro Band ~50ms — Sync-Aufruf akzeptabel.
        """
        from pathlib import Path
        from core.bandpilot_md import write_bandpilot_md
        base = Path(__file__).parent.parent
        stats_dir = base / "statistics"
        output_dir = base / "auswertung"
        for band in ("20m", "40m"):
            try:
                write_bandpilot_md(stats_dir, output_dir, band, ft_mode="FT8")
            except Exception as e:  # noqa: BLE001
                print(f"[Bandpilot-MD] {band} fehlgeschlagen: {e}")

    def _init_psk_polling(self):
        """PSKReporter Timer (erste Abfrage nach 2 Min, danach alle 5 Min Rate-Limit)."""
        from PySide6.QtCore import QTimer
        self._psk_timer = QTimer(self)
        self._psk_timer.timeout.connect(self._fetch_psk_stats)
        self._psk_timer.start(120000)  # 2 Minuten fuer erste Abfrage
        self._psk_first_fetch = True
        self._psk_repeat_interval = 300000  # 5 Minuten (PSKReporter Rate-Limit)
        self._psk_last_fetch_time = None
        self._psk_band = ""

    def _init_locator_db_autosave(self):
        """LocatorDB alle 5 Min auf Disk schreiben.

        Schuetzt vor Datenverlust bei App-Crash oder Hard-Kill (z.B. durch
        kill_old_instances beim naechsten Start, das closeEvent ueberspringt).
        Atomic-Write im LocatorDB.save() macht das crash-sicher (.tmp + replace).
        """
        from PySide6.QtCore import QTimer
        self._locator_save_timer = QTimer(self)
        self._locator_save_timer.timeout.connect(self._autosave_locator_db)
        self._locator_save_timer.start(300_000)  # 5 Minuten

    def _autosave_locator_db(self):
        """Wird vom Timer aufgerufen — Save mit try/except (kein Crash bei IO-Fehler).

        Speichert LocatorDB UND RxHistoryStore (gemeinsame Persistenz-Strategie:
        atomarer Write, max 5 Min Datenverlust bei kill_old_instances)."""
        try:
            self.locator_db.save()
        except OSError as e:
            print(f"[LocatorDB] Auto-Save fehlgeschlagen: {e}")
        try:
            self.rx_history_store.save()
        except OSError as e:
            print(f"[RxHistory] Auto-Save fehlgeschlagen: {e}")

    def _init_propagation_polling(self):
        """Propagation: Hintergrund-Abruf + UI-Update jede Minute (Zeitkorrektur live)."""
        from PySide6.QtCore import QTimer
        from core import propagation as _prop
        self._prop_error_shown = False
        _prop.start_background_updater()
        self._prop_timer = QTimer(self)
        self._prop_timer.timeout.connect(self._update_propagation_ui)
        self._prop_timer.start(60_000)  # 1 Minute (Zeitkorrektur ist live)
        # Erster UI-Update nach kurzem Delay (Abruf läuft im Hintergrund)
        QTimer.singleShot(3000, self._update_propagation_ui)

    def _init_presence_watchdog(self):
        """Operator Presence (Totmannschalter, gesetzliche Pflicht DE).

        Fest 15 Min, nicht konfigurierbar, nicht umgehbar.
        Bei Ablauf: CQ stoppt, kein neuer TX. Laufendes QSO wird zu Ende gefuehrt.
        Maus reicht als Operator-Nachweis — 15 Min ohne Mausbewegung = nicht am Rechner.
        """
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QCursor
        _PRESENCE_TIMEOUT = 900  # 15 Minuten in Sekunden
        self._presence_remaining = _PRESENCE_TIMEOUT
        self._presence_timeout = _PRESENCE_TIMEOUT
        self._presence_expired = False
        self._presence_timer = QTimer(self)
        self._presence_timer.timeout.connect(self._on_presence_tick)
        self._presence_timer.start(1000)  # Jede Sekunde
        # Presence-Reset: Maus-Polling (alle 500ms QCursor.pos() pruefen)
        self._presence_last_mouse_pos = QCursor.pos()
        self._presence_poll_timer = QTimer(self)
        self._presence_poll_timer.timeout.connect(self._poll_mouse_activity)
        self._presence_poll_timer.start(500)

    def _init_cq_countdown_timer(self):
        """CQ-Freq Countdown: sekündlich aktualisieren (unabhängig vom Decode-Zyklus)."""
        from PySide6.QtCore import QTimer
        self._cq_countdown_timer = QTimer(self)
        self._cq_countdown_timer.timeout.connect(self._tick_cq_countdown)
        self._cq_countdown_timer.start(1000)

    def _init_statusbar(self):
        """Statusbar + Statistik-Indikator + Hilfe-Button."""
        self._update_statusbar()
        self.statusBar().setStyleSheet(
            "color: #888; font-family: Menlo; font-size: 11px; "
            "background-color: #111;"
        )
        # Statistik-Indikator (permanentes Widget, rechts in Statusbar)
        from PySide6.QtWidgets import QLabel as _QLabel
        self._stats_indicator = _QLabel("Statistik")
        self._stats_indicator.setStyleSheet(
            "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
        )
        self._stats_indicator.setVisible(self.settings.get("stats_enabled", True))
        self.statusBar().addPermanentWidget(self._stats_indicator)

        # P44 (v0.97.10): DT-Korrektur als eigenes Permanent-Widget rechts
        # in Statusbar neben _stats_indicator. Default grau, grün bei
        # aktiver Mess-Phase. Vorher: ganzer Statusbar-StyleSheet wurde
        # gewechselt → ALLE Texte grün (Bug).
        self._dt_indicator = _QLabel("DT: —")
        self._dt_indicator.setStyleSheet(
            "color: #555; font-family: Menlo; font-size: 11px; padding: 0 6px;"
        )
        self.statusBar().addPermanentWidget(self._dt_indicator)

        # Bundle D (v0.97.21): Slot-Progress-Bar rechts in Statusbar.
        # Zeigt aktuellen FT8/FT4/FT2-Slot-Fortschritt (0..cycle_dur s).
        # Farbe wechselt mit Slot-Parity: Cyan (Even) / Magenta (Odd).
        # Wird sekündlich aus `_tick_cq_countdown` aktualisiert.
        from PySide6.QtWidgets import QProgressBar as _QProgressBar
        self._slot_progress_bar = _QProgressBar()
        self._slot_progress_bar.setRange(0, 1000)
        self._slot_progress_bar.setValue(0)
        self._slot_progress_bar.setTextVisible(False)
        self._slot_progress_bar.setFixedSize(80, 14)
        self._slot_progress_bar.setToolTip(
            "FT8/FT4/FT2-Slot — Cyan = Even, Magenta = Odd. "
            "Balken füllt sich über die Slot-Dauer.")
        self._slot_progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #333; border-radius: 2px;"
            " background: #1a1a1a; }"
            "QProgressBar::chunk { background: #00CCFF; border-radius: 1px; }"
        )
        self._slot_progress_is_even = True
        self.statusBar().addPermanentWidget(self._slot_progress_bar)

        # P1.QRZ-UPLOAD-UI-2: Bulk-Cancel-Widget (initial versteckt)
        from PySide6.QtWidgets import (
            QWidget as _QW, QHBoxLayout as _QHL,
            QPushButton as _QPB2,
        )
        self._qrz_status_widget = _QW()
        _qrz_lay = _QHL(self._qrz_status_widget)
        _qrz_lay.setContentsMargins(0, 0, 0, 0)
        _qrz_lay.setSpacing(4)
        self._qrz_status_label = _QLabel("QRZ ↑")
        self._qrz_status_label.setStyleSheet(
            "color: #4488cc; font-family: Menlo; font-size: 11px; padding: 0 4px;"
        )
        self._qrz_status_cancel_btn = _QPB2("✕")
        self._qrz_status_cancel_btn.setFixedSize(18, 18)
        self._qrz_status_cancel_btn.setStyleSheet(
            "QPushButton { background: rgba(180,30,30,0.4); color: #FFAAAA;"
            "border: 1px solid #533; border-radius: 3px; font-size: 10px; padding: 0;}"
            "QPushButton:hover { background: rgba(220,40,40,0.6); }"
            "QPushButton:disabled { color: #555; }"
        )
        self._qrz_status_cancel_btn.clicked.connect(self._on_qrz_status_cancel_clicked)
        _qrz_lay.addWidget(self._qrz_status_label)
        _qrz_lay.addWidget(self._qrz_status_cancel_btn)
        self._qrz_status_widget.hide()
        self.statusBar().addPermanentWidget(self._qrz_status_widget)

        from PySide6.QtWidgets import QPushButton as _QPB
        _help_btn = _QPB(" ? ")
        _help_btn.setStyleSheet(
            "QPushButton { background: #1a2a3a; color: #88AACC; border: 1px solid #336;"
            "border-radius: 3px; font-size: 12px; font-weight: bold; padding: 2px 8px; }"
            "QPushButton:hover { background: #2a3a5a; }"
        )
        _help_btn.setFixedHeight(22)
        _help_btn.setToolTip(
            "Funktionsuebersicht — Feature Overview"
        )
        _help_btn.clicked.connect(self._on_help_clicked)
        self.statusBar().addPermanentWidget(_help_btn)
        # DT-Anzeige nur in der Statusbar-Message (kein separates Label mehr)

    def _setup_ui(self):
        self.rx_panel = RXPanel(
            my_call=self.settings.callsign,
            my_grid=self.settings.locator,
            country_filter=self.settings.get("country_filter", []),
            hidden_cols=self.settings.get("rx_panel_hidden_cols", []),
        )
        self.qso_panel = QSOPanel()
        # Logbuch mit ADIF-Dateien laden (AdifWriter schreibt in adif/ Unterordner)
        self.qso_panel.logbook.load_adif(Path.cwd() / "adif")
        self.qso_panel.upload_qrz.connect(self._on_qrz_upload)
        self.qso_panel.logbook.qso_clicked.connect(self._on_logbook_qso_clicked)
        # Bundle D (v0.97.21): Slot-Filter Signal-Verdrahtung (R1-F1).
        self.qso_panel.slot_filter_changed.connect(self.rx_panel.apply_slot_filter)
        # Tab-Wechsel: Detail-Overlay zuruecksetzen wenn User vom Logbuch weg navigiert
        self.qso_panel.tabs.currentChanged.connect(self._on_qso_tab_changed)
        self.control_panel = ControlPanel(callsign=self.settings.callsign)
        # P1.ANTENNE-COLLAPSE: Initial-State aus Settings laden + Persistenz-Hook
        _antenne_collapsed = self.settings.get("antenne_card_collapsed", False)
        self.control_panel._ant_card.set_collapsed(_antenne_collapsed)
        self.control_panel.antenne_collapse_changed.connect(
            self._on_antenne_collapse_changed)
        # P1.COLLAPSE-RADIO-MODEBAND (v0.95.17): Initial-State + Persistenz
        _modeband_collapsed = self.settings.get("modeband_card_collapsed", False)
        self.control_panel._modeband_card.set_collapsed(_modeband_collapsed)
        self.control_panel.modeband_collapse_changed.connect(
            self._on_modeband_collapse_changed)
        _radio_collapsed = self.settings.get("radio_card_collapsed", False)
        self.control_panel._radio_card.set_collapsed(_radio_collapsed)
        self.control_panel.radio_collapse_changed.connect(
            self._on_radio_collapse_changed)

        # QSO Detail Overlay (wird ueber Control Panel gelegt bei Logbuch-Klick)
        from ui.qso_detail_overlay import QSODetailOverlay
        self._detail_overlay = QSODetailOverlay()
        self._detail_overlay.upload_requested.connect(
            lambda rec: self._qrz_upload_single(rec))
        self._qrz_client = None  # Lazy init

        # Control Panel in ScrollArea einpacken — scrollbar wenn Fenster zu klein
        self._ctrl_scroll = QScrollArea()
        self._ctrl_scroll.setWidget(self.control_panel)
        self._ctrl_scroll.setWidgetResizable(True)
        self._ctrl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._ctrl_scroll.setMinimumWidth(320)
        self._ctrl_scroll.setStyleSheet(
            "QScrollArea { background: #08080e; border: none; }"
            "QScrollArea > QWidget > QWidget { background: #08080e; }"
            "QScrollBar:vertical { background: #111; width: 6px; }"
            "QScrollBar::handle:vertical { background: #333; border-radius: 3px; }"
        )

        # Right Panel: Stacked Widget (Control Panel + Detail Overlay)
        from PySide6.QtWidgets import QStackedWidget
        self._right_stack = QStackedWidget()
        self._right_stack.addWidget(self._ctrl_scroll)     # Index 0: Control Panel
        self._right_stack.addWidget(self._detail_overlay)   # Index 1: QSO Detail
        self._right_stack.setCurrentIndex(0)
        self._right_stack.setMinimumWidth(320)
        self._detail_overlay.btn_close.clicked.connect(
            lambda: self._right_stack.setCurrentIndex(0))
        # Delete-Signal: Logbuch loeschen + Overlay schliessen
        self._detail_overlay.delete_requested.connect(self._on_logbook_delete)


        # Alle 3 Panels in einem QSplitter → sichtbarer Trenner bleibt erhalten
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.rx_panel)
        self.splitter.addWidget(self.qso_panel)
        self.splitter.addWidget(self._right_stack)

        # EMPFANG + QSO 50:50, Control fix (wird in _restore_geometry überschrieben)
        self.splitter.setSizes([500, 500, 400])
        self.splitter.setStretchFactor(0, 1)  # RX: dehnen
        self.splitter.setStretchFactor(1, 1)  # QSO: dehnen
        self.splitter.setStretchFactor(2, 0)  # Control: nicht dehnen

        # RX-Warnung: rotes Banner oben im Fenster (sichtbar wenn RX deaktiviert)
        self._rx_warning_label = QLabel("⚠   EMPFANG RX DEAKTIVIERT   ⚠")
        self._rx_warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rx_warning_label.setFixedHeight(26)
        self._rx_warning_label.setStyleSheet(
            "QLabel { background-color: rgba(160, 0, 0, 0.90); color: #FF4444; "
            "font-family: Menlo; font-size: 12px; font-weight: bold; "
            "padding: 2px; letter-spacing: 2px; border-bottom: 1px solid #FF0000; }"
        )
        self._rx_warning_label.setVisible(False)

        # Debug-Konsole (unter dem Haupt-Splitter, ein-/ausblendbar via Ctrl+D)
        from ui.debug_console import DebugConsoleWidget
        self._debug_console = DebugConsoleWidget()

        # Vertikaler Splitter: oben Hauptbereich, unten Debug-Konsole
        self._main_vsplitter = QSplitter(Qt.Orientation.Vertical)
        self._main_vsplitter.addWidget(self.splitter)
        self._main_vsplitter.addWidget(self._debug_console)
        self._main_vsplitter.setSizes([600, 0])  # Debug standardmaessig ausgeblendet
        self._main_vsplitter.setStretchFactor(0, 1)
        self._main_vsplitter.setStretchFactor(1, 0)

        # Debug sichtbar? Aus Settings laden
        debug_visible = self.settings.get("debug_console_visible", False)
        self._debug_console.setVisible(debug_visible)
        if debug_visible:
            self._main_vsplitter.setSizes([500, 150])

        # Ctrl+D: Debug-Konsole Toggle
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+D"), self, self._toggle_debug_console)

        _container = QWidget()
        _container.setStyleSheet("background: transparent;")
        _vlay = QVBoxLayout(_container)
        _vlay.setContentsMargins(0, 0, 0, 0)
        _vlay.setSpacing(0)
        _vlay.addWidget(self._rx_warning_label)
        _vlay.addWidget(self._main_vsplitter)
        self.setCentralWidget(_container)

    def _connect_signals(self):
        # Karten-Snapshot: Decoder-Thread → GUI-Thread (QueuedConnection erzwingt
        # Marshalling, Slot laeuft GUI-thread-seitig)
        self.direction_map_signal.connect(
            self._on_direction_map_snapshot, Qt.QueuedConnection
        )

        # P34: Dynamic-Ratio-Wechsel → GUI-Slot (Decoder-Thread → GUI-Thread)
        self._dynamic_ctrl.ratio_changed_dynamic.connect(
            self._on_dynamic_ratio_changed, Qt.QueuedConnection
        )

        # RX Panel → QSO starten + RX-Toggle
        self.rx_panel.station_clicked.connect(self._on_station_clicked)
        self.rx_panel.rx_toggled.connect(self._on_rx_panel_toggled)
        self.rx_panel.country_filter_changed.connect(self._on_country_filter_changed)
        self.rx_panel.hidden_cols_changed.connect(self._on_rx_hidden_cols_changed)

        # Control Panel
        self.control_panel.mode_changed.connect(self._on_mode_changed)
        self.control_panel.band_changed.connect(self._on_band_changed)
        self.control_panel.power_changed.connect(self._on_power_changed)
        self.control_panel.advance_clicked.connect(self._on_advance)
        self.control_panel.cancel_clicked.connect(self._on_cancel)
        self.control_panel.cq_clicked.connect(self._on_cq_clicked)
        self.control_panel.tune_clicked.connect(self._on_tune_clicked)
        self.control_panel.rx_mode_changed.connect(self._on_rx_mode_changed)
        self.control_panel.einmessen_clicked.connect(self._handle_dx_tuning)
        self.control_panel.settings_clicked.connect(self._on_settings_clicked)
        self.control_panel.map_clicked.connect(lambda: self.open_direction_map())
        # Manuelle TX-Frequenz im Normal-Modus: Klick im Histogramm + Spinbox
        self.control_panel._freq_hist.tx_freq_clicked.connect(self._on_normal_tx_freq_clicked)
        self.control_panel._tx_freq_spin.valueChanged.connect(self._on_normal_tx_freq_spin_changed)

        # QSO State Machine
        self.qso_sm.state_changed.connect(self._on_state_changed)
        self.qso_sm.send_message.connect(self._on_send_message)
        self.qso_sm.qso_complete.connect(self._on_qso_complete)
        # P33 (v0.97.14): visual feuert sofort bei 73-Empfang fuer ✓-Anzeige,
        # confirmed (full) feuert nach Courtesy-73-Send fuer alle weiteren Ops.
        self.qso_sm.qso_confirmed_visual.connect(self._on_qso_confirmed_visual)
        self.qso_sm.qso_confirmed.connect(self._on_qso_confirmed)
        self.qso_sm.qso_timeout.connect(self._on_qso_timeout)
        self.qso_sm.tx_slot_for_partner.connect(self._on_tx_slot_for_partner)
        # P1.9 (v0.95.3): CQ-Reply waehrend CQ_CALLING → Encoder-Replace versuchen
        self.qso_sm.try_replace_pending_tx.connect(self._on_try_replace_pending_tx)
        self.qso_sm.queue_changed.connect(self._on_caller_queue_changed)

        # Timer
        self.timer.cycle_tick.connect(self._on_cycle_tick)
        self.timer.cycle_start.connect(self._on_cycle_start)

    def _toggle_debug_console(self):
        """Debug-Konsole ein/ausblenden (Ctrl+D)."""
        visible = not self._debug_console.isVisible()
        self._debug_console.setVisible(visible)
        if visible:
            self._main_vsplitter.setSizes([500, 150])
        else:
            self._main_vsplitter.setSizes([600, 0])
        self.settings.set("debug_console_visible", visible)
        self.settings.save()

    def _on_help_clicked(self):
        """Hilfe-Dialog oeffnen mit Feature-Dokumentation."""
        from ui.help_dialog import HelpDialog
        lang = self.settings.get("language", "de")
        dlg = HelpDialog(self, language=lang)
        dlg.exec()

    # ── Easter Egg ───────────────────────────────────────────────

    def _on_easter_egg_toggle(self):
        """Easter Egg: Klick auf Versionsnummer = Test-Override fuer Mode-Coupling.

        v0.78: Buttons sind im RX-Mode "diversity" eh sichtbar — Easter-Egg ist
        nur Override fuer "normal". Persistiert NICHT — jede Session und jeder
        RX-Mode-Wechsel beginnt mit deaktiviertem Override.
        """
        self._easter_egg_active = not self._easter_egg_active
        if not self._easter_egg_active:
            # Aktive Modi sauber stoppen — Signal-Slots kuemmern sich um UI-Cleanup
            if self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("easter_egg_off")
            if self._omni_cq.is_active():
                self._omni_cq.stop("easter_egg_off")
            # R1-Fix: 5s UI-Cooldown abbrechen wenn Button versteckt wird —
            # sonst inkonsistenter Button-State bei naechster Easter-Egg-Aktivierung
            if self._auto_hunt_cooldown_timer.isActive():
                self._auto_hunt_cooldown_timer.stop()
                self.control_panel.btn_auto_hunt.setEnabled(True)
                self.control_panel.btn_auto_hunt.setText("AUTO HUNT")
                self._auto_hunt_cooldown_seconds = 0
        self._update_button_visibility()
        print(f"[Easter-Egg] Override {'aktiv' if self._easter_egg_active else 'inaktiv'}")
        self._update_statusbar()

    # ── Mode-Coupling Buttons (v0.78) ────────────────────────────

    def _update_button_visibility(self):
        """3-Button-Layout mode-abhaengig + Easter-Egg-Override.

        Plan v0.78:
        - RX-Mode "normal":     nur btn_cq sichtbar
        - RX-Mode "diversity":  btn_omni_cq + btn_auto_hunt sichtbar, btn_cq versteckt
        - Easter-Egg-Override:  in "normal" zusaetzlich alle Power-User-Buttons sichtbar

        Wird gerufen nach Init, RX-Mode-Wechsel und Easter-Egg-Toggle.
        """
        rx_mode = getattr(self, "_rx_mode", "normal")
        is_diversity = (rx_mode == "diversity")
        show_power_buttons = is_diversity or self._easter_egg_active
        self.control_panel.btn_omni_cq.setHidden(not show_power_buttons)
        self.control_panel.btn_auto_hunt.setHidden(not show_power_buttons)
        # btn_cq: in Diversity unsichtbar, sonst sichtbar
        self.control_panel.btn_cq.setHidden(is_diversity)

    # ── OMNI-TX UI-Lifecycle (v0.78) ─────────────────────────────

    def _on_btn_omni_cq_toggled(self, checked: bool):
        """User-Klick auf btn_omni_cq: OMNI starten/stoppen.

        P4.OMNI-NEUBAU (v0.96.0): OMNI ist eigenstaendig — kein
        qso_state.cq_mode mehr. OMNI emittet selbst CQ via encoder.transmit().
        Bei eingehender Antwort uebergibt mw_cycle.on_message_decoded
        an qso_state.start_qso (Hunt-Pfad).

        Mutually-exclusive: laufender Auto-Hunt wird via 'superseded' gestoppt.
        Bei aktivem QSO Toggle blockieren (UX-Hilfe — verhindert Klick-Nirvana).
        """
        if checked and not self._omni_cq.is_active():
            if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
                btn = self.control_panel.btn_omni_cq
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                self.statusBar().showMessage(
                    "OMNI-CQ nur startbar wenn kein aktives QSO laeuft "
                    "— erst laufendes QSO beenden",
                    4000,
                )
                return
            if self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("superseded")
            self._omni_cq.start()
            self.control_panel.update_omni_tx(True)
            self._update_statusbar()
            print("[OMNI-CQ] User-Start")
        elif not checked and self._omni_cq.is_active():
            self._omni_cq.stop("manual_halt")

    def _on_omni_stopped(self, reason: str):
        """Slot fuer OmniCQ.omni_stopped(reason): Button-State + Statusbar
        zuruecksetzen + Pre-QSO-Flag invalidieren.

        R1 R4 KRITISCH: _omni_was_active_pre_qso explizit auf False — sonst
        koennte ein Caller-Queue-QSO nach Stop fälschlich `_maybe_resume_omni`
        triggern.
        """
        btn = self.control_panel.btn_omni_cq
        btn.blockSignals(True)
        btn.setChecked(False)
        btn.blockSignals(False)
        self._omni_was_active_pre_qso = False
        # V2-L3 Defense-in-Depth: Slot-Tracking nullen.
        self._last_qso_tx_even = None
        self.control_panel.update_omni_tx(False)
        self._update_statusbar()
        print(f"[OMNI-CQ-UI] Stop ({reason})")

    def _on_omni_freq_changed(self, freq_hz: int):
        """OMNI hat neue CQ-Audiofrequenz gewählt (Sticky-Gap-Algo)."""
        print(f"[OMNI-CQ] CQ-Audiofrequenz: {freq_hz} Hz")
        self._update_statusbar()

    @Slot(int, bool)
    def _on_omni_cq_count_changed(self, remaining: int, tx_even: bool):
        """OMNI CQ-Counter (P23: Down-Counter) — Statusbar aktualisieren."""
        self._update_statusbar()

    @Slot(bool)
    def _on_omni_parity_flipped(self, new_tx_even: bool):
        """OMNI Paritaets-Wechsel — User-Notification + Statusbar.

        P11 (10.05.2026 Mike-Field-Test): force repaint() weil Qt-EventLoop
        showMessage() manchmal verzoegert anzeigt — Mike sah veraltetes (O)
        nach Flip auf Even.
        """
        parity_str = "Even" if new_tx_even else "Odd"
        print(f"[OMNI-CQ-UI] Paritaets-Wechsel auf {parity_str}")
        self._update_statusbar()
        # P11: force-repaint damit der neue Wert sofort sichtbar ist
        self.statusBar().repaint()

    @Slot(str, bool, bool)
    def _on_omni_slot_action(self, label: str, is_tx: bool, target_even: bool):
        """P7.OMNI-SIMPLIFY: OMNI emittet slot_action NUR bei TX-Slot.

        TX-Slot wird ueber encoder.tx_started -> qso_panel.add_tx angezeigt
        (Sende-Eintrag). Hier ist nichts zu tun. RX-Anzeige (Horche) entfaellt
        bei P7 — OMNI ist passiver CQ-Modus, RX-Stationen kommen ueber
        rx_panel an.
        """
        pass

    # ── Auto-Hunt UI-Lifecycle (v0.75) ───────────────────────────

    def _on_btn_auto_hunt_toggled(self, checked: bool):
        """User-Klick auf btn_auto_hunt: start/stop_auto_hunt.

        Mutually-exclusive: laufendes OMNI-TX wird via "superseded" gestoppt.
        """
        if checked and not self._auto_hunt.active:
            if self._omni_cq.is_active():
                self._omni_cq.stop("superseded")
            self._auto_hunt.start_auto_hunt(600)
            self._auto_hunt_polling_timer.start()
            self._on_auto_hunt_polling_tick()  # initialer Text-Set
            print("[Auto-Hunt] User-Start (10 Min)")
        elif not checked and self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("manual_halt")

    def _on_auto_hunt_stopped(self, reason: str):
        """Slot fuer auto_hunt_stopped(reason): startet UI-Reflexions-Cooldown.

        5 Sekunden disabled-State auf btn_auto_hunt (Reflex-Klick verhindern),
        dann zurueck zu Idle.
        """
        self._auto_hunt_polling_timer.stop()
        btn = self.control_panel.btn_auto_hunt
        # Wenn Button im checked-State (manual_halt-Klick), zurueck setzen ohne
        # erneuten toggled-Trigger
        btn.blockSignals(True)
        btn.setChecked(False)
        btn.blockSignals(False)
        btn.setEnabled(False)
        self._auto_hunt_cooldown_seconds = 5
        btn.setText(f"AUTO HUNT ({self._auto_hunt_cooldown_seconds})")
        self._auto_hunt_cooldown_timer.start()
        print(f"[Auto-Hunt-UI] Stop ({reason}) → 5s Reflexions-Cooldown")

    def _on_auto_hunt_cooldown_tick(self):
        """1s-Tick waehrend 5s UI-Reflexions-Cooldown."""
        self._auto_hunt_cooldown_seconds -= 1
        btn = self.control_panel.btn_auto_hunt
        if self._auto_hunt_cooldown_seconds > 0:
            btn.setText(f"AUTO HUNT ({self._auto_hunt_cooldown_seconds})")
        else:
            btn.setText("AUTO HUNT")
            btn.setEnabled(True)
            self._auto_hunt_cooldown_timer.stop()

    def _on_auto_hunt_polling_tick(self):
        """1s-Polling waehrend aktiver Session: Live-Countdown auf Button."""
        if not self._auto_hunt.active:
            self._auto_hunt_polling_timer.stop()
            return
        sec = self._auto_hunt.seconds_remaining()
        m, s = divmod(sec, 60)
        self.control_panel.btn_auto_hunt.setText(f"AUTO HUNT — {m}:{s:02d}")

    # ── Propagation ──────────────────────────────────────────────

    def _update_propagation_ui(self):
        """Propagations-Balken aus Hintergrund-Cache aktualisieren."""
        # Init-Race-Guard: _set_band kann band_changed-Signal feuern bevor
        # _init_propagation_polling gelaufen ist (Init-Reihenfolge-Latent-Bug,
        # aufgetaucht beim v0.75 App-Restart).
        if not hasattr(self, "_prop_error_shown"):
            return
        from core import propagation as _prop
        conditions = _prop.get_conditions()
        if conditions is None:
            # Netzwerkfehler — Balken ausblenden + einmalige Meldung
            self.control_panel.update_propagation(None)
            if not self._prop_error_shown:
                self._prop_error_shown = True
                QMessageBox.information(
                    self, "Propagation",
                    "Kein Netzwerk — keine Propagationsdaten verfügbar."
                )
        else:
            self._prop_error_shown = False   # Reset für nächsten Fehler
            self.control_panel.update_propagation(
                conditions, active_band=self.settings.band)

    # ── PSKReporter ──────────────────────────────────────────────

    def _fetch_psk_stats(self):
        # 11.05.2026 P28: strategische Debug-Punkte fuer PSK-Pipeline
        # (Mike: "geht anfrage raus ja/nein kommt antwort ja/nein
        # verarbeiten wir sie ja/nein").
        from core.debug_log import debug_log as _dbg
        if not self._has_sent_cq:
            self.control_panel.psk_label.setText("PSK: — (nur nach CQ)")
            self.control_panel.psk_label.setStyleSheet(
                "color: #557766; font-family: Menlo; font-size: 10px; padding: 2px;"
            )
            _dbg("PSK", "SKIP — _has_sent_cq=False (noch keine CQ gesendet)")
            return
        # Nach erster Abfrage auf 3-Min-Intervall wechseln
        if self._psk_first_fetch:
            self._psk_first_fetch = False
            self._psk_timer.setInterval(self._psk_repeat_interval)  # 5 Minuten
            _dbg("PSK", "first fetch — Timer-Intervall auf 5 Min umgestellt")
        self._psk_band = self.settings.band.upper()
        _dbg("PSK", f"TRIGGER fetch — band={self._psk_band} mode={self.settings.mode}")
        threading.Thread(target=self._psk_worker, daemon=True).start()

    def _psk_worker(self):
        import urllib.request
        import xml.etree.ElementTree as ET
        from datetime import datetime, timezone
        from core.debug_log import debug_log as _dbg

        call = self.settings.callsign
        my_grid = self.settings.locator
        mode = self.settings.mode.upper()
        try:
            url = (f"https://retrieve.pskreporter.info/query?"
                   f"senderCallsign={call}&flowStartSeconds=-600&mode={mode}")
            _dbg("PSK", f"REQUEST call={call} mode={mode} window=600s")
            req = urllib.request.Request(
                url, headers={"User-Agent": "SimpleFT8/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read().decode("utf-8")
            _dbg("PSK", f"RESPONSE OK bytes={len(xml_data)}")

            root = ET.fromstring(xml_data)
            from core.geo import grid_to_latlon, distance_km
            my_pos = grid_to_latlon(my_grid)
            if not my_pos:
                _dbg("PSK", f"ABORT — my_pos None fuer Grid='{my_grid}'")
                return

            reports = root.findall(".//receptionReport")
            spots = []
            for rr in reports:
                loc = rr.get("receiverLocator", "")
                rx_call = rr.get("receiverCallsign", "")
                rx_dxcc = rr.get("receiverDXCC", "")
                pos = grid_to_latlon(loc[:4]) if len(loc) >= 4 else None
                if pos:
                    km = int(distance_km(
                        my_pos[0], my_pos[1], pos[0], pos[1]
                    ))
                    dlat = pos[0] - my_pos[0]
                    dlon = pos[1] - my_pos[1]
                    bearing = math.degrees(math.atan2(dlon, dlat)) % 360
                    spots.append((km, bearing, rx_call, rx_dxcc))
            _dbg("PSK", f"PARSED reception_reports={len(reports)} valid_spots={len(spots)}")

            if not spots:
                self.control_panel.update_psk_stats(
                    0, 0, 0, "", "", 0, 0, 0, 0
                )
                _dbg("PSK", "UPDATE UI: keine Spots (Label 'PSK: keine Spots')")
                return

            spots.sort(key=lambda x: -x[0])
            avg_km = sum(s[0] for s in spots) // len(spots)
            max_spot = spots[0]

            n_km = max(
                (s[0] for s in spots if 315 <= s[1] or s[1] < 45), default=0
            )
            e_km = max(
                (s[0] for s in spots if 45 <= s[1] < 135), default=0
            )
            s_km = max(
                (s[0] for s in spots if 135 <= s[1] < 225), default=0
            )
            w_km = max(
                (s[0] for s in spots if 225 <= s[1] < 315), default=0
            )

            self._psk_last_fetch_time = datetime.now(timezone.utc).strftime("%H:%M")
            self.control_panel.update_psk_stats(
                len(spots), avg_km, max_spot[0],
                max_spot[2], max_spot[3],
                n_km, e_km, s_km, w_km,
                band=self._psk_band,
                fetch_time=self._psk_last_fetch_time,
            )
            _dbg("PSK", (
                f"UPDATE UI: spots={len(spots)} avg={avg_km}km max={max_spot[0]}km "
                f"({max_spot[2]}/{max_spot[3]}) band={self._psk_band}"
            ))
        except Exception as e:
            _dbg("PSK", f"ERROR {type(e).__name__}: {e}")
            print(f"[PSK] Fehler: {e}")

    # ── Settings ─────────────────────────────────────────────────

    @Slot(bool)
    def _on_antenne_collapse_changed(self, collapsed: bool) -> None:
        """P1.ANTENNE-COLLAPSE: Persistiert Toggle-State in Settings."""
        self.settings.set("antenne_card_collapsed", collapsed)
        self.settings.save()

    @Slot(bool)
    def _on_modeband_collapse_changed(self, collapsed: bool) -> None:
        """P1.COLLAPSE-RADIO-MODEBAND: persist Modus+Band-Card collapse state."""
        self.settings.set("modeband_card_collapsed", collapsed)
        self.settings.save()

    @Slot(bool)
    def _on_radio_collapse_changed(self, collapsed: bool) -> None:
        """P1.COLLAPSE-RADIO-MODEBAND: persist Radio-Card collapse state."""
        self.settings.set("radio_card_collapsed", collapsed)
        self.settings.save()

    @Slot()
    def _on_settings_clicked(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self._update_statusbar()
            self.qso_sm.max_calls = self.settings.get("max_calls", 3)
            # v0.93: OPERATE_CYCLES + diversity_operate_cycles entfernt (1h-Frist zeit-basiert)
            self.radio.tx_audio_level = (
                self.settings.get("tx_level", 100) / 100.0
            )
            if self.radio.ip:
                self.radio.set_power(self.settings.get("power_preset", 15))
            # Debug-Konsole Toggle aus Settings
            debug_vis = self.settings.get("debug_console_visible", False)
            self._debug_console.setVisible(debug_vis)
            if debug_vis:
                self._main_vsplitter.setSizes([500, 150])
            else:
                self._main_vsplitter.setSizes([600, 0])
            # P3 v0.95.20: Audio-Dump-Settings live aktualisieren
            self._audio_dump_enabled = self.settings.get("audio_dump_enabled", False)
            self._audio_dump_max_files = self.settings.get("audio_dump_max_files", 200)
            # P50 (v0.97.20): Sichtbare Bänder live aktualisieren
            self.apply_visible_bands()

    def apply_visible_bands(self):
        """P50 (v0.97.20): Sichtbarkeits-Toggle für Band-Buttons anwenden.

        Liest ``enabled_bands`` aus Settings (defensive Filter dort)
        und gibt die Liste an ``ControlPanel.set_visible_bands``.
        Aktuelles Band bleibt sichtbar (R1-F1 in ControlPanel).
        Wird gerufen beim App-Start und nach Settings-Dialog-OK.
        """
        bands = self.settings.get_enabled_bands()
        self.control_panel.set_visible_bands(bands)

    def _update_statusbar(self):
        work_freq = self.settings.frequency_mhz
        if getattr(self, '_tune_active', False) and getattr(self, '_tune_freq_mhz', None):
            freq_display = f"TUNE: {self._tune_freq_mhz * 1000:.3f} kHz"
        else:
            freq_display = f"{work_freq * 1000:.3f} kHz"
        freq = work_freq  # Rückwärtskompatibilität für restliche Nutzung
        mode_labels = {
            "normal": "Normal",
            "diversity": "DIVERSITY",
        }
        mode_str = mode_labels.get(self._rx_mode, "Normal")
        if getattr(self, '_omni_cq', None) and self._omni_cq.is_active():
            # P7.OMNI-SIMPLIFY: 1 Counter mit aktueller Paritaet (E/O/?).
            # P31 (11.05.2026): Display-Wert (pre-decrement) statt cq_remaining
            # (post-decrement) — konsistent mit qso_panel. ↻10/9/.../1 → ↻10.
            parity = self._omni_cq.cq_tx_even_display
            if parity is True:
                parity_str = "E"
            elif parity is False:
                parity_str = "O"
            else:
                parity_str = "—"  # noch nicht initialisiert
            omni_str = f"  Ω CQ={self._omni_cq.cq_remaining_display} ({parity_str})"
        else:
            omni_str = ""
        # DT-Korrektur Status — P44 (v0.97.10): eigenes Permanent-Widget
        # _dt_indicator (rechts in Statusbar neben _stats_indicator).
        # Globaler Statusbar-Style bleibt grau wie in __init__ gesetzt —
        # nicht mehr dynamisch ändern (sonst werden ALLE Texte grün).
        from core import ntp_time
        dt_phase = ntp_time._phase
        if ntp_time._correction == 0.0 and ntp_time._is_initial:
            dt_text, dt_color = "DT: —", "#888"
        elif dt_phase == "measure":
            dt_text, dt_color = "DT: Korrektur", "#00DD66"
        else:
            dt_text, dt_color = "DT: Aktiv", "#888"
        if hasattr(self, '_dt_indicator'):
            self._dt_indicator.setText(dt_text)
            self._dt_indicator.setStyleSheet(
                f"color: {dt_color}; font-family: Menlo; "
                f"font-size: 11px; padding: 0 6px;"
            )
        # P47 (v0.97.11): Filter-Anzeige entfernt — war irrefuehrend
        # (FT2 zeigte 100-4000 Hz, Decoder lief faktisch auf 3000 Hz).
        # AP-Lite
        ap_str = ""
        if hasattr(self, '_ap_lite') and self._ap_lite.enabled:
            r = self._ap_lite.rescue_count
            a = self._ap_lite.attempt_count
            if a > 0:
                ap_str = f"  |  AP: {r}/{a}"
            else:
                ap_str = "  |  AP: aktiv"
        # CQ-Freq Status + Antenna Preference
        cq_hz = getattr(self._diversity_ctrl, 'cq_freq_hz', None)
        recalc = getattr(self._diversity_ctrl, '_recalc_count', 0)
        freq_str = f"  |  Freq: #{recalc} {cq_hz}Hz" if cq_hz else ""
        # Smart Antenna waehrend QSO
        from core.qso_state import QSOState
        _in_qso = self.qso_sm.state not in (
            QSOState.IDLE, QSOState.TIMEOUT, QSOState.CQ_CALLING, QSOState.CQ_WAIT)
        if _in_qso and self.qso_sm.qso.their_call:
            if (self._rx_mode == "diversity"
                    and hasattr(self, '_antenna_prefs')):
                pref_entry = self._antenna_prefs.get_pref(self.qso_sm.qso.their_call)
                if pref_entry:
                    # Einheitliches Format: ANT1 schlicht, ANT2 mit ↑Gewinn
                    if pref_entry['best_ant'] == "A1":
                        freq_str += "  |  RX: ANT1"
                    else:
                        delta = pref_entry.get('delta_db')
                        if delta is None:
                            freq_str += "  |  RX: ANT2"
                        else:
                            freq_str += f"  |  RX: ANT2 ↑{abs(delta):.1f} dB"
            elif self._rx_mode == "normal":
                freq_str += "  |  RX: ANT1"
        # P44 (v0.97.10): {dt_text} raus aus zentralem msg — DT erscheint
        # jetzt nur noch im eigenen _dt_indicator-Widget rechts.
        # P47 (v0.97.11): Filter-Anzeige raus — war irrefuehrend.
        msg = (f"{self.settings.callsign}  |  {self.settings.locator}  |  "
               f"{self.settings.mode} {self.settings.band}  |  "
               f"{freq_display}  |  "
               f"{mode_str}{omni_str}{freq_str}{ap_str}")
        self.statusBar().showMessage(msg)

        # Live-QSO-Status oben im QSO-Panel — waehrend aktivem QSO sichtbar
        # welche RX-Antenne mit wieviel Gewinn genutzt wird (User muss nicht
        # in die Statusbar schauen). Reset uebernimmt qso_panel.add_qso_complete.
        # P1.15: Status-Anzeige `→ Call | RX: ANT` entfernt (Mike: stoerend)

    # ── Hilfsfunktionen ──────────────────────────────────────────

    @staticmethod
    def _msgbox_style() -> str:
        return styles.MSGBOX_STYLE

    def _tick_cq_countdown(self):
        """Sekündlicher Update des CQ-Freq-Countdown-Balkens.
        Wert kommt aus slot-synchronem Such-Counter (~60s, friert bei Pause ein).

        P9 (10.05.2026 Mike-Field-Test): zusaetzlich Re-Mess-Countdown jede
        Sekunde refresht (vorher nur bei Diversity-Switch ~10 Min sichtbar).
        Bundle D (v0.97.21): zusätzlich Slot-Progress-Bar in der Statusbar
        aktualisieren (cyan/magenta je Slot-Parity).
        """
        if self._rx_mode == "diversity" and self._diversity_ctrl.cq_freq_hz is not None:
            self.control_panel.update_cq_freq_countdown(
                self._diversity_ctrl.seconds_until_search)
            # P34-Stufe2: update_remeasure_countdown ist No-Op (1h-Frist
            # entfallen). Aufruf bleibt fuer API-Stabilitaet zukuenftiger
            # Refactors weg.
        else:
            self.control_panel.set_cq_countdown_visible(False)
        # Bundle D: Slot-Progress-Bar
        self._update_slot_progress_bar()

    def _update_slot_progress_bar(self):
        """Bundle D (v0.97.21): Statusbar-Slot-Balken aktualisieren.

        Liest `cycle_dur` vom Timer (FT8=15, FT4=7.5, FT2=3.8). Berechnet
        Fortschritt im aktuellen Slot (0..1000 Promille). Wechselt Farbe
        je Slot-Parity: Cyan `#00CCFF` (Even) / Magenta `#FF66CC` (Odd).
        Farb-Update nur bei Parity-Wechsel (Stylesheet-Reset ist teuer).
        """
        if not hasattr(self, "_slot_progress_bar"):
            return
        cycle_dur = getattr(self.timer, "cycle_duration", 15.0)
        if cycle_dur <= 0:
            return
        import time as _t
        now = _t.time()
        cycle_num = int(now / cycle_dur)
        is_even = (cycle_num % 2 == 0)
        progress_in_slot = (now % cycle_dur) / cycle_dur
        self._slot_progress_bar.setValue(int(progress_in_slot * 1000))
        if is_even != self._slot_progress_is_even:
            self._slot_progress_is_even = is_even
            chunk = "#00CCFF" if is_even else "#FF66CC"  # cyan / magenta
            self._slot_progress_bar.setStyleSheet(
                "QProgressBar { border: 1px solid #333; border-radius: 2px;"
                " background: #1a1a1a; }"
                f"QProgressBar::chunk {{ background: {chunk}; border-radius: 1px; }}"
            )

    def _restore_geometry(self):
        """Fenstergeometrie + Splitter-Breiten aus Settings laden."""
        w = self.settings.get("window_w")
        h = self.settings.get("window_h")
        x = self.settings.get("window_x")
        y = self.settings.get("window_y")
        if w and h:
            self.resize(int(w), int(h))
        if x is not None and y is not None:
            self.move(int(x), int(y))
        sizes = self.settings.get("splitter_sizes")
        if sizes and len(sizes) == 3:
            self.splitter.setSizes([int(s) for s in sizes])

    # ── Operator Presence (Totmannschalter) ─────────────────────

    def _poll_mouse_activity(self):
        """Alle 500ms: Hat sich die Maus bewegt? → Presence Reset.

        Bulletproof-Methode: kein EventFilter noetig, funktioniert immer.
        """
        from PySide6.QtGui import QCursor
        pos = QCursor.pos()
        if pos != self._presence_last_mouse_pos:
            self._presence_last_mouse_pos = pos
            self._reset_presence()


    def _reset_presence(self):
        """Operator ist aktiv — Timer zuruecksetzen."""
        was_expired = self._presence_expired
        self._presence_remaining = self._presence_timeout
        self._presence_expired = False
        if was_expired:
            print("[Presence] Operator zurueck — TX freigegeben")
            # CQ wieder starten wenn vorher aktiv war
            if self.qso_sm._was_cq or self.qso_sm.cq_mode:
                self.qso_sm.start_cq()
                self.control_panel.set_cq_active(True)
                print("[Presence] CQ automatisch wieder aufgenommen")

    def _on_presence_tick(self):
        """Jede Sekunde: Countdown herunterzaehlen."""
        if self._presence_remaining > 0:
            self._presence_remaining -= 1

        self.control_panel.update_presence(self._presence_remaining)

        if self._presence_remaining <= 0 and not self._presence_expired:
            self._presence_expired = True
            print("[Presence] TIMEOUT — Operator nicht anwesend, CQ wird gestoppt")
            # Auto-Hunt sofort stoppen (Defense-in-Depth zur 10-Min-Hard-Cap).
            # Reason "totmann_expired": Cooldowns + _last_tx_even bleiben,
            # damit User bei Wiederkehr explizit fortsetzen kann (Pflicht-Restart).
            if self._auto_hunt.active:
                self._auto_hunt.stop_auto_hunt("totmann_expired")
            # v0.78: OMNI-TX bei Totmann-Expire stoppen (analog Auto-Hunt)
            if self._omni_cq.is_active():
                self._omni_cq.stop("totmann_expired")
            # CQ stoppen (aber laufendes QSO zu Ende fuehren!)
            if self.qso_sm.cq_mode:
                # Nur CQ stoppen wenn KEIN aktives QSO laeuft
                if self.qso_sm.state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT,
                                          QSOState.IDLE, QSOState.TIMEOUT):
                    self.qso_sm.stop_cq()
                    self.control_panel.set_cq_active(False)
                    self.qso_panel.add_info(
                        "Operator Presence abgelaufen — CQ gestoppt. "
                        "Maus bewegen oder Taste druecken zum Fortsetzen."
                    )
                else:
                    # QSO laeuft → nach QSO-Ende stoppen
                    self.qso_panel.add_info(
                        "Operator Presence abgelaufen — CQ wird nach QSO-Ende gestoppt."
                    )

    def presence_can_tx(self) -> bool:
        """True wenn TX erlaubt (Operator anwesend ODER QSO laeuft).

        Laufende QSOs werden IMMER zu Ende gefuehrt — nur neue CQ werden blockiert.
        """
        if not self._presence_expired:
            return True
        # QSO laeuft → TX erlauben damit es sauber abgeschlossen wird
        if self.qso_sm.state in (QSOState.TX_CALL, QSOState.WAIT_REPORT,
                                  QSOState.TX_REPORT, QSOState.WAIT_RR73,
                                  QSOState.TX_RR73):
            return True
        return False

    # ── Richtungs-Karte (lazy create, Schritt 7+9) ─────────────

    def open_direction_map(self, default_mode: str = "rx") -> None:
        """Karten-Dialog oeffnen (lazy create). Wird in Schritt 9 vom Settings-
        Button aufgerufen."""
        if self._direction_map_dialog is None:
            from ui.direction_map_widget import DirectionMapDialog
            self._direction_map_dialog = DirectionMapDialog(
                my_locator=self.settings.locator,
                default_mode=default_mode,
                callsign=self.settings.callsign,
                mode=self.settings.mode,
                parent=self,
            )
        self._direction_map_dialog.set_locator(self.settings.locator)
        self._direction_map_dialog.set_callsign(
            self.settings.callsign, self.settings.mode
        )
        self._direction_map_dialog.set_locator_db(self.locator_db)
        # RX-History des aktiven Bandes vorladen (v0.73): zeigt sofort die
        # letzte Stunde Empfangsdaten — auch nach App-Restart.
        self._reload_rx_history_on_map(self.settings.band)
        self._direction_map_dialog.show()
        self._direction_map_dialog.raise_()

    def _reload_rx_history_on_map(self, band: str) -> None:
        """Karten-Canvas mit RX-History des Bandes (alle Modi gemerged) befuellen.

        Wird beim Karten-Open + Bandwechsel aufgerufen. Konvertiert RxEntries
        zu StationPoints via locator_db (priorisiert exakte Position aus DB
        ueber Decode-Zeitpunkt-Locator)."""
        if self._direction_map_dialog is None:
            return
        if getattr(self, "rx_history_store", None) is None:
            return
        from ui.direction_map_widget import entries_to_station_points
        entries = self.rx_history_store.get_band_entries(band)
        points = entries_to_station_points(entries, locator_db=self.locator_db)
        self._direction_map_dialog.canvas.update_stations(points)

    def _build_map_snapshot(self) -> dict:
        """Snapshot aus aktuellen Stations-Akkumulatoren bauen.

        Liest Locator wenn vorhanden auch direkt aus FT8Message.field3 (CQ-Calls)
        und fuettert _locator_cache. Damit landen Stationen die wir vorher mal
        in CQ gesehen haben spaeter trotzdem auf der Karte, auch wenn sie aktuell
        nur Reports senden.
        """
        import time as _t
        if self._rx_mode == "diversity":
            stations = self._diversity_stations
        else:
            stations = self._normal_stations

        snap = {}
        for call, msg in stations.items():
            # Locator aus aktueller Message (CQ → field3 ist Locator)
            if getattr(msg, "is_grid", False):
                self._locator_cache.update(call, msg.field3)
            loc = self._locator_cache.get(call)
            snap[call] = {
                "snr": float(msg.snr),
                "freq_hz": int(msg.freq_hz),
                "antenna": getattr(msg, "antenna", "") or "",
                "snr_a1": getattr(msg, "_snr_a1", None),
                "snr_a2": getattr(msg, "_snr_a2", None),
                "ts": _t.time(),
                "locator": loc,
            }
        return snap

    def _emit_map_snapshot_if_open(self) -> None:
        """Wird aus mw_cycle gerufen — emittiert Signal nur wenn Karte offen."""
        if self._direction_map_dialog is None or not self._direction_map_dialog.isVisible():
            return
        snapshot = self._build_map_snapshot()
        # Qt.QueuedConnection — sicheres Marshalling Decoder-Thread → GUI-Thread
        self.direction_map_signal.emit(snapshot, self.settings.band)

    @Slot(dict, str)
    def _on_direction_map_snapshot(self, snapshot: dict, band: str) -> None:
        """GUI-Thread Slot. Delegiert ans Widget je nach aktivem Mode."""
        if self._direction_map_dialog is None:
            return
        from ui.direction_map_widget import snapshot_to_station_points
        points = snapshot_to_station_points(
            snapshot, self._locator_cache, band=band,
            locator_db=self.locator_db,
        )
        if self._direction_map_dialog.mode == "rx":
            self._direction_map_dialog.update_rx_stations(
                points, total_decoded=len(snapshot))
        # TX-Modus wird in Schritt 8 ueber PSKReporter befuellt, nicht hier.

    @Slot(str)
    def _on_dynamic_ratio_changed(self, new_ratio: str) -> None:
        """P34: GUI-Thread Slot. Wenn DynamicDiversityController ein neues
        Ratio gesetzt hat, Antennen-Panel updaten.

        Aufruf via QueuedConnection vom Decoder-Thread.
        """
        try:
            self.control_panel.update_diversity_ratio(
                new_ratio,
                scoring_mode=self._diversity_ctrl.scoring_mode,
                # P40: RX-Antennen-Suffix nicht verlieren bei Ratio-Wechsel
                current_ant=getattr(self, "_diversity_current_ant", None),
            )
        except Exception as exc:
            # Defensive: GUI-Update fehlschlagen darf den Dynamic-Pfad nicht killen
            print(f"[Dynamic] GUI-Update Fehler: {exc}")

    # P34-Stufe2 (v0.97.19): _apply_dynamic_toggle entfernt — Dynamic ist
    # Default ohne Toggle. _enable_diversity/_disable_diversity steuern
    # activate()/deactivate() implizit.

    def closeEvent(self, event):
        # P34-Stufe2: MessStatusDialog gibt's nicht mehr.

        # P22-A10: Staged Preset-Eintraege verwerfen (kein Half-State auf Disk).
        for store_attr in ('_standard_store', '_dx_store'):
            store = getattr(self, store_attr, None)
            if store and hasattr(store, 'discard_all_staged'):
                n = store.discard_all_staged()
                if n:
                    print(f"[App-Quit] {n} staged Preset-Eintrag(e) "
                          f"in {store_attr} verworfen")

        # P1.QRZ-UPLOAD-UI (KP-3): Bulk-Worker sauber stoppen vor App-Close.
        # Disconnect VOR cancel(), sonst kann Worker noch finished.emit() auf
        # zerstoertem Dialog/Slot feuern.
        if hasattr(self, '_qrz_worker') and self._qrz_worker:
            try:
                self._qrz_worker.finished.disconnect()
                self._qrz_worker.progress.disconnect()
                self._qrz_worker.cooldown_tick.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._qrz_worker.cancel()
            self._qrz_worker.shutdown(wait=False)
        # Fenstergeometrie + Splitter-Breiten speichern
        geom = self.geometry()
        self.settings.set("window_x", geom.x())
        self.settings.set("window_y", geom.y())
        self.settings.set("window_w", geom.width())
        self.settings.set("window_h", geom.height())
        self.settings.set("splitter_sizes", self.splitter.sizes())
        self.timer.stop()
        if self._rx_mode == "diversity":
            self._apply_normal_mode()
        # Reconnect-Schleife abbrechen bevor disconnect
        self.radio.abort_reconnect()
        if hasattr(self, '_countdown_timer'):
            self._countdown_timer.stop()
        # Karten-Dialog schliessen (falls offen)
        if self._direction_map_dialog is not None:
            self._direction_map_dialog.close()
        self.decoder.stop()
        self.radio.disconnect()
        # Locator-DB persistieren (in-memory waehrend Laufzeit, JSON beim Close)
        try:
            self.locator_db.save()
        except OSError as e:
            print(f"[LocatorDB] Save fehlgeschlagen: {e}")
        # RX-History-Cache persistieren (v0.73)
        try:
            self.rx_history_store.save()
        except OSError as e:
            print(f"[RxHistory] Save fehlgeschlagen: {e}")
        self.settings.save()
        event.accept()
