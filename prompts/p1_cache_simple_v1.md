# P1.CACHE-SIMPLE V1 — Diversity/Gain-Cache komplett entkoppelt + UX-Cleanup

**Stand:** 2026-05-07.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Compact → Code.
**Mike-Anweisung:** „SimpleFT8 ist der Programm-Name. Halten wir es komplett
getrennt. Egal was Gain sagt: Diversity gilt 60 Min, Gain gilt 6h. Beide
unabhängig. Bei Ablauf: Diversity automatisch neu messen, kein Dialog.
Gain bei Ablauf: Fenster auf, Messung läuft sofort, nur Abbruch-Knopf —
kein ja/nein/vielleicht."

---

## 1. Aktueller Zustand (was Mike stört)

### Problem A — Cache-Reuse-Toast war Pillepalle (BEREITS GELÖSCHT)

`mw_radio.py:957-968` zeigte 5s-Toast „Cache geladen: 70:30 vor X Min."
bei normalem Cache-Hit. Mike-Argument: „Wie 'Computer fährt runter — OK?'
Wenn Wert noch gültig ist, warum bestätigen?"

**Status:** Toast-Klasse `ui/diversity_cache_toast.py` + Smoke-Test
gelöscht, Cache-Reuse-Pfad still. Nicht-committed (gehört zu diesem
Bundle).

### Problem B — Modal-Wahl-Dialog „Weiter / Neu messen"

`mw_radio.py:1003-1063`: bei Ratio>1h aber Gain<6h erscheint Modal-
Dialog mit 2 Buttons. Mike: „Computer-fährt-runter-Pattern." Antwort
ist fast immer „Weiter" (Gain noch frisch, warum Voll-Messung?).

### Problem C — Frische Ratio wird mit altem Gain ignoriert

`_try_diversity_cache_reuse` Z.932-937:

```python
if not store.is_valid_ratio(band, ft_mode):
    return False
if not store.is_valid_gain(band, ft_mode):  # ⛔ Kreuz-Dependency
    return False
```

Wenn Ratio 10 Min alt aber Gain >6h → Cache-Reuse failt → volle
Pipeline misst alles neu. **Frische Daten ignoriert.**

### Problem D — Volle Pipeline läuft ohne Ankündigung

Bei „Gain abgelaufen, alles neu" (Z.1060-1063) startet Pipeline still
über `_start_dx_tuning`. Mike sieht Antennen-Histogramm-Phase, aber
keine klare „Messung läuft, ~3-5 Min, Abbruch möglich"-Info.

---

## 2. Mike's Vision (KISS pur)

**Diversity (Ratio) und Gain komplett entkoppelt** — jeder mit eigener
Frist, jeder mit eigenem Verhalten bei Ablauf:

| Werte-Typ | Frist | Bei Bandwechsel: jünger | Bei Bandwechsel: älter |
|---|---|---|---|
| **Diversity (Ratio)** | 60 Min | Lade aus Cache, **still** | **Automatisch neu messen** (~2-4 Min, kein Dialog) |
| **Gain** | 6h | Ignorieren, **still** | **Fenster auf** „Gain wird gemessen" + Abbruch-Knopf (Default = Messung läuft) |

**Beide Checks unabhängig:** Wenn Gain abgelaufen aber Ratio frisch
→ Gain neu messen, Ratio aus Cache übernehmen. Wenn Ratio abgelaufen
aber Gain frisch → nur Ratio neu, Gain aus Cache.

**Keine Wahl-Dialoge mehr.** Default-Verhalten ist immer das Sinnvolle.
Abbruch-Button als Notbremse.

---

## 3. Akzeptanzkriterien

1. `_try_diversity_cache_reuse` lädt **NUR** aus Cache wenn Ratio < 60 Min.
   **Kein Gain-Check** mehr (Kreuz-Dependency raus).
2. Wenn Ratio jünger ist aber Gain älter → Cache-Reuse OK, ABER
   Gain-Refresh wird im Hintergrund/separat angestoßen (siehe 4).
3. Wenn Ratio älter als 60 Min → automatisch Phase 3 Ratio-Messung
   ohne Dialog. Status-Bar/Histogramm zeigt „Diversity wird neu
   eingemessen (~2-4 Min)".
4. Wenn Gain älter als 6h → **neuer Auto-Mess-Dialog** erscheint:
   ```
   ┌─────────────────────────────────────┐
   │  20m FT8 — Gain wird neu gemessen   │
   │                                     │
   │  Letzte Gain-Kalibrierung 8h alt.   │
   │  Messung läuft (~2-3 Min)…          │
   │                                     │
   │           [ Abbrechen ]             │
   └─────────────────────────────────────┘
   ```
   - **Default:** Messung läuft sofort
   - **Abbruch:** Mit alten Werten weiterarbeiten (Risiko-Akzeptanz)
   - **Modal nicht erforderlich** — könnte non-modal sein, Mike entscheidet
5. Modal-Wahl-Dialog (Z.1009-1050) komplett raus.
6. Cache-Reuse-Toast bleibt raus (bereits gelöscht).
7. Tests grün + neue Tests für Auto-Mess-Verhalten.

---

## 4. Betroffene Module/Dateien

### 4.1 `ui/mw_radio.py`

- `_try_diversity_cache_reuse` Z.917-960:
  - Gain-Check entfernen (Z.936-937)
  - Wenn Ratio valid → laden + Gain-Check separat triggern (siehe 4.2)
- `_check_diversity_preset` Z.987-1063:
  - Wahl-Dialog raus (Z.1009-1050)
  - Neue Logik: 2 unabhängige Checks (Ratio + Gain) → je nach Status
    Auto-Pfad starten
- Neue Methode `_start_gain_only_measurement(callback=None)` für
  isolierte Gain-Messung wenn Ratio aus Cache OK ist
- `_start_dx_tuning(...)` Aufrufe ggf. anpassen je nach Pfad

### 4.2 Neue UI-Komponente

- `ui/gain_measure_progress_dialog.py` (NEU) — non-modal Progress-Dialog
  mit Abbruch-Knopf für Gain-Messung
- Properties: title, info-text, cancel-button
- Signal: `cancel_clicked()` → ruft `_dx_tune_dialog.cancel()` o.ä. auf

### 4.3 `ui/diversity_cache_toast.py` (BEREITS GELÖSCHT)

Schon weg, kein weiterer Eingriff.

### 4.4 Tests

- `tests/test_diversity_cache_reuse.py` — Erweitern:
  - `test_cache_reuse_loads_ratio_only_if_fresh` — kein Gain-Check
  - `test_cache_reuse_with_stale_gain_loads_ratio` — frische Ratio + alter
    Gain → Ratio aus Cache geladen, Gain-Refresh getriggert
- `tests/test_p1_cache_simple.py` (NEU) — Auto-Mess-Verhalten:
  - `test_stale_ratio_triggers_auto_remeasure_no_dialog`
  - `test_stale_gain_shows_progress_dialog_with_cancel`
  - `test_cancel_uses_stale_values`
- Alte Wahl-Dialog-Tests (falls vorhanden) entfernen

---

## 5. Randbedingungen

- **Hardware-Schutz ANT1=TX:** unverändert. Gain-Messung nutzt TUNE
  auf ANT1.
- **Diversity-Lock während Messung:** wenn Auto-Pfad läuft, andere
  TX-Aktionen blockieren wie bisher (`_diversity_measuring`-Flag).
- **Compact-Risiko:** V3 muss alle Diffs Compact-fest enthalten.
  Mike geht essen, Compact danach.
- **Edge-Case Antennen-Tausch:** alte Ratio mit neuem Gain → potentiell
  schlechte Diversity. Mike akzeptiert das (KALIBRIEREN-Button für
  manuellen Voll-Reset).
- **Gain-Refresh-Trigger ohne Ratio-Refresh:** wenn nur Gain abgelaufen
  ist, läuft Gain-Messung (~2-3 Min). Ratio bleibt aus Cache. Diversity
  ist während der Gain-Messung kurz inaktiv (Gain-Phase nutzt TUNE auf
  ANT1, ANT2 nicht parallel decodierbar). User akzeptiert kurze Pause.

---

## 6. Nicht im Scope

- Animation des Progress-Dialogs (KISS)
- Settings-Option „immer fragen" vs „auto" (KISS, Default = auto)
- Background-Refresh ohne UI-Block (overengineering, Hobby-Tool)
- Per-Band-individuelle Fristen (z.B. 80m anders als 20m) — KISS, eine
  Frist für alle
- Ratio-Refresh-Toast nach Abschluss („Diversity neu gemessen, 70:30")
  → Mike's Toast-Argument gilt analog, kein Toast bei Routine-Erfolg

---

## 7. Testbarkeit

**Pflicht-Tests in `tests/test_p1_cache_simple.py`:**

1. `test_cache_reuse_only_checks_ratio`:
   - PresetStore mit Ratio frisch + Gain abgelaufen
   - `_try_diversity_cache_reuse` → True (lädt Ratio)
   - **Vorher (Bug):** False

2. `test_cache_reuse_with_stale_gain_triggers_gain_refresh`:
   - Ratio frisch, Gain >6h
   - Cache-Reuse lädt Ratio → Gain-Auto-Refresh wird angestoßen
   - Progress-Dialog erscheint

3. `test_stale_ratio_auto_remeasures_silent`:
   - Ratio >1h, Gain frisch
   - Bandwechsel → Phase 3 Ratio-Messung läuft automatisch
   - **Kein Dialog** (vorher Wahl-Dialog)

4. `test_progress_dialog_cancel_uses_stale_values`:
   - Gain-Progress-Dialog, User klickt Abbruch
   - Alte Werte bleiben aktiv, kein TX-Block

5. `test_progress_dialog_default_runs_measurement`:
   - Gain-Progress-Dialog, kein User-Klick → Messung läuft durch
   - Nach Abschluss: Dialog schließt sich automatisch

**Pflicht-Tests in `tests/test_diversity_cache_reuse.py` (Update):**

6. Alte Tests die Gain-Check als Pflicht erwarteten → invertieren oder
   umschreiben

---

## 8. Offene Fragen für V2/R1

1. **Progress-Dialog modal vs non-modal:** Modal blockt App während
   Messung — User kann nichts klicken. Non-modal erlaubt RX-Tabelle
   anzusehen. Welcher Stil passt?
2. **Auto-Mess-Trigger-Reihenfolge:** Wenn beide Ratio + Gain abgelaufen
   sind — erst Gain, dann Ratio? Oder volle Pipeline wie bisher?
3. **Gain-Refresh-Trigger im Hintergrund:** wenn Cache-Reuse Ratio lädt
   aber Gain abgelaufen — soll Gain-Messung sofort triggern oder erst
   beim nächsten Bandwechsel/CQ?
4. **Statusbar-Hinweis bei Auto-Ratio-Messung:** „Diversity wird neu
   eingemessen (~3 Min)" — gut oder still?
5. **`_check_diversity_preset` vs `_try_diversity_cache_reuse`:** beide
   Methoden konsolidieren oder Trennung beibehalten?
6. **Race bei Cancel:** User klickt Abbruch während TUNE-Phase → was
   passiert mit Radio-State? Sauberer Cleanup?
7. **`_start_tune_only` (Z.1080)** — wird im neuen Pfad gebraucht oder
   raus?

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
