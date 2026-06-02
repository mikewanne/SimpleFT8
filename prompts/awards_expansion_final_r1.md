# Final-Review: Diplome-Erweiterung (implementiert)

Du bist Final-Reviewer (DeepSeek v4-pro) für ein Hobby-Funker-FT8-Tool
(SimpleFT8, EIN Operator, KEIN Contest-Tool). Der Plan (V3) wurde von dir
mitgeprüft und vom User freigegeben. Hier ist der **fertige Code**. Deine
Aufgabe: **Push-Freigabe ja/nein + Bugs/Findings** (🔴 Blocker / 🟠 wichtig /
🟡 nice-to-have). Antworte knapp und konkret.

## Was umgesetzt wurde (gegen V3-Plan)
1. **WAE** — Näherung über eindeutige europäische DXCC-Entities (`CONT=="EU"`),
   Tooltip ehrlich als Näherung gekennzeichnet. Ziel 70.
2. **WPX** — `wpx_prefix(call)` parst Präfix aus dem Rufzeichen. **Alle 3
   Slash-Formen** behandelt (gegen 25 echte Log-Calls verifiziert, 25/25 OK):
   - Mobil-Suffix: `F5OYA/P → F5`, `S51PV/QRP → S51`
   - Präfix-Slash vorn: `OE/DL6CGU → OE0` (ohne Ziffer → "0"), `SV9/DL1MTB → SV9`
   - Regions-Ziffer: `N1UL/3 → N3`, `RA0QK/8 → RA8`
   (Dein V1-Skizzen-Vorschlag `digit_parts[0]` war hier falsch — hätte
   `OE/DL6CGU → DL6` ergeben. Korrigiert: kürzerer Teil = Standort-Präfix.)
   Ziel 300, PFX-Feld ignoriert (immer aus CALL).
3. **DXCC-Band-Tiefe** — DXCC-Karte erweitert um Challenge-Zähler (Entity-Band-
   Slots, Ziel 1000, nur HF-Bänder 160-6m, 60m+2m raus) + kompakte
   5-Band-DXCC-Zeile (✓ ab 100 Entities je 80/40/20/15/10m).
4. **Sichtbarkeit** — eigenes Modul `core/awards_prefs.py` (JSON in
   `~/.simpleft8/`), kein Settings-Durchreichen. 👁-Button pro Karte,
   Klappbereich unten mit klickbaren "wieder einblenden"-Buttons. Karten via
   `setVisible`, kein Layout-Neubau.

## Verifizierte Fakten
- Volle Test-Suite: **2277 passed** (vorher 2255, +22 neue Tests).
- End-to-End über echtes Logbuch (18329 QSOs): DXCC 157/123, WAE 63/59,
  WPX 1516/1147, WAC 6/6, WAS 49/48, WAZ 38/33, Challenge 562, 5BD: nur 15m ✓.
- `AwardsDialog.__init__(records, parent)` — Signatur UNVERÄNDERT (kein Bruch).
- Reines Logdaten-Auswerten + Anzeige: **kein TX, keine Hardware, ANT1/ANT2
  nicht berührt.**

## Prüf-Schwerpunkte (bitte besonders ansehen)
1. `wpx_prefix` — übersehene Slash-Edge-Case oder Crash bei exotischem Input?
2. `_apply_visibility` / `_clear_layout` — Qt-Memory/Lifecycle bei wiederholtem
   Toggle (takeAt + deleteLater, Stretch-Item neu erzeugt)? Lambda-Closure
   `k=key` korrekt gebunden?
3. `compute_awards` — Performance über 18k Records ok (läuft pro Record 1×
   wpx_prefix mit Regex)? Korrektheit der Band-Normalisierung?
4. `awards_prefs` — Defensive Fehlerbehandlung vollständig?
5. KISS-Verstoß / Overengineering irgendwo?

Gib am Ende ein klares **PUSH FREIGEBEN** oder **NICHT FREIGEBEN** + Liste.
