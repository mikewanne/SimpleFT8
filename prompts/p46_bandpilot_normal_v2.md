# P46 — Bandpilot Normal-Reintegration (V2 Self-Review, 13.05.2026)

**V2-Auftrag:** Frische-KI-Review von V1 — was uebersieht V1? Welche
Annahmen halluziniert V1? Was wuerde R1 sofort bemaengeln?

---

## V2-Findings (kritische Selbst-Pruefung)

### L1 — V1 untersucht NICHT die Settings-Migrations-Spur

`core/mode_recommender.py:29` verweist auf
`config/settings.py:_migrate_bandpilot_settings_v088`. V1 sagt
„KEIN Touch" zu Migration, hat aber nicht verifiziert ob die Migration
Normal als legitimen Wert akzeptiert.

→ V3: Migration kurz pruefen — laesst sie alle 3 Modi durch?

### L2 — V1 vergisst dass `_current_rx_mode_string()` einen 4. Wert liefern kann

`_current_rx_mode_string` kann auch `None` returnen (waehrend
dx_tuning). V1 erklaert das in der Doku (Z.770-772) aber:
- Test T1-T5 setzen explizit `current="normal"` oder `current="diversity_dx"` → OK
- Aber: was wenn jemand spaeter einen 4. Modus einfuehrt? Aktuell nur
  3 Strings im Code-Pfad.

→ V3: keine Aktion. Definierte Strings, Defensive-`None`-Behandlung
schon in mw_radio.py:770-772.

### L3 — Was passiert bei MANUAL-Modus wenn User Normal-Button waehlt?

Manual-Dialog `bandpilot_dialogs.py:177-184` iteriert ueber `rec["ranking"]`
und erstellt fuer JEDEN Modus einen Button (auch Normal). Click ruft
`_select(mode_code)`, was `self.chosen = mode_code; self.accept()`.

`_apply_bandpilot_manual` Z.866-872 prueft dann:
```python
chosen = self._show_bandpilot_manual_dialog(...)
if chosen is None or chosen == current:
    return False
self._set_rx_mode_direct(chosen)
return True
```

Ohne P46-Block ist `chosen="normal"` legitim → `_set_rx_mode_direct("normal")` wird aufgerufen. **Funktioniert.**

→ V3: T5 verifiziert das.

### L4 — `_set_rx_mode_direct("normal")` Pfad pruefen

V1 nimmt an dass `_set_rx_mode_direct` einen `"normal"` String akzeptiert.
Pruefen — irgendwo gibt es vielleicht einen Switch der nur Diversity
behandelt.

→ V3: Code-Verifikation pro grep — was macht `_set_rx_mode_direct("normal")`?

### L5 — V1 vergisst Audit der TOAST-Anzeige bei Normal-Switch

`BandpilotAutoToast` zeigt `chosen_label = USER_LABEL.get(rec["decision_mode"], rec["decision_mode"])`.
Bei `decision_mode="normal"` → `USER_LABEL["normal"]` = "Normal".
Toast zeigt korrekt „Normal gewaehlt (X.X Sta./Slot)". **Funktioniert.**

→ V3: keine Aktion, T-Validation reicht.

### L6 — Was passiert bei Auto-Wechsel zu Normal waehrend TX laeuft?

`_apply_bandpilot_auto` hat TX-Verzoegerungspfad ab Z.818-836:
```python
if not self.encoder.is_transmitting:
    # Sofort wechseln
    ...
# TX laeuft → verzoegern bis tx_finished
self._bandpilot_pending = (band, utc_hour, rec, target)
```

`target="normal"` wird gespeichert in `_bandpilot_pending`. Bei
`_on_bandpilot_tx_finished` Z.857: `self._set_rx_mode_direct(target)`.

→ Pfad funktioniert auch fuer Normal. T6 (NEU): TX-Verzoegerung mit
Normal als Target.

### L7 — Test-Mock `_make_mock_self` ist auf Diversity-Default

Helper-Funktion `_make_mock_self` in `test_mw_radio_bandpilot.py:23-45`
hat `is_transmitting=False` als Default, kein expliziter Modus-Pfad
fuer Normal. Sollte mit P46 weiter funktionieren weil Mock generisch
ist.

→ V3: keine Aktion. Tests T1-T6 nutzen Helper.

### L8 — Was wenn 24h-Cache veraltete Empfehlungen liefert die noch ohne Normal sind?

`HourlyBandpilotCache` hat TTL 24h. Wenn Cache vor P46 erstellt wurde
und Normal NICHT enthielt, wuerde Empfehlung Normal nicht kennen.

ABER: `aggregate_stats_by_hour` iteriert IMMER ueber alle 3 `CODE_MODES`
(Z.158). Cache-Eintraege haben also IMMER alle 3 Modi-Daten. P35-Bug-E
hat nur am UI-Filter geblockt, nicht am Aggregator.

→ V3: keine Cache-Invalidierung noetig. **Korrektheits-Anker:** Test
fuer aggregate_stats_by_hour vorhanden (test_bandpilot_md.py) testet
schon 3-Wege-Output.

### L9 — Toast/Dialog-Wording: ist "Normal" ein hinreichender Label?

Aktuell `USER_LABEL["normal"] = "Normal"`. Mike kennt seine Modi —
ausreichend. Keine Aenderung.

### L10 — `decision_mode == current_mode` Edge-Case

In `_maybe_apply_bandpilot` AUTO-Pfad: nach Entfernung des Skips wird
auch bei `current=normal` der Recommender befragt. Wenn der Recommender
„normal" als decision_mode zurueckgibt (top-1 = current), ist
`decision == "no_change"` → `_apply_bandpilot_auto` Z.807: `if rec["decision"] == "no_change": return False`. OK, kein Toast, kein Switch.

→ V3: T3 deckt das ab.

### L11 — Migration vom CACHE

Wenn Mike P46 installiert hat aber cache von 12./13.05. liegt schon
auf Platte: Cache hat Daten ueber alle 3 Modi. Recommender liefert
korrektes 3-Wege-Ranking. **Funktioniert ab Start.**

→ V3: keine Migration noetig.

### L12 — Mike's „App-Start IMMER 20m FT8 Normal" (P35-Bug-F)

V1 AK7 sagt orthogonal. **Verifikation:**
- `main_window.__init__` setzt initial 20m FT8 Normal (hardcoded)
- `_maybe_apply_bandpilot` wird VOM Band-/Modus-Wechsel-Pfad aufgerufen
- Beim App-Start passiert KEIN Band-Wechsel (Init = 20m FT8 Normal)

Aber: was wenn nach Init der Bandwechsel-Trigger feuert weil
Settings-Restore? Nein — P35-Bug-F hat das Restore aus Settings
abgeschaltet (commit `91728f7`).

→ V3: AK7 bleibt, kein zusaetzlicher Test fuer App-Start-Pfad noetig.

### L13 — `BandpilotManualDialog` ist `exec()`-blocking

Dialog ist modal (`.exec()`). Aktueller User-Workflow: Bandwechsel →
Modal blockt UI bis Auswahl. Bei Normal-Wechsel kein neuer Workflow,
funktioniert wie bisher.

→ V3: keine Aktion.

### L14 — V1 unterschaetzt Doku-Update-Scope

V1 sagt „falls Datei existiert" — pruefen:

```
docs/explained/bandpilot_de.md → existiert?
docs/explained/bandpilot.md (EN) → existiert?
```

Falls JA: aktualisieren ist Pflicht (Hobby-Funker-User-Doku).

→ V3: Files pruefen, ggf. inhaltliche Anpassung.

### L15 — V1 hat keinen Test fuer P35-Bug-F Erhalt (App-Start)

Risiko R3 erwaehnt Bug-F-Schutz, aber kein Test. Sollten wir einen
Smoke-Test schreiben dass App-Start IMMER 20m FT8 Normal bleibt?

→ Nein — das ist `main_window.__init__`-Verhalten, getestet durch
bestehende init-Tests (falls vorhanden). P46 modifiziert nicht
`main_window.__init__`.

### L16 — Was sagen die `_diversity_in_operate` / Diversity-State-Variablen?

Wenn Bandpilot von DX zu Normal switcht, sind diverse Diversity-State-
Variablen (Histogram, Queue, dynamic-Ratio-Buffer) noch im Diversity-
State. Wer cleant das?

`_set_rx_mode_direct("normal")` — was macht das? Lass uns das ansehen.

→ V3: grep nach `_set_rx_mode_direct` Implementation. Wenn da
Diversity-Stop saubere Logik hat → OK. Wenn nicht → potenzieller Bug.

**Das ist wahrscheinlich der wichtigste V2-Befund.**

---

## V2 → V3 Konsequenzen

1. **L4 + L16:** `_set_rx_mode_direct` pruefen — speziell Diversity→Normal-
   Uebergang. Wenn nicht clean: P46 koennte latent-Bug ausloesen wenn
   Bandpilot Normal vorschlaegt aus Diversity.
2. **L14:** `docs/explained/bandpilot*.md` pruefen + ggf. Doku.
3. **L6:** T6 NEU — TX-Verzoegerung mit Normal als Target.
4. Tests T1-T6 (statt T1-T5).

V3 muss vorab `_set_rx_mode_direct` verifizieren — ohne diese Aufklaerung
ist V3 nicht code-ready.

---

## Was R1 wahrscheinlich finden wird

- **KRITISCH:** L16 Diversity-State-Cleanup beim Wechsel zu Normal.
  Wenn `_set_rx_mode_direct("normal")` nicht sauber Diversity-Histogram
  + Queue resettet, ist das ein latent-Bug.
- **SOLLTE:** Test-Coverage fuer Manual-Dialog Normal-Klick (T5).
- **SOLLTE:** Doku-Update bandpilot.md.
- **KOENNTE:** P35-Bug-E Kommentare in Tests sind alt — Update.
- **HINWEIS:** P35-Bug-F Hinweis bleibt unveraendert.

V3 sollte L16 vor V3-Schluss klaeren.
