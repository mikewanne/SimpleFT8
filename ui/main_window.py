"""SimpleFT8 Main Window — 3-Fenster-Layout mit QSplitter.

Kernlogik ist in 4 Mixins aufgeteilt:
  - CycleMixin  (mw_cycle.py)  — Zyklusverarbeitung, Diversity Akkumulation
  - QSOMixin    (mw_qso.py)    — QSO-Steuerung, CQ, Station-Klick, QRZ
  - RadioMixin  (mw_radio.py)  — Radio-Verbindung, Band, Diversity, DX-Tuning
  - TXMixin     (mw_tx.py)     — TX-Regelung, Meter, SWR
"""

import math
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QMessageBox, QScrollArea, QLabel,
)
from PySide6.QtCore import Qt, Slot

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

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle(f"SimpleFT8 — {settings.callsign}")
        self.setMinimumSize(1200, 600)
        self.resize(1400, 700)
        self._apply_dark_theme()

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

        # Optionale Features (NACH _setup_ui, weil Easter-Egg-Signal verbunden wird)
        self._init_optional_features()

        # Timer + Radio starten (NACH OMNI-TX/Auto-Hunt/AP-Lite Init!)
        self.timer.start()
        self._start_radio()

        # UI mit gespeicherten Settings synchronisieren
        self.control_panel._set_band(settings.band)
        self.control_panel._set_mode(settings.mode)
        self.control_panel.set_power_preset(settings.get("power_preset", 10))

        # Hintergrund-Timer
        self._init_psk_polling()
        self._init_propagation_polling()
        self._init_presence_watchdog()
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
        self.encoder = Encoder(settings.audio_freq_hz)
        self.decoder = Decoder(max_freq=settings.max_decode_freq)
        self.decoder._my_call = settings.callsign
        self.adif = AdifWriter()

        # Stations-Statistik Logger + Warmup
        from core.station_stats import StationStatsLogger
        from core.antenna_pref import AntennaPreferenceStore
        from core.preset_store import PresetStore
        self._stats_logger = StationStatsLogger()
        self._stats_warmup_cycles = 6
        self._antenna_prefs = AntennaPreferenceStore()
        # Getrennte Preset-Dateien für Standard und DX (2h-Frist pro Band+FTMode)
        self._standard_store = PresetStore("presets_standard.json")
        self._dx_store = PresetStore("presets_dx.json")
        # Einmalige Migration aus altem config.json-Format
        self._standard_store.migrate_from_settings(self.settings._data, mode="standard")
        self._dx_store.migrate_from_settings(self.settings._data, mode="dx")

    def _init_qso_log(self):
        """QSO-Verzeichnis (Worked-Before) aus aktuellem Pfad + adif_import_path laden."""
        from log.qso_log import QSOLog
        self.qso_log = QSOLog()
        self.qso_log.load_directory(Path.cwd())
        import_path = self.settings.get("adif_import_path")
        if import_path:
            self.qso_log.load_directory(Path(import_path))
        print(f"[QSOLog] {self.qso_log.worked_count()} unique Calls, {self.qso_log.qso_count()} QSOs")

    def _init_radio_state(self):
        """Radio via Factory + Reconnect-Counter + DX-Tune-Dialog Slot."""
        self.radio = create_radio(self.settings)
        self._reconnect_attempts = 0
        self._reconnect_countdown = 0
        self._dx_tune_dialog = None  # Aktiver DX-Tune Dialog
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
        self._active_qso_targets: set = set()  # Stationen im aktiven QSO → 150s Aging
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
        # OMNI-TX: Initialisieren (deaktiviert), Easter Egg verbinden
        from core import omni_tx as _omni
        _block_cycles = max(10, self.settings.get("diversity_operate_cycles", 80) // 2)
        self._omni_tx = _omni.get_instance(block_cycles=_block_cycles)
        self.control_panel.omni_tx_clicked.connect(self._on_omni_tx_easter_egg)

        # Auto-Hunt: Initialisieren (deaktiviert, zusammen mit OMNI-TX)
        from core.auto_hunt import AutoHunt
        self._auto_hunt = AutoHunt()
        self._auto_hunt.set_qso_log(self.qso_log)
        self._auto_hunt.set_band(self.settings.band)

        # AP-Lite: Initialisieren (deaktiviert, AP_LITE_ENABLED=False)
        from core import ap_lite as _ap
        self._ap_lite = _ap.get_instance(encoder=self.encoder)

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
        from PySide6.QtWidgets import QPushButton as _QPB
        _help_btn = _QPB(" ? ")
        _help_btn.setStyleSheet(
            "QPushButton { background: #1a2a3a; color: #88AACC; border: 1px solid #336;"
            "border-radius: 3px; font-size: 12px; font-weight: bold; padding: 2px 8px; }"
            "QPushButton:hover { background: #2a3a5a; }"
        )
        _help_btn.setFixedHeight(22)
        _help_btn.clicked.connect(self._on_help_clicked)
        self.statusBar().addPermanentWidget(_help_btn)
        # DT-Anzeige nur in der Statusbar-Message (kein separates Label mehr)

    def _setup_ui(self):
        self.rx_panel = RXPanel(
            my_call=self.settings.callsign,
            my_grid=self.settings.locator,
            country_filter=self.settings.get("country_filter", []),
        )
        self.qso_panel = QSOPanel()
        # Logbuch mit ADIF-Dateien laden (AdifWriter schreibt in adif/ Unterordner)
        self.qso_panel.logbook.load_adif(Path.cwd() / "adif")
        self.qso_panel.upload_qrz.connect(self._on_qrz_upload)
        self.qso_panel.logbook.qso_clicked.connect(self._on_logbook_qso_clicked)
        # Tab-Wechsel: Detail-Overlay zuruecksetzen wenn User vom Logbuch weg navigiert
        self.qso_panel.tabs.currentChanged.connect(self._on_qso_tab_changed)
        self.control_panel = ControlPanel(callsign=self.settings.callsign)

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
        # RX Panel → QSO starten + RX-Toggle
        self.rx_panel.station_clicked.connect(self._on_station_clicked)
        self.rx_panel.rx_toggled.connect(self._on_rx_panel_toggled)
        self.rx_panel.country_filter_changed.connect(self._on_country_filter_changed)

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
        self.control_panel.remeasure_clicked.connect(self._on_diversity_remeasure)
        self.control_panel.settings_clicked.connect(self._on_settings_clicked)

        # QSO State Machine
        self.qso_sm.state_changed.connect(self._on_state_changed)
        self.qso_sm.send_message.connect(self._on_send_message)
        self.qso_sm.qso_complete.connect(self._on_qso_complete)
        self.qso_sm.qso_confirmed.connect(self._on_qso_confirmed)
        self.qso_sm.qso_timeout.connect(self._on_qso_timeout)
        self.qso_sm.tx_slot_for_partner.connect(self._on_tx_slot_for_partner)
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

    def _on_omni_tx_easter_egg(self):
        """Easter Egg: OMNI-TX via Klick auf Versionsnummer aktivieren/deaktivieren."""
        if self._omni_tx.active:
            # Deaktivieren
            self._omni_tx.disable()
            self._auto_hunt.disable()
            self.control_panel.update_omni_tx(False)
            self.control_panel.btn_cq.setText("CQ RUFEN")
            self._update_statusbar()
        else:
            # Aktivierungsdialog
            msg = QMessageBox(self)
            msg.setWindowTitle("OMNI-TX")
            msg.setText(
                "<b>OMNI-TX aktivieren?</b><br><br>"
                "SimpleFT8 wechselt automatisch zwischen Even und Odd Slot.<br>"
                "Gleiche Sendezeit, mehr Reichweite.<br>"
                "Technisch regelkonform."
            )
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            msg.button(QMessageBox.StandardButton.Yes).setText("Aktivieren")
            msg.button(QMessageBox.StandardButton.Cancel).setText("Abbrechen")
            msg.setStyleSheet(self._msgbox_style())
            if msg.exec() == QMessageBox.StandardButton.Yes:
                self._omni_tx.enable()
                self._auto_hunt.enable()
                self.control_panel.update_omni_tx(True)
                self.control_panel.btn_cq.setText("OMNI CQ")
                self._update_statusbar()

    # ── Propagation ──────────────────────────────────────────────

    def _update_propagation_ui(self):
        """Propagations-Balken aus Hintergrund-Cache aktualisieren."""
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
            self.control_panel.update_propagation(conditions)

    # ── PSKReporter ──────────────────────────────────────────────

    def _fetch_psk_stats(self):
        if not self._has_sent_cq:
            self.control_panel.psk_label.setText("PSK: — (nur nach CQ)")
            self.control_panel.psk_label.setStyleSheet(
                "color: #557766; font-family: Menlo; font-size: 10px; padding: 2px;"
            )
            return
        # Nach erster Abfrage auf 3-Min-Intervall wechseln
        if self._psk_first_fetch:
            self._psk_first_fetch = False
            self._psk_timer.setInterval(self._psk_repeat_interval)  # 5 Minuten
        self._psk_band = self.settings.band.upper()
        threading.Thread(target=self._psk_worker, daemon=True).start()

    def _psk_worker(self):
        import urllib.request
        import xml.etree.ElementTree as ET
        from datetime import datetime, timezone

        call = self.settings.callsign
        my_grid = self.settings.locator
        mode = self.settings.mode.upper()
        try:
            url = (f"https://retrieve.pskreporter.info/query?"
                   f"senderCallsign={call}&flowStartSeconds=-600&mode={mode}")
            req = urllib.request.Request(
                url, headers={"User-Agent": "SimpleFT8/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read().decode("utf-8")

            root = ET.fromstring(xml_data)
            spots = []
            from core.geo import grid_to_latlon, distance_km
            my_pos = grid_to_latlon(my_grid)
            if not my_pos:
                return

            for rr in root.findall(".//receptionReport"):
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

            if not spots:
                self.control_panel.update_psk_stats(
                    0, 0, 0, "", "", 0, 0, 0, 0
                )
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
        except Exception as e:
            print(f"[PSK] Fehler: {e}")

    # ── Settings ─────────────────────────────────────────────────

    @Slot()
    def _on_settings_clicked(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self._update_statusbar()
            self.qso_sm.max_calls = self.settings.get("max_calls", 3)
            self._diversity_ctrl.OPERATE_CYCLES = self.settings.get("diversity_operate_cycles", 80)
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
        if getattr(self, '_omni_tx', None) and self._omni_tx.active:
            omni_str = (f"  Ω Even={self._omni_tx.cq_even_count} "
                        f"Odd={self._omni_tx.cq_odd_count}")
        else:
            omni_str = ""
        # DT-Korrektur Status — nur DT-Label gruen, Statusbar bleibt grau
        from core import ntp_time
        dt_phase = ntp_time._phase
        if ntp_time._correction == 0.0 and ntp_time._is_initial:
            dt_text, dt_color = "DT: —", "#888"
        elif dt_phase == "measure":
            dt_text, dt_color = "DT: Korrektur", "#00DD66"
        else:
            dt_text, dt_color = "DT: Aktiv", "#888"
        # DT-Farbe in Statusbar: gruen bei Korrektur via kurzen StyleSheet-Wechsel
        if dt_color != "#888":
            self.statusBar().setStyleSheet(
                f"color: {dt_color}; font-family: Menlo; font-size: 11px; background-color: #0a1a0a;")
        else:
            self.statusBar().setStyleSheet(
                "color: #888; font-family: Menlo; font-size: 11px; background-color: #111;")
        # Filter-Anzeige pro Modus
        _FILTERS = {"FT8": "100-3100", "FT4": "100-3100", "FT2": "100-4000"}
        filter_str = _FILTERS.get(self.settings.mode, "100-3100")
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
                    delta = pref_entry['delta_db']
                    if delta is None:
                        freq_str += f"  |  RX: {pref_entry['best_ant']}"
                    else:
                        freq_str += (f"  |  RX: {pref_entry['best_ant']} "
                                     f"({delta:+.1f} dB)")
            elif self._rx_mode == "normal":
                freq_str += "  |  RX: ANT1"
        msg = (f"{self.settings.callsign}  |  {self.settings.locator}  |  "
               f"{self.settings.mode} {self.settings.band}  |  "
               f"{freq_display}  |  Filter: {filter_str} Hz  |  "
               f"{mode_str}  |  {dt_text}{omni_str}{freq_str}{ap_str}")
        self.statusBar().showMessage(msg)

    # ── Hilfsfunktionen ──────────────────────────────────────────

    @staticmethod
    def _msgbox_style() -> str:
        return styles.MSGBOX_STYLE

    def _tick_cq_countdown(self):
        """Sekündlicher Update des CQ-Freq-Countdown-Balkens.
        Wert kommt aus slot-synchronem Such-Counter (~60s, friert bei Pause ein)."""
        if self._rx_mode == "diversity" and self._diversity_ctrl.cq_freq_hz is not None:
            self.control_panel.update_cq_freq_countdown(
                self._diversity_ctrl.seconds_until_search)
        else:
            self.control_panel.set_cq_countdown_visible(False)

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

    def closeEvent(self, event):
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
        self.decoder.stop()
        self.radio.disconnect()
        self.settings.save()
        event.accept()
