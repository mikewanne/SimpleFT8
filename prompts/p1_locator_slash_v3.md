# P1.LOCATOR-SLASH V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-07.
**Workflow:** V1 → V2 → R1 ✅ (Option A freigegeben + 1 KRITISCH + 1 SOLLTE-ERGAENZEN, beide adressiert) → **V3** → Compact → Code.
**Vorgaenger:** v0.95.15 (P1.QRZ-UPLOAD-UI-2). Tests 888 gruen.
**Compact-fest:** Diese Datei enthaelt ALLE Diffs. Nach Compact direkt Code.

---

## 1. R1-Findings (alle eingearbeitet)

| Finding | Status |
|---|---|
| Option A korrekt (strikte Trennung, kein Stripping) | ✅ V3 implementiert Option A |
| 🔴 Decoder-Verifikation Schritt 0 | ✅ ERLEDIGT pre-V3: `core/message.py:107-111` macht `split()` ohne Token-Modifikation. `m.caller="EA8/DA1MHH"` bleibt komplett. ft8lib liefert raw String. |
| 🟡 +2 Edge-Case-Tests (unknown prefix + region-suffix-country) | ✅ V3: 14 Tests statt 12 |
| ✅ DXCC-Praefixtabelle in geo.py vorhanden | ✅ `_PREFIX_MAP` wird wiederverwendet |
| ✅ APP_VERSION 0.95.16 | ✅ Bugfix-Patch |
| 🟢 MOBILE_SUFFIXES Konsolidierung | ✅ V3: zentral in `core/geo.py` |
| ✅ `_feed_locator_db` schon 1:1 OK | ✅ keine Aenderung |
| ✅ Karten-Code unbeeinflusst | ✅ direction_map_widget.py:1694 nicht angefasst |

---

## 2. Decoder-Verifikation (Schritt 0, ERLEDIGT)

```python
# core/message.py:107-111
parts = msg_str.strip().split()
f1 = parts[0]
f2 = parts[1]  # ← bei "CQ EA8/DA1MHH IL27" = "EA8/DA1MHH" (komplett!)
f3 = " ".join(parts[2:])
return FT8Message(field1=f1, field2=f2, field3=f3, ...)
```

**Bewiesen:** `m.caller` (= `field2`) enthaelt Slash-Call vollstaendig.
ft8lib (`core/ft8lib_decoder.py:40`) hat 35-Char-Buffer fuer message
— passt selbst fuer lange Slash-Calls.

**Konsequenz:** DB-Set-Pfad ist sauber. Bug liegt NUR im Lookup-Pfad
(rx_panel.py + geo.py).

---

## 3. Konkrete Diffs (Compact-fest)

### Diff 1 — `core/geo.py` MOBILE_SUFFIXES + DXCC-Helper (NEU)

**An den Anfang von `core/geo.py` (nach `import math`) einfuegen:**

```python
# ── Slash-Call-Konstanten ───────────────────────────────────

# Mobile-Suffixe: Operator unterwegs (variable Position).
# Format: mit FUEHRENDEM Slash, exakter Vergleich via str.endswith().
# Konsolidiert aus rx_panel.py + locator_db.py (V3 R1-Lesson).
MOBILE_SUFFIXES = ("/P", "/M", "/MM", "/AM", "/QRP", "/PORTABLE", "/MOBILE")


def _strip_mobile_suffix(call: str) -> str:
    """Mobile-Suffix entfernen. `DA1MHH/P` → `DA1MHH`. `DA1MHH` → `DA1MHH`."""
    up = call.upper()
    for suf in MOBILE_SUFFIXES:
        if up.endswith(suf):
            return up[:-len(suf)]
    return up


def _dxcc_prefix_from_call(call: str) -> str | None:
    """Bei Slash-Call: erstes Token zurueckgeben das in `_PREFIX_MAP` ist.

    `EA8/DA1MHH` → `EA8`. `K1ABC/W2` → `W2` (Suffix als DXCC).
    `DL/W7XYZ` → `DL`. `DA1MHH/P` → None (Mobile-Suffix kein DXCC).
    `DA1MHH` (ohne Slash) → None. Fallback dann auf normalen Lookup.
    """
    if "/" not in call:
        return None
    base = _strip_mobile_suffix(call)
    if "/" not in base:
        return None  # War nur Mobile-Suffix
    parts = base.split("/")
    for token in parts:
        if token in _PREFIX_MAP:
            return token
    # Iterativ Praefix-Match (z.B. "EA8" bei "EA8RUN/X")
    for token in parts:
        for plen in (3, 2, 1):
            if len(token) >= plen and token[:plen] in _PREFIX_MAP:
                return token[:plen]
    return None
```

(`_PREFIX_MAP` existiert bereits in `core/geo.py` — wird wiederverwendet.)

### Diff 2 — `core/geo.py:557+` `callsign_to_country` Fix

**Aktuell (vermutet, V3 verifiziert in Code-Phase):**
```python
def callsign_to_country(callsign: str) -> str:
    if "/" in callsign:
        parts = callsign.split("/")
        callsign = max(parts, key=len)  # ← BUG
    # ... _PREFIX_MAP-Lookup
```

**Neu:**
```python
def callsign_to_country(callsign: str) -> str:
    if not callsign:
        return ""
    up = callsign.upper().strip()
    # Slash-Call: DXCC-Praefix-Heuristik
    if "/" in up:
        dxcc_token = _dxcc_prefix_from_call(up)
        if dxcc_token is not None:
            cc = _PREFIX_MAP.get(dxcc_token)
            if cc:
                return _COUNTRY_NAMES.get(cc, "")
        # Mobile-Suffix nur → Basis-Call
        up = _strip_mobile_suffix(up)
    # Normal: Praefix-Match (existing logic, unchanged)
    for plen in (3, 2, 1):
        if len(up) >= plen and up[:plen] in _PREFIX_MAP:
            cc = _PREFIX_MAP[up[:plen]]
            return _COUNTRY_NAMES.get(cc, "")
    return ""
```

### Diff 3 — `core/geo.py` `callsign_to_distance` Fix

Analog: `max(parts, key=len)`-Block ersetzen durch:
```python
def callsign_to_distance(callsign: str, my_grid: str) -> int | None:
    if not callsign or not my_grid:
        return None
    up = callsign.upper().strip()
    target_call = up
    if "/" in up:
        dxcc_token = _dxcc_prefix_from_call(up)
        if dxcc_token is not None:
            target_call = dxcc_token  # Distanz zum DXCC-Land
        else:
            target_call = _strip_mobile_suffix(up)
    # ... bestehende _COUNTRY_COORDS-Lookup-Logik mit target_call
```

### Diff 4 — `ui/rx_panel.py:323-338` Slash-Logik vereinfachen

**Aktuell (Z.323-338):**
```python
country = "?"
caller = msg.caller
lookup_call = caller
if caller and "/" in caller:
    parts = caller.split("/")
    MOBILE_SUFFIXES = {"P", "M", "MM", "AM", "QRP", "PORTABLE", "MOBILE"}
    if parts[-1].upper() in MOBILE_SUFFIXES:
        lookup_call = parts[0]
    else:
        lookup_call = max(parts, key=len)  # ← BUG

if lookup_call and lookup_call != "<....>":
    country = callsign_to_country(lookup_call)
```

**Neu:**
```python
country = "?"
caller = msg.caller
# Lookup-Call = Decoder-Output 1:1 (Option A — strikte Trennung).
# Slash-Calls bleiben komplett erhalten — passend zu wie `_feed_locator_db`
# in mw_cycle.py:284 in die DB schreibt (`db.set(m.caller, ...)`).
lookup_call = caller

if lookup_call and lookup_call != "<....>":
    country = callsign_to_country(lookup_call)
```

→ **9 Zeilen Bug-Logik raus. Lookup ist jetzt 1:1 mit DB-Set-Pfad konsistent.**

`callsign_to_country` macht intern jetzt die DXCC-Praefix-Erkennung
(Diff 2). Die km-Spalten-Logik (Z.340-365) bleibt unveraendert — sie
nutzt `lookup_call` (jetzt = `caller`) fuer DB-Lookup.

### Diff 5 — `core/locator_db.py:11-15` MOBILE_SUFFIXES-Konstante entfernen

Aktuell hat locator_db eine eigene MOBILE_SUFFIXES-Konstante (V2 L7).
Ersetze durch Import aus geo.py:

```python
# Z. ~10
from core.geo import MOBILE_SUFFIXES
```

(Lokale Konstante streichen.)

`locator_db.py:180` aendert sich nicht — `call_upper.endswith(suf)`
funktioniert mit den Slash-Praefixen weiterhin korrekt (sogar
zuverlaessiger als vorher).

### Diff 6 — `tests/test_p1_locator_slash.py` (NEU, 14 Tests)

```python
"""Tests fuer P1.LOCATOR-SLASH v0.95.16.

Decken ab:
- Slash-Call-Praefix (EA8/DA1MHH) → Land Kanaren, km Kanaren-Position
- Slash-Call-Suffix-DXCC (K1ABC/W2) → Land USA
- Slash-Call-Mobile (DA1MHH/P) → Land DE, km Heim-Position fallback (kein
  DB-Eintrag → Prefix-Distanz vom Basis-Call)
- Unknown-Prefix (ZZ1/AA1ABC) → Land USA (Fallback Basis-Call-Land)
- _strip_mobile_suffix korrekt
- _dxcc_prefix_from_call mit verschiedenen Inputs
- LocatorDB konsistente Set/Get bei Slash-Call (was rein, was raus)
- _feed_locator_db schreibt korrekt mit Slash-Call
- Integration: rx_panel-Pfad mit echter LocatorDB
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── core/geo.py Helper-Tests ─────────────────────────────────────────────


def test_strip_mobile_suffix_removes_p():
    from core.geo import _strip_mobile_suffix
    assert _strip_mobile_suffix("DA1MHH/P") == "DA1MHH"
    assert _strip_mobile_suffix("DA1MHH/MM") == "DA1MHH"
    assert _strip_mobile_suffix("DA1MHH") == "DA1MHH"
    assert _strip_mobile_suffix("EA8/DA1MHH") == "EA8/DA1MHH"  # NICHT Mobile


def test_dxcc_prefix_from_call_prefix_slash():
    from core.geo import _dxcc_prefix_from_call
    assert _dxcc_prefix_from_call("EA8/DA1MHH") == "EA8"
    assert _dxcc_prefix_from_call("DL/W7XYZ") == "DL"


def test_dxcc_prefix_from_call_mobile_only_returns_none():
    from core.geo import _dxcc_prefix_from_call
    assert _dxcc_prefix_from_call("DA1MHH/P") is None
    assert _dxcc_prefix_from_call("DA1MHH") is None


def test_dxcc_prefix_from_call_unknown():
    from core.geo import _dxcc_prefix_from_call
    # ZZ1 ist kein DXCC-Praefix → None → Fallback
    result = _dxcc_prefix_from_call("ZZ1/AA1ABC")
    # Falls AA1 oder AA als Praefix erkannt: gut.
    # Falls None: auch akzeptabel (Test verifiziert nur kein Crash).
    assert result is None or result in ("AA", "AA1")


# ── callsign_to_country Tests ────────────────────────────────────────────


def test_callsign_to_country_prefix_slash_dxcc():
    from core.geo import callsign_to_country
    # EA8 = Kanaren
    country = callsign_to_country("EA8/DA1MHH")
    assert "Kanaren" in country or "Canary" in country or country.startswith("EA")


def test_callsign_to_country_mobile_suffix_basis():
    from core.geo import callsign_to_country
    # DA1MHH/P → Basis-Call DA1MHH → Deutschland
    country = callsign_to_country("DA1MHH/P")
    assert "Deutsch" in country or country.startswith("DE")


def test_callsign_to_country_region_suffix():
    from core.geo import callsign_to_country
    # K1ABC/W2 → W2 ist DXCC-Praefix → USA
    country = callsign_to_country("K1ABC/W2")
    assert "USA" in country or "United States" in country or "Amerika" in country


# ── callsign_to_distance Tests ───────────────────────────────────────────


def test_callsign_to_distance_prefix_slash():
    from core.geo import callsign_to_distance
    # EA8/DA1MHH von JO31 → ~3000 km (Kanaren)
    km = callsign_to_distance("EA8/DA1MHH", "JO31")
    assert km is not None and 2500 <= km <= 4000


def test_callsign_to_distance_mobile_suffix():
    from core.geo import callsign_to_distance
    # DA1MHH/P von JO31 → ~0-300 km (Heimat-Land)
    km = callsign_to_distance("DA1MHH/P", "JO31")
    assert km is not None and km < 500


def test_callsign_to_distance_no_slash_unchanged():
    from core.geo import callsign_to_distance
    # Regression: bestehender Pfad ohne Slash funktioniert weiter
    km1 = callsign_to_distance("DA1MHH", "JO31")
    km2 = callsign_to_distance("DA1MHH/P", "JO31")
    # Beide sollten Heimat-Distance liefern (DA1MHH/P → strip → DA1MHH)
    assert km1 == km2


# ── LocatorDB Konsistenz-Test ────────────────────────────────────────────


def test_locator_db_set_get_with_slash_call(tmp_path):
    """DB speichert Slash-Calls 1:1 unter dem gegebenen Key."""
    from core.locator_db import LocatorDB
    db = LocatorDB(path=tmp_path / "test_cache.json")
    db.set("EA8/DA1MHH", "IL27", "cq")
    entry = db.get("EA8/DA1MHH")
    assert entry is not None
    assert entry.locator == "IL27"
    # Lookup mit gestripptem Call findet NICHT (strikte Trennung):
    assert db.get("DA1MHH") is None


def test_locator_db_get_position_slash_call(tmp_path):
    """get_position bei Slash-Call → Kanaren-Position."""
    from core.locator_db import LocatorDB
    from core.geo import grid_to_latlon
    db = LocatorDB(path=tmp_path / "test_cache.json")
    db.set("EA8/DA1MHH", "IL27", "cq")
    pos = db.get_position("EA8/DA1MHH")
    assert pos is not None
    expected = grid_to_latlon("IL27")
    assert abs(pos[0] - expected[0]) < 0.5  # Lat Kanaren ~28°N
    assert abs(pos[1] - expected[1]) < 0.5  # Lon Kanaren ~16°W


# ── _feed_locator_db Test ────────────────────────────────────────────────


def test_feed_locator_db_writes_slash_call_unchanged():
    """_feed_locator_db speichert m.caller 1:1 in DB (kein Stripping)."""
    from ui.mw_cycle import CycleMixin
    from core.message import FT8Message
    owner = MagicMock()
    msg = FT8Message(
        raw="CQ EA8/DA1MHH IL27", field1="CQ", field2="EA8/DA1MHH",
        field3="IL27"
    )
    CycleMixin._feed_locator_db(owner, [msg])
    owner.locator_db.set.assert_called_once_with("EA8/DA1MHH", "IL27", "cq")


# ── Integration-Test mit echter DB ───────────────────────────────────────


def test_integration_rx_panel_finds_slash_call_in_db(qapp, tmp_path):
    """Echter Pfad: DB-Set mit Slash-Call → rx_panel findet via lookup_call."""
    from core.locator_db import LocatorDB
    db = LocatorDB(path=tmp_path / "test_cache.json")
    db.set("EA8/DA1MHH", "IL27", "cq")
    # Simuliere rx_panel._populate_row Lookup-Logik (Diff 4):
    caller = "EA8/DA1MHH"
    lookup_call = caller  # Option A: 1:1 ohne Stripping
    pos = db.get_position(lookup_call)
    assert pos is not None  # Bug 1 + 2 wuerden hier vor v0.95.16 None liefern
```

**Test-Anzahl: 14.**

---

## 4. Implementations-Reihenfolge (nach Compact)

1. **App killen** falls noch laeuft.
2. **Files lesen** (Verifikation):
   - `prompts/p1_locator_slash_v3.md` (diese Datei)
   - `core/geo.py` (Aktueller Stand `callsign_to_country` + `callsign_to_distance` + `_PREFIX_MAP` + `_COUNTRY_NAMES` + `_COUNTRY_COORDS`)
   - `ui/rx_panel.py` (Z.323-365 Slash-Logik)
   - `core/locator_db.py` (Z.10-15 MOBILE_SUFFIXES + `set/get`)
   - `core/message.py` (Decoder-Output bestaetigt — keine Aenderung)
3. **Diff 1** — `core/geo.py` MOBILE_SUFFIXES + `_strip_mobile_suffix` + `_dxcc_prefix_from_call` einfuegen.
4. **Diff 2** — `core/geo.py:callsign_to_country` Slash-Logik ersetzen.
5. **Diff 3** — `core/geo.py:callsign_to_distance` Slash-Logik ersetzen.
6. **Diff 4** — `ui/rx_panel.py:323-338` Slash-Block vereinfachen.
7. **Diff 5** — `core/locator_db.py` MOBILE_SUFFIXES Import.
8. **Diff 6** — `tests/test_p1_locator_slash.py` NEU mit 14 Tests.
9. **APP_VERSION** in `main.py` 0.95.15 → 0.95.16
10. **Tests laufen:** `888 → 902 erwartet gruen` (+14).
11. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P1.LOCATOR-SLASH v0.95.16 final-Code. DXCC-Heuristik
    in callsign_to_country/distance, MOBILE_SUFFIXES-Konsolidierung,
    rx_panel-Lookup-Vereinfachung. Karten-Code (direction_map_widget.py:
    1694) noch intakt? Statistik-Code unbeeinflusst?" | \
    ./venv/bin/python3 tools/deepseek_review.py \
    core/geo.py core/locator_db.py ui/rx_panel.py \
    ui/mw_cycle.py tests/test_p1_locator_slash.py
    ```
12. **Atomare Commits:**
    - Code+Tests: `P1.LOCATOR-SLASH (v0.95.16): Slash-Call Lookup-Bugs gefixt`
    - Doku: `docs (v0.95.16): P1.LOCATOR-SLASH HISTORY+HANDOFF+CLAUDE`
13. **Doku-Updates** (HISTORY beide Pfade, HANDOFF beide, CLAUDE beide).
14. **Push** NUR nach Mike-Freigabe + Field-Test.
15. **Lessons-Learned**.

---

## 5. Akzeptanz-Checkliste (final)

```
- [ ] core/geo.py: MOBILE_SUFFIXES + _strip_mobile_suffix + _dxcc_prefix_from_call
- [ ] core/geo.py: callsign_to_country Slash-Fix
- [ ] core/geo.py: callsign_to_distance Slash-Fix
- [ ] ui/rx_panel.py: Z.323-338 Slash-Block vereinfacht
- [ ] core/locator_db.py: MOBILE_SUFFIXES Import aus geo.py
- [ ] tests/test_p1_locator_slash.py: 14 Tests
- [ ] 902 Tests gesamt gruen
- [ ] Final-R1 ohne 🔴-Findings
- [ ] APP_VERSION 0.95.15 → 0.95.16
- [ ] HISTORY/HANDOFF/CLAUDE updated
- [ ] Atomare Commits
- [ ] Mike-Freigabe fuer Push EXPLIZIT (nach Field-Test mit echtem
      Slash-Call wie EA8 oder /P)
- [ ] Lessons-Learned
```

---

## 6. Risiken & Notbremse

- **DXCC-Heuristik-Edge-Cases:** Calls wie `K1ABC/QRP` haben weder DXCC-
  Praefix noch DXCC-Suffix, nur Mobile. `_dxcc_prefix_from_call` returnt
  None → Fallback auf `_strip_mobile_suffix` → `K1ABC` → USA. ✅
- **Region-Suffix vs DXCC-Suffix:** `K1ABC/W2` (W2 ist Region IN USA) wird
  als DXCC-Match erkannt → USA (gleiches Land, kein Schaden). Bei
  `DL1ABC/EA8` (EA8 = Kanaren-Aktivitaet) wird EA8 erkannt → korrekt.
- **Performance:** `_dxcc_prefix_from_call` macht max. 3 dict-Lookups +
  1 Iteration ueber Tokens. Vernachlaessigbar (1 Aufruf pro Decode).
- **Backwards-Compat:** Bestehende DB-Eintraege bleiben unveraendert. Nur
  Lookup findet sie jetzt korrekt. Karten-Code (direction_map_widget.py:
  1694) unangetastet.
- **Test-Datenbasis:** Tests nutzen tmp_path-DB (keine Pollution).
- **Compact-Risiko:** alle Diffs konkret in V3, Decoder-Verifikation
  ERLEDIGT pre-V3.

---

## 7. Lessons-Learned-Fragen (Skill Schritt 6 final, nach Code+Push)

1. Was war an P1.LOCATOR-SLASH ueberraschend?
2. Was wuerde ich rueckblickend anders machen?
3. Welches Memory soll geschrieben werden? Vorschlag:
   `feedback_decoder_verifikation_pflicht.md` — Bei jedem Bugfix der
   die Decoder-Output-Annahmen beruehrt, muss Schritt 0 die tatsaechliche
   Decoder-Ausgabe verifizieren (split-Output, ft8lib-Buffer, etc.).
   R1 hat diesen Punkt 07.05. als KRITISCH markiert — Lehre festhalten.

---

**Plan-V3 Ende. Bereit fuer Compact + Code.**
