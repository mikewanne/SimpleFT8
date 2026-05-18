# P76-A SWR-Safety-Bug — V2 (Self-Review)

**Workflow-Schritt:** V1 → **V2** → R1 → V3
**Datum:** 18.05.2026 nach Compact
**Vorgaenger:** prompts/p76a_swr_safety_v1.md

---

## Code-Verifikation durchgefuehrt

### 1. Bug-Stelle bestaetigt

`ui/mw_tx.py:_tune_post_swr_check` Z.262 `swr_now = self.radio.last_swr`. **Bug echt.**

### 2. FlexRadio `last_swr`-Verhalten (radio/flexradio.py)

- Z.69 `self._last_swr = 1.0` — Init
- Z.1382-1396 `_handle_meter` SWR-Branch:
  ```python
  swr = val
  if swr < 1.0 or swr > 50.0:
      swr = raw / 256.0  # Alternativer Divisor
  if swr < 1.0:
      swr = 1.0          # ← BUG-Quelle: <1.0 wird auf 1.0 geclamped
  if 1.0 <= swr <= 50.0:
      self._last_swr = swr  # ← wird tatsaechlich ueberschrieben
  ```

- Nach `tune_off()` kommen weiter Meter-Updates. Ohne TX-Traeger sind die Werte chaotisch niedrig (<1.0) → Clamp auf 1.0 → `_last_swr=1.0`.

**Mike-Symptom „TUNE OK SWR 1.0" 3× hintereinander passt exakt zu diesem Pfad.**

### 3. Phase B + Cancel-Pfad

`_tune_converge_to_target` (Z.370-442):
- Initial-Sample-Phase: `_wait_with_event_loop(1500)` — 1.5 s mit aktivem Event-Loop, SWR-Updates kommen rein
- Max 5 Iterationen × 1000 ms — weitere SWR-Updates
- **Waehrend Phase B ist TX aktiv** (`tune_on()` noch nicht abgeschaltet) → SWR-Werte sind valid und aktualisieren `_last_swr` fortlaufend
- Cancel via `_tune_convergence_cancelled = True` → return None → Phase B beendet

**Konsequenz:** Direkt VOR `tune_off()` ist `radio.last_swr` der frischeste valide Wert — egal ob Phase B durchlief, abgebrochen wurde oder uebersprungen (SWR-bad-Skip).

### 4. Re-Entry-Pfad

`_tune_stop` (Z.167-170):
```python
if getattr(self, '_tune_stop_active', False):
    self._tune_convergence_cancelled = True
    return
self._tune_stop_active = True
```

2. Aufruf returnt **ohne `tune_off()`** → kein Freeze noetig (1. Aufruf macht ihn).
✓ Freeze unconditional vor Z.192 ist sicher.

---

## Findings

### F1 ✅ V1-Diagnose verifiziert

Bug-Mechanik durch FlexRadio-Clamp + Meter-Loop-Persistenz nach TX-Off ist exakt wie in V1 beschrieben. Mike's Symptom matched 1:1.

### F2 ⚠️ Init-Stelle muss praezisiert werden

`mw_tx.py` ist **Mixin** ohne eigenes `__init__`. Init-Pattern in diesem Modul (Beispiele):
- `self._fwdpwr_samples` — initialisiert in MainWindow.__init__ via Mixin-Init oder bei erster Verwendung
- `self._tune_active = False` — initialisiert in MainWindow.__init__
- `self._tune_post_check_token = object()` — wird in `_tune_stop` neu erzeugt, kein Vorab-Init noetig

**Loesung V2:**
- Option A: In `ui/main_window.py:__init__` analog `_tune_active`: `self._tune_last_valid_swr: float | None = None`
- Option B: Defensive `getattr(self, '_tune_last_valid_swr', None)` ueberall

**Empfehlung V2:** Option A (explizit in main_window.py initialisieren — konsistent mit existierendem Pattern).

### F3 ⚠️ Disconnect-Edge

V1 hatte `if self.radio.ip:` um den Freeze. Das ist **falsch**:

- Bei Disconnect mitten im TUNE: `radio.last_swr` ist letzter valider Wert vor Verbindungsabbruch
- Diesen wollen wir trotzdem einfrieren!
- `_tune_post_swr_check` Z.254 hat schon eigenen Disconnect-Guard (`if not self.radio.ip: emit FAIL + return`)

**Korrektur V2:** Freeze unconditional VOR `tune_off()` ohne `radio.ip`-Guard. `radio.last_swr` als Property liest nur lokales `_last_swr`-Attribut — funktioniert auch bei Disconnect.

### F4 ⚠️ Variante A vs C — Empfehlung Variante A

- Phase B laeuft ~6.5 s mit kontinuierlichen SWR-Updates (Event-Loop aktiv)
- `_last_swr` wird permanent aktualisiert (jeder Meter-Frame)
- Single-Snapshot direkt vor `tune_off()` = letzter valide Wert
- Sampling-deque (Variante C) waere Overkill, mehr Code, mehr Test-Aufwand
- KISS schlaegt Eleganz (CLAUDE.md Programmier-Leitsatz 1)

**Empfehlung V2:** Variante A. R1 darf gerne Variante C als Sicherheits-Variante diskutieren, aber Variante A reicht funktional.

### F5 ⚠️ AC1-Wording praezisieren

V1-AC1: „Bei SWR > Limit waehrend TUNE → Band-Marker gesetzt" — das ist schon P63-Verhalten.

**V2-AC1 (praeziser):**
- AC1: Wenn `radio.last_swr` direkt vor `tune_off()` > `swr_limit` ist, dann liest `_tune_post_swr_check` 2 s spaeter genau diesen Wert (z.B. 2.7), NICHT den durch Meter-Loop-Clamp auf 1.0 gesprungenen Wert.

### F6 ⚠️ Test-Strategie

**T1 (Setter):**
```python
def test_p76_freeze_swr_before_tune_off(monkeypatch):
    win = make_window_with_mock_radio()
    win.radio.last_swr = 2.7
    win._tune_active = True
    win.radio.tune_off = MagicMock()
    # Freeze sollte VOR tune_off() passieren
    win._tune_stop(None)
    assert win._tune_last_valid_swr == 2.7
    # tune_off() wurde danach gerufen
    win.radio.tune_off.assert_called_once()
```

**T3 (SWR-bad-Pfad mit Bug-Schutz):**
```python
def test_p76_swr_bad_after_tune_off_clamp(monkeypatch):
    win = make_window_with_mock_radio()
    win._tune_last_valid_swr = 2.7  # gefroren
    win.radio.last_swr = 1.0        # post-tune_off Clamp
    win.settings.swr_limit = 2.5
    win._tune_post_check_token = obj = object()
    win._tune_post_swr_check(obj)
    # Korrekt: liest gefrorenen Wert (2.7), nicht radio.last_swr (1.0)
    assert "17m" in win._swr_blocked_bands  # oder aktuelles Band
```

**T4 (SWR-OK-Pfad mit Bug-Schutz):**
```python
def test_p76_swr_ok_uses_frozen_value(monkeypatch):
    win._tune_last_valid_swr = 1.5
    win.radio.last_swr = 1.0       # post-tune_off Clamp
    win._tune_post_swr_check(obj)
    # add_info bekommt 1.5, nicht 1.0
    assert any("SWR 1.5" in call for call in win.qso_panel.add_info.call_args_list)
```

**T5 (Reset):**
```python
def test_p76_reset_after_post_check():
    win._tune_last_valid_swr = 2.7
    win._tune_post_swr_check(token)
    assert win._tune_last_valid_swr is None
```

**T6 (Fallback bei missing):**
```python
def test_p76_fallback_when_freeze_missing():
    win._tune_last_valid_swr = None  # Freeze hat nicht stattgefunden
    win.radio.last_swr = 1.0
    win.settings.swr_limit = 2.5
    win._tune_post_swr_check(obj)
    # Fallback liest radio.last_swr (1.0) → SWR-OK (defensive)
```

**T7 (Source-Level Check):**
```python
def test_p76_freeze_before_tune_off_source_check():
    code = Path("ui/mw_tx.py").read_text()
    # _tune_last_valid_swr = self.radio.last_swr MUSS vor self.radio.tune_off() stehen
    freeze_pos = code.find("self._tune_last_valid_swr = self.radio.last_swr")
    tune_off_pos = code.find("self.radio.tune_off()")
    assert 0 < freeze_pos < tune_off_pos
```

### F7 ⚠️ Phase-B-Skip-Branch (Mike's Fall)

Code Z.180-186:
```python
if swr_after_match <= swr_limit:
    self._tune_converged_rf = self._tune_converge_to_target(target_w=10)
else:
    print(f"[P54-FIX] Phase B SKIP — SWR {swr_after_match:.1f} > Limit ...")
    self._tune_converged_rf = None
```

**Mike's Fall (17m SWR 2.7):**
- Z.178: `swr_after_match = 2.7` (TX aktiv, Wert valid)
- Z.180: `2.7 <= 2.5` = False → Phase B SKIP
- Z.184-186: print + `_tune_converged_rf = None`
- Z.192: `tune_off()` — TX endet
- **Hier muss Freeze SEIN** zwischen Z.186 und Z.192.

Variante A funktioniert ohne Probleme — Freeze liest `self.radio.last_swr` welches noch 2.7 ist (kein Meter-Update kam zwischen Phase A und SKIP-Branch).

✓ OK fuer Mike-Fall.

### F8 ⚠️ State-Var Naming

`_tune_last_valid_swr` ist OK. Alternativen:
- `_tune_swr_frozen` — kuerzer, klarer Zweck
- `_tune_swr_pre_off` — beschreibt WANN gesichert
- `_tune_last_valid_swr` — beschreibt WAS gesichert (V1-Vorschlag)

**Empfehlung V2:** `_tune_last_valid_swr` (V1 lassen).

### F9 ⚠️ Auto-Tune-Pfad Konsistenz

`_tune_post_swr_check` Z.337+345 emittet `auto_tune_done(success, swr_now, fwdpwr)`. Mit Fix:
- `swr_now` ist der echte Wert (2.7) → Dialog zeigt korrekten SWR
- Signal-Konsumenten (AutoTuneDialog) zeigen jetzt echten Wert statt 1.0

✓ Bonus-Fix: AutoTuneDialog wird ehrlicher.

### F10 ⚠️ Logging in `_tune_post_swr_check`

Z.354: `print(f"[P63] Post-TUNE — SWR {swr_now:.1f}, Limit {swr_limit:.1f}")` — wird jetzt korrekten Wert printen. ✓

### F11 ⚠️ RFPreset-Save-Pfad

Wenn (im V1-Szenario-A) `swr_now <= swr_limit`, ruft Z.291-293 `rf_preset_store.save(... rf=rf_to_save)`.
- Vor Fix: bei false-OK (geclampter 1.0) → Save mit `rf_to_save=10` (hartcoded weil `_tune_converged_rf=None` bei Phase-B-Skip)
- Nach Fix: bei echtem SWR 2.7 → SWR-bad-Branch → KEIN Save → korrekt
- Nach Fix: bei echtem SWR 1.5 → SWR-OK-Branch + Save mit korrektem rf-Wert → korrekt

✓ RFPreset wird nicht mehr mit Falsch-Anker korrumpiert.

### F12 ⚠️ Migrations-Test

Keine Migration noetig — State-Var ist neu, alte Settings/Stores nicht betroffen.

---

## Aktualisierte Fix-Strategie

### Code-Aenderungen (3 Stellen)

**1. `ui/main_window.py` `__init__`** (1 Zeile)
- Nach existierenden `_tune_active`-Initialisierungen:
  ```python
  self._tune_last_valid_swr: float | None = None
  ```

**2. `ui/mw_tx.py:_tune_stop` direkt VOR `radio.tune_off()` Z.192** (3 Zeilen)
```python
# P76-A SAFETY: SWR einfrieren BEVOR tune_off().
# Nach tune_off() liefert FlexRadio Meter-Updates ohne TX-Traeger
# Werte <1.0 die auf 1.0 geclamped werden → false-OK-Bug.
self._tune_last_valid_swr = self.radio.last_swr
```

**3. `ui/mw_tx.py:_tune_post_swr_check` Z.262 ersetzen** (5 Zeilen)
```python
# P76-A SAFETY: gefrorenen Wert lesen (waehrend TX gemessen).
# Fallback nur wenn freeze nicht passiert ist (Defensive).
swr_now = self._tune_last_valid_swr
if swr_now is None or swr_now < 1.0:
    swr_now = self.radio.last_swr
self._tune_last_valid_swr = None  # Reset fuer naechsten TUNE
```

**Gesamt:** ~9 LOC ohne Tests. Sehr klein, sehr kontrolliert.

---

## Offene Fragen fuer R1-V4-pro

1. **Variante A bestaetigen?** Single-Snapshot vor `tune_off()` reicht oder Sampling-deque sicherer?
2. **F2 Init-Stelle:** main_window.py `__init__` korrekte Stelle? (oder besser via Mixin-Pattern?)
3. **F3 Disconnect-Edge:** Freeze unconditional ohne `radio.ip`-Guard — risikolos? `radio.last_swr` ist Property auf lokales Attribut → ja, sollte sicher sein.
4. **F6 Test-Strategie:** Genug Coverage mit 6 Tests + 1 Source-Level?
5. **F7 Phase-B-Skip-Branch:** Variante A deckt alle 3 Pfade ab (Skip / Convergenz / Cancel) — Verifikation OK?
6. **Reset-Timing:** `_tune_last_valid_swr = None` AM ENDE von `_tune_post_swr_check` vs SOFORT nach Read? KISS = am Ende, aber Race mit Re-Entry?

---

## Workflow-Schritte

✅ V1
✅ V2 (Self-Review — dieses Dokument)
⏭ **R1 mit DeepSeek-V4-pro** — Variante A bestaetigen + Edge-Cases pruefen
⏭ V3
⏭ Code (3 atomare Commits + Tests + Doku)
⏭ Final-R1
⏭ Field-Test
