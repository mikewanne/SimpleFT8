"""SimpleFT8 Main Window — 3-Fenster-Layout mit QSplitter."""

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QStatusBar,
    QMessageBox,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

from config.settings import Settings, BAND_FREQUENCIES
from core.timing import FT8Timer
from core.qso_state import QSOStateMachine, QSOState
from core.encoder import Encoder
from core.decoder import Decoder
from core.message import FT8Message
from log.adif import AdifWriter
from radio.flexradio import FlexRadio
from .rx_panel import RXPanel
from .qso_panel import QSOPanel
from .control_panel import ControlPanel
from .settings_dialog import SettingsDialog
from .dx_tune_dialog import DXTuneDialog


class _UCBAntennaSelector:
    """UCB1-Algorithmus fuer adaptive Antennen-Auswahl im AUTO-Modus.

    Loest die Bias-Spirale: exploriert automatisch die weniger gemessene
    Antenne wenn Unsicherheit steigt. Kein manueller Reset noetig.
    """

    def __init__(self, weight: float = 1.5):
        self._weight = weight
        self.reset()

    def reset(self):
        self._plays   = {"A1": 0,   "A2": 0}
        self._rewards = {"A1": 0.0, "A2": 0.0}

    def choose(self) -> str:
        """Naechste Antenne auswaehlen (UCB1)."""
        import math
        # Jede Antenne mindestens einmal spielen lassen
        for ant in ("A1", "A2"):
            if self._plays[ant] == 0:
                return ant
        total = self._plays["A1"] + self._plays["A2"]
        best, best_score = "A1", -1.0
        for ant in ("A1", "A2"):
            avg     = self._rewards[ant] / self._plays[ant]
            explore = self._weight * math.sqrt(math.log(total) / self._plays[ant])
            score   = avg + explore
            if score > best_score:
                best_score = score
                best = ant
        return best

    def update(self, ant: str, reward: float):
        """Reward nach Zyklus-Ende einpflegen."""
        if ant in self._plays:
            self._plays[ant]   += 1
            self._rewards[ant] += reward

    def rates(self) -> dict:
        """Erfolgsraten pro Antenne (fuer Anzeige)."""
        return {
            ant: (self._rewards[ant] / self._plays[ant] if self._plays[ant] > 0 else 0.0)
            for ant in ("A1", "A2")
        }


class MainWindow(QMainWindow):
    """SimpleFT8 Hauptfenster — 3 Panels horizontal."""

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle(f"SimpleFT8 — {settings.callsign}")
        self.setMinimumSize(1200, 600)
        self.resize(1400, 700)

        # Dark Theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #16192b;
            }
            QWidget {
                background-color: #16192b;
                color: #CCCCCC;
            }
            QSplitter::handle:horizontal {
                background-color: #555;
                width: 4px;
                border-left: 1px solid #777;
                border-right: 1px solid #333;
            }
        """)

        # Core-Komponenten
        self.timer = FT8Timer(settings.mode)
        self.qso_sm = QSOStateMachine(settings.callsign, settings.locator)
        self.encoder = Encoder(settings.audio_freq_hz)
        self.decoder = Decoder(max_freq=settings.max_decode_freq)
        self.decoder._my_call = settings.callsign
        self.adif = AdifWriter()

        # FlexRadio
        self.radio = FlexRadio(
            ip=settings.get("flexradio_ip", ""),
            port=settings.get("flexradio_port", 4992),
        )

        self._reconnect_attempts = 0
        self._reconnect_countdown = 0
        self._dx_mode = False
        self._dx_tune_dialog = None  # Aktiver DX-Tune Dialog
        # Diversity (simpel: Antenne pro Zyklus wechseln)
        self._rx_mode = "normal"  # "normal", "diversity", "dx_tuning"
        self._diversity_cycle = 0  # Zaehler fuer Antennen-Wechsel
        self._diversity_stations = {}  # key → FT8Message (akkumuliert)
        self._normal_stations = {}     # key → FT8Message (Normal, 2-Min-Fenster)
        self._diversity_bias = "AUTO"  # Manueller Bias: 100:0 / 70:30 / AUTO / 30:70 / 0:100
        self._diversity_stats = {"A1_only": 0, "A2_only": 0, "A1_wins": 0, "A2_wins": 0}
        self._ucb_selector = _UCBAntennaSelector(weight=1.5)  # UCB1 fuer AUTO-Modus
        self._active_qso_targets: set = set()  # Stationen im aktiven QSO → 150s Aging
        import threading as _threading
        self._diversity_lock = _threading.Lock()  # BUG-2: Race Condition Guard

        # Bias-Pattern-Tabelle (DeepSeek-Review: _BIAS_PATTERNS Dict)
        # None = spezielles Block-A/B 4-Zyklus-Pattern (AUTO)
        self._BIAS_PATTERNS = {
            "100:0": ("A1",),
            "70:30": ("A1", "A2", "A1", "A1", "A2"),
            "AUTO":  None,  # 4-Zyklus Block A/B
            "30:70": ("A2", "A1", "A2", "A2", "A1"),
            "0:100": ("A2",),
        }

        # UI aufbauen
        self._setup_ui()
        self._connect_signals()

        # Timer starten
        self.timer.start()

        # FlexRadio + Decoder starten
        self._start_radio()

        # UI mit gespeicherten Settings synchronisieren
        self.control_panel._set_band(settings.band)
        self.control_panel._set_mode(settings.mode)
        self.control_panel.power_slider.setValue(settings.power_watts)

        # PSKReporter Timer (alle 3 Minuten abfragen)
        from PySide6.QtCore import QTimer
        self._psk_timer = QTimer(self)
        self._psk_timer.timeout.connect(self._fetch_psk_stats)
        self._psk_timer.start(180000)  # 3 Minuten

        # Statusbar
        self._update_statusbar()
        self.statusBar().setStyleSheet(
            "color: #888; font-family: Menlo; font-size: 11px; "
            "background-color: #111;"
        )

        # Fenstergeometrie wiederherstellen
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, self._restore_geometry)

    def _setup_ui(self):
        self.rx_panel = RXPanel(
            my_call=self.settings.callsign,
            my_grid=self.settings.locator,
            country_filter=self.settings.get("country_filter", []),
        )
        self.qso_panel = QSOPanel()
        self.control_panel = ControlPanel(callsign=self.settings.callsign)

        # Alle 3 Panels in einem QSplitter → sichtbarer Trenner bleibt erhalten
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.rx_panel)
        self.splitter.addWidget(self.qso_panel)
        self.splitter.addWidget(self.control_panel)

        # EMPFANG + QSO 50:50, Control fix (wird in _restore_geometry überschrieben)
        self.splitter.setSizes([500, 500, 400])
        self.splitter.setStretchFactor(0, 1)  # RX: dehnen
        self.splitter.setStretchFactor(1, 1)  # QSO: dehnen
        self.splitter.setStretchFactor(2, 0)  # Control: nicht dehnen

        self.setCentralWidget(self.splitter)

    def _start_radio(self):
        """FlexRadio verbinden und Decoder starten (mit Auto-Retry)."""
        # Audio-Callback + Signals verbinden
        self.radio.on_audio_callback = self.decoder.feed_audio
        self.radio.error.connect(lambda msg: print(f"[Radio] {msg}"))
        self.radio.connected.connect(self._on_radio_connected)
        self.radio.disconnected.connect(self._on_radio_disconnected)

        # Decoder-Signals
        self.decoder.message_decoded.connect(self.on_message_decoded)
        self.decoder.cycle_decoded.connect(self._on_cycle_decoded)

        # Encoder
        self.encoder.set_radio(self.radio)
        self.encoder.set_decoder(self.decoder)
        self.encoder.tx_started.connect(
            lambda msg: self.control_panel.set_tx_active(True)
        )
        self.encoder.tx_finished.connect(self._on_tx_finished)

        # Auto-Connect im Hintergrund
        self.control_panel.set_connection_status("searching")
        import threading
        threading.Thread(
            target=self._connect_worker, daemon=True
        ).start()

    def _connect_worker(self):
        """Verbindung im Hintergrund herstellen."""
        ok = self.radio.auto_connect(max_retries=10, retry_delay=3.0)
        if not ok:
            self.control_panel.set_connection_status("disconnected")

    def _on_radio_connected(self):
        """Wird aufgerufen wenn FlexRadio verbunden ist."""
        self._reconnect_attempts = 0
        self.control_panel.set_connection_status("connected")
        # Gespeichertes Band + Frequenz setzen
        s = self.radio._slice_idx
        freq = self.settings.frequency_mhz
        band = self.settings.band
        self.radio.set_frequency(freq, slice_idx=s)
        self.radio.apply_ft8_preset(slice_idx=s, band=band)
        print(f"[FlexRadio] Band: {band}, Freq: {freq:.3f} MHz")
        self.decoder.set_quality("normal")  # Start: schnell (NORMAL-Modus)
        self.decoder.start()
        self.radio.create_tx_stream()
        # Meter an GUI koppeln
        self.radio.meter_update.connect(self._on_meter_update)
        self.radio.swr_alarm.connect(self._on_swr_alarm)

    def _on_radio_disconnected(self):
        """Verbindung verloren — unbegrenzt reconnecten mit Exponential Backoff."""
        self.control_panel.set_connection_status("disconnected")
        self.decoder.stop()
        self._reconnect_attempts += 1
        self._reconnect_countdown = 0

        # QTimer im GUI-Thread erstellen (darf NICHT im Worker-Thread sein)
        from PySide6.QtCore import QTimer
        if not hasattr(self, '_countdown_timer'):
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_timer.start(1000)

        self.control_panel.set_connection_status("reconnecting")
        import threading
        threading.Thread(target=self._reconnect_worker, daemon=True).start()

    def _on_countdown_tick(self):
        """Countdown-Anzeige im GUI-Thread aktualisieren."""
        secs = self._reconnect_countdown
        if secs > 0:
            self.control_panel.connection_label.setText(
                f"RADIO: Reconnect in {secs}s..."
            )
            self.control_panel.connection_label.setStyleSheet(
                "color: #FFD700; font-family: Menlo; font-size: 12px; font-weight: bold;"
            )

    def _reconnect_worker(self):
        """Reconnect-Schleife im Hintergrund (Exponential Backoff, unbegrenzt)."""
        def _on_waiting(secs_remaining: int):
            # Thread-safe: nur primitiven int setzen, QTimer liest ihn
            self._reconnect_countdown = secs_remaining

        ok = self.radio.reconnect_forever(on_waiting=_on_waiting)
        self._reconnect_countdown = 0

        # Timer stoppen (Thread-sicher via invokeMethod)
        from PySide6.QtCore import QMetaObject, Qt
        if hasattr(self, '_countdown_timer'):
            QMetaObject.invokeMethod(
                self._countdown_timer, "stop",
                Qt.ConnectionType.QueuedConnection,
            )

        if not ok:
            self.control_panel.set_connection_status("disconnected")

    def _on_cycle_decoded(self, messages: list):
        """Ein kompletter FT8-Zyklus dekodiert."""
        if not self.rx_panel._rx_active:
            return
        # Slot-Parity: dekodierte Messages waren im VORHERIGEN Zyklus gesendet
        msg_was_even = not self.timer.is_even_cycle()
        if messages:
            for m in messages:
                m._tx_even = msg_was_even
        count = len(messages) if messages else 0
        self.control_panel.update_decode_count(count)

        if self._rx_mode == "diversity":
            # Queue IMMER poppen — auch bei 0 Stationen!
            # Sonst geraet die Queue aus dem Takt wenn eine Antenne nichts empfaengt
            ant_queue = getattr(self, '_diversity_ant_queue', None)
            if ant_queue:
                ant = ant_queue.popleft()
            else:
                ant = "A1"

        # UCB1 Update (nur im AUTO-Modus, nach jedem Diversity-Zyklus)
        if self._rx_mode == "diversity" and self._diversity_bias == "AUTO":
            reward = sum(
                max(0.0, (m.snr + 20) / 30.0)
                for m in (messages or []) if m.snr is not None
            )
            self._ucb_selector.update(ant if self._rx_mode == "diversity" else "A1", reward)

        if self._rx_mode == "diversity" and messages:
            # Diversity: Stationen akkumulieren per Callsign
            # Zwei Timestamps:
            #   _last_heard:   wann zuletzt dekodiert (fuer Aging)
            #   _last_changed: wann sich Inhalt geaendert hat (fuer UTC-Anzeige)
            # Aging: 2 Min nicht mehr dekodiert → raus
            # ant wurde oben schon aus der Queue geholt
            import time as _t
            now = _t.time()
            utc_str = _t.strftime("%H%M%S", _t.gmtime())
            changed = False
            for msg in messages:
                key = msg.caller
                if not key:
                    continue
                msg.antenna = ant
                existing = self._diversity_stations.get(key)
                if existing is None:
                    # Neue Station
                    msg._last_heard = now
                    msg._last_changed = now
                    msg._utc_display = utc_str
                    self._diversity_stations[key] = msg
                    changed = True
                else:
                    # Station bekannt — hat sich IRGENDWAS geaendert?
                    snr_changed = msg.snr != existing.snr
                    ant_changed = ant != getattr(existing, 'antenna', '')
                    content_changed = (
                        msg.field1 != existing.field1 or
                        msg.field2 != existing.field2 or
                        msg.field3 != existing.field3
                    )
                    if snr_changed or ant_changed or content_changed:
                        # Etwas hat sich geaendert → Timestamp + Werte updaten
                        existing._last_heard = now
                        existing._utc_display = utc_str
                        # Antennen-Vergleich: auf welcher war sie staerker?
                        if ant_changed and existing.antenna in ("A1", "A2"):
                            old_ant = existing.antenna
                            if msg.snr > existing.snr:
                                # Neue Antenne staerker
                                existing.antenna = f"{ant}>{old_ant[-1]}"
                            else:
                                # Alte Antenne war staerker
                                existing.antenna = f"{old_ant}>{ant[-1]}"
                        elif not ant_changed:
                            pass  # Antenne gleich, nichts aendern
                        existing.snr = msg.snr
                        if content_changed:
                            existing.raw = msg.raw
                            existing.field1 = msg.field1
                            existing.field2 = msg.field2
                            existing.field3 = msg.field3
                        changed = True
                    # Sonst: exakt gleich → kein Update, altert nach 2 Min raus

            # Alte Stationen entfernen (75s normal, 150s wenn aktiv angerufen)
            stale = [k for k, m in self._diversity_stations.items()
                     if now - getattr(m, '_last_heard', now) > (
                         150 if k in self._active_qso_targets else 75)]
            if stale:
                changed = True
                for k in stale:
                    del self._diversity_stations[k]

            # Tabelle neu aufbauen wenn sich was geaendert hat
            if changed:
                self.rx_panel.table.setRowCount(0)
                for m in self._diversity_stations.values():
                    self.rx_panel.add_message(m)
                self.rx_panel.reapply_sort()
                # Diversity-Stats aktualisieren
                a1_only = sum(1 for m in self._diversity_stations.values()
                              if getattr(m, 'antenna', '') == 'A1')
                a2_only = sum(1 for m in self._diversity_stations.values()
                              if getattr(m, 'antenna', '') == 'A2')
                a1_wins = sum(1 for m in self._diversity_stations.values()
                              if str(getattr(m, 'antenna', '')).startswith('A1>'))
                a2_wins = sum(1 for m in self._diversity_stations.values()
                              if str(getattr(m, 'antenna', '')).startswith('A2>'))
                # UCB1-Raten in Stats anzeigen wenn AUTO aktiv
                if self._diversity_bias == "AUTO":
                    rates = self._ucb_selector.rates()
                    plays = self._ucb_selector._plays
                    self.control_panel.update_diversity_stats(
                        a1_only, a2_only, a1_wins, a2_wins,
                        ucb_rate_a1=rates["A1"], ucb_rate_a2=rates["A2"],
                        ucb_plays_a1=plays["A1"], ucb_plays_a2=plays["A2"],
                    )
                else:
                    self.control_panel.update_diversity_stats(
                        a1_only, a2_only, a1_wins, a2_wins
                    )

            self.control_panel.update_decode_count(
                len(self._diversity_stations)
            )

        elif self._rx_mode == "normal" and messages:
            # Normal: Akkumulation mit 2-Min-Fenster (wie Diversity, ohne Antennenwechsel)
            import time as _t
            now = _t.time()
            utc_str = _t.strftime("%H%M%S", _t.gmtime())
            changed = False
            for msg in messages:
                key = msg.caller
                if not key:
                    continue
                existing = self._normal_stations.get(key)
                if existing is None:
                    msg._last_heard = now
                    msg._utc_display = utc_str
                    self._normal_stations[key] = msg
                    changed = True
                else:
                    existing._last_heard = now
                    snr_changed = msg.snr != existing.snr
                    content_changed = (
                        msg.field1 != existing.field1 or
                        msg.field2 != existing.field2 or
                        msg.field3 != existing.field3
                    )
                    if snr_changed or content_changed:
                        existing._utc_display = utc_str
                        existing.snr = msg.snr
                        if content_changed:
                            existing.raw = msg.raw
                            existing.field1 = msg.field1
                            existing.field2 = msg.field2
                            existing.field3 = msg.field3
                        changed = True
            # Aging: 75s normal, 150s wenn aktiv angerufen
            stale = [k for k, m in self._normal_stations.items()
                     if now - getattr(m, '_last_heard', now) > (
                         150 if k in self._active_qso_targets else 75)]
            if stale:
                changed = True
                for k in stale:
                    del self._normal_stations[k]
            if changed:
                self.rx_panel.table.setRowCount(0)
                for m in self._normal_stations.values():
                    self.rx_panel.add_message(m)
                self.rx_panel.reapply_sort()
            self.control_panel.update_decode_count(len(self._normal_stations))
            if self._normal_stations:
                avg_snr = round(sum(m.snr for m in self._normal_stations.values()) / len(self._normal_stations))
                self.control_panel.update_snr(avg_snr)

        elif messages:
            # DX Tuning: nur aktueller Zyklus
            self.rx_panel.table.setRowCount(0)
            for msg in messages:
                self.rx_panel.add_message(msg)
            self.rx_panel.reapply_sort()

        # DX-Tune Dialog fuettern wenn aktiv
        if self._dx_tune_dialog is not None:
            self._dx_tune_dialog.feed_cycle(messages)

    def _connect_signals(self):
        # RX Panel → QSO starten + RX-Toggle
        self.rx_panel.station_clicked.connect(self._on_station_clicked)
        self.rx_panel.rx_toggled.connect(self._on_rx_panel_toggled)
        self.rx_panel.country_filter_changed.connect(self._on_country_filter_changed)

        # Control Panel
        self.control_panel.mode_changed.connect(self._on_mode_changed)
        self.control_panel.band_changed.connect(self._on_band_changed)
        self.control_panel.power_changed.connect(self._on_power_changed)
        self.control_panel.auto_toggled.connect(self._on_auto_toggled)
        self.control_panel.advance_clicked.connect(self._on_advance)
        self.control_panel.cancel_clicked.connect(self._on_cancel)
        self.control_panel.cq_clicked.connect(self._on_cq_clicked)
        self.control_panel.tune_clicked.connect(self._on_tune_clicked)
        self.control_panel.tx_level_changed.connect(self._on_tx_level_changed)
        self.control_panel.rx_mode_changed.connect(self._on_rx_mode_changed)
        self.control_panel.einmessen_clicked.connect(self._handle_dx_tuning)
        self.control_panel.settings_clicked.connect(self._on_settings_clicked)
        self.control_panel.bias_changed.connect(self._on_bias_changed)

        # QSO State Machine
        self.qso_sm.state_changed.connect(self._on_state_changed)
        self.qso_sm.send_message.connect(self._on_send_message)
        self.qso_sm.qso_complete.connect(self._on_qso_complete)
        self.qso_sm.qso_timeout.connect(self._on_qso_timeout)

        # Timer
        self.timer.cycle_tick.connect(self._on_cycle_tick)
        self.timer.cycle_start.connect(self._on_cycle_start)

    # ── Station angeklickt ──────────────────────────────────────

    @Slot(object)
    def _on_station_clicked(self, msg: FT8Message):
        """User hat eine Station in der Empfangsliste angeklickt."""
        # Wenn gerade TX läuft: Klick merken, nach TX-Ende ausführen
        if self.encoder.is_transmitting:
            self._pending_click = msg
            print(f"[QSO] TX aktiv — {msg.caller} wird nach TX-Ende gerufen")
            return
        self._pending_click = None
        # CQ-Modus beenden wenn aktiv
        if self.qso_sm.cq_mode:
            self.qso_sm.stop_cq()
            self.control_panel.set_cq_active(False)
        self._active_qso_targets.add(msg.caller)  # 150s Aging fuer angerufene Station
        self.rx_panel.set_active_call(msg.caller)  # Zeile im RX-Panel hervorheben
        self.qso_panel.add_info(f"Rufe {msg.caller}...")
        self.qso_sm.max_calls = self.settings.get("max_calls", 3)
        # Even/Odd: sende im GEGENTEILIGEN Slot der Gegenstation
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
            print(f"[TX] Slot: Gegenstation={'EVEN' if their_even else 'ODD'} → wir={'ODD' if their_even else 'EVEN'}")
        else:
            self.encoder.tx_even = None  # Fallback: nächster Slot
        self.qso_sm.start_qso(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
        )

    def _on_country_filter_changed(self, country_filter: list):
        """Länder-Filter in Settings speichern."""
        self.settings.set("country_filter", country_filter)
        self.settings.save()

    @Slot(bool)
    def _on_rx_panel_toggled(self, active: bool):
        """RX ON/OFF vom Panel — bei OFF sofort auf ANT1 und Diversity-Stop."""
        if not active and self._rx_mode == "diversity" and self.radio.ip:
            import threading
            s = self.radio._slice_idx
            band = self.settings.band
            gain = FlexRadio.PREAMP_PRESETS.get(band, 10)
            def _reset_ant():
                self.radio._send_cmd(f"slice set {s} rxant=ANT1")
                self.radio._send_cmd(f"slice set {s} rfgain={gain}")
            threading.Thread(target=_reset_ant, daemon=True).start()
            with self._diversity_lock:
                self._diversity_current_ant = "A1"
        self.control_panel.update_decode_count(0)
        self.control_panel.set_rx_active(active)

    # ── Modus / Band / Power ────────────────────────────────────

    @Slot(str)
    def _on_mode_changed(self, mode: str):
        self.settings.set("mode", mode)
        self.timer.set_mode(mode)
        self._update_statusbar()

    @Slot(int)
    def _on_power_changed(self, power: int):
        self.settings.set("power_watts", power)
        if self.radio.ip:
            self.radio.set_power(power)

    @Slot(bool)
    def _on_tune_clicked(self, on: bool):
        if self.radio.ip:
            if on:
                self.radio.tune_on()
            else:
                self.radio.tune_off()

    @Slot(int)
    def _on_tx_level_changed(self, value: int):
        if self.radio.ip:
            self.radio.set_tx_level(value / 100.0)

    @Slot(str)
    def _on_band_changed(self, band: str):
        self.settings.set("band", band)
        freq = self.settings.frequency_mhz
        # Empfangsliste komplett leeren bei Bandwechsel
        self.rx_panel.table.setRowCount(0)
        self._diversity_stations = {}
        self._normal_stations = {}
        self.control_panel.update_decode_count(0)
        # Bias + UCB1 auf AUTO zuruecksetzen bei Bandwechsel
        if self._diversity_bias != "AUTO":
            self._diversity_bias = "AUTO"
            self.control_panel.set_bias("AUTO")
        self._ucb_selector.reset()
        if self.radio.ip:
            s = self.radio._slice_idx
            self.radio.set_frequency(freq, slice_idx=s)
            self.radio.apply_ft8_preset(slice_idx=s, band=band)
            if self._rx_mode == "diversity":
                # Diversity: 2. Slice auch umtunen + Preset anpassen
                if self.radio._slice_idx_b is not None:
                    gain_b = FlexRadio.PREAMP_PRESETS.get(band, 10) + 10
                    self.radio._send_cmd(
                        f"slice set {self.radio._slice_idx_b} rfgain={gain_b}"
                    )
                    self.control_panel.dx_info.setText(
                        f"ANT1+ANT2 (Gain {gain_b})"
                    )
            elif self._rx_mode == "normal":
                self._apply_dx_preset_for_band(band)
            else:
                self._apply_normal_mode()
        self._update_statusbar()

    # ── RX Modus: NORMAL / DIVERSITY / DX TUNING ──────────────

    @Slot(str)
    def _on_rx_mode_changed(self, mode: str):
        """RX-Modus umschalten (nur 'normal' oder 'diversity')."""
        if not self.radio.ip:
            self.control_panel.set_rx_mode("normal")
            return

        old_mode = self._rx_mode

        # Alten Modus sauber beenden + Liste immer leeren bei Wechsel
        if old_mode == "diversity":
            self._disable_diversity()
        self.rx_panel.table.setRowCount(0)
        self.control_panel.update_decode_count(0)

        # Decode-Qualitaet automatisch: normal=schnell, diversity=tief
        self.decoder.set_quality(mode)

        # Neuen Modus aktivieren
        if mode == "normal":
            self._rx_mode = "normal"
            self._normal_stations = {}
            self._apply_normal_mode()
        elif mode == "diversity":
            self._rx_mode = "diversity"
            self._diversity_stations = {}
            self._enable_diversity()

        self._update_statusbar()

    def _enable_diversity(self):
        """Diversity aktivieren: Antenne pro Zyklus wechseln, Stationen akkumulieren."""
        from collections import deque
        self._diversity_cycle = 0
        self._diversity_stations = {}
        self._diversity_current_ant = "A1"
        self._diversity_ant_queue = deque()

        band = self.settings.band
        preset = self.settings.get_dx_preset(band)

        if preset and "ant1_gain" in preset:
            # Preset vorhanden: per-Antenne optimierte Gains laden
            self._diversity_ant1_gain = preset["ant1_gain"]
            self._diversity_ant2_gain = preset["ant2_gain"]
            measured = preset.get("measured", "?")
            self.control_panel.dx_info.setText(
                f"ANT1(G{self._diversity_ant1_gain}) + "
                f"ANT2(G{self._diversity_ant2_gain})"
            )
            print(
                f"[Diversity] Preset geladen: ANT1 G{self._diversity_ant1_gain}, "
                f"ANT2 G{self._diversity_ant2_gain} (gemessen {measured})"
            )
        else:
            # Kein Preset: Standard-Gains + Hinweis
            self._diversity_ant1_gain = FlexRadio.PREAMP_PRESETS.get(band, 10)
            self._diversity_ant2_gain = FlexRadio.PREAMP_PRESETS.get(band, 10) + 10
            self.control_panel.dx_info.setText(
                f"ANT1(G{self._diversity_ant1_gain}) + "
                f"ANT2(G{self._diversity_ant2_gain})"
            )
            # Hinweis nur wenn kein Preset existiert (nicht wenn veraltet)
            if not preset:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(
                    500,
                    lambda: QMessageBox.information(
                        self, "Kein DX Preset",
                        f"Kein Antennen-Preset fuer {band}.\n\n"
                        f"Tipp: Mit DX TUNING einmessen → optimale Preamp-Werte\n"
                        f"fuer ANT1 und ANT2 separat finden.\n\n"
                        f"Standard-Gains werden verwendet:\n"
                        f"  ANT1: {self._diversity_ant1_gain} dB\n"
                        f"  ANT2: {self._diversity_ant2_gain} dB",
                    )
                )
            print(f"[Diversity] AKTIV — Standard-Gains, kein Preset fuer {band}")

    def _disable_diversity(self):
        """Diversity deaktivieren: zurueck auf ANT1."""
        self._diversity_stations = {}
        self._diversity_cycle = 0
        self._diversity_bias = "AUTO"
        self._ucb_selector.reset()
        self._apply_normal_mode()
        self.control_panel.dx_info.setText("")
        self.control_panel.clear_diversity_cycle()
        print("[Diversity] Deaktiviert")

    @Slot(str)
    def _on_bias_changed(self, bias: str):
        """Manueller Bias-Switch: Slot-Verteilung aendern."""
        self._diversity_bias = bias
        # Queue leeren (DeepSeek: Desync-Schutz bei Pattern-Wechsel)
        with self._diversity_lock:
            ant_queue = getattr(self, '_diversity_ant_queue', None)
            if ant_queue is not None:
                ant_queue.clear()
            self._diversity_cycle = 0  # Neustart Pattern-Zaehler
        print(f"[Diversity] Bias: {bias}")

    def _handle_dx_tuning(self):
        """DX-Tuning Modus: Preset laden oder Messung starten."""
        band = self.settings.band
        preset = self.settings.get_dx_preset(band)

        if preset:
            self._apply_dx_preset(preset)
            msg = QMessageBox(self)
            msg.setWindowTitle("DX Preset")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(
                f"DX Preset fuer {band} geladen:\n\n"
                f"  RX-Antenne:  {preset['rxant']}\n"
                f"  RF-Gain:     {preset['gain']} dB\n"
                f"  Gemessen:    {preset.get('measured', '?')}\n\n"
                f"TX bleibt auf ANT1."
            )
            msg.setStyleSheet(self._msgbox_style())
            msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            btn_new = msg.addButton(
                "Neu messen", QMessageBox.ButtonRole.ActionRole
            )
            msg.exec()
            if msg.clickedButton() == btn_new:
                self._start_dx_tuning()
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle("DX Tuning")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setText(
                f"Kein DX Preset fuer {band}.\n\n"
                f"DX Tuning starten?\n"
                f"(Messung dauert ca. 3-5 Minuten)"
            )
            msg.setStyleSheet(self._msgbox_style())
            btn_start = msg.addButton(
                "Tuning starten", QMessageBox.ButtonRole.AcceptRole
            )
            msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == btn_start:
                self._start_dx_tuning()
            else:
                pass  # EINMESSEN abgebrochen — Modus unveraendert lassen

    def _start_dx_tuning(self):
        """DX Tune Dialog — optional TUNE-Schritt + SWR-Pruefung vor Einmessen."""
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QTimer

        tune_power = self.settings.get("tune_power", 10)
        swr_limit  = self.settings.get("swr_limit", 3.0)

        # TUNE anbieten (Antennentuner einstellen bevor Messung startet)
        msg = QMessageBox(self)
        msg.setWindowTitle("Vor dem Einmessen: TUNE")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(
            f"Vor dem Einmessen den Tuner einstellen?\n\n"
            f"TUNE sendet {tune_power}W auf ANT1 fuer 5 Sekunden.\n"
            f"Bei SWR > {swr_limit:.1f} wird Einmessen abgebrochen."
        )
        msg.setStyleSheet(self._msgbox_style())
        btn_tune  = msg.addButton("Tunen + Messen", QMessageBox.ButtonRole.AcceptRole)
        btn_skip  = msg.addButton("Direkt messen",  QMessageBox.ButtonRole.ActionRole)
        btn_abort = msg.addButton("Abbrechen",      QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() == btn_abort:
            self._set_mode("normal")
            return

        if msg.clickedButton() == btn_tune and self.radio.ip:
            # TX-Leistung auf Tune-Wert setzen, TUNE starten
            self.radio._send_cmd(f"transmit set rfpower={tune_power}")
            self.radio.tune_on()

            def _after_tune():
                self.radio.tune_off()
                self.radio._send_cmd(f"transmit set rfpower={self.settings.power_watts}")
                # Buffer leeren: AT hat RX-Impedanz geändert → alte Daten ungültig
                self._normal_stations = {}
                self._diversity_stations = {}
                self.rx_panel.table.setRowCount(0)
                # SWR pruefen
                swr = self.radio._last_swr
                if swr > swr_limit:
                    QMessageBox.warning(
                        self, "SWR zu hoch",
                        f"SWR {swr:.1f} > {swr_limit:.1f} — Einmessen abgebrochen.\n"
                        f"Antenne/Tuner pruefen!"
                    )
                    self._set_mode("normal")
                    return
                self._open_dx_tune_dialog()

            QTimer.singleShot(5000, _after_tune)
        else:
            # Direkt einmessen ohne TUNE
            self._open_dx_tune_dialog()

    def _open_dx_tune_dialog(self):
        """DX Tune Dialog oeffnen — NICHT-MODAL damit Signale durchkommen."""
        band = self.settings.band
        dialog = DXTuneDialog(self.radio, band, parent=self)
        self._dx_tune_dialog = dialog

        # Nicht-modal: open() statt exec() — sonst blockiert der
        # modale Event-Loop die Signal-Zustellung vom Decoder-Thread
        dialog.accepted.connect(self._on_dx_tune_accepted)
        dialog.rejected.connect(self._on_dx_tune_rejected)
        dialog.show()

    def _on_dx_tune_accepted(self):
        """DX Tuning erfolgreich — Preset speichern."""
        dialog = self._dx_tune_dialog
        if dialog is None:
            return
        r = dialog.get_results()
        band = self.settings.band
        self.settings.save_dx_preset(
            band=band,
            rxant=r.get("best_ant", "ANT1"),
            gain=r.get("best_gain", 0),
            ant1_avg=r.get("ant1_avg", 0.0),
            ant2_avg=r.get("ant2_avg", 0.0),
            ant1_gain=r.get("ant1_gain", r.get("best_gain", 0)),
            ant2_gain=r.get("ant2_gain", r.get("best_gain", 0)),
        )
        ant1_g = r.get("ant1_gain", r.get("best_gain", 0))
        ant2_g = r.get("ant2_gain", r.get("best_gain", 0))
        self.control_panel.dx_info.setText(
            f"ANT1(G{ant1_g}) + ANT2(G{ant2_g})"
        )
        # Diversity-Gains sofort aktualisieren falls gerade aktiv
        if self._rx_mode == "diversity":
            self._diversity_ant1_gain = ant1_g
            self._diversity_ant2_gain = ant2_g
        self._dx_tune_dialog = None

    def _on_dx_tune_rejected(self):
        """DX Tuning abgebrochen — zurueck auf Normal."""
        self._dx_tune_dialog = None
        self._dx_mode = False
        self._apply_normal_mode()
        self.control_panel.dx_info.setText("")

    def _apply_dx_preset(self, preset: dict):
        """DX-Preset am Radio anwenden."""
        s = self.radio._slice_idx
        rxant = preset.get("rxant", "ANT1")
        gain = preset.get("gain", 10)
        self.radio._send_cmd(f"slice set {s} rxant={rxant}")
        self.radio._send_cmd(f"slice set {s} rfgain={gain}")
        self.radio._send_cmd(f"slice set {s} txant=ANT1")
        self.control_panel.dx_info.setText(f"{rxant}, Gain {gain} dB")
        print(f"[DX] Preset geladen: {rxant}, Gain {gain}")

    def _apply_dx_preset_for_band(self, band: str):
        """DX-Preset fuer ein bestimmtes Band laden (nach Bandwechsel)."""
        preset = self.settings.get_dx_preset(band)
        if preset:
            self._apply_dx_preset(preset)
        else:
            self.control_panel.dx_info.setText("kein Preset")

    def _apply_normal_mode(self):
        """Normal-Modus: beste RX-Antenne aus DX-Preset (falls vorhanden), TX immer ANT1."""
        s = self.radio._slice_idx
        band = self.settings.band
        from radio.flexradio import FlexRadio

        preset = self.settings.get_dx_preset(band)
        if preset:
            rxant = preset.get("rxant", "ANT1")
            gain  = preset.get("gain", FlexRadio.PREAMP_PRESETS.get(band, 10))
            # Alter des Presets berechnen
            import datetime
            measured_str = preset.get("measured", "")
            age_days = None
            try:
                measured_dt = datetime.datetime.strptime(measured_str, "%Y-%m-%d %H:%M")
                age_days = (datetime.datetime.now() - measured_dt).days
            except Exception:
                pass
            if age_days is not None and age_days > 7:
                self.control_panel.dx_info.setText(f"RX:{rxant} G{gain}dB ({age_days}d alt!)")
                self.control_panel.dx_info.setStyleSheet("color: #FFA500;")
            else:
                self.control_panel.dx_info.setText(f"RX:{rxant} G{gain}dB")
                self.control_panel.dx_info.setStyleSheet("")
            print(f"[DX] Normal-Modus: RX={rxant} TX=ANT1, Gain {gain} (Preset, {age_days}d alt)")
        else:
            rxant = "ANT1"
            gain  = FlexRadio.PREAMP_PRESETS.get(band, 10)
            self.control_panel.dx_info.setText("Kein Preset")
            self.control_panel.dx_info.setStyleSheet("color: #888888;")
            print(f"[DX] Normal-Modus: ANT1, Gain {gain} (kein Preset)")

        self.radio._send_cmd(f"slice set {s} rxant={rxant}")
        self.radio._send_cmd(f"slice set {s} txant=ANT1")
        self.radio._send_cmd(f"slice set {s} rfgain={gain}")

    # ── Meter / SWR ─────────────────────────────────────────────

    @Slot(float)
    def _on_swr_alarm(self, swr: float):
        import time as _t
        now = _t.time()
        if now - getattr(self, '_last_swr_alarm', 0) < 10:
            return  # Cooldown: max 1 Alarm pro 10s
        self._last_swr_alarm = now
        self.statusBar().showMessage(f"SWR ALARM: {swr:.1f} — TX gestoppt! Tuner/Antenne pruefen.", 10000)
        print(f"[SWR] Alarm: {swr:.1f} — TX gestoppt")

    @Slot(str, float)
    def _on_meter_update(self, name: str, value: float):
        if name == "FWDPWR":
            self.control_panel.update_watt(value)
        elif name == "SWR":
            self.control_panel.update_swr(value)
        elif name == "ALC":
            self.control_panel.update_alc(value)

    # ── QSO Steuerung ──────────────────────────────────────────

    @Slot(bool)
    def _on_auto_toggled(self, auto_on: bool):
        self.qso_sm.auto_mode = auto_on
        self.settings.set("auto_mode", auto_on)

    @Slot()
    def _on_cq_clicked(self):
        if self.control_panel.btn_cq.isChecked():
            # CQ: immer auf festem Slot senden (aktueller Gegenteil-Slot)
            # So antworten Stationen konsistent im anderen Slot
            self.encoder.tx_even = not self.timer.is_even_cycle()
            slot = "EVEN" if self.encoder.tx_even else "ODD"
            print(f"[CQ] Fester TX-Slot: {slot}")
            self.qso_panel.add_info("CQ-Modus gestartet")
            self.qso_sm.start_cq()
        else:
            count = self.qso_sm.cq_qso_count
            self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
            self.qso_sm.stop_cq()
            self.control_panel.update_qso_counter(0)

    @Slot()
    def _on_advance(self):
        self.qso_sm.advance()

    @Slot()
    def _on_cancel(self):
        self._active_qso_targets.clear()
        self.rx_panel.set_active_call("")
        self.qso_panel.add_info("QSO abgebrochen")
        self.qso_sm.cancel()
        self.control_panel.set_cq_active(False)

    @Slot(object)
    def _on_state_changed(self, state: QSOState):
        name = state.name
        self.control_panel.update_state(name)
        # AP-Prioritaet: aktiver QSO-Partner bekommt hoechste AP-Hint-Prioritaet
        if state not in (QSOState.IDLE, QSOState.TIMEOUT):
            self.decoder.priority_call = getattr(
                self.qso_sm, 'their_call', ''
            ) or ""
        else:
            self.decoder.priority_call = ""

        in_qso = state not in (
            QSOState.IDLE, QSOState.TIMEOUT,
            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
        )
        self.control_panel.btn_advance.setEnabled(
            state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73)
            and not self.qso_sm.auto_mode
            and not self.qso_sm.cq_mode
        )
        self.control_panel.btn_cancel.setEnabled(
            in_qso or state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT)
        )

        is_tx = state in (
            QSOState.TX_CALL, QSOState.TX_REPORT,
            QSOState.TX_RR73, QSOState.CQ_CALLING,
        )
        self.control_panel.set_tx_active(is_tx)

        if self.qso_sm.cq_mode:
            self.control_panel.update_qso_counter(self.qso_sm.cq_qso_count)

    def _on_tx_finished(self):
        """TX abgeschlossen — PTT aus, zurueck zu RX."""
        self.control_panel.set_tx_active(False)
        # Race-Condition-Schutz: wenn Encoder noch eine gequeuete Nachricht hat,
        # war dieses TX die ALTE Nachricht (z.B. CQ). State hat sich schon geaendert
        # (z.B. zu TX_REPORT). NICHT on_message_sent() aufrufen — warten bis
        # die gequeuete Nachricht tatsaechlich gesendet wurde.
        if getattr(self.encoder, '_pending_msg', None):
            print("[TX] Alte Nachricht fertig — pending message folgt, kein State-Wechsel")
        else:
            self.qso_sm.on_message_sent()
        # Pending Klick ausfuehren (Station waehrend TX angeklickt)
        pending = getattr(self, '_pending_click', None)
        if pending:
            self._pending_click = None
            print(f"[QSO] TX fertig — starte gequeueten Klick auf {pending.caller}")
            self._on_station_clicked(pending)

    @Slot(str)
    def _on_send_message(self, message: str):
        """FT8-Nachricht encoden und ueber FlexRadio senden."""
        self.qso_panel.add_tx(message)
        self.encoder.transmit(message)

    @Slot(object)
    def _on_qso_complete(self, qso_data):
        """QSO abgeschlossen — ADIF schreiben."""
        self._active_qso_targets.discard(qso_data.their_call)
        self.rx_panel.set_active_call("")
        self.qso_panel.add_qso_complete(qso_data.their_call)

        band = self.settings.band.upper()
        freq = self.settings.frequency_mhz

        self.adif.log_qso(
            call=qso_data.their_call,
            band=band,
            freq_mhz=freq,
            mode=self.settings.mode,
            rst_sent=qso_data.our_snr or "-10",
            rst_rcvd=qso_data.their_snr or "-10",
            gridsquare=qso_data.their_grid or "",
            my_gridsquare=self.settings.locator,
            my_callsign=self.settings.callsign,
            tx_power=self.settings.power_watts,
            time_on=qso_data.start_time,
        )

    @Slot(str)
    def _on_qso_timeout(self, their_call: str):
        self._active_qso_targets.discard(their_call)
        self.rx_panel.set_active_call("")
        self.qso_panel.add_timeout(their_call)

    # ── Timer ───────────────────────────────────────────────────

    @Slot(float, float)
    def _on_cycle_tick(self, seconds_in_cycle: float, cycle_duration: float):
        if not self.rx_panel._rx_active:
            return
        self.control_panel.update_cycle_bar(seconds_in_cycle, cycle_duration)

    @Slot(int, bool)
    def _on_cycle_start(self, cycle_num: int, is_even: bool):
        self.qso_sm.on_cycle_end()

        # Diversity: Antenne umschalten bei jedem Zyklus (non-blocking)
        if self._rx_mode == "diversity" and self.radio.ip and self.rx_panel._rx_active:
            # BUG-1: TX-Schutz — waehrend TX keine Antenne umschalten!
            if self.encoder.is_transmitting:
                return

            with self._diversity_lock:  # BUG-2: Race Condition Guard
                # Queue: aktuelle Antenne merken BEVOR umgeschaltet wird.
                ant_queue = getattr(self, '_diversity_ant_queue', None)
                if ant_queue is not None:
                    ant_queue.append(self._diversity_current_ant)

                self._diversity_cycle += 1
                s = self.radio._slice_idx
                band = self.settings.band

                # Bias-basiertes Pattern (DeepSeek-Review: _BIAS_PATTERNS Dict)
                bias = self._diversity_bias
                pattern = self._BIAS_PATTERNS.get(bias)
                if pattern is None:
                    # AUTO: UCB1-Algorithmus waehlt adaptiv die bessere Antenne
                    # Ersetzt das feste 4-Zyklus Even/Odd Pattern
                    _pos = (self._diversity_cycle - 1) % 4  # nur fuer Zyklus-Indikator
                    try:
                        self._diversity_current_ant = self._ucb_selector.choose()
                    except Exception:
                        # Fallback auf einfaches Even/Odd
                        self._diversity_current_ant = "A1" if (self._diversity_cycle % 2) == 1 else "A2"
                else:
                    _pos = (self._diversity_cycle - 1) % len(pattern)
                    self._diversity_current_ant = pattern[_pos]

                if self._diversity_current_ant == "A1":
                    gain = getattr(self, '_diversity_ant1_gain',
                                   FlexRadio.PREAMP_PRESETS.get(band, 10))
                else:
                    gain = getattr(self, '_diversity_ant2_gain',
                                   FlexRadio.PREAMP_PRESETS.get(band, 10) + 10)
                ant_cmd = "ANT1" if self._diversity_current_ant == "A1" else "ANT2"
                self.control_panel.update_diversity_cycle(_pos, self._diversity_current_ant)

            # BUG-3: ant_cmd + gain als Argumente, nicht als Closure
            import threading
            def _switch(cmd=ant_cmd, g=gain, sl=s):
                self.radio._send_cmd(f"slice set {sl} rxant={cmd}")
                self.radio._send_cmd(f"slice set {sl} rfgain={g}")
            threading.Thread(target=_switch, daemon=True).start()

    def on_message_decoded(self, msg: FT8Message):
        """Vom Decoder — NUR fuer QSO-Logik, NICHT fuer Tabelle!"""
        if not self.rx_panel._rx_active:
            return
        self.control_panel.update_snr(msg.snr)
        self.qso_sm.set_last_snr(msg.snr)
        self.qso_sm.on_message_received(msg)

        # Empfangene an-uns-Nachricht im QSO-Log
        if msg.target == self.settings.callsign:
            self.qso_panel.add_rx(msg.raw)

    # ── PSKReporter ─────────────────────────────────────────────

    def _fetch_psk_stats(self):
        import threading
        threading.Thread(target=self._psk_worker, daemon=True).start()

    def _psk_worker(self):
        import urllib.request
        import xml.etree.ElementTree as ET
        import math

        call = self.settings.callsign
        my_grid = self.settings.locator
        try:
            url = (f"https://retrieve.pskreporter.info/query?"
                   f"senderCallsign={call}&flowStartSeconds=-600&mode=FT8")
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

            self.control_panel.update_psk_stats(
                len(spots), avg_km, max_spot[0],
                max_spot[2], max_spot[3],
                n_km, e_km, s_km, w_km,
            )
        except Exception as e:
            print(f"[PSK] Fehler: {e}")

    # ── Settings ────────────────────────────────────────────────

    @Slot()
    def _on_settings_clicked(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self._update_statusbar()
            self.qso_sm.max_calls = self.settings.get("max_calls", 3)
            if hasattr(self.radio, '_tx_audio_level'):
                self.radio._tx_audio_level = (
                    self.settings.get("tx_level", 100) / 100.0
                )
            if self.radio.ip:
                self.radio.set_power(self.settings.power_watts)

    def _update_statusbar(self):
        freq = self.settings.frequency_mhz
        mode_labels = {
            "normal": "Normal",
            "diversity": "DIVERSITY",
        }
        mode_str = mode_labels.get(self._rx_mode, "Normal")
        self.statusBar().showMessage(
            f"{self.settings.callsign}  |  {self.settings.locator}  |  "
            f"{self.settings.mode}  |  {self.settings.band}  |  "
            f"{freq:.3f} MHz  |  {mode_str}"
        )

    # ── Hilfsfunktionen ─────────────────────────────────────────

    @staticmethod
    def _msgbox_style() -> str:
        return """
            QMessageBox {
                background-color: #1a1a2e;
            }
            QMessageBox QLabel {
                color: #CCC;
                font-family: Menlo;
                font-size: 12px;
            }
            QPushButton {
                background: #333; color: #CCC;
                border: 1px solid #555; border-radius: 4px;
                padding: 6px 16px; font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover { background: #444; }
        """

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
