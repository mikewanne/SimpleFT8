# P79 — UI-Bundle V3 (Final-Spec nach V1→V2→R1)

**Status:** V3 (Final-Spec für Code-Phase).
**Datum:** 2026-05-18 nach Compact.
**R1-Bilanz:** 9 Findings (0 ROT, 1 ORANGE F6, 3 GELB, 5 WEISS) — alle
übernommen, Mike-Freigabe „du machst das super".
**V4-pro-Cycle:** 26 (nach 25 0-Hallu-Cycles).

---

## Acceptance Criteria

### AC1 — `qso_panel.add_info` Auto-Detect (Patch 1)
- Modul-Konstante `_SYMBOL_COLORS` mit 4 Einträgen + Wartungs-Kommentar (R1-F1).
- `add_info` startet mit Empty-Guard `if not text: return` + 1-Zeilen-Kommentar (R1-F4).
- Symbol-Detection via `text.startswith(symbol)`-Loop (V2-F5, R1-F2 bestätigt).
- Bei Treffer: `_append_two_color(f"       {symbol}", color, rest, "#666666")`.
- Bei kein Treffer / kein Symbol: `_append_colored(f"       {text}", "#666666")` (heutiges Verhalten).

### AC2 — `mw_tx.py:401-405` Text-Erweiterung (Patch 2)
- Manueller TUNE-Bad-Pfad ersetzen durch:
  ```
  ⚠ Band {band} gesperrt — SWR {swr} > Limit {limit}.
  Antenne pruefen ODER SWR-Limit in Einstellungen anpassen
  ODER manueller TUNE zum Freischalten.
  ```
- Tuner-fehlt-Branch Z.407-411 UNVERÄNDERT.
- `_on_swr_alarm` (mw_tx:710) Text UNVERÄNDERT (separater Pfad).

### AC3 — `mw_radio._show_calibration_done` Modal → add_info + Statusbar (Patch 3)
- 50-LOC QDialog komplett ersetzen durch:
  ```python
  def _show_calibration_done(self, band, ant1_g, ant2_g):
      """P79: Kalibrierungs-Ergebnis als Live-Log-Zeile (Modal weg).

      Mike-Wunsch: weniger Popups, fluessigerer Workflow.
      Doppelte Anzeige (Log + Statusbar 3s) deckt Tab-Wechsel +
      Auto-Trim ab (R1-F6 ORANGE).
      """
      if ant2_g is not None:
          text = (f"✓ Kalibrierung {band} gespeichert. "
                  f"ANT1: {ant1_g} dB | ANT2: {ant2_g} dB")
      else:
          text = f"✓ Kalibrierung {band} gespeichert. ANT1: {ant1_g} dB"
      self.qso_panel.add_info(text)
      # R1-F6: Statusbar-Echo 3s — tab-uebergreifend sichtbar,
      # robust gegen QSO-Log-Trim. Non-blocking, kein Klick.
      try:
          self.statusBar().showMessage(text, 3000)
      except Exception:
          pass  # Statusbar evtl. nicht verfuegbar in Test-Smoke
  ```
- Aufrufer (Z.1660 + Z.1679) UNVERÄNDERT.
- Synergie-Effekt: ✓-Symbol wird durch Patch 1 grün gerendert.

### AC4 — Punkt 4 (Gain-Mess SWR → QSO-Log) AUSGENOMMEN
- Mike-Entscheidung 18.05.: erst Field-Test, dann Folge-Patch.
- Begruendung V2-F1: alle bekannten add_info-Pfade existieren bereits.

### AC5 — Tests
T1-T11 wie V2 + **T12 NEU (R1-F7 GELB):**
- T12: `add_info("⚠")` (Symbol-only ohne Rest) crasht nicht und ruft
  `_append_two_color` mit `rest=""`.

Tests via `inspect.getsource(method)` für Source-Level (R1-F-V2-F4).

### AC6 — Hardware-Pflicht
R1-F9 bestätigt: P79 reines UI, kein TX-Trigger, ANT1-Pflicht nicht beruehrt.

---

## Implementations-Reihenfolge (atomare Commits)

1. **C1** `ui/qso_panel.py` — `_SYMBOL_COLORS` + `add_info`-Refactor.
2. **C2** `tests/test_p79_ui_bundle.py` NEU — T1-T7 (qso_panel-Tests).
3. **C3** `ui/mw_tx.py:401-405` — Text-Erweiterung Patch 2.
4. **C4** Tests T8 (mw_tx Source-Level).
5. **C5** `ui/mw_radio.py:1681-1731` — `_show_calibration_done` Refactor.
6. **C6** Tests T9-T12 (mw_radio Source-Level + Smoke + Edge).
7. **C7** APP_VERSION 0.97.50→0.97.51 in `main.py` + Backup.
8. **C8** HISTORY+HANDOFF+CLAUDE+TODO Update.

---

## Field-Test-Plan (V3 §5)

**F1** — App-Start, `add_info("⚠ Test")` via Console feuern → orange Symbol sichtbar.
**F2** — App-Start, `add_info("✓ Test")` → grünes Symbol sichtbar.
**F3** — TUNE auf gesperrtem Band → neue 3-Optionen-Text in qso_panel.
**F4** — Kalibrierung Normal durchlaufen → KEIN Modal, statt dessen
   ✓-Zeile in qso_panel + 3s Statusbar-Echo.
**F5** — Kalibrierung Diversity → ✓-Zeile mit ANT1 + ANT2 Werten.
**F6** — Während Kalibrierung Tab auf Logbuch → nach Fertig zurueck auf QSO:
   ✓-Zeile da, Statusbar war flüchtig (3s) → robust.

---

## Push-Plan

P79 als v0.97.51 lokal gebündelt. Nach Field-Test F1-F6 ✓ → Push
v0.97.40-50 + v0.97.51 zu GitHub (in einem Push, 11+1 Commits ahead).
Vorher Debug-Cleanup (P76-DBG-Prints raus).

---

## LOC-Bilanz Final

| Datei | Aenderung | LOC |
|---|---|---|
| `ui/qso_panel.py` | `_SYMBOL_COLORS` Konstante + add_info-Refactor | +18 |
| `ui/mw_tx.py:401-405` | Text-Erweiterung | +2 |
| `ui/mw_radio.py:1681-1731` | Modal raus, add_info + Statusbar | -42 |
| `tests/test_p79_ui_bundle.py` NEU | 12 Tests | +120 |
| `main.py` | APP_VERSION | +1/-1 |
| **Netto Code** | **-22 LOC** | (Schlanker!) |
| **Netto + Tests** | **+98 LOC** | |

---

**Naechster Schritt:** C1 Code-Patch — `ui/qso_panel.py`.
