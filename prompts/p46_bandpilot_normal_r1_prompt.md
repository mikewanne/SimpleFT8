# R1-Review fuer P46 — Bandpilot Normal-Reintegration

Du bist erfahrener Python-/PySide6-Engineer + UX-Bewerter. **Du loest
das Problem NICHT — du kritisierst und verbesserst den Plan.**

## Kontext (FT8-Funk-Tool SimpleFT8, v0.97.16 → 0.97.17, Hobby-Funker-Tool)

**Mike's Strategie-Wechsel:**
- 11.05.2026 P35-Bug-E: Bandpilot wurde so eingebaut dass er Normal-Modus
  NIE empfiehlt (`current == "normal"` → skip, `target == "normal"` → skip).
  Grund: damalige Vorsicht.
- 12.05.2026 P46: Vision-Wechsel — „ganz oder gar nicht, wenn schon Pilot
  dann alle 3 Modi". 95% der Faelle gewinnt Normal nicht, aber die
  5% Spezialfaelle (17m/12m duenne Daten, 20m resonante Antenne ruhige
  Stunden, Single-Antenna-Setups) rechtfertigen den Aufwand.

**Code-Realitaet vorher:**
- `core/mode_recommender.py` macht bereits 3-Wege-Vergleich (alle 3 Modi)
- `ui/bandpilot_dialogs.py` zeigt schon alle 3 Modi
- NUR `ui/mw_radio.py:774-779` + `:811-816` blockieren Normal als
  Empfehlungs-Ziel
- Bestehende Tests in `tests/test_mw_radio_bandpilot.py` umgehen
  P35-Bug-E mit `current="diversity_normal"` Workaround

## Was V3 (geplant) macht

**Code-Aenderung:**
1. `mw_radio.py:774-779` entfernen — Normal-skip in `_maybe_apply_bandpilot`
2. `mw_radio.py:811-816` entfernen — Normal-block in `_apply_bandpilot_auto`

**Tests:**
3. Bestehende 4 Tests: Workaround-Kommentare raus, `current="normal"` wo sinnvoll
4. 6 neue Tests in `tests/test_p46_bandpilot_normal.py`:
   - T1 Auto: current=normal, top1=diversity_dx, switch → wechselt
   - T2 Auto: current=diversity_dx, top1=normal, switch → wechselt zu **normal** (vorher geblockt!)
   - T3 Auto: current=normal, top1=normal, no_change → nichts
   - T4 Manual: current=normal → Dialog
   - T5 Manual: current=diversity_dx, top1=normal → Dialog, Normal-Button waehlbar
   - T6 Auto: TX laeuft + target=normal → defer + tx_finished → wechselt

**Doku:** `docs/explained/bandpilot_de.md` + `.md` (falls existiert) + HISTORY + Memory.

## Verifikationen aus V2

- `_set_rx_mode_direct("normal")` ruft `_disable_diversity()` BEVOR
  Normal aktiv setzt → Diversity-State-Cleanup ist sauber
- P35-Bug-F (App-Start IMMER 20m FT8 Normal) ist in `main_window.__init__`,
  **orthogonal** zum Bandpilot-Pfad — wird NICHT veraendert
- Cache `~/.simpleft8/bandpilot_hourly.json` enthaelt schon Daten ueber
  alle 3 Modi (P35-Bug-E hat nur UI-Filter geblockt, nicht Aggregator)
- Manual-Dialog `BandpilotManualDialog` iteriert ueber alle 3 Modi und
  erzeugt Buttons — Normal-Button-Click ruft `_select("normal")` → `accept()`,
  `_apply_bandpilot_manual` macht `_set_rx_mode_direct("normal")`. Funktioniert.

## Deine Aufgabe (Kritik des Plans)

1. **Strategie-Wechsel akzeptabel?** Mike geht von „Bandpilot empfiehlt
   nie Normal" zu „darf alles". Risiken die V1/V2 uebersehen?
2. **Reicht es die 2 Skip-Bloecke zu entfernen?** Oder gibt's noch
   andere Stellen wo Normal blockiert wird?
3. **Edge-Cases:** Was passiert bei Bandpilot-Auto, current=normal,
   Manual-Dialog-Cancel, TX-Verzoegerung, Band-Wechsel waehrend
   pending? V1/V2 sind das durchgegangen.
4. **Tests T1-T6 ausreichend?** Was fehlt?
5. **Test-Anpassung der bestehenden Tests** (Workaround-Kommentare
   raus): sind das echte Verhaltens-Aenderungen oder reine Kosmetik?
6. **Bandpilot-Recommender-Schwellen:** `MIN_DAYS_HOUR=3 + MIN_CYCLES_HOUR=20`
   — bei Single-Antenna-Setups (keine Diversity-Daten) liefert
   Recommender `None`. Reicht das als Sicherheits-Netz?
7. **UX:** Bei Bandwechsel kommt Toast „Bandpilot wechselt zu Normal".
   Konsistent mit anderen Toasts? Verwirrend fuer User die seit P35
   gewohnt sind dass Normal ihre Wahl ist?
8. **Versions-Bump:** 0.97.17 OK? Oder ist Strategie-Wechsel ein
   minor-Bump (0.98.0)?

## Format

Tabelle:

| Schwere | Finding | Datei:Zeile | Empfehlung |

Schweregrade:
- **KRITISCH** — Plan muss geaendert werden, Push blockiert
- **SOLLTE-FIX** — Plan-Verbesserung empfohlen, kein Blocker
- **KOENNTE** — Optional
- **HINWEIS** — Info, keine Aktion

Am Ende: **Gesamtbewertung 1-10** und **„Code-Schreiben freigegeben"** /
**„Plan muss erst X machen"**.

Brutal-ehrlich. P46 ist UX-Strategie-Aenderung — Konsequenzen lieber
jetzt diskutieren als nach Push.
