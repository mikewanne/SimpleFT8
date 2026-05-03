# Bandpilot Stunden-Logik — V2 Self-Review (Stand 2026-05-04)

## Zweck dieses Dokuments

V2 entsteht durch eine "frische-KI-Brille" auf V1
(`prompts/bandpilot_stundenlogik_v1.md`). V2 fuellt Luecken, klaert
Mehrdeutigkeiten, definiert Edge-Cases. V2 geht danach an DeepSeek-R1
zur Pruefung. R1-Findings → V3 → Plan-Mode → Code.

V1 ist NICHT verworfen — V2 ergaenzt V1, beide gemeinsam bilden den
Input fuer R1.

---

## Kontext-Verifikation (Schritt 0)

Vor V2 wurden folgende Quellen gelesen:

| Quelle | Befund |
|---|---|
| `prompts/bandpilot_stundenlogik_v1.md` | 11 AKs + 7 Konsens-Punkte, finalisiert 2026-05-04 |
| `core/mode_recommender.py` | Alte API: `aggregate_stats()` + `recommend(diversity_pref)` mit Kandidat A `(s+d)/2` + `Bandpilot`-Klasse + `BandpilotSummaryCache` |
| `ui/mw_radio.py:355-660` | `_maybe_apply_bandpilot()` mit Override-Set + `_bandpilot_setting_mode`-Flag + `_set_rx_mode_direct` + `_activate_diversity_with_scoring` |
| `ui/settings_dialog.py:305-590` | `bandpilot_cb` + `bandpilot_pref_combo` + `_show_bandpilot_help` mit QMessageBox |
| `config/settings.py:69-70` | DEFAULTS: `bandpilot_enabled=False` + `bandpilot_diversity_pref="auto"` |
| `tests/test_mode_recommender.py` | 22 Tests, davon 9 testen Kandidat-A-Logik (mit `(s+d)/2`) |
| Stats-Datei-Format | Header `# Statistik YYYY-MM-DD HH:00-HH:59 UTC \| FT8 \| <band> \| <mode>`, Zeilen `\| HH:MM:SS \| <int> \| <snr> \|` |
| `MEMORY.md` Eintrag | Konsens-Snapshot identisch zu V1 |

**Konsequenz:** Alle V1-Module-Referenzen sind verifiziert. Kein Code-
Pfad halluziniert. Existierende Tests fuer Kandidat A muessen entfernt
oder umgeschrieben werden (Punkt M unten).

---

## Findings + Praezisierungen ueber V1 hinaus

Nummerierung A..Y im Reihenfolge der Schwere (KISS-Pragmatismus zuerst,
dann Edge-Cases).

### A) Toleranz-Regel: gegen aktuellen Mean, nicht gegen Top-2 (KRITISCH)

**V1 sagt:** "Wenn `Top-1 - Top-2 < max(5%, 1 Station)` -> bleibt
aktueller Modus".

**Problem:** Das prueft Top-1 gegen Top-2, nicht gegen den **aktuellen**
Modus. Edge-Case:
- Top-1 = Diversity DX (40 Sta./Slot)
- Top-2 = Diversity Std (38 Sta./Slot)
- Top-3 = Normal (35 Sta./Slot) ← aktueller Modus

Top-1 - Top-2 = 2 Sta. < 5% von 40 = 2 Sta. → Toleranz greift → kein
Wechsel. Aber Normal (aktuell, 35) ist **deutlich** schlechter als
Top-1 (40). Der User bleibt im klar schlechteren Modus.

**Korrigierte Regel (V2):**
```
if aktueller_mean >= Top-1_mean - max(0.05 * Top-1_mean, 1.0):
    kein Wechsel  ("no_change")
else:
    Wechsel zu Top-1
```

**Begruendung:** Wir wollen wechseln wenn Top-1 **spuerbar besser** als
der aktuelle Modus ist. Top-2 ist irrelevant fuer die Wechsel-
Entscheidung. Pingpong-Schutz greift trotzdem: wenn die drei Werte
eng beieinander liegen, ist der aktuelle Modus immer "nah genug" an
Top-1.

**Spezialfall aktuell == Top-1:** Differenz = 0 < Toleranz → kein
Wechsel. Korrekt.

### B) `recommend_for_hour` — Signatur und Rueckgabe klar definieren

**V1 sagt:** `recommend_for_hour(summary, hour, mode, current_mode) -> str | None`.

**V2 praezisiert:**

```python
def recommend_for_hour(
    summary_24h: dict[int, dict[str, dict]],
    hour: int,                        # 0..23 UTC
    current_mode: str | None,         # "normal"|"diversity_normal"|"diversity_dx"|None
    bandpilot_mode: str,              # "auto"|"manual"  (off ruft nicht)
) -> dict | None:
    """
    Returns:
        None              wenn zu wenig Daten in einem der 3 Modi
        {
          "top1":          "<mode>",          # immer gesetzt
          "top1_mean":     45.2,              # immer gesetzt
          "ranking":       [(mode, mean), ...],   # 3-elementig, sortiert desc
          "decision":      "no_change" | "switch",
          "decision_mode": "<mode>" | None,   # bei "no_change" = current_mode
        }
    """
```

- "decision" basiert auf Toleranz-Regel A.
- "decision_mode" ist der Modus den der Aufrufer setzen sollte (kann
  identisch mit current_mode sein → Auto: nichts tun, Manuell:
  stillschweigend bestaetigen).
- "ranking" ist fuer den Manuell-Dialog (alle 3 Werte anzeigen).
- `current_mode=None` (z.B. waehrend dx_tuning): in `_maybe_apply_bandpilot`
  vorher abfangen → Bandpilot greift NICHT bei dx_tuning. Kein
  Edge-Case in der Rezepfunktion.

### C) Hourly-Aggregation Performance: Variante A (Pre-Compute beim App-Start)

**V1 sagt:** "Generierung beim App-Start (sync, < 1s pro Band)".

**V2 praezisiert:**

- Pro Band einmal `aggregate_stats_by_hour(stats_dir, band)` rufen, das
  intern alle 24 Stunden in **einem Pass** ueber die MD-Files aggregiert.
- Returnt `dict[int, dict[str, dict]]` (hour → mode → {days, cycles, mean}).
- Daten in Cache (`~/.simpleft8/bandpilot_hourly.json`) mit TTL 24h
  pro Band — analog `BandpilotSummaryCache` in v0.87.
- Bei Bandwechsel: Cache lesen → Aktuelle Stunde rauspicken → entscheiden.
- Lazy-Aggregation: erst beim ersten Aufruf pro Band aggregieren, nicht
  alle 9 Baender beim App-Start. Das `_init_bandpilot_recommendations`
  generiert nur die MD-Reports (siehe AK 2 / Punkt D).

**Begruendung:** Bei 5+ Tagen × 24 Std × 3 Modi pro Band sind das
schon spuerbare Mengen MD-Files. Lazy + Cache hat sich in v0.87
bewaehrt.

### D) MD-Empfehlungs-Datei: Format-Klarstellung

**V1 sagt:** `auswertung/Bandpilot-<band>-FT8.md`, Spalten
`UTC | Normal Tage·Sta | Diversity Std Tage·Sta | Diversity DX Tage·Sta | Top-1`.

**V2 praezisiert:**

```markdown
# Bandpilot Empfehlung — 40m FT8

Stand: 2026-05-04 (App-Start). Quelle: `statistics/<Mode>/40m/FT8/`.

| UTC | Normal | Div Standard | Div DX | Top-1 |
|---:|---:|---:|---:|:---|
| 00 | 4·12.3 | 3·15.7 | 5·22.1 | Diversity DX |
| 01 | 2·8.5  | —      | 3·11.0 | _zu wenig Daten_ |
| ...
| 13 | 5·45.2 | 4·38.0 | 5·52.7 | Diversity DX |
| ...
| 23 | 4·30.1 | 3·28.5 | 5·40.4 | Diversity DX |
```

- Format pro Zelle: `<Tage>·<Mean mit 1 Nachkomma>`.
- Fehlend / 0 Tage: `—` (Em-Dash).
- Top-1: User-Label (`"Normal"` / `"Diversity Standard"` / `"Diversity DX"`),
  bei zu wenig Daten in einem oder mehreren Modi → `_zu wenig Daten_`
  (kursiv).
- **Sprache: nur DE** (Mike's Default). EN-Variante out of scope V1.
  Falls EN noetig: spaetere Erweiterung wie generate_plots.py
  (`auswertung/en/Bandpilot-<band>-FT8.md`).
- Tabellen-Header in DE: "UTC | Normal | Div Standard | Div DX | Top-1".

### E) Robustheit: Statistik-Verzeichnis fehlt oder ist leer

**V1 sagt nichts dazu.**

**V2 ergaenzt:**

- Wenn `statistics/<mode>/<band>/FT8/` fehlt oder leer:
  `aggregate_stats_by_hour` returnt leeres dict.
- `_init_bandpilot_recommendations`: bei leerem Aggregat → MD-Datei
  trotzdem erzeugen mit Hinweis-Zeile am Anfang ("_Keine Statistik-
  Daten vorhanden — bitte FT8-Sessions laufen lassen._"), keine
  Tabelle ausgeben. KEIN Crash.
- Bandpilot-Empfehlung in mw_radio.py: bei leerem Aggregat →
  Statusbar-Hinweis "Bandpilot: keine Statistik vorhanden", keine
  Wechsel. Manuell-Modus zeigt KEIN Dialog.

### F) Settings-Migration: robuste, idempotente Strategie

**V1 sagt:** "Migration einmalig beim ersten Start mit neuer Version".

**V2 praezisiert:**

```python
# In Settings.load() nach _data.update(saved):
self._migrate_bandpilot_settings_v088()

def _migrate_bandpilot_settings_v088(self):
    if "bandpilot_mode" in self._data:
        return  # schon migriert ODER User hat es manuell gesetzt
    old_enabled = self._data.pop("bandpilot_enabled", None)
    self._data.pop("bandpilot_diversity_pref", None)  # verworfen
    if old_enabled is True:
        self._data["bandpilot_mode"] = "auto"
    else:
        self._data["bandpilot_mode"] = "off"
    self.save()
```

- Idempotent: zweiter Aufruf macht nichts (Marker = `bandpilot_mode`
  existiert).
- `pop()` entfernt alte Keys aus dem Dict, neuer save() speichert nur
  noch den neuen Key.
- DEFAULTS in V0.88: nur `"bandpilot_mode": "off"` — die alten beiden
  Keys verschwinden.

### G) Stundenwechsel-Konvention: Bandpilot reagiert NUR bei Bandwechsel

**V1 implizit, V2 macht es explizit:**

- Bandpilot wird in `_on_band_changed` aufgerufen (`_maybe_apply_bandpilot(band)`).
- Bandpilot wird **nicht** auf einen Stundenwechsel reagieren —
  d.h. wenn User um 12:55 das Band wechselt, gilt die Stunde 12 fuer
  diesen Wechsel, auch wenn die App noch lange weiterlaeuft.
- Begruendung: User-Aktion-getriggert ist klar, Stunden-getriggerter
  Auto-Wechsel mitten in einer Funk-Session ist nervig.
- Zukunft: optionaler "Stunden-Tick alle :00 UTC" als Erweiterung,
  out of scope V1.

### H) Edge-Case: Bandpilot bei dx_tuning

`_current_rx_mode_string()` returnt `None` waehrend `_rx_mode == "dx_tuning"`.

**V2 ergaenzt:** `_maybe_apply_bandpilot(band)` prueft als ERSTES:

```python
current = self._current_rx_mode_string()
if current is None:
    return False  # dx_tuning laeuft → Bandpilot still
```

### I) Toast — Multi-Monitor-Verhalten

**V1 sagt:** "3-Sekunden-Toast mittig auf Bildschirm".

**V2 praezisiert:**

- `QDialog` mit `parent=self` (MainWindow). Qt platziert das Dialog
  relativ zum Parent → automatisch auf demselben Bildschirm wie das
  MainWindow.
- `setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)` damit es kein
  Taskbar-Eintrag gibt.
- `setAttribute(Qt.WA_DeleteOnClose)` fuer sauberes Aufraeumen.
- Position: in `showEvent` mittig zum Parent-Geometry zentrieren.
- Self-Close: `QTimer.singleShot(3000, self.close)`.
- Optional [×]-Button: 1 QPushButton oben rechts, `clicked → close`.

### J) Schnelle Bandwechsel: alten Toast/Dialog schliessen

**V1 sagt nichts.**

**V2 ergaenzt:**

- `MainWindow._bandpilot_active_toast` und `_bandpilot_active_dialog`
  als Member-Refs.
- Vor neuem Toast/Dialog: `if self._bandpilot_active_toast: close()`.
- Bei Manuell: gleicher Mechanismus fuer Dialog.
- Begruendung: schnelle Band-Hop-Sequenz darf nicht 3 gestapelte
  Dialogs erzeugen.

### K) Encoding-Konvention: Code vs UI

**V2 fixiert:**

| Ebene | Werte |
|---|---|
| Settings-Key | `"bandpilot_mode"` ∈ `{"off", "auto", "manual"}` |
| Code-Modus-String | `"normal"`, `"diversity_normal"`, `"diversity_dx"` |
| UI-Label (Toast, Dialog, MD-Datei) | `"Normal"`, `"Diversity Standard"`, `"Diversity DX"` |
| Statistik-Verzeichnis | `Normal`, `Diversity_Normal`, `Diversity_Dx` |
| Settings-Combo-Anzeige | `"Aus"`, `"Auto"`, `"Manuell"` |

Mapping-Helper in `core/mode_recommender.py`:
```python
USER_LABEL = {
    "normal":           "Normal",
    "diversity_normal": "Diversity Standard",
    "diversity_dx":     "Diversity DX",
}
STATS_DIR = {
    "normal":           "Normal",
    "diversity_normal": "Diversity_Normal",
    "diversity_dx":     "Diversity_Dx",
}
```

### L) MD-Generator: Modul-Ort

**V1 sagt:** `tools/build_bandpilot_recommendations.py`.

**V2 schlaegt vor:** `core/bandpilot_md.py` mit Funktion
`write_bandpilot_md(stats_dir, output_dir, band, ft_mode="FT8")`.

**Begruendung:**
- `tools/` ist fuer manuelle Helper-Skripte (z.B. `refresh_stats.sh`).
- Code wird sowohl von `ui/main_window.py` (App-Start) als auch von
  `scripts/generate_plots.py` aufgerufen → gehoert ins Core-Paket
  damit beide importieren koennen ohne `sys.path`-Tricks.
- Tests in `tests/test_bandpilot_md.py` analog `test_mode_recommender.py`.

### M) Kandidat-A-Tests entfernen

V0.87-Tests in `tests/test_mode_recommender.py` testen die
Aggregat-Logik `(s+d)/2`. In V0.88 ist diese Logik weg.

**V2 fixiert:**

| Test | Aktion |
|---|---|
| `test_recommend_normal_wins` | LOESCHEN (testet Kandidat A) |
| `test_recommend_diversity_auto_picks_standard` | LOESCHEN |
| `test_recommend_diversity_auto_picks_dx` | LOESCHEN |
| `test_recommend_diversity_pref_standard_forces_standard` | LOESCHEN |
| `test_recommend_diversity_pref_dx_forces_dx` | LOESCHEN |
| `test_recommend_normal_pref_ignored_when_normal_wins` | LOESCHEN |
| `test_bandpilot_recommend_for_band` | LOESCHEN (alte API) |
| `test_bandpilot_diversity_pref_propagates` | LOESCHEN |
| `test_recommend_insufficient_*` | UMSCHREIBEN auf `recommend_for_hour` |
| `_aggregate_mode` / `_parse_stats_file` Tests | BEHALTEN (Helper unveraendert) |
| `BandpilotSummaryCache` Tests | UMSCHREIBEN auf neuen Cache-Key (`hourly`) ODER alten Cache loeschen + neuen schreiben |

**Neue Tests** (V1 AK 10):
- `test_aggregate_stats_by_hour_three_days_three_modes`
- `test_recommend_for_hour_normal_top1_no_change`
- `test_recommend_for_hour_diversity_dx_top1_switch`
- `test_recommend_for_hour_tolerance_5pct_keeps_current`
- `test_recommend_for_hour_tolerance_1station_keeps_current`
- `test_recommend_for_hour_insufficient_one_mode_returns_none`
- `test_settings_migration_enabled_true_to_auto`
- `test_settings_migration_enabled_false_to_off`
- `test_settings_migration_idempotent`
- `test_bandpilot_md_generates_24_rows`
- `test_bandpilot_md_handles_missing_data_gracefully`

### N) `tx_finished`-Signal — verifizieren

**V1 setzt voraus:** Encoder hat `tx_finished`-Signal.

**V2-Risiko:** Wenn das Signal nicht existiert, ist AK 7 (TX-Schutz)
nicht implementierbar.

**Pflicht-Verifikation in Phase 6** vor Commit:
```bash
grep -rn "tx_finished\|tx_finished_signal\|on_tx_finished" core/ ui/
```

Falls fehlt: Encoder bekommt eine `Signal()` `tx_finished` die nach
dem letzten emittierten Slot getriggert wird. Implementierung in
Phase 6.

**Fallback wenn Signal nicht baubar:** Polling — `QTimer` checkt alle
500ms `radio.is_transmitting()`. Akzeptabel als Notloesung, aber
sauberer waere ein Signal.

### O) `recommend_for_hour` Edge-Case: `current_mode = None`

Schon abgedeckt durch H — Bandpilot wird gar nicht aufgerufen wenn
dx_tuning laeuft. Aber zur Defensiv-Programmierung in der
Recommend-Funktion:

```python
if current_mode is None:
    return None  # nicht entscheidbar — Aufrufer soll das filtern
```

### P) Phase-Reihenfolge — V1 ist OK, V2 schlaegt Detailaenderung vor

V1 hat 11 Phasen. V2 schlaegt vor:

| # | Phase | Bemerkung |
|---|---|---|
| 1 | `core/mode_recommender.py` Refactor + Tests | Ohne UI-Hooks |
| 2 | `core/bandpilot_md.py` + Tests | Nicht `tools/`! |
| 3 | `config/settings.py` Migration + DEFAULTS | Standalone-Test moeglich |
| 4 | `ui/settings_dialog.py` Combo-Update | Kein Bandpilot-Trigger noetig |
| 5 | `ui/mw_radio.py` `_maybe_apply_bandpilot` neu, Override-Set raus | Kerntransplantation |
| 6 | Toast-Dialog + Manuell-Dialog (UI) | Mit Highlighting |
| 7 | TX-Schutz + Statusbar-Hinweis | Erst hier `tx_finished` verifizieren |
| 8 | App-Start-Hook fuer MD-Generierung | `_init_optional_features` |
| 9 | Doku-Komplett-Update DE+EN | docs/explained/bandpilot_de.md + .md |
| 10 | README + Version v0.88 + HISTORY-Stub | Vor Tests |
| 11 | Tests final, Final-R1, HANDOFF/CLAUDE/Memory + Push + GitHub-Release | Letzter Schritt |

Detail-Aenderung ggu V1: Phase 4 (Settings-Dialog) **vor** Phase 5
(Bandpilot-Logik), weil Phase 5 die neue Combo bereits voraussetzt.

### Q) HISTORY.md grep — Kollision mit v0.87 vermeiden

V2-Pflicht vor Phase 1: 
```bash
grep -n "Bandpilot" HISTORY.md
```

v0.87 Eintrag bleibt unveraendert (war Kandidat A). v0.88-Eintrag
nimmt explizit Bezug:
```
## 2026-05-XX v0.88 — Bandpilot Stunden-Refactor
**Ersetzt** v0.87-Konzept (globaler Pooled Mean + Aggregat (S+D)/2)
durch Stunden-genaue 3-Werte-Anzeige ohne Aggregation.
[Details]
```

Memory `feedback_bandpilot_ux_pref_in_settings.md` ist aktuell — neu
fassen ist nicht noetig (schon am 04.05. ueberschrieben).

### R) Aktuelle Stunde mit-aggregieren

Frage: Wenn um 13:30 Bandwechsel, soll die Stunde "13" der **heutige**
13-UTC-Block mit-aggregiert werden, auch wenn er noch nicht voll ist?

**V2 entscheidet:** Ja, der heutige Tag wird voll mitgezaehlt mit den
bisher geloggten Slots. Kein Sonderfall — `aggregate_stats_by_hour`
liest alle MD-Files. Wenn `2026-05-04_13.md` schon ein paar Slots hat,
zaehlen die mit. Kann den Tag-Counter erhoehen (Tag 5 statt 4) wenn
heute der erste Slot in Stunde 13 schon drin ist.

**Risiko:** Sehr wenige Slots heute → weniger zuverlaessig. Aber
durch MIN_CYCLES_HOUR=20 (gesamt ueber alle Tage) abgefedert.

### S) Edge-Case: Aktuelle Stunde hat keine Daten in EINEM Modus

**V1 sagt** (AK 9): "alle drei Modi muessen MIN_DAYS_HOUR + MIN_CYCLES_HOUR
erfuellen — sonst Stille".

**V2 bestaetigt:** ja. Wenn Diversity DX um 03 UTC nie gemessen wurde,
gibt es keine Empfehlung um 03 UTC fuer dieses Band — Statusbar 5s
"Bandpilot: nicht genug Daten fuer 40m um 03 UTC". KISS.

Falls Mike das spaeter aufweichen will (z.B. "vergleiche nur die 2
Modi mit Daten"): V2 lehnt ab, weil das die Empfehlung verfaelscht
(asymmetrische Datenbasis).

### T) Statusbar-Hinweis: 5s, dann clear

**V2 fixiert:** `self.statusBar().showMessage(text, 5000)` (Qt-API,
`timeout` in ms). Nach 5s automatisch weg. Keine extra Logik noetig.

### U) Kein zusaetzlicher `bandpilot_migrated`-Marker

Stattdessen: das Vorhandensein von `bandpilot_mode` in `_data` ist
selbst der Marker. Spart einen weiteren Settings-Key.

### V) Toleranz-Formel — Pseudocode

```python
def pick_top_with_tolerance(
    means: dict[str, float],   # {"normal": 35, "diversity_normal": 38, "diversity_dx": 40}
    current: str,              # "normal"
) -> tuple[str, str]:
    """Returns (top1_mode, decision_mode).
    decision_mode == current → "no_change", sonst → switch zu top1_mode.
    """
    sorted_modes = sorted(means.items(), key=lambda x: x[1], reverse=True)
    top1_mode, top1_mean = sorted_modes[0]
    current_mean = means[current]
    tolerance = max(0.05 * top1_mean, 1.0)
    if current_mean >= top1_mean - tolerance:
        return top1_mode, current  # kein Wechsel
    return top1_mode, top1_mode    # Wechsel zu Top-1
```

Test-Tabelle (alle MIN_DAYS+MIN_CYCLES erfuellt):
| Normal | Std | DX | aktuell | Top-1 | Decision |
|---:|---:|---:|---|---|---|
| 35 | 38 | 40 | normal | dx | switch dx |
| 39 | 38 | 40 | normal | dx | no_change (40-39=1 = Toleranz max(2,1)=2 → 1<2) |
| 35 | 38 | 40 | dx | dx | no_change |
| 100 | 80 | 90 | normal | normal | no_change (aktuell == top-1) |
| 35 | 90 | 80 | normal | std | switch std (90-35=55, Toleranz max(4.5,1)=4.5) |

### W) Diversity-Sub-Mode-Wechsel im Auto

Wenn aktuell Diversity Standard und Auto sagt Diversity DX:
- `_set_rx_mode_direct("diversity_dx")` → `_disable_diversity()` →
  `_activate_diversity_with_scoring("dx")` → Preset-Check, ggf. neue
  Pipeline (Tunen + Gain + Einmessen).
- **Wichtig:** Pipeline kann mehrere Sekunden dauern. Toast erscheint
  vorher, der Wechsel ist erst nach Pipeline-Ende sichtbar (statusbar
  zeigt es).
- Risiko: User wechselt das Band waehrend die Pipeline laeuft → die
  alte v0.87-Logik hat das schon abgefedert (`_pending_dx_diversity`-
  Flag). Pruefen ob v0.88 damit kollidiert.

### X) Z-Order: Toast/Dialog ueber MainWindow, NICHT ueber Settings-Dialog

`parent=self` (MainWindow) → Qt setzt z-Order korrekt. Wenn der User
gerade den Settings-Dialog offen hat und das Band in einem anderen
Pfad wechselt (sollte nicht passieren, aber): Settings-Dialog ist
modal → Bandpilot-Dialog erscheint dahinter. Akzeptabel.

### Y) `_bandpilot_setting_mode`-Flag in v0.88

Mit Override-Set entfaellt dieser Flag → Code-Stelle `mw_radio.py:381-385`
komplett raus. `_set_rx_mode_direct` muss den Flag nicht mehr setzen.

**Vorsicht:** Falls andere Code-Pfade den Flag noch lesen → grep
nach `_bandpilot_setting_mode` BEVOR loeschen.

---

## Zusammengefasste neue Akzeptanzkriterien (V2-Ergaenzungen)

| # | AK | Quelle |
|---|---|---|
| 12 | Toleranz gegen aktuellen Mean, nicht Top-2 | A |
| 13 | `recommend_for_hour` returnt strukturiertes dict | B |
| 14 | Lazy-Aggregation pro Band + JSON-Cache | C |
| 15 | MD-Datei nur DE, Format `Tage·Mean`, `—` bei leer | D |
| 16 | Robustheit bei fehlendem Stats-Dir | E |
| 17 | Settings-Migration idempotent, alte Keys raus | F |
| 18 | Bandpilot reagiert NUR bei Bandwechsel | G |
| 19 | Defensiv: bei dx_tuning skippen | H |
| 20 | Toast/Dialog parent-relative + WA_DeleteOnClose | I |
| 21 | Schnelle Bandwechsel: alten Toast schliessen | J |
| 22 | Encoding-Konvention fixiert | K |
| 23 | MD-Generator in `core/bandpilot_md.py` | L |
| 24 | Kandidat-A-Tests loeschen + 11 neue | M |
| 25 | `tx_finished`-Signal verifizieren in Phase 6 | N |
| 26 | Phase 4 (Settings) vor Phase 5 (Logik) | P |
| 27 | HISTORY.md v0.88-Entry erwaehnt v0.87-Replacement | Q |
| 28 | `bandpilot_mode`-Existenz = Migrations-Marker | U |

---

## Was V2 NICHT aendert ggu V1

- 11 V1-AKs bleiben gueltig (mit Praezisierungen aus V2).
- 7-Punkte-Konsens-Snapshot bleibt.
- Versionsbump v0.87.1 → v0.88.
- Out-of-Scope-Liste bleibt (Default-Modus pro Band, Band-Empfehlung,
  10-Min-Hysterese, manueller Bandpilot-Button, Color-Symbol-Pattern).

---

## R1-Briefing — Was R1 bewerten soll

R1 bekommt zusammen mit V1 + V2:
- `core/mode_recommender.py` (alte API, fuer Refactor-Kontext)
- `ui/mw_radio.py` (`_maybe_apply_bandpilot` + `_set_rx_mode_direct` +
  `_activate_diversity_with_scoring`)
- `ui/settings_dialog.py` (alte Bandpilot-Combo)
- `config/settings.py` (DEFAULTS + load/save)
- `tests/test_mode_recommender.py` (alte Tests)
- README.md (Bandpilot-Sektion)
- `docs/explained/bandpilot_de.md` (alte Doku)

**Auftrag an R1 (kein Code, nur Prompt-Kritik):**

1. Sind die V2-Praezisierungen vollstaendig? Welche Edge-Cases fehlen?
2. Ist die Toleranz-Regel A korrekt formuliert?
3. Stimmt die Phase-Reihenfolge? Gibt es Reihenfolge-Faelle die brechen?
4. Welche Test-Faelle fehlen ueber die V2-Liste hinaus?
5. Ist `core/bandpilot_md.py` der richtige Modul-Ort, oder doch `tools/`?
6. Migrations-Strategie F: gibt es Race-Conditions oder Dateien-Zugriff
   ohne Lock?
7. Sind 11 atomare Commits realistisch oder eher 13-15?
8. Welche Module-Hooks (Signal-Slot, Subscriber) sind eventuell
   uebersehen worden?
9. Ist die Doku-Reorganisation (Phase 9) ausreichend, oder muss eine
   Migrations-Note fuer Bestands-User ins README?

R1 soll **NICHT** den Code schreiben. R1 soll V2 kritisieren.

---

## Naechster Schritt

V2 ist fertig. Naechster Schritt:
1. R1-Review-Skript: `tools/deepseek_review.py` mit V1+V2 +
   relevanten Files (siehe oben).
2. Schritt 2.5: R1-Findings gegen Code verifizieren.
3. V3 schreiben (V1 + V2 + R1-Validierte Findings konsolidieren).
4. Mike-Freigabe.
5. Plan-Mode + 11 atomare Commits.
