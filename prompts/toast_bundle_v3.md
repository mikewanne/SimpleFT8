# Toast-Bundle (V3, 13.05.2026)

**Status:** V3 nach R1-Findings 9/10 — SOLLTE-FIX Emoji-Fallback uebernommen. Bereit fuer Code.

---

## R1-Bilanz V2-Review

| Schwere | Finding | Aktion |
|---|---|---|
| **SOLLTE-FIX** | Emoji-Fallback fehlt | **uebernommen** — Env-Var `SIMPLEFT8_TEXT_MARKERS` |
| KOENNTE | Smoke-Test reicht fuer Layout | belassen |
| HINWEIS | 🥇🥈🥉-Wahl perfekt | belassen |
| HINWEIS | 6s als Konstante KISS-OK | belassen |
| HINWEIS | Doppelmarker `●` + 🥇 OK | belassen |
| HINWEIS | UTF-8 Default in Python 3 | belassen |
| HINWEIS | 5 Tests reichen → werden 6 mit Fallback | +1 Test |

## Endgueltige Lösung

### Maßnahme A — `_rank_marker` mit Fallback

```python
import os

_USE_EMOJI = not os.environ.get("SIMPLEFT8_TEXT_MARKERS")
_MEDAL_MARKERS = ("🥇", "🥈", "🥉")
_TEXT_MARKERS = ("Top:", "2.:", "3.:")
_TOAST_DISPLAY_MS = 6000


def _rank_marker(idx: int) -> str:
    """Ranking-Marker fuer Top-1/2/3.

    Default: 🥇🥈🥉. Mit `SIMPLEFT8_TEXT_MARKERS=1` → Text-Fallback
    ("Top:", "2.:", "3.:") fuer Systeme ohne Color-Emoji-Renderer
    (alte Linux-Desktops, Headless-CI).
    """
    markers = _MEDAL_MARKERS if _USE_EMOJI else _TEXT_MARKERS
    return markers[idx] if 0 <= idx <= 2 else ""
```

### Maßnahmen B+C+D wie V1 (unveraendert)

### Tests `tests/test_toast_bundle.py` — 6 Tests

| T# | Test | Erwartung |
|---|---|---|
| T1 | `test_rank_marker_default_medals` | 🥇🥈🥉 fuer idx 0/1/2 (Default) |
| T2 | `test_rank_marker_returns_empty_for_invalid_idx` | "" fuer idx 3, -1 |
| T3 | `test_auto_toast_uses_medal_markers` | Toast enthaelt 🥇 in Label |
| T4 | `test_manual_dialog_uses_medal_markers` | Dialog enthaelt 🥇 in Label |
| T5 | `test_toast_display_ms_is_6000` | `_TOAST_DISPLAY_MS == 6000` |
| T6 (NEU) | `test_rank_marker_text_fallback` | mit monkeypatch `_USE_EMOJI=False` → "Top:" "2.:" "3.:" |

## Files (unveraendert)

| Datei | Aenderung |
|---|---|
| `ui/bandpilot_dialogs.py` | `_rank_marker` Helper + Konstanten + Maßnahmen B+C+D |
| `tests/test_toast_bundle.py` NEU | 6 Tests |
| `main.py` | APP_VERSION 0.97.17 → 0.97.18 |

---

**V3 freigegeben für Code-Implementation** (autonom).
