[deepseek] ~8052 Tokens, 2 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=10419 out=6321 total=16740
Hier ist das Review für den Toast-Bundle-Plan. Die Übersicht folgt deiner gewünschten Tabellenstruktur, plus einer finalen Bewertung.

---

| Schwere | Finding | Datei:Zeile | Empfehlung |
|---|---|---|---|
| **SOLLTE-FIX** | **Emoji-Fallback fehlt im Plan.** Der Plan sagt „Sollte funktionieren“ und verweist auf R1-Frage 4. Fakt ist: Alte macOS-, Linux-Desktop- oder Headless-CI-Umgebungen ohne Color-Emoji-Font rendern `🥇` als leere Box oder Monochrome-Zeichen. Die UX verschlechtert sich dort dann sogar gegenüber dem vorherigen Text-Marker `1.`. Der Plan *kann* so umgesetzt werden, muss aber bewusst entscheiden, ob ein Fallback eingebaut wird oder nicht. | `_rank_marker`–Definition | **Nimm dem Plan die Unsicherheit.** Entweder baust du einen einfachen Fallback in `_rank_marker` ein (`RANK_MARKERS = ("🥇", "🥈", "🥉")` plus Text-Fallback) oder du dokumentierst *explizit*, dass das Risiko akzeptiert wird, weil der Medaillen-Gewinn im Normalbetrieb das Risiko auf Altsystemen überwiegt. **Ein `os.environ`-Flag ist nicht nötig** – ein simpler Check in `_rank_marker` (z. B. `_USE_EMOJI = not os.environ.get("SIMPLEFT8_TEXT_MARKERS")`) reicht und macht die Tests deterministisch. |
| **KOENNTE** | **Kein Sicherheitsnetz für Toast-Layout bei breiten Emoji-Glyphen.** Emoji sind oft breiter als ein Monospace-Char (Menlo). Im QVBoxLayout wächst der Dialog dynamisch, aber der `title`-Label und das `chosen`-Label sind zentriert. Ein breiter Emoji kann den Zeilenumbruch triggern. | `BandpilotAutoToast` Layout | Smoke-Test (T3) wie geplant reicht aus. Ergänze im Plan einen **Hinweis auf manuelles UI-Checking** für das Layout. Kein automatisierter Test nötig. |
| **HINWEIS** | Medaillen-Wahl `🥇🥈🥉` ist **perfekt**. Sie sind universell, sofort als Ranking dekodierbar und heben sich klar vom `●`-Marker ab. Sterne wären zu unspezifisch, Text-Marker verfehlen das Ziel. | `_rank_marker` | Beibehalten. |
| **HINWEIS** | `6s`-Wert ist subjektiv (Mike). Als Konstante (`_TOAST_DISPLAY_MS = 6000`) **KISS-OK**. Kein User-Setting nötig. Falls später weitere Nutzer Feedback geben, kann die Konstante trivial in Settings verschoben werden. | `_TOAST_DISPLAY_MS` | Beibehalten. |
| **HINWEIS** | **Doppelmarker** im Manual-Dialog (`●` + Medaille) sind klar getrennt und gut lesbar. Die Symbole haben unterschiedliche Semantik (current vs. ranking). Keine Verwechslungsgefahr. | `BandpilotManualDialog` | Beibehalten. |
| **HINWEIS** | **`# -*- coding: utf-8 -*-` ist in Python 3 Default.** Nicht nötig. | `tests/test_toast_bundle.py` | Keine Aktion. |
| **HINWEIS** | **5 Tests sind ausreichend.** T1–T2 decken die Unit ab, T3–T4 die Integration, T5 die Konstante. Die alte Test-Suite bleibt grün. Ein Test auf *Nichtvorhandensein* von `"1."` wäre zwar denkbar, ist aber durch die positiven Tests implizit abgedeckt. | `tests/test_toast_bundle.py` | Keine neuen Tests nötig. |

---

## Gesamtbewertung & Entscheid

**Gesamtbewertung:** `9 / 10`

**Begründung:**
Der Plan ist **sehr KISS**. Er adressiert die UX-Schwäche präzise, validiert die Auswirkungen auf bestehende Tests, extrahiert die Magic-Numbers, und hat eine klare Backup-/Commit-Strategie. Der gesamte Scope ist klein, atomar, und rückwärtskompatibel.

Einziger wirklich relevanter Kritikpunkt ist das fehlende **Defensive-Handling für das Emoji-Rendering** (SOLLTE-FIX). Das ist kein Showstopper für den Code, aber eine bewusste Design-Entscheidung, die der Plan treffen sollte, bevor der Code geschrieben wird. Ohne diese Entscheidung kann der Code auf einer alten Linux-Distro UX-technisch kaputt sein.

**Entscheid:** **Code-Schreiben freigegeben** unter der Bedingung, dass der SOLLTE-FIX (Emoji-Fallback) *vor* dem Commit finalisiert wird. Entweder baust du den Fallback ein, oder du dokumentierst im Doku-Commit (C4) warum das Risiko akzeptiert wird.
