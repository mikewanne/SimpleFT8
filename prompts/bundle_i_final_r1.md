[deepseek] ~43167 Tokens, 5 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=48819 out=4620 total=53439
**Code-Review Bundle I (v0.97.25 → v0.97.26)**  
Geprüft: `settings_dialog.py` Z.333–356, `qso_state.py` Z.530–720, `mw_radio.py` Z.541–560, Tests T4.1–T4.8 + T2.1–T2.8.

---

## 1. `settings_dialog.py` Z.333–356 – GroupBox Sichtbare Bänder

**Bewertung: Korrekt, kein Bug.**  
- `bands_group.setStyleSheet` ist lokal auf die GroupBox begrenzt – andere QCheckBoxes im Dialog (z. B. `stats_cb`, `debug_console_cb`) bleiben unberührt. Stylesheet-CSS-Selektor `QCheckBox::indicator` greift nur innerhalb des GroupBox-Scopes.  
- Spacing 10→16 und Margins (12,8,12,10)→(16,16,16,16) sind reine Layout-Kosmetik, keine Logik-Auswirkung.  
- KISS: erfüllt. Keine neue Methode, nur Zahlenwerte geändert.  
- Tests: nicht nötig (reines UI-Layout ohne signal/seitige Logik).

✅ **Grünes Licht.**

---

## 2. `qso_state.py` – Verschiebung `qso_confirmed_visual` + Doppelschutz-Pfad

### 2.1 Haupt-Pfad: 73-Empfang → Courtesy-Send → visual

Vorher:
```
Empf. 73 → sofort visual.emit (zu früh) → Sende 73 → full.emit → CQ
```
Jetzt (Bundle I):
```
Empf. 73 → *kein Emit* → Sende 73 (TX_73_COURTESY) → NACH Sende: visual + full → CQ
```

**Analyse des Code-Flusses (qso_state.py):**  

1. `on_message_received` (WAIT_73-Branch, ~Z.690):
   - `is_73 or is_rr73` → `courtesy_73_sent = True`, State = `TX_73_COURTESY`, `send_message("73")`.
   - **Kein** `qso_confirmed_visual.emit()` mehr hier. ✅  

2. `on_message_sent` (TX_73_COURTESY-Branch, ~Z.715):
   - `qso_confirmed_visual.emit(self.qso)` gefolgt von `qso_confirmed.emit(self.qso)`.
   - Danach `_resume_cq_if_needed()`. ✅

**Bewertung:**  
- Reihenfolge im QSO-Panel ist jetzt: *Empf. 73* → *Sende 73* → *✓ QSO komplett*.  
- Mike-Wunsch (visual NACH Courtesy-Send) exakt umgesetzt.  
- Kein Race: `_set_state(TX_73_COURTESY)` erfolgt VOR dem `send_message.emit` (wie seit P1.10 Fix), sodass `on_message_received` im nächsten Zyklus nicht nochmal den gleichen Branch trifft.  
- Test T2.1–T2.5 bestätigen die korrekte Reihenfolge.

### 2.2 Doppelschutz-Pfad (else-Branch in WAIT_73)

```python
else:
    # Hypothetischer Doppelschutz
    self.qso_confirmed_visual.emit(self.qso)
    self.qso_confirmed.emit(self.qso)
    self._resume_cq_if_needed()
```

**Frage:** `visual + full` direkt nacheinander OK weil `courtesy_73_sent` schon `True` ist?

**Antwort: Ja, das ist korrekt.**  
- Dieser Pfad wird nur betreten, wenn `courtesy_73_sent` bereits `True` ist, der State aber trotzdem noch `WAIT_73` ist – ein hypothetischer Edge-Case, der im regulären Betrieb nicht vorkommt (State wechselt nach erstem 73 auf `TX_73_COURTESY` und nach `on_message_sent` weiter zu `IDLE`).  
- Dass `courtesy_73_sent = True` bedeutet: Das Courtesy-73 wurde bereits gesendet. Es gibt also keinen ausstehenden TX-Slot mehr, der noch eine Verzögerung erfordert. `visual + full` sofort zu feuern, ist hier korrekt und risikofrei – es gibt keinen Timing-Konflikt mehr, weil nichts mehr gesendet wird.  
- Das ist ein defensiver Fallback, der die Maschine in einen sauberen Endzustand bringt, falls sie durch einen externen Fehler (z. B. Event-Doppelung) nochmal in diesen Branch springt.

✅ **Korrekt und sicher.**

---

## 3. `mw_radio.py` Z.541–560 – Stop-Block in `_on_rx_mode_changed`

**Code:**
```python
if mode != old_mode:
    if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
        self._omni_cq.stop("rx_mode_change")          # 1
    if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
        self._auto_hunt.stop_auto_hunt("rx_mode_change") # 2
    if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
        self.qso_sm.stop_cq()                          # 3
        self.qso_sm.cancel()
        self.control_panel.set_cq_active(False)
    if self.encoder.is_transmitting:
        self.encoder.abort()                           # 4
        if self.radio.ip:
            self.radio.ptt_off()
```

### 3.1 Reihenfolge OMNI → AutoHunt → qso_sm → encoder.abort+ptt_off

**Frage:** Risiko dass OMNI-Stop irgendwas mit encoder macht das mit unserem abort kollidiert?

**Antwort: Kein Risiko.**

- **OMNI-Stop** (`core/omni_cq.py:stop`) setzt Flags (`_active=False`, `_mode=None`), cleart den eigenen TX-Attempt-Stack und feuert `status_changed`. OMNI selbst steuert **keinen** Hardware-Encoder direkt; es reicht CQ-Nachrichten über Signale an `qso_sm` weiter. Es gibt keine OMNI-Methode, die den `encoder`-Thread oder das `is_transmitting`-Flag antastet.  
- **AutoHunt-Stop** (`stop_auto_hunt`) setzt ebenfalls nur Flags und stoppt interne Timer – kein Encoder-Zugriff.  
- **`qso_sm.stop_cq()` + `cancel()`** setzen den State auf IDLE und löschen Pendings – kein Encoder-Zugriff.  
- **`encoder.abort()`** erfolgt **danach** als letzter Schritt. Selbst wenn OMNI/AutoHunt/qso_sm hypothetisch den Encoder modifizieren würden (tun sie nicht), ist `abort()` der definitive K.O.-Schlag, der alle ausstehenden Übertragungen abbricht und `is_transmitting` auf False setzt.

Die Reihenfolge ist **logisch absteigend**: erst die High-Level-Controller ausschalten (damit sie keine neuen Nachrichten generieren), dann die QSO-Maschine neutralisieren, dann das Low-Level-Transmit-Hardware-Signal killen.  
Genau dieses Pattern ist in `_on_band_changed` Z.404–414 seit Langem im Einsatz und hat sich bewährt.

✅ **KISS-konform, kein Kollisions-Risiko.**

---

## 4. Test T4.6 – Bandpilot-Pfad

**Auszug:**
```python
def test_t4_6_bandpilot_path_also_stops_cq(app):
    obj = _make_mw_radio(cq_mode=True, qso_state_name="CQ_CALLING")
    obj._on_rx_mode_changed("diversity")
    obj.qso_sm.stop_cq.assert_called_once()
```

**Frage:** Testet nicht echten Bandpilot-Aufruf sondern nur dass der gleiche Code-Pfad läuft — ausreichend oder muss `_apply_bandpilot_auto` explizit getestet werden?

**Antwort: Ausreichend für diesen Bundle-Scope.**

**Begründung:**
- Der Stop-Block sitzt in `_on_rx_mode_changed`. Egal welcher Caller (`_on_rx_panel_toggled`, `_apply_bandpilot_auto` via `_set_rx_mode_direct`, oder manueller Mode-Click), **derselbe Code** wird durchlaufen.  
- Ein separater Integrationstest, der den vollen Bandpilot-Pfad (`_maybe_apply_bandpilot` → `_apply_bandpilot_auto` → `_set_rx_mode_direct` → `_on_rx_mode_changed`) mit Mock-Statistiken aufbaut, würde fast 100 Zeilen Setup benötigen (Mock für ModeRecommender, Settings, radio.ip, encoder etc.).  
- Der **Fehler aus dem Field-Test** (OMNI an, Mode-Wechsel, verzögerter CQ-Slot) wird durch die existierenden T4.1–T4.8 vollständig abgedeckt: der kritische Pfad ist `cq_mode=True + State != IDLE` → `stop_cq` + `cancel`.  
- KISS: Unit-Test auf der Ebene, wo der Bug gefixt wurde, ist angemessen. Ein expliziter Bandpilot-Integrationstest wäre Overkill für diesen Fix, könnte aber in einem späteren Bundle, das den Bandpilot überholt, sinnvoll sein.

**Empfehlung:** Wenn der Bandpilot in einem künftigen Bundle signifikant umgebaut wird, kann man dort einen Integrationstest nachrüsten. Für Bundle I ist T4.6 ausreichend.

✅ **Test-Abdeckung im Scope ausreichend.**

---

## 5. Gesamt-Fazit

| Änderung | Status | Begründung |
|----------|--------|-----------|
| Settings-Dialog Layout | ✅ OK | Nur Kosmetik, kein Bug |
| qso_confirmed_visual-Verschiebung | ✅ OK | Korrekte Reihenfolge, Tests grün |
| Doppelschutz else-Branch | ✅ OK | Defensiver Fallback, kein Timing-Konflikt |
| Stop-Block _on_rx_mode_changed | ✅ OK | Reihenfolge sicher, analog Bandwechsel |
| T4.6 Test-Scope | ✅ Ausreichend | Gleicher Code-Pfad, KISS |
| Alle 15 neuen Tests grün (1205→1220) | ✅ OK | Regression bestätigt |

**Keine Bugs gefunden.** Die Änderungen sind logisch konsistent, defensiv abgesichert und KISS-konform. Das Bundle kann ohne Änderungen angenommen werden.
