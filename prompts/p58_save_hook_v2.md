# P58 — V2: Self-Review der V1-Spec

## Self-Review Findings

### SR1 — V1 schlägt Option B vor OHNE die Wurzel zu kennen

**Risiko:** Option B baut den Pfad um, aber wenn die Wurzel ein
ganz anderer Bug ist (z.B. Settings.set() schreibt nicht atomar →
get() liest stale Wert), würden wir das Symptom nicht den Bug
fixen.

**Code-Check verifiziert:** `config/settings.py` `set()` schreibt
in-memory dict + ruft `save()` der atomar JSON schreibt. `get()`
liest aus in-memory dict. **Kein Race.** Plus: Connect-Hook bei
Restart hat 1.5 gelesen — Persistenz funktioniert nachweislich.

**Hypothesen verbleibend:**
- A) `self.parent()` returnt nicht das erwartete Objekt
- B) `parent.radio.ip` ist None obwohl FlexRadio verbunden
- C) `getattr(parent.radio, "ip", None)` returnt None weil
  `ip`-Attribut nicht direkt am Radio, sondern hinter Property

**Lass mich Code-Check machen** für C:

→ `radio/flexradio.py`: `self.ip = "192.168.x.x"` wird gesetzt — sollte
  durchgehen. Aber: wann wird `self.ip` gesetzt? Möglicherweise erst
  am Ende der `connect()`-Methode. Während Connect-Phase ist `ip` None.

→ `radio/base_radio.py`: `RadioInterface` (ABC) — schau ob `ip`
  initialisiert wird.

**Befund:** Wenn die App schon eine Weile lief, ist `radio.ip` per
Definition ein gesetzter String. Wenn der Save-Hook NICHT propagierte,
muss es eine andere Wurzel sein.

→ **Diagnose-Print ist KRITISCH** — Option A muss VOR Option B
laufen, sonst raten wir.

### SR2 — Signal-Pattern braucht Lifecycle-Check

`QDialog` mit Signal: was passiert wenn Dialog ohne Save geschlossen
wird (Cancel/Esc)? Sollte Signal NICHT feuern. V1-Spec sagt nur
„Signal in `_save_and_close`" — das ist korrekt da nur dort emit.
Aber: gibt es weitere Schließ-Pfade?

→ Code-Check: `ui/settings_dialog.py` hat `_save_and_close()`
  (Z.~675) und Cancel-Button der `self.reject()` ruft. Signal nur
  in Save-Pfad → korrekt.

### SR3 — V1 erwähnt P56 aber P56 ist noch nicht geplant

V1 sagt „P56 Gain pro Band wird auch Live-Propagation brauchen".
Das ist Spekulation — P56 könnte stattdessen via Settings-Save
ohne Live-Trigger laufen (Gain wird beim nächsten Mess-Lauf eh
neu geladen). 

**Fix in V3:** P56-Referenz raus, oder nur als „möglich" markiert.

### SR4 — AC4 ist überflüssig

AC4: „Bestehender Connect-Hook bleibt unverändert" — das ist eh
Regression-Schutz, gehört in Test (T4) nicht in AC. Plus: V1 plant
keine Änderung in `mw_radio.py`, also redundant.

**Fix in V3:** AC4 raus, T4 bleibt.

### SR5 — T2 ist zu vage

T2 sagt „Slot ruft `radio.set_swr_limit()` mit aktuellem Settings-
Wert". Aber wie wird das getestet? Mock-Radio, Signal-emit,
assertEqual(mock.set_swr_limit.call_args[0][0], 1.5)?

**Fix in V3:** T2 konkret machen mit Mock-Pattern.

### SR6 — Diagnose-Print sollte temporär sein

Wenn wir Option A als Diagnose-Schritt machen, bleibt der Print
im Code? Nein — bei Code-Commit raus oder hinter ENV-Var-Gate
(SIMPLEFT8_P58_DBG=1).

**Empfehlung:** Diagnose-Print ENV-gated lassen, falls in Zukunft
ähnliche Bugs auftreten.

### SR7 — Was wenn weitere Live-Settings im Save-Hook stehen?

Code-Check: `ui/settings_dialog.py:680-683` ist NUR `swr_limit`-
Propagation. Aber `_save_and_close` setzt 20+ Settings (power_watts,
tx_level, max_calls, language, stats_enabled, ...). Davon brauchen
welche Live-Propagation?

→ `tx_level`: `radio.tx_audio_level = settings.get("tx_level", 100)/100`
  — wird das nach Save propagiert? Z.1063: `self.radio.tx_audio_level
  = ...` — ABER das ist in `_on_settings_clicked` NACH `dialog.exec()`,
  also nur wenn Dialog mit Save schloss. **Funktioniert heute.**

→ `power_preset`: Z.1067 `self.radio.set_power(...)` analog.
  **Funktioniert heute.**

→ `swr_limit`: war HIER der Sonderfall — wurde inline im Dialog
  propagiert statt im MainWindow nach Dialog.exec().

**Erkenntnis:** Die "richtige" Architektur existiert SCHON — alle
anderen Live-Settings werden NACH `dialog.exec()` in
`_on_settings_clicked` propagiert. **P53 hat nur den falschen Pfad
gewählt** (inline im Dialog).

→ **Fix ist viel einfacher als V1 dachte:** swr_limit-Setter-Call
in `_on_settings_clicked` nach Z.1067 verschieben. Kein Signal
nötig.

## V2-Empfehlung — Architektur-Konsistenz statt Signal-Pattern

**Update zur V1 — Option D (NEU):**

Inline-Code in `_save_and_close` raus. Stattdessen in
`_on_settings_clicked` nach `dialog.exec()` analog zu `tx_audio_level`
und `set_power`:

```python
# main_window.py:_on_settings_clicked
if dialog.exec():
    self._update_statusbar()
    self.qso_sm.max_calls = self.settings.get("max_calls", 3)
    self.radio.tx_audio_level = self.settings.get("tx_level", 100) / 100.0
    if self.radio.ip:
        self.radio.set_power(self.settings.get("power_preset", 15))
        self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))  # NEU
    ...
```

**Vorteile:**
- Konsistent zu allen anderen Live-Settings
- `self.radio` direkt zugänglich (KEIN parent-Lookup-Problem)
- `dialog.exec()` returned bool — Save vs. Cancel handled automatisch
- Kein neues Signal, kein Konstruktor-Eingriff
- 1 Zeile Code

**Nachteil:** keine

**Diagnose-Print** trotzdem temporär einbauen UM die Wurzel zu
dokumentieren bevor wir den alten Pfad raushauen:

```python
# settings_dialog.py:680-683 - temporär für Diagnose:
parent = self.parent()
print(f"[P58-DIAG] parent_type={type(parent).__name__ if parent else 'None'}, "
      f"has_radio={hasattr(parent, 'radio')}, "
      f"radio_ip={getattr(getattr(parent, 'radio', None), 'ip', 'no-attr')}")
# Dann original Code löschen
```

Mike testet 1× zur Bestätigung der Wurzel, dann Diagnose-Print
auch raus → finaler Zustand: Inline-Code in Dialog komplett weg,
Propagation in MainWindow.

## Aktualisierte Files

- `ui/settings_dialog.py:680-683` **löschen** (4 Zeilen Inline-
  Propagation komplett raus)
- `ui/main_window.py:_on_settings_clicked` **1 Zeile hinzu** unter
  bestehenden Setter-Calls

## Aktualisierte Tests (T2 konkret)

- **T1:** `_save_and_close` setzt nur `settings.set()`, KEIN
  Radio-Aufruf (Pure-Function-Test) → verifiziert via Mock-Radio
  dass `set_swr_limit` NICHT vom Dialog gerufen wird
- **T2:** `_on_settings_clicked` Integration — MockRadio mit
  `ip="1.2.3.4"`, Dialog.exec() mockt True, Save mit swr_limit=2.5,
  assert `mock_radio.set_swr_limit.called_once_with(2.5)`
- **T3:** `radio.ip is None` → `set_swr_limit` NICHT gerufen
  (Skip-Pfad)
- **T4:** Connect-Hook `mw_radio.py:179` unverändert (Regression)
- **T5:** Bestehende SWR-Watchdog-Tests grün (Final-R1-Schutz)
- **T6 NEU:** Cancel-Pfad (`dialog.exec()` returns False) →
  Setter NICHT gerufen

## Workflow weiter

V3 wird Option D dokumentieren (V1's A/B/C wurden durch Code-Check
obsolet — D ist die saubere Lösung). Final-R1-Vorlage nach Code.
