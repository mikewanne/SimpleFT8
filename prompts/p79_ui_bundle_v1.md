# P79 — UI-Bundle (6 Mike-Punkte aus Field-Test 18.05.2026)

**Status:** V1 (Draft, vor Self-Review V2).
**Quelle:** Memory `project_p79_ui_bundle_pre_compact.md`.
**Stand:** v0.97.50, Tests 1484 grün, P76-A+C Field-Tests alle ✓.

---

## Problem (Mike-Wortlaut)

Nach P76-A + P76-C Field-Tests gestern fand Mike **6 UI-Verbesserungen** die
zusammen als P79-Bundle eingespielt werden sollen. Voller V1→V2→R1→V3→Code-
Workflow (CLAUDE.md-Pflicht — keine Trivial-Klausel weil >5 LOC + neue UI-
Konvention).

---

## Die 6 Punkte

### Punkt 1 — Text-Formulierung erweitern (mehrere Handlungsoptionen)

**Aktuell** `ui/mw_tx.py:401-405` (else-Branch in `_tune_post_swr_check`):

```python
self.qso_panel.add_info(
    f"⚠ Band {band} gesperrt — SWR {swr_now:.1f} > "
    f"Limit {swr_limit:.1f}. Manueller TUNE zum "
    f"Freischalten nach Antennen-Check."
)
```

**Mike-Wunsch:** Text macht nur EINE Handlung klar (TUNE). Aber es gibt drei
gleichwertige Optionen — Mike-Quote:

> „Text fehler sollte eindeutiger sein nicht nur Manueller TUNE zum
> Freischalten. sondern vlt noch antte überprüfen oder swr limit anpassen ?"

**Neue Formulierung:**

```python
self.qso_panel.add_info(
    f"⚠ Band {band} gesperrt — SWR {swr_now:.1f} > "
    f"Limit {swr_limit:.1f}. Antenne pruefen ODER "
    f"SWR-Limit in Einstellungen anpassen ODER "
    f"manueller TUNE zum Freischalten."
)
```

Tuner-fehlt-Branch (Z.407-411) bleibt unveraendert — Tuner-Match
fehlgeschlagen heisst tatsaechlich nur Antennen-Check sinnvoll.

### Punkt 2 + 3 + 6 — Style fuer ⚠/✓-Zeilen (Symbol-Auto-Detect)

**Mike-Quote:** „text in qso fenster sehr unscheinbar (dunkelgrau) evt gelb
oder rot oder fett oder unterstrichen"

**Mike-Praeferenz Variante B (Memory):** „nur Symbol/Praefix gefaerbt, Rest
grau lesbar bleiben".

**Architektur-Entscheidung — Option II (Auto-Detect in `add_info`):**

`ui/qso_panel.py` `add_info` heute (Z.298-300):
```python
def add_info(self, text: str):
    """Info-Nachricht anzeigen."""
    self._append_colored(f"       {text}", "#666666")
```

→ alles dunkelgrau, Symbole unauffaellig.

**Neu Auto-Detect:** wenn `text` mit Symbol startet → Symbol+Space in Farbe,
Rest etwas heller (#888888 statt #666666 für Lesbarkeit).

```python
# Symbol → Farbe-Mapping (Modul-Konstante)
_SYMBOL_COLORS = {
    "⚠": "#FF6600",  # Orange-Rot für Warnungen
    "✓": "#00CC66",  # Grün für Erfolg
    "✗": "#FF4444",  # Rot für Fehler
    "⏳": "#44BBFF",  # Cyan für Warteliste/laufend
}
_INFO_REST_COLOR = "#888888"  # heller als heutiges #666 für Lesbarkeit
_INFO_DEFAULT_COLOR = "#888888"  # ohne Symbol → einheitlich grau

def add_info(self, text: str):
    """Info-Nachricht anzeigen.

    Symbol-Auto-Detect (P79): Beginnt der Text mit ⚠/✓/✗/⏳, wird das
    Symbol farbig (Orange/Grün/Rot/Cyan) gerendert, der Rest in
    lesbarem Grau. KISS — keine neuen Helper, keine Call-Site-Migration.
    """
    if text and text[0] in _SYMBOL_COLORS:
        symbol = text[0]
        rest = text[1:]
        self._append_two_color(
            f"       {symbol}", _SYMBOL_COLORS[symbol],
            rest, _INFO_REST_COLOR
        )
    else:
        self._append_colored(f"       {text}", _INFO_DEFAULT_COLOR)
```

**Wirkung:**
- Alle ~30 bestehenden `add_info`-Aufrufer bleiben unveraendert.
- ⚠-Zeilen (SWR-Sperre, Diversity blockiert) → Orange-Symbol sichtbar.
- ✓-Zeilen (Kalibrierung gespeichert, P75 TUNE OK) → Grünes Symbol.
- Reine Info-Zeilen (CQ-Modus gestartet, Rufe XYZ) bleiben grau.

**Punkt 3 (Konsistenz):** sobald das Symbol konsequent vor jeden Hinweis
gestellt wird, ist Style automatisch konsistent. Punkt 6 (Variante B) ist
exakt dieses Verhalten — nur Symbol gefaerbt, Rest grau.

### Punkt 4 — Gain-Mess-Abbruch wegen SWR → QSO-Log-Meldung

**Mike-Quote:** „wechsel auf diversity nicht möglich, (in mitteilungsfenster
(verbesserung meldung auch im QSO fenster als status meldung ?"

**Code-Pfad-Audit (zu verifizieren in V2/R1):**

| Pfad | Aktueller Code | add_info? |
|---|---|---|
| `_check_diversity_preset` Marker-Pre-Check (mw_radio:1284-1290) | already done | ✓ ja |
| `_on_swr_alarm` Stop-Block (mw_tx:710) | already done | ✓ ja |
| Auto-TUNE-Fehler (mw_tx:391-396) | `dlg.auto_tune_done.emit(False, ...)` → Dialog schliesst, Lock-Release in `_on_dx_tune_rejected` (?) | **prüfen** |
| `_assess_gain` returnt missing aber TUNE startet nicht (Marker rot) | im Pre-Check Z.1284 abgefangen | ✓ ja |

**V3-Spec:** im V2-Self-Review verifizieren ob es einen Pfad gibt der die
Gain-Mess-Pipeline abbricht ohne `qso_panel.add_info`. Falls ja: 1-Zeilen
Add-info-Patch ergänzen analog Z.1286.

**Hypothese-1 (Vermutung):** Auto-TUNE-Phase A (vor Gain-Mess) fehlschlägt
→ AutoTuneDialog zeigt Fail-Banner, Lock wird in mw_radio released, aber
qso_panel.add_info fehlt → User sieht nur Statusbar nicht QSO-Log.

### Punkt 5 — Modal „Kalibrierung gespeichert" raus → QSO-Log

**Mike-Quote:** „verbesserung ui, kalibrierung gespeichert als info text auch
qso fenster, seperates info fenster modual weg, spart sekunden flüssigeren
ablauf"

**Aktuell** `ui/mw_radio.py:1681-1731`:

```python
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    """Auto-Close-Info-Popup 'Kalibrierung abgeschlossen' — 3s, kein OK."""
    from PySide6.QtCore import Qt as _Qt, QTimer as _QTimer
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
    dlg = QDialog(self)
    dlg.setWindowTitle("Kalibrierung abgeschlossen")
    dlg.setWindowFlag(_Qt.WindowType.WindowStaysOnTopHint, True)
    dlg.setStyleSheet("QDialog, QWidget { background-color: #16192b; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 16)
    lay.setSpacing(10)
    lbl_title = QLabel(f"✓  Kalibrierung {band} gespeichert.")
    lbl_title.setStyleSheet(...)
    lay.addWidget(lbl_title)
    if ant2_g is not None:
        lbl_info = QLabel(f"ANT1: {ant1_g} dB  |  ANT2: {ant2_g} dB")
    else:
        lbl_info = QLabel(f"ANT1: {ant1_g} dB")
    ...
    _close_timer = _QTimer(dlg)
    _close_timer.setSingleShot(True)
    _close_timer.timeout.connect(dlg.accept)
    _close_timer.start(3000)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
```

**Neu — komplett ersetzen durch ~5 Zeilen:**

```python
def _show_calibration_done(self, band: str, ant1_g: int, ant2_g: int | None):
    """P79: Kalibrierungs-Ergebnis als Live-Log-Zeile (Modal weg)."""
    if ant2_g is not None:
        text = (f"✓ Kalibrierung {band} gespeichert. "
                f"ANT1: {ant1_g} dB | ANT2: {ant2_g} dB")
    else:
        text = f"✓ Kalibrierung {band} gespeichert. ANT1: {ant1_g} dB"
    self.qso_panel.add_info(text)
```

**Wirkung:** Punkt 5 wirkt synergistisch mit Punkt 2 — durch Auto-Detect
zeigt die ✓-Zeile direkt das grüne Symbol an, ohne separates Popup-Fenster.
Mike-Vision „weniger Fenster die aufploppen" umgesetzt — analog Bundle J
QMessageBox-Eliminierungen und P75 (TUNE-bad-Modal raus).

Aufrufer `_show_calibration_done` (Z.1660 + Z.1679) bleiben unveraendert —
nur die Methode wird intern ersetzt.

---

## Aenderungs-Liste (kompakt)

| Datei | Aenderung | LOC |
|---|---|---|
| `ui/qso_panel.py` | `add_info` Auto-Detect (Modul-Konstanten + ~8 Zeilen) | +12 |
| `ui/mw_tx.py:401-405` | Text-Erweiterung „Antenne pruefen ODER ..." | +2 |
| `ui/mw_radio.py:1681-1731` | `_show_calibration_done` komplett ersetzen | -47/+8 |
| `ui/mw_radio.py` | (Punkt 4) ggf. fehlende `add_info` an Auto-TUNE-Fail-Pfad | +1-3 |
| `tests/test_p79_ui_bundle.py` NEU | Source-Level + Smoke-Tests | ~15 Tests |

**Geschätzt:** netto ~-25 LOC (Modal-Block fällt weg, neuer Helper kleiner).

---

## Architektur-Begruendung Option II (Auto-Detect) statt Option I (3 Helper)

**Option I (verworfen):** neue Helper `add_warning`/`add_success` neben
`add_info` → 30+ Call-Sites müssten migriert werden, explizit aber
wartungs-aufwendig.

**Option II (gewählt — KISS):** Auto-Detect in `add_info` → keine Call-Site-
Migration, Symbol-Konvention bleibt stabil (Mike nutzt schon ⚠/✓/✗ überall).

Risiko: implizit. Mitigation: feste Symbol→Farbe-Map als Modul-Konstante,
Test-Coverage für jede Symbol-Variante.

---

## Hardware-Pflicht-Check ⛔

P79 ist **rein UI** — kein TX-Trigger, keine Antennen-Schaltung. ANT1-Pflicht
nicht betroffen (CLAUDE.md HARDWARE-WARNUNG erfüllt).

---

## Tests-Plan (Source-Level + Smoke)

1. **T1** — `add_info("⚠ Test")` → `_append_two_color` mit `#FF6600` aufgerufen.
2. **T2** — `add_info("✓ Test")` → `_append_two_color` mit `#00CC66`.
3. **T3** — `add_info("✗ Test")` → `_append_two_color` mit `#FF4444`.
4. **T4** — `add_info("⏳ Test")` → `_append_two_color` mit `#44BBFF`.
5. **T5** — `add_info("normale Info")` → `_append_colored` Default.
6. **T6** — `add_info("")` → kein Crash (Empty-Guard).
7. **T7** — `_SYMBOL_COLORS` enthält genau {⚠, ✓, ✗, ⏳} (Konvention-Lock).
8. **T8** — `mw_tx.py:_tune_post_swr_check` enthält Substring `"ODER SWR-Limit"`.
9. **T9** — `mw_radio.py` enthält KEIN `QDialog` mehr in `_show_calibration_done`.
10. **T10** — `_show_calibration_done(band, 25, None)` ruft `add_info` mit
    `"✓ Kalibrierung 20m gespeichert. ANT1: 25 dB"`.
11. **T11** — `_show_calibration_done(band, 25, 30)` ruft `add_info` mit
    `"... ANT1: 25 dB | ANT2: 30 dB"`.
12. **T12** — Punkt 4 (V2-pflichtig falls Pfad bestätigt): Auto-TUNE-Fail-
    Branch ruft `qso_panel.add_info(...)`.

---

## Offene Fragen für V2/R1

1. **Punkt 4 Pfad-Verifikation:** ist der Auto-TUNE-Fail-Pfad (mw_tx:391-396)
   wirklich ohne `add_info` für den User? Source-Check pflicht.
2. **`add_qso_complete` / `add_timeout`** rendern Symbol+Text einheitlich mit
   einer Farbe — Soll das auch auf Variante B (Symbol-Color-Split) umgestellt
   werden für Konsistenz? V2-Frage. Vermutlich nein (sind keine `add_info`-
   Pfade und haben eigene Farbgebung).
3. **`_INFO_REST_COLOR = #888888` vs. heutiges `#666666`:** Lesbarkeits-
   Gewinn vs. „bewusst dezent für unwichtige Infos". Mike-Beobachtung deutet
   auf zu dunkel. Werte-Vorschlag offen für DeepSeek-Bewertung.
4. **Test-Mock-Strategie:** Source-Level-Tests via `inspect.getsource` +
   regex (analog P55/P76-C) oder Qt-Smoke mit `QT_QPA_PLATFORM=offscreen`?
   Smoke ist hier vermutlich besser (Color-Argumente per spy abfangen).

---

## Push-Plan (nach Final-R1 OK)

P79 wird als v0.97.51 gebündelt. Nach Field-Test F1-F5 (siehe V3 §5)
Push pending v0.97.40-50 + v0.97.51 zu GitHub. **Erst Field-Test**, nicht
sofort — gilt unabhaengig wie klein die Aenderung wirkt.

---

**Naechster Schritt:** V2 (Self-Review) — Hauptpunkte zu pruefen:
- Halluzinations-Check: alle Zeilen-Nummern + Methodennamen via grep
  verifizieren (mw_tx:401-405, mw_radio:1681-1731, qso_panel:298-300).
- Punkt 4 Pfad-Audit gegen Code.
- `_SYMBOL_COLORS` Farben gegen vorhandene Farb-Werte in qso_panel
  pruefen (✓-Farben heute `#44FF44`, sollen wir auf `#00CC66` umstellen
  oder bei `#44FF44` bleiben? V2 entscheidet).
