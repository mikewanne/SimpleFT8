# Toast-Bundle (V2 Self-Review, 13.05.2026)

**V2-Auftrag:** Frische-KI-Review von V1 — was uebersieht V1?

---

## V2-Findings

### L1 — V1 prueft nicht ob Mac-Font im Toast Color-Emoji rendert

`_TOAST_STYLE` setzt `font-family: Menlo` (Monospace ohne Color-Emoji). PySide6 Qt-Renderer fallback auf System-Font fuer Glyphs die Menlo nicht hat → macOS Apple Color Emoji wird aktiviert → 🥇 als Color-Emoji.

**Empirie:** macOS Sequoia Qt-Rendering hat Color-Emoji seit Jahren. Sollte funktionieren.

**Risiko:** Wenn nicht → 🥇 als monochrome Char. Immer noch lesbar, aber nicht so visuell.

→ V3: keine Aenderung, R1-Hinweis abwarten.

### L2 — V1 setzt 6 Sekunden hart, kein Sekunde-Vergleich

Mike sagt „6s wäre besser", aber das ist sein erster Eindruck. Was wenn auch 6s zu kurz? Iteration ist OK, V3 stellt sicher dass Konstante leicht änderbar.

→ V3: Konstante `_TOAST_DISPLAY_MS = 6000` am Modul-Anfang.

### L3 — V1 vergisst „Top-2/Top-3-Buttons" im Manual-Dialog

Manual-Dialog hat 3 Buttons unter dem Ranking. Sollten die auch Medaillen tragen? In V1 nur die Labels über den Buttons. Buttons selbst zeigen nur `USER_LABEL.get(mode_code, mode_code)` (= "Normal", "Diversity Standard", etc.).

**Pro Medaillen-Buttons:** noch klarer welcher die Empfehlung ist.
**Contra:** Button-Text wird länger, Layout kann brechen.

→ V3: Buttons unverändert lassen (Top-1 ist schon farblich grün via `btn_top1`-Style). Medaillen nur über den Buttons. KISS.

### L4 — V1 vergisst Mike-Konstante-Test

Wenn `_TOAST_DISPLAY_MS = 6000` als Konstante, sollte ein Test das pruefen — sonst kann jemand auf 1000 runtersetzen ohne dass es auffällt.

→ V3: T5 NEU — `from ui.bandpilot_dialogs import _TOAST_DISPLAY_MS; assert _TOAST_DISPLAY_MS == 6000`.

### L5 — V1 verifiziert nicht ob Emoji-Char-Length im QLabel-Layout problematisch ist

QLabel-Width wachst dynamisch. Emoji ist 1-2 Char-Wide (Pixel-Wise variabel). Bei breiterer Toast-Anzeige könnte das Layout sich verschieben.

→ V3: Smoke-Test reicht (instanziierbar ohne Exception). Layout-Test wäre overengineering.

### L6 — V1 erwähnt P14-Lesson nicht: bei Symptom-Fixes Wurzel pruefen

P14-Lesson: bei symptomatischer Anzeige-Aenderung pruefen ob Wurzel woanders liegt. Hier ist „Toast-Marker unklar" ein UI-Wahrnehmungs-Problem — kein Algorithmus-Bug. Wurzel ist tatsaechlich „Text-Marker ist nicht visuell genug". OK.

→ V3: keine Aktion.

### L7 — V1 vergisst Help-Text/Tooltip ueber Medaillen

Wenn neue User die App benutzen — sehen sie 🥇 sofort als Ranking? Universelle Symbolik, sollte verstanden werden.

→ V3: keine Aktion, Symbolik universell.

### L8 — Emoji-Encoding in Tests

Tests die `"🥇"` als Literal nutzen — Python-Source-File braucht UTF-8 Encoding-Tag oder Default (Python 3 = UTF-8 default). Kein Problem.

→ V3: keine Aktion.

### L9 — APP_VERSION-Bump 0.97.17 → 0.97.18 oder 0.98.0?

UX-Aenderung (Marker + Sekunden) ist Patch-Level. 0.97.18 OK.

→ V3: 0.97.18.

### L10 — `_rank_marker` als Klassen-Methode vs Modul-Funktion?

V1 sagt Modul-Funktion. Das ist KISS. Stateless, deterministisch.

→ V3: Modul-Funktion bleibt.

---

## V2 → V3 Aenderungen

1. **L2:** `_TOAST_DISPLAY_MS = 6000` als Modul-Konstante am Anfang.
2. **L4:** T5 NEU — Konstanten-Test (5 Tests total statt 4).

Restliche L-Findings keine Aktion.

---

## Was R1 vermutlich finden wird

- KOENNTE: Emoji-Fallback-Pattern (Defensive falls System es nicht rendert) — z.B. `os.environ.get("SIMPLEFT8_NO_EMOJI", "0") == "1"` → Text-Marker
- KOENNTE: 6s als Mike-Wunsch ist subjektiv — User-Setting? (Overengineering bei einem User)
- HINWEIS: Test-Robustheit gegen Emoji-Encoding-Issues

V3 wird vermutlich keine grossen Aenderungen erfordern. Schauen wir was R1 dazu sagt.
