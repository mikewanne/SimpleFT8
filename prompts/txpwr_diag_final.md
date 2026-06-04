# Final-R1: Diagnose-Logging Watt-Bug — bitte Verhaltensneutralität bestätigen

Plan war: NUR debug_log('TXPWR',…) an 3 Stellen (_auto_adjust_tx_level 1x/Slot, _on_power_changed, _apply_rf_preset) + action-Default 'hold' gegen NameError. KEINE Regelungsänderung. Prüfe den Diff: (1) wirklich verhaltensneutral? (2) action in ALLEN Pfaden definiert? (3) Attribut-Zugriffe in der Logzeile immer gültig (auch f-String wird bei deaktiviertem Log ausgewertet)? (4) Flood-Risiko? Knapp, gegen Diff prüfen.

```diff
diff --git a/ui/mw_tx.py b/ui/mw_tx.py
index e2a1614..b01285d 100644
--- a/ui/mw_tx.py
+++ b/ui/mw_tx.py
@@ -8,6 +8,8 @@ from typing import TYPE_CHECKING
 
 from PySide6.QtCore import Slot
 
+from core.debug_log import debug_log
+
 if TYPE_CHECKING:
     from .main_window import MainWindow
 
@@ -39,6 +41,10 @@ class TXMixin:
         # 4. Radio aktualisieren
         if self.radio.ip:
             self.radio.set_power(self._rfpower_current)
+        # Diagnose (Watt-Bug): Watt-Knopf = frischer set_power (die „Heilung")
+        debug_log("TXPWR",
+                  f"power_btn target={power}W → preset_rf={self._rfpower_current}% "
+                  f"set_power={'sent' if self.radio.ip else 'no-radio'}")
 
     def _apply_rf_preset(self):
         """Lädt RF-Preset für aktuelle (radio, band, watts) — None → Settings-Default.
@@ -73,6 +79,10 @@ class TXMixin:
                   f"rf={self._rfpower_current}")
         self._rfpower_converged = False
         self._was_converged = False
+        # Diagnose (Watt-Bug): wann rfpower neu geladen wird (Band-/Watt-/Init-Wechsel)
+        debug_log("TXPWR",
+                  f"apply_preset {band}_{watts}W → rf={self._rfpower_current}% "
+                  f"({'hit' if saved is not None else 'default'})")
 
     @Slot(bool)
     def _on_tune_clicked(self, on: bool):
@@ -766,6 +776,7 @@ class TXMixin:
 
         new_audio   = current_audio
         new_rfpower = self._rfpower_current
+        action = "hold"  # Diagnose-Marker (TXPWR-Log) — Default für In-Band/keine Änderung
 
         # Schritt 1: audio sofort auf CLIP_LIMIT begrenzen (nicht schrittweise!)
         if current_audio > CLIP_LIMIT:
@@ -800,10 +811,12 @@ class TXMixin:
             self.radio.set_power(new_rfpower)
             self._rfpower_converged = False
             self._was_converged = False
+            action = f"set_rf->{new_rfpower}"
         elif not self._was_converged:
             # Konvergenz erkannt: 1× speichern pro (band, watts)-Zyklus
             self._rfpower_converged = True
             self._was_converged = True
+            action = f"converge_save rf={self._rfpower_current}"
             band = self.settings.band
             watts = self._power_target
             self.rf_preset_store.save(
@@ -830,6 +843,19 @@ class TXMixin:
               f"raw={raw_peak:.2f} audio {current_audio:.2f}→{new_audio:.2f} "
               f"rfpower {new_rfpower}%")
 
+        # Diagnose (Watt-Bug 05.06.): persistent ins Debug-Log — zeigt bei
+        # Wiederauftreten, ob App-RF% von der realen Wattzahl abweicht und
+        # set_power nicht mehr gesendet wird (action=hold am Anschlag). 1×/Slot,
+        # nur bei aktivem Debug-Log → kein Hot-Path-Flood. Mit den [ANT]-Logs
+        # per Zeitstempel korrelierbar (Diversity-Switch → danach kleben?).
+        debug_log("TXPWR",
+                  f"{self.settings.band}/{self.settings.mode} "
+                  f"target={target}W app_rf={self._rfpower_current}% "
+                  f"fwdpwr={fwdpwr:.0f}W audio={current_audio:.2f} "
+                  f"peak={raw_peak:.2f} swr={getattr(self.radio, 'last_swr', 0.0):.2f} "
+                  f"conv={self._rfpower_converged}/{self._was_converged} "
+                  f"action={action}")
+
     @Slot(str, float)
     def _on_meter_update(self, name: str, value: float):
         if name == "FWDPWR":
```
