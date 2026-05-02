"""Smoke-Test: Help-Dialog _FEATURES Liste vs docs/explained/-Dateien.

Stellt sicher, dass jeder Eintrag in `_FEATURES` von ui/help_dialog.py
zwei real existierende Markdown-Dateien hat:
- `docs/explained/<base>_de.md` (Deutsch)
- `docs/explained/<base>.md` (Englisch)

Bricht den Test wenn ein Eintrag in `_FEATURES` ergaenzt wird ohne
dass die Doku-Files angelegt wurden — verhindert "Dokument noch nicht
vorhanden"-Anzeige im Help-Dialog auf Mike's Bildschirm.

Auch implizit: prueft dass keine alte Doku-Datei verwaist ist (alle
in `_FEATURES` referenzierten existieren).
"""

from pathlib import Path

import pytest

from ui.help_dialog import _FEATURES, _DOCS_DIR


@pytest.mark.parametrize(
    "label_de,label_en,base",
    _FEATURES,
    ids=[f[2] for f in _FEATURES],
)
def test_feature_doc_exists(label_de: str, label_en: str, base: str):
    """Beide Doku-Files (DE+EN) existieren fuer dieses Feature."""
    de_path = _DOCS_DIR / f"{base}_de.md"
    en_path = _DOCS_DIR / f"{base}.md"
    assert de_path.exists(), f"DE-Doku fehlt: {de_path}"
    assert en_path.exists(), f"EN-Doku fehlt: {en_path}"


def test_features_are_alphabetically_sorted():
    """_FEATURES ist alphabetisch nach Anzeige-Name DE sortiert (KISS).

    Case-insensitive Sortierung — wie der Leser im Help-Dialog erwartet
    ("Anrufer-Warteliste" vor "AP-Lite Rettung", weil 'n' < 'p').
    """
    de_names = [f[0] for f in _FEATURES]
    expected = sorted(de_names, key=str.lower)
    assert de_names == expected, (
        "_FEATURES nicht alphabetisch sortiert. "
        "Erwartet:\n  " + "\n  ".join(expected) +
        "\nGefunden:\n  " + "\n  ".join(de_names)
    )


def test_features_count_minimum():
    """Sicherheitsgurt: mindestens 15 Features sind dokumentiert."""
    assert len(_FEATURES) >= 15, (
        f"Nur {len(_FEATURES)} Features in _FEATURES — "
        "irgendwas wurde versehentlich entfernt?"
    )


def test_no_duplicate_slugs():
    """Kein Slug doppelt — sonst hat sich Help-Dialog verlinkt."""
    slugs = [f[2] for f in _FEATURES]
    assert len(slugs) == len(set(slugs)), (
        f"Doppelte Slugs in _FEATURES: {[s for s in slugs if slugs.count(s) > 1]}"
    )
