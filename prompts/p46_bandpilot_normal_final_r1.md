[deepseek] ~25549 Tokens, 2 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=28440 out=3663 total=32103
## Final-R1 Review P46 — Ergebnisse

**Code-Reviewer:** DeepSeek Reasoner  
**PR:** R1-Umsetzung (V1→V2→V3)  
**Stand:** v0.97.17, Tests 1227→1233 grün

---

### Ergebnis der 8 Prüfpunkte

| # | Punkt | Status | Begründung |
|---|-------|--------|------------|
| 1 | **R1-F1 (KRITISCH) – Block-Logik entfernt** | ✅ Erfüllt | Beide `if current/target == "normal": return False` gelöscht. Neue T1+T2 testen die freigegebenen Pfade korrekt. Code in `_maybe_apply_bandpilot` und `_apply_bandpilot_auto` enthält keine Filter mehr. |
| 2 | **R1-F2 (SOLLTE) – Doppelaufruf vermieden** | ✅ Erfüllt | `_set_rx_mode_direct("normal")` ruft bei `_rx_mode == "diversity"` genau 1× `_disable_diversity()` auf (das selbst `_apply_normal_mode` + `set_rx_mode` macht). Danach nur UI-Setter (`btn_diversity.setText`, `_freq_hist.setVisible`). |
| 3 | **R1-F3 (SOLLTE) – 5-Tupel-Konsistenz** | ✅ Erfüllt | `_apply_bandpilot_auto` speichert `(band, utc_hour, rec, target, current)` (5 Elemente). `_on_bandpilot_tx_finished` entpackt gleich und prüft `current_now != pending_current`. |
| 4 | **R1-F4 (KOENNTE) – T7 deckt Pfad ab** | ✅ Erfüllt | Test `test_normal_insufficient_data` ruft `maybe_apply_bandpilot` mit `rec=None`, erwartet Aufruf von `_show_bandpilot_insufficient_data`. Mock + Assertion korrekt. |
| 5 | **Side-Effects: Manual-Dialog-Cancel** | ✅ OK | `_show_bandpilot_manual_dialog` returned `None` bei Cancel. `_apply_bandpilot_manual` prüft `chosen is None or chosen == current: return False`. Kein unerwarteter Wechsel. |
| 6 | **Backward-Kompat: `_bandpilot_pending`** | ✅ OK | Nur Runtime-State, keine Persistenz. Alte 4-Tupel existieren nicht im Filesystem. Unboxing auf 5-tupel immer korrekt. |
| 7 | **Doku-Datei `docs/explained/bandpilot_de.md`** | ⚠️ Fehlt | Im PR nicht aktualisiert. Sollte den neuen 3-Wege-Vergleich (Normal/Std/DX) beschreiben. → Finding KOENNTE (siehe Tabelle). |
| 8 | **App-Start-Pfad** | ✅ Verifiziert | `_maybe_apply_bandpilot` wird nur in `_on_band_changed` aufgerufen. Beim Start wird `_on_band_changed` erst **nach** Radio-Connect (via Settings-Restore) getriggert. Vorher `radio.ip=False` → der Aufruf wird übersprungen. Kein doppelter oder vergessener Pfad. |

---

### Findings-Tabelle

| Schwere | Finding | Datei:Zeile | Empfehlung |
|---------|---------|-------------|------------|
| **KOENNTE** | Doku `docs/explained/bandpilot_de.md` nicht an P46 angepasst – fehlt Hinweis, dass Normal jetzt empfohlen werden kann (3-Wege-Vergleich) | `docs/explained/bandpilot_de.md` | Abschnitt "Normal-Empfehlung" ergänzen: Bandpilot vergleicht Normal, Diversity Standard und Diversity DX. Normal ist jetzt gültiges Target. |

---

### Gesamtbewertung

**9/10** – Saubere Umsetzung. Alle R1-Findings korrigiert. Keine kritischen oder schwerwiegenden Mängel.  
Einzige Kleinigkeit: Doku-Datei müsste nachgezogen werden (KOENNTE).

**➡️ Push freigegeben**  
(mit optionalem Doku-Update vor Merge, aber kein Blocker)
