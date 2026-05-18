# DeepSeek R1-Review fuer P79 UI-Bundle (V4-pro, 26-Cycle-Position)

## Kontext

Du bist DeepSeek V4-pro im Rolle des **R1-Reviewers** fuer SimpleFT8, ein
privates FT8/FT4/FT2-Funker-Tool. Voller V1→V2→R1→V3→Code→Final-R1-Workflow
ist Pflicht. Mike (Hobby-Funker, DA1MHH) hat 6 UI-Verbesserungen aus heutigem
Field-Test angefragt — V1 ist der Initial-Vorschlag, V2 ist mein Self-Review
mit 8 Findings die V1 teils korrigiert haben. Du sollst V2 jetzt durchgehen.

**Hinweis Mike-Klarung 18.05.2026 nach Compact:** Punkt 4 (Gain-Mess-Abbruch
SWR → QSO-Log) ist in V3 **AUSGENOMMEN** — V2-F1 zeigt dass alle bekannten
add_info-Pfade schon existieren. Mike will erst Field-Test machen.

**Stand:** v0.97.50, Tests 1484 grün, Push pending v0.97.40-50 wegen Field-
Tests von P75/P76-A/P76-C die alle ✓ sind. P79 wird v0.97.51.

**V4-pro Empirische Bilanz bis jetzt:** 25 Cycles, 0 Halluzinationen, 100%
verifizierbar (Bundle I+J+P51+P53+P55+Bundle K+P58+P60+P61+P62+P63+Intent+
P52+Bundle-L+P66+P67+P54+P54-FIX+P69+P71+P75+P76-A+P76-C).

---

## Was P79 macht (kompakter Plan)

### Patch 1 — `ui/qso_panel.py` add_info Auto-Detect (Variante B KISS)

`add_info` heute (Z.298-300) rendert alles in `#666666` dunkelgrau. Mike
sagt das ist „unscheinbar" bei Warnungen.

Neu: Symbol-Auto-Detect ohne Call-Site-Migration der ~30 Aufrufer.

```python
_SYMBOL_COLORS = {
    "⚠": "#FFAA00",   # Orange (analog Bundle F v0.97.23: Magenta→Orange-Korrektur)
    "✓": "#44FF44",   # Hellgruen (analog add_qso_complete Z.287)
    "✗": "#FF4444",   # Hellrot (analog add_timeout Z.295)
    "⏳": "#44BBFF",   # Cyan (analog add_rx)
}

def add_info(self, text: str):
    if not text:
        return
    for symbol, color in _SYMBOL_COLORS.items():
        if text.startswith(symbol):
            rest = text[len(symbol):]
            self._append_two_color(
                f"       {symbol}", color,
                rest, "#666666"  # Rest bleibt heutiges Grau
            )
            return
    self._append_colored(f"       {text}", "#666666")
```

### Patch 2 — `ui/mw_tx.py:401-405` SWR-Sperre-Text erweitern

Mike: „Text fehler sollte eindeutiger sein nicht nur Manueller TUNE zum
Freischalten. sondern vlt noch antte überprüfen oder swr limit anpassen ?"

Aktuell:
```python
f"⚠ Band {band} gesperrt — SWR {swr_now:.1f} > Limit {swr_limit:.1f}. "
f"Manueller TUNE zum Freischalten nach Antennen-Check."
```

Neu:
```python
f"⚠ Band {band} gesperrt — SWR {swr_now:.1f} > Limit {swr_limit:.1f}. "
f"Antenne pruefen ODER SWR-Limit in Einstellungen anpassen ODER "
f"manueller TUNE zum Freischalten."
```

Tuner-fehlt-Branch (Z.407-411) bleibt unveraendert.

### Patch 3 — `ui/mw_radio.py:1681-1731` Modal raus, durch add_info ersetzen

Mike: „verbesserung ui, kalibrierung gespeichert als info text auch qso
fenster, seperates info fenster modual weg, spart sekunden flüssigeren
ablauf"

Heute: 50-LOC QDialog Auto-Close 3s mit WindowStaysOnTopHint. Mike findet
das stoert seinen Workflow.

Neu (~8 LOC):
```python
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    if ant2_g is not None:
        text = (f"✓ Kalibrierung {band} gespeichert. "
                f"ANT1: {ant1_g} dB | ANT2: {ant2_g} dB")
    else:
        text = f"✓ Kalibrierung {band} gespeichert. ANT1: {ant1_g} dB"
    self.qso_panel.add_info(text)
```

Synergistisch mit Patch 1: ✓ wird grün gerendert durch Auto-Detect.

### Patch 4 — Punkt 4 (Gain-Mess SWR-Meldung) AUSGENOMMEN

Mike-Entscheidung (a) — Field-Test erst, dann ggf. Folge-Patch. Begruendung
in V2-F1: alle bekannten add_info-Pfade existieren bereits.

---

## V2-Findings die V1 korrigiert haben

1. **F1** — Punkt 4 widerlegt (schon implementiert) → V3 raus.
2. **F2** — Farben angepasst an Codebasis (`#FFAA00`, `#44FF44`, `#FF4444`,
   `#44BBFF`) statt V1's `#FF6600`/`#00CC66`.
3. **F3** — Rest-Grau bleibt `#666666` (V1's `#888` zu laut).
4. **F4** — Tests via `inspect.getsource(method)`, nicht raw-grep.
5. **F5** — `text.startswith(symbol)`-Loop statt `text[0]` (Multi-Codepoint).
6. **F6** — Empty-Guard `if not text: return`.
7. **F7** — `add_qso_complete` + `add_timeout` AUSSER Scope.
8. **F8** — kein retroaktiver Symbol-Patch in andere Aufrufer.

---

## Was du als R1 leisten sollst

### Findings-Liste mit Schweregrad

Format pro Finding:
```
F<NR>: <KURZ> [🔴 ROT | 🟠 ORANGE | 🟡 GELB | ⚪ WEISS]
Begruendung: <warum>
Vorschlag: <konkret>
```

- 🔴 **ROT** = Bug, Sicherheit, Datenverlust, Race-Condition → muss adressiert.
- 🟠 **ORANGE** = Risiko, Edge-Case, KISS-Verletzung → soll adressiert.
- 🟡 **GELB** = Verbesserung, Wartung, Doku → kann adressiert.
- ⚪ **WEISS** = INFO, keine Aktion noetig.

### Spezielle Pruef-Punkte

1. **Backwards-Compat:** gibt es `add_info`-Aufrufer (siehe alle ~30) die
   ein Symbol senden das **nicht** in `_SYMBOL_COLORS` ist, sodass das
   neue Verhalten regressiv waere? Bitte aktiv suchen in den 3 Files.
2. **Race / Thread-Safety:** `add_info` wird aus dem GUI-Thread aufgerufen
   (Qt-Slots). Gibt es Aufrufe aus Decoder/Worker-Thread? Falls ja,
   `_append_two_color` greift QTextEdit-API → muss QueuedConnection sein.
3. **`_append_two_color` Existenz:** check ob die Methode existiert
   (qso_panel.py:375-390) und ob Symbol+Space als 1. Argument korrekt
   gerendert wird (Newline-Verhalten).
4. **F5 Loop-Pattern:** ist die `text.startswith(symbol)`-Loop deterministisch
   bei Dict-Iter (Python 3.7+ ordered) — oder soll explizit `list` davor?
5. **F6 Empty-Guard:** Verhalten heute ist „lege leere Zeile ab" — wird das
   irgendwo bewusst genutzt (z.B. Trenner)? grep `add_info("")`.
6. **F7-Entscheidung:** soll `add_qso_complete` (✓) und `add_timeout` (✗)
   wirklich aus Scope bleiben, oder zerstoert das die Konsistenz?
7. **Modal-Loeschen Patch 3:** P79 entfernt das `WindowStaysOnTopHint`-
   Modal. Gibt es Cases wo der User die ✓-Bestaetigung BRAUCHT (z.B.
   blockierende Bestaetigung dass Kalibrierung erfolgreich gespeichert ist)?
   add_info ist non-blocking — schluckt es eine Info wenn QSO-Log gerade
   scroll-busy ist? `_auto_trim_by_age` 5min-Window — Gefahr Info zu
   verlieren?
8. **Test-Coverage:** sind die 11 Tests ausreichend? Vorschlaege fuer
   weitere Edge-Cases.

### Hardware-Pflicht-Check ⛔

P79 ist rein UI — kein TX-Trigger. Aber bitte verifizieren ob keiner der
Patches einen vorhandenen ANT1-Pflicht-Pfad versehentlich beruehrt.

### Push-Empfehlung

Am Ende eine Zeile: „**PUSH FREIGEGEBEN**" oder „**PUSH BLOCKIERT WEGEN
F<x>**" mit kurzer Begruendung.

---

## Anbei: V1 (Originalvorschlag) + V2 (Self-Review) + 3 Code-Files

V1 + V2 sind in `prompts/p79_ui_bundle_v1.md` + `prompts/p79_ui_bundle_v2.md`.
Code-Files: `ui/qso_panel.py` (komplett, ~430 LOC), `ui/mw_tx.py` (Bereich
TUNE-Logik), `ui/mw_radio.py` (Bereich Diversity + `_show_calibration_done`).

Im Anschluss kommen die Files. Bitte gehe V2 durch, finde Findings, gib
Push-Empfehlung.
