# P1.CACHE-SIMPLE V2 — Self-Review

**Stand:** 2026-05-07.
**Workflow:** V1 → **V2 (diese Datei)** → R1 → V3 → Compact → Code.
**Aufgabe:** V1 als „frische KI" reviewen.

---

## L1 — V1 §4.2 erfindet neuen Dialog-Typ — DXTuneDialog macht das schon

V1 schlägt `ui/gain_measure_progress_dialog.py` (NEU) als Progress-
Dialog mit Abbruch vor. Aber:

`DXTuneDialog` (`ui/dx_tune_dialog.py`, instanziiert in
`mw_radio.py:1183`) ist **schon** non-modal, immer im Vordergrund mit
GUI-Lock + `accepted`/`rejected`-Signals (Z.1195-1197). Dialog hat
sehr wahrscheinlich Cancel-Button (klassisch QDialog-Reject).

**V2-Korrektur:** kein neuer Dialog. Bestehender DXTuneDialog
übernimmt die Rolle „Gain-Messung läuft, Abbruch möglich".
Verifizierung am Code in V3 Pflicht. Falls DXTuneDialog Wahl-Buttons
hat („OK / Abbrechen / Skip"), evtl. minimaler Refactor zu „nur
Abbrechen".

---

## L2 — V1 verpasst: `_on_dx_tune_rejected` führt zu Endlos-Pipeline

`mw_radio.py:1364-1383`: bei Cancel wird:
1. Pending-Flags reset
2. TX abort
3. `_enable_diversity(scoring_mode=scoring)` aufgerufen → **triggert
   wieder `_check_diversity_preset`** → wenn Cache-Reuse fehlschlägt
   → wieder Pipeline → Endlos-Schleife

**V2-Korrektur:** Bei Cancel mit „mit alten Werten weiter"-Semantik
muss eine Stale-Acceptance-Pfad existieren:
- Wenn alte Werte vorhanden (auch >Frist) → laden, Cache-Reuse mit
  expired-Override
- Wenn gar keine Werte → Diversity-Modus deaktivieren, zurück auf
  Normal mit Hinweis

V3 muss neuen Pfad „lade-trotz-abgelaufen-bei-Cancel" einbauen.
PresetStore braucht ggf. Methode `get_with_expired_ok(band, mode)`.

---

## L3 — V1 unklar: was passiert bei „Ratio frisch + Gain abgelaufen"?

V1 §3.2 sagt „Gain-Refresh wird im Hintergrund/separat angestoßen".
Aber im echten Code:
- `_enable_diversity(cached_ratio=...)` setzt Diversity-Mode auf
  operate, kein Gain-Refresh
- Wenn Gain abgelaufen ist sind die ANT1/ANT2-Verstärker auf alten
  Werten = potentiell schief

**V2-Klärung:** 2 Optionen:
- **A)** Gain-Messung sofort nach Cache-Reuse triggern. Diversity läuft
  während ~3 Min Gain-Phase mit alten Werten weiter. Nach Gain neu:
  Werte werden korrigiert.
- **B)** Cache-Reuse **lehnt ab** wenn Gain abgelaufen → Pipeline
  startet → Gain neu, Ratio aus Cache übernehmen (kein Phase 3).

**V2-Empfehlung B** (sauberer, KISS): wenn Gain abgelaufen → Auto-
Mess-Dialog (= DXTuneDialog) für Gain-Phase. Phase 3 wird übersprungen
weil Ratio aus Cache. Mike's „beide unabhängig" passt zu B weil
Reihenfolge erst Gain, dann Ratio-aus-Cache.

R1 darf das überstimmen — V2-Empfehlung nicht final.

---

## L4 — V1 §3.4 Auto-Mess-Dialog vs DXTuneDialog Status-Anzeige

DXTuneDialog hat vermutlich Phase-Indikator („Phase 1/2/3", Progress-
Bar, ZyklenZähler). Wenn Phase 3 übersprungen wird (Ratio aus Cache),
muss Dialog am Ende „Fertig"-Status zeigen, nicht erwarten dass Phase
3 läuft.

**V2-Korrektur:** Code-Verifikation in `dx_tune_dialog.py` ob Dialog
mit nur-Phase-2-Modus klarkommt. Evtl. neuer Modus `mode="gain_only"`
nötig.

---

## L5 — V1 verpasst: Statusbar-Hinweise bei Auto-Mess

V1 §3.3 sagt „Status-Bar/Histogramm zeigt 'Diversity wird neu
eingemessen'". Wo genau? Aktuell zeigt Statusbar nur Connection-State.
Histogramm zeigt FT8-Frequenzen, nicht Mess-Phase.

**V2-Klärung:** DXTuneDialog ist sichtbar im Vordergrund während
Messung. Brauchen wir extra Statusbar-Text? KISS-Antwort: Nein —
Dialog ist groß und sichtbar. Statusbar bleibt unverändert.

V3 entscheidet final.

---

## L6 — V1 §6 Out-of-Scope erweitern

V1 listet einige Out-of-Scope. V2 ergänzt:
- **DXTuneDialog-Refactor:** falls Dialog UI-Anpassung braucht (Mode
  „nur Gain"), das ist im Scope. Falls nicht: stays as-is.
- **Backward-Compat-Tests:** existierende Cache-Reuse-Tests müssen
  invertiert werden (Gain-Check raus). V1 erwähnt das in §4.4 aber
  nicht explizit als „im Scope".

---

## L7 — V1 §7 Tests-Liste — Settings-Mock-Pattern fehlt

V1 listet 6 Tests aber nicht das Mock-Pattern. PresetStore braucht
testbare Stub mit kontrollierbaren Timestamps.

**V2-Korrektur:** Tests sollten `monkeypatch.setattr(time, 'time', ...)`
oder `freezegun` nutzen, um Cache-Alter exakt zu steuern. Bestehende
Cache-Reuse-Tests in `tests/test_diversity_cache_reuse.py` zeigen
vermutlich das Pattern — V3 dort grep'en.

---

## L8 — V1 fehlt: bestehender Toast-Cleanup ist Teil dieses Bundles

V1 §1.A erwähnt dass Toast-Klasse + Test bereits gelöscht sind, aber
die Änderungen sind **nicht committed** (Mike will alles in einem
Rutsch). V3 muss dokumentieren:

- `ui/diversity_cache_toast.py` gelöscht
- `tests/test_diversity_cache_reuse.py` Smoke-Test entfernt
- `mw_radio.py:957-968` Toast-Aufruf entfernt
- `_try_diversity_cache_reuse` `scoring_label`-Variable entfernt (war
  nur für Toast)

Plus die aktuellen un-commited Änderungen aus dem Default-Label-Fix
(„QSO Finish") gehören nicht zu diesem Bundle (sind committed in
86ae475 + gepusht).

---

## L9 — V1 fehlt: Compact-Strategie

Mike geht essen, will Compact nach V3. Pattern aus P1.AP-FIX +
P1.ANTENNE-COLLAPSE: Memory-File für post-Compact-Wiedereinstieg
schreiben.

**V3 muss enthalten:**
- Alle Diffs konkret mit Datei:Zeile-Range
- Memory-File `project_p1_cache_simple_in_progress.md` Vorbereitung
- Implementations-Reihenfolge

---

## L10 — V1 verpasst: Mode-Wechsel innerhalb Diversity (Standard ↔ DX)

V1 fokussiert auf Bandwechsel. Aber Mode-Wechsel innerhalb Diversity
(z.B. Standard → DX) triggert auch `_check_diversity_preset` mit
neuem `scoring`-Wert. Cache ist pro `scoring` separat.

**V2-Klärung:** Logik gilt analog. Standard-Cache und DX-Cache
unabhängig prüfen. Kein Sonderfall.

---

## L11 — V1 verpasst: Edge-Case „erste Aktivierung Diversity nie kalibriert"

Wenn User Diversity zum ersten Mal aktiviert (kein Cache vorhanden):
- `is_valid_ratio` False, `is_valid_gain` False
- Volle Pipeline läuft → DXTuneDialog erscheint
- Mike's Vision passt: Default-Verhalten ist Messung, Abbruch möglich

**V2-Bestätigung:** Kein Eingriff nötig, aktueller Pfad funktioniert
in der neuen Logik.

---

## L12 — Zusammenfassung der V2-Korrekturen für V3

1. **DXTuneDialog wiederverwenden** statt neuen Progress-Dialog (L1)
2. **Cancel-Pfad mit Stale-Acceptance** ausbauen (L2)
3. **Pfad „Ratio frisch + Gain abgelaufen":** Option B — DXTuneDialog
   für Gain-only, Ratio aus Cache, Phase 3 skip (L3)
4. **DXTuneDialog evtl. mit `mode="gain_only"` erweitern** (L4)
5. **Keine Statusbar-Hinweise** — DXTuneDialog ist sichtbar genug (L5)
6. **Backward-Compat-Tests** explizit im Scope (L6)
7. **Settings-Mock + Time-Mock-Pattern** klären (L7)
8. **Toast-Cleanup gehört zu diesem Bundle** (L8)
9. **Compact-Strategie** (L9)
10. **Mode-Wechsel** unverändert (L10)
11. **Erste Aktivierung** unverändert (L11)
12. **HISTORY/HANDOFF/CLAUDE/TODO/Memory** als Pflicht-Schritt einplanen

---

## Pruefauftraege fuer R1

1. **DXTuneDialog wiederverwenden:** Hat der Dialog Cancel-Button,
   Phase-Indikator, kann „nur Gain" laufen? Code in
   `ui/dx_tune_dialog.py` prüfen.
2. **Stale-Acceptance-Pfad bei Cancel:** Wie sauber implementieren?
   Neue Methode `_load_stale_or_disable()` in mw_radio.py?
3. **Pfad „Ratio frisch + Gain abgelaufen":** Option A (Hintergrund-
   Refresh) vs B (Sequential: erst Gain, dann Ratio aus Cache)?
4. **`_check_diversity_preset` Refactor-Plan:** alle Pfade konsolidieren
   in eine Funktion oder zwei (Ratio-Check, Gain-Check)?
5. **PresetStore-API:** Brauchen wir `get_with_expired_ok()` für
   Stale-Acceptance, oder reicht direktes `entry = store.get(...)`?
6. **Test-Coverage:** 6 Tests aus V1 + Backward-Compat-Updates reichen?
7. **Race-Conditions:** während Gain-Phase läuft, kommt Bandwechsel —
   sauber abfangen?
8. **Compact-Plan:** Diffs konkret in V3, Reihenfolge festlegen.

---

**Workflow-Status:** V2 fertig. Weiter mit R1.
