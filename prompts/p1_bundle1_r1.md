# P1-Bundle1 R1 Findings (DeepSeek-Reasoner)

**Stand:** 2026-05-06, R1-Review von V2 mit 4 Code-Files.
**Tokens:** in=64193 out=7662 total=71855.
**Workflow:** V1 → V2 → **R1** (diese Datei) → V3.

---

## 6.1 Theme-Konsistenz
- **`#666` für P1.6** – korrekt, wird in `qso_panel.py` für Status-Texte verwendet (z.B. `status_label`, Zeile ~111). Passt zur Konvention.
- **`#00DDFF` für aktive Sterne** – Neon-Cyan, entspricht Theme (in styles.py als `CYAN` definiert, vgl. Kommentar „Neon-Cyan #00DDFF"). OK.
- **`#3a3a4e` für inaktive Sterne** – im Code nicht direkt als Konvention etabliert. Es gibt `#3a3a5e` in `mw_radio.py` (Dialog-Hover), das ist nah dran. **Risiko:** `#3a3a4e` könnte auf `#1a1a2e` Hintergrund zu wenig Kontrast bieten – V2 selbst fragt das. Ich empfehle stattdessen `#444` oder `#555` wie die inaktiven Band-Buttons in `control_panel.py` (z.B. `QPushButton:checked`-Hintergrund). Sonst: Theme-konsistent.

## 6.2 Sub-Aufgaben-Konflikte
Alle 5 Sub-Aufgaben bearbeiten getrennte Code-Bereiche:
- P1.6: `control_panel.py` Easter-Egg-Zeile (`_version_label`).
- P1.12: `control_panel.py` (Antennenkarte+Signale) + `main_window.py` + `mw_radio.py`.
- P1.15: `main_window.py` (`_update_statusbar`).
- P1.16: `qso_panel.py` (`_auto_trim` + neue Timestamp-Liste).
- P1.19: `control_panel.py` (`_QSOStatusCard.snr_label` → neues Widget) + neuer `StarsConditionWidget`.

Keine gemeinsamen Variablen oder Methoden (ausser `status_label`-Referenzen, aber die sind getrennt). **Kein Konflikt.** ✅

## 6.3 Test-Coverage
V2 zählt „14 neue Tests". Die konkrete Aufstellung:
- P1.6: 0 Unit-Tests (nur Smoke).
- P1.12: 0 Unit-Tests (bestehende Tests auf `btn_remeasure`-Referenz prüfen).
- P1.15: 0 Unit-Tests (nur Smoke).
- P1.16: 4 Tests (`_append_colored`, `mock time.time`, Trenn-Linien, Scroll-Position).
- P1.19: 4 Tests (`compute_local_conditions` 3 Fälle + Widget+Rendering+Tooltip).

Summe: 8 Unit-Tests, nicht 14. Die restlichen 6 sind wohl Smoke-Tests oder bestehende Test-Anpassungen. **In der Liste fehlen explizite Tests für:**
- P1.15: Assertion dass `status_label` NICHT `→ Call` enthält nach Aktivierung.
- P1.12: Assertion dass `btn_remeasure` nicht existiert (oder dass `Phase-Label` allein ist).
- P1.16: Integrationstest mit mehreren `add_tx`/`add_rx`-Aufrufen und anschließendem Trim.
- P1.19: Test für Tooltip-Format (z.B. `"5 Stationen, Median -12 dB"`).

Die 14 Tests sind also **nicht vollständig aufgeschlüsselt** – ich empfehle, die fehlenden Tests zu ergänzen, sonst wird die Abdeckung überschätzt.

## 6.4 P1.16 Performance
V2 rechnet mit ~200 Blocks bei 20 QSOs × 10 Einträge = 200. Das ist konservativ: Bei intensiver Session (z.B. 40 QSOs/h) könnten es bis zu 400 werden. Der 30s-Timer iteriert dann über 400 `self._block_timestamps` – das ist O(n) und braucht <1 ms. **Performance unkritisch.**
**Edge Case übersehen:** Die `_auto_trim_by_age`-Methode löscht alte Blocks, aber wenn der User manuell `clear()` auf dem QTextEdit aufruft (gibt es aktuell nicht, könnte später kommen), muss die Timestamp-Liste resynchronisiert werden. V2 erwähnt „Re-Build der Liste nach Cleanup", aber implementiert keinen `clear`-Hook. Für V3 einplanen.

## 6.5 P1.19 Berechnungs-Schwellen
**FT8-Domain-Prüfung:**
- **Typische Stationsanzahl auf 40m/20m:** Tagsüber auf 20m oft 30–60 aktive Stationen im sichtbaren Fenster. 25 für 5 Sterne ist realistisch (ca. 50% der Maximalbelegung). Auf 40m nachts ähnlich.
- **SNR-Skala:** Median > -12 dB ist ein gutes Signal (stark rauschend, aber klar decodierbar). -22 dB für 2 Sterne ist die Untergrenze für zuverlässigen Decode (~5% Fehlerrate). Die Schwellen sind sinnvoll und nicht überoptimiert.
- **Kompatibilität mit Datenstruktur:** `_normal_stations`/`_diversity_stations` sind Dicts, deren Values `FT8Message`-Objekte sind. Diese haben `.snr` (wird in `_build_map_snapshot` als `float(msg.snr)` verwendet). ✅ **Kompatibel.**
- **Median-Definition:** V2 verwendet „obere Hälfte nach SNR absteigend sortiert" – das ist ein **einseitiger** Median (nicht der klassische Median aller Werte). Das ist für FT8 sinnvoll, weil schwache Stationen (Rauschen) den Median nicht drücken. Kein Einwand.

## 6.6 Atomarer Commit?
5 unabhängige UI-Änderungen, ~150 Zeilen, thematisch verwandt (UI-Cleanup). **Atomarer Commit ist akzeptabel**, solange die Commit-Message sauber listet, was geändert wurde. Ich würde jedoch **empfehlen, P1.16 (QSO-Panel Rolling) und P1.19 (Sterne) als zweiten Commit auszugliedern**, weil sie neue Funktionalität einführen (nur Cleanup + neues Widget) – das erleichtert späteres Revert. Aber Mike's „1 Commit"-Vorgabe können wir so erfüllen.

## 6.7 Order von Tests
Triviale Tests zuerst (P1.6,12,15), dann zeitbasierte (P1.16), dann `compute_local_conditions` (P1.19). **Reihenfolge sinnvoll.** Ergänzung: Die Widget-Rendering-Tests (P1.19) sollten nach den reinen Logik-Tests kommen, damit man bei Fehlern sofort weiß, ob die Logik oder das Layout kaputt ist.

## 6.8 Backward-Compat
**Kritischer Punkt:** V2 sagt „`update_snr()` weiter aufrufbar (intern nötig)". Aber `update_snr()` in `control_panel.py` setzt `snr_label.setText(...)`. Wenn wir `snr_label` durch `conditions_widget` ersetzen, stürzt `update_snr()` ab (AttributeError: `StarsConditionWidget` hat kein `setText`).
**Lösung:** V2 schreibt „Bestehende `update_snr(snr)` Methode beibehalten" – das funktioniert nicht. Entweder `update_snr()` muss umdefiniert werden (z.B. als Dummy oder zur internen Logik) oder die `snr_label`-Referenz muss bestehen bleiben (z.B. `snr_label` unsichtbar machen). **Klärung in V3 erforderlich.**

**Weitere Backward-Kompatibilität:**
- P1.12: Entfernung von `btn_remeasure` und Signal `remeasure_clicked` → alle Referenzen entfernt (bestätigt). ✅
- P1.15: Nur der `→ Call | RX: ANT`-Block gelöscht, andere Status-Label-Aufrufe bleiben (z.B. `"X QSO(s) diese Session"`). ✅
- P1.16: Alte `_auto_trim` wird durch neue Methode ersetzt → kein API-Bruch (nur intern). ✅

## Neue Befunde (KP1-KP5)

### KP1 – `update_snr()` bricht nach P1.19-Ersetzung ⛔ KRITISCH
- **Problem:** `update_snr()` in `control_panel.py` setzt `self.snr_label.setText(...)`. Nach Ersetzung durch `conditions_widget` existiert `snr_label` nicht mehr → RuntimeError.
- **Code-Stelle:** `control_panel.py` Methode `update_snr(self, snr)` (ca. Zeile 895).
- **Empfehlung:** Entweder `update_snr()` entfernen und alle Aufrufer durch `update_local_conditions()` ersetzen, oder `snr_label` als unsichtbaren Platzhalter behalten (`self.snr_label = QLabel()` → `self.snr_label.hide()`). KISS: Ersetzung aller `update_snr`-Aufrufe (prüfen in `main_window.py`, `mw_radio.py` etc.). V2 hat das schlicht übersehen.

### KP2 – P1.16: Kein Schutz vor manuellem Clear()
- **Problem:** Wenn jemals `self.log_view.clear()` aufgerufen wird, bleibt `self._block_timestamps` alt → folgende `_auto_trim_by_age` löscht fälschlich neue Zeilen.
- **Empfehlung:** `_auto_trim_by_age` sollte vor Löschung prüfen ob `len(self._block_timestamps) > document.blockCount()`, und wenn ja, die Liste kürzen (`self._block_timestamps = self._block_timestamps[-document.blockCount():]`).

### KP3 – P1.12: Orphan-Signal `remeasure_clicked`
- **Problem:** `Signal()` in `ControlPanel` bleibt als Bloat wenn Button + Connection entfernt sind.
- **Empfehlung:** Signal-Definition aus `ControlPanel`-Klassendefinition löschen.

### KP4 – P1.15: Präzise Code-Stelle ist `_update_statusbar`
- **Problem:** V2 sagt „in `_on_state_changed` o.ä." – faktisch in `MainWindow._update_statusbar()` (Zeilen ~930-944).
- **Empfehlung:** In V3 präzise referenzieren.

### KP5 – P1.19: Widget-Zuordnung `_QSOStatusCard` ↔ `ControlPanel`
- **Problem:** `snr_label` ist Attribut von `_QSOStatusCard`, wird in `ControlPanel.__init__` per `self.snr_label = qso_card.snr_label` geholt. Bei Ersetzung muss auch das in `_QSOStatusCard` definiert werden.
- **Empfehlung:** `StarsConditionWidget` in `_QSOStatusCard` platzieren, `ControlPanel.conditions_widget = qso_card.conditions_widget`.

## Empfehlung Gesamt
- **Plan freigegeben** mit folgenden Auflagen:
  1. **KP1 (update_snr) zwingend klären:** Entweder alle Aufrufer auf `update_local_conditions` umstellen oder `snr_label` als unsichtbaren Stub lassen. In V3 diskutieren.
  2. **KP2 (Clear-Bug) in P1.16-Code einbauen** – sonst später schwer zu findender Datenfehler.
  3. **KP3 (orphan Signal) bereinigen** – kleine Sauberkeit.
  4. **KP4 und KP5 sind nur Präzisierungen** – kein Block.
- Tests: Die 14 Tests in V2 sind grob geschätzt. Bitte vor V3 eine konkrete Test-Liste mit mindestens 10 Unit-Tests + Smoke aufstellen.
- **Gesamtaufwand:** überschaubar, Hobby-Tool-KISS-Philosophie bleibt gewahrt.
