# P61 V3 — Auto-Hunt Recent-QSO-Cooldown (final, nach R1-V4-pro)

**Session:** 15.05.2026 vormittags · APP_VERSION 0.97.32 → 0.97.33 · Tests
1279 → ~1289 (+10)

## 1. Symptom + Wurzel (Kurz)

Auto-Hunt picked HA8RC 30s nach abgeschlossenem QSO erneut. Existierende
`qso_log.is_worked_on_band`-Filterung in `_score` (`core/auto_hunt.py:286`)
hat aus unbekannten Gründen versagt (Race oder ADIF-Exception denkbar,
nicht reproduzierbar). Fix: zusätzliche Cooldown-Schicht direkt in
`AutoHunt` mit Key `(base_call, band, mode)`, gefüllt sofort beim Pick.

## 2. R1-Findings eingearbeitet

| Finding | Status |
|---|---|
| F1 ROT — `AutoHunt._mode` fehlt | ✓ V3 ergänzt `_mode` + `set_mode` |
| F2 ORANGE — manueller QSO-Cover via `on_qso_complete` | ✓ explizit in Doku-Block |
| F3 GELB — Cooldown-Dicts zusammenlegen | ✗ abgelehnt: getrennt klarer und testbar |
| F4 ORANGE — Lazy-Cleanup-Zeile explizit | ✓ Code-Snippet unten |
| F5 ANT1-Pflicht unverändert | ✓ bestätigt |
| F6 — Tests T9+T10 optional | ✓ aufgenommen — Coverage stärker |
| F7 — try/except adif.log_qso | ✗ abgelehnt: Mike-Spec „ADIF-Fehler MUSS sichtbar sein", siehe V1 §5 |

## 3. Code-Plan (atomar)

### C1 — `core/auto_hunt.py`

**Konstante (oben im Modul, neben `_COOLDOWN_SECS`):**
```python
_RECENT_QSO_COOLDOWN_S = 300  # 5 Min Recent-QSO-Cooldown (P61, analog _LOG_DEDUP_WINDOW_S)
```

**`AutoHunt.__init__` Erweiterung:**
```python
self._mode: str = "FT8"       # P61: Mode-Tracking für Cooldown-Key
self._recent_qso: dict[tuple[str, str, str], float] = {}
# Schlüssel: (base_call, band, mode), Wert: time.time() beim Pick/QSO-Ende
```

**Neue Methode `set_mode`:**
```python
def set_mode(self, mode: str):
    """Aktueller FT-Modus für Cooldown-Key. Wird bei Mode-Wechsel gerufen."""
    self._mode = (mode or "FT8").upper()
```

**Neue Methode `mark_pick` (zentral, P61 Belt-and-Suspenders):**
```python
def mark_pick(self, call: str):
    """P61: Pick-Zeitpunkt-Cooldown. Verhindert dass Auto-Hunt eine
    Station, die gerade angerufen wurde, sofort wieder pickt — auch
    wenn qso_log.add_qso aus irgendeinem Grund nicht synchron läuft.

    Robust gegen:
    - Race Decoder-cycle_decoded vs Encoder-tx_finished
    - Exception in adif.log_qso überspringt qso_log.add_qso
    - Manuelle QSO-Pfade ohne Auto-Hunt-Logik
    """
    if not call:
        return
    base = call.strip().upper().split("/")[0]
    key = (base, self._band.upper(), self._mode.upper())
    self._recent_qso[key] = time.time()
```

**`select_next` — neuer Filter-Block VOR `_cooldown`-Check (~Z.222):**
```python
for msg in (messages or []):
    if not getattr(msg, 'is_cq', False):
        continue
    call = msg.caller
    if not call:
        continue
    base = call.strip().upper().split("/")[0]
    key = (base, self._band.upper(), self._mode.upper())

    # P61: Recent-QSO-Cooldown VOR Fail-Cooldown
    last_qso = self._recent_qso.get(key, 0)
    if now - last_qso < _RECENT_QSO_COOLDOWN_S:
        continue
    elif last_qso > 0:
        # Lazy-Cleanup — Eintrag abgelaufen, raus
        del self._recent_qso[key]

    # Bestehender Fail-Cooldown
    last_fail = self._cooldown.get(call, 0)
    if now - last_fail < _COOLDOWN_SECS:
        continue
    # ... bestehende SNR + candidate-Logik
```

**`on_qso_complete` Erweiterung (redundante Sicherung, R1-F2):**
```python
def on_qso_complete(self, call: str):
    self._current_target = None
    self._cooldown.pop(call, None)
    self.mark_pick(call)  # P61: redundant aber sichert manuelle QSO-Pfade
    print(f"[Auto-Hunt] QSO mit {call} fertig — Recent-Cooldown gesetzt")
```

### C2 — `ui/mw_cycle.py`

**`_run_auto_hunt` nach erfolgreichem `select_next`-Pick (~Z.498):**
```python
if not _candidate:
    return
# P61: Pick-Zeitpunkt SOFORT in _recent_qso eintragen,
# noch BEVOR start_qso aufgerufen wird. Schützt gegen Race
# zwischen tx_finished und nächstem cycle_decoded.
self._auto_hunt.mark_pick(_candidate.call)
self._active_qso_targets.add(_candidate.call)
# ... bestehender Pfad
```

### C3 — `ui/mw_radio.py` (Mode-Awareness)

**In `_on_mode_changed` (Mode-Wechsel-Handler) nach `set_mode`-Pfaden:**
```python
# P61: AutoHunt Mode-Awareness — Cooldown-Key trennt FT8/FT4/FT2
if hasattr(self, "_auto_hunt") and self._auto_hunt is not None:
    self._auto_hunt.set_mode(mode)
```

Falls die App in `main_window.py` initial Mode setzt, dort auch
`self._auto_hunt.set_mode(settings.mode)` direkt nach
`self._auto_hunt.set_band(settings.band)` (`main_window.py:333`).

### C4 — `tests/test_p61_autohunt_recent_qso.py` NEU

10 Tests (T1-T10):

- **T1** `select_next` direkt nach `mark_pick(call)` → None (cooldown greift)
- **T2** `select_next` 301s nach `mark_pick` → Pick erlaubt (cooldown abgelaufen, Eintrag gelöscht via Lazy-Cleanup)
- **T3** Band-Wechsel via `set_band("40m")` — selbes Call auf 40m sofort
  pickbar (Key ist `(call, band, mode)`)
- **T4** Mode-Wechsel via `set_mode("FT4")` — selbes Call auf FT4 sofort
  pickbar
- **T5** Base-Call-Normalisierung `HA8RC/P` → `HA8RC` (Mark + Filter
  matched)
- **T6** Source-Level: `_recent_qso` existiert in `core/auto_hunt.py`
- **T7** Race-Schutz: `mark_pick` direkt aufrufen + `select_next` → None
  ohne `on_qso_complete` zwischen drin
- **T8** Source-Level-Reihenfolge: `_recent_qso`-Check kommt VOR
  `_cooldown`-Check im `select_next`-Body
- **T9** `on_qso_complete(call)` ruft `mark_pick(call)` — manuelle QSO-
  Coverage (verifiziert via Mock auf `mark_pick`)
- **T10** Mode-Trennung — `mark_pick(call)` mit `_mode="FT8"`,
  `set_mode("FT4")`, `select_next` mit selber CQ-Msg → Pick erlaubt

### C5 — `main.py` APP_VERSION + Backup

- APP_VERSION `"0.97.32"` → `"0.97.33"`
- Backup `Appsicherungen/2026-05-15_v0.97.32_vor_p61/` (vollständige
  Sicherung)

### C6 — Doku (HISTORY/HANDOFF/CLAUDE.md/Memory/TODO/MEMORY.md)

- HISTORY.md `## 2026-05-15 v0.97.33 — P61 Auto-Hunt Recent-QSO-Cooldown`
- HANDOFF.md neuer Stand
- CLAUDE.md Header Aktueller-Stand
- TODO.md P61 als ERLEDIGT markieren
- Memory `project_p61_autohunt_recent_qso_cooldown.md` NEU
- MEMORY.md Index-Eintrag
- Plan-Files (V1+V2+V3+R1+Final-R1) committed

## 4. Risiko-Matrix

| Risiko | Bewertung | Mitigation |
|---|---|---|
| Legitimer Re-QSO blockt | niedrig | Manueller Klick umgeht Cooldown (separater Pfad) |
| Dict-Wachstum | trivial | Lazy-Cleanup + Hobby-Tool max ~50 QSOs/Tag |
| `_mode` initial nicht gesetzt | niedrig | Default `"FT8"`, kein None-Crash |
| Mode-Wechsel von Settings | mittel | C3 verkabelt `_on_mode_changed` |
| Test-Mock-Drift | niedrig | T9 mocked `mark_pick`, prüft nur Aufruf |

## 5. Hardware-Pflicht ANT1

Keine TX-Antennen-Logik berührt. P53-T5-Test (`set_tx_antenna` nicht im
Stop-Pfad) bleibt grün. ANT1-Pflicht unverändert.

## 6. Field-Test-Punkte für Mike

| F# | Was prüfen |
|---|---|
| F1 | QSO mit Station X auf Band Y → in 5 Min nicht erneut Auto-Hunt-Pick |
| F2 | Nach 5 Min QSO mit X kann erneut gepickt werden |
| F3 | Band Y→Z wechseln → X auf Z sofort pickbar (Cooldown Band-spezifisch) |
| F4 | Mode FT8→FT4 wechseln → X auf FT4 sofort pickbar (Cooldown Mode-spezifisch) |
| F5 | Manueller Klick auf X im RX-Panel innerhalb Cooldown → QSO startet sofort (Cooldown blockt NUR Auto-Hunt-Auto-Pick) |
| F6 | Regression P60-F2: Auto-Hunt-Toggle-Stop während TX bricht sofort ab |
| F7 | Regression P60-F4: HALT bricht alle TX weiterhin ab |

## 7. Aus Scope

- Wurzel-Diagnose von `is_worked_on_band`-Versagen (Folge-Untersuchung
  bei Bedarf)
- ADIF-Write-Exception-Handling (Mike-Spec: Fehler MUSS sichtbar sein)
- Vereinheitlichung `_cooldown` + `_recent_qso` (R1-F3 abgelehnt)
