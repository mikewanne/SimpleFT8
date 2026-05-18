# P79 — UI-Bundle V2 (Self-Review von V1)

**Status:** V2 (Self-Review nach V1, vor R1 DeepSeek).
**Datum:** 2026-05-18 nach Compact.
**Ziel:** Halluzinations-Check, Code-Verifikation aller V1-Behauptungen,
Punkt-4-Pfad-Audit, Farb-Werte gegen Codebasis, Findings nummeriert.

---

## Methodik

Alle V1-Code-Pfade per grep + Read gegen aktuellen Code v0.97.50 verifiziert.
Findings als F1-F8 nummeriert, jeweils mit „**Quelle:**", „**Korrektur:**",
„**Wirkung auf V3:**".

---

## V1-Verifikation (was hält stand, was muss korrigiert)

### V1-Behauptung: `qso_panel.add_info` Z.298-300 mit `#666666`
✓ **Bestätigt:** `ui/qso_panel.py:298-300`, dunkelgrau `#666666`, ruft
`_append_colored(f"       {text}", "#666666")`.

### V1-Behauptung: `mw_tx.py:401-405` SWR-Sperre-Text
✓ **Bestätigt:** Z.401-405 mit Text „Manueller TUNE zum Freischalten nach
Antennen-Check." — V1-Erweiterung sauber einsetzbar.

### V1-Behauptung: `mw_radio.py:1681-1731` Modal `_show_calibration_done`
✓ **Bestätigt:** Z.1681 Methoden-Definition, ~50 LOC QDialog+QTimer+QLabel,
endet Z.1731 mit `dlg.activateWindow()`.

### V1-Behauptung: 30+ Call-Sites von `add_info`
✓ **Bestätigt:** grep liefert **~30 Treffer** über mw_qso.py (14),
mw_radio.py (4), mw_tx.py (4), main_window.py (5), mw_cycle.py-evtl.
Option II (Auto-Detect) verhindert Migration in allen 30 Sites.

---

## Findings (V2-Self-Review)

### F1 — Punkt 4 ist im Code BEREITS implementiert ⚠ (Korrektur!)

**V1-Hypothese-1 sagte:** „Auto-TUNE-Fehler-Pfad fehlt `add_info`".

**V2-Verifikation:**
- `mw_radio.py:528-529` (in `_on_band_changed`) ruft **bereits**:
  ```python
  if not success:
      self.qso_panel.add_info(
          f"⚠ Auto-TUNE {band.upper()} fehlgeschlagen oder abgebrochen")
  ```
- `mw_radio.py:1286-1288` (`_check_diversity_preset` Pre-Check) ruft
  bereits `add_info("⚠ Diversity blockiert — Band X SWR-Sperre…")`.
- `mw_tx.py:710` (`_on_swr_alarm` Stop-Block) ruft bereits
  `add_info("⚠ Band X gesperrt — SWR Y.Y")`.

**Korrektur:** Punkt 4 ist NICHT „add_info fehlt", sondern entweder
- (a) Mike's Beobachtung war vor P76-C-Implementation (Marker-Set heute Vormittag).
- (b) Mike meint einen anderen Pfad — z.B. „TUNE OK aber Gain-Mess findet zu
  wenig Stationen" → DXTuneDialog returnt mit `_results=None` → Reject. Hier
  gibt es vermutlich KEINE add_info-Zeile.

**Wirkung auf V3:**
- Vor Code-Phase **eine Klarfrage an Mike** stellen: „welche konkrete UI-
  Sequenz hast du gesehen wo Statusbar feuerte aber QSO-Log nicht?" Ohne
  diese Klärung ist Punkt 4 spekulativ — nicht in V3-AC aufnehmen.
- Alternative: Punkt 4 in **V3 als „beobachten in Field-Test"** markieren,
  nicht als Code-Patch.

### F2 — Vorhandene ✓-Farbe in qso_panel ist `#44FF44`, nicht `#00CC66`

**Quelle:** `ui/qso_panel.py:287` `add_qso_complete` nutzt `#44FF44` (hellgrün).
V1 schlug `#00CC66` (mittelgrün) für ⚠/✓-Auto-Detect vor → **Stil-Inkonsistenz**.

**Vergleich vorhandene Farben:**
- `#44FF44` (hellgrün) — `add_qso_complete`
- `#FF4444` (hellrot) — `add_timeout`
- `#FFAA00` (orange) — TX-Zeilen `add_tx`
- `#44BBFF` (cyan) — RX-Zeilen `add_rx`
- `#666666` (dunkelgrau) — `add_info` heute

**Korrektur:** `_SYMBOL_COLORS` an vorhandene Palette anpassen:
```python
_SYMBOL_COLORS = {
    "⚠": "#FFAA00",  # Orange (analog TX-Farbe — sichtbar aber nicht hektisch)
    "✓": "#44FF44",  # Hellgrün (analog add_qso_complete)
    "✗": "#FF4444",  # Hellrot (analog add_timeout)
    "⏳": "#44BBFF",  # Cyan (analog add_rx)
}
```

**Wirkung auf V3:** Farbpalette einheitlich, Mike-Wunsch „funker-like" (kein
Magenta — analog Bundle F v0.97.23 wo `#FF66CC`→`#FFAA00` gefixt wurde).
**ROT-Variante #FF6600 streichen** — Mike-Field-Test-Memory zeigt orange
`#FFAA00` ist die etablierte Warn-Farbe.

### F3 — Rest-Text `#888888` vs. `#666666` — V1-Empfehlung zu hell?

**V1 schlug `#888888`** für Rest-Text. Vergleich mit aktuellem Code:
- `status_label` (qso_panel:154) nutzt `#666` für „X QSO(s) diese Session" —
  bewusst dezent.
- `add_info` heute `#666666`.

**Risiko:** `#888888` macht alle Info-Zeilen lauter — wirkt nicht mehr
„passiv". Mike sagte aber „dunkelgrau ist unscheinbar bei Warnungen" —
das ist über Symbol-Farbe gelöst.

**Korrektur:** Rest-Text **bei `#666666` lassen** (heutiges Verhalten). Symbol-
Färbung macht die Warnung sichtbar, Rest-Text bleibt lesbar-aber-dezent.

**Wirkung auf V3:** kein `_INFO_REST_COLOR=#888` — nur `_SYMBOL_COLORS` neu,
sonst alles wie heute. Schlanker Patch.

### F4 — V1-Test T9 ist nicht ausreichend („KEIN QDialog")

**V1 T9:** „`mw_radio.py` enthält KEIN `QDialog` mehr in
`_show_calibration_done`."

**Problem:** `mw_radio.py` enthält an anderen Stellen weitere QDialogs (z.B.
DXTuneDialog Import in Z.1520). Source-Level-grep `class.*QDialog` greift,
aber regex auf gesamte Datei → false positive.

**Korrektur:** Test scoped auf Methoden-Source:
```python
import inspect
from ui.mw_radio import MWRadioMixin
src = inspect.getsource(MWRadioMixin._show_calibration_done)
assert "QDialog" not in src
assert "qso_panel.add_info" in src
```

**Wirkung auf V3:** alle Source-Level-Tests müssen `inspect.getsource(method)`
verwenden (Pattern aus P55/P76-C), nicht raw-file-grep.

### F5 — Symbol-Erkennung: `text[0]` versus multi-char Symbol

**Quelle:** V1-Code `if text and text[0] in _SYMBOL_COLORS`.

**Verifikation:** ⚠ (U+26A0), ✓ (U+2713), ✗ (U+2717), ⏳ (U+23F3) sind ALLE
**single-codepoint BMP-Zeichen** — `text[0]` funktioniert in Python 3.x korrekt.

Aber: Falls Mike später Multi-Codepoint-Symbole nutzt (z.B. ❌ U+274C, oder
Emoji-Variation-Selectors), würde `text[0]` brechen.

**Korrektur:** robusteres Pattern via `text.startswith(symbol)`-Loop:
```python
def add_info(self, text: str):
    if text:
        for symbol, color in _SYMBOL_COLORS.items():
            if text.startswith(symbol):
                rest = text[len(symbol):]
                self._append_two_color(
                    f"       {symbol}", color,
                    rest, "#666666"
                )
                return
    self._append_colored(f"       {text}", "#666666")
```

**Wirkung auf V3:** KISS-konform (5 LOC), zukunftssicher gegen Multi-CP-Symbole.

### F6 — Default-Color bei leerem Text

**V1-Code:** `if text and text[0] in _SYMBOL_COLORS:` — bei leerem `text`
fällt's auf else-Branch `_append_colored(f"       ", "#666666")` → leere
graue Zeile. Heute identisch (kein Bug, aber unnötig).

**Korrektur (optional):** Empty-Guard am Anfang:
```python
if not text:
    return  # silent — keine leere Zeile
```

**Wirkung auf V3:** Mike-UX-Vorteil: kein unsichtbares leeres Append. R1 soll
entscheiden ob das Verhalten ändern oder bleiben.

### F7 — `add_qso_complete` + `add_timeout` haben EIGENES Symbol+Farbe-Pattern

**Quelle:**
- `add_qso_complete:287` rendert `"       ✓ QSO mit X komplett"` einheitlich
  in `#44FF44` (Symbol + Text gleiche Farbe).
- `add_timeout:295` rendert `"       ✗ X — Timeout"` einheitlich in `#FF4444`.

V1-Auto-Detect würde diese Pfade NICHT betreffen weil sie `_append_colored`
direkt aufrufen, nicht `add_info`.

**V2-Frage:** soll P79 diese Methoden auch auf Variante-B umstellen
(Symbol+Rest-Split)?

**Empfehlung:** **NEIN**. Diese sind „Statusmeldungen" mit eigenem Stil
(grünes/rotes QSO-Komplett-Banner). Funktional anders als „passive Info mit
Warn-Präfix". Konsistenz: `add_info` ist der einzige Pfad der heterogene
Info-Pfade abdeckt — dort macht Auto-Detect Sinn. Die anderen sind
spezialisiert.

**Wirkung auf V3:** explizit als „aus Scope" markieren — `add_qso_complete`
und `add_timeout` bleiben unverändert.

### F8 — Existierende `add_info`-Calls mit Symbol — sind ALLE current-style-symbolisch?

**grep `add_info.*⚠`:** Treffer in mw_tx.py (3x), mw_radio.py (2x), mw_qso.py (?)
**grep `add_info.*✓`:** Treffer in mw_tx.py (2x — TUNE OK, Band freigegeben),
mw_qso.py (?)

**Wichtige Stellen ohne Symbol heute (bleiben grau):**
- `"CQ-Modus gestartet"` mw_qso:336 → grau ✓
- `"Rufe XYZ..."` mw_qso:238 → grau ✓
- `"CQ gestoppt — Einmessen aktiv"` mw_radio:1115 → grau ✓
- `"HALT — alles gestoppt"` mw_qso:372 → grau ✓ (Mike könnte ein ⚠ wünschen?
  Out-of-scope für P79 — Mike-Feedback abwarten)

**Wirkung auf V3:** kein retroaktiver Symbol-Patch. P79 betrifft NUR
`add_info`-Auto-Detect, Aufrufer bleiben unverändert. Wenn ein Pfad „lauter"
werden soll, kann ein Symbol prefix in einem späteren Bundle ergänzt werden.

---

## Halluzinations-Check (V1 → V2)

| V1-Claim | Verifikation | Status |
|---|---|---|
| `qso_panel.add_info` Z.298-300 | ✓ Read | OK |
| `mw_tx.py:401-405` SWR-Text | ✓ Read | OK |
| `mw_radio.py:1681-1731` Modal | ✓ Read | OK (zeilengenau) |
| 30 add_info Call-Sites | ✓ grep | OK |
| Symbol-Codepoints single-BMP | ✓ Unicode-Check | OK |
| Punkt 4 add_info fehlt | ✗ widerlegt — schon da | F1-Korrektur |
| `#00CC66` für ✓ | ✗ widerlegt — `#44FF44` etabliert | F2-Korrektur |
| `#FF6600` für ⚠ | ✗ widerlegt — `#FFAA00` etabliert | F2-Korrektur |
| `#888888` für Rest | ✗ widerlegt — heutiges `#666` bleibt | F3-Korrektur |

**Halluzinations-Rate V1:** 4 von 9 verifizierbaren Claims daneben. Mässig.
KISS-Vorteil von V2: alle 4 Korrekturen sind „weniger machen" — schlankerer
V3-Patch.

---

## Korrigierter V3-Vorschlag (kompakt)

### Patch 1 — `ui/qso_panel.py` `add_info` Auto-Detect

```python
# Modul-Konstante (oben in qso_panel.py)
_SYMBOL_COLORS = {
    "⚠": "#FFAA00",  # Orange (Warnung)
    "✓": "#44FF44",  # Hellgrün (Erfolg, analog add_qso_complete)
    "✗": "#FF4444",  # Hellrot (Fehler, analog add_timeout)
    "⏳": "#44BBFF",  # Cyan (Warteliste, analog add_rx)
}

def add_info(self, text: str):
    """Info-Nachricht anzeigen.

    P79: Symbol-Auto-Detect — beginnt der Text mit ⚠/✓/✗/⏳, wird das
    Symbol farbig gerendert, der Rest bleibt dezent grau (#666). KISS,
    keine Call-Site-Migration der ~30 Aufrufer.
    """
    if not text:
        return
    for symbol, color in _SYMBOL_COLORS.items():
        if text.startswith(symbol):
            rest = text[len(symbol):]
            self._append_two_color(
                f"       {symbol}", color,
                rest, "#666666"
            )
            return
    self._append_colored(f"       {text}", "#666666")
```

### Patch 2 — `ui/mw_tx.py:401-405` Text-Erweiterung

```python
self.qso_panel.add_info(
    f"⚠ Band {band} gesperrt — SWR {swr_now:.1f} > "
    f"Limit {swr_limit:.1f}. Antenne pruefen ODER "
    f"SWR-Limit in Einstellungen anpassen ODER "
    f"manueller TUNE zum Freischalten."
)
```

### Patch 3 — `ui/mw_radio.py:1681-1731` `_show_calibration_done` ersetzen

```python
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    """P79: Kalibrierungs-Ergebnis als Live-Log-Zeile (Modal weg).

    Vorher (v0.97.50): Auto-Close-QDialog 3s, brach Mike's Workflow.
    Jetzt: ✓-Zeile in qso_panel via Auto-Detect grün gerendert.
    """
    if ant2_g is not None:
        text = (f"✓ Kalibrierung {band} gespeichert. "
                f"ANT1: {ant1_g} dB | ANT2: {ant2_g} dB")
    else:
        text = f"✓ Kalibrierung {band} gespeichert. ANT1: {ant1_g} dB"
    self.qso_panel.add_info(text)
```

### Patch 4 — Punkt 4 ausgelassen / als „Field-Test-Beobachtung"

V2-F1-Korrektur: kein Code-Patch ohne Mike-Klärung welcher Pfad gemeint war.
Aktuell sind alle bekannten SWR-Abbruch-Pfade mit `add_info` versorgt.

### Tests (12 → 11 reduziert)

T1-T6 wie V1, **angepasste Farben** (T1 → `#FFAA00`, T2 → `#44FF44`,
T3 → `#FF4444`, T4 → `#44BBFF`).
T7 — `_SYMBOL_COLORS` Konvention-Lock.
T8 — Source-Level: `mw_tx.py:_tune_post_swr_check` enthält `"ODER SWR-Limit"`.
T9 — `inspect.getsource(MWRadioMixin._show_calibration_done)` enthält KEIN
`QDialog`, enthält `qso_panel.add_info`.
T10 — `_show_calibration_done(band, 25, None)` ruft `add_info` mit
`"✓ Kalibrierung 20m gespeichert. ANT1: 25 dB"`.
T11 — `_show_calibration_done(band, 25, 30)` ruft `add_info` mit ANT2-Suffix.
**T12 entfällt** (Punkt 4 raus aus V3).

### LOC-Bilanz korrigiert

| Datei | V1 LOC | V2 LOC korrigiert |
|---|---|---|
| `ui/qso_panel.py` | +12 | +13 (mit Empty-Guard + Loop-Pattern) |
| `ui/mw_tx.py` | +2 | +2 (unverändert) |
| `ui/mw_radio.py` | -47/+8 | -47/+8 (unverändert) |
| Tests | ~15 | ~11 (Punkt 4 raus) |
| **Netto** | **~-25 LOC** | **~-24 LOC** |

---

## Offene Fragen für R1 DeepSeek-Review

1. **Punkt-4-Frage:** soll P79 das offene Punkt 4 ohne Mike-Klärung
   einplanen (z.B. defensive add_info in jedem Auto-TUNE-Reject-Pfad), oder
   sauber raus halten und Mike Field-Test entscheiden lassen?
2. **F5 Multi-Codepoint:** lohnt sich die Loop-Variante gegen die simple
   `text[0]`-Variante? KISS-Argument für simple, Robustheit für Loop.
3. **F7 Konsistenz:** soll `add_qso_complete` und `add_timeout` mit auf
   Symbol-Color-Split umgestellt werden für UI-Konsistenz, oder Eigenstil
   behalten?
4. **`_SYMBOL_COLORS` Position:** Modul-Level (qso_panel.py oben) oder
   Klassen-Attribut von `QSOPanel`? V2-Empfehlung: Modul-Level (KISS).
5. **Backwards-Compat-Risiko:** gibt es `add_info`-Aufrufer die `text` mit
   einem führenden Symbol senden, das **nicht** in `_SYMBOL_COLORS` ist
   (z.B. emoji oder unicode aus Locator-Anzeige)? grep liefert nur die
   bekannten 4 → kein Risiko.

---

**Naechster Schritt:** V2-Prompt + V1 + relevante Files (qso_panel.py,
mw_tx.py 350-420, mw_radio.py 1640-1740) an DeepSeek R1 via
`tools/deepseek_review.py`.

R1-Prompt-Fokus:
- Punkt-4-Strategie (klären vs. raus halten)
- F2-Farbpalette gegen Hobby-Funker-UX (Mike: „funker-like, nix Disco")
- F5/F7 Architektur-Entscheidungen
- Test-Coverage-Lücken aufdecken
- Backwards-Compat Risiko-Audit
