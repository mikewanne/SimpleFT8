"""P91 — Dialog-Lifecycle-Crash-Fix (P90 Folge-Bug, v0.97.61)

Mike-Field-Test 20.05.2026 nach v0.97.60-Push:
SIGSEGV-Crash beim Klick auf „ohne Radio weiter" (P90 Field-Test F1).

Crash-Analyse: GUI-Thread `thread.join(2.0)` blockt → Worker terminiert
→ Stack-Unwind freigibt `dlg = self._connect_dialog` (strong ref)
→ wenn Worker letzte Ref hatte, Dialog-Destruktor laeuft im
Worker-Thread → Race mit Qt-Event-Dispatch im GUI-Thread → SIGSEGV.

DeepSeek-V4-pro Brainstorm-R1 Empfehlung Variante C (A+B kombiniert):
- Worker: `weakref.ref(self._connect_dialog)` statt strong ref
- GUI: `dialog_keepalive` + `deleteLater()` als Belt-and-suspenders

Tests T1-T8 (alle ohne Radio):
- T1: `weakref` Import in `ui/mw_radio.py`
- T2: `_connect_worker` nutzt `weakref.ref(self._connect_dialog)`
- T3: `_connect_worker` macht KEINE strong reference (`dlg = self._connect_dialog` raus)
- T4: `_connect_worker` `on_attempt` ruft `dlg_ref()` und None-checked
- T5: `_connect_worker` failed-Branch ruft `dlg_ref()` und None-checked
- T6: Cleanup-Block hat `dialog_keepalive`-Pattern
- T7: Cleanup-Block setzt `self._connect_dialog = None` VOR join
- T8: APP_VERSION-Bump auf 0.97.61+
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── T1 — weakref Import ────────────────────────────────────────────────


def test_t1_weakref_import():
    """`weakref` muss in `ui/mw_radio.py` importiert sein."""
    import ui.mw_radio as mw_radio
    assert hasattr(mw_radio, "weakref"), \
        "P91: `import weakref` muss am Modul-Top stehen"


# ── T2 — Worker nutzt weakref.ref ─────────────────────────────────────


def test_t2_worker_uses_weakref():
    """`_connect_worker` MUSS `weakref.ref(self._connect_dialog)` nutzen."""
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._connect_worker)
    assert "weakref.ref(self._connect_dialog)" in src, \
        "P91: Worker MUSS weakref.ref() nutzen statt strong ref"


# ── T3 — Worker hält KEINE strong ref ─────────────────────────────────


def test_t3_worker_no_strong_ref():
    """P91 Critical: Alte Zeile `dlg = self._connect_dialog` darf
    NICHT mehr existieren — sonst kommt Crash zurueck.
    """
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._connect_worker)
    # Negative-Check: alte strong-ref-Assignment ist raus
    assert "dlg = self._connect_dialog" not in src, \
        "P91: Strong-ref `dlg = self._connect_dialog` MUSS entfernt sein!"


# ── T4 — on_attempt ruft dlg_ref() ────────────────────────────────────


def test_t4_on_attempt_dereferences_weakref():
    """`on_attempt` MUSS `dlg = dlg_ref()` aufrufen und None-checken."""
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._connect_worker)
    # on_attempt-Closure
    assert "dlg = dlg_ref()" in src, \
        "P91: weakref muss in on_attempt via dlg_ref() dereferenziert werden"
    # Plus None-Check + try/except RuntimeError
    assert "if dlg is not None" in src
    assert "RuntimeError" in src


# ── T5 — failed_signal-Branch nutzt dlg_ref() ─────────────────────────


def test_t5_failed_branch_dereferences_weakref():
    """failed_signal-Pfad nach `auto_connect`-Return muss auch
    `dlg_ref()` nutzen, nicht alte strong ref.
    """
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._connect_worker)
    # Mindestens 2x `dlg = dlg_ref()` (on_attempt + failed-Branch)
    assert src.count("dlg = dlg_ref()") >= 2, \
        "P91: failed-Branch MUSS auch dlg_ref() aufrufen (statt alte `dlg`-Closure)"


# ── T6 — Cleanup-Block: dialog_keepalive-Pattern ─────────────────────


def test_t6_cleanup_dialog_keepalive():
    """P91 Cleanup-Block muss `dialog_keepalive` halten + `deleteLater()`."""
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._start_radio)
    assert "dialog_keepalive = self._connect_dialog" in src, \
        "P91: Keepalive-Snapshot muss existieren"
    assert "dialog_keepalive.deleteLater()" in src, \
        "P91: Qt-Cleanup via deleteLater() MUSS gerufen werden"


# ── T7 — Cleanup-Reihenfolge: None-Set VOR join ───────────────────────


def test_t7_cleanup_order_none_before_join():
    """P91 critical: `self._connect_dialog = None` MUSS vor `thread.join`
    passieren — sonst hat Worker noch strong ref wenn er terminiert.
    """
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._start_radio)

    pos_keepalive = src.find("dialog_keepalive = self._connect_dialog")
    pos_none = src.find(
        "self._connect_dialog = None",
        pos_keepalive,  # nach keepalive, nicht das Final-Statement
    )
    pos_join = src.find(".join(timeout=2.0)")
    pos_delete_later = src.find("dialog_keepalive.deleteLater()")

    assert pos_keepalive > 0
    assert pos_none > pos_keepalive, \
        "P91: None-Set muss NACH keepalive-Snapshot kommen"
    assert pos_none < pos_join, \
        "P91: None-Set MUSS vor thread.join (Worker-Termination) passieren"
    assert pos_delete_later > pos_join, \
        "P91: deleteLater() MUSS nach thread.join (Worker beendet) kommen"


# ── T8 — APP_VERSION-Bump ─────────────────────────────────────────────


def test_t8_app_version_bump():
    """APP_VERSION muss >= 0.97.61 sein (P91)."""
    import main
    assert main.APP_VERSION >= "0.97.61", \
        f"APP_VERSION ist {main.APP_VERSION}, erwartet >= 0.97.61"
