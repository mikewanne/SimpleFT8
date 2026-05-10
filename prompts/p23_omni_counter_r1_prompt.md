# R1-Auftrag: Kritischer Review von P23.OMNI-COUNTER-EIGEN V2

## Deine Rolle

Du bist DeepSeek-Reasoner und reviewst einen Implementierungsplan
(V2) — NICHT den Code selbst (existiert noch nicht). Dein Ziel: den
Plan kritisieren und konkret verbessern, bevor er umgesetzt wird.

**Du sollst NICHT die Probleme loesen, sondern den Plan kritisieren.**

## Kontext: SimpleFT8 OMNI-CQ

OMNI-CQ ist Mike's automatischer CQ-Modus: ruft kontinuierlich CQ in
EINER Slot-Paritaet (Even ODER Odd), wechselt periodisch zur anderen
Paritaet. Heute (P7, v0.96.4) wird die Wechsel-Trigger ueber den
Diversity-Such-Counter abgeleitet (alle ~10 Min). Mike will das
auflösen — eigener Counter im OMNI selbst, sichtbar im Display.

**Mike-Spec 10.05.2026:**
- Counter pro Modus: FT8=10, FT4=20, FT2=40 (alle ~5 Min Wallclock)
- Counter zaehlt DOWN nach jedem TX. Bei 0: flip + reset auf TARGET.
- QSO eingehend → Counter Reset auf TARGET (positiv-Verstaerkung)
- Antennen-Mess fertig → Counter Reset auf TARGET
- Bandwechsel/Modus-Wechsel → OMNI STOP (wie heute)
- Display: `13:30:45 [O] →  Sende   CQ DA1MHH JO31  ↻10`

## Was du bekommst

1. **V2-Plan** (siehe unten)
2. **`core/omni_cq.py`** — komplettes Modul (246 Zeilen, der zu refactorn ist)
3. **`ui/mw_cycle.py`** — Auszug Hook-Pfad (`_refresh_diversity_freq_view`,
   `_handle_diversity_measure`)
4. **`ui/qso_panel.py`** — der `add_tx`-Bereich
5. **`ui/mw_qso.py`** — `_on_tx_started`
6. **`ui/main_window.py`** — `_on_omni_cq_count_changed`
7. **`tests/test_omni_cq_signal.py`** — bestehende Tests die migrate werden

## Was du pruefen sollst

### A. Architektur

A1. Counter-Down + Auto-Flip in `on_cycle_start` korrekt? Edge-Case wenn
    `_cq_remaining` waehrend Auto-Flip mit anderem Code-Pfad kollidiert?
A2. `reset_counter_after_measure` no-op-Logik (nicht aktiv ODER paused)
    sinnvoll? Edge-Case wenn `paused` aber Mess fertig wird?
A3. `_get_target` nur in `start()` — wirklich sicher dass Modus
    waehrend OMNI-Lifecycle nicht wechseln kann? mw_radio.py:212 ruft
    `stop("mode_change")` — hat irgendein anderer Pfad eine Chance,
    `_timer.mode` zu aendern ohne OMNI zu stoppen?
A4. `_cq_target` wird in `stop()` auf `_OMNI_DEFAULT_TARGET` resettet.
    Beim naechsten `start()` neu aus `_get_target()` gesetzt. Sicher
    dass kein Stale-Target uebrig bleibt?

### B. Race-Conditions

B1. `on_cycle_start` und `reset_counter_after_measure` werden beide aus
    GUI-Thread gerufen (Qt-Slots). Race?
B2. Bei Auto-Flip in `on_cycle_start`: `flip_tx_parity()` emittiert
    `parity_flipped`. Direkt danach setzt `on_cycle_start`
    `_cq_remaining = _cq_target` und emittiert `cq_count_changed`. UI-
    Reihenfolge garantiert?
B3. Was wenn `pause()` zwischen `_cq_remaining -= 1` und
    `cq_count_changed.emit` gerufen wird (theoretisch)? Counter-Wert
    konsistent?

### C. Display

C1. `add_tx` mit `omni_remaining` und `ant_label` zusammen — V2 sagt
    `_append_three_color` (existiert das?). Was wenn nicht? Fallback
    sauber?
C2. Suffix `  ↻N` — Symbol ↻ ist U+21BB (Unicode). Funktioniert in
    Qt-Text-Rendering offscreen + nativ? Kein Font-Fallback-Risiko?
C3. Counter im Statusbar wechselt von "0" niemals (durch Auto-Flip-
    sofort-Reset). UI sieht nur 1 → TARGET. Kein "0"-Flicker — V2-L2
    erfuellt?

### D. Migration

D1. Tests die `cq_count_changed` mit 2-Arg-Lambda lauschen — bleiben
    unveraendert (V2-L4: Format bleibt `(int, bool)`). Verifizieren dass
    semantischer Wechsel (count → remaining) keine Test-Asserts kippt.
D2. `on_search_trigger`-Tests aus `test_omni_cq_signal.py` (T8, T8b, T14)
    — entfernen oder als Negative-Tests umbauen?
D3. Existing Field `_cq_count` Property — durch `_cq_remaining` ersetzt.
    Andere Code-Stellen die `omni.cq_count` lesen? V2 hat `cq_remaining`
    als neue Property.

### E. Tests V2

E1. Decken T1-T16 die kritischen Pfade ab? Fehlt etwas? Spy-Pattern (statt
    E2E mock-heavy)?
E2. T7 `test_remaining_reaches_zero_triggers_flip_and_reset` — wie
    verifizieren dass NUR EIN Emit pro Slot kommt (kein Zwischen-0-emit)?
E3. T15 `qso_panel.add_tx` Whitebox — Helpers (`_append_three_color` etc.)
    via Spy oder direkt rendered Text pruefen?

### F. KISS

F1. Ist V2 angemessen schlank fuer Hobby-Tool? Oder ist die Mess-Reset-
    Logik (A4) overengineered?
F2. `_OMNI_DEFAULT_TARGET = 10` Fallback fuer unbekannte Modi —
    Verteidigungslinie noetig oder YAGNI?
F3. Sollte `cq_count_changed` Signal-Format bewusst auf `(int, int, bool)`
    umgestellt werden mit `target` mit-emittiert? Oder bleibt `(int, bool)`
    (Backwards-Compat) wie V2 sagt? Welche Variante ist sauberer?

## Form deiner Antwort

- **KRITISCH** (Bug im Plan, muss in V3 raus): konkret + Datei:Zeile
- **SOLLTE** (Verbesserung empfohlen): konkret + Begruendung
- **KOENNTE** (Optional): kurz
- KISS-Bewertung am Ende

Halluzination vermeiden: bei Behauptungen ueber Code, Datei:Zeile-
Verweis. Wenn du es nicht siehst, sag „nicht im uebersendeten Code".

---

## V2-Plan (Anhang)

[V2-Inhalt wird vom CLI angehaengt]
