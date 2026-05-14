# R1-Review fuer Toast-Bundle (deepseek-reasoner)

Du bist erfahrener PySide6-/UX-Engineer. **Du loest das Problem NICHT — du kritisierst und verbesserst den Plan.**

## Kontext (SimpleFT8 v0.97.17, Hobby-Funker-Tool)

Mike-Field-Test nach P46-Bandpilot: Auto-Modus-Toast erscheint bei
Bandwechsel mit Ranking 1./2./3. der 3 Modi. Mike sagt:
- „1 2 oder 3 sind nicht ersichtlich bei der Kuerze der Anzeige
  dass das ein Ranking ist"
- Toast-Zeit 5s ist zu kurz, 6s besser

## Plan-Inhalt (V3)

**`ui/bandpilot_dialogs.py`:**
1. Neuer Modul-Helper `_rank_marker(idx)` → `"🥇"`, `"🥈"`, `"🥉"` fuer idx 0/1/2, `""` bei out-of-range
2. `BandpilotAutoToast` Z.106-110: `{idx + 1}.` → `{_rank_marker(idx)}` im Ranking-Label
3. `BandpilotAutoToast` Z.113: `QTimer.singleShot(5000, ...)` → `QTimer.singleShot(_TOAST_DISPLAY_MS, ...)` mit `_TOAST_DISPLAY_MS = 6000`
4. `BandpilotManualDialog` Z.161-168: gleiche Marker-Aenderung in Ranking-Labels (Buttons unveraendert)

**5 Tests `tests/test_toast_bundle.py`:**
- T1 `_rank_marker(0/1/2)` returnt 🥇🥈🥉
- T2 `_rank_marker(3 / -1)` returnt ""
- T3 Auto-Toast enthaelt 🥇-Marker
- T4 Manual-Dialog enthaelt 🥇-Marker
- T5 `_TOAST_DISPLAY_MS == 6000`

## Verifikationen

- KEIN bestehender Test prueft `"1."` `"2."` `"3."` Strings → Marker-Aenderung sicher
- Bestehender Test `test_manual_dialog_shows_current_marker` prueft `●`-Marker fuer current → bleibt unveraendert (anderes Symbol als Ranking-Marker)
- `_TOAST_STYLE` Z.27-43 setzt `font-family: Menlo` (monospace). PySide6 Qt-Fallback nutzt Apple Color Emoji fuer Color-Glyphs. Sollte funktionieren — bei Render-Problem siehe R1-Frage 4

## Deine Aufgabe

1. **Medaillen-Wahl:** 🥇🥈🥉 — universelle Symbolik? Gibt es bessere Alternativen fuer ein technisches Funker-Tool? (Sterne ★★☆, Trophy, "Top/Mid/Low"?)
2. **6s-Wert:** subjektiv von Mike. KISS-OK ohne User-Setting?
3. **Emoji-Fallback:** Was wenn macOS / Linux / Windows-System Color-Emoji nicht rendert (alte OS-Versionen)?
   Vorschlag fuer Defensive: `os.environ.get("SIMPLEFT8_NO_EMOJI", "0") == "1"` → Text-Marker? Oder Overkill?
4. **Doppelmarker im Manual-Dialog:** Z.164-165 alt `{marker}  {idx + 1}. {label}` (mit ● fuer current + Ranking-Ziffer). Neu: `{marker}  {_rank_marker(idx)} {label}` (mit ● + 🥇/🥈/🥉). Lesbarkeit OK?
5. **Tests T3+T4 verlassen sich auf Emoji-Encoding in Python-Source:** Python 3 default UTF-8. Reicht das oder explicit `# -*- coding: utf-8 -*-` Header?
6. **Sind 5 Tests genug oder fehlt was?**

## Format

Tabelle:

| Schwere | Finding | Datei:Zeile | Empfehlung |

KRITISCH | SOLLTE-FIX | KOENNTE | HINWEIS

Am Ende: **Gesamtbewertung 1-10** + **„Code-Schreiben freigegeben"** / **„V3 muss erst X"**.

Bewerte: ist Plan KISS, oder over/underengineered?
