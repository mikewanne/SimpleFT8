# Toast-Bundle — Medaillen + 6s + Konsistenz (V1, 13.05.2026)

**Status:** V1 → V2 → R1 → V3 → Code (autonom).

**Trivial-Klausel:** nein — Verhaltens-/UX-Aenderung, beruehrt 2 Dialog-Klassen, Tests müssen weiterhin grün bleiben.

---

## 1. Mike-Anliegen (Field-Test 13.05.2026 mittags)

Nach P46-Field-Test (Auto-Modus auf 20m wechselte sauber zu Diversity DX) sagt Mike:

1. **„1 2 oder 3 sind nicht ersichtlich bei der kürze der anzeige"** — Ranking-Marker als Text-Ziffer ist auf 5 Sek-Toast nicht sofort als Ranking erkennbar.
2. **„dort steht 1 2 oder 3"** — Toast und Manual-Dialog nutzen beide `"1./2./3."` was nicht klar genug ist.
3. **Toast-Zeit zu kurz:** „3 Sekunden geschätzt, 6 wäre besser" — tatsächlich 5000ms aktuell, Mike will mehr Lesezeit.

## 2. Verifizierter Code-Stand

**`ui/bandpilot_dialogs.py:`**
- `BandpilotAutoToast` Z.106-110 — Ranking mit `{idx + 1}.` als Text-Marker
- `BandpilotAutoToast` Z.113 — `QTimer.singleShot(5000, self._safe_close)` (Self-Close in 5s)
- `BandpilotManualDialog` Z.161-168 — Ranking mit `{idx + 1}.` + `●` für current

**Bestehende Tests** (`tests/test_mw_radio_bandpilot.py:239-303`):
- `test_auto_toast_instantiable_without_crash` — Smoke
- `test_auto_toast_contains_top1_label` — prueft Labels `"Diversity DX"`, `"40m"`, `"13 UTC"` — bleibt grün
- `test_manual_dialog_shows_current_marker` — prueft `●`-Marker für current → bleibt grün (`●` ist anderes Symbol als Ranking-Marker)
- KEIN Test prueft `"1."`, `"2."`, `"3."` explizit → Marker-Aenderung sicher

## 3. Loesung

### Maßnahme A — Medaillen-Helper
Neuer Modul-Helper in `ui/bandpilot_dialogs.py`:
```python
def _rank_marker(idx: int) -> str:
    """Ranking-Marker: 🥇 (Top-1), 🥈 (Top-2), 🥉 (Top-3).

    Fallback fuer mehr als 3 Eintraege (theoretisch unmoeglich da
    immer 3 Modi): leere Zeichenkette.
    """
    return ("🥇", "🥈", "🥉")[idx] if 0 <= idx <= 2 else ""
```

### Maßnahme B — `BandpilotAutoToast` Marker-Anpassung

Z.106-110 alt:
```python
for idx, (mode_code, mean) in enumerate(rec["ranking"]):
    row = QLabel(f"{idx + 1}. {USER_LABEL.get(mode_code, mode_code)}: "
                 f"{mean:.1f}")
    row.setObjectName("row_top1" if idx == 0 else "row_neutral")
    layout.addWidget(row)
```

neu:
```python
for idx, (mode_code, mean) in enumerate(rec["ranking"]):
    row = QLabel(f"{_rank_marker(idx)} {USER_LABEL.get(mode_code, mode_code)}: "
                 f"{mean:.1f}")
    row.setObjectName("row_top1" if idx == 0 else "row_neutral")
    layout.addWidget(row)
```

### Maßnahme C — Self-Close 5s → 6s

Z.113:
```python
# Self-close nach 6 Sekunden (Mike-Feedback 13.05.: 5s zu kurz fuer Ranking-Lesezeit)
QTimer.singleShot(6000, self._safe_close)
```

### Maßnahme D — `BandpilotManualDialog` Marker-Konsistenz

Z.161-168 alt:
```python
for idx, (mode_code, mean) in enumerate(rec["ranking"]):
    label = USER_LABEL.get(mode_code, mode_code)
    marker = "●" if mode_code == current else " "
    lbl = QLabel(f"  {marker}  {idx + 1}. {label:<22} "
                 f"{mean:>6.1f} Sta./Slot")
```

neu:
```python
for idx, (mode_code, mean) in enumerate(rec["ranking"]):
    label = USER_LABEL.get(mode_code, mode_code)
    marker = "●" if mode_code == current else " "
    lbl = QLabel(f"  {marker}  {_rank_marker(idx)} {label:<22} "
                 f"{mean:>6.1f} Sta./Slot")
```

→ `●` (current-Marker) bleibt + neuer `🥇/🥈/🥉` Ranking-Marker. Beide nebeneinander.

## 4. Akzeptanzkriterien

| AK | Bedingung | Verifikation |
|---|---|---|
| AK1 | `_rank_marker(0)` returnt `"🥇"`, `_rank_marker(1)` `"🥈"`, `_rank_marker(2)` `"🥉"` | Unit-Test |
| AK2 | `_rank_marker(idx)` für `idx > 2` oder `idx < 0` returnt `""` (Defensive) | Unit-Test |
| AK3 | `BandpilotAutoToast` enthält `🥇`-Marker bei Top-1 | Test (findChildren QLabel) |
| AK4 | `BandpilotManualDialog` enthält `🥇`-Marker bei Top-1 | Test |
| AK5 | `BandpilotManualDialog` behält `●`-Marker bei current (Test bleibt grün) | bestehender Test |
| AK6 | Self-Close-Zeit ist `6000ms` | grep |
| AK7 | Volle Test-Suite grün (1233 → 1233 + 3 neue) | pytest |

## 5. Files

| Datei | Aenderung |
|---|---|
| `ui/bandpilot_dialogs.py` | `_rank_marker` Helper NEU; Maßnahmen B + C + D |
| `tests/test_toast_bundle.py` NEU | 4 Tests (T1-T4) |
| `main.py` | APP_VERSION 0.97.17 → 0.97.18 |

**KEIN Touch:**
- `core/mode_recommender.py`
- `ui/mw_radio.py`
- `_TOAST_STYLE` + `_MANUAL_STYLE` (Emoji laesst sich mit Menlo-Font darstellen, alternativ Qt-Default-Font-Fallback)

## 6. Tests (`test_toast_bundle.py` — 4 Tests)

| T# | Test | Erwartung |
|---|---|---|
| T1 | `test_rank_marker_returns_medals` | Helper liefert 🥇🥈🥉 für idx 0/1/2 |
| T2 | `test_rank_marker_returns_empty_for_invalid_idx` | idx=3, idx=-1 returnt `""` |
| T3 | `test_auto_toast_uses_medal_markers` | Toast enthaelt `🥇` in einem Label |
| T4 | `test_manual_dialog_uses_medal_markers` | Dialog enthaelt `🥇` in einem Label |

## 7. Backup & Commits

**Backup:** `Appsicherungen/2026-05-13_v0.97.17_vor_toast_bundle/ui/bandpilot_dialogs.py`.

**Atomare Commits:**
- **C1** `ui/bandpilot_dialogs.py` — `_rank_marker` Helper + Maßnahmen B+C+D
- **C2** `tests/test_toast_bundle.py` — 4 neue Tests
- **C3** `main.py` — APP_VERSION 0.97.18
- **C4** Doku (HISTORY + HANDOFF + CLAUDE + Memory + TODO)

## 8. Risiken

| R | Risiko | Mitigation |
|---|---|---|
| R1 | Emoji rendert nicht (Menlo-Font hat keine Color-Emoji) | Qt-System-Font-Fallback nutzt iOS-Emoji. Mac/Linux haben Color-Emoji-Renderer. Bei Render-Problem → Fallback auf Text-Marker `"1°"/"2°"/"3°"` |
| R2 | Bestehende Tests brechen (Format-Change) | Bestehende Tests prüfen nur "Diversity DX" + "40m" + "13 UTC" + `●` — bleibt grün |
| R3 | Toast-Layout zu breit wegen Emoji | Emoji ist 1-2 chars wide, Layout dynamisch (QVBoxLayout) → wächst falls nötig |

## 9. Was R1 vermutlich sagt

- KOENNTE: Emoji-Fallback wenn System es nicht rendert (R1-Tendenz Defensive)
- HINWEIS: 6s-Zeit ist kein magischer Wert, sollte vielleicht in Settings als Konstante
- HINWEIS: `_rank_marker` als Modul-Funktion oder Klassen-Methode? — Modul-Funktion ist KISS

→ V3 wird vermutlich gleich bleiben, eventuell R1 vorschlägt Fallback-Pattern.

---

**Naechster Schritt:** V2 Self-Review.
