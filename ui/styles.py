"""SimpleFT8 UI Styles — Zentrales Dark Theme.

Alle Farben, Fonts, Stylesheets an einem Ort.
Wird von control_panel.py, rx_panel.py, qso_panel.py etc. importiert.
"""

# ── Basis-Farben ──────────────────────────────────────────────────────────────
BG          = "#16192b"     # Haupt-Hintergrund
BG_DARK     = "#111111"     # Karten-Hintergrund
BG_HOVER    = "rgba(255,255,255,0.12)"
TEXT        = "#CCC"        # Standard-Text
TEXT_DIM    = "#666"        # Gedimmter Text
TEXT_BRIGHT = "#FFF"        # Heller Text
FONT        = "Menlo"       # Monospace-Font
SEP_COLOR   = "#333"        # Trennlinien
MIN_WIDTH   = 320           # Mindestbreite Control Panel

# ── LED / Indikator Farben ────────────────────────────────────────────────────
LED_GREEN   = "#00ee55"
LED_BLUE    = "#00aaff"
LED_RED     = "#FF5555"
LED_TEAL    = "#00CCFF"
LED_YELLOW  = "#FFCC00"

# ── Diversity Ratio Label Styles ──────────────────────────────────────────────
_DIV_BASE = "border-radius:3px;font-size:10px;font-family:Menlo;font-weight:bold;padding:1px 4px;"

DIV_PCT_OFF    = f"background:rgba(255,255,255,0.04);color:#666;border:1px solid #333;{_DIV_BASE}"
DIV_PCT_GREEN  = f"background:rgba(0,180,60,0.22);color:{LED_GREEN};border:1px solid rgba(0,200,80,0.6);{_DIV_BASE}"
DIV_PCT_RED    = f"background:rgba(200,50,50,0.22);color:{LED_RED};border:1px solid rgba(220,60,60,0.6);{_DIV_BASE}"
DIV_PCT_TEAL   = f"background:rgba(0,170,200,0.18);color:{LED_TEAL};border:1px solid rgba(0,180,210,0.5);{_DIV_BASE}"
DIV_PCT_YELLOW = f"background:rgba(200,170,0,0.18);color:{LED_YELLOW};border:1px solid rgba(210,180,0,0.5);{_DIV_BASE}"

# ── Button Basis-Style (Qt Stylesheet) ────────────────────────────────────────
BTN_BASE = """
    QPushButton {
        background-color: rgba(255,255,255,0.06);
        color: #BBB;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 4px;
        font-family: Menlo;
        font-size: 11px;
        font-weight: bold;
        padding: 3px 8px;
        min-height: 22px;
    }
    QPushButton:checked {
        background-color: #0066AA;
        color: white;
        border-color: #00AAFF;
    }
    QPushButton:hover {
        background-color: rgba(255,255,255,0.12);
    }
"""


def card_style(accent: str) -> str:
    """Einheitlicher Karten-Stil: dunkler Rahmen + farbige Top-Akzent-Linie."""
    return f"""
QFrame#card {{
    background-color: {BG_DARK};
    border: 1px solid #222222;
    border-top: 3px solid {accent};
    border-radius: 6px;
}}
""" + BTN_BASE


# ── Vordefinierte Karten-Styles ───────────────────────────────────────────────
CARD_BLUE   = card_style("#4477cc")
CARD_GREEN  = card_style("#2a8c4a")
CARD_TEAL   = card_style("#2a8c8c")
CARD_ORANGE = card_style("#8c5a2a")
CARD_DEFAULT = CARD_BLUE   # Legacy alias

# ── QMessageBox Dark Theme ────────────────────────────────────────────────────
MSGBOX_STYLE = """
    QMessageBox {
        background-color: #16192b;
        border: 1px solid #2a2d45;
        border-radius: 8px;
        padding: 20px;
    }
    QMessageBox QLabel {
        color: #CCC;
        font-family: Menlo;
        font-size: 12px;
        line-height: 1.4;
        margin-top: 4px;
    }
    QMessageBox QLabel#qt_msgboxex_icon_label {
        min-width: 0px; min-height: 0px;
        max-width: 0px; max-height: 0px;
    }
    QPushButton {
        background-color: rgba(255,255,255,0.08);
        color: #CCC;
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 6px;
        padding: 7px 20px;
        font-family: Menlo;
        font-size: 12px;
        margin: 4px;
    }
    QPushButton:hover {
        background-color: rgba(255,255,255,0.14);
        border-color: rgba(255,255,255,0.3);
    }
    QPushButton:pressed {
        background-color: rgba(0,100,200,0.3);
    }
    QPushButton:default {
        background-color: rgba(40,80,160,0.45);
        border-color: #3a5a9a;
        font-weight: bold;
    }
    QPushButton:default:hover {
        background-color: rgba(50,100,180,0.55);
    }
"""
