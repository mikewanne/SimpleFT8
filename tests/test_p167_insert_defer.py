"""P167 (02.06.2026): Der P164-Einschub (vorgemerkte Station nach QSO-Ende
rufen) wird in den nächsten Event-Tick defert statt synchron gestartet.

Bug (Mike-Field, v0.98.51): Der Einschub-Hook läuft synchron mitten im
qso_state-Abschluss-Handler (qso_timeout/qso_confirmed.emit). start_qso setzte
TX_CALL, aber der Handler rief DANACH `_resume_cq_if_needed()` → `_set_state(
IDLE)` und überschrieb den frischen TX_CALL → Einschub-QSO hing nach 1 Anruf,
Auto-Hunt blieb pausiert.

Fix: `_p158_maybe_start_inserted_call` parkt den msg in `_deferred_insert_msg`
und scheduled `QTimer.singleShot(0, _execute_deferred_insert)`. Der Klick läuft
erst nachdem der State stabil IDLE ist. HALT (`_on_cancel`) nullt
`_deferred_insert_msg` → Race-Schutz.
"""

import pytest

from ui.mw_qso import QSOMixin


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _Stub(QSOMixin):
    """Minimal-Stub: nur die Attribute/Methoden, die der Einschub-Pfad nutzt."""

    def __init__(self):
        self._qso_pending_insert = None
        self._deferred_insert_msg = None
        self._p158_insertable = {}
        self.clicked = []

    def _on_station_clicked(self, msg, hard_stop=True):
        self.clicked.append((msg, hard_stop))


def test_insert_is_deferred_not_synchronous(qapp):
    from PySide6.QtWidgets import QApplication
    s = _Stub()
    s._qso_pending_insert = "MSG"
    s._p158_maybe_start_inserted_call()
    # Synchron darf NICHTS passieren — nur parken + schedulen.
    assert s.clicked == []
    assert s._deferred_insert_msg == "MSG"
    assert s._qso_pending_insert is None
    # Erst der Event-Tick führt den Einschub aus (sanft, hard_stop=False).
    QApplication.processEvents()
    assert s.clicked == [("MSG", False)]
    assert s._deferred_insert_msg is None


def test_no_pending_is_noop(qapp):
    from PySide6.QtWidgets import QApplication
    s = _Stub()
    s._p158_maybe_start_inserted_call()
    QApplication.processEvents()
    assert s.clicked == []
    assert s._deferred_insert_msg is None


def test_halt_cancels_deferred_insert(qapp):
    from PySide6.QtWidgets import QApplication
    s = _Stub()
    s._qso_pending_insert = "MSG"
    s._p158_maybe_start_inserted_call()
    # HALT im Fenster zwischen Defer und Event-Tick: _on_cancel nullt den Merker.
    s._deferred_insert_msg = None
    QApplication.processEvents()
    assert s.clicked == []   # Einschub verworfen, kein Geister-QSO


def test_execute_deferred_insert_consumes_msg(qapp):
    s = _Stub()
    s._deferred_insert_msg = "X"
    s._execute_deferred_insert()
    assert s.clicked == [("X", False)]
    assert s._deferred_insert_msg is None
    # Zweiter Aufruf ist no-op (Merker schon konsumiert).
    s._execute_deferred_insert()
    assert s.clicked == [("X", False)]
