"""Intent-Klausel (v0.97.37): App-Start-Disclaimer mit MIT-Lizenz +
DA1MHH-Intent + Funklizenz-Verstöße als Haftungs-Ausschluss.

Mike-Vorbereitung für eventuelle GitHub-Veröffentlichung. Voller
V1→V2→R1→V3-Workflow trotz Trivial-Patch (CLAUDE.md-Pflicht).

R1-V4-pro: 3 Findings, alle übernommen — Höhe 380 → 400 (HiDPI-Puffer),
Wortlaut keine Änderung, KISS (in main.py patchen).

Source-Level-Tests (Inhalt verifiziert ohne Qt-Instanz).
"""

from __future__ import annotations

from pathlib import Path


def _read_main() -> str:
    return (Path(__file__).parent.parent / "main.py").read_text()


# ── T1 — Disclaimer enthält DA1MHH-Intent ───────────────────────────────


def test_t1_disclaimer_mentions_da1mhh():
    """AC2: Persönlicher Funkbetrieb DA1MHH ist im Disclaimer genannt."""
    src = _read_main()
    assert "DA1MHH" in src, "Intent-Klausel: DA1MHH-Erwähnung fehlt"
    assert "persönliches Bastel-Tool" in src, (
        "Intent-Klausel: persönlicher Bastel-Tool-Intent fehlt")


# ── T2 — MIT-Lizenz explizit genannt ───────────────────────────────────


def test_t2_disclaimer_mentions_mit_license():
    """AC3: MIT-Lizenz im Disclaimer genannt."""
    src = _read_main()
    assert "MIT-Lizenz" in src, "Intent-Klausel: MIT-Lizenz-Erwähnung fehlt"


# ── T3 — Funklizenz-Verstöße als Haftungs-Ausschluss ───────────────────


def test_t3_disclaimer_mentions_funklizenz():
    """AC4: Funklizenz-Verstöße als Haftungs-Ausschluss genannt."""
    src = _read_main()
    assert "Funklizenz-Verstöße" in src, (
        "Intent-Klausel: Funklizenz-Verstöße-Erwähnung fehlt")
    assert "auf eigene Gefahr" in src, (
        "Intent-Klausel: Eigengefahr-Disclaimer fehlt")


# ── T4 — Dialog-Höhe 400 (R1-F2 HiDPI-Puffer) ──────────────────────────


def test_t4_dialog_height_at_least_400():
    """AC5/R1-F2: Dialog `setFixedSize(540, 400)` damit Disclaimer-Text
    auch bei HiDPI nicht abgeschnitten wird."""
    src = _read_main()
    # Suche im _show_hardware_warning-Bereich
    idx_func = src.find("def _show_hardware_warning")
    assert idx_func > 0, "Funktion _show_hardware_warning fehlt"
    snippet = src[idx_func:idx_func + 2000]
    assert "setFixedSize(540, 400)" in snippet, (
        "Intent-Klausel R1-F2: Höhe muss 400 sein (HiDPI-Puffer)")


# ── Bonus — Alter Disclaimer-Text ist NICHT mehr drin ───────────────────


def test_bonus_old_disclaimer_removed():
    """Alter Wortlaut „private Machbarkeitsstudie" ist ersetzt."""
    src = _read_main()
    assert "private Machbarkeitsstudie" not in src, (
        "Intent-Klausel: alter Disclaimer-Text muss entfernt sein")
