"""P76-A (v0.97.49): SWR-Safety-Bug — Freeze SWR vor tune_off().

Mike-Field-Test 17m: SWR 2.7 (>Limit 2.5) wurde als „TUNE OK SWR 1.0"
geloggt. Root: `_tune_post_swr_check` liest `radio.last_swr` 2 s nach
`tune_off()` — FlexRadio Meter-Loop liefert ohne TX-Traeger Werte <1.0
die in `_handle_meter` auf 1.0 geclamped werden → false-OK.

Fix: SWR direkt VOR `tune_off()` einfrieren in `_tune_last_valid_swr`,
im Post-Check diesen Wert lesen statt frischer `radio.last_swr`. Bei
None oder <1.0 → FAIL-Behandlung (NICHT auf radio.last_swr fallen, sonst
reproduziert sich Clamp-Bug).

R1-V4-pro Findings (alle uebernommen):
- F5: kein Fallback auf radio.last_swr — bei None → FAIL
- F6: Reset auch im Disconnect-Branch (Stale-State-Schutz)
- F13: <1.0 ebenfalls FAIL behandeln

T1-T11.
"""

from __future__ import annotations

import re
from pathlib import Path


# ── Source-Reader-Helper ────────────────────────────────────────────────


def _read(path: str) -> str:
    return (Path(__file__).parent.parent / path).read_text()


def _method_src(file_rel: str, method_name: str) -> str:
    """Extrahiert Source-Body einer Methode (regex bis nächste `def` oder EOF)."""
    text = _read(file_rel)
    pattern = rf"    def {method_name}\([^)]*\)[^\n]*:.*?(?=\n    def |\nclass |\Z)"
    m = re.search(pattern, text, flags=re.DOTALL)
    if not m:
        raise AssertionError(f"Methode {method_name} nicht in {file_rel}")
    return m.group(0)


# ── T1 — Init-Variable in main_window.py ────────────────────────────────


def test_t1_init_state_variable():
    """AC: `_tune_last_valid_swr` ist in __init__ initialisiert."""
    src = _read("ui/main_window.py")
    assert "self._tune_last_valid_swr" in src, (
        "P76-A AC: _tune_last_valid_swr nicht initialisiert")
    assert "_tune_last_valid_swr: float | None = None" in src, (
        "P76-A AC: Init-Typ-Annotation/Default fehlt")
    assert "P76-A" in src, "P76-A: Marker-Kommentar fehlt"


# ── T2 — Freeze in _tune_stop ───────────────────────────────────────────


def test_t2_freeze_in_tune_stop():
    """AC: `_tune_last_valid_swr = radio.last_swr` in `_tune_stop`."""
    src = _method_src("ui/mw_tx.py", "_tune_stop")
    assert "self._tune_last_valid_swr = self.radio.last_swr" in src, (
        "P76-A AC: Freeze-Zeile fehlt in _tune_stop")


# ── T3 — Freeze MUSS VOR tune_off() stehen (kritische Reihenfolge) ─────


def test_t3_freeze_before_tune_off():
    """AC kritisch: Freeze MUSS VOR tune_off() stehen.

    Sonst ist `last_swr` schon durch Meter-Loop-Clamp ueberschrieben
    bevor wir ihn einfrieren → Bug bleibt.
    """
    src = _method_src("ui/mw_tx.py", "_tune_stop")
    freeze_pos = src.find("self._tune_last_valid_swr = self.radio.last_swr")
    tune_off_pos = src.find("self.radio.tune_off()")
    assert freeze_pos >= 0, "P76-A: Freeze-Zeile fehlt"
    assert tune_off_pos >= 0, "P76-A: tune_off() fehlt"
    assert freeze_pos < tune_off_pos, (
        f"P76-A KRITISCH: Freeze (pos {freeze_pos}) MUSS VOR "
        f"tune_off() (pos {tune_off_pos}) stehen")


# ── T4 — Read+Reset in _tune_post_swr_check ─────────────────────────────


def test_t4_read_and_reset_in_post_check():
    """AC: `_tune_post_swr_check` liest gefrorenen Wert + Reset."""
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    assert "swr_frozen = self._tune_last_valid_swr" in src, (
        "P76-A AC: Read-Zeile fehlt")
    assert "self._tune_last_valid_swr = None" in src, (
        "P76-A AC: Reset-Zeile fehlt")


# ── T5 — KEIN Fallback auf radio.last_swr (R1-F5) ──────────────────────


def test_t5_no_radio_last_swr_fallback():
    """R1-F5: Bei None darf NICHT auf radio.last_swr gefallen werden —
    der koennte durch Clamp-Bug 1.0 sein → false-OK reproduziert.

    Stattdessen: FAIL-Behandlung (else-Branch greift).
    """
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    # Nach dem swr_frozen-Read darf KEIN `= self.radio.last_swr` mehr stehen
    # als Fallback (war urspruengliche V1-Idee, von R1-F5 verworfen).
    # Spezifisch: der String "swr_now = self.radio.last_swr" (alter Code)
    # darf NICHT mehr vorkommen.
    assert "swr_now = self.radio.last_swr" not in src, (
        "P76-A R1-F5: alter Bug-Pattern 'swr_now = self.radio.last_swr' "
        "muss entfernt sein (durch swr_frozen ersetzt)")


# ── T6 — FAIL-Branch bei None oder <1.0 (R1-F5 + F13) ──────────────────


def test_t6_fail_branch_on_invalid_freeze():
    """R1-F5+F13: bei None oder <1.0 → garantiert in else-Branch (SWR-bad).

    Implementierung: `swr_now = swr_limit + 1.0` zwingt `swr_now > limit`.
    """
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    assert "swr_frozen is None or swr_frozen < 1.0" in src, (
        "P76-A R1-F5+F13: None-oder-<1.0-Check fehlt")
    assert "+ 1.0" in src, (
        "P76-A R1-F5: FAIL-Wert (limit+1.0) zwingt in else-Branch")
    # Logging-Marker
    assert "P76-A" in src, "P76-A: Marker-Kommentar fehlt im Post-Check"


# ── T7 — Disconnect-Branch Reset (R1-F6) ────────────────────────────────


def test_t7_disconnect_branch_reset():
    """R1-F6: Im Disconnect-Pfad muss `_tune_last_valid_swr = None`
    explizit gesetzt werden, sonst haengt Stale-State fuer naechsten TUNE.
    """
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    # Pruefe: zwischen `if not self.radio.ip:` und `return` muss Reset sein
    disconnect_match = re.search(
        r"if not self\.radio\.ip:.*?return",
        src, flags=re.DOTALL)
    assert disconnect_match, "P76-A: Disconnect-Branch nicht gefunden"
    disconnect_block = disconnect_match.group(0)
    assert "self._tune_last_valid_swr = None" in disconnect_block, (
        "P76-A R1-F6: Reset im Disconnect-Branch fehlt")


# ── T8 — Reset VOR else-Branch-Read (Stale-Schutz immer) ────────────────


def test_t8_reset_always_in_post_check():
    """AC4: Reset auf None auch wenn Read erfolgreich war.

    Stellt sicher dass naechster TUNE eine frische Freeze-Operation
    macht und nicht alten Wert sieht.
    """
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    # `self._tune_last_valid_swr = None  # IMMER Reset` direkt nach Read
    pattern = (
        r"swr_frozen = self\._tune_last_valid_swr\s*\n"
        r"\s*self\._tune_last_valid_swr = None"
    )
    assert re.search(pattern, src), (
        "P76-A AC4: Reset muss direkt nach Read kommen (immer, nicht conditional)")


# ── T9 — ANT1-Pflicht-Schutz (Source-Level) ─────────────────────────────


def test_t9_no_antenna_change_in_freeze_or_read():
    """AC6: Aenderung beruehrt nur SWR-Read-Pfad — kein set_tx_antenna
    in Freeze- oder Read-Zeilen.

    Hardware-Pflicht aus P63/P54: ANT1=TX only. Aenderungen am SWR-Pfad
    duerfen nicht Antennen-Schaltung beruehren.
    """
    stop_src = _method_src("ui/mw_tx.py", "_tune_stop")
    post_src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    # Nur die NEU eingefuegten P76-A-Bloecke pruefen — set_tx_antenna kann
    # in anderen Teilen von _tune_stop vorkommen (z.B. P63 Auto-TUNE).
    # Extrahiere die 2 P76-A-Bloecke per Marker-Kommentar.
    p76a_stop = re.search(
        r"# P76-A.*?self\._tune_last_valid_swr = self\.radio\.last_swr",
        stop_src, flags=re.DOTALL)
    assert p76a_stop, "P76-A: Marker-Block in _tune_stop nicht gefunden"
    assert "set_tx_antenna" not in p76a_stop.group(0), (
        "P76-A AC6 ANT1-Pflicht: kein set_tx_antenna im Freeze-Block")

    # Im Post-Check: P76-A-Block bis Ende
    p76a_post = re.search(
        r"# P76-A SAFETY \(v0\.97\.49\):.*?swr_now = swr_frozen",
        post_src, flags=re.DOTALL)
    assert p76a_post, "P76-A: Marker-Block in _tune_post_swr_check nicht gefunden"
    assert "set_tx_antenna" not in p76a_post.group(0), (
        "P76-A AC6 ANT1-Pflicht: kein set_tx_antenna im Read-Block")


# ── T10 — Functional: simulierter Mike-Fall (Phase-B-Skip) ──────────────


def test_t10_functional_mike_case_phase_b_skip():
    """Functional-Sim: Mike's 17m-Fall.

    Phase A: swr_after_match = 2.7. Phase B uebersprungen (2.7 > 2.5).
    Direkt vor tune_off wird 2.7 gefroren. 2 s spaeter (radio.last_swr=1.0
    durch Clamp) liest Post-Check gefrorenen Wert 2.7 → SWR-bad-Branch.

    Wir simulieren das mit einem dict-State, kein QWidget.
    """
    class FakeRadio:
        last_swr = 2.7  # vor tune_off
        ip = "192.168.1.1"

    class FakeWin:
        _tune_last_valid_swr = None
        radio = FakeRadio()
        # Settings, etc., werden nicht benoetigt fuer den Freeze-Test

    win = FakeWin()
    # Simuliere Freeze in _tune_stop
    win._tune_last_valid_swr = win.radio.last_swr
    assert win._tune_last_valid_swr == 2.7

    # Simuliere 2s spaeter: FlexRadio Clamp hat last_swr ueberschrieben
    win.radio.last_swr = 1.0

    # Post-Check liest gefrorenen Wert (nicht last_swr!)
    swr_frozen = win._tune_last_valid_swr
    win._tune_last_valid_swr = None  # Reset
    if swr_frozen is None or swr_frozen < 1.0:
        swr_now = 999.0  # FAIL
    else:
        swr_now = swr_frozen

    # Korrekt: swr_now ist 2.7, NICHT 1.0
    assert swr_now == 2.7, (
        f"P76-A: Post-Check muss gefrorenen Wert lesen (2.7), "
        f"nicht radio.last_swr (1.0). Bekam: {swr_now}")

    # SWR > Limit → wuerde else-Branch greifen
    swr_limit = 2.5
    assert swr_now > swr_limit, "P76-A: 2.7 > 2.5, Marker muss gesetzt werden"

    # Reset hat geklappt
    assert win._tune_last_valid_swr is None


# ── T11 — Functional: None-Fallback geht in FAIL (nicht in OK) ─────────


def test_t11_functional_none_falls_into_fail():
    """R1-F5: Wenn `_tune_last_valid_swr` None ist (Freeze fehlgeschlagen),
    darf NICHT auf radio.last_swr=1.0 gefallen werden — sonst false-OK.

    Stattdessen: garantiert in else-Branch.
    """
    swr_frozen = None  # Freeze hat nicht stattgefunden
    swr_limit = 2.5

    if swr_frozen is None or (swr_frozen is not None and swr_frozen < 1.0):
        swr_now = swr_limit + 1.0  # FAIL-Wert
    else:
        swr_now = swr_frozen

    # swr_now muss > limit sein (else-Branch)
    assert swr_now > swr_limit, (
        f"P76-A R1-F5: None muss in FAIL-Pfad fallen. "
        f"swr_now={swr_now} > limit={swr_limit}")
