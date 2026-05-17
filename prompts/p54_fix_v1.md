# P54-FIX V1 — Echte 10W-Closed-Loop-Konvergenz beim TUNE + Krücken-Skalierung

## Ziel

Aktuelle P54-Implementierung speichert beim TUNE einen **Wunschwert**
(`rf_preset_store.save(band, 10, 10)`) — also hart „Slider 10 = 10W"
für jedes Band, egal was die Antenne in Wirklichkeit macht. Das
zerstört die Kalibrierungs-Philosophie der `RFPresetStore`-Tabelle
(echte band-spezifische Stellgrößen) für resonante UND off-band Antennen.

**Mike's Konzept (von Anfang an):**

1. **TUNE mit echter Closed-Loop-Konvergenz** bis FWDPWR ≈ 10W → echten
   Slider-Wert speichern (analog zur QSO-Closed-Loop-Logik in
   `_auto_adjust_tx_level`).
2. **Krücken-Skalierung mit Sicherheits-Faktor** als Initial-Startwert
   wenn ein höheres Watt-Ziel angesprochen wird und nur 1 Stützpunkt
   existiert. Sobald Closed-Loop konvergiert → echten Wert speichern.

Plus: bestehende `RFPresetStore`-Lade-Logik (Hybrid-Strategie:
exakter Treffer → 2-Punkt-Interpolation → None) bleibt **unverändert**.
Settings-Tabelle bleibt funktional.

## Code-Verifikation (Pflicht)

- `core/rf_preset_store.py:105` `load()` — Hybrid-Strategie OK,
  unverändert lassen.
- `ui/mw_tx.py:42` `_apply_rf_preset()` — Krücken-Skalierung hier
  einfügen (Caller-Level, nicht in Store).
- `ui/mw_tx.py:163` `_tune_post_swr_check` — aktueller hart-Save
  `(band, 10, 10)` muss durch konvergierten Wert ersetzt werden.
- `ui/mw_tx.py:269` `_start_auto_tune_for_band_change` — Auto-TUNE-
  Sequenz, hier Convergenz-Phase einfügen.
- `ui/mw_tx.py:66` `_on_tune_clicked` — manuelles TUNE, gleiche
  Convergenz-Phase wiederverwenden.
- `ui/mw_tx.py:444` `_auto_adjust_tx_level` — bestehende Closed-Loop-
  Logik als Template für die TUNE-Convergenz.

## Architektur-Entscheidungen

### Entscheidung 1 — Wo läuft Closed-Loop während TUNE?

**Option A:** Während der `tune_duration_s` (15s) iterativ messen
und anpassen.
**Option B:** Zwei Phasen: erst Tuner-Match (10s, Slider fest),
dann Convergenz (5s, Slider anpassen).

→ **Option B gewählt.** Begründung: LDG AT-200 Pro Spec sagt Full-Tune
typisch <15s. Während Tuner-Match-Phase ist Last instabil
(SWR schwankt) → Closed-Loop wäre instabil. Erst nach Match (SWR
stabil) macht Convergenz Sinn.

### Entscheidung 2 — Zeit-Aufteilung

- `tune_duration_s = 15` → 10s Match + 5s Convergenz
- `tune_duration_s = 30` → 22s Match + 8s Convergenz

Hartkodiert: `_TUNE_MATCH_RATIO = 2/3` der Gesamtdauer ist Match-Phase,
Rest ist Convergenz.

### Entscheidung 3 — Krücken-Skalierung in `_apply_rf_preset`

Wenn `rf_preset_store.load()` `None` returnt:
1. Schaue ob für das Band genau **1 Stützpunkt** existiert
   (`store.get_all(radio_type)[band]`).
2. Wenn ja: linear hochrechnen mit Sicherheits-Faktor 0,9:
   ```python
   rf = anchor_rf * (target_watt / anchor_watt) * 0.9
   ```
3. Wenn nein: Fallback auf `settings.get_tx_power(band, 50)` wie bisher.

Closed-Loop im 1. QSO konvergiert → speichert echten Wert → ab 2.
Stützpunkt greift wieder die normale Hybrid-Strategie (lineare
Interpolation in `RFPresetStore.load`).

## Akzeptanzkriterien

**AC1** — Neue Helper-Methode `_tune_converge_to_target(target_w: int,
duration_s: int) -> int | None` in `mw_tx.py`:

```python
def _tune_converge_to_target(self, target_w: int = 10,
                              duration_s: int = 5) -> int | None:
    """Closed-Loop-Convergenz waehrend TUNE.
    
    Voraussetzung: TUNE laeuft (radio.tune_on() schon aktiv,
    _tune_active=True). Tuner ist gematched (vorhergehende Phase A).
    
    Iterativ rfpower anpassen bis FWDPWR ≈ target_w (±1 W) oder
    Timeout. Max 5 Iterationen, je ~1s.
    
    Returns konvergierter rfpower-Slider-Wert (0-100) oder None
    wenn Convergenz fehlschlaegt.
    """
    if not self.radio.ip:
        return None
    
    TOLERANCE_W = 1.0
    MAX_ITERATIONS = 5
    SETTLE_MS = 1000  # 1s pro Iteration zum Sample-Sammeln
    
    rf_current = 10  # Start-Slider (wie TUNE bisher)
    self.radio.set_rfpower_direct(rf_current)
    
    # Initial-Sample-Phase (1s)
    self._fwdpwr_samples.clear()
    QApplication.processEvents()  # Meter-Updates durchlassen
    # ... sleep 1s mit Event-Loop ...
    
    for iteration in range(MAX_ITERATIONS):
        if not self._fwdpwr_samples:
            continue
        fwdpwr = sum(self._fwdpwr_samples) / len(self._fwdpwr_samples)
        self._fwdpwr_samples.clear()
        
        if abs(fwdpwr - target_w) <= TOLERANCE_W:
            return rf_current  # Konvergiert
        
        # Proportionale Anpassung (analog _auto_adjust_tx_level)
        if fwdpwr > 0:
            estimated = int(rf_current * (target_w / fwdpwr))
            step = max(1, min(15, abs(estimated - rf_current)))
            if fwdpwr < target_w:
                rf_current = min(100, rf_current + step)
            else:
                rf_current = max(1, rf_current - step)
            self.radio.set_rfpower_direct(rf_current)
            # ... sleep 1s ...
        else:
            return None  # Kein Mess-Signal
    
    # Max Iterations erreicht — letzten Wert zurueckgeben (best-effort)
    return rf_current
```

**Implementierungs-Detail:** Da wir im Qt-Event-Loop laufen müssen
(damit Meter-Updates ankommen), verwenden wir `QTimer` + Callback-
Kette statt `time.sleep()`. Konkrete Struktur:

```python
def _tune_converge_step(self, iteration: int, target_w: int,
                         on_finished_callback):
    # ... Iteration n ausführen, dann QTimer.singleShot fuer n+1 ...
```

Oder: nutze `QEventLoop` + `QTimer` synchron (saubere KISS-Lösung).

**AC2** — `_start_auto_tune_for_band_change` und `_on_tune_clicked`
nutzen den neuen Helper:

Reihenfolge:
1. `tune_on()` + Slider=10 wie bisher
2. **Phase A (Tuner-Match):** warten `match_duration_s` (= 2/3 von
   `tune_duration_s`, also 10s bei 15s, 20s bei 30s)
3. **Phase B (Convergenz):** `_tune_converge_to_target(10,
   duration_s = tune_duration_s - match_duration_s)`
4. Ergebnis `rf_converged` merken (in State-Var oder Closure)
5. `_tune_stop` → `_tune_post_swr_check`
6. In `_tune_post_swr_check`: bei SWR-Good speichere `(band, 10,
   rf_converged)` statt hart `(band, 10, 10)`

**AC3** — `_tune_post_swr_check` Save-Logik:

Statt:
```python
self.rf_preset_store.save(radio_type, band, 10, 10)
```

Neu:
```python
rf_to_save = self._tune_converged_rf or 10  # Fallback bei Convergenz-Fail
self.rf_preset_store.save(radio_type, band, 10, rf_to_save)
```

`_tune_converged_rf` wird in `_tune_converge_to_target` gesetzt und
in `_tune_stop` ausgelesen → an `_tune_post_swr_check` weitergegeben.

**AC4** — Krücken-Skalierung in `_apply_rf_preset`:

Erweitern:
```python
def _apply_rf_preset(self):
    if self.radio is None:
        ...
    band = self.settings.band
    watts = getattr(self, "_power_target", None) or self.settings.get("power_preset", 10)
    
    saved = self.rf_preset_store.load(self.radio.radio_type, band, watts)
    if saved is not None:
        self._rfpower_current = saved
        print(f"[RF-Preset] geladen: {band}_{watts}W → rf={saved}")
    else:
        # P54-FIX AC4: Krücken-Skalierung wenn genau 1 Stützpunkt vorhanden
        krucke = self._kruecken_skalierung(band, watts)
        if krucke is not None:
            self._rfpower_current = krucke
            print(f"[RF-Preset] Krücke: {band}_{watts}W → rf={krucke} (linear x0.9)")
        else:
            self._rfpower_current = self.settings.get_tx_power(band, default=50)
            print(f"[RF-Preset] Default: {band}_{watts}W → rf=50%")
    
    self._rfpower_converged = False
    self._was_converged = False


def _kruecken_skalierung(self, band: str, target_w: int) -> int | None:
    """P54-FIX: linear hochrechnen vom 10W-Anker × Sicherheits-Faktor 0,9.
    
    Returns rfpower-Wert (1-100) oder None wenn keine Krücke möglich.
    """
    radio_type = self.radio.radio_type
    all_presets = self.rf_preset_store.get_all(radio_type)
    band_data = all_presets.get(band, {})
    
    if len(band_data) != 1:
        # Mehrere Stützpunkte → Hybrid-Interpolation hätte gegriffen,
        # oder kein einziger → Default-Pfad
        return None
    
    anchor_watt, anchor = next(iter(band_data.items()))
    if anchor_watt <= 0:
        return None
    
    anchor_rf = anchor.get("rf", 0)
    if anchor_rf <= 0:
        return None
    
    estimated = anchor_rf * (target_w / anchor_watt) * 0.9
    return max(1, min(100, int(round(estimated))))
```

**AC5** — Hardware-Schutz während Convergenz

- `set_tx_antenna("ANT1")` einmal am Anfang (steht bereits in
  `_start_auto_tune_for_band_change` und `_on_tune_clicked`).
- Während Convergenz wird KEIN `set_tx_antenna`-Aufruf gemacht.
- SWR-Watchdog ist via `_tune_in_progress = True` bypassed (wie heute).
- Max-Slider 100% wird nie überschritten (`min(100, ...)`).
- Min-Slider 1% (`max(1, ...)`) — verhindert Crash bei FWDPWR > Ziel
  durch reflektierte Leistung.
- Convergenz-Timeout: max 5 Iterationen × 1s = 5s extra TUNE-Dauer.

**AC6** — Convergenz-Fehler-Pfade

- Kein FWDPWR-Signal (Radio reagiert nicht): nach 1s ohne Sample
  → return None → Fallback hart auf rf=10 (Backward-Compat)
- Divergenz (Werte oszillieren): nach Max-Iterations → letzten Wert
  zurückgeben (best-effort, immerhin besser als rf=10 hart)
- Convergenz-Fail bei SWR-Bad: kein Save (wie bisher)

**AC7** — Settings-Tabelle bleibt unverändert

`RFPresetStore.get_all()` + Tabellen-Render in `settings_dialog.py`
bleibt **komplett unangetastet**. Die Lüge wird nur an einer Stelle
korrigiert (Save-Pfad in `_tune_post_swr_check`).

**AC8** — Tests `tests/test_p54_fix.py`:

- T1: `_tune_converge_to_target` mit perfekter Linearität →
  konvergiert bei rf=10 wenn FWDPWR=10W.
- T2: `_tune_converge_to_target` mit Off-Band-Verlust (FWDPWR=7W bei
  rf=10) → konvergiert auf rf≈14.
- T3: `_tune_converge_to_target` mit FWDPWR > Ziel (zu viel) →
  reduziert rf.
- T4: `_tune_converge_to_target` Max-Iterations → returnt
  letzten Wert (best-effort).
- T5: `_tune_converge_to_target` ohne FWDPWR-Sample → returnt None.
- T6: `_tune_post_swr_check` speichert konvergierten Wert
  (nicht hart 10).
- T7: `_kruecken_skalierung` mit 1 Stützpunkt → linear × 0.9.
- T8: `_kruecken_skalierung` mit 0 Stützpunkten → None.
- T9: `_kruecken_skalierung` mit 2+ Stützpunkten → None
  (Hybrid-Strategie übernimmt).
- T10: `_apply_rf_preset` nutzt Krücke wenn Store None returnt.
- T11: `_apply_rf_preset` nutzt Default 50% wenn Krücke None returnt.
- T12: Convergenz-Fail (kein Sample) → Save mit Fallback rf=10
  (Backward-Compat).
- T13: Hardware ANT1 vor Convergenz (Source-Level Check unchanged).
- T14: `RFPresetStore.get_all()` unverändert (Smoke).

## Atomare Commits

- C1: Backup `Appsicherungen/2026-05-16_v0.97.44_vor_p54fix/`.
- C2: `ui/mw_tx.py` Helper `_tune_converge_to_target` NEU.
- C3: `ui/mw_tx.py` `_tune_post_swr_check` Save-Logik mit konvergiertem
  Wert.
- C4: `ui/mw_tx.py` Helper `_kruecken_skalierung` + `_apply_rf_preset`
  erweitert.
- C5: `ui/mw_tx.py` `_start_auto_tune_for_band_change` + `_on_tune_clicked`
  nutzen Convergenz-Phase.
- C6: `tests/test_p54_fix.py` NEU (14 Tests).
- C7: `main.py` APP_VERSION 0.97.44 → 0.97.45.
- C8: HISTORY+HANDOFF+CLAUDE+Memory aktualisieren.

## Field-Test (Mike, mit Radio)

- F1: TUNE auf 40m resonant → Convergenz erreicht rf≈10–14 (je nach
  Antenne), Save mit echtem Wert. Tabelle zeigt korrekten Wert.
- F2: TUNE auf 17m mit SWR 2,5:1 → Convergenz erreicht rf≈14–18,
  Save mit höherem Wert. Tabelle zeigt das.
- F3: Erstes QSO 50W auf neuem Band ohne 50W-Eintrag → Krücke greift
  (rf=14×5×0.9 = ~63). Closed-Loop konvergiert nach + speichert.
- F4: 2. QSO mit anderer Wattzahl → Hybrid-Interpolation greift
  (2+ Stützpunkte).
- F5: TUNE mit FWDPWR=0 (Radio antwortet nicht) → Convergenz-Fail,
  Save mit Fallback rf=10 (kein Crash).
- F6: Manueller TUNE-Klick → gleiche Convergenz-Phase, gleicher Save.
- F7: Settings-Tabelle zeigt nach mehreren Sessions echte band-
  spezifische Werte (10W-Anker realitätsnah, höhere Watt-Werte
  konvergiert).

## Aus Scope

- IC-7300 Spline-Interpolation (RFPresetStore-Doku erwähnt das,
  aber wir bleiben bei linear).
- Mehrere Frequenz-Punkte pro Band (z.B. 40m unten + 40m oben).
- Automatische Re-Kalibrierung bei Wetter-Wechsel (User triggert
  manuell wenn nötig).
