# OPT-61 Final-R1 (Bestätigungspass auf den fertigen Diff)

Du hast in R1 GO gegeben. Hier ist der UMGESETZTE Diff. Bitte prüfe NUR noch,
ob die Umsetzung exakt dem abgesegneten Plan entspricht und verhaltensneutral
ist. Knapp: PUSH FREIGEBEN oder NICHT (mit Grund).

## Was umgesetzt wurde
- Neue `@property is_busy` in `QSOStateMachine` (core/qso_state.py): inline-Tupel
  `not in (IDLE, TIMEOUT, CQ_CALLING, CQ_WAIT)`.
- 7 Call-Sites ersetzt (6× `not in (...)` → `is_busy`; 1× `in (...)` → `not is_busy`):
  main_window (`_qso_active_for_msg_defer`, `_in_qso`, CQ-Stop-Guard),
  mw_cycle (`qso_busy`, `_in_qso`), mw_qso (2× Hunt-QSO-Abbruch).
- 2 jetzt tote lokale `from core.qso_state import QSOState` in main_window entfernt
  (pyflakes-bestätigt sauber, AST-Parse OK, kein „undefined name").
- Die ANDEREN State-Mengen (2/3/6-State) blieben unangetastet.

## Test-Anpassung (wichtig — bitte mitprüfen)
`test_p81_autohunt_stop_defer.py` T1 mockte `qso_sm` als `MagicMock(state=...)`
und ließ die echte `_qso_active_for_msg_defer` laufen. Die liest jetzt
`qso_sm.is_busy` → bei MagicMock truthy → T1 (kein-QSO-States) brach (erwartet
False). Fix: Helper `_qso_sm_in_state(state)` baut eine ECHTE QSOStateMachine →
`is_busy` ist die echte Property (keine Logik-Duplikation im Test). T2 besteht
dadurch jetzt aus dem RICHTIGEN Grund (vorher zufällig durch Mock-Truthiness).

## Tests
Volle Suite **2453 passed** (2438 → +15 neuer `test_qso_is_busy.py`:
alle 12 Enum-States explizit eingeordnet + Vollständigkeits-/Komplement-
Mutationsbeweis). test_p81 16/16 grün.

## Fragen
1. Diff verhaltensneutral + plan-konform?
2. Test-Helper-Fix korrekt (echte SM statt Mock = keine Verschleierung)?
3. Etwas übersehen? Sonst: PUSH FREIGEBEN.

---
## DIFF
diff --git a/core/qso_state.py b/core/qso_state.py
index 9af05ff..277b8a0 100755
--- a/core/qso_state.py
+++ b/core/qso_state.py
@@ -203,6 +203,19 @@ class QSOStateMachine(QObject):
         """Aktuellen SNR-Wert vom Decoder übernehmen."""
         self._last_snr = snr
 
+    @property
+    def is_busy(self) -> bool:
+        """True wenn eine QSO-Austausch-Sequenz mit einer Gegenstation laeuft.
+
+        „Nicht busy" = IDLE / TIMEOUT / CQ_CALLING / CQ_WAIT — in diesen
+        Zustaenden laeuft kein QSO, das vor Bandwechsel / Frequenzsprung /
+        Stop geschuetzt werden muesste. (OPT-61: ersetzt 7× dasselbe Tupel.)
+        """
+        return self.state not in (
+            QSOState.IDLE, QSOState.TIMEOUT,
+            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
+        )
+
     # ── CQ-Modus ────────────────────────────────────────────────
 
     def start_cq(self):
diff --git a/tests/test_p81_autohunt_stop_defer.py b/tests/test_p81_autohunt_stop_defer.py
index 2e08256..9c1b26e 100644
--- a/tests/test_p81_autohunt_stop_defer.py
+++ b/tests/test_p81_autohunt_stop_defer.py
@@ -25,6 +25,15 @@ from unittest.mock import MagicMock, patch
 import pytest
 
 
+def _qso_sm_in_state(state):
+    """Echte QSOStateMachine im gewuenschten State — so liefert
+    `qso_sm.is_busy` die ECHTE Property (OPT-61), keine Mock-Truthiness."""
+    from core.qso_state import QSOStateMachine
+    sm = QSOStateMachine("DA1MHH", "JO31")
+    sm.state = state
+    return sm
+
+
 # ── T1 — kein-QSO-States: add_info SOFORT, KEIN Defer ─────────────────
 
 
@@ -40,7 +49,7 @@ def test_t1_polling_tick_sofort_bei_kein_qso(state_name):
     obj._auto_hunt_polling_timer = MagicMock()
     obj._auto_hunt_last_mouse_t = 0.0
     obj._auto_hunt_stop_msg_pending = False
-    obj.qso_sm = MagicMock(state=getattr(QSOState, state_name))
+    obj.qso_sm = _qso_sm_in_state(getattr(QSOState, state_name))
     obj._qso_active_for_msg_defer = (
         lambda: mw_mod.MainWindow._qso_active_for_msg_defer(obj)
     )
@@ -74,7 +83,7 @@ def test_t2_polling_tick_defert_bei_aktivem_qso(state_name):
     obj._auto_hunt_polling_timer = MagicMock()
     obj._auto_hunt_last_mouse_t = 0.0
     obj._auto_hunt_stop_msg_pending = False
-    obj.qso_sm = MagicMock(state=getattr(QSOState, state_name))
+    obj.qso_sm = _qso_sm_in_state(getattr(QSOState, state_name))
     obj._qso_active_for_msg_defer = (
         lambda: mw_mod.MainWindow._qso_active_for_msg_defer(obj)
     )
diff --git a/ui/main_window.py b/ui/main_window.py
index d946792..3dd41b4 100755
--- a/ui/main_window.py
+++ b/ui/main_window.py
@@ -1153,11 +1153,7 @@ class MainWindow(QMainWindow, CycleMixin, QSOMixin, RadioMixin, TXMixin):
         """True wenn ein QSO im Gange ist, also die Stop-Meldung deferred
         werden soll. „kein QSO" = IDLE, TIMEOUT, CQ_CALLING, CQ_WAIT.
         """
-        from core.qso_state import QSOState
-        return self.qso_sm.state not in (
-            QSOState.IDLE, QSOState.TIMEOUT,
-            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
-        )
+        return self.qso_sm.is_busy
 
     def _flush_auto_hunt_stop_msg(self):
         """Wenn eine deferred Stop-Meldung pending ist, jetzt im QSO-Panel
@@ -1459,9 +1455,7 @@ class MainWindow(QMainWindow, CycleMixin, QSOMixin, RadioMixin, TXMixin):
         recalc = getattr(self._diversity_ctrl, '_recalc_count', 0)
         freq_str = f"  |  Freq: #{recalc} {cq_hz}Hz" if cq_hz else ""
         # Smart Antenna waehrend QSO
-        from core.qso_state import QSOState
-        _in_qso = self.qso_sm.state not in (
-            QSOState.IDLE, QSOState.TIMEOUT, QSOState.CQ_CALLING, QSOState.CQ_WAIT)
+        _in_qso = self.qso_sm.is_busy
         if _in_qso and self.qso_sm.qso.their_call:
             if (self._rx_mode == "diversity"
                     and hasattr(self, '_antenna_prefs')):
@@ -1612,8 +1606,7 @@ class MainWindow(QMainWindow, CycleMixin, QSOMixin, RadioMixin, TXMixin):
             # CQ stoppen (aber laufendes QSO zu Ende fuehren!)
             if self.qso_sm.cq_mode:
                 # Nur CQ stoppen wenn KEIN aktives QSO laeuft
-                if self.qso_sm.state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT,
-                                          QSOState.IDLE, QSOState.TIMEOUT):
+                if not self.qso_sm.is_busy:
                     self.qso_sm.stop_cq()
                     self.control_panel.set_cq_active(False)
                     self.qso_panel.add_info(
diff --git a/ui/mw_cycle.py b/ui/mw_cycle.py
index 68590b4..cbb1684 100644
--- a/ui/mw_cycle.py
+++ b/ui/mw_cycle.py
@@ -226,10 +226,7 @@ class CycleMixin:
         volle ~60s Karenzzeit verfuegbar sind und kein Mid-QSO-Frequenz-
         sprung passiert.
         """
-        qso_busy = self.qso_sm.state not in (
-            QSOState.IDLE, QSOState.TIMEOUT,
-            QSOState.CQ_CALLING, QSOState.CQ_WAIT,
-        )
+        qso_busy = self.qso_sm.is_busy
         with self._diversity_lock:
             self._diversity_ctrl.sync_from_stations(self._diversity_stations)
             if qso_busy:
@@ -670,10 +667,7 @@ class CycleMixin:
                 self._diversity_ctrl.on_operate_cycle()
 
                 # Smart Antenna: waehrend QSO auf beste Antenne forcieren
-                _in_qso = self.qso_sm.state not in (
-                    QSOState.IDLE, QSOState.TIMEOUT,
-                    QSOState.CQ_CALLING, QSOState.CQ_WAIT,
-                )
+                _in_qso = self.qso_sm.is_busy
                 pref_ant = None
                 if _in_qso and self.qso_sm.qso.their_call and hasattr(self, '_antenna_prefs'):
                     pref_ant = self._antenna_prefs.get(self.qso_sm.qso.their_call)
diff --git a/ui/mw_qso.py b/ui/mw_qso.py
index 449ec69..ea7821d 100644
--- a/ui/mw_qso.py
+++ b/ui/mw_qso.py
@@ -220,9 +220,7 @@ class QSOMixin:
             if self.qso_sm.cq_mode:
                 self.qso_sm.stop_cq()
                 self.control_panel.set_cq_active(False)
-            elif self.qso_sm.state not in (QSOState.IDLE, QSOState.TIMEOUT,
-                                            QSOState.CQ_CALLING,
-                                            QSOState.CQ_WAIT):
+            elif self.qso_sm.is_busy:
                 # Hunt-QSO laeuft → abbrechen damit on_message_sent nicht
                 # in WAIT_REPORT/RR73 wechselt
                 self.qso_sm.cancel()
@@ -367,8 +365,7 @@ class QSOMixin:
                 self.control_panel.set_cq_active(False)
                 return
             # Laufendes Hunt-QSO abbrechen bevor CQ startet!
-            if self.qso_sm.state not in (QSOState.IDLE, QSOState.TIMEOUT,
-                                          QSOState.CQ_CALLING, QSOState.CQ_WAIT):
+            if self.qso_sm.is_busy:
                 self.qso_sm.cancel()
                 self._active_qso_targets.clear()
                 self.rx_panel.set_active_call("")
