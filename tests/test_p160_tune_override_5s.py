"""P160 (28.05.2026) — 5s zur Rechtsklick-TUNE-Override-Auswahl ergänzen.

Mike-Wunsch: Schnell-TUNE für empfindliche Lasten (20-W-Dummyload schnell
zerschossen) — kurz Träger raus um zu sehen wie sich der SWR gerade verhält,
ohne neu einzumessen und ohne ins Settings-Menü zu gehen. Der Rechtsklick-
Override bot bisher nur 10/15/20s.

5s ist sicher + konsistent: kürzer als bestehende Werte (weniger TX-Zeit),
5W/ANT1 wie alle TUNE, und im Linksklick-Pfad (_on_tune_clicked, Whitelist
5/10/15) bereits erlaubt. DeepSeek-R1 GO (Option a): kein neues Risiko, keine
Sonderbehandlung — der 5s-Override durchläuft denselben Post-Check wie der
bestehende Linksklick-5s.

Änderung (3 Zeilen):
- control_panel: Menü-Schleife (10,15,20) → (5,10,15,20)
- mw_tx._on_tune_override: Whitelist (10,15,20) → (5,10,15,20)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MW_TX_SRC = (REPO / "ui" / "mw_tx.py").read_text()
CP_SRC = (REPO / "ui" / "control_panel.py").read_text()


def _override_body() -> str:
    m = re.search(r"def _on_tune_override\(self, duration_s.*?(?=\n    def )",
                  MW_TX_SRC, re.S)
    assert m is not None, "_on_tune_override nicht gefunden"
    return m.group(0)


def test_t1_override_whitelist_accepts_5():
    """T1: _on_tune_override-Whitelist enthält 5 (5/10/15/20)."""
    body = _override_body()
    assert "duration_s not in (5, 10, 15, 20)" in body, (
        "P160: Override-Whitelist muss 5 enthalten → (5, 10, 15, 20)")


def test_t2_override_rejects_outside_whitelist():
    """T2: Werte außerhalb (5,10,15,20) werden weiter abgewiesen (Defensive
    bleibt — kein beliebiger Wert durchschlüpft)."""
    body = _override_body()
    # Es gibt genau EINEN Whitelist-Guard mit return danach
    assert "not in (5, 10, 15, 20)" in body
    # 25 wäre z.B. weiterhin draußen — der Guard ist eine geschlossene Menge
    assert "(5, 10, 15, 20)" in body and "30" not in _override_body().split("not in")[1][:20]


def test_t3_menu_offers_5s():
    """T3: Das Rechtsklick-Kontextmenü bietet 5s an (Schleife 5/10/15/20)."""
    assert "for sec in (5, 10, 15, 20):" in CP_SRC, (
        "P160: TUNE-Override-Menü muss 5s anbieten → (5, 10, 15, 20)")


def test_t4_menu_docstring_mentions_5s():
    """T4: Menü-Docstring nennt 5s (Doku-Konsistenz)."""
    assert "Zeigt Menü mit 5s / 10s / 15s / 20s" in CP_SRC, (
        "P160: Menü-Docstring muss 5s/10s/15s/20s nennen")
    assert "P160" in CP_SRC, "P160-Marker fehlt"


def test_t5_left_click_path_unchanged():
    """T5: Linksklick-Pfad (_on_tune_clicked) bleibt bei seiner Whitelist
    (5,10,15) — P160 ändert NUR den Override, nicht den Setting-Pfad."""
    m = re.search(r"def _on_tune_clicked\(self, on.*?(?=\n    def )",
                  MW_TX_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "duration_s not in (5, 10, 15)" in body, (
        "P160: Linksklick-Pfad (Setting-basiert) bleibt unverändert 5/10/15")
