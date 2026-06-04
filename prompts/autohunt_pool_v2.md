# R1-Plan-Review: Auto-Hunt aus akkumuliertem Pool + Frische-Fenster + "gearbeitete auch anrufen"-Schalter

Du bist Senior-Reviewer eines PySide6/Python FT8-Funk-Tools (SimpleFT8, Hobby-Funk,
KISS-Philosophie, KEIN Contest-Tool). Prüfe DIESEN PLAN kritisch BEVOR Code geschrieben
wird. Code ist die Referenz — die angehängten Dateien sind der reale Ist-Zustand.

## Problem (Mike-Field, abgestimmt)

1. **Auto-Hunt sieht nur den Moment-Slot.** `mw_cycle._run_auto_hunt(messages)` gibt
   `select_next` nur die Decodes DIESES einen 15s/7.5s-Slots. Die RX-Liste akkumuliert
   dagegen über `core/station_accumulator.py` (CQ-Rufer bis 20 Slots sichtbar). Folge:
   man SIEHT eine 45s-alte CQ-Station in der Liste, Auto-Hunt ignoriert sie aber, weil
   sie in genau diesem Moment nicht ruft. Bei FT4 schlimmer (kürzere Slots). Auch: bei
   einem leeren Decode-Slot wählt Auto-Hunt gar nichts, obwohl der Pool voll ist.

2. **Kein "gearbeitete-trotzdem-anrufen"-Schalter.** Heute filtert select_next schon
   gearbeitete Stationen (Band+Mode-genau) immer raus. Für Diplom-Jagd (z.B. 250 USA-
   QSOs im neuen Zeitraum) will Mike die optional WIEDER anrufen.

3. **"alle N gearbeitet"-Meldung** zählt heute Moment-Slot-Kandidaten (N=1-2) → verwirrt.

## Lösung (mein V2-Plan)

### Änderung 1 — Pool statt Moment-Slot
- Neue Modul-Konstante in `core/auto_hunt.py`:
  `AUTO_HUNT_FRESH_SLOTS = {"FT8": 3, "FT4": 3, "FT2": 3}`
  (3 in allen Modi; FT4 NICHT mehr, weil eine CQ-Station modus-invariant jeden
  2. Slot ruft → 3 Slots = überall ≤1 verpasster Ruf. FT4 ruft häufiger, fängt man
  schneller. FT4→4 nur datenbasiert später.)
- `mw_cycle._run_auto_hunt` ruft NICHT mehr mit `messages`, sondern mit einem neuen
  Helper `self._build_auto_hunt_pool()`:
  ```python
  def _build_auto_hunt_pool(self):
      pool_dict = (self._diversity_stations if self._rx_mode == "diversity"
                   else self._normal_stations)
      slot = self.timer.cycle_duration
      fresh = AUTO_HUNT_FRESH_SLOTS.get(self.settings.mode.upper(), 3)
      max_age = fresh * slot
      now = time.time()
      return [m for m in pool_dict.values()
              if getattr(m, 'is_cq', False)
              and (now - getattr(m, '_last_heard', 0)) <= max_age]
  ```
- `select_next` bleibt UNVERÄNDERT in Signatur (nimmt `messages`-Liste) — bekommt
  jetzt nur den Pool statt Moment-Slot. Begründung: accumulate_stations läuft in
  `_on_cycle_decoded` (Z.144 `_handle_diversity_operate`→accumulate) VOR `_run_auto_hunt`
  (Z.191), der Pool ist also aktuell inkl. Moment-Slot.

### Änderung 2 — "gearbeitete auch anrufen"-Schalter
- `core/auto_hunt.py`: Instanz-Flag `self._skip_worked = True` + Setter
  `set_skip_worked(skip: bool)`. In `select_next` die Worked-Filter-Zeile (Z.501-504)
  nur ausführen wenn `self._skip_worked`.
- `config/settings.py` DEFAULTS: `"auto_hunt_call_worked": False` (Default = wie heute,
  gearbeitete überspringen).
- `ui/settings_dialog.py`: QCheckBox "Schon gearbeitete Stationen auch anrufen" im
  Tab "FT8 & Diversity" + load/save/reset (Muster wie `auto_tune_band_cb`).
- `mw_cycle._run_auto_hunt`: setzt das Flag JEDEN Slot frisch:
  `self._auto_hunt.set_skip_worked(not self.settings.get("auto_hunt_call_worked", False))`
  → immer live, kein Settings-Dialog-Hook nötig.

### Änderung 3 — klarere Meldung
- `main_window._on_auto_hunt_all_worked`: "Auto-Hunt: alle {n} aktiven CQ-Rufer auf
  {band} {mode} schon gearbeitet" (n ist jetzt die Pool-Größe = was man sieht).

### Tests
- Neue `test_autohunt_pool.py`: Frische-Filter (frisch drin / >N Slots raus), is_cq-Filter,
  skip_worked an=filtert/aus=behält, Default-Flag. Bestehende select_next-Tests bleiben
  grün (Default `_skip_worked=True` → Worked-Filter aktiv wie bisher).

## Verifizierte Fakten (aus angehängtem Code)
- `FT8Message.is_cq` ist ein **Property** (live aus `field1`). accumulate_stations
  aktualisiert `field1/2/3` bei Inhaltsänderung → eine CQ-Station, die ins QSO wechselt,
  hat sofort `is_cq==False` → fällt aus dem Pool. ✓
- `_last_heard` wird in accumulate_stations IMMER gesetzt (neu + bekannt, P157). ✓
- `_tx_even` wird beim Update NICHT aktualisiert (bleibt Erst-Empfang) — bei CQ-Rufern
  ist die Slot-Parity aber konstant. ✓
- Pool max ~20 CQ-Rufer (Aging-Cap AGING_SLOTS_CQ_CALLER=20) → Filter/Scoring trivial.

## Meine offenen Fragen an dich (R1)
1. **Frische-Grenze + Jitter:** `(now - _last_heard) <= fresh*slot`. Eine vor genau 3
   Slots gehörte Station hat age ≈ 3*slot, durch Timing-Jitter evtl. knapp drüber → fällt
   raus. Brauche ich einen halben Slot Puffer (`(fresh + 0.5) * slot`), oder ist das
   Mikro-Optimierung/Overengineering? Was ist robuster UND KISS?
2. **set_skip_worked jeden Slot** (statt nur bei Start + Dialog-Save): billig & robust,
   oder unnötig? Risiko übersehen?
3. **Welcher Pool im Edge-Fall** (rx_mode == "dx_tune", Auto-Hunt theoretisch nicht aktiv):
   mein Fallback nimmt `_normal_stations`. Sicher genug, oder explizit leeren Pool?
4. **Worked-Filter + Meldung:** bei `_skip_worked=False` (Diplom-Modus) wird der Filter
   übersprungen → "alle gearbeitet"-Meldung feuert nie. Korrekt? Strukturiere ich den
   n_before_worked-Block richtig (nur im skip_worked-Zweig)?
5. **Übersehe ich eine Race/State-Falle?** Besonders: kann eine gerade gepickte Station
   im nächsten Slot doppelt gepickt werden? (mark_pick → _recent_qso 30-Min-Cooldown
   greift in select_next — reicht das, da sie ja im Pool bleibt?)
6. **Hardware-Sicherheit:** rein State-/Anzeige-Logik, kein TX-Pfad-Eingriff, ANT1/ANT2
   unberührt — bestätigst du das? (Auto-Hunt-TX läuft unverändert über den bestehenden
   start_qso-Pfad.)
7. **Overengineering-Check (Mike-Pflicht):** Ist irgendwas am Plan zu kompliziert für
   ein Hobby-Tool? Gibt es eine simplere Variante die dasselbe leistet?

Gib ein klares Urteil: GO / PLAN ÜBERARBEITEN, mit den konkreten Korrekturen.
