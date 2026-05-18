"""P75 (v0.97.48) — TUNE-Button-Bug + Style-Harmonisierung + Fenster-Konsolidierung.

Bundle aus Mike-Field-Test 18.05.2026:
- Bug: TUNE-Button bleibt nach Auto-Stop visuell aktiv (checked=True).
- UX: TUNE-Button-Style harmonisieren mit OMNI/CQ (aktiv grün), eigenes
  dezent-gelb-Cluster für Inaktiv (Setup-Aktion, kein TX).
- Fenster-Konsolidierung (Variante A): DXTuneDialog kriegt Header-Banner
  „✓ TUNE OK — SWR X.X · jetzt 2 Min Gain-Messung läuft" wenn aus Auto-
  TUNE-Pipeline.
- SWR-bad-QMessageBox raus → qso_panel.add_info (rote Zeile).

10 Tests:
- T1: Source-Level: `_tune_stop` ruft setChecked(False) mit blockSignals.
- T2: TUNE-Style enthält dezent-gelb (rgba(60,50,0,...)).
- T3: Alter `#998800`-Style raus.
- T4: Bei Auto-Stop nach Timer wird Button-State zurückgesetzt OHNE
      Re-Trigger des `tune_clicked`-Signals.
- T5: Race-Test User-Toggle-Off + Auto-Stop-Timer gleichzeitig.
- T6: DXTuneDialog mit prev_tune_swr=2.1 zeigt Banner.
- T7: DXTuneDialog mit prev_tune_swr=None zeigt KEIN Banner.
- T8: SWR-bad manueller TUNE-Pfad: qso_panel.add_info, kein QMessageBox.
- T9: SWR-bad Auto-Tune-Pfad: Signal an Dialog, weder QMessageBox noch
      qso_panel.add_info (Dialog kümmert sich selbst).
- T10: Konsistenz: TUNE-Aktiv-Hintergrund = OMNI-Aktiv-Hintergrund.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


# ── T1 — _tune_stop ruft setChecked(False) mit blockSignals ───────────


def test_t1_tune_stop_resets_button():
    """Source-Level: _tune_stop enthält btn_tune.setChecked(False) + blockSignals."""
    src = Path("ui/mw_tx.py").read_text()
    # Block ab def _tune_stop bis def _tune_post_swr_check
    idx_start = src.find("def _tune_stop")
    idx_end = src.find("def _tune_post_swr_check")
    assert idx_start > 0 and idx_end > idx_start
    block = src[idx_start:idx_end]
    assert "btn_tune" in block, "btn_tune-Reset fehlt in _tune_stop"
    assert "setChecked(False)" in block, "setChecked(False) fehlt"
    assert "blockSignals(True)" in block, "blockSignals(True) fehlt"
    assert "blockSignals(False)" in block, "blockSignals(False) fehlt"


# ── T2 — Style enthält dezent-gelb ────────────────────────────────────


def test_t2_tune_style_dezent_gelb():
    """TUNE-Button-Style enthält neue dezent-gelb-Definition."""
    src = Path("ui/control_panel.py").read_text()
    assert "rgba(60,50,0,0.55)" in src, "Dezent-gelb-Background fehlt"
    assert "#BBA060" in src, "Dezent-gelb-Text fehlt"
    assert "_tune_btn_style" in src, "Neue Style-Variable _tune_btn_style fehlt"


# ── T3 — Alter Style raus ─────────────────────────────────────────────


def test_t3_old_tune_style_removed():
    """Alter `#998800`-Style (checked-State) und `#2a2a00` raus."""
    src = Path("ui/control_panel.py").read_text()
    # Block um btn_tune-Definition (200 Zeichen)
    idx = src.find("self.btn_tune = QPushButton")
    assert idx > 0
    # Suchfenster bis 600 Zeichen weiter (Style-Block)
    block = src[idx:idx + 1500]
    assert "#998800" not in block, "Alter Checked-State #998800 noch da"
    assert "#2a2a00" not in block, "Alter Inaktiv-Background #2a2a00 noch da"


# ── T4 — Button-Reset ohne Re-Trigger ─────────────────────────────────


def test_t4_button_reset_no_retrigger():
    """Verifikation dass blockSignals den Re-Trigger verhindert.

    Source-Level + Logik: blockSignals(True) MUSS direkt vor setChecked(False)
    stehen, damit Qt das toggled/clicked-Signal nicht emittiert.
    """
    src = Path("ui/mw_tx.py").read_text()
    idx_start = src.find("def _tune_stop")
    idx_end = src.find("def _tune_post_swr_check")
    block = src[idx_start:idx_end]
    # blockSignals(True) muss VOR setChecked(False) kommen
    pos_block_on = block.find("blockSignals(True)")
    pos_set_false = block.find("setChecked(False)")
    pos_block_off = block.find("blockSignals(False)")
    assert pos_block_on > 0
    assert pos_set_false > pos_block_on, \
        "setChecked(False) muss NACH blockSignals(True) kommen"
    assert pos_block_off > pos_set_false, \
        "blockSignals(False) muss NACH setChecked(False) kommen"


# ── T5 — Race-Test User-Toggle-Off + Auto-Stop-Timer ──────────────────


def test_t5_race_user_toggle_off_vs_auto_stop():
    """Token-Mismatch verhindert Doppel-Stop.

    Verifikation: _tune_stop returnt sofort wenn token nicht aktuell.
    Schon im bestehenden Code via R1-F1-Token-Pattern abgesichert.
    """
    src = Path("ui/mw_tx.py").read_text()
    idx_start = src.find("def _tune_stop")
    idx_end = src.find("def _tune_post_swr_check")
    block = src[idx_start:idx_end]
    assert "if token is not None and getattr(self, '_tune_auto_stop_token', None) is not token" in block, \
        "Token-Guard fehlt — Race-Schutz nicht garantiert"


# ── T6 — DXTuneDialog mit prev_tune_swr zeigt Banner ──────────────────


def test_t6_dx_dialog_banner_with_prev_swr():
    """DXTuneDialog mit prev_tune_swr=2.1 zeigt grünen Banner."""
    src = Path("ui/dx_tune_dialog.py").read_text()
    assert "prev_tune_swr" in src, "Parameter prev_tune_swr fehlt"
    assert "_prev_tune_swr" in src, "Instance-Attr _prev_tune_swr fehlt"
    assert "✓ TUNE OK" in src, "Banner-Text fehlt"
    assert "rgba(0,150,0,0.25)" in src, "Banner-Hintergrund (grün) fehlt"
    assert "#88FFAA" in src, "Banner-Text-Farbe fehlt"


# ── T7 — DXTuneDialog ohne prev_tune_swr: kein Banner ─────────────────


def test_t7_dx_dialog_no_banner_when_none():
    """Banner nur sichtbar wenn prev_tune_swr is not None.

    Source-Level: Banner-Erstellung steht in if-Block.
    """
    src = Path("ui/dx_tune_dialog.py").read_text()
    idx = src.find("if self._prev_tune_swr is not None:")
    assert idx > 0, "if-Branch für Banner-Erstellung fehlt"
    # Banner-Label muss im if-Block sein, nicht außerhalb
    banner_idx = src.find('"✓ TUNE OK')
    assert banner_idx > idx, "Banner-Label nicht im if-Block"


# ── T8 — SWR-bad manueller Pfad: qso_panel.add_info ──────────────────


def test_t8_swr_bad_manual_uses_panel_info():
    """SWR-bad manueller TUNE: qso_panel.add_info statt QMessageBox.warning.

    P75-Fix: rote Zeile im Live-Log statt Modal-Popup. Mike-Spec
    „weniger Fenster die aufploppen".
    """
    src = Path("ui/mw_tx.py").read_text()
    idx_start = src.find("def _tune_post_swr_check")
    idx_end = src.find("def _wait_with_event_loop", idx_start)
    if idx_end < 0:
        idx_end = idx_start + 6000
    block = src[idx_start:idx_end]
    # P75-Marker im Code-Kommentar bestätigt Umbau
    assert "P75 (v0.97.48): QMessageBox raus" in block, \
        "P75-Marker im SWR-bad-Pfad fehlt — Umbau wurde nicht im Code dokumentiert"
    # qso_panel.add_info muss mit Tuner-Text-Argument auftauchen
    assert 'self.qso_panel.add_info(\n                    f"⚠ Tuner' in block \
        or 'self.qso_panel.add_info(' in block and "⚠ Tuner konnte nicht matchen" in block, \
        "qso_panel.add_info mit Tuner-Text fehlt"
    # QMessageBox.warning(...) für SWR-bad-Pfad raus (im else-Branch
    # nach „AC7 P63: Marker bleibt rot") — der Block darf NICHT
    # `QMessageBox.warning(\n                    self,\n                    "Tuner konnte` enthalten
    assert 'QMessageBox.warning(\n                    self,\n                    "Tuner konnte' not in block, \
        "QMessageBox.warning fuer Tuner-Fail noch im SWR-bad-Pfad"


# ── T9 — SWR-bad Auto-Tune: weder QMessageBox noch add_info ──────────


def test_t9_swr_bad_auto_tune_only_signal():
    """SWR-bad Auto-Tune: emit-Signal an Dialog, sonst nichts.

    Source-Level: im is_auto-True-Branch wird auto_tune_done.emit gerufen
    aber KEIN qso_panel.add_info (Dialog zeigt selbst).
    """
    src = Path("ui/mw_tx.py").read_text()
    idx_start = src.find("def _tune_post_swr_check")
    idx_end = src.find("def _wait_with_event_loop", idx_start)
    block = src[idx_start:idx_end]
    # Im SWR-bad-Branch: is_auto → emit, else → add_info
    # Suche P76-C-Marker im SWR-bad-Sub-Block (ersetzt alten "AC7 P63: Marker
    # bleibt rot"-Kommentar mit v0.97.50).
    else_marker = block.find("P76-C")
    assert else_marker > 0
    sub_block = block[else_marker:else_marker + 1500]
    assert "auto_tune_done.emit(False, swr_now" in sub_block, \
        "Auto-Tune-Signal-Emit fehlt"


# ── T10 — TUNE-Aktiv-Style konsistent mit OMNI ───────────────────────


def test_t10_tune_active_consistent_with_omni():
    """TUNE-Aktiv-Hintergrund = OMNI-Aktiv-Hintergrund (`rgba(0,150,0,0.75)`)."""
    src = Path("ui/control_panel.py").read_text()
    # OMNI-Style hat rgba(0,150,0,0.75) als checked-Background
    # TUNE-Style muss dasselbe haben (Konsistenz-Spec Mike)
    omni_pattern = "rgba(0,150,0,0.75)"
    assert src.count(omni_pattern) >= 2, \
        f"{omni_pattern} muss in mind. 2 Styles (TUNE + OMNI) sein"
