# Final-R1: Einmess-Fenster verschlankt (v0.99.8) — fertiger Code-Review

Du hast den AUFBAU bereits abgesegnet (V1 GO: ein Fortschritts-Zähler statt drei,
Doppel-Titel raus, Fachjargon weg, Tabelle mit klarer Beschriftung). Jetzt prüfst du
den FERTIGEN Code. Es ist ein PySide6/Qt-Fortschritts-Dialog (DXTuneDialog), reine
UI-Anzeige — die Mess-/Antennen-Logik ist NICHT angefasst. 2423 Tests grün (vorher 2417).

## Was umgesetzt wurde (Diff unten)
1. **Doppelten Titel weg:** großes Body-Titel-Label entfernt (`_title_label` war nirgends
   sonst genutzt). Fenstertitel (Titelleiste) bleibt unverändert — von `_get_mode_label()`,
   weil 4 Smoke-Tests den `windowTitle()` asserten.
2. **Drei Fortschritts-Zähler → einer:** „Runde 1/2 — ANT1 Gain 20 dB" + „Schritt 5/12
   (5/6 in dieser Runde)" + Balken „4/12 Zyklen" → jetzt: step_label „Gerade: ANT2 · 10 dB"
   (Lebenszeichen) + Balken-Text „Zyklus 5 / 12 · noch ~2:00 min".
   **Off-by-one behoben:** Balkenwert zählt jetzt den LAUFENDEN Zyklus mit (`setValue(_step+1)`)
   → Balken und Text nennen dieselbe Zahl (vorher Balken=_step=4, Label=_step+1=5).
3. **time_label-Widget entfernt:** Restzeit wandert in den Balken-Text (`_update_time`
   setzt `progress.setFormat(...)` statt `time_label.setText(...)`).
4. **mode_label „Misst gleichzeitig für Standard- und DX-Modus" entfernt** (+ aus
   `_apply_state_ui`-Visibility-Schleife).
5. **detail_label-Widget BLEIBT** für ADC-Übersteuerungs-Warnung + Abschluss-Meldung;
   im Normalbetrieb jetzt leer (`setText("")` in `_start_step`).
6. **Gelber 2-Zeilen-Fachjargon-Block → eine graue Zeile** „TX bleibt auf ANT1 ·
   vergleicht ANT1 ⇄ ANT2".
7. **Results-Header** „(Top-5 SNR-Schnitt pro Kombination)" → „— Ø SNR pro Antenne & Gain".
8. **Höhe** 460/490/510 → 360/390/410 px.
9. Veraltete „8 Schritte"-Kommentare → „12 Schritte" (Schedule ist real 12: GAIN [0,10,20]).
10. Abschluss: `progress.setFormat("Fertig — alle Zyklen gemessen")` statt time_label-Clear.

## DIFF
```diff
diff --git a/ui/dx_tune_dialog.py b/ui/dx_tune_dialog.py
index d1c2a37..9100c9c 100755
--- a/ui/dx_tune_dialog.py
+++ b/ui/dx_tune_dialog.py
@@ -54,7 +54,7 @@ def _build_interleaved_schedule() -> list:
             for gain in GAIN_VALUES:
                 schedule.append(("ANT2", gain))
                 schedule.append(("ANT1", gain))
-    return schedule  # 8 Schritte (ROUNDS × 2 Antennen × 2 Gain-Stufen)
+    return schedule  # 12 Schritte (ROUNDS=2 × 2 Antennen × 3 Gain-Stufen [0/10/20])
 
 
 class DXTuneDialog(QDialog):
@@ -105,7 +105,7 @@ class DXTuneDialog(QDialog):
         self._tune_elapsed_s = 0
 
         # Messplan
-        self._schedule = _build_interleaved_schedule()  # 8 Schritte
+        self._schedule = _build_interleaved_schedule()  # 12 Schritte
         self._step = 0          # aktueller Schritt im Schedule
         self._phase_data = {}   # (ant, gain) -> [snr_werte]
         self._cancelled = False
@@ -113,14 +113,14 @@ class DXTuneDialog(QDialog):
 
         _mode_label = self._get_mode_label()
         self.setWindowTitle(f"{_mode_label} — Kalibrierung {band}")
-        # P75: Höhe +30 px für Banner wenn vorhanden (Phase-1-Übergang)
-        # P74-A: bei TUNE-Phase brauchen wir ~50 px extra für Spinner +
-        # Status-Label (in der GAIN-UI ausgeblendet).
-        _height = 460
+        # v0.99.8: Fenster verschlankt (doppelter Titel + 3 Fortschritts-Zähler
+        # raus) → Höhe von ~480 auf ~360 px. P75: +30 px für Banner.
+        # P74-A: TUNE-Phase braucht ~50 px extra (Spinner + Status-Label).
+        _height = 360
         if self._prev_tune_swr is not None:
-            _height = 490
+            _height = 390
         if with_tune_phase:
-            _height = 510
+            _height = 410
         self.setFixedSize(520, _height)
         self.setModal(False)  # Non-modal damit Decoder-Signale durchkommen
         self._setup_ui()
@@ -194,45 +194,42 @@ class DXTuneDialog(QDialog):
         )
         layout.addWidget(self._tune_status_label)
 
-        # Titel
-        title = QLabel(f"{self._get_mode_label()} — Kalibrierung {self.band}")
-        title.setStyleSheet("color: #00AAFF; font-size: 18px; font-weight: bold;")
-        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
-        self._title_label = title  # P74-A: für state-aware Wechsel
-        layout.addWidget(title)
-
-        hint = QLabel(
-            "12 Zyklen interleaved • ANT1 & ANT2 bei gleichem Gain verglichen\n"
-            "Dauert ca. 3 Minuten  •  TX bleibt immer auf ANT1"
-        )
-        hint.setStyleSheet("color: #FFD700; font-size: 11px;")
+        # v0.99.8: Großes Body-Titel-Label entfernt — war eine Doppelung des
+        # Fenstertitels (Titelleiste). Der zweizeilige gelbe „12 Zyklen
+        # interleaved …"-Block (Fachjargon) + die kursive „Misst gleichzeitig
+        # für Standard- und DX-Modus"-Zeile sind durch diese eine knappe graue
+        # Zeile ersetzt — nur die für den Funker relevante Sicherheits-Info.
+        hint = QLabel("TX bleibt auf ANT1  ·  vergleicht ANT1 ⇄ ANT2")
+        hint.setStyleSheet("color: #888; font-size: 11px;")
         hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
         layout.addWidget(hint)
 
         layout.addWidget(self._sep())
 
-        # Aktueller Schritt
+        # v0.99.8: „Gerade: ANT2 · 10 dB" — ein Lebenszeichen welche Kombination
+        # gerade gemessen wird (ersetzt „Runde 1/2 — ANT1 Gain 20 dB").
         self.step_label = QLabel("Starte Messung...")
         self.step_label.setStyleSheet("color: #00AAFF; font-size: 13px; font-weight: bold;")
         layout.addWidget(self.step_label)
 
+        # detail_label bleibt für ADC-Übersteuerungs-Warnung + Abschluss-Meldung;
+        # im Normalbetrieb leer (das frühere „Schritt 5/12 (5/6 in dieser Runde)"
+        # ist entfallen — der Fortschritt steht jetzt allein im Balken-Text).
+        # mode_label „Misst gleichzeitig …" (P51) ist ganz entfallen.
         self.detail_label = QLabel("")
         self.detail_label.setFont(_FONT_MONO_SM)
         self.detail_label.setStyleSheet("color: #AAA;")
         layout.addWidget(self.detail_label)
 
-        # P51 (v0.97.28): Hinweis dass Messung gleichzeitig fuer beide Modi gilt.
-        self.mode_label = QLabel("Misst gleichzeitig für Standard- und DX-Modus")
-        self.mode_label.setStyleSheet("color: #66AACC; font-style: italic; font-size: 11px;")
-        layout.addWidget(self.mode_label)
-
-        # Fortschritt
+        # Fortschritt — EIN Zähler: Balken-Text trägt Zyklus + Restzeit
+        # („Zyklus 5 / 12 · noch ~2:00 min"), gesetzt in _update_time. Der Wert
+        # zählt den LAUFENDEN Zyklus mit (_step+1) → kein 4-vs-5-Widerspruch mehr.
         self.progress = QProgressBar()
         self.progress.setRange(0, len(self._schedule))
         self.progress.setValue(0)
         self.progress.setFixedHeight(22)
         self.progress.setTextVisible(True)
-        self.progress.setFormat(f"%v / {len(self._schedule)} Zyklen")
+        self.progress.setFormat(f"Zyklus 0 / {len(self._schedule)}")
         self.progress.setStyleSheet("""
             QProgressBar {
                 background-color: #222; border: 1px solid #444;
@@ -247,15 +244,10 @@ class DXTuneDialog(QDialog):
         """)
         layout.addWidget(self.progress)
 
-        self.time_label = QLabel("")
-        self.time_label.setStyleSheet("color: #666; font-size: 10px;")
-        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
-        layout.addWidget(self.time_label)
-
         layout.addWidget(self._sep())
 
         # Ergebnisse
-        results_header = QLabel("Zwischenergebnisse  (Top-5 SNR-Schnitt pro Kombination)")
+        results_header = QLabel("Zwischenergebnisse  —  Ø SNR pro Antenne & Gain")
         results_header.setStyleSheet("color: #888; font-size: 10px; font-weight: bold;")
         layout.addWidget(results_header)
 
@@ -306,8 +298,8 @@ class DXTuneDialog(QDialog):
         self._tune_spinner.setVisible(is_tune)
         self._tune_status_label.setVisible(is_tune)
         # Phase-2-UI nur ausserhalb TUNE
-        for w in (self.step_label, self.detail_label, self.mode_label,
-                  self.progress, self.time_label, self.results_text):
+        for w in (self.step_label, self.detail_label,
+                  self.progress, self.results_text):
             w.setVisible(not is_tune)
 
     def _start_tune_phase(self):
@@ -451,16 +443,14 @@ class DXTuneDialog(QDialog):
         self.radio.set_rfgain(gain)
         self.radio.set_tx_antenna("ANT1")
 
-        round_num = self._step // (len(GAIN_VALUES) * 2) + 1
-        pos_in_round = self._step % (len(GAIN_VALUES) * 2) + 1
-        self.step_label.setText(
-            f"Runde {round_num}/{ROUNDS} — {ant}  Gain {gain} dB"
-        )
-        self.detail_label.setText(
-            f"Schritt {self._step + 1}/{len(self._schedule)}  "
-            f"({pos_in_round}/{len(GAIN_VALUES) * 2} in dieser Runde)"
-        )
-        self.progress.setValue(self._step)
+        # v0.99.8: nur noch ein Lebenszeichen welche Kombination läuft. Die
+        # frühere „Runde X/Y" + „Schritt X/Y (X/Y in Runde)"-Doppelung ist
+        # entfallen — der Fortschritt steht allein im Balken (_update_time).
+        self.step_label.setText(f"Gerade:  {ant} · {gain} dB")
+        self.detail_label.setText("")
+        # Wert zählt den LAUFENDEN Zyklus mit (_step+1) → Balken und Text
+        # nennen dieselbe Zahl, kein 4-vs-5-Widerspruch.
+        self.progress.setValue(self._step + 1)
         self._update_time()
         self._update_results_display()
 
@@ -717,7 +707,7 @@ class DXTuneDialog(QDialog):
         )
         self.detail_label.setStyleSheet("color: #44FF44;")
         self.progress.setValue(len(self._schedule))
-        self.time_label.setText("")
+        self.progress.setFormat("Fertig — alle Zyklen gemessen")
         self.btn_cancel.setVisible(False)
         self._update_results_display()
         # Automatisch speichern und Dialog schliessen (Programm laeuft sofort weiter)
@@ -767,10 +757,17 @@ class DXTuneDialog(QDialog):
         self.results_text.setText("\n".join(lines) if lines else "—")
 
     def _update_time(self):
-        remaining = len(self._schedule) - self._step
+        # v0.99.8: Zyklus-Zähler + Restzeit zusammen im Balken-Text (eine Quelle
+        # statt früher Balken + separates time_label). Der laufende Zyklus zählt
+        # mit (_step+1), die Restzeit umfasst die noch nicht begonnenen Zyklen.
+        n = len(self._schedule)
+        current = min(self._step + 1, n)
+        remaining = n - self._step
         secs = remaining * 15
         m, s = divmod(secs, 60)
-        self.time_label.setText(f"Restzeit: ca. {m:.0f}:{s:02.0f} min")
+        self.progress.setFormat(
+            f"Zyklus {current} / {n}  ·  noch ~{m:.0f}:{s:02.0f} min"
+        )
 
     def _on_cancel(self):
         """P74-A: state-aware Cancel.

```

## Prüf-Auftrag (kritisch, Code ist Referenz)
1. **Kein toter Verweis:** Greift irgendwo noch Code auf `self.time_label`, `self.mode_label`
   oder `self._title_label` zu (→ AttributeError zur Laufzeit)? Besonders in `_apply_state_ui`,
   `_finish`, `_start_step`, `_update_time`, Fehler-/Cancel-Pfade.
2. **Balken-Logik:** `setValue(_step+1)` + `_update_time` setzt Format „Zyklus {current} / {n}
   · noch ~{m}:{s} min" mit `current = min(_step+1, n)`, `remaining = n - _step`. Stimmen
   Zähler und Restzeit über alle Schritte (0..11) + Abschluss? Beim letzten Schritt (_step=11):
   current=12, remaining=1 → „Zyklus 12/12 · noch ~0:15 min" — danach `_finish` setzt
   „Fertig". Konsistent?
3. **detail_label:** wird in `_start_step` auf "" gesetzt, in der ADC-Warnung + im Abschluss
   befüllt (orange/grün). Ist das schlüssig (keine hängende alte Warnung)? Beim nächsten
   Schritt nach einer ADC-Warnung wird sie geleert — gewollt?
4. **`_apply_state_ui`:** Visibility-Schleife enthält jetzt nur noch (step_label,
   detail_label, progress, results_text). Fehlt etwas, das in der TUNE-Phase versteckt
   werden müsste? (mode_label/time_label gibt es nicht mehr.)
5. **Höhe:** reichen 360/390/410 px für den verschlankten Inhalt, oder Gefahr dass der
   Balken-Text „Zyklus 5 / 12 · noch ~2:00 min" oder die Results-Box abgeschnitten wird?
6. **Regression:** ist die Mess-/Scoring-/Antennen-Logik wirklich unberührt (kein TX-Pfad,
   ANT1 bleibt TX)? Wurde versehentlich Verhalten geändert statt nur Anzeige?
7. **Übersehenes / KISS:** etwas zu viel oder zu wenig?

Urteil: **PUSH FREIGEBEN** oder **NICHT FREIGEBEN** (mit konkreten Bugs).
