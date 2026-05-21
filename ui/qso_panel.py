"""SimpleFT8 QSO Panel — Fenster 2: QSO-Verlauf + Logbuch mit Tabs."""

import time
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QStackedWidget, QSizePolicy, QMenu,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from ui.logbook_widget import LogbookWidget


# P79 (v0.97.51): Symbol-Auto-Detect in add_info (Variante B KISS).
# Wenn der Text mit einem dieser Symbole beginnt, wird das Symbol farbig
# gerendert, der Rest bleibt im heutigen Dezent-Grau (#666666). Mike-Wunsch
# „Warnungen sichtbarer, Rest lesbar". Neue Eintraege nur bei kuenftigen
# add_info-Praefixen noetig — bestehende ~30 Call-Sites bleiben unveraendert.
_SYMBOL_COLORS = {
    "⚠": "#FFAA00",   # Orange (analog Bundle F v0.97.23: Magenta→Orange)
    "✓": "#44FF44",   # Hellgruen (analog add_qso_complete)
    "✗": "#FF4444",   # Hellrot (analog add_timeout)
    "⏳": "#44BBFF",   # Cyan (analog add_rx)
}


# Signal wie von QTabWidget — Mixin sendet Index-Wechsel
class QSOPanel(QWidget):
    """QSO-Verlaufsfenster mit Tabs: Live Log + Logbuch."""

    upload_qrz = Signal()  # QRZ.com Upload angefordert
    # Bundle E (v0.97.22): TX-Slot-Lock (Mike SmartSDR-Style, Normal-only)
    # — emittet "none"|"even"|"odd". MainWindow persistiert + Settings.
    # Wirkung: Encoder.tx_even wird auf gewählten Slot festgesetzt
    # (via core/qso_state.resolve_tx_slot).
    tx_slot_lock_changed = Signal(str)
    # P95 (v0.97.67): Spalten-Config Rechtsklick → persistiert via MainWindow.
    eo_tag_visibility_changed = Signal(bool)
    ant_label_visibility_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        # P95 (v0.97.67): Spalten-Visibility-Flags VOR _setup_ui (wird im
        # log_view-Context-Menu gelesen). Default: beide an.
        self._show_eo_tag: bool = True
        self._show_ant_label: bool = True
        # P95: _entries als SOT für Re-Render bei Toggle. Ersetzt
        # _block_timestamps (waren parallel zu log_view-Blocks).
        self._entries: list[dict] = []
        self._setup_ui()
        self._qso_count = 0
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(30_000)  # 30s
        self._cleanup_timer.timeout.connect(self._auto_trim_by_age)
        self._cleanup_timer.start()
        # P29 (11.05.2026): letzter OMNI-TX-Parity-State fuer Leerzeilen-
        # Trennung bei Paritaets-Wechsel. None = noch kein OMNI-TX gesehen.
        # P95: bei _rerender_all() wird der State durchlaufend rekonstruiert.
        self._last_omni_tx_even: bool | None = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Kopf-Zeile: links EVEN/ODD | rechts QSO/Logbuch-Tabs ──
        head_row = QHBoxLayout()
        head_row.setContentsMargins(2, 0, 2, 0)
        head_row.setSpacing(8)

        # Bundle D (v0.97.21): Links EVEN/ODD als Filter-Buttons
        # (Normal-Modus only). In Diversity ausgeblendet via
        # set_slot_buttons_visible(False). 2 exclusive QPushButtons
        # mit "both"-Default (keiner checked = beide Slots sichtbar).
        self._slot_container = QWidget()
        self._slot_container.setSizePolicy(QSizePolicy.Policy.Expanding,
                                           QSizePolicy.Policy.Fixed)
        slot_row = QHBoxLayout(self._slot_container)
        slot_row.setContentsMargins(0, 0, 0, 0)
        slot_row.setSpacing(4)
        self._btn_even = QPushButton("EVEN")
        self._btn_odd = QPushButton("ODD")
        for btn in (self._btn_even, self._btn_odd):
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Stylesheet konsistent mit rx_panel _FILTER_STYLE (R1-S1)
        slot_btn_style = (
            "QPushButton { background: #222; color: #888;"
            " border: 1px solid #444; border-radius: 3px; padding: 2px 8px; }"
            "QPushButton:hover { background: #2a2a2a; color: #CCC; }"
            "QPushButton:checked { background: #883300; color: #FFF;"
            " border-color: #FF6622; }"
        )
        self._btn_even.setStyleSheet(slot_btn_style)
        self._btn_odd.setStyleSheet(slot_btn_style)
        self._btn_even.setToolTip(
            "TX-Slot-Lock: senden nur im Even-Slot (hören im Odd).\n"
            "Klick erneut zum Aufheben.")
        self._btn_odd.setToolTip(
            "TX-Slot-Lock: senden nur im Odd-Slot (hören im Even).\n"
            "Klick erneut zum Aufheben.")
        self._btn_even.clicked.connect(lambda: self._on_slot_btn_clicked("even"))
        self._btn_odd.clicked.connect(lambda: self._on_slot_btn_clicked("odd"))
        slot_row.addWidget(self._btn_even)
        slot_row.addWidget(self._btn_odd)
        # Legacy-Aliase fuer alten Code-Pfad — verweisen auf Buttons.
        # _update_slot_display ist No-Op geworden (Slot-Live ist jetzt
        # in der Statusbar als _slot_progress_bar, Bundle D AC13-15).
        self._even_label = self._btn_even
        self._odd_label = self._btn_odd

        # Rechts: QSO/Logbuch Tab-Buttons
        tabs_container = QWidget()
        tabs_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tabs_row = QHBoxLayout(tabs_container)
        tabs_row.setContentsMargins(0, 0, 0, 0)
        tabs_row.setSpacing(0)
        self._btn_tab_qso = QPushButton("QSO")
        self._btn_tab_log = QPushButton("Logbuch")
        for btn in (self._btn_tab_qso, self._btn_tab_log):
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_tab_qso.setChecked(True)
        self._apply_tab_button_style()
        self._btn_tab_qso.clicked.connect(lambda: self._set_tab_index(0))
        self._btn_tab_log.clicked.connect(lambda: self._set_tab_index(1))
        # P100: Rechtsklick auf QSO-Tab-Button → gleiches Spalten-Menü
        # wie im Log-Bereich (ohne Copy/SelectAll, da Button kein Text-Widget).
        self._btn_tab_qso.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._btn_tab_qso.customContextMenuRequested.connect(
            self._on_qso_button_context_menu)
        tabs_row.addWidget(self._btn_tab_qso)
        tabs_row.addWidget(self._btn_tab_log)

        head_row.addWidget(self._slot_container, 1)
        head_row.addWidget(tabs_container, 1)
        # Bundle D AC11: bei verstecktem slot_container füllen
        # QSO+Logbuch-Buttons den Platz (Expanding ist schon gesetzt).
        self._tabs_container = tabs_container
        layout.addLayout(head_row)
        # Bundle D: _slot_timer entfaellt — Slot-Live-Indikator ist jetzt
        # die _slot_progress_bar in der Statusbar (cyan/magenta).

        # ── Inhalt: QStackedWidget ersetzt QTabWidget ──
        self.tabs = QStackedWidget()
        self.tabs.setStyleSheet(
            "QStackedWidget { border: 1px solid #333; border-radius: 4px; "
            "background: #0d0d1a; }"
        )
        # currentChanged → damit _on_qso_tab_changed im Main Window weiter funktioniert
        self.tabs.currentChanged.connect(self._on_tab_changed_internal)

        # Tab 1: Live QSO Log
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        live_layout.setContentsMargins(0, 4, 0, 0)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Menlo", 12))
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d1a;
                color: #CCCCCC;
                border: none;
                padding: 6px;
                selection-background-color: #0066AA;
            }
        """)
        # P95 (v0.97.67): Rechtsklick auf log_view → Spalten-Toggle-Menü
        # (Even/Odd-Tag, Antennen-Label). Persistierung via MainWindow.
        self.log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._on_log_context_menu)
        live_layout.addWidget(self.log_view)

        self.status_label = QLabel("Keine QSOs")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        live_layout.addWidget(self.status_label)

        self.tabs.addWidget(live_tab)

        # Tab 2: Logbuch
        self.logbook = LogbookWidget()
        self.logbook.upload_requested.connect(self.upload_qrz.emit)
        self.tabs.addWidget(self.logbook)

        layout.addWidget(self.tabs)

    # Kompatibilitaet mit QTabWidget API (main_window.py ruft tabs.currentChanged)
    def _on_tab_changed_internal(self, index: int):
        self._btn_tab_qso.setChecked(index == 0)
        self._btn_tab_log.setChecked(index == 1)
        self._apply_tab_button_style()

    def _set_tab_index(self, index: int):
        self.tabs.setCurrentIndex(index)

    def _apply_tab_button_style(self):
        active_ss = (
            "QPushButton { background: #0d0d1a; color: #00AAFF; "
            "border: 1px solid #333; border-bottom: 2px solid #00AAFF; "
            "font-family: Menlo; font-size: 11px; font-weight: bold; }"
        )
        inactive_ss = (
            "QPushButton { background: #1a1a2e; color: #888; "
            "border: 1px solid #333; "
            "font-family: Menlo; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { color: #CCCCCC; }"
        )
        self._btn_tab_qso.setStyleSheet(active_ss if self._btn_tab_qso.isChecked() else inactive_ss)
        self._btn_tab_log.setStyleSheet(active_ss if self._btn_tab_log.isChecked() else inactive_ss)

    def _slot_tag(self) -> str:
        """Aktuellen Slot als Tag: [E] oder [O]."""
        now = time.time()
        slot = getattr(self, '_cycle_duration', 15.0)
        return "[E]" if int(now / slot) % 2 == 0 else "[O]"

    def add_tx(self, message: str, ant_label: str = "",
               tx_even: bool | None = None,
               slot_start_ts: float | None = None,
               omni_remaining: int | None = None):
        """Eigene gesendete Nachricht — IMMER ins Log (Mike-Wunsch v0.78:
        keine Sammelanzeige, alle CQ-Rufe einzeln untereinander sichtbar).

        P95 (v0.97.67): Eintrag in `_entries` + `_render_entry` für
        Re-Render-Fähigkeit bei Toggle (Spalten-Visibility).
        """
        if slot_start_ts is None or tx_even is None:
            now = time.time()
            slot = getattr(self, '_cycle_duration', 15.0)
            slot_start_ts = now - (now % slot)
            tx_even = int(slot_start_ts / slot) % 2 == 0
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
        tag = "[E]" if tx_even else "[O]"
        entry = {
            "kind": "tx", "ts": time.time(), "utc": utc, "tag": tag,
            "tx_even": tx_even, "message": message,
            "ant_label": ant_label, "omni_remaining": omni_remaining,
        }
        self._entries.append(entry)
        self._render_entry(entry)

    def add_rx(self, message: str,
               tx_even: bool | None = None,
               slot_start_ts: float | None = None,
               ant_label: str = ""):
        """Empfangene Antwort anzeigen.

        ant_label: P15 — '(ANT2 ↑X.X dB)' zeigt welche Antenne RX gewann.
        P95: Eintrag in `_entries` + `_render_entry`.
        """
        if slot_start_ts is None or tx_even is None:
            now = time.time()
            slot = getattr(self, '_cycle_duration', 15.0)
            slot_start_ts = now - (now % slot)
            tx_even = int(slot_start_ts / slot) % 2 == 0
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
        tag = "[E]" if tx_even else "[O]"
        entry = {
            "kind": "rx", "ts": time.time(), "utc": utc, "tag": tag,
            "message": message, "ant_label": ant_label,
        }
        self._entries.append(entry)
        self._render_entry(entry)

    def add_listening(self, slot_start_ts: float, tx_even: bool):
        """OMNI RX-Slot-Anzeige (Lebenszeichen in stillen Slots)."""
        utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
        tag = "[E]" if tx_even else "[O]"
        entry = {"kind": "listening", "ts": time.time(),
                 "utc": utc, "tag": tag}
        self._entries.append(entry)
        self._render_entry(entry)

    def add_qso_complete(self, their_call: str):
        """QSO als abgeschlossen markieren."""
        self._qso_count += 1
        entry = {"kind": "complete", "ts": time.time(),
                 "their_call": their_call}
        self._entries.append(entry)
        self._render_entry(entry)
        self.status_label.setText(f"{self._qso_count} QSO(s) diese Session")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")

    def add_timeout(self, their_call: str):
        """Timeout anzeigen."""
        entry = {"kind": "timeout", "ts": time.time(),
                 "their_call": their_call}
        self._entries.append(entry)
        self._render_entry(entry)

    def add_info(self, text: str):
        """Info-Nachricht anzeigen.

        P79 (v0.97.51): Symbol-Auto-Detect — Symbol farbig, Rest grau.
        P95 (v0.97.67): in `_entries` für Re-Render.
        """
        if not text:
            return
        entry = {"kind": "info", "ts": time.time(), "text": text}
        self._entries.append(entry)
        self._render_entry(entry)

    def _render_entry(self, e: dict):
        """P95 (v0.97.67): Eintrag basierend auf Visibility-Flags rendern.

        Wird sowohl beim Live-Append (add_*) als auch beim Re-Render
        (Toggle) aufgerufen. P29 OMNI-Parity-Tracker wird hier gepflegt
        (Live: durchlaufend; Re-Render: vor _rerender_all auf None reset).
        """
        kind = e["kind"]
        if kind == "tx":
            tag_str = f"{e['tag']} " if self._show_eo_tag else ""
            line = f"{e['utc']} {tag_str}→ Sende {e['message']}"
            omni_rem = e.get("omni_remaining")
            if omni_rem is not None:
                line = f"{line} ↻{omni_rem}"
                # P29: Leerzeile bei OMNI-Paritätswechsel
                if (self._last_omni_tx_even is not None
                        and self._last_omni_tx_even != e['tx_even']):
                    self._append_colored("", "#000000")
                self._last_omni_tx_even = e['tx_even']
                tx_color = "#E09600" if e['tx_even'] else "#FFAA00"
            else:
                tx_color = "#FFAA00"
            ant = e.get("ant_label", "")
            if ant and self._show_ant_label:
                self._append_two_color(line, tx_color, f" {ant}", "#888888")
            else:
                self._append_colored(line, tx_color)
        elif kind == "rx":
            tag_str = f"{e['tag']} " if self._show_eo_tag else ""
            line = f"{e['utc']} {tag_str}← Empf. {e['message']}"
            ant = e.get("ant_label", "")
            if ant and self._show_ant_label:
                self._append_two_color(line, "#44BBFF",
                                       f" {ant}", "#888888")
            else:
                self._append_colored(line, "#44BBFF")
        elif kind == "listening":
            tag_str = f"{e['tag']} " if self._show_eo_tag else ""
            self._append_colored(
                f"{e['utc']} {tag_str}← Horche …", "#666666")
        elif kind == "complete":
            self._append_colored(
                f"       ✓ QSO mit {e['their_call']} komplett", "#44FF44")
            self._append_colored("─" * 30, "#333333")
        elif kind == "timeout":
            self._append_colored(
                f"       ✗ {e['their_call']} — Timeout", "#FF4444")
            self._append_colored("─" * 30, "#333333")
        elif kind == "info":
            text = e["text"]
            for symbol, color in _SYMBOL_COLORS.items():
                if text.startswith(symbol):
                    self._append_two_color(
                        f"       {symbol}", color,
                        text[len(symbol):], "#666666")
                    return
            self._append_colored(f"       {text}", "#666666")

    def _rerender_all(self):
        """P95 (v0.97.67): log_view komplett neu aus `_entries` zeichnen.

        Wird bei Visibility-Toggle und nach _auto_trim_by_age gerufen.
        Scroll-Position wird absolut wiederhergestellt (R1-F2 clamped
        auf neues max). _last_omni_tx_even durchlaufend rekonstruiert.
        """
        sb = self.log_view.verticalScrollBar()
        saved = sb.value()
        max_before = sb.maximum()
        at_bottom = saved >= max_before - 5
        self.log_view.clear()
        self._last_omni_tx_even = None
        for entry in self._entries:
            self._render_entry(entry)
        if at_bottom:
            sb.setValue(sb.maximum())
        else:
            sb.setValue(min(saved, sb.maximum()))

    def _build_columns_menu(self):
        """P100 (v0.97.71) + P101 (v0.97.73): Spalten-Toggle-Menü Builder.

        P101 nach Mike-Field-Test 21.05.: Padding symmetrisch 20/20 (zuvor
        asymmetrisch 32/28). Indicator explizit `subcontrol-position:
        left center` — verhindert dass macOS den Haken rechts rendert
        (themen-abhängige Qt-Default-Position, R1-Empfehlung).
        """
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1a1a2e; color: #CCC; border: 1px solid #444; }"
            "QMenu::item { padding: 4px 20px 4px 20px; }"
            "QMenu::item:selected { background: #0066AA; }"
            "QMenu::item:checked { color: #00AAFF; }"
            "QMenu::indicator { width: 14px; height: 14px; margin-left: 0px;"
            " subcontrol-position: left center; }"
        )
        a_eo = menu.addAction("Even/Odd-Tag")
        a_eo.setCheckable(True)
        a_eo.setChecked(self._show_eo_tag)
        a_eo.triggered.connect(self._toggle_eo_tag)
        a_ant = menu.addAction("Antennen-Anzeige")
        a_ant.setCheckable(True)
        a_ant.setChecked(self._show_ant_label)
        a_ant.triggered.connect(self._toggle_ant_label)
        return menu

    def _on_log_context_menu(self, pos):
        """P95 (v0.97.67): Rechtsklick auf log_view → Spalten-Toggle-Menü.

        P100 (v0.97.71): Copy/SelectAll entfernt (Mike-Wunsch — Menü soll
        nur Spalten-Toggles enthalten). Padding rechts 20→32px.
        """
        menu = self._build_columns_menu()
        menu.exec(self.log_view.mapToGlobal(pos))

    def _on_qso_button_context_menu(self, pos):
        """P100 (v0.97.71): Rechtsklick auf QSO-Tab-Button → Spalten-Menü.

        Mike-Spec: konsistent zum log_view-Pfad. QSO-Button ist optisch
        näher an „Spaltenkopf"-Erwartung als der Log-Bereich selber.
        """
        menu = self._build_columns_menu()
        menu.exec(self._btn_tab_qso.mapToGlobal(pos))

    def _toggle_eo_tag(self, show: bool):
        """P95: Even/Odd-Tag ein/ausblenden + Re-Render + persistieren."""
        self._show_eo_tag = show
        self._rerender_all()
        self.eo_tag_visibility_changed.emit(show)

    def _toggle_ant_label(self, show: bool):
        """P95: Antennen-Label ein/ausblenden + Re-Render + persistieren."""
        self._show_ant_label = show
        self._rerender_all()
        self.ant_label_visibility_changed.emit(show)

    def _update_slot_display(self):
        """Bundle D (v0.97.21): No-Op geworden.

        Vorher: färbte _even_label/_odd_label im 500ms-Takt mit Live-
        Slot-Highlight. Jetzt sind EVEN/ODD Filter-Buttons (kein Live-
        Indikator mehr). Slot-Phase wird in der Statusbar
        (_slot_progress_bar mit cyan/magenta) angezeigt.

        Bleibt als Stub damit alter Code-Pfad nicht crasht.
        """
        return

    def _on_slot_btn_clicked(self, parity: str) -> None:
        """Bundle E (v0.97.22): TX-Slot-Lock-Button-Klick.

        Exklusive Logik: Klick auf einen Button checkt ihn, uncheckt
        den anderen. Klick auf bereits aktiven Button uncheckt ihn →
        Lock aus (= "none"). Emittet ``tx_slot_lock_changed``.
        MainWindow persistiert den Wert in Settings.
        """
        if parity == "even":
            if self._btn_even.isChecked():
                self._btn_odd.setChecked(False)
        elif parity == "odd":
            if self._btn_odd.isChecked():
                self._btn_even.setChecked(False)
        # Lock-Wert berechnen
        e = self._btn_even.isChecked()
        o = self._btn_odd.isChecked()
        if e and not o:
            lock = "even"
        elif o and not e:
            lock = "odd"
        else:
            lock = "none"
        self.tx_slot_lock_changed.emit(lock)

    def set_slot_buttons_visible(self, visible: bool) -> None:
        """Bundle D/E: EVEN/ODD-Buttons-Container ein-/ausblenden.

        In Diversity-Modus: ausblenden (Lock wirkt eh nur Normal). Lock-
        State in Settings bleibt persistiert. MainWindow ruft auf bei
        rx_mode-Wechsel.
        """
        self._slot_container.setVisible(visible)

    def set_tx_slot_lock_buttons(self, lock: str) -> None:
        """Bundle E (v0.97.22): Buttons aus Settings-Wert setzen.

        Wird bei App-Start (Normal-Modus) + Modus-Wechsel zurück Normal
        aufgerufen. Setzt Buttons OHNE Signal-Emit (blockSignals).
        """
        if lock not in ("none", "even", "odd"):
            lock = "none"
        self._btn_even.blockSignals(True)
        self._btn_odd.blockSignals(True)
        self._btn_even.setChecked(lock == "even")
        self._btn_odd.setChecked(lock == "odd")
        self._btn_even.blockSignals(False)
        self._btn_odd.blockSignals(False)

    def _append_colored(self, text: str, color: str):
        """Single-Block Append in einer Farbe.

        P95 (v0.97.67): kein _block_timestamps mehr — _entries ist SOT
        und enthält die Timestamps für _auto_trim_by_age.
        """
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.setTextColor(QColor(color))
        self.log_view.append(text)
        # Auto-Scroll nach unten
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_two_color(self, text1: str, color1: str, text2: str, color2: str):
        """Single-Block Append in zwei Farben (Haupttext + Akzent)."""
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.setTextColor(QColor(color1))
        self.log_view.append(text1)
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color2))
        cursor.insertText(text2, fmt)
        self.log_view.setTextCursor(cursor)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _auto_trim_by_age(self, max_age_s: float = 300.0):
        """P1.16 / P95 (v0.97.67): Einträge älter als max_age_s entfernen.

        P95: arbeitet jetzt auf `_entries` (SOT) statt parallel zum
        log_view-Block-Count. Bei Trim → _rerender_all() zeichnet log_view
        komplett neu. Mindest-Schwelle 5 verhindert Flackern.
        """
        now = time.time()
        cutoff = now - max_age_s
        n_old = sum(1 for e in self._entries if e["ts"] < cutoff)
        if n_old < 5:  # Mindest-Schwelle gegen Flackern
            return
        self._entries = [e for e in self._entries if e["ts"] >= cutoff]
        self._rerender_all()
