"""OPT-61: QSOStateMachine.is_busy-Property (KISS — ersetzt 7× dasselbe
4-State-Tupel `(IDLE, TIMEOUT, CQ_CALLING, CQ_WAIT)` an den UI-Call-Sites).

is_busy == True  ⟺  eine QSO-Austausch-Sequenz mit einer Gegenstation laeuft.
„Nicht busy"      =  IDLE / TIMEOUT / CQ_CALLING / CQ_WAIT (kein zu schuetzendes QSO).

Mutationsbeweis: jeder der 12 Enum-States wird explizit eingeordnet; ein
Vollstaendigkeits-Test schlaegt an, sobald jemand das Set veraendert oder
einen neuen State hinzufuegt ohne ihn bewusst einzuordnen.
"""
import pytest

from core.qso_state import QSOState, QSOStateMachine


# Die EXAKTE Erwartung pro State (verhaltensgleich zum alten Tupel).
NOT_BUSY = {
    QSOState.IDLE,
    QSOState.TIMEOUT,
    QSOState.CQ_CALLING,
    QSOState.CQ_WAIT,
}
BUSY = {
    QSOState.TX_CALL,
    QSOState.WAIT_REPORT,
    QSOState.TX_REPORT,
    QSOState.WAIT_RR73,
    QSOState.TX_RR73,
    QSOState.WAIT_73,
    QSOState.TX_73_COURTESY,
    QSOState.LOGGING,   # legacy/ungenutzt — faellt korrekt unter „busy" (war nie im not-in-Set)
}


def _sm():
    return QSOStateMachine("DA1MHH", "JO31")


def test_default_state_is_not_busy():
    """Frische State-Machine ist IDLE → nicht busy."""
    assert _sm().is_busy is False


@pytest.mark.parametrize("state", sorted(NOT_BUSY, key=lambda s: s.name))
def test_not_busy_states(state):
    sm = _sm()
    sm.state = state
    assert sm.is_busy is False, f"{state.name} sollte NICHT busy sein"


@pytest.mark.parametrize("state", sorted(BUSY, key=lambda s: s.name))
def test_busy_states(state):
    sm = _sm()
    sm.state = state
    assert sm.is_busy is True, f"{state.name} sollte busy sein"


def test_all_enum_states_classified():
    """Vollstaendigkeit: NOT_BUSY ∪ BUSY deckt JEDEN Enum-State genau einmal ab.

    Schlaegt an, wenn ein neuer State hinzukommt (zwingt zur bewussten
    Einordnung) oder wenn die Mengen sich ueberschneiden.
    """
    all_states = set(QSOState)
    assert NOT_BUSY | BUSY == all_states
    assert NOT_BUSY & BUSY == set()


def test_is_busy_is_pure_complement():
    """is_busy ist exakt das Komplement von NOT_BUSY ueber ALLE States
    (Mutationsbeweis gegen ein verschobenes Set in der Property)."""
    sm = _sm()
    for state in QSOState:
        sm.state = state
        assert sm.is_busy is (state not in NOT_BUSY), state.name
