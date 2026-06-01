"""Bug 1 (01.06.2026) — HTML-Anchor-Format darf NICHT auf Folgezeilen bluten.

Mike-Field-Bug (Screenshots 31.05./01.06.): Nach einer klickbaren
"← Empf."-Einschub-Zeile (P164-Anchor, cyan + unterstrichen + href
"huntinsert:<call>") wurden auch die nachfolgenden eigenen
"→ Gesendet"-TX-Zeilen cyan + unterstrichen + klickbar dargestellt.

Root Cause: `_append_anchor_line` (ui/qso_panel.py) hängt via
QTextBrowser.append('<a ...>') HTML an. Das hinterlässt im log_view ein
currentCharFormat mit fontUnderline + anchorHref. Die normalen Methoden
`_append_colored`/`_append_two_color` setzen via setTextColor nur die
Vordergrundfarbe zurück → Folgezeilen erben Unterstrich + Klickbarkeit.

Diese Tests prüfen das echte QTextCharFormat pro Zeile (kein Mock):
- Anchor-Zeile MUSS Link bleiben (Regression-Schutz für P164).
- Folgezeilen (TX/RX/Info) dürfen KEIN isAnchor/anchorHref/fontUnderline tragen
  und behalten ihre eigene Farbe — auch nach _rerender_all().
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QTextCursor


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# --- Helper: charFormat jedes Zeichens der ersten Zeile, die `needle` enthält -

def _line_char_formats(panel, needle):
    """Liste der QTextCharFormat aller Zeichen im ersten Block, der `needle`
    enthält. Leere Liste, wenn keine Zeile passt."""
    doc = panel.log_view.document()
    block = doc.begin()
    while block.isValid():
        if needle in block.text():
            fmts = []
            pos = block.position()
            n = max(block.length() - 1, 0)  # ohne Paragraph-Separator
            for i in range(n):
                cur = QTextCursor(doc)
                cur.setPosition(pos + i + 1)  # charFormat = Zeichen davor
                fmts.append(cur.charFormat())
            return fmts
        block = block.next()
    return []


def _add_anchor_then_tx(panel):
    """P164-Anchor-Zeile (fremde Station ruft uns) + eigene TX-Zeile danach."""
    panel.add_rx("DA1MHH F5MYK IN97", tx_even=True,
                 slot_start_ts=0.0, insert_call="F5MYK")
    panel.add_tx("R3DII DA1MHH -20", tx_even=False, slot_start_ts=15.0)


# --- Tests ------------------------------------------------------------------

def test_anchor_line_stays_link(qapp):
    """Regression-Schutz: die Einschub-Zeile MUSS ein klickbarer Anchor sein."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    _add_anchor_then_tx(panel)
    anchor_fmts = _line_char_formats(panel, "F5MYK IN97")
    assert anchor_fmts, "Anchor-Zeile nicht gefunden"
    assert any(f.isAnchor() and f.anchorHref() == "huntinsert:F5MYK"
               for f in anchor_fmts), "Einschub-Zeile ist kein klickbarer Link mehr"


def test_tx_after_anchor_is_not_a_link(qapp):
    """Kern: die TX-Zeile nach dem Anchor darf KEIN Link/Unterstrich sein."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    _add_anchor_then_tx(panel)
    tx_fmts = _line_char_formats(panel, "Gesendet R3DII")
    assert tx_fmts, "TX-Zeile nicht gefunden"
    for f in tx_fmts:
        assert not f.isAnchor(), "TX-Zeile faelschlich Anchor (Bleed!)"
        assert not f.anchorHref(), f"TX-Zeile hat anchorHref (Bleed): {f.anchorHref()}"
        assert not f.fontUnderline(), "TX-Zeile faelschlich unterstrichen (Bleed!)"


def test_tx_after_anchor_keeps_own_color(qapp):
    """Die TX-Zeile behält ihre orange Farbe (#FFAA00), erbt NICHT das Anchor-Cyan."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    _add_anchor_then_tx(panel)
    tx_fmts = _line_char_formats(panel, "Gesendet R3DII")
    assert tx_fmts, "TX-Zeile nicht gefunden"
    names = {f.foreground().color().name().lower() for f in tx_fmts}
    assert "#7fe0ff" not in names, f"TX-Zeile erbte Anchor-Cyan: {names}"
    assert "#ffaa00" in names, f"TX-Zeile nicht in erwarteter Orange: {names}"


def test_no_bleed_after_rerender(qapp):
    """Auch nach _rerender_all() (30s-Trim / Spalten-Toggle) kein Bleed."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    _add_anchor_then_tx(panel)
    panel._rerender_all()
    tx_fmts = _line_char_formats(panel, "Gesendet R3DII")
    assert tx_fmts, "TX-Zeile nach Re-Render nicht gefunden"
    for f in tx_fmts:
        assert not f.isAnchor(), "Bleed nach Re-Render (isAnchor)"
        assert not f.fontUnderline(), "Bleed nach Re-Render (underline)"
    # Anchor bleibt nach Re-Render klickbar
    anchor_fmts = _line_char_formats(panel, "F5MYK IN97")
    assert any(f.isAnchor() for f in anchor_fmts), "Anchor nach Re-Render verloren"


def test_info_line_after_anchor_is_not_a_link(qapp):
    """Auch eine Info-Zeile (z.B. Timeout-Trennlinie) erbt kein Anchor-Format."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_rx("DA1MHH F5MYK IN97", tx_even=True,
                 slot_start_ts=0.0, insert_call="F5MYK")
    panel.add_timeout("R3DII")
    to_fmts = _line_char_formats(panel, "Timeout")
    assert to_fmts, "Timeout-Zeile nicht gefunden"
    for f in to_fmts:
        assert not f.isAnchor(), "Timeout-Zeile faelschlich Anchor (Bleed!)"
        assert not f.fontUnderline(), "Timeout-Zeile faelschlich unterstrichen"
