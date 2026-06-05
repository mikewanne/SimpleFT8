"""Tests fuer core/atomic_json.atomic_write_json (OPT-54).

Schreibt ausschliesslich nach ``tmp_path`` — niemals nach ~/.simpleft8.
"""

import json

import pytest

from core.atomic_json import atomic_write_json


def test_roundtrip_dict(tmp_path):
    """Geschriebenes JSON ist exakt wieder lesbar."""
    p = tmp_path / "data.json"
    payload = {"a": 1, "b": [2, 3], "c": "x"}
    atomic_write_json(p, payload, indent=2)
    assert json.loads(p.read_text()) == payload


def test_roundtrip_list(tmp_path):
    """Auch eine Liste (awards_prefs-Fall) geht durch."""
    p = tmp_path / "list.json"
    atomic_write_json(p, ["WAS", "WAZ"], indent=2)
    assert json.loads(p.read_text()) == ["WAS", "WAZ"]


def test_creates_parent_dirs(tmp_path):
    """Eltern-Verzeichnis wird bei Bedarf erzeugt (mkdir parents)."""
    p = tmp_path / "sub" / "deeper" / "x.json"
    atomic_write_json(p, {"ok": True}, indent=2)
    assert p.exists()
    assert json.loads(p.read_text()) == {"ok": True}


def test_no_tmp_left_after_success(tmp_path):
    """Nach Erfolg liegt KEINE .tmp-Datei mehr im Verzeichnis (os.replace)."""
    p = tmp_path / "clean.json"
    atomic_write_json(p, {"v": 1}, indent=2)
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == [], f"tmp-Reste: {leftover}"


def test_dump_kwargs_separators_vs_indent(tmp_path):
    """dump_kwargs werden durchgereicht → kompakt vs. eingerueckt bit-genau.

    Sichert die Format-Identitaet der migrierten Stores:
    indent=2 (rf_preset/mode_recommender) vs. separators=(",",":")
    (psk_reporter/locator_db).
    """
    payload = {"a": 1, "b": 2}

    p_compact = tmp_path / "compact.json"
    atomic_write_json(p_compact, payload, separators=(",", ":"))
    assert p_compact.read_text() == '{"a":1,"b":2}'

    p_indent = tmp_path / "indent.json"
    atomic_write_json(p_indent, payload, indent=2)
    assert p_indent.read_text() == json.dumps(payload, indent=2)
    assert "\n" in p_indent.read_text()  # eingerueckt = mehrzeilig


def test_overwrite_replaces_atomically(tmp_path):
    """Zweiter Write ersetzt den ersten vollstaendig (kein Anhaengen)."""
    p = tmp_path / "over.json"
    atomic_write_json(p, {"first": 1}, indent=2)
    atomic_write_json(p, {"second": 2}, indent=2)
    assert json.loads(p.read_text()) == {"second": 2}


def test_exception_propagates_not_swallowed(tmp_path):
    """Helfer schluckt NIE selbst — nicht-serialisierbares Objekt -> TypeError.

    Vertrag: der Aufrufer entscheidet ueber Fehlerbehandlung. Schluckte der
    Helfer still, wuerde ein vergessenes try/except unbemerkt Daten verlieren.
    """
    p = tmp_path / "bad.json"

    class NotSerializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(p, {"x": NotSerializable()})


def test_no_partial_file_on_dump_error(tmp_path):
    """Bricht json.dump ab, darf die Zieldatei NICHT halbfertig existieren.

    Der Schreibvorgang laeuft auf der tmp-Datei; os.replace passiert erst NACH
    erfolgreichem dump → die Zieldatei bleibt unberuehrt (Atomaritaets-Kern).
    """
    p = tmp_path / "target.json"
    p.write_text('{"orig": true}')  # bestehender, gueltiger Inhalt

    class NotSerializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(p, {"x": NotSerializable()}, indent=2)

    # Zieldatei unveraendert (alte Daten intakt), kein zerrissener Stand
    assert json.loads(p.read_text()) == {"orig": True}
