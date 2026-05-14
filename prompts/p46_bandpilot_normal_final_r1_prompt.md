# Final-R1 Review fuer P46 (deepseek-reasoner)

V1→V2→R1 (8/10, 1 KRITISCH + 2 SOLLTE + 1 KOENNTE) → V3 alle Findings
uebernommen → Code → JETZT Final-R1.

## Was wurde umgesetzt

**Aenderungen `ui/mw_radio.py`:**

1. **Maßnahme A** — `_maybe_apply_bandpilot` Z.774-779 `if current == "normal": return False` GELOESCHT
2. **Maßnahme B** — `_apply_bandpilot_auto` Z.811-816 `if target == "normal": return False` GELOESCHT
3. **Maßnahme C** (R1-F2) — `_set_rx_mode_direct` `target == "normal"`-Pfad refactored: bei `_rx_mode == "diversity"` wird `_disable_diversity()` einmal aufgerufen (macht alles inkl. `_apply_normal_mode`), nicht mehr Doppelaufruf
4. **Maßnahme D** (R1-F3) — `_apply_bandpilot_auto` speichert `current` zusaetzlich im pending-Tupel (5-elementig). `_on_bandpilot_tx_finished` prueft Konsistenz mit aktuellem Modus, verwirft pending bei Aenderung

**Tests `tests/test_mw_radio_bandpilot.py`:**

5. 2 P35-Bug-E-Tests GELOESCHT (`test_bandpilot_skips_when_current_is_normal`, `test_bandpilot_rejects_normal_target`) — testeten alte Block-Logik
6. 4 Workaround-Kommentare bereinigt (P35-Bug-E-Hinweise raus)
7. 2 bestehende TX-finished-Tests: 5-Tupel + `_current_rx_mode_string`-Mock ergaenzt

**Neue Tests `tests/test_p46_bandpilot_normal.py` — 8 Tests:**

- T1 Auto current=normal → switch zu diversity_dx ✅
- T2 Auto current=diversity_dx → switch zu **normal** (vorher geblockt!) ✅
- T3 Auto current=normal, no_change → nichts ✅
- T4 Manual current=normal → Dialog ✅
- T5 Manual current=diversity_dx, top1=normal, User waehlt normal ✅
- T6 Auto TX laeuft, target=normal → defer + 5-elementiges pending ✅
- T7 (R1-F4) Auto current=normal + rec=None → Statusbar-Hinweis ✅
- T8 (R1-F3) TX-pending verworfen wenn User Modus geaendert hat ✅

**Test-Bilanz:** 1227 → 1233 grün (+8 P46 −2 geloescht +2 angepasst).

**APP_VERSION:** 0.97.16 → 0.97.17

## Verifikationen

- `_set_rx_mode_direct("normal")` ruft `_apply_normal_mode()` jetzt
  GENAU 1× (nicht 2×). Code-Review Z.726-737.
- `_bandpilot_pending` ist konsistent 5-elementig sowohl beim Schreiben
  (Z.829) als auch beim Lesen (Z.853).
- P35-Bug-F (App-Start IMMER 20m FT8 Normal) ist NICHT angefasst —
  bleibt in `main_window.__init__`, orthogonal zum Bandpilot-Pfad.
- Cache `bandpilot_hourly.json` unveraendert — `aggregate_stats_by_hour`
  hat schon immer alle 3 Modi aggregiert.

## Pruefe bitte

1. **R1-F1 (KRITISCH) erfuellt?** Beide alten Tests geloescht statt umgeschrieben, neue T1+T2 decken Pfad ab. Sauber?
2. **R1-F2 (SOLLTE) erfuellt?** Doppelaufruf weg, sauber refactored?
3. **R1-F3 (SOLLTE) erfuellt?** 5-Tupel-Konsistenz an allen Stellen?
4. **R1-F4 (KOENNTE) erfuellt?** T7 deckt Pfad ab?
5. **Side-Effects:** Manual-Dialog-Cancel-Pfad bei Normal — funktioniert?
6. **Backward-Kompat:** Existierende `_bandpilot_pending`-Tupel von
   vor v0.97.17 koennen NICHT existieren (nur runtime-State, keine
   Persistenz). OK?
7. **Doku-Datei:** `docs/explained/bandpilot_de.md` — existiert die?
   Sollte Hinweis auf Normal-Empfehlung enthalten?
8. **App-Start-Pfad:** `_maybe_apply_bandpilot` wird beim App-Start
   nicht aufgerufen (nur bei Band-Wechsel-Hook). Verifiziert?

## Format

Tabelle:

| Schwere | Finding | Datei:Zeile | Empfehlung |

KRITISCH (Push-Blocker) | SOLLTE-FIX | KOENNTE | HINWEIS

Am Ende: **Gesamtbewertung 1-10** + **„Push freigegeben"** oder
**„Push blockiert wegen X"**.

Brutal-ehrlich. P46 ist UX-Strategie-Aenderung, Konsequenzen jetzt
besser klären.
