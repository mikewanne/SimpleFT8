"""Regression-Test fuer Live-Locator-Feeding in die DB.

Der Bug v0.67-v0.69: `is_grid` ist eine @property (nicht callable). Code
in mw_cycle._feed_locator_db rief `m.is_grid()` mit Klammern → TypeError
→ wurde silent gefangen → DB bekam aus Live-Decodes nichts. Locator-DB
wuchs nur durch ADIF-Bulk-Import.
"""
from unittest.mock import MagicMock

from core.message import parse_ft8_message


class _FakeOwner:
    """Minimaler self-Stand-In fuer _feed_locator_db (nur locator_db noetig)."""
    def __init__(self):
        self.locator_db = MagicMock()


def _feed(owner, messages):
    """Importiere und rufe die echte _feed_locator_db-Methode."""
    from ui.mw_cycle import CycleMixin
    CycleMixin._feed_locator_db(owner, messages)


def test_cq_message_writes_locator_to_db():
    """'CQ R9CA LO97' → db.set('R9CA', 'LO97', 'cq')."""
    owner = _FakeOwner()
    msg = parse_ft8_message("CQ R9CA LO97")
    _feed(owner, [msg])
    owner.locator_db.set.assert_called_once_with("R9CA", "LO97", "cq")


def test_directed_reply_with_grid_writes_locator():
    """'RA4ALY DL6YJB JO31' → caller=DL6YJB → db.set('DL6YJB', 'JO31', 'cq').

    Diese Antwort-Form wird haeufiger empfangen als reine CQ-Calls und war
    durch den is_grid()-Bug komplett verloren.
    """
    owner = _FakeOwner()
    msg = parse_ft8_message("RA4ALY DL6YJB JO31")
    _feed(owner, [msg])
    owner.locator_db.set.assert_called_once_with("DL6YJB", "JO31", "cq")


def test_report_message_does_not_write():
    """'DL6YJB DL3ABC -10' (Report, kein Locator) → kein db.set."""
    owner = _FakeOwner()
    msg = parse_ft8_message("DL6YJB DL3ABC -10")
    _feed(owner, [msg])
    owner.locator_db.set.assert_not_called()


def test_rr73_does_not_write():
    """'DL6YJB DL3ABC RR73' → kein db.set."""
    owner = _FakeOwner()
    msg = parse_ft8_message("DL6YJB DL3ABC RR73")
    _feed(owner, [msg])
    owner.locator_db.set.assert_not_called()


def test_no_db_no_crash():
    """locator_db=None → kein Crash."""
    class _NoDB:
        pass
    _feed(_NoDB(), [parse_ft8_message("CQ R9CA LO97")])
    # kein assert noetig — Test besteht wenn keine Exception fliegt


def test_empty_messages_no_call():
    """Leere Liste → kein db.set."""
    owner = _FakeOwner()
    _feed(owner, [])
    owner.locator_db.set.assert_not_called()
