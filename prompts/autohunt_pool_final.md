# Final-R1: Auto-Hunt-Pool-Umbau — fertiger Code-Review (v0.99.7)

Du hast den PLAN bereits freigegeben (GO mit 3 Korrekturen: +1.0s Jitter-Puffer,
Fallback-Pool-Kommentar, Worked-Filter explizit klammern). Alle 3 sind eingebaut.

Jetzt prüfst du den FERTIGEN Code (Diff unten + die volle `core/auto_hunt.py` ist
angehängt). 2417 Tests grün (vorher 2405, +12 neue `test_autohunt_pool.py`).

## Was umgesetzt wurde
1. `core/auto_hunt.py`: Konstante `AUTO_HUNT_FRESH_SLOTS={"FT8":3,"FT4":3,"FT2":3}`,
   Instanz-Flag `_skip_worked=True` + Setter `set_skip_worked`, Worked-Filter-Block in
   `select_next` jetzt unter `if self._skip_worked and self._qso_log is not None:`
   (n_before_worked + all_worked-Emit komplett innerhalb dieses Blocks).
2. `ui/mw_cycle.py`: `_build_auto_hunt_pool()` (frische CQ-Rufer aus dem
   rx-mode-passenden Akkumulator, `max_age = fresh*slot + 1.0`); `_run_auto_hunt` setzt
   `set_skip_worked(not settings.get("auto_hunt_call_worked", False))` pro Slot und
   ruft `select_next(messages=self._build_auto_hunt_pool())`.
3. `config/settings.py` DEFAULTS: `auto_hunt_call_worked: False`.
4. `ui/settings_dialog.py`: Checkbox + load/save/reset.
5. `ui/main_window.py`: Meldung "alle N aktiven CQ-Rufer ... schon gearbeitet".

## DIFF (Code-Kern)

```diff
diff --git a/config/settings.py b/config/settings.py
index e53290d..941e393 100755
--- a/config/settings.py
+++ b/config/settings.py
@@ -63,6 +63,9 @@ DEFAULTS = {
     "mode": "FT8",
     "auto_mode": False,
     "max_calls": 5,    # P98 (v0.97.70): 99 → 5 (FT8-Standard, Mike-Field-Test)
+    # v0.99.7: Auto-Hunt ruft auch schon gearbeitete Stationen an (Diplom-Modus).
+    # False (Default) = wie bisher: gearbeitete (Band+Mode-genau) ueberspringen.
+    "auto_hunt_call_worked": False,
     "tune_power": 10,
     "diversity_operate_cycles": 80,  # 80/160/240 — Betriebszyklen bis Neueinmessung
     "radio_type": "flex",            # "flex"/"flexradio" = FlexRadio SmartSDR,
diff --git a/core/auto_hunt.py b/core/auto_hunt.py
index 8306e68..d81669b 100644
--- a/core/auto_hunt.py
+++ b/core/auto_hunt.py
@@ -60,6 +60,15 @@ _MAX_ATTEMPTS  = 3      # Max Anrufversuche pro Station
 _COOLDOWN_SECS = 300    # 5 Minuten Cooldown nach fehlgeschlagenem Anruf
 _PAUSE_CYCLES  = 1      # Zyklen Pause nach QSO-Ende bevor naechste Station
 
+# v0.99.7 (04.06.2026): Auto-Hunt waehlt aus dem akkumulierten Stations-Pool
+# (station_accumulator), nicht mehr nur aus dem Moment-Slot. „Frisch" = die
+# Station hat in den letzten N Slots zuletzt gerufen. Modus-aware, aber bewusst
+# in ALLEN Modi 3: eine CQ-Station ruft modus-invariant jeden 2. Slot → 3 Slots
+# = ueberall hoechstens 1 verpasster Ruf Puffer. FT4 ruft HAEUFIGER (kuerzere
+# Slots), man faengt sie schneller — nicht langsamer. FT4 nur datenbasiert auf
+# 4 anheben (NICHT auf Verdacht). Frueher sah Auto-Hunt effektiv nur 1 Slot.
+AUTO_HUNT_FRESH_SLOTS = {"FT8": 3, "FT4": 3, "FT2": 3}
+
 
 def country_rarity_class(count: int) -> int:
     """QSO-Count mit einem Land → persoenliche Seltenheits-Klasse (0..4).
@@ -164,6 +173,10 @@ class AutoHunt(QObject):
         self._recent_qso: dict[tuple[str, str, str], float] = {}
         self._manual_override: bool = False     # Manueller Klick → pausieren
         self._current_target: Optional[str] = None
+        # v0.99.7: „Schon gearbeitete Stationen ueberspringen" (Default = wie
+        # bisher). False = Diplom-Modus, dann werden auch gearbeitete Stationen
+        # wieder angerufen. Gesetzt pro Slot aus dem Setting via set_skip_worked.
+        self._skip_worked: bool = True
         # P169 Phase 2: Entprell-Flag fuer die „alle gearbeitet"-Transparenz-
         # Meldung. Reset NUR bei start_auto_hunt / set_band / set_mode (NICHT
         # pro Pick — sonst Meldung nach jedem QSO auf voll-gearbeitetem Band).
@@ -211,6 +224,16 @@ class AutoHunt(QObject):
         """
         self._my_grid = (grid or "").strip()
 
+    def set_skip_worked(self, skip: bool):
+        """v0.99.7: Worked-Filter an/aus. True (Default) = schon gearbeitete
+        Stationen ueberspringen (Band+Mode-genau). False = Diplom-Modus: auch
+        gearbeitete wieder anrufen (z.B. USA-Diplom im neuen Zeitraum).
+
+        Wird in mw_cycle._run_auto_hunt pro Slot aus dem Setting
+        `auto_hunt_call_worked` gesetzt → eine Aenderung im Settings-Dialog
+        wirkt sofort, ohne extra Signal-Routing."""
+        self._skip_worked = bool(skip)
+
     def mark_pick(self, call: str):
         """P61: Pick-Zeitpunkt-Cooldown setzen. Verhindert dass Auto-Hunt
         eine Station, die gerade angerufen wurde, sofort wieder pickt —
@@ -497,20 +520,25 @@ class AutoHunt(QObject):
         # Band UND in diesem Mode raus — keine Dublette. Mode-genau: dieselbe
         # Station auf 20m FT8 gearbeitet bleibt auf 20m FT4 ein gueltiges Ziel.
         # Eine ANDERE Station aus demselben (seltenen) Land bleibt Kandidat.
-        n_before_worked = len(candidates)
-        if self._qso_log is not None:
+        #
+        # v0.99.7: Worked-Filter NUR wenn _skip_worked aktiv (Default). Im
+        # Diplom-Modus (_skip_worked=False) bleiben gearbeitete Stationen
+        # Kandidaten → die „alle gearbeitet"-Transparenz-Meldung feuert dann
+        # bewusst nie (gearbeitete sind ja gewollte Ziele).
+        if self._skip_worked and self._qso_log is not None:
+            n_before_worked = len(candidates)
             candidates = [c for c in candidates
                           if not self._qso_log.is_worked_on_band_mode(
                               c.call, self._band, self._mode)]
-        if not candidates:
-            _hlog("HUNT", "NO_CANDIDATE reason=all_worked_on_band")
-            # P169 Phase 2: Transparenz. Es gab rufbare CQ-Stationen, aber alle
-            # sind auf Band+Mode schon gearbeitet → einmal (entprellt) melden,
-            # damit der stille Auto-Hunt nicht raetselhaft wirkt.
-            if n_before_worked > 0 and not self._all_worked_reported:
-                self._all_worked_reported = True
-                self.all_worked.emit(self._band, self._mode, n_before_worked)
-            return None
+            if not candidates:
+                _hlog("HUNT", "NO_CANDIDATE reason=all_worked_on_band")
+                # P169 Phase 2: Transparenz. Es gab rufbare CQ-Stationen, aber
+                # alle sind auf Band+Mode schon gearbeitet → einmal (entprellt)
+                # melden, damit der stille Auto-Hunt nicht raetselhaft wirkt.
+                if n_before_worked > 0 and not self._all_worked_reported:
+                    self._all_worked_reported = True
+                    self.all_worked.emit(self._band, self._mode, n_before_worked)
+                return None
 
         # P165: DX-Scoring als lexikografische Tupel-Rangordnung (kleiner =
         # hoehere Prioritaet). Seltenheit > Land-auf-Band-neu > Distanz > SNR >
diff --git a/ui/mw_cycle.py b/ui/mw_cycle.py
index af75173..e98858f 100644
--- a/ui/mw_cycle.py
+++ b/ui/mw_cycle.py
@@ -15,6 +15,7 @@ from core.qso_state import QSOState, ACTIVE_QSO_STATES
 from core.message import FT8Message
 from core import ntp_time
 from core.station_accumulator import accumulate_stations, remove_stale
+from core.auto_hunt import AUTO_HUNT_FRESH_SLOTS
 from radio.presets import PREAMP_PRESETS
 
 # P94 (v0.97.66): Quick-73-Fenster für kürzlich gearbeitete Stationen.
@@ -531,13 +532,45 @@ class CycleMixin:
             self.rx_panel.add_message(msg)
         self.rx_panel.reapply_sort()
 
+    def _build_auto_hunt_pool(self):
+        """v0.99.7: Frische CQ-Rufer aus dem akkumulierten Stations-Pool.
+
+        Auto-Hunt sah bisher nur den Moment-Slot (`messages`) — eine 45s-alte,
+        sichtbare CQ-Station wurde ignoriert. Jetzt waehlt Auto-Hunt aus dem
+        gleichen Akkumulator wie die RX-Liste (station_accumulator), beschraenkt
+        auf Stationen die in den letzten `AUTO_HUNT_FRESH_SLOTS`-Slots zuletzt
+        gerufen haben.
+
+        `is_cq` ist ein Live-Property (aus field1): wechselt eine CQ-Station ins
+        QSO, faellt sie automatisch raus. `_last_heard` setzt accumulate_stations
+        immer (P157). Der +1.0s-Puffer faengt Qt-Timer-Jitter an der Slot-Grenze
+        (DeepSeek-R1). Pool ist aktuell: accumulate_stations laeuft in
+        `_on_cycle_decoded` VOR `_run_auto_hunt`.
+        """
+        # Auto-Hunt ist nur im Diversity-Modus aktiv → _diversity_stations.
+        # Fallback _normal_stations ist ein toter Pfad (defensiv, harmlos).
+        pool_dict = (self._diversity_stations if self._rx_mode == "diversity"
+                     else self._normal_stations)
+        slot = self.timer.cycle_duration
+        fresh = AUTO_HUNT_FRESH_SLOTS.get(self.settings.mode.upper(), 3)
+        max_age = fresh * slot + 1.0   # +1s Jitter-Puffer (DeepSeek-R1)
+        now = time.time()
+        return [m for m in pool_dict.values()
+                if getattr(m, 'is_cq', False)
+                and (now - getattr(m, '_last_heard', 0)) <= max_age]
+
     def _run_auto_hunt(self, messages):
         """Auto-Hunt: automatisch CQ-Stationen anrufen (verstecktes Feature)."""
         if not self._auto_hunt.active:
             return
+        # v0.99.7: Worked-Filter-Schalter pro Slot live aus dem Setting setzen
+        # (Default: gearbeitete ueberspringen). AN = Diplom-Modus.
+        self._auto_hunt.set_skip_worked(
+            not self.settings.get("auto_hunt_call_worked", False))
         _idle = self.qso_sm.state in (QSOState.IDLE, QSOState.TIMEOUT)
+        # v0.99.7: aus dem akkumulierten Pool waehlen statt nur Moment-Slot.
         _candidate = self._auto_hunt.select_next(
-            messages=messages or [],
+            messages=self._build_auto_hunt_pool(),
             qso_idle=_idle,
             presence_ok=self.presence_can_tx(),
         )

```

## Prüf-Auftrag (sei kritisch, Code ist Referenz)
1. **Korrektheit des geklammerten Worked-Filters:** Ist `n_before_worked` jetzt
   ausschließlich im `if self._skip_worked`-Block definiert und referenziert? Kein
   NameError-Pfad bei `_skip_worked=False`?
2. **Frische-Filter:** `(now - getattr(m,'_last_heard',0)) <= max_age`. Eine Station
   ohne `_last_heard` bekommt 0 → `now - 0` riesig → rausgefiltert. Korrekt (kann nicht
   vorkommen, accumulate setzt es immer, aber defensiv ok)?
3. **Reihenfolge/Race:** Pool wird aus `_diversity_stations` gebaut, das in
   `_on_cycle_decoded` VOR `_run_auto_hunt` durch accumulate_stations aktualisiert wird.
   Bei leerem Slot (`messages=[]`) läuft accumulate NICHT, aber der Pool enthält noch die
   gealterten Stationen (remove_stale lief). Ist es korrekt/gewollt, dass Auto-Hunt jetzt
   auch bei leerem Moment-Slot aus dem Pool wählt? (Das ist der Hauptgewinn.)
4. **Doppel-Pick:** gepickte Station bleibt im Pool (Aging 20 Slots), aber select_next's
   `_recent_qso`-Cooldown (30 Min) filtert sie. Lückenlos?
5. **set_skip_worked pro Slot:** billig & robust, oder Problem?
6. **Hardware:** rein Auswahl/Anzeige, kein TX-Pfad, ANT1/ANT2 unberührt — bestätigt?
7. **Übersehene Edge-Cases / Regressionen / tote Reste?**

Urteil: **PUSH FREIGEBEN** oder **NICHT FREIGEBEN** (mit konkreten Bugs).
